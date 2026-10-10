import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from test_lisans import _lisans, anahtar  # noqa: E402,F401


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_lisans_penceresi_kod_yukler_ve_ayarlar_kilitlenir(app, db, anahtar, monkeypatch):  # noqa: F811
    from koordmes import lisans
    from koordmes.ui import ortak
    from koordmes.ui.ana_pencere import AnaPencere
    from koordmes.ui.lisans_penceresi import LisansPenceresi
    from koordmes.ui.sayfa_ayarlar import KurumBilgileri

    monkeypatch.setattr(ortak, "bilgi", lambda *a, **k: None)
    monkeypatch.setattr(ortak, "hata", lambda *a, **k: pytest.fail(a[1]))
    w = AnaPencere(db)
    assert "Deneme sürümü" in w.windowTitle()

    p = LisansPenceresi(db, parent=w)
    p._yukle(lisans.kodla(_lisans(anahtar, bitis="")))
    assert p.durum.seviye == lisans.LISANSLI
    w.lisans_guncelle()
    assert "Lisanslı: Deneme MTAL" in w.windowTitle()

    k = KurumBilgileri(db)
    k.show()
    app.processEvents()
    assert k.w["ad"].text() == "Deneme MTAL" and k.w["ad"].isReadOnly() and not k.w["il"].isReadOnly()
    k.w["ad"].setText("Değiştirilmiş")
    k.kaydet()
    assert db.kurum()["ad"] == "Deneme MTAL"


def test_suresi_dolunca_zorunlu_pencere_devam_ettirmez(app, db, anahtar):  # noqa: F811
    from datetime import date

    from koordmes import lisans
    from koordmes.ui.lisans_penceresi import LisansPenceresi

    lisans.durum(db, date(2026, 1, 1))
    d = lisans.durum(db, date(2026, 3, 1))
    p = LisansPenceresi(db, d, zorunlu=True)
    assert not p.devam.isEnabled()
