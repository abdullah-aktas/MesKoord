import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_kilavuz_dosyasi_var_ve_menudeki_ekranlari_anlatir(app, db):
    from koordmes.ui.ana_pencere import AnaPencere
    from koordmes.ui.kilavuz import kilavuz_metni
    from conftest import pencereyi_kapat

    metin = kilavuz_metni()
    w = AnaPencere(db)
    eksik = [ad for ad in w.sayfa_adlari() if ad not in metin]
    pencereyi_kapat(w)
    assert not eksik, f"Kılavuzda anlatılmayan menü ekranları: {eksik}"


def test_kilavuz_penceresi_icindekiler_arama_ve_pdf(app, tmp_path):
    from koordmes.ui.kilavuz import KilavuzPenceresi, pdf_yaz

    p = KilavuzPenceresi()
    assert p.icindekiler.count() > 10
    p._basliga_git(p.icindekiler.item(p.icindekiler.count() - 1))
    assert p.metin.verticalScrollBar().value() > 0
    p.ara.setText("Güvenli Çıkış")
    assert p.bul() and p.metin.textCursor().selectedText() == "Güvenli Çıkış"
    p.ara.setText("bu-metin-kilavuzda-yok-xyz")
    assert not p.bul()
    yol = pdf_yaz(p.metin.document(), tmp_path / "k.pdf")
    assert yol.stat().st_size > 20_000
