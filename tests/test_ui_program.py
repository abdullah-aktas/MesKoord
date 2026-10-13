import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_program_ekrani_belgeden_yukler(app, db, tmp_path):
    from openpyxl import Workbook

    from koordmes.ui.sayfa_program import ProgramSayfasi, hucre_metni

    wb = Workbook()
    ws = wb.active
    ws.append(["10-A Sınıfı Haftalık Ders Programı"])
    ws.append([None, "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"])
    ws.append(["1. Ders", "Kimya\nDeniz Ak", None, None, None, None])
    ws.append(["2. Ders", "Kimya\nDeniz Ak", None, None, "Fizik\nEce Su", None])
    wb.save(tmp_path / "program.xlsx")

    sayfa = ProgramSayfasi(db)
    p = sayfa.widget(2)
    sayfa.setCurrentIndex(2)
    sayfa.show()
    sonuclar = p.belge_yukle([tmp_path / "program.xlsx"], sormadan=True)
    assert sum(s.eklenen for s in sonuclar) == 3
    p.tip.setCurrentIndex(0)
    p.kimlik.setCurrentIndex(p.kimlik.findText("10-A"))
    p.ciz()
    assert p.tablo.item(0, 0).text().startswith("Kimya\nDeniz Ak") and "(kilitli)" in p.tablo.item(1, 3).text()

    ece = db.q1("SELECT id FROM ogretmenler WHERE ad = 'Ece'")["id"]
    db.execute("UPDATE ders_atamalari SET ogretmen2_id = ? WHERE ders_id = (SELECT id FROM dersler WHERE ad = 'Kimya')",
               (ece,))
    p.ciz()
    assert hucre_metni("sinif", p.hucreler[(1, 1)]) == "Kimya\nDeniz Ak / Ece Su"
    p.tip.setCurrentIndex(1)
    p.kimlik.setCurrentIndex(p.kimlik.findText("Ece Su"))
    assert set(p.hucreler) == {(1, 1), (1, 2), (4, 2)}


def test_nobet_ve_ozel_durumlar(app, db):
    from koordmes.ui.sayfa_program import ProgramSayfasi

    sinif = db.insert("siniflar", {"ad": "9 BT A", "seviye": 9})
    ali = db.insert("ogretmenler", {"ad": "Ali", "soyad": "Can"})
    veli = db.insert("ogretmenler", {"ad": "Veli", "soyad": "Demir"})
    ders = db.insert("dersler", {"ad": "Programlama"})
    atama = db.insert("ders_atamalari", {"sinif_id": sinif, "ders_id": ders, "ogretmen_id": ali, "haftalik_saat": 2})
    sayfa = ProgramSayfasi(db)
    assert sayfa.count() == 6 and sayfa.tabText(2) == "Sınıf / Öğretmen / Mekan"
    assert sayfa.widget(2).__class__.__name__ == "ProgramTablosu"
    assert sayfa.tabText(0) == "İş Adımları ve Mevzuat"

    nobet = sayfa.widget(4)
    nobet.yukle()
    nobet.tablo.cellWidget(0, 1).setCurrentIndex(1)
    nobet.tablo.item(0, 2).setText("Bahçe")
    nobet.tablo.item(0, 3).setText("9A")
    nobet.kaydet()
    r = db.q1("SELECT nobet_gun, nobet_yeri, sinif_ogretmenligi FROM ogretmenler WHERE id = ?", (ali,))
    assert (r["nobet_gun"], r["nobet_yeri"], r["sinif_ogretmenligi"]) == (1, "Bahçe", "9A")

    ozel = sayfa.widget(5)
    ozel.yukle()
    ozel.siniflar.item(0, 1).setText("Pzt, Sal")
    ozel.siniflar.item(0, 2).setText("Çar, Per, Cum")
    ozel.atamalar.item(0, 3).setText("Veli Demir")
    ozel.atamalar.item(0, 4).setText("Bilişim Lab.")
    ozel.atamalar.item(0, 5).setText("Grup-1")
    ozel.kaydet()
    s = db.q1("SELECT okul_gunleri, isletme_gunleri FROM siniflar WHERE id = ?", (sinif,))
    assert s["okul_gunleri"] == "1,2" and s["isletme_gunleri"] == "3,4,5"
    a = db.q1("SELECT ogretmen2_id, atolye_id, birlestirme FROM ders_atamalari WHERE id = ?", (atama,))
    assert a["ogretmen2_id"] == veli and a["birlestirme"] == "Grup-1"
    assert db.q1("SELECT ad FROM atolyeler WHERE id = ?", (a["atolye_id"],))["ad"] == "Bilişim Lab."
