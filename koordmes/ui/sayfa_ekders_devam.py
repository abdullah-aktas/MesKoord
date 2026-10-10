"""Ek ders puantajı ve devamsızlık/değerlendirme ekranları."""
from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget

from ..mevzuat import AYLAR
from ..services import belgeler, raporlar
from ..services.utils import para
from . import ortak
from .crud import CrudSayfasi
from .varliklar import BECERI_NOTLARI, DEVAMSIZLIK, EK_DERS_KAYITLARI


class Puantaj(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        ust = QHBoxLayout()
        self.ay = ortak.AySecici()
        self.ay.degisti.connect(lambda *_: self.yenile())
        ust.addWidget(self.ay)
        b = QPushButton("Excel'e Aktar (Puantaj)")
        b.clicked.connect(self.excel)
        ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        self.bilgi = QLabel()
        self.bilgi.setWordWrap(True)
        self.bilgi.setStyleSheet("color:#555")
        lay.addWidget(self.bilgi)
        self.model = ortak.TabloModeli([])
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        lay.addWidget(self.view, 1)
        self.ozet = QLabel()
        self.ozet.setStyleSheet("font-weight:bold")
        lay.addWidget(self.ozet)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def _veri(self):
        basliklar, satirlar, self.liste = raporlar.ekders_tablosu(self.db, *self.ay.deger())
        return basliklar, satirlar

    def yenile(self):
        k = self.db.ayar("aylik_katsayi")
        self.bilgi.setText(
            f"Gündüz saat ücreti: {self.db.ayar('ek_ders_gosterge_gunduz')} x {k} = "
            f"{para(self.db.ayar('ek_ders_gosterge_gunduz') * k)} TL, gece: "
            f"{para(self.db.ayar('ek_ders_gosterge_gece') * k)} TL (brüt). Haftalık programdaki dersler ve "
            "koordinatörlük görevleri önce aylık karşılığı doldurur; kalan saatler ek derstir. Resmî tatildeki dersler "
            "ödenmez. Kesin ödeme KBS'de yapılır; bu tablo puantaj hazırlığı içindir.")
        b, s = self._veri()
        self.model.basliklar = b
        self.model.ayarla(s)
        ortak.sutunlari_sigdir(self.view, 160)
        for c in range(4, len(b) - 7):
            self.view.setColumnWidth(c, 30)
        self.ozet.setText(f"{len(s)} öğretmen — Toplam ek ders: {sum(p.toplam for p in self.liste):g} saat — "
                          f"Tahmini brüt: {para(sum(p.brut for p in self.liste))} TL")

    def excel(self):
        yil, ay = self.ay.deger()
        yol = ortak.kaydet_yolu(self, f"Ek Ders Puantajı {AYLAR[ay - 1]} {yil}.xlsx")
        if yol:
            ortak.kaydedildi(self, raporlar.ekders_puantaj(self.db, yil, ay, yol))


class EkDersSayfasi(QTabWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.addTab(Puantaj(db), "Aylık Puantaj")
        self.addTab(CrudSayfasi(db, EK_DERS_KAYITLARI), "Elle Ek Ders Kayıtları")


class DevamOzeti(QWidget):
    BASLIKLAR = raporlar.DEVAM_BASLIKLAR

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        ust = QHBoxLayout()
        for metin, fn in [("Yenile", self.yenile), ("Seçilenlere Veli Bildirimi (Word)", self.mektup),
                          ("Excel'e Aktar", self.excel)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        self.bilgi = QLabel()
        ust.addWidget(self.bilgi)
        lay.addLayout(ust)
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        lay.addWidget(self.view, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self):
        self.bilgi.setText(f"Sınırlar: özürsüz {self.db.ayar('devamsizlik_ozursuz_sinir'):g} gün, toplam "
                           f"{self.db.ayar('devamsizlik_toplam_sinir'):g} gün")
        rows, self.liste = raporlar.devam_satirlari(self.db)
        renk = {"Sınırı aştı": ortak.RENK_KRITIK, "Sınıra yakın": ortak.RENK_UYARI, "Veli bildirimi": ortak.RENK_BILGI}
        self.model.ayarla(rows, [x.ogrenci_id for x in self.liste],
                          {i: renk[x.durum] for i, x in enumerate(self.liste) if x.durum in renk})
        ortak.sutunlari_sigdir(self.view)

    def mektup(self):
        ids = [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)]
        if not ids:
            ortak.bilgi(self, "Listeden öğrenci seçiniz.")
            return
        son = None
        for i in ids:
            son = belgeler.uret(self.db, "devamsizlik_bildirimi", i)
        ortak.kaydedildi(self, son if len(ids) == 1 else son.parent, coklu=len(ids) > 1)

    def excel(self):
        yol = ortak.kaydet_yolu(self, "Devamsızlık Özeti.xlsx")
        if yol:
            ortak.kaydedildi(self, raporlar.devam_ozeti(self.db, yol))


class DevamSayfasi(QTabWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.addTab(DevamOzeti(db), "Devamsızlık Özeti")
        self.addTab(CrudSayfasi(db, DEVAMSIZLIK), "Devamsızlık Kayıtları")
        self.addTab(CrudSayfasi(db, BECERI_NOTLARI), "İşletmede Mesleki Eğitim Notları")
