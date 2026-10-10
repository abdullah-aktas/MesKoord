import os
import smtplib

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from koordmes.services import paylasim
from koordmes.services.paylasim import PostaAyarlari


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_whatsapp_numarasi():
    assert paylasim.whatsapp_no("0532 123 45 67") == "905321234567"
    assert paylasim.whatsapp_no("(532) 123-4567") == "905321234567"
    assert paylasim.whatsapp_no("+90 532 123 45 67") == "905321234567"
    assert paylasim.whatsapp_no("0090 532 123 45 67") == "905321234567"
    assert paylasim.whatsapp_no("0482 215 10 10") == "904822151010"
    assert paylasim.whatsapp_no("123") == ""
    assert paylasim.whatsapp_no("") == ""


def test_adresler():
    uyg, web = paylasim.whatsapp_adresleri("905321234567", "Ders programı ektedir")
    assert uyg == "whatsapp://send?phone=905321234567&text=Ders%20program%C4%B1%20ektedir"
    assert web.startswith("https://web.whatsapp.com/send?phone=905321234567&text=")
    assert paylasim.whatsapp_adresleri("", "")[0] == "whatsapp://send?"
    m = paylasim.mailto_adresi(["a@b.com", "c@d.org"], "Konu", "Metin")
    assert m.startswith("mailto:a@b.com,c@d.org?subject=Konu&body=Metin")
    assert paylasim.eposta_gecerli("ali.veli@meb.k12.tr")
    assert not paylasim.eposta_gecerli("ali@")
    assert not paylasim.eposta_gecerli("a b@c.com")


def test_kisiler_iletisimi_olanlari_listeler(db):
    db.insert("ogretmenler", {"ad": "Ayşe", "soyad": "Kaya", "eposta": "ayse@meb.k12.tr", "telefon": ""})
    db.insert("ogretmenler", {"ad": "Boş", "soyad": "Kişi"})
    db.insert("isletmeler", {"ad": "Usta Mobilya", "yetkili": "Ali Usta", "telefon": "0532 111 22 33",
                             "usta_ogretici": "Veli Usta", "usta_ogretici_tel": "05321112234"})
    db.insert("ogrenciler", {"ad": "Can", "soyad": "Er", "veli_ad": "Hasan Er", "veli_tel": "0533 000 00 00"})
    k = {x.rol: x for x in paylasim.kisiler(db)}
    assert k["Öğretmen"].eposta == "ayse@meb.k12.tr"
    assert k["İşletme"].ad == "Ali Usta - Usta Mobilya"
    assert k["Usta öğretici"].telefon == "05321112234"
    assert k["Veli"].ad.startswith("Hasan Er - Can Er")
    assert not any(x.ad == "Boş Kişi" for x in paylasim.kisiler(db))


def test_ileti_ekli_ve_smtp_her_aliciya_ayri(tmp_path, monkeypatch):
    dosya = tmp_path / "program.pdf"
    dosya.write_bytes(b"%PDF-1.4 deneme")
    ayar = PostaAyarlari("smtp.ornek.com", 587, "STARTTLS", "okul@ornek.com", "Derik MTAL")
    gonderilen = []

    class Sahte:
        def __init__(self, sunucu, port, timeout=None):
            assert (sunucu, port) == ("smtp.ornek.com", 587)

        def starttls(self, context=None):
            pass

        def login(self, k, p):
            if p != "dogru":
                raise smtplib.SMTPAuthenticationError(535, b"hayir")

        def send_message(self, m):
            gonderilen.append(m)

        def quit(self):
            pass

    monkeypatch.setattr(smtplib, "SMTP", Sahte)
    iletiler = [paylasim.ileti(ayar, [a], "Konu", "Metin", [dosya]) for a in ("a@b.com", "c@d.com")]
    s = paylasim.smtp_gonder(ayar, "dogru", iletiler)
    assert s.gonderilen == ["a@b.com", "c@d.com"] and not s.hatalar
    ek = list(gonderilen[0].iter_attachments())
    assert [e.get_filename() for e in ek] == ["program.pdf"]
    assert ek[0].get_content() == b"%PDF-1.4 deneme"
    assert "Derik MTAL" in gonderilen[0]["From"]
    with pytest.raises(paylasim.PaylasimHatasi, match="uygulama şifresi"):
        paylasim.smtp_gonder(ayar, "yanlis", iletiler)


def test_posta_ayarinda_sifre_saklanmaz(tmp_path, monkeypatch):
    monkeypatch.setattr(PostaAyarlari, "yol", staticmethod(lambda: tmp_path / "posta.json"))
    PostaAyarlari("smtp.gmail.com", 587, "STARTTLS", "okul@gmail.com", "Okul").kaydet()
    metin = (tmp_path / "posta.json").read_text("utf-8")
    assert "smtp.gmail.com" in metin and "parola" not in metin and "sifre" not in metin
    assert PostaAyarlari.yukle().hazir


def test_paylas_penceresi_whatsapp_sirayla_acar(app, db, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QDesktopServices, QGuiApplication

    from koordmes.ui.paylas import PaylasPenceresi, klasordeki_dosyalar

    db.insert("ogretmenler", {"ad": "Ayşe", "soyad": "Kaya", "eposta": "ayse@meb.k12.tr", "telefon": "0532 123 45 67"})
    db.insert("ogretmenler", {"ad": "Mehmet", "soyad": "Ak", "telefon": "0533 765 43 21"})
    dosya = tmp_path / "program.pdf"
    dosya.write_bytes(b"x")
    acilan = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda u: acilan.append(u.toString()) or True)

    p = PaylasPenceresi(None, [dosya], db)
    for i in range(p.kisi_listesi.count()):
        p.kisi_listesi.item(i).setCheckState(Qt.Checked)
    p.diger.setText("veli@ornek.com, 0544 000 11 22")
    assert p.eposta_alicilari() == ["ayse@meb.k12.tr", "veli@ornek.com"]
    assert p.whatsapp_numaralari() == ["905321234567", "905337654321", "905440001122"]

    p.whatsapp()
    assert acilan[-1].startswith("whatsapp://send?phone=905321234567")
    urls = QGuiApplication.clipboard().mimeData().urls()
    assert [u.toLocalFile() for u in urls] == [str(dosya.resolve()).replace("\\", "/")]
    assert "2/3" in p.b_wa.text()
    p.whatsapp()
    p.whatsapp()
    assert acilan[-1].startswith("whatsapp://send?phone=905440001122")
    assert p.b_wa.text() == "WhatsApp ile Gönder"

    p.rol.setCurrentText("İşletme")
    assert all(p.kisi_listesi.item(i).isHidden() for i in range(p.kisi_listesi.count()))

    (tmp_path / "eski.xlsx").write_bytes(b"x")
    os.utime(tmp_path / "eski.xlsx", (1, 1))
    dosyalar, secili = klasordeki_dosyalar(tmp_path)
    assert dosyalar[0] == dosya and dosya in secili and tmp_path / "eski.xlsx" not in secili
    QGuiApplication.clipboard().clear()
    p.deleteLater()
    app.processEvents()
