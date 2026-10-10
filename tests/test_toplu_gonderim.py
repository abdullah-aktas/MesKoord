import os
import smtplib

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from koordmes.services import toplu_gonderim


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_isletmelere_sozlesme_ve_ucret_kendi_belgesiyle(ornek_db, tmp_path):
    db = ornek_db
    sozlesme = toplu_gonderim.hazirla(db, "isletme_sozlesme", tmp_path / "s")
    assert sozlesme and all(not g.hata for g in sozlesme)
    aktif = {r["isletme_id"]: r["n"] for r in db.q("""SELECT isletme_id, COUNT(*) n FROM yerlestirmeler
                                                     WHERE durum = 'Aktif' AND isletme_id IS NOT NULL
                                                     GROUP BY isletme_id""")}
    for g in sozlesme:
        iid = int(g.kisi.anahtar.split(":")[1])
        assert len(g.dosyalar) == aktif[iid]
        assert all(d.exists() and d.suffix == ".docx" for d in g.dosyalar)
    ucret = toplu_gonderim.hazirla(db, "isletme_ucret", tmp_path / "u", 2026, 10)
    assert len(ucret) == len(aktif) and all(len(g.dosyalar) == 1 for g in ucret)
    konu, metin = toplu_gonderim.metinler(db, "isletme_ucret", ucret[0].kisi, 2026, 10)
    assert "Ekim 2026" in konu and "{" not in metin


def test_koordinator_yazilari(ornek_db, tmp_path):
    from koordmes.services import koordinator
    koordinator.otomatik_gorevlendir(ornek_db)
    gorev = toplu_gonderim.hazirla(ornek_db, "koordinator_gorev", tmp_path / "g")
    assert gorev and all(g.kisi.rol == "Öğretmen" and len(g.dosyalar) == 1 and not g.hata for g in gorev)
    bildirim = toplu_gonderim.hazirla(ornek_db, "isletme_koordinator", tmp_path / "b")
    assert bildirim and all(g.kisi.rol == "İşletme" and len(g.dosyalar) == 1 and not g.hata for g in bildirim)


def test_ekran_ogretmen_programlarini_hazirlar_ve_eposta_gonderir(app, ornek_db, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from koordmes import config
    from koordmes.services import program
    from koordmes.services.paylasim import PostaAyarlari
    from koordmes.ui import ortak, paylas
    from koordmes.ui.sayfa_toplu_gonderim import TopluGonderimSayfasi

    if not ornek_db.q1("SELECT 1 FROM program_hucreleri"):
        program.programi_olustur(ornek_db, sure_limit=5, seed=1)
    ogr = ornek_db.q("SELECT id FROM ogretmenler")
    for n, r in enumerate(ogr):
        ornek_db.update("ogretmenler", r["id"], {"eposta": f"ogretmen{n}@okul.k12.tr", "telefon": "0532 000 00 0" + str(n % 10)})
    monkeypatch.setattr(config, "output_dir", lambda: tmp_path)
    monkeypatch.setattr(PostaAyarlari, "yukle", classmethod(lambda cls: cls("smtp.ornek.com", 587, "STARTTLS",
                                                                            "okul@ornek.com", "Okul")))
    monkeypatch.setattr(paylas, "parola_al", lambda *a, **k: "dogru")
    import koordmes.ui.sayfa_toplu_gonderim as stg
    monkeypatch.setattr(stg, "parola_al", lambda *a, **k: "dogru")
    monkeypatch.setattr(ortak, "onay", lambda *a, **k: True)
    giden = []

    class Sahte:
        def __init__(self, *a, **k):
            pass

        def starttls(self, context=None):
            pass

        def login(self, k, p):
            pass

        def send_message(self, m):
            giden.append(m)

        def quit(self):
            pass

    monkeypatch.setattr(smtplib, "SMTP", Sahte)

    s = TopluGonderimSayfasi(ornek_db)
    s.tur.setCurrentIndex(s.tur.findData("ogretmen_program"))
    s.hazirla()
    assert s.gonderiler and all(g.dosyalar and g.dosyalar[0].suffix == ".pdf" for g in s.gonderiler)
    assert all(g.dosyalar[0].stat().st_size > 500 for g in s.gonderiler)
    s.tablo.item(0, 0).setCheckState(Qt.Unchecked)
    s.smtp_gonder()
    for _ in range(200):
        app.processEvents()
        if s.isEnabled():
            break
        import time
        time.sleep(0.02)
    assert len(giden) == len(s.gonderiler) - 1
    ilk = giden[0]
    assert ilk["To"] == s.gonderiler[1].kisi.eposta
    assert s.gonderiler[1].kisi.ad.split()[0] in ilk.get_body().get_content()
    assert [a.get_filename() for a in ilk.iter_attachments()] == [s.gonderiler[1].dosyalar[0].name]
    assert s.tablo.item(1, 5).text() == "E-posta gönderildi"
    assert s.tablo.item(0, 5).text() == ""
