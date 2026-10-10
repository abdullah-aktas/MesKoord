"""Açılışta seçili çalışma biçimine göre veritabanını açar: tek başına, sunucu ya da sunucuya bağlı istemci."""
from __future__ import annotations

import sqlite3
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox, QSplashScreen

from .. import config, hesaplar, marka
from ..ag import protokol as P
from ..ag.istemci import BaglantiBilgisi, BaglantiHatasi, ParmakIziHatasi, ParolaHatasi, UzakDatabase
from ..ag.kesif import KesifYanitlayici
from ..ag.sunucu import KoordSunucu, SunucuDatabase
from ..db import Database
from .ag_koprusu import AgKoprusu
from .giris import giris_sor


class _Acilis:
    def __init__(self, splash: QSplashScreen | None):
        self.splash = splash

    def yaz(self, metin: str) -> None:
        if self.splash is not None:
            self.splash.show()
            self.splash.showMessage(metin, Qt.AlignBottom | Qt.AlignHCenter, Qt.GlobalColor.white)
            QApplication.processEvents()

    def gizle(self) -> None:
        if self.splash is not None:
            self.splash.hide()


def veritabani_ac(splash: QSplashScreen | None = None) -> tuple[Database, AgKoprusu | None] | None:
    """(veritabanı, ağ köprüsü) döndürür; kullanıcı çıkmayı seçerse None."""
    a = P.AgAyarlari.yukle()
    acilis = _Acilis(splash)
    if a.kip == P.KIP_ISTEMCI:
        return _istemci(a, acilis)
    hesaplar.gunlugu_temizle(config.db_path())
    if a.kip == P.KIP_SUNUCU:
        return _sunucu(a, acilis)
    acilis.yaz("Veritabanı açılıyor...")
    return Database(), None


def _sunucu(a: P.AgAyarlari, acilis: _Acilis):
    acilis.yaz("Veritabanı açılıyor ve ağ sunucusu başlatılıyor...")
    db = SunucuDatabase()
    if not a.parola_ozeti:
        acilis.gizle()
        QMessageBox.warning(None, marka.URUN, "Sunucu parolası belirlenmemiş; program şimdilik yalnızca bu "
                                              "bilgisayarda çalışacak. Çok Kullanıcılı Çalışma ekranından parola "
                                              "belirleyin.")
        return db, None
    hata: Exception | None = None
    for _ in range(12):  # yeniden başlatmada eski pencere portu birkaç saniye tutabilir
        try:
            s = KoordSunucu(db.path, a.parola_ozeti, a.port, a.sunucu_adi)
            s.baslat()
            break
        except OSError as e:
            hata = e
            time.sleep(0.5)
    else:
        acilis.gizle()
        QMessageBox.warning(None, "Sunucu başlatılamadı",
                            f"Ağ sunucusu {a.port} portunda başlatılamadı:\n{hata}\n\nBu port başka bir programca "
                            "kullanılıyor ya da MesKoord zaten açık olabilir. Program şimdilik yalnızca bu "
                            "bilgisayarda çalışacak; diğer bilgisayarlar bağlanamaz.")
        return db, None
    db.sunucu = s
    kesif = KesifYanitlayici(s.ad, s.port)
    if not kesif.baslat():
        kesif = None
    return db, AgKoprusu.sunucu_olarak(s, kesif)


def _parola_sor(a: P.AgAyarlari) -> str | None:
    parola, ok = QInputDialog.getText(None, "Sunucu parolası",
                                      f"{a.adres} sunucusunun parolasını yazın:", QLineEdit.Password)
    return parola if ok else None


def _istemci(a: P.AgAyarlari, acilis: _Acilis):
    bilgi = BaglantiBilgisi.ayarlardan(a)
    giris_hatasi = ""
    while True:
        if not bilgi.parola:
            acilis.gizle()
            if a.hesap:
                sonuc = giris_sor(None, f"<b>{a.adres}</b> sunucusuna kendi kullanıcı adınız ve parolanızla girin.",
                                  bilgi.kullanici if bilgi.kullanici != P.varsayilan_kullanici() else "", giris_hatasi)
                if sonuc is None:
                    return _baglanamadi(a, acilis, "Giriş yapılmadı.")
                bilgi.kullanici, bilgi.parola = sonuc
            else:
                parola = _parola_sor(a)
                if parola is None:
                    return _baglanamadi(a, acilis, "Parola girilmedi.")
                bilgi.parola = parola
        acilis.yaz(f"{a.adres} sunucusuna bağlanılıyor...")
        try:
            db = UzakDatabase(bilgi)
            hesap = bool(db.conn.sunucu.get("hesap"))
            if hesap and (not a.hesap or a.kullanici != bilgi.kullanici or a.parola_gizli):
                a.hesap, a.kullanici, a.parola = True, bilgi.kullanici, ""
                a.kaydet()
            return db, AgKoprusu.istemci_olarak(db)
        except ParolaHatasi as e:
            acilis.gizle()
            bilgi.parola = ""
            if e.hesap != a.hesap:
                # Sunucuda hesaplar yeni açıldı ya da kapatıldı: giriş biçimi değişir
                a.hesap = e.hesap
                a.parola = ""
                a.kaydet()
                if e.hesap:
                    giris_hatasi = ""
                    QMessageBox.information(None, "Kişisel giriş", "Sunucuda kişisel kullanıcı hesapları açılmış. "
                                            "Okulun size verdiği kullanıcı adı ve kendi parolanızla girin.")
                else:
                    bilgi.kullanici = P.varsayilan_kullanici()
                continue
            if e.hesap:
                giris_hatasi = str(e)
                continue
            QMessageBox.warning(None, "Parola yanlış", f"{e}\nParolayı yeniden yazın.")
            if a.parola_gizli:
                a.parola = ""
                a.kaydet()
        except ParmakIziHatasi as e:
            acilis.gizle()
            from .sayfa_ag import sunucuyu_dogrula
            kutu = QMessageBox(QMessageBox.Critical, "Sunucu kimliği değişmiş", str(e))
            kabul = kutu.addButton("Yeni Kimliği Doğrula...", QMessageBox.AcceptRole)
            kutu.addButton("Diğer Seçenekler", QMessageBox.RejectRole)
            kutu.exec()
            if kutu.clickedButton() is not kabul:
                return _baglanamadi(a, acilis, "Sunucunun kimliği doğrulanmadı.")
            iz = sunucuyu_dogrula(None, a.adres, a.sunucu_portu)
            if not iz:
                return _baglanamadi(a, acilis, "Sunucunun kimliği doğrulanmadı.")
            a.parmak_izi = bilgi.parmak_izi = iz
            a.kaydet()
        except (BaglantiHatasi, sqlite3.Error, OSError) as e:
            sonuc = _baglanamadi(a, acilis, str(e), yeniden=True)
            if sonuc != "yeniden":
                return sonuc


def _baglanamadi(a: P.AgAyarlari, acilis: _Acilis, neden: str, yeniden: bool = False):
    acilis.gizle()
    kutu = QMessageBox(QMessageBox.Warning, "Sunucuya bağlanılamadı",
                       f"{a.adres}:{a.sunucu_portu} sunucusuna bağlanılamadı.\n\n{neden}")
    kutu.setInformativeText("Sunucu bilgisayarının açık olduğunu, MesKoord'un orada çalıştığını ve iki bilgisayarın "
                            "aynı ağda olduğunu denetleyin.\n\n'Bu Bilgisayarın Verisiyle Aç' seçilirse bu oturumda "
                            "yapılan değişiklikler sunucuya gitmez.")
    tekrar = kutu.addButton("Yeniden Dene", QMessageBox.AcceptRole) if yeniden else None
    yerel = kutu.addButton("Bu Bilgisayarın Verisiyle Aç", QMessageBox.DestructiveRole)
    kutu.addButton("Çık", QMessageBox.RejectRole)
    kutu.exec()
    if tekrar is not None and kutu.clickedButton() is tekrar:
        return "yeniden"
    if kutu.clickedButton() is yerel:
        return Database(), None
    return None
