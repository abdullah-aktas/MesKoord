"""e-Okul sınıf ve öğretmen ders programı PDF/Excel çizelgeleri.

Sayfa düzeni: satırlar gün, sütunlar ders saati. Sınıf programında hücre 'DERSKODU' ve öğretmen
kısaltmasıdır ('Y.TSY'); altındaki açıklama tablosu kodu ders adına, haftalık saate, mekâna ve
öğretmene bağlar. Öğretmen programında hücre 'sınıf' ve ders kodudur; sayfa başında ad, nöbet
günü/yeri ve sınıf öğretmenliği kodu yazar. İki öğretmenli (grup) derslerde açıklamadaki ikinci ad
ortak öğretmen olur. Günü yalnızca işletmede mesleki eğitim (IME) olan sınıfların işletme günleri,
dersi olan günler okul günleri olarak yazılır.
"""
from __future__ import annotations

import re

from .aktarim import metin, norm, tr_ad
from .okuyucu import Tablo
from .program_belge import gun_coz

_SESLI = set("AEIİOÖUÜaeıioöuü")
_KISALTMA = re.compile(r"^[A-ZÇĞİÖŞÜ]\.[A-ZÇĞİÖŞÜ]{2,4}$")
_SINIF = re.compile(r"^(9|10|11|12)(?:\s|[A-ZÇĞİÖŞÜ])")
_BOS = {"", "x", "-", "bos"}


def ogretmen_kodu(adsoyad: str) -> str:
    """'YUNUS TOSYALIOĞLU' -> 'Y.TSY'. e-Okul: adın ilk harfi + soyadın ilk harfi ve sonraki ünsüzler."""
    parca = [p for p in metin(adsoyad).split() if p]
    if len(parca) < 2:
        return ""
    return f"{parca[0][0]}.{_soyad_kodu(parca[-1])}"


def _soyad_kodu(soyad: str) -> str:
    """İlk harf + sonraki ünsüzler; 3 harf dolmazsa eksik harfler soyadın sonundan, özgün sırayla.

    KAYA -> KYA (sondaki sesli), ÇEN -> ÇEN (tek sesli arada kalır), KABAK -> KBK (yinelenen ünsüz düşmez).
    """
    harf = [c for c in soyad if c.isalpha()]
    if not harf:
        return ""
    tut = {0}
    for i, c in enumerate(harf):
        if i and c not in _SESLI:
            tut.add(i)
            if len(tut) == 3:
                return "".join(harf[j] for j in sorted(tut))
    for i in range(len(harf) - 1, 0, -1):
        if i not in tut:
            tut.add(i)
            if len(tut) == 3:
                break
    return "".join(harf[j] for j in sorted(tut)[:3])


def _kod_es(a: str, b: str) -> bool:
    def f(s: str) -> str:
        return s.replace("İ", "i").replace("I", "ı").replace(".", "").lower()

    return bool(a and b) and f(a) == f(b)


def _sinif_benzer(s: str) -> bool:
    s = " ".join(metin(s).split())
    return bool(s) and " " in s and len(s) <= 16 and bool(_SINIF.match(s))


def _ime(kod: str, ad: str) -> bool:
    n = norm(f"{kod} {ad}")
    return n == "ime" or "isletmelerde mesleki" in n


def _izgara(tablo: Tablo) -> tuple[int, dict[int, int]] | None:
    for i, r in enumerate(tablo.satirlar[:8]):
        metinler = [metin(c) for c in r]
        if not any("ders" in norm(c) and "gun" in norm(c) for c in metinler):
            continue
        sut = {}
        for j, c in enumerate(metinler):
            m = re.fullmatch(r"\(?(\d{1,2})\)?", c.strip())
            if m and 1 <= int(m.group(1)) <= 16:
                sut[j] = int(m.group(1))
        if len(sut) >= 5:
            return i, sut
    return None


def _legend(tablo: Tablo) -> bool:
    for r in tablo.satirlar[:4]:
        n = norm(" ".join(metin(c) for c in r))
        if "dersin adi" in n or "dersin ogretmeni" in n:
            return True
    return False


def _ozet(tablo: Tablo) -> bool:
    if _legend(tablo) or _izgara(tablo):
        return False
    uygun = 0
    for r in tablo.satirlar[:12]:
        hucre = [metin(c) for c in r if metin(c)]
        if not hucre or any(norm(c) == "toplamlar" for c in hucre):
            continue
        # Ders adı 'KİMYA' gibi kısa da olabilir; kod ve saat sayısından uzun bir sözcük yeter.
        if any(_sinif_benzer(c) for c in hucre) and any(
                len(c) >= 4 and not c.isdigit() and not _sinif_benzer(c) for c in hucre):
            uygun += 1
    return uygun >= 1


def _form_baslik(tablo: Tablo) -> bool:
    if not tablo.form or not tablo.satirlar:
        return False
    n = norm(" ".join(metin(c) for c in tablo.satirlar[0]))
    return any(k in n for k in ("adi soyadi", "sinif ogretmen", "nobet", "ders programi"))


def _aday(tablo: Tablo) -> bool:
    return _izgara(tablo) is not None or _legend(tablo) or _ozet(tablo) or _form_baslik(tablo)


def eokul_dilimi(tablolar: list[Tablo], i: int) -> tuple[int, list[Tablo]]:
    """i. tablodan başlayan aynı dosyadaki e-Okul programını düz aktarım tablolarına çevirir."""
    if i >= len(tablolar) or not _aday(tablolar[i]):
        return 0, []
    kaynak = tablolar[i].kaynak
    j = i
    grup = []
    while j < len(tablolar) and tablolar[j].kaynak == kaynak and _aday(tablolar[j]):
        grup.append(tablolar[j])
        j += 1
    if not any(_izgara(t) for t in grup):
        return 0, []
    uretilen = donustur_grup(grup)
    return (j - i, uretilen) if uretilen else (0, [])


def donustur_grup(tablolar: list[Tablo]) -> list[Tablo]:
    program: list[list] = []
    siniflar: dict[str, dict] = {}
    ogretmenler: dict[str, dict] = {}
    bekleyen: dict | None = None

    def yaz():
        nonlocal bekleyen
        if not bekleyen:
            return
        if bekleyen["tur"] == "sinif":
            _yaz_sinif(bekleyen, program, siniflar)
        else:
            _yaz_ogretmen(bekleyen, program, ogretmenler)
        bekleyen = None

    for t in tablolar:
        if t.form:
            continue
        iz = _izgara(t)
        if iz:
            yaz()
            bekleyen = _izgara_oku(t, iz)
            continue
        if bekleyen and bekleyen["tur"] == "sinif" and _legend(t):
            bekleyen["legend"] = _legend_oku(t)
            yaz()
            continue
        if bekleyen and bekleyen["tur"] == "ogretmen" and _ozet(t):
            bekleyen["ozet"] = _ozet_oku(t)
            yaz()
    yaz()
    return _tablolar(tablolar[0].kaynak if tablolar else "", program, siniflar, ogretmenler)


def _izgara_oku(tablo: Tablo, iz: tuple[int, dict[int, int]]) -> dict:
    bas, sutun = iz
    baglam = "\n".join(" ".join(metin(c) for c in r if metin(c)) for r in tablo.satirlar[:bas])
    tur = "ogretmen" if re.search(r"ad[ıi]\s+soyad[ıi]\s*:", baglam, re.I) else "sinif"
    sinif = ""
    rehber = ""
    if tur == "sinif":
        m = re.search(r"sınıf\s*:\s*(.+?)\s+toplam\b", baglam, re.I) or re.search(
            r"sinif\s*:\s*(.+?)\s+toplam\b", baglam, re.I)
        sinif = " ".join(m.group(1).split()) if m else ""
        r = re.search(r"sınıf öğretmeni\s*:\s*([A-ZÇĞİÖŞÜ][^:\n]{2,})", baglam, re.I)
        if r and "ogretmenligi" not in norm(r.group(0)):
            rehber = tr_ad(" ".join(r.group(1).split()[:4]))
    ad, nobet_gun, nobet_yeri, kod = _ogretmen_baslik(baglam)
    hucreler = []
    for r in tablo.satirlar[bas + 1:]:
        g = gun_coz(metin(r[0]) if r else "")
        if not g or g > 5:
            continue
        for j, saat in sutun.items():
            ham = metin(r[j] if j < len(r) else "")
            if not ham or norm(ham) in _BOS or re.match(r"\d{1,2}[:.]\d{2}", ham):
                continue
            hucreler.append((g, saat, ham))
    return {"tur": tur, "sinif": sinif, "rehber": rehber, "ogretmen": ad, "nobet_gun": nobet_gun,
            "nobet_yeri": nobet_yeri, "sinif_ogretmenligi": kod, "hucreler": hucreler, "legend": {}, "ozet": {}}


def _ogretmen_baslik(baglam: str) -> tuple[str, int | None, str, str]:
    ad = ""
    m = re.search(r"ad[ıi]\s+soyad[ıi]\s*:\s*(.+?)(?:\s+eğitici|\s+egitici|$)", baglam, re.I)
    if m:
        ad = tr_ad(m.group(1).strip(" :"))
    nobet_gun, nobet_yeri = None, ""
    m = re.search(r"nöbet günü ve yeri\s*:\s*(.*)$", baglam, re.I | re.M)
    if not m:
        m = re.search(r"nobet gunu ve yeri\s*:\s*(.*)$", baglam, re.I | re.M)
    if m:
        kalan = m.group(1).strip(" :")
        parca = kalan.split(None, 1)
        if parca:
            g = gun_coz(parca[0])
            if g and g <= 5:
                nobet_gun, nobet_yeri = g, (parca[1].strip() if len(parca) > 1 else "")
            elif kalan:
                nobet_yeri = kalan
    kod = ""
    m = re.search(r"sınıf öğretmenliği\s*:\s*(.+?)(?:\s+nöbet\b|$)", baglam, re.I)
    if not m:
        m = re.search(r"sinif ogretmenligi\s*:\s*(.+?)(?:\s+nobet\b|$)", baglam, re.I)
    if m:
        kod = m.group(1).strip(" :")
        if not kod or norm(kod).startswith("nobet") or len(kod) > 24:
            kod = ""
    return ad, nobet_gun, nobet_yeri, kod


def _legend_oku(tablo: Tablo) -> dict[str, dict]:
    bas = next((i for i, r in enumerate(tablo.satirlar[:4])
                if "dersin adi" in norm(" ".join(metin(c) for c in r))
                or "dersin ogretmeni" in norm(" ".join(metin(c) for c in r))), 0)
    baslik = [norm(c) for c in tablo.satirlar[bas]]

    def bul(fn, varsayilan: int = -1) -> int:
        for j, n in enumerate(baslik):
            if n and fn(n):
                return j
        return varsayilan

    kod_j = bul(lambda n: n == "ders" or ("ders" in n and "adi" not in n and "ogretmen" not in n), 1)
    ad_j = bul(lambda n: "dersin adi" in n or n == "ders adi", 2)
    if kod_j == ad_j:
        kod_j, ad_j = 1, 2
    yer_j = bul(lambda n: n == "yer" or n.startswith("yer "))
    ogr_j = bul(lambda n: "ogretmen" in n, 5)
    out = {}
    for r in tablo.satirlar[bas + 1:]:
        kod = " ".join(metin(r[kod_j] if 0 <= kod_j < len(r) else "").split())
        ad = " ".join(metin(r[ad_j] if 0 <= ad_j < len(r) else "").split())
        if not kod or norm(kod) in ("ders", "s no", "sno") or not ad:
            continue
        ogretmenler = [tr_ad(p) for p in re.split(r"\s*,\s*", metin(r[ogr_j] if 0 <= ogr_j < len(r) else ""))
                       if p.strip()]
        yer = metin(r[yer_j] if 0 <= yer_j < len(r) else "")
        out[_anahtar(kod)] = {"kod": kod, "ad": ad, "yer": yer, "ogretmenler": ogretmenler}
    return out


def _ozet_oku(tablo: Tablo) -> dict[tuple[str, str], str]:
    """(sınıf, ders kodu) -> dersin tam adı. Sütun kayması olsa da sınıf ve uzun ad aranır."""
    out = {}
    for r in tablo.satirlar:
        hucre = [metin(c) for c in r]
        if any(norm(c) == "toplamlar" for c in hucre):
            continue
        siniflar = [c for c in hucre if _sinif_benzer(c)]
        if not siniflar:
            continue
        sinif = siniflar[0]
        j = hucre.index(sinif)
        kod, ad = "", ""
        for c in hucre[j + 1:]:
            if not c or c == sinif:
                continue
            if not kod and len(c) <= 16 and not c.isdigit():
                kod = " ".join(c.split())
            elif kod and len(c) > len(kod):
                ad = " ".join(c.split())
                break
        if sinif and kod and ad:
            out[(_anahtar(sinif), _anahtar(kod))] = ad
    return out


def _anahtar(s: str) -> str:
    return " ".join(s.replace("İ", "i").replace("I", "ı").split()).lower()


def _bol_sinif_hucre(ham: str) -> tuple[str, str]:
    satirlar = [p.strip() for p in re.split(r"[\r\n]+", ham) if p.strip()]
    if len(satirlar) >= 2 and _KISALTMA.match(satirlar[-1].replace(" ", "")):
        return " ".join(" ".join(satirlar[:-1]).split()), satirlar[-1].replace(" ", "")
    tok = ham.split()
    if tok and _KISALTMA.match(tok[-1]):
        return " ".join(tok[:-1]), tok[-1]
    return " ".join(ham.split()), ""


def _bol_ogretmen_hucre(ham: str, siniflar: list[str]) -> tuple[str, str]:
    satirlar = [p.strip() for p in re.split(r"[\r\n]+", ham) if p.strip()]
    if len(satirlar) >= 2 and _sinif_benzer(satirlar[0]):
        return " ".join(satirlar[0].split()), " ".join(" ".join(satirlar[1:]).split())
    duz = " ".join(ham.split())
    for ad in sorted(siniflar, key=len, reverse=True):
        if duz == ad or duz.startswith(ad + " "):
            return ad, duz[len(ad):].strip()
    return "", duz


def _ogretmen_sec(kisaltma: str, adlar: list[str]) -> tuple[str, str]:
    if not adlar:
        return "", ""
    es = next((a for a in adlar if _kod_es(ogretmen_kodu(a), kisaltma)), None) if kisaltma else None
    bir = es or adlar[0]
    diger = next((a for a in adlar if a != bir), "")
    return bir, diger


def _yaz_sinif(b: dict, program: list, siniflar: dict) -> None:
    if not b["sinif"] or not b["hucreler"]:
        return
    legend = b["legend"]
    okul, isletme = set(), set()
    gun_normal: dict[int, int] = {}
    gun_ime: dict[int, int] = {}
    for g, saat, ham in b["hucreler"]:
        kod, kis = _bol_sinif_hucre(ham)
        bilgi = legend.get(_anahtar(kod), {})
        ad = bilgi.get("ad") or kod
        if not ad:
            continue
        if _ime(kod, ad):
            gun_ime[g] = gun_ime.get(g, 0) + 1
        else:
            gun_normal[g] = gun_normal.get(g, 0) + 1
        bir, iki = _ogretmen_sec(kis, bilgi.get("ogretmenler") or [])
        program.append([b["sinif"], g, saat, ad, bilgi.get("kod") or kod, bir, iki or None, bilgi.get("yer") or None])
    for g in set(gun_normal) | set(gun_ime):
        if gun_normal.get(g):
            okul.add(g)
        elif gun_ime.get(g):
            isletme.add(g)
    kayit = siniflar.setdefault(b["sinif"], {"okul": set(), "isletme": set(), "rehber": ""})
    kayit["okul"] |= okul
    kayit["isletme"] |= isletme
    if b["rehber"]:
        kayit["rehber"] = b["rehber"]


def _yaz_ogretmen(b: dict, program: list, ogretmenler: dict) -> None:
    if b["ogretmen"]:
        kayit = ogretmenler.setdefault(b["ogretmen"], {"nobet_gun": None, "nobet_yeri": "", "sinif_ogretmenligi": ""})
        if b["nobet_gun"]:
            kayit["nobet_gun"] = b["nobet_gun"]
            kayit["nobet_yeri"] = b["nobet_yeri"]
        if b["sinif_ogretmenligi"]:
            kayit["sinif_ogretmenligi"] = b["sinif_ogretmenligi"]
    for g, saat, ham in b["hucreler"]:
        sinif, kod = _bol_ogretmen_hucre(ham, _ozet_sinif_yazim(b["ozet"], ham))
        if not sinif or not kod:
            continue
        ders = b["ozet"].get((_anahtar(sinif), _anahtar(kod))) or kod
        program.append([sinif, g, saat, ders, kod, b["ogretmen"], None, None])


def _ozet_sinif_yazim(ozet: dict, ham: str) -> list[str]:
    """Özet anahtarı küçük harflidir; hücredeki yazımı (ör. '10EE A') bölmede kullanılır."""
    duz = " ".join(p.strip() for p in re.split(r"[\r\n]+", ham) if p.strip())
    bulunan = []
    for sinif_a, _kod in ozet:
        # anahtar küçük; hücrede aynı dizinin özgün halini aramak için ham metinde ara
        m = re.search(re.escape(sinif_a).replace(r"\ ", r"\s+"), duz, re.I)
        if m:
            bulunan.append(" ".join(m.group(0).split()))
    if not bulunan:
        ilk = re.split(r"[\r\n]+", ham)[0].strip()
        if _sinif_benzer(ilk):
            bulunan.append(" ".join(ilk.split()))
    return bulunan


def _tablolar(kaynak: str, program: list, siniflar: dict, ogretmenler: dict) -> list[Tablo]:
    out = []
    if ogretmenler:
        out.append(Tablo(kaynak, "e-Okul öğretmenleri", [
            ["Adı Soyadı", "Nöbet Günü", "Nöbet Yeri", "Sınıf Öğretmenliği"],
            *[[ad, k["nobet_gun"] or "", k["nobet_yeri"], k["sinif_ogretmenligi"]]
              for ad, k in ogretmenler.items()]]))
    if siniflar:
        out.append(Tablo(kaynak, "e-Okul sınıfları", [
            ["Sınıf/Şube", "Okul Günleri", "İşletme Günleri", "Rehber Öğretmen", "Program"],
            *[[ad, ",".join(map(str, sorted(k["okul"]))) or "-",
               ",".join(map(str, sorted(k["isletme"]))) or "-", k["rehber"],
               "MEM" if "msm" in norm(ad).split() or "mesem" in norm(ad) else ""]
              for ad, k in siniflar.items()]]))
    if program:
        out.append(Tablo(kaynak, "e-Okul haftalık ders programı", [
            ["Sınıf/Şube", "Gün", "Ders Saati (1, 2, ...)", "Ders Adı", "Kısa Ad", "Öğretmen Adı Soyadı",
             "2. Öğretmen (grup/ortak ders)", "Atölye/Lab./Derslik"],
            *program]))
    return out
