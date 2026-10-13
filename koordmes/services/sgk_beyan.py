"""Aylık prim ve hizmet belgesi (APHB) beyan takibi, iptal/ek düzeltmesi ve SGK işlemleri ön kontrolleri.

- Beyan kaydı: e-Bildirge V2'de onaylanan belgenin satırları (kişi, belge türü, gün, PEK, giriş/çıkış, eksik gün)
  dönemle birlikte saklanır. Asıl ve ek belgeler satır ekler, iptal belgesi kişinin o belge türündeki satırını
  düşer; dönemin SGK'daki güncel hali bu kayıtlardan çıkarılır. Başka bir programla verilmiş belge, yüklenen XML
  dosyasından da kaydedilebilir.
- Fark analizi: belge verildikten sonra işlenen devamsızlık, nakil, geriye dönük çıkış ya da belge türü değişikliği
  okul kayıtlarını beyandan ayırır. Değişen ve listeden çıkan kişiler için beyan edilen değerlerle iptal belgesi,
  değişen ve yeni kişiler için güncel değerlerle ek belge hazırlanır; bütün belgeyi iptal edip yeniden vermek
  gerekmez.
- Ön kontrol: belge hazırlanmadan önce e-Bildirge'nin reddedeceği ya da ceza doğuracak durumlar (işyeri bilgisi,
  devamsızlığın işlenmesi, T.C., verilmemiş işe giriş bildirgesi, önceki ayın belgesi, yaş ve belge türü).
- Dönem sonu toplu çıkış ön koşulları: önceki ayın belgesi, çıkış ayının devamsızlıkları, ayrılış nedeni kodu,
  ders yılı sonu ve tatil.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from .. import config
from ..mevzuat import AYLAR, OKUL_ICI_TURLER, maol_mi
from . import sigorta, sgk_dosya, sgk_risk
from .sgk_dosya import MAHIYETLER, AphbSatiri, DosyaSonucu, SgkDosyaHatasi
from .utils import ay_araligi, para, tarih, tr

AYRILIS_NEDENLERI = {"22": "Diğer nedenler"}
ALANLAR = [("gun", "prim günü"), ("pek", "PEK"), ("giris", "giriş günü"), ("cikis", "çıkış günü"),
           ("eksik_gun", "eksik gün"), ("eksik_neden", "eksik gün nedeni"), ("cikis_nedeni", "işten çıkış nedeni")]

GIRIS_YUKLEME = ("SGK 4A (uyg.sgk.gov.tr/SgkTescil4a) > Talep İşlemleri > Talep Yükleme > İşe Giriş Talebi Yükleme ile "
                 "dosyayı yükleyin; 'Talepleri Görüntüle'de kayıt sayısını 100 yapıp 'Seçili Talepleri Onayla'ya bir "
                 "kez basın ve bekleyin, her 100 kişide 'Toplu PDF Döküm' alın. Hata veren öğrencileri tek tek girin. "
                 "Onaydan sonra satırları 'Bildirildi' işaretleyin.")
CIKIS_YUKLEME = ("SGK 4A (uyg.sgk.gov.tr/SgkTescil4a) > Talep İşlemleri > Talep Silme > İşten Çıkış Talepleri Silme'den "
                 "eski yıllardan kalan talepleri silin; sonra Talep Yükleme > İşten Çıkış Talebi Yükleme ile dosyayı "
                 "yükleyin. 'Talepleri Görüntüle'de kayıt sayısını 100 yapıp 'Seçili Talepleri Onayla'ya bir kez basın "
                 "ve bekleyin (birden çok basmak hata verir); her 100 kişide 'Toplu PDF Döküm' alın ve liste bitene "
                 "kadar tekrarlayın. Hata veren öğrencileri (özellikle açık lise) tek tek çıkarın. Onaydan sonra "
                 "satırları 'Bildirildi' işaretleyin.")


def donem(yil: int, ay: int) -> str:
    return f"{yil:04d}-{ay:02d}"


def _donem_adi(yil: int, ay: int) -> str:
    return f"{AYLAR[ay - 1]} {yil}"


def _onceki(yil: int, ay: int) -> tuple[int, int]:
    return (yil - 1, 12) if ay == 1 else (yil, ay - 1)


# ------------------------------------------------------------------ beyan kayıtları

@dataclass
class Beyan:
    id: int
    donem: str
    mahiyet: str
    tahakkuk: str
    tarih: date | None
    kisi: int
    aciklama: str

    @property
    def etiket(self) -> str:
        return f"{MAHIYETLER.get(self.mahiyet, self.mahiyet)} {tr(self.tarih)} ({self.kisi} kişi)"


def beyanlar(db, yil: int, ay: int) -> list[Beyan]:
    return [Beyan(r["id"], r["donem"], r["mahiyet"], r["tahakkuk"] or "A", tarih(r["tarih"]), r["kisi"] or 0,
                  r["aciklama"] or "")
            for r in db.q("SELECT * FROM sgk_beyanlari WHERE donem = ? ORDER BY id", (donem(yil, ay),))]


def beyan_satirlari(db, beyan_id: int) -> list[AphbSatiri]:
    return [AphbSatiri(r["belge"], r["kanun"] or "00000", r["tc"], r["ad"] or "", r["soyad"] or "",
                       float(r["pek"] or 0), int(r["gun"] or 0), tarih(r["giris"]), tarih(r["cikis"]),
                       int(r["eksik_gun"] or 0), r["eksik_neden"] or "", r["cikis_nedeni"] or "", r["meslek"] or "",
                       bool(r["okul_ici"]), r["ogrenci_id"])
            for r in db.q("SELECT * FROM sgk_beyan_satirlari WHERE beyan_id = ? ORDER BY id", (beyan_id,))]


def _topla(a: AphbSatiri, b: AphbSatiri) -> AphbSatiri:
    return replace(a, gun=min(30, a.gun + b.gun), pek=round(a.pek + b.pek, 2), giris=a.giris or b.giris,
                   cikis=b.cikis or a.cikis, eksik_gun=b.eksik_gun or a.eksik_gun,
                   eksik_neden=b.eksik_neden or a.eksik_neden, cikis_nedeni=b.cikis_nedeni or a.cikis_nedeni)


def beyan_edilen(db, yil: int, ay: int) -> dict[tuple[str, str], AphbSatiri]:
    """Kayıtlı beyanlara göre dönemin SGK'daki hali: (T.C., belge türü) -> satır."""
    out: dict[tuple[str, str], AphbSatiri] = {}
    for b in beyanlar(db, yil, ay):
        for s in beyan_satirlari(db, b.id):
            k = (s.tc, s.belge)
            if b.mahiyet == "I":
                out.pop(k, None)
            elif b.mahiyet == "E" and k in out:
                out[k] = _topla(out[k], s)
            else:
                out[k] = s
    return out


def _kaydet(db, yil: int, ay: int, mahiyet: str, satirlar: list[AphbSatiri], tarih_: date, tahakkuk: str,
            aciklama: str) -> int:
    with db.conn:
        bid = db.conn.execute("""INSERT INTO sgk_beyanlari (donem, mahiyet, tahakkuk, tarih, kisi, aciklama)
                                 VALUES (?, ?, ?, ?, ?, ?)""",
                              (donem(yil, ay), mahiyet, tahakkuk, tarih_.isoformat(), len({s.tc for s in satirlar}),
                               aciklama)).lastrowid
        for s in satirlar:
            db.conn.execute(
                """INSERT INTO sgk_beyan_satirlari (beyan_id, ogrenci_id, tc, ad, soyad, belge, kanun, gun, pek, giris,
                   cikis, eksik_gun, eksik_neden, cikis_nedeni, meslek, okul_ici)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (bid, s.ogrenci_id, s.tc, s.ad, s.soyad, str(s.belge).zfill(2), s.kanun, s.gun, round(s.pek, 2),
                 s.giris.isoformat() if s.giris else None, s.cikis.isoformat() if s.cikis else None, s.eksik_gun,
                 s.eksik_neden, s.cikis_nedeni, s.meslek, int(s.okul_ici)))
    return bid


def beyan_kaydet(db, yil: int, ay: int, mahiyet: str = "A", satirlar: list[AphbSatiri] | None = None,
                 tarih_: date | None = None, tahakkuk: str | None = None, aciklama: str = "") -> int:
    """e-Bildirge'de onaylanan belgeyi kaydeder. Satır verilmezse dönemin güncel listesi (asıl belge) yazılır."""
    if mahiyet not in MAHIYETLER:
        raise SgkDosyaHatasi(f"Belge mahiyeti A, E veya I olmalı: {mahiyet}")
    if mahiyet == "A" and any(b.mahiyet == "A" for b in beyanlar(db, yil, ay)):
        raise SgkDosyaHatasi(f"{_donem_adi(yil, ay)} asıl belgesi zaten kayıtlı. Sonradan değişen kişiler için "
                             "düzeltme (iptal + ek) kullanın ya da kaydı silip yeniden kaydedin.")
    if satirlar is None:
        if mahiyet != "A":
            raise SgkDosyaHatasi("Ek ve iptal belgeleri satırlarıyla birlikte kaydedilir.")
        satirlar = sgk_dosya.aphb_satirlari(db, yil, ay)
    if not satirlar:
        raise SgkDosyaHatasi(f"{_donem_adi(yil, ay)} döneminde kaydedilecek sigortalı yok.")
    tarih_ = tarih_ or date.today()
    tahakkuk = tahakkuk or sgk_dosya.tahakkuk_nedeni(db, yil, ay, tarih_)
    bid = _kaydet(db, yil, ay, mahiyet, satirlar, tarih_, tahakkuk, aciklama)
    if mahiyet == "A":
        try:  # ayar yazma yetkisi olmayan rolde beyan kaydı yeterlidir
            sgk_risk.aphb_isaretle(db, yil, ay, tarih_)
        except Exception:  # noqa: BLE001 - yerelde sqlite3.DatabaseError, ağda istemci hatası
            pass
    return bid


def beyan_sil(db, beyan_id: int) -> None:
    r = db.q1("SELECT donem, mahiyet FROM sgk_beyanlari WHERE id = ?", (beyan_id,))
    db.delete("sgk_beyanlari", beyan_id)
    if r and r["mahiyet"] == "A" and not db.q1("SELECT 1 FROM sgk_beyanlari WHERE donem = ? AND mahiyet = 'A'",
                                               (r["donem"],)):
        try:
            db.ayar_yaz(sgk_risk.aphb_anahtari(int(r["donem"][:4]), int(r["donem"][5:])), "")
        except Exception:  # noqa: BLE001
            pass


@dataclass
class XmlBeyani:
    yil: int
    ay: int
    mahiyet: str
    tahakkuk: str
    satirlar: list[AphbSatiri]


def _ggaa(s: str | None, yil: int) -> date | None:
    s = (s or "").strip()
    if len(s) != 4 or not s.isdigit():
        return None
    try:
        return date(yil, int(s[2:]), int(s[:2]))
    except ValueError:
        return None


def xml_oku(db, yol: Path | str) -> XmlBeyani:
    """e-Bildirge V2 aylık prim ve hizmet belgesi XML'ini (bu programın ya da başka programın ürettiği) okur."""
    from lxml import etree
    try:
        kok = etree.parse(str(yol)).getroot()
    except (OSError, etree.XMLSyntaxError) as e:
        raise SgkDosyaHatasi(f"XML okunamadı: {e}") from e
    bordro = kok.find("BORDRO")
    if kok.tag != "AYLIKBILDIRGELER" or bordro is None:
        raise SgkDosyaHatasi("Dosya e-Bildirge V2 aylık prim ve hizmet belgesi XML'i değil.")
    try:
        yil, ay = int(bordro.get("HIZMETDONEMYIL") or bordro.get("DONEMYIL")), \
            int(bordro.get("HIZMETDONEMAY") or bordro.get("DONEMAY"))
    except (TypeError, ValueError) as e:
        raise SgkDosyaHatasi("Belgede dönem (yıl/ay) bulunamadı.") from e
    okul_belgeleri = {str(db.ayar("belge_okul_yukumlu")).zfill(2), str(db.ayar("belge_okul_degil")).zfill(2)}
    ogrenci = {r["tc"]: r["id"] for r in db.q("SELECT id, tc FROM ogrenciler WHERE tc != ''")}
    satirlar = []
    for b in kok.iter("BILDIRGELER"):
        belge, kanun = str(b.get("BELGETURU") or "").zfill(2), b.get("KANUN") or "00000"
        for s in b.iter("SIGORTALI"):
            tc = (s.get("TCKNO") or "").strip()
            satirlar.append(AphbSatiri(
                belge, kanun, tc, s.get("AD") or "", s.get("SOYAD") or "", float(s.get("PEK") or 0),
                int(s.get("GUN") or 0), _ggaa(s.get("GIRISGUN"), yil), _ggaa(s.get("CIKISGUN"), yil),
                int(s.get("EKSIKGUNSAYISI") or 0), s.get("EKSIKGUNNEDENI") or "", s.get("ISTENCIKISNEDENI") or "",
                s.get("MESLEKKOD") or "", belge in okul_belgeleri, ogrenci.get(tc)))
    if not satirlar:
        raise SgkDosyaHatasi("Belgede sigortalı satırı yok.")
    return XmlBeyani(yil, ay, bordro.get("BELGEMAHIYET") or "A", bordro.get("TAHAKKUKNEDEN") or "A", satirlar)


def xmlden_kaydet(db, yol: Path | str, tarih_: date | None = None) -> XmlBeyani:
    x = xml_oku(db, yol)
    beyan_kaydet(db, x.yil, x.ay, x.mahiyet, x.satirlar, tarih_, x.tahakkuk, f"XML: {Path(yol).name}")
    return x


# ------------------------------------------------------------------ fark analizi ve düzeltme

@dataclass
class FarkSatiri:
    durum: str  # Eklenecek | Değişti | İptal edilecek
    tc: str
    ad: str
    eski: AphbSatiri | None
    yeni: AphbSatiri | None
    aciklama: str

    @property
    def ogrenci_id(self) -> int | None:
        return (self.yeni or self.eski).ogrenci_id

    @property
    def belge(self) -> str:
        if self.eski and self.yeni and self.eski.belge != self.yeni.belge:
            return f"{self.eski.belge} → {self.yeni.belge}"
        return (self.yeni or self.eski).belge


@dataclass
class BeyanFarki:
    yil: int
    ay: int
    beyanlar: list[Beyan]
    satirlar: list[FarkSatiri] = field(default_factory=list)

    @property
    def beyan_var(self) -> bool:
        return bool(self.beyanlar)

    @property
    def iptal_satirlari(self) -> list[AphbSatiri]:
        return [f.eski for f in self.satirlar if f.eski is not None]

    @property
    def ek_satirlari(self) -> list[AphbSatiri]:
        return [f.yeni for f in self.satirlar if f.yeni is not None]

    def ozet(self) -> str:
        if not self.beyan_var:
            return f"{_donem_adi(self.yil, self.ay)} için kayıtlı beyan yok."
        if not self.satirlar:
            return f"{_donem_adi(self.yil, self.ay)}: verilen belge okul kayıtlarıyla aynı."
        n = defaultdict(int)
        for f in self.satirlar:
            n[f.durum] += 1
        return f"{_donem_adi(self.yil, self.ay)} belgesi verildikten sonra " + \
            ", ".join(f"{n[k]} kişi {ad}" for k, ad in (("Değişti", "değişti"), ("Eklenecek", "eklenecek"),
                                                         ("İptal edilecek", "iptal edilecek")) if n[k]) + \
            f": {len(self.iptal_satirlari)} satır iptal, {len(self.ek_satirlari)} satır ek belge."


def _deger(s: AphbSatiri, alan: str) -> str:
    v = getattr(s, alan)
    if alan == "pek":
        return para(v)
    if isinstance(v, date):
        return tr(v)
    return str(v or ("0" if alan in ("gun", "eksik_gun") else "-"))


def _degisenler(eski: AphbSatiri, yeni: AphbSatiri) -> list[str]:
    out = []
    for alan, ad in ALANLAR:
        a, b = getattr(eski, alan), getattr(yeni, alan)
        ayni = abs(a - b) < 0.005 if alan == "pek" else (a or None) == (b or None)
        if not ayni:
            out.append(f"{ad} {_deger(eski, alan)} → {_deger(yeni, alan)}")
    return out


def fark_analizi(db, yil: int, ay: int) -> BeyanFarki:
    bl = beyanlar(db, yil, ay)
    sonuc = BeyanFarki(yil, ay, bl)
    if not bl:
        return sonuc
    eski_tc: dict[str, list[AphbSatiri]] = defaultdict(list)
    for s in beyan_edilen(db, yil, ay).values():
        eski_tc[s.tc].append(s)
    yeni_tc: dict[str, list[AphbSatiri]] = defaultdict(list)
    for s in sgk_dosya.aphb_satirlari(db, yil, ay):
        yeni_tc[s.tc].append(s)
    for tc in sorted(set(eski_tc) | set(yeni_tc), key=lambda t: ((eski_tc.get(t) or yeni_tc[t])[0].ad, t)):
        eski = {s.belge: s for s in eski_tc.get(tc, [])}
        yeni = {s.belge: s for s in yeni_tc.get(tc, [])}
        ortak = sorted(set(eski) & set(yeni))
        sadece_eski = sorted(set(eski) - set(yeni))
        sadece_yeni = sorted(set(yeni) - set(eski))
        ciftler = [(eski[b], yeni[b]) for b in ortak]
        while sadece_eski and sadece_yeni:  # belge türü değişmiş
            ciftler.append((eski[sadece_eski.pop(0)], yeni[sadece_yeni.pop(0)]))
        for e, y in ciftler:
            degisen = _degisenler(e, y)
            if e.belge != y.belge:
                degisen.insert(0, f"belge türü {e.belge} → {y.belge}")
            if degisen:
                sonuc.satirlar.append(FarkSatiri("Değişti", tc, f"{y.ad} {y.soyad}", e, y, "; ".join(degisen)))
        for b in sadece_eski:
            e = eski[b]
            sonuc.satirlar.append(FarkSatiri("İptal edilecek", tc, f"{e.ad} {e.soyad}", e, None,
                                             f"Okul kayıtlarına göre bu dönemde belge {b} ile sigortalı değil "
                                             f"(beyanda {e.gun} gün)"))
        for b in sadece_yeni:
            y = yeni[b]
            sonuc.satirlar.append(FarkSatiri("Eklenecek", tc, f"{y.ad} {y.soyad}", None, y,
                                             f"Beyanda yok: belge {b}, {y.gun} gün"
                                             + (f", {y.eksik_gun} eksik gün" if y.eksik_gun else "")))
    return sonuc


def duzeltme_dosyalari(db, yil: int, ay: int, klasor: Path | str | None = None, bicim: str = "xml",
                       bugun: date | None = None) -> DosyaSonucu:
    """Yalnızca değişen kişiler için iptal (beyan edilen değerlerle) ve ek (güncel değerlerle) belgeleri."""
    fark = fark_analizi(db, yil, ay)
    if not fark.beyan_var:
        raise SgkDosyaHatasi(f"{_donem_adi(yil, ay)} için kayıtlı beyan yok. Önce verilen belgeyi kaydedin "
                             "('Beyanı Kaydet' ya da 'Beyanı XML'den Al').")
    if not fark.satirlar:
        raise SgkDosyaHatasi(f"{_donem_adi(yil, ay)} belgesinden sonra değişiklik yok; düzeltme gerekmez.")
    tahakkuk = sgk_dosya.tahakkuk_nedeni(db, yil, ay, bugun)
    klasor = Path(klasor) if klasor else config.output_dir() / "SGK"
    sonuc = DosyaSonucu()
    sira = 1
    for mahiyet, satirlar in (("I", fark.iptal_satirlari), ("E", fark.ek_satirlari)):
        if not satirlar:
            continue
        satirlar = sorted(satirlar, key=lambda r: (r.belge, r.kanun, r.ad, r.soyad))
        sgk_dosya.aphb_yaz(db, yil, ay, satirlar, mahiyet, tahakkuk, klasor, bicim,
                           f"e-Bildirge APHB {yil}-{ay:02d} Düzeltme {sira} {MAHIYETLER[mahiyet]}", sonuc)
        sira += 1
    sonuc.kisi = len({f.tc for f in fark.satirlar})
    adimlar = []
    if fark.iptal_satirlari:
        adimlar.append(f"önce 'İptal' dosyasını ({len(fark.iptal_satirlari)} satır) yükleyip onaylayın")
    if fark.ek_satirlari:
        adimlar.append(f"sonra 'Ek' dosyasını ({len(fark.ek_satirlari)} satır) yükleyip onaylayın")
    sonuc.uyarilar.insert(0, "e-Bildirge V2'de dönemi seçip " + ", ".join(adimlar) + "; ardından 'Düzeltmeyi Kaydet' "
                          "deyin.")
    if tahakkuk == "B" and fark.ek_satirlari:
        au = db.ayar("asgari_ucret_brut")
        n = len({s.tc for s in fark.ek_satirlari})
        ceza = n * au * db.ayar("sgk_ipc_ek_belge_kisi")
        sonuc.uyarilar.append(f"Yasal süre ({sgk_risk.aphb_son_gunu(db, yil, ay):%d.%m.%Y}) geçtiği için tahakkuk "
                              f"nedeni B yazıldı. Ek belge için olası idari para cezası ~{para(ceza)} TL ({n} kişi); "
                              f"kendiliğinden verilip peşin ödenirse ~{para(ceza * db.ayar('sgk_ipc_indirim'))} TL.")
    return sonuc


def duzeltme_kaydet(db, yil: int, ay: int, tarih_: date | None = None) -> tuple[int | None, int | None]:
    """e-Bildirge'de onaylanan iptal ve ek belgelerini beyan kayıtlarına işler: (iptal kaydı, ek kaydı)."""
    fark = fark_analizi(db, yil, ay)
    if not fark.beyan_var or not fark.satirlar:
        raise SgkDosyaHatasi("Kaydedilecek düzeltme yok.")
    tarih_ = tarih_ or date.today()
    iptal = beyan_kaydet(db, yil, ay, "I", fark.iptal_satirlari, tarih_, aciklama="Düzeltme") \
        if fark.iptal_satirlari else None
    ek = beyan_kaydet(db, yil, ay, "E", fark.ek_satirlari, tarih_, aciklama="Düzeltme") \
        if fark.ek_satirlari else None
    return iptal, ek


# ------------------------------------------------------------------ ön kontroller

@dataclass
class Kontrol:
    durum: bool | None  # True tamam, False sorun, None dikkat/bilgi
    baslik: str
    detay: str
    git: str = ""

    @property
    def isaret(self) -> str:
        return {True: "Tamam", False: "Sorun", None: "Dikkat"}[self.durum]


def _isyeri_kontrolu(db) -> Kontrol:
    k = db.kurum()
    git = "Ayarlar ve Mevzuat Parametreleri"
    try:
        isy = sgk_dosya.isyeri(db)
        if str(db.ayar("sgk_isyeri_sicil_okul") or "").strip():
            sgk_dosya.isyeri(db, True)
    except SgkDosyaHatasi as e:
        return Kontrol(False, "İşyeri bilgileri", str(e), git)
    if not (k["ad"] or "").strip():
        return Kontrol(False, "İşyeri bilgileri", "Kurum adı boş; e-Bildirge belgeyi işyeri satırında reddeder "
                                                 "('Hata Satırı 3').", git)
    if not (k["adres"] or "").strip():
        return Kontrol(None, "İşyeri bilgileri", f"Sicil {isy.etiket}; kurum adresi boş, '{isy.adres}' yazılacak.",
                       git)
    return Kontrol(True, "İşyeri bilgileri", f"Sicil {isy.etiket}, {isy.unvan[:50]}")


def _devamsizlik_kontrolu(db, bas: date, bit: date, bugun: date, cikis: bool = False) -> Kontrol:
    r = db.q1("SELECT COUNT(*) AS n, MAX(tarih) AS son, SUM(CASE WHEN sgk_eksik = 1 THEN 1 ELSE 0 END) AS e "
              "FROM devamsizlik WHERE tarih BETWEEN ? AND ?", (bas.isoformat(), bit.isoformat()))
    baslik = "Çıkış ayının devamsızlıkları" if cikis else "Devamsızlıkların işlenmesi (e-Okul)"
    if r["n"]:
        return Kontrol(True, baslik, f"{r['n']} kayıt, son kayıt {tr(r['son'])}; {r['e'] or 0} kayıt SGK eksik "
                                     "günü sayılıyor.")
    if not cikis and bugun <= bit:
        return Kontrol(None, baslik, "Ay henüz bitmedi; ay sonunda e-Okul devamsızlıklarını aktarın.", "Veri Aktarımı")
    neden = "ayrılış bildirgesindeki eksik gün buradan hesaplanır" if cikis else "eksik günler belgeye yazılamaz"
    return Kontrol(None, baslik, f"Bu aralıkta devamsızlık kaydı yok; {neden}. e-Okul > Günlük Devamsızlık Girişi > "
                                 "Raporlar > 'Öğrenci Devamsızlık Ayrıntılı (OOK08001R060)' raporunu Excel olarak alıp "
                                 "Veri Aktarımı'na sürükleyin.", "Veri Aktarımı")


def _yas_kontrolu(db, satirlar: list[sigorta.SigortaSatiri], son: date) -> Kontrol:
    yas = int(db.ayar("gss_yukumlu_yas"))
    yukumlu = {str(db.ayar("belge_isletme_yukumlu")), str(db.ayar("belge_okul_yukumlu"))}
    ids = {s.ogrenci_id for s in satirlar if str(s.belge_turu) in yukumlu}
    asan = []
    for r in db.q("SELECT id, ad, soyad, dogum_tarihi FROM ogrenciler WHERE bakmakla_yukumlu = 1 "
                  "AND COALESCE(baska_sigortali, 0) = 0"):
        d = tarih(r["dogum_tarihi"])
        if r["id"] in ids and d and sigorta.yas_doldugu_gun(d, yas) <= son:
            asan.append(f"{r['ad']} {r['soyad']}")
    if asan:
        return Kontrol(False, "Belge türü (bakmakla yükümlülük yaşı)",
                       f"{len(asan)} öğrenci {yas} yaşını doldurdu, belge 7/49 yerine 42/50 olmalı: "
                       + ", ".join(asan[:5]) + ("…" if len(asan) > 5 else ""), "Öğrenciler / Çıraklar")
    return Kontrol(True, "Belge türü (bakmakla yükümlülük yaşı)", f"{yas} yaş sınırını aşan bakmakla yükümlü yok")


def _maol_kontrolu(db, satirlar: list[sigorta.SigortaSatiri]) -> Kontrol | None:
    ids = {s.ogrenci_id for s in satirlar}
    if not ids:
        return None
    soru = ",".join("?" * len(ids))
    rows = db.q(f"""SELECT o.ad, o.soyad, o.statu, s.program, COALESCE(o.baska_sigortali, 0) AS baska
                    FROM ogrenciler o LEFT JOIN siniflar s ON s.id = o.sinif_id WHERE o.id IN ({soru})""", list(ids))
    maol = [r for r in rows if maol_mi(r["program"], r["statu"])]
    if not maol:
        return None
    isaretli = sum(1 for r in maol if r["baska"])
    return Kontrol(None, "Açık lise (MAOL) öğrencileri",
                   f"{len(maol)} MAOL öğrencisi bildirilecek ({isaretli} tanesi 'başka işte sigortalı' işaretli). "
                   "Kendi işyerinden 4A/4B/4C sigortalı çalışanları öğrenci kartında işaretleyin: genel sağlık "
                   "sigortası primi ayrıca ödenmez, belge 7/49 yazılır. SGK 4A'da işe giriş hatası veren MAOL "
                   "öğrencisini tek tek girin.", "Öğrenciler / Çıraklar")


def on_kontrol(db, yil: int, ay: int, bugun: date | None = None) -> list[Kontrol]:
    """Aylık prim ve hizmet belgesi hazırlanmadan / verilmeden önceki kontrol listesi."""
    from . import sgk_toplu
    bugun = bugun or date.today()
    ilk, son = ay_araligi(yil, ay)
    out = [_isyeri_kontrolu(db)]
    liste = sigorta.aylik_liste(db, yil, ay)
    if not liste:
        out.append(Kontrol(False, "Bildirilecek sigortalılar", f"{_donem_adi(yil, ay)} döneminde sigortalı öğrenci "
                                                              "yok; yerleştirme (sigorta) kayıtlarını kontrol edin.",
                           "Yerleştirme ve Sözleşmeler"))
        return out
    belgeler = defaultdict(int)
    for s in liste:
        belgeler[str(s.belge_turu)] += 1
    out.append(Kontrol(True, "Bildirilecek sigortalılar", f"{len({s.ogrenci_id for s in liste})} öğrenci; "
                       + ", ".join(f"belge {b}: {n}" for b, n in sorted(belgeler.items()))))
    out.append(_devamsizlik_kontrolu(db, ilk, son, bugun))

    uyarilar: list[str] = []
    sgk_dosya.aphb_satirlari(db, yil, ay, uyarilar)
    tc = [u.split(":")[0] for u in uyarilar if "T.C." in u]
    out.append(Kontrol(not tc, "T.C. kimlik numaraları",
                       (f"{len(tc)} öğrenci belgeye alınamaz: " + ", ".join(tc[:5])) if tc else "Hepsi geçerli",
                       "Öğrenciler / Çıraklar" if tc else ""))
    uzun = [u for u in uyarilar if "karakterden uzun" in u]
    if uzun:
        out.append(Kontrol(None, "Ad / soyad uzunluğu", f"{len(uzun)} kişide ad veya soyad 18 karakterde "
                                                        "kısaltılacak; e-Bildirge'de 'Sicil No ile Sorgu' ile düzeltin."))

    giris = [b for b in sigorta.bekleyen_bildirimler(db, bugun, ileri_gun=0)
             if b.tur == "Giriş" and not b.bildirildi and b.olay_tarihi <= son]
    out.append(Kontrol(not giris, "İşe giriş bildirgeleri",
                       (f"{len(giris)} öğrencinin işe girişi 'bildirildi' işaretli değil; e-Bildirge girişi olmayan "
                        "sigortalıyı kabul etmez: " + ", ".join(b.ogrenci for b in giris[:5])) if giris else
                       "Bütün girişler bildirilmiş", "SGK Sigorta İşlemleri" if giris else ""))
    disi = [x for x in sgk_toplu.liste_disi_kalanlar(db, yil, ay) if x.seviye == "Liste dışı"]
    out.append(Kontrol(True if not disi else None, "Liste dışı kalan aktif öğrenciler",
                       f"{len(disi)} aktif öğrenci listede yok (Liste Dışı Kalanlar sekmesinde nedenleri)" if disi else
                       "Yok"))
    out.append(_yas_kontrolu(db, liste, son))
    maol = _maol_kontrolu(db, liste)
    if maol:
        out.append(maol)

    py, pa = _onceki(yil, ay)
    if sigorta.aylik_liste(db, py, pa) and not sgk_risk.aphb_verildi(db, py, pa):
        out.append(Kontrol(False, "Önceki ayın belgesi", f"{_donem_adi(py, pa)} belgesi verildi olarak kayıtlı değil."))
    else:
        out.append(Kontrol(True, "Önceki ayın belgesi", "Verildi" if sgk_risk.aphb_verildi(db, py, pa) else
                           "Önceki ayda sigortalı yok"))

    son_gun = sgk_risk.aphb_son_gunu(db, yil, ay)
    fark = fark_analizi(db, yil, ay)
    verildi = sgk_risk.aphb_verildi(db, yil, ay)
    if fark.beyan_var:
        out.append(Kontrol(not fark.satirlar, "Bu ayın belgesi",
                           f"Verildi ({tr(verildi)}). " + fark.ozet()
                           + (" Düzeltme dosyalarını (iptal + ek) üretin." if fark.satirlar else "")))
    elif verildi:
        out.append(Kontrol(None, "Bu ayın belgesi", f"Verildi işaretli ({tr(verildi)}) ama satır kaydı yok; sonraki "
                                                    "değişiklikleri izlemek için 'Beyanı XML'den Al' ile yüklediğiniz "
                                                    "dosyayı kaydedin."))
    elif bugun > son_gun:
        out.append(Kontrol(False, "Bu ayın belgesi", f"Son gün {tr(son_gun)} geçti; tahakkuk nedeni B yazılır, idari "
                                                     "para cezası doğabilir. Hemen verin."))
    else:
        out.append(Kontrol(None, "Bu ayın belgesi", f"Son gün {tr(son_gun)} ({(son_gun - bugun).days} gün kaldı). "
                                                    "Yükleyip onayladıktan sonra 'Beyanı Kaydet' deyin."))
    return out


def cikis_on_kontrol(db, tarih_: date, bugun: date | None = None) -> list[Kontrol]:
    """Dönem sonu toplu işten çıkıştan önce kontrol listesi."""
    bugun = bugun or date.today()
    out = []
    py, pa = _onceki(tarih_.year, tarih_.month)
    if sigorta.aylik_liste(db, py, pa) and not sgk_risk.aphb_verildi(db, py, pa):
        out.append(Kontrol(False, "Önceki ayın belgesi",
                           f"Toplu çıkıştan önce {_donem_adi(py, pa)} aylık prim ve hizmet belgesini verin; çıkış ayının "
                           "belgesi çıkışlardan sonra verilir. Aksi halde önceki dönem bilgisi ayrılış bildirgesine "
                           "yazılır ve sonradan verilen belgeyle çakışabilir.", "SGK Sigorta İşlemleri"))
    else:
        out.append(Kontrol(True, "Önceki ayın belgesi", f"{_donem_adi(py, pa)}: verildi ya da sigortalı yok"))
    out.append(_devamsizlik_kontrolu(db, date(tarih_.year, tarih_.month, 1), tarih_, bugun, cikis=True))
    kod = str(db.ayar("sgk_cikis_nedeni") or "").zfill(2)
    out.append(Kontrol(True if kod in AYRILIS_NEDENLERI else None, "İşten ayrılış nedeni kodu",
                       f"{kod} - {AYRILIS_NEDENLERI[kod]}" if kod in AYRILIS_NEDENLERI else
                       f"Kod {kod}; dönem sonu öğrenci çıkışlarında genellikle 22 (Diğer nedenler) kullanılır.",
                       "" if kod in AYRILIS_NEDENLERI else "Ayarlar ve Mevzuat Parametreleri"))
    yil_sonu = tarih(db.kurum()["ders_yili_sonu"])
    if yil_sonu is None:
        out.append(Kontrol(None, "Ders yılı sonu", "Kurum bilgilerinde ders yılı sonu girilmemiş.",
                           "Ayarlar ve Mevzuat Parametreleri"))
    elif tarih_ > yil_sonu:
        out.append(Kontrol(None, "Ders yılı sonu", f"Çıkış tarihi ders yılı sonundan ({tr(yil_sonu)}) sonra."))
    else:
        out.append(Kontrol(True, "Ders yılı sonu", f"Ders yılı sonu {tr(yil_sonu)}"))
    tatil = next((t for t in db.q("SELECT ad, baslangic, bitis FROM tatiller")
                  if tarih(t["baslangic"]) and tarih(t["baslangic"]) <= tarih_ <= (tarih(t["bitis"]) or tarih_)
                  and sgk_risk._TATIL_BILDIRILMEZ.search(t["ad"] or "")), None)
    if tatil:
        out.append(Kontrol(False, "Tatil", f"Çıkış tarihi '{tatil['ad']}' içinde; ara tatil ve yarıyıl tatilinde "
                                           "işten ayrılış bildirilmez."))
    acik = db.q("""SELECT y.tur, COUNT(*) AS n FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                   WHERE y.durum = 'Aktif' AND (y.bitis IS NULL OR y.bitis = '') GROUP BY y.tur""")
    okul = sum(r["n"] for r in acik if r["tur"] in OKUL_ICI_TURLER)
    isletme = sum(r["n"] for r in acik if r["tur"] not in OKUL_ICI_TURLER)
    ayri = bool(str(db.ayar("sgk_isyeri_sicil_okul") or "").strip())
    out.append(Kontrol(None if okul + isletme else True, "Açık sigorta kayıtları",
                       f"İşletmede {isletme}, okulda alan eğitimi {okul} kayıt çıkış tarihi bekliyor"
                       + ("; okul ve işletme için iki ayrı XML dosyası üretilir." if ayri and okul and isletme else ".")))
    return out


def kontrol_ozeti(kontroller: list[Kontrol]) -> str:
    sorun = [k for k in kontroller if k.durum is False]
    dikkat = [k for k in kontroller if k.durum is None]
    if not sorun and not dikkat:
        return "Bütün kontroller tamam."
    s = []
    if sorun:
        s.append(f"{len(sorun)} sorun ({', '.join(k.baslik for k in sorun)})")
    if dikkat:
        s.append(f"{len(dikkat)} dikkat ({', '.join(k.baslik for k in dikkat)})")
    return "; ".join(s) + "."


def excel_yaz(fark: BeyanFarki, kontroller: list[Kontrol], yol: Path | str) -> Path:
    from .excel_io import ExcelYazici
    x = ExcelYazici()
    baslik = f"SGK Aylık Beyan - {_donem_adi(fark.yil, fark.ay)}"
    x.sayfa("Ön Kontrol", ["Durum", "Kontrol", "Ayrıntı"], [[k.isaret, k.baslik, k.detay] for k in kontroller],
            baslik=baslik, alt_bilgi=[kontrol_ozeti(kontroller)])
    x.sayfa("Beyan Farkları", ["Durum", "Ad Soyad", "T.C.", "Belge", "Beyan: gün", "Beyan: PEK", "Şimdi: gün",
                               "Şimdi: PEK", "Açıklama"],
            [[f.durum, f.ad, f.tc, f.belge, f.eski.gun if f.eski else "", f.eski.pek if f.eski else "",
              f.yeni.gun if f.yeni else "", f.yeni.pek if f.yeni else "", f.aciklama] for f in fark.satirlar],
            baslik=baslik, alt_bilgi=[fark.ozet()] + [f"Beyan: {b.etiket}" for b in fark.beyanlar])
    return x.kaydet(yol)
