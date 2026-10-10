import hashlib
import json
from datetime import datetime, timedelta

import pytest

from koordmes.services import guncelleme
from koordmes.services.guncelleme import GuncellemeAyarlari, GuncellemeHatasi, YeniSurum


def _surum_json(tmp_path, surum="9.0.0", sha=None, indir=None):
    kurulum = tmp_path / "MesKoord_Kurulum_9.0.0.exe"
    kurulum.write_bytes(b"kurulum" * 1000)
    yol = tmp_path / "surum.json"
    yol.write_text(guncelleme.surum_json(surum, indir or kurulum.as_uri(),
                                         sha if sha is not None else hashlib.sha256(kurulum.read_bytes()).hexdigest(),
                                         "## 9.0.0\n- Yeni"), encoding="utf-8")
    return yol, kurulum


def test_surum_karsilastirma():
    assert guncelleme.daha_yeni("1.4.0", "1.3.0")
    assert guncelleme.daha_yeni("1.10.0", "1.9.9")
    assert not guncelleme.daha_yeni("1.3.0", "1.3.0")
    assert not guncelleme.daha_yeni("1.2.9", "1.3.0")


def test_yeni_surum_bulunur_ve_indirilip_dogrulanir(tmp_path):
    yol, kurulum = _surum_json(tmp_path)
    yeni = guncelleme.denetle(yol.as_uri(), "1.3.0")
    assert yeni.surum == "9.0.0" and yeni.notlar.startswith("## 9.0.0")
    assert guncelleme.denetle(yol.as_uri(), "9.0.0") is None
    hedef = tmp_path / "indir"
    hedef.mkdir()
    adimlar = []
    sonuc = guncelleme.indir(yeni, hedef, lambda a, t: adimlar.append(a))
    assert sonuc.read_bytes() == kurulum.read_bytes() and adimlar[-1] == len(kurulum.read_bytes())


def test_ozet_uyusmazsa_kurulum_silinir(tmp_path):
    yol, _ = _surum_json(tmp_path, sha="0" * 64)
    yeni = guncelleme.denetle(yol.as_uri(), "1.3.0")
    hedef = tmp_path / "indir"
    hedef.mkdir()
    with pytest.raises(GuncellemeHatasi, match="SHA256"):
        guncelleme.indir(yeni, hedef)
    assert list(hedef.iterdir()) == []


def test_guvensiz_adres_reddedilir(tmp_path):
    with pytest.raises(GuncellemeHatasi, match="güvenli olmayan"):
        guncelleme.denetle("http://ornek.com/surum.json", "1.3.0")
    yol, _ = _surum_json(tmp_path, indir="http://ornek.com/kurulum.exe")
    with pytest.raises(GuncellemeHatasi, match="geçersiz"):
        guncelleme.denetle(yol.as_uri(), "1.3.0")
    with pytest.raises(GuncellemeHatasi):
        guncelleme.indir(YeniSurum("9.0.0", "ftp://ornek.com/k.exe"), tmp_path)
    (tmp_path / "bozuk.json").write_text("{bozuk", encoding="utf-8")
    with pytest.raises(GuncellemeHatasi, match="alınamadı"):
        guncelleme.denetle((tmp_path / "bozuk.json").as_uri(), "1.3.0")


def test_adres_yoksa_denetlenmez(monkeypatch):
    monkeypatch.setattr(guncelleme, "GUNCELLEME_ADRESI", "")
    monkeypatch.delenv("MESKOORD_GUNCELLEME_ADRESI", raising=False)
    monkeypatch.delenv("KOORDMES_GUNCELLEME_ADRESI", raising=False)
    assert guncelleme.denetle() is None
    assert not GuncellemeAyarlari().zamani_geldi()


def test_gunde_bir_denetlenir(monkeypatch):
    monkeypatch.setattr(guncelleme, "GUNCELLEME_ADRESI", "https://ornek.com/surum.json")
    simdi = datetime(2026, 10, 10, 12)
    a = GuncellemeAyarlari(son_denetim=(simdi - timedelta(hours=2)).isoformat())
    assert not a.zamani_geldi(simdi)
    a.son_denetim = (simdi - timedelta(days=1)).isoformat()
    assert a.zamani_geldi(simdi)
    a.otomatik = False
    assert not a.zamani_geldi(simdi)


def test_indirme_adresi_turetilir():
    gh = "https://github.com/okul/meskoord/releases/latest/download/surum.json"
    assert guncelleme.indirme_adresi(gh, "MesKoord_Kurulum_1.4.0.exe", "1.4.0") == \
        "https://github.com/okul/meskoord/releases/download/v1.4.0/MesKoord_Kurulum_1.4.0.exe"
    assert guncelleme.indirme_adresi("https://okul.k12.tr/meskoord/surum.json", "k.exe", "1.4.0") == \
        "https://okul.k12.tr/meskoord/k.exe"
    assert json.loads(guncelleme.surum_json("1.4.0", "https://x/k.exe", "ab", "n"))["surum"] == "1.4.0"
