"""Ortaöğretim Kurumları Yönetmeliğinin işletmelerde mesleki eğitim hükümleri.

* md.136: işletmeye gönderilecek öğrencilerin seçimi ve sıralaması
* md.89/1-g, md.144/1-g: puan çizelgelerinin dönem sonundan önce teslimi
* md.89/2, md.82/2-ğ: alan taraması ve işletme talepleri
* md.89/1-ğ, md.82/2-g: mezun ve işyeri anketleri
* md.82/2-b, md.144/1-ç: usta öğretici hizmetiçi eğitim programı
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .. import config
from ..mevzuat import OKUL_ICI_TURLER
from .excel_io import ExcelYazici, tablo_yaz
from .utils import tarih, tr

GONDERILECEK = "Gönderilecek"
YEDEK = "Yedek"
ONCELIKLI = "Sıralamasız (öncelikli)"
KOSULSUZ = "Koşulu sağlamıyor"
ORTALAMASIZ = "Ortalama girilmemiş"


def _yol(yol: Path | str | None, ad: str) -> Path:
    return Path(yol) if yol else config.output_dir() / f"{ad}.xlsx"


# ------------------------------------------------------------------ öğrenci seçimi (md.136)

@dataclass
class Aday:
    ogrenci_id: int
    ad: str
    sinif: str
    okul_no: str
    ortalama: float | None
    oncelikli: bool
    agir_disiplin: bool
    yerlesik: bool
    sonuc: str = ""
    sira: int | None = None


def adaylar(db, alan_id: int | None = None, seviye: int | None = None) -> list[Aday]:
    kosul, params = ["o.aktif = 1"], []
    if alan_id:
        kosul.append("s.alan_id = ?")
        params.append(alan_id)
    if seviye:
        kosul.append("s.seviye = ?")
        params.append(seviye)
    rows = db.q(f"""SELECT o.id, o.ad, o.soyad, o.okul_no, o.basari_ortalamasi, o.oncelikli, o.agir_disiplin,
                           s.ad AS sinif,
                           EXISTS(SELECT 1 FROM yerlestirmeler y WHERE y.ogrenci_id = o.id AND y.durum = 'Aktif'
                                  AND y.isletme_id IS NOT NULL) AS yerlesik
                    FROM ogrenciler o JOIN siniflar s ON s.id = o.sinif_id
                    WHERE {' AND '.join(kosul)} ORDER BY s.ad, o.okul_no""", params)
    return [Aday(r["id"], f"{r['ad']} {r['soyad']}", r["sinif"] or "", r["okul_no"] or "",
                 float(r["basari_ortalamasi"]) if r["basari_ortalamasi"] is not None else None,
                 bool(r["oncelikli"]), bool(r["agir_disiplin"]), bool(r["yerlesik"])) for r in rows]


def sirala(liste: list[Aday], kontenjan: int) -> list[Aday]:
    """Öncelikli öğrenciler sıralamaya girmeden kontenjandan yerleşir; ağır disiplin cezası olanlar ayrılır;
    kalanlar başarı ortalamasına göre sıralanır. Kontenjan 0 ise sınır uygulanmaz."""
    kalan = kontenjan if kontenjan > 0 else len(liste)
    out: list[Aday] = []
    for a in liste:
        if a.oncelikli:
            a.sonuc, a.sira = ONCELIKLI, None
            kalan -= 1
            out.append(a)
    sirali = sorted((a for a in liste if not a.oncelikli and not a.agir_disiplin and a.ortalama is not None),
                    key=lambda a: (-a.ortalama, a.ad))
    for n, a in enumerate(sirali, 1):
        a.sira = n
        a.sonuc = GONDERILECEK if kalan > 0 else YEDEK
        kalan -= 1
        out.append(a)
    for a in liste:
        if not a.oncelikli and a.ortalama is None and not a.agir_disiplin:
            a.sonuc, a.sira = ORTALAMASIZ, None
            out.append(a)
    for a in liste:
        if not a.oncelikli and a.agir_disiplin:
            a.sonuc, a.sira = KOSULSUZ, None
            out.append(a)
    return out


def alan_kontenjani(db, alan_id: int | None) -> int:
    if not alan_id:
        return int(db.q1("SELECT COALESCE(SUM(kontenjan), 0) FROM isletmeler WHERE aktif = 1")[0])
    return int(db.q1("SELECT COALESCE(SUM(kontenjan), 0) FROM isletmeler WHERE aktif = 1 AND alan_id = ?",
                     (alan_id,))[0])


SECIM_BASLIKLAR = ["Sıra", "Öğrenci", "Sınıf", "Okul No", "Başarı Ortalaması", "Sonuç", "Şu an işletmede"]


def secim_satirlari(liste: list[Aday]) -> list[list]:
    return [[a.sira or "", a.ad, a.sinif, a.okul_no, a.ortalama if a.ortalama is not None else "", a.sonuc,
             "Evet" if a.yerlesik else ""] for a in liste]


def secim_excel(db, liste: list[Aday], alan: str, kontenjan: int, yol: Path | str | None = None) -> Path:
    say = Counter(a.sonuc for a in liste)
    return tablo_yaz(_yol(yol, f"Öğrenci Seçim Sıralaması {alan}"), SECIM_BASLIKLAR, secim_satirlari(liste),
                     baslik=f"{db.kurum()['ad']} - {alan} işletmelerde mesleki eğitim öğrenci sıralaması "
                            f"(kontenjan: {kontenjan or 'sınırsız'})",
                     alt_bilgi=[f"{k}: {v}" for k, v in say.items()] +
                               ["Öncelikli ve disiplin bilgileri kişisel veridir; listeyi yalnızca komisyonla "
                                "paylaşınız (Ortaöğretim Kurumları Yönetmeliği md.136)."])


def secim_baglami(liste: list[Aday], alan: str, kontenjan: int) -> dict:
    def satir(a: Aday) -> str:
        ort = f" - {a.ortalama:g}" if a.ortalama is not None else ""
        return f"{a.ad} ({a.sinif} / {a.okul_no}){ort}"
    return {"alan": alan, "kontenjan": kontenjan or "sınırsız",
            "oncelikli_listesi": "\n".join(satir(a) for a in liste if a.sonuc == ONCELIKLI) or "-",
            "sira_listesi": "\n".join(f"{a.sira}. {satir(a)} - {a.sonuc}" for a in liste
                                      if a.sonuc in (GONDERILECEK, YEDEK)) or "-",
            "kosulsuz_listesi": "\n".join(f"{satir(a)} - {a.sonuc}" for a in liste
                                          if a.sonuc in (KOSULSUZ, ORTALAMASIZ)) or "-"}


def secim_tutanagi(db, liste: list[Aday], alan: str, kontenjan: int) -> Path:
    from . import belgeler
    return belgeler.uret(db, "ogrenci_secim_tutanagi", 0, baglam=secim_baglami(liste, alan, kontenjan))


# ------------------------------------------------------------------ dönem sonları ve puan çizelgesi

def donem_sonlari(db) -> list[tuple[int, date]]:
    k = db.kurum()
    out = []
    for no, kol in ((1, "birinci_donem_sonu"), (2, "ders_yili_sonu")):
        d = tarih(k[kol])
        if d:
            out.append((no, d))
    return out


def ders_yili_baslangici(db) -> date | None:
    return tarih(db.kurum()["ders_yili_baslangic"])


def puan_eksikleri(db, donem: int) -> list[str]:
    """İşletmede eğitim gören ve bu dönem işletme notu girilmemiş öğrenciler."""
    rows = db.q("""SELECT DISTINCT o.id, o.ad, o.soyad, s.ad AS sinif, y.tur FROM yerlestirmeler y
                   JOIN ogrenciler o ON o.id = y.ogrenci_id LEFT JOIN siniflar s ON s.id = o.sinif_id
                   WHERE y.durum = 'Aktif' AND y.isletme_id IS NOT NULL AND NOT EXISTS (
                       SELECT 1 FROM beceri_notlari b WHERE b.ogrenci_id = o.id AND b.donem = ?
                       AND b.isletme_notu IS NOT NULL) ORDER BY s.ad, o.ad""", (donem,))
    return [f"{r['ad']} {r['soyad']} ({r['sinif'] or ''})" for r in rows if r["tur"] not in OKUL_ICI_TURLER]


@dataclass
class PuanTeslimi:
    donem: int
    donem_sonu: date
    son_teslim: date
    eksik: list[str]


def puan_teslimleri(db, bugun: date | None = None, gun_once: int = 21) -> list[PuanTeslimi]:
    """Teslim tarihine `gun_once` gün kalmış ya da teslim tarihi geçmiş ama dönem bitmemiş dönemler."""
    bugun = bugun or date.today()
    sure = int(db.ayar("puan_cizelgesi_gun"))
    out = []
    for no, son in donem_sonlari(db):
        teslim = son - timedelta(days=sure)
        if teslim - timedelta(days=gun_once) <= bugun <= son:
            out.append(PuanTeslimi(no, son, teslim, puan_eksikleri(db, no)))
    return out


# ------------------------------------------------------------------ alan taraması, anketler, hizmetiçi

TALEP_BASLIKLAR = ["Alan", "Talep Eden İşletme", "Talep Edilen Öğrenci", "Mevcut Kontenjan", "İşletmedeki Öğrenci",
                   "Alt Sınıf Öğrenci (gelecek yıl aday)", "Fark (talep+kontenjan-aday)"]


def talep_satirlari(db) -> list[list]:
    talep = defaultdict(lambda: [set(), 0])
    for r in db.q("SELECT isletme_id, alan_id, talep_sayisi FROM isletme_talepleri"):
        t = talep[r["alan_id"]]
        t[0].add(r["isletme_id"])
        t[1] += r["talep_sayisi"] or 0
    alanlar = {r["id"]: r["ad"] for r in db.q("SELECT id, ad FROM alanlar ORDER BY ad")}
    kontenjan = {r["alan_id"]: r["k"] for r in db.q(
        "SELECT alan_id, SUM(kontenjan) k FROM isletmeler WHERE aktif = 1 GROUP BY alan_id")}
    isletmede = {r["alan_id"]: r["n"] for r in db.q(
        """SELECT s.alan_id, COUNT(DISTINCT o.id) n FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
           JOIN siniflar s ON s.id = o.sinif_id WHERE y.durum = 'Aktif' AND y.isletme_id IS NOT NULL
           GROUP BY s.alan_id""")}
    aday = {r["alan_id"]: r["n"] for r in db.q(
        """SELECT s.alan_id, COUNT(*) n FROM ogrenciler o JOIN siniflar s ON s.id = o.sinif_id
           WHERE o.aktif = 1 AND s.seviye = 11 AND s.program != 'MEM' GROUP BY s.alan_id""")}
    out = []
    for aid in sorted(set(alanlar) | {k for k in talep if k}, key=lambda a: alanlar.get(a, "")):
        isl, n = talep.get(aid, (set(), 0))
        k, a = kontenjan.get(aid) or 0, aday.get(aid) or 0
        if not (n or k or a or isletmede.get(aid)):
            continue
        out.append([alanlar.get(aid, "-"), len(isl), n, k, isletmede.get(aid) or 0, a, n + k - a])
    return out


def talep_ozeti(db, yol: Path | str | None = None) -> Path:
    x = ExcelYazici()
    x.sayfa("Alan Özeti", TALEP_BASLIKLAR, talep_satirlari(db),
            baslik=f"{db.kurum()['ad']} - Alan Taraması ve İşletme Talepleri Özeti",
            alt_bilgi=["Fark eksi ise gelecek yıl için yeni işletme bulunmalıdır (md.89/2, md.82/2-ğ)."])
    rows = db.q("""SELECT t.tarih, i.ad AS isletme, a.ad AS alan, t.dal, t.talep_sayisi,
                          o.ad || ' ' || o.soyad AS ogretmen, t.aciklama
                   FROM isletme_talepleri t LEFT JOIN isletmeler i ON i.id = t.isletme_id
                   LEFT JOIN alanlar a ON a.id = t.alan_id LEFT JOIN ogretmenler o ON o.id = t.ogretmen_id
                   ORDER BY a.ad, t.tarih""")
    x.sayfa("Talepler", ["Tarih", "İşletme", "Alan", "Dal", "Talep", "Öğretmen", "Açıklama"],
            [[tr(r["tarih"]), r["isletme"], r["alan"], r["dal"], r["talep_sayisi"], r["ogretmen"], r["aciklama"]]
             for r in rows])
    return x.kaydet(_yol(yol, "Alan Taraması ve İşletme Talepleri"))


def anket_ozeti(db, yol: Path | str | None = None) -> Path:
    rows = db.q("""SELECT a.*, o.ad || ' ' || o.soyad AS ogrenci, i.ad AS isletme,
                          t.ad || ' ' || t.soyad AS ogretmen
                   FROM anketler a LEFT JOIN ogrenciler o ON o.id = a.ogrenci_id
                   LEFT JOIN isletmeler i ON i.id = a.isletme_id LEFT JOIN ogretmenler t ON t.id = a.ogretmen_id
                   ORDER BY a.tur, a.tarih""")
    x = ExcelYazici()
    durum = Counter(r["calisma_durumu"] or "Belirtilmemiş" for r in rows if r["tur"] == "Mezun")
    mezun = sum(durum.values())
    x.sayfa("Mezun Durumu", ["Durum", "Kişi", "Oran"],
            [[d, n, f"%{n * 100 / mezun:.0f}"] for d, n in durum.most_common()],
            baslik=f"{db.kurum()['ad']} - Mezun İzleme ve İşyeri Anketleri Değerlendirmesi")
    puan = defaultdict(list)
    for r in rows:
        if r["memnuniyet"]:
            puan[r["tur"]].append(int(r["memnuniyet"]))
    x.sayfa("Memnuniyet", ["Anket Türü", "Yanıt", "Ortalama (1-5)"],
            [[t, len(p), round(sum(p) / len(p), 2)] for t, p in sorted(puan.items())],
            alt_bilgi=[f"Elektronik ortama aktarılmamış anket: "
                       f"{sum(1 for r in rows if not r['e_ortama_aktarildi'])}"])
    x.sayfa("Anketler", ["Tarih", "Tür", "Mezun/Öğrenci", "İşletme", "Öğretmen", "Durum", "Memnuniyet",
                         "E-ortamda", "Görüşler"],
            [[tr(r["tarih"]), r["tur"], r["ogrenci"], r["isletme"], r["ogretmen"], r["calisma_durumu"],
              r["memnuniyet"], "Evet" if r["e_ortama_aktarildi"] else "", r["gorusler"]] for r in rows])
    return x.kaydet(_yol(yol, "Mezun ve İşyeri Anketleri"))


def hizmetici_programi(db, yol: Path | str | None = None) -> Path:
    rows = db.q("""SELECT h.*, i.ad AS isletme FROM hizmetici_egitimler h
                   LEFT JOIN isletmeler i ON i.id = h.isletme_id ORDER BY h.tarih""")
    k = db.kurum()
    return tablo_yaz(_yol(yol, "Usta Öğretici Hizmetiçi Eğitim Programı"),
                     ["Tarih", "Konu", "İşletme", "Katılımcılar", "Eğitimi Veren", "Yer", "Süre (saat)", "Durum"],
                     [[tr(r["tarih"]), r["konu"], r["isletme"] or "Ortak", r["katilimcilar"], r["egitici"], r["yer"],
                       r["sure_saat"], r["durum"]] for r in rows],
                     baslik=f"{k['ad']} - {k['egitim_yili']} Usta Öğretici ve Eğitici Personel Hizmetiçi Eğitim "
                            "Programı",
                     alt_bilgi=["Ortaöğretim Kurumları Yönetmeliği md.82/2-b uyarınca okul müdürünün onayına sunulur.",
                                f"Koordinatör Müdür Yardımcısı: {k['koordinator_mudur_yrd'] or ''}"])
