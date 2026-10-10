"""Toplu gönderim: her öğretmene ve işletmeye kendi belgesini e-posta veya WhatsApp ile gönderme."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QComboBox, QFormLayout, QHeaderView, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..services import paylasim, toplu_gonderim
from ..services.paylasim import PostaAyarlari
from ..services.toplu_gonderim import TURLER, Gonderi
from . import ortak
from .paylas import PostaAyarPenceresi, dosyalari_panoya_kopyala, parola_al, parolayi_unut

SUTUNLAR = ["Gönder", "Alıcı", "E-posta", "Telefon", "Dosyalar", "Durum"]


class TopluGonderimSayfasi(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.gonderiler: list[Gonderi] = []
        self.hedef: Path | None = None
        self._wa_kuyruk: list[int] = []
        self._posta_kuyruk: list[int] = []
        lay = QVBoxLayout(self)
        bilgi = QLabel("Her öğretmene kendi ders programını veya görevlendirme yazısını, her işletmeye kendi "
                       "bildirimini ve sözleşmelerini gönderin. Belgeler kişi başına ayrı üretilir; e-posta her "
                       "alıcıya ayrı ileti olarak gider, böylece kimse başkasının adresini veya belgesini görmez. "
                       "E-posta veya telefonu eksik olanlar Öğretmenler / İşletmeler ekranından tamamlanır.")
        bilgi.setWordWrap(True)
        lay.addWidget(bilgi)

        ust = ortak.AkisDuzeni()
        self.tur = QComboBox()
        for t in TURLER.values():
            self.tur.addItem(t.etiket, t.anahtar)
        self.tur.currentIndexChanged.connect(lambda _: self._tur_degisti())
        ust.addWidget(ortak.etiketli("Gönderim:", self.tur))
        self.ay = ortak.AySecici()
        ust.addWidget(self.ay)
        self.b_hazirla = QPushButton("Belgeleri Hazırla")
        self.b_hazirla.clicked.connect(self.hazirla)
        ust.addWidget(self.b_hazirla)
        b = QPushButton("Klasörü Aç")
        b.clicked.connect(lambda: self.hedef and ortak.dosya_ac(self.hedef))
        ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)

        self.tablo = QTableWidget(0, len(SUTUNLAR))
        self.tablo.setHorizontalHeaderLabels(SUTUNLAR)
        self.tablo.verticalHeader().setVisible(False)
        h = self.tablo.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.Stretch)
        h.setSectionResizeMode(5, QHeaderView.Stretch)
        lay.addWidget(self.tablo, 1)

        f = QFormLayout()
        self.konu = QLineEdit()
        f.addRow("Konu", self.konu)
        self.metin = QPlainTextEdit()
        self.metin.setMaximumHeight(120)
        self.metin.setToolTip("{ad} alıcının adıyla, {donem} seçilen ayla, {kurum} okul adıyla değişir.")
        f.addRow("Mesaj", self.metin)
        lay.addLayout(f)

        alt = ortak.AkisDuzeni()
        self.b_smtp = QPushButton("E-posta ile Hepsine Gönder")
        self.b_smtp.setToolTip("Programdan doğrudan gönderir; her alıcıya ayrı ileti. Şifre gönderirken sorulur.")
        self.b_smtp.clicked.connect(self.smtp_gonder)
        self.b_posta = QPushButton("Sıradakini Posta Programında Aç")
        self.b_posta.setToolTip("Outlook gibi posta programında sıradaki alıcının iletisini ekli açar.")
        self.b_posta.clicked.connect(self.posta_siradaki)
        self.b_wa = QPushButton("WhatsApp: Sıradakini Aç")
        self.b_wa.setToolTip("Sıradaki alıcının belgesini panoya kopyalar ve WhatsApp sohbetini açar; Ctrl+V ile "
                             "yapıştırıp gönderin.")
        self.b_wa.clicked.connect(self.whatsapp_siradaki)
        b_ayar = QPushButton("E-posta Ayarları...")
        b_ayar.clicked.connect(lambda: PostaAyarPenceresi(self).exec())
        for b in (self.b_smtp, self.b_posta, self.b_wa, b_ayar):
            alt.addWidget(b)
        alt.addStretch()
        lay.addLayout(alt)
        self.durum = QLabel()
        self.durum.setWordWrap(True)
        lay.addWidget(self.durum)
        self._tur_degisti()
        self._dugmeler()

    # ------------------------------------------------------------------ hazırlık
    def _anahtar(self) -> str:
        return self.tur.currentData()

    def _tur_degisti(self) -> None:
        t = TURLER[self._anahtar()]
        self.ay.setVisible(t.aylik)
        self.konu.setText(t.konu)
        self.metin.setPlainText(t.metin)
        self.gonderiler = []
        self._doldur()

    def hazirla(self) -> None:
        tur = self._anahtar()
        yil, ay = self.ay.deger() if TURLER[tur].aylik else (None, None)
        self.hedef = toplu_gonderim.klasor(tur)
        hedef = self.hedef
        if tur == "ogretmen_program":
            from .sayfa_program import program_pdf

            def pdf(db, tip, kid, etiket, yol):
                QApplication.processEvents()
                return program_pdf(db, tip, kid, etiket, yol)

            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self._hazir(toplu_gonderim.hazirla(self.db, tur, hedef, pdf_uret=pdf))
            finally:
                QApplication.restoreOverrideCursor()
            return
        self.b_hazirla.setEnabled(False)
        self.durum.setText("Belgeler hazırlanıyor...")

        def is_():
            kopya = self.db.kopya()
            try:
                return toplu_gonderim.hazirla(kopya, tur, hedef, yil, ay)
            finally:
                kopya.close()

        def hata(tb: str):
            self.b_hazirla.setEnabled(True)
            ortak.hata(self, "Belgeler hazırlanamadı:\n" + (tb.strip().splitlines() or [""])[-1])

        ortak.arka_planda(is_, self._hazir, hata)

    def _hazir(self, gonderiler: list[Gonderi]) -> None:
        self.b_hazirla.setEnabled(True)
        self.gonderiler = gonderiler
        for g in gonderiler:
            if g.hata:
                g.durum = f"Belge üretilemedi: {g.hata}"
            elif not paylasim.eposta_gecerli(g.kisi.eposta) and not paylasim.whatsapp_no(g.kisi.telefon):
                g.durum = "E-posta ve telefon yok"
        self._wa_kuyruk, self._posta_kuyruk = [], []
        self._doldur()
        hazir = sum(1 for g in gonderiler if g.dosyalar)
        self.durum.setText(f"{len(gonderiler)} alıcı, {hazir} alıcının belgesi hazır. "
                           + ("" if gonderiler else "Bu gönderim için kayıt bulunamadı."))

    def _doldur(self) -> None:
        self.tablo.setRowCount(len(self.gonderiler))
        for i, g in enumerate(self.gonderiler):
            sec = QTableWidgetItem()
            sec.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            sec.setCheckState(Qt.Checked if g.dosyalar and not g.hata else Qt.Unchecked)
            self.tablo.setItem(i, 0, sec)
            for j, v in enumerate([g.kisi.ad, g.kisi.eposta, g.kisi.telefon,
                                   ", ".join(d.name for d in g.dosyalar), g.durum], 1):
                it = QTableWidgetItem(v)
                it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.tablo.setItem(i, j, it)
        self._dugmeler()

    def _dugmeler(self) -> None:
        var = bool(self.gonderiler)
        for b in (self.b_smtp, self.b_posta, self.b_wa):
            b.setEnabled(var)

    def _durum_yaz(self, i: int, metin: str, renk=None) -> None:
        self.gonderiler[i].durum = metin
        it = self.tablo.item(i, 5)
        it.setText(metin)
        if renk is not None:
            for j in range(len(SUTUNLAR)):
                self.tablo.item(i, j).setBackground(renk)

    def secili(self) -> list[int]:
        return [i for i, g in enumerate(self.gonderiler)
                if self.tablo.item(i, 0).checkState() == Qt.Checked and g.dosyalar and not g.hata]

    def _metinler(self, g: Gonderi) -> tuple[str, str]:
        yil, ay = self.ay.deger()
        return toplu_gonderim.metinler(self.db, self._anahtar(), g.kisi, yil, ay, self.konu.text(),
                                       self.metin.toPlainText())

    # ------------------------------------------------------------------ e-posta
    def smtp_gonder(self) -> None:
        satirlar = [i for i in self.secili() if paylasim.eposta_gecerli(self.gonderiler[i].kisi.eposta)]
        eksik = len(self.secili()) - len(satirlar)
        if not satirlar:
            ortak.hata(self, "Seçili alıcılardan e-posta adresi olan yok.")
            return
        ayar = PostaAyarlari.yukle()
        if not ayar.hazir:
            if not PostaAyarPenceresi(self).exec():
                return
            ayar = PostaAyarlari.yukle()
        if not ortak.onay(self, f"{len(satirlar)} alıcıya {ayar.kullanici} adresinden ayrı ayrı e-posta gönderilecek."
                                + (f"\n{eksik} seçili alıcının e-postası olmadığı için atlanacak." if eksik else "")
                                + "\nDevam edilsin mi?", "Toplu E-posta"):
            return
        parola = parola_al(self, ayar)
        if parola is None:
            return
        iletiler, kimler = [], []
        for i in satirlar:
            g = self.gonderiler[i]
            konu, metin = self._metinler(g)
            iletiler.append(paylasim.ileti(ayar, [g.kisi.eposta], konu, metin, g.dosyalar))
            kimler.append(i)
            self._durum_yaz(i, "Gönderiliyor...")
        self.setEnabled(False)

        def is_():
            return paylasim.smtp_gonder(ayar, parola, iletiler)

        def bitti(s: paylasim.GonderimSonucu):
            self.setEnabled(True)
            hatali = dict(s.hatalar)
            for i in kimler:
                adres = self.gonderiler[i].kisi.eposta
                if adres in hatali:
                    self._durum_yaz(i, f"Gönderilemedi: {hatali[adres]}", ortak.RENK_KRITIK)
                else:
                    self._durum_yaz(i, "E-posta gönderildi", ortak.RENK_TAMAM)
            self.durum.setText(f"{len(s.gonderilen)} e-posta gönderildi" +
                               (f", {len(s.hatalar)} gönderilemedi." if s.hatalar else "."))

        def hata(tb: str):
            self.setEnabled(True)
            parolayi_unut(ayar)
            for i in kimler:
                self._durum_yaz(i, "Gönderilmedi", ortak.RENK_UYARI)
            ortak.hata(self, "E-postalar gönderilemedi:\n" + (tb.strip().splitlines() or [""])[-1].split(": ", 1)[-1])

        ortak.arka_planda(is_, bitti, hata)

    def posta_siradaki(self) -> None:
        if not self._posta_kuyruk:
            self._posta_kuyruk = [i for i in self.secili() if paylasim.eposta_gecerli(self.gonderiler[i].kisi.eposta)]
            if not self._posta_kuyruk:
                ortak.hata(self, "Seçili alıcılardan e-posta adresi olan yok.")
                return
        i = self._posta_kuyruk.pop(0)
        g = self.gonderiler[i]
        konu, metin = self._metinler(g)
        self.b_posta.setEnabled(False)
        self._durum_yaz(i, "Posta programında açık...")

        def is_():
            paylasim.posta_programiyla_ac(g.dosyalar, [g.kisi.eposta], konu, metin)

        def bitti(_):
            self.b_posta.setEnabled(True)
            self._durum_yaz(i, "Posta programında açıldı", ortak.RENK_TAMAM)
            self._sira_metni(self.b_posta, self._posta_kuyruk, "Sıradakini Posta Programında Aç")

        def hata(tb: str):
            self.b_posta.setEnabled(True)
            self._posta_kuyruk.insert(0, i)
            self._durum_yaz(i, "Posta programı açılamadı", ortak.RENK_UYARI)
            ortak.hata(self, "Posta programı açılamadı: " + (tb.strip().splitlines() or [""])[-1].split(": ", 1)[-1]
                       + "\n\n'E-posta ile Hepsine Gönder' programdan doğrudan gönderir.")

        ortak.arka_planda(is_, bitti, hata)

    # ------------------------------------------------------------------ WhatsApp
    def whatsapp_siradaki(self) -> None:
        if not self._wa_kuyruk:
            self._wa_kuyruk = [i for i in self.secili() if paylasim.whatsapp_no(self.gonderiler[i].kisi.telefon)]
            if not self._wa_kuyruk:
                ortak.hata(self, "Seçili alıcılardan telefonu olan yok.")
                return
        i = self._wa_kuyruk.pop(0)
        g = self.gonderiler[i]
        _, metin = self._metinler(g)
        dosyalari_panoya_kopyala(g.dosyalar)
        uygulama, web = paylasim.whatsapp_adresleri(paylasim.whatsapp_no(g.kisi.telefon), metin)
        if not QDesktopServices.openUrl(QUrl(uygulama)):
            QDesktopServices.openUrl(QUrl(web))
        self._durum_yaz(i, "WhatsApp açıldı: Ctrl+V ile yapıştırıp gönderin", ortak.RENK_TAMAM)
        self.tablo.scrollToItem(self.tablo.item(i, 1))
        self._sira_metni(self.b_wa, self._wa_kuyruk, "WhatsApp: Sıradakini Aç")

    @staticmethod
    def _sira_metni(b: QPushButton, kuyruk: list[int], varsayilan: str) -> None:
        b.setText(f"{varsayilan} ({len(kuyruk)} kaldı)" if kuyruk else varsayilan)
