"""e-Okul, e-Mesem ve SGK sistemlerini program içinde açan tarayıcı ekranı."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QSplitter,
                               QTabBar, QTabWidget, QVBoxLayout, QWidget)

from .. import config
from ..services import baglanti
from ..services.baglanti import DIS_TARAYICI, SISTEM_SOZLUK, SISTEMLER, Sistem
from . import ortak

try:
    from PySide6.QtWebEngineCore import QWebEngineDownloadRequest, QWebEnginePage, QWebEngineProfile
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_VAR = True
except ImportError:  # PySide6-Addons kurulu değil
    WEBENGINE_VAR = False

SIFRE_ALANI_JS = """(function(){var f=document.querySelectorAll('input[type=password]');
for(var i=0;i<f.length;i++){var e=f[i];if(e.offsetParent!==null&&!e.disabled)return true;}return false;})()"""

DURUM_RENGI = {baglanti.DURUM_BAGLI: "#1b5e20", baglanti.DURUM_GIRIS: "#8a6d3b", baglanti.DURUM_ACIK: "#555"}

_profil = None
_sayfalar: list = []


def profil():
    """Tüm sekmelerin paylaştığı tarayıcı profili. Oturum çerezleri diske yazılmaz; program
    kapanınca bütün oturumlar sona erer."""
    global _profil
    if _profil is None:
        _profil = QWebEngineProfile(config.AD, QApplication.instance())
        kok = config.data_dir() / "Tarayici"
        _profil.setPersistentStoragePath(str(kok / "Depo"))
        _profil.setCachePath(str(kok / "Onbellek"))
        _profil.setPersistentCookiesPolicy(QWebEngineProfile.NoPersistentCookies)
        QApplication.instance().aboutToQuit.connect(_kapat)
    return _profil


def _kapat() -> None:
    """Profil, kendisini kullanan sayfalardan önce silinirse Chromium çöker (0xC0000409)."""
    global _profil
    import shiboken6
    for s in _sayfalar:
        if shiboken6.isValid(s):
            v = s.parent()
            if isinstance(v, QWebEngineView) and shiboken6.isValid(v):
                v.setPage(None)
            shiboken6.delete(s)
    _sayfalar.clear()
    if _profil is not None and shiboken6.isValid(_profil):
        shiboken6.delete(_profil)
    _profil = None


if WEBENGINE_VAR:
    class _Sayfa(QWebEnginePage):
        def __init__(self, sekme_ac, parent=None):
            super().__init__(profil(), parent)
            self._sekme_ac = sekme_ac
            _sayfalar.append(self)

        def createWindow(self, _tur):
            return self._sekme_ac()

        def chooseFiles(self, mod, eski, _turler):
            klasor = baglanti.yukleme_baslangici()
            if mod == QWebEnginePage.FileSelectOpenMultiple:
                yollar, _ = QFileDialog.getOpenFileNames(self.parent(), "Yüklenecek dosyaları seçin", klasor)
                return yollar
            yol, _ = QFileDialog.getOpenFileName(self.parent(), "Yüklenecek dosyayı seçin", klasor)
            return [yol] if yol else []


class TarayiciSekmesi(QWidget):
    def __init__(self, ekran: "BaglantiSayfasi", sistem: Sistem, adres: str | None = None):
        super().__init__()
        self.ekran = ekran
        self.sistem = sistem
        self.durum = baglanti.DURUM_ACIK

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        arac = QHBoxLayout()
        self.view = QWebEngineView()
        self.sayfa = _Sayfa(lambda: ekran.sekme_ac(sistem, bos=True).sayfa, self.view)
        self.view.setPage(self.sayfa)
        for metin, fn in [("◀ Geri", self.view.back), ("İleri ▶", self.view.forward), ("Yenile", self.view.reload),
                          ("Başa Dön", lambda: self.view.setUrl(QUrl(sistem.adres)))]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            arac.addWidget(b)
        self.adres = QLabel()
        self.adres.setTextInteractionFlags(Qt.TextSelectableByMouse)
        arac.addWidget(self.adres, 1)
        self.durum_lbl = QLabel()
        arac.addWidget(self.durum_lbl)
        self.elle = QPushButton("Girişi Yaptım")
        self.elle.setToolTip("Program girişi kendisi algılayamazsa bu sistemi bağlı olarak işaretler.")
        self.elle.clicked.connect(self._elle_bagla)
        arac.addWidget(self.elle)
        b = QPushButton("Edge/Chrome'da Aç")
        b.setToolTip("Sayfayı bilgisayarın varsayılan tarayıcısında açar. Oradan indirilen Excel listeleri de "
                     "İndirilenler klasöründen alınır.")
        b.clicked.connect(lambda: self.dis_tarayicida_ac())
        arac.addWidget(b)
        lay.addLayout(arac)
        lay.addWidget(self.view, 1)

        self._coktu = False
        self.sayfa.renderProcessTerminated.connect(self._sayfa_coktu)
        self.view.urlChanged.connect(lambda u: (self.adres.setText(u.toString()), self.denetle()))
        self.view.loadFinished.connect(lambda _ok: self.denetle())
        self.view.titleChanged.connect(lambda _t: self.ekran.sekme_basligi(self))
        self._zamanlayici = QTimer(self)
        self._zamanlayici.timeout.connect(self.denetle)
        self._zamanlayici.start(1000)
        self._durumu_goster()
        if adres:
            self.view.setUrl(QUrl(adres))

    def denetle(self) -> None:
        url = self.view.url().toString()
        if url:
            self.sayfa.runJavaScript(SIFRE_ALANI_JS, 0, lambda v, url=url: self._durum_hesapla(url, bool(v)))

    def _durum_hesapla(self, url: str, sifre_alani_var: bool) -> None:
        if baglanti.giris_adimi_mi(url, sifre_alani_var):
            self.ekran.giris_goruldu[self.sistem.anahtar] = True
        yeni = baglanti.durum(self.sistem, url, sifre_alani_var, self.ekran.giris_goruldu.get(self.sistem.anahtar, False))
        if yeni != self.durum:
            self.durum = yeni
            self._durumu_goster()
            self.ekran.durum_degisti(self)

    def dis_tarayicida_ac(self, url: str | None = None) -> None:
        url = url or self.view.url().toString() or self.sistem.adres
        QDesktopServices.openUrl(QUrl(url))

    def _sayfa_coktu(self, durum, _kod) -> None:
        if durum == QWebEnginePage.NormalTerminationStatus or self._coktu:
            return
        self._coktu = True
        url = self.view.url().toString() or self.sistem.adres
        self.durum_lbl.setText(f"<b style='color:#b00020'>{self.sistem.ad}: program içinde açılamadı, "
                               "varsayılan tarayıcıda açıldı</b>")
        self.dis_tarayicida_ac(url)
        self.ekran.dis_tarayici_bilgisi(self.sistem)

    def _elle_bagla(self) -> None:
        self.ekran.giris_goruldu[self.sistem.anahtar] = True
        self.denetle()

    def _durumu_goster(self) -> None:
        self.durum_lbl.setText(f"<b style='color:{DURUM_RENGI[self.durum]}'>{self.sistem.ad}: {self.durum}</b>")
        self.elle.setVisible(self.durum != baglanti.DURUM_BAGLI)


class BaglantiSayfasi(QWidget):
    def __init__(self, db, pencere=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.pencere = pencere
        self.giris_goruldu: dict[str, bool] = {}
        self._indirmeler: list = []
        self._profil_bagli = False

        lay = QVBoxLayout(self)
        lbl = QLabel("Mesleki ve teknik Anadolu lisesi, mesleki eğitim merkezi ve çok programlı Anadolu lisesi "
                     "aynı ekrandan çalışır. Sistemi açın ve girişi <b>kendi şifrenizle</b> yapın; MesKoord "
                     "şifrelerinizi görmez ve saklamaz. Giriş algılanınca sekme hemen <b>Bağlı</b> olur. "
                     "İndirdiğiniz öğrenci, öğretmen, işletme ve SGK listeleri programa işlenir; eklenen ve "
                     "değişen kayıtlar ana sayfada bildirilir. Aynı kayıtları ilgili ekranlardan elle de "
                     "girebilirsiniz. Program kapanınca oturumlar kapanır.")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        ust = ortak.AkisDuzeni()
        for s in SISTEMLER:
            b = QPushButton(s.ad)
            b.setToolTip(s.aciklama)
            b.clicked.connect(lambda _=False, s=s: self.ac(s.anahtar))
            ust.addWidget(b)
        ust.addStretch(1)
        self.otomatik = QCheckBox("İndirilen listeleri otomatik aktar")
        self.otomatik.setChecked(True)
        ust.addWidget(self.otomatik)
        self.izle = QCheckBox("Edge/Chrome ile indirilen listeleri de al")
        self.izle.setToolTip("Bilgisayarın İndirilenler klasörüne bu ekran açıkken yeni inen Excel/CSV/HTML "
                             "tablolarını yakalar. Daha önce inmiş dosyalara dokunulmaz.")
        self.izle.setChecked(True)
        self.izle.toggled.connect(self._izlemeyi_ayarla)
        ust.addWidget(self.izle)
        self.belgeler = QCheckBox("PDF/Word/ZIP de")
        self.belgeler.setToolTip("e-Okul/e-Mesem'den PDF, Word veya ZIP olarak indirilen listeler de alınır. Dosya "
                                 "yalnızca bu bilgisayarda okunur; içinde tanınan bir liste yoksa hiçbir şey "
                                 "değişmez.")
        self.belgeler.setChecked(True)
        ust.addWidget(self.belgeler)
        b = QPushButton("İndirilenler Klasörü")
        b.clicked.connect(lambda: ortak.dosya_ac(config.data_dir() / "Indirilenler"))
        ust.addWidget(b)
        lay.addLayout(ust)

        self.durumlar = QLabel()
        lay.addWidget(self.durumlar)

        bolme = QSplitter(Qt.Vertical)
        self.sekmeler = QTabWidget()
        self.sekmeler.setTabsClosable(True)
        self.sekmeler.tabCloseRequested.connect(self._sekme_kapat)
        self.bos = QLabel()
        self.bos.setWordWrap(True)
        self.bos.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.bos.setText(self._bos_metin())
        self.sekmeler.addTab(self.bos, "Başlarken")
        self.sekmeler.tabBar().setTabButton(0, QTabBar.RightSide, None)
        bolme.addWidget(self.sekmeler)

        alt = QWidget()
        al = QVBoxLayout(alt)
        al.setContentsMargins(0, 0, 0, 0)
        dug = QHBoxLayout()
        dug.addWidget(QLabel("<b>İndirilen dosyalar</b> (çift tıklayınca dosya açılır)"))
        dug.addStretch(1)
        b = QPushButton("Seçili Dosyayı Aktarım Ekranında İncele")
        b.clicked.connect(self._aktarimda_incele)
        dug.addWidget(b)
        al.addLayout(dug)
        self.kayit_model = ortak.TabloModeli(["Saat", "Sistem", "Dosya", "Sonuç"])
        self.kayit, self.kayit_proxy = ortak.tablo_gorunumu(self.kayit_model, False)
        self.kayit.doubleClicked.connect(self._dosya_ac)
        al.addWidget(self.kayit, 1)
        bolme.addWidget(alt)
        bolme.setStretchFactor(0, 5)
        bolme.setStretchFactor(1, 1)
        lay.addWidget(bolme, 1)
        self._kayitlar: list[list] = []
        self._yollar: list[Path] = []
        self._renkler: dict[int, object] = {}
        self._is_kuyruk: list[tuple[Sistem, Path]] = []
        self._isleniyor = False
        self._ac_kuyruk: list[str] = []
        self._aciliyor = False
        self._durumlari_yaz()

        self.indirilenler = Path(QStandardPaths.writableLocation(QStandardPaths.DownloadLocation) or
                                 Path.home() / "Downloads")
        self._izleyici = QFileSystemWatcher(self)
        self._izleyici.directoryChanged.connect(lambda _: self._klasor_degisti())
        self._bilinen: set[str] = set()
        self._bekleyen: dict[Path, int] = {}
        self._kontrol = QTimer(self)
        self._kontrol.setInterval(1500)
        self._kontrol.timeout.connect(self._bekleyenleri_isle)
        self._izlemeyi_ayarla(self.izle.isChecked())

    def _bos_metin(self) -> str:
        if not WEBENGINE_VAR:
            return ("<b>Tarayıcı bileşeni kurulu değil.</b><br>Komut isteminde şunu çalıştırın:<br>"
                    "<code>.venv\\Scripts\\python.exe -m pip install PySide6-Addons</code>")
        satirlar = "".join(f"<li><b>{s.ad}</b>: {s.aciklama}</li>" for s in SISTEMLER)
        return (f"<p>Yukarıdaki düğmelerle bir sistemi açın.</p><ul>{satirlar}</ul>"
                "<p>Giriş algılanınca sekme başlığında <b>Bağlı</b> yazar. Algılanmazsa sekmedeki "
                "<b>Girişi Yaptım</b> düğmesine basın.</p>")

    # ------------------------------------------------------------------ sekmeler

    def turune_gore_ac(self) -> None:
        """Kurum türünün sistemlerini tek tek açar; hepsi aynı anda açılmaz, ekran kilitlenmez."""
        from ..services.kurum_turu import sistemler
        if not WEBENGINE_VAR:
            ortak.hata(self, "Tarayıcı bileşeni (PySide6-Addons) kurulu değil.")
            return
        if self._aciliyor:
            return
        k = self.db.kurum()
        self._ac_kuyruk = [a for a in sistemler(k["tur"] or "MTAL") if a in SISTEM_SOZLUK]
        self._aciliyor = True
        self._ac_siradaki()

    def _ac_siradaki(self) -> None:
        if not self._ac_kuyruk:
            self._aciliyor = False
            return
        self.ac(self._ac_kuyruk.pop(0))
        if self._ac_kuyruk:
            QTimer.singleShot(700, self._ac_siradaki)
        else:
            self._aciliyor = False

    def ac(self, anahtar: str) -> None:
        if not WEBENGINE_VAR:
            ortak.hata(self, "Tarayıcı bileşeni (PySide6-Addons) kurulu değil.")
            return
        sistem = SISTEM_SOZLUK[anahtar]
        for i in range(self.sekmeler.count()):
            w = self.sekmeler.widget(i)
            if isinstance(w, TarayiciSekmesi) and w.sistem.anahtar == anahtar:
                self.sekmeler.setCurrentIndex(i)
                return
        self.sekme_ac(sistem)

    def sekme_ac(self, sistem: Sistem, bos: bool = False) -> TarayiciSekmesi:
        if not self._profil_bagli:
            profil().downloadRequested.connect(self._indirme_istendi)
            self._profil_bagli = True
        w = TarayiciSekmesi(self, sistem, None if bos else sistem.adres)
        i = self.sekmeler.addTab(w, sistem.ad)
        self.sekmeler.setCurrentIndex(i)
        self._durumlari_yaz()
        return w

    def _sekme_kapat(self, i: int) -> None:
        w = self.sekmeler.widget(i)
        if not isinstance(w, TarayiciSekmesi):
            return
        self.sekmeler.removeTab(i)
        w.deleteLater()
        self._durumlari_yaz()

    def sekme_basligi(self, w: TarayiciSekmesi) -> None:
        i = self.sekmeler.indexOf(w)
        if i >= 0:
            baslik = w.view.title() or w.sistem.ad
            isaret = "● " if w.durum == baglanti.DURUM_BAGLI else ""
            self.sekmeler.setTabText(i, f"{isaret}{w.sistem.ad}" + (f" - {baslik[:30]}" if baslik != w.sistem.ad else ""))
            self.sekmeler.setTabToolTip(i, f"{w.sistem.ad}: {w.durum}")

    def durum_degisti(self, w: TarayiciSekmesi) -> None:
        self.sekme_basligi(w)
        self._durumlari_yaz()

    def _durumlari_yaz(self) -> None:
        durum = {}
        for i in range(self.sekmeler.count()):
            w = self.sekmeler.widget(i)
            if isinstance(w, TarayiciSekmesi):
                if durum.get(w.sistem.anahtar) != baglanti.DURUM_BAGLI:
                    durum[w.sistem.anahtar] = w.durum
        parca = [f"<span style='color:{DURUM_RENGI[durum[s.anahtar]]}'>{s.ad}: {durum[s.anahtar]}</span>"
                 if s.anahtar in durum else f"<span style='color:#999'>{s.ad}: kapalı</span>" for s in SISTEMLER]
        self.durumlar.setText("Bağlantılar: " + " &nbsp;|&nbsp; ".join(parca))

    def dis_tarayici_bilgisi(self, sistem: Sistem) -> None:
        izleme = (f"Orada indirdiğiniz listeler {self.indirilenler} klasöründen otomatik alınacak."
                  if self.izle.isChecked() else "İndirdiğiniz dosyaları Veri Aktarımı ekranına sürükleyin.")
        self._kaydet(sistem, None, "Program içinde açılamadı; varsayılan tarayıcıda açıldı. Girişi orada yapın. "
                     + izleme, ortak.RENK_UYARI)

    # ------------------------------------------------------------------ İndirilenler klasörü

    def _dosyalar(self) -> set[str]:
        try:
            return {p.name for p in self.indirilenler.iterdir() if p.is_file()}
        except OSError:
            return set()

    def _izlemeyi_ayarla(self, acik: bool) -> None:
        klasor = str(self.indirilenler)
        if acik and self.indirilenler.is_dir():
            self._bilinen = self._dosyalar()
            if klasor not in self._izleyici.directories():
                self._izleyici.addPath(klasor)
        elif klasor in self._izleyici.directories():
            self._izleyici.removePath(klasor)
            self._bekleyen.clear()

    def _klasor_degisti(self) -> None:
        simdi = self._dosyalar()
        for ad in simdi - self._bilinen:
            yol = self.indirilenler / ad
            if baglanti.izlenecek_mi(yol, self.belgeler.isChecked()):
                self._bekleyen.setdefault(yol, -1)
        self._bilinen = simdi
        if self._bekleyen and not self._kontrol.isActive():
            self._kontrol.start()

    def _bekleyenleri_isle(self) -> None:
        for yol, onceki in list(self._bekleyen.items()):
            try:
                boyut = yol.stat().st_size
            except OSError:
                self._bekleyen.pop(yol)
                continue
            if boyut == 0 or boyut != onceki:
                self._bekleyen[yol] = boyut
                continue
            self._bekleyen.pop(yol)
            self._isle(DIS_TARAYICI, yol)
        if not self._bekleyen:
            self._kontrol.stop()

    # ------------------------------------------------------------------ indirmeler

    def _sekme_bul(self, sayfa) -> TarayiciSekmesi | None:
        for i in range(self.sekmeler.count()):
            w = self.sekmeler.widget(i)
            if isinstance(w, TarayiciSekmesi) and w.sayfa is sayfa:
                return w
        return None

    def _indirme_istendi(self, istek) -> None:
        w = self._sekme_bul(istek.page())
        sistem = w.sistem if w else next((s for s in SISTEMLER if baglanti.sistemin_mi(s, istek.url().toString())),
                                          SISTEMLER[0])
        ad = istek.suggestedFileName() or istek.downloadFileName() or "indirilen"
        yol = baglanti.benzersiz_yol(baglanti.indirme_klasoru(sistem), ad)
        istek.setDownloadDirectory(str(yol.parent))
        istek.setDownloadFileName(yol.name)
        self._indirmeler.append(istek)
        istek.isFinishedChanged.connect(lambda i=istek, s=sistem, y=yol: self._indirme_bitti(i, s, y))
        istek.accept()

    def _indirme_bitti(self, istek, sistem: Sistem, yol: Path) -> None:
        if not istek.isFinished():
            return
        if istek in self._indirmeler:
            self._indirmeler.remove(istek)
        if istek.state() != QWebEngineDownloadRequest.DownloadCompleted:
            self._kaydet(sistem, yol, f"İndirilemedi: {istek.interruptReasonString()}", ortak.RENK_KRITIK)
            return
        self._isle(sistem, yol)

    def _isle(self, sistem: Sistem, yol: Path) -> None:
        self._is_kuyruk.append((sistem, yol))
        self._isle_siradaki()

    def _isle_siradaki(self) -> None:
        if self._isleniyor or not self._is_kuyruk:
            return
        sistem, yol = self._is_kuyruk.pop(0)
        self._isleniyor = True
        otomatik = self.otomatik.isChecked()
        if self.pencere is not None:
            self.pencere.statusBar().showMessage(f"{sistem.ad}: {yol.name} aktarılıyor…", 8000)

        def is_() -> object:
            kopya = self.db.kopya()
            try:
                return baglanti.indirileni_isle(kopya, yol, otomatik)
            finally:
                kopya.close()

        def bitti(s) -> None:
            self._isleniyor = False
            self._sonucu_goster(sistem, yol, s)
            self._isle_siradaki()

        def hata(tb: str) -> None:
            self._isleniyor = False
            satir = tb.strip().splitlines()[-1] if tb.strip() else "aktarım hatası"
            self._kaydet(sistem, yol, f"Aktarım hatası: {satir}", ortak.RENK_KRITIK)
            self._isle_siradaki()

        ortak.arka_planda(is_, bitti, hata)

    def _sonucu_goster(self, sistem: Sistem, yol: Path, s) -> None:
        renk = (ortak.RENK_TAMAM if s.aktarildi or s.sgk_listesi else ortak.RENK_UYARI if s.hatalar or s.taninmayan
                else None)
        self._kaydet(sistem, yol, s.ozet, renk)
        self._ana_yenile()
        if self.pencere is None:
            return
        if s.aktarildi:
            self.pencere.statusBar().showMessage(f"{sistem.ad}: {yol.name} aktarıldı. {s.ozet}", 15000)
        elif s.sgk_listesi:
            self.pencere.statusBar().showMessage(f"{sistem.ad}: {yol.name} SGK listesi olarak alındı. "
                                                 "SGK > Liste Karşılaştırma sekmesine bakın.", 15000)
        elif s.taninmayan:
            self.pencere.statusBar().showMessage(f"{yol.name}: liste türü tanınamadı. Aşağıdaki listeden seçip "
                                                 "'Aktarım Ekranında İncele' ile türünü belirleyin.", 15000)

    def _ana_yenile(self) -> None:
        sayfalar = getattr(self.pencere, "sayfa", None)
        if isinstance(sayfalar, dict):
            ana = sayfalar.get("Ana Sayfa")
            if ana is not None and hasattr(ana, "yenile"):
                ana.yenile()

    def _kaydet(self, sistem: Sistem, yol: Path | None, sonuc: str, renk) -> None:
        self._kayitlar.insert(0, [datetime.now().strftime("%H:%M:%S"), sistem.ad, yol.name if yol else "-", sonuc])
        self._yollar.insert(0, yol)
        self._renkler = {k + 1: v for k, v in self._renkler.items()}
        if renk is not None:
            self._renkler[0] = renk
        self.kayit_model.ayarla(self._kayitlar, renkler=self._renkler)
        ortak.sutunlari_sigdir(self.kayit, 500)

    def _secili_yol(self) -> Path | None:
        satirlar = ortak.secili_satirlar(self.kayit, self.kayit_proxy)
        return self._yollar[satirlar[0]] if satirlar else None

    def _dosya_ac(self, idx) -> None:
        r = self.kayit_proxy.mapToSource(idx).row()
        if 0 <= r < len(self._yollar) and self._yollar[r]:
            ortak.dosya_ac(self._yollar[r])

    def _aktarimda_incele(self) -> None:
        yol = self._secili_yol()
        if not yol:
            ortak.bilgi(self, "Önce listeden indirilen bir dosya seçin.")
            return
        w = self.pencere.git("Veri Aktarımı") if self.pencere is not None else None
        if w is not None:
            w.dosyalari_ekle([str(yol)])
