"""Ceza koruması arayüzü: kayıttan sonra "şimdi ne yapmalı" penceresi ve ana pencerenin üstündeki acil işler bandı."""
from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton

from ..services import koruma, sgk_beyan, sgk_dosya
from . import ortak


def rehber_goster(parent, db, rh: koruma.Rehber | None) -> None:
    if rh is None:
        return
    box = QMessageBox(parent)
    box.setWindowTitle(rh.baslik)
    box.setIcon(QMessageBox.Warning if rh.kritik else QMessageBox.Information)
    box.setText(rh.metin)
    xml = box.addButton("SGK Bildirge Dosyasını Şimdi Hazırla", QMessageBox.AcceptRole) if rh.xml_tur else None
    box.addButton("Tamam", QMessageBox.RejectRole)
    box.exec()
    if xml is not None and box.clickedButton() == xml:
        bildirge_hazirla(parent, db, rh.yerlestirme_ids, rh.xml_tur)


def bildirge_hazirla(parent, db, ids: list[int], tur: str):
    from .sayfa_sgk_ucret import dosya_sonucu_goster, sgk_klasoru
    try:
        sonuc = sgk_dosya.bildirge_dosyalari(db, ids, tur, sgk_klasoru())
    except sgk_dosya.SgkDosyaHatasi as e:
        ortak.hata(parent, str(e))
        return None
    dosya_sonucu_goster(parent, sonuc, sgk_beyan.GIRIS_YUKLEME if tur == "Giriş" else sgk_beyan.CIKIS_YUKLEME,
                        "sgk4a")
    return sonuc


class KorumaBandi(QFrame):
    """Süresi geçmiş ya da bugün/yarın dolan işler; "Ne yapmalıyım?" `hedef` ekranı açtırır."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("korumaBandi")
        self.setStyleSheet("#korumaBandi{background:#f8d7da;border-bottom:1px solid #e0a3a9}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        self.etiket = QLabel()
        self.etiket.setWordWrap(True)
        self.etiket.setTextFormat(Qt.RichText)
        self.etiket.setStyleSheet("color:#721c24")
        lay.addWidget(self.etiket, 1)
        self.goster = QPushButton("Ne yapmalıyım?")
        lay.addWidget(self.goster)
        kapat = QPushButton("Sonra")
        kapat.setToolTip("Bandı yarım saat gizler; uyarılar Ana Sayfa'da kalır.")
        kapat.clicked.connect(self.sonra)
        lay.addWidget(kapat)
        self.hedef = "Ana Sayfa"
        self.kritikler: list[koruma.Kritik] = []
        self.hide()

    def sonra(self) -> None:
        self.hide()

    def ayarla(self, kritikler: list[koruma.Kritik]) -> None:
        self.kritikler = kritikler
        if not kritikler:
            self.hide()
            return
        ilk = kritikler[0]
        self.hedef = ilk.git or "Ana Sayfa"
        ek = f" &nbsp;<i>(+{len(kritikler) - 1} acil iş daha, hepsi Ana Sayfa'da)</i>" if len(kritikler) > 1 else ""
        self.etiket.setText(f"<b>⚠ Ceza riski / acil iş:</b> {escape(ilk.mesaj[:260])}{ek}")
        self.show()
