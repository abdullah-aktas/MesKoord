"""Sol menü: açılır-kapanır gruplar, menüde arama ve simge şeridine daralan panel."""
from __future__ import annotations

from functools import cache

from PySide6.QtCore import QEasingCurve, QEvent, QPoint, QRect, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QAction, QColor, QFont, QFontDatabase, QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu, QPushButton,
                               QStyle, QStyledItemDelegate, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                               QWidget, QWidgetAction)

from .. import marka
from ..services.aktarim import norm

GENIS = 248
DAR = 64
GRUP_YUKSEKLIGI = 36
SAYFA_YUKSEKLIGI = 31
TUR, AD = Qt.UserRole, Qt.UserRole + 1

# Segoe Fluent Icons (Windows 11) / Segoe MDL2 Assets (Windows 10) kod noktaları; yazı tipi yoksa yedek karakter
SIMGELER = {
    "GENEL": ("\ue80f", "⌂"), "TANIMLAR": ("\ue716", "☰"), "DERS PROGRAMI": ("\ue787", "▦"),
    "İŞLETMELERDE MESLEKİ EĞİTİM": ("\ue821", "⚒"), "PERSONEL": ("\ue77b", "☺"), "EVRAK": ("\ue8a5", "✉"),
    "SİSTEM": ("\ue713", "⚙"),
    "_ara": ("\ue721", "⌕"), "_menu": ("\ue700", "≡"), "_asagi": ("\ue70d", "▾"), "_sag": ("\ue76c", "▸"),
    "_cikis": ("\ue7e8", "⏻"), "_temizle": ("\ue711", "✕"), "_grup": ("\ue8fd", "•"),
}


@cache
def _simge_ailesi() -> str | None:
    aileler = set(QFontDatabase.families())
    return next((a for a in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if a in aileler), None)


def simge_fontu(piksel: int) -> QFont:
    f = QFont(_simge_ailesi() or "Segoe UI Symbol")
    f.setPixelSize(piksel)
    return f


def glif(anahtar: str) -> str:
    kod, yedek = SIMGELER.get(anahtar, SIMGELER["_grup"])
    return kod if _simge_ailesi() else yedek


def simge(anahtar: str, renk: str = "#FFFFFF", boyut: int = 18) -> QIcon:
    pm = QPixmap(boyut * 2, boyut * 2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.TextAntialiasing)
    p.setFont(simge_fontu(int(boyut * 1.6)))
    p.setPen(QColor(renk))
    p.drawText(pm.rect(), Qt.AlignCenter, glif(anahtar))
    p.end()
    pm.setDevicePixelRatio(2)
    return QIcon(pm)


class _Agac(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.aktif_grup = ""
        self.setObjectName("menu")
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)
        self.setIndentation(0)
        self.setExpandsOnDoubleClick(False)
        self.setAnimated(True)
        self.setMouseTracking(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setFrameShape(QFrame.NoFrame)
        self.setItemDelegate(_Cizici(self))


class _Cizici(QStyledItemDelegate):
    def __init__(self, agac: _Agac):
        super().__init__(agac)
        self.agac = agac

    def sizeHint(self, opt, idx):
        return QSize(opt.rect.width(), GRUP_YUKSEKLIGI if idx.data(TUR) == "grup" else SAYFA_YUKSEKLIGI)

    def paint(self, p: QPainter, opt, idx):
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        r = opt.rect
        ustunde = bool(opt.state & QStyle.State_MouseOver)
        ad = idx.data(AD)
        if idx.data(TUR) == "grup":
            acik = self.agac.isExpanded(idx)
            aktif = ad == self.agac.aktif_grup
            if ustunde:
                p.fillRect(r, QColor("#22346F"))
            p.setFont(simge_fontu(15))
            p.setPen(QColor(marka.VURGU_ACIK if aktif else "#9AA8D2"))
            p.drawText(QRect(r.left() + 12, r.top(), 22, r.height()), Qt.AlignCenter, glif(ad))
            f = QFont(opt.font)
            f.setPointSizeF(8)
            f.setBold(True)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 0.2)
            p.setFont(f)
            p.setPen(QColor("#FFFFFF" if (aktif or acik or ustunde) else "#BCC6E4"))
            yazi = QRect(r.left() + 42, r.top(), r.width() - 42 - 24, r.height())
            p.drawText(yazi, Qt.AlignVCenter | Qt.AlignLeft,
                       QFontMetrics(f).elidedText(ad, Qt.ElideRight, yazi.width()))
            p.setFont(simge_fontu(9))
            p.setPen(QColor("#8D9BC7"))
            p.drawText(QRect(r.right() - 22, r.top(), 16, r.height()), Qt.AlignCenter,
                       glif("_asagi" if acik else "_sag"))
        else:
            secili = bool(opt.state & QStyle.State_Selected)
            kutu = r.adjusted(8, 2, -8, -2)
            p.setPen(Qt.NoPen)
            if secili:
                p.setBrush(QColor(marka.ANA_ACIK))
                p.drawRoundedRect(kutu, 6, 6)
                p.setBrush(QColor(marka.VURGU))
                p.drawRoundedRect(QRect(kutu.left(), kutu.top() + 6, 3, kutu.height() - 12), 1.5, 1.5)
            elif ustunde:
                p.setBrush(QColor("#25387B"))
                p.drawRoundedRect(kutu, 6, 6)
            if opt.state & QStyle.State_HasFocus and self.agac.hasFocus():
                p.setBrush(Qt.NoBrush)
                p.setPen(QColor(marka.VURGU))
                p.drawRoundedRect(kutu.adjusted(0, 0, -1, -1), 6, 6)
            f = QFont(opt.font)
            f.setPointSizeF(9.5)
            if secili:
                f.setWeight(QFont.DemiBold)
            p.setFont(f)
            p.setPen(QColor("#FFFFFF" if secili else "#D3DAEF"))
            yazi = QRect(r.left() + 42, r.top(), r.width() - 42 - 14, r.height())
            p.drawText(yazi, Qt.AlignVCenter | Qt.AlignLeft,
                       QFontMetrics(f).elidedText(ad, Qt.ElideRight, yazi.width()))
        p.restore()


class YanMenu(QWidget):
    """Gruplar akordeon gibi açılır (biri açılınca ötekiler kapanır); Ctrl+K arar, Ctrl+B şeride daraltır."""

    secildi = Signal(str)
    cikis_istendi = Signal()
    daraldi = Signal(bool)

    def __init__(self, gruplar: list[tuple[str, list[str]]], parent=None):
        super().__init__(parent)
        self.setObjectName("yanPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.gruplar = gruplar
        self.dar = False
        self._gecici_genis = False
        self._araniyor = False
        self._sayfa_ogesi: dict[str, QTreeWidgetItem] = {}
        self._grup_ogesi: dict[str, QTreeWidgetItem] = {}
        self._ray_dugmeleri: dict[str, QToolButton] = {}
        self._animasyon = QVariantAnimation(self)
        self._animasyon.setDuration(170)
        self._animasyon.setEasingCurve(QEasingCurve.OutCubic)
        self._animasyon.valueChanged.connect(lambda v: self.setFixedWidth(int(v)))
        self.setFixedWidth(GENIS)

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self._baslik())
        cizgi = QFrame()
        cizgi.setObjectName("markaCizgi")
        v.addWidget(cizgi)

        self.genis_alan = QWidget()
        g = QVBoxLayout(self.genis_alan)
        g.setContentsMargins(0, 10, 0, 0)
        g.setSpacing(6)
        self.arama = QLineEdit()
        self.arama.setObjectName("menuArama")
        self.arama.setPlaceholderText("Menüde ara…   Ctrl+K")
        self.arama.setAccessibleName("Menüde ara")
        self.arama.addAction(simge("_ara", "#9AA8D2", 14), QLineEdit.LeadingPosition)
        self._temizle = self.arama.addAction(simge("_temizle", "#C9D1EA", 12), QLineEdit.TrailingPosition)
        self._temizle.setVisible(False)
        self._temizle.triggered.connect(self.arama.clear)
        self.arama.textChanged.connect(self._ara)
        self.arama.returnPressed.connect(self._ilk_sonucu_ac)
        self.arama.installEventFilter(self)
        kutu = QHBoxLayout()
        kutu.setContentsMargins(12, 0, 12, 0)
        kutu.addWidget(self.arama)
        g.addLayout(kutu)
        self.sonuc_yok = QLabel("Eşleşen menü bulunamadı.")
        self.sonuc_yok.setObjectName("aramaSonucYok")
        self.sonuc_yok.setVisible(False)
        g.addWidget(self.sonuc_yok)
        self.agac = _Agac()
        g.addWidget(self.agac, 1)
        v.addWidget(self.genis_alan, 1)

        self.ray = QWidget()
        r = QVBoxLayout(self.ray)
        r.setContentsMargins(8, 10, 8, 0)
        r.setSpacing(4)
        ara = self._ray_dugmesi("_ara", "Menüde ara (Ctrl+K)")
        ara.clicked.connect(self.ara_odakla)
        r.addWidget(ara, 0, Qt.AlignHCenter)
        ayrac = QFrame()
        ayrac.setObjectName("rayAyrac")
        r.addWidget(ayrac)
        for grup, _ in gruplar:
            b = self._ray_dugmesi(grup, grup)
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, gr=grup: self._ray_menusu(gr))
            self._ray_dugmeleri[grup] = b
            r.addWidget(b, 0, Qt.AlignHCenter)
        r.addStretch(1)
        self.ray.setVisible(False)
        v.addWidget(self.ray, 1)

        self.cikis = QPushButton("Güvenli Çıkış")
        self.cikis.setObjectName("cikisDugmesi")
        self.cikis.setIcon(simge("_cikis", "#FFFFFF", 16))
        self.cikis.setToolTip("Taslakları kaydeder, isteğe bağlı yedek alır ve programı güvenle kapatır (Ctrl+Q)")
        self.cikis.clicked.connect(self.cikis_istendi)
        v.addWidget(self.cikis)

        for grup, sayfalar in gruplar:
            gi = QTreeWidgetItem([grup])
            gi.setData(0, TUR, "grup")
            gi.setData(0, AD, grup)
            gi.setFlags(Qt.ItemIsEnabled)
            gi.setToolTip(0, grup)
            self.agac.addTopLevelItem(gi)
            self._grup_ogesi[grup] = gi
            for ad in sayfalar:
                si = QTreeWidgetItem([ad])
                si.setData(0, TUR, "sayfa")
                si.setData(0, AD, ad)
                si.setToolTip(0, ad)
                gi.addChild(si)
                self._sayfa_ogesi[ad] = si
        self.agac.itemClicked.connect(self._tiklandi)
        self.agac.itemActivated.connect(self._tiklandi)
        self.agac.itemExpanded.connect(self._acildi)
        self.agac.itemCollapsed.connect(lambda _: self.agac.viewport().update())
        self.agac.itemSelectionChanged.connect(self._secim_degisti)

    # --- yapı ---
    def _baslik(self) -> QWidget:
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(12, 10, 8, 8)
        h.setSpacing(8)
        self.logo = QLabel()
        self.logo.setPixmap(marka.logo_pixmap(42))
        self.logo.setToolTip(f"{marka.URUN} — {marka.SLOGAN}")
        h.addWidget(self.logo, 0, Qt.AlignTop)
        self.yazi = QWidget()
        y = QVBoxLayout(self.yazi)
        y.setContentsMargins(0, 0, 0, 0)
        y.setSpacing(0)
        ad = QLabel(f"{marka.URUN_ON}<span style='color:{marka.VURGU_ACIK}'>{marka.URUN_SON}</span>")
        ad.setObjectName("markaAdi")
        ad.setAccessibleName(marka.URUN)
        y.addWidget(ad)
        self.kurum_etiketi = QLabel()
        self.kurum_etiketi.setObjectName("markaAlt")
        self.kurum_etiketi.setWordWrap(True)
        y.addWidget(self.kurum_etiketi)
        h.addWidget(self.yazi, 1)
        self.daralt = QToolButton()
        self.daralt.setObjectName("menuDugmesi")
        self.daralt.setIcon(simge("_menu", "#FFFFFF", 18))
        self.daralt.setIconSize(QSize(18, 18))
        self.daralt.setFixedSize(40, 36)
        self.daralt.setToolTip("Menüyü daralt / genişlet (Ctrl+B)")
        self.daralt.setAccessibleName("Menüyü daralt veya genişlet")
        self.daralt.clicked.connect(lambda: self.dar_yap(not self.dar))
        h.addWidget(self.daralt, 0, Qt.AlignTop)
        return w

    def _ray_dugmesi(self, anahtar: str, ipucu: str) -> QToolButton:
        b = QToolButton()
        b.setObjectName("rayDugmesi")
        b.setIcon(simge(anahtar, "#FFFFFF" if not anahtar.startswith("_") else "#C9D1EA", 18))
        b.setIconSize(QSize(20, 20))
        b.setFixedSize(46, 40)
        b.setToolTip(ipucu)
        b.setAccessibleName(ipucu)
        return b

    # --- seçim ---
    def gecerli(self) -> str:
        ogeler = self.agac.selectedItems()
        return ogeler[0].data(0, AD) if ogeler and ogeler[0].data(0, TUR) == "sayfa" else ""

    def sec(self, ad: str) -> bool:
        oge = self._sayfa_ogesi.get(ad)
        if oge is None:
            return False
        if oge.isHidden() or (oge.parent() and oge.parent().isHidden()):
            self.arama.clear()
        grup = oge.parent()
        if not grup.isExpanded():
            grup.setExpanded(True)
        self.agac.setCurrentItem(oge)
        self.agac.scrollToItem(oge)
        return True

    def _secim_degisti(self) -> None:
        ad = self.gecerli()
        if not ad:
            return
        grup = self._sayfa_ogesi[ad].parent().data(0, AD)
        self.agac.aktif_grup = grup
        for g, b in self._ray_dugmeleri.items():
            b.setChecked(g == grup)
        self.agac.viewport().update()
        self.secildi.emit(ad)
        if self._gecici_genis:
            self.arama.clear()
            self.dar_yap(True, kalici=False)

    def _tiklandi(self, oge: QTreeWidgetItem, _sutun: int = 0) -> None:
        if oge.data(0, TUR) == "grup":
            oge.setExpanded(not oge.isExpanded())

    def _acildi(self, oge: QTreeWidgetItem) -> None:
        if not self._araniyor:
            for g in self._grup_ogesi.values():
                if g is not oge and g.isExpanded():
                    g.setExpanded(False)
            if oge.childCount():
                self.agac.scrollToItem(oge.child(oge.childCount() - 1))
                self.agac.scrollToItem(oge)
        self.agac.viewport().update()

    # --- arama ---
    def ara_odakla(self) -> None:
        if self.dar:
            self._gecici_genis = True
            self.dar_yap(False, kalici=False)
        self.arama.setFocus(Qt.ShortcutFocusReason)
        self.arama.selectAll()

    def _ara(self, metin: str) -> None:
        q = norm(metin)
        self._temizle.setVisible(bool(metin))
        self._araniyor = bool(q)
        bulunan = 0
        for grup, gi in self._grup_ogesi.items():
            grup_uyar = bool(q) and q in norm(grup)
            gorunen = 0
            for i in range(gi.childCount()):
                si = gi.child(i)
                uyar = not q or grup_uyar or q in norm(si.data(0, AD))
                si.setHidden(not uyar)
                gorunen += uyar
            gi.setHidden(gorunen == 0)
            if q:
                gi.setExpanded(gorunen > 0)
                bulunan += gorunen
        self.sonuc_yok.setVisible(bool(q) and bulunan == 0)
        if not q:
            aktif = self._grup_ogesi.get(self.agac.aktif_grup)
            for gi in self._grup_ogesi.values():
                gi.setExpanded(gi is aktif)
            sec = self.agac.selectedItems()
            if sec:
                self.agac.scrollToItem(sec[0])

    def _ilk_sonucu_ac(self) -> None:
        for gi in self._grup_ogesi.values():
            if gi.isHidden():
                continue
            for i in range(gi.childCount()):
                si = gi.child(i)
                if not si.isHidden():
                    ad = si.data(0, AD)
                    self.arama.clear()
                    self.sec(ad)
                    self.agac.setFocus()
                    return

    def eventFilter(self, nesne, olay):
        if nesne is self.arama and olay.type() == QEvent.KeyPress:
            if olay.key() == Qt.Key_Escape:
                if self.arama.text():
                    self.arama.clear()
                elif self._gecici_genis:
                    self.dar_yap(True, kalici=False)
                else:
                    self.agac.setFocus()
                return True
            if olay.key() == Qt.Key_Down:
                self.agac.setFocus()
                return True
        return super().eventFilter(nesne, olay)

    # --- daraltma ---
    def dar_yap(self, dar: bool, kalici: bool = True, animasyon: bool = True) -> None:
        if kalici or dar:
            self._gecici_genis = False
        self.dar = dar
        self.genis_alan.setVisible(not dar)
        self.ray.setVisible(dar)
        self.logo.setVisible(not dar)
        self.yazi.setVisible(not dar)
        self.cikis.setText("" if dar else "Güvenli Çıkış")
        self.cikis.setProperty("dar", dar)
        self.cikis.style().unpolish(self.cikis)
        self.cikis.style().polish(self.cikis)
        hedef = DAR if dar else GENIS
        self._animasyon.stop()
        if animasyon and self.isVisible():
            self._animasyon.setStartValue(self.width())
            self._animasyon.setEndValue(hedef)
            self._animasyon.start()
        else:
            self.setFixedWidth(hedef)
        if kalici:
            self.daraldi.emit(dar)

    def _ray_menusu(self, grup: str) -> None:
        b = self._ray_dugmeleri[grup]
        b.setChecked(grup == self.agac.aktif_grup)
        menu = self.ray_menusu_olustur(grup)
        menu.exec(b.mapToGlobal(QPoint(b.width() + 8, 0)))
        menu.deleteLater()

    def ray_menusu_olustur(self, grup: str) -> QMenu:
        menu = QMenu(self)
        menu.setObjectName("rayMenu")
        baslik = QLabel(grup)
        baslik.setObjectName("rayMenuBaslik")
        wa = QWidgetAction(menu)
        wa.setDefaultWidget(baslik)
        menu.addAction(wa)
        gecerli = self.gecerli()
        for ad in dict(self.gruplar)[grup]:
            a = QAction(ad, menu)
            if ad == gecerli:
                f = a.font()
                f.setBold(True)
                a.setFont(f)
            a.triggered.connect(lambda _=False, s=ad: self.sec(s))
            menu.addAction(a)
        return menu
