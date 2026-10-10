"""Çok kullanıcılı (ağ) çalışma: uzak veritabanı yerel veritabanıyla aynı davranmalı."""
import sqlite3
import threading
import time
from datetime import date

import pytest
from conftest import TEST_PAROLASI, baglanti_bilgisi

from koordmes import lisans
from koordmes.ag import protokol as P
from koordmes.ag.istemci import (OlayDinleyici, ParmakIziHatasi, ParolaHatasi, UzakDatabase, sunucu_bilgisi)


def test_temel_islemler_ve_satir(uzak_db):
    i = uzak_db.insert("alanlar", {"ad": "Bilişim Teknolojileri", "kod": "BT"})
    assert i > 0
    r = uzak_db.q1("SELECT id, ad AS Ad, kod FROM alanlar WHERE id = ?", (i,))
    assert r["ad"] == r["AD"] == r[1] == "Bilişim Teknolojileri"
    assert r.keys() == ["id", "Ad", "kod"] and dict(r)["kod"] == "BT" and tuple(r)[0] == i
    uzak_db.update("alanlar", i, {"kod": "BİL"})
    assert uzak_db.q1("SELECT kod FROM alanlar WHERE id = ?", (i,))[0] == "BİL"
    assert uzak_db.columns("alanlar")[:2] == ["id", "ad"]
    uzak_db.ayar_yaz("asgari_ucret_brut", "40000,5")
    assert uzak_db.ayar("asgari_ucret_brut") == pytest.approx(40000.5)
    uzak_db.delete("alanlar", i)
    assert uzak_db.q1("SELECT * FROM alanlar WHERE id = ?", (i,)) is None
    cur = uzak_db.conn.execute("SELECT 1 AS a UNION SELECT 2")
    assert [r["a"] for r in cur] == [1, 2]
    assert uzak_db.conn.execute("SELECT ?, ?, ?", (b"\x00\x01", date(2026, 9, 1), True)).fetchone()[:] == \
        (b"\x00\x01", "2026-09-01", 1)


def test_islem_savepoint_ve_hatalar(uzak_db):
    c = uzak_db.conn
    c.commit()
    c.execute("BEGIN")
    c.execute("INSERT INTO alanlar (ad) VALUES ('A')")
    c.execute("SAVEPOINT satir")
    c.execute("INSERT INTO alanlar (ad) VALUES ('B')")
    c.execute("ROLLBACK TO satir")
    c.execute("RELEASE satir")
    assert c.in_transaction
    c.commit()
    assert [r["ad"] for r in uzak_db.q("SELECT ad FROM alanlar ORDER BY ad")] == ["A"]
    with pytest.raises(sqlite3.IntegrityError):
        uzak_db.insert("ogrenciler", {"ad": None})
    with pytest.raises(sqlite3.OperationalError):
        uzak_db.q("SELECT * FROM olmayan_tablo")
    with pytest.raises(sqlite3.DatabaseError):
        uzak_db.q("ATTACH DATABASE 'x.db' AS x")
    try:
        with c:
            c.execute("INSERT INTO alanlar (ad) VALUES ('C')")
            raise RuntimeError
    except RuntimeError:
        pass
    assert not c.in_transaction
    assert uzak_db.q1("SELECT COUNT(*) FROM alanlar WHERE ad = 'C'")[0] == 0
    c.executemany("INSERT INTO alanlar (ad) VALUES (?)", [("D",), ("E",)])
    c.commit()
    assert uzak_db.q1("SELECT COUNT(*) FROM alanlar")[0] == 3


def test_iki_istemci_ayni_veriyi_gorur_ve_bildirim_alir(sunucu):
    a = UzakDatabase(baglanti_bilgisi(sunucu, "ayse"))
    bilgi_b = baglanti_bilgisi(sunucu, "mehmet")
    bilgi_b.istemci = "baska-program"
    b = UzakDatabase(bilgi_b)
    olaylar, durumlar = [], []
    gelen = threading.Event()
    d = OlayDinleyici(bilgi_b, lambda o: (olaylar.append(o), gelen.set()), lambda ok, m: durumlar.append(ok))
    d.start()
    try:
        bas = time.monotonic()
        while not d.bagli and time.monotonic() - bas < 5:
            time.sleep(0.05)
        a.insert("alanlar", {"ad": "Muhasebe"})
        assert gelen.wait(5), "bildirim gelmedi"
        o = olaylar[-1]["olaylar"][-1]
        assert o["kim"] == "ayse" and "alanlar" in o["tablolar"]
        assert b.q1("SELECT ad FROM alanlar")["ad"] == "Muhasebe"
        adlar = {k["kullanici"] for k in d.kullanicilar}
        assert {"ayse", "mehmet", "sunucu"} <= adlar
        # sunucu bilgisayarının kendi (yerel) değişikliği de bildirilir
        gelen.clear()
        sunucu.yerel_db.insert("alanlar", {"ad": "Elektrik"})
        assert gelen.wait(5)
        assert olaylar[-1]["olaylar"][-1]["kim"] == "sunucu"
    finally:
        d.durdur()
        a.close()
        b.close()


def test_eszamanli_yazma_kilitlenmeden_tamamlanir(sunucu):
    hatalar = []

    def yaz(no):
        d = UzakDatabase(baglanti_bilgisi(sunucu, f"k{no}"))
        try:
            for i in range(25):
                with d.conn:
                    d.conn.execute("INSERT INTO alanlar (ad) VALUES (?)", (f"{no}-{i}",))
        except Exception as e:  # noqa: BLE001
            hatalar.append(e)
        finally:
            d.close()

    isler = [threading.Thread(target=yaz, args=(n,)) for n in range(4)]
    for t in isler:
        t.start()
    for t in isler:
        t.join(60)
    assert not hatalar
    assert sunucu.yerel_db.q1("SELECT COUNT(*) FROM alanlar")[0] == 100


def test_guvenlik_parola_ve_sertifika(sunucu):
    yanlis = baglanti_bilgisi(sunucu)
    yanlis.parola = "yanlış"
    with pytest.raises(ParolaHatasi):
        UzakDatabase(yanlis)
    sahte = baglanti_bilgisi(sunucu)
    sahte.parmak_izi = "0" * 64
    with pytest.raises(ParmakIziHatasi) as e:
        UzakDatabase(sahte)
    assert e.value.yeni_iz == sunucu.parmak_izi and not e.value.ilk
    iz, bilgi = sunucu_bilgisi("127.0.0.1", sunucu.port)
    assert iz == sunucu.parmak_izi and bilgi["ad"] == "SINAMA"
    assert P.dogrulama_kodu(iz).count("-") == 3
    assert P.parola_dogru(TEST_PAROLASI, sunucu.parola_ozeti) and not P.parola_dogru("x", sunucu.parola_ozeti)


def test_oturum_dusunce_yeniden_baglanir(sunucu, uzak_db):
    uzak_db.insert("alanlar", {"ad": "A"})
    for o in list(sunucu.oturumlar.values()):
        sunucu.oturumu_kapat(o.anahtar)
    assert uzak_db.q1("SELECT COUNT(*) FROM alanlar")[0] == 1
    uzak_db.conn.execute("INSERT INTO alanlar (ad) VALUES ('B')")
    for o in list(sunucu.oturumlar.values()):
        sunucu.oturumu_kapat(o.anahtar)
    with pytest.raises(sqlite3.OperationalError, match="geri alındı"):
        uzak_db.conn.commit()
    assert uzak_db.q1("SELECT COUNT(*) FROM alanlar")[0] == 1


def test_kopya_yedek_ve_geri_yukleme(sunucu, uzak_db, tmp_path):
    uzak_db.insert("alanlar", {"ad": "Önce"})
    k = uzak_db.kopya()
    assert k.uzak and k.q1("SELECT ad FROM alanlar")["ad"] == "Önce"
    k.close()
    yedek = uzak_db.yedekle()
    assert yedek.exists() and yedek.stat().st_size > 0
    uzak_db.insert("alanlar", {"ad": "Sonra"})
    uzak_db.geri_yukle(yedek)
    assert [r["ad"] for r in uzak_db.q("SELECT ad FROM alanlar")] == ["Önce"]
    with pytest.raises(sqlite3.DatabaseError):
        bozuk = tmp_path / "bozuk.db"
        bozuk.write_bytes(b"bu bir veritabani degil")
        uzak_db.geri_yukle(bozuk)


def test_sunucu_lisansi_istemciye_gecer(sunucu, uzak_db):
    assert lisans.SUNUCU_LISANSLARI == lisans.lisans_metinleri()


def test_ornek_veri_agda_yerel_ile_ayni(uzak_db, tmp_path):
    from koordmes.db import Database
    from koordmes.services import ornek_veri
    ornek_veri.yukle(uzak_db, programi_coz=False)
    yerel = Database(tmp_path / "yerel.db")
    ornek_veri.yukle(yerel, programi_coz=False)
    for t in ("ogrenciler", "isletmeler", "yerlestirmeler", "ogretmenler"):
        assert [tuple(r) for r in uzak_db.q(f"SELECT * FROM {t} ORDER BY id")] == \
            [tuple(r) for r in yerel.q(f"SELECT * FROM {t} ORDER BY id")]
    yerel.close()


def test_ayarlar_dosyasi_ve_parola_gizleme(tmp_path, monkeypatch):
    monkeypatch.setenv("MESKOORD_DATA", str(tmp_path))
    a = P.AgAyarlari(kip=P.KIP_ISTEMCI, adres="192.168.1.10")
    a.parola = "gizli parola"
    a.kaydet()
    assert "gizli parola" not in P.AgAyarlari.yol().read_text("utf-8")
    b = P.AgAyarlari.yukle()
    assert b.kip == P.KIP_ISTEMCI and b.adres == "192.168.1.10" and b.parola == "gizli parola"
