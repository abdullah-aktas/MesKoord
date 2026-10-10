import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _sinif(db, seviye=10, dal="Yazılım Geliştirme"):
    alan = db.insert("alanlar", {"ad": "Bilişim Teknolojileri"})
    dal_id = db.insert("dallar", {"alan_id": alan, "ad": dal}) if dal else None
    return db.insert("siniflar", {"ad": f"{seviye}-A", "seviye": seviye, "program": "MTAL-ATP", "alan_id": alan,
                                  "dal_id": dal_id})


def test_zorunlu_ders_diyalogu_secilenleri_acar(app, db):
    from PySide6.QtCore import Qt
    from koordmes.services import cerceve
    from koordmes.ui.sayfa_cerceve import ZorunluDersDialog

    sid = _sinif(db)
    d = ZorunluDersDialog(db, sid, cerceve.sinif_programi(db, sid))
    assert d.tablo.dersler and not d.dal_kaydet.isVisibleTo(d)
    satir, ders = next(iter(d.tablo.dersler.items()))
    d.tablo.item(satir, 0).setCheckState(Qt.Unchecked)
    d._uygula()
    assert d.result() and d.sonuc is not None
    adlar = {r["ad"] for r in db.q("SELECT d.ad FROM ders_atamalari da JOIN dersler d ON d.id = da.ders_id")}
    assert ders.ad not in adlar and len(adlar) == len(d.tablo.dersler) - 1


def test_dal_secilmeyen_sinifta_dal_da_kaydedilir(app, db):
    from koordmes.services import cerceve
    from koordmes.ui.sayfa_cerceve import ZorunluDersDialog

    sid = _sinif(db, dal=None)
    e = cerceve.sinif_programi(db, sid)
    d = ZorunluDersDialog(db, sid, e)
    d.secim.setCurrentIndex(d.secim.count() - 1)
    assert d.dal_kaydet.isVisibleTo(d) and d.dal_kaydet.isChecked()
    d._uygula()
    dal = cerceve.sinif_bilgisi(db, sid)["dal"]
    assert dal == d.program.dal and cerceve.uyumsuzluklar(db) == []


def test_cerceve_sayfasi_ve_sinif_kaydi(app, db, monkeypatch):
    from koordmes.services import cerceve
    from koordmes.ui import ortak, sayfa_cerceve
    from koordmes.ui.sayfa_cerceve import CerceveSayfasi

    monkeypatch.setattr(ortak, "bilgi", lambda *a, **k: None)
    monkeypatch.setattr(ortak, "onay", lambda *a, **k: True)
    sid = _sinif(db, seviye=11)
    p = CerceveSayfasi(db)
    p.show()
    app.processEvents()
    assert p.secili is not None and p.tablo.rowCount() > 5
    p.siniftan()
    assert (p.secili.seviye, p.secili.alan, p.secili.dal) == (11, "Bilişim Teknolojileri", "Yazılım Geliştirme")
    p.tanimlara_ekle()
    assert db.q1("SELECT COUNT(*) c FROM dallar")["c"] >= 2

    acilan = []
    monkeypatch.setattr(sayfa_cerceve.ZorunluDersDialog, "exec",
                        lambda self: (acilan.append(self.sinif_id), self._uygula(), self.result())[-1])
    s = dict(db.q1("SELECT * FROM siniflar WHERE id = ?", (sid,)))
    sayfa_cerceve.sinif_kaydedildi(None, db, sid, s, s)
    assert not acilan, "izlenen alanlar değişmeden diyalog açılmaz"
    sayfa_cerceve.sinif_kaydedildi(None, db, sid, s, None)
    assert acilan == [sid] and cerceve.uyumsuzluklar(db) == []
