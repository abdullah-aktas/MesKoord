"""Asistan ekranı: Türkçe komutlar, gündem, süreç adımları, veri denetimi ve dosya sürükle-bırak."""
from __future__ import annotations

import html
import re
from datetime import date
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QApplication, QComboBox, QCompleter, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
                               QTextBrowser, QVBoxLayout, QWidget)

from .. import marka
from ..services import aktarim, asistan, denetim, okuyucu, surecler
from ..services.aktarim import TANIMLAR
from ..services.asistan import Yanit, h
from . import eylem, ortak
from .sayfa_aktarim import surukle_dosyalar

HIZLI = [("Bugün", "bugün ne yapmalıyım"), ("Denetim", "denetim"), ("Aylık kapanış", "geçen ayın kapanışını hazırla"),
         ("SGK", "sgk listesi"), ("Ücret", "ücret hesapla"), ("Ek ders", "ek ders puantajı"),
         ("Devamsızlık", "devamsızlık"), ("Yardım", "yardım")]
_LINK = re.compile(r"href=(['\"])(komut|git|kart|eylem|file|klasor|aktar):(.*?)\1")
SEVIYE_RENGI = {"Kritik": ortak.RENK_KRITIK, "Uyarı": ortak.RENK_UYARI, "Bilgi": ortak.RENK_BILGI}
DURUM_RENGI = {True: ortak.RENK_TAMAM, False: ortak.RENK_UYARI, None: ortak.RENK_BILGI}


class SurecPaneli(QWidget):
    def __init__(self, sayfa: "AsistanSayfasi"):
        super().__init__()
        self.sayfa = sayfa
        lay = QVBoxLayout(self)
        ust = QHBoxLayout()
        self.surec = QComboBox()
        for k, s in surecler.SURECLER.items():
            self.surec.addItem(s.baslik, k)
        self.surec.setCurrentIndex(max(0, self.surec.findData("aylik")))
        self.surec.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.surec.setMinimumContentsLength(14)
        ust.addWidget(self.surec, 1)
        self.ay = ortak.AySecici()
        b = date.today()
        self.ay.ayarla(*(surecler.onceki_ay(b) if b.day <= 15 else (b.year, b.month)))
        ust.addWidget(self.ay)
        lay.addLayout(ust)
        self.aciklama = QLabel()
        self.aciklama.setWordWrap(True)
        self.aciklama.setStyleSheet("color:#555")
        lay.addWidget(self.aciklama)
        self.tablo = QTableWidget(0, 3)
        self.tablo.setHorizontalHeaderLabels(["", "Adım", "Durum"])
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setSelectionBehavior(QTableWidget.SelectRows)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.tablo.horizontalHeader().setStretchLastSection(True)
        self.tablo.setColumnWidth(1, 230)
        self.tablo.setWordWrap(True)
        self.tablo.doubleClicked.connect(lambda _: self.calistir())
        lay.addWidget(self.tablo, 1)
        alt = ortak.AkisDuzeni()
        for metin, fn in [("Seçili Adımı Çalıştır", self.calistir), ("Yenile", self.yenile),
                          ("Aylık Kapanışı Hazırla", self.kapanis)]:
            btn = QPushButton(metin)
            btn.clicked.connect(fn)
            alt.addWidget(btn)
        lay.addLayout(alt)
        self.surec.currentIndexChanged.connect(lambda _: self.yenile())
        self.ay.degisti.connect(lambda *_: self.yenile())
        self.adimlar: list[surecler.AdimDurumu] = []

    def yenile(self):
        k = self.surec.currentData()
        self.ay.setVisible(k == "aylik")
        sur = surecler.SURECLER[k]
        yil, ay = self.ay.deger()
        self.adimlar = surecler.durumlar(self.sayfa.db, k, yil, ay)
        tamam = sum(1 for d in self.adimlar if d.durum is True)
        olculen = sum(1 for d in self.adimlar if d.durum is not None)
        self.aciklama.setText(f"{sur.aciklama}  —  {tamam}/{olculen} adım tamam. Çift tıklayarak adımı çalıştırın.")
        self.tablo.setRowCount(len(self.adimlar))
        for r, d in enumerate(self.adimlar):
            ogeler = [QTableWidgetItem(asistan.DURUM_ISARETI[d.durum]), QTableWidgetItem(d.adim.baslik),
                      QTableWidgetItem(d.detay + ("" if d.adim.eylem else "  (elle yapılır)"))]
            for c, it in enumerate(ogeler):
                it.setBackground(QBrush(DURUM_RENGI[d.durum]))
                it.setToolTip(d.detay)
                self.tablo.setItem(r, c, it)
        self.tablo.resizeRowsToContents()

    def calistir(self):
        r = self.tablo.currentRow()
        if not 0 <= r < len(self.adimlar):
            ortak.bilgi(self, "Listeden bir adım seçin.")
            return
        a = self.adimlar[r].adim
        if not a.eylem:
            ortak.bilgi(self, f"“{a.baslik}” adımı elle yapılır: {self.adimlar[r].detay}")
            return
        yil, ay = self.ay.deger()
        self.sayfa.eylem_calistir(a.eylem, yil=yil, ay=ay)

    def kapanis(self):
        yil, ay = self.ay.deger()
        self.sayfa.eylem_calistir("aylik_kapanis", yil=yil, ay=ay)


class DenetimPaneli(QWidget):
    def __init__(self, sayfa: "AsistanSayfasi"):
        super().__init__()
        self.sayfa = sayfa
        self.bulgular: list[denetim.Bulgu] = []
        lay = QVBoxLayout(self)
        ust = QHBoxLayout()
        btn = QPushButton("Verileri Denetle")
        btn.clicked.connect(self.yenile)
        ust.addWidget(btn)
        self.ozet = QLabel("Kayıtlardaki eksik, hatalı ve mevzuata aykırı durumlar listelenir.")
        self.ozet.setWordWrap(True)
        ust.addWidget(self.ozet, 1)
        lay.addLayout(ust)
        self.tablo = QTableWidget(0, 3)
        self.tablo.setHorizontalHeaderLabels(["Önem", "Konu", "Bulgu"])
        self.tablo.verticalHeader().setVisible(False)
        self.tablo.setSelectionBehavior(QTableWidget.SelectRows)
        self.tablo.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tablo.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tablo.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tablo.horizontalHeader().setStretchLastSection(True)
        self.tablo.setWordWrap(True)
        self.tablo.doubleClicked.connect(self._git)
        lay.addWidget(self.tablo, 1)
        lay.addWidget(QLabel("Çift tıklayınca ilgili ekran açılır."))
        self.yapildi = False

    def yenile(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.bulgular = denetim.denetle(self.sayfa.db)
        finally:
            QApplication.restoreOverrideCursor()
        self.yapildi = True
        self.ozet.setText(denetim.ozet(self.bulgular) if self.bulgular else "Sorun bulunamadı.")
        self.tablo.setRowCount(len(self.bulgular))
        for r, b in enumerate(self.bulgular):
            ogeler = [QTableWidgetItem(b.seviye), QTableWidgetItem(b.kategori), QTableWidgetItem(b.metin)]
            for c, it in enumerate(ogeler):
                it.setBackground(QBrush(SEVIYE_RENGI.get(b.seviye, QColor("white"))))
                it.setToolTip(b.metin)
                self.tablo.setItem(r, c, it)
        self.tablo.resizeRowsToContents()

    def _git(self, idx):
        if 0 <= idx.row() < len(self.bulgular) and self.bulgular[idx.row()].git:
            self.sayfa.git(self.bulgular[idx.row()].git)


class AsistanSayfasi(QWidget):
    def __init__(self, db, pencere=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.pencere = pencere
        self._linkler: list[tuple[str, str, dict]] = []
        self._bekleyen: list[str] = []
        self.setAcceptDrops(True)

        lay = QHBoxLayout(self)
        bol = QSplitter(Qt.Horizontal)
        sol = QWidget()
        sl = QVBoxLayout(sol)
        sl.setContentsMargins(0, 0, 0, 0)
        baslik = QLabel(f"<span style='font-size:14pt; font-weight:bold; color:{marka.ANA}'>{marka.URUN} Asistan</span>"
                        "<br><span style='color:#555'>Ne yapmak istediğinizi yazın, aşağıdaki kısayolları kullanın "
                        "veya Excel/Word/PDF dosyalarını bu pencereye sürükleyin.</span>")
        baslik.setWordWrap(True)
        sl.addWidget(baslik)
        self.log = QTextBrowser()
        self.log.setOpenLinks(False)
        self.log.setAcceptDrops(False)
        self.log.anchorClicked.connect(self._link)
        self.log.setStyleSheet("QTextBrowser { background: #ffffff; border: 1px solid #c9d3e3; }")
        sl.addWidget(self.log, 1)
        hizli = ortak.AkisDuzeni()
        for etiket, komut in HIZLI:
            b = QPushButton(etiket)
            b.clicked.connect(lambda _=False, k=komut: self.gonder(k))
            hizli.addWidget(b)
        hizli.addStretch(1)
        sl.addLayout(hizli)
        giris = QHBoxLayout()
        self.girdi = QLineEdit()
        self.girdi.setAcceptDrops(False)
        self.girdi.setPlaceholderText("Örn: ekim sgk listesi · geçen ayın kapanışını hazırla · 12-A · Ahmet Yılmaz")
        tamam = QCompleter(asistan.ORNEKLER, self)
        tamam.setCaseSensitivity(Qt.CaseInsensitive)
        tamam.setFilterMode(Qt.MatchContains)
        self.girdi.setCompleter(tamam)
        self.girdi.returnPressed.connect(lambda: self.gonder(self.girdi.text()))
        giris.addWidget(self.girdi, 1)
        for metin, fn in [("Gönder", lambda: self.gonder(self.girdi.text())), ("Dosya Ekle...", self.dosya_sec),
                          ("Temizle", self.log.clear)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            giris.addWidget(b)
        sl.addLayout(giris)
        bol.addWidget(sol)

        self.sekmeler = QTabWidget()
        self.surec = SurecPaneli(self)
        self.denetim = DenetimPaneli(self)
        self.sekmeler.addTab(self.surec, "Süreçler")
        self.sekmeler.addTab(self.denetim, "Veri Denetimi")
        self.sekmeler.currentChanged.connect(self._sekme)
        bol.addWidget(self.sekmeler)
        bol.setStretchFactor(0, 3)
        bol.setStretchFactor(1, 2)
        bol.setSizes([700, 480])
        lay.addWidget(bol)
        self._ilk = True

    def showEvent(self, e):
        super().showEvent(e)
        if self._ilk:
            self._ilk = False
            QTimer.singleShot(0, self._karsila)
        else:
            self.surec.yenile()

    def _karsila(self):
        self.surec.yenile()
        self.yanit(asistan.gundem(self.db, date.today()))
        self._yaz("Yapabileceklerimi görmek için <a href='komut:yardım'>yardım</a> yazın.")

    def _sekme(self, i: int):
        if self.sekmeler.widget(i) is self.denetim and not self.denetim.yapildi:
            self.denetim.yenile()

    # ------------------------------------------------------------------ sohbet

    def _baglantilar(self, s: str, kw: dict | None = None) -> str:
        def degistir(m):
            self._linkler.append((m.group(2), html.unescape(m.group(3)), kw or {}))
            return f"href='act:{len(self._linkler) - 1}'"
        return _LINK.sub(degistir, s)

    def _yaz(self, metin: str, kullanici: bool = False, kw: dict | None = None) -> None:
        if kullanici:
            self.log.append(f"<table width='100%' cellpadding='6'><tr><td align='right'>"
                            f"<span style='color:#1f3864'><b>Siz:</b> {h(metin)}</span></td></tr></table>")
        else:
            self.log.append(f"<table width='100%' cellpadding='8' bgcolor='#eef3fb'><tr><td>"
                            f"{self._baglantilar(metin, kw)}</td></tr></table>")
        sb = self.log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def yanit(self, y: Yanit) -> None:
        s = y.metin
        if y.dosyalar:
            s += "<br><b>Hazırlanan:</b> " + " · ".join(
                f"<a href='file:{h(str(p))}'>{h(p.name)}</a>" for p in y.dosyalar)
            s += f" &nbsp;(<a href='klasor:{h(str(y.dosyalar[0]))}'>klasörde göster</a>)"
        if y.oneriler:
            s += "<br>" + "<br>".join(f"&nbsp;&nbsp;▸ <a href='eylem:{h(e)}'>{h(et)}</a>" for et, e in y.oneriler)
        if y.git:
            s += f"<br>➜ <a href='git:{h(y.git)}'>{h(y.git)} ekranını aç</a>"
        self._yaz(s, kw=y.eylem_kw)

    def gonder(self, komut: str) -> None:
        komut = komut.strip()
        if not komut:
            return
        self.girdi.clear()
        self._yaz(komut, kullanici=True)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            y = asistan.yorumla(self.db, komut)
        except Exception as e:
            y = Yanit(f"<span style='color:#a00'>Bir hata oluştu: {h(e)}</span>")
        finally:
            QApplication.restoreOverrideCursor()
        self.yanit(y)
        if y.eylem:
            self.eylem_calistir(y.eylem, **y.eylem_kw)
        elif y.dosyalar:
            self.surec.yenile()

    def eylem_calistir(self, anahtar: str, **kw) -> None:
        e = surecler.EYLEMLER[anahtar]
        if e.uzun:
            self._yaz(f"<i>{h(e.etiket)} çalışıyor, lütfen bekleyin…</i>")
        if not eylem.calistir(self, self.db, anahtar, self._eylem_bitti, **kw):
            self._yaz(f"<i>{h(e.etiket)}: iptal edildi.</i>")

    def _eylem_bitti(self, s: surecler.EylemSonucu) -> None:
        if not s.mesaj and s.git:
            self.git(s.git)
            return
        self.yanit(asistan.eylem_sonucu_yaniti(s))
        self.surec.yenile()
        if self.denetim.yapildi:
            self.denetim.yenile()

    def git(self, ad: str) -> QWidget | None:
        if self.pencere is None:
            return None
        return self.pencere.git(ad)

    def _link(self, url) -> None:
        if url.scheme() != "act":
            return
        try:
            tur, deger, kw = self._linkler[int(url.path())]
        except (ValueError, IndexError):
            return
        if tur == "komut":
            self.gonder(deger)
        elif tur == "kart":
            t, _, kid = deger.partition(":")
            self._yaz(asistan.kart(self.db, t, int(kid)))
        elif tur == "git":
            self.git(deger)
        elif tur == "eylem":
            if deger in surecler.EYLEMLER:
                self.eylem_calistir(deger, **kw)
        elif tur == "file":
            ortak.dosya_ac(deger)
        elif tur == "klasor":
            ortak.klasorde_goster(deger)
        elif tur == "aktar":
            if deger == "onayla":
                self._aktar_onayla()
            elif deger == "incele":
                w = self.git("Veri Aktarımı")
                if w is not None and self._bekleyen:
                    w.dosyalari_ekle(self._bekleyen)

    # ------------------------------------------------------------------ dosyalar

    def dragEnterEvent(self, e):
        if surukle_dosyalar(e):
            e.acceptProposedAction()

    def dropEvent(self, e):
        yollar = surukle_dosyalar(e)
        if yollar:
            e.acceptProposedAction()
            self.dosyalari_al(yollar)

    def dosya_sec(self):
        yollar, _ = QFileDialog.getOpenFileNames(self, "Aktarılacak dosyaları seçin", str(Path.home()),
                                                 okuyucu.DOSYA_FILTRESI)
        if yollar:
            self.dosyalari_al(yollar)

    def dosyalari_al(self, yollar: list[str]) -> None:
        self._yaz("Dosya: " + ", ".join(Path(y).name for y in yollar), kullanici=True)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            bulunan, hatalar = aktarim.dosyalari_incele(yollar)
            deneme, hatalar2 = aktarim.otomatik_aktar(self.db, yollar, deneme=True) if bulunan else ([], [])
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self._yaz(f"<span style='color:#a00'>Dosyalar okunamadı: {h(e)}</span>")
            return
        QApplication.restoreOverrideCursor()
        s = ""
        if bulunan:
            s += f"<b>{len(bulunan)} tablo buldum:</b><ul>"
            for b in bulunan:
                if b.en_iyi:
                    veri = max(0, len(b.tablo.satirlar) - b.en_iyi.bas - 1)
                    s += f"<li>{h(b.tablo.etiket)} → <b>{h(TANIMLAR[b.en_iyi.anahtar].etiket)}</b> ({veri} satır)</li>"
                else:
                    s += f"<li>{h(b.tablo.etiket)} → <span style='color:#a60'>tanınmadı</span></li>"
            s += "</ul>"
        tum_hata = list(dict.fromkeys(hatalar + hatalar2))
        if tum_hata:
            s += "<span style='color:#a00'>" + "<br>".join(h(x) for x in tum_hata[:8]) + "</span><br>"
        if deneme:
            s += "<b>Deneme sonucu (henüz kaydedilmedi):</b><br>" + "<br>".join(h(d.ozet_metni()) for d in deneme)
            hatali = sum(len(d.hatalar) for d in deneme)
            if hatali:
                s += f"<br><span style='color:#a60'>{hatali} satır aktarılamayacak; ayrıntı için aktarım ekranında " \
                     f"inceleyin.</span>"
            s += ("<br><br>▸ <a href='aktar:onayla'>Aktar (önce yedek alınır)</a> &nbsp; "
                  "▸ <a href='aktar:incele'>Aktarım ekranında incele / sütunları düzelt</a>")
            self._bekleyen = list(yollar)
        elif bulunan:
            s += "Otomatik aktarılabilecek tablo yok. ▸ <a href='aktar:incele'>Aktarım ekranında veri türünü seçin</a>"
            self._bekleyen = list(yollar)
        self._yaz(s or "Dosyalarda tablo bulunamadı.")

    def _aktar_onayla(self) -> None:
        if not self._bekleyen:
            self._yaz("Aktarılacak dosya yok; dosyaları yeniden sürükleyin.")
            return
        yollar, self._bekleyen = self._bekleyen, []
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.db.yedekle()
            sonuclar, hatalar = aktarim.otomatik_aktar(self.db, yollar)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            self._yaz(f"<span style='color:#a00'>Aktarım yapılamadı: {h(e)}</span>")
            return
        QApplication.restoreOverrideCursor()
        s = "<b>Aktarım tamamlandı:</b><br>" + "<br>".join(h(x.ozet_metni()) for x in sonuclar)
        if hatalar:
            s += "<br><span style='color:#a00'>" + "<br>".join(h(x) for x in hatalar[:8]) + "</span>"
        satir_hata = [x for r in sonuclar for x in r.hatalar]
        if satir_hata:
            s += "<br><span style='color:#a60'>Aktarılamayan satırlar:<br>" + \
                 "<br>".join(h(x) for x in satir_hata[:10]) + ("<br>…" if len(satir_hata) > 10 else "") + "</span>"
        oneriler: list[tuple[str, str, dict[str, Any]]] = []
        gorulen = set()
        for r in sonuclar:
            if not (r.eklenen or r.guncellenen):
                continue
            yeni = list(r.yeni.get("yerlestirmeler", []))
            for etiket, e in surecler.sonraki_adimlar(r.anahtar, yeni):
                if e not in gorulen:
                    gorulen.add(e)
                    oneriler.append((etiket, e, {"ids": yeni} if e == "sozlesmeler_yeni" else {}))
        self._yaz(s)
        if oneriler:
            parca = []
            for etiket, e, kw in oneriler:
                self._linkler.append(("eylem", e, kw))
                parca.append(f"&nbsp;&nbsp;▸ <a href='act:{len(self._linkler) - 1}'>{h(etiket)}</a>")
            self.log.append("<table width='100%' cellpadding='8' bgcolor='#eef3fb'><tr><td><b>Sıradaki adımlar:</b>"
                            "<br>" + "<br>".join(parca) + "</td></tr></table>")
        self.surec.yenile()
