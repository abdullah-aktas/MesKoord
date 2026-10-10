from koordmes.services import sigorta, toplu_giris, ucret
from koordmes.services.toplu_giris import GIRIS_SOZLUK, HIZLI


def _satir(**kw):
    return [kw.get(s.anahtar, "") for s in HIZLI.sutunlar]


def test_hizli_giris_ogrenci_sinif_isletme_yerlestirme(db):
    satirlar = [
        _satir(tc="10000000146", ad_soyad="AYŞE YILMAZ", sinif="11/A", program="MEM", statu="Çırak",
               bakmakla_yukumlu="H", isletme="Usta Mobilya Ltd. Şti.", personel_sayisi="8", baslangic="01.09.2026"),
        _satir(ad_soyad="Mehmet Demir", sinif="11-A", bakmakla_yukumlu="E", isletme="Usta Mobilya",
               baslangic="15.09.2026"),
        [""] * len(HIZLI.sutunlar),
    ]
    sonuclar, durumlar = toplu_giris.kaydet(db, HIZLI, satirlar)
    assert set(durumlar) == {0, 1}
    assert all(d.durum in ("eklendi", "guncellendi") for d in durumlar.values()), durumlar
    assert db.q1("SELECT COUNT(*) n FROM isletmeler")["n"] == 1
    assert db.q1("SELECT program FROM siniflar WHERE ad = '11-A'")["program"] == "MEM"
    ayse = db.q1("SELECT * FROM ogrenciler WHERE tc = '10000000146'")
    assert ayse["ad"] == "Ayşe" and ayse["bakmakla_yukumlu"] == 0 and ayse["statu"] == "Çırak"

    sgk = {s.ad: s for s in sigorta.aylik_liste(db, 2026, 9)}
    assert sgk["Ayşe"].belge_turu == "42" and sgk["Ayşe"].gun == 30
    assert sgk["Mehmet"].belge_turu == "7" and sgk["Mehmet"].gun == 16
    ucretler = ucret.aylik_hesap(db, 2026, 9)
    assert len(ucretler) == 2 and all(u.dk_pay == 1.0 for u in ucretler)


def test_deneme_kaydetmez(db):
    satirlar = [_satir(ad_soyad="Ali Kaya", sinif="10-B", isletme="Kaya Oto", baslangic="01.09.2026")]
    _, durumlar = toplu_giris.kaydet(db, HIZLI, satirlar, deneme=True)
    assert durumlar[0].durum == "eklendi"
    assert db.q1("SELECT COUNT(*) n FROM ogrenciler")["n"] == 0


def test_excelden_basliklarla_yapistirma_ad_soyad_birlesir():
    metin = "Soyadı\tAdı\tTC Kimlik No\tİşletme\r\nYILMAZ\tAYŞE\t10000000146\tUsta Mobilya\r\n"
    satirlar = toplu_giris.yapistirilan_metin(metin)
    es = toplu_giris.basliklari_esle(HIZLI, satirlar[0])
    sira = [s.anahtar for s in HIZLI.sutunlar]
    assert es[sira.index("tc")] == [2]
    assert es[sira.index("isletme")] == [3]
    assert es[sira.index("ad_soyad")] == [1, 0]


def test_basliksiz_yapistirma_eslenmez():
    assert toplu_giris.basliklari_esle(HIZLI, ["10000000146", "Ayşe Yılmaz", "11-A"]) is None


def test_denetim_bulgulari():
    satirlar = [_satir(tc="12345678901", ad_soyad="Ali", isletme="X", baslangic="31.02.2026",
                       bakmakla_yukumlu="belki", personel_sayisi="çok")]
    mesajlar = {b.mesaj for b in toplu_giris.denetle(HIZLI, satirlar)}
    assert "T.C. kimlik no geçersiz" in mesajlar
    assert any("tarih" in m for m in mesajlar)
    assert any("E veya H" in m for m in mesajlar)
    assert any("sayı olmalı" in m for m in mesajlar)
    assert not toplu_giris.denetle(HIZLI, [[""] * len(HIZLI.sutunlar)])


def test_tek_turlu_giris_isletmeler(db):
    tur = GIRIS_SOZLUK["isletmeler"]
    sira = [s.anahtar for s in tur.sutunlar]
    r = [""] * len(sira)
    r[sira.index("ad")], r[sira.index("personel_sayisi")], r[sira.index("kamu_kurumu")] = "Derik Fırın", "25", "H"
    _, durumlar = toplu_giris.kaydet(db, tur, [r])
    assert durumlar[0].durum == "eklendi"
    assert db.q1("SELECT personel_sayisi FROM isletmeler")["personel_sayisi"] == 25
    assert [s for s in tur.sutunlar if s.anahtar == "kamu_kurumu"][0].secenekler == ("E", "H")


def test_taslak_kaydet_yukle(db):
    satirlar = [_satir(ad_soyad="Ali Kaya", isletme="Kaya Oto"), [""] * len(HIZLI.sutunlar)]
    toplu_giris.taslak_kaydet(HIZLI, satirlar)
    geri = toplu_giris.taslak_yukle(HIZLI)
    assert len(geri) == 1 and geri[0][1] == "Ali Kaya"
    toplu_giris.taslak_kaydet(HIZLI, [])
    assert toplu_giris.taslak_yukle(HIZLI) == []
