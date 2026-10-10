"""Ortaöğretim Kurumları Yönetmeliği (işletmelerde mesleki eğitim) hükümleri."""
from datetime import date

import pytest

from koordmes.services import belgeler, denetim, koordinator, mesleki_egitim as me, surecler, takvim


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _isletme_ogrencileri(db, n: int, alan_ad: str = "Bilişim Teknolojileri", tur: str = "İşletmede Mesleki Eğitim",
                         **isletme) -> int:
    alan = db.q1("SELECT id FROM alanlar WHERE ad = ?", (alan_ad,))["id"]
    sinif = db.q1("SELECT id FROM siniflar WHERE alan_id = ? AND seviye = 12", (alan,))["id"]
    iid = db.insert("isletmeler", {"ad": f"Büyük İşletme {n}", "alan_id": alan, "guzergah": "Merkez",
                                   "mesafe_km": 2, "personel_sayisi": 80, "usta_ogretici": "Usta",
                                   "kontenjan": 40, **isletme})
    for k in range(n):
        oid = db.insert("ogrenciler", {"ad": f"Deneme{k}", "soyad": "Öğrenci", "sinif_id": sinif})
        db.insert("yerlestirmeler", {"ogrenci_id": oid, "isletme_id": iid, "tur": tur, "baslangic": "2026-09-14",
                                     "sozlesme_no": f"X{k}", "sozlesme_tarihi": "2026-09-10"})
    return iid


def test_on_bes_ogrenciyi_asan_isletme_bolunur(ornek_db):
    iid = _isletme_ogrencileri(ornek_db, 20)
    gruplar = [ih for ih in koordinator.isletme_ihtiyaclari(ornek_db, date(2026, 10, 1)) if ih.isletme_id == iid]
    assert sorted(ih.ogrenci_sayisi for ih in gruplar) == [5, 15]
    assert all("grup" in ih.ad for ih in gruplar)
    b = {x.mesaj.split(" (")[0] for x in denetim.denetle(ornek_db, date(2026, 10, 1))}
    assert any("usta öğretici / eğitici personele 16" in m for m in b)
    assert any("eğitim birimi kurulmamış" in m for m in b)


def test_doner_sermaye_ve_il_disi_staj_kapsam_disi(ornek_db):
    d = _isletme_ogrencileri(ornek_db, 2, doner_sermaye=1)
    s = _isletme_ogrencileri(ornek_db, 3, tur="Staj", il_disi=1)
    sonuc = koordinator.otomatik_gorevlendir(ornek_db, date(2026, 10, 1), kaydet=False)
    atanan = {g["isletme_id"] for g in sonuc.gorevler}
    assert d not in atanan and s not in atanan
    nedenler = " ".join(n for _, n in sonuc.kapsam_disi)
    assert "md.88/8" in nedenler and "md.88/2-g" in nedenler
    koordinatorsuz = next((b for b in denetim.denetle(ornek_db, date(2026, 10, 1))
                           if b.mesaj.startswith("Koordinatör öğretmen görevlendirilmemiş")), None)
    assert koordinatorsuz is None or not {"Büyük İşletme 2", "Büyük İşletme 3"} & set(koordinatorsuz.ornekler)


def test_atolye_ogretmeni_oncelikli(ornek_db):
    sonuc = koordinator.otomatik_gorevlendir(ornek_db, date(2026, 10, 1), kaydet=False)
    ogretmen = {r["id"]: r for r in ornek_db.q("SELECT * FROM ogretmenler")}
    atolye = [g for g in sonuc.gorevler if koordinator.atolye_ogretmeni_mi(ogretmen[g["ogretmen_id"]])]
    assert atolye, "atölye/lab. öğretmenlerine görev verilmeli"
    for t in sonuc.alan_disi:
        assert "→" in t


def test_ogrenci_secimi_md136(ornek_db):
    bt = ornek_db.q1("SELECT id FROM alanlar WHERE ad = 'Bilişim Teknolojileri'")["id"]
    adaylar = me.adaylar(ornek_db, bt, 11)
    assert adaylar and all(a.sinif == "11-A" for a in adaylar)
    liste = me.sirala(adaylar, 3)
    sonuclar = [a.sonuc for a in liste]
    assert sonuclar.count(me.GONDERILECEK) == 3
    assert me.KOSULSUZ in sonuclar
    sirali = [a.ortalama for a in liste if a.sonuc in (me.GONDERILECEK, me.YEDEK)]
    assert sirali == sorted(sirali, reverse=True)
    ee = ornek_db.q1("SELECT id FROM alanlar WHERE ad LIKE 'Elektrik%'")["id"]
    ee_liste = me.sirala(me.adaylar(ornek_db, ee, 11), 1)
    assert ee_liste[0].sonuc == me.ONCELIKLI
    assert not any(a.sonuc == me.GONDERILECEK for a in ee_liste)
    yol = me.secim_tutanagi(ornek_db, liste, "Bilişim Teknolojileri", 3)
    assert yol.exists()
    assert me.secim_excel(ornek_db, liste, "Bilişim", 3, yol.with_suffix(".xlsx")).exists()


def test_sozlesme_suresi_ve_gun_dagilimi(ornek_db):
    y = ornek_db.q1("SELECT id FROM yerlestirmeler WHERE durum = 'Aktif' AND isletme_id IS NOT NULL LIMIT 1")["id"]
    ornek_db.execute("UPDATE yerlestirmeler SET sozlesme_tarihi = NULL WHERE id = ?", (y,))
    ornek_db.execute("UPDATE siniflar SET okul_gunleri = '1', isletme_gunleri = '2,3,4,5' WHERE ad = '12-A'")
    b = denetim.denetle(ornek_db, date(2026, 10, 1))
    assert any("md.143" in x.mesaj and x.seviye == "Kritik" for x in b)
    assert any("md.134" in x.mesaj and "12-A" in x.ornekler[0] for x in b)
    u = takvim.uyarilar(ornek_db, date(2026, 9, 15))
    assert any(x.konu == "Sözleşme" and "ikinci haftası" in x.mesaj for x in u)


def test_puan_cizelgesi_hatirlatma(ornek_db):
    u = takvim.uyarilar(ornek_db, date(2027, 1, 10))
    puan = [x for x in u if x.konu == "Değerlendirme"]
    assert puan and "17.01.2027" in puan[0].mesaj
    b = denetim.denetle(ornek_db, date(2027, 1, 20))
    assert any("puan çizelgesi teslim süresi geçti" in x.mesaj for x in b)


def test_yeni_belgeler_ve_surecler(ornek_db):
    iid = ornek_db.q1("SELECT isletme_id FROM koordinator_gorevleri LIMIT 1")["isletme_id"]
    for anahtar in ("koordinator_bildirimi", "isletme_uygunluk"):
        assert belgeler.uret(ornek_db, anahtar, iid).exists()
    assert belgeler.uret(ornek_db, "koordinatorluk_komisyon_karari", 1).exists()
    for e in ("komisyon_karari", "koordinator_bildirimleri", "uygunluk_tutanaklari", "alan_taramasi",
              "anket_ozeti", "hizmetici", "puan_cizelgesi"):
        s = surecler.calistir(ornek_db, e)
        assert s.mesaj and all(p.exists() for p in s.dosyalar)
    d = surecler.durumlar(ornek_db, "yonetmelik", 2026, 10)
    assert d and not any(x.detay.startswith("Denetlenemedi") for x in d)
    assert me.talep_satirlari(ornek_db)


def test_komisyon_sayfasi(app, ornek_db, monkeypatch):
    from koordmes.ui import ortak
    from koordmes.ui.sayfa_komisyon import KomisyonSayfasi

    monkeypatch.setattr(ortak, "kaydedildi", lambda *a, **k: None)
    s = KomisyonSayfasi(ornek_db)
    s.show()
    s.secim_sekmesi()
    sec = s.secim
    sec.alan.setCurrentIndex(sec.alan.findText("Bilişim Teknolojileri"))
    sec.seviye.setCurrentIndex(sec.seviye.findData(11))
    sec.sirala()
    assert sec.model.rowCount() == 6 and "Gönderilecek" in sec.durum.text()
    sec.tutanak()
    s.close()
