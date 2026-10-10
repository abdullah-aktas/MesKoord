"""Ders programı belgelerinin tanınması: e-Okul / aSc / okulun kendi Excel, PDF, Word çizelgeleri.

Tanınan biçimler düz tablolara çevrilir ve olağan aktarım tanımlarıyla kaydedilir:
  * Haftalık program ızgarası (satırlar ders saati, sütunlar günler ya da tersi; hücrede "Ders / Öğretmen /
    Atölye"). Sınıf veya öğretmen, tablo başlığından / sayfa adından okunur. Tüm okulun tek tablodaki çarşaf
    programı (satırlar sınıf veya öğretmen, sütunlar gün + saat) da tanınır. -> "Haftalık Ders Programı (Gün-Saat)"
  * Matris ders dağılımı (satırlar ders veya öğretmen, sütunlar sınıflar; hücrede saat, gerekirse öğretmen veya
    ders adı; tersi de olur). -> "Ders Dağılımı"
  * Öğretmen müsaitlik / boş gün çizelgesi (satırlar öğretmen, sütunlar gün veya gün + saat; hücrede işaret).
    -> "Öğretmenler" (müsait olmadığı zamanlar)
"""
from __future__ import annotations

import re
from typing import Any

from .aktarim import _sinif_mi, metin, norm, satir_baglamlari, sinif_adi, tr_ad
from .okuyucu import Tablo

_GUNLER = [("pazartesi", 1), ("sali", 2), ("carsamba", 3), ("persembe", 4), ("cumartesi", 6), ("cuma", 5),
           ("pazar", 7)]
_GUN_KISA = {"pzt": 1, "pts": 1, "pt": 1, "sal": 2, "sl": 2, "car": 3, "crs": 3, "csb": 3, "per": 4, "prs": 4,
             "prsb": 4, "cum": 5, "cm": 5, "cma": 5, "cmt": 6, "cts": 6, "paz": 7, "pz": 7}
_ROMA = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10, "xi": 11,
         "xii": 12}
_ZAMAN = re.compile(r"^\d{1,2}[:.]\d{2}(\s*[-–]\s*\d{1,2}[:.]\d{2})?$")
_ATOLYE = re.compile(r"\b(atolye\w*|atl|lab\w*|laboratuvar\w*|salon\w*|derslik\w*|mekan\w*|bt sinifi|"
                     r"spor salonu|konferans\w*)\b")
_KISI = re.compile(r"^([A-ZÇĞİÖŞÜ]\.\s?){1,2}[A-ZÇĞİÖŞÜ][a-zçğıöşüA-ZÇĞİÖŞÜ]+$|"
                   r"^[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(\s[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)*\s[A-ZÇĞİÖŞÜ]{2,}$")
_BOS_HUCRE = {"", "x", "-", "bos", "ogle arasi", "ogle", "ogle yemegi", "teneffus", "ara"}
_DEGIL = ("koordinator", "isletme", "gorev cizelge", "ziyaret", "nobet", "sinav", "mevcut", "istatistik")
_DERS_DEGIL = {"erkek", "kiz", "toplam", "mevcut", "ogrenci sayisi", "sube mevcudu", "kiz ogrenci", "erkek ogrenci"}
_TOPLAM = re.compile(r"^(genel\s+)?toplam|^top\.?$", re.I)


# ------------------------------------------------------------------ gün / saat çözümleme

def gun_coz(v: Any) -> int | None:
    """'Pazartesi', 'Pzt', 'SALI', '3', '3. gün' -> 1..7."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(v) if 1 <= v <= 7 and float(v).is_integer() else None
    n = norm(v)
    if not n:
        return None
    m = re.fullmatch(r"(\d)( gun\w*)?", n)
    if m:
        k = int(m.group(1))
        return k if 1 <= k <= 7 else None
    w = n.split()[0]
    for ad, i in _GUNLER:
        if w == ad:
            return i
    if w in _GUN_KISA:
        return _GUN_KISA[w]
    adaylar = {i for ad, i in _GUNLER if len(w) >= 3 and ad.startswith(w)}
    return adaylar.pop() if len(adaylar) == 1 else None


def saat_coz(v: Any) -> int | None:
    """'1', '1.', '1. ders', '1.saat', 'Ders 1', 'III' -> 1..16. Saat aralıkları ('08:30-09:10') None döner."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(v) if 1 <= v <= 16 and float(v).is_integer() else None
    s = metin(v)
    if not s or _ZAMAN.match(s):
        return None
    n = norm(s)
    m = re.fullmatch(r"(?:ders |saat )?(\d{1,2})(?: (?:ders|saat|ders saati)\w*)?", n)
    if m and 1 <= int(m.group(1)) <= 16:
        return int(m.group(1))
    m = re.fullmatch(r"([ivx]+)( (?:ders|saat)\w*)?", n)
    if not m or not (m.group(2) or "." in s):  # tek başına 'X' / 'V' işarettir
        return None
    return _ROMA.get(m.group(1))


def _gun_saat_basligi(v: Any) -> tuple[int | None, int | None]:
    """'Pazartesi' -> (1, None); 'Pzt 3' / 'Pazartesi-3' / '1. Gün 3. Saat' -> (1, 3)."""
    s = metin(v)
    if not s or len(s) > 30:
        return None, None
    n = norm(s)
    if isinstance(v, (int, float)) or (n.split()[0].isdigit() and " gun" not in f" {n}"):
        return None, None
    g = gun_coz(n)
    if g is None:
        return None, None
    sayilar = re.findall(r"\d{1,2}", n)
    if n.split()[0].isdigit():
        sayilar = sayilar[1:]
    h = int(sayilar[0]) if sayilar and 1 <= int(sayilar[0]) <= 16 else None
    return g, h


def _saat_etiketi(v: Any) -> bool:
    s = metin(v)
    return saat_coz(s) is not None or bool(_ZAMAN.match(s))


# ------------------------------------------------------------------ hücre çözümleme

def ad_duzelt(v: Any) -> str:
    """'Ahmet YILMAZ' -> 'Ahmet Yılmaz', 'A.YILMAZ' -> 'A. Yılmaz'."""
    s = re.sub(r"\.(?=[^\s.])", ". ", re.sub(r"\s+", " ", metin(v)))
    return " ".join(tr_ad(w) if w.isupper() and len(w) > 2 else w for w in s.split(" "))


def _parcalar(s: str) -> list[str]:
    satirlar = [p.strip() for p in re.split(r"[\r\n]+", s) if p.strip()]
    if len(satirlar) > 1:
        out = []
        for p in satirlar:
            out += [x.strip() for x in re.split(r"\s*[\[\]()]\s*", p) if x.strip()]
        return out
    return [p.strip() for p in re.split(r"\s+[-–/|]\s+|\s*[\[\]()]\s*|\s*;\s*|\s*\|\s*", s) if p.strip()]


def _salt_sinif(p: str) -> str | None:
    """Yalnızca sınıf adından oluşan metin ('11-B', '11/B Sınıfı'); '11-B Grafik' değil."""
    kalan = re.sub(r"\b(sinifi|sinif|subesi|sube)\b", " ", norm(p)).split()
    return _sinif_mi(p) if len(kalan) <= 2 and len(p) <= 16 else None


def hucre_coz(v: Any) -> dict[str, str] | None:
    """'Matematik\\nA. Yılmaz\\nLab-1', 'MAT (A.YILMAZ) [ATL-2]', '9-A Web Tasarım' -> {ders, ogretmen, atolye, sinif}."""
    s = metin(v)
    if norm(s) in _BOS_HUCRE:
        return None
    out: dict[str, str] = {}
    kalan: list[str] = []
    for p in _parcalar(s):
        n = norm(p)
        if not n:
            continue
        if "sinif" not in out and _salt_sinif(p):
            out["sinif"] = sinif_adi(p)
            continue
        m = re.match(r"^(\d{1,2}\s*[-/.]?\s*[A-ZÇĞİÖŞÜa-zçğıöşü])\s+(\S.*)$", p)
        if "sinif" not in out and m and _sinif_mi(m.group(1)):
            out["sinif"] = sinif_adi(m.group(1))
            p, n = m.group(2), norm(m.group(2))
        if "atolye" not in out and _ATOLYE.search(n):
            out["atolye"] = p
        elif "ogretmen" not in out and _KISI.match(p):
            out["ogretmen"] = ad_duzelt(p)
        else:
            kalan.append(p)
    if kalan:
        out["ders"] = kalan[0]
    if "ogretmen" not in out and len(kalan) > 1:
        out["ogretmen"] = ad_duzelt(kalan[1])
    if "atolye" not in out and len(kalan) > 2:
        out["atolye"] = kalan[2]
    return out if out.get("ders") else None


# ------------------------------------------------------------------ müsaitlik

_ISARET_KAPALI = {"musait degil", "musait olmayan", "yok", "kapali", "izinli", "izin", "hayir", "h", "dolu",
                  "bos", "bos gun", "istemiyor", "ders verilmez", "verilmez", "olmaz"}
_ISARET_ACIK = {"musait", "uygun", "var", "evet", "e", "olur", "ok"}
_ISARETLER = {"x", "+", "✓", "✔", "*", "v", "1", "0", "-", "•", "●", "o"}


def musaitlik_metinden(v: Any, saat_sayisi: int) -> str:
    """'Çarşamba', 'Salı 5-8', 'Pzt öğleden sonra; Cuma' gibi metni '3-*,2-5,2-6,...' biçimine çevirir."""
    from .program import musaitlik_metni
    s = metin(v)
    if s in ("-", "—", "–"):
        return ""
    if re.fullmatch(r"[\d\s,;*\-]+", s) and "-" in s:
        return s.replace(" ", "").replace(";", ",")
    S = saat_sayisi
    kapali: set[tuple[int, int]] = set()
    gun: int | None = None
    saatler: set[int] = set()
    onceki = ""

    def bitir():
        if gun:
            kapali.update((gun, h) for h in (saatler or range(1, S + 1)) if 1 <= h <= S)

    for m in re.finditer(r"(\d{1,2})\.?\s*(?:[-–]|ile)\s*(\d{1,2})|(\d{1,2})|([^\W\d_]+)", tr_kucuk_basit(s)):
        if m.group(1):
            a, b = int(m.group(1)), int(m.group(2))
            saatler |= set(range(min(a, b), max(a, b) + 1))
        elif m.group(3):
            saatler.add(int(m.group(3)))
        else:
            w = norm(m.group(4))
            g = gun_coz(w) if len(w) >= 3 and w not in ("saat", "sonra", "once") else None
            if g and g <= 7:
                bitir()
                gun, saatler = g, set()
            elif w == "sonra" and onceki in ("ogleden", "oglen", "ogle"):
                saatler |= set(range(S // 2 + 1, S + 1))
            elif (w == "once" and onceki in ("ogleden", "oglen", "ogle")) or w == "sabah":
                saatler |= set(range(1, S // 2 + 1))
            onceki = w
    bitir()
    return musaitlik_metni(kapali, S)


def tr_kucuk_basit(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


# ------------------------------------------------------------------ tablo tanıma

def _hucre(row: list[Any], j: int) -> Any:
    return row[j] if j < len(row) else None


def _baslik_metni(tablo: Tablo, bas: int) -> str:
    parca = [tablo.ad, tablo.kaynak]
    for row in tablo.satirlar[max(0, bas - 4):bas]:
        parca += [metin(c) for c in row if metin(c)]
    return norm(" ".join(parca))


def _varlik(tablo: Tablo, bas: int) -> tuple[str | None, str | None]:
    """Izgara başlığından önceki satırlardan sınıf veya öğretmen ('sinif', '9-A') / ('ogretmen', 'Ali Can')."""
    bag: dict[str, str] = {}
    for i, b in sorted(satir_baglamlari(tablo).items()):
        if i < bas:
            if "sinif" in b:
                bag.pop("ogretmen", None)
            if "ogretmen" in b:
                bag.pop("sinif", None)
            bag.update(b)
    if bag.get("sinif") and _sinif_mi(bag["sinif"]):
        return "sinif", _sinif_mi(bag["sinif"])
    if bag.get("ogretmen"):
        return "ogretmen", ad_duzelt(bag["ogretmen"])
    for row in reversed(tablo.satirlar[max(0, bas - 4):bas]):
        for c in row:
            s = metin(c)
            m = re.search(r"\b(\d{1,2}\s*[-/.]?\s*[A-ZÇĞİÖŞÜ])\b\s*(s[ıi]n[ıi]f|ş?ube|SINIF|ŞUBE)", s)
            if m and _sinif_mi(m.group(1)):
                return "sinif", _sinif_mi(m.group(1))
    if _salt_sinif(tablo.ad):
        return "sinif", _sinif_mi(tablo.ad)
    if _KISI.match(metin(tablo.ad)):
        return "ogretmen", ad_duzelt(tablo.ad)
    return None, None


def _gun_baslik_satiri(rows: list[list[Any]], bas: int = 0, azami: int = 10) -> tuple[int, dict[int, tuple]] | None:
    for i in range(bas, min(len(rows), bas + azami)):
        sut = {}
        for j, v in enumerate(rows[i]):
            g, h = _gun_saat_basligi(v)
            if g and g <= 6:
                sut[j] = (g, h)
        if len({g for g, _ in sut.values()}) >= 3:
            return i, sut
    return None


def _isaret_mi(v: Any) -> bool:
    s = metin(v)
    n = norm(s)
    return s.lower() in _ISARETLER or n in _ISARET_KAPALI or n in _ISARET_ACIK or (len(s) <= 2 and not s.isalnum())


class _Cikti:
    def __init__(self):
        self.program: list[list[Any]] = []
        self.musaitlik: dict[str, set[tuple[int, int]]] = {}
        self.dagilim: list[list[Any]] = []


def _izgara(tablo: Tablo, cikti: _Cikti) -> bool:
    rows = tablo.satirlar
    bulundu = False
    i = 0
    while i < len(rows):
        b = _gun_baslik_satiri(rows, i, azami=len(rows))
        if not b:
            break
        bas, sut = b
        if any(k in _baslik_metni(tablo, bas) for k in _DEGIL):
            return False
        ilk = min(sut)
        sutunlar: dict[int, tuple[int, int | None]] = {}
        gun = None
        saat_satiri = bas + 1 < len(rows) and sum(
            1 for j in range(ilk, len(rows[bas + 1])) if saat_coz(_hucre(rows[bas + 1], j))) >= 3
        for j in range(ilk, max(len(rows[bas]), len(rows[bas + 1]) if bas + 1 < len(rows) else 0)):
            if j in sut:
                gun = sut[j][0]
                h = sut[j][1]
            elif metin(_hucre(rows[bas], j)):
                gun = None
                continue
            else:
                h = None
            if gun is None:
                continue
            if saat_satiri:
                h = saat_coz(_hucre(rows[bas + 1], j))
            elif j not in sut:
                continue
            sutunlar[j] = (gun, h)
        carsaf = any(h for _, h in sutunlar.values())
        veri = bas + 2 if saat_satiri else bas + 1
        sonraki = _gun_baslik_satiri(rows, veri, azami=len(rows))
        son = sonraki[0] - (1 if sonraki and sonraki[0] > veri else 0) if sonraki else len(rows)
        baglamlar = satir_baglamlari(tablo)
        if sonraki:
            son = min(son, *(k for k in baglamlar if veri <= k < sonraki[0]), sonraki[0])
        govde = rows[veri:son]
        etiket_j = ilk - 1 if ilk > 0 else None
        if carsaf:
            if etiket_j is None:
                i = son
                continue
            bulundu |= _carsaf(govde, etiket_j, sutunlar, cikti, tablo)
        else:
            tur, ad = _varlik(tablo, bas)
            bulundu |= _basit_izgara(govde, etiket_j, sutunlar, tur, ad, cikti, tablo)
        i = max(son, bas + 1)
    return bulundu


def _musaitlik_isle(govde, etiket_j, sutunlar, cikti, tablo: Tablo) -> bool:
    hucreler = [_hucre(r, j) for r in govde for j in sutunlar if metin(_hucre(r, j))]
    if not hucreler or sum(1 for h in hucreler if _isaret_mi(h)) < 0.8 * len(hucreler):
        return False
    baslik = norm(" ".join([tablo.ad] + [metin(c) for r in tablo.satirlar[:6] for c in r
                                         if metin(c) and len(metin(c)) > 12]))
    isaret_acik = not re.search(r"bos gun|istek|musait (olmadig|olmayan|degil)|kapali|izin", baslik) and \
        bool(re.search(r"musait|uygun", baslik))
    S = 16
    for r in govde:
        ad = ad_duzelt(_hucre(r, etiket_j))
        if not ad or _TOPLAM.match(ad):
            continue
        kapali: set[tuple[int, int]] = set()
        for j, (g, h) in sutunlar.items():
            v = metin(_hucre(r, j))
            n = norm(v)
            if n in _ISARET_KAPALI:
                k = True
            elif n in _ISARET_ACIK:
                k = False
            else:
                k = bool(v) != isaret_acik
            if k:
                kapali |= {(g, h)} if h else {(g, x) for x in range(1, S + 1)}
        cikti.musaitlik[ad] = kapali
    return True


def _carsaf(govde, etiket_j, sutunlar, cikti: _Cikti, tablo: Tablo | None = None) -> bool:
    if tablo is not None and _musaitlik_isle(govde, etiket_j, sutunlar, cikti, tablo):
        return True
    n0 = len(cikti.program)
    for r in govde:
        etiket = metin(_hucre(r, etiket_j))
        if not etiket or _TOPLAM.match(etiket):
            continue
        sinif = _salt_sinif(etiket)
        for j, (g, h) in sutunlar.items():
            if not h:
                continue
            c = hucre_coz(_hucre(r, j))
            if not c:
                continue
            if sinif:
                cikti.program.append([sinif, g, h, c["ders"], c.get("ogretmen"), c.get("atolye")])
            elif c.get("sinif"):
                cikti.program.append([c["sinif"], g, h, c["ders"], ad_duzelt(etiket), c.get("atolye")])
    return len(cikti.program) > n0


def _basit_izgara(govde, etiket_j, sutunlar, tur, ad, cikti: _Cikti, tablo: Tablo) -> bool:
    if etiket_j is not None:
        etiketler = [metin(_hucre(r, etiket_j)) for r in govde if metin(_hucre(r, etiket_j))]
        saatli = sum(1 for e in etiketler if _saat_etiketi(e))
        if etiketler and saatli < 0.6 * len(etiketler):
            return _musaitlik_isle(govde, etiket_j, sutunlar, cikti, tablo)
    n0 = len(cikti.program)
    sira = 0
    for r in govde:
        if etiket_j is not None:
            e = _hucre(r, etiket_j)
            if not _saat_etiketi(e):
                continue
            sira = saat_coz(e) or sira + 1
        else:
            if not any(metin(_hucre(r, j)) for j in sutunlar):
                continue
            sira += 1
        for j, (g, _) in sutunlar.items():
            c = hucre_coz(_hucre(r, j))
            if not c:
                continue
            if tur == "sinif":
                cikti.program.append([ad, g, sira, c["ders"], c.get("ogretmen"), c.get("atolye")])
            elif c.get("sinif"):
                cikti.program.append([c["sinif"], g, sira, c["ders"], ad if tur == "ogretmen" else c.get("ogretmen"),
                                      c.get("atolye")])
    return len(cikti.program) > n0


def _gun_satirli(tablo: Tablo, cikti: _Cikti) -> bool:
    """Satırlar günler, sütunlar ders saatleri."""
    rows = tablo.satirlar
    gun_satirlari = [i for i, r in enumerate(rows) if r and gun_coz(_hucre(r, 0)) and len(norm(_hucre(r, 0))) <= 12]
    if len({gun_coz(rows[i][0]) for i in gun_satirlari}) < 3:
        return False
    bas = gun_satirlari[0] - 1
    if bas < 0 or any(k in _baslik_metni(tablo, bas) for k in _DEGIL):
        return False
    saatler = {}
    sira = 0
    for j in range(1, len(rows[bas])):
        v = _hucre(rows[bas], j)
        if saat_coz(v) or _ZAMAN.match(metin(v)):
            sira = saat_coz(v) or sira + 1
            saatler[j] = sira
    if len(saatler) < 3:
        return False
    tur, ad = _varlik(tablo, bas)
    n0 = len(cikti.program)
    for i in gun_satirlari:
        g = gun_coz(rows[i][0])
        for j, h in saatler.items():
            c = hucre_coz(_hucre(rows[i], j))
            if not c:
                continue
            if tur == "sinif":
                cikti.program.append([ad, g, h, c["ders"], c.get("ogretmen"), c.get("atolye")])
            elif c.get("sinif"):
                cikti.program.append([c["sinif"], g, h, c["ders"], ad if tur == "ogretmen" else c.get("ogretmen"),
                                      c.get("atolye")])
    return len(cikti.program) > n0


def _saat_ve_metin(v: Any) -> tuple[int | None, str]:
    s = metin(v)
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return (int(v) if 0 < v <= 40 else None), ""
    m = re.search(r"(?<![\d.])(\d{1,2})(?![\d.])", s)
    if not m or not 0 < int(m.group(1)) <= 40:
        return None, s
    kalan = (s[:m.start()] + " " + s[m.end():]).strip(" ()[]-/:,;")
    return int(m.group(1)), re.sub(r"\s+", " ", kalan.replace("(", " ").replace(")", " ")).strip()


def _matris(tablo: Tablo, cikti: _Cikti) -> bool:
    rows = tablo.satirlar
    if any(k in norm(f"{tablo.ad} {tablo.kaynak}") for k in _DEGIL):
        return False
    for bas in range(min(10, len(rows))):
        basliklar = rows[bas]
        sinif_sut = {j: _sinif_mi(metin(v)) for j, v in enumerate(basliklar)
                     if metin(v) and _salt_sinif(metin(v)) and not _TOPLAM.match(metin(v))}
        if len(sinif_sut) >= 2:
            return _matris_sutun_sinif(rows, bas, sinif_sut, cikti)
    # tersi: satırlar sınıf, sütunlar ders
    for bas in range(min(10, len(rows))):
        govde = rows[bas + 1:]
        siniflar = [r for r in govde if r and metin(_hucre(r, 0)) and _salt_sinif(metin(r[0]))]
        if len(siniflar) < 2 or len(siniflar) < 0.6 * len([r for r in govde if any(metin(c) for c in r)]):
            continue
        dersler = {j: metin(v) for j, v in enumerate(rows[bas]) if j > 0 and metin(v) and not _TOPLAM.match(metin(v))
                   and saat_coz(v) is None and not _sinif_mi(metin(v)) and norm(v) not in _DERS_DEGIL}
        if len(dersler) < 2:
            continue
        hucreler = [_hucre(r, j) for r in siniflar for j in dersler if metin(_hucre(r, j))]
        if not hucreler or sum(1 for h in hucreler if _saat_ve_metin(h)[0]) < 0.6 * len(hucreler):
            continue
        n0 = len(cikti.dagilim)
        for r in siniflar:
            for j, ders in dersler.items():
                saat, ogr = _saat_ve_metin(_hucre(r, j))
                if saat:
                    cikti.dagilim.append([_sinif_mi(metin(r[0])), ders, ad_duzelt(ogr) or None, saat])
        return len(cikti.dagilim) > n0
    return False


def _matris_sutun_sinif(rows, bas, sinif_sut, cikti: _Cikti) -> bool:
    basliklar = [norm(v) for v in rows[bas]]
    ilk = min(sinif_sut)
    ogretmen_j = next((j for j in range(ilk) if "ogretmen" in basliklar[j] or "adi soyadi" in basliklar[j]), None)
    ders_j = next((j for j in range(ilk) if basliklar[j].startswith("ders") or basliklar[j] == "dersin adi"), None)
    satir_ogretmen = ogretmen_j is not None and ders_j is None
    if ders_j is None and ogretmen_j is None:
        ders_j = next((j for j in range(ilk) if any(metin(_hucre(r, j)) for r in rows[bas + 1:])), None)
    if ders_j is None and ogretmen_j is None:
        return False
    govde = [r for r in rows[bas + 1:] if any(metin(c) for c in r)]
    hucreler = [_hucre(r, j) for r in govde for j in sinif_sut if metin(_hucre(r, j))]
    if not hucreler or sum(1 for h in hucreler if _saat_ve_metin(h)[0]) < 0.6 * len(hucreler):
        return False
    n0 = len(cikti.dagilim)
    for r in govde:
        etiket = metin(_hucre(r, ogretmen_j if satir_ogretmen else ders_j))
        if not etiket or _TOPLAM.match(etiket) or norm(etiket) in _DERS_DEGIL:
            continue
        satir_ogr = ad_duzelt(_hucre(r, ogretmen_j)) if ogretmen_j is not None and not satir_ogretmen else None
        for j, sinif in sinif_sut.items():
            saat, ek = _saat_ve_metin(_hucre(r, j))
            if not saat:
                continue
            if satir_ogretmen:
                if ek:
                    cikti.dagilim.append([sinif, ek, ad_duzelt(etiket), saat])
            else:
                cikti.dagilim.append([sinif, etiket, ad_duzelt(ek) or satir_ogr, saat])
    return len(cikti.dagilim) > n0


def donustur(tablo: Tablo) -> list[Tablo] | None:
    """Tablo bir program belgesiyse aktarılabilir düz tablolar döner, değilse None."""
    if tablo.form or len(tablo.satirlar) < 3:
        return None
    cikti = _Cikti()
    rows = tablo.satirlar
    b = _gun_baslik_satiri(rows, 0, azami=len(rows))
    if b:
        tanindi = _izgara_ve_musaitlik(tablo, cikti)
    else:
        tanindi = _gun_satirli(tablo, cikti) or _matris(tablo, cikti)
    if not tanindi:
        return None
    out = []
    if cikti.program:
        out.append(Tablo(tablo.kaynak, f"{tablo.ad} (haftalık ders programı)",
                         [["Sınıf/Şube", "Gün", "Ders Saati", "Ders Adı", "Öğretmen", "Atölye/Lab."],
                          *cikti.program]))
    if cikti.dagilim:
        out.append(Tablo(tablo.kaynak, f"{tablo.ad} (ders dağılımı)",
                         [["Sınıf/Şube", "Ders Adı", "Öğretmen", "Haftalık Saat"], *cikti.dagilim]))
    if cikti.musaitlik:
        from .program import musaitlik_metni
        out.append(Tablo(tablo.kaynak, f"{tablo.ad} (öğretmen müsaitlik)",
                         [["Öğretmen Adı Soyadı", "Müsait Olmadığı Zamanlar"],
                          *[[ad, musaitlik_metni(k, 16) or "-"] for ad, k in cikti.musaitlik.items()]]))
    return out or None


def _izgara_ve_musaitlik(tablo: Tablo, cikti: _Cikti) -> bool:
    rows = tablo.satirlar
    b = _gun_baslik_satiri(rows, 0, azami=len(rows))
    bas, sut = b
    ilk = min(sut)
    if ilk > 0 and not any(h for _, h in sut.values()):
        etiketler = [metin(_hucre(r, ilk - 1)) for r in rows[bas + 1:] if metin(_hucre(r, ilk - 1))]
        saat_satiri = bas + 1 < len(rows) and sum(
            1 for j in range(ilk, len(rows[bas + 1])) if saat_coz(_hucre(rows[bas + 1], j))) >= 3
        if etiketler and not saat_satiri and sum(1 for e in etiketler if _saat_etiketi(e)) < 0.6 * len(etiketler):
            sutunlar = {j: (g, None) for j, (g, _) in sut.items()}
            if any(k in _baslik_metni(tablo, bas) for k in _DEGIL):
                return False
            return _musaitlik_isle(rows[bas + 1:], ilk - 1, sutunlar, cikti, tablo)
    return _izgara(tablo, cikti)


def genislet(tablolar: list[Tablo]) -> list[Tablo]:
    """Program belgelerini düz tablolara çevirir; diğer tablolar olduğu gibi kalır.

    e-Okul sınıf/öğretmen programı (gün satırı, ders saati sütunu) önce ayrılır; tanınmazsa
    mevcut ızgara, matris ve müsaitlik çözümlemesi kullanılır.
    """
    from . import eokul_program
    out: list[Tablo] = []
    i = 0
    while i < len(tablolar):
        try:
            n, uretilen = eokul_program.eokul_dilimi(tablolar, i)
        except Exception:  # noqa: BLE001 - tanınamayan biçim olağan aktarıma bırakılır
            n, uretilen = 0, []
        if n and uretilen:
            out.extend(uretilen)
            i += n
            continue
        try:
            d = donustur(tablolar[i])
        except Exception:  # noqa: BLE001
            d = None
        out.extend(d or [tablolar[i]])
        i += 1
    return out
