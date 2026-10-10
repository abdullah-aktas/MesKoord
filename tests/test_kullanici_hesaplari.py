import json
import sqlite3

import pytest

from koordmes import hesaplar as H
from koordmes.db import Database


@pytest.fixture
def yerel(tmp_path, monkeypatch):
    monkeypatch.setenv("MESKOORD_DATA", str(tmp_path / "data"))
    d = Database(tmp_path / "h.db")
    yield d
    d.close()


def _hesaplar(db):
    yonetici = H.hesaplari_ac(db, "Ayşe Yılmaz", "ayse", "yonetici-1")
    pid = H.kullanici_ekle(db, "Mehmet Kaya", "mehmet", H.PERSONEL, "personel-1")
    iid = H.kullanici_ekle(db, "Zeynep Ak", "zeynep", H.IZLEYICI, "izleyici-1")
    return yonetici, pid, iid


def test_hesaplar_kapaliyken_herkes_tam_yetkili_ve_gunluk_tutulur(yerel):
    assert not H.hesaplar_acik(yerel)
    assert yerel.kimlik.yonetici
    oid = yerel.insert("ogrenciler", {"ad": "Ali", "soyad": "Veli", "tc": "12345678901"})
    yerel.update("ogrenciler", oid, {"okul_no": "17", "tc": "10987654321"})
    yerel.update("ogrenciler", oid, {"okul_no": "17"})  # değişiklik yok: günlüğe yazılmaz
    yerel.delete("ogrenciler", oid)
    g = yerel.q("SELECT * FROM islem_gunlugu WHERE tablo = 'ogrenciler' ORDER BY id")
    assert [r["islem"] for r in g] == ["Ekleme", "Değişiklik", "Silme"]
    assert all(r["kayit"] == "Ali Veli" and r["kayit_id"] == oid for r in g)
    assert g[0]["kullanici"] == yerel.kimlik.ad
    degisen = json.loads(g[1]["ayrinti"])
    assert degisen["okul_no"] == ["", "17"]
    assert degisen["tc"] == ["***", "***"]  # kişisel veri günlüğe açık yazılmaz


def test_gunluk_elle_degistirilemez_ve_aynı_ayar_gunluge_girmez(yerel):
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        yerel.execute("DELETE FROM islem_gunlugu")
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        yerel.execute("INSERT INTO islem_gunlugu (zaman, islem, tablo) VALUES ('x', 'y', 'z')")
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        yerel.execute("DROP TRIGGER temp.kg_ogrenciler_i")
    ham = yerel.q1("SELECT deger FROM ayarlar WHERE anahtar = 'asgari_ucret_net'")["deger"]
    yerel.ayar_yaz("asgari_ucret_net", ham)
    assert yerel.q1("SELECT COUNT(*) n FROM islem_gunlugu")["n"] == 0
    yerel.ayar_yaz("asgari_ucret_net", 30000)
    r = yerel.q1("SELECT * FROM islem_gunlugu")
    assert (r["islem"], r["kayit"]) == ("Değişiklik", "asgari_ucret_net")


def test_roller_yerelde_uygulanir(yerel, tmp_path):
    yon, pid, iid = _hesaplar(yerel)
    assert H.hesaplar_acik(yerel)
    assert H.dogrula(yerel.path, "MEHMET", "yanlis-parola") is None
    personel = H.dogrula(yerel.path, "MEHMET", "personel-1")
    assert personel.rol == H.PERSONEL and personel.parola_degistirmeli and personel.ad == "Mehmet Kaya"
    assert yerel.q1("SELECT parola_ozeti FROM kullanicilar WHERE id = ?", (pid,))["parola_ozeti"] is None

    yerel.kimlik_ata(personel)
    yerel.insert("ogrenciler", {"ad": "Can", "soyad": "Er"})
    for sql in ["UPDATE kurum SET ad = 'X' WHERE id = 1", "UPDATE ayarlar SET deger = '1' WHERE anahtar = 'x'",
                "DELETE FROM kullanicilar", "UPDATE kullanicilar SET rol = 'yonetici'", "DROP TABLE evrak"]:
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            yerel.execute(sql)
    with pytest.raises(sqlite3.IntegrityError, match="kendi parolanızı"):
        H.parola_ata(yerel, yon.id, "baskasinin")
    H.kendi_parolasini_degistir(yerel, "personel-1", "yeni-parola")
    assert not yerel.kimlik.parola_degistirmeli
    assert H.dogrula(yerel.path, "mehmet", "yeni-parola") is not None
    with pytest.raises(ValueError, match="yanlış"):
        H.kendi_parolasini_degistir(yerel, "eski-yanlis", "baska-parola")
    kopya = yerel.kopya()
    try:
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            kopya.execute("UPDATE kurum SET ad = 'X' WHERE id = 1")
    finally:
        kopya.close()
    gunluk = yerel.q1("SELECT * FROM islem_gunlugu WHERE tablo = 'ogrenciler'")
    assert gunluk["kullanici"] == "Mehmet Kaya"

    yerel.kimlik_ata(H.dogrula(yerel.path, "zeynep", "izleyici-1"))
    assert yerel.q("SELECT * FROM ogrenciler")
    with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
        yerel.insert("ogrenciler", {"ad": "Yok", "soyad": "Yok"})


def test_son_yonetici_korunur_ve_hesaplar_kapatilabilir(yerel):
    yon, pid, _ = _hesaplar(yerel)
    with pytest.raises(ValueError, match="En az bir etkin yönetici"):
        H.kullanici_guncelle(yerel, yon.id, "Ayşe Yılmaz", H.PERSONEL, True)
    with pytest.raises(ValueError, match="zaten var"):
        H.kullanici_ekle(yerel, "Başka", "Ayse", H.PERSONEL, "123456")
    with pytest.raises(ValueError, match="boşluk"):
        H.kullanici_ekle(yerel, "Başka", "ay se", H.PERSONEL, "123456")
    H.kullanici_guncelle(yerel, pid, "Mehmet Kaya", H.YONETICI, True)
    H.kullanici_guncelle(yerel, yon.id, "Ayşe Yılmaz", H.PERSONEL, False)
    assert H.dogrula(yerel.path, "ayse", "yonetici-1") is None  # pasif hesap giremez
    H.hesaplari_kapat(yerel)
    assert not H.hesaplar_acik(yerel)


def test_gunluk_saklama_suresi(yerel):
    yerel.insert("alanlar", {"ad": "Bilişim"})
    c = sqlite3.connect(str(yerel.path))
    with c:
        c.execute("UPDATE islem_gunlugu SET zaman = '2020-01-01 10:00:00'")
    c.close()
    H.gunlugu_temizle(yerel.path)
    assert yerel.q1("SELECT COUNT(*) n FROM islem_gunlugu")["n"] == 0


def test_agda_kisisel_hesaplarla_giris_ve_yetki(sunucu):
    from conftest import baglanti_bilgisi
    from koordmes.ag.istemci import ParolaHatasi, UzakDatabase
    yerel = sunucu.yerel_db
    _hesaplar(yerel)

    with pytest.raises(ParolaHatasi) as e:  # sunucu parolası artık geçmez
        UzakDatabase(baglanti_bilgisi(sunucu))
    assert e.value.hesap

    b = baglanti_bilgisi(sunucu, kullanici="mehmet")
    b.parola = "personel-1"
    d = UzakDatabase(b)
    try:
        assert d.kimlik.rol == H.PERSONEL and d.kimlik.ad == "Mehmet Kaya" and d.kimlik.parola_degistirmeli
        oid = d.insert("ogrenciler", {"ad": "Ağdan", "soyad": "Gelen"})
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            d.execute("UPDATE kurum SET ad = 'X' WHERE id = 1")
        assert d.q1("SELECT parola_ozeti FROM kullanicilar WHERE kullanici_adi = 'ayse'")["parola_ozeti"] is None
        r = yerel.q1("SELECT * FROM islem_gunlugu WHERE tablo = 'ogrenciler' AND kayit_id = ?", (oid,))
        assert (r["kullanici"], r["bilgisayar"]) == ("Mehmet Kaya", "PC-mehmet")
        assert {k["kullanici"] for k in sunucu.kullanicilar()} >= {"Mehmet Kaya"}

        yol = d.yedekle()  # personel: yedek sunucuda alınır, dosya indirilmez
        assert not yol.exists() and list((sunucu.yol.parent / "data" / "Yedekler").glob("*.db"))
        with pytest.raises(sqlite3.OperationalError, match="yalnızca yönetici"):
            d.geri_yukle(sunucu.yol)

        H.kendi_parolasini_degistir(d, "personel-1", "agda-yeni")
        k = d.kopya()  # arka plan bağlantısı yeni parolayla açılır
        k.close()
    finally:
        d.close()

    b = baglanti_bilgisi(sunucu, kullanici="zeynep")
    b.parola = "izleyici-1"
    d = UzakDatabase(b)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
            d.insert("ogrenciler", {"ad": "Yok", "soyad": "Yok"})
    finally:
        d.close()
