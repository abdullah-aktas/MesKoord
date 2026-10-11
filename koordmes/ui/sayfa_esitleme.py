"""e-Okul öğrenci listesi eşitleme ekranı (nakil gelen / giden öğrenciler)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QFileDialog, QLabel, QListWidget, QPushButton,
                               QSplitter, QVBoxLayout, QWidget)

from ..mevzuat import OGRENCI_STATULERI
from ..services import excel_io, ogrenci_esitleme as oe, okuyucu
from . import ortak
from .sayfa_aktarim import surukle_dosyalar

RENKLER = {"Yeni": ortak.RENK_TAMAM, "Listede yok": ortak.RENK_KRITIK, "Yeniden kayıt": ortak.RENK_BILGI,
           "Sınıf değişmiş": ortak.RENK_UYARI, "Bilgi farkı": ortak.RENK_UYARI}


class EsitlemeSayfasi(QWidget):
    BASLIKLAR = ["Durum", "Ad Soyad", "No", "T.C.", "Okulda", "e-Okul Listesinde"]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.sonuc: oe.EsitlemeSonucu | None = None
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lbl = QLabel("e-Okul'dan aldığınız güncel öğrenci listelerini (sınıf listesi, OOK08001R020 vb.; Excel, PDF, "
                     "Word) seçin ya da buraya sürükleyin. Listedeki sınıflarda okul kayıtlarıyla karşılaştırılır: "
                     "nakil gelenler eklenir, nakil gidenler pasif yapılır (açık sigortası ayrılış tarihiyle "
                     "kapatılır ve işten ayrılış bildirimi bekleyenlere düşer), sınıfı ya da bilgisi değişenler "
                     "güncellenir. Satır seçerseniz yalnızca seçilenler uygulanır.")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#555")
        lay.addWidget(lbl)
        ust = ortak.AkisDuzeni()
        b = QPushButton("Liste Dosyalarını Seç...")
        b.clicked.connect(self.dosya_sec)
        ust.addWidget(b)
        self.filtre = QComboBox()
        self.filtre.addItem("(Tüm farklar)", None)
        for t in oe.TURLER:
            self.filtre.addItem(t, t)
        self.filtre.currentIndexChanged.connect(lambda _: self.goster())
        ust.addWidget(ortak.etiketli("Göster:", self.filtre))
        self.statu = QComboBox()
        self.statu.addItem("(Dosyaya göre)", None)
        for s in OGRENCI_STATULERI:
            self.statu.addItem(s, s)
        ust.addWidget(ortak.etiketli("Yeni öğrencilerin statüsü:", self.statu))
        self.tarih = QDateEdit(QDate.currentDate())
        self.tarih.setCalendarPopup(True)
        self.tarih.setDisplayFormat("dd.MM.yyyy")
        ust.addWidget(ortak.etiketli("Ayrılış tarihi:", self.tarih))
        self.kapat = QCheckBox("Ayrılanların açık sigortasını kapat")
        self.kapat.setChecked(True)
        ust.addWidget(self.kapat)
        for metin, fn in [("Uygula", self.uygula), ("Excel'e Aktar", self.excel)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        sp = QSplitter()
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        sp.addWidget(self.view)
        self.notlar = QListWidget()
        sp.addWidget(self.notlar)
        sp.setSizes([900, 300])
        lay.addWidget(sp, 1)
        self.durum = QLabel("Dosya seçilmedi.")
        self.durum.setWordWrap(True)
        lay.addWidget(self.durum)
        self.yollar: list[str] = []

    def dragEnterEvent(self, e):
        if surukle_dosyalar(e):
            e.acceptProposedAction()

    def dropEvent(self, e):
        yollar = surukle_dosyalar(e)
        if yollar:
            self.yukle(yollar)

    def dosya_sec(self):
        yollar, _ = QFileDialog.getOpenFileNames(self, "e-Okul öğrenci listelerini seçin", str(Path.home()),
                                                 okuyucu.DOSYA_FILTRESI)
        if yollar:
            self.yukle(yollar)

    def yukle(self, yollar: list[str]):
        tablolar, hatalar = [], []
        for y in yollar:
            try:
                tablolar += okuyucu.oku(y)
            except Exception as e:
                hatalar.append(f"{Path(y).name}: {e}")
        self.yollar = list(yollar)
        self.sonuc = oe.karsilastir(self.db, tablolar)
        self.sonuc.notlar[:0] = hatalar
        self.goster()

    def yenile(self):
        if self.yollar:
            self.yukle(self.yollar)

    def _gorunen(self) -> list[oe.EsitlemeSatiri]:
        if not self.sonuc:
            return []
        t = self.filtre.currentData()
        return [s for s in self.sonuc.satirlar if t is None or s.tur == t]

    def goster(self):
        satirlar = self._gorunen()
        self.model.ayarla([[s.tur, s.ad, s.okul_no, s.tc, s.okulda, s.listede] for s in satirlar], satirlar,
                          {i: RENKLER[s.tur] for i, s in enumerate(satirlar)})
        ortak.sutunlari_sigdir(self.view, 360)
        self.notlar.clear()
        if not self.sonuc:
            return
        self.notlar.addItems(self.sonuc.notlar or ["Not yok."])
        say = self.sonuc.sayilar()
        kapsam = ", ".join(self.sonuc.kapsam) or "tüm okul"
        self.durum.setText(f"Listede {self.sonuc.liste_sayisi} öğrenci (sınıflar: {kapsam}). "
                           + (", ".join(f"{t}: {say[t]}" for t in oe.TURLER if say[t]) or "Fark yok."))

    def uygula(self):
        if not self.sonuc:
            ortak.bilgi(self, "Önce e-Okul listesini seçin.")
            return
        secili = [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)] or self._gorunen()
        if not secili:
            ortak.bilgi(self, "Uygulanacak fark yok.")
            return
        n = sum(1 for s in secili if s.tur == "Listede yok")
        if not ortak.onay(self, f"{len(secili)} değişiklik uygulansın mı?"
                          + (f"\n\n{n} öğrenci pasif yapılacak (nakil giden / kaydı silinen)." if n else "")):
            return
        q = self.tarih.date()
        u = oe.uygula(self.db, secili, date(q.year(), q.month(), q.day()), self.kapat.isChecked(),
                      self.statu.currentData())
        self.yenile()
        ortak.bilgi(self, u.metin())

    def excel(self):
        if not self.sonuc:
            return
        yol = ortak.kaydet_yolu(self, "e-Okul Öğrenci Eşitleme.xlsx")
        if yol:
            satirlar = [[s.tur, s.ad, s.okul_no, s.tc, s.okulda, s.listede] for s in self._gorunen()]
            ortak.kaydedildi(self, excel_io.tablo_yaz(yol, self.BASLIKLAR, satirlar, "e-Okul Öğrenci Eşitleme",
                                                      alt_bilgi=self.sonuc.notlar))
