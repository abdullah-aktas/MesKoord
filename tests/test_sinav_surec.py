import os
from datetime import date, timedelta

import pytest

from test_sinav import PAZARTESI, _donem, _okul

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _ders_yili(db, t: str = "2026-09-14") -> None:
    db.execute("UPDATE kurum SET ders_yili_baslangic = ? WHERE id = 1", (t,))


# ------------------------------------------------------------------ ders yılı ve kapalı seanslar

def test_ders_yili_icinde_otomatik_ve_elle(db):
    from koordmes.services import sinav

    _ders_yili(db)
    kasim = sinav.donem_ekle(db, "Kasım", baslangic=PAZARTESI)
    eylul = sinav.donem_ekle(db, "Eylül", baslangic=date(2026, 9, 7))
    temmuz = sinav.donem_ekle(db, "Temmuz", baslangic=date(2027, 7, 5))
    assert sinav.ders_yili_icinde(db, sinav.donem(db, kasim))
    assert not sinav.ders_yili_icinde(db, sinav.donem(db, eylul))
    assert not sinav.ders_yili_icinde(db, sinav.donem(db, temmuz))
    db.update("sinav_donemleri", eylul, {"ders_yili_icinde": "Evet"})
    db.update("sinav_donemleri", kasim, {"ders_yili_icinde": "Hayır"})
    assert sinav.ders_yili_icinde(db, sinav.donem(db, eylul))
    assert not sinav.ders_yili_icinde(db, sinav.donem(db, kasim))
    tarihsiz = _donem(db)
    assert sinav.ders_yili_icinde(db, sinav.donem(db, tarihsiz))


def test_koordinatorluk_ve_ders_saati_kapali_seans_olur(db):
    from koordmes.services import sinav

    okul = _okul(db, 3)
    _ders_yili(db)
    cem, oguz = okul["ogretmen"]["Cem Aksoy"], okul["ogretmen"]["Oğuz Bayram"]
    isletme = db.insert("isletmeler", {"ad": "Örnek A.Ş."})
    db.insert("koordinator_gorevleri", {"ogretmen_id": oguz, "isletme_id": isletme, "gun": 2, "haftalik_saat": 4})
    atama = db.q1("SELECT id FROM ders_atamalari WHERE ogretmen_id = ?", (cem,))["id"]
    db.insert("program_hucreleri", {"atama_id": atama, "gun": 1, "saat": 2})
    did = _donem(db, gun=2, saatler=[("08:40", "09:20"), ("10:30", "11:10")])
    seans = {(r["tarih"], r["sira"]): r["id"] for r in sinav.seanslar(db, did)}
    pzt, sali = PAZARTESI.isoformat(), (PAZARTESI + timedelta(days=1)).isoformat()

    db.ayar_yaz("program_ders_saatleri", "08:00-08:40, 08:50-09:30, 09:40-10:20")
    k = sinav.kapali_seans_nedenleri(db, did)
    assert k[oguz] == {seans[(sali, 1)]: "koordinator", seans[(sali, 2)]: "koordinator"}
    assert k[cem] == {seans[(pzt, 1)]: "ders"}

    db.update("sinav_donemleri", did, {"ders_yili_icinde": "Hayır"})
    assert sinav.kapali_seans_nedenleri(db, did) == {}
    db.update("sinav_donemleri", did, {"ders_yili_icinde": "Evet"})

    sinav.ogretmenleri_hazirla(db, did)
    assert sinav.kume_coz(db.q1("SELECT kapali_seanslar FROM sinav_ogretmenleri WHERE ogretmen_id = ?",
                                (oguz,))["kapali_seanslar"]) == {seans[(sali, 1)], seans[(sali, 2)]}
    sinav.ogretmen_ayarla(db, did, oguz, kapali_seanslar=set())
    assert set(sinav.eksik_kapali_seanslar(db, did)) == {oguz}
    assert sinav.nobetten_doldur(db, did) == 1
    assert sinav.eksik_kapali_seanslar(db, did) == {}


def test_isletme_gunundeki_ogrencinin_sinavi_baska_gune(db):
    from koordmes.services import sinav

    okul = _okul(db, 6)
    _ders_yili(db)
    db.update("siniflar", okul["sinif"]["10-A"], {"isletme_gunleri": "1,2,3,4"})
    did = _donem(db, gun=5, saatler=sinav.VARSAYILAN_SAATLER[:2])
    sid = sinav.sinav_ekle(db, did, "Matematik", 10)
    sinav.sinav_ogrenci_ekle(db, sid, okul["ogrenci"]["10-A"])

    def gun() -> int:
        sinav.planla(db, did, sure_limit=1, seed=1)
        r = db.q1("SELECT se.tarih FROM sinavlar s JOIN sinav_seanslari se ON se.id = s.seans_id WHERE s.id = ?",
                  (sid,))
        return date.fromisoformat(r["tarih"]).weekday()

    assert gun() == 4
    db.update("sinav_donemleri", did, {"ders_yili_icinde": "Hayır"})
    assert gun() == 0


# ------------------------------------------------------------------ yerleşmeme nedenleri

def test_yerlesmeyen_sinavin_ayrintili_nedeni_ve_ek_gun_onerisi(db):
    from koordmes.services import sinav

    okul = _okul(db, 4)
    did = _donem(db, gun=1, saatler=sinav.VARSAYILAN_SAATLER[:3])
    ogr = okul["ogrenci"]["9-A"]
    for ders in ("Matematik", "Fizik", "Kimya"):
        sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, ders, 9), ogr)
    s = sinav.planla(db, did, sure_limit=2, seed=1)
    assert len(s.nedenler) == 1 and s.nedenler[0].sinav_id == s.yerlesemeyen[0][0]
    n = s.nedenler[0]
    assert n.ogrenci == 4 and "sınav yükü" in n.ozet
    assert any("3 sınavı var" in x and "en az 2 sınav günü" in x for x in n.nedenler)
    assert any("günlük sınav sınırı" in x for x in n.nedenler)
    assert n.oneriler and "Sınav günü ekleyin" in n.oneriler[0]
    assert any("1 sınav günü uzatılırsa" in x and "10.11.2026" not in x and "03.11.2026" in x for x in s.notlar)
    assert any("günlük sınav sınırı 2 yerine 3" in x for x in s.notlar)
    assert len(sinav.seanslar(db, did)) == 3

    nedenler = sinav.yerlesmeme_nedenleri(db, did)
    assert [x.sinav_id for x in nedenler] == [n.sinav_id]
    assert "engel olan" in "\n".join(nedenler[0].nedenler)


def test_ogretmen_ve_salon_engeli_aciklanir(db):
    from koordmes.services import sinav

    okul = _okul(db, 10)
    did = _donem(db, gun=1, saatler=sinav.VARSAYILAN_SAATLER[:1])
    db.insert("sinav_salonlari", {"ad": "Salon", "kapasite": 15, "sira": 1})
    a = sinav.sinav_ekle(db, did, "Matematik", 9)
    b = sinav.sinav_ekle(db, did, "Fizik", 10)
    sinav.sinav_ogrenci_ekle(db, a, okul["ogrenci"]["9-A"])
    sinav.sinav_ogrenci_ekle(db, b, okul["ogrenci"]["10-A"])
    s = sinav.planla(db, did, sure_limit=1, seed=0)
    assert s.yerlesen == 1
    metin = s.nedenler[0].metin()
    assert "salon kapasitesi" in metin and "toplam salon kapasitesi 15" in metin
    assert "Salonlar" in "\n".join(s.nedenler[0].oneriler)


# ------------------------------------------------------------------ öneriler, ek ders, iş adımları

def test_kural_ve_birlestirme_onerileri(db):
    from koordmes.services import sinav, sinav_surec

    okul = _okul(db, 4)
    did = _donem(db)
    ogr = okul["ogrenci"]["10-A"]
    db.insert("dersler", {"ad": "Geometri", "tur": "Kültür"})
    sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, "Matematik", 10), ogr[:3])
    sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, "Geometri", 10), ogr[1:])
    sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, "Fizik", 10), ogr[:2])
    sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, "Kimya", 9), okul["ogrenci"]["9-A"])
    oneriler = sinav_surec.kural_onerileri(db, did)
    assert [(o.ders1, o.ders2, o.ortak) for o in oneriler] == [("Geometri", "Matematik", 2)]
    assert sinav_surec.kural_onerilerini_ekle(db, did) == 1
    assert sinav_surec.kural_onerileri(db, did) == []

    eml = sinav.sinav_ekle(db, did, "Tarih", 12, grup="EML")
    atl = sinav.sinav_ekle(db, did, "Tarih", 12, grup="ATL")
    oys = sinav.sinav_ekle(db, did, "Tarih", 12, grup="OYS")
    on2 = okul["ogrenci"]["12-A"]
    sinav.sinav_ogrenci_ekle(db, eml, on2[:3])
    sinav.sinav_ogrenci_ekle(db, atl, on2[3:])
    sinav.sinav_ogrenci_ekle(db, oys, on2[:1])
    b = sinav_surec.birlestirme_onerileri(db, did)
    assert len(b) == 1 and set(b[0].sinav_ids) == {eml, atl} and b[0].ogrenci == 4
    sinav.sinavlari_birlestir(db, b[0].sinav_ids)
    assert sinav_surec.birlestirme_onerileri(db, did) == []


def test_gorev_ucretleri_ek_ders_puantajina_aktarilir(db):
    from koordmes.services import ekders, sinav, sinav_surec

    okul = _okul(db, 6)
    did = _donem(db, gun=2)
    for ders, sv in (("Matematik", 9), ("Fizik", 10), ("Tarih", 12)):
        sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, ders, sv), okul["ogrenci"][f"{sv}-A"])
    db.insert("sinav_salonlari", {"ad": "Salon", "kapasite": 30, "sira": 1})
    sinav.planla(db, did, sure_limit=2, seed=1)
    sinav.gorevlileri_ata(db, did, seed=1)
    gereken = sum(k["saat"] for k in sinav.gorev_ucretleri(db, did))
    assert gereken > 0 and sinav_surec.ekders_durumu(db, did) == (0.0, gereken)

    a = sinav_surec.ekderse_aktar(db, did)
    assert a.saat == gereken and a.satir >= a.ogretmen > 0 and "aktarıldı" in a.ozet()
    assert sinav_surec.ekderse_aktar(db, did).satir == a.satir
    kayit = db.q("SELECT * FROM ek_ders_kayitlari WHERE tur = 'Sınav Görevi'")
    assert len(kayit) == a.satir and sum(r["saat"] for r in kayit) == gereken
    assert sinav_surec.ekders_durumu(db, did) == (gereken, gereken)
    p = ekders.puantaj(db, PAZARTESI.year, PAZARTESI.month)
    assert sum(x.diger.get("Sınav Görevi", 0) for x in p) == gereken

    g = db.q1("SELECT g.id FROM sinav_gorevlileri g JOIN sinavlar s ON s.id = g.sinav_id WHERE s.donem_id = ? "
              "LIMIT 1", (did,))["id"]
    db.update("sinav_gorevlileri", g, {"durum": sinav.GELMEDI})
    aktarilan, yeni = sinav_surec.ekders_durumu(db, did)
    assert yeni < aktarilan


def test_is_adimlari_sureci_izler(db):
    from koordmes.services import sinav, sinav_surec

    adimlar = sinav_surec.is_adimlari(db, None)
    assert adimlar[0].durum is False and adimlar[0].git == sinav_surec.DONEM_AYARI

    okul = _okul(db, 6)
    did = sinav.donem_ekle(db, "Kasım Sorumluluk", baslangic=PAZARTESI, bitis=PAZARTESI + timedelta(days=4))
    adim = {a.baslik: a for a in sinav_surec.is_adimlari(db, did)}
    assert adim["Sınav dönemi, türü ve tarihleri"].durum is True
    assert adim["e-Okul'dan sorumlu öğrenci listesini aktarma"].durum is False
    assert "OOK12001R012" in adim["e-Okul'dan sorumlu öğrenci listesini aktarma"].detay
    assert adim["Seans çizelgesi (sınav günleri ve oturumlar)"].durum is False

    sinav.seanslari_olustur(db, did, sinav.tarihleri_uret(PAZARTESI, PAZARTESI + timedelta(days=4)),
                            sinav.VARSAYILAN_SAATLER[:3])
    for ders, sv in (("Matematik", 9), ("Fizik", 10), ("Tarih", 12)):
        sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, ders, sv), okul["ogrenci"][f"{sv}-A"])
    db.insert("sinav_salonlari", {"ad": "Salon", "kapasite": 30, "sira": 1})
    db.update("ogrenciler", okul["ogrenci"]["9-A"][0], {"aktif": 0})
    adim = {a.baslik: a for a in sinav_surec.is_adimlari(db, did, bugun=PAZARTESI - timedelta(days=7))}
    assert adim["e-Okul'dan sorumlu öğrenci listesini aktarma"].durum is True
    assert adim["Öğrenci durumu (okuldan ayrılan, tek ders koşulu)"].durum is False
    assert adim["Sınavları seanslara yerleştirme"].durum is False
    assert adim["Komisyon ve gözcü görevlendirme"].durum is None

    s, satirlar = sinav_surec.hepsini_yap(db, did, sure_limit=2)
    assert s.yerlesen == 3 and any("Denetim" in x for x in satirlar)
    adim = {a.baslik: a for a in sinav_surec.is_adimlari(db, did, bugun=PAZARTESI - timedelta(days=7))}
    assert adim["Sınavları seanslara yerleştirme"].durum is True
    assert adim["Komisyon ve gözcü görevlendirme"].durum is True
    assert adim["Öğrencileri salon ve sıralara yerleştirme"].durum is True
    assert adim["Görev ücretlerini ek ders puantajına aktarma"].durum is False
    sinav_surec.ekderse_aktar(db, did)
    son = sinav_surec.is_adimlari(db, did, bugun=PAZARTESI + timedelta(days=10))
    adim = {a.baslik: a for a in son}
    assert adim["Görev ücretlerini ek ders puantajına aktarma"].durum is True
    assert adim["Sınav günü: öğrenci yoklaması ve gelmeyen görevliler"].durum is False
    assert [a.no for a in son] == list(range(1, len(son) + 1))


def test_tek_ders_donemi_ogrenci_denetimi(db):
    from koordmes.services import sinav, sinav_surec

    okul = _okul(db, 2)
    did = sinav.donem_ekle(db, "Tek Ders", tur="Tek Ders", baslangic=PAZARTESI)
    on2, dokuz = okul["ogrenci"]["12-A"], okul["ogrenci"]["9-A"]
    sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, "Matematik", 12), on2)
    sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, "Fizik", 12), on2[:1])
    sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, "Kimya", 9), dokuz[:1])
    sorun = sinav_surec._ogrenci_sorunlari(db, did, "Tek Ders")
    assert len(sorun) == 2 and any("12. sınıf değil" in x for x in sorun) and any("2 sınavı var" in x for x in sorun)


def test_ana_sayfa_hatirlatmalari(db):
    from koordmes.services import sinav, sinav_surec, takvim

    okul = _okul(db, 4)
    did = sinav.donem_ekle(db, "Kasım Sorumluluk", baslangic=PAZARTESI, bitis=PAZARTESI + timedelta(days=1))
    assert any("sınav listesi boş" in m for _, m, _ in sinav_surec.hatirlatmalar(db, PAZARTESI - timedelta(days=5)))
    sinav.seanslari_olustur(db, did, [PAZARTESI, PAZARTESI + timedelta(days=1)], sinav.VARSAYILAN_SAATLER[:2])
    sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, "Matematik", 9), okul["ogrenci"]["9-A"])
    u = [x for x in takvim.uyarilar(db, PAZARTESI - timedelta(days=1)) if x.konu == "Sınav"]
    assert u and u[0].seviye == "Kritik" and "yerleşmemiş" in u[0].mesaj
    assert u[0].git == "Sınav Planlama ve Görevlendirme"
    assert not [x for x in takvim.uyarilar(db, PAZARTESI - timedelta(days=30)) if x.konu == "Sınav"]

    db.insert("sinav_salonlari", {"ad": "Salon", "kapasite": 30, "sira": 1})
    sinav_surec.hepsini_yap(db, did, sure_limit=1)
    mesaj = [m for _, m, _ in sinav_surec.hatirlatmalar(db, PAZARTESI - timedelta(days=3))]
    assert len(mesaj) == 1 and "ilan edin" in mesaj[0]
    sonra = [m for _, m, _ in sinav_surec.hatirlatmalar(db, PAZARTESI + timedelta(days=5))]
    assert any("ek ders puantajına" in m for m in sonra) and any("e-Okul'a girin" in m for m in sonra)
    sinav_surec.ekderse_aktar(db, did)
    assert not any("ek ders" in m for _, m, _ in sinav_surec.hatirlatmalar(db, PAZARTESI + timedelta(days=5)))


def test_asistan_sinav_komutlari(db):
    from koordmes.services import asistan, sinav

    y = asistan.yorumla(db, "sınav iş adımları")
    assert "Sınav dönemi yok" in y.metin or "yapılamadı" in y.metin
    okul = _okul(db, 4)
    did = _donem(db, gun=2)
    sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, "Matematik", 9), okul["ogrenci"]["9-A"])
    y = asistan.yorumla(db, "sorumluluk sınavı iş adımları")
    assert "adımdan" in y.metin and y.git == "Sınav Planlama ve Görevlendirme"
    assert asistan.yorumla(db, "tek ders sınavlarını planla").eylem == "sinav_planla"
    assert asistan.yorumla(db, "sınav ücretlerini ek derse aktar").git == "Ek Ders Puantajı"
    from koordmes.services import surecler
    s = surecler.calistir(db, "sinav_planla")
    assert "yerleştirildi" in s.mesaj


# ------------------------------------------------------------------ arayüz

@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def mesajlar(monkeypatch):
    from koordmes.ui import ortak

    kayit = []
    monkeypatch.setattr(ortak, "bilgi", lambda _p, m, *a, **k: kayit.append(("bilgi", m)))
    monkeypatch.setattr(ortak, "hata", lambda _p, m, *a, **k: kayit.append(("hata", m)))
    monkeypatch.setattr(ortak, "onay", lambda *a, **k: True)
    return kayit


def test_arayuz_is_adimlari_ve_neden_penceresi(app, db, mesajlar, monkeypatch):
    from koordmes.services import sinav
    from koordmes.ui import sayfa_sinav
    from koordmes.ui.sayfa_sinav import SinavNedenPenceresi, SinavSayfasi

    okul = _okul(db, 4)
    did = _donem(db, gun=1, saatler=sinav.VARSAYILAN_SAATLER[:2])
    for ders in ("Matematik", "Fizik", "Kimya"):
        sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, ders, 9), okul["ogrenci"]["9-A"])
    db.insert("dersler", {"ad": "Geometri", "tur": "Kültür"})
    sinav.sinav_ogrenci_ekle(db, sinav.sinav_ekle(db, did, "Geometri", 9), okul["ogrenci"]["9-A"][:1])
    w = SinavSayfasi(db)
    w.show()
    app.processEvents()
    adim = w.adimlar
    assert w.currentWidget() is adim and adim.tablo.rowCount() == len(adim.adimlar) > 10
    assert "adım tamam" in adim.ozet.text()
    i = next(i for i, a in enumerate(adim.adimlar) if a.git == "Salonlar")
    assert adim.git(adim._hedef(i)) is w.salonlar and w.currentIndex() == 4

    adim.kural_onerileri()
    assert {frozenset((r["ders1"], r["ders2"])) for r in sinav.kurallar(db, did)} == {
        frozenset(("Geometri", "Matematik")), frozenset(("Fizik", "Kimya"))}

    acilan = []
    monkeypatch.setattr(SinavNedenPenceresi, "exec", lambda self: acilan.append(self) or 0)
    sinav.planla(db, did, sure_limit=1, seed=0)
    adim.nedenler()
    assert len(acilan) == 1
    d = acilan[0]
    assert d.tablo.rowCount() == len(d.nedenler) >= 1 and d.tablo.item(0, 1).text() == "4 öğrenci"
    assert "Ne yapmalı?" in d.ayrinti.toHtml()

    w.planlama.nedenler()
    assert len(acilan) == 2
    sayfa_sinav.ekderse_aktar(adim, db, did)
    assert mesajlar[-1][0] == "bilgi"
    w.close()
