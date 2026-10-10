"""Sunucu bilgisayarı için: Windows açılınca arka planda başlama, sistem tepsisi ve tek örnek denetimi.

Sunucu penceresi kapatılınca diğer bilgisayarların bağlantısı kesilmesin diye program tepsiye iner; Güvenli
Çıkış'la kapanır. Program ikinci kez açılmak istenirse yeni örnek açılmaz, çalışan örneğin penceresi öne gelir
(aynı veritabanında iki sunucu ve port çakışması olmasın).
"""
from __future__ import annotations

import getpass
import hashlib
import os
import sys
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .. import config, marka

ARKA_PLAN = "--arka-plan"
RUN_ANAHTARI = r"Software\Microsoft\Windows\CurrentVersion\Run"
DEGER_ADI = config.AD
ESKI_DEGER_ADI = config.ESKI_AD


def baslatma_komutu() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" {ARKA_PLAN}'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    calistirici = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{calistirici}" "{Path(__file__).resolve().parents[2] / "run.py"}" {ARKA_PLAN}'


def _kayit(ad: str) -> str | None:
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_ANAHTARI) as k:
            return winreg.QueryValueEx(k, ad)[0]
    except OSError:
        return None


def otomatik_baslat_acik() -> bool:
    if os.name != "nt":
        return False
    return _kayit(DEGER_ADI) is not None or _kayit(ESKI_DEGER_ADI) is not None


def otomatik_baslat_ayarla(acik: bool) -> None:
    """Bu Windows kullanıcısı oturum açınca MesKoord'u arka planda (tepside) başlatır ya da başlatmaz."""
    if os.name != "nt":
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_ANAHTARI, 0, winreg.KEY_SET_VALUE) as k:
        if acik:
            winreg.SetValueEx(k, DEGER_ADI, 0, winreg.REG_SZ, baslatma_komutu())
        for ad in ((ESKI_DEGER_ADI,) if acik else (DEGER_ADI, ESKI_DEGER_ADI)):
            if _kayit(ad) is not None:
                winreg.DeleteValue(k, ad)


def otomatik_baslatmayi_guncelle() -> None:
    """Kurulu programda: eski adla (KoordMES.exe) yazılmış ya da yolu değişmiş açılış kaydını yeniler."""
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return
    if _kayit(ESKI_DEGER_ADI) is not None or _kayit(DEGER_ADI) not in (None, baslatma_komutu()):
        try:
            otomatik_baslat_ayarla(True)
        except OSError:
            pass


class TekOrnek(QObject):
    """Aynı Windows kullanıcısı ve veri klasörü için tek MesKoord örneği."""

    def __init__(self, goster: Callable[[], None]):
        super().__init__()
        anahtar = hashlib.sha1(f"{getpass.getuser()}|{config.data_dir()}".lower().encode("utf-8")).hexdigest()[:12]
        self.ad = f"{config.AD}-{anahtar}"
        self._goster = goster
        self._sunucu: QLocalServer | None = None

    def baska_ornek_var(self) -> bool:
        """Çalışan bir örnek varsa ona 'öne gel' der ve True döner."""
        s = QLocalSocket()
        s.connectToServer(self.ad)
        if not s.waitForConnected(500):
            return False
        s.write(b"goster")
        s.flush()
        s.waitForBytesWritten(500)
        s.disconnectFromServer()
        return True

    def dinle(self) -> None:
        QLocalServer.removeServer(self.ad)
        self._sunucu = QLocalServer(self)
        self._sunucu.newConnection.connect(self._baglanti)
        self._sunucu.listen(self.ad)

    def _baglanti(self) -> None:
        while self._sunucu is not None and self._sunucu.hasPendingConnections():
            s = self._sunucu.nextPendingConnection()
            s.disconnected.connect(s.deleteLater)
            self._goster()

    def kapat(self) -> None:
        if self._sunucu is not None:
            self._sunucu.close()
            self._sunucu = None


class Tepsi(QSystemTrayIcon):
    def __init__(self, ac: Callable[[], None], cik: Callable[[], None], ag=None):
        super().__init__(marka.uygulama_simgesi())
        self.ag = ag
        menu = QMenu()
        a = QAction(f"{marka.URUN} Penceresini Aç", menu)
        a.triggered.connect(ac)
        menu.addAction(a)
        menu.setDefaultAction(a)
        self.durum = QAction("", menu)
        self.durum.setEnabled(False)
        menu.addAction(self.durum)
        menu.addSeparator()
        c = QAction("Güvenli Çıkış", menu)
        c.triggered.connect(cik)
        menu.addAction(c)
        self._menu = menu
        self.setContextMenu(menu)
        self.activated.connect(lambda neden: ac() if neden in (QSystemTrayIcon.DoubleClick,
                                                                QSystemTrayIcon.Trigger) else None)
        if ag is not None:
            ag.durum_degisti.connect(self.guncelle)
        self.guncelle()

    @staticmethod
    def kullanilabilir() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def guncelle(self) -> None:
        metin = self.ag.durum_metni()[0] if self.ag is not None else "Tek bilgisayar"
        self.durum.setText(metin)
        self.setToolTip(f"{marka.URUN} — {metin}")

    def ilk_bildirim(self) -> None:
        self.showMessage(marka.URUN, f"{marka.URUN} arka planda sunucu olarak çalışmayı sürdürüyor; diğer bilgisayarların "
                                     "bağlantısı kesilmedi. Kapatmak için simgeye sağ tıklayıp Güvenli Çıkış'ı seçin.",
                         QSystemTrayIcon.Information, 8000)
