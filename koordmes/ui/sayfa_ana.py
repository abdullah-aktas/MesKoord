"""Ana sayfa: özet sayılar ve yasal süre uyarıları."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..services import degisiklik, takvim
from ..services.utils import tr
from . import ortak

RENKLER = {"Kritik": ortak.RENK_KRITIK, "Uyarı": ortak.RENK_UYARI, "Bilgi": ortak.RENK_BILGI}


class Kart(QFrame):
    def __init__(self, baslik: str):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("QFrame{background:#ffffff;border:1px solid #d0d7e2;border-radius:8px}")
        lay = QVBoxLayout(self)
        self.deger = QLabel("0")
        self.deger.setStyleSheet("font-size:26px;font-weight:bold;color:#2F5597;border:none")
        lb = QLabel(baslik)
        lb.setStyleSheet("color:#555;border:none")
        lay.addWidget(self.deger, alignment=Qt.AlignCenter)
        lay.addWidget(lb, alignment=Qt.AlignCenter)


class AnaSayfa(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        ust = QHBoxLayout()
        self.baslik = QLabel()
        self.baslik.setStyleSheet("font-size:18px;font-weight:bold")
        ust.addWidget(self.baslik)
        ust.addStretch()
        b = QPushButton("Yenile")
        b.clicked.connect(self.yenile)
        ust.addWidget(b)
        lay.addLayout(ust)

        self.degisim = QLabel()
        self.degisim.setWordWrap(True)
        self.degisim.setTextFormat(Qt.RichText)
        self.degisim.setStyleSheet("background:#e8f0fe;border:1px solid #c5d4f0;border-radius:6px;padding:8px")
        lay.addWidget(self.degisim)

        grid = QGridLayout()
        self.kartlar = {}
        for i, (k, ad) in enumerate([("ogrenci", "Aktif Öğrenci"), ("isletmede", "İşletmede Eğitim Gören"),
                                     ("isletme", "Aktif İşletme"), ("ogretmen", "Öğretmen"),
                                     ("koord", "Koordinatör Öğretmen"), ("sgk", "Bekleyen SGK Bildirimi")]):
            self.kartlar[k] = Kart(ad)
            grid.addWidget(self.kartlar[k], 0, i)
        lay.addLayout(grid)

        lay.addWidget(QLabel("<b>Yasal süreler ve uyarılar</b> &nbsp;<span style='color:#555'>Kırmızı satırlar ceza "
                             "riskidir. Ne yapacağınızı açıklama sütunu söyler; satıra çift tıklayınca işin "
                             "yapılacağı ekran açılır.</span>"))
        self.model = ortak.TabloModeli(["Önem", "Konu", "Açıklama", "Tarih"])
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        self.view.doubleClicked.connect(self._git)
        lay.addWidget(self.view, 1)

    def _git(self, idx) -> None:
        r = self.proxy.mapToSource(idx).row()
        hedef = self.model.kimlikler[r] if 0 <= r < len(self.model.kimlikler) else ""
        w = self.window()
        if hedef and hasattr(w, "git"):
            w.git(hedef)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self):
        k = self.db.kurum()
        self.baslik.setText(f"{k['ad'] or 'Kurum adı girilmemiş'}  —  {k['egitim_yili'] or ''} Eğitim-Öğretim Yılı")
        bildirim = degisiklik.oku(self.db)
        if bildirim:
            self.degisim.setText("<b>Son veri değişikliği</b><br>" + bildirim.replace("\n", "<br>"))
            self.degisim.show()
        else:
            self.degisim.hide()
        q = lambda sql: self.db.q1(sql)["c"]
        self.kartlar["ogrenci"].deger.setText(str(q("SELECT COUNT(*) c FROM ogrenciler WHERE aktif = 1")))
        self.kartlar["isletmede"].deger.setText(str(q(
            "SELECT COUNT(DISTINCT ogrenci_id) c FROM yerlestirmeler WHERE durum = 'Aktif' AND isletme_id IS NOT NULL")))
        self.kartlar["isletme"].deger.setText(str(q(
            "SELECT COUNT(DISTINCT isletme_id) c FROM yerlestirmeler WHERE durum = 'Aktif' AND isletme_id IS NOT NULL")))
        self.kartlar["ogretmen"].deger.setText(str(q("SELECT COUNT(*) c FROM ogretmenler WHERE aktif = 1")))
        self.kartlar["koord"].deger.setText(str(q("SELECT COUNT(DISTINCT ogretmen_id) c FROM koordinator_gorevleri")))
        uyarilar = takvim.uyarilar(self.db)
        self.kartlar["sgk"].deger.setText(str(sum(1 for u in uyarilar if u.konu == "SGK" and "bildirgesi" in u.mesaj)))
        self.model.ayarla([[u.seviye, u.konu, u.mesaj, tr(u.tarih)] for u in uyarilar], [u.git for u in uyarilar],
                          {i: RENKLER[u.seviye] for i, u in enumerate(uyarilar)})
        self.view.setColumnWidth(0, 70)
        self.view.setColumnWidth(1, 120)
        self.view.setColumnWidth(2, 820)
