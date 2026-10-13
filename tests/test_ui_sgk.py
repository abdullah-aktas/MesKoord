import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _sec(view, satirlar):
    from PySide6.QtCore import QItemSelectionModel
    sm = view.selectionModel()
    sm.clearSelection()
    for r in satirlar:
        sm.select(view.model().index(r, 0), QItemSelectionModel.Select | QItemSelectionModel.Rows)


def test_karsilastirma_ekrani(app, ornek_db, tmp_path):
    from openpyxl import Workbook

    from koordmes.services import sigorta
    from koordmes.ui.sayfa_sgk_ucret import SgkSayfasi

    db = ornek_db
    okul = sigorta.aylik_liste(db, 2026, 10)
    wb = Workbook()
    ws = wb.active
    ws.append(["Dönem: 2026/10"])
    ws.append(["T.C. Kimlik No", "Adı", "Soyadı", "Belge Türü", "Prim Ödeme Günü"])
    hedef = okul[0]
    for s in okul:
        ws.append([s.tc, s.ad, s.soyad + "can" if s is hedef else s.soyad, s.belge_turu, s.gun])
    wb.save(tmp_path / "aphb.xlsx")

    sayfa = SgkSayfasi(db)
    k = sayfa.widget(3)
    sayfa.setCurrentIndex(3)
    sayfa.show()
    k.yukle([tmp_path / "aphb.xlsx"])
    assert k.sonuc is not None and k.ay.deger() == (2026, 10)
    satir = next(i for i, f in enumerate(k.sonuc.farklar) if f.tur == "Ad/soyad farklı")
    _sec(k.view, [k.proxy.mapFromSource(k.model.index(satir, 0)).row()])
    k.duzelt(sormadan=True)
    assert db.q1("SELECT soyad FROM ogrenciler WHERE id = ?", (hedef.ogrenci_id,))["soyad"].endswith("can")
    assert not any(f.tur == "Ad/soyad farklı" for f in k.sonuc.farklar)


def test_risk_ekrani(app, db):
    from koordmes.ui.sayfa_sgk_ucret import SgkSayfasi

    sinif = db.insert("siniflar", {"ad": "11-A"})
    ogr = db.insert("ogrenciler", {"ad": "Ali", "soyad": "Kaya", "tc": "10000000078", "sinif_id": sinif,
                                   "dogum_tarihi": "2004-01-01"})
    db.insert("yerlestirmeler", {"ogrenci_id": ogr, "baslangic": "2026-01-05", "sigorta_giris_bildirildi": 1,
                                 "sigorta_giris_bildirim_tarihi": "2026-01-02"})
    sayfa = SgkSayfasi(db)
    r = sayfa.widget(4)
    sayfa.setCurrentIndex(4)
    sayfa.show()
    i = next(i for i, x in enumerate(r.riskler) if x.eylem == "yukumlu_kaldir")
    _sec(r.view, [r.proxy.mapFromSource(r.model.index(i, 0)).row()])
    r.uygula(sormadan=True)
    assert db.q1("SELECT bakmakla_yukumlu FROM ogrenciler WHERE id = ?", (ogr,))["bakmakla_yukumlu"] == 0
    assert not any(x.eylem == "yukumlu_kaldir" for x in r.riskler)
