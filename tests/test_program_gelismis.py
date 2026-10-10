from koordmes.services import ekders, program


def _temel(db, siniflar=("9-A",), ogretmenler=("Ali Can", "Ece Su")):
    S = {ad: db.insert("siniflar", {"ad": ad}) for ad in siniflar}
    T = {}
    for ad in ogretmenler:
        a, s = ad.split()
        T[ad] = db.insert("ogretmenler", {"ad": a, "soyad": s, "unvan": "Öğretmen"})
    return S, T


def _ders(db, ad, atolye=0, blok=1):
    return db.insert("dersler", {"ad": ad, "atolye_gerekli": atolye, "blok": blok})


def _hucreler(db, atama):
    return db.q("SELECT * FROM program_hucreleri WHERE atama_id = ? ORDER BY gun, saat", (atama,))


def test_iki_ogretmenli_ders_iki_ogretmeni_de_baglar(db):
    S, T = _temel(db, ("9-A", "9-B"))
    db.ayar_yaz("gunluk_ders_saati", 2)
    a = db.insert("ders_atamalari", {"sinif_id": S["9-A"], "ders_id": _ders(db, "Atölye"), "ogretmen_id": T["Ali Can"],
                                     "ogretmen2_id": T["Ece Su"], "haftalik_saat": 5})
    b = db.insert("ders_atamalari", {"sinif_id": S["9-B"], "ders_id": _ders(db, "Kimya"), "ogretmen_id": T["Ece Su"],
                                     "haftalik_saat": 5})
    s = program.programi_olustur(db, sure_limit=5, seed=3)
    assert not s.yerlesmeyen
    assert program.catismalar(db) == []
    a_saat = {(r["gun"], r["saat"]) for r in _hucreler(db, a)}
    b_saat = {(r["gun"], r["saat"]) for r in _hucreler(db, b)}
    assert len(a_saat) == 5 and len(b_saat) == 5 and not a_saat & b_saat
    tablo = program.program_tablosu(db, "ogretmen", T["Ece Su"])
    assert len(tablo) == 10 and tablo[next(iter(a_saat))]["ogretmen2"] == "Ece Su"


def test_kalabalik_sinif_iki_atolyeye_bolunur(db):
    S, T = _temel(db)
    alan = db.insert("alanlar", {"ad": "Bilişim"})
    db.update("siniflar", S["9-A"], {"alan_id": alan})
    for i in range(18):
        db.insert("ogrenciler", {"ad": f"Ö{i}", "soyad": "X", "sinif_id": S["9-A"]})
    lab1 = db.insert("atolyeler", {"ad": "Lab-1", "alan_id": alan, "kapasite": 10})
    lab2 = db.insert("atolyeler", {"ad": "Lab-2", "alan_id": alan, "kapasite": 10})
    buyuk = db.insert("atolyeler", {"ad": "Büyük Lab", "alan_id": alan, "kapasite": 20})
    a = db.insert("ders_atamalari", {"sinif_id": S["9-A"], "ders_id": _ders(db, "Ağ", atolye=1, blok=2),
                                     "ogretmen_id": T["Ali Can"], "haftalik_saat": 4})
    program.programi_olustur(db, sure_limit=5, seed=1)
    assert {r["atolye_id"] for r in _hucreler(db, a)} == {buyuk}  # mevcuda yeten tek mekân seçilir

    db.delete("atolyeler", buyuk)
    db.update("ders_atamalari", a, {"ogretmen2_id": T["Ece Su"]})
    program.programi_olustur(db, sure_limit=5, seed=1)
    h = _hucreler(db, a)
    assert len(h) == 4 and all({r["atolye_id"], r["atolye2_id"]} == {lab1, lab2} for r in h)
    assert program.catismalar(db) == []
    assert not [b for b in program.on_denetim(db) if b.konu == "Mekân"]


def test_birlestirilmis_dersler_ayni_saatte(db):
    S, T = _temel(db, ("9-A", "9-B"), ("Ali Can",))
    bed = _ders(db, "Beden Eğitimi", blok=2)
    a = db.insert("ders_atamalari", {"sinif_id": S["9-A"], "ders_id": bed, "ogretmen_id": T["Ali Can"],
                                     "haftalik_saat": 2, "birlestirme": "BED-9"})
    b = db.insert("ders_atamalari", {"sinif_id": S["9-B"], "ders_id": bed, "ogretmen_id": T["Ali Can"],
                                     "haftalik_saat": 2, "birlestirme": "bed-9"})
    s = program.programi_olustur(db, sure_limit=5, seed=1)
    assert not s.yerlesmeyen
    assert [(r["gun"], r["saat"]) for r in _hucreler(db, a)] == [(r["gun"], r["saat"]) for r in _hucreler(db, b)]
    assert program.catismalar(db) == [] and program.eksik_saatler(db) == []
    tablo = program.program_tablosu(db, "ogretmen", T["Ali Can"])
    assert len(tablo) == 2 and all(x["sinif"] == "9-A + 9-B" and len(x["ids"]) == 2 for x in tablo.values())
    db.update("ogretmenler", T["Ali Can"], {"aylik_karsilik": 0})
    [p] = ekders.puantaj(db, 2026, 10)
    assert p.aylik_karsilik == 0 and max(p.gunluk.values()) == 2  # birleşik ders öğretmene bir kez yazılır


def test_koordinatorluk_gunu_ve_gunluk_azami(db):
    S, T = _temel(db, ("9-A", "9-B"), ("Ali Can",))
    isl = db.insert("isletmeler", {"ad": "Usta"})
    db.insert("koordinator_gorevleri", {"ogretmen_id": T["Ali Can"], "isletme_id": isl, "gun": 3, "haftalik_saat": 4})
    db.ayar_yaz("program_ogretmen_gunluk_azami", 3)
    for s in S.values():
        db.insert("ders_atamalari", {"sinif_id": s, "ders_id": _ders(db, f"D{s}"), "ogretmen_id": T["Ali Can"],
                                     "haftalik_saat": 6})
    sonuc = program.programi_olustur(db, sure_limit=5, seed=2)
    assert not sonuc.yerlesmeyen and not sonuc.notlar
    rows = db.q("SELECT gun, COUNT(*) n FROM program_hucreleri GROUP BY gun")
    assert 3 not in {r["gun"] for r in rows} and max(r["n"] for r in rows) <= 3

    # 4 günde en çok 12 saat verilebilir: 14 saatlik yük ön denetimde yakalanır, çözüm koordinatörlük gününü açar
    db.execute("UPDATE ders_atamalari SET haftalik_saat = 7")
    assert any(b.seviye == "Kritik" and b.konu == "Öğretmen" for b in program.on_denetim(db))
    db.ayar_yaz("program_ogretmen_gunluk_azami", 0)
    sonuc = program.programi_olustur(db, sure_limit=5, seed=2)
    assert not sonuc.yerlesmeyen


def test_on_denetim_sinif_ve_bos_dagilim(db):
    assert program.on_denetim(db)[0].konu == "Ders dağılımı"
    S, T = _temel(db)
    db.update("siniflar", S["9-A"], {"okul_gunleri": "1,2"})
    db.insert("ders_atamalari", {"sinif_id": S["9-A"], "ders_id": _ders(db, "Mat"), "ogretmen_id": T["Ali Can"],
                                 "haftalik_saat": 30})
    assert any(b.konu == "Sınıf" and b.seviye == "Kritik" for b in program.on_denetim(db))
