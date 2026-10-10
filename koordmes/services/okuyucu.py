"""Çok biçimli tablo okuyucu.

Desteklenen biçimler: Excel (.xlsx/.xlsm/.xls), LibreOffice (.ods), CSV/TXT/TSV, Word (.docx),
PDF, HTML (e-Okul'un .xls uzantılı HTML çıktıları dahil) ve JSON. Biçim, uzantıdan önce dosya
içeriğinden belirlenir. Her dosyadan bir veya daha çok `Tablo` döner (çalışma sayfaları, Word/PDF
tabloları, "Etiket: Değer" biçimindeki form alanları).
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

UZANTILAR = [".xlsx", ".xlsm", ".xls", ".ods", ".csv", ".txt", ".tsv", ".docx", ".pdf", ".html", ".htm", ".json",
             ".zip"]
DOSYA_FILTRESI = ("Desteklenen dosyalar (" + " ".join(f"*{u}" for u in UZANTILAR) + ");;"
                  "Excel (*.xlsx *.xlsm *.xls);;Word (*.docx);;PDF (*.pdf);;CSV / Metin (*.csv *.txt *.tsv);;"
                  "ZIP arşivi (*.zip);;Tüm dosyalar (*.*)")
_ARSIV_AZAMI = 50 * 1024 * 1024


@dataclass
class Tablo:
    kaynak: str
    ad: str
    satirlar: list[list[Any]] = field(default_factory=list)
    form: bool = False  # "Etiket: Değer" listesinden oluşturulmuş tek kayıtlık tablo

    @property
    def etiket(self) -> str:
        return f"{self.kaynak} › {self.ad}"

    @property
    def sutun_sayisi(self) -> int:
        return max((len(r) for r in self.satirlar), default=0)


class OkumaHatasi(ValueError):
    pass


def oku(yol: Path | str) -> list[Tablo]:
    yol = Path(yol)
    if not yol.exists():
        raise OkumaHatasi(f"Dosya bulunamadı: {yol}")
    ham = yol.read_bytes()
    ext = yol.suffix.lower()
    ad = yol.name
    if ham[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(ham)) as z:
            isimler = set(z.namelist())
        if "word/document.xml" in isimler:
            tablolar = _docx(yol, ad)
        elif "xl/workbook.xml" in isimler:
            tablolar = _xlsx(yol, ad)
        elif "content.xml" in isimler:
            tablolar = _ods(ham, ad)
        else:
            return _arsiv(ham, ad)
    elif ham[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        if ext == ".doc":
            raise OkumaHatasi(f"{ad}: eski Word (.doc) biçimi okunamaz. Word'de açıp .docx olarak kaydedin.")
        tablolar = _xls(yol, ad)
    elif ham[:5] == b"%PDF-":
        tablolar = _pdf(yol, ad)
    else:
        metin = _coz(ham)
        bas = metin.lstrip()[:500].lower()
        if ext == ".json" or bas.startswith(("[", "{")):
            tablolar = _json(metin, ad)
        elif bas.startswith("<") and ("<table" in metin.lower() or "<html" in bas):
            tablolar = _html(metin, ad)
        elif ext in (".rtf",) or bas.startswith("{\\rtf"):
            raise OkumaHatasi(f"{ad}: RTF biçimi desteklenmiyor. Word'de açıp .docx olarak kaydedin.")
        else:
            tablolar = _metin(metin, ad)
    tablolar = [t for t in (_temizle(t) for t in tablolar) if t.satirlar]
    if not tablolar:
        raise OkumaHatasi(f"{ad}: dosyada okunabilir tablo bulunamadı. Taranmış (resim) PDF'ler okunamaz.")
    return tablolar


def oku_coklu(yollar: list[Path | str]) -> tuple[list[Tablo], list[str]]:
    tablolar, hatalar = [], []
    for y in yollar:
        try:
            tablolar.extend(oku(y))
        except Exception as e:  # dosya bazında hata raporlanır
            hatalar.append(str(e) if isinstance(e, OkumaHatasi) else f"{Path(y).name}: {e}")
    return tablolar, hatalar


# ------------------------------------------------------------------ biçim okuyucuları

def _arsiv(ham: bytes, ad: str) -> list[Tablo]:
    """ZIP arşivindeki desteklenen dosyalar (e-Okul/e-Mesem toplu indirmeleri)."""
    import tempfile
    out: list[Tablo] = []
    hatalar: list[str] = []
    with zipfile.ZipFile(io.BytesIO(ham)) as z, tempfile.TemporaryDirectory() as gecici:
        for bilgi in z.infolist():
            ic = Path(bilgi.filename)
            if bilgi.is_dir() or ic.suffix.lower() not in UZANTILAR or ic.suffix.lower() == ".zip":
                continue
            if bilgi.file_size > _ARSIV_AZAMI:
                hatalar.append(f"{ic.name}: çok büyük")
                continue
            hedef = Path(gecici) / f"{len(out)}_{ic.name}"
            hedef.write_bytes(z.read(bilgi))
            try:
                for t in oku(hedef):
                    t.kaynak = f"{ad} › {ic.name}"
                    out.append(t)
            except OkumaHatasi as e:
                hatalar.append(str(e).replace(hedef.name, ic.name))
    if not out:
        ek = (" (" + "; ".join(hatalar) + ")") if hatalar else ""
        raise OkumaHatasi(f"{ad}: arşivde okunabilir tablo bulunamadı{ek}.")
    return out


# Tablonun üstündeki metinden yalnızca bağlam bilgisi taşıyan satırlar (sınıf/şube, dönem, belge türü, işletme,
# alan/dal) tabloya eklenir; okul adı gibi başlıklar eklenmez.
_AY_ADLARI = ("ocak", "subat", "mart", "nisan", "mayis", "haziran", "temmuz", "agustos", "eylul", "ekim", "kasim",
              "aralik")
_BAGLAM_ETIKETI = re.compile(r"(^| )(sinif\w*|sube\w*|donem\w*|belge turu|alan\w*|dal\w*|isletme\w*|isyeri\w*|"
                             r"is yeri\w*|ogretmen\w*|koordinator\w*|yil ay|hizmet donemi)( |$)")


def baglam_satiri_mi(s: str) -> bool:
    s = s.strip()
    if not s or len(s) > 160:
        return False
    sade = _sade(s)
    if ":" in s and _BAGLAM_ETIKETI.search(_sade(s.split(":")[0]) + " "):
        return True
    # e-Okul öğretmen programının sayfa başlığı. _sade 'ı' harfini düşürdüğü için başlık ayrıca katlanır.
    kat = s.replace("İ", "i").replace("I", "ı").replace("ı", "i").lower().translate(_TR)
    kat = re.sub(r"[^a-z0-9:]+", " ", kat)
    if re.search(r"(adi soyadi|nobet gunu|sinif ogretmenligi)\s*:", kat):
        return True
    if re.search(r"(^| )(sinif\w*|sube\w*)( |$)", sade) and re.search(r"\b(9|10|11|12)\b", sade):
        return True
    return bool(re.search(r"\b20\d\d\b", sade)) and any(re.search(rf"(^| ){a}( |$)", sade) for a in _AY_ADLARI)


def _etiket_deger_metni(hucreler: list[str]) -> str:
    """['Alanı', 'Elektrik'] -> 'Alanı: Elektrik' (bilgi tablolarındaki etiket-değer satırları)."""
    if len(hucreler) == 2 and ":" not in hucreler[0] and len(hucreler[0]) <= 30 \
            and _BAGLAM_ETIKETI.search(_sade(hucreler[0]) + " "):
        return f"{hucreler[0]}: {hucreler[1]}"
    return " ".join(hucreler)


def _onsoz_satirlari(metinler: list[str], genislik: int, azami: int = 6) -> list[list[Any]]:
    secilen = [m.strip() for m in metinler if baglam_satiri_mi(m)][-azami:]
    return [[m] + [""] * (genislik - 1) for m in secilen]


def _coz(ham: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16") if ham[:2] in (b"\xff\xfe", b"\xfe\xff") else ("utf-8-sig", "cp1254"):
        try:
            return ham.decode(enc)
        except UnicodeDecodeError:
            continue
    return ham.decode("latin-1")


def _xlsx(yol: Path, ad: str) -> list[Tablo]:
    from openpyxl import load_workbook
    wb = load_workbook(yol, read_only=True, data_only=True)
    out = []
    try:
        for ws in wb.worksheets:
            out.append(Tablo(ad, ws.title, [list(r) for r in ws.iter_rows(values_only=True)]))
    finally:
        wb.close()
    return out


def _xls(yol: Path, ad: str) -> list[Tablo]:
    import xlrd
    book = xlrd.open_workbook(str(yol))
    out = []
    for sh in book.sheets():
        rows = []
        for i in range(sh.nrows):
            row = []
            for j in range(sh.ncols):
                c = sh.cell(i, j)
                if c.ctype == xlrd.XL_CELL_DATE:
                    row.append(xlrd.xldate.xldate_as_datetime(c.value, book.datemode))
                elif c.ctype == xlrd.XL_CELL_NUMBER and float(c.value).is_integer():
                    row.append(int(c.value))
                else:
                    row.append(c.value)
            rows.append(row)
        out.append(Tablo(ad, sh.name, rows))
    return out


_ODS = {"table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
        "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
        "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0"}


def _ods(ham: bytes, ad: str) -> list[Tablo]:
    with zipfile.ZipFile(io.BytesIO(ham)) as z:
        kok = ET.fromstring(z.read("content.xml"))
    T, O = "{%s}" % _ODS["table"], "{%s}" % _ODS["office"]
    out = []
    for tablo in kok.iter(T + "table"):
        rows = []
        for tr in tablo.iter(T + "table-row"):
            row: list[Any] = []
            for td in tr:
                if td.tag not in (T + "table-cell", T + "covered-table-cell"):
                    continue
                tip = td.get(O + "value-type")
                if tip in ("float", "percentage", "currency"):
                    v: Any = float(td.get(O + "value"))
                    v = int(v) if v.is_integer() else v
                elif tip == "date":
                    try:
                        v = datetime.fromisoformat(td.get(O + "date-value")[:19])
                    except ValueError:
                        v = td.get(O + "date-value")
                else:
                    v = "\n".join("".join(p.itertext()) for p in td.iter("{%s}p" % _ODS["text"])) or None
                tekrar = min(int(td.get(T + "number-columns-repeated", "1")), 200)
                row.extend([v] * tekrar)
            satir_tekrar = min(int(tr.get(T + "number-rows-repeated", "1")), 1 if not any(row) else 50)
            rows.extend([list(row) for _ in range(satir_tekrar)])
        out.append(Tablo(ad, tablo.get(T + "name") or f"Tablo {len(out) + 1}", rows))
    return out


def _metin(metin: str, ad: str) -> list[Tablo]:
    satirlar = [s for s in metin.splitlines() if s.strip()]
    if not satirlar:
        return []
    ornek = "\n".join(satirlar[:50])
    try:
        dialect = csv.Sniffer().sniff(ornek, delimiters=";,\t|")
        rows = [list(r) for r in csv.reader(satirlar, dialect)]
        if max(len(r) for r in rows) > 1:
            return [Tablo(ad, "Liste", rows)]
    except csv.Error:
        pass
    rows = [re.split(r"\s{2,}|\t", s.strip()) for s in satirlar]
    tablolar = []
    if max(len(r) for r in rows) > 1:
        tablolar.append(Tablo(ad, "Liste", rows))
    form = _form_tablosu(satirlar, ad)
    if form:
        tablolar.append(form)
    return tablolar


class _HtmlTablolari(HTMLParser):
    _SATIR_SONU = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr", "caption"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tablolar: list[list[list[str]]] = []
        self.onsozler: list[list[str]] = []  # her tablonun üstündeki tablo dışı metin satırları
        self._yigin: list[list[list[str]]] = []
        self._hucre: list[str] | None = None
        self._colspan = 1
        self._dis: list[str] = [""]
        self._bekleyen: list[list[str]] = []
        self._atla = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._atla += 1
        elif tag in self._SATIR_SONU and not self._yigin:
            self._dis.append("")
        if tag == "table":
            if not self._yigin:
                self._bekleyen.append([s.strip() for s in self._dis if s.strip()])
                self._dis = [""]
            self._yigin.append([])
        elif tag == "tr" and self._yigin:
            self._yigin[-1].append([])
        elif tag in ("td", "th") and self._yigin:
            if not self._yigin[-1]:
                self._yigin[-1].append([])
            self._hucre = []
            try:
                self._colspan = max(1, min(50, int(dict(attrs).get("colspan") or 1)))
            except ValueError:
                self._colspan = 1
        elif tag == "br" and self._hucre is not None:
            self._hucre.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._hucre is not None and self._yigin:
            metin = re.sub(r"\s+", " ", "".join(self._hucre)).strip()
            self._yigin[-1][-1].extend([metin] + [""] * (self._colspan - 1))
            self._hucre = None
        elif tag == "table" and self._yigin:
            self.tablolar.append(self._yigin.pop())
            self.onsozler.append(self._bekleyen.pop() if not self._yigin and self._bekleyen else [])
        elif tag in ("script", "style") and self._atla:
            self._atla -= 1
        elif tag in self._SATIR_SONU and not self._yigin:
            self._dis.append("")

    def handle_data(self, data):
        if self._hucre is not None:
            self._hucre.append(data)
        elif not self._yigin and not self._atla:
            self._dis[-1] += re.sub(r"\s+", " ", data)


def _html(metin: str, ad: str) -> list[Tablo]:
    p = _HtmlTablolari()
    p.feed(metin)
    out = []
    tasinan: list[str] = []  # yalnızca bağlam satırlarından oluşan küçük bilgi tabloları sonraki tabloya eklenir
    for t, onsoz in zip(p.tablolar, p.onsozler):
        satirlar = [_etiket_deger_metni([h for h in r if h]) for r in t]
        satirlar = [s for s in satirlar if s.strip()]
        if not satirlar:
            continue
        if len(satirlar) <= 4 and all(baglam_satiri_mi(s) for s in satirlar):
            tasinan += onsoz + satirlar
            continue
        rows = [list(r) for r in t]
        rows = _onsoz_satirlari(tasinan + onsoz, max(len(r) for r in rows) or 1, 10) + rows
        tasinan = []
        out.append(Tablo(ad, f"Tablo {len(out) + 1}", rows))
    if tasinan and not out:
        out.append(Tablo(ad, "Bilgiler", [[s] for s in tasinan]))
    return out


def _docx_satirlari(t) -> list[list[str | None]]:
    rows = []
    for r in t.rows:
        row, onceki = [], None
        for c in r.cells:
            if c._tc is onceki:  # yatay birleştirilmiş hücre tekrarı
                row.append(None)
                continue
            onceki = c._tc
            row.append(c.text.strip())
        rows.append(row)
    return rows


def _form_satirlari(rows: list[list[str | None]]) -> list[str]:
    """Tablo satırlarını form satırlarına çevirir: tek hücre = bölüm başlığı, iki hücre = 'Etiket : Değer',
    dört hücre = iki etiket-değer çifti (imza tabloları hariç)."""
    imza = any("imza" in _sade(c or "") for r in rows for c in r)
    out = []
    for r in rows:
        h = [c for c in r if c is not None]
        if len(h) == 1 and h[0]:
            out.append(h[0])
        elif len(h) == 2 and h[0]:
            out.append(f"{h[0]} : {h[1]}")
        elif len(h) == 4 and not imza and h[0] and h[2] and len(h[0]) <= 45 and len(h[2]) <= 45:
            out += [f"{h[0]} : {h[1]}", f"{h[2]} : {h[3]}"]
    return out


def _docx(yol: Path, ad: str) -> list[Tablo]:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    doc = Document(str(yol))
    out: list[Tablo] = []
    paragraflar: list[str] = []
    form_satirlari: list[str] = []  # belge sırasıyla: bölüm başlıkları tablolarla birlikte okunur
    onceki: list[str] = []  # son tablodan bu yana gelen paragraflar (sınıf/dönem başlıkları)
    for el in doc.element.body.iterchildren():
        if el.tag == qn("w:p"):
            metin = Paragraph(el, doc).text
            if metin.strip():
                paragraflar.append(metin)
                form_satirlari += [s for s in metin.splitlines() if s.strip()]
                onceki += [s for s in metin.splitlines() if s.strip()]
        elif el.tag == qn("w:tbl"):
            rows = _docx_satirlari(Table(el, doc))
            genislik = max((len(r) for r in rows), default=1)
            out.append(Tablo(ad, f"Tablo {len(out) + 1}", _onsoz_satirlari(onceki, genislik) + rows))
            onceki = []
            form_satirlari += _form_satirlari(rows)
    sekmeli = [p.split("\t") for p in paragraflar if "\t" in p.strip()]
    if len(sekmeli) >= 2 and max(len(r) for r in sekmeli) > 1:
        out.append(Tablo(ad, "Metin listesi", sekmeli))
    form = _form_tablosu(form_satirlari, ad)
    if form:
        out.append(form)
    return out


def _pdf(yol: Path, ad: str) -> list[Tablo]:
    try:
        import pdfplumber
    except ImportError as e:  # pragma: no cover - paket kurulu değilse
        raise OkumaHatasi("PDF okumak için pdfplumber paketi gerekli.") from e
    out: list[Tablo] = []
    metin_satirlari: list[str] = []
    with pdfplumber.open(str(yol)) as pdf:
        # Sayfalara bölünmüş aynı tablo birleştirilir; her sayfa/tablo üstündeki sınıf, dönem gibi bilgiler
        # ara satır olarak eklenir ki farklı sınıfların listeleri tek tabloda birleşince sınıf bilgisi kaybolmasın.
        birlesik: list[list[Any]] | None = None
        bas_satiri: list[Any] | None = None
        for sayfa in pdf.pages:
            try:
                bulunan = sayfa.find_tables()
                satirlar_ = sayfa.extract_text_lines() if bulunan else []
            except Exception:  # bozuk sayfa: tablo yok sayılır
                bulunan, satirlar_ = [], []
            ust_sinir = 0.0
            for tb in bulunan:
                ust = [s["text"] for s in satirlar_ if s["bottom"] <= tb.bbox[1] + 1 and s["top"] >= ust_sinir - 1]
                ust_sinir = tb.bbox[3]
                t = [[_pdf_metni(c).strip() for c in r] for r in (tb.extract() or []) if r]
                if not t:
                    continue
                if not _gunlu_izgara(t) and not _eokul_izgarasi(t):
                    # Satır sonu ders/öğretmen ya da sınıf/ders kodu ayırır; e-Okul ızgarasında da korunur.
                    t = [[c.replace("\n", " ") for c in r] for r in t]
                t = _sutunlari_sikistir(t)
                onsoz = _onsoz_satirlari([_pdf_metni(s) for s in ust], len(t[0]))
                if birlesik and len(t[0]) == len(bas_satiri):
                    birlesik.extend(onsoz + (t[1:] if t[0] == bas_satiri else t))
                else:
                    if birlesik:
                        out.append(Tablo(ad, f"Tablo {len(out) + 1}", birlesik))
                    birlesik, bas_satiri = onsoz + t, t[0]
            metin_satirlari.extend(_pdf_metni(sayfa.extract_text(layout=True)).splitlines())
        if birlesik:
            out.append(Tablo(ad, f"Tablo {len(out) + 1}", birlesik))
    satirlar = [s for s in metin_satirlari if s.strip()]
    if not out and satirlar:
        rows = [re.split(r"\s{2,}", s.strip()) for s in satirlar]
        if sum(1 for r in rows if len(r) > 2) >= 2:
            out.append(Tablo(ad, "Metin tablosu", rows))
    form = _form_tablosu(satirlar, ad)
    if form:
        out.append(form)
    return out


_GUN_ADI = re.compile(r"^(pazartesi|sal[ıi]|[çc]ar[şs]amba|per[şs]embe|cuma|cumartesi|pzt|[çc]r[şs]|pr[şs])\b",
                      re.I)


def _gunlu_izgara(rows: list[list[str]]) -> bool:
    return any(sum(1 for c in r if _GUN_ADI.match((c or "").strip().replace("I", "ı").replace("İ", "i").lower()))
               >= 3 for r in rows[:4])


def _eokul_izgarasi(rows: list[list[str]]) -> bool:
    """e-Okul sınıf/öğretmen programı: 'Ders\\Gün' satırında (1) (2) (3) ... sütunları."""
    for r in rows[:8]:
        metinler = [(c or "").strip() for c in r]
        if not any(re.search(r"ders", c, re.I) and re.search(r"g[uü]n", c, re.I) for c in metinler):
            continue
        if sum(1 for c in metinler if re.fullmatch(r"\(\d{1,2}\)", c)) >= 5:
            return True
    return False


_CID = re.compile(r"\(cid:\d+\)")


def _pdf_metni(s: str | None) -> str:
    # Karakter eşlemesi eksik glifler (cid:N) olarak gelir; Türkçe PDF'lerde bu neredeyse her zaman "i" harfidir.
    return _CID.sub("i", s or "")


def _sutunlari_sikistir(rows: list[list[str]]) -> list[list[str]]:
    """Çift çizgili PDF tablolarında kaymış hücreleri toplar: hiçbir satırda birlikte dolu olmayan komşu sütunlar
    aynı sütundur."""
    n = max(len(r) for r in rows)
    rows = [list(r) + [""] * (n - len(r)) for r in rows]
    gruplar = [[0]]
    for j in range(1, n):
        if any(r[j] and any(r[k] for k in gruplar[-1]) for r in rows):
            gruplar.append([j])
        else:
            gruplar[-1].append(j)
    if len(gruplar) == n:
        return rows
    return [[next((r[k] for k in g if r[k]), "") for g in gruplar] for r in rows]


def _json(metin: str, ad: str) -> list[Tablo]:
    try:
        veri = json.loads(metin)
    except json.JSONDecodeError as e:
        raise OkumaHatasi(f"{ad}: JSON çözülemedi ({e}).") from e
    gruplar = veri.items() if isinstance(veri, dict) else [("Liste", veri)]
    out = []
    for isim, liste in gruplar:
        if not isinstance(liste, list) or not liste or not all(isinstance(x, dict) for x in liste):
            continue
        anahtarlar: list[str] = []
        for x in liste:
            anahtarlar += [k for k in x if k not in anahtarlar]
        out.append(Tablo(ad, str(isim), [anahtarlar] + [[x.get(k) for k in anahtarlar] for x in liste]))
    return out


# ------------------------------------------------------------------ yardımcılar

_FORM = re.compile(r"^\s*([^:]{2,60}?)\s*:\s*(.+?)\s*$")
_AZAMI_DEGER = 200  # daha uzun "Etiket: ..." satırları sözleşme maddesidir, alan değildir

# Bölüm başlıklarından ve etiketlerden anlaşılan kişi/kurum. Sıra önemlidir: "Öğrenci Velisi" velidir.
_VARLIKLAR = (("usta", ("usta ogretici", "egitici personel", "usta egitici")),
              ("veli", ("veli", "vasi")),
              ("isletme", ("isletme", "isveren", "isyeri", "firma")),
              ("ogrenci", ("ogrenci", "cirak", "kursiyer", "stajyer")))
_ONEK = {"ogrenci": "Öğrenci", "veli": "Veli", "usta": "Usta Öğretici", "isletme": "İşletme"}
# Bölüm içinde bu sözcüklerle başlayan etiketler o bölümün kişisine/kurumuna aittir ("Adres" -> "İşletme Adres")
_ONEKLENIR = {"ad", "adi", "soyad", "soyadi", "isim", "ismi", "adres", "adresi", "telefon", "telefonu", "tel", "gsm",
              "cep", "faks", "t", "tc", "kimlik", "e", "eposta", "mail", "iban", "banka", "hesap", "vergi", "sgk",
              "sicil", "yetkili", "okul", "numara", "numarasi", "no", "sinif", "sinifi", "sube", "alan", "alani", "dal",
              "dali", "dogum", "cinsiyet", "cinsiyeti", "personel", "calisan", "unvan", "unvani", "statu", "statusu",
              "baba", "anne", "yakinlik", "meslek", "mesleki"}
# Sözleşme metninden çıkarılan değerler (tabloda ayrıca yazmıyorsa)
_METIN_KALIPLARI = (
    ("Başlangıç Tarihi", re.compile(r"(\d{1,2}[./]\d{1,2}[./]\d{4})\s*(?:tarihinde|tarihi itibar\w*(?:la)?)\s+"
                                    r"ba[sş]la", re.I)),
    ("Bitiş Tarihi", re.compile(r"(\d{1,2}[./]\d{1,2}[./]\d{4})\s*tarihinde\s+(?:sona\s+erer|biter|tamamlan)", re.I)),
    ("Aylık Ücret", re.compile(r"ayl[ıi]k\s+(\d[\d.]*(?:,\d{1,2})?)\s*(?:TL|₺)", re.I)),
)
_TELEFONLU = re.compile(r"^(.*?)\s*\(\s*(\+?\d[\d\s()\-]{6,})\s*\)\s*$")
_TR = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def _temiz_deger(d: str) -> str:
    """Boş form noktalarını ('......', '___') atar; 'Mah.' gibi kısaltmaların noktası kalır."""
    d = re.sub(r"(\s*[.…_]{2,}\s*)+$", "", d.strip())
    return re.sub(r"^(\s*[.…_]{2,}\s*)+", "", d).strip()


def _sade(s: str) -> str:
    s = s.replace("İ", "i").replace("I", "ı").lower().translate(_TR)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _varlik(s: str) -> str | None:
    sade = _sade(s)
    for kod, kelimeler in _VARLIKLAR:
        if any(re.search(r"(^| )" + k, sade) for k in kelimeler):
            return kod
    return None


def _baslik_mi(s: str) -> bool:
    s = s.strip()
    if not s or ":" in s or len(s) > 80:
        return False
    harfler = [c for c in s if c.isalpha()]
    if harfler and sum(c.isupper() for c in harfler) / len(harfler) >= 0.6:
        return True
    return bool(re.match(r"^[A-ZÇĞİÖŞÜ0-9]{1,3}[).\-]\s", s)) or "bilgi" in _sade(s)


def _bol(etiket: str, deger: str) -> list[tuple[str, str]]:
    """'Adres / Telefon' : 'X / Y' -> [('Adres', 'X'), ('Telefon', 'Y')]. Değer parçaları tutmazsa etiketin ilk
    parçası kullanılır ('Veli / Vasi' gibi eş anlamlı etiketler)."""
    for ayrac, deger_ayraclari in ((" / ", (r"\s+/\s+", r"\s*/\s*")), (" - ", (r"\s+-\s+",))):
        if ayrac not in etiket:
            continue
        parcalar = [p.strip() for p in etiket.split(ayrac) if p.strip()]
        for d_ayrac in deger_ayraclari:
            degerler = [d.strip() for d in re.split(d_ayrac, deger)]
            if len(degerler) == len(parcalar):
                return list(zip(parcalar, degerler))
        return [(parcalar[0], deger)]
    return [(etiket, deger)]


def _form_tablosu(satirlar: list[str], ad: str) -> Tablo | None:
    """'Etiket: Değer' satırlarından tek kayıtlık bir tablo üretir (doldurulmuş form/sözleşme).

    Bölüm başlıkları ("A) ÖĞRENCİ BİLGİLERİ", "İŞLETME BİLGİLERİ") izlenir; bölümdeki genel etiketlere bölümün
    adı eklenir ("Adres" -> "İşletme Adres"). Böylece aynı etiketin öğrenci ve işletme için ayrı değerleri
    kaybolmaz. Bileşik etiketler ("Okul No / Sınıf") ayrı alanlara bölünür."""
    etiketler: list[str] = []
    degerler: list[str] = []
    bolum: str | None = None

    def ekle(e: str, d: str) -> None:
        if e and d and e not in etiketler:
            etiketler.append(e)
            degerler.append(d)

    for s in satirlar:
        if _baslik_mi(s):
            bolum = _varlik(s)
            continue
        for parca in re.split(r"\s{3,}|\t+", s):
            m = _FORM.match(parca)
            if not m or m.group(1).strip().isdigit():
                continue
            etiket, deger = m.group(1).strip(), _temiz_deger(m.group(2))
            if len(deger) > _AZAMI_DEGER or re.match(r"(madde|md) \d", _sade(etiket)):
                continue
            ana = _varlik(etiket)
            for e, d in _bol(etiket, deger):
                d = _temiz_deger(d)
                if _varlik(e) is None:
                    if ana:
                        e = f"{_ONEK[ana]} {e}"
                    elif bolum and (_sade(e).split() or [""])[0] in _ONEKLENIR:
                        e = f"{_ONEK[bolum]} {e}"
                tel = _TELEFONLU.match(d)
                if tel and not re.search(r"tel|gsm|cep", _sade(e)):
                    ekle(e, tel.group(1).strip())
                    ekle(f"{e} Telefon", re.sub(r"\s+", " ", tel.group(2)).strip())
                else:
                    ekle(e, d)
    tum = " ".join(satirlar)
    for e, kalip in _METIN_KALIPLARI:
        m = kalip.search(tum)
        if m and not any(_sade(e) in _sade(x) for x in etiketler):
            ekle(e, m.group(1))
    if len(etiketler) < 3:
        return None
    return Tablo(ad, "Form alanları", [etiketler, degerler], form=True)


def _temizle(t: Tablo) -> Tablo:
    rows = []
    for r in t.satirlar:
        r = [(v.strip() or None) if isinstance(v, str) else v for v in r]
        if any(v not in (None, "") for v in r):
            rows.append(r)
    if rows:
        genislik = max(len(r) for r in rows)
        dolu = [any(j < len(r) and r[j] not in (None, "") for r in rows) for j in range(genislik)]
        son = max((j for j, d in enumerate(dolu) if d), default=-1) + 1
        rows = [(r + [None] * genislik)[:son] for r in rows]
    t.satirlar = rows
    return t
