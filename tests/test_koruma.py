import os
from datetime import date

import pytest

from conftest import pencereyi_kapat
from koordmes.mevzuat import isletmeye_giden_sinif, maol_mi, mem_mi
from koordmes.services import koruma, mesleki_egitim, sgk_beyan, sigorta, takvim

SICIL = "2 8510 01 01 1234567 063 01 12 000"
AYSE, ISMAIL, CAN = "10000000078", "10000000146", "10000000214"


def _sinif(db, ad, seviye, program):
    return db.insert("siniflar", {"ad": ad, "seviye": seviye, "program": program})


@pytest.fixture
def okul(db):
    """Aynı okulda MTAL 12. sınıf, MESEM çırağı ve açık lise (MAOL) öğrencisi."""
    db.update("kurum", 1, {"ad": "Atatürk MTAL", "il": "Ankara", "ilce": "Çankaya", "sgk_isyeri_sicil": SICIL,
                           "ders_yili_baslangic": "2026-09-07"})
    isl = db.insert("isletmeler", {"ad": "Usta Elektrik"})
    mtal, mem, maol = _sinif(db, "12-A", 12, "MTAL-AMP"), _sinif(db, "MEM-10", 10, "MEM"), _sinif(db, "AL-12", 12, "MAOL")
    a = db.insert("ogrenciler", {"ad": "Ayşe", "soyad": "Işık", "tc": AYSE, "sinif_id": mtal, "bakmakla_yukumlu": 1,
                                 "dogum_tarihi": "2006-10-15"})
    i = db.insert("ogrenciler", {"ad": "İsmail", "soyad": "Öztürk", "tc": ISMAIL, "sinif_id": mem, "statu": "Çırak",
                                 "bakmakla_yukumlu": 1, "dogum_tarihi": "2010-03-01"})
    c = db.insert("ogrenciler", {"ad": "Can", "soyad": "Demir", "tc": CAN, "sinif_id": maol, "statu": "Açık Lise",
                                 "bakmakla_yukumlu": 0, "baska_sigortali": 1, "dogum_tarihi": "1990-01-01"})
    y = lambda o, tur, bas, **k: db.insert("yerlestirmeler", {"ogrenci_id": o, "isletme_id": isl, "tur": tur,
                                                              "baslangic": bas, **k})
    return db, {"a": a, "i": i, "c": c, "isl": isl,
                "ya": y(a, "İşletmede Mesleki Eğitim", "2026-09-14", sigorta_giris_bildirildi=1,
                        sozlesme_tarihi="2026-09-10"),
                "yi": y(i, "Çıraklık", "2026-10-01"),
                "yc": y(c, "İşletmede Mesleki Eğitim", "2026-10-01", sozlesme_tarihi="2026-09-28")}


def test_mesem_ve_maol_tanima():
    assert mem_mi("MEM") and mem_mi(None, "Kalfa (MEM 12)") and mem_mi(None, None, "Çıraklık")
    assert not mem_mi("MTAL-AMP", "Öğrenci") and not mem_mi("MAOL", "Açık Lise")
    assert maol_mi("MAOL") and maol_mi(None, "Açık Lise") and not maol_mi("MTAL-AMP", "Öğrenci")
    assert isletmeye_giden_sinif("MTAL-AMP", 12) and isletmeye_giden_sinif("MEM", 9)
    assert not isletmeye_giden_sinif("MAOL", 12) and not isletmeye_giden_sinif("MTAL-AMP", 11)


def test_yas_siniri_ve_baska_sigortali_belge_turu(okul):
    db, ids = okul
    belge = lambda yil, ay: {s.ogrenci_id: str(s.belge_turu) for s in sigorta.aylik_liste(db, yil, ay)}
    assert belge(2026, 10)[ids["a"]] == "7"  # 15 Ekim'de 20 yaşına giriyor; ay başında yükümlü
    assert belge(2026, 11)[ids["a"]] == "42"
    assert belge(2026, 11)[ids["c"]] == "7"  # başka işte sigortalı: GSS primi yok
    assert sigorta.yas_doldugu_gun(date(2008, 2, 29), 21) == date(2029, 3, 1)
    assert sigorta.yas_doldugu_gun(date(2008, 2, 29), 20) == date(2028, 2, 29)
    db.update("yerlestirmeler", ids["ya"], {"bitis": "2026-11-20"})
    cikis = next(b for b in sigorta.bekleyen_bildirimler(db, date(2026, 11, 21)) if b.yerlestirme_id == ids["ya"])
    assert cikis.tur == "Çıkış" and cikis.belge_turu == "42"


def test_mesem_sozlesme_sureleri(okul):
    db, ids = okul
    s = {x.ogrenci_id: x for x in mesleki_egitim.sozlesme_sureleri(db)}
    assert set(s) == {ids["i"]} and s[ids["i"]].mem and s[ids["i"]].son == date(2026, 11, 30)
    db.update("yerlestirmeler", ids["yi"], {"bitis": "2026-11-02", "durum": "Sona Erdi",
                                            "fesih_nedeni": "İşyeri değişikliği"})
    s = mesleki_egitim.sozlesme_sureleri(db)
    assert [(x.neden, x.son) for x in s] == [("İşyeri değişikliği", date(2026, 11, 16))]
    m = [u for u in takvim.uyarilar(db, date(2026, 11, 10)) if u.konu == "MESEM"]
    assert m and "yeni işletmeyle sözleşme" in m[0].mesaj and m[0].git == "Yerleştirme ve Sözleşmeler"


def test_takvim_ceza_riskleri_ve_muhsgk(okul):
    db, ids = okul
    bugun = date(2026, 10, 20)
    u = takvim.uyarilar(db, bugun)
    sgk = [x for x in u if x.konu == "SGK" and "İsmail" in x.mesaj]
    assert sgk and sgk[0].seviye == "Kritik" and "SÜRESİ GEÇTİ" in sgk[0].mesaj and sgk[0].git == takvim.SGK_EKRANI
    assert any("MUHSGK" in x.mesaj for x in u)
    assert all(x.git for x in u if x.konu in takvim.KONU_EKRANI)
    k = koruma.kritikler(db, bugun)
    assert any("İsmail" in x.mesaj and x.git == takvim.SGK_EKRANI for x in k)
    sgk_beyan.beyan_kaydet(db, 2026, 9, tarih_=date(2026, 10, 15))
    assert not any("MUHSGK" in x.mesaj for x in takvim.uyarilar(db, bugun))


def test_yerlestirme_rehberi(okul):
    db, ids = okul
    rh = koruma.yerlestirme_rehberi(db, ids["yi"], None, bugun=date(2026, 9, 25))
    assert rh.xml_tur == "Giriş" and rh.yerlestirme_ids == [ids["yi"]] and not rh.kritik
    assert rh.satirlar[0].startswith("MESEM çırağı: İsmail Öztürk")
    assert "İşe giriş bildirgesi en geç 30.09.2026" in rh.metin
    assert "Çıraklık sözleşmesi (MESEM) en geç 30.11.2026" in rh.metin

    gec = koruma.yerlestirme_rehberi(db, ids["yi"], None, bugun=date(2026, 10, 5))
    assert gec.kritik and "süresi GEÇTİ" in gec.metin and "dörtte bire" in gec.metin

    db.update("ogrenciler", ids["c"], {"baska_sigortali": 0})
    maol = koruma.yerlestirme_rehberi(db, ids["yc"], None, bugun=date(2026, 9, 25))
    assert maol.satirlar[0].startswith("Açık lise (MAOL) öğrencisi") and "Başka bir işte sigortalı" in maol.metin

    onceki = dict(db.q1("SELECT * FROM yerlestirmeler WHERE id = ?", (ids["ya"],)))
    assert koruma.yerlestirme_rehberi(db, ids["ya"], onceki, bugun=date(2026, 10, 1)) is None

    db.insert("tatiller", {"ad": "Yarıyıl Tatili", "baslangic": "2027-01-25", "bitis": "2027-02-05"})
    db.update("yerlestirmeler", ids["ya"], {"bitis": "2027-01-29"})
    rh = koruma.yerlestirme_rehberi(db, ids["ya"], onceki, bugun=date(2027, 1, 20))
    assert rh.kritik and "Yarıyıl Tatili" in rh.metin and rh.xml_tur is None


def test_toplu_rehber(okul):
    db, ids = okul
    rh = koruma.toplu_rehber(db, [ids["yi"], ids["yc"], ids["ya"]], "Giriş", bugun=date(2026, 9, 28))
    assert rh.xml_tur == "Giriş" and sorted(rh.yerlestirme_ids) == sorted([ids["yi"], ids["yc"]])
    assert "2 öğrenci için işe giriş bildirgesi" in rh.metin and "30.09.2026" in rh.metin
    assert koruma.toplu_rehber(db, [ids["ya"]], "Giriş", bugun=date(2026, 9, 28)) is None


def test_maol_on_kontrol(okul):
    db, ids = okul
    k = [x for x in sgk_beyan.on_kontrol(db, 2026, 10, bugun=date(2026, 11, 2)) if "MAOL" in x.baslik]
    assert k and k[0].git == "Öğrenciler / Çıraklar"


@pytest.fixture(scope="module")
def app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_ui_koruma_bandi_ve_ana_sayfa(app, okul):
    from PySide6.QtTest import QTest
    from koordmes.ui.ana_pencere import AnaPencere
    db, _ = okul
    w = AnaPencere(db)
    w.show()
    w.koruma_denetle()
    for _ in range(80):
        app.processEvents()
        if w.koruma_bandi.kritikler:
            break
        QTest.qWait(50)
    assert w.koruma_bandi.isVisible() and w.koruma_bandi.kritikler
    assert "Ceza riski" in w.koruma_bandi.etiket.text()
    w.koruma_bandi.goster.click()
    assert w.gecerli_sayfa() is w.sayfa[w.koruma_bandi.kritikler[0].git or "Ana Sayfa"]
    ana = w.git("Ana Sayfa")
    for _ in range(80):
        app.processEvents()
        if any(g == takvim.SGK_EKRANI for g in ana.model.kimlikler):
            break
        QTest.qWait(50)
    r = next(i for i, g in enumerate(ana.model.kimlikler) if g == takvim.SGK_EKRANI)
    ana._git(ana.proxy.mapFromSource(ana.model.index(r, 0)))
    assert w.gecerli_sayfa() is w.sayfa[takvim.SGK_EKRANI]
    pencereyi_kapat(w)
