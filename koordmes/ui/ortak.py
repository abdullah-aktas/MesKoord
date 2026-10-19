"""Arayüz yardımcıları."""
from __future__ import annotations

import os
import subprocess
import traceback
from datetime import date
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import (QAbstractTableModel, QModelIndex, QObject, QPoint, QRect, QSize, QSortFilterProxyModel, Qt,
                            QThread, QUrl, Signal)
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QPageLayout, QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QLayout, QMessageBox,
                               QSizePolicy, QSpacerItem, QSpinBox, QTableView, QWidget)

from .. import config
from ..mevzuat import AYLAR

RENK_KRITIK = QColor("#f8d7da")
RENK_UYARI = QColor("#fff3cd")
RENK_BILGI = QColor("#d1ecf1")
RENK_TAMAM = QColor("#d4edda")


class AkisDuzeni(QLayout):
    """Sığmayan öğeleri alt satıra geçiren yatay düzen (düğme satırları için).

    QHBoxLayout yerine kullanılır: addWidget/addStretch/addSpacing aynı biçimde çağrılır. addStretch satır içinde
    küçük bir ayraç bırakır. Sayfanın en küçük genişliği, satırın tamamı değil en geniş tek öğe olur.
    """

    def __init__(self, parent=None, bosluk: int = 6):
        super().__init__(parent)
        self._ogeler = []
        self._bosluk = bosluk
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:
        self._ogeler.append(item)

    def addWidget(self, w, *_):
        QLayout.addWidget(self, w)

    def addStretch(self, *_):
        self.addItem(QSpacerItem(14, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

    def addSpacing(self, n: int):
        self.addItem(QSpacerItem(n, 0, QSizePolicy.Fixed, QSizePolicy.Minimum))

    def count(self) -> int:
        return len(self._ogeler)

    def itemAt(self, i: int):
        return self._ogeler[i] if 0 <= i < len(self._ogeler) else None

    def takeAt(self, i: int):
        return self._ogeler.pop(i) if 0 <= i < len(self._ogeler) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, genislik: int) -> int:
        return self._yerlestir(QRect(0, 0, genislik, 0), True)

    def setGeometry(self, r: QRect) -> None:
        super().setGeometry(r)
        self._yerlestir(r, False)

    def sizeHint(self) -> QSize:
        m = self.contentsMargins()
        g = sum(o.sizeHint().width() for o in self._ogeler if not o.isEmpty())
        g += self._bosluk * max(0, len(self._ogeler) - 1)
        y = max((o.sizeHint().height() for o in self._ogeler if not o.isEmpty()), default=0)
        return QSize(g + m.left() + m.right(), y + m.top() + m.bottom())

    def minimumSize(self) -> QSize:
        s = QSize()
        for o in self._ogeler:
            if not o.isEmpty() and o.widget() is not None:
                s = s.expandedTo(o.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _yerlestir(self, r: QRect, sadece_olc: bool) -> int:
        m = self.contentsMargins()
        alan = r.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        satirlar, satir, x = [], [], 0
        for o in self._ogeler:
            if o.isEmpty() and o.widget() is not None:
                continue
            ayrac = o.widget() is None
            g = o.sizeHint().width()
            if satir and x + g > alan.width():
                satirlar.append(satir)
                satir, x = [], 0
            if ayrac and not satir:
                continue
            satir.append(o)
            x += g + self._bosluk
        if satir:
            satirlar.append(satir)
        y = alan.y()
        for satir in satirlar:
            while satir and satir[-1].widget() is None:
                satir.pop()
            yukseklik = max((o.sizeHint().height() for o in satir), default=0)
            x = alan.x()
            for o in satir:
                boyut = o.sizeHint()
                if not sadece_olc:
                    o.setGeometry(QRect(QPoint(x, y + (yukseklik - boyut.height()) // 2), boyut))
                x += boyut.width() + self._bosluk
            y += yukseklik + self._bosluk
        return max(0, y - alan.y() - self._bosluk) + m.top() + m.bottom()


def etiketli(etiket: str, w: QWidget) -> QWidget:
    """Etiketle denetimi tek parça yapar; AkisDuzeni satırı kırarken ikisini ayırmaz."""
    kutu = QWidget()
    h = QHBoxLayout(kutu)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(4)
    h.addWidget(QLabel(etiket))
    h.addWidget(w)
    return kutu


class TabloModeli(QAbstractTableModel):
    """Basit liste-tabanlı tablo modeli. rows: list[list[Any]]."""

    def __init__(self, basliklar: list[str], rows: list[list[Any]] | None = None, parent=None):
        super().__init__(parent)
        self.basliklar = basliklar
        self.rows = rows or []
        self.kimlikler: list[Any] = []
        self.renkler: dict[int, QColor] = {}
        self.hizalama: dict[int, Qt.AlignmentFlag] = {}

    def ayarla(self, rows: list[list[Any]], kimlikler: list[Any] | None = None,
               renkler: dict[int, QColor] | None = None) -> None:
        self.beginResetModel()
        self.rows = rows
        self.kimlikler = kimlikler or []
        self.renkler = renkler or {}
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.basliklar)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        v = self.rows[index.row()][index.column()]
        if role == Qt.DisplayRole:
            if isinstance(v, float):
                return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return "" if v is None else str(v)
        if role == Qt.UserRole:
            return v
        if role == Qt.BackgroundRole and index.row() in self.renkler:
            return QBrush(self.renkler[index.row()])
        if role == Qt.TextAlignmentRole:
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return self.hizalama.get(index.column())
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.basliklar[section]
        return None

    def kimlik(self, row: int):
        return self.kimlikler[row] if row < len(self.kimlikler) else None


class SiralamaProxy(QSortFilterProxyModel):
    def lessThan(self, left, right):
        a, b = left.data(Qt.UserRole), right.data(Qt.UserRole)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return a < b
        return str(a or "").lower() < str(b or "").lower()


def tablo_gorunumu(model: TabloModeli, filtrelenebilir: bool = True) -> tuple[QTableView, SiralamaProxy]:
    view = QTableView()
    proxy = SiralamaProxy()
    proxy.setSourceModel(model)
    proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
    proxy.setFilterKeyColumn(-1)
    view.setModel(proxy)
    view.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
    view.setSortingEnabled(True)
    view.setSelectionBehavior(QTableView.SelectRows)
    view.setAlternatingRowColors(True)
    view.verticalHeader().setVisible(False)
    view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
    view.horizontalHeader().setStretchLastSection(True)
    view.setEditTriggers(QTableView.NoEditTriggers)
    return view, proxy


def secili_satirlar(view: QTableView, proxy: SiralamaProxy) -> list[int]:
    return sorted({proxy.mapToSource(i).row() for i in view.selectionModel().selectedRows()})


def sutunlari_sigdir(view: QTableView, azami: int = 320) -> None:
    view.resizeColumnsToContents()
    for c in range(view.model().columnCount()):
        if view.columnWidth(c) > azami:
            view.setColumnWidth(c, azami)


class AySecici(QWidget):
    degisti = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("Dönem:"))
        self.ay = QComboBox()
        self.ay.addItems(AYLAR)
        self.yil = QSpinBox()
        self.yil.setRange(2020, 2100)
        bugun = date.today()
        self.ay.setCurrentIndex(bugun.month - 1)
        self.yil.setValue(bugun.year)
        lay.addWidget(self.ay)
        lay.addWidget(self.yil)
        self.ay.currentIndexChanged.connect(lambda _: self.degisti.emit(*self.deger()))
        self.yil.valueChanged.connect(lambda _: self.degisti.emit(*self.deger()))

    def deger(self) -> tuple[int, int]:
        return self.yil.value(), self.ay.currentIndex() + 1

    def ayarla(self, yil: int, ay: int) -> None:
        self.yil.setValue(yil)
        self.ay.setCurrentIndex(ay - 1)


class _Isci(QObject):
    bitti = Signal(object)
    hata = Signal(str)

    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self.fn = fn

    def calistir(self):
        try:
            self.bitti.emit(self.fn())
        except Exception:
            self.hata.emit(traceback.format_exc())


class _ArkaKopru(QObject):
    """Ana iş parçacığında yaşar; işçi sinyallerini güvenle UI'ye aktarır."""

    def __init__(self, th: QThread, bitince: Callable[[Any], None], hata: Callable[[str], None], kayit: list):
        super().__init__()
        self._th = th
        self._bitince = bitince
        self._hata = hata
        self._kayit = kayit

    def bitti(self, r) -> None:
        self._th.quit()
        self._th.wait(120_000)
        if self._kayit in _aktif_isler:
            _aktif_isler.remove(self._kayit)
        self._bitince(r)

    def hata(self, e: str) -> None:
        self._th.quit()
        self._th.wait(120_000)
        if self._kayit in _aktif_isler:
            _aktif_isler.remove(self._kayit)
        self._hata(e)


_aktif_isler: list = []


def arka_planda(fn: Callable[[], Any], bitince: Callable[[Any], None], hata: Callable[[str], None]) -> None:
    """fn'i ayrı iş parçacığında çalıştırır. fn kendi DB bağlantısını açmalıdır.
    Sonuç ana iş parçacığına kuyruklanır; bitince/hata orada çağrılır (UI ve DB güvenli)."""
    th = QThread()
    isci = _Isci(fn)
    kayit: list = []
    kopru = _ArkaKopru(th, bitince, hata, kayit)
    kayit.extend((th, isci, kopru))
    isci.moveToThread(th)
    th.started.connect(isci.calistir)
    isci.bitti.connect(kopru.bitti, Qt.QueuedConnection)
    isci.hata.connect(kopru.hata, Qt.QueuedConnection)
    _aktif_isler.append(kayit)
    th.start()


def bilgi(parent, metin: str, baslik: str = "Bilgi") -> None:
    QMessageBox.information(parent, baslik, metin)


def hata(parent, metin: str, baslik: str = "Hata") -> None:
    QMessageBox.critical(parent, baslik, metin)


def onay(parent, metin: str, baslik: str = "Onay") -> bool:
    return QMessageBox.question(parent, baslik, metin, QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes


def kaydet_yolu(parent, varsayilan_ad: str, filtre: str = "Excel Dosyası (*.xlsx)") -> Path | None:
    yol, _ = QFileDialog.getSaveFileName(parent, "Kaydet", str(config.output_dir() / varsayilan_ad), filtre)
    return Path(yol) if yol else None


def dosya_ac(yol: Path | str) -> None:
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(yol)))


def klasorde_goster(yol: Path | str) -> None:
    yol = Path(yol)
    if os.name == "nt" and yol.is_file():
        subprocess.Popen(["explorer", "/select,", str(yol)])
    else:
        dosya_ac(yol if yol.is_dir() else yol.parent)


def kaydedildi(parent, yol: Path, coklu: bool = False) -> None:
    box = QMessageBox(parent)
    box.setWindowTitle("Kaydedildi")
    box.setText(f"{'Dosyalar' if coklu else 'Dosya'} kaydedildi:\n{yol}")
    ac = box.addButton("Aç", QMessageBox.AcceptRole)
    klasor = box.addButton("Klasörü Aç", QMessageBox.ActionRole)
    paylas_btn = box.addButton("Paylaş (e-posta / WhatsApp)...", QMessageBox.ActionRole)
    box.addButton("Kapat", QMessageBox.RejectRole)
    box.exec()
    if box.clickedButton() == ac:
        dosya_ac(yol)
    elif box.clickedButton() == klasor:
        klasorde_goster(yol)
    elif box.clickedButton() == paylas_btn:
        from .paylas import paylas
        paylas(parent, yol)


def html_pdf(html: str, yol: Path, yatay: bool = True) -> Path:
    doc = QTextDocument()
    doc.setHtml(html)
    w = QPdfWriter(str(yol))
    w.setPageSize(QPageSize(QPageSize.A4))
    w.setPageOrientation(QPageLayout.Landscape if yatay else QPageLayout.Portrait)
    w.setResolution(96)
    doc.setPageSize(w.pageLayout().paintRectPixels(96).size().toSizeF())
    doc.print_(w)
    return yol


KURUM_LOGOSU: Path | None = None  # ana pencere ayarlar; raporların başına konur


def html_tablo(baslik: str, basliklar: list[str], satirlar: list[list[Any]], alt: str = "") -> str:
    th = "".join(f"<th>{h}</th>" for h in basliklar)
    tr = "".join("<tr>" + "".join(f"<td>{'' if v is None else v}</td>" for v in s) + "</tr>" for s in satirlar)
    logo = (f"<p style='text-align:center; margin:0'><img src='{QUrl.fromLocalFile(str(KURUM_LOGOSU)).toString()}'"
            f" height='60'></p>" if KURUM_LOGOSU and Path(KURUM_LOGOSU).exists() else "")
    return (f"<html><body style='font-family:Arial; font-size:9pt'>{logo}"
            f"<h3 style='text-align:center'>{baslik}</h3>"
            f"<table border='1' cellspacing='0' cellpadding='4' width='100%' style='border-collapse:collapse'>"
            f"<tr style='background:#dde4f0'>{th}</tr>{tr}</table><p>{alt}</p></body></html>")
