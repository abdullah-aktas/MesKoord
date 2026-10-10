from datetime import date

from koordmes.services import sgk_risk


def _ogrenci(db, ad, tc, dogum="2010-03-01", yukumlu=1):
    sinif = db.q1("SELECT id FROM siniflar") or {"id": db.insert("siniflar", {"ad": "11-A", "seviye": 11})}
    return db.insert("ogrenciler", {"ad": ad, "soyad": "Deneme", "tc": tc, "dogum_tarihi": dogum,
                                    "sinif_id": sinif["id"], "bakmakla_yukumlu": yukumlu})


def _yerlestir(db, ogr, bas, bit=None, **ek):
    isl = db.q1("SELECT id FROM isletmeler") or {"id": db.insert("isletmeler", {"ad": "Usta Elektrik"})}
    return db.insert("yerlestirmeler", {"ogrenci_id": ogr, "isletme_id": isl["id"], "baslangic": bas,
                                        "bitis": bit, **ek})


def _bul(riskler, konu, kisi=None):
    return [r for r in riskler if konu in r.konu and (kisi is None or kisi in r.kisi)]


def test_risk_tespiti_ve_duzeltme(db):
    a = _ogrenci(db, "Ali", "10000000078")
    _yerlestir(db, a, "2026-09-28")
    b = _ogrenci(db, "Büyük", "10000000146", dogum="2005-06-10")
    _yerlestir(db, b, "2026-09-15", sigorta_giris_bildirildi=1, sigorta_giris_bildirim_tarihi="2026-09-14")
    c = _ogrenci(db, "Hatalı", "123")
    _yerlestir(db, c, "2026-09-15", sigorta_giris_bildirildi=1, sigorta_giris_bildirim_tarihi="2026-09-20")
    d = _ogrenci(db, "Yakın", "10000000214", dogum="2006-11-01")
    _yerlestir(db, d, "2026-10-12")

    riskler = sgk_risk.analiz(db, date(2026, 10, 7))
    giris = _bul(riskler, "İşe giriş bildirgesi gecikti", "Ali")[0]
    assert giris.seviye == "Kritik" and giris.tahmini_ceza == 33030 and giris.indirimli_ceza < giris.tahmini_ceza
    assert "1/4" in giris.oneri and giris.eylem == "bildirildi:Giriş"
    assert _bul(riskler, "İşe giriş bildirgesi yaklaşıyor", "Yakın")
    yas = _bul(riskler, "20 yaşını doldurdu", "Büyük")[0]
    assert yas.eylem == "yukumlu_kaldir" and "42" in yas.aciklama
    assert _bul(riskler, "20 yaşını dolduracak", "Yakın")
    assert _bul(riskler, "T.C. kimlik no", "Hatalı")
    assert _bul(riskler, "geç bildirilmiş", "Hatalı")
    aphb = _bul(riskler, "09/2026 APHB")
    assert not aphb  # son gün 26.10, henüz 7 günden uzak
    assert "olası idari para cezası" in sgk_risk.ozet(riskler).lower()

    sgk_risk.uygula(db, giris)
    sgk_risk.uygula(db, yas)
    riskler = sgk_risk.analiz(db, date(2026, 10, 7))
    assert not _bul(riskler, "gecikti", "Ali") and not _bul(riskler, "20 yaşını doldurdu", "Büyük")

    riskler = sgk_risk.analiz(db, date(2026, 10, 22))
    assert _bul(riskler, "09/2026 APHB son günü yaklaşıyor")[0].seviye == "Uyarı"
    aphb = _bul(sgk_risk.analiz(db, date(2026, 10, 28)), "09/2026 APHB verildi mi")[0]
    assert aphb.seviye == "Kritik" and 0 < aphb.tahmini_ceza <= 2 * 33030
    sgk_risk.uygula(db, aphb)
    assert not _bul(sgk_risk.analiz(db, date(2026, 10, 28)), "09/2026 APHB")


def test_tatilde_ayrilis_ve_acik_yerlestirme(db, tmp_path):
    db.insert("tatiller", {"ad": "Yarıyıl Tatili", "baslangic": "2027-01-25", "bitis": "2027-02-05"})
    a = _ogrenci(db, "Tatil", "10000000078")
    _yerlestir(db, a, "2026-09-15", "2027-01-30", sigorta_giris_bildirildi=1,
               sigorta_giris_bildirim_tarihi="2026-09-14")
    b = _ogrenci(db, "Açık", "10000000146")
    _yerlestir(db, b, "2026-09-15", sigorta_giris_bildirildi=1, sigorta_giris_bildirim_tarihi="2026-09-14",
               sigorta_cikis_bildirildi=1)
    riskler = sgk_risk.analiz(db, date(2026, 10, 7))
    assert _bul(riskler, "Tatilde işten ayrılış", "Tatil")
    assert _bul(riskler, "Çıkış bildirilmiş ama yerleştirme açık", "Açık")
    assert sgk_risk.excel_yaz(riskler, tmp_path / "risk.xlsx").exists()


def test_ornek_veride_calisir(ornek_db):
    from koordmes.services import asistan, denetim
    riskler = sgk_risk.analiz(ornek_db, date(2026, 10, 7))
    assert all(r.seviye in sgk_risk.SEVIYE_SIRASI for r in riskler)
    y = asistan.yorumla(ornek_db, "SGK ceza riskleri", date(2026, 10, 7))
    assert "SGK hata ve ceza riskleri" in y.metin
    assert asistan.yorumla(ornek_db, "sgk listesi karşılaştır").git == "SGK Sigorta İşlemleri"
    assert asistan.yorumla(ornek_db, "ekim sgk listesi").metin != y.metin
    assert denetim.denetle(ornek_db, date(2026, 10, 7))
