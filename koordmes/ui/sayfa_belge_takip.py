"""Koordinatörlük formları (barkodlu) ve teslim takibi ekranı."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QLabel, QLineEdit, QPushButton, QSplitter,
                               QTabWidget, QVBoxLayout, QWidget)

from ..mevzuat import AYLAR
from ..services import belge_takip as bt, excel_io
from ..services.utils import ay_araligi, tr
from . import ortak


def _tarih_secici(d: date) -> QDateEdit:
    w = QDateEdit(QDate(d.year, d.month, d.day))
    w.setCalendarPopup(True)
    w.setDisplayFormat("dd.MM.yyyy")
    return w


def _tarih(w: QDateEdit) -> date:
    q = w.date()
    return date(q.year(), q.month(), q.day())


def _ogretmenler(cb: QComboBox, db) -> None:
    secili = cb.currentData()
    cb.blockSignals(True)
    cb.clear()
    cb.addItem("(Tüm öğretmenler)", None)
    for r in db.q("""SELECT DISTINCT o.id, o.ad || ' ' || o.soyad AS ad FROM ogretmenler o
                     WHERE o.id IN (SELECT ogretmen_id FROM koordinator_gorevleri)
                        OR o.id IN (SELECT ogretmen_id FROM belge_takibi) ORDER BY ad"""):
        cb.addItem(r["ad"], r["id"])
    cb.setCurrentIndex(max(0, cb.findData(secili)))
    cb.blockSignals(False)


def _donem(tur: str, t: date) -> str:
    return tr(t) if tur == "G" else f"{AYLAR[t.month - 1]} {t.year}"


class FormlarSekmesi(QWidget):
    BASLIKLAR = ["Form", "Tarih / Dönem", "Öğretmen", "İşletme", "Barkod"]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lbl = QLabel("Koordinatör öğretmenlerin görev günlerinden barkodlu formlar üretilir: her görev günü ve "
                     "işletme için günlük rehberlik görev formu, her işletme için aylık rehberlik raporu ve her "
                     "öğretmen için aylık görev formu. Tatil günleri ve görev başlangıç/bitiş tarihleri dikkate "
                     "alınır. Üretilen formlar 'Teslim Takibi' listesine eklenir; doldurulan form teslim edilince "
                     "barkodu okutulur.")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#555")
        lay.addWidget(lbl)
        ust = ortak.AkisDuzeni()
        ilk, son = ay_araligi(date.today().year, date.today().month)
        self.bas, self.bit = _tarih_secici(ilk), _tarih_secici(son)
        ust.addWidget(ortak.etiketli("Tarih aralığı:", self.bas))
        ust.addWidget(self.bit)
        self.turler = {}
        for k, ad in bt.FORM_TURLERI.items():
            c = QCheckBox(ad)
            c.setChecked(True)
            c.toggled.connect(lambda _: self.yenile())
            self.turler[k] = c
            ust.addWidget(c)
        self.ogretmen = QComboBox()
        self.ogretmen.currentIndexChanged.connect(lambda _: self.yenile())
        ust.addWidget(ortak.etiketli("Öğretmen:", self.ogretmen))
        for metin, fn in [("Listele", self.yenile), ("Word Formlarını Üret", self.uret),
                          ("Yazdırmadan Takibe Ekle", self.takibe_ekle)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        self.bas.dateChanged.connect(lambda _: self.yenile())
        self.bit.dateChanged.connect(lambda _: self.yenile())
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        lay.addWidget(self.view, 1)
        self.durum = QLabel()
        lay.addWidget(self.durum)
        self.liste: list[bt.Form] = []

    def showEvent(self, e):
        super().showEvent(e)
        _ogretmenler(self.ogretmen, self.db)
        self.yenile()

    def yenile(self):
        turler = [k for k, c in self.turler.items() if c.isChecked()]
        bas, bit = _tarih(self.bas), _tarih(self.bit)
        self.liste = bt.formlar(self.db, turler, bas, bit, self.ogretmen.currentData()) if bas <= bit else []
        self.model.ayarla([[bt.FORM_TURLERI[f.tur], f.donem, f.ogretmen, f.isletme, f.barkod] for f in self.liste],
                          self.liste)
        ortak.sutunlari_sigdir(self.view)
        self.durum.setText(f"{len(self.liste)} form." if self.liste else
                           "Bu aralıkta koordinatörlük görev günü yok (Koordinatörlük > Görev Dağılımı).")

    def _secilen(self) -> list[bt.Form]:
        return [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)] or self.liste

    def uret(self):
        liste = self._secilen()
        if not liste:
            ortak.bilgi(self, "Üretilecek form yok.")
            return
        yollar = bt.formlari_uret(self.db, liste)
        ortak.kaydedildi(self, yollar[0].parent, coklu=True)

    def takibe_ekle(self):
        liste = self._secilen()
        n = bt.kaydet(self.db, liste)
        ortak.bilgi(self, f"{n} form teslim takibine eklendi ({len(liste) - n} form zaten listedeydi).")


class TeslimSekmesi(QWidget):
    BASLIKLAR = ["Durum", "Form", "Tarih / Dönem", "Öğretmen", "İşletme", "Son Teslim", "Teslim", "Barkod"]
    OZET = ["Öğretmen", "Form", "Teslim", "Bekleyen", "Geciken"]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        oku = ortak.AkisDuzeni()
        self.barkod = QLineEdit()
        self.barkod.setPlaceholderText("Barkodu okutun ya da numarayı yazıp Enter'a basın")
        self.barkod.setMinimumWidth(320)
        self.barkod.returnPressed.connect(self.okut)
        oku.addWidget(ortak.etiketli("Barkod:", self.barkod))
        self.sonuc = QLabel()
        self.sonuc.setWordWrap(True)
        oku.addWidget(self.sonuc)
        oku.addStretch()
        lay.addLayout(oku)
        ust = ortak.AkisDuzeni()
        bugun = date.today()
        self.bas = _tarih_secici(date(bugun.year if bugun.month >= 9 else bugun.year - 1, 9, 1))
        self.bit = _tarih_secici(ay_araligi(bugun.year, bugun.month)[1])
        ust.addWidget(ortak.etiketli("Tarih aralığı:", self.bas))
        ust.addWidget(self.bit)
        self.tur = QComboBox()
        self.tur.addItem("(Tüm formlar)", None)
        for k, ad in bt.FORM_TURLERI.items():
            self.tur.addItem(ad, k)
        ust.addWidget(self.tur)
        self.ogretmen = QComboBox()
        ust.addWidget(ortak.etiketli("Öğretmen:", self.ogretmen))
        self.bekleyen = QCheckBox("Yalnızca teslim edilmeyenler")
        ust.addWidget(self.bekleyen)
        for w in (self.tur, self.ogretmen):
            w.currentIndexChanged.connect(lambda _: self.yenile())
        for w in (self.bas, self.bit):
            w.dateChanged.connect(lambda _: self.yenile())
        self.bekleyen.toggled.connect(lambda _: self.yenile())
        for metin, fn in [("Seçilenleri Teslim Al", self.elle_teslim), ("Teslimi Geri Al", self.geri_al),
                          ("Excel'e Aktar", self.excel)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        sp = QSplitter()
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        sp.addWidget(self.view)
        self.m_ozet = ortak.TabloModeli(self.OZET)
        self.v_ozet, _ = ortak.tablo_gorunumu(self.m_ozet)
        sp.addWidget(self.v_ozet)
        sp.setSizes([900, 380])
        lay.addWidget(sp, 1)

    def showEvent(self, e):
        super().showEvent(e)
        _ogretmenler(self.ogretmen, self.db)
        self.yenile()
        self.barkod.setFocus()

    def _liste(self) -> list[bt.TakipSatiri]:
        return bt.takip_listesi(self.db, _tarih(self.bas), _tarih(self.bit), self.tur.currentData(),
                                self.ogretmen.currentData(), self.bekleyen.isChecked())

    def yenile(self):
        liste = self._liste()
        renk = {"Bekliyor": None, "Gecikti": ortak.RENK_KRITIK}
        self.model.ayarla([[s.durum, bt.FORM_TURLERI[s.tur], _donem(s.tur, s.tarih), s.ogretmen, s.isletme,
                            tr(s.son_teslim), tr(s.teslim), s.barkod] for s in liste], [s.id for s in liste],
                          {i: renk.get(s.durum, ortak.RENK_TAMAM) for i, s in enumerate(liste)
                           if renk.get(s.durum, ortak.RENK_TAMAM) is not None})
        ortak.sutunlari_sigdir(self.view)
        self.m_ozet.ayarla(bt.ozet(liste))
        ortak.sutunlari_sigdir(self.v_ozet)

    def okut(self):
        kod = self.barkod.text().strip()
        if not kod:
            return
        s = bt.teslim_al(self.db, kod)
        self.sonuc.setText(s.mesaj)
        self.sonuc.setStyleSheet(f"color:{'#155724' if s.tamam else '#b00020'}; font-weight:bold")
        self.barkod.clear()
        self.barkod.setFocus()
        self.yenile()

    def _secili(self) -> list[int]:
        return [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)]

    def elle_teslim(self):
        ids = self._secili()
        if not ids:
            ortak.bilgi(self, "Listeden form seçin.")
            return
        n = 0
        for i in ids:
            r = self.db.q1("SELECT barkod, teslim_tarihi FROM belge_takibi WHERE id = ?", (i,))
            if r and not r["teslim_tarihi"] and bt.teslim_al(self.db, r["barkod"]).tamam:
                n += 1
        self.yenile()
        ortak.bilgi(self, f"{n} form teslim alındı.")

    def geri_al(self):
        ids = self._secili()
        if ids and ortak.onay(self, f"{len(ids)} formun teslim kaydı silinsin mi?"):
            for i in ids:
                bt.teslimi_geri_al(self.db, i)
            self.yenile()

    def excel(self):
        yol = ortak.kaydet_yolu(self, "Koordinatörlük Formları Teslim Takibi.xlsx")
        if not yol:
            return
        x = excel_io.ExcelYazici()
        x.sayfa("Formlar", self.BASLIKLAR, self.model.rows, "Koordinatörlük Formları Teslim Takibi")
        x.sayfa("Öğretmen Özeti", self.OZET, self.m_ozet.rows, "Öğretmen Bazında Özet")
        ortak.kaydedildi(self, x.kaydet(yol))


class BelgeTakipSayfasi(QTabWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.addTab(FormlarSekmesi(db), "Barkodlu Formlar")
        self.addTab(TeslimSekmesi(db), "Teslim Takibi")
