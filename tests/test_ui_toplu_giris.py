import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_yapistir_denetle_kaydet(app, db, monkeypatch):
    from koordmes.services import sigorta, toplu_giris
    from koordmes.ui import ortak
    from koordmes.ui.sayfa_toplu_giris import TopluGirisSayfasi

    monkeypatch.setattr(ortak, "onay", lambda *a, **k: True)
    monkeypatch.setattr(ortak, "bilgi", lambda *a, **k: None)
    s = TopluGirisSayfasi(db)
    s.show()
    app.clipboard().setText("Sınıf\tAdı\tSoyadı\tİşletme Adı\tBaşlama Tarihi\r\n"
                            "11-A\tAyşe\tYılmaz\tUsta Mobilya\t01.09.2026\r\n"
                            "11-A\tAli\tKaya\tUsta Mobilya\t31.02.2026\r\n")
    s.yapistir()
    dolu = toplu_giris.dolu_satirlar(s.satirlar())
    assert dolu == [0, 1]
    assert s._deger(0, 1) == "Ayşe Yılmaz"

    assert s.kontrol() is False
    assert s.tablo.item(1, 8).background().color() == ortak.RENK_KRITIK

    s.tablo.item(1, 8).setText("15.09.2026")
    assert s.kontrol() is True
    s.kaydet(False)
    assert {o.ad for o in sigorta.aylik_liste(db, 2026, 9)} == {"Ayşe", "Ali"}
    assert toplu_giris.dolu_satirlar(s.satirlar()) == []
    assert toplu_giris.taslak_yukle(s.tur) == []


def _belge(tmp_path):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for r in [["Sınıfı : 11-B"], ["Okul No", "Adı Soyadı", "Veli Telefonu"], ["701", "Ece Nur Sarı", "0532 111 22 33"],
              ["702", "Kaan Ok", ""], [None, "Okul Müdürü", None]]:
        ws.append(r)
    wb.save(tmp_path / "eokul.xlsx")
    return str(tmp_path / "eokul.xlsx")


def test_belge_yukle_tabloya_al(app, db, tmp_path, monkeypatch):
    from koordmes.ui import ortak
    from koordmes.ui.sayfa_toplu_giris import TopluGirisSayfasi

    monkeypatch.setattr(ortak, "onay", lambda *a, **k: True)
    monkeypatch.setattr(ortak, "bilgi", lambda *a, **k: None)
    s = TopluGirisSayfasi(db)
    s.belge_yukle([_belge(tmp_path)], secim="tablo")
    assert s.tur.anahtar == "ogrenciler"
    anahtarlar = [x.anahtar for x in s.tur.sutunlar]
    assert s._deger(0, anahtarlar.index("ad_soyad")) == "Ece Nur Sarı"
    assert s._deger(1, anahtarlar.index("sinif")) == "11-B"
    assert s._deger(2, anahtarlar.index("ad_soyad")) == ""
    s.kaydet(False)
    assert db.q1("SELECT COUNT(*) n FROM ogrenciler")["n"] == 2


def test_belge_yukle_akilli_kaydet(app, db, tmp_path):
    from koordmes.ui.sayfa_toplu_giris import TopluGirisSayfasi

    s = TopluGirisSayfasi(db)
    s.belge_yukle([_belge(tmp_path)], secim="kaydet")
    rows = db.q("SELECT o.ad, o.veli_tel, s.ad AS sinif FROM ogrenciler o JOIN siniflar s ON s.id = o.sinif_id")
    assert {(r["ad"], r["sinif"]) for r in rows} == {("Ece Nur", "11-B"), ("Kaan", "11-B")}
    assert "akıllı kaydedildi" in s.ozet.text()


def test_tek_degeri_secili_hucrelere_yapistir_ve_asagi_doldur(app, db):
    from PySide6.QtCore import QItemSelectionModel
    from koordmes.ui.sayfa_toplu_giris import TopluGirisSayfasi

    s = TopluGirisSayfasi(db)
    for i in range(3):
        s._yaz(i, 1, f"Öğrenci {i}")
    s._yaz(0, 6, "Usta Mobilya")
    sm = s.tablo.selectionModel()
    for i in range(3):
        sm.select(s.tablo.model().index(i, 6), QItemSelectionModel.Select)
    s.asagi_doldur()
    assert [s._deger(i, 6) for i in range(3)] == ["Usta Mobilya"] * 3

    app.clipboard().setText("01.09.2026")
    s.tablo.clearSelection()
    for i in range(3):
        sm.select(s.tablo.model().index(i, 8), QItemSelectionModel.Select)
    s.yapistir()
    assert [s._deger(i, 8) for i in range(3)] == ["01.09.2026"] * 3
