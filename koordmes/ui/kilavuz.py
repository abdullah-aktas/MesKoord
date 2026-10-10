"""Yardım > Kullanım Kılavuzu: docs/KULLANIM_KILAVUZU.md'yi program içinde gösterir, arar ve PDF'e çevirir."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QPageLayout, QPageSize, QPdfWriter, QShortcut, QTextDocument
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
                               QSplitter, QTextBrowser, QVBoxLayout, QWidget)

from .. import marka
from . import ortak

DOSYA_ADI = "KULLANIM_KILAVUZU.md"


def kilavuz_yolu() -> Path:
    # Paketlenmiş programda docs/ klasörü _internal içine konur (MesKoord.spec); yapı kaynak kodla aynıdır.
    return Path(__file__).resolve().parents[2] / "docs" / DOSYA_ADI


def kilavuz_metni() -> str:
    try:
        return kilavuz_yolu().read_text("utf-8")
    except OSError:
        return (f"# {marka.URUN} Kullanım Kılavuzu\n\nKılavuz dosyası bulunamadı ({kilavuz_yolu()}). "
                "Programı yeniden kurun ya da program klasöründeki KULLANIM_KILAVUZU.pdf dosyasını açın.")


def belge(metin: str | None = None) -> QTextDocument:
    doc = QTextDocument()
    doc.setMarkdown(metin if metin is not None else kilavuz_metni())
    return doc


def pdf_yaz(doc: QTextDocument, yol: Path) -> Path:
    w = QPdfWriter(str(yol))
    w.setPageSize(QPageSize(QPageSize.A4))
    w.setPageOrientation(QPageLayout.Portrait)
    w.setResolution(96)
    w.setTitle(doc.metaInformation(QTextDocument.DocumentTitle) or f"{marka.URUN} Kullanım Kılavuzu")
    kopya = doc.clone()
    kopya.setPageSize(w.pageLayout().paintRectPixels(96).size().toSizeF())
    kopya.print_(w)
    return yol


class KilavuzPenceresi(QDialog):
    def __init__(self, parent: QWidget | None = None, metin: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(f"{marka.URUN} Kullanım Kılavuzu")
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        lay = QVBoxLayout(self)

        ust = QHBoxLayout()
        self.ara = QLineEdit()
        self.ara.setPlaceholderText("Kılavuzda ara (Enter: sonraki, Shift+Enter: önceki)")
        self.ara.setClearButtonEnabled(True)
        self.ara.returnPressed.connect(lambda: self.bul(geri=False))
        QShortcut(QKeySequence("Shift+Return"), self.ara, activated=lambda: self.bul(geri=True))
        ust.addWidget(self.ara, 1)
        for etiket, fn in [("Bul", lambda: self.bul(geri=False)), ("PDF Olarak Kaydet", self.pdf_kaydet)]:
            b = QPushButton(etiket)
            b.clicked.connect(fn)
            ust.addWidget(b)
        lay.addLayout(ust)

        ayirici = QSplitter()
        self.icindekiler = QListWidget()
        self.icindekiler.itemClicked.connect(self._basliga_git)
        ayirici.addWidget(self.icindekiler)
        self.metin = QTextBrowser()
        self.metin.setOpenExternalLinks(True)
        self.metin.setDocument(belge(metin))
        ayirici.addWidget(self.metin)
        ayirici.setSizes([260, 760])
        lay.addWidget(ayirici, 1)

        kapat = QPushButton("Kapat")
        kapat.clicked.connect(self.accept)
        lay.addWidget(kapat, alignment=Qt.AlignRight)
        self._icindekileri_doldur()
        self.resize(1080, 760)

    def _icindekileri_doldur(self) -> None:
        blok = self.metin.document().begin()
        while blok.isValid():
            seviye = blok.blockFormat().headingLevel()
            if seviye in (2, 3) and blok.text().strip():
                it = QListWidgetItem(("" if seviye == 2 else "    ") + blok.text().strip())
                it.setData(Qt.UserRole, blok.position())
                self.icindekiler.addItem(it)
            blok = blok.next()

    def _basliga_git(self, it: QListWidgetItem) -> None:
        doc = self.metin.document()
        blok = doc.findBlock(it.data(Qt.UserRole))
        ust = doc.documentLayout().blockBoundingRect(blok).top()
        self.metin.verticalScrollBar().setValue(int(ust))

    def bul(self, geri: bool = False) -> bool:
        aranan = self.ara.text().strip()
        if not aranan:
            return False
        bayrak = QTextDocument.FindBackward if geri else QTextDocument.FindFlag(0)
        if self.metin.find(aranan, bayrak):
            return True
        imlec = self.metin.textCursor()
        imlec.movePosition(imlec.MoveOperation.End if geri else imlec.MoveOperation.Start)
        self.metin.setTextCursor(imlec)
        return self.metin.find(aranan, bayrak)

    def pdf_kaydet(self) -> None:
        yol = ortak.kaydet_yolu(self, f"{marka.URUN}_Kullanim_Kilavuzu.pdf", "PDF Dosyası (*.pdf)")
        if yol:
            ortak.kaydedildi(self, pdf_yaz(self.metin.document(), yol))
