"""Toplu belge üretimi ekranı."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

from .. import config
from ..services import belgeler
from . import ortak

KAYNAK_SQL = {
    "yerlestirme": """SELECT y.id, o.ad || ' ' || o.soyad || ' - ' || COALESCE(i.ad, y.tur) || ' (' || COALESCE(s.ad, '') || ')'
                      FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                      LEFT JOIN isletmeler i ON i.id = y.isletme_id LEFT JOIN siniflar s ON s.id = o.sinif_id
                      WHERE y.durum = 'Aktif' ORDER BY s.ad, o.ad""",
    "ogretmen": """SELECT DISTINCT o.id, o.ad || ' ' || o.soyad FROM ogretmenler o
                   JOIN koordinator_gorevleri kg ON kg.ogretmen_id = o.id ORDER BY o.ad""",
    "ziyaret": """SELECT z.id, z.tarih || ' - ' || COALESCE(i.ad, '') || ' - ' || COALESCE(o.ad || ' ' || o.soyad, '')
                  FROM ziyaretler z LEFT JOIN isletmeler i ON i.id = z.isletme_id
                  LEFT JOIN ogretmenler o ON o.id = z.ogretmen_id ORDER BY z.tarih DESC LIMIT 500""",
    "ogrenci": """SELECT o.id, o.ad || ' ' || o.soyad || ' (' || COALESCE(s.ad, '') || ')' FROM ogrenciler o
                  LEFT JOIN siniflar s ON s.id = o.sinif_id WHERE o.aktif = 1 ORDER BY s.ad, o.ad""",
    "isletme_ay": "SELECT id, ad FROM isletmeler WHERE aktif = 1 ORDER BY ad",
    "isletme": "SELECT id, ad FROM isletmeler WHERE aktif = 1 ORDER BY ad",
    "isletme_koord": """SELECT DISTINCT i.id, i.ad FROM isletmeler i
                        JOIN koordinator_gorevleri kg ON kg.isletme_id = i.id ORDER BY i.ad""",
    "kurum": "SELECT 1, 'Okul geneli (tek belge)'",
}


class BelgeSayfasi(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lbl = QLabel("Belgeler Word şablonlarından üretilir. Şablonları kendi resmî formatınıza göre Word'de "
                     "düzenleyebilirsiniz; {{alan_adi}} biçimindeki yer tutucular otomatik doldurulur.")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        ust = QHBoxLayout()
        ust.addWidget(QLabel("Belge türü:"))
        self.tur = QComboBox()
        for k, b in belgeler.BELGE_TURLERI.items():
            if b.kaynak in KAYNAK_SQL:
                self.tur.addItem(b.etiket, k)
        self.tur.currentIndexChanged.connect(lambda _: self.doldur())
        ust.addWidget(self.tur, 1)
        self.ay = ortak.AySecici()
        ust.addWidget(self.ay)
        lay.addLayout(ust)
        self.liste = QListWidget()
        self.liste.setSelectionMode(QListWidget.ExtendedSelection)
        lay.addWidget(self.liste, 1)
        alt = ortak.AkisDuzeni()
        for metin, fn in [("Tümünü Seç", self.liste.selectAll), ("Seçilenler İçin Üret", self.uret),
                          ("Şablonu Word'de Aç", self.sablon_ac), ("Şablon Klasörü", lambda: ortak.dosya_ac(config.templates_dir())),
                          ("Şablonları Varsayılana Döndür", self.sifirla),
                          ("Çıktı Klasörü", lambda: ortak.dosya_ac(config.output_dir()))]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            alt.addWidget(b)
        lay.addLayout(alt)

    def showEvent(self, e):
        super().showEvent(e)
        self.doldur()

    def doldur(self):
        b = belgeler.BELGE_TURLERI[self.tur.currentData()]
        self.ay.setVisible(b.kaynak == "isletme_ay")
        self.liste.clear()
        for r in self.db.q(KAYNAK_SQL[b.kaynak]):
            it = QListWidgetItem(str(r[1]))
            it.setData(256, r[0])
            self.liste.addItem(it)

    def uret(self):
        ids = [it.data(256) for it in self.liste.selectedItems()]
        if not ids:
            ortak.bilgi(self, "Listeden en az bir kayıt seçiniz.")
            return
        anahtar = self.tur.currentData()
        yil, ay = self.ay.deger()
        son, hatalar = None, []
        for i in ids:
            try:
                son = belgeler.uret(self.db, anahtar, i, yil=yil, ay=ay)
            except Exception as e:
                hatalar.append(str(e))
        if hatalar:
            ortak.hata(self, "\n".join(hatalar[:10]))
        if son:
            ortak.kaydedildi(self, son if len(ids) == 1 else son.parent, coklu=len(ids) > 1)

    def sablon_ac(self):
        ortak.dosya_ac(belgeler.sablon_yolu(self.tur.currentData()))

    def sifirla(self):
        if ortak.onay(self, "Tüm şablonlar varsayılan hâline döndürülecek; yaptığınız değişiklikler kaybolur."):
            belgeler.tum_sablonlari_hazirla(yeniden=True)
            ortak.bilgi(self, "Şablonlar yenilendi.")
