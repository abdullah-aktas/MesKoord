"""Ana pencere: sol menü ve sayfalar."""
from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
                               QMainWindow, QMessageBox, QProgressDialog, QPushButton, QScrollArea, QStackedWidget,
                               QTabWidget, QVBoxLayout, QWidget)

from .. import APP_NAME, APP_TITLE, __version__, config, lisans, marka
from ..services import guncelleme
from . import ortak
from . import varliklar as V
from .crud import CrudSayfasi
from .lisans_penceresi import LisansPenceresi
from .sayfa_aktarim import AktarimSayfasi, surukle_dosyalar
from .sayfa_ana import AnaSayfa
from .sayfa_asistan import AsistanSayfasi
from .sayfa_ayarlar import AyarlarSayfasi, MevzuatParametreleri
from .sayfa_baglanti import BaglantiSayfasi
from .sayfa_toplu_giris import TopluGirisSayfasi
from .sayfa_toplu_gonderim import TopluGonderimSayfasi
from .sayfa_belge_aktar import BelgeSayfasi
from .sayfa_belge_takip import BelgeTakipSayfasi
from .sayfa_ekders_devam import DevamSayfasi, EkDersSayfasi
from .sayfa_esitleme import EsitlemeSayfasi
from .sayfa_komisyon import KomisyonSayfasi, isletme_sayfasi
from .sayfa_koordinator import KoordinatorSayfasi
from .sayfa_program import ProgramSayfasi
from .sayfa_program_araclari import ProgramAraclariSayfasi
from .sayfa_sgk_ucret import SgkSayfasi, UcretSayfasi
from .sayfa_sinav import SinavSayfasi
from .sayfa_yerlestirme import yerlestirme_sayfasi
from .yan_menu import YanMenu

STIL = marka.stil()
DAR_EKRAN = 1280  # bu genişliğin altındaki ekranlarda menü ilk açılışta simge şeridi olarak gelir
# Canlı yenilemede dokunulmayan sayfalar (kullanıcının kaydetmediği girişleri silinmesin)
CANLI_YENILEME_DISI = (MevzuatParametreleri, TopluGirisSayfasi, AktarimSayfasi, BaglantiSayfasi, EsitlemeSayfasi)


def arayuz_ayarlari() -> QSettings:
    """Pencere boyutu, menü ve son ekran ayarları; 1.3.0 öncesi KoordMES adıyla saklananlar bir kez aktarılır."""
    ayar = QSettings(QSettings.defaultFormat(), QSettings.UserScope, APP_NAME, "arayuz")
    if not ayar.allKeys():
        eski = QSettings(QSettings.defaultFormat(), QSettings.UserScope, config.ESKI_AD, "arayuz")
        for k in eski.allKeys():
            ayar.setValue(k, eski.value(k))
    return ayar


def sayfayi_yenile(w: QWidget | None) -> bool:
    """Görünen sayfayı (sekmeliyse görünen sekmeyi) veritabanından yeniden okur."""
    while isinstance(w, QTabWidget):
        w = w.currentWidget()
    if w is None or isinstance(w, CANLI_YENILEME_DISI):
        return False
    for ad in ("canli_yenile", "yenile", "doldur"):
        fn = getattr(w, ad, None)
        if callable(fn):
            fn()
            return True
    return False


class CikisPenceresi(QDialog):
    def __init__(self, parent, ayar: QSettings, isler: int, ag_uyarisi: str):
        super().__init__(parent)
        self.setWindowTitle("Güvenli Çıkış")
        lay = QVBoxLayout(self)
        ust = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(marka.logo_pixmap(64))
        ust.addWidget(logo)
        ust.addWidget(QLabel(f"<h3 style='color:{marka.ANA}'>{marka.URUN} kapatılsın mı?</h3>"
                             "Açık işlemler tamamlanır, taslaklar kaydedilir ve veritabanı güvenle kapatılır."), 1)
        lay.addLayout(ust)
        if isler:
            uy = QLabel(f"<b style='color:#b00020'>Arka planda süren {isler} işlem var.</b> Çıkışta bitmesi beklenir.")
            uy.setWordWrap(True)
            lay.addWidget(uy)
        if ag_uyarisi:
            uy = QLabel(ag_uyarisi)
            uy.setWordWrap(True)
            uy.setStyleSheet("color:#8a4b00")
            lay.addWidget(uy)
        self.yedek = QCheckBox("Çıkmadan önce veritabanını yedekle")
        self.yedek.setChecked(ayar.value("cikista_yedek", True, type=bool))
        lay.addWidget(self.yedek)
        bb = QDialogButtonBox()
        tamam = bb.addButton("Güvenli Çıkış", QDialogButtonBox.AcceptRole)
        tamam.setDefault(True)
        bb.addButton("Vazgeç", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self._ayar = ayar

    def accept(self):
        self._ayar.setValue("cikista_yedek", self.yedek.isChecked())
        super().accept()


class AnaPencere(QMainWindow):
    def __init__(self, db, ag=None):
        super().__init__()
        self.db = db
        self.ag = ag
        self.ayar = arayuz_ayarlari()
        self._cikis_hazir = False
        self._cikis_istendi = False
        self.yeniden_baslat = False
        self.tepsi = None  # sunucu bilgisayarında run.py kurar; pencere kapatılınca program tepsiye iner
        self._tepsi_bildirildi = False
        self.setStyleSheet(STIL)
        self.setWindowIcon(marka.uygulama_simgesi())
        ortak.KURUM_LOGOSU = marka.kurum_logosu(db)

        self.uretici: dict[str, Callable[[], QWidget]] = {}
        self.sayfa: dict[str, QWidget] = {}
        self._kap: dict[str, QScrollArea] = {}
        crud = lambda v: (lambda: CrudSayfasi(db, v))
        yapi = [
            ("GENEL", [("Asistan", lambda: AsistanSayfasi(db, self)), ("Ana Sayfa", lambda: AnaSayfa(db)),
                       ("Toplu Veri Girişi", lambda: TopluGirisSayfasi(db, self)),
                       ("Veri Aktarımı", lambda: AktarimSayfasi(db, self)),
                       ("e-Okul Öğrenci Eşitleme (Nakil)", lambda: EsitlemeSayfasi(db)),
                       ("e-Okul / e-Mesem / SGK Bağlantısı", lambda: BaglantiSayfasi(db, self)),
                       ("Toplu Gönderim (E-posta / WhatsApp)", lambda: TopluGonderimSayfasi(db))]),
            ("TANIMLAR", [("Öğrenciler / Çıraklar", crud(V.OGRENCILER)), ("Öğretmenler", crud(V.OGRETMENLER)),
                          ("İşletmeler", lambda: isletme_sayfasi(db)), ("Sınıflar / Şubeler", crud(V.SINIFLAR)),
                          ("Alanlar", crud(V.ALANLAR)), ("Dallar", crud(V.DALLAR)), ("Dersler", crud(V.DERSLER)),
                          ("Atölye / Laboratuvarlar", crud(V.ATOLYELER)), ("Tatil Günleri", crud(V.TATILLER))]),
            ("DERS PROGRAMI", [("Ders Dağılımı ve Atölye Yerleşimi", lambda: ProgramSayfasi(db)),
                               ("Program Araçları (Kısıt, Sürüm, Devir, Yük)", lambda: ProgramAraclariSayfasi(db))]),
            ("SINAV PLANLAMA", [("Sınav Planlama ve Görevlendirme", lambda: SinavSayfasi(db))]),
            ("İŞLETMELERDE MESLEKİ EĞİTİM", [
                ("Yerleştirme ve Sözleşmeler", lambda: yerlestirme_sayfasi(db)),
                ("Koordinatörlük", lambda: KoordinatorSayfasi(db)),
                ("Koordinatörlük Formları ve Teslim Takibi", lambda: BelgeTakipSayfasi(db)),
                ("Komisyon ve İzleme İşleri", lambda: KomisyonSayfasi(db)),
                ("SGK Sigorta İşlemleri", lambda: SgkSayfasi(db)),
                ("Öğrenci Ücreti ve Devlet Katkısı", lambda: UcretSayfasi(db)),
                ("Devamsızlık ve Değerlendirme", lambda: DevamSayfasi(db))]),
            ("PERSONEL", [("Ek Ders Puantajı", lambda: EkDersSayfasi(db))]),
            ("EVRAK", [("Belge Üretimi", lambda: BelgeSayfasi(db)), ("Evrak Kayıt Defteri", crud(V.EVRAK))]),
            ("SİSTEM", [("Ayarlar ve Mevzuat Parametreleri", lambda: AyarlarSayfasi(db, self)),
                        ("Çok Kullanıcılı Çalışma (Ağ)", self._ag_sayfasi)]),
        ]
        for _, ogeler in yapi:
            self.uretici.update(ogeler)

        merkez = QWidget()
        lay = QHBoxLayout(merkez)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.yan = YanMenu([(grup, [ad for ad, _ in ogeler]) for grup, ogeler in yapi])
        self.yan.secildi.connect(self._sec)
        self.yan.cikis_istendi.connect(self.guvenli_cikis)
        self.yan.daraldi.connect(lambda dar: self.ayar.setValue("menu_dar", dar))
        self.kurum_etiketi = self.yan.kurum_etiketi
        lay.addWidget(self.yan)
        self.yigin = QStackedWidget()
        lay.addWidget(self.yigin, 1)
        self.setCentralWidget(merkez)
        ekran = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        self.yan.dar_yap(self.ayar.value("menu_dar", ekran.width() < DAR_EKRAN, type=bool), kalici=False,
                         animasyon=False)
        son = self.ayar.value("son_sayfa", "Asistan")
        self.git(son if son in self.uretici else "Asistan")

        self._menuler()
        self.durum_ag = QPushButton()
        self.durum_ag.setFlat(True)
        self.durum_ag.clicked.connect(lambda: self.git("Çok Kullanıcılı Çalışma (Ağ)"))
        self.statusBar().addWidget(self.durum_ag)
        self.durum_konum = QLabel()
        self.statusBar().addWidget(self.durum_konum, 1)
        self.durum_kullanici = QPushButton()
        self.durum_kullanici.setFlat(True)
        self.durum_kullanici.clicked.connect(lambda: self._ayarlar_sekmesi("Kullanıcılar"))
        self.statusBar().addPermanentWidget(self.durum_kullanici)
        self.lisans_dugmesi = QPushButton()
        self.lisans_dugmesi.setFlat(True)
        self.lisans_dugmesi.clicked.connect(self.lisans_penceresi)
        self.statusBar().addPermanentWidget(self.lisans_dugmesi)
        self.lisans_guncelle()
        self.setAcceptDrops(True)

        self._yenile_zamanlayici = QTimer(self)
        self._yenile_zamanlayici.setSingleShot(True)
        self._yenile_zamanlayici.timeout.connect(self._canli_yenile)
        self._bekleyen_degisiklik = False
        if ag is not None:
            ag.degisti.connect(self._uzak_degisiklik)
            ag.durum_degisti.connect(self.ag_durumu_guncelle)
        self.ag_durumu_guncelle()
        self.kullanici_guncelle()
        self._boyutlandir()

        self._yedek_zamanlayici = QTimer(self)
        self._yedek_zamanlayici.timeout.connect(self._otomatik_yedek)
        if not db.uzak:
            self._yedek_zamanlayici.start(10 * 60 * 1000)
            QTimer.singleShot(90 * 1000, self._otomatik_yedek)
        QTimer.singleShot(20 * 1000, self._guncelleme_otomatik)

    # --- düzen ---
    def _menuler(self) -> None:
        dosya = self.menuBar().addMenu("Dosya")
        yedek = QAction("Şimdi Yedekle", self)
        yedek.triggered.connect(self._yedekle)
        dosya.addAction(yedek)
        dosya.addSeparator()
        self.a_parola = QAction("Parolamı Değiştir...", self)
        self.a_parola.triggered.connect(self._parola_degistir)
        dosya.addAction(self.a_parola)
        self.a_kullanici = QAction("Kullanıcı Değiştir (Oturumu Kapat)", self)
        self.a_kullanici.triggered.connect(self.kullanici_degistir)
        dosya.addAction(self.a_kullanici)
        dosya.addSeparator()
        cikis = QAction("Güvenli Çıkış", self)
        cikis.setShortcut(QKeySequence("Ctrl+Q"))
        cikis.triggered.connect(self.guvenli_cikis)
        dosya.addAction(cikis)
        gorunum = self.menuBar().addMenu("Görünüm")
        ara = QAction("Menüde Ara", self)
        ara.setShortcut(QKeySequence("Ctrl+K"))
        ara.triggered.connect(self.yan.ara_odakla)
        gorunum.addAction(ara)
        self.a_dar = QAction("Menüyü Daralt (Simge Şeridi)", self)
        self.a_dar.setCheckable(True)
        self.a_dar.setChecked(self.yan.dar)
        self.a_dar.setShortcut(QKeySequence("Ctrl+B"))
        self.a_dar.triggered.connect(lambda dar: self.yan.dar_yap(dar))
        self.yan.daraldi.connect(self.a_dar.setChecked)
        gorunum.addAction(self.a_dar)
        yardim = self.menuBar().addMenu("Yardım")
        kilavuz = QAction("Kullanım Kılavuzu", self)
        kilavuz.setShortcut(QKeySequence("F1"))
        kilavuz.triggered.connect(self.kilavuz_penceresi)
        yardim.addAction(kilavuz)
        yardim.addSeparator()
        denetle = QAction("Güncellemeleri Denetle...", self)
        denetle.triggered.connect(lambda: self.guncelleme_denetle())
        yardim.addAction(denetle)
        self.a_guncelleme = QAction("Açılışta Güncellemeleri Denetle", self)
        self.a_guncelleme.setCheckable(True)
        self.a_guncelleme.setChecked(guncelleme.GuncellemeAyarlari.yukle().otomatik)
        self.a_guncelleme.toggled.connect(self._guncelleme_otomatik_ayarla)
        yardim.addAction(self.a_guncelleme)
        yardim.addSeparator()
        for metin, fn in [("Lisans Bilgileri...", self.lisans_penceresi), ("Hakkında", self._hakkinda)]:
            a = QAction(metin, self)
            a.triggered.connect(fn)
            yardim.addAction(a)

    def _boyutlandir(self) -> None:
        """İlk açılışta ekrana sığdırır; sonraki açılışlarda son konum ve boyutu (ekrana sığıyorsa) kullanır."""
        ekran = (self.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        self.setMinimumSize(min(900, ekran.width()), min(560, ekran.height()))
        g = self.ayar.value("pencere")
        if g is not None and self.restoreGeometry(g):
            cerceve = self.frameGeometry()
            if (cerceve.width() <= ekran.width() and cerceve.height() <= ekran.height()
                    and ekran.contains(cerceve.center())):
                return
        if ekran.width() < 1500 or ekran.height() < 900:
            self.resize(ekran.width(), ekran.height())
            self.move(ekran.topLeft())
            self.setWindowState(Qt.WindowMaximized)
            return
        w, h = min(1440, int(ekran.width() * 0.9)), min(900, int(ekran.height() * 0.9))
        self.resize(w, h)
        self.move(ekran.center().x() - w // 2, ekran.center().y() - h // 2)

    # --- lisans ---
    def lisans_guncelle(self) -> None:
        self.lisans = lisans.durum(self.db)
        self.setWindowTitle(f"{APP_TITLE}  v{__version__}  -  {self.lisans.pencere_eki}")
        az = self.lisans.seviye == lisans.LISANSLI and self.lisans.kalan_gun is not None \
            and self.lisans.kalan_gun <= 30
        metin = self.lisans.pencere_eki + (f" (bitişe {self.lisans.kalan_gun} gün)" if az else "")
        self.lisans_dugmesi.setText(metin)
        uyari = self.lisans.seviye != lisans.LISANSLI or az
        self.lisans_dugmesi.setStyleSheet("color:#b00020; font-weight:bold" if uyari else "color:#1b5e20")
        self.kurum_guncelle()

    def kurum_guncelle(self) -> None:
        k = self.db.kurum()
        self.kurum_etiketi.setText(k["ad"] or marka.KISA_TANIM)
        ortak.KURUM_LOGOSU = marka.kurum_logosu(self.db)

    def lisans_penceresi(self) -> None:
        LisansPenceresi(self.db, parent=self).exec()
        self.lisans_guncelle()

    # --- güncelleme ---
    def _guncelleme_otomatik_ayarla(self, acik: bool) -> None:
        a = guncelleme.GuncellemeAyarlari.yukle()
        a.otomatik = acik
        a.kaydet()

    def _guncelleme_otomatik(self) -> None:
        if guncelleme.GuncellemeAyarlari.yukle().zamani_geldi():
            self.guncelleme_denetle(sessiz=True)

    def guncelleme_denetle(self, sessiz: bool = False) -> None:
        if not guncelleme.adres():
            if not sessiz:
                ortak.bilgi(self, f"Bu kurulumda güncelleme adresi tanımlı değil (sürüm {__version__}).\n"
                                  "Yeni sürümü programı dağıtan kişiden kurulum dosyası olarak isteyin; eskisinin "
                                  "üzerine kurulur, veriler ve lisans korunur.", "Güncelleme")
            return

        def bitti(yeni):
            a = guncelleme.GuncellemeAyarlari.yukle()
            a.son_denetim = datetime.now().isoformat(timespec="seconds")
            a.kaydet()
            if yeni is None:
                if not sessiz:
                    ortak.bilgi(self, f"MesKoord güncel (sürüm {__version__}).", "Güncelleme")
                return
            if sessiz and yeni.surum == a.atlanan:
                return
            self._yeni_surum(yeni)

        def hata(tb: str):
            if not sessiz:
                ortak.hata(self, "Güncelleme denetlenemedi:\n" + (tb.strip().splitlines() or [""])[-1], "Güncelleme")

        ortak.arka_planda(guncelleme.denetle, bitti, hata)

    def _yeni_surum(self, yeni: guncelleme.YeniSurum) -> None:
        kutu = QMessageBox(self)
        kutu.setWindowTitle("Yeni sürüm")
        kutu.setText(f"<b>MesKoord {yeni.surum} yayımlandı.</b> Bu bilgisayarda {__version__} kurulu.")
        notlar = yeni.notlar.strip()
        ek = ("\n\nAğda çalışıyorsanız bütün bilgisayarlar aynı sürüme geçmelidir; önce sunucu bilgisayarı "
              "güncelleyin." if self.ag is not None or self.db.uzak else "")
        kutu.setInformativeText("Kurulum eskisinin üzerine yapılır; veriler ve lisans korunur." + ek)
        if notlar:
            kutu.setDetailedText(notlar)
        kur = kutu.addButton("İndir ve Kur", QMessageBox.AcceptRole)
        atla = kutu.addButton("Bu Sürümü Atla", QMessageBox.DestructiveRole)
        kutu.addButton("Sonra", QMessageBox.RejectRole)
        kutu.exec()
        if kutu.clickedButton() == kur:
            self._guncelleme_indir(yeni)
        elif kutu.clickedButton() == atla:
            a = guncelleme.GuncellemeAyarlari.yukle()
            a.atlanan = yeni.surum
            a.kaydet()

    def _guncelleme_indir(self, yeni: guncelleme.YeniSurum) -> None:
        pd = QProgressDialog(f"MesKoord {yeni.surum} indiriliyor...", "", 0, 0, self)
        pd.setWindowTitle("Güncelleme")
        pd.setCancelButton(None)
        pd.setMinimumDuration(0)
        pd.setWindowModality(Qt.WindowModal)
        durum = [0, 0]
        zamanlayici = QTimer(pd)

        def goster():
            alinan, toplam = durum
            if toplam:
                pd.setMaximum(100)
                pd.setValue(min(100, alinan * 100 // toplam))
            pd.setLabelText(f"MesKoord {yeni.surum} indiriliyor... {alinan / 1e6:.0f} MB")

        zamanlayici.timeout.connect(goster)
        zamanlayici.start(250)
        pd.show()

        def is_():
            return guncelleme.indir(yeni, ilerleme=lambda a, t: durum.__setitem__(slice(0, 2), [a, t]))

        def bitti(yol):
            zamanlayici.stop()
            pd.close()
            if not ortak.onay(self, f"Kurulum dosyası indirildi ve doğrulandı:\n{yol}\n\nProgram kapanacak ve "
                                    "kurulum başlayacak. Devam edilsin mi?", "Güncelleme"):
                ortak.klasorde_goster(yol)
                return
            import subprocess
            subprocess.Popen([str(yol)], close_fds=True)
            self.guvenli_cikis()

        def hata(tb: str):
            zamanlayici.stop()
            pd.close()
            ortak.hata(self, "Güncelleme indirilemedi:\n" + (tb.strip().splitlines() or [""])[-1], "Güncelleme")

        ortak.arka_planda(is_, bitti, hata)

    def kilavuz_penceresi(self) -> None:
        from .kilavuz import KilavuzPenceresi
        KilavuzPenceresi(self).exec()

    # --- sayfalar ---
    def _ag_sayfasi(self) -> QWidget:
        from .sayfa_ag import AgSayfasi
        return AgSayfasi(self.db, self)

    def _sec(self, ad: str) -> None:
        if ad not in self.uretici:
            return
        if ad not in self.sayfa:
            w = self.uretici[ad]()
            self.sayfa[ad] = w
            kap = QScrollArea()
            kap.setWidgetResizable(True)
            kap.setFrameShape(QFrame.NoFrame)
            kap.setWidget(w)
            self._kap[ad] = kap
            self.yigin.addWidget(kap)
        self.yigin.setCurrentWidget(self._kap[ad])
        self.ayar.setValue("son_sayfa", ad)

    def gecerli_sayfa(self) -> QWidget | None:
        kap = self.yigin.currentWidget()
        return kap.widget() if isinstance(kap, QScrollArea) else kap

    def sayfa_adlari(self) -> list[str]:
        return list(self.uretici)

    def git(self, ad: str) -> QWidget | None:
        """Menüdeki adıyla sayfayı açar ve döndürür."""
        if ad not in self.uretici:
            return None
        self.yan.sec(ad)
        self._sec(ad)
        return self.sayfa.get(ad)

    # --- çok kullanıcılı çalışma ---
    def ag_durumu_guncelle(self) -> None:
        if self.ag is None:
            self.durum_ag.setText("● Tek bilgisayar")
            self.durum_ag.setStyleSheet("color:#666")
            self.durum_ag.setToolTip("Çok kullanıcılı çalışma için tıklayın")
            self.durum_konum.setText(f"Veri klasörü: {config.data_dir()}")
            return
        metin, iyi = self.ag.durum_metni()
        self.durum_ag.setText("● " + metin)
        self.durum_ag.setStyleSheet(f"color:{'#1b5e20' if iyi else '#b00020'}; font-weight:bold")
        self.durum_ag.setToolTip("\n".join(self.ag.kullanici_listesi()) or metin)
        self.durum_konum.setText(f"Veritabanı: {self.db.konum}")

    def _uzak_degisiklik(self, olay: dict) -> None:
        kimler = sorted({o.get("kim") or "?" for o in olay.get("olaylar", [])})
        if kimler:
            self.statusBar().showMessage(f"Güncellendi: {', '.join(kimler)} değişiklik yaptı", 6000)
        self._bekleyen_degisiklik = True
        self._yenile_zamanlayici.start(350)

    def _canli_yenile(self) -> None:
        if not self._bekleyen_degisiklik:
            return
        if QApplication.activeModalWidget() is not None or QApplication.activePopupWidget() is not None \
                or QApplication.mouseButtons() != Qt.NoButton:
            self._yenile_zamanlayici.start(1500)
            return
        self._bekleyen_degisiklik = False
        try:
            sayfayi_yenile(self.gecerli_sayfa())
        except Exception as e:  # noqa: BLE001
            self.statusBar().showMessage(f"Ekran yenilenemedi: {e}", 6000)

    # --- sürükle bırak ---
    def dragEnterEvent(self, e):
        if surukle_dosyalar(e):
            e.acceptProposedAction()

    def dropEvent(self, e):
        yollar = surukle_dosyalar(e)
        if yollar:
            e.acceptProposedAction()
            w = self.git("Veri Aktarımı")
            if w is not None:
                w.dosyalari_ekle(yollar)

    # --- kullanıcı ---
    def kullanici_guncelle(self) -> None:
        k = self.db.kimlik
        self.durum_kullanici.setVisible(k.hesapli)
        self.durum_kullanici.setText(f"Kullanıcı: {k.ad} ({k.rol_adi})")
        self.durum_kullanici.setToolTip("Hesap ve parola işlemleri için tıklayın")
        self.a_parola.setVisible(k.hesapli)
        self.a_kullanici.setVisible(k.hesapli)

    def _ayarlar_sekmesi(self, sekme: str) -> None:
        w = self.git("Ayarlar ve Mevzuat Parametreleri")
        if isinstance(w, QTabWidget):
            for i in range(w.count()):
                if w.tabText(i) == sekme:
                    w.setCurrentIndex(i)

    def _parola_degistir(self) -> None:
        from .giris import parola_degistir
        parola_degistir(self, self.db)

    def kullanici_degistir(self) -> None:
        """Programı yeniden başlatır; açılışta yeni kullanıcı adı ve parola sorulur."""
        self.yeniden_baslat = True
        if not self.guvenli_cikis():
            self.yeniden_baslat = False

    # --- yedek / çıkış ---
    def _yedekle(self) -> None:
        try:
            yol = self.db.yedekle()
        except Exception as e:  # noqa: BLE001
            ortak.hata(self, f"Yedek alınamadı:\n{e}")
            return
        if yol.exists():
            ortak.kaydedildi(self, yol)
        else:
            ortak.bilgi(self, f"Yedek sunucu bilgisayarında alındı ({yol.name}).")

    def _otomatik_yedek(self) -> None:
        from .. import yedekleme
        if self.db.uzak or not yedekleme.YedekAyarlari.yukle().zamani_geldi():
            return
        try:
            yol = self.db.yedekle()
        except Exception as e:  # noqa: BLE001
            self.statusBar().showMessage(f"Otomatik yedek alınamadı: {e}", 15000)
            return
        hata = yedekleme.YedekAyarlari.yukle().son_hata
        self.statusBar().showMessage(hata or f"Otomatik yedek alındı: {yol.name}", 15000 if hata else 6000)

    def tepsiden_ac(self) -> None:
        """Tepsiden açılınca: hesaplar açıksa kimin açtığı yeniden sorulur (sunucu bilgisayarı ortak olabilir)."""
        if self.isHidden() and self.db.kimlik.hesapli:
            from .giris import parola_degistir, yerel_giris
            onceki = self.db.kimlik
            kimlik = yerel_giris(None, self.db, "Sunucu arka planda çalışıyor. Programı açmak için giriş yapın.",
                                 iptal_metni="Vazgeç")
            if kimlik is None:
                return
            self.db.kimlik_ata(kimlik)
            if kimlik.parola_degistirmeli and not parola_degistir(None, self.db, zorunlu=True):
                self.db.kimlik_ata(onceki)
                return
            self.kullanici_guncelle()
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()

    def guvenli_cikis(self) -> bool:
        """Programı kapatır (pencere çarpısı sunucu bilgisayarında yalnızca tepsiye indirir)."""
        self._cikis_istendi = True
        try:
            return self.close()
        finally:
            self._cikis_istendi = False

    def closeEvent(self, e):
        if not self._cikis_hazir and not self._cikis_istendi and self.tepsi is not None:
            e.ignore()
            self.ayar.setValue("pencere", self.saveGeometry())
            self.hide()
            if not self._tepsi_bildirildi:
                self._tepsi_bildirildi = True
                self.tepsi.ilk_bildirim()
            return
        if self._cikis_hazir or self._guvenli_cikis():
            e.accept()
            if self.tepsi is not None:
                self.tepsi.hide()
                QTimer.singleShot(0, QApplication.quit)
        else:
            e.ignore()

    def _guvenli_cikis(self) -> bool:
        ag_uyarisi = self.ag.cikis_uyarisi() if self.ag is not None else ""
        dlg = CikisPenceresi(self, self.ayar, len(ortak._aktif_isler), ag_uyarisi)
        if dlg.exec() != QDialog.Accepted:
            return False
        if ortak._aktif_isler and not self._isleri_bekle():
            return False
        for w in self.sayfa.values():
            fn = getattr(w, "kapanirken", None)
            if callable(fn):
                try:
                    fn()
                except Exception:  # noqa: BLE001
                    pass
        if dlg.yedek.isChecked():
            try:
                self.db.yedekle()
            except Exception as ex:  # noqa: BLE001
                if QMessageBox.warning(self, "Yedek alınamadı", f"{ex}\n\nYine de çıkılsın mı?",
                                       QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
                    return False
        self.ayar.setValue("pencere", self.saveGeometry())
        self._cikis_hazir = True
        return True

    def _isleri_bekle(self) -> bool:
        ilerleme = QProgressDialog("Arka plandaki işlemlerin bitmesi bekleniyor...", "Vazgeç", 0, 0, self)
        ilerleme.setWindowTitle("Güvenli Çıkış")
        ilerleme.setMinimumDuration(0)
        ilerleme.show()
        while ortak._aktif_isler:
            QApplication.processEvents()
            if ilerleme.wasCanceled():
                return False
            time.sleep(0.05)
        ilerleme.close()
        return True

    def _hakkinda(self) -> None:
        kutu = QMessageBox(self)
        kutu.setWindowTitle("Hakkında")
        kutu.setIconPixmap(marka.logo_pixmap(110))
        kutu.setText(f"<h2 style='color:{marka.ANA}; margin-bottom:0'>{marka.URUN}</h2>"
                     f"<span style='color:{marka.VURGU_KOYU}'>{marka.SLOGAN}</span><br>Sürüm {__version__}")
        kutu.setInformativeText(
            f"<b>{marka.YAYINCI}</b> ürünüdür.<br><br>"
            "Mesleki ve teknik Anadolu liseleri ile mesleki eğitim merkezleri için ders programı, atölye "
            "yerleşimi, koordinatörlük, SGK, öğrenci ücreti/devlet katkısı, ek ders, devamsızlık ve resmî belge "
            "işlemleri. Birden çok bilgisayarda aynı anda kullanılabilir.<br><br>"
            "Hesaplamalar Ayarlar ekranındaki mevzuat parametrelerine dayanır; resmî işlem öncesinde güncel "
            "mevzuatla karşılaştırınız.<br><br>"
            f"<b>Lisans:</b> {self.lisans.pencere_eki}<br>"
            "Kullanılan açık kaynak bileşenlerin lisansları program klasöründeki UCUNCU_TARAF_LISANSLARI.txt "
            "dosyasındadır.")
        kutu.exec()
