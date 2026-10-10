"""Marka kimliği: ad, renkler ve simge dosyaları.

MesKoord: MESleki KOORDinasyon. Simge, bir atölye dişlisinin içinde okul ile işletmeyi (iki tepe düğümü)
öğrenci üzerinden (ortadaki turkuaz düğüm) birbirine bağlayan kesintisiz bir çizginin oluşturduğu M harfidir.
Görseller araclar/marka_olustur.py ile çizilir; vektör aslı dagitim/marka/meskoord_simge.svg.

Teknik adlar da MesKoord'dur (Belgeler/MesKoord, MesKoord.exe, ProgramData/MesKoord, ağ tanıtıcısı); 1.3.0
öncesinin KoordMES adlı klasör ve kayıtları config.py ile ilk açılışta taşınır. Kod paketinin adı (koordmes)
yalnızca geliştiricinin gördüğü bir addır.
"""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from . import APP_PUBLISHER

URUN = "MesKoord"
URUN_ASCII = "MesKoord"
URUN_ON, URUN_SON = "Mes", "Koord"   # logotipte iki renk: Mes(leki) + Koord(inasyon)
SLOGAN = "Mesleki Eğitim Koordinasyon ve Yönetim Sistemi"
KISA_TANIM = "Mesleki koordinasyon"
YAYINCI = APP_PUBLISHER

ANA = "#1B2A63"          # gece mavisi: menü, başlıklar, simge zemini
ANA_KOYU = "#101943"
ANA_ACIK = "#2B3F8C"
ANA_ORTA = "#3D56A8"
VURGU = "#1FB5A0"        # turkuaz: seçili menü çizgisi, ayraç, simgedeki öğrenci düğümü
VURGU_KOYU = "#0B7F6F"   # açık zemin üzerinde vurgu yazısı
VURGU_ACIK = "#5FE3CD"
ZEMIN = "#F4F6FB"
CIZGI = "#CBD3E6"
YAZI = "#1A2036"

KLASOR = Path(__file__).with_name("gorseller")
SIMGE = KLASOR / "simge.png"              # 512 px, ayrıntılı
SIMGE_KUCUK = KLASOR / "simge_kucuk.png"  # 64 px, 16-32 piksel için kalınlaştırılmış
LOGO_YATAY = KLASOR / "logo_yatay.png"    # simge + ad, saydam zemin (açık renkli zeminlerde)
ACILIS = KLASOR / "acilis.png"
GORSELLER = (SIMGE, SIMGE_KUCUK, LOGO_YATAY, ACILIS)

KURUM_LOGOSU_AYARI = "kurum_logosu_png"


def uygulama_simgesi():
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QIcon
    ikon = QIcon()
    for boyut in (16, 20, 24, 32):
        ikon.addFile(str(SIMGE_KUCUK), QSize(boyut, boyut))
    for boyut in (48, 64, 128, 256):
        ikon.addFile(str(SIMGE), QSize(boyut, boyut))
    return ikon


def logo_pixmap(yukseklik: int):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap
    pm = QPixmap(str(SIMGE_KUCUK if yukseklik <= 32 else SIMGE))
    return pm.scaledToHeight(yukseklik, Qt.SmoothTransformation)


def kurum_logosu_yaz(db, kaynak: Path | None) -> None:
    """Belgelerde kullanılacak kurum logosunu veritabanına koyar (ağdaki bütün bilgisayarlar görür)."""
    if kaynak is None:
        db.ayar_yaz(KURUM_LOGOSU_AYARI, "")
        return
    from PIL import Image
    im = Image.open(kaynak)
    im.thumbnail((600, 600))
    import io
    tampon = io.BytesIO()
    im.save(tampon, "PNG")
    db.ayar_yaz(KURUM_LOGOSU_AYARI, base64.b64encode(tampon.getvalue()).decode("ascii"))


def kurum_logosu(db) -> Path | None:
    """Ayarlar > Kurum Bilgileri'nde yüklenen kurum logosu; yüklenmemişse None (belgelere logo basılmaz)."""
    from . import config
    try:
        veri = db.ayar(KURUM_LOGOSU_AYARI)
    except Exception:  # noqa: BLE001
        veri = None
    if not veri:
        return None
    ham = base64.b64decode(veri)
    yol = config.data_dir() / "onbellek" / f"kurum_logosu_{hashlib.sha1(ham).hexdigest()[:12]}.png"
    if not yol.exists():
        yol.parent.mkdir(parents=True, exist_ok=True)
        yol.write_bytes(ham)
    return yol


def stil() -> str:
    return f"""
QMainWindow, QWidget {{ font-family: 'Segoe UI'; font-size: 10pt; }}
QWidget#yanPanel {{ background: {ANA}; }}
QLabel#markaAdi {{ color: #ffffff; font-size: 15pt; font-weight: 600; }}
QLabel#markaAlt {{ color: {VURGU_ACIK}; font-size: 8pt; }}
QFrame#markaCizgi {{ background: {VURGU}; max-height: 2px; min-height: 2px; border: none; }}
QTreeWidget#menu {{ background: transparent; color: #ffffff; border: none; outline: 0; }}
QTreeWidget#menu::item, QTreeWidget#menu::item:selected, QTreeWidget#menu::item:hover,
QTreeWidget#menu::branch {{ background: transparent; border: none; }}
QWidget#yanPanel QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px 1px; }}
QWidget#yanPanel QScrollBar::handle:vertical {{ background: #3A4D92; border-radius: 3px; min-height: 28px; }}
QWidget#yanPanel QScrollBar::handle:vertical:hover {{ background: {ANA_ORTA}; }}
QWidget#yanPanel QScrollBar::add-line, QWidget#yanPanel QScrollBar::sub-line,
QWidget#yanPanel QScrollBar::add-page, QWidget#yanPanel QScrollBar::sub-page {{ height: 0; background: none; }}
QLineEdit#menuArama {{ background: #22336F; color: #ffffff; border: 1px solid #34488F; border-radius: 7px;
                      padding: 5px 4px; selection-background-color: {VURGU}; font-size: 9.5pt; }}
QLineEdit#menuArama:focus {{ border-color: {VURGU}; background: #1E2D66; }}
QLabel#aramaSonucYok {{ color: #9AA8D2; padding: 6px 18px; font-size: 9pt; }}
QToolButton#menuDugmesi, QToolButton#rayDugmesi {{ background: transparent; border: none; border-radius: 8px; }}
QToolButton#menuDugmesi:hover, QToolButton#rayDugmesi:hover {{ background: #25387B; }}
QToolButton#rayDugmesi:checked {{ background: {ANA_ACIK}; border-left: 3px solid {VURGU}; }}
QFrame#rayAyrac {{ background: #2C3E80; max-height: 1px; min-height: 1px; border: none; margin: 4px 6px; }}
QMenu#rayMenu {{ background: #ffffff; border: 1px solid {CIZGI}; padding: 4px; }}
QMenu#rayMenu::item {{ padding: 7px 28px 7px 14px; color: {YAZI}; }}
QMenu#rayMenu::item:selected {{ background: #E4EAF8; color: {ANA}; }}
QLabel#rayMenuBaslik {{ color: {VURGU_KOYU}; font-weight: bold; font-size: 8pt; padding: 6px 14px 4px 14px; }}
QPushButton#cikisDugmesi {{ background: transparent; color: #ffffff; border: 1px solid #3A4D92;
                           border-radius: 7px; padding: 7px; margin: 8px 12px 10px 12px; }}
QPushButton#cikisDugmesi[dar="true"] {{ margin: 8px 9px 10px 9px; }}
QPushButton#cikisDugmesi:hover {{ background: #B3261E; border-color: #B3261E; }}
QPushButton {{ padding: 5px 12px; border: 1px solid #b3bedb; border-radius: 4px; background: #f3f5fb; }}
QPushButton:hover {{ background: #e3e9f7; border-color: {ANA_ORTA}; }}
QPushButton:default {{ border: 1px solid {ANA}; }}
QTableView {{ gridline-color: #d9d9d9; selection-background-color: #d2dbf3; selection-color: #000; }}
QHeaderView::section {{ background: #e6ebf7; padding: 4px; border: 1px solid {CIZGI}; font-weight: bold;
                        color: {ANA}; }}
QTabBar::tab {{ padding: 6px 14px; }}
QTabBar::tab:selected {{ color: {ANA}; border-bottom: 2px solid {VURGU}; }}
QGroupBox::title {{ color: {ANA}; }}
QStatusBar {{ background: #eef1f9; }}
"""
