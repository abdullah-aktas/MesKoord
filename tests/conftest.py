import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# offscreen Qt kendi yazı tipi listesini bulamaz; PDF'lere metin yerine boş kutu yazar
if os.name == "nt":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))


@pytest.fixture(autouse=True, scope="session")
def _gecici_qt_ayarlari(tmp_path_factory):
    """Pencere konumu vb. QSettings kayıtları gerçek kullanıcı ayarlarına (kayıt defteri) yazılmasın."""
    from PySide6.QtCore import QSettings
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path_factory.mktemp("qt_ayar")))
    # Hiçbir test gerçek Belgeler\MesKoord (ya da taşınacak eski Belgeler\KoordMES) klasörüne dokunmasın
    os.environ["MESKOORD_DATA"] = str(tmp_path_factory.mktemp("veri"))


def pencereyi_kapat(w) -> None:
    w._cikis_hazir = True
    w.close()


TEST_PAROLASI = "sınama-parolası"


@pytest.fixture
def sunucu(tmp_path):
    """Geçici veritabanı üzerinde çalışan ağ sunucusu (rastgele portta, yalnızca bu bilgisayardan)."""
    os.environ["MESKOORD_DATA"] = str(tmp_path / "data")
    from koordmes.ag import protokol as P
    from koordmes.ag.sunucu import KoordSunucu, SunucuDatabase
    yerel = SunucuDatabase(tmp_path / "test.db")
    s = KoordSunucu(yerel.path, P.parola_ozeti(TEST_PAROLASI), port=0, ad="SINAMA", host="127.0.0.1",
                    yerel_kullanici="sunucu", sertifika_klasoru=tmp_path)
    s.baslat()
    yerel.sunucu = s
    s.yerel_db = yerel
    yield s
    s.durdur()
    yerel.close()


def baglanti_bilgisi(s, kullanici="istemci"):
    from koordmes.ag.istemci import BaglantiBilgisi
    return BaglantiBilgisi("127.0.0.1", s.port, TEST_PAROLASI, s.parmak_izi, kullanici=kullanici,
                           bilgisayar=f"PC-{kullanici}")


@pytest.fixture
def uzak_db(sunucu):
    from koordmes.ag.istemci import UzakDatabase
    d = UzakDatabase(baglanti_bilgisi(sunucu))
    yield d
    d.close()


@pytest.fixture
def db(tmp_path, request):
    if "1" in (os.environ.get("MESKOORD_TEST_UZAK"), os.environ.get("KOORDMES_TEST_UZAK")):
        yield request.getfixturevalue("uzak_db")
        return
    os.environ["MESKOORD_DATA"] = str(tmp_path / "data")
    from koordmes.db import Database
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


@pytest.fixture
def ornek_db(db):
    from koordmes.services import ornek_veri
    ornek_veri.yukle(db, programi_coz=True)
    return db
