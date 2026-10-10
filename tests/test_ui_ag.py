"""Ağ modunda ana pencere: başka bilgisayardaki değişiklik açık ekrana anında yansır."""
import os
import time

import pytest
from conftest import baglanti_bilgisi, pencereyi_kapat

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _bekle(app, kosul, sure=8.0):
    bitis = time.monotonic() + sure
    while time.monotonic() < bitis:
        app.processEvents()
        if kosul():
            return True
        time.sleep(0.02)
    return False


def _satir_sayisi(w):
    return w.gecerli_sayfa().model.rowCount()


def test_sunucu_penceresi_istemci_degisikligini_gosterir(app, sunucu):
    from koordmes.ag.istemci import UzakDatabase
    from koordmes.ui.ag_koprusu import AgKoprusu
    from koordmes.ui.ana_pencere import AnaPencere
    ag = AgKoprusu.sunucu_olarak(sunucu, None)
    w = AnaPencere(sunucu.yerel_db, ag)
    w.git("Alanlar")
    assert _satir_sayisi(w) == 0
    bilgi = baglanti_bilgisi(sunucu, "ayse")
    bilgi.istemci = "diger-bilgisayar"
    istemci = UzakDatabase(bilgi)
    try:
        istemci.insert("alanlar", {"ad": "Gıda Teknolojisi"})
        assert _bekle(app, lambda: _satir_sayisi(w) == 1), "sunucu ekranı yenilenmedi"
        assert "ayse" in w.statusBar().currentMessage()
        assert _bekle(app, lambda: any("ayse" in k for k in ag.kullanici_listesi()))
        assert "Sunucu açık" in w.durum_ag.text()
        assert "ayse" in ag.cikis_uyarisi()
        sayfa = w.git("Çok Kullanıcılı Çalışma (Ağ)") or w.gecerli_sayfa()
        assert sayfa.kullanicilar.rowCount() >= 2
    finally:
        istemci.close()
        pencereyi_kapat(w)


def test_istemci_penceresi_sunucu_degisikligini_gosterir(app, sunucu):
    from koordmes.ag.istemci import UzakDatabase
    from koordmes.ui.ag_koprusu import AgKoprusu
    from koordmes.ui.ana_pencere import AnaPencere
    db = UzakDatabase(baglanti_bilgisi(sunucu, "mehmet"))
    ag = AgKoprusu.istemci_olarak(db)
    w = AnaPencere(db, ag)
    try:
        w.git("Alanlar")
        assert _bekle(app, ag.bagli)
        assert "SINAMA sunucusuna bağlı" in w.durum_ag.text()
        sunucu.yerel_db.insert("alanlar", {"ad": "Bilişim"})
        assert _bekle(app, lambda: _satir_sayisi(w) == 1), "istemci ekranı yenilenmedi"
        # kendi yaptığımız değişiklik için bildirim gelmez ama ekranı zaten biz yeniledik
        db.insert("alanlar", {"ad": "Muhasebe"})
        assert sunucu.yerel_db.q1("SELECT COUNT(*) FROM alanlar")[0] == 2
    finally:
        pencereyi_kapat(w)
        ag.kapat()
        db.close()
