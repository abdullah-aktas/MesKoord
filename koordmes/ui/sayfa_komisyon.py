"""Komisyon ve izleme işleri: öğrenci seçimi (md.136), alan taraması, anketler, hizmetiçi eğitim."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QPushButton, QSpinBox, QTabWidget, QVBoxLayout,
                               QWidget)

from ..services import mesleki_egitim as me
from . import ortak
from .crud import CrudSayfasi
from .varliklar import ALAN_FK, ANKETLER, HIZMETICI_EGITIMLER, ISLETME_TALEPLERI, ISLETMELER

RENKLER = {me.KOSULSUZ: ortak.RENK_KRITIK, me.ORTALAMASIZ: ortak.RENK_UYARI, me.ONCELIKLI: ortak.RENK_BILGI,
           me.GONDERILECEK: ortak.RENK_TAMAM}


class SecimSekmesi(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.liste: list[me.Aday] = []
        lay = QVBoxLayout(self)
        lbl = QLabel("İşletmelere gönderilecek öğrenciler; alt sınıf yılsonu başarı ortalaması ve kısa süreli "
                     "uzaklaştırmadan ağır disiplin cezası almamış olma ölçütleriyle sıralanır. Şehit/gazi çocukları "
                     "ve koruma/eğitim tedbiri kararı bulunanlar sıralamaya girmeden yerleşir (Ortaöğretim Kurumları "
                     "Yönetmeliği md.136). Ortalama ve bu bilgiler Öğrenciler ekranından, Toplu Veri Girişinden veya "
                     "e-Okul listesi aktarılarak girilir.")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#555")
        lay.addWidget(lbl)
        ust = QHBoxLayout()
        ust.addWidget(QLabel("Alan:"))
        self.alan = QComboBox()
        self.alan.currentIndexChanged.connect(lambda _: self._kontenjan_oner())
        ust.addWidget(self.alan, 2)
        ust.addWidget(QLabel("Sınıf seviyesi:"))
        self.seviye = QComboBox()
        self.seviye.addItem("(Tümü)", None)
        for s in (9, 10, 11, 12):
            self.seviye.addItem(f"{s}. sınıf", s)
        ust.addWidget(self.seviye)
        ust.addWidget(QLabel("Kontenjan:"))
        self.kontenjan = QSpinBox()
        self.kontenjan.setRange(0, 9999)
        self.kontenjan.setSpecialValueText("sınırsız")
        self.kontenjan.setToolTip("Varsayılan: alanın aktif işletmelerinin kontenjan toplamı. 0 = sınırsız.")
        ust.addWidget(self.kontenjan)
        for metin, fn in [("Sırala", self.sirala), ("Excel'e Aktar", self.excel),
                          ("Komisyon Tutanağı (Word)", self.tutanak)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        lay.addLayout(ust)
        self.model = ortak.TabloModeli(me.SECIM_BASLIKLAR)
        self.view, _ = ortak.tablo_gorunumu(self.model)
        lay.addWidget(self.view, 1)
        self.durum = QLabel()
        lay.addWidget(self.durum)
        self._ilk = True

    def showEvent(self, e):
        super().showEvent(e)
        if self._ilk:
            self._ilk = False
            self.alan.blockSignals(True)
            self.alan.addItem("(Tüm alanlar)", None)
            for r in self.db.q(ALAN_FK):
                self.alan.addItem(str(r[1]), r[0])
            self.alan.blockSignals(False)
            self._kontenjan_oner()

    def _kontenjan_oner(self) -> None:
        self.kontenjan.setValue(me.alan_kontenjani(self.db, self.alan.currentData()))

    def _alan_adi(self) -> str:
        return self.alan.currentText() if self.alan.currentData() else "Tüm alanlar"

    def sirala(self) -> None:
        self.liste = me.sirala(me.adaylar(self.db, self.alan.currentData(), self.seviye.currentData()),
                               self.kontenjan.value())
        self.model.ayarla(me.secim_satirlari(self.liste), [a.ogrenci_id for a in self.liste],
                          {i: RENKLER[a.sonuc] for i, a in enumerate(self.liste) if a.sonuc in RENKLER})
        ortak.sutunlari_sigdir(self.view)
        say = {s: sum(1 for a in self.liste if a.sonuc == s) for s in
               (me.ONCELIKLI, me.GONDERILECEK, me.YEDEK, me.ORTALAMASIZ, me.KOSULSUZ)}
        self.durum.setText(f"{len(self.liste)} öğrenci — " + ", ".join(f"{k}: {v}" for k, v in say.items() if v))

    def _hazir(self) -> bool:
        if not self.liste:
            self.sirala()
        if not self.liste:
            ortak.bilgi(self, "Seçilen alanda öğrenci yok.")
            return False
        return True

    def excel(self) -> None:
        if not self._hazir():
            return
        yol = ortak.kaydet_yolu(self, f"Öğrenci Seçim Sıralaması {self._alan_adi()}.xlsx")
        if yol:
            ortak.kaydedildi(self, me.secim_excel(self.db, self.liste, self._alan_adi(), self.kontenjan.value(), yol))

    def tutanak(self) -> None:
        if self._hazir():
            ortak.kaydedildi(self, me.secim_tutanagi(self.db, self.liste, self._alan_adi(), self.kontenjan.value()))


def _rapor(fn, ad: str):
    def eylem(sayfa: CrudSayfasi, _ids) -> None:
        yol = ortak.kaydet_yolu(sayfa, f"{ad}.xlsx")
        if yol:
            ortak.kaydedildi(sayfa, fn(sayfa.db, yol))
    return eylem


def isletme_sayfasi(db) -> CrudSayfasi:
    from .sayfa_yerlestirme import _belge_uret
    return CrudSayfasi(db, replace(ISLETMELER, eylemler=[
        ("Uygunluk Tespit Tutanağı (Word)", lambda s, ids: _belge_uret(s, ids, "isletme_uygunluk")),
        ("Koordinatör Bildirim Yazısı (Word)", lambda s, ids: _belge_uret(s, ids, "koordinator_bildirimi")),
    ]))


class KomisyonSayfasi(QTabWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.secim = SecimSekmesi(db)
        self.addTab(self.secim, "Öğrenci Seçimi (md.136)")
        self.addTab(CrudSayfasi(db, replace(ISLETME_TALEPLERI, eylemler=[
            ("Alan Özeti (Excel)", _rapor(me.talep_ozeti, "Alan Taraması ve İşletme Talepleri"))])),
            "Alan Taraması / İşletme Talepleri")
        self.addTab(CrudSayfasi(db, replace(ANKETLER, eylemler=[
            ("Değerlendirme (Excel)", _rapor(me.anket_ozeti, "Mezun ve İşyeri Anketleri"))])),
            "Mezun ve İşyeri Anketleri")
        self.addTab(CrudSayfasi(db, replace(HIZMETICI_EGITIMLER, eylemler=[
            ("Program (Excel)", _rapor(me.hizmetici_programi, "Usta Öğretici Hizmetiçi Eğitim Programı"))])),
            "Usta Öğretici Hizmetiçi Eğitim")

    def secim_sekmesi(self) -> None:
        self.setCurrentWidget(self.secim)
