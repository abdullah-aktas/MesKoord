"""Çıktıyı e-posta veya WhatsApp ile paylaşma penceresi ve posta ayarları."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog,
                               QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton,
                               QSpinBox, QVBoxLayout, QWidget)

from ..services import paylasim
from ..services.paylasim import PostaAyarlari
from . import ortak

YOL_SMTP, YOL_PROGRAM, YOL_WEB = "smtp", "program", "web"
_parolalar: dict[tuple[str, str], str] = {}  # yalnızca program açıkken bellekte; diske yazılmaz


def db_bul(w) -> object | None:
    while w is not None:
        db = getattr(w, "db", None)
        if db is not None:
            return db
        w = w.parentWidget() if isinstance(w, QWidget) else None
    return None


def dosyalari_panoya_kopyala(dosyalar: list[Path]) -> None:
    m = QMimeData()
    m.setUrls([QUrl.fromLocalFile(str(Path(d).resolve())) for d in dosyalar])
    QGuiApplication.clipboard().setMimeData(m)


def parola_al(parent, ayar: PostaAyarlari, yeniden: bool = False) -> str | None:
    anahtar = (ayar.sunucu, ayar.kullanici)
    if anahtar in _parolalar and not yeniden:
        return _parolalar[anahtar]
    p, ok = QInputDialog.getText(parent, "E-posta şifresi",
                                 f"{ayar.kullanici} şifresi\n(Gmail'de 'uygulama şifresi'). Program kapanınca "
                                 "unutulur, diske yazılmaz.", QLineEdit.Password)
    if not ok or not p:
        return None
    _parolalar[anahtar] = p
    return p


def parolayi_unut(ayar: PostaAyarlari) -> None:
    _parolalar.pop((ayar.sunucu, ayar.kullanici), None)


def klasordeki_dosyalar(yol: Path) -> tuple[list[Path], set[Path]]:
    """Klasördeki dosyalar (yeniden eskiye) ve son kayıtla birlikte üretilmiş olanlar (en yeniden 5 dk içinde)."""
    dosyalar = sorted((p for p in yol.iterdir() if p.is_file() and not p.name.startswith(("~$", "."))),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    if not dosyalar:
        return [], set()
    son = dosyalar[0].stat().st_mtime
    return dosyalar, {p for p in dosyalar if son - p.stat().st_mtime <= 300}


class PostaAyarPenceresi(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("E-posta Gönderim Ayarları")
        self.ayar = PostaAyarlari.yukle()
        lay = QVBoxLayout(self)
        bilgi = QLabel("Programdan doğrudan e-posta göndermek için posta hesabınızın sunucu bilgilerini girin. "
                       "Şifre burada saklanmaz; gönderirken sorulur ve program kapanınca unutulur. Gmail'de "
                       "Google hesabı > Güvenlik > 'Uygulama şifreleri' bölümünde üretilen şifre kullanılır.")
        bilgi.setWordWrap(True)
        lay.addWidget(bilgi)
        f = QFormLayout()
        self.hazir = QComboBox()
        self.hazir.addItem("Seçin...")
        self.hazir.addItems(list(paylasim.HAZIR_SUNUCULAR))
        self.hazir.currentTextChanged.connect(self._hazir_secildi)
        f.addRow("Hazır ayar", self.hazir)
        self.sunucu = QLineEdit(self.ayar.sunucu)
        f.addRow("SMTP sunucusu", self.sunucu)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(self.ayar.port or 587))
        f.addRow("Port", self.port)
        self.guvenlik = QComboBox()
        self.guvenlik.addItems(["STARTTLS", "SSL"])
        self.guvenlik.setCurrentText(self.ayar.guvenlik or "STARTTLS")
        f.addRow("Güvenlik", self.guvenlik)
        self.kullanici = QLineEdit(self.ayar.kullanici)
        self.kullanici.setPlaceholderText("ornek@gmail.com")
        f.addRow("Gönderen e-posta", self.kullanici)
        self.gonderen = QLineEdit(self.ayar.gonderen_ad)
        self.gonderen.setPlaceholderText("Okul adı veya adınız")
        f.addRow("Görünen ad", self.gonderen)
        lay.addLayout(f)
        self.durum = QLabel()
        self.durum.setWordWrap(True)
        lay.addWidget(self.durum)
        alt = QHBoxLayout()
        dene = QPushButton("Kendime Deneme İletisi Gönder")
        dene.clicked.connect(self._dene)
        alt.addWidget(dene)
        alt.addStretch()
        kutu = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        kutu.accepted.connect(self._kaydet)
        kutu.rejected.connect(self.reject)
        alt.addWidget(kutu)
        lay.addLayout(alt)

    def _hazir_secildi(self, ad: str) -> None:
        if ad in paylasim.HAZIR_SUNUCULAR:
            s, p, g = paylasim.HAZIR_SUNUCULAR[ad]
            self.sunucu.setText(s)
            self.port.setValue(p)
            self.guvenlik.setCurrentText(g)

    def _oku(self) -> PostaAyarlari:
        return PostaAyarlari(self.sunucu.text().strip(), self.port.value(), self.guvenlik.currentText(),
                             self.kullanici.text().strip(), self.gonderen.text().strip())

    def _kaydet(self) -> None:
        a = self._oku()
        if not a.hazir:
            ortak.hata(self, "Sunucu ve geçerli bir gönderen e-posta adresi girin.")
            return
        a.kaydet()
        self.ayar = a
        self.accept()

    def _dene(self) -> None:
        a = self._oku()
        if not a.hazir:
            ortak.hata(self, "Sunucu ve geçerli bir gönderen e-posta adresi girin.")
            return
        p = parola_al(self, a, yeniden=True)
        if p is None:
            return
        self.durum.setText("Deneme iletisi gönderiliyor...")
        self.setEnabled(False)

        def is_():
            return paylasim.smtp_gonder(a, p, [paylasim.ileti(a, [a.kullanici], "MesKoord deneme iletisi",
                                                              "Bu ileti MesKoord e-posta ayarını denemek için "
                                                              "gönderildi.", [])])

        def bitti(_s):
            self.setEnabled(True)
            self.durum.setText(f"<b style='color:#1b5e20'>Gönderildi.</b> {a.kullanici} gelen kutusuna bakın.")

        def hata(tb: str):
            self.setEnabled(True)
            parolayi_unut(a)
            self.durum.setText(f"<b style='color:#b00020'>Gönderilemedi:</b> {_son_satir(tb)}")

        ortak.arka_planda(is_, bitti, hata)


def _son_satir(tb: str) -> str:
    satir = tb.strip().splitlines()[-1] if tb.strip() else "bilinmeyen hata"
    return satir.split(": ", 1)[-1] if "PaylasimHatasi" in satir else satir


class PaylasPenceresi(QDialog):
    def __init__(self, parent, dosyalar: list[Path], db=None, secili: set[Path] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Paylaş: e-posta veya WhatsApp")
        self.resize(760, 640)
        self.db = db if db is not None else db_bul(parent)
        self._wa_kuyruk: list[str] = []
        lay = QVBoxLayout(self)

        lay.addWidget(QLabel("<b>Gönderilecek dosyalar</b>"))
        self.dosyalar = QListWidget()
        self.dosyalar.setMaximumHeight(110)
        for d in dosyalar:
            it = QListWidgetItem(d.name)
            it.setData(Qt.UserRole, str(d))
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if secili is None or d in secili else Qt.Unchecked)
            self.dosyalar.addItem(it)
        lay.addWidget(self.dosyalar)

        ust = QHBoxLayout()
        ust.addWidget(QLabel("<b>Alıcılar</b>"))
        self.rol = QComboBox()
        self.rol.addItems(["Hepsi", "Öğretmen", "İşletme", "Usta öğretici", "Veli", "Öğrenci"])
        self.ara = QLineEdit()
        self.ara.setPlaceholderText("Ad, işletme veya sınıf ara")
        ust.addWidget(self.rol)
        ust.addWidget(self.ara, 1)
        lay.addLayout(ust)
        self.kisi_listesi = QListWidget()
        self.kisiler = paylasim.kisiler(self.db) if self.db is not None else []
        for k in self.kisiler:
            it = QListWidgetItem(k.etiket)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.kisi_listesi.addItem(it)
        lay.addWidget(self.kisi_listesi, 1)
        self.rol.currentTextChanged.connect(lambda _: self._suz())
        self.ara.textChanged.connect(lambda _: self._suz())

        f = QFormLayout()
        self.diger = QLineEdit()
        self.diger.setPlaceholderText("Listede olmayan e-posta adresleri veya telefonlar, virgülle")
        f.addRow("Diğer alıcılar", self.diger)
        konu, metin = paylasim.varsayilan_metin(self.db, dosyalar or [Path("belge")])
        self.konu = QLineEdit(konu)
        f.addRow("Konu", self.konu)
        self.metin = QPlainTextEdit(metin)
        self.metin.setMaximumHeight(110)
        f.addRow("Mesaj", self.metin)
        self.eposta_yolu = QComboBox()
        self._yollari_doldur()
        f.addRow("E-posta yolu", self.eposta_yolu)
        lay.addLayout(f)

        self.durum = QLabel("WhatsApp'ta grup seçecekseniz alıcı işaretlemeden 'WhatsApp ile Gönder'e basın, "
                            "açılan WhatsApp'ta grubu seçip Ctrl+V ile yapıştırın.")
        self.durum.setWordWrap(True)
        self.durum.setStyleSheet("color:#555")
        lay.addWidget(self.durum)

        alt = QHBoxLayout()
        self.b_eposta = QPushButton("E-posta ile Gönder")
        self.b_eposta.clicked.connect(self.eposta)
        self.b_wa = QPushButton("WhatsApp ile Gönder")
        self.b_wa.clicked.connect(self.whatsapp)
        b_ayar = QPushButton("E-posta Ayarları...")
        b_ayar.clicked.connect(self._ayarlar)
        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.accept)
        for b in (self.b_eposta, self.b_wa, b_ayar):
            alt.addWidget(b)
        alt.addStretch()
        alt.addWidget(kapat)
        lay.addLayout(alt)

    # ------------------------------------------------------------------ yardımcılar
    def _yollari_doldur(self) -> None:
        self.eposta_yolu.clear()
        ayar = PostaAyarlari.yukle()
        program = paylasim.varsayilan_posta_programi()
        if ayar.hazir:
            self.eposta_yolu.addItem(f"Programdan doğrudan gönder ({ayar.kullanici})", YOL_SMTP)
        if program:
            self.eposta_yolu.addItem(f"Posta programında aç ({program})", YOL_PROGRAM)
        self.eposta_yolu.addItem("Tarayıcıdaki posta (Gmail, Outlook.com...)", YOL_WEB)
        if not ayar.hazir:
            self.eposta_yolu.addItem("Programdan doğrudan gönder (önce ayar yapılır)", YOL_SMTP)

    def _suz(self) -> None:
        rol = self.rol.currentText()
        ara = paylasim_norm(self.ara.text())
        for i, k in enumerate(self.kisiler):
            gorunur = (rol == "Hepsi" or k.rol == rol) and (not ara or ara in paylasim_norm(k.etiket))
            self.kisi_listesi.item(i).setHidden(not gorunur)

    def secili_dosyalar(self) -> list[Path]:
        return [Path(self.dosyalar.item(i).data(Qt.UserRole)) for i in range(self.dosyalar.count())
                if self.dosyalar.item(i).checkState() == Qt.Checked]

    def secili_kisiler(self) -> list[paylasim.Kisi]:
        return [k for i, k in enumerate(self.kisiler) if self.kisi_listesi.item(i).checkState() == Qt.Checked]

    def _diger(self) -> list[str]:
        return [x.strip() for x in self.diger.text().replace(";", ",").split(",") if x.strip()]

    def eposta_alicilari(self) -> list[str]:
        out = [k.eposta for k in self.secili_kisiler() if paylasim.eposta_gecerli(k.eposta)]
        out += [x for x in self._diger() if paylasim.eposta_gecerli(x)]
        return list(dict.fromkeys(out))

    def whatsapp_numaralari(self) -> list[str]:
        out = [paylasim.whatsapp_no(k.telefon) for k in self.secili_kisiler()]
        out += [paylasim.whatsapp_no(x) for x in self._diger() if not paylasim.eposta_gecerli(x)]
        return list(dict.fromkeys(n for n in out if n))

    def _yaz(self, metin: str, renk: str = "#1b5e20") -> None:
        self.durum.setStyleSheet(f"color:{renk}")
        self.durum.setText(metin)

    def _ayarlar(self) -> None:
        if PostaAyarPenceresi(self).exec():
            self._yollari_doldur()

    # ------------------------------------------------------------------ e-posta
    def eposta(self) -> None:
        dosyalar = self.secili_dosyalar()
        if not dosyalar:
            ortak.hata(self, "Gönderilecek en az bir dosya işaretleyin.")
            return
        if paylasim.toplam_mb(dosyalar) > paylasim.BUYUK_EK_MB and not ortak.onay(
                self, f"Ekler {paylasim.toplam_mb(dosyalar):.0f} MB. Çoğu posta sunucusu 20-25 MB üstünü kabul "
                      "etmez. Yine de denensin mi?"):
            return
        alicilar = self.eposta_alicilari()
        yol = self.eposta_yolu.currentData()
        konu, metin = self.konu.text().strip(), self.metin.toPlainText()
        if yol == YOL_SMTP:
            self._smtp(dosyalar, alicilar, konu, metin)
        elif yol == YOL_PROGRAM:
            self._posta_programi(dosyalar, alicilar, konu, metin)
        else:
            self._web(dosyalar, alicilar, konu, metin)

    def _smtp(self, dosyalar, alicilar, konu, metin) -> None:
        ayar = PostaAyarlari.yukle()
        if not ayar.hazir:
            if not PostaAyarPenceresi(self).exec():
                return
            self._yollari_doldur()
            ayar = PostaAyarlari.yukle()
        if not alicilar:
            ortak.hata(self, "E-posta adresi olan en az bir alıcı seçin veya 'Diğer alıcılar'a adres yazın.")
            return
        parola = parola_al(self, ayar)
        if parola is None:
            return
        self.setEnabled(False)
        self._yaz(f"{len(alicilar)} alıcıya gönderiliyor...", "#555")

        def is_():
            return paylasim.smtp_gonder(ayar, parola, [paylasim.ileti(ayar, [a], konu, metin, dosyalar)
                                                       for a in alicilar])

        def bitti(s: paylasim.GonderimSonucu):
            self.setEnabled(True)
            if s.hatalar:
                self._yaz(f"{len(s.gonderilen)} alıcıya gönderildi. Gönderilemeyen: "
                          + "; ".join(f"{a} ({h})" for a, h in s.hatalar), "#b00020")
            else:
                self._yaz(f"Gönderildi: {', '.join(s.gonderilen)}")

        def hata(tb: str):
            self.setEnabled(True)
            parolayi_unut(ayar)
            self._yaz(f"Gönderilemedi: {_son_satir(tb)}", "#b00020")

        ortak.arka_planda(is_, bitti, hata)

    def _posta_programi(self, dosyalar, alicilar, konu, metin) -> None:
        self._yaz("Posta programında ileti açılıyor. Gönder düğmesine siz basın.", "#555")

        def is_():
            paylasim.posta_programiyla_ac(dosyalar, alicilar, konu, metin)

        def bitti(_):
            self._yaz("İleti posta programında açıldı.")

        def hata(tb: str):
            self._yaz(f"Posta programı açılamadı ({_son_satir(tb)}). Tarayıcıdaki posta açılıyor.", "#8a6d3b")
            self._web(dosyalar, alicilar, konu, metin)

        ortak.arka_planda(is_, bitti, hata)

    def _web(self, dosyalar, alicilar, konu, metin) -> None:
        dosyalari_panoya_kopyala(dosyalar)
        if not QDesktopServices.openUrl(QUrl(paylasim.mailto_adresi(alicilar, konu, metin))):
            QDesktopServices.openUrl(QUrl(paylasim.gmail_adresi(alicilar, konu, metin)))
        ortak.klasorde_goster(dosyalar[0])
        self._yaz("Posta sayfası açıldı ve dosyalar panoya kopyalandı. İletiye Ctrl+V ile yapıştırın ya da açılan "
                  "klasörden sürükleyin.")

    # ------------------------------------------------------------------ WhatsApp
    def whatsapp(self) -> None:
        dosyalar = self.secili_dosyalar()
        if not dosyalar:
            ortak.hata(self, "Gönderilecek en az bir dosya işaretleyin.")
            return
        if not self._wa_kuyruk:
            self._wa_kuyruk = self.whatsapp_numaralari() or [""]
            self._wa_toplam = len(self._wa_kuyruk)
        no = self._wa_kuyruk.pop(0)
        dosyalari_panoya_kopyala(dosyalar)
        uygulama, web = paylasim.whatsapp_adresleri(no, self.metin.toPlainText().strip())
        if not QDesktopServices.openUrl(QUrl(uygulama)):
            QDesktopServices.openUrl(QUrl(web))
        sira = self._wa_toplam - len(self._wa_kuyruk)
        kime = f"+{no}" if no else "seçeceğiniz kişi veya grup"
        self._yaz(f"WhatsApp açıldı ({kime}). Dosya panoda: sohbete tıklayıp Ctrl+V ile yapıştırın ve gönderin."
                  + (f" Sonra sıradaki alıcı için yeniden basın ({sira}/{self._wa_toplam})." if self._wa_kuyruk else ""))
        self.b_wa.setText(f"WhatsApp: Sıradaki ({sira + 1}/{self._wa_toplam})" if self._wa_kuyruk
                          else "WhatsApp ile Gönder")


def paylasim_norm(s: str) -> str:
    from ..services.aktarim import norm
    return norm(s)


def paylas(parent, yol: Path | str, db=None) -> None:
    yol = Path(yol)
    if yol.is_dir():
        dosyalar, secili = klasordeki_dosyalar(yol)
    else:
        dosyalar, secili = [yol], {yol}
    if not dosyalar:
        ortak.hata(parent, "Paylaşılacak dosya bulunamadı.")
        return
    PaylasPenceresi(parent, dosyalar, db, secili).exec()
