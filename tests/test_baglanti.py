from koordmes.services import baglanti, degisiklik
from koordmes.services.baglanti import DURUM_ACIK, DURUM_BAGLI, DURUM_GIRIS, SISTEM_SOZLUK

EOKUL = SISTEM_SOZLUK["eokul"]
EBILDIRGE = SISTEM_SOZLUK["ebildirge"]


def test_acilis_sayfasi_bagli_sayilmaz():
    assert baglanti.durum(EOKUL, "https://e-okul.meb.gov.tr/", False, False) == DURUM_ACIK


def test_edevlet_ve_sifre_alani_giris_adimidir():
    assert baglanti.durum(EOKUL, "https://giris.turkiye.gov.tr/Giris/gir", False, False) == DURUM_GIRIS
    assert baglanti.durum(EBILDIRGE, "https://ebildirge.sgk.gov.tr/EBildirgeV2", True, False) == DURUM_GIRIS


def test_giristen_sonra_sistem_sayfasi_bagli():
    url = "https://e-okul.meb.gov.tr/OrtaOgretim/OKL/OOK06001.aspx"
    assert baglanti.durum(EOKUL, url, False, True) == DURUM_BAGLI
    assert baglanti.durum(EBILDIRGE, url, False, True) == DURUM_ACIK


def test_benzer_alan_adi_kabul_edilmez():
    assert not baglanti.sistemin_mi(EOKUL, "https://e-okul.meb.gov.tr.ornek.com/")
    assert baglanti.sistemin_mi(EOKUL, "https://E-OKUL.meb.gov.tr/x")


def test_benzersiz_ve_guvenli_dosya_adi(tmp_path):
    (tmp_path / "liste.xls").write_text("x")
    assert baglanti.benzersiz_yol(tmp_path, "liste.xls").name == "liste (1).xls"
    assert baglanti.guvenli_dosya_adi('a:b/c?.xlsx') == "a_b_c_.xlsx"


def test_indirilen_liste_aktarilir(db, tmp_path):
    yol = tmp_path / "isletmeler.csv"
    yol.write_text("İşletme Adı;Vergi No;Yetkili;Personel Sayısı\nUsta Mobilya;1234567890;Ali Kaya;12\n",
                   encoding="utf-8")
    s = baglanti.indirileni_isle(db, yol, otomatik=True)
    assert s.aktarildi, s.ozet
    assert db.q1("SELECT personel_sayisi FROM isletmeler WHERE ad LIKE 'Usta%'")["personel_sayisi"] == 12
    assert "işletme" in degisiklik.oku(db)


def test_vizite_sistemi_giristen_sonra_bagli():
    vizite = SISTEM_SOZLUK["vizite"]
    assert vizite.adres.startswith("https://uyg.sgk.gov.tr/vizite/")
    assert baglanti.durum(vizite, vizite.adres, False, False) == DURUM_ACIK
    assert baglanti.durum(vizite, vizite.adres, True, False) == DURUM_GIRIS
    assert baglanti.durum(vizite, "https://uyg.sgk.gov.tr/vizite/anasayfa.do", False, True) == DURUM_BAGLI
    assert baglanti.durum(vizite, "https://e-okul.meb.gov.tr/", False, True) == DURUM_ACIK


def test_yuklenecek_sgk_dosyasi_secme_penceresinde_hazir(tmp_path):
    xml = tmp_path / "aphb.xml"
    xml.write_text("<x/>", encoding="utf-8")
    baglanti.yuklenecek_ayarla([xml])
    assert baglanti.yukleme_baslangici() == str(xml)
    xml.unlink()
    assert baglanti.yukleme_baslangici() != str(xml)
    baglanti.yuklenecek_ayarla([])


def test_taninmayan_dosya_aktarilmaz(db, tmp_path):
    yol = tmp_path / "makbuz.txt"
    yol.write_text("Tahakkuk fişi\nToplam: 100\n", encoding="utf-8")
    s = baglanti.indirileni_isle(db, yol, otomatik=True)
    assert not s.aktarildi
    assert not baglanti.indirileni_isle(db, yol, otomatik=False).aktarildi
