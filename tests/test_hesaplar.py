from datetime import date

import pytest

from koordmes.services import sigorta, ucret
from koordmes.services.utils import tc_gecerli


def _ogrenci_yerlestir(db, personel=10, program="MTAL-AMP", statu="Öğrenci", yukumlu=1, kamu=0,
                       bas="2026-09-14", bit=None, tur="İşletmede Mesleki Eğitim"):
    s = db.insert("siniflar", {"ad": "12-A", "seviye": 12, "program": program})
    o = db.insert("ogrenciler", {"ad": "Ali", "soyad": "Yılmaz", "tc": "10000000146", "sinif_id": s,
                                 "statu": statu, "bakmakla_yukumlu": yukumlu})
    i = db.insert("isletmeler", {"ad": "Firma", "personel_sayisi": personel, "kamu_kurumu": kamu})
    y = db.insert("yerlestirmeler", {"ogrenci_id": o, "isletme_id": i, "tur": tur, "baslangic": bas, "bitis": bit})
    return o, y


def test_prim_gun_tam_ay_30():
    assert sigorta.prim_gun(date(2026, 1, 1), None, 2026, 2) == 30
    assert sigorta.prim_gun(date(2026, 1, 1), None, 2026, 3) == 30


def test_prim_gun_parmak_hesabi():
    assert sigorta.prim_gun(date(2026, 9, 14), None, 2026, 9) == 17
    assert sigorta.prim_gun(date(2026, 1, 1), date(2026, 3, 10), 2026, 3) == 10
    assert sigorta.prim_gun(date(2026, 3, 2), None, 2026, 3) == 30
    assert sigorta.prim_gun(date(2026, 10, 1), None, 2026, 9) == 0


def test_gecici12_ucret_ve_devlet_katkisi_20_alti(db):
    _ogrenci_yerlestir(db, personel=10, bas="2026-01-01")
    [s] = ucret.aylik_hesap(db, 2026, 10)
    assert s.gun == 30
    assert s.en_az_ucret == pytest.approx(28075.50 * 0.30, abs=0.01)
    assert s.devlet_katkisi == pytest.approx(28075.50 * 0.30 * 2 / 3, abs=0.02)


def test_devlet_katkisi_20_ustu_ve_kamu(db):
    _ogrenci_yerlestir(db, personel=25, bas="2026-01-01")
    [s] = ucret.aylik_hesap(db, 2026, 10)
    assert s.devlet_katkisi == pytest.approx(8422.65 / 3, abs=0.02)
    db.execute("UPDATE isletmeler SET kamu_kurumu = 1")
    [s] = ucret.aylik_hesap(db, 2026, 10)
    assert s.devlet_katkisi == 0


def test_mem_devlet_katkisi_tamami(db):
    _ogrenci_yerlestir(db, personel=50, program="MEM", statu="Çırak", bas="2026-01-01", tur="Çıraklık")
    [s] = ucret.aylik_hesap(db, 2026, 10)
    assert s.devlet_katkisi == pytest.approx(s.en_az_ucret, abs=0.01)


def test_gecici12_kapali_md25(db):
    db.ayar_yaz("gecici12_aktif", "0")
    _ogrenci_yerlestir(db, personel=10, bas="2026-01-01")
    [s] = ucret.aylik_hesap(db, 2026, 10)
    assert s.oran == 0.15
    assert s.devlet_katkisi == 0


def test_sigorta_prim_ve_belge_turu(db):
    o, _ = _ogrenci_yerlestir(db, yukumlu=1, bas="2026-01-01")
    [s] = sigorta.aylik_liste(db, 2026, 10)
    assert s.belge_turu == "7"
    assert s.gun == 30
    assert s.pek == pytest.approx(33030 * 0.5, abs=0.01)
    assert s.prim == pytest.approx(33030 * 0.5 * 0.01, abs=0.01)
    db.execute("UPDATE ogrenciler SET bakmakla_yukumlu = 0")
    [s] = sigorta.aylik_liste(db, 2026, 10)
    assert s.belge_turu == "42"
    assert s.prim == pytest.approx(33030 * 0.5 * 0.06, abs=0.01)


def test_okulda_alan_egitimi_belge_49(db):
    _ogrenci_yerlestir(db, bas="2026-01-01", tur="Okulda Alan Eğitimi")
    [s] = sigorta.aylik_liste(db, 2026, 10)
    assert s.belge_turu == "49"


def test_ozursuz_devamsizlik_eksik_gun(db):
    o, _ = _ogrenci_yerlestir(db, bas="2026-01-01")
    for d in ("2026-10-05", "2026-10-06"):
        db.insert("devamsizlik", {"ogrenci_id": o, "tarih": d, "tur": "Özürsüz", "gun": 1, "sgk_eksik": 1})
    [s] = sigorta.aylik_liste(db, 2026, 10)
    assert s.gun == 28 and s.eksik_gun == 2 and s.eksik_neden == "15"


def test_bekleyen_bildirimler(db):
    _, y = _ogrenci_yerlestir(db, bas="2026-10-05", bit="2026-10-20")
    b = sigorta.bekleyen_bildirimler(db, date(2026, 10, 1))
    turler = {x.tur for x in b}
    assert turler == {"Giriş", "Çıkış"}
    cikis = next(x for x in b if x.tur == "Çıkış")
    assert cikis.son_tarih == date(2026, 10, 30)
    sigorta.bildirildi_isaretle(db, y, "Giriş")
    assert {x.tur for x in sigorta.bekleyen_bildirimler(db, date(2026, 10, 1))} == {"Çıkış"}


def test_tc_dogrulama():
    assert tc_gecerli("10000000146")
    assert not tc_gecerli("12345678901")
