"""Deneme amaçlı örnek veri seti."""
from __future__ import annotations

import random

ERKEK = ["Ahmet", "Mehmet", "Mustafa", "Ali", "Hüseyin", "Emre", "Burak", "Yusuf", "Ömer", "Furkan", "Eren",
         "Kerem", "Berat", "Efe", "Arda", "Enes", "Kaan", "Onur", "Serkan", "Tuna"]
KADIN = ["Ayşe", "Fatma", "Zeynep", "Elif", "Merve", "Esra", "Büşra", "Selin", "Ece", "Derya", "Nur",
         "Sude", "Defne", "İrem", "Gizem", "Melis"]
SOYAD = ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Yıldırım", "Öztürk", "Aydın", "Özdemir",
         "Arslan", "Doğan", "Kılıç", "Aslan", "Çetin", "Kara", "Koç", "Kurt", "Özkan", "Şimşek", "Polat", "Erdem"]


def tc_uret(rng: random.Random) -> str:
    d = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(8)]
    d10 = ((sum(d[0:9:2]) * 7) - sum(d[1:8:2])) % 10
    d.append(d10)
    d.append(sum(d) % 10)
    return "".join(map(str, d))


def iban_uret(rng: random.Random) -> str:
    bban = "00010" + "0" + "".join(str(rng.randint(0, 9)) for _ in range(16))
    kontrol = 98 - int(bban + "2927" + "00") % 97
    s = f"TR{kontrol:02d}{bban}"
    return " ".join(s[i:i + 4] for i in range(0, len(s), 4))


def yukle(db, programi_coz: bool = True, seed: int = 42) -> None:
    rng = random.Random(seed)
    c = db.conn
    for t in ["program_hucreleri", "ders_atamalari", "koordinator_gorevleri", "ziyaretler", "devamsizlik",
              "beceri_notlari", "ek_ders_kayitlari", "aylik_odemeler", "yerlestirmeler", "ogrenciler", "dersler",
              "atolyeler", "isletme_talepleri", "anketler", "hizmetici_egitimler", "isletmeler", "siniflar",
              "ogretmenler", "dallar", "alanlar", "tatiller", "evrak"]:
        c.execute(f"DELETE FROM {t}")
    c.execute("""UPDATE kurum SET ad = 'Atatürk Mesleki ve Teknik Anadolu Lisesi', tur = 'MTAL', kurum_kodu = '123456',
                 il = 'Ankara', ilce = 'Yenimahalle', buyuksehir = 1, mudur = 'Hasan Tekin',
                 koordinator_mudur_yrd = 'Selma Uçar', sgk_isyeri_sicil = '2 8599 01 01 1234567 006 06 12 000',
                 adres = 'Örnek Mah. Okul Cad. No:1 Yenimahalle/Ankara', telefon = '0312 000 00 00',
                 egitim_yili = '2026-2027', ders_yili_baslangic = '2026-09-07',
                 birinci_donem_sonu = '2027-01-22', ders_yili_sonu = '2027-06-25' WHERE id = 1""")

    alan = {k: db.insert("alanlar", {"ad": ad, "kod": k}) for k, ad in
            [("BT", "Bilişim Teknolojileri"), ("EE", "Elektrik-Elektronik Teknolojisi"),
             ("MA", "Motorlu Araçlar Teknolojisi")]}
    dal = {"BT": db.insert("dallar", {"alan_id": alan["BT"], "ad": "Web Programcılığı"}),
           "EE": db.insert("dallar", {"alan_id": alan["EE"], "ad": "Elektrik Tesisatları ve Pano Montörlüğü"}),
           "MA": db.insert("dallar", {"alan_id": alan["MA"], "ad": "Otomotiv Elektromekanik"})}
    atolye = {
        "BT1": db.insert("atolyeler", {"ad": "Bilişim Lab-1", "tur": "Laboratuvar", "alan_id": alan["BT"]}),
        "BT2": db.insert("atolyeler", {"ad": "Bilişim Lab-2", "tur": "Laboratuvar", "alan_id": alan["BT"]}),
        "EE1": db.insert("atolyeler", {"ad": "Elektrik Atölyesi-1", "alan_id": alan["EE"]}),
        "EE2": db.insert("atolyeler", {"ad": "Elektrik Atölyesi-2", "alan_id": alan["EE"]}),
        "MA1": db.insert("atolyeler", {"ad": "Motor Atölyesi", "alan_id": alan["MA"]}),
    }

    def ogretmen(ad, soyad, brans, alan_k=None, unvan="Öğretmen", koord=0):
        return db.insert("ogretmenler", {"tc": tc_uret(rng), "ad": ad, "soyad": soyad, "brans": brans,
                                         "alan_id": alan.get(alan_k), "unvan": unvan, "koordinator": koord,
                                         "telefon": f"05{rng.randint(30, 59)} {rng.randint(100, 999)} "
                                                    f"{rng.randint(10, 99)} {rng.randint(10, 99)}"})
    T = {
        "TDE1": ogretmen("Aylin", "Korkmaz", "Türk Dili ve Edebiyatı"),
        "TDE2": ogretmen("Murat", "Ekinci", "Türk Dili ve Edebiyatı"),
        "MAT1": ogretmen("Cem", "Aksoy", "Matematik"),
        "MAT2": ogretmen("Deniz", "Tunç", "Matematik"),
        "ING": ogretmen("Seda", "Bulut", "İngilizce"),
        "TAR": ogretmen("Kemal", "Ateş", "Tarih"),
        "COG": ogretmen("Nilay", "Güneş", "Coğrafya"),
        "FEN": ogretmen("Oğuz", "Bayram", "Fizik"),
        "KIM": ogretmen("Pınar", "Sezer", "Kimya"),
        "BIY": ogretmen("Gül", "Eren", "Biyoloji"),
        "DIN": ogretmen("Yakup", "Karaca", "Din Kültürü ve Ahlak Bilgisi"),
        "BED": ogretmen("Tolga", "Uysal", "Beden Eğitimi ve Spor"),
        "BT1": ogretmen("Serdar", "Altun", "Bilişim Teknolojileri", "BT", koord=1),
        "BT2": ogretmen("Hande", "Işık", "Bilişim Teknolojileri", "BT", koord=1),
        "BT3": ogretmen("Volkan", "Er", "Bilişim Teknolojileri", "BT", "Atölye/Lab. Öğretmeni", koord=1),
        "EE1": ogretmen("Levent", "Akın", "Elektrik-Elektronik Teknolojisi", "EE", koord=1),
        "EE2": ogretmen("Barış", "Tan", "Elektrik-Elektronik Teknolojisi", "EE", koord=1),
        "EE3": ogretmen("Sinan", "Oral", "Elektrik-Elektronik Teknolojisi", "EE", "Atölye/Lab. Öğretmeni", koord=1),
        "MA1": ogretmen("Erkan", "Sarı", "Motorlu Araçlar Teknolojisi", "MA", koord=1),
        "MA2": ogretmen("Okan", "Duman", "Motorlu Araçlar Teknolojisi", "MA", "Atölye/Lab. Öğretmeni", koord=1),
        "MDY": ogretmen("Selma", "Uçar", "Elektrik-Elektronik Teknolojisi", "EE", "Koordinatör Müdür Yardımcısı"),
    }

    def ders(ad, kisa, tur="Kültür", alan_k=None, atolye_g=0, blok=2):
        return db.insert("dersler", {"ad": ad, "kisa_ad": kisa, "tur": tur, "alan_id": alan.get(alan_k),
                                     "atolye_gerekli": atolye_g, "blok": blok})
    D = {
        "TDE": ders("Türk Dili ve Edebiyatı", "TDE"), "MAT": ders("Matematik", "MAT"),
        "ING": ders("İngilizce", "İNG"), "TAR": ders("Tarih", "TAR"),
        "INK": ders("T.C. İnkılap Tarihi ve Atatürkçülük", "İNK"), "COG": ders("Coğrafya", "COĞ"),
        "FIZ": ders("Fizik", "FİZ"), "KIM": ders("Kimya", "KİM"), "BIY": ders("Biyoloji", "BİY"),
        "DIN": ders("Din Kültürü ve Ahlak Bilgisi", "DİN", blok=1), "BED": ders("Beden Eğitimi ve Spor", "BED"),
        "MGA": ders("Mesleki Gelişim Atölyesi", "MGA", "Atölye", None, 0, 4),
        "BT_TEMEL": ders("Bilişim Temelleri", "BTT", "Meslek", "BT", 1, 4),
        "BT_PROG": ders("Programlama Temelleri", "PRG", "Meslek", "BT", 1, 4),
        "BT_WEB": ders("Web Tasarımı ve Programlama", "WEB", "Atölye", "BT", 1, 4),
        "BT_VT": ders("Veri Tabanı", "VT", "Meslek", "BT", 1, 2),
        "EE_TEMEL": ders("Elektrik-Elektronik Esasları", "EEE", "Meslek", "EE", 1, 4),
        "EE_TES": ders("Elektrik Tesisatları", "TES", "Atölye", "EE", 1, 4),
        "EE_PANO": ders("Pano Montaj", "PNO", "Atölye", "EE", 1, 4),
        "MA_TEMEL": ders("Motorlu Araçlar Temel Uygulamaları", "MTU", "Atölye", "MA", 1, 4),
        "MA_EM": ders("Otomotiv Elektromekanik Sistemleri", "OES", "Atölye", "MA", 1, 4),
        "MEM_TEORI": ders("Meslek Teorisi (MEM)", "MTE", "Meslek", "MA", 0, 2),
        "MEM_TDE": ders("Genel Kültür (MEM)", "GNK", "Kültür", None, 0, 2),
    }

    def sinif(ad, seviye, alan_k, program="MTAL-AMP", okul="1,2,3,4,5", isletme=""):
        return db.insert("siniflar", {"ad": ad, "seviye": seviye, "program": program, "alan_id": alan.get(alan_k),
                                      "dal_id": dal.get(alan_k) if seviye >= 11 else None,
                                      "okul_gunleri": okul, "isletme_gunleri": isletme})
    S = {
        "9A": sinif("9-A", 9, None), "9B": sinif("9-B", 9, None),
        "10A": sinif("10-A", 10, "BT"), "10B": sinif("10-B", 10, "EE"),
        "11A": sinif("11-A", 11, "BT"), "11B": sinif("11-B", 11, "EE"), "11C": sinif("11-C", 11, "MA"),
        "12A": sinif("12-A", 12, "BT", okul="1,2", isletme="3,4,5"),
        "12B": sinif("12-B", 12, "EE", okul="1,2", isletme="3,4,5"),
        "12C": sinif("12-C", 12, "MA", okul="4,5", isletme="1,2,3"),
        "MEM": sinif("MEM-11 Otomotiv", 11, "MA", "MEM", okul="1", isletme="2,3,4,5"),
    }

    def atama(s, d, t, saat, blok=None, atolye_k=None):
        db.insert("ders_atamalari", {"sinif_id": S[s], "ders_id": D[d], "ogretmen_id": T.get(t) if t else None,
                                     "haftalik_saat": saat, "blok": blok, "atolye_id": atolye.get(atolye_k)})
    for s, tde, mat in [("9A", "TDE1", "MAT1"), ("9B", "TDE2", "MAT2")]:
        for d, t, h in [("TDE", tde, 5), ("MAT", mat, 4), ("ING", "ING", 4), ("TAR", "TAR", 2), ("COG", "COG", 2),
                        ("FIZ", "FEN", 2), ("KIM", "KIM", 2), ("BIY", "BIY", 2), ("DIN", "DIN", 2), ("BED", "BED", 2)]:
            atama(s, d, t, h)
    atama("9A", "MGA", "BT3", 8, 4, "BT2")
    atama("9B", "MGA", "EE3", 8, 4, "EE2")
    for s, tde, mat, alan_d, ogr in [("10A", "TDE1", "MAT1", ["BT_TEMEL", "BT_PROG"], ["BT1", "BT2"]),
                                     ("10B", "TDE2", "MAT2", ["EE_TEMEL", "EE_TES"], ["EE1", "EE2"])]:
        for d, t, h in [("TDE", tde, 4), ("MAT", mat, 2), ("ING", "ING", 2), ("TAR", "TAR", 2), ("FIZ", "FEN", 2),
                        ("DIN", "DIN", 1), ("BED", "BED", 2)]:
            atama(s, d, t, h)
        atama(s, alan_d[0], ogr[0], 8, 4)
        atama(s, alan_d[1], ogr[1], 8, 4)
    for s, tde, alan_d, ogr in [("11A", "TDE1", ["BT_WEB", "BT_VT"], ["BT2", "BT3"]),
                                ("11B", "TDE2", ["EE_TES", "EE_PANO"], ["EE2", "EE3"]),
                                ("11C", "TDE2", ["MA_TEMEL", "MA_EM"], ["MA1", "MA2"])]:
        for d, t, h in [("TDE", tde, 3), ("ING", "ING", 2), ("TAR", "TAR", 2), ("DIN", "DIN", 1), ("BED", "BED", 2)]:
            atama(s, d, t, h)
        atama(s, alan_d[0], ogr[0], 12, 4)
        atama(s, alan_d[1], ogr[1], 8, 4)
    for s, tde, alan_d, ogr in [("12A", "TDE1", "BT_WEB", "BT1"), ("12B", "TDE2", "EE_PANO", "EE1"),
                                ("12C", "TDE1", "MA_EM", "MA1")]:
        for d, t, h in [("TDE", tde, 2), ("INK", "TAR", 2), ("DIN", "DIN", 1), ("BED", "BED", 1)]:
            atama(s, d, t, h, 1 if h == 1 else None)
        atama(s, alan_d, ogr, 8, 4)
    atama("MEM", "MEM_TEORI", "MA2", 4, 2)
    atama("MEM", "MEM_TDE", "TDE2", 2)

    isletmeler = []
    for ad, alan_k, guz, km, per, kamu in [
        ("Mavi Yazılım Ltd. Şti.", "BT", "Merkez", 3, 24, 0), ("Kod Atölyesi Bilişim", "BT", "Merkez", 5, 8, 0),
        ("Ankara Teknokent Veri A.Ş.", "BT", "Batı", 14, 60, 0), ("Yenimahalle Belediyesi Bilgi İşlem", "BT", "Merkez", 2, 120, 1),
        ("Işık Elektrik Taahhüt", "EE", "OSB", 18, 12, 0), ("Volt Pano Sistemleri A.Ş.", "EE", "OSB", 20, 45, 0),
        ("Güç Elektrik Tesisat", "EE", "Merkez", 4, 6, 0), ("Enerji Mühendislik Ltd.", "EE", "Batı", 12, 22, 0),
        ("Usta Oto Servis", "MA", "Merkez", 3, 9, 0), ("Motor Plus Yetkili Servis", "MA", "OSB", 16, 38, 0),
        ("Şimşek Oto Elektrik", "MA", "Batı", 11, 4, 0), ("Kara Otomotiv", "MA", "Merkez", 6, 15, 0),
    ]:
        isletmeler.append((db.insert("isletmeler", {
            "ad": ad, "alan_id": alan[alan_k], "guzergah": guz, "mesafe_km": km, "personel_sayisi": per,
            "kamu_kurumu": kamu, "vergi_no": str(rng.randint(1000000000, 9999999999)),
            "yetkili": f"{rng.choice(ERKEK)} {rng.choice(SOYAD)}", "usta_ogretici": f"{rng.choice(ERKEK)} {rng.choice(SOYAD)}",
            "telefon": f"0312 {rng.randint(200, 499)} {rng.randint(10, 99)} {rng.randint(10, 99)}",
            "adres": f"{guz} Bölgesi No:{rng.randint(1, 99)} Ankara", "kontenjan": 6,
            "usta_belgesi": 0 if len(isletmeler) % 5 == 4 else 1,
            "uygunluk_tarihi": None if len(isletmeler) % 6 == 5 else "2026-06-15",
            "plan_onay_tarihi": "2026-09-18"}), alan_k))

    no = 100
    ogrenciler: dict[str, list[int]] = {}
    for s_key, adet in [("9A", 6), ("9B", 6), ("10A", 5), ("10B", 5), ("11A", 6), ("11B", 6), ("11C", 5),
                        ("12A", 8), ("12B", 8), ("12C", 7), ("MEM", 6)]:
        ogrenciler[s_key] = []
        for _ in range(adet):
            no += 1
            kiz = rng.random() < 0.3
            mem = s_key == "MEM"
            ogrenciler[s_key].append(db.insert("ogrenciler", {
                "tc": tc_uret(rng), "okul_no": str(no), "ad": rng.choice(KADIN if kiz else ERKEK),
                "soyad": rng.choice(SOYAD), "cinsiyet": "K" if kiz else "E", "sinif_id": S[s_key],
                "dogum_tarihi": f"{2009 if s_key.startswith('12') else 2010}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                "statu": "Çırak" if mem else "Öğrenci", "bakmakla_yukumlu": 0 if rng.random() < 0.15 else 1,
                "veli_ad": f"{rng.choice(ERKEK)} {rng.choice(SOYAD)}",
                "veli_tel": f"05{rng.randint(30, 59)} {rng.randint(100, 999)} {rng.randint(10, 99)} {rng.randint(10, 99)}",
                "iban": iban_uret(rng),
                "basari_ortalamasi": 50 + (no * 37) % 48 + 0.25 if s_key.startswith("11") else None}))

    baslangic = "2026-09-14"
    sayac = 1
    alan_sinif = {"12A": "BT", "12B": "EE", "12C": "MA", "MEM": "MA"}
    for s_key, alan_k in alan_sinif.items():
        uygun = [i for i, a in isletmeler if a == alan_k]
        for j, oid in enumerate(ogrenciler[s_key]):
            iid = uygun[j % len(uygun)]
            db.insert("yerlestirmeler", {
                "ogrenci_id": oid, "isletme_id": iid, "tur": "Çıraklık" if s_key == "MEM" else "İşletmede Mesleki Eğitim",
                "baslangic": baslangic, "bitis": None, "sozlesme_no": f"2026/{sayac:03d}" if sayac % 9 else "",
                "sozlesme_tarihi": "2026-09-10", "ucret": 0, "sigorta_giris_bildirildi": 0 if sayac in (3, 17) else 1,
                "sigorta_giris_bildirim_tarihi": "2026-09-11"})
            sayac += 1
    fesih = ogrenciler["12B"][-1]
    db.conn.execute("UPDATE yerlestirmeler SET bitis = '2026-09-25', durum = 'Feshedildi', "
                    "fesih_nedeni = 'Nakil' WHERE ogrenci_id = ?", (fesih,))
    for s_key in ("11A", "11B", "11C"):
        for oid in ogrenciler[s_key]:
            db.insert("yerlestirmeler", {"ogrenci_id": oid, "isletme_id": None, "tur": "Okulda Alan Eğitimi",
                                         "baslangic": baslangic, "sigorta_giris_bildirildi": 1})

    for oid, tarih_, tur, yer in [(ogrenciler["12A"][0], "2026-09-16", "Özürsüz", "İşletme"),
                                  (ogrenciler["12A"][0], "2026-09-17", "Özürsüz", "İşletme"),
                                  (ogrenciler["12A"][0], "2026-09-22", "Özürsüz", "Okul"),
                                  (ogrenciler["12A"][1], "2026-09-23", "Raporlu", "İşletme"),
                                  (ogrenciler["12C"][2], "2026-09-15", "Özürsüz", "İşletme")]:
        db.insert("devamsizlik", {"ogrenci_id": oid, "tarih": tarih_, "tur": tur, "yer": yer, "gun": 1,
                                  "sgk_eksik": 1 if tur == "Özürsüz" else 0})
    for _ in range(4):
        db.insert("devamsizlik", {"ogrenci_id": ogrenciler["12A"][0], "tarih": f"2026-09-{24 + _:02d}",
                                  "tur": "Özürsüz", "yer": "İşletme", "gun": 1, "sgk_eksik": 1})

    for ad, b, e in [("Cumhuriyet Bayramı", "2026-10-29", "2026-10-29"), ("Yılbaşı", "2027-01-01", "2027-01-01"),
                     ("Ulusal Egemenlik ve Çocuk Bayramı", "2027-04-23", "2027-04-23"),
                     ("Emek ve Dayanışma Günü", "2027-05-01", "2027-05-01"),
                     ("Atatürk'ü Anma, Gençlik ve Spor Bayramı", "2027-05-19", "2027-05-19")]:
        db.insert("tatiller", {"ad": ad, "baslangic": b, "bitis": e})
    c.execute("UPDATE ogrenciler SET agir_disiplin = 1 WHERE id = ?", (ogrenciler["11A"][-1],))
    c.execute("UPDATE ogrenciler SET oncelikli = 1 WHERE id = ?", (ogrenciler["11B"][0],))
    for iid, alan_k in isletmeler[:4]:
        db.insert("isletme_talepleri", {"tarih": "2026-10-05", "isletme_id": iid, "alan_id": alan[alan_k],
                                        "talep_sayisi": 2, "ogretmen_id": T["BT1"]})
    db.insert("hizmetici_egitimler", {"tarih": "2026-11-12", "konu": "İş pedagojisi ve öğrenci değerlendirme",
                                      "katilimcilar": "Usta öğreticiler", "egitici": "Selma Uçar",
                                      "yer": "Okul konferans salonu", "sure_saat": 3})
    db.conn.commit()

    if programi_coz:
        from . import koordinator, program
        program.programi_olustur(db, sure_limit=15, seed=seed)
        koordinator.otomatik_gorevlendir(db)
