import os

import pytest

from koordmes.services import program
from koordmes.services import program_mevzuat as pm

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _ogretmen(db, ad, **k):
    a, s = ad.split()
    return db.insert("ogretmenler", {"ad": a, "soyad": s, "unvan": k.pop("unvan", "Öğretmen"), **k})


def _ders(db, ad, blok=1, **k):
    return db.insert("dersler", {"ad": ad, "blok": blok, **k})


def _atama(db, sinif, ders, ogretmen, saat, **k):
    return db.insert("ders_atamalari", {"sinif_id": sinif, "ders_id": ders, "ogretmen_id": ogretmen,
                                        "haftalik_saat": saat, **k})


def _hucreler(db, atama):
    return [(r["gun"], r["saat"]) for r in
            db.q("SELECT gun, saat FROM program_hucreleri WHERE atama_id = ? ORDER BY gun, saat", (atama,))]


# ------------------------------------------------------------------ parametreler kesin uygulanır

def test_genel_kapali_sabahci_ve_ogretmen_yarim_gun(db):
    db.ayar_yaz("gunluk_ders_saati", 8)
    db.ayar_yaz("program_genel_kapali", "5-*")
    sabahci = db.insert("siniflar", {"ad": "9-A", "tedrisat": "Sabahçı"})
    oglenci = db.insert("siniflar", {"ad": "9-B", "tedrisat": "Öğlenci"})
    t = _ogretmen(db, "Ali Can")
    db.ayar_yaz("program_ogretmen_yarim_gun", 1)
    a = _atama(db, sabahci, _ders(db, "Mat"), t, 6)
    b = _atama(db, oglenci, _ders(db, "Fiz"), t, 6)
    s = program.programi_olustur(db, sure_limit=5, seed=1)
    assert not s.yerlesmeyen
    assert all(h <= 4 and g != 5 for g, h in _hucreler(db, a))
    assert all(h >= 5 and g != 5 for g, h in _hucreler(db, b))
    assert not {g for g, _ in _hucreler(db, a)} & {g for g, _ in _hucreler(db, b)}
    assert program.kural_ihlalleri(db) == []

    db.execute("UPDATE program_hucreleri SET gun = 1 WHERE atama_id = ?", (b,))
    db.execute("UPDATE program_hucreleri SET gun = 1 WHERE atama_id = ?", (a,))
    assert any("hem sabah hem öğleden sonra" in m for m in program.kural_ihlalleri(db))


def test_blok_deseni_ve_ogle_bolunmez_isareti(db):
    db.ayar_yaz("gunluk_ders_saati", 6)
    db.ayar_yaz("program_ogle_arasi", 3)
    db.ayar_yaz("program_ogle_tum_bloklar", 0)
    s = db.insert("siniflar", {"ad": "10-A", "okul_gunleri": "1,2,3"})
    t1, t2 = _ogretmen(db, "Ali Can"), _ogretmen(db, "Ece Su")
    desenli = _atama(db, s, _ders(db, "Atölye", blok=2, blok_deseni="3+2"), t1, 5)
    bolunmez = _atama(db, s, _ders(db, "Lab", blok=2, ogle_bolunmez=1), t2, 4)
    assert [a.desen for a in program.atamalari_oku(db) if a.id == desenli] == [[3, 2]]
    sonuc = program.programi_olustur(db, sure_limit=5, seed=2)
    assert not sonuc.yerlesmeyen
    gunluk = {}
    for g, h in _hucreler(db, desenli):
        gunluk.setdefault(g, []).append(h)
    assert sorted(len(v) for v in gunluk.values()) == [2, 3]
    yer = set(_hucreler(db, bolunmez))
    assert not any((g, 3) in yer and (g, 4) in yer for g in range(1, 6))
    assert program.bloklara_bol(7, 2, [3, 3]) == [3, 3, 1] and program.bloklara_bol(2, 2, [3]) == [2]


def test_beden_egitimi_ilk_son_gun_ve_uygulamali_ogleden_sonra(db):
    db.ayar_yaz("gunluk_ders_saati", 8)
    db.ayar_yaz("program_ogle_arasi", 4)
    s = db.insert("siniflar", {"ad": "11-A"})
    bed = _atama(db, s, _ders(db, "Beden Eğitimi ve Spor", blok=1), _ogretmen(db, "Spor Hoca"), 2)
    atl = _atama(db, s, _ders(db, "Web Atölyesi", blok=4, atolye_gerekli=1), _ogretmen(db, "Bil Hoca"), 4)
    mat = _atama(db, s, _ders(db, "Matematik", blok=2), _ogretmen(db, "Mat Hoca"), 4)
    program.programi_olustur(db, sure_limit=5, seed=3)
    assert {g for g, _ in _hucreler(db, bed)} <= {1, 5}
    assert len(_hucreler(db, atl)) == 4 and len(_hucreler(db, mat)) == 4
    assert not pm.program_denetimi(db)

    db.execute("UPDATE program_hucreleri SET gun = 3 WHERE atama_id = ?", (bed,))
    assert any(b.konu == "Beden eğitimi / müzik" for b in pm.program_denetimi(db))

    tek = db.insert("siniflar", {"ad": "11-B", "okul_gunleri": "2"})
    uyg = _atama(db, tek, _ders(db, "Ağ Atölyesi", blok=4, atolye_gerekli=1), _ogretmen(db, "Ağ Hoca"), 4)
    teo = _atama(db, tek, _ders(db, "Tarih", blok=4), _ogretmen(db, "Tar Hoca"), 4)
    for seed in range(4):
        program.programi_olustur(db, sure_limit=5, seed=seed)
        assert [h for _, h in _hucreler(db, teo)] == [1, 2, 3, 4]
        assert [h for _, h in _hucreler(db, uyg)] == [5, 6, 7, 8]


def test_iyilestirme_kesin_kurallari_bozmaz(db):
    db.ayar_yaz("program_iyilestirme_tur", 3)
    db.ayar_yaz("program_ogretmen_gunluk_azami", 4)
    siniflar = [db.insert("siniflar", {"ad": f"9-{c}", "kapali_saatler": "*-1"}) for c in "ABC"]
    hocalar = [_ogretmen(db, f"Hoca {i}") for i in range(4)]
    for i, s in enumerate(siniflar):
        for j in range(4):
            _atama(db, s, _ders(db, f"D{i}{j}", blok=2), hocalar[(i + j) % 4], 4)
    sonuc = program.programi_olustur(db, sure_limit=8, seed=5)
    assert not sonuc.yerlesmeyen
    assert program.catismalar(db) == [] and program.kural_ihlalleri(db) == []
    gunluk = db.q("""SELECT dog.ogretmen_id, ph.gun, COUNT(*) n FROM program_hucreleri ph
                     JOIN ders_ogretmenleri dog ON dog.atama_id = ph.atama_id GROUP BY 1, 2""")
    assert max(r["n"] for r in gunluk) <= 4


# ------------------------------------------------------------------ yerleşmeme nedenleri

def test_neden_ogretmen_musait_degil_ve_koordinatorluk(db):
    db.ayar_yaz("gunluk_ders_saati", 4)
    s = db.insert("siniflar", {"ad": "12-A", "okul_gunleri": "1,2"})
    t = _ogretmen(db, "Ali Can", musait_olmayan="1-*")
    isl = db.insert("isletmeler", {"ad": "Usta"})
    db.insert("koordinator_gorevleri", {"ogretmen_id": t, "isletme_id": isl, "gun": 2, "haftalik_saat": 4})
    _atama(db, s, _ders(db, "Atölye", blok=2), t, 4)
    on = program.on_denetim(db)
    assert any(b.konu == "Blok" and b.seviye == "Kritik" for b in on)
    sonuc = program.programi_olustur(db, sure_limit=3, seed=1)
    assert len(sonuc.nedenler) == 2
    n = sonuc.nedenler[0]
    metin = n.metin
    assert "Öğretmen müsait değil" in metin and "koordinatörlük" in metin and "Ali Can" in metin
    assert "Sınıfın okul günü değil" in metin and "okul günü" not in n.ozet
    assert any("Müsait Olmadığı Saatler" in o for o in n.oneriler)
    assert any("kesin uyuldu" in x for x in sonuc.notlar)


def test_neden_mekan_ve_ogretmen_dolu(db):
    db.ayar_yaz("gunluk_ders_saati", 2)
    a, b = db.insert("siniflar", {"ad": "10-A", "okul_gunleri": "1"}), db.insert("siniflar", {"ad": "10-B",
                                                                                           "okul_gunleri": "1"})
    lab = db.insert("atolyeler", {"ad": "Bilişim Lab"})
    d = _ders(db, "Ağ", blok=2, atolye_gerekli=1)
    _atama(db, a, d, _ogretmen(db, "Ali Can"), 2, atolye_id=lab)
    _atama(db, b, d, _ogretmen(db, "Ece Su"), 2, atolye_id=lab)
    sonuc = program.programi_olustur(db, sure_limit=2, seed=1)
    [n] = sonuc.nedenler
    assert "atölye/laboratuvar boş değil" in n.ozet and any("Bilişim Lab" in x for x in n.nedenler)
    assert any("mekân" in o for o in n.oneriler)
    assert [x.etiket for x in program.yerlesmeme_nedenleri(db)] == [n.etiket]


def test_elle_ekleme_uyarilari(db):
    db.ayar_yaz("program_ogle_arasi", 4)
    s = db.insert("siniflar", {"ad": "9-A", "okul_gunleri": "1,2,3,4", "kapali_saatler": "1-1"})
    t = _ogretmen(db, "Ali Can", musait_olmayan="2-3")
    isl = db.insert("isletmeler", {"ad": "Usta"})
    db.insert("koordinator_gorevleri", {"ogretmen_id": t, "isletme_id": isl, "gun": 3, "haftalik_saat": 4})
    a = _atama(db, s, _ders(db, "Atölye", blok=2), t, 4)
    assert any("ders konmayacak" in u for u in program.elle_ekleme_uyarilari(db, a, 1, 1))
    assert any("müsait değil" in u for u in program.elle_ekleme_uyarilari(db, a, 2, 3))
    assert any("koordinatörlük" in u for u in program.elle_ekleme_uyarilari(db, a, 3, 2))
    assert any("okul günü değil" in u for u in program.elle_ekleme_uyarilari(db, a, 5, 2))
    db.insert("program_hucreleri", {"atama_id": a, "gun": 4, "saat": 4})
    assert any("öğle arasında" in u for u in program.elle_ekleme_uyarilari(db, a, 4, 5))
    assert program.elle_ekleme_uyarilari(db, a, 4, 2) == []


# ------------------------------------------------------------------ mevzuat ve norm

def test_yuk_denetimi_karar_md5_md6_md15_ve_md12_tercih(db):
    s = db.insert("siniflar", {"ad": "10-A"})
    cok = _ogretmen(db, "Ali Can")
    az = _ogretmen(db, "Ece Su", oncelikli_tercih="Süt izni kullanıyor")
    _atama(db, s, _ders(db, "Mat"), cok, 31)
    _atama(db, s, _ders(db, "Fiz"), az, 4)
    isl = db.insert("isletmeler", {"ad": "Usta"})
    db.insert("koordinator_gorevleri", {"ogretmen_id": az, "isletme_id": isl, "gun": 3, "haftalik_saat": 30})
    bulgular = pm.yuk_denetimi(db)
    kritik = [b.mesaj for b in bulgular if b.seviye == "Kritik"]
    assert any("Ali Can" in m and "1 saat verilemez" in m for m in kritik)
    assert any("Ece Su" in m and "işletmelerde meslek eğitimi" in m for m in kritik)
    assert any("günde en çok" in m for m in kritik)
    assert any(b.konu == "Öğretmen tercihi" and "Ece Su" in b.mesaj for b in bulgular)
    db.update("ogretmenler", az, {"musait_olmayan": "1-1"})
    assert not any(b.konu == "Öğretmen tercihi" for b in pm.yuk_denetimi(db))


def test_norm_formulleri():
    assert [pm.norm_genel(x) for x in (5, 6, 30, 31, 42, 43, 56, 57)] == [0, 1, 1, 2, 2, 2, 2, 3]
    assert [pm.norm_atolye(x) for x in (14, 15, 40, 41, 80, 81, 201, 202, 219, 220)] == \
           [0, 1, 1, 2, 2, 3, 5, 5, 5, 6]
    assert [pm.grup_sayisi(9, n) for n in (15, 21, 31)] == [1, 2, 3]
    assert [pm.grup_sayisi(11, n) for n in (16, 17, 25, 33)] == [1, 2, 3, 4]
    assert [pm.mudur_yardimcisi_normu(n) for n in (0, 500, 501, 2600)] == [0, 1, 2, 5]
    assert [pm.rehberlik_normu(n) for n in (149, 150, 500, 1000)] == [0, 1, 2, 3]


def test_norm_kadro_grup_ve_yonetici_dusulur(db):
    alan = db.insert("alanlar", {"ad": "Bilişim"})
    s = db.insert("siniflar", {"ad": "11-A", "seviye": 11, "alan_id": alan})
    for i in range(20):
        db.insert("ogrenciler", {"ad": f"Ö{i}", "soyad": "X", "sinif_id": s})
    bt = _ogretmen(db, "Ali Can", brans="Bilişim Teknolojileri", unvan="Atölye/Lab. Öğretmeni")
    my = _ogretmen(db, "Veli Ak", brans="Bilişim Teknolojileri", unvan="Müdür Yardımcısı")
    _atama(db, s, _ders(db, "Web", blok=4, atolye_gerekli=1, brans="Bilişim Teknolojileri"), bt, 12)
    _atama(db, s, _ders(db, "Veri Tabanı", blok=2, atolye_gerekli=1, brans="Bilişim Teknolojileri"), my, 4)
    [satir] = [n for n in pm.norm_kadro(db) if n.brans == "Bilişim Teknolojileri"]
    assert satir.ders_yuku == 24 and satir.norm == 1 and satir.mevcut == 1 and satir.tur.startswith("Atölye")
    yon = [n for n in pm.norm_kadro(db) if n.brans == "Müdür yardımcısı"][0]
    assert yon.norm == 1 and yon.mevcut == 1


def test_mem_teorik_gun_ve_is_adimlari(db):
    s = db.insert("siniflar", {"ad": "MEM-11", "program": "MEM", "okul_gunleri": "1,2,3"})
    _atama(db, s, _ders(db, "Meslek Teorisi"), None, 4)
    assert any(b.konu == "MEM" and b.seviye == "Kritik" for b in program.on_denetim(db))
    assert any(b.konu == "MEM teorik eğitim günü" for b in pm.mevzuat_denetimi(db))
    adim = {a.baslik.split(" (")[0].split(";")[0]: a for a in pm.is_adimlari(db)}
    assert adim["Sınıflar / şubeler"].durum is False
    assert adim["Öğretmenlere ders atama"].durum is False
    assert adim["DAĞITIM: otomatik yerleştirme"].durum is False
    assert len(pm.is_adimlari(db)) == 16

    db.update("siniflar", s, {"okul_gunleri": "1"})
    t = _ogretmen(db, "Ali Can")
    db.execute("UPDATE ders_atamalari SET ogretmen_id = ?", (t,))
    program.programi_olustur(db, sure_limit=3, seed=1)
    adim = {a.no: a for a in pm.is_adimlari(db)}
    assert adim[2].durum and adim[5].durum and adim[11].durum and adim[12].durum
    assert all(a.git for a in adim.values())


# ------------------------------------------------------------------ e-Okul

def test_eokul_cizelgesi_ve_karsilastirma(db, tmp_path):
    s = db.insert("siniflar", {"ad": "10-A"})
    t1, t2 = _ogretmen(db, "Yunus Tosyalıoğlu"), _ogretmen(db, "Yasin Tosyalı")
    mat = _atama(db, s, _ders(db, "Matematik", kisa_ad="MAT"), t1, 2)
    _atama(db, s, _ders(db, "Fizik"), t2, 2)
    program.programi_olustur(db, sure_limit=3, seed=1)
    tutarlilik = pm.eokul_tutarliligi(db)
    assert any("Aynı e-Okul kısaltması" in x for x in tutarlilik)
    yol = pm.eokul_cizelgesi(db, tmp_path / "eokul.xlsx")
    k = pm.eokul_karsilastir(db, [yol])
    assert k.okunan == 4 and k.eslesen == 4 and not k.farklar

    g, h = _hucreler(db, mat)[0]
    db.execute("DELETE FROM program_hucreleri WHERE atama_id = ? AND gun = ? AND saat = ?", (mat, g, h))
    k = pm.eokul_karsilastir(db, [yol])
    assert k.eslesen == 3 and any("programda boş" in f for f in k.farklar)


def test_teblig_satirlari(db):
    s = db.insert("siniflar", {"ad": "9-A"})
    _atama(db, s, _ders(db, "Mat"), _ogretmen(db, "Ali Can"), 3)
    program.programi_olustur(db, sure_limit=3, seed=1)
    [satir] = pm.teblig_satirlari(db)
    assert satir[1] == "Ali Can" and satir[3] == "3"
    assert "md" not in pm.teblig_metni(db) or "12. maddesi" in pm.teblig_metni(db)


# ------------------------------------------------------------------ arayüz

@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_ui_is_adimlari_ve_yerlesmeyen_penceresi(app, db, monkeypatch):
    from koordmes.ui import ortak
    from koordmes.ui.sayfa_program import ProgramSayfasi, YerlesmeyenPenceresi

    db.ayar_yaz("gunluk_ders_saati", 2)
    s = db.insert("siniflar", {"ad": "10-A", "okul_gunleri": "1"})
    t = _ogretmen(db, "Ali Can", musait_olmayan="1-2")
    a = _atama(db, s, _ders(db, "Mat"), t, 2)
    sayfa = ProgramSayfasi(db)
    surec = sayfa.widget(0)
    surec.yenile()
    assert surec.adimlar.rowCount() == 16 and "adım tamam" in surec.ozet.text()
    assert surec.bulgular.rowCount() >= 1 and surec.norm.rowCount() >= 2
    hedef = surec.adimlar.item(4, 0).data(0x0100)
    assert hedef.endswith(pm.SEKME_DAGILIM)
    assert surec.git(hedef) is sayfa.widget(1) and sayfa.currentIndex() == 1

    program.programi_olustur(db, sure_limit=2, seed=1)
    nedenler = program.yerlesmeme_nedenleri(db)
    assert len(nedenler) == 1
    w = YerlesmeyenPenceresi(nedenler, "başlık", ["not"])
    assert w.tablo.rowCount() == 1 and "Ne yapmalı" in w.ayrinti.toHtml()
    w.close()

    tablo = sayfa.program_tablosu()
    tablo._kimlikleri_doldur()
    tablo.kimlik.setCurrentIndex(tablo.kimlik.findData(s))
    sorular = []
    monkeypatch.setattr(ortak, "onay", lambda _p, metin, *a: sorular.append(metin) or False)
    monkeypatch.setattr(ortak, "bilgi", lambda _p, metin, *a: pytest.fail(metin))
    monkeypatch.setattr(ortak, "hata", lambda _p, metin, *a: pytest.fail(metin))
    monkeypatch.setattr("koordmes.ui.sayfa_program.QInputDialog.getItem",
                        lambda *a, **k: (a[3][0], True))
    tablo._ders_ekle(1, 2)
    assert sorular and "müsait değil" in sorular[0] and _hucreler(db, a) == [(1, 1)]
    surec.isaret_ogretmen.setCurrentIndex(surec.isaret_ogretmen.findData(t))
    assert "Aylık karşılığı" in surec.isaret_ozet.text()
    sayfa.close()
