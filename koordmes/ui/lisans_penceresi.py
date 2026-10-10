"""Lisans durumu, lisans yükleme ve lisans talebi pencereleri."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout)

from .. import config, lisans, marka
from . import ortak

RENK = {lisans.LISANSLI: "#1b5e20", lisans.TOLERANS: "#8a6d3b", lisans.DENEME: marka.ANA,
        lisans.KAPALI: "#b00020"}
BASLIK = {lisans.LISANSLI: "Lisanslı", lisans.TOLERANS: "Lisans süresi doldu (ek süre)",
          lisans.DENEME: "Deneme sürümü", lisans.KAPALI: "Lisans gerekli"}


def satici_metni() -> str:
    s = lisans.SATICI
    satirlar = [x for x in (s["ad"], s["telefon"] and f"Tel: {s['telefon']}",
                            s["eposta"] and f"E-posta: {s['eposta']}", s["web"]) if x]
    return "\n".join(satirlar)


class KodPenceresi(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lisans Kodunu Yapıştır")
        self.resize(560, 260)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"Size gönderilen ve <b>{lisans.KOD_ONEKI}</b> ile başlayan lisans kodunun tamamını "
                             "aşağıya yapıştırın."))
        self.metin = QPlainTextEdit()
        pano = QApplication.clipboard().text()
        if lisans.KOD_ONEKI in pano:
            self.metin.setPlainText(pano.strip())
        lay.addWidget(self.metin, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)


class TalepPenceresi(QDialog):
    ALANLAR = [("kurum_kodu", "MEB Kurum Kodu *"), ("kurum_adi", "Kurum Adı *"), ("il", "İl"), ("ilce", "İlçe"),
               ("yetkili", "Yetkili (Ad Soyad, Unvan)"), ("telefon", "Telefon"), ("eposta", "E-posta")]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Lisans Talebi")
        self.resize(620, 560)
        k = db.kurum()
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Bilgileri kontrol edin. <b>Kurum adı ve kodu lisansa kilitlenir</b> ve programın "
                             "ürettiği bütün resmî belgelerde bu ad yazar; MEBBİS'teki resmî adı yazın."))
        f = QFormLayout()
        ilk = {"kurum_kodu": k["kurum_kodu"], "kurum_adi": k["ad"], "il": k["il"], "ilce": k["ilce"],
               "yetkili": k["mudur"], "telefon": k["telefon"], "eposta": k["eposta"]}
        self.w = {}
        for a, e in self.ALANLAR:
            self.w[a] = QLineEdit(ilk.get(a) or "")
            self.w[a].textChanged.connect(self._yenile)
            f.addRow(e, self.w[a])
        lay.addLayout(f)
        lay.addWidget(QLabel("Talep metni (lisansı veren birime gönderilecek):"))
        self.metin = QPlainTextEdit()
        self.metin.setReadOnly(True)
        lay.addWidget(self.metin, 1)
        if satici_metni():
            lay.addWidget(QLabel("<b>Gönderilecek yer:</b><br>" + satici_metni().replace("\n", "<br>")))
        alt = QHBoxLayout()
        for metin, fn in [("Panoya Kopyala", self._kopyala), ("Dosyaya Kaydet...", self._kaydet)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            alt.addWidget(b)
        if lisans.SATICI["eposta"]:
            b = QPushButton("E-posta ile Gönder")
            b.clicked.connect(self._eposta)
            alt.addWidget(b)
        alt.addStretch()
        b = QPushButton("Kapat")
        b.clicked.connect(self.accept)
        alt.addWidget(b)
        lay.addLayout(alt)
        self._yenile()

    def _bilgi(self) -> dict:
        return {a: w.text().strip() for a, w in self.w.items()}

    def _yenile(self) -> None:
        self.metin.setPlainText(lisans.talep_metni(self.db, self._bilgi()))

    def _gecerli(self) -> bool:
        b = self._bilgi()
        if not b["kurum_kodu"].isdigit() or not b["kurum_adi"]:
            ortak.hata(self, "Kurum kodu (yalnızca rakam) ve kurum adı zorunludur.")
            return False
        return True

    def _kopyala(self) -> None:
        if self._gecerli():
            QApplication.clipboard().setText(self.metin.toPlainText())
            ortak.bilgi(self, "Talep metni panoya kopyalandı. E-postanıza veya yazışmanıza yapıştırabilirsiniz.")

    def _kaydet(self) -> None:
        if not self._gecerli():
            return
        varsayilan = config.output_dir() / f"{marka.URUN_ASCII}_Lisans_Talebi_{self._bilgi()['kurum_kodu']}.txt"
        yol, _ = QFileDialog.getSaveFileName(self, "Talep dosyası", str(varsayilan), "Metin (*.txt)")
        if yol:
            Path(yol).write_text(self.metin.toPlainText(), encoding="utf-8")
            ortak.kaydedildi(self, Path(yol))

    def _eposta(self) -> None:
        if self._gecerli():
            konu = f"{marka.URUN} lisans talebi - {self._bilgi()['kurum_kodu']}"
            QDesktopServices.openUrl(QUrl(f"mailto:{lisans.SATICI['eposta']}?subject={quote(konu)}"
                                          f"&body={quote(self.metin.toPlainText())}"))


class LisansPenceresi(QDialog):
    """zorunlu=True: program açılmadan önce, lisans/deneme süresi bittiğinde gösterilir."""

    def __init__(self, db, durum: lisans.Durum | None = None, zorunlu: bool = False, parent=None):
        super().__init__(parent)
        self.db = db
        self.zorunlu = zorunlu
        self.durum = durum or lisans.durum(db)
        self.setWindowTitle(f"{marka.URUN} Lisans Bilgileri")
        self.resize(660, 460)
        lay = QVBoxLayout(self)
        ust = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(marka.logo_pixmap(72))
        ust.addWidget(logo)
        self.baslik = QLabel()
        ust.addWidget(self.baslik, 1)
        lay.addLayout(ust)
        self.ayrinti = QLabel()
        self.ayrinti.setWordWrap(True)
        self.ayrinti.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.ayrinti, 1)
        aciklama = QLabel(f"{marka.URUN} kurum bazında lisanslanır: bir lisans, MEB kurum koduyla belirtilen okulun/kurumun "
                          "bütün bilgisayarlarında kullanılabilir (ağda sunucu bilgisayarın lisansı istemcilere de "
                          "geçer). Verileriniz yalnızca okulunuzun kendi bilgisayarlarında saklanır; lisans süresi "
                          "bitse de silinmez.")
        aciklama.setWordWrap(True)
        aciklama.setStyleSheet("color:#555")
        lay.addWidget(aciklama)
        if satici_metni():
            lay.addWidget(QLabel("<b>Lisans ve destek:</b> " + satici_metni().replace("\n", " · ")))
        r1 = QHBoxLayout()
        for metin, fn in [("Lisans Dosyası Yükle...", self._dosya), ("Lisans Kodunu Yapıştır...", self._kod),
                          ("Lisans Talebi Oluştur...", lambda: TalepPenceresi(self.db, self).exec())]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            r1.addWidget(b)
        lay.addLayout(r1)
        r2 = QHBoxLayout()
        if zorunlu:
            b = QPushButton("Verilerimi Yedekle")
            b.clicked.connect(self._yedekle)
            r2.addWidget(b)
            b = QPushButton("Veri Klasörünü Aç")
            b.clicked.connect(lambda: ortak.dosya_ac(config.data_dir()))
            r2.addWidget(b)
        r2.addStretch()
        self.devam = QPushButton("Programa Devam" if zorunlu else "Kapat")
        self.devam.setDefault(True)
        self.devam.clicked.connect(self.accept)
        r2.addWidget(self.devam)
        if zorunlu:
            b = QPushButton("Çıkış")
            b.clicked.connect(self.reject)
            r2.addWidget(b)
        lay.addLayout(r2)
        self._goster()

    def _goster(self) -> None:
        d = self.durum
        self.baslik.setText(f"<h2 style='color:{RENK[d.seviye]}'>{BASLIK[d.seviye]}</h2>")
        metin = d.mesaj
        if d.lisans is not None:
            metin += "\n\n" + d.lisans.ozet()
        if d.tarih_uyarisi:
            metin += "\n\nUYARI: " + d.tarih_uyarisi
        self.ayrinti.setText(metin)
        self.devam.setEnabled(d.calisir)

    def _yukle(self, kaynak) -> None:
        try:
            lis = lisans.kaydet(kaynak)
        except lisans.LisansHatasi as e:
            ortak.hata(self, str(e))
            return
        k = self.db.kurum()
        if (k["kurum_kodu"] or "").strip() not in ("", lis.kurum_kodu) and not ortak.onay(
                self, f"Bu lisans {lis.kurum_adi} ({lis.kurum_kodu}) adına. Programdaki kurum kodu "
                      f"{k['kurum_kodu']}. Kurum adı ve kodu lisanstakiyle değiştirilecek. Devam edilsin mi?"):
            (config.data_dir() / lisans.DOSYA_ADI).unlink(missing_ok=True)
            return
        lisans.kurum_uygula(self.db, lis)
        self.durum = lisans.durum(self.db)
        self._goster()
        if self.durum.seviye == lisans.LISANSLI:
            ortak.bilgi(self, f"Lisans yüklendi.\n\n{lis.ozet()}")
        else:
            ortak.hata(self, self.durum.mesaj)

    def _dosya(self) -> None:
        yol, _ = QFileDialog.getOpenFileName(self, "Lisans dosyasını seçin", str(Path.home()),
                                             f"{marka.URUN} lisansı (*.lic);;Metin (*.txt);;Tüm dosyalar (*)")
        if yol:
            self._yukle(Path(yol))

    def _kod(self) -> None:
        d = KodPenceresi(self)
        if d.exec() == QDialog.Accepted and d.metin.toPlainText().strip():
            self._yukle(d.metin.toPlainText())

    def _yedekle(self) -> None:
        yol = self.db.yedekle()
        if yol.exists():
            ortak.kaydedildi(self, yol)
        else:
            ortak.bilgi(self, f"Yedek sunucu bilgisayarında alındı ({yol.name}).")
