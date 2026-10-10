import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from koordmes.services import degisiklik, koordinator
from koordmes.services.aktarim import IceAktarmaSonucu
from koordmes.services.kurum_turu import sistemler, tur_tahmin


def test_tur_tahmin():
    assert tur_tahmin("Derik Mesleki ve Teknik Anadolu Lisesi") == "MTAL"
    assert tur_tahmin("Mesleki Eğitim Merkezi") == "MEM"
    assert tur_tahmin("Çok Programlı Anadolu Lisesi") == "ÇPAL"
    assert tur_tahmin("çok programlo anadolu lisesi") == "ÇPAL"
    assert tur_tahmin("Mesleki ve Teknik Anadolu Lisesi ve Mesleki Eğitim Merkezi") == "MTAL+MEM"
    assert tur_tahmin("Deneme MTAL") == "MTAL"
    assert tur_tahmin("Atatürk Anadolu Lisesi") is None
    assert tur_tahmin("") is None


def test_sistem_sirasi():
    assert sistemler("MEM")[0] == "emesem"
    assert sistemler("MTAL")[0] == "eokul"
    assert sistemler("ÇPAL") == sistemler("MTAL")
    assert "emesem" in sistemler("MTAL+MEM")
    assert "vizite" in sistemler("MTAL")
    assert "vizite" in sistemler("MEM")


def test_cpal_okul_koordinator_sinirini_kullanir(db):
    db.update("kurum", 1, {"tur": "ÇPAL", "buyuksehir": 0})
    okul = koordinator.haftalik_azami(db)
    db.update("kurum", 1, {"tur": "MEM", "buyuksehir": 0})
    assert koordinator.haftalik_azami(db) != okul


def test_degisiklik_ozeti_saklanir(db):
    s = IceAktarmaSonucu(anahtar="ogrenciler")
    s.eklenen = 2
    s.guncellenen = 1
    assert "öğrenci: 2 yeni, 1 güncellenen" in degisiklik.metin([s])
    degisiklik.kaydet(db, [s], "SGK listesi güncellendi.")
    kayit = degisiklik.oku(db)
    assert "öğrenci: 2 yeni, 1 güncellenen" in kayit
    assert "SGK listesi güncellendi." in kayit


def test_ad_yazilinca_tur_secilir_elle_secim_kalir(db):
    from PySide6.QtWidgets import QApplication
    from koordmes.ui.sayfa_ayarlar import KurumBilgileri

    app = QApplication.instance() or QApplication([])
    k = KurumBilgileri(db)
    k.show()
    app.processEvents()
    k.w["ad"].setText("Derik Çok Programlı Anadolu Lisesi")
    assert k.tur.currentData() == "ÇPAL"
    k.tur.setCurrentIndex(k.tur.findData("MTAL"))
    k.tur.activated.emit(k.tur.currentIndex())
    k.w["ad"].setText("Derik Çok Programlı Anadolu Lisesi")
    assert k.tur.currentData() == "MTAL"
    k.w["kurum_kodu"].setText("12345678")
    assert k.kaydet(sessiz=True) is True
    assert db.kurum()["tur"] == "MTAL"
    assert db.kurum()["ad"] == "Derik Çok Programlı Anadolu Lisesi"
