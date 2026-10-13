import os
from datetime import date

import pytest
from lxml import etree

from koordmes.services import sgk_beyan, sgk_dosya, sgk_risk, sgk_toplu, sigorta

SICIL = "2 8510 01 01 1234567 063 01 12 000"
AYSE, ISMAIL, CAN = "10000000078", "10000000146", "10000000214"


def _ogrenci(db, ad, soyad, tc, yukumlu=1):
    s = db.q1("SELECT id FROM siniflar WHERE program = 'MTAL-AMP'")
    sid = s["id"] if s else db.insert("siniflar", {"ad": "12-AMP", "seviye": 12, "program": "MTAL-AMP"})
    return db.insert("ogrenciler", {"ad": ad, "soyad": soyad, "tc": tc, "sinif_id": sid, "bakmakla_yukumlu": yukumlu})


def _yerlestir(db, ogr, bas, bit=None):
    isl = db.q1("SELECT id FROM isletmeler") or {"id": db.insert("isletmeler", {"ad": "Usta Elektrik"})}
    return db.insert("yerlestirmeler", {"ogrenci_id": ogr, "isletme_id": isl["id"], "tur": "İşletmede Mesleki Eğitim",
                                        "baslangic": bas, "bitis": bit})


@pytest.fixture
def veri(db):
    db.update("kurum", 1, {"ad": "Atatürk Mesleki ve Teknik Anadolu Lisesi", "il": "Ankara", "ilce": "Çankaya",
                           "sgk_isyeri_sicil": SICIL})
    a = _ogrenci(db, "Ayşe", "Işık", AYSE)
    b = _ogrenci(db, "İsmail", "Öztürk", ISMAIL, yukumlu=0)
    c = _ogrenci(db, "Can", "Demir", CAN)
    return db, {"a": a, "b": b, "c": c, "ya": _yerlestir(db, a, "2026-09-14"),
                "yb": _yerlestir(db, b, "2026-10-05", "2026-10-20")}


def _sigortalilar(yol):
    kok = etree.parse(str(yol)).getroot()
    return kok.find("BORDRO").get("BELGEMAHIYET"), {s.get("TCKNO"): s for s in kok.iter("SIGORTALI")}


def test_beyan_kaydi_fark_ve_duzeltme(veri, tmp_path):
    db, ids = veri
    sgk_beyan.beyan_kaydet(db, 2026, 10, tarih_=date(2026, 11, 5))
    assert sgk_risk.aphb_verildi(db, 2026, 10) == date(2026, 11, 5)
    assert sgk_beyan.fark_analizi(db, 2026, 10).satirlar == []
    with pytest.raises(sgk_dosya.SgkDosyaHatasi, match="zaten kayıtlı"):
        sgk_beyan.beyan_kaydet(db, 2026, 10)

    db.insert("devamsizlik", {"ogrenci_id": ids["a"], "tarih": "2026-10-12", "tur": "Özürsüz", "gun": 1})
    _yerlestir(db, ids["c"], "2026-10-15")
    db.delete("yerlestirmeler", ids["yb"])
    fark = sgk_beyan.fark_analizi(db, 2026, 10)
    assert {f.tc: f.durum for f in fark.satirlar} == {AYSE: "Değişti", ISMAIL: "İptal edilecek", CAN: "Eklenecek"}
    assert "eksik gün 0 → 1" in next(f for f in fark.satirlar if f.tc == AYSE).aciklama
    assert "1 kişi değişti, 1 kişi eklenecek, 1 kişi iptal edilecek" in fark.ozet()

    s = sgk_beyan.duzeltme_dosyalari(db, 2026, 10, tmp_path, bugun=date(2026, 11, 10))
    iptal, ek = s.yollar
    assert "Düzeltme 1 İptal" in iptal.name and "Düzeltme 2 Ek" in ek.name
    assert sgk_dosya.xsd_dogrula(iptal) == [] and sgk_dosya.xsd_dogrula(ek) == []
    mahiyet, kisiler = _sigortalilar(iptal)
    assert mahiyet == "I" and set(kisiler) == {AYSE, ISMAIL} and kisiler[AYSE].get("GUN") == "30"
    mahiyet, kisiler = _sigortalilar(ek)
    assert mahiyet == "E" and set(kisiler) == {AYSE, CAN}
    assert kisiler[AYSE].get("GUN") == "29" and kisiler[AYSE].get("EKSIKGUNSAYISI") == "1"
    assert s.kisi == 3 and s.uyarilar[0].startswith("e-Bildirge V2'de dönemi seçip önce 'İptal'")

    iptal_id, ek_id = sgk_beyan.duzeltme_kaydet(db, 2026, 10)
    assert iptal_id and ek_id and sgk_beyan.fark_analizi(db, 2026, 10).satirlar == []
    assert set(sgk_beyan.beyan_edilen(db, 2026, 10)) == {(AYSE, "07"), (CAN, "07")}
    with pytest.raises(sgk_dosya.SgkDosyaHatasi, match="değişiklik yok"):
        sgk_beyan.duzeltme_dosyalari(db, 2026, 10, tmp_path)

    sgk_beyan.beyan_sil(db, ek_id)
    assert len(sgk_beyan.fark_analizi(db, 2026, 10).satirlar) == 2
    for b in sgk_beyan.beyanlar(db, 2026, 10):
        sgk_beyan.beyan_sil(db, b.id)
    assert sgk_risk.aphb_verildi(db, 2026, 10) is None


def test_gec_duzeltmede_tahakkuk_b_ve_ceza(veri, tmp_path):
    db, ids = veri
    sgk_beyan.beyan_kaydet(db, 2026, 10, tarih_=date(2026, 11, 5))
    _yerlestir(db, ids["c"], "2026-10-15")
    s = sgk_beyan.duzeltme_dosyalari(db, 2026, 10, tmp_path, bugun=date(2026, 12, 3))
    [ek] = s.yollar
    assert etree.parse(str(ek)).getroot().find("BORDRO").get("TAHAKKUKNEDEN") == "B"
    assert any("idari para cezası" in u for u in s.uyarilar)
    riskler = sgk_risk.analiz(db, date(2026, 12, 3))
    r = next(r for r in riskler if r.konu == "10/2026 belgesi verildikten sonra kayıtlar değişti")
    assert r.tahmini_ceza > 0 and "Aylık Beyan" in r.oneri


def test_xml_den_beyan_okuma(veri, tmp_path):
    db, ids = veri
    sonuc = sgk_dosya.aphb_dosyalari(db, 2026, 10, tmp_path, "xml", bugun=date(2026, 11, 3))
    x = sgk_beyan.xmlden_kaydet(db, sonuc.yollar[0], date(2026, 11, 5))
    assert (x.yil, x.ay, x.mahiyet, x.tahakkuk) == (2026, 10, "A", "A")
    assert {s.tc: s.ogrenci_id for s in x.satirlar} == {AYSE: ids["a"], ISMAIL: ids["b"]}
    ismail = next(s for s in x.satirlar if s.tc == ISMAIL)
    assert (ismail.giris, ismail.cikis, ismail.belge, ismail.cikis_nedeni) == \
           (date(2026, 10, 5), date(2026, 10, 20), "42", "22")
    assert sgk_beyan.fark_analizi(db, 2026, 10).satirlar == []
    assert sgk_beyan.beyanlar(db, 2026, 10)[0].aciklama == f"XML: {sonuc.yollar[0].name}"

    (tmp_path / "bos.xml").write_text("<A/>", "utf-8")
    with pytest.raises(sgk_dosya.SgkDosyaHatasi, match="aylık prim"):
        sgk_beyan.xml_oku(db, tmp_path / "bos.xml")


def test_iptal_dosyasi_once_aphb_iptal_satirlari(veri, tmp_path):
    db, _ = veri
    sgk_beyan.beyan_kaydet(db, 2026, 10, tarih_=date(2026, 11, 5))
    db.execute("UPDATE ogrenciler SET bakmakla_yukumlu = 0 WHERE tc = ?", (AYSE,))
    fark = sgk_beyan.fark_analizi(db, 2026, 10)
    [f] = fark.satirlar
    assert f.durum == "Değişti" and f.belge == "07 → 42" and f.aciklama.startswith("belge türü 07 → 42")
    s = sgk_dosya.aphb_dosyalari(db, 2026, 10, tmp_path, "xml", mahiyet="I", bugun=date(2026, 11, 10))
    _, kisiler = _sigortalilar(s.yollar[0])
    assert set(kisiler) == {AYSE, ISMAIL} and any("beyan" in u.lower() for u in s.uyarilar)


def test_aylik_on_kontrol(veri):
    db, ids = veri
    bugun = date(2026, 11, 3)
    k = {x.baslik: x for x in sgk_beyan.on_kontrol(db, 2026, 10, bugun)}
    assert k["İşyeri bilgileri"].durum is not False
    assert k["Bildirilecek sigortalılar"].durum is True
    assert k["İşe giriş bildirgeleri"].durum is False and "Ayşe Işık" in k["İşe giriş bildirgeleri"].detay
    assert k["Önceki ayın belgesi"].durum is False
    assert k["Devamsızlıkların işlenmesi (e-Okul)"].durum is None
    assert k["Bu ayın belgesi"].durum is None and "gün kaldı" in k["Bu ayın belgesi"].detay

    for y in (ids["ya"], ids["yb"]):
        sigorta.bildirildi_isaretle(db, y, "Giriş", date(2026, 9, 10))
    sgk_beyan.beyan_kaydet(db, 2026, 9, tarih_=date(2026, 10, 20))
    db.insert("devamsizlik", {"ogrenci_id": ids["a"], "tarih": "2026-10-12", "gun": 1})
    k = {x.baslik: x for x in sgk_beyan.on_kontrol(db, 2026, 10, bugun)}
    assert all(k[b].durum is True for b in ("İşe giriş bildirgeleri", "Önceki ayın belgesi",
                                            "Devamsızlıkların işlenmesi (e-Okul)"))
    sgk_beyan.beyan_kaydet(db, 2026, 10, tarih_=bugun)
    assert {x.baslik: x for x in sgk_beyan.on_kontrol(db, 2026, 10, bugun)}["Bu ayın belgesi"].durum is True

    db.update("kurum", 1, {"ad": ""})
    k = sgk_beyan.on_kontrol(db, 2026, 10, bugun)
    assert k[0].durum is False and "Hata Satırı 3" in k[0].detay
    assert sgk_beyan.kontrol_ozeti(k).startswith("1 sorun (İşyeri bilgileri)")
    assert sgk_beyan.on_kontrol(db, 2020, 1, bugun)[-1].durum is False


def test_toplu_cikis_on_kontrolu(veri):
    db, _ = veri
    db.insert("tatiller", {"ad": "Yarıyıl Tatili", "baslangic": "2027-01-18", "bitis": "2027-01-29"})
    k = {x.baslik: x for x in sgk_beyan.cikis_on_kontrol(db, date(2027, 1, 22), date(2027, 1, 22))}
    assert k["Önceki ayın belgesi"].durum is False and "Aralık 2026" in k["Önceki ayın belgesi"].detay
    assert k["Tatil"].durum is False
    assert k["İşten ayrılış nedeni kodu"].durum is True
    assert k["Ders yılı sonu"].durum is None
    assert "İşletmede 1" in k["Açık sigorta kayıtları"].detay

    db.update("kurum", 1, {"ders_yili_sonu": "2027-06-26"})
    sgk_beyan.beyan_kaydet(db, 2027, 5, tarih_=date(2027, 6, 10))
    k = {x.baslik: x for x in sgk_beyan.cikis_on_kontrol(db, date(2027, 6, 26), date(2027, 6, 26))}
    assert k["Önceki ayın belgesi"].durum is True and k["Ders yılı sonu"].durum is True and "Tatil" not in k


def test_risk_uygula_beyan_kaydeder(veri):
    db, _ = veri
    r = next(r for r in sgk_risk.analiz(db, date(2026, 11, 10)) if r.eylem == "aphb:2026-09")
    assert "beyan edilen satırlar kaydedildi" in sgk_risk.uygula(db, r)
    assert [b.mahiyet for b in sgk_beyan.beyanlar(db, 2026, 9)] == ["A"]
    assert not any(r.eylem == "aphb:2026-09" for r in sgk_risk.analiz(db, date(2026, 11, 10)))


def test_tarihe_gore_bildirge_bekleyenler(veri):
    db, ids = veri
    yc = _yerlestir(db, ids["c"], "2026-10-15")
    assert sgk_toplu.bildirge_bekleyenler(db, date(2026, 10, 15), "Giriş") == [yc]
    assert sgk_toplu.bildirge_bekleyenler(db, date(2026, 10, 15), "Giriş", []) == []
    assert sgk_toplu.bildirge_bekleyenler(db, date(2026, 10, 20), "Çıkış") == [ids["yb"]]
    sigorta.bildirildi_isaretle(db, ids["yb"], "Çıkış")
    assert sgk_toplu.bildirge_bekleyenler(db, date(2026, 10, 20), "Çıkış") == []


def test_eylemler_ve_asistan(veri, tmp_path, monkeypatch):
    from koordmes import config
    from koordmes.services import asistan, surecler

    db, ids = veri
    monkeypatch.setattr(config, "output_dir", lambda: tmp_path)
    bugun = date(2026, 11, 3)
    y = asistan.yorumla(db, "ekim sgk ön kontrol", bugun)
    assert "Ekim 2026 SGK belge ön kontrolü" in y.metin and "İşe giriş bildirgeleri" in y.metin
    y = asistan.yorumla(db, "ekim sgk belgesi verildi", bugun)
    assert y.eylem == "sgk_beyan_kaydet" and y.eylem_kw == {"yil": 2026, "ay": 10}
    assert surecler.EYLEMLER["sgk_beyan_kaydet"].onay
    surecler.calistir(db, "sgk_beyan_kaydet", **y.eylem_kw)
    assert sgk_risk.aphb_verildi(db, 2026, 10)
    assert "değişiklik yok" in asistan.yorumla(db, "ekim sgk düzeltme", bugun).metin
    _yerlestir(db, ids["c"], "2026-10-15")
    y = asistan.yorumla(db, "ekim sgk düzeltme", bugun)
    assert len(y.dosyalar) == 1 and "Ek" in y.dosyalar[0].name
    adim = next(a for a in surecler.durumlar(db, "aylik", 2026, 10) if a.adim.eylem == "sgk_xml")
    assert adim.durum is False and "düzeltme" in adim.detay
    assert any(a.adim.eylem == "sgk_on_kontrol" for a in surecler.durumlar(db, "aylik", 2026, 10))


def test_aylik_beyan_ekrani(veri, tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QDate
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from koordmes import config
    from koordmes.ui import ortak, sayfa_sgk_ucret
    from koordmes.ui.sayfa_sgk_beyan import AylikBeyan
    from koordmes.ui.sayfa_sgk_ucret import SgkSayfasi

    db, ids = veri
    monkeypatch.setattr(config, "output_dir", lambda: tmp_path)
    monkeypatch.setattr(ortak, "onay", lambda *a, **k: True)
    mesajlar = []
    monkeypatch.setattr(ortak, "bilgi", lambda _p, m, *a: mesajlar.append(m))
    monkeypatch.setattr(ortak, "hata", lambda _p, m, *a: mesajlar.append(m))
    gosterilen = []
    monkeypatch.setattr(sayfa_sgk_ucret, "dosya_sonucu_goster", lambda _p, s, *a: gosterilen.append(s))

    sayfa = SgkSayfasi(db)
    assert sayfa.tabText(2) == "Aylık Beyan (Adım Adım)"
    w = sayfa.widget(2)
    assert isinstance(w, AylikBeyan)
    w.ay.ayarla(2026, 10)
    w.yenile()
    assert w.kmodel.rowCount() >= 5 and "ön kontrol" in w.kontrol_ozeti.text()
    w.kaydet()
    assert sgk_beyan.beyanlar(db, 2026, 10) and w.fmodel.rowCount() == 0
    _yerlestir(db, ids["c"], "2026-10-15")
    w.yenile()
    assert w.fmodel.rowCount() == 1 and w.fmodel.rows[0][0] == "Eklenecek"
    w.duzeltme()
    assert gosterilen and gosterilen[-1].yollar[0].parent == tmp_path / "SGK"
    monkeypatch.setattr(ortak, "kaydet_yolu", lambda *a, **k: tmp_path / "beyan.xlsx")
    monkeypatch.setattr(ortak, "kaydedildi", lambda *a, **k: None)
    w.excel()
    assert (tmp_path / "beyan.xlsx").exists()
    w.duzeltme_kaydet()
    assert w.fmodel.rowCount() == 0 and [b.mahiyet for b in w.fark.beyanlar] == ["A", "E"]
    w.sil()
    assert w.fmodel.rowCount() == 1

    xml = sgk_dosya.aphb_dosyalari(db, 2026, 9, tmp_path, "xml", bugun=date(2026, 10, 3)).yollar[0]
    w.xmlden(str(xml))
    assert w.ay.deger() == (2026, 9) and sgk_beyan.beyanlar(db, 2026, 9)

    giris, cikis = sayfa.widget(5), sayfa.widget(6)
    giris.tarih.setDate(QDate(2026, 10, 15))
    giris.yenile()
    assert giris.bildirge_xml("Giriş", sessiz=True).kisi == 1
    cikis.tarih.setDate(QDate(2026, 10, 20))
    cikis.yenile()
    assert "Toplu çıkış ön kontrolü" in cikis.kontrol.text()
    assert cikis.bildirge_xml("Çıkış", sessiz=True).kisi == 1
    cikis.tarih.setDate(QDate(2026, 10, 21))
    assert cikis.bildirge_xml("Çıkış") is None and "bildirimi bekleyen" in mesajlar[-1]
