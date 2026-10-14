"""e-Okul, e-Mesem ve SGK sistemlerine kullanıcının kendi girişiyle bağlanma.

Bu sistemlerin dış programlara açık bir servisi olmadığından program yalnızca bir tarayıcı
penceresi sunar: girişi kullanıcı yapar, girişten sonra sistemden indirilen listeler
yakalanıp veritabanına aktarılır. Şifreler programda tutulmaz.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from .. import config
from . import aktarim


@dataclass(frozen=True)
class Sistem:
    anahtar: str
    ad: str
    adres: str
    alan_adlari: tuple[str, ...]
    aciklama: str


SISTEMLER: list[Sistem] = [
    Sistem("eokul", "e-Okul", "https://mebbis.meb.gov.tr/Default.aspx", ("mebbis.meb.gov.tr",),
           "MEBBİS hesabınızla giriş yapın. Öğrenci listelerini, İşletmelerde Mesleki Eğitim modülündeki "
           "öğrenci-işletme listesini ve devamsızlık raporlarını Excel olarak indirin."),
    Sistem("emesem", "e-Mesem", "https://e-mesem.meb.gov.tr/", ("e-mesem.meb.gov.tr",),
           "Kurum girişini yapın. Öğrenci-işletme, sözleşme ve devlet katkısı listelerini Excel olarak indirin."),
    Sistem("ebildirge", "e-Bildirge V2", "https://ebildirge.sgk.gov.tr/EBildirgeV2", ("ebildirge.sgk.gov.tr",),
           "İşyeri kullanıcı adı, sistem şifresi ve işyeri şifresiyle giriş yapın. Aylık prim ve hizmet "
           "belgesini buradan yükleyip onaylarsınız; dosya seçme penceresi MesKoord çıktı klasöründe açılır."),
    Sistem("sgk4a", "SGK İşe Giriş / Çıkış", "https://uyg.sgk.gov.tr/SgkTescil4a/", ("uyg.sgk.gov.tr",),
           "e-Bildirge kullanıcı bilgilerinizle giriş yapın. İşe giriş ve işten ayrılış bildirgelerini verin; "
           "indirdiğiniz bildirge listeleri öğrencilerin SGK giriş/çıkış durumuna işlenir."),
    Sistem("vizite", "SGK e-Vizite", "https://uyg.sgk.gov.tr/vizite/welcome.do", ("uyg.sgk.gov.tr",),
           "İşyeri hekimi vizite ve istirahat ekranı. Girişten sonra vizite işlemlerini programdan çıkmadan yapın; "
           "indirdiğiniz listeler yakalanır."),
]
SISTEM_SOZLUK = {s.anahtar: s for s in SISTEMLER}
DIS_TARAYICI = Sistem("dis", "Edge/Chrome", "", (), "Bilgisayarın İndirilenler klasörüne inen listeler")

IZLENEN_UZANTILAR = {".xls", ".xlsx", ".xlsm", ".csv", ".ods", ".htm", ".html"}
BELGE_UZANTILARI = {".pdf", ".docx", ".zip"}
GECICI_UZANTILAR = {".crdownload", ".partial", ".part", ".tmp", ".download"}

GIRIS_ALAN_ADLARI = ("giris.turkiye.gov.tr", "mebbis.meb.gov.tr")

DURUM_ACIK = "Açık (giriş yapılmadı)"
DURUM_GIRIS = "Giriş bekleniyor"
DURUM_BAGLI = "Bağlı"


def alan_adi(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def sistemin_mi(sistem: Sistem, url: str) -> bool:
    h = alan_adi(url)
    return any(h == a or h.endswith("." + a) for a in sistem.alan_adlari)


def giris_adimi_mi(url: str, sifre_alani_var: bool) -> bool:
    h = alan_adi(url)
    return sifre_alani_var or any(h == a or h.endswith("." + a) for a in GIRIS_ALAN_ADLARI)


def durum(sistem: Sistem, url: str, sifre_alani_var: bool, giris_goruldu: bool) -> str:
    """Sayfanın adresine ve şifre alanı içerip içermediğine göre bağlantı durumu.

    Sistemlerin açılış sayfaları da şifre alanı içermediğinden, "Bağlı" sayılmak için
    önce bir giriş adımından (şifre alanı veya e-Devlet/MEBBİS girişi) geçilmiş olmalıdır.
    """
    if giris_adimi_mi(url, sifre_alani_var):
        return DURUM_GIRIS
    if giris_goruldu and sistemin_mi(sistem, url):
        return DURUM_BAGLI
    return DURUM_ACIK


_yuklenecek: list[Path] = []


def yuklenecek_ayarla(yollar: list[Path]) -> None:
    """Sistemin dosya yükleme penceresi bu dosyalarla açılır (son üretilen SGK XML'i gibi)."""
    _yuklenecek[:] = [Path(y) for y in yollar]


def yukleme_baslangici() -> str:
    """Dosya seçme penceresinin açılacağı yol: varsa yüklenmeyi bekleyen dosya, yoksa çıktı klasörü."""
    for y in _yuklenecek:
        if y.exists():
            return str(y)
    return str(config.output_dir())


def indirme_klasoru(sistem: Sistem) -> Path:
    p = config.data_dir() / "Indirilenler" / sistem.ad.replace("/", "-")
    p.mkdir(parents=True, exist_ok=True)
    return p


def guvenli_dosya_adi(ad: str) -> str:
    ad = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", ad).strip(" .")
    return ad or "indirilen"


def izlenecek_mi(yol: Path, belgeler: bool = False) -> bool:
    """Dış tarayıcıyla İndirilenler klasörüne inen dosyalardan tablo dosyaları alınır; PDF, Word ve ZIP
    yalnızca kullanıcı isterse (belgeler=True) alınır. Diğer dosyalara dokunulmaz."""
    ad = yol.name.lower()
    uzantilar = IZLENEN_UZANTILAR | (BELGE_UZANTILARI if belgeler else set())
    return (yol.suffix.lower() in uzantilar and not ad.startswith(("~$", "."))
            and not any(ad.endswith(u) for u in GECICI_UZANTILAR))


def benzersiz_yol(klasor: Path, ad: str) -> Path:
    yol = klasor / guvenli_dosya_adi(ad)
    n = 1
    while yol.exists():
        yol = klasor / f"{Path(ad).stem} ({n}){Path(ad).suffix}"
        n += 1
    return yol


@dataclass
class IndirmeSonucu:
    yol: Path
    aktarildi: bool = False
    satirlar: list[str] = field(default_factory=list)
    hatalar: list[str] = field(default_factory=list)
    taninmayan: int = 0  # türü tanınmayan tablo sayısı (Veri Aktarımı ekranında elle seçilebilir)
    sgk_listesi: bool = False  # SGK sigortalı/hizmet listesi: karşılaştırma ekranında kullanılır

    @property
    def ozet(self) -> str:
        if self.aktarildi:
            s = "; ".join(self.satirlar)
            if self.sgk_listesi:
                s += "; SGK listesi karşılaştırma için alındı"
            if self.taninmayan:
                s += f" ({self.taninmayan} tablo tanınmadı: Aktarım ekranında türünü seçebilirsiniz)"
            return s
        if self.sgk_listesi:
            return "SGK listesi alındı: SGK > Liste Karşılaştırma sekmesinde okul kayıtlarıyla karşılaştırıldı"
        if self.hatalar:
            ek = " — 'Seçili Dosyayı Aktarım Ekranında İncele' ile türünü seçin" if self.taninmayan else ""
            return "Aktarılmadı: " + "; ".join(self.hatalar) + ek
        return "Kaydedildi (aktarım yapılmadı)"


def indirileni_isle(db, yol: Path | str, otomatik: bool) -> IndirmeSonucu:
    """İndirilen dosyadaki (Excel, PDF, Word, HTML, ZIP...) tanınan tabloları aktarır. Aktarımdan önce yedek
    alınır. SGK sigortalı/hizmet listeleri ayrıca karşılaştırma için saklanır."""
    yol = Path(yol)
    sonuc = IndirmeSonucu(yol)
    if not otomatik:
        return sonuc
    from . import sgk_karsilastirma
    bulunan, hatalar = aktarim.dosyalari_incele([yol])
    sonuc.sgk_listesi = sgk_karsilastirma.son_listeyi_kaydet(yol, [b.tablo for b in bulunan])
    sonuc.taninmayan = sum(1 for b in bulunan if not b.en_iyi and not sgk_karsilastirma.sgk_tablosu(b.tablo))
    if not any(b.en_iyi for b in bulunan):
        if not sonuc.sgk_listesi:
            sonuc.hatalar = hatalar or ["dosyada tanınan bir veri listesi yok"]
        else:
            from . import degisiklik
            degisiklik.kaydet(db, [], "SGK listesi güncellendi. Farklar SGK > Liste Karşılaştırma "
                              "ve ana sayfadaki uyarılarda görünür.")
        return sonuc
    db.yedekle()
    sonuclar, hatalar = aktarim.otomatik_aktar(db, [yol])
    sonuc.satirlar = [s.ozet_metni() for s in sonuclar]
    sonuc.hatalar = hatalar
    sonuc.aktarildi = any(s.eklenen or s.guncellenen for s in sonuclar)
    from . import degisiklik
    ek = ""
    if sonuc.sgk_listesi:
        ek = "SGK listesi güncellendi. Farklar SGK > Liste Karşılaştırma ve ana sayfadaki uyarılarda görünür."
    if sonuc.aktarildi or ek:
        degisiklik.kaydet(db, sonuclar, ek)
    return sonuc
