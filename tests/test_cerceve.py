import pytest

from koordmes.mevzuat import isletmeye_giden_sinif
from koordmes.services import asistan, cerceve, denetim, surecler


def _sinif(db, ad="10-A", seviye=10, program="MTAL-ATP", alan="BİLİŞİM TEKNOLOJİLERİ ALANI",
           dal="Yazılım Geliştirme Dalı", **kw):
    alan_id = db.insert("alanlar", {"ad": alan}) if alan else None
    dal_id = db.insert("dallar", {"alan_id": alan_id, "ad": dal}) if dal and alan_id else None
    return db.insert("siniflar", {"ad": ad, "seviye": seviye, "program": program, "alan_id": alan_id,
                                  "dal_id": dal_id, **kw})


def test_veri_yuklenir_ve_alan_adlari_eslesir():
    assert cerceve.veri_var() and len(cerceve.programlar()) > 1000
    assert cerceve.eslestir("BİLİŞİM TEKNOLOJİLERİ ALANI", cerceve.alanlar("MTAL")) == "Bilişim Teknolojileri"
    assert cerceve.eslestir("Yapay Zeka", cerceve.alanlar("MTAL")) == "Yapay Zekâ"
    e = cerceve.bul("MTAL", "ATP", 9, "Bilişim Teknolojileri")
    assert e.program and not e.sorun, "9. sınıfta dallar aynı çizelgeyi kullanır"


def test_dala_gore_degisen_seviyede_dal_istenir():
    e = cerceve.bul("MTAL", "ATP", 10, "Bilişim Teknolojileri")
    assert e.program is None and "dal" in e.sorun and len(e.secenekler) >= 2
    p = cerceve.bul("MTAL", "ATP", 10, "Bilişim Teknolojileri", "yazılım geliştirme").program
    assert p.dal == "Yazılım Geliştirme" and p.okul_dersleri


def test_program_ozel_durumlari():
    amp11 = cerceve.bul("MTAL", "AMP-11", 11, "Muhasebe ve Finansman", "Muhasebe").program
    assert amp11.program == "AMP-11" and amp11.isletme_saati == 16 and amp11.isletme_gunu == 2
    son = cerceve.bul("MTAL", "AMP-11", 12, "Muhasebe ve Finansman", "Muhasebe").program
    assert son.program == "AMP" and son.isletme_gunu == 3
    atp = cerceve.bul("MTAL", "ATP", 12, "Muhasebe ve Finansman", "Muhasebe").program
    assert atp.akademik_destek == 31 and not atp.isletme_saati
    mem = cerceve.bul("MEM", "MEM", 11, "Yiyecek İçecek Hizmetleri", "Aşçılık", protokol=False).program
    tde = next(d for d in mem.dersler if d.ad == "Türk Dili ve Edebiyatı")
    assert tde.saat == 0 and tde.parantezli_saat == 2 and tde not in mem.okul_dersleri
    assert mem.isletme_gunu == 4
    yeni_ad = cerceve.bul("MTAL", "AMP", 9, "Motorlu Araçlar Teknolojisi").program
    assert yeni_ad.alan == "Otomotiv Teknolojileri"


def test_zorunlu_dersler_sinifa_acilir(db):
    rehber = db.insert("ogretmenler", {"ad": "Ayşe", "soyad": "Rehber"})
    sid = _sinif(db, rehber_ogretmen_id=rehber)
    tde_ogr = db.insert("ogretmenler", {"ad": "Ali", "soyad": "Edebiyat"})
    tde = db.insert("dersler", {"ad": "TÜRK DİLİ VE EDEBİYATI", "tur": "Kültür"})
    secmeli = db.insert("dersler", {"ad": "Seçmeli Ders", "tur": "Kültür"})
    db.insert("ders_atamalari", {"sinif_id": sid, "ders_id": tde, "ogretmen_id": tde_ogr, "haftalik_saat": 2})
    db.insert("ders_atamalari", {"sinif_id": sid, "ders_id": secmeli, "haftalik_saat": 2})

    p = cerceve.sinif_programi(db, sid).program
    s = cerceve.uygula(db, sid, p)
    assert s.guncellenen == ["Türk Dili ve Edebiyatı (2 → 4 saat)"]
    assert len(s.eklenen) == len(p.okul_dersleri) - 1
    atamalar = {r["ad"]: r for r in db.q("""SELECT d.ad, d.tur, d.alan_id, d.kisa_ad, da.* FROM ders_atamalari da
                                           JOIN dersler d ON d.id = da.ders_id WHERE da.sinif_id = ?""", (sid,))}
    assert atamalar["TÜRK DİLİ VE EDEBİYATI"]["ogretmen_id"] == tde_ogr
    assert atamalar["Seçmeli Ders"]["haftalik_saat"] == 2
    assert atamalar["Rehberlik ve Yönlendirme"]["ogretmen_id"] == rehber
    assert atamalar["Nesne Tabanlı Programlama"]["tur"] == "Meslek" and atamalar["Nesne Tabanlı Programlama"]["alan_id"]
    assert atamalar["Din Kültürü ve Ahlak Bilgisi"]["alan_id"] is None
    assert atamalar["Din Kültürü ve Ahlak Bilgisi"]["kisa_ad"] == "DKAB"
    assert sum(r["haftalik_saat"] for n, r in atamalar.items() if n != "Seçmeli Ders") == p.okul_saati

    tekrar = cerceve.uygula(db, sid, p)
    assert not tekrar.degisti and len(tekrar.mevcut) == len(p.okul_dersleri)
    assert cerceve.uyumsuzluklar(db) == []


def test_ders_tanimi_alanlar_arasinda_karismaz(db):
    s1 = _sinif(db, "9-A", 9, "MTAL-AMP", "Bilişim Teknolojileri", None)
    s2 = _sinif(db, "9-B", 9, "MTAL-AMP", "Muhasebe ve Finansman", None)
    cerceve.tum_siniflara_uygula(db)
    mga = db.q("SELECT alan_id FROM dersler WHERE ad = 'Mesleki Gelişim Atölyesi'")
    assert len(mga) == 2, "her alanın meslek dersi kendi alanına bağlı açılır"
    assert db.q1("SELECT COUNT(*) c FROM dersler WHERE ad = 'Matematik'")["c"] == 1
    assert {r["sinif_id"] for r in db.q("SELECT sinif_id FROM ders_atamalari")} == {s1, s2}


def test_isletme_dersleri_ve_gun_uyarilari(db):
    sid = _sinif(db, "12-A", 12, "MTAL-AMP", "Bilişim Teknolojileri", "Yazılım Geliştirme")
    s = cerceve.uygula(db, sid, cerceve.sinif_programi(db, sid).program)
    assert not db.q1("SELECT 1 FROM dersler WHERE ad = 'İşletmelerde Mesleki Eğitim'")
    assert any("3 gün işletmelerde" in u for u in s.uyarilar)


def test_denetim_eksik_zorunlu_dersi_bulur(db):
    sid = _sinif(db)
    cerceve.uygula(db, sid, cerceve.sinif_programi(db, sid).program)
    db.execute("DELETE FROM ders_atamalari WHERE ders_id = (SELECT id FROM dersler WHERE ad = 'Felsefe')")
    db.execute("UPDATE ders_atamalari SET haftalik_saat = 1 WHERE ders_id = (SELECT id FROM dersler WHERE ad = 'Tarih')")
    _sinif(db, "10-B", 10, "MTAL-ATP", "Bilişim Teknolojileri", None)
    bulgular = denetim.denetle(db)

    def ornekler(baslangic):
        return next(x.ornekler for x in bulgular if x.mesaj.startswith(baslangic))

    assert "10-A (Felsefe)" in ornekler("Çerçeve öğretim programındaki zorunlu ders")
    assert "10-A (Tarih (1/2))" in ornekler("Haftalık saati çerçeve öğretim programından farklı")
    assert any(o.startswith("10-B") for o in ornekler("Çerçeve öğretim programı belirlenemeyen"))


def test_eylem_asistan_ve_surec(db):
    _sinif(db)
    y = asistan.yorumla(db, "zorunlu dersleri aç")
    assert y.eylem == "cerceve_dersleri"
    s = surecler.calistir(db, "cerceve_dersleri")
    assert "1 sınıfta" in s.mesaj and db.q1("SELECT COUNT(*) c FROM ders_atamalari")["c"] > 10
    adim = next(a for a in surecler.durumlar(db, "yil_basi") if a.adim.eylem == "cerceve_dersleri")
    assert adim.durum is True


@pytest.mark.parametrize("program, seviye, beklenen", [
    ("MTAL-AMP", 11, False), ("MTAL-AMP-11", 11, True), ("MTAL-AMP-11", 10, False), ("MTAL-ATP", 12, True),
    ("MEM", 9, True)])
def test_isletmeye_giden_sinif(program, seviye, beklenen):
    assert isletmeye_giden_sinif(program, seviye) is beklenen
