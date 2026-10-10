from datetime import date

import pytest

from koordmes.services import asistan, denetim, surecler
from koordmes.services.utils import iban_gecerli

BUGUN = date(2026, 10, 1)


def test_iban_dogrulama():
    from random import Random
    from koordmes.services.ornek_veri import iban_uret
    iban = iban_uret(Random(1))
    assert iban_gecerli(iban) and iban_gecerli(" ".join(iban[i:i + 4] for i in range(0, len(iban), 4)))
    bozuk = iban[:-1] + str((int(iban[-1]) + 1) % 10)
    assert not iban_gecerli(bozuk) and not iban_gecerli("DE89370400440532013000")


@pytest.mark.parametrize("komut, eylem, dosya", [
    ("geçen ayın kapanışını hazırla", "aylik_kapanis", False),
    ("programı oluştur", "program_olustur", False),
    ("koordinatör görevlendir", "koordinator", False),
    ("yeni eğitim yılına geç", "yeni_egitim_yili", False),
    ("ekim sgk listesi", None, True),
    ("ek ders puantajı", None, True),
    ("ek ders ücreti", None, True),
    ("ücret hesapla", None, True),
    ("devamsızlık durumu", None, True),
])
def test_niyet_yorumlama(ornek_db, komut, eylem, dosya):
    y = asistan.yorumla(ornek_db, komut, BUGUN)
    assert y.eylem == eylem
    assert bool(y.dosyalar) == dosya, y.metin


def test_donem_ve_tarih_cozumu(ornek_db):
    assert asistan.donem_bul("ekim sgk", BUGUN) == (2026, 10)
    assert asistan.donem_bul("gecen ay", BUGUN) == (2026, 9)
    assert asistan.donem_bul("ocak", BUGUN) == (2027, 1)
    y = asistan.yorumla(ornek_db, "yıl sonu 25.06.2027", BUGUN)
    assert y.eylem == "yil_sonu" and y.eylem_kw["tarih"] == date(2027, 6, 25)
    assert asistan.yorumla(ornek_db, "ekim sgk listesi", BUGUN).dosyalar[0].name.endswith("Ekim 2026.xlsx")


def test_sorgu_kartlari(ornek_db):
    o = ornek_db.q1("SELECT ad, soyad FROM ogrenciler LIMIT 1")
    y = asistan.yorumla(ornek_db, f"{o['ad']} {o['soyad']}", BUGUN)
    assert "Öğrenci" in y.metin
    assert "Sınıf: 12-A" in asistan.yorumla(ornek_db, "12-A", BUGUN).metin
    i = ornek_db.q1("SELECT ad FROM isletmeler LIMIT 1")["ad"]
    assert "İşletme:" in asistan.yorumla(ornek_db, i.split()[0] + " " + i.split()[1], BUGUN).metin
    assert "bulamadım" in asistan.yorumla(ornek_db, "zzqx", BUGUN).metin


def test_gundem_yardim_istatistik(ornek_db):
    assert asistan.yorumla(ornek_db, "bugün ne yapmalıyım", BUGUN).metin
    assert "komut:" in asistan.yorumla(ornek_db, "yardım", BUGUN).metin
    assert "Aktif öğrenci" in asistan.yorumla(ornek_db, "istatistik", BUGUN).metin
    assert "asgari" in asistan.yorumla(ornek_db, "parametreler", BUGUN).metin.lower()


def test_surec_durumlari(ornek_db):
    for k in surecler.SURECLER:
        d = surecler.durumlar(ornek_db, k, 2026, 9)
        assert d and not any(x.detay.startswith("Denetlenemedi") for x in d), [x.detay for x in d]
        for x in d:
            assert x.adim.eylem is None or x.adim.eylem in surecler.EYLEMLER


def test_denetim_bulgulari(ornek_db):
    ornek_db.execute("UPDATE ogrenciler SET tc = '12345678901' WHERE id = (SELECT MIN(id) FROM ogrenciler)")
    b = denetim.denetle(ornek_db, BUGUN)
    assert any("T.C." in x.mesaj for x in b)
    assert all(x.seviye in ("Kritik", "Uyarı", "Bilgi") for x in b)


def test_aylik_kapanis_ve_yil_gecisi(ornek_db):
    s = surecler.aylik_kapanis(ornek_db, 2026, 9)
    assert s.dosyalar and all(p.exists() for p in s.dosyalar)
    say = lambda seviye: ornek_db.q1("SELECT COUNT(*) FROM ogrenciler o JOIN siniflar s ON s.id = o.sinif_id "
                                     "WHERE s.ad LIKE ? AND o.aktif = 1", (f"{seviye}-%",))[0]
    on_bir = say(11)
    assert on_bir and say(12)
    surecler.yeni_egitim_yili(ornek_db)
    assert say(12) == on_bir
    assert ornek_db.q1("SELECT COUNT(*) FROM koordinator_gorevleri")[0] == 0
