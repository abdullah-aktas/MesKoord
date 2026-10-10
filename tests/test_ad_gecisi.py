"""1.3.0 ad değişikliği (KoordMES -> MesKoord): eski klasör, dosya, lisans ve ayarların taşınması."""
import os
from datetime import datetime
from pathlib import Path

import pytest

from koordmes import config, lisans, yedekleme


@pytest.fixture
def ev(monkeypatch, tmp_path):
    for d in ("MESKOORD_DATA", "KOORDMES_DATA"):
        monkeypatch.delenv(d, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(config, "_secilen", {})
    (tmp_path / "Documents").mkdir()
    return tmp_path / "Documents"


def test_eski_veri_klasoru_ve_veritabani_tasinir(ev):
    eski = ev / "KoordMES"
    (eski / "Yedekler").mkdir(parents=True)
    (eski / "koordmes.db").write_bytes(b"veri")
    (eski / "koordmes.db-shm").write_bytes(b"")
    (eski / ".koordmes_kurulum").write_text("2026-01-05", encoding="ascii")
    assert config.data_dir() == ev / "MesKoord" and not eski.exists()
    assert config.db_path() == ev / "MesKoord" / "meskoord.db"
    assert config.db_path().read_bytes() == b"veri"
    assert not (ev / "MesKoord" / "koordmes.db-shm").exists()
    assert lisans._isaret_tarihi().isoformat() == "2026-01-05"


def test_yarim_islem_gunlugu_varsa_veritabani_eski_adla_kalir(ev):
    eski = ev / "KoordMES"
    eski.mkdir()
    (eski / "koordmes.db").write_bytes(b"veri")
    (eski / "koordmes.db-wal").write_bytes(b"gunluk")
    assert config.db_path() == ev / "MesKoord" / "koordmes.db"


def test_yeni_klasor_varsa_eskisine_dokunulmaz(ev):
    (ev / "KoordMES").mkdir()
    (ev / "MesKoord").mkdir()
    assert config.data_dir() == ev / "MesKoord" and (ev / "KoordMES").exists()


def test_ortam_degiskeni_eski_adla_da_calisir(monkeypatch, tmp_path):
    monkeypatch.delenv("MESKOORD_DATA", raising=False)
    monkeypatch.setenv("KOORDMES_DATA", str(tmp_path / "eski_degisken"))
    assert config.data_dir() == tmp_path / "eski_degisken"


def test_eski_ve_yeni_yedekler_birlikte_siralanir_ve_temizlenir(tmp_path):
    from koordmes.db import eski_yedekleri_temizle
    for ad in ("koordmes_20260101_120000_000.db", "koordmes_20260301_120000_000.db",
               config.yedek_adi(datetime(2026, 2, 1, 12)), config.yedek_adi(datetime(2026, 4, 1, 12))):
        (tmp_path / ad).write_bytes(b"")
    assert [p.name[9:17] for p in config.yedek_dosyalari(tmp_path)] == ["20260101", "20260201", "20260301",
                                                                       "20260401"]
    eski_yedekleri_temizle(tmp_path, 2)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["koordmes_20260301_120000_000.db",
                                                          "meskoord_20260401_120000_000.db"]


def test_usb_yedek_klasoru_yeni_adina_tasinir(tmp_path):
    eski = tmp_path / "KoordMES_Yedekler"
    eski.mkdir()
    (eski / "koordmes_20260101_120000_000.db").write_bytes(b"")
    yedek = tmp_path / "meskoord_20260201_120000_000.db"
    yedek.write_bytes(b"x")
    kopya = yedekleme.ikinci_klasore_kopyala(yedek, str(tmp_path))
    assert kopya.parent.name == "MesKoord_Yedekler" and not eski.exists()
    assert len(list(kopya.parent.glob("*.db"))) == 2


def test_eski_urun_adli_lisans_ve_eski_programdata_klasoru(monkeypatch, tmp_path):
    import base64
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    ozel = Ed25519PrivateKey.generate()
    acik = base64.b64encode(ozel.public_key().public_bytes(serialization.Encoding.Raw,
                                                           serialization.PublicFormat.Raw)).decode()
    monkeypatch.setattr(lisans, "ACIK_ANAHTARLAR", {"T1": acik})
    veri = {"urun": "KoordMES", "lisans_no": "KM-2025-0007", "kurum_kodu": "111111", "kurum_adi": "Eski Lisanslı MTAL",
            "baslangic": "2025-09-01", "bitis": "", "anahtar": "T1"}
    veri["imza"] = base64.b64encode(ozel.sign(lisans.kanonik(veri))).decode()
    assert lisans.dogrula(veri).kurum_adi == "Eski Lisanslı MTAL"
    with pytest.raises(lisans.LisansHatasi, match="ürününe ait"):
        lisans.dogrula({**veri, "urun": "BaskaUrun"})

    yeni = tmp_path / "ProgramData" / "MesKoord"
    eski = yeni.with_name("KoordMES")
    eski.mkdir(parents=True)
    (eski / "okul.lic").write_text(lisans.dosya_metni(veri), encoding="utf-8")
    monkeypatch.setattr(lisans, "ortak_klasor", lambda: yeni)
    monkeypatch.setattr(lisans, "program_klasoru", lambda: tmp_path / "Program")
    lis, _ = lisans.bul()
    assert lis is not None and lis.kurum_kodu == "111111"


def test_yeni_lisanslar_yeni_urun_adiyla_imzalanir():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    assert lisans.imzala({"a": 1}, Ed25519PrivateKey.generate(), "T1")["urun"] == "MesKoord"


def test_ag_tanitici_eski_adi_da_tanir():
    from koordmes.ag import protokol as P
    assert P.URUN == "MesKoord" and "KoordMES" in P.URUN_ADLARI
    assert b"KOORDMES-KESIF-1" in P.KESIF_ISTEKLERI and P.KESIF_ISTEGI == b"MESKOORD-KESIF-1"


def test_kesif_eski_istege_de_yanit_verir():
    import json
    import socket
    from koordmes.ag import protokol as P
    from koordmes.ag.kesif import KesifYanitlayici

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    y = KesifYanitlayici("SINAMA", 47400, kesif_portu=port)
    assert y.baslat()
    try:
        for istek in P.KESIF_ISTEKLERI:
            c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            c.settimeout(3)
            c.sendto(istek, ("127.0.0.1", port))
            yanit = json.loads(c.recvfrom(2048)[0])
            c.close()
            assert yanit["urun"] == "MesKoord" and yanit["ad"] == "SINAMA"
    finally:
        y.durdur()


def test_eski_arayuz_ayarlari_aktarilir():
    from PySide6.QtCore import QSettings
    from koordmes.ui.ana_pencere import arayuz_ayarlari

    yeni = QSettings(QSettings.defaultFormat(), QSettings.UserScope, "MesKoord", "arayuz")
    onceki = {k: yeni.value(k) for k in yeni.allKeys()}
    yeni.clear()
    eski = QSettings(QSettings.defaultFormat(), QSettings.UserScope, "KoordMES", "arayuz")
    eski.setValue("menu_dar", True)
    eski.setValue("son_sayfa", "Dallar")
    eski.sync()
    try:
        a = arayuz_ayarlari()
        assert a.value("menu_dar", type=bool) and a.value("son_sayfa") == "Dallar"
    finally:
        eski.clear()
        yeni.clear()
        for k, v in onceki.items():
            yeni.setValue(k, v)


@pytest.mark.skipif(os.name != "nt", reason="Windows kayıt defteri")
def test_otomatik_baslatma_kaydi_kurulu_programda_yenilenir(monkeypatch):
    from koordmes.ui import tepsi
    kayitlar = {"KoordMES": r'"C:\Program Files\KoordMES\KoordMES.exe" --arka-plan'}
    monkeypatch.setattr(tepsi, "_kayit", lambda ad: kayitlar.get(ad))
    monkeypatch.setattr(tepsi, "otomatik_baslat_ayarla",
                        lambda acik: (kayitlar.pop("KoordMES", None), kayitlar.update(MesKoord=tepsi.baslatma_komutu())))
    tepsi.otomatik_baslatmayi_guncelle()
    assert "MesKoord" not in kayitlar  # kaynak koddan çalışırken kurulu programın kaydına dokunulmaz
    monkeypatch.setattr(tepsi.sys, "frozen", True, raising=False)
    tepsi.otomatik_baslatmayi_guncelle()
    assert set(kayitlar) == {"MesKoord"} and tepsi.otomatik_baslat_acik()
