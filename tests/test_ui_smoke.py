import os

import pytest

from conftest import pencereyi_kapat

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_tum_sayfalar_acilir(app, ornek_db):
    from PySide6.QtWidgets import QTabWidget
    from koordmes.ui.ana_pencere import AnaPencere

    w = AnaPencere(ornek_db)
    w.show()
    for ad in w.sayfa_adlari():
        sayfa = w.git(ad)
        app.processEvents()
        assert sayfa is w.gecerli_sayfa()
        if isinstance(sayfa, QTabWidget):
            for i in range(sayfa.count()):
                sayfa.setCurrentIndex(i)
                app.processEvents()
    assert len(w.sayfa) == len(w.uretici)
    pencereyi_kapat(w)


def test_yan_menu_akordeon_arama_ve_serit(app, ornek_db):
    from koordmes.ui.ana_pencere import AnaPencere

    w = AnaPencere(ornek_db)
    w.show()
    yan = w.yan
    yan.dar_yap(False, animasyon=False)
    acik = lambda: [g for g, o in yan._grup_ogesi.items() if o.isExpanded()]
    w.git("SGK Sigorta İşlemleri")
    assert acik() == ["İŞLETMELERDE MESLEKİ EĞİTİM"] and yan.agac.aktif_grup == "İŞLETMELERDE MESLEKİ EĞİTİM"
    yan._tiklandi(yan._grup_ogesi["TANIMLAR"])
    assert acik() == ["TANIMLAR"]
    yan._tiklandi(yan._grup_ogesi["TANIMLAR"])
    assert acik() == []

    yan.arama.setText("ucret")
    gorunen = [ad for ad, o in yan._sayfa_ogesi.items() if not o.isHidden() and not o.parent().isHidden()]
    assert gorunen == ["Öğrenci Ücreti ve Devlet Katkısı"]
    yan.arama.setText("evrak")
    assert not yan._grup_ogesi["EVRAK"].isHidden() and yan._grup_ogesi["EVRAK"].childCount() == 2
    yan.arama.setText("zzzz")
    assert yan.sonuc_yok.isVisibleTo(yan)
    yan.arama.setText("puantaj")
    yan._ilk_sonucu_ac()
    assert yan.arama.text() == "" and yan.gecerli() == "Ek Ders Puantajı"
    assert type(w.gecerli_sayfa()).__name__ == "EkDersSayfasi"
    assert acik() == ["PERSONEL"]

    w.a_dar.trigger()
    assert yan.dar and w.ayar.value("menu_dar", type=bool)
    menu = yan.ray_menusu_olustur("EVRAK")
    menu.actions()[1].trigger()
    assert yan.gecerli() == "Belge Üretimi" and yan._ray_dugmeleri["EVRAK"].isChecked()
    yan.ara_odakla()
    assert not yan.dar
    yan.arama.setText("dallar")
    yan._ilk_sonucu_ac()
    assert yan.dar and yan.gecerli() == "Dallar"
    w.a_dar.trigger()
    assert not yan.dar and not w.ayar.value("menu_dar", type=bool)
    pencereyi_kapat(w)

    w2 = AnaPencere(ornek_db)
    assert type(w2.gecerli_sayfa()).__name__ == "CrudSayfasi" and w2.yan.gecerli() == "Dallar"
    w2.git("Asistan")
    pencereyi_kapat(w2)


def test_akis_duzeni_satir_kirar(app):
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget
    from koordmes.ui import ortak

    w = QWidget()
    v = QVBoxLayout(w)
    akis = ortak.AkisDuzeni()
    dugmeler = [QPushButton(f"Uzunca Bir Düğme {i}") for i in range(8)]
    for b in dugmeler:
        akis.addWidget(b)
    akis.addStretch()
    v.addLayout(akis)
    assert w.minimumSizeHint().width() < sum(b.sizeHint().width() for b in dugmeler) / 3
    w.resize(400, 300)
    w.show()
    app.processEvents()
    assert len({b.y() for b in dugmeler}) > 2
    assert all(b.geometry().right() <= 400 for b in dugmeler)


def test_program_tablosu_cizer(app, ornek_db):
    from koordmes.ui.sayfa_program import ProgramTablosu

    p = ProgramTablosu(ornek_db)
    p.show()
    app.processEvents()
    dolu = sum(1 for r in range(p.tablo.rowCount()) for c in range(p.tablo.columnCount()) if p.tablo.item(r, c))
    assert dolu > 0


def test_pdf_cikti(app, ornek_db, tmp_path):
    from koordmes.ui import ortak

    yol = ortak.html_pdf(ortak.html_tablo("Deneme", ["A", "B"], [["ç", "ş"]]), tmp_path / "x.pdf")
    assert yol.exists() and yol.stat().st_size > 500
