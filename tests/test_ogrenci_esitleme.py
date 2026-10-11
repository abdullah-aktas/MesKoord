from datetime import date

from koordmes.services import ogrenci_esitleme as oe
from koordmes.services.okuyucu import Tablo

BAS = ["Öğrenci No", "T.C. Kimlik No", "Adı", "Soyadı", "Sınıfı"]


def _kur(db):
    a = db.insert("siniflar", {"ad": "11-A", "seviye": 11})
    b = db.insert("siniflar", {"ad": "11-B", "seviye": 11})
    c = db.insert("siniflar", {"ad": "12-A", "seviye": 12})
    o = {}
    for no, ad, soyad, sinif, k in [("1", "Ali", "Can", a, {}), ("2", "Ece", "Su", a, {}),
                                    ("3", "Veli", "Tan", a, {}), ("4", "Ayşe", "Gül", b, {"aktif": 0}),
                                    ("5", "Can", "Ak", c, {}), ("6", "Su", "Er", a, {"tc": ""})]:
        o[no] = db.insert("ogrenciler", {"okul_no": no, "ad": ad, "soyad": soyad, "sinif_id": sinif, **k})
    return o


def test_karsilastir_ve_uygula(db):
    o = _kur(db)
    db.insert("yerlestirmeler", {"ogrenci_id": o["3"], "tur": "İşletmede Mesleki Eğitim",
                                 "baslangic": "2026-09-15", "durum": "Aktif"})
    liste = Tablo("OOK08001R020.xls", "Sayfa1", [
        ["T.C. MİLLÎ EĞİTİM BAKANLIĞI"],
        BAS,
        ["1", "", "ALİ", "CAN", "11. Sınıf / A Şubesi"],
        ["2", "", "ECE", "SU", "11. Sınıf / B Şubesi"],       # sınıf değişmiş
        ["4", "", "AYŞE", "GÜL", "11. Sınıf / B Şubesi"],     # pasifti, yeniden kayıt
        ["6", "10000000146", "SU", "ER", "11-A"],             # T.C. eksikti
        ["9", "", "YENİ", "ÖĞRENCİ", "11-A"],                 # nakil gelen
    ])
    s = oe.karsilastir(db, [liste])
    assert s.liste_sayisi == 5 and set(s.kapsam) == {"11-A", "11-B"}
    tur = {x.ad: x.tur for x in s.satirlar}
    assert tur == {"Ece Su": "Sınıf değişmiş", "Ayşe Gül": "Yeniden kayıt", "Su Er": "Bilgi farkı",
                   "Yeni Öğrenci": "Yeni", "Veli Tan": "Listede yok"}  # 12-A listede olmadığından kapsam dışı
    assert s.sayilar()["Yeni"] == 1

    u = oe.uygula(db, s.satirlar, date(2026, 10, 9))
    assert not u.hatalar and u.kapatilan == 1
    assert "1 yeni öğrenci" in u.metin()
    sinif = lambda no: db.q1("SELECT s.ad FROM ogrenciler o JOIN siniflar s ON s.id = o.sinif_id "
                             "WHERE o.okul_no = ?", (no,))["ad"]
    assert sinif("2") == "11-B" and sinif("9") == "11-A"
    assert db.q1("SELECT aktif FROM ogrenciler WHERE id = ?", (o["4"],))["aktif"] == 1
    assert db.q1("SELECT aktif FROM ogrenciler WHERE id = ?", (o["3"],))["aktif"] == 0
    assert db.q1("SELECT tc FROM ogrenciler WHERE id = ?", (o["6"],))["tc"] == "10000000146"
    y = db.q1("SELECT bitis, durum, fesih_nedeni FROM yerlestirmeler")
    assert (y["bitis"], y["durum"], y["fesih_nedeni"]) == ("2026-10-09", "Sona Erdi", "Nakil")

    # ikinci karşılaştırmada fark kalmaz
    assert oe.karsilastir(db, [liste]).satirlar == []


def test_sinifsiz_liste_tum_okul_ve_tanınmayan_tablo(db):
    o = _kur(db)
    liste = Tablo("liste.xlsx", "S", [["Öğrenci No", "Adı Soyadı"], ["1", "Ali Can"], ["5", "Can Ak"]])
    s = oe.karsilastir(db, [liste, Tablo("x", "x", [["Renk"], ["mavi"]])])
    assert any("tanınmadı" in n for n in s.notlar) and any("tüm okul" in n for n in s.notlar)
    assert {x.ogrenci_id for x in s.satirlar if x.tur == "Listede yok"} == {o["2"], o["3"], o["6"]}
    u = oe.uygula(db, [x for x in s.satirlar if x.ogrenci_id == o["2"]], yerlestirme_kapat=False)
    assert u.sayilar["Listede yok"] == 1 and u.kapatilan == 0


def test_tc_cakismasi_hata_olarak_raporlanir(db):
    o = _kur(db)
    db.update("ogrenciler", o["5"], {"tc": "10000000146"})
    liste = Tablo("l", "l", [BAS, ["6", "10000000146", "Su", "Er", "11-A"]])
    s = oe.karsilastir(db, [liste])
    # T.C. Can Ak'ta kayıtlı ama ad ve numara Su Er'e ait: Can Ak'ın üzerine yazılmaz
    [fark] = [x for x in s.satirlar if x.tur != "Listede yok"]
    assert (fark.ogrenci_id, fark.tur) == (o["6"], "Bilgi farkı")
    assert any("Can Ak adına kayıtlı" in n for n in s.notlar)
    u = oe.uygula(db, [fark])
    assert len(u.hatalar) == 1 and "başka öğrencide" in u.hatalar[0]
    assert db.q1("SELECT ad FROM ogrenciler WHERE id = ?", (o["5"],))["ad"] == "Can"

    db.update("ogrenciler", o["6"], {"okul_no": "66"})
    db.delete("ogrenciler", o["6"])
    s = oe.karsilastir(db, [liste])
    [yeni] = [x for x in s.satirlar if x.tur == "Yeni"]
    u = oe.uygula(db, [yeni])
    assert "başka öğrencide" in u.hatalar[0] and u.sayilar["Yeni"] == 0
