import base64
import importlib.util
import os
from datetime import date, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from koordmes import config, lisans


@pytest.fixture
def anahtar(monkeypatch, tmp_path):
    ozel = Ed25519PrivateKey.generate()
    acik = base64.b64encode(ozel.public_key().public_bytes(serialization.Encoding.Raw,
                                                           serialization.PublicFormat.Raw)).decode()
    monkeypatch.setattr(lisans, "ACIK_ANAHTARLAR", {"T1": acik})
    ortak = tmp_path / "ProgramData" / "MesKoord"
    monkeypatch.setattr(lisans, "ortak_klasor", lambda: ortak)
    monkeypatch.setattr(lisans, "program_klasoru", lambda: tmp_path / "Program")
    return ozel


def _lisans(ozel, **kw):
    veri = {"lisans_no": "KM-2026-0001", "kurum_kodu": "123456", "kurum_adi": "Deneme MTAL", "il": "Ankara",
            "ilce": "Çankaya", "baslangic": "2026-09-01", "bitis": "2027-08-31"}
    veri.update(kw)
    return lisans.imzala(veri, ozel, "T1")


def test_imza_dogrulanir_degistirilince_reddedilir(anahtar):
    veri = _lisans(anahtar)
    assert lisans.dogrula(veri).kurum_adi == "Deneme MTAL"
    with pytest.raises(lisans.LisansHatasi, match="imza"):
        lisans.dogrula({**veri, "kurum_adi": "Başka Okul"})
    with pytest.raises(lisans.LisansHatasi, match="imza"):
        lisans.dogrula({**veri, "bitis": "2099-08-31"})
    with pytest.raises(lisans.LisansHatasi, match="tanınmayan"):
        lisans.dogrula({**veri, "anahtar": "X9"})
    baska = lisans.imzala(veri, Ed25519PrivateKey.generate(), "T1")
    with pytest.raises(lisans.LisansHatasi):
        lisans.dogrula(baska)


def test_lisans_kodu_e_postadan_bolunmus_gelse_de_cozulur(anahtar):
    veri = _lisans(anahtar)
    kod = lisans.kodla(veri)
    bolunmus = "Merhaba,\n\n" + "\n".join(kod[i:i + 60] for i in range(0, len(kod), 60)) + "\n"
    assert lisans.dogrula(lisans.coz(bolunmus)).lisans_no == "KM-2026-0001"
    assert lisans.coz(lisans.dosya_metni(veri)) == veri


def test_deneme_suresi_ve_sifirlanamamasi(db, anahtar):
    bas = date(2026, 10, 1)
    d = lisans.durum(db, bas)
    assert d.seviye == lisans.DENEME and d.kalan_gun == 30 and d.calisir
    assert lisans.durum(db, bas + timedelta(days=29)).kalan_gun == 1
    assert lisans.durum(db, bas + timedelta(days=30)).seviye == lisans.KAPALI

    db.ayar_yaz(lisans.AYAR_DENEME, "")
    db.ayar_yaz(lisans.AYAR_SON_GORULME, "")
    assert lisans.durum(db, bas + timedelta(days=30)).seviye == lisans.KAPALI


def test_tarih_geri_alinirsa_son_gorulen_tarih_esas_alinir(db, anahtar):
    lisans.durum(db, date(2026, 10, 25))
    d = lisans.durum(db, date(2026, 10, 1))
    assert d.tarih_uyarisi and d.kalan_gun == 30
    assert lisans.etkin_tarih(db, date(2026, 10, 1))[0] == date(2026, 10, 25)
    assert lisans.etkin_tarih(db, date(2026, 10, 24))[1] == ""


def test_lisans_yuklenince_kurum_kilitlenir_ve_sureler(db, anahtar):
    lis = lisans.kaydet(lisans.kodla(_lisans(anahtar)))
    assert lis.kaynak == config.data_dir() / lisans.DOSYA_ADI
    lisans.kurum_uygula(db, lis)
    k = db.kurum()
    assert (k["ad"], k["kurum_kodu"], k["il"], k["ilce"]) == ("Deneme MTAL", "123456", "Ankara", "Çankaya")

    d = lisans.durum(db, date(2027, 8, 1))
    assert d.seviye == lisans.LISANSLI and d.kalan_gun == 30
    d = lisans.durum(db, date(2027, 9, 10))
    assert d.seviye == lisans.TOLERANS and d.calisir and d.kalan_gun == 20
    d = lisans.durum(db, date(2027, 10, 1))
    assert d.seviye == lisans.KAPALI and not d.calisir


def test_suresiz_ve_ortak_klasordeki_lisans(db, anahtar):
    ortak = lisans.ortak_klasor()
    ortak.mkdir(parents=True)
    (ortak / lisans.DOSYA_ADI).write_text(lisans.dosya_metni(_lisans(anahtar, bitis="")), encoding="utf-8")
    d = lisans.durum(db, date(2040, 1, 1))
    assert d.seviye == lisans.LISANSLI and d.kalan_gun is None

    (config.data_dir() / lisans.DOSYA_ADI).write_text("{bozuk", encoding="utf-8")
    lis, hatalar = lisans.bul()
    assert lis is not None and len(hatalar) == 1


def test_talep_metni_lisans_yoneticisinde_okunur(db):
    db.update("kurum", 1, {"ad": "İnönü MTAL", "kurum_kodu": "765432", "il": "İzmir", "ilce": "Bornova"})
    d = lisans.talep_coz(lisans.talep_metni(db, {"eposta": "okul@meb.k12.tr"}))
    assert d["kurum_kodu"] == "765432" and d["kurum_adi"] == "İnönü MTAL"
    assert d["il"] == "İzmir" and d["ilce"] == "Bornova" and d["eposta"] == "okul@meb.k12.tr"


def _yonetici(monkeypatch, tmp_path):
    monkeypatch.setenv("MESKOORD_LISANS_DIZINI", str(tmp_path / "yonetim"))
    yol = Path(__file__).resolve().parents[1] / "araclar" / "lisans_yonetici.py"
    spec = importlib.util.spec_from_file_location("lisans_yonetici_test", yol)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_lisans_yonetici_uretir_numaralar_ve_kaydeder(monkeypatch, tmp_path, db):
    m = _yonetici(monkeypatch, tmp_path)
    _, acik = m.anahtar_olustur("T1", "gizli-sifre")
    monkeypatch.setattr(lisans, "ACIK_ANAHTARLAR", {"T1": acik})
    with pytest.raises(SystemExit, match="yanlış"):
        m.ozel_anahtar_yukle(sifre_sor=lambda: "yanlis")

    veri, yol = m.lisans_uret("123456", "Deneme  MTAL", date(2026, 9, 1), date(2027, 8, 31), il="Ankara",
                              fatura_no="F-1", sifre_sor=lambda: "gizli-sifre")
    assert veri["kurum_adi"] == "Deneme MTAL"
    assert lisans.oku(yol).lisans_no == veri["lisans_no"]
    assert (yol.parent / (yol.stem + "_KOD.txt")).read_text(encoding="utf-8").count(lisans.KOD_ONEKI) == 1
    veri2, _ = m.lisans_uret("654321", "Öteki MEM", date(2026, 9, 1), None, sifre_sor=lambda: "gizli-sifre")
    assert int(veri2["lisans_no"][-4:]) == int(veri["lisans_no"][-4:]) + 1 and veri2["bitis"] == ""
    assert [k["fatura_no"] for k in m.kayitlar()] == ["F-1", ""]

    with pytest.raises(SystemExit, match="rakam"):
        m.lisans_uret("12A", "X", date(2026, 9, 1), None, sifre_sor=lambda: "gizli-sifre")
    m.sifre_degistir(None, lambda: "gizli-sifre", None)
    m.ozel_anahtar_yukle()


def test_programdaki_acik_anahtar_tanimli():
    assert lisans.ACIK_ANAHTARLAR, "Dağıtım paketinde en az bir açık anahtar olmalı"
    for acik in lisans.ACIK_ANAHTARLAR.values():
        assert len(base64.b64decode(acik)) == 32
    assert os.path.basename(lisans.__file__) == "lisans.py"
