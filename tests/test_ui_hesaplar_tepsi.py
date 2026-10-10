"""Kullanıcılar / İşlem Günlüğü sekmeleri, otomatik yedek ayarları ve tepsi yardımcıları."""
import os
from datetime import datetime, timedelta

import pytest
from conftest import pencereyi_kapat

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def yerel_db(tmp_path):
    os.environ["MESKOORD_DATA"] = str(tmp_path / "data")
    from koordmes.db import Database
    d = Database(tmp_path / "test.db")
    yield d
    d.close()


def _sekme(w, ad):
    from PySide6.QtWidgets import QTabWidget
    ayarlar = w.git("Ayarlar ve Mevzuat Parametreleri") or w.gecerli_sayfa()
    assert isinstance(ayarlar, QTabWidget)
    for i in range(ayarlar.count()):
        if ayarlar.tabText(i) == ad:
            ayarlar.setCurrentIndex(i)
            return ayarlar.widget(i)
    raise AssertionError(f"{ad} sekmesi yok")


def test_gunluk_ve_kullanicilar_sekmesi(app, yerel_db):
    from koordmes import hesaplar as H
    from koordmes.ui.ana_pencere import AnaPencere
    yerel_db.insert("alanlar", {"ad": "Gıda Teknolojisi"})
    w = AnaPencere(yerel_db)
    try:
        assert not w.durum_kullanici.isVisibleTo(w)
        gunluk = _sekme(w, "İşlem Günlüğü")
        gunluk.yenile()
        satirlar = gunluk.satirlar()
        assert any("Gıda Teknolojisi" in s[5] and s[3] == "Ekleme" for s in satirlar), satirlar
        assert gunluk.kisi.count() >= 2

        kul = _sekme(w, "Kullanıcılar")
        kul.yenile()
        assert kul.dugmeler["ac"].isVisibleTo(kul) and not kul.dugmeler["yeni"].isVisibleTo(kul)

        kimlik = H.hesaplari_ac(yerel_db, "Ayşe Yılmaz", "ayse", "parola123")
        yerel_db.kimlik_ata(kimlik)
        w.kullanici_guncelle()
        kul.yenile()
        assert kul.model.rowCount() == 1
        assert kul.dugmeler["yeni"].isVisibleTo(kul) and not kul.dugmeler["ac"].isVisibleTo(kul)
        assert w.durum_kullanici.isVisibleTo(w) and "Ayşe Yılmaz" in w.durum_kullanici.text()

        H.kullanici_ekle(yerel_db, "Can Demir", "can", H.PERSONEL, "parola456")
        yerel_db.kimlik_ata(H.dogrula(yerel_db.path, "can", "parola456"))
        kul.yenile()
        assert not kul.view.isVisibleTo(kul) and kul.dugmeler["parolam"].isVisibleTo(kul)
        gunluk.yenile()
        assert gunluk.yetkisiz.isVisibleTo(gunluk) and not gunluk.view.isVisibleTo(gunluk)
        kurum = _sekme(w, "Kurum Bilgileri")
        kurum.show()
        app.processEvents()
    finally:
        pencereyi_kapat(w)


def test_ayrinti_metni():
    from koordmes.ui.sayfa_kullanicilar import ayrinti_metni
    metin = ayrinti_metni("ogrenciler", '{"ad_soyad": ["Ali", "Ali Can"], "tc": ["***", "***"]}',
                          {("ogrenciler", "ad_soyad"): "Ad Soyad"})
    assert metin.startswith("Ad Soyad: Ali → Ali Can")
    assert ayrinti_metni("x", "", {}) == ""


def test_yedek_ayarlari_ve_ikinci_klasor(tmp_path, yerel_db):
    from koordmes import yedekleme as Y
    a = Y.YedekAyarlari.yukle()
    assert a.otomatik and a.aralik_saat == 24 and a.zamani_geldi()
    ikinci = tmp_path / "usb"
    a.ikinci_klasor = str(ikinci)
    a.kaydet()
    yol = yerel_db.yedekle()
    a = Y.YedekAyarlari.yukle()
    assert a.son_yedek and not a.son_hata
    assert not a.zamani_geldi()
    assert a.zamani_geldi(datetime.now() + timedelta(hours=25))
    kopya = list((ikinci / Y.IKINCI_KLASOR_ADI).glob("*.db"))
    assert [k.name for k in kopya] == [yol.name]
    a.otomatik = False
    assert not a.zamani_geldi(datetime.now() + timedelta(days=30))
    # elle seçilen yere alınan yedek otomatik sayılmaz, ikinci klasöre kopyalanmaz
    yerel_db.yedekle(tmp_path / "elle.db")
    assert len(list((ikinci / Y.IKINCI_KLASOR_ADI).glob("*.db"))) == 1


def test_ikinci_klasor_yoksa_hata_kaydedilir(tmp_path, yerel_db):
    from koordmes import yedekleme as Y
    a = Y.YedekAyarlari.yukle()
    dosya = tmp_path / "dosya.txt"
    dosya.write_text("x")
    a.ikinci_klasor = str(dosya)
    a.kaydet()
    yerel_db.yedekle()
    assert Y.YedekAyarlari.yukle().son_hata


def test_otomatik_yedek_grubu_ve_ag_secenekleri(app, yerel_db):
    from koordmes.ui.ana_pencere import AnaPencere
    w = AnaPencere(yerel_db)
    try:
        veri = _sekme(w, "Veri ve Yedekleme")
        veri.show()
        app.processEvents()
        sayfa = w.git("Çok Kullanıcılı Çalışma (Ağ)") or w.gecerli_sayfa()
        assert hasattr(sayfa, "s_otomatik") and hasattr(sayfa, "s_tepsi")
        assert sayfa.i_parola_etiket.text() == "Sunucu parolası"
        sayfa._hesap = True
        sayfa._hesap_gorunumu()
        assert sayfa.i_parola_etiket.text() == "Parolanız" and not sayfa.i_hatirla.isVisibleTo(sayfa)
    finally:
        pencereyi_kapat(w)


def test_tepsi_yardimcilari(app):
    from koordmes.ui import tepsi
    komut = tepsi.baslatma_komutu()
    assert komut.endswith(tepsi.ARKA_PLAN) and "run.py" in komut
    gosterildi = []
    tek = tepsi.TekOrnek(lambda: gosterildi.append(1))
    tek.ad += "-test"
    assert not tek.baska_ornek_var()
    tek.dinle()
    try:
        ikinci = tepsi.TekOrnek(lambda: None)
        ikinci.ad = tek.ad
        assert ikinci.baska_ornek_var()
        for _ in range(50):
            app.processEvents()
            if gosterildi:
                break
        assert gosterildi
    finally:
        tek.kapat()
