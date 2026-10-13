import pytest

from koordmes.services import program, program_araclari as pa


def _ogretmen(db, ad, brans="", **k):
    a, s = ad.split()
    return db.insert("ogretmenler", {"ad": a, "soyad": s, "unvan": "Öğretmen", "brans": brans, **k})


def _ders(db, ad, blok=1):
    return db.insert("dersler", {"ad": ad, "blok": blok})


def _atama(db, sinif, ders, ogretmen, saat, **k):
    return db.insert("ders_atamalari", {"sinif_id": sinif, "ders_id": ders, "ogretmen_id": ogretmen,
                                        "haftalik_saat": saat, **k})


def _gunler(db, atama):
    return {r["gun"] for r in db.q("SELECT gun FROM program_hucreleri WHERE atama_id = ?", (atama,))}


def test_sinif_kapali_saatleri_ve_ogle_arasi(db):
    db.ayar_yaz("gunluk_ders_saati", 6)
    db.ayar_yaz("program_ogle_arasi", 3)
    s = db.insert("siniflar", {"ad": "9-A", "kapali_saatler": "*-1,5-*"})
    t = _ogretmen(db, "Ali Can")
    a = _atama(db, s, _ders(db, "Atölye", blok=2), t, 8)
    sonuc = program.programi_olustur(db, sure_limit=5, seed=1)
    assert not sonuc.yerlesmeyen
    hucreler = db.q("SELECT gun, saat FROM program_hucreleri WHERE atama_id = ? ORDER BY gun, saat", (a,))
    assert len(hucreler) == 8
    assert all(h["saat"] != 1 and h["gun"] != 5 for h in hucreler)
    yer = {(h["gun"], h["saat"]) for h in hucreler}
    assert not any((g, 3) in yer and (g, 4) in yer for g in range(1, 6))
    assert program.kural_ihlalleri(db) == []

    db.execute("UPDATE program_hucreleri SET saat = 1 WHERE id = (SELECT MIN(id) FROM program_hucreleri)")
    assert any("kapalı saati" in m for m in program.kural_ihlalleri(db))


def test_ders_grubu_ayni_gune_gelmez(db):
    s = db.insert("siniflar", {"ad": "9-A"})
    t1, t2 = _ogretmen(db, "Ali Can"), _ogretmen(db, "Ece Su")
    mat, fiz = _ders(db, "Matematik"), _ders(db, "Fizik")
    a = _atama(db, s, mat, t1, 2)
    b = _atama(db, s, fiz, t2, 2)
    db.insert("program_ders_gruplari", {"ad": "Sayısal", "dersler": f"{mat},{fiz}", "aktif": 1})
    sonuc = program.programi_olustur(db, sure_limit=5, seed=4)
    assert not sonuc.yerlesmeyen
    assert not _gunler(db, a) & _gunler(db, b)
    assert program.kural_ihlalleri(db) == []

    # aynı günü zorunlu kılan veri: parametrelere kesin uyulur, yerleşmeyen blok nedeniyle bildirilir
    db.update("siniflar", s, {"okul_gunleri": "1"})
    sonuc = program.programi_olustur(db, sure_limit=5, seed=4)
    n = len(sonuc.yerlesmeyen)
    assert n and any("kesin uyuldu" in x and f"{n} blok daha" in x for x in sonuc.notlar)
    neden = sonuc.nedenler[0]
    assert len(sonuc.nedenler) == n and "aynı güne gelmemesi" in neden.ozet
    assert any("Matematik" in x for x in neden.nedenler) and any("Kısıtlar" in o for o in neden.oneriler)
    assert program.kural_ihlalleri(db) == []
    assert [x.etiket for x in program.yerlesmeme_nedenleri(db)] == [neden.etiket] * n

    # gevşetmeye izin verilirse dersler yerleşir, ihlal raporlanır
    db.ayar_yaz("program_kural_gevset", 1)
    sonuc = program.programi_olustur(db, sure_limit=5, seed=4)
    assert not sonuc.yerlesmeyen and any("gevşetildi" in n for n in sonuc.notlar)
    assert any("Aynı güne gelmemeli" in m for m in program.kural_ihlalleri(db))


def test_ogretmen_ayni_gun_kurali_rehberlik_muaf(db):
    db.ayar_yaz("program_ogretmen_ayni_gun", 1)
    s = db.insert("siniflar", {"ad": "9-A"})
    t = _ogretmen(db, "Ali Can")
    a = _atama(db, s, _ders(db, "Tarih"), t, 2)
    b = _atama(db, s, _ders(db, "Coğrafya"), t, 2)
    r = _atama(db, s, _ders(db, "Rehberlik ve Yönlendirme"), t, 1)
    atamalar = program.atamalari_oku(db)
    kurallar = program.gun_kurallari(atamalar, [], True, program.rehberlik_dersleri(db))
    assert kurallar == {a: {b}, b: {a}}
    sonuc = program.programi_olustur(db, sure_limit=5, seed=2)
    assert not sonuc.yerlesmeyen and not _gunler(db, a) & _gunler(db, b)
    assert len(_gunler(db, r)) == 1


def test_surum_kaydet_ve_yukle(db):
    s = db.insert("siniflar", {"ad": "9-A"})
    t = _ogretmen(db, "Ali Can")
    a = _atama(db, s, _ders(db, "Mat"), t, 3)
    program.programi_olustur(db, sure_limit=5, seed=1)
    db.execute("UPDATE program_hucreleri SET kilitli = 1 WHERE id = (SELECT MIN(id) FROM program_hucreleri)")
    ilk = {(r["gun"], r["saat"], r["kilitli"]) for r in db.q("SELECT * FROM program_hucreleri")}
    sid = pa.surum_kaydet(db, "Eylül", "ilk hâli")
    assert pa.surumler(db)[0]["hucre"] == 3

    db.execute("DELETE FROM program_hucreleri")
    db.insert("program_hucreleri", {"atama_id": a, "gun": 5, "saat": 8})
    sonuc = pa.surum_yukle(db, sid)
    assert sonuc.yapilan == 3
    assert {(r["gun"], r["saat"], r["kilitli"]) for r in db.q("SELECT * FROM program_hucreleri")} == ilk
    otomatik = [x for x in pa.surumler(db) if x["ad"].startswith("Otomatik")]
    assert len(otomatik) == 1 and otomatik[0]["hucre"] == 1

    # ders dağılımı yeniden kurulmuşsa hücre aynı sınıf-ders atamasına eşlenir
    db.delete("ders_atamalari", a)
    yeni = _atama(db, s, db.q1("SELECT id FROM dersler")["id"], t, 3)
    assert pa.surum_yukle(db, sid, once_yedekle=False).yapilan == 3
    assert len(_gunler(db, yeni)) >= 1
    pa.surum_sil(db, sid)
    assert all(x["id"] != sid for x in pa.surumler(db))
    with pytest.raises(ValueError):
        pa.surum_yukle(db, sid)


def test_toplu_cak(db):
    s1, s2 = db.insert("siniflar", {"ad": "9-A"}), db.insert("siniflar", {"ad": "9-B", "okul_gunleri": "1,2"})
    t1, t2 = _ogretmen(db, "Ali Can"), _ogretmen(db, "Ece Su")
    reh = _ders(db, "Rehberlik")
    r1 = _atama(db, s1, reh, t1, 1)
    r2 = _atama(db, s2, reh, t2, 1)
    mat = _atama(db, s1, _ders(db, "Mat"), t2, 2)
    db.insert("program_hucreleri", {"atama_id": mat, "gun": 3, "saat": 2})
    db.insert("program_hucreleri", {"atama_id": r1, "gun": 1, "saat": 1})
    sonuc = pa.toplu_cak(db, reh, 3, 2, [s1, s2])
    assert sonuc.yapilan == 1
    assert any("okul günü değil" in m for m in sonuc.mesajlar)
    assert any("kaldırıldı" in m for m in sonuc.mesajlar)
    h = db.q("SELECT gun, saat, kilitli FROM program_hucreleri WHERE atama_id = ?", (r1,))
    assert [(x["gun"], x["saat"], x["kilitli"]) for x in h] == [(3, 2, 1)]
    assert not db.q("SELECT 1 FROM program_hucreleri WHERE atama_id = ?", (mat,))
    assert not db.q("SELECT 1 FROM program_hucreleri WHERE atama_id = ?", (r2,))

    db.insert("program_hucreleri", {"atama_id": mat, "gun": 1, "saat": 1, "kilitli": 1})
    sonuc = pa.toplu_cak(db, reh, 1, 1, [s1])
    assert sonuc.yapilan == 0 and "kilitli" in sonuc.mesajlar[0]


def test_sinif_ogretmeni_ata(db):
    s1, s2 = db.insert("siniflar", {"ad": "9-A", "seviye": 9}), db.insert("siniflar", {"ad": "9-B", "seviye": 9})
    t1, t2 = _ogretmen(db, "Ali Can"), _ogretmen(db, "Ece Su")
    _atama(db, s1, _ders(db, "Mat"), t1, 6)
    _atama(db, s1, _ders(db, "Rehberlik"), t2, 1)
    _atama(db, s2, _ders(db, "Fizik"), t2, 4)
    _atama(db, s2, _ders(db, "Kimya"), t1, 2)
    out = pa.sinif_ogretmeni_ata(db)
    assert out == [("9-A", "Ece Su"), ("9-B", "Ali Can")]
    assert db.q1("SELECT rehber_ogretmen_id FROM siniflar WHERE id = ?", (s1,))["rehber_ogretmen_id"] == t2
    assert db.q1("SELECT sinif_ogretmenligi FROM ogretmenler WHERE id = ?", (t1,))["sinif_ogretmenligi"] == "9-B"
    assert pa.sinif_ogretmeni_ata(db) == []


def test_yuk_analizi(db):
    s1, s2 = db.insert("siniflar", {"ad": "9-A"}), db.insert("siniflar", {"ad": "9-B"})
    t1 = _ogretmen(db, "Ali Can", "Matematik")
    t2 = _ogretmen(db, "Ece Su", "Matematik")
    beden = _ders(db, "Beden")
    _atama(db, s1, beden, t1, 2, birlestirme="B9")
    _atama(db, s2, beden, t1, 2, birlestirme="b9")
    _atama(db, s1, _ders(db, "Mat"), t1, 30)
    _atama(db, s2, _ders(db, "Fizik"), None, 3)
    assert pa.ogretmen_yukleri(db) == {t1: 32}
    satirlar = {y.ogretmen_id: y for y in pa.ogretmen_yuk_tablosu(db)}
    assert satirlar[t1].ders_saati == 32 and satirlar[t2].ders_saati == 0
    assert satirlar[t1].ek_ders == 32 - satirlar[t1].aylik_karsilik
    assert satirlar[t2].eksik == satirlar[t2].aylik_karsilik
    [ozet] = pa.brans_ozeti(list(satirlar.values()))
    assert ozet[:6] == ["Matematik", 2, 32, 16.0, 0, 32]
    atanmamis = pa.atanmamis_dersler(db)
    assert ["9-B", "Fizik", 3, "Öğretmen atanmamış"] in atanmamis


def test_ders_devri(db):
    s = db.insert("siniflar", {"ad": "9-A"})
    giden = _ogretmen(db, "Ali Can", "Matematik")
    t2 = _ogretmen(db, "Ece Su", "Matematik")
    t3 = _ogretmen(db, "Veli Tan", "Matematik")
    _ogretmen(db, "Zeki Er", "Fizik")
    a = _atama(db, s, _ders(db, "Mat"), giden, 4)
    b = _atama(db, s, _ders(db, "Geometri"), giden, 2)
    _atama(db, s, _ders(db, "Analiz"), t2, 3)
    db.update("siniflar", s, {"rehber_ogretmen_id": giden})
    db.insert("program_hucreleri", {"atama_id": b, "gun": 1, "saat": 1})
    db.insert("program_hucreleri", {"atama_id": db.q1("SELECT id FROM ders_atamalari WHERE ogretmen_id = ?",
                                                       (t2,))["id"], "gun": 2, "saat": 1})
    assert [x["id"] for x in pa.devir_adaylari(db, giden)] == [t3, t2]
    sonuc = pa.ders_devret(db, giden, pasif_yap=True)
    assert sonuc.yapilan == 2
    assert db.q1("SELECT ogretmen_id FROM ders_atamalari WHERE id = ?", (a,))["ogretmen_id"] == t3      # en az yüklü
    assert db.q1("SELECT ogretmen_id FROM ders_atamalari WHERE id = ?", (b,))["ogretmen_id"] == t2      # t3 artık daha yüklü; t2 1. gün 1. saatte boş
    assert db.q1("SELECT aktif FROM ogretmenler WHERE id = ?", (giden,))["aktif"] == 0
    assert db.q1("SELECT rehber_ogretmen_id FROM siniflar WHERE id = ?", (s,))["rehber_ogretmen_id"] is None

    isl = db.insert("isletmeler", {"ad": "Usta"})
    db.insert("koordinator_gorevleri", {"ogretmen_id": t2, "isletme_id": isl, "gun": 3, "haftalik_saat": 2})
    sonuc = pa.ders_devret(db, t2, hedef_id=t3, koordinatorluk=True)
    assert sonuc.yapilan == 2 and any("koordinatörlük" in m for m in sonuc.mesajlar)
    assert db.q1("SELECT ogretmen_id FROM koordinator_gorevleri")["ogretmen_id"] == t3

    yalniz = _ogretmen(db, "Can Ak", "Kimya")
    _atama(db, s, _ders(db, "Kimya"), yalniz, 2)
    with pytest.raises(ValueError):
        pa.ders_devret(db, yalniz)
