import os

from openpyxl import Workbook

from koordmes.services import aktarim, program, program_belge
from koordmes.services.okuyucu import Tablo

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]


def _xlsx(yol, sayfalar):
    wb = Workbook()
    wb.remove(wb.active)
    for ad, satirlar in sayfalar.items():
        ws = wb.create_sheet(ad)
        for r in satirlar:
            ws.append(r)
    wb.save(yol)
    return yol


def _hucreler(db, sinif):
    return {(r["gun"], r["saat"]): (r["ders"], r["ogretmen"], r["atolye"], r["kilitli"]) for r in db.q(
        """SELECT ph.gun, ph.saat, ph.kilitli, d.ad AS ders, o.ad || ' ' || o.soyad AS ogretmen, a.ad AS atolye
           FROM program_hucreleri ph JOIN ders_atamalari da ON da.id = ph.atama_id JOIN dersler d ON d.id = da.ders_id
           JOIN siniflar s ON s.id = da.sinif_id LEFT JOIN ogretmenler o ON o.id = da.ogretmen_id
           LEFT JOIN atolyeler a ON a.id = ph.atolye_id WHERE s.ad = ?""", (sinif,))}


# ------------------------------------------------------------------ çözümleyiciler

def test_gun_saat_hucre_cozumleme():
    assert [program_belge.gun_coz(x) for x in ("Pazartesi", "SALI", "Çar", "Prş", "cuma", "Cumartesi", 3, "x")] == \
        [1, 2, 3, 4, 5, 6, 3, None]
    assert [program_belge.saat_coz(x) for x in ("1", "2.", "3. Ders", "Ders 4", "V.", 6, "08:30-09:10", "X")] == \
        [1, 2, 3, 4, 5, 6, None, None]
    assert program_belge.hucre_coz("Matematik\nAhmet YILMAZ") == {"ders": "Matematik", "ogretmen": "Ahmet Yılmaz"}
    c = program_belge.hucre_coz("WEB (A.Kaya) [Bilişim Lab.]")
    assert c == {"ders": "WEB", "ogretmen": "A. Kaya", "atolye": "Bilişim Lab."}
    assert program_belge.hucre_coz("9-A Matematik") == {"sinif": "9-A", "ders": "Matematik"}
    assert program_belge.hucre_coz("ÖĞLE ARASI") is None


def test_musaitlik_metinden():
    m = program_belge.musaitlik_metinden
    assert m("Çarşamba", 8) == "3-*"
    assert m("Salı 5-8", 8) == "2-5,2-6,2-7,2-8"
    assert m("Pzt öğleden sonra; Cuma", 8) == "1-5,1-6,1-7,1-8,5-*"
    assert m("1-*,3-4", 8) == "1-*,3-4"
    assert m("-", 8) == ""


# ------------------------------------------------------------------ belgeler

def test_sinif_programi_izgarasi_kilitli_aktarilir(db, tmp_path):
    bas = [None, *GUNLER]
    sayfa = [["9-A Sınıfı Haftalık Ders Programı"], bas,
             ["1. Ders", "Matematik\nAhmet YILMAZ", "Web Tasarım\nAyşe Kaya\nBilişim Lab.", None, None, None],
             ["2. Ders", "Matematik\nAhmet YILMAZ", "Web Tasarım\nAyşe Kaya\nBilişim Lab.", None, None, None],
             ["ÖĞLE ARASI", None, None, None, None, None],
             ["3. Ders", "Türk Dili ve Edebiyatı\nCan Ece", None, None, None, "Matematik\nAhmet YILMAZ"],
             [None, "Okul Müdürü", None, None, None, None],
             [],
             ["9-B Sınıfı Haftalık Ders Programı"], bas,
             ["1. Ders", "Web Tasarım\nAyşe Kaya\nBilişim Lab.", None, None, None, None]]
    yol = _xlsx(tmp_path / "program.xlsx", {"Programlar": sayfa})
    bulunan, _ = aktarim.dosyalari_incele([yol])
    assert [b.en_iyi.anahtar for b in bulunan] == ["program_hucreleri"]
    sonuclar, hatalar = aktarim.otomatik_aktar(db, [yol])
    assert not hatalar and sum(s.eklenen for s in sonuclar) == 7
    h = _hucreler(db, "9-A")
    assert h[(1, 1)] == ("Matematik", "Ahmet Yılmaz", None, 1) and h[(5, 3)][0] == "Matematik"
    assert h[(2, 2)] == ("Web Tasarım", "Ayşe Kaya", "Bilişim Lab.", 1)
    assert (1, 4) not in h and len(h) == 6
    assert _hucreler(db, "9-B")[(1, 1)][0] == "Web Tasarım"
    saat = {r["ad"]: r["haftalik_saat"] for r in db.q(
        "SELECT d.ad, da.haftalik_saat FROM ders_atamalari da JOIN dersler d ON d.id = da.ders_id "
        "JOIN siniflar s ON s.id = da.sinif_id WHERE s.ad = '9-A'")}
    assert saat == {"Matematik": 3, "Web Tasarım": 2, "Türk Dili ve Edebiyatı": 1}
    assert program.catismalar(db) == []

    # kilitli saatler korunur; dağılımda saati artırılan ders kalan saatlere yerleşir
    db.execute("UPDATE ders_atamalari SET haftalik_saat = 5 WHERE ders_id = (SELECT id FROM dersler "
               "WHERE ad = 'Matematik')")
    program.programi_olustur(db, sure_limit=5, seed=1)
    h = _hucreler(db, "9-A")
    assert sum(1 for v in h.values() if v[0] == "Matematik") == 5 and h[(1, 1)][3] == 1
    assert program.catismalar(db) == []


def test_tum_okul_carsaf_programi(db, tmp_path):
    ust = ["Sınıf"]
    alt = [None]
    for g in GUNLER[:3]:
        ust += [g, None, None]
        alt += [1, 2, 3]
    sayfa = [["OKUL HAFTALIK DERS PROGRAMI"], ust, alt,
             ["10-A", "MAT / A.Yılmaz", "MAT / A.Yılmaz", None, None, "FİZ / B.Demir", None, None, None, None],
             ["10-B", "FİZ / B.Demir", None, None, None, None, None, "MAT / A.Yılmaz", None, None]]
    yol = _xlsx(tmp_path / "carsaf.xlsx", {"Sayfa1": sayfa})
    sonuclar, hatalar = aktarim.otomatik_aktar(db, [yol])
    assert not hatalar
    assert _hucreler(db, "10-A") == {(1, 1): ("MAT", "A. Yılmaz", None, 1), (1, 2): ("MAT", "A. Yılmaz", None, 1),
                                     (2, 2): ("FİZ", "B. Demir", None, 1)}
    assert _hucreler(db, "10-B")[(3, 1)][0] == "MAT"


def test_ogretmen_programi_sinif_hucreden(db, tmp_path):
    sayfa = [["Öğretmen: Ayşe Kaya"], ["Saat", *GUNLER],
             ["1", "12-A Web Tasarım", None, "11-B Grafik", None, None],
             ["2", "12-A Web Tasarım", None, None, None, None]]
    yol = _xlsx(tmp_path / "ogretmen.xlsx", {"Ayşe": sayfa})
    aktarim.otomatik_aktar(db, [yol])
    assert _hucreler(db, "12-A")[(1, 2)] == ("Web Tasarım", "Ayşe Kaya", None, 1)
    assert _hucreler(db, "11-B")[(3, 1)][1] == "Ayşe Kaya"


def test_gun_satirli_program():
    t = Tablo("x.xlsx", "11-C", [["Gün", "1", "2", "3"], ["Pazartesi", "Kimya\nDeniz Ak", "Kimya\nDeniz Ak", None],
                                  ["Salı", None, "Fizik\nEce Su", None], ["Çarşamba", None, None, None]])
    [d] = program_belge.donustur(t)
    assert d.satirlar[1:] == [["11-C", 1, 1, "Kimya", "Deniz Ak", None], ["11-C", 1, 2, "Kimya", "Deniz Ak", None],
                              ["11-C", 2, 2, "Fizik", "Ece Su", None]]


def test_matris_ders_dagilimi(db, tmp_path):
    sayfa = [["DERS DAĞILIM ÇİZELGESİ"], ["Dersler", "9-A", "9-B", "10-A", "Toplam"],
             ["Matematik", "4 (Ahmet Yılmaz)", "4 (Ahmet Yılmaz)", "", 8],
             ["Beden Eğitimi", "2 - Can Ece", "2 - Can Ece", "2 - Can Ece", 6],
             ["Toplam", 6, 6, 2, 14]]
    yol = _xlsx(tmp_path / "dagilim.xlsx", {"Dağılım": sayfa})
    sonuclar, hatalar = aktarim.otomatik_aktar(db, [yol])
    assert not hatalar and sum(s.eklenen for s in sonuclar) == 5
    rows = {(r["s"], r["d"]): (r["o"], r["haftalik_saat"]) for r in db.q(
        """SELECT s.ad s, d.ad d, o.ad || ' ' || o.soyad o, da.haftalik_saat FROM ders_atamalari da
           JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id
           LEFT JOIN ogretmenler o ON o.id = da.ogretmen_id""")}
    assert rows[("9-A", "Matematik")] == ("Ahmet Yılmaz", 4) and rows[("10-A", "Beden Eğitimi")] == ("Can Ece", 2)
    assert ("10-A", "Matematik") not in rows


def test_matris_ogretmen_satirli_ve_ters():
    t = Tablo("x.xlsx", "D", [["Öğretmen Adı Soyadı", "9-A", "9-B"], ["Ahmet Yılmaz", "MAT 4", "MAT 4"],
                               ["Can Ece", "BED 2", None]])
    [d] = program_belge.donustur(t)
    assert d.satirlar[1:] == [["9-A", "MAT", "Ahmet Yılmaz", 4], ["9-B", "MAT", "Ahmet Yılmaz", 4],
                              ["9-A", "BED", "Can Ece", 2]]
    t = Tablo("x.xlsx", "D", [["Sınıf", "Matematik", "Fizik"], ["9-A", 4, 2], ["9-B", 4, None]])
    [d] = program_belge.donustur(t)
    assert d.satirlar[1:] == [["9-A", "Matematik", None, 4], ["9-A", "Fizik", None, 2], ["9-B", "Matematik", None, 4]]


def test_musaitlik_cizelgesi_ve_liste(db, tmp_path):
    sayfa = [["ÖĞRETMEN BOŞ GÜN İSTEKLERİ"], ["Öğretmen", *GUNLER],
             ["Ahmet Yılmaz", None, None, "X", None, None], ["Can Ece", "X", None, None, None, "X"]]
    liste = [["Adı Soyadı", "Branş", "Müsait Olmadığı Günler"], ["Deniz Ak", "Kimya", "Salı 5-8"]]
    yol = _xlsx(tmp_path / "musait.xlsx", {"Boş Gün": sayfa, "Öğretmenler": liste})
    sonuclar, hatalar = aktarim.otomatik_aktar(db, [yol])
    assert not hatalar
    m = {f"{r['ad']} {r['soyad']}": r["musait_olmayan"] for r in db.q("SELECT * FROM ogretmenler")}
    assert m["Ahmet Yılmaz"] == "3-*" and m["Can Ece"] == "1-*,5-*"
    assert m["Deniz Ak"] == "2-5,2-6,2-7,2-8"


def test_program_disi_tablolar_degismez():
    t = Tablo("x.xlsx", "Öğrenciler", [["Okul No", "Adı Soyadı", "Sınıfı"], ["1", "Ali Veli", "9-A"],
                                        ["2", "Can Ece", "9-B"]])
    assert program_belge.donustur(t) is None
    t = Tablo("x.xlsx", "Mevcut", [["", "9-A", "9-B"], ["Erkek", 10, 12], ["Kız", 8, 9]])
    assert program_belge.donustur(t) is None
    t = Tablo("x.xlsx", "Koordinatör Görev Çizelgesi", [["Öğretmen", *GUNLER], ["Ali Can", "Usta Oto", "", "", "", ""],
                                                         ["Ece Su", "", "Mobilya Ltd", "", "", ""]])
    assert program_belge.donustur(t) is None


def test_pdf_program(db, tmp_path):
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from koordmes.ui import ortak
    hucre = lambda x: f"<td>{x}</td>"
    html = ("<p>12-B Sınıfı Ders Programı</p><table border='1'><tr><th>Saat</th>"
            + "".join(f"<th>{g}</th>" for g in GUNLER) + "</tr>"
            + "<tr>" + hucre("1") + hucre("Grafik<br>Ece Su") + hucre("") * 4 + "</tr>"
            + "<tr>" + hucre("2") + hucre("Grafik<br>Ece Su") + hucre("") * 3 + hucre("Kimya<br>Deniz Ak") + "</tr>"
            + "</table>")
    yol = tmp_path / "program.pdf"
    ortak.html_pdf(html, yol)
    aktarim.otomatik_aktar(db, [yol])
    h = _hucreler(db, "12-B")
    assert h[(1, 1)][:2] == ("Grafik", "Ece Su") and h[(5, 2)][:2] == ("Kimya", "Deniz Ak")


def _periyotlar(n=9):
    return ["Ders\\Gün", *[f"({i})" for i in range(1, n + 1)]]


def _gun(ad, n, saatler=()):
    satir = [ad, *([None] * n)]
    for saat, hucre in saatler:
        satir[saat] = hucre
    return satir


def _aktar_tablolar(db, tablolar):
    genis = program_belge.genislet(tablolar)
    bulunan = [aktarim.Bulunan(t, aktarim.tahmin_et(t)) for t in genis]
    sirali = sorted((b for b in bulunan if b.en_iyi),
                    key=lambda b: (aktarim.TANIMLAR[b.en_iyi.anahtar].sira, b.tablo.ad))
    sonuclar = [aktarim.aktar(db, b.tablo, b.en_iyi.anahtar, b.en_iyi.bas, b.en_iyi.eslesme) for b in sirali]
    return sonuclar


def test_ogretmen_kodu_eokul():
    from koordmes.services.eokul_program import ogretmen_kodu
    beklenen = {
        "YUNUS TOSYALIOĞLU": "Y.TSY", "İSMAİL SAĞDAŞLİ": "İ.SĞD", "SEMRA TUNÇ": "S.TNÇ",
        "HOGIR ÖZTEMEL": "H.ÖZT", "SERKAN IŞIK": "S.IŞK", "BEDİRHAN KAYA": "B.KYA",
        "DİLAN ÇEN": "D.ÇEN", "MEHMET HEYBETULLAH ALMAK": "M.ALM", "ŞURA NUR AĞDIK": "Ş.AĞD",
        "TUĞÇE TİMÜÇİN": "T.TMÇ", "SELÇUK KABAK": "S.KBK", "CAHİT SÖYLEMEZ": "C.SYL",
        "ÜMİT ZİREK": "Ü.ZRK", "SAADET ÖZPLOLAT": "S.ÖZP", "FIRAT TOKCAN": "F.TKC",
        "SABAHAT BEŞTAŞ": "S.BŞT",
    }
    assert {ad: ogretmen_kodu(ad) for ad in beklenen} == beklenen


def test_eokul_sinif_ve_ogretmen_programi(db):
    n = 11
    sinif = [
        Tablo("sinif.pdf", "9 BT A", [
            ["Sınıf : 9 BT A Toplam Ders Saati: 45 Sınıf Öğretmeni :"],
            _periyotlar(n),
            _gun("Saat", n, [(1, "08:20\n09:00")]),
            _gun("Pazartesi", n, [(1, "PT\nY.TSY"), (2, "PT\nY.TSY"), (3, "TRH\nA.YLM"), (11, "DKAB\nM.USL")]),
            _gun("Salı", n, [(1, "IME"), (2, "IME")]),
            _gun("Çarşamba", n),
        ]),
        Tablo("sinif.pdf", "açıklama", [
            ["S.No", "Ders", "Dersin Adı", "Hs", "Yer", "Dersin Öğretmeni"],
            ["1", "PT", "PROGRAMLAMA TEMELLERİ", "2", "Bilişim Lab.", "YUNUS TOSYALIOĞLU,BEDİRHAN KAYA"],
            ["2", "TRH", "TARİH", "1", "", "AYŞE YILMAZ"],
            ["3", "DKAB", "DİN KÜLTÜRÜ", "1", "", "MAHMUT USLU"],
            ["4", "IME", "İŞLETMELERDE MESLEKİ EĞİTİM", "2", "", ""],
        ]),
        Tablo("sinif.pdf", "9 MSM", [
            ["Sınıf : 9 MSM Toplam Ders Saati: 8 Sınıf Öğretmeni :"],
            _periyotlar(8),
            _gun("Cuma", 8, [(1, "TRH\nA.YLM")]),
        ]),
        Tablo("sinif.pdf", "açıklama 9 MSM", [
            ["S.No", "Ders", "Dersin Adı", "Hs", "Yer", "Dersin Öğretmeni"],
            ["1", "TRH", "TARİH", "1", "", "AYŞE YILMAZ"],
        ]),
    ]
    ogretmen = [
        Tablo("ogretmen.pdf", "Sabahat", [
            ["Sayı: Sınıf Öğretmenliği : 11AE Nöbet Günü ve Yeri: Pzt ATÖLYE"],
            ["Adı Soyadı: SABAHAT BEŞTAŞ Eğitici Kolu(Kulüp) :"],
            _periyotlar(8),
            _gun("Pazartesi", 8, [(1, "11 EE\nETP"), (2, "11 EE\nETP")]),
        ]),
        Tablo("ogretmen.pdf", "özet", [
            ["1", "11 EE", "ETP", "ELEKTRİK TESİSAT PROJLERİ", "2"],
            ["Toplamlar", "", "", "", "2"],
        ]),
        Tablo("ogretmen.pdf", "Form alanları", [
            ["Adı Soyadı", "Sınıf Öğretmenliği", "Nöbet Günü ve Yeri"],
            ["FULYA DEMİR", "Nöbet Günü ve Yeri:", "01.01.2026"],
        ], form=True),
    ]
    sonuclar = _aktar_tablolar(db, sinif + ogretmen)
    assert not any(s.hatalar for s in sonuclar)
    assert not any("Öğretmen yok" in x.mesaj for s in sonuclar for x in s.satirlar)

    bt = db.q1("SELECT * FROM siniflar WHERE ad = '9 BT A'")
    assert bt["okul_gunleri"] == "1" and bt["isletme_gunleri"] == "2" and bt["program"] == "MTAL-AMP"
    msm = db.q1("SELECT * FROM siniflar WHERE ad = '9 MSM'")
    assert msm["program"] == "MEM" and msm["okul_gunleri"] == "5" and msm["isletme_gunleri"] == ""
    assert db.ayar("gunluk_ders_saati") == 11

    h = _hucreler(db, "9 BT A")
    assert h[(1, 1)] == ("PROGRAMLAMA TEMELLERİ", "Yunus Tosyalıoğlu", "Bilişim Lab.", 1)
    assert h[(1, 3)][:2] == ("TARİH", "Ayşe Yılmaz") and h[(2, 1)][0] == "İŞLETMELERDE MESLEKİ EĞİTİM"
    assert h[(2, 1)][1] is None and h[(1, 11)][0] == "DİN KÜLTÜRÜ"
    ortak = db.q1("""SELECT o2.ad || ' ' || o2.soyad AS ad FROM ders_atamalari da
                     JOIN dersler d ON d.id = da.ders_id JOIN siniflar s ON s.id = da.sinif_id
                     JOIN ogretmenler o2 ON o2.id = da.ogretmen2_id
                     WHERE s.ad = '9 BT A' AND d.kisa_ad = 'PT'""")
    assert ortak["ad"] == "Bedirhan Kaya"
    assert db.q1("SELECT kisa_ad FROM dersler WHERE ad = 'PROGRAMLAMA TEMELLERİ'")["kisa_ad"] == "PT"

    nobet = db.q1("SELECT * FROM ogretmenler WHERE ad = 'Sabahat'")
    assert (nobet["soyad"], nobet["nobet_gun"], nobet["nobet_yeri"], nobet["sinif_ogretmenligi"]) == \
        ("Beştaş", 1, "ATÖLYE", "11AE")
    assert _hucreler(db, "11 EE")[(1, 1)][:2] == ("ELEKTRİK TESİSAT PROJLERİ", "Sabahat Beştaş")
    assert db.q1("SELECT id FROM ogretmenler WHERE ad = 'Fulya'") is None
    assert program.catismalar(db) == []


def test_eokul_boslukla_birlesmis_hucre():
    """pdfplumber satır sonunu boşluğa çevirse de kod ile öğretmen/sınıf ayrılır."""
    sinif = Tablo("s.pdf", "ızgara", [
        ["Sınıf : 9 BT A Toplam Ders Saati: 10"],
        _periyotlar(5),
        _gun("Pazartesi", 5, [(1, "PT Y.TSY"), (2, "TDE 11 F.TKY"), (3, "S.E.U B.KYA")]),
    ])
    aciklama = Tablo("s.pdf", "açıklama", [
        ["Ders", "Dersin Adı", "Dersin Öğretmeni"],
        ["PT", "PROGRAMLAMA TEMELLERİ", "YUNUS TOSYALIOĞLU"],
        ["TDE 11", "TÜRK DİLİ VE EDEBİYATI", "FIRAT TOKCAN"],
        ["S.E.U", "SEÇMELİ ENDÜSTRİYEL UYGULAMALAR", "BEDİRHAN KAYA"],
    ])
    ogretmen = Tablo("o.pdf", "ızgara", [
        ["Adı Soyadı: SABAHAT BEŞTAŞ"],
        _periyotlar(5),
        _gun("Pazartesi", 5, [(1, "11 EE ETP"), (2, "10EE A 10UYG")]),
    ])
    ozet = Tablo("o.pdf", "özet", [
        ["1", "11 EE", "ETP", "ELEKTRİK TESİSAT PROJLERİ"],
        ["2", "10EE A", "10UYG", "10. SINIF UYGULAMALARI"],
    ])
    tablolar = program_belge.genislet([sinif, aciklama, ogretmen, ozet])
    satirlar = [r for t in tablolar if t.ad.startswith("e-Okul haftalık") for r in t.satirlar[1:]]
    assert ["9 BT A", 1, 1, "PROGRAMLAMA TEMELLERİ", "PT", "Yunus Tosyalıoğlu"] == satirlar[0][:6]
    assert satirlar[1][3:5] == ["TÜRK DİLİ VE EDEBİYATI", "TDE 11"]
    assert satirlar[2][3:6] == ["SEÇMELİ ENDÜSTRİYEL UYGULAMALAR", "S.E.U", "Bedirhan Kaya"]
    assert ["11 EE", 1, 1, "ELEKTRİK TESİSAT PROJLERİ", "ETP"] == satirlar[3][:5]
    assert ["10EE A", 1, 2, "10. SINIF UYGULAMALARI", "10UYG"] == satirlar[4][:5]
