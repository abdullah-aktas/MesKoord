from datetime import date

import pytest

from koordmes.services import aktarim, sgk_karsilastirma as sk, sgk_toplu
from koordmes.services.okuyucu import Tablo

TC = "10000000146"


def _ogrenci(db, ad, sinif, **k):
    a, s = ad.split()
    return db.insert("ogrenciler", {"ad": a, "soyad": s, "sinif_id": sinif, **k})


def _siniflar(db):
    s12 = db.insert("siniflar", {"ad": "12-A", "seviye": 12, "isletme_gunleri": "2,3,4,5"})
    s10 = db.insert("siniflar", {"ad": "10-A", "seviye": 10})
    return s12, s10


def test_toplu_giris_ve_cikis(db):
    s12, s10 = _siniflar(db)
    a = _ogrenci(db, "Ali Can", s12, okul_no="1")
    b = _ogrenci(db, "Ece Su", s10, okul_no="2")
    c = _ogrenci(db, "Veli Tan", s12, okul_no="3")
    _ogrenci(db, "Pasif Kişi", s12, aktif=0)
    db.insert("yerlestirmeler", {"ogrenci_id": c, "tur": "İşletmede Mesleki Eğitim", "baslangic": "2026-09-15",
                                 "durum": "Aktif"})
    t = date(2026, 10, 1)
    adaylar = {x.ogrenci_id: x for x in sgk_toplu.giris_adaylari(db, t)}
    assert set(adaylar) == {a, b}
    assert adaylar[a].onerilen_tur == "İşletmede Mesleki Eğitim"
    assert adaylar[b].onerilen_tur == "Okulda Alan Eğitimi"
    assert [x.ogrenci_id for x in sgk_toplu.giris_adaylari(db, t, [s10])] == [b]

    s = sgk_toplu.toplu_giris(db, [a, b, c], t)
    assert s.yapilan == 2 and len(s.atlanan) == 1 and "açık yerleştirmesi" in s.atlanan[0]
    assert sgk_toplu.giris_adaylari(db, t) == []
    turler = {r["ogrenci_id"]: r["tur"] for r in db.q("SELECT ogrenci_id, tur FROM yerlestirmeler")}
    assert turler[a] == "İşletmede Mesleki Eğitim" and turler[b] == "Okulda Alan Eğitimi"

    cikis = sgk_toplu.cikis_adaylari(db, [s12])
    assert {x.ogrenci_id for x in cikis} == {a, c}
    s = sgk_toplu.toplu_cikis(db, [x.yerlestirme_id for x in cikis], date(2026, 9, 20), "")
    assert s.yapilan == 1 and "başlangıçtan" in s.atlanan[0]  # Ali 01.10'da başladı
    r = db.q1("SELECT bitis, durum FROM yerlestirmeler WHERE ogrenci_id = ?", (c,))
    assert (r["bitis"], r["durum"]) == ("2026-09-20", "Sona Erdi")
    assert {x.ogrenci_id for x in sgk_toplu.cikis_adaylari(db)} == {a, b}
    assert {x.ogrenci_id for x in sgk_toplu.cikis_adaylari(db, sadece_tarihsiz=False)} == {a, b}

    ya = db.q1("SELECT id FROM yerlestirmeler WHERE ogrenci_id = ?", (a,))["id"]
    sgk_toplu.toplu_cikis(db, [ya], date(2026, 11, 3), "Sağlık durumu")
    r = db.q1("SELECT durum, fesih_nedeni FROM yerlestirmeler WHERE id = ?", (ya,))
    assert (r["durum"], r["fesih_nedeni"]) == ("Feshedildi", "Sağlık durumu")
    assert "2 öğrenci için" in sgk_toplu.IslemSonucu(2).metin("x")


def test_liste_disi_kalanlar_ve_bilgi_kontrol(db):
    s12, _ = _siniflar(db)
    yok = _ogrenci(db, "Ali Can", s12)
    sonra = _ogrenci(db, "Ece Su", s12)
    bitti = _ogrenci(db, "Veli Tan", s12)
    tamam = _ogrenci(db, "Ayşe Gül", s12, tc=TC, dogum_tarihi="2009-01-01", cinsiyet="K", veli_tel="5551112233",
                     iban="")
    pasif = _ogrenci(db, "Pasif Kişi", s12, aktif=0, tc="12345678901")
    for oid, b, e in [(sonra, "2026-11-01", None), (bitti, "2026-01-01", "2026-06-30"),
                      (tamam, "2026-09-01", None), (pasif, "2026-09-01", None)]:
        db.insert("yerlestirmeler", {"ogrenci_id": oid, "tur": "İşletmede Mesleki Eğitim", "baslangic": b,
                                     "bitis": e, "durum": "Aktif"})
    out = {}
    for x in sgk_toplu.liste_disi_kalanlar(db, 2026, 10):
        out.setdefault(x.ogrenci_id, []).append(x)
    assert out[yok][0].neden == "Yerleştirme (sigorta) kaydı yok"
    assert "dönemden sonra" in out[sonra][0].neden
    assert "sona ermiş" in out[bitti][0].neden
    assert tamam not in out
    nedenler = [x.neden for x in out[pasif]]
    assert all(x.seviye == "Uyarı" for x in out[pasif])
    assert any("pasif" in n for n in nedenler) and any("geçersiz" in n for n in nedenler)

    eksik = {x.ogrenci_id: x.eksikler for x in sgk_toplu.bilgi_kontrol(db)}
    assert eksik[tamam] == ["IBAN yok (ücret ödemesi)"]
    assert yok not in eksik and pasif not in eksik
    tum = {x.ogrenci_id for x in sgk_toplu.bilgi_kontrol(db, sadece_sigortali=False)}
    assert yok in tum


def test_sgk_listesinden_yerlestirme_olustur(db):
    s12, _ = _siniflar(db)
    o = _ogrenci(db, "Ali Can", s12, tc=TC)
    liste = sk.SgkListesi([sk.SgkKaydi(TC, "ALİ", "CAN", giris=date(2026, 9, 15), cikis=date(2026, 10, 20),
                                       donem=(2026, 10))])
    sonuc = sk.karsilastir(db, liste, 2026, 10)
    fark = next(f for f in sonuc.farklar if f.eylem == "yerlestirme_olustur")
    assert fark.tur == "Okulda yerleştirme yok"
    assert "oluşturuldu" in sk.duzelt(db, fark)
    y = db.q1("SELECT * FROM yerlestirmeler WHERE ogrenci_id = ?", (o,))
    assert (y["tur"], y["baslangic"], y["bitis"], y["durum"]) == ("İşletmede Mesleki Eğitim", "2026-09-15",
                                                                  "2026-10-20", "Sona Erdi")
    assert y["sigorta_giris_bildirildi"] == 1 and y["sigorta_cikis_bildirildi"] == 1
    with pytest.raises(ValueError):
        sk.duzelt(db, fark)
    assert sk.yerlestirme_turu_tahmini(db, o, str(db.ayar("belge_okul_yukumlu"))) == "Okulda Alan Eğitimi"


def test_ogrenci_kunye_ve_acik_lise(db):
    bas = ["Okul No", "Adı", "Soyadı", "T.C. Kimlik No", "Baba Adı", "Anne Adı", "Doğum Yeri", "Nüfusa Kayıtlı İl",
           "Nüfusa Kayıtlı İlçe"]
    t = Tablo("Öğrenci Künye Listesi.xlsx", "Sayfa1",
              [bas, ["12", "AHMET", "YILMAZ", TC, "MEHMET", "AYŞE", "KONYA", "KONYA", "SELÇUKLU"]])
    aktarim.aktar(db, t, "ogrenciler")
    r = db.q1("SELECT * FROM ogrenciler")
    assert (r["baba_adi"], r["anne_adi"], r["dogum_yeri"], r["nufus_il"], r["nufus_ilce"]) == \
        ("Mehmet", "Ayşe", "Konya", "Konya", "Selçuklu")
    assert r["statu"] == "Öğrenci"

    maol = Tablo("Yüz Yüze Eğitim Öğrenci Listesi.xlsx", "Sayfa1",
                 [["Okul No", "Adı", "Soyadı"], ["99", "Can", "Er"]])
    aktarim.aktar(db, maol, "ogrenciler")
    assert db.q1("SELECT statu FROM ogrenciler WHERE okul_no = '99'")["statu"] == "Açık Lise"
    assert not aktarim.acik_lise_listesi(t, 0)

    aktarim.aktar(db, Tablo("liste.xlsx", "S", [["Okul No", "Adı", "Soyadı"], ["77", "Su", "Ak"]]), "ogrenciler",
                  sec=aktarim.Secenekler(ogrenci_statusu="Çırak"))
    assert db.q1("SELECT statu FROM ogrenciler WHERE okul_no = '77'")["statu"] == "Çırak"


def test_devamsizlik_tarih_araligi_otomatik_yer_ve_okul_ici_sigorta(db):
    s12, s10 = _siniflar(db)
    a = _ogrenci(db, "Ali Can", s12, okul_no="1")
    b = _ogrenci(db, "Ece Su", s10, okul_no="2")
    db.insert("yerlestirmeler", {"ogrenci_id": b, "tur": "Okulda Alan Eğitimi", "baslangic": "2026-09-01",
                                 "durum": "Aktif"})
    bas = ["Öğrenci No", "Adı Soyadı", "Tarih", "Türü"]
    satirlar = [["1", "Ali Can", "05.10.2026", "Özürsüz"],   # pazartesi: okul günü
                ["1", "Ali Can", "06.10.2026", "Özürsüz"],   # salı: işletme günü
                ["2", "Ece Su", "07.10.2026", "Özürsüz"],
                ["2", "Ece Su", "15.11.2026", "Özürsüz"]]    # aralık dışı
    sec = aktarim.Secenekler(devamsizlik_yeri="Otomatik", bas=date(2026, 10, 1), bit=date(2026, 10, 31))
    s = aktarim.aktar(db, Tablo("d", "d", [bas] + satirlar), "devamsizlik", sec=sec)
    assert s.eklenen == 3 and s.atlanan == 1
    rows = {(r["ogrenci_id"], r["tarih"]): (r["yer"], r["sgk_eksik"]) for r in db.q("SELECT * FROM devamsizlik")}
    assert rows[(a, "2026-10-05")] == ("Okul", 0)
    assert rows[(a, "2026-10-06")] == ("İşletme", 1)
    assert rows[(b, "2026-10-07")] == ("Okul", 1)
