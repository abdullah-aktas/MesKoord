import os

import pytest

from conftest import pencereyi_kapat

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def sessiz(monkeypatch):
    """Modal ileti kutularını kaydedip geçer."""
    from koordmes.ui import eylem, ortak
    iletiler = []
    monkeypatch.setattr(ortak, "bilgi", lambda p, m, *a: iletiler.append(m))
    monkeypatch.setattr(ortak, "hata", lambda p, m, *a: iletiler.append("HATA " + m))
    monkeypatch.setattr(ortak, "onay", lambda *a: True)
    monkeypatch.setattr(eylem, "sonuc_goster", lambda p, w, s: iletiler.append(s.mesaj))
    return iletiler


def test_gezinme_hedefleri_menude_var(app, ornek_db):
    from koordmes.services import denetim, surecler
    from koordmes.ui.ana_pencere import AnaPencere

    w = AnaPencere(ornek_db)
    adlar = set(w.sayfa_adlari())
    hedefler = {e.git for e in surecler.EYLEMLER.values() if e.git}
    hedefler |= {b.git for b in denetim.denetle(ornek_db) if b.git}
    assert hedefler - adlar == set()
    assert w.git("Veri Aktarımı") is not None
    pencereyi_kapat(w)


def test_asistan_komutlari_ve_linkler(app, ornek_db, sessiz):
    from koordmes.ui.ana_pencere import AnaPencere

    w = AnaPencere(ornek_db)
    w.show()
    app.processEvents()
    a = w.git("Asistan")
    a._karsila()
    for komut in ["yardım", "ekim sgk listesi", "denetim", "12-A", "istatistik", "aylık süreç", "parametreler"]:
        a.gonder(komut)
    metin = a.log.toPlainText()
    assert "SGK prim hizmet listesi" in metin and "Sınıf: 12-A" in metin
    assert a._linkler and all(t in ("komut", "git", "kart", "eylem", "file", "klasor", "aktar")
                              for t, _, _ in a._linkler)
    kart = next(i for i, (t, _, _) in enumerate(a._linkler) if t == "kart")
    from PySide6.QtCore import QUrl
    a._link(QUrl(f"act:{kart}"))
    a.eylem_calistir("koordinator")
    assert "görevlendirildi" in a.log.toPlainText()
    a.sekmeler.setCurrentIndex(1)
    app.processEvents()
    assert a.denetim.yapildi and a.denetim.tablo.rowCount() > 0
    assert a.surec.tablo.rowCount() > 0
    pencereyi_kapat(w)


def test_asistan_surukle_birak_aktarim(app, ornek_db, sessiz, tmp_path):
    from koordmes.services.excel_io import tablo_yaz
    from koordmes.ui.sayfa_asistan import AsistanSayfasi

    yol = tmp_path / "e-Okul öğrenci listesi.xlsx"
    tablo_yaz(yol, ["Öğrenci No", "T.C. Kimlik No", "Adı", "Soyadı", "Sınıfı"],
              [[9001, "", "Deniz", "Yeni", "9. Sınıf / C Şubesi"]])
    a = AsistanSayfasi(ornek_db)
    a.dosyalari_al([str(yol)])
    assert "Öğrenciler" in a.log.toPlainText() and a._bekleyen
    assert ornek_db.q1("SELECT COUNT(*) FROM ogrenciler WHERE okul_no = '9001'")[0] == 0
    a._aktar_onayla()
    assert ornek_db.q1("SELECT COUNT(*) FROM ogrenciler WHERE okul_no = '9001'")[0] == 1
    assert ornek_db.q1("SELECT COUNT(*) FROM siniflar WHERE ad = '9-C'")[0] == 1


def test_aktarim_sihirbazi(app, ornek_db, sessiz, tmp_path):
    from PySide6.QtCore import Qt
    from koordmes.services.excel_io import tablo_yaz
    from koordmes.ui.sayfa_aktarim import AktarimSayfasi

    yol = tmp_path / "liste.xlsx"
    tablo_yaz(yol, ["Sıra", "Ad Soyad", "Branş", "Telefon"], [[1, "Mehmet Deneme", "Elektrik", "0555"]])
    s = AktarimSayfasi(ornek_db)
    s.show()
    assert s.dosyalari_ekle([str(yol)]) == 1
    o = s.ogeler[0]
    s.tur.setCurrentIndex(s.tur.findData("ogretmenler"))
    assert o.anahtar == "ogretmenler" and o.hazir
    s.aktar_secili(True)
    assert ornek_db.q1("SELECT COUNT(*) FROM ogretmenler WHERE soyad = 'Deneme'")[0] == 0
    assert s.sonuc_model.rowCount() == 1
    assert s.liste.item(0).checkState() == Qt.Checked
    s.aktar_isaretli(False)
    assert ornek_db.q1("SELECT COUNT(*) FROM ogretmenler WHERE soyad = 'Deneme'")[0] == 1
    s.close()
