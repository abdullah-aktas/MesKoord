"""Veri aktarım motoru.

Okunan her tablonun hangi veri türü olduğu (öğrenci listesi, işletme listesi, devamsızlık,
dekont vb.) başlıklarından tahmin edilir, sütunlar eş anlamlı başlıklarla eşleştirilir ve kayıtlar
ilişkileriyle birlikte işlenir: eksik sınıf, alan, işletme veya öğrenci gerekirse oluşturulur,
işletme değiştiren öğrencinin önceki yerleştirmesi kapatılır. Aktarım tek işlem (transaction)
içinde yapılır; deneme modunda hiçbir değişiklik kalıcı olmaz.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from ..mevzuat import AYLAR, GUNLER, OKUL_ICI_TURLER, YERLESTIRME_TURLERI
from . import okuyucu
from .okuyucu import Tablo
from .utils import ay_araligi, gunler_listesi, tarih as _tarih_temel, tc_gecerli

# ------------------------------------------------------------------ metin normalleştirme


def tr_kucuk(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def norm(s: Any) -> str:
    s = tr_kucuk(str(s or "").strip())
    s = s.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _ilk_buyuk(w: str) -> str:
    if not w:
        return w
    return ("İ" if w[0] == "i" else "I" if w[0] == "ı" else w[0].upper()) + w[1:]


def tr_ad(s: Any) -> str:
    """Tamamı büyük harfli adları ('AYŞE NUR IŞIK') Türkçe kurallarla düzeltir ('Ayşe Nur Işık')."""
    s = re.sub(r"\s+", " ", metin(s))
    if s and s.upper() == s and any(c.isalpha() for c in s):
        return " ".join("-".join(_ilk_buyuk(tr_kucuk(p)) for p in w.split("-")) for w in s.split(" "))
    return s


def metin(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, datetime):
        return v.strftime("%d.%m.%Y")
    return str(v).strip()


def sayi(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v))
    if not s or s in "-.,":
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", s):
        s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


_AY_NORM = {norm(a): i for i, a in enumerate(AYLAR, 1)}


def tarih(v: Any) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if 20000 < v < 80000:  # Excel seri tarih
            return date(1899, 12, 30) + timedelta(days=int(v))
        return None
    d = _tarih_temel(v)
    if d:
        return d
    s = str(v).strip()
    m = re.match(r"^(\d{1,2})[./\-](\d{1,2})[./\-](\d{2,4})", s)
    if m:
        g, a, y = (int(x) for x in m.groups())
        y += 2000 if y < 100 else 0
        try:
            return date(y, a, g)
        except ValueError:
            return None
    m = re.match(r"^(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})", s)
    if m:
        try:
            return date(*(int(x) for x in m.groups()))
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})\s+([^\s\d]+)\s+(\d{4})", s)
    if m and norm(m.group(2)) in _AY_NORM:
        try:
            return date(int(m.group(3)), _AY_NORM[norm(m.group(2))], int(m.group(1)))
        except ValueError:
            return None
    return None


def evet(v: Any, varsayilan: int | None = None) -> int | None:
    n = norm(v)
    if not n:
        return varsayilan
    if n in ("1", "e", "evet", "var", "x", "true", "yes", "olur", "uygun", "aktif"):
        return 1
    if n in ("0", "h", "hayir", "yok", "false", "no", "pasif"):
        return 0
    return varsayilan


def _devam_degeri(v: Any) -> float | None:
    """Devamsızlık hücresi: sayı (1 / 0,5), 'Yarım Gün' -> 0.5, 'X' / 'Tam Gün' -> 1."""
    n = norm(v)
    if not n:
        return None
    if "yarim" in n:
        return 0.5
    x = sayi(v)
    if x is not None:
        return x if 0 < x <= 31 else None
    return 1.0 if n in ("x", "var", "evet", "e", "tam", "tam gun", "v") else None


_GUN_NORM = {norm(g): i for i, g in enumerate(GUNLER, 1)}
_GUN_NORM.update({"pzt": 1, "pts": 1, "sal": 2, "car": 3, "crs": 3, "per": 4, "prs": 4, "cum": 5, "cmt": 6,
                  "cumartesi": 6, "paz": 7, "pazar": 7})


def gun_no(v: Any) -> int | None:
    n = norm(v)
    if not n:
        return None
    if n.isdigit() and 1 <= int(n) <= 7:
        return int(n)
    if n in _GUN_NORM:
        return _GUN_NORM[n]
    return _GUN_NORM.get(n[:3])


def gunler_coz(v: Any) -> str:
    """'Pazartesi, Salı' / 'Pzt-Sal' / '1,2' -> '1,2'."""
    if v is None or v == "":
        return ""
    out = {g for p in re.split(r"[,;/\-\s]+", metin(v)) if (g := gun_no(p))}
    return ",".join(str(g) for g in sorted(out))


def ay_coz(v: Any, varsayilan_yil: int | None = None) -> tuple[int, int] | None:
    """'2026-10', '10/2026', 'Ekim 2026', 'Ekim' -> (yıl, ay)."""
    if v is None or v == "":
        return None
    if isinstance(v, (datetime, date)):
        return v.year, v.month
    n = norm(v)
    yil = next((int(x) for x in re.findall(r"\b(20\d\d)\b", n)), varsayilan_yil)
    for ad, i in _AY_NORM.items():
        if ad in n.split():
            return (yil, i) if yil else None
    m = re.search(r"\b(20\d\d)\s+(\d{1,2})\b", n) or re.search(r"\b(\d{1,2})\s+(20\d\d)\b", n)
    if m:
        a, b = (int(x) for x in m.groups())
        y, a = (a, b) if a > 12 else (b, a)
        if 1 <= a <= 12:
            return y, a
    if n.isdigit() and 1 <= int(n) <= 12 and yil:
        return yil, int(n)
    return None


def sinif_adi(v: Any) -> str:
    """'11. Sınıf / A Şubesi', '11/A', '11 A', '11a' -> '11-A'. Tanınmazsa olduğu gibi döner."""
    ham = re.sub(r"\s+", " ", metin(v))
    t = re.sub(r"[./\\\-_()|:]+", " ", tr_kucuk(ham))
    t = re.sub(r"\b(sınıfı|sınıf|sinifi|sinif|şubesi|şube|subesi|sube)\b", " ", t)
    tok = t.split()
    for i, w in enumerate(tok):
        m = re.fullmatch(r"(\d{1,2})([a-zçğıöşü])", w)
        if m and 1 <= int(m.group(1)) <= 12:
            return f"{int(m.group(1))}-{_harf(m.group(2))}"
        if w.isdigit() and 1 <= int(w) <= 12 and i + 1 < len(tok) and re.fullmatch(r"[a-zçğıöşü]", tok[i + 1]):
            kalan = tok[i + 2:]
            # '11 A' ve '9-A Sınıfı Programı' -> 9-A. '9 T A' alan kodu (arkada tek harf) olduğu gibi kalır.
            if not kalan or all(len(x) > 1 for x in kalan):
                return f"{int(w)}-{_harf(tok[i + 1])}"
    return ham


def _harf(c: str) -> str:
    return "İ" if c == "i" else "I" if c == "ı" else c.upper()


def _seviye(ad: str) -> int:
    m = re.search(r"\b(9|10|11|12)\b", re.sub(r"[^\d]+", " ", ad))
    return int(m.group(1)) if m else 9


def ad_soyad_bol(s: str) -> tuple[str, str]:
    parca = s.split()
    if len(parca) <= 1:
        return s, ""
    return " ".join(parca[:-1]), parca[-1]


_SIRKET_EKLERI = {"ltd", "sti", "as", "a", "s", "san", "tic", "ve", "limited", "sirketi", "anonim", "ltdsti",
                  "sanayi", "ticaret", "insaat", "co", "inc"}


def isletme_anahtari(ad: str) -> str:
    tok = [t for t in norm(ad).split() if t not in _SIRKET_EKLERI]
    return " ".join(tok) or norm(ad)


# ------------------------------------------------------------------ belge bağlamı
# e-Okul/e-Mesem/e-Bildirge çıktılarında sınıf, dönem, belge türü, işletme gibi bilgiler çoğu zaman sütun olarak
# değil, tablonun üstünde ("Sınıfı : 11-A") veya gruplar arasında ara başlık satırı ("11-A SINIFI") olarak yer alır.

_BAGLAM_ETIKETLERI: dict[str, set[str]] = {
    "sinif": {"sinif", "sinifi", "sinif sube", "sinifi subesi", "sinif ve sube", "sinifi ve subesi", "sinif sube adi",
              "sinif adi", "sube adi", "sinif seviyesi sube"},
    "sube": {"sube", "subesi"},
    "seviye": {"sinif seviyesi", "seviye", "seviyesi"},
    "alan": {"alan", "alani", "meslek alani", "alan adi"},
    "dal": {"dal", "dali", "meslek dali", "dal adi"},
    "ay": {"donem", "donemi", "ay", "ayi", "yil ay", "hizmet donemi", "prim donemi", "bordro donemi", "odeme donemi",
           "ait oldugu ay", "ait oldugu donem", "belge donemi", "ucret donemi", "yil ay donem"},
    "belge_turu": {"belge turu", "belge turu kodu", "belge cesidi", "belge no"},
    "isletme": {"isletme", "isletme adi", "isletmenin adi", "isletme unvani", "isyeri", "isyeri adi", "isyeri unvani",
                "is yeri", "is yeri adi", "is yeri unvani", "firma", "firma adi"},
    "ogretmen": {"ogretmen", "ogretmeni", "ogretmen adi soyadi", "koordinator ogretmen", "koordinator ogretmeni",
                 "dersin ogretmeni", "ogretmenin adi soyadi"},
}
_BAGLAM_ETIKET = {e: k for k, kume in _BAGLAM_ETIKETLERI.items() for e in kume}
BAGLAM_ADLARI = {"sinif": "Sınıf/Şube", "alan": "Alan", "dal": "Dal", "ay": "Dönem", "belge_turu": "Belge Türü",
                 "isletme": "İşletme", "ogretmen": "Öğretmen"}


def _etiket_sonek(s: str, sozluk: dict[str, str] | None = None) -> tuple[str, str] | None:
    """Metnin sonundaki bilinen bağlam etiketi: '11-A   Alanı' -> ('alan', '11-A')."""
    w = s.split()
    for L in range(min(4, len(w)), 0, -1):
        k = (sozluk or _BAGLAM_ETIKET).get(norm(" ".join(w[-L:])))
        if k:
            return k, " ".join(w[:-L])
    return None


def _sinif_mi(s: str) -> str | None:
    ad = sinif_adi(s)
    return ad if re.fullmatch(r"\d{1,2}-\S", ad) else None


def _baglam_degeri(k: str, v: str) -> str | None:
    v = re.sub(r"\s+", " ", v).strip(" .-–/")
    if not v:
        return None
    if k == "ay":
        n = norm(v)
        if len(re.findall(r"\b20\d\d\b", n)) >= 2:  # öğretim yılı ("2026-2027"), ay değil
            return None
        a = ay_coz(v)
        return f"{a[0]}-{a[1]:02d}" if a else None
    if k == "belge_turu":
        m = re.match(r"\d{1,2}", v)
        return str(int(m.group())) if m else None
    if k in ("alan", "dal"):
        v = re.sub(r"\s+(alan[ıi]|dal[ıi])$", "", v, flags=re.I)
    if k == "sinif":
        return _sinif_mi(v) or v
    return v if len(v) <= 120 else None


def baglam_coz(hucreler: list[Any]) -> dict[str, str]:
    """Bir başlık/ara satırındaki bağlam bilgileri: {'sinif': '11-A', 'ay': '2026-10', 'belge_turu': '7', ...}."""
    parca: list[str] = []
    for h in hucreler:
        parca += [p.strip() for p in re.split(r"\s{3,}|\t|\n|\|", metin(h)) if p.strip()]
    ciftler: list[tuple[str, str]] = []
    serbest: list[str] = []
    i = 0
    while i < len(parca):
        p = parca[i]
        govde = p.rstrip(": ").strip()
        if ":" in govde:
            seg = govde.split(":")
            etiket = _etiket_sonek(seg[0])
            for k in range(1, len(seg)):
                deger = seg[k]
                sonraki = _etiket_sonek(deger) if k < len(seg) - 1 else None
                if sonraki:
                    deger = sonraki[1]
                if etiket:
                    ciftler.append((etiket[0], deger))
                etiket = sonraki
        elif norm(govde) in _BAGLAM_ETIKET and i + 1 < len(parca) and norm(parca[i + 1]) not in _BAGLAM_ETIKET:
            ciftler.append((_BAGLAM_ETIKET[norm(govde)], parca[i + 1].lstrip(": ")))
            i += 1
        else:
            serbest.append(p)
        i += 1
    out: dict[str, str] = {}
    sube = seviye = ""
    for k, v in ciftler:
        if k == "sube":
            sube = v.strip()
            continue
        if k == "seviye":
            seviye = norm(v).split(" ")[0]
            continue
        d = _baglam_degeri(k, v)
        if d and k not in out:
            out[k] = d
    sv = out.get("sinif", seviye)
    if sube and sv and norm(sv).isdigit():
        out["sinif"] = _sinif_mi(f"{norm(sv)} {sube}") or f"{sv}-{sube}"
    for p in serbest:
        n = norm(p)
        if "sinif" not in out and re.search(r"(^| )(sinif|sube)\w*", n) and (s := _sinif_mi(p)):
            out["sinif"] = s
        if "ay" not in out and len(re.findall(r"\b20\d\d\b", n)) == 1 and any(a in n.split() for a in _AY_NORM):
            d = _baglam_degeri("ay", p)
            if d:
                out["ay"] = d
    if not out and len(parca) == 1 and re.fullmatch(r"\d{1,2}\s*[-/.]?\s*[A-Za-zÇĞİÖŞÜçğıöşü]", parca[0]):
        out["sinif"] = _sinif_mi(parca[0]) or parca[0]
    return out


def _dolu_hucreler(row: list[Any]) -> list[Any]:
    return [h for h in row if metin(h)]


def satir_baglamlari(tablo: Tablo) -> dict[int, dict[str, str]]:
    """Bağlam bilgisi taşıyan satırlar {satır no: bağlam}: başlık üstü bilgiler ve ara başlık satırları."""
    if tablo.form:
        return {}
    onbellek = getattr(tablo, "_baglam_onbellek", None)
    if onbellek is not None and onbellek[0] == len(tablo.satirlar):
        return onbellek[1]
    out: dict[int, dict[str, str]] = {}
    for i, row in enumerate(tablo.satirlar):
        dolu = _dolu_hucreler(row)
        if not dolu or len(dolu) > 8:
            continue
        etiketli = sum(1 for h in dolu if ":" in metin(h) or norm(metin(h).rstrip(": ")) in _BAGLAM_ETIKET)
        if len(dolu) > 2 and etiketli * 2 < len(dolu):
            continue
        b = baglam_coz(dolu)
        if b:
            out[i] = b
    try:
        tablo._baglam_onbellek = (len(tablo.satirlar), out)
    except AttributeError:
        pass
    return out


def baglam_ozeti(tablo: Tablo) -> str:
    """'Sınıf/Şube: 11-A, 11-B; Dönem: 2026-10' (belgede başlık/ara satırlardan okunan bilgiler)."""
    degerler: dict[str, list[str]] = {}
    for b in satir_baglamlari(tablo).values():
        for k, v in b.items():
            if k in BAGLAM_ADLARI and v not in degerler.setdefault(k, []):
                degerler[k].append(v)
    return "; ".join(f"{BAGLAM_ADLARI[k]}: {', '.join(v[:4])}{' …' if len(v) > 4 else ''}"
                     for k, v in degerler.items())


def on_baglam(tablo: Tablo, bas: int) -> dict[str, str]:
    """Başlık satırından önceki bağlam bilgileri (yakındaki satır öncelikli)."""
    out: dict[str, str] = {}
    for i, b in sorted(satir_baglamlari(tablo).items()):
        if i < bas:
            out.update(b)
    return out


# e-Okul ayrıntılı devamsızlık raporunda (OOK08001R060) tarihler öğrenci başına gruplanır: öğrenci bilgisi ya bir ara
# satırda ("Öğrenci No: 501  Adı Soyadı: ÇAĞLA ÖZTÜRK") ya da grubun yalnızca ilk satırında yazar.
_OGRENCI_BASLIK_ETIKETLERI = {
    "okul_no": {"ogrenci no", "okul no", "ogrenci numarasi", "okul numarasi", "ogr no", "numarasi"},
    "ad_soyad": {"adi soyadi", "ad soyad", "ad soyadi", "ogrenci adi soyadi", "ogrencinin adi soyadi", "ogrenci"},
    "tc": {"tc kimlik no", "t c kimlik no", "tc no", "t c no", "kimlik no", "tc kimlik numarasi"},
}
_OGRENCI_BASLIK = {**_BAGLAM_ETIKET, **{e: k for k, kume in _OGRENCI_BASLIK_ETIKETLERI.items() for e in kume}}
_GRUPLU_TURLER = ("devamsizlik",)


def ogrenci_basligi(row: list[Any]) -> dict[str, str]:
    """Öğrenci grup başlığı satırındaki kimlik bilgileri: {'okul_no': '501', 'ad_soyad': 'ÇAĞLA ÖZTÜRK'}."""
    dolu = _dolu_hucreler(row)
    if not dolu or len(dolu) > 8:
        return {}
    parca: list[str] = []
    for h in dolu:
        parca += [p.strip() for p in re.split(r"\s{3,}|\t|\n|\|", metin(h)) if p.strip()]
    out: dict[str, str] = {}

    def ekle(k: str, v: str) -> None:
        v = re.sub(r"\s+", " ", v).strip(" .-–/:")
        if k in _OGRENCI_BASLIK_ETIKETLERI and v and k not in out:
            out[k] = v

    for i, p in enumerate(parca):
        seg = p.split(":")
        if len(seg) > 1:
            etiket = _etiket_sonek(seg[0], _OGRENCI_BASLIK)
            for k in range(1, len(seg)):
                deger = seg[k]
                sonraki = _etiket_sonek(deger, _OGRENCI_BASLIK) if k < len(seg) - 1 else None
                if sonraki:
                    deger = sonraki[1]
                if etiket:
                    ekle(etiket[0], deger)
                etiket = sonraki
        elif norm(p) in _OGRENCI_BASLIK and i + 1 < len(parca) and norm(parca[i + 1]) not in _OGRENCI_BASLIK:
            k, v = _OGRENCI_BASLIK[norm(p)], parca[i + 1]
            if (any(c.isdigit() for c in v) if k != "ad_soyad" else len(v.split()) >= 2 and not tarih(v)):
                ekle(k, v)
    if not out and len(parca) == 1:
        m = re.fullmatch(r"(\d{1,6})\s*[-–.)/]?\s+([^\d:]{3,60})", parca[0])
        if m:
            out = {"okul_no": m.group(1), "ad_soyad": m.group(2).strip()}
    if "okul_no" in out and not re.fullmatch(r"[\w\-/]{1,12}", out["okul_no"]):
        out.pop("okul_no")
    return out if {"okul_no", "ad_soyad", "tc"} & set(out) else {}


def ogrenci_basliklari(tablo: Tablo) -> dict[int, dict[str, str]]:
    """Öğrenci grup başlığı satırları {satır no: kimlik}."""
    if tablo.form:
        return {}
    onbellek = getattr(tablo, "_ogrenci_onbellek", None)
    if onbellek is not None and onbellek[0] == len(tablo.satirlar):
        return onbellek[1]
    out = {i: b for i, row in enumerate(tablo.satirlar) if (b := ogrenci_basligi(row))}
    try:
        tablo._ogrenci_onbellek = (len(tablo.satirlar), out)
    except AttributeError:
        pass
    return out


# ------------------------------------------------------------------ tanımlar

A = tuple[str, str, list[str]]

_OGRENCI: list[A] = [
    ("tc", "Öğrenci T.C. Kimlik No", ["tc", "tc kimlik no", "tc kimlik", "tckn", "kimlik no", "tc no", "tcno",
                                      "tc kimlik numarasi", "ogrenci tc", "ogrenci tc kimlik no", "tc numarasi",
                                      "kimlik numarasi", "ogrencinin tc kimlik no", "sigortali tc kimlik no",
                                      "sigortalinin tc kimlik no", "sigortali tc", "cirak tc kimlik no"]),
    ("okul_no", "Okul No", ["okul no", "ogrenci no", "no", "numara", "okul numarasi", "ogr no", "ogrenci numarasi",
                            "numarasi", "okul nosu", "ogrenci okul no"]),
    ("ad", "Adı", ["ad", "adi", "ogrenci adi", "ogrencinin adi", "isim", "ismi", "sigortalinin adi", "sigortali adi",
                   "cirak adi", "kursiyer adi"]),
    ("soyad", "Soyadı", ["soyad", "soyadi", "ogrenci soyadi", "ogrencinin soyadi", "soyisim", "soyismi",
                         "sigortalinin soyadi", "sigortali soyadi", "cirak soyadi", "kursiyer soyadi"]),
    ("ad_soyad", "Adı Soyadı", ["adi soyadi", "ad soyad", "ad soyadi", "adi ve soyadi", "ogrenci adi soyadi",
                                "ogrencinin adi soyadi", "ogrenci", "ogrenci ad soyad", "isim soyisim",
                                "ad ve soyad", "ogrencinin adi ve soyadi", "adsoyad", "cirak adi soyadi",
                                "aday cirak adi soyadi", "kursiyer adi soyadi", "sigortalinin adi soyadi",
                                "sigortali adi soyadi", "cirak", "kursiyer"]),
    ("sinif", "Sınıf/Şube", ["sinif", "sinifi", "sube", "sinif sube", "sinif ve sube", "sinifi subesi",
                             "sinif sube adi", "subesi", "sinifi ve subesi", "sinif seviyesi sube"]),
]
_OGRETMEN_REF: A = ("ogretmen", "Öğretmen Adı Soyadı",
                    ["ogretmen", "ogretmen adi soyadi", "ogretmeni", "ogretmenin adi soyadi", "koordinator",
                     "koordinator ogretmen", "koordinator ogretmen adi soyadi", "dersin ogretmeni",
                     "koordinator ogretmeni", "sorumlu ogretmen", "ogretmen ad soyad", "personel adi soyadi"])
_ISLETME_REF: A = ("isletme", "İşletme Adı",
                   ["isletme", "isletme adi", "isletmenin adi", "firma", "firma adi", "isyeri", "isyeri adi",
                    "isletme unvani", "staj yeri", "beceri egitimi yeri", "isletmenin unvani", "isletme ismi",
                    "egitim yeri", "kurum isletme adi", "isletme kurum adi", "is yeri", "is yeri adi",
                    "is yeri unvani", "isyeri unvani", "calistigi isyeri", "calistigi is yeri",
                    "egitim gordugu isletme", "mesleki egitim yeri", "beceri egitim yeri", "isletme firma adi"])
_ALAN: A = ("alan", "Alan", ["alan", "alani", "meslek alani", "alan adi"])
_DAL: A = ("dal", "Dal", ["dal", "dali", "meslek dali", "dal adi"])


@dataclass
class IceAktarmaTanimi:
    tablo: str
    etiket: str
    alanlar: list[A]
    zorunlu: list[list[str]] = field(default_factory=list)  # en az bir grubu tam olmalı
    agirlik: dict[str, float] = field(default_factory=dict)
    ipucu: list[str] = field(default_factory=list)
    isleyici: str = ""
    sira: int = 50
    tarih_etiketi: str = ""
    aciklama: str = ""

    @property
    def anahtar(self) -> str:
        return self.tablo

    def baslik(self, k: str) -> str:
        return next((g for a, g, _ in self.alanlar if a == k), k)


TANIMLAR: dict[str, IceAktarmaTanimi] = {t.tablo: t for t in [
    IceAktarmaTanimi("ogretmenler", "Öğretmenler", [
        ("tc", "T.C. Kimlik No", ["tc", "tc kimlik no", "tckn", "kimlik no", "tc no", "tc kimlik numarasi"]),
        ("ad", "Adı", ["ad", "adi", "personel adi"]),
        ("soyad", "Soyadı", ["soyad", "soyadi", "personel soyadi"]),
        ("ad_soyad", "Adı Soyadı", ["adi soyadi", "ad soyad", "ad soyadi", "personel adi soyadi", "ogretmen",
                                    "ogretmen adi soyadi", "adi ve soyadi", "personel"]),
        ("brans", "Branş", ["brans", "bransi", "alan brans", "brans adi", "kadro bransi"]),
        _ALAN,
        ("unvan", "Unvan / Görev", ["unvan", "unvani", "gorevi", "kadro unvani", "gorev", "gorev unvani"]),
        ("telefon", "Telefon", ["telefon", "cep telefonu", "gsm", "cep", "tel"]),
        ("eposta", "E-posta", ["eposta", "e posta", "mail", "e mail", "mail adresi"]),
        ("koordinator", "Koordinatör (E/H)", ["koordinator", "koordinatorluk", "koordinator mu"]),
        ("musait_olmayan", "Müsait Olmadığı Zamanlar", ["musait olmadigi gunler", "musait olmadigi gun",
                                                        "musait olmadigi zamanlar", "musait olmadigi saatler",
                                                        "musait olmayan", "musait degil", "bos gun", "bos gunu",
                                                        "bos gun istegi", "bos gunler", "izinli gun", "izin gunu",
                                                        "istenmeyen gunler", "istenmeyen saatler", "kapali gunler",
                                                        "ders verilmeyecek gunler", "ders konmayacak gunler"]),
        ("nobet_gun", "Nöbet Günü", ["nobet gunu", "nobet gun"]),
        ("nobet_yeri", "Nöbet Yeri", ["nobet yeri"]),
        ("sinif_ogretmenligi", "Sınıf Öğretmenliği", ["sinif ogretmenligi", "sinif ogretmenlik kodu"]),
    ], [["ad", "soyad"], ["ad_soyad"]], {"brans": 3, "unvan": 3, "eposta": 1.5, "koordinator": 2,
                                         "musait_olmayan": 3, "nobet_gun": 2, "sinif_ogretmenligi": 2},
        ["ogretmen", "personel", "kadro"], "ogretmen", 10),
    IceAktarmaTanimi("isletmeler", "İşletmeler", [
        ("ad", "İşletme Adı", _ISLETME_REF[2] + ["kurum adi"]),
        ("vergi_no", "Vergi No", ["vergi no", "vergi numarasi", "vkn", "vergi kimlik no", "tc vergi no"]),
        ("vergi_dairesi", "Vergi Dairesi", ["vergi dairesi"]),
        ("sgk_sicil", "SGK İşyeri Sicil No", ["sgk sicil", "sgk sicil no", "isyeri sicil no", "sgk isyeri sicil no",
                                              "sicil no"]),
        ("yetkili", "Yetkili / İşveren", ["yetkili", "yetkili adi", "isveren", "isletme yetkilisi", "yetkili kisi",
                                          "isveren vekili", "yetkili adi soyadi"]),
        ("telefon", "Telefon", ["telefon", "tel", "isletme telefonu", "telefon no"]),
        ("eposta", "E-posta", ["eposta", "e posta", "mail"]),
        ("adres", "Adres", ["adres", "isletme adresi", "acik adres", "isletmenin adresi"]),
        ("ilce", "İlçe", ["ilce"]),
        ("guzergah", "Güzergah", ["guzergah", "bolge", "rota", "semt"]),
        ("mesafe_km", "Okula Uzaklık (km)", ["mesafe", "mesafe km", "uzaklik", "okula uzaklik km", "okula uzaklik",
                                             "km"]),
        ("personel_sayisi", "Personel Sayısı", ["personel sayisi", "calisan sayisi", "personel", "isci sayisi",
                                                "calisan"]),
        ("usta_ogretici", "Usta Öğretici / Eğitici Personel", ["usta ogretici", "egitici personel",
                                                               "usta ogretici egitici personel", "usta ogretici adi"]),
        ("usta_ogretici_tel", "Usta Öğretici Tel", ["usta ogretici tel", "egitici personel tel",
                                                    "usta ogretici telefonu"]),
        ("iban", "IBAN", ["iban", "iban no"]),
        _ALAN,
        ("kontenjan", "Kontenjan", ["kontenjan", "ogrenci kontenjani", "kapasite"]),
        ("kamu_kurumu", "Kamu Kurumu (E/H)", ["kamu", "kamu kurumu", "kamu kurumu mu"]),
    ], [["ad"]], {"vergi_no": 3, "sgk_sicil": 3, "yetkili": 2, "usta_ogretici": 3, "personel_sayisi": 2,
                  "kontenjan": 2, "kamu_kurumu": 2, "vergi_dairesi": 3},
        ["isletme", "firma", "isyeri"], "isletme", 11),
    IceAktarmaTanimi("siniflar", "Sınıflar / Şubeler", [
        ("ad", "Sınıf/Şube", ["sinif", "sube", "sinif sube", "sinif adi", "sube adi", "sinifi"]),
        ("seviye", "Seviye", ["seviye", "sinif seviyesi"]),
        ("program", "Program (MTAL-AMP/MTAL-AMP-11/MTAL-ATP/MEM)", ["program", "program turu", "egitim programi"]),
        _ALAN, _DAL,
        ("okul_gunleri", "Okul Günleri", ["okul gunleri", "okul gunu", "okulda oldugu gunler"]),
        ("isletme_gunleri", "İşletme Günleri", ["isletme gunleri", "isletme gunu", "isletmede oldugu gunler",
                                                "beceri egitimi gunleri"]),
        ("rehber", "Rehber Öğretmen", ["rehber ogretmen", "sinif rehber ogretmeni", "rehber"]),
    ], [["ad", "okul_gunleri"], ["ad", "isletme_gunleri"], ["ad", "seviye"], ["ad", "rehber"], ["ad", "program"]],
        {"okul_gunleri": 3, "isletme_gunleri": 3, "rehber": 2, "seviye": 2, "program": 2},
        ["sinif", "sube"], "sinif", 12),
    IceAktarmaTanimi("atolyeler", "Atölye / Laboratuvarlar", [
        ("ad", "Atölye/Lab. Adı", ["atolye", "atolye adi", "laboratuvar", "laboratuvar adi", "derslik", "atolye lab"]),
        ("tur", "Tür", ["tur", "turu"]),
        _ALAN,
        ("kapasite", "Kapasite", ["kapasite", "ogrenci kapasitesi"]),
    ], [["ad", "kapasite"], ["ad", "tur"]], {"kapasite": 3, "ad": 2}, ["atolye", "laboratuvar"], "atolye", 13),
    IceAktarmaTanimi("dersler", "Dersler", [
        ("ad", "Ders Adı", ["ders", "ders adi", "dersin adi"]),
        ("kisa_ad", "Kısa Ad", ["kisa ad", "kisaltma", "kod"]),
        _ALAN,
        ("tur", "Tür (Kültür/Meslek/Atölye)", ["tur", "ders turu", "dersin turu"]),
        ("atolye_gerekli", "Atölye Gerekli (E/H)", ["atolye gerekli", "atolye", "laboratuvar", "atolyede"]),
        ("blok", "Blok Saat", ["blok", "blok saat"]),
    ], [["ad"]], {"kisa_ad": 2, "atolye_gerekli": 2, "blok": 1.5, "tur": 1.5}, ["ders"], "ders", 14),
    IceAktarmaTanimi("ogrenciler", "Öğrenciler / Çıraklar", _OGRENCI + [
        ("dogum_tarihi", "Doğum Tarihi", ["dogum tarihi", "d tarihi", "dogum t"]),
        ("cinsiyet", "Cinsiyet", ["cinsiyet", "cinsiyeti"]),
        ("statu", "Statü", ["statu", "ogrenci statusu", "ogrenim durumu", "durumu"]),
        ("bakmakla_yukumlu", "Bakmakla Yükümlü (E/H)", ["bakmakla yukumlu", "bakmakla yukumlu olunan", "gss",
                                                         "genel saglik sigortasi", "aile sigortasi"]),
        ("veli_ad", "Veli Adı Soyadı", ["veli adi", "veli", "veli adi soyadi", "velinin adi soyadi", "veli ad soyad"]),
        ("veli_tel", "Veli Telefon", ["veli tel", "veli telefon", "veli telefonu", "veli cep", "veli cep telefonu",
                                      "veli gsm"]),
        ("telefon", "Telefon", ["telefon", "cep telefonu", "ogrenci tel", "ogrenci telefonu", "cep", "gsm"]),
        ("iban", "IBAN", ["iban", "iban no", "ogrenci iban"]),
        ("adres", "Adres", ["adres", "ev adresi", "ikamet adresi"]),
        ("basari_ortalamasi", "Yılsonu Başarı Ortalaması", ["yilsonu basari ortalamasi", "yil sonu basari ortalamasi",
                                                           "basari ortalamasi", "yilsonu basari puani",
                                                           "yil sonu basari puani", "ybp"]),
        ("baba_adi", "Baba Adı", ["baba adi", "babasinin adi", "baba ismi"]),
        ("anne_adi", "Anne Adı", ["anne adi", "ana adi", "annesinin adi", "anasinin adi", "anne ismi"]),
        ("dogum_yeri", "Doğum Yeri", ["dogum yeri", "d yeri", "dogdugu yer"]),
        ("nufus_il", "Nüfusa Kayıtlı İl", ["nufusa kayitli oldugu il", "nufusa kayitli il", "nufus ili", "nufus il",
                                           "kayitli oldugu il", "nufus kayit ili"]),
        ("nufus_ilce", "Nüfusa Kayıtlı İlçe", ["nufusa kayitli oldugu ilce", "nufusa kayitli ilce", "nufus ilcesi",
                                               "nufus ilce", "kayitli oldugu ilce", "nufus kayit ilcesi"]),
        _ALAN, _DAL,
    ], [["ad", "soyad"], ["ad_soyad"]], {"okul_no": 2, "veli_ad": 3, "veli_tel": 3, "dogum_tarihi": 2, "sinif": 2,
                                         "bakmakla_yukumlu": 2, "statu": 1.5, "baba_adi": 2, "anne_adi": 2,
                                         "dogum_yeri": 2, "nufus_il": 2, "nufus_ilce": 2},
        ["ogrenci", "sinif listesi", "e okul", "cirak", "kunye", "nufus", "yuz yuze", "maol", "acik lise"],
        "ogrenci", 20,
        aciklama="e-Okul şube listesi, doğum tarihi raporu (00G01001R070), künye defteri (00G01001R094) ve MAOL "
                 "yüz yüze eğitim öğrenci listesi de bu türle aktarılır; dosyadaki dolu bilgiler mevcut öğrenciye "
                 "işlenir."),
    IceAktarmaTanimi("ders_atamalari", "Ders Dağılımı (Sınıf-Ders-Öğretmen)", [
        ("sinif", "Sınıf/Şube", ["sinif", "sube", "sinif sube", "sinifi"]),
        ("ders", "Ders Adı", ["ders", "ders adi", "dersin adi"]),
        _OGRETMEN_REF,
        ("haftalik_saat", "Haftalık Saat", ["saat", "haftalik saat", "ders saati", "hds", "haftalik ders saati",
                                            "saati"]),
        ("blok", "Blok", ["blok", "blok saat"]),
        ("atolye", "Atölye/Lab.", ["atolye", "laboratuvar", "derslik", "atolye lab"]),
        ("ogretmen2", "2. Öğretmen (grup/ortak ders)", ["2 ogretmen", "ikinci ogretmen", "ogretmen 2",
                                                         "yardimci ogretmen", "ortak ogretmen", "2 grup ogretmeni",
                                                         "ikinci grup ogretmeni"]),
        ("atolye2", "2. Atölye/Lab. (2. grup)", ["2 atolye", "ikinci atolye", "atolye 2", "2 grup atolyesi",
                                                 "ikinci grup atolyesi", "2 laboratuvar", "2 derslik"]),
        ("birlestirme", "Birleştirme Grubu", ["birlestirme", "birlestirme grubu", "birlestirilmis", "birlesik sinif",
                                              "birlestirilen siniflar", "ortak ders grubu"]),
    ], [["sinif", "ders", "haftalik_saat"]], {"ders": 2, "haftalik_saat": 2, "ogretmen": 2, "ogretmen2": 2,
                                              "atolye2": 2, "birlestirme": 2},
        ["ders dagilim", "dagilim", "ders yuku"], "atama", 30),
    IceAktarmaTanimi("program_hucreleri", "Haftalık Ders Programı (Gün-Saat)", [
        ("sinif", "Sınıf/Şube", ["sinif", "sube", "sinif sube", "sinifi"]),
        ("gun", "Gün", ["gun", "gunu", "ders gunu", "haftanin gunu"]),
        ("saat", "Ders Saati (1, 2, ...)", ["ders saati", "saat", "kacinci saat", "saat no", "ders no", "ders sirasi",
                                             "saati"]),
        ("ders", "Ders Adı", ["ders", "ders adi", "dersin adi"]),
        ("kisa_ad", "Kısa Ad", ["kisa ad", "kisaltma", "ders kodu", "dersin kodu"]),
        _OGRETMEN_REF,
        ("ogretmen2", "2. Öğretmen (grup/ortak ders)", ["2 ogretmen", "ikinci ogretmen", "ogretmen 2",
                                                         "yardimci ogretmen", "ortak ogretmen"]),
        ("atolye", "Atölye/Lab./Derslik", ["atolye", "laboratuvar", "derslik", "atolye lab", "mekan", "yer"]),
    ], [["sinif", "gun", "saat", "ders"]], {"gun": 4, "saat": 2, "ders": 2, "ogretmen": 2, "kisa_ad": 1,
                                            "ogretmen2": 1},
        ["ders programi", "haftalik program", "haftalik ders"], "program_hucresi", 31,
        aciklama="Belgedeki her ders saati programa kilitli olarak yazılır; ders dağılımı (haftalık saat, öğretmen) "
                 "kendiliğinden oluşur. Otomatik yerleştirme yalnızca kalan saatleri doldurur."),
    IceAktarmaTanimi("yerlestirmeler", "İşletme Yerleştirmeleri (Öğrenci-İşletme)", _OGRENCI + [
        _ISLETME_REF,
        ("vergi_no", "İşletme Vergi No", ["vergi no", "vergi numarasi", "vkn"]),
        ("isletme_adres", "İşletme Adresi", ["isletme adresi", "isletmenin adresi", "adres"]),
        ("isletme_tel", "İşletme Telefonu", ["isletme telefonu", "isletme tel", "telefon"]),
        ("yetkili", "İşletme Yetkilisi", ["yetkili", "isveren", "isletme yetkilisi"]),
        ("usta_ogretici", "Usta Öğretici", ["usta ogretici", "egitici personel"]),
        ("usta_ogretici_tel", "Usta Öğretici Tel", ["usta ogretici tel", "usta ogretici telefonu",
                                                     "egitici personel tel", "usta ogretici telefon"]),
        ("personel_sayisi", "İşletme Personel Sayısı", ["personel sayisi", "calisan sayisi"]),
        ("tur", "Eğitim Türü", ["tur", "egitim turu", "yerlestirme turu"]),
        ("baslangic", "Başlangıç Tarihi", ["baslangic", "baslama tarihi", "baslangic tarihi", "ise baslama tarihi",
                                           "giris tarihi", "isletmeye baslama tarihi", "sozlesme baslangic tarihi",
                                           "sozlesme baslama tarihi", "egitime baslama tarihi",
                                           "isyerine baslama tarihi", "is yerine baslama tarihi"]),
        ("bitis", "Bitiş Tarihi", ["bitis", "bitis tarihi", "ayrilis tarihi", "sozlesme bitis tarihi",
                                   "fesih tarihi", "sozlesme fesih tarihi", "ayrilma tarihi"]),
        ("sozlesme_no", "Sözleşme No", ["sozlesme no", "sozlesme numarasi", "sozlesme sayisi"]),
        ("sozlesme_tarihi", "Sözleşme Tarihi", ["sozlesme tarihi", "sozlesme imza tarihi", "sozlesme onay tarihi"]),
        ("ucret", "Aylık Ücret", ["ucret", "aylik ucret", "ogrenci ucreti", "odenecek ucret"]),
    ], [["isletme", "tc"], ["isletme", "okul_no"], ["isletme", "ad_soyad"], ["isletme", "ad", "soyad"]],
        {"isletme": 4, "baslangic": 2, "sozlesme_no": 3, "usta_ogretici": 1.5, "vergi_no": 1.5},
        ["yerlestirme", "isletme ogrenci", "beceri egitimi", "staj"], "yerlestirme", 40,
        "Başlangıç tarihi (dosyada yoksa)"),
    IceAktarmaTanimi("koordinator_gorevleri", "Koordinatörlük Görevleri", [
        _OGRETMEN_REF, _ISLETME_REF,
        ("gun", "Gün", ["gun", "gorev gunu", "ziyaret gunu", "gunu"]),
        ("haftalik_saat", "Haftalık Saat", ["saat", "haftalik saat", "ders saati"]),
        ("baslangic", "Başlangıç", ["baslangic", "baslangic tarihi"]),
        ("bitis", "Bitiş", ["bitis", "bitis tarihi"]),
    ], [["ogretmen", "isletme", "gun"]], {"gun": 3, "ogretmen": 2, "isletme": 2},
        ["koordinator", "gorevlendirme"], "koordinator", 45),
    IceAktarmaTanimi("devamsizlik", "Devamsızlık", _OGRENCI + [
        ("tarih", "Tarih", ["tarih", "devamsizlik tarihi", "gun tarihi", "devamsiz oldugu tarih"]),
        ("tur", "Tür (Özürsüz/Özürlü/Raporlu/İzinli)", ["tur", "devamsizlik turu", "ozur durumu", "durum"]),
        ("yer", "Yer (Okul/İşletme)", ["yer", "devamsizlik yeri"]),
        ("gun", "Gün", ["gun", "gun sayisi", "devamsizlik gun", "suresi", "sure", "devamsizlik suresi"]),
        ("ozursuz", "Özürsüz (toplam)", ["ozursuz", "ozursuz devamsizlik", "ozursuz gun", "toplam ozursuz"]),
        ("ozurlu", "Özürlü (toplam)", ["ozurlu", "ozurlu devamsizlik", "ozurlu gun", "toplam ozurlu"]),
        ("aciklama", "Açıklama", ["aciklama", "not"]),
    ], [["tarih", "tc"], ["tarih", "okul_no"], ["tarih", "ad_soyad"], ["tarih", "ad", "soyad"],
        ["ozursuz", "okul_no"], ["ozursuz", "tc"], ["ozursuz", "ad_soyad"], ["ozurlu", "okul_no"]],
        {"ozursuz": 4, "ozurlu": 4, "tarih": 2, "yer": 2, "gun": 1.5},
        ["devamsiz", "devam"], "devamsizlik", 50, "Devamsızlık tarihi (dosyada yoksa)",
        "e-Okul toplam devamsızlık listeleri yıllık toplam kabul edilir ve önceki toplu kayıtların yerine geçer."),
    IceAktarmaTanimi("beceri_notlari", "İşletmede Mesleki Eğitim Notları", _OGRENCI + [
        ("donem", "Dönem", ["donem", "yariyil"]),
        ("isletme_notu", "İşletme Notu", ["isletme notu", "isletme puani", "usta ogretici notu", "isletme degerlendirme"]),
        ("koordinator_notu", "Koordinatör Notu", ["koordinator notu", "koordinator puani", "ogretmen notu"]),
        ("tarih", "Tarih", ["tarih", "degerlendirme tarihi"]),
        ("aciklama", "Açıklama", ["aciklama", "gorus"]),
    ], [["isletme_notu"], ["koordinator_notu"]], {"isletme_notu": 4, "koordinator_notu": 4},
        ["not", "beceri", "degerlendirme"], "beceri", 51),
    IceAktarmaTanimi("tatiller", "Tatil Günleri", [
        ("ad", "Tatil Adı", ["tatil", "tatil adi", "aciklama", "ad", "resmi tatil", "bayram"]),
        ("baslangic", "Başlangıç", ["baslangic", "baslangic tarihi", "tarih", "ilk gun"]),
        ("bitis", "Bitiş", ["bitis", "bitis tarihi", "son gun"]),
    ], [["ad", "baslangic"]], {"ad": 2}, ["tatil", "takvim"], "tatil", 15),
    IceAktarmaTanimi("ek_ders_kayitlari", "Elle Ek Ders Kayıtları", [
        _OGRETMEN_REF,
        ("tarih", "Tarih", ["tarih"]),
        ("tur", "Tür (Gündüz/Gece/Nöbet/DYK…)", ["tur", "ek ders turu", "gorev turu"]),
        ("saat", "Saat", ["saat", "ek ders saati", "sure"]),
        ("aciklama", "Açıklama", ["aciklama"]),
    ], [["ogretmen", "tarih", "saat"]], {"saat": 1.5, "tur": 2}, ["ek ders", "nobet", "dyk"], "ekders", 60),
    IceAktarmaTanimi("ziyaretler", "İşletme Ziyaretleri", [
        _OGRETMEN_REF, _ISLETME_REF,
        ("tarih", "Ziyaret Tarihi", ["tarih", "ziyaret tarihi"]),
        ("durum", "Durum", ["durum", "ziyaret durumu", "yapildi mi"]),
        ("tespitler", "Tespitler", ["tespitler", "tespit", "gorusler", "aciklama"]),
        ("oneriler", "Öneriler", ["oneriler", "oneri"]),
    ], [["isletme", "tarih"]], {"tespitler": 3, "oneriler": 3, "durum": 2, "tarih": 1.5},
        ["ziyaret", "rehberlik"], "ziyaret", 61),
    IceAktarmaTanimi("dekontlar", "Ücret Dekontları (işletme ödemeleri)", _OGRENCI + [
        ("donem", "Dönem (Ay/Yıl)", ["donem", "ay", "odeme donemi", "ucret donemi", "hangi ay"]),
        ("yil", "Yıl", ["yil"]),
        ("odenen", "Ödenen Tutar", ["odenen", "odenen ucret", "tutar", "odeme tutari", "dekont tutari",
                                    "yatirilan tutar", "odenen tutar", "yatirilan ucret"]),
        ("dekont_tarihi", "Dekont / Ödeme Tarihi", ["dekont tarihi", "odeme tarihi", "islem tarihi", "tarih"]),
    ], [["odenen", "tc"], ["odenen", "okul_no"], ["odenen", "ad_soyad"], ["dekont_tarihi", "tc"]],
        {"odenen": 4, "dekont_tarihi": 3, "donem": 1.5}, ["dekont", "odeme", "banka"], "dekont", 70),
    IceAktarmaTanimi("sgk_bildirimleri", "SGK İşe Giriş / Ayrılış Bildirgeleri", _OGRENCI + [
        ("islem", "İşlem (Giriş/Çıkış)", ["islem", "islem turu", "bildirge turu", "hareket"]),
        ("tarih", "İşlem Tarihi", ["tarih", "islem tarihi"]),
        ("giris_tarihi", "İşe Giriş Tarihi", ["ise giris tarihi", "giris tarihi", "sigorta baslangic tarihi",
                                              "sigortali baslama tarihi"]),
        ("cikis_tarihi", "İşten Ayrılış Tarihi", ["isten cikis tarihi", "cikis tarihi", "isten ayrilis tarihi",
                                                  "ayrilis tarihi"]),
        ("bildirim_tarihi", "Bildirim Tarihi", ["bildirim tarihi", "bildirge tarihi", "onay tarihi"]),
    ], [["giris_tarihi", "tc"], ["cikis_tarihi", "tc"], ["islem", "tarih", "tc"]],
        {"giris_tarihi": 3, "cikis_tarihi": 3, "islem": 2, "bildirim_tarihi": 3},
        ["sgk", "e bildirge", "bildirge", "sigorta"], "sgk", 71),
]}


_OGRENCI_ALANLARI = {a for a, _, _ in _OGRENCI} | {"dogum_tarihi", "cinsiyet", "statu", "bakmakla_yukumlu",
                                                   "telefon", "iban", "adres", "alan", "dal", "baba_adi",
                                                   "anne_adi", "dogum_yeri", "nufus_il", "nufus_ilce"}
_YERLESTIRME_ISLETME_ALANLARI = {"vergi_no", "isletme_adres", "isletme_tel", "yetkili", "usta_ogretici",
                                 "usta_ogretici_tel", "personel_sayisi"}


def _onekli_esanlamlilar() -> None:
    """Formlarda bölüm adıyla öneklenmiş etiketler için ("İşletme Adres", "Öğrenci Telefon") eş anlamlılar."""
    for t in TANIMLAR.values():
        ogrenci_turu = any(a == "tc" for a, _, _ in t.alanlar) and t.tablo != "ogretmenler"
        yeni = []
        for a, g, syn in t.alanlar:
            ek: list[str] = []
            if t.tablo == "isletmeler" or (t.tablo == "yerlestirmeler" and a in _YERLESTIRME_ISLETME_ALANLARI):
                ek = ["isletme " + norm(s) for s in syn
                      if not norm(s).startswith(("isletme", "isyeri", "firma", "isveren", "usta", "egitici"))]
            elif ogrenci_turu and a in _OGRENCI_ALANLARI:
                ek = ["ogrenci " + norm(s) for s in syn if not norm(s).startswith(("ogrenci", "ogr ", "veli"))]
            yeni.append((a, g, syn + [e for e in ek if e not in syn]))
        t.alanlar = yeni


_onekli_esanlamlilar()


def zorunlu_tamam(tanim: IceAktarmaTanimi, es: dict[str, int]) -> bool:
    return any(all(k in es for k in grup) for grup in tanim.zorunlu)


def zorunlu_metni(tanim: IceAktarmaTanimi) -> str:
    return " veya ".join(" + ".join(tanim.baslik(x) for x in grup) for grup in tanim.zorunlu)


# ------------------------------------------------------------------ başlık eşleştirme

_KUME: dict[str, dict[str, tuple[set[str], list[list[str]]]]] = {}


def _kume(tanim: IceAktarmaTanimi):
    if tanim.tablo not in _KUME:
        k = {}
        for a, g, syn in tanim.alanlar:
            hepsi = {norm(x) for x in [g, *syn]}
            k[a] = (hepsi, [s.split() for s in hepsi if len(s.split()) >= 2])
        _KUME[tanim.tablo] = k
    return _KUME[tanim.tablo]


_EKLER = {"i", "u", "in", "un", "nin", "nun", "si", "su", "ni", "nu", "yi", "yu", "e", "a", "de", "da", "ler",
          "lar", "leri", "lari"}


def _sozcuk_uyar(tok: str, s: str) -> bool:
    """Başlık sözcüğü eş anlamlının sözcüğüyle başlıyor mu? Kısa kökler yalnızca Türkçe eklerle uzayabilir
    ('ad' -> 'adi' olur, 'adres' olmaz); 'tel' -> 'telefon' kısaltması kabul edilir."""
    if tok == s:
        return True
    if not tok.startswith(s):
        return False
    return len(s) >= 4 or s == "tel" or tok[len(s):] in _EKLER


def _benzerlik(n: str, kume: tuple[set[str], list[list[str]]]) -> float:
    if n in kume[0]:
        return 3.0
    tok = n.split()
    en = 0.0
    for s in kume[1]:
        L = len(s)
        for i in range(len(tok) - L + 1):
            if all(_sozcuk_uyar(tok[i + j], s[j]) for j in range(L)):
                en = max(en, 2.0 + L * 0.01)
                break
    return en


def eslestir(baslik_satiri: list[Any], tanim: IceAktarmaTanimi) -> dict[str, int]:
    kume = _kume(tanim)
    adaylar = []
    for j, h in enumerate(baslik_satiri):
        if isinstance(h, (int, float, datetime, date)) and not isinstance(h, bool):
            continue
        n = norm(h)
        if not n or len(n) > 80:
            continue
        for a in kume:
            p = _benzerlik(n, kume[a])
            if p:
                adaylar.append((p, -j, a, j))
    adaylar.sort(reverse=True)
    es: dict[str, int] = {}
    kullanilan: set[int] = set()
    for _, _, a, j in adaylar:
        if a in es or j in kullanilan:
            continue
        es[a] = j
        kullanilan.add(j)
    return es


def birlesik_baslik(ust: list[Any], alt: list[Any]) -> list[str]:
    """İki satırlı (birleştirilmiş hücreli) başlık: üst satırdaki grup adı alttaki sütun adlarına eklenir
    ('Öğrenci' + 'Adı' -> 'Öğrenci Adı', 'İşletme' + 'Vergi No' -> 'İşletme Vergi No')."""
    out, grup = [], ""
    for j in range(max(len(ust), len(alt))):
        u = metin(ust[j]) if j < len(ust) else ""
        a = metin(alt[j]) if j < len(alt) else ""
        if u:
            grup = u
        elif not a:
            grup = ""
        out.append(f"{grup} {a}".strip() if a else u)
    return out


def satir_eslestir(rows: list[list[Any]], i: int, tanim: IceAktarmaTanimi) -> dict[str, int]:
    """i. satırı başlık sayarak eşleme; üst satırla birlikte iki satırlı başlık daha iyi eşleşirse o kullanılır."""
    es = eslestir(rows[i], tanim)
    if i > 0 and len(_dolu_hucreler(rows[i - 1])) >= 2:
        es2 = eslestir(birlesik_baslik(rows[i - 1], rows[i]), tanim)
        if len(es2) > len(es):
            return es2
    return es


def baslik_bul(rows: list[list[Any]], tanim: IceAktarmaTanimi, tara: int = 25) -> tuple[int, dict[str, int]]:
    """Başlık satırını ve {alan: sütun} eşlemesini bulur. İki satırlı başlıklar da denenir."""
    en_iyi: tuple[int, dict[str, int]] = (-1, {})
    for i in range(min(tara, len(rows))):
        es = satir_eslestir(rows, i, tanim)
        if len(es) > len(en_iyi[1]) or (len(es) == len(en_iyi[1]) and es and zorunlu_tamam(tanim, es)
                                         and not zorunlu_tamam(tanim, en_iyi[1])):
            en_iyi = (i, es)
    return en_iyi


def baglam_alanlari(tanim: IceAktarmaTanimi) -> dict[str, str]:
    """Bağlam bilgisi -> tanımdaki alan."""
    alanlar = {a for a, _, _ in tanim.alanlar}
    esle = {k: k for k in ("sinif", "alan", "dal", "isletme", "ogretmen", "belge_turu")}
    if tanim.tablo in ("dekontlar", "sgk_liste"):
        esle["ay"] = "donem"
    return {k: a for k, a in esle.items() if a in alanlar}


def sanal_alanlar(tablo: Tablo, tanim: IceAktarmaTanimi, eslesme: dict[str, int]) -> dict[str, int]:
    """Sütunu olmayan ama belge bağlamından (başlık üstü/ara satırlar) gelen alanlar {alan: -1}."""
    anahtarlar = {k for b in satir_baglamlari(tablo).values() for k in b}
    out = {a: -1 for k, a in baglam_alanlari(tanim).items() if k in anahtarlar and a not in eslesme}
    if tanim.tablo in _GRUPLU_TURLER:
        out.update({k: -1 for b in ogrenci_basliklari(tablo).values() for k in b if k not in eslesme})
    return out


def hazir_mi(tablo: Tablo, anahtar: str, eslesme: dict[str, int]) -> bool:
    t = TANIMLAR[anahtar]
    return zorunlu_tamam(t, {**eslesme, **sanal_alanlar(tablo, t, eslesme)})


@dataclass
class Tahmin:
    anahtar: str
    puan: float
    bas: int
    eslesme: dict[str, int]

    @property
    def tanim(self) -> IceAktarmaTanimi:
        return TANIMLAR[self.anahtar]


def tahmin_et(tablo: Tablo) -> list[Tahmin]:
    """Tablonun olası veri türlerini puana göre sıralı döndürür.

    SGK aylık prim ve hizmet belgesi listeleri (prim günü/PEK/belge türü) kayıt olarak aktarılmaz; bunlar SGK
    karşılaştırmasında kullanılır (öğretmen/öğrenci listesi sanılmasın)."""
    from . import sgk_karsilastirma
    sgk = sgk_karsilastirma.sgk_tablosu(tablo)
    if sgk and sgk_karsilastirma.aphb_mi(sgk[1]):
        return []
    ad = norm(f"{Path(tablo.kaynak).stem} {tablo.ad}")
    out = []
    for k, t in TANIMLAR.items():
        bas, es = baslik_bul(tablo.satirlar, t)
        sanal = sanal_alanlar(tablo, t, es) if bas >= 0 else {}
        if bas < 0 or not zorunlu_tamam(t, {**es, **sanal}):
            continue
        puan = sum(t.agirlik.get(a, 1.0) for a in es) + sum(t.agirlik.get(a, 1.0) * 0.5 for a in sanal)
        if any(ip in ad for ip in t.ipucu):
            puan += 3
        if tablo.form and k == "yerlestirmeler":
            puan += 5  # öğrenci + işletme bilgisi taşıyan form sözleşmedir; ayrıntılar ek geçişlerle aktarılır
        veri = len(tablo.satirlar) - bas - 1
        if veri <= 0:
            puan -= 5
        out.append(Tahmin(k, round(puan, 2), bas, es))
    out.sort(key=lambda x: (-x.puan, TANIMLAR[x.anahtar].sira))
    return out


# ------------------------------------------------------------------ sonuç

@dataclass
class SatirSonucu:
    no: int
    durum: str  # eklendi | guncellendi | atlandi | hata
    mesaj: str
    ozet: str


@dataclass
class Secenekler:
    guncelle: bool = True
    olustur: bool = True
    tarih: date | None = None
    devamsizlik_yeri: str = "Okul"  # Okul | İşletme | Otomatik (tarih sınıfın işletme gününe denk geliyorsa İşletme)
    donem: tuple[int, int] | None = None
    ogrenci_statusu: str | None = None  # dosyada statü yoksa yeni/güncellenen öğrencilere yazılır
    bas: date | None = None  # tarihli kayıtlarda (devamsızlık) bu aralığın dışı atlanır
    bit: date | None = None


@dataclass
class IceAktarmaSonucu:
    anahtar: str = ""
    kaynak: str = ""
    deneme: bool = False
    eklenen: int = 0
    guncellenen: int = 0
    atlanan: int = 0
    hatalar: list[str] = field(default_factory=list)
    satirlar: list[SatirSonucu] = field(default_factory=list)
    yeni: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))
    etkilenen: dict[str, set[int]] = field(default_factory=lambda: defaultdict(set))
    iliskili: Counter = field(default_factory=Counter)
    ek: list["IceAktarmaSonucu"] = field(default_factory=list)  # aynı tablodan güncellenen diğer kayıt türleri

    def ekle(self, no: int, durum: str, mesaj: str, ozet: str) -> None:
        self.satirlar.append(SatirSonucu(no, durum, mesaj, ozet))
        if durum == "eklendi":
            self.eklenen += 1
        elif durum == "guncellendi":
            self.guncellenen += 1
        elif durum == "hata":
            self.hatalar.append(f"Kayıt {no} ({ozet}): {mesaj}")
        else:
            self.atlanan += 1

    def ozet_metni(self) -> str:
        t = TANIMLAR.get(self.anahtar)
        parca = [f"{t.etiket if t else self.anahtar}: {self.eklenen} eklendi, {self.guncellenen} güncellendi"]
        if self.atlanan:
            parca.append(f"{self.atlanan} atlandı")
        if self.hatalar:
            parca.append(f"{len(self.hatalar)} hatalı")
        s = ", ".join(parca)
        if self.iliskili:
            s += " (" + ", ".join(f"{n} {k}" for k, n in self.iliskili.items()) + ")"
        for e in self.ek:
            if e.eklenen or e.guncellenen or e.hatalar:
                s += f"; ayrıca {e.ozet_metni().removeprefix('[DENEME] ')} (aynı tablodaki ek bilgiler)"
        return ("[DENEME] " if self.deneme else "") + s


# ------------------------------------------------------------------ satır işleyiciler

class _Aktarici:
    def __init__(self, db, sec: Secenekler, sonuc: IceAktarmaSonucu, idx: dict | None = None):
        self.db = db
        self.sec = sec
        self.sonuc = sonuc
        self._idx: dict[str, dict[str, list[int]]] = {} if idx is None else idx
        self._ucret_cache: dict[tuple[int, int], dict[int, Any]] = {}

    # --- genel ---
    def _x(self, sql: str, params=()) -> Any:
        return self.db.conn.execute(sql, tuple(params))

    def _ekle(self, tablo: str, vals: dict) -> int:
        cur = self._x(f"INSERT INTO {tablo} ({', '.join(vals)}) VALUES ({', '.join('?' for _ in vals)})",
                      list(vals.values()))
        self.sonuc.yeni[tablo].append(cur.lastrowid)
        self.sonuc.etkilenen[tablo].add(cur.lastrowid)
        return cur.lastrowid

    def _guncelle(self, tablo: str, kid: int, vals: dict) -> None:
        if vals:
            self._x(f"UPDATE {tablo} SET {', '.join(f'{k} = ?' for k in vals)} WHERE id = ?", [*vals.values(), kid])
        self.sonuc.etkilenen[tablo].add(kid)

    def _kaydet(self, tablo: str, vals: dict, mevcut: int | None) -> tuple[str, int]:
        if mevcut:
            if not self.sec.guncelle:
                return "atlandi", mevcut
            self._guncelle(tablo, mevcut, vals)
            return "guncellendi", mevcut
        return "eklendi", self._ekle(tablo, vals)

    def _indeks(self, tur: str) -> dict[str, list[int]]:
        if tur not in self._idx:
            ix: dict[str, list[int]] = defaultdict(list)
            if tur in ("ogrenci", "ogretmen"):
                for r in self.db.q(f"SELECT id, ad, soyad FROM {tur}ler"):
                    ix[norm(f"{r['ad']} {r['soyad']}")].append(r["id"])
            elif tur == "isletme":
                for r in self.db.q("SELECT id, ad FROM isletmeler"):
                    ix[isletme_anahtari(r["ad"])].append(r["id"])
            elif tur == "sinif":
                for r in self.db.q("SELECT id, ad FROM siniflar"):
                    ix[norm(r["ad"])].append(r["id"])
                    ix[norm(sinif_adi(r["ad"]))].append(r["id"])
            else:
                tablo = {"alan": "alanlar", "ders": "dersler", "atolye": "atolyeler", "dal": "dallar"}[tur]
                for r in self.db.q(f"SELECT id, ad FROM {tablo}"):
                    ix[norm(r["ad"])].append(r["id"])
            self._idx[tur] = ix
        return self._idx[tur]

    def _ad_soyad(self, d: dict) -> tuple[str, str]:
        ad, soyad = tr_ad(d.get("ad")), tr_ad(d.get("soyad"))
        if not ad and metin(d.get("ad_soyad")):
            ad, soyad = ad_soyad_bol(tr_ad(d["ad_soyad"]))
        return ad, soyad

    def _basit(self, tur: str, tablo: str, ad: str, ekstra: dict | None = None) -> int | None:
        ad = metin(ad)
        if not ad:
            return None
        ix = self._indeks(tur)
        if ix.get(norm(ad)):
            return ix[norm(ad)][0]
        kid = self._ekle(tablo, {"ad": ad, **(ekstra or {})})
        ix[norm(ad)].append(kid)
        self.sonuc.iliskili[f"yeni {tur_adi(tur)}"] += 1
        return kid

    def alan_id(self, ad: Any) -> int | None:
        return self._basit("alan", "alanlar", tr_ad(ad))

    def dal_id(self, ad: Any, alan_id: int | None) -> int | None:
        return self._basit("dal", "dallar", tr_ad(ad), {"alan_id": alan_id})

    def sinif_id(self, ham: Any, d: dict | None = None) -> int | None:
        ham = metin(ham)
        if not ham:
            return None
        ix = self._indeks("sinif")
        ad = sinif_adi(ham)
        for anahtar in (norm(ham), norm(ad)):
            if ix.get(anahtar):
                return ix[anahtar][0]
        d = d or {}
        n = norm(ham)
        vals: dict[str, Any] = {"ad": ad, "seviye": _seviye(ad)}
        if any(k in n.split() for k in ("mem", "msm", "mesem")) or "mesleki egitim merkezi" in n or "cirak" in n:
            vals["program"] = "MEM"
        if metin(d.get("alan")):
            vals["alan_id"] = self.alan_id(d["alan"])
            if metin(d.get("dal")):
                vals["dal_id"] = self.dal_id(d["dal"], vals["alan_id"])
        kid = self._ekle("siniflar", vals)
        ix[norm(ad)].append(kid)
        ix[n].append(kid)
        self.sonuc.iliskili["yeni sınıf"] += 1
        return kid

    def ogretmen_bul(self, adsoyad: Any, olustur: bool = False) -> int | None:
        s = tr_ad(adsoyad)
        if not s:
            return None
        ix = self._indeks("ogretmen")
        if ix.get(norm(s)):
            return ix[norm(s)][0]
        m = re.fullmatch(r"([A-Za-zÇĞİÖŞÜçğıöşü])\.\s*(\S.*)", s)
        if m:  # 'A. Yılmaz' -> adı A ile başlayan tek Yılmaz
            bas, soyad = norm(m.group(1)), norm(m.group(2))
            adaylar = {i[0] for k, i in ix.items() if k.startswith(bas) and k.endswith(" " + soyad) and i}
            if len(adaylar) == 1:
                kid = adaylar.pop()
                ix[norm(s)].append(kid)
                return kid
        if not olustur:
            raise ValueError(f"Öğretmen bulunamadı: {s}")
        ad, soyad = ad_soyad_bol(s)
        kid = self._ekle("ogretmenler", {"ad": ad, "soyad": soyad})
        ix[norm(s)].append(kid)
        self.sonuc.iliskili["yeni öğretmen"] += 1
        return kid

    def isletme_bul(self, ad: Any, vergi_no: Any = None, ekstra: dict | None = None,
                    olustur: bool = True) -> int | None:
        ad = metin(ad)
        vn = metin(vergi_no)
        r = self.db.q1("SELECT id FROM isletmeler WHERE vergi_no = ? AND vergi_no != ''", (vn,)) if vn else None
        if not r and not ad:
            return None
        ix = self._indeks("isletme")
        anahtar = isletme_anahtari(ad) if ad else ""
        if r or ix.get(anahtar):
            kid = r["id"] if r else ix[anahtar][0]
            if ekstra:
                bos = {k: v for k, v in ekstra.items() if v not in (None, "")}
                mevcut = self.db.q1("SELECT * FROM isletmeler WHERE id = ?", (kid,))
                eksik = {k: v for k, v in bos.items() if not mevcut[k]}
                if eksik:
                    self._guncelle("isletmeler", kid, eksik)
            return kid
        if not olustur:
            raise ValueError(f"İşletme bulunamadı: {ad}")
        vals = {"ad": ad, **({"vergi_no": vn} if vn else {}),
                **{k: v for k, v in (ekstra or {}).items() if v not in (None, "")}}
        kid = self._ekle("isletmeler", vals)
        ix[anahtar].append(kid)
        self.sonuc.iliskili["yeni işletme"] += 1
        return kid

    def ogrenci_bul(self, d: dict, olustur: bool = False) -> int | None:
        tc, no = metin(d.get("tc")), metin(d.get("okul_no"))
        ad, soyad = self._ad_soyad(d)
        if tc:
            r = self.db.q1("SELECT id FROM ogrenciler WHERE tc = ?", (tc,))
            if r:
                return r["id"]
        adlar = self._indeks("ogrenci").get(norm(f"{ad} {soyad}"), []) if ad else []
        if no:
            rows = self.db.q("SELECT id FROM ogrenciler WHERE okul_no = ?", (no,))
            ids = [r["id"] for r in rows]
            if len(ids) == 1 and (not adlar or ids[0] in adlar):
                return ids[0]
            ortak = [i for i in ids if i in adlar]
            if ortak:
                return ortak[0]
        if len(adlar) == 1:
            r = self.db.q1("SELECT tc FROM ogrenciler WHERE id = ?", (adlar[0],))
            if not tc or not r["tc"]:
                return adlar[0]
        if len(adlar) > 1:
            sinif = self.sinif_id(d.get("sinif"), d) if metin(d.get("sinif")) else None
            ayni = [r["id"] for r in self.db.q(f"SELECT id FROM ogrenciler WHERE sinif_id IS ? AND id IN "
                                                  f"({','.join('?' * len(adlar))})", [sinif, *adlar])]
            if len(ayni) == 1:
                return ayni[0]
        if not olustur or not ad:
            kim = " ".join(x for x in (f"{ad} {soyad}".strip(), f"No: {no}" if no else "", f"TC: {tc}" if tc else "")
                           if x)
            raise ValueError(f"Öğrenci bulunamadı ({kim or 'kimlik bilgisi yok'})")
        vals = {"ad": ad, "soyad": soyad, "tc": tc, "okul_no": no}
        if metin(d.get("sinif")):
            vals["sinif_id"] = self.sinif_id(d["sinif"], d)
        kid = self._ekle("ogrenciler", vals)
        self._indeks("ogrenci")[norm(f"{ad} {soyad}")].append(kid)
        self.sonuc.iliskili["yeni öğrenci"] += 1
        return kid

    # --- veri türleri ---
    def ogretmen(self, d: dict) -> tuple[str, str]:
        ad, soyad = self._ad_soyad(d)
        if not ad:
            return "atlandi", "Ad bilgisi yok"
        vals: dict[str, Any] = {"ad": ad, "soyad": soyad}
        for k in ("tc", "brans", "telefon", "eposta"):
            if metin(d.get(k)):
                vals[k] = tr_ad(d[k]) if k == "brans" else metin(d[k])
        u = norm(d.get("unvan"))
        if u:
            vals["unvan"] = ("Müdür" if u == "mudur" else "Müdür Başyardımcısı" if "bas" in u and "yard" in u
                             else "Koordinatör Müdür Yardımcısı" if "koord" in u and "yard" in u
                             else "Müdür Yardımcısı" if "yard" in u
                             else "Atölye/Lab. Öğretmeni" if "atolye" in u or "lab" in u else "Öğretmen")
        if metin(d.get("alan")):
            vals["alan_id"] = self.alan_id(d["alan"])
        k = evet(d.get("koordinator"))
        if k is not None:
            vals["koordinator"] = k
        if metin(d.get("musait_olmayan")):
            from . import program_belge
            vals["musait_olmayan"] = program_belge.musaitlik_metinden(d["musait_olmayan"],
                                                                      self.db.ayar("gunluk_ders_saati"))
        g = gun_no(d.get("nobet_gun")) if metin(d.get("nobet_gun")) else None
        if g and 1 <= g <= 5:
            vals["nobet_gun"] = g
        if metin(d.get("nobet_yeri")):
            vals["nobet_yeri"] = metin(d["nobet_yeri"])
        if metin(d.get("sinif_ogretmenligi")):
            vals["sinif_ogretmenligi"] = metin(d["sinif_ogretmenligi"])
        mevcut = None
        if vals.get("tc"):
            r = self.db.q1("SELECT id FROM ogretmenler WHERE tc = ?", (vals["tc"],))
            mevcut = r["id"] if r else None
        if not mevcut:
            ids = self._indeks("ogretmen").get(norm(f"{ad} {soyad}"))
            mevcut = ids[0] if ids else None
        durum, kid = self._kaydet("ogretmenler", vals, mevcut)
        if durum == "eklendi":
            self._indeks("ogretmen")[norm(f"{ad} {soyad}")].append(kid)
        return durum, ""

    def isletme(self, d: dict) -> tuple[str, str]:
        ad = metin(d.get("ad"))
        if not ad:
            return "atlandi", "İşletme adı yok"
        vals: dict[str, Any] = {"ad": ad}
        for k in ("vergi_no", "sgk_sicil", "yetkili", "telefon", "eposta", "adres", "ilce", "guzergah",
                  "usta_ogretici", "usta_ogretici_tel", "iban"):
            if metin(d.get(k)):
                vals[k] = metin(d[k]).replace(" ", "") if k == "iban" else metin(d[k])
        for k in ("mesafe_km", "personel_sayisi", "kontenjan"):
            x = sayi(d.get(k))
            if x is not None:
                vals[k] = x if k == "mesafe_km" else int(x)
        if metin(d.get("alan")):
            vals["alan_id"] = self.alan_id(d["alan"])
        kamu = evet(d.get("kamu_kurumu"))
        if kamu is not None:
            vals["kamu_kurumu"] = kamu
        mevcut = None
        if vals.get("vergi_no"):
            r = self.db.q1("SELECT id FROM isletmeler WHERE vergi_no = ?", (vals["vergi_no"],))
            mevcut = r["id"] if r else None
        if not mevcut:
            ids = self._indeks("isletme").get(isletme_anahtari(ad))
            mevcut = ids[0] if ids else None
        durum, kid = self._kaydet("isletmeler", vals, mevcut)
        if durum == "eklendi":
            self._indeks("isletme")[isletme_anahtari(ad)].append(kid)
        mesaj = "" if vals.get("personel_sayisi") else "Personel sayısı yok (ücret oranını etkiler)"
        return durum, mesaj

    def sinif(self, d: dict) -> tuple[str, str]:
        ham = metin(d.get("ad"))
        if not ham:
            return "atlandi", "Sınıf adı yok"
        ad = sinif_adi(ham)
        vals: dict[str, Any] = {"ad": ad}
        sv = sayi(d.get("seviye"))
        vals["seviye"] = int(sv) if sv else _seviye(ad)
        p = norm(d.get("program"))
        if p:
            vals["program"] = "MEM" if "mem" in p or "cirak" in p else "MTAL-ATP" if "atp" in p or "teknik" in p \
                else "MTAL-AMP-11" if re.search(r"amp 11|11 sinifta", p) else "MTAL-AMP"
        if metin(d.get("alan")):
            vals["alan_id"] = self.alan_id(d["alan"])
            if metin(d.get("dal")):
                vals["dal_id"] = self.dal_id(d["dal"], vals["alan_id"])
        for k in ("okul_gunleri", "isletme_gunleri"):
            if metin(d.get(k)):
                vals[k] = gunler_coz(d[k])
        if metin(d.get("rehber")):
            vals["rehber_ogretmen_id"] = self.ogretmen_bul(d["rehber"], olustur=True)
        ix = self._indeks("sinif")
        ids = ix.get(norm(ad)) or ix.get(norm(ham))
        durum, kid = self._kaydet("siniflar", vals, ids[0] if ids else None)
        if durum == "eklendi":
            ix[norm(ad)].append(kid)
        return durum, ""

    def atolye(self, d: dict) -> tuple[str, str]:
        ad = metin(d.get("ad"))
        if not ad:
            return "atlandi", "Atölye adı yok"
        vals: dict[str, Any] = {"ad": ad}
        t = norm(d.get("tur"))
        if t:
            vals["tur"] = "Laboratuvar" if "lab" in t else "Derslik" if "ders" in t else "Atölye"
        if metin(d.get("alan")):
            vals["alan_id"] = self.alan_id(d["alan"])
        k = sayi(d.get("kapasite"))
        if k:
            vals["kapasite"] = int(k)
        ids = self._indeks("atolye").get(norm(ad))
        durum, kid = self._kaydet("atolyeler", vals, ids[0] if ids else None)
        if durum == "eklendi":
            self._indeks("atolye")[norm(ad)].append(kid)
        return durum, ""

    def ders(self, d: dict) -> tuple[str, str]:
        ad = metin(d.get("ad"))
        if not ad:
            return "atlandi", "Ders adı yok"
        vals: dict[str, Any] = {"ad": ad}
        if metin(d.get("kisa_ad")):
            vals["kisa_ad"] = metin(d["kisa_ad"])
        if metin(d.get("alan")):
            vals["alan_id"] = self.alan_id(d["alan"])
        t = norm(d.get("tur"))
        if t:
            vals["tur"] = "Kültür" if "kultur" in t or "ortak" in t else "Atölye" if "atolye" in t else "Meslek"
        a = evet(d.get("atolye_gerekli"))
        if a is not None:
            vals["atolye_gerekli"] = a
        b = sayi(d.get("blok"))
        if b:
            vals["blok"] = int(b)
        ids = self._indeks("ders").get(norm(ad))
        durum, kid = self._kaydet("dersler", vals, ids[0] if ids else None)
        if durum == "eklendi":
            self._indeks("ders")[norm(ad)].append(kid)
        return durum, ""

    def atama(self, d: dict) -> tuple[str, str]:
        sinif, ders = metin(d.get("sinif")), metin(d.get("ders"))
        if not sinif or not ders:
            return "atlandi", "Sınıf veya ders yok"
        sinif_id = self.sinif_id(sinif, d)
        ders_id = self._basit("ders", "dersler", ders)
        ogr_id = self.ogretmen_bul(d.get("ogretmen"), olustur=True) if metin(d.get("ogretmen")) else None
        saat = int(sayi(d.get("haftalik_saat")) or 0)
        if saat <= 0:
            raise ValueError("Haftalık saat yok veya sıfır")
        vals: dict[str, Any] = {"sinif_id": sinif_id, "ders_id": ders_id, "ogretmen_id": ogr_id, "haftalik_saat": saat}
        b = sayi(d.get("blok"))
        if b:
            vals["blok"] = int(b)
        if metin(d.get("atolye")):
            vals["atolye_id"] = self._basit("atolye", "atolyeler", metin(d["atolye"]))
            self._x("UPDATE dersler SET atolye_gerekli = 1 WHERE id = ?", (ders_id,))
        if metin(d.get("ogretmen2")):
            vals["ogretmen2_id"] = self.ogretmen_bul(d["ogretmen2"], olustur=True)
        if metin(d.get("atolye2")):
            vals["atolye2_id"] = self._basit("atolye", "atolyeler", metin(d["atolye2"]))
        if metin(d.get("birlestirme")):
            vals["birlestirme"] = metin(d["birlestirme"])
        r = self.db.q1("SELECT id FROM ders_atamalari WHERE sinif_id = ? AND ders_id = ?", (sinif_id, ders_id))
        durum, _ = self._kaydet("ders_atamalari", vals, r["id"] if r else None)
        return durum, "" if ogr_id else "Öğretmen atanmamış"

    def program_hucresi(self, d: dict) -> tuple[str, str]:
        """Programdaki bir ders saati: atama yoksa oluşturulur, saat programa kilitli yazılır."""
        from . import program_belge
        sinif, ders = metin(d.get("sinif")), metin(d.get("ders"))
        if not sinif or not ders:
            return "atlandi", "Sınıf veya ders yok"
        gun = program_belge.gun_coz(d.get("gun"))
        saat = program_belge.saat_coz(d.get("saat"))
        if not gun or gun > 5:
            raise ValueError(f"Gün okunamadı veya hafta sonu: {metin(d.get('gun'))}")
        if not saat:
            raise ValueError(f"Ders saati okunamadı: {metin(d.get('saat'))}")
        S = self.db.ayar("gunluk_ders_saati")
        if saat > S:
            if saat > 16:
                raise ValueError(f"{saat}. ders saati çok büyük")
            self._x(self.db.AYAR_YAZ, ("gunluk_ders_saati", str(saat)))
            self.sonuc.iliskili[f"günlük ders saati {saat} yapıldı"] = 1
        sinif_id = self.sinif_id(sinif, d)
        kisa = metin(d.get("kisa_ad"))
        ders_id = self._basit("ders", "dersler", ders, {"kisa_ad": kisa} if kisa else None)
        if kisa:
            self._x("UPDATE dersler SET kisa_ad = ? WHERE id = ? AND (kisa_ad IS NULL OR TRIM(kisa_ad) = '')",
                    (kisa, ders_id))
        ogr_id = self.ogretmen_bul(d.get("ogretmen"), olustur=True) if metin(d.get("ogretmen")) else None
        ogr2_id = self.ogretmen_bul(d.get("ogretmen2"), olustur=True) if metin(d.get("ogretmen2")) else None
        if ogr2_id == ogr_id:
            ogr2_id = None
        atolye_id = self._basit("atolye", "atolyeler", metin(d["atolye"])) if metin(d.get("atolye")) else None
        if atolye_id:
            self._x("UPDATE dersler SET atolye_gerekli = 1 WHERE id = ? AND atolye_gerekli = 0", (ders_id,))
        r = self.db.q1("SELECT * FROM ders_atamalari WHERE sinif_id = ? AND ders_id = ?", (sinif_id, ders_id))
        if r:
            atama_id = r["id"]
            guncel: dict[str, Any] = {}
            birincil, ikinci = r["ogretmen_id"], r["ogretmen2_id"]
            for aday in (ogr_id, ogr2_id):
                if not aday:
                    continue
                if not birincil:
                    birincil = aday
                    guncel["ogretmen_id"] = aday
                elif aday not in (birincil, ikinci) and not ikinci:
                    ikinci = aday
                    guncel["ogretmen2_id"] = aday
            if atolye_id and not r["atolye_id"]:
                guncel["atolye_id"] = atolye_id
            if guncel:
                self._guncelle("ders_atamalari", atama_id, guncel)
        else:
            vals: dict[str, Any] = {"sinif_id": sinif_id, "ders_id": ders_id, "ogretmen_id": ogr_id,
                                    "haftalik_saat": 0, "atolye_id": atolye_id}
            if ogr2_id:
                vals["ogretmen2_id"] = ogr2_id
            atama_id = self._ekle("ders_atamalari", vals)
        cakisan = self.db.q1("""SELECT d.ad FROM program_hucreleri ph JOIN ders_atamalari da ON da.id = ph.atama_id
                                JOIN dersler d ON d.id = da.ders_id
                                WHERE da.sinif_id = ? AND ph.gun = ? AND ph.saat = ? AND ph.atama_id != ?""",
                             (sinif_id, gun, saat, atama_id))
        if cakisan:
            self._x("""DELETE FROM program_hucreleri WHERE gun = ? AND saat = ? AND atama_id IN
                       (SELECT id FROM ders_atamalari WHERE sinif_id = ?) AND atama_id != ?""",
                    (gun, saat, sinif_id, atama_id))
        mevcut = self.db.q1("SELECT id FROM program_hucreleri WHERE atama_id = ? AND gun = ? AND saat = ?",
                            (atama_id, gun, saat))
        if mevcut:
            self._x("UPDATE program_hucreleri SET kilitli = 1, atolye_id = COALESCE(?, atolye_id) WHERE id = ?",
                    (atolye_id, mevcut["id"]))
            durum = "guncellendi"
        else:
            self._ekle("program_hucreleri", {"atama_id": atama_id, "gun": gun, "saat": saat, "atolye_id": atolye_id,
                                             "kilitli": 1})
            durum = "eklendi"
        n = self.db.q1("SELECT COUNT(*) n FROM program_hucreleri WHERE atama_id = ?", (atama_id,))["n"]
        self._x("UPDATE ders_atamalari SET haftalik_saat = MAX(haftalik_saat, ?) WHERE id = ?", (n, atama_id))
        mesaj = f"Sınıfın bu saatteki '{cakisan['ad']}' dersi yerine yazıldı" if cakisan else ""
        ime = "isletmelerde mesleki" in norm(ders) or norm(kisa) == "ime"
        return durum, mesaj or ("" if ogr_id or ime else "Öğretmen yok")

    def ogrenci(self, d: dict) -> tuple[str, str]:
        ad, soyad = self._ad_soyad(d)
        if not ad:
            return "atlandi", "Ad bilgisi yok"
        tc, no = metin(d.get("tc")), metin(d.get("okul_no"))
        if no and not re.fullmatch(r"[\w\-/]+", no):
            return "atlandi", "Okul no geçersiz (başlık/alt bilgi satırı olabilir)"
        uyarilar = []
        if tc and not tc_gecerli(tc):
            uyarilar.append("T.C. kimlik no geçersiz")
        vals: dict[str, Any] = {"ad": ad, "soyad": soyad}
        for k in ("tc", "okul_no", "veli_tel", "telefon", "adres"):
            if metin(d.get(k)):
                vals[k] = metin(d[k])
        if metin(d.get("veli_ad")):
            vals["veli_ad"] = tr_ad(d["veli_ad"])
        for k in ("baba_adi", "anne_adi", "dogum_yeri", "nufus_il", "nufus_ilce"):
            if metin(d.get(k)):
                vals[k] = tr_ad(d[k])
        if metin(d.get("iban")):
            vals["iban"] = metin(d["iban"]).replace(" ", "").upper()
        c = norm(d.get("cinsiyet"))
        if c:
            vals["cinsiyet"] = "K" if c[0] in "kf" else "E"
        if d.get("dogum_tarihi") not in (None, ""):
            dt = tarih(d["dogum_tarihi"])
            if dt:
                vals["dogum_tarihi"] = dt.isoformat()
        st = norm(d.get("statu"))
        if st:
            vals["statu"] = ("Kalfa (MEM 12)" if "kalfa" in st else "Aday Çırak" if "aday" in st
                             else "Çırak" if "cirak" in st
                             else "Açık Lise" if "acik" in st or "maol" in st or "uzaktan" in st else "Öğrenci")
        elif self.sec.ogrenci_statusu:
            vals["statu"] = self.sec.ogrenci_statusu
        b = evet(d.get("bakmakla_yukumlu"))
        if b is not None:
            vals["bakmakla_yukumlu"] = b
        ort = sayi(d.get("basari_ortalamasi"))
        if ort is not None and 0 <= ort <= 100:
            vals["basari_ortalamasi"] = ort
        if metin(d.get("sinif")):
            vals["sinif_id"] = self.sinif_id(d["sinif"], d)
        try:
            mevcut = self.ogrenci_bul(d)
        except ValueError:
            mevcut = None
        durum, kid = self._kaydet("ogrenciler", vals, mevcut)
        if durum == "eklendi":
            self._indeks("ogrenci")[norm(f"{ad} {soyad}")].append(kid)
        return durum, "; ".join(uyarilar)

    def yerlestirme(self, d: dict) -> tuple[str, str]:
        if not metin(d.get("isletme")):
            return "atlandi", "İşletme adı yok"
        mesajlar = []
        ogr_id = self.ogrenci_bul(d, olustur=self.sec.olustur)
        ekstra = {"adres": metin(d.get("isletme_adres")), "telefon": metin(d.get("isletme_tel")),
                  "yetkili": tr_ad(d.get("yetkili")), "usta_ogretici": tr_ad(d.get("usta_ogretici")),
                  "usta_ogretici_tel": metin(d.get("usta_ogretici_tel"))}
        p = sayi(d.get("personel_sayisi"))
        if p is not None:
            ekstra["personel_sayisi"] = int(p)
        isletme_id = self.isletme_bul(d.get("isletme"), d.get("vergi_no"), ekstra, olustur=self.sec.olustur)
        bas = tarih(d.get("baslangic")) or self.sec.tarih
        if not bas:
            raise ValueError("Başlangıç tarihi yok; aktarım seçeneklerinden varsayılan tarih belirleyin")
        bit = tarih(d.get("bitis"))
        o = self.db.q1("""SELECT o.statu, s.program FROM ogrenciler o LEFT JOIN siniflar s ON s.id = o.sinif_id
                          WHERE o.id = ?""", (ogr_id,))
        t = norm(d.get("tur"))
        if "cirak" in t:
            tur = "Çıraklık"
        elif "staj" in t:
            tur = "Staj"
        elif "tamamlayici" in t:
            tur = "Tamamlayıcı Eğitim"
        elif "okulda" in t:
            tur = "Okulda Alan Eğitimi"
        elif t and metin(d.get("tur")) in YERLESTIRME_TURLERI:
            tur = metin(d["tur"])
        elif o and (o["statu"] in ("Aday Çırak", "Çırak", "Kalfa (MEM 12)") or (o["program"] or "") == "MEM"):
            tur = "Çıraklık"
        else:
            tur = "İşletmede Mesleki Eğitim"
        vals: dict[str, Any] = {"ogrenci_id": ogr_id, "isletme_id": isletme_id, "tur": tur, "baslangic": bas.isoformat()}
        if bit:
            vals["bitis"] = bit.isoformat()
        for k in ("sozlesme_no",):
            if metin(d.get(k)):
                vals[k] = metin(d[k])
        st = tarih(d.get("sozlesme_tarihi"))
        if st:
            vals["sozlesme_tarihi"] = st.isoformat()
        u = sayi(d.get("ucret"))
        if u:
            vals["ucret"] = u
        r = self.db.q1("""SELECT id FROM yerlestirmeler WHERE ogrenci_id = ? AND isletme_id IS ?
                          AND (baslangic = ? OR durum = 'Aktif') ORDER BY baslangic = ? DESC""",
                       (ogr_id, isletme_id, bas.isoformat(), bas.isoformat()))
        if not r:
            for e in self.db.q("""SELECT y.id, y.baslangic, i.ad FROM yerlestirmeler y
                                  LEFT JOIN isletmeler i ON i.id = y.isletme_id
                                  WHERE y.ogrenci_id = ? AND y.durum = 'Aktif' AND y.baslangic < ?
                                    AND (y.bitis IS NULL OR y.bitis = '' OR y.bitis >= ?)""",
                               (ogr_id, bas.isoformat(), bas.isoformat())):
                if e["id"] in self.sonuc.yeni.get("yerlestirmeler", []):
                    continue
                kapanis = bas - timedelta(days=1)
                self._guncelle("yerlestirmeler", e["id"], {"bitis": kapanis.isoformat(), "durum": "Sona Erdi",
                                                           "fesih_nedeni": "İşletme değişikliği"})
                self.sonuc.iliskili["kapatılan eski yerleştirme"] += 1
                mesajlar.append(f"Önceki yerleştirme ({e['ad'] or '-'}) {kapanis:%d.%m.%Y} tarihiyle kapatıldı")
        durum, _ = self._kaydet("yerlestirmeler", vals, r["id"] if r else None)
        return durum, "; ".join(mesajlar)

    def _isletme_gunu(self, ogr_id: int, t: date) -> bool:
        r = self.db.q1("""SELECT s.isletme_gunleri FROM ogrenciler o JOIN siniflar s ON s.id = o.sinif_id
                          WHERE o.id = ?""", (ogr_id,))
        return bool(r) and t.isoweekday() in gunler_listesi(r["isletme_gunleri"])

    def _okul_ici_sigortali(self, ogr_id: int, t: date) -> bool:
        """Okulda alan eğitimi sigortası süren öğrencinin okul devamsızlığı da SGK'ya eksik gün bildirilir."""
        ph = ", ".join("?" for _ in OKUL_ICI_TURLER)
        return self.db.q1(f"""SELECT 1 FROM yerlestirmeler WHERE ogrenci_id = ? AND tur IN ({ph})
                              AND baslangic IS NOT NULL AND baslangic <= ?
                              AND (bitis IS NULL OR bitis = '' OR bitis >= ?)""",
                          (ogr_id, *sorted(OKUL_ICI_TURLER), t.isoformat(), t.isoformat())) is not None

    def devamsizlik(self, d: dict) -> tuple[str, str]:
        y = norm(d.get("yer"))
        t = tarih(d.get("tarih"))
        if t and ((self.sec.bas and t < self.sec.bas) or (self.sec.bit and t > self.sec.bit)):
            return "atlandi", "Seçilen tarih aralığının dışında"
        try:
            ogr_id = self.ogrenci_bul(d)
        except ValueError as e:
            return "atlandi", f"{e}; MesKoord'da kayıtlı olmayan öğrenci atlandı"
        yer = "İşletme" if "isletme" in y or "beceri" in y else "Okul" if "okul" in y else self.sec.devamsizlik_yeri
        if yer not in ("Okul", "İşletme"):
            yer = "İşletme" if t and self._isletme_gunu(ogr_id, t) else "Okul"
        sgk = 1 if yer == "İşletme" or (t and self._okul_ici_sigortali(ogr_id, t)) else 0
        aciklama = metin(d.get("aciklama"))
        if t:
            tn = norm(d.get("tur"))
            tur = ("Raporlu" if "rapor" in tn else "İzinli" if "izin" in tn
                   else "Özürlü" if tn.startswith("ozurlu") or tn == "ozurlu" else "Özürsüz")
            g = norm(d.get("gun"))
            gun = 0.5 if "yarim" in g else (sayi(d.get("gun")) or 1.0)
            kalemler = [(tur, gun)]
            if not tn and ("ozurlu" in d or "ozursuz" in d):  # e-Okul R060: Özürlü / Özürsüz ayrı sütunlarda
                kalemler = [(k, v) for k, v in (("Özürlü", _devam_degeri(d.get("ozurlu"))),
                                                ("Özürsüz", _devam_degeri(d.get("ozursuz")))) if v]
                if not kalemler:
                    return "atlandi", "Bu tarihte özürlü/özürsüz devamsızlık değeri yok"
            durumlar = []
            for tur, gun in kalemler:
                vals = {"ogrenci_id": ogr_id, "tarih": t.isoformat(), "tur": tur, "yer": yer, "gun": gun,
                        "sgk_eksik": sgk, "aciklama": aciklama}
                ikili = len(kalemler) > 1
                r = self.db.q1("SELECT id FROM devamsizlik WHERE ogrenci_id = ? AND tarih = ? AND yer = ?"
                               + (" AND tur = ?" if ikili else ""), (ogr_id, t.isoformat(), yer, *([tur] if ikili else [])))
                durumlar.append(self._kaydet("devamsizlik", vals, r["id"] if r else None)[0])
            return ("eklendi" if "eklendi" in durumlar else durumlar[0]), \
                ", ".join(f"{k} {v:g} gün" for k, v in kalemler) if len(kalemler) > 1 else ""
        t = self.sec.tarih or date.today()
        degerler = {"Özürsüz": sayi(d.get("ozursuz")), "Özürlü": sayi(d.get("ozurlu"))}
        if degerler["Özürsüz"] is None and degerler["Özürlü"] is None:
            degerler["Özürsüz"] = sayi(d.get("gun"))
        durum = "atlandi"
        for tur, gun in degerler.items():
            if gun is None:
                continue
            onceki = self.db.q("""SELECT id FROM devamsizlik WHERE ogrenci_id = ? AND yer = ? AND tur = ?
                                  AND aciklama LIKE 'Toplu aktarım%'""", (ogr_id, yer, tur))
            for r in onceki:
                self._x("DELETE FROM devamsizlik WHERE id = ?", (r["id"],))
            if gun > 0:
                self._ekle("devamsizlik", {"ogrenci_id": ogr_id, "tarih": t.isoformat(), "tur": tur, "yer": yer,
                                           "gun": gun, "sgk_eksik": 0, "aciklama": "Toplu aktarım (dönem toplamı)"})
            if onceki or gun > 0:
                durum = "guncellendi" if onceki else "eklendi"
        return durum, "Toplam devamsızlık; önceki toplu kayıtların yerine geçti" if durum != "atlandi" else "Değer yok"

    def beceri(self, d: dict) -> tuple[str, str]:
        ogr_id = self.ogrenci_bul(d)
        dn = norm(d.get("donem"))
        donem = 2 if dn in ("2", "ii", "ikinci", "2 donem", "ikinci donem") or dn.startswith("2") else 1
        vals: dict[str, Any] = {"ogrenci_id": ogr_id, "donem": donem}
        for k in ("isletme_notu", "koordinator_notu"):
            x = sayi(d.get(k))
            if x is not None:
                if not 0 <= x <= 100:
                    raise ValueError(f"{TANIMLAR['beceri_notlari'].baslik(k)} 0-100 arasında olmalı")
                vals[k] = x
        t = tarih(d.get("tarih"))
        if t:
            vals["tarih"] = t.isoformat()
        if metin(d.get("aciklama")):
            vals["aciklama"] = metin(d["aciklama"])
        r = self.db.q1("SELECT id FROM beceri_notlari WHERE ogrenci_id = ? AND donem = ?", (ogr_id, donem))
        durum, _ = self._kaydet("beceri_notlari", vals, r["id"] if r else None)
        return durum, ""

    def tatil(self, d: dict) -> tuple[str, str]:
        ad = metin(d.get("ad"))
        bas = tarih(d.get("baslangic"))
        if not ad or not bas:
            return "atlandi", "Ad veya tarih yok"
        bit = tarih(d.get("bitis")) or bas
        if bit < bas:
            raise ValueError("Bitiş başlangıçtan önce")
        r = self.db.q1("SELECT id FROM tatiller WHERE baslangic = ? AND lower(ad) = lower(?)", (bas.isoformat(), ad))
        durum, _ = self._kaydet("tatiller", {"ad": ad, "baslangic": bas.isoformat(), "bitis": bit.isoformat()},
                                r["id"] if r else None)
        return durum, ""

    def ekders(self, d: dict) -> tuple[str, str]:
        tid = self.ogretmen_bul(d.get("ogretmen"))
        t = tarih(d.get("tarih"))
        if not t:
            raise ValueError("Tarih yok")
        saat = sayi(d.get("saat"))
        if not saat:
            raise ValueError("Saat yok")
        tn = norm(d.get("tur"))
        tur = ("Gece" if "gece" in tn else "Nöbet" if "nobet" in tn else "DYK" if "dyk" in tn or "destek" in tn
               else "Belleticilik" if "bellet" in tn else "Sınav Görevi" if "sinav" in tn
               else "Planlama/Bakım-Onarım" if "bakim" in tn or "planlama" in tn
               else "Gündüz" if not tn or "gunduz" in tn else "Diğer")
        r = self.db.q1("SELECT id FROM ek_ders_kayitlari WHERE ogretmen_id = ? AND tarih = ? AND tur = ?",
                       (tid, t.isoformat(), tur))
        durum, _ = self._kaydet("ek_ders_kayitlari", {"ogretmen_id": tid, "tarih": t.isoformat(), "tur": tur,
                                                      "saat": saat, "aciklama": metin(d.get("aciklama"))},
                                r["id"] if r else None)
        return durum, ""

    def koordinator(self, d: dict) -> tuple[str, str]:
        tid = self.ogretmen_bul(d.get("ogretmen"))
        iid = self.isletme_bul(d.get("isletme"), olustur=self.sec.olustur)
        g = gun_no(d.get("gun"))
        if not g or g > 5:
            raise ValueError(f"Gün tanınmadı: {metin(d.get('gun'))}")
        vals: dict[str, Any] = {"ogretmen_id": tid, "isletme_id": iid, "gun": g,
                                "haftalik_saat": int(sayi(d.get("haftalik_saat")) or 1)}
        for k in ("baslangic", "bitis"):
            t = tarih(d.get(k))
            if t:
                vals[k] = t.isoformat()
        r = self.db.q1("SELECT id FROM koordinator_gorevleri WHERE ogretmen_id = ? AND isletme_id = ? AND gun = ?",
                       (tid, iid, g))
        durum, _ = self._kaydet("koordinator_gorevleri", vals, r["id"] if r else None)
        self._x("UPDATE ogretmenler SET koordinator = 1 WHERE id = ?", (tid,))
        return durum, ""

    def ziyaret(self, d: dict) -> tuple[str, str]:
        iid = self.isletme_bul(d.get("isletme"), olustur=self.sec.olustur)
        tid = self.ogretmen_bul(d.get("ogretmen")) if metin(d.get("ogretmen")) else None
        t = tarih(d.get("tarih"))
        if not t:
            raise ValueError("Ziyaret tarihi yok")
        dn = norm(d.get("durum"))
        durum_ = ("Yapılmadı" if "yapilmadi" in dn or dn in ("h", "hayir", "0")
                  else "Yapıldı" if "yapildi" in dn or dn in ("e", "evet", "1", "x")
                  else "Yapıldı" if not dn and metin(d.get("tespitler")) else "Planlandı")
        vals: dict[str, Any] = {"isletme_id": iid, "ogretmen_id": tid, "tarih": t.isoformat(), "durum": durum_}
        for k in ("tespitler", "oneriler"):
            if metin(d.get(k)):
                vals[k] = metin(d[k])
        r = self.db.q1("SELECT id FROM ziyaretler WHERE isletme_id = ? AND tarih = ? AND (ogretmen_id IS ? OR ? IS NULL)",
                       (iid, t.isoformat(), tid, tid))
        durum, _ = self._kaydet("ziyaretler", vals, r["id"] if r else None)
        return durum, ""

    def dekont(self, d: dict) -> tuple[str, str]:
        from . import ucret
        ogr_id = self.ogrenci_bul(d)
        dt = tarih(d.get("dekont_tarihi"))
        yil_v = sayi(d.get("yil"))
        donem = ay_coz(d.get("donem"), int(yil_v) if yil_v else (dt.year if dt else None))
        if not donem and self.sec.donem:
            donem = self.sec.donem
        if not donem and dt:
            onceki = dt.replace(day=1) - timedelta(days=1)
            donem = (onceki.year, onceki.month)
        if not donem:
            raise ValueError("Dönem belirlenemedi (dönem sütunu, dekont tarihi veya aktarım dönemi gerekli)")
        yil, ay = donem
        ilk, son = ay_araligi(yil, ay)
        y = self.db.q1("""SELECT id FROM yerlestirmeler WHERE ogrenci_id = ? AND isletme_id IS NOT NULL
                          AND baslangic <= ? AND (bitis IS NULL OR bitis = '' OR bitis >= ?)
                          ORDER BY baslangic DESC""", (ogr_id, son.isoformat(), ilk.isoformat()))
        if not y:
            raise ValueError(f"{AYLAR[ay - 1]} {yil} döneminde öğrencinin işletme yerleştirmesi yok")
        if donem not in self._ucret_cache:
            self._ucret_cache[donem] = {s.yerlestirme_id: s for s in ucret.aylik_hesap(self.db, yil, ay)}
        hesap = self._ucret_cache[donem].get(y["id"])
        odenen = sayi(d.get("odenen"))
        dk = f"{yil:04d}-{ay:02d}"
        r = self.db.q1("SELECT * FROM aylik_odemeler WHERE donem = ? AND yerlestirme_id = ?", (dk, y["id"]))
        vals: dict[str, Any] = {"dekont_teslim": 1, "dekont_tarihi": (dt or date.today()).isoformat()}
        if odenen is not None:
            vals["odenen_ucret"] = odenen
        if not r and hesap:
            vals.update({"gun": hesap.gun, "en_az_ucret": hesap.en_az_ucret, "odenecek_ucret": hesap.odenecek_ucret,
                         "devlet_katkisi": hesap.devlet_katkisi})
        if r:
            durum, _ = self._kaydet("aylik_odemeler", vals, r["id"])
        else:
            durum = "eklendi"
            self._ekle("aylik_odemeler", {"donem": dk, "yerlestirme_id": y["id"], **vals})
        beklenen = (r["odenecek_ucret"] if r else None) or (hesap.odenecek_ucret if hesap else None)
        if odenen is not None and beklenen and odenen + 0.01 < beklenen:
            return durum, f"EKSİK ÖDEME: {odenen:.2f} TL < {beklenen:.2f} TL ({AYLAR[ay - 1]} {yil})"
        return durum, f"{AYLAR[ay - 1]} {yil} dekontu işlendi"

    def sgk(self, d: dict) -> tuple[str, str]:
        ogr_id = self.ogrenci_bul(d)
        giris, cikis = tarih(d.get("giris_tarihi")), tarih(d.get("cikis_tarihi"))
        islem, t = norm(d.get("islem")), tarih(d.get("tarih"))
        if t and ("giris" in islem or "baslama" in islem):
            giris = giris or t
        elif t and ("cikis" in islem or "ayrilis" in islem):
            cikis = cikis or t
        if not giris and not cikis:
            return "atlandi", "Giriş/çıkış tarihi yok"
        bt = (tarih(d.get("bildirim_tarihi")) or date.today()).isoformat()
        mesajlar, durum = [], "atlandi"
        yer = self.db.q("SELECT * FROM yerlestirmeler WHERE ogrenci_id = ? ORDER BY baslangic", (ogr_id,))
        if giris:
            adaylar = sorted((abs((tarih(y["baslangic"]) - giris).days), y["id"]) for y in yer if tarih(y["baslangic"]))
            if adaylar and adaylar[0][0] <= 15:
                self._guncelle("yerlestirmeler", adaylar[0][1], {"sigorta_giris_bildirildi": 1,
                                                                 "sigorta_giris_bildirim_tarihi": bt})
                durum = "guncellendi"
                mesajlar.append("İşe giriş bildirildi olarak işaretlendi")
            else:
                mesajlar.append(f"{giris:%d.%m.%Y} girişine uyan yerleştirme yok")
        if cikis:
            uyan = [y for y in yer if tarih(y["bitis"]) == cikis]
            acik = [y for y in yer if not tarih(y["bitis"]) and tarih(y["baslangic"]) and tarih(y["baslangic"]) <= cikis]
            hedef = (uyan or acik or [None])[-1]
            if hedef:
                vals: dict[str, Any] = {"sigorta_cikis_bildirildi": 1, "sigorta_cikis_bildirim_tarihi": bt}
                if not uyan:
                    vals.update({"bitis": cikis.isoformat(), "durum": "Sona Erdi"})
                    mesajlar.append(f"Yerleştirme {cikis:%d.%m.%Y} tarihiyle sona erdirildi")
                self._guncelle("yerlestirmeler", hedef["id"], vals)
                durum = "guncellendi"
                mesajlar.append("İşten ayrılış bildirildi olarak işaretlendi")
            else:
                mesajlar.append(f"{cikis:%d.%m.%Y} çıkışına uyan yerleştirme yok")
        if durum == "atlandi":
            raise ValueError("; ".join(mesajlar))
        return durum, "; ".join(mesajlar)


def tur_adi(tur: str) -> str:
    return {"alan": "alan", "dal": "dal", "ders": "ders", "atolye": "atölye", "sinif": "sınıf"}.get(tur, tur)


# ------------------------------------------------------------------ aktarım

def _ozet(d: dict) -> str:
    oncelik = ["ad_soyad", "ad", "soyad", "okul_no", "tc", "isletme", "ogretmen", "sinif", "ders", "tarih"]
    parca = [metin(d[k]) for k in oncelik if metin(d.get(k))]
    return " ".join(parca[:3])[:60] or "-"


_OGRENCI_KIMLIK = {a for a, _, _ in _OGRENCI}
_KIMLIK = _OGRENCI_KIMLIK | {"isletme", "vergi_no"}
# Bir tablo tek türde aktarılır; tablodaki diğer türlere ait sütunlar (yerleştirme listesindeki öğrenci veli
# telefonu, işletme SGK sicil no vb.) bu türlerle ayrıca işlenir.
_EK_TURLER = ("isletmeler", "ogrenciler", "yerlestirmeler")


def _ortak_ad(tur: str, alan: str) -> str:
    return "isletme" if tur == "isletmeler" and alan == "ad" else alan


def _kimlik_mi(tur: str, alan: str) -> bool:
    return _ortak_ad(tur, alan) in _KIMLIK


@dataclass
class _EkGecis:
    anahtar: str
    eslesme: dict[str, int]
    bilgi: list[str]  # kimlik dışı alanlar: satırda biri doluysa geçiş çalışır


def ek_gecisler(rows: list[list[Any]], bas: int, anahtar: str, eslesme: dict[str, int],
                sec: Secenekler | None = None) -> list[_EkGecis]:
    """Ana türün kullanmadığı sütunlardan beslenen ek kayıt türleri (öğrenci/işletme ayrıntıları)."""
    baslik = rows[bas]
    ortak = {_ortak_ad(anahtar, k): j for k, j in eslesme.items() if _kimlik_mi(anahtar, k)}
    dolu = set(eslesme.values())
    out = []
    for tur in _EK_TURLER:
        if tur == anahtar or (tur == "yerlestirmeler" and anahtar not in ("ogrenciler", "isletmeler")):
            continue
        t = TANIMLAR[tur]
        es = eslestir(baslik, t)
        bilgi = {k: j for k, j in es.items() if not _kimlik_mi(tur, k) and j not in dolu}
        if not bilgi:
            continue
        kim = {}
        ogrenci_kimligi_var = any(k in _OGRENCI_KIMLIK for k in ortak)
        for a, _, _ in t.alanlar:
            if not _kimlik_mi(tur, a):
                continue
            ok = _ortak_ad(tur, a)
            if ok in ortak:
                kim[a] = ortak[ok]
            elif (a in es and es[a] not in dolu and es[a] not in bilgi.values()
                  and not (ok in _OGRENCI_KIMLIK and ogrenci_kimligi_var)):
                kim[a] = es[a]
        son = {**kim, **bilgi}
        if not zorunlu_tamam(t, son):
            continue
        if tur == "yerlestirmeler" and "baslangic" not in son and not (sec and sec.tarih):
            continue
        out.append(_EkGecis(tur, son, list(bilgi)))
        dolu |= set(son.values())
    return out


def kayit_satirlari(tablo: Tablo, tanim: IceAktarmaTanimi, bas: int, eslesme: dict[str, int], baglam: bool = True):
    """Başlıktan sonraki kayıt satırları: (veri satır no, satır, {alan: değer}, bağlam ekleyici).

    baglam=True ise ara başlık satırları (ör. '11-B SINIFI') sonraki satırların bağlamını günceller ve kayıt
    sayılmaz; tekrarlanan başlıklar, toplam/imza satırları ve tek hücreli alt bilgiler atlanır. Sütunu olmayan
    alanlar (sınıf, dönem, işletme...) bağlamdan doldurulur."""
    rows = tablo.satirlar
    baglamlar = satir_baglamlari(tablo) if baglam else {}
    esle = baglam_alanlari(tanim) if baglam else {}
    gecerli = on_baglam(tablo, bas) if baglam else {}
    baslik_norm = {k: norm(rows[bas][j]) for k, j in eslesme.items() if j < len(rows[bas])}
    ust_baslik = [norm(h) for h in rows[bas - 1]] if bas > 0 else None
    kimlik_sutunu = any(k in eslesme for k in ("tc", "okul_no")) and "ad_soyad" in {a for a, _, _ in tanim.alanlar}
    gruplu = baglam and tanim.tablo in _GRUPLU_TURLER
    basliklar = ogrenci_basliklari(tablo) if gruplu else {}
    kimlik_alanlari = ("tc", "okul_no", "ad", "soyad", "ad_soyad")
    ogrenci = next((b for i, b in sorted(basliklar.items(), reverse=True) if i < bas), {}) if gruplu else {}

    def baglam_ekle(d: dict) -> dict:
        for bk, alan in esle.items():
            if bk in gecerli and not metin(d.get(alan)):
                d[alan] = gecerli[bk]
        return d

    for n, row in enumerate(rows[bas + 1:], 1):
        d = {k: (row[j] if j < len(row) else None) for k, j in eslesme.items()}
        tekrar = bool(baslik_norm) and all(norm(d.get(k)) == v for k, v in baslik_norm.items())
        if gruplu and not tekrar and bas + n in basliklar:
            ogrenci = dict(basliklar[bas + n])  # öğrenci grup başlığı: sonraki tarihler bu öğrencinin
            gecerli.update(baglamlar.get(bas + n, {}))
            continue
        if bas + n in baglamlar:
            gecerli.update(baglamlar[bas + n])  # ara başlık: sonraki satırların sınıfı/dönemi/işletmesi
            continue
        if not any(metin(v) for v in d.values()):
            continue
        if tekrar:
            continue  # sayfa başında tekrarlanan başlık
        if baglam:
            dolu = _dolu_hucreler(row)
            if ust_baslik and [norm(h) for h in row] == ust_baslik:
                continue  # iki satırlı başlığın tekrarlanan üst satırı
            if dolu and re.match(r"(genel )?toplam|imza|onay", norm(dolu[0])) and len(dolu) <= 3:
                continue
            if kimlik_sutunu and len(dolu) == 1 and not any(metin(d.get(k)) for k in ("tc", "okul_no")) \
                    and not (gruplu and tarih(d.get("tarih"))):
                continue  # tek hücreli alt bilgi (imza adı, unvan, açıklama)
        if gruplu:
            if any(metin(d.get(k)) for k in kimlik_alanlari):
                ogrenci = {k: d[k] for k in (*kimlik_alanlari, "sinif") if metin(d.get(k))}
            else:
                d.update({k: v for k, v in ogrenci.items() if not metin(d.get(k))})  # gruplanmış satır
        yield n, row, baglam_ekle(d), baglam_ekle


_ACIK_LISE = ("yuz yuze egitim", "acik ogretim", "acik lise", "maol")


def acik_lise_listesi(tablo: Tablo, bas: int) -> bool:
    """MAOL 'Yüz Yüze Eğitim Öğrenci Listesi' gibi açık öğretim listeleri (dosya adı veya başlık üstü)."""
    ust = " ".join(metin(v) for row in tablo.satirlar[:max(0, bas)] for v in row)
    s = norm(f"{Path(tablo.kaynak).stem} {tablo.ad} {ust}")
    return any(k in s for k in _ACIK_LISE)


def aktar(db, tablo: Tablo, anahtar: str, bas: int | None = None, eslesme: dict[str, int] | None = None,
          sec: Secenekler | None = None, deneme: bool = False,
          ilerleme: Callable[[int, int], None] | None = None, ek: bool = True,
          baglam: bool = True) -> IceAktarmaSonucu:
    """Tabloyu verilen türde aktarır.

    baglam=True (dosyalar): başlık üstündeki ve ara satırlardaki sınıf/dönem/işletme gibi bilgiler sütunu olmayan
    alanlara aktarılır; bu satırlar ve imza/toplam gibi alt bilgi satırları kayıt sayılmaz. Elle girilen tablolarda
    (toplu giriş) kapalıdır.
    """
    tanim = TANIMLAR[anahtar]
    rows = tablo.satirlar
    if bas is None or eslesme is None:
        b2, e2 = baslik_bul(rows, tanim)
        bas = b2 if bas is None else bas
        eslesme = e2 if eslesme is None else eslesme
    sanal = sanal_alanlar(tablo, tanim, eslesme) if baglam and bas >= 0 else {}
    if bas < 0 or not zorunlu_tamam(tanim, {**eslesme, **sanal}):
        raise ValueError(f"{tablo.etiket}: {tanim.etiket} için gerekli sütunlar bulunamadı. "
                         f"Gerekli: {zorunlu_metni(tanim)}")
    sec = sec or Secenekler()
    if anahtar == "ogrenciler" and not sec.ogrenci_statusu and "statu" not in eslesme and acik_lise_listesi(tablo, bas):
        sec = replace(sec, ogrenci_statusu="Açık Lise")
    sonuc = IceAktarmaSonucu(anahtar=anahtar, kaynak=tablo.etiket, deneme=deneme)
    ana = _Aktarici(db, sec, sonuc)
    isleyici = getattr(ana, tanim.isleyici)
    gecisler = []  # (sıra, anahtar, eşleme, bilgi alanları, işleyici, sonuç); ana tür bilgi=None
    for g in (ek_gecisler(rows, bas, anahtar, eslesme, sec) if ek else []):
        s = IceAktarmaSonucu(anahtar=g.anahtar, kaynak=tablo.etiket, deneme=deneme, yeni=sonuc.yeni,
                             etkilenen=sonuc.etkilenen)
        sonuc.ek.append(s)
        gecisler.append((TANIMLAR[g.anahtar].sira, g.anahtar, g.eslesme, g.bilgi,
                         getattr(_Aktarici(db, sec, s, ana._idx), TANIMLAR[g.anahtar].isleyici), s))
    gecisler.append((tanim.sira, anahtar, eslesme, None, isleyici, sonuc))
    gecisler.sort(key=lambda x: x[0])
    veri_sayisi = len(rows) - bas - 1

    db.conn.commit()
    db.conn.execute("BEGIN")
    try:
        for n, row, d, baglam_ekle in kayit_satirlari(tablo, tanim, bas, eslesme, baglam):
            for _, _, es, bilgi, fn, s in gecisler:
                d2 = d if bilgi is None else baglam_ekle({k: (row[j] if j < len(row) else None) for k, j in es.items()})
                if bilgi is not None and not any(metin(d2.get(k)) for k in bilgi):
                    continue
                db.conn.execute("SAVEPOINT satir")
                try:
                    durum, mesaj = fn(d2)
                    db.conn.execute("RELEASE satir")
                except Exception as e:  # satır bazında hata raporlanır, aktarım sürer
                    db.conn.execute("ROLLBACK TO satir")
                    db.conn.execute("RELEASE satir")
                    durum, mesaj = "hata", str(e)
                s.ekle(n, durum, mesaj, _ozet(d2))
            if ilerleme:
                ilerleme(n, veri_sayisi)
    except Exception:
        db.conn.rollback()
        raise
    if deneme:
        db.conn.rollback()
    else:
        db.conn.commit()
    return sonuc


def en_uygun_tablo(tablolar: list[Tablo], anahtar: str) -> Tablo | None:
    tanim = TANIMLAR[anahtar]
    en, puan = None, -1
    for t in tablolar:
        bas, es = baslik_bul(t.satirlar, tanim)
        if bas >= 0 and zorunlu_tamam(tanim, es) and len(es) > puan:
            en, puan = t, len(es)
    return en


def ice_aktar(db, anahtar: str, yol: Path | str, ilerleme: Callable[[int, int], None] | None = None,
              sec: Secenekler | None = None, deneme: bool = False) -> IceAktarmaSonucu:
    """Dosyadaki en uygun tabloyu verilen türde aktarır."""
    tablolar = okuyucu.oku(yol)
    t = en_uygun_tablo(tablolar, anahtar)
    if not t:
        raise ValueError(f"Başlık satırı bulunamadı. Gerekli sütunlar: {zorunlu_metni(TANIMLAR[anahtar])}")
    return aktar(db, t, anahtar, sec=sec, deneme=deneme, ilerleme=ilerleme)


@dataclass
class Bulunan:
    tablo: Tablo
    tahminler: list[Tahmin]

    @property
    def en_iyi(self) -> Tahmin | None:
        return self.tahminler[0] if self.tahminler else None


def dosyalari_incele(yollar: list[Path | str]) -> tuple[list[Bulunan], list[str]]:
    """Ders programı çizelgeleri (ızgara, matris dağılım, müsaitlik) önce düz tablolara çevrilir."""
    from . import program_belge
    tablolar, hatalar = okuyucu.oku_coklu(yollar)
    return [Bulunan(t, tahmin_et(t)) for t in program_belge.genislet(tablolar)], hatalar


def otomatik_aktar(db, yollar: list[Path | str], sec: Secenekler | None = None, deneme: bool = False
                   ) -> tuple[list[IceAktarmaSonucu], list[str]]:
    """Dosyalardaki tanınan tüm tabloları bağımlılık sırasına göre aktarır."""
    bulunan, hatalar = dosyalari_incele(yollar)
    sirali = sorted([b for b in bulunan if b.en_iyi], key=lambda b: TANIMLAR[b.en_iyi.anahtar].sira)
    from . import sgk_karsilastirma
    for b in bulunan:
        if not b.en_iyi:
            hatalar.append(f"{b.tablo.etiket}: SGK hizmet listesi; SGK > Liste Karşılaştırma ekranında kullanın"
                           if sgk_karsilastirma.sgk_tablosu(b.tablo) else f"{b.tablo.etiket}: veri türü tanınamadı")
    sonuclar = []
    for b in sirali:
        try:
            sonuclar.append(aktar(db, b.tablo, b.en_iyi.anahtar, b.en_iyi.bas, b.en_iyi.eslesme, sec, deneme))
        except Exception as e:
            hatalar.append(str(e))
    return sonuclar, hatalar


def sablon_olustur(anahtar: str | None, yol: Path | str) -> Path:
    """Boş aktarım şablonu. anahtar None ise tüm türler ayrı sayfalarda tek dosyada."""
    from .excel_io import ExcelYazici
    x = ExcelYazici()
    for k in ([anahtar] if anahtar else sorted(TANIMLAR, key=lambda k: TANIMLAR[k].sira)):
        t = TANIMLAR[k]
        basliklar = [g for a, g, _ in t.alanlar if a not in ("ad_soyad", "ozursuz", "ozurlu", "yil")]
        x.sayfa(t.etiket[:31].replace("/", "-"), basliklar, [])
    return x.kaydet(yol)
