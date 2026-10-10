"""MesKoord başlatıcı."""
import sqlite3
import sys
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLocale, QProcess, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QSplashScreen

from koordmes import APP_NAME, __version__, config, hesaplar, lisans, marka
from koordmes.ag import protokol as P
from koordmes.services import belgeler
from koordmes.ui import giris, tepsi
from koordmes.ui.ag_baslat import veritabani_ac
from koordmes.ui.ana_pencere import AnaPencere
from koordmes.ui.lisans_penceresi import LisansPenceresi

HATA_GUNLUGU = "hata_gunlugu.txt"


def hata_kaydet(metin: str) -> None:
    try:
        with (config.data_dir() / HATA_GUNLUGU).open("a", encoding="utf-8") as f:
            f.write(f"\n===== {datetime.now():%d.%m.%Y %H:%M:%S}  sürüm {__version__} =====\n{metin}")
    except OSError:
        pass


def kendini_sina(rapor: Path) -> int:
    """Paketlenmiş programda bütün bileşenlerin bulunduğunu denetler (surum_hazirla.py çalıştırır)."""
    satirlar, kod = [f"{marka.URUN} {__version__}"], 0
    denetimler = [
        ("arayüz sayfaları", lambda: __import__("koordmes.ui.ana_pencere")),
        ("tarayıcı bileşeni", lambda: __import__("PySide6.QtWebEngineWidgets")),
        ("Excel", lambda: __import__("openpyxl")),
        ("Word", lambda: __import__("docx")),
        ("eski Excel", lambda: __import__("xlrd")),
        ("PDF", lambda: __import__("pdfplumber")),
        ("marka görselleri", lambda: [p.stat() for p in marka.GORSELLER]),
        ("ağ bileşenleri", lambda: (__import__("koordmes.ag.sunucu"), __import__("koordmes.ag.istemci"),
                                    __import__("ssl"), __import__("koordmes.ui.sayfa_ag"))),
        ("kullanıcı hesapları", lambda: (__import__("koordmes.hesaplar"), __import__("koordmes.ui.giris"),
                                         __import__("koordmes.ui.sayfa_kullanicilar"))),
        ("yedekleme ve tepsi", lambda: (__import__("koordmes.yedekleme"), __import__("koordmes.ui.tepsi"),
                                        __import__("PySide6.QtNetwork"))),
        ("açık anahtar", lambda: lisans.ACIK_ANAHTARLAR or (_ for _ in ()).throw(RuntimeError("boş"))),
        ("kullanım kılavuzu", lambda: __import__("koordmes.ui.kilavuz", fromlist=["kilavuz_yolu"]).kilavuz_yolu()
         .stat()),
        ("çerçeve öğretim programları", lambda: __import__("koordmes.services.cerceve", fromlist=["programlar"])
         .programlar() or (_ for _ in ()).throw(RuntimeError("boş"))),
    ]

    def imza_denetimi():
        try:
            lisans.dogrula({a: "x" for a in lisans.ZORUNLU_ALANLAR} | {"urun": lisans.URUN, "anahtar": "KM1",
                                                                       "imza": "AAAA"})
        except lisans.LisansHatasi as e:
            if "imza" not in str(e).lower() and "tanınmayan" not in str(e):
                raise
    denetimler.append(("imza doğrulama", imza_denetimi))
    for ad, fn in denetimler:
        try:
            fn()
            satirlar.append(f"TAMAM  {ad}")
        except Exception as e:  # noqa: BLE001
            satirlar.append(f"HATA   {ad}: {e!r}")
            kod = 1
    rapor.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    return kod


def main() -> int:
    if len(sys.argv) >= 3 and sys.argv[1] == "--kendini-sina":
        return kendini_sina(Path(sys.argv[2]))
    arka_plan = tepsi.ARKA_PLAN in sys.argv
    QLocale.setDefault(QLocale(QLocale.Turkish, QLocale.Turkey))
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setWindowIcon(marka.uygulama_simgesi())
    pencere_ref: list[AnaPencere] = []
    tek = tepsi.TekOrnek(lambda: pencere_ref[0].tepsiden_ac() if pencere_ref else None)
    if tek.baska_ornek_var():
        return 0
    tek.dinle()
    tepsi.otomatik_baslatmayi_guncelle()
    a = P.AgAyarlari.yukle()
    tepside = a.kip == P.KIP_SUNUCU and a.tepside_calis and tepsi.Tepsi.kullanilabilir()
    arka_plan = arka_plan and tepside
    splash = QSplashScreen(QPixmap(str(marka.ACILIS)))
    if not arka_plan:
        splash.show()
        app.processEvents()

    def hata_yakala(tur, deger, iz):
        metin = "".join(traceback.format_exception(tur, deger, iz))
        if isinstance(deger, sqlite3.DatabaseError) and hesaplar.yetki_hatasi_mi(deger):
            QMessageBox.warning(None, "Yetki yok", f"{hesaplar.YETKI_YOK}\n\nBu işlem gerekiyorsa okuldaki "
                                "yönetici hesabı sahibinden yetki isteyin.")
            return
        print(metin, file=sys.stderr)
        hata_kaydet(metin)
        if isinstance(deger, sqlite3.OperationalError):
            ileti = str(deger)
            if "Sunucu" in ileti:
                QMessageBox.warning(None, "Sunucu bağlantısı",
                                    f"{ileti}\n\nBağlantı geri gelince işlemi yeniden deneyin; durum çubuğunun "
                                    "solunda bağlantı durumu görünür.")
                return
            if "locked" in ileti or "busy" in ileti:
                QMessageBox.warning(None, "Veritabanı meşgul",
                                    "Başka bir kullanıcı ya da işlem uzun süredir veritabanına yazıyor. Biraz "
                                    "sonra yeniden deneyin.")
                return
        QMessageBox.critical(None, "Beklenmeyen hata",
                             metin[-3000:] + f"\n\nAyrıntı: {config.data_dir() / HATA_GUNLUGU}")

    sys.excepthook = hata_yakala
    acilan = veritabani_ac(None if arka_plan else splash)
    if acilan is None:
        tek.kapat()
        return 0
    db, ag = acilan

    def kapat():
        tek.kapat()
        if ag is not None:
            ag.kapat()
        try:
            db.close()
        except Exception:  # noqa: BLE001
            pass

    durum = lisans.durum(db)
    if not durum.calisir or durum.seviye == lisans.TOLERANS or durum.tarih_uyarisi:
        splash.hide()
        pencere = LisansPenceresi(db, durum, zorunlu=True)
        if pencere.exec() != QDialog.Accepted or not pencere.durum.calisir:
            kapat()
            return 0
        durum = pencere.durum
    if durum.seviye in (lisans.LISANSLI, lisans.TOLERANS):
        lisans.kurum_uygula(db, durum.lisans)
    if arka_plan and hesaplar.hesaplar_acik(db):
        # Windows açılışında kimse giriş yapmadan sunucu çalışır; pencere tepsiden açılırken giriş sorulur
        db.kimlik_ata(hesaplar.Kimlik("Sunucu (arka plan)", hesaplar.IZLEYICI, hesapli=True))
    elif not arka_plan:
        splash.hide()
        if not giris.kullanici_girisi(db):
            kapat()
            return 0
        splash.show()
    splash.showMessage("Belge şablonları hazırlanıyor...", Qt.AlignBottom | Qt.AlignHCenter, Qt.GlobalColor.white)
    belgeler.tum_sablonlari_hazirla()
    w = AnaPencere(db, ag)
    pencere_ref.append(w)
    # Windows kapanırken ya da oturum kapatılırken pencere tepsiye inip kapanışı engellemesin
    app.commitDataRequest.connect(lambda _oturum: setattr(w, "_cikis_hazir", True))
    if tepside:
        app.setQuitOnLastWindowClosed(False)
        w.tepsi = tepsi.Tepsi(w.tepsiden_ac, w.guvenli_cikis, ag)
        w.tepsi.show()
    if arka_plan:
        splash.close()
    else:
        w.show()
        splash.finish(w)
    kod = app.exec()
    kapat()
    if w.yeniden_baslat:
        program, argumanlar = (sys.executable, []) if getattr(sys, "frozen", False) else \
            (sys.executable, [str(Path(__file__).resolve())])
        QProcess.startDetached(program, argumanlar)
    return kod


if __name__ == "__main__":
    sys.exit(main())
