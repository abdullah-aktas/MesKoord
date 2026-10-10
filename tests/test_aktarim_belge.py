"""Belgelerden (sözleşme, form, zengin listeler) bütün verinin aktarılması."""
from koordmes.services import aktarim, belgeler, okuyucu
from koordmes.services.okuyucu import Tablo


def _form(tablolar):
    return next(t for t in tablolar if t.form)


def test_form_bolumleri_ve_bilesik_etiketler(tmp_path):
    yol = tmp_path / "form.txt"
    yol.write_text("A) ÖĞRENCİ BİLGİLERİ\n"
                   "Adı Soyadı: Ayşe Kaya\nOkul No / Sınıf: 512 / 11-B\nAdres / Telefon: Merkez Mah. / 0532 000 11 22\n"
                   "Veli / Vasi: Hasan Kaya (0533 444 55 66)\n"
                   "B) İŞLETME BİLGİLERİ\n"
                   "İşletme Adı: Dicle Bilişim\nAdres: Cumhuriyet Cad. No:5\nYetkili / Telefon: Ali Demir / 0482 111 22 33\n"
                   "Başlangıç - Bitiş: 01.10.2026 - 18.06.2027\n", encoding="utf-8")
    t = _form(okuyucu.oku(yol))
    alan = dict(zip(*t.satirlar))
    assert alan["Öğrenci Okul No"] == "512" and alan["Öğrenci Sınıf"] == "11-B"
    assert alan["Öğrenci Adres"] == "Merkez Mah." and alan["Öğrenci Telefon"] == "0532 000 11 22"
    assert alan["Veli"] == "Hasan Kaya" and alan["Veli Telefon"] == "0533 444 55 66"
    assert alan["İşletme Adres"] == "Cumhuriyet Cad. No:5" and alan["İşletme Telefon"] == "0482 111 22 33"
    assert alan["İşletme Yetkili"] == "Ali Demir"
    assert alan["Başlangıç"] == "01.10.2026" and alan["Bitiş"] == "18.06.2027"
    tah = aktarim.tahmin_et(t)[0]
    assert tah.anahtar == "yerlestirmeler"
    ad = {k: t.satirlar[0][j] for k, j in tah.eslesme.items()}
    assert ad["isletme_adres"] == "İşletme Adres" and ad["isletme_tel"] == "İşletme Telefon"


def test_uretilen_sozlesme_bos_veritabanina_eksiksiz_aktarilir(ornek_db, tmp_path):
    from koordmes.db import Database
    y = ornek_db.q1("""SELECT y.id FROM yerlestirmeler y JOIN isletmeler i ON i.id = y.isletme_id
                       JOIN ogrenciler o ON o.id = y.ogrenci_id
                       WHERE i.vergi_no != '' AND o.tc != '' ORDER BY y.id LIMIT 1""")["id"]
    ornek_db.execute("""UPDATE ogrenciler SET dogum_tarihi = '2009-03-04', adres = 'Yenişehir Mah. 3. Sok.',
                        telefon = '0532 111 22 33', veli_ad = 'Hasan Yıldız', veli_tel = '0533 222 33 44',
                        iban = 'TR330006100519786457841326'
                        WHERE id = (SELECT ogrenci_id FROM yerlestirmeler WHERE id = ?)""", (y,))
    ornek_db.execute("""UPDATE isletmeler SET sgk_sicil = '2.4711.01.01.1234567.047.01.23', adres = 'Sanayi Sitesi 4',
                        telefon = '0482 444 55 66', yetkili = 'Mehmet Demir', usta_ogretici = 'Ali Usta',
                        personel_sayisi = 12 WHERE id = (SELECT isletme_id FROM yerlestirmeler WHERE id = ?)""", (y,))
    ornek_db.execute("UPDATE yerlestirmeler SET sozlesme_no = 'S-2026/17', sozlesme_tarihi = '2026-09-10', "
                     "bitis = '2027-06-18' WHERE id = ?", (y,))
    kaynak = ornek_db.q1("""SELECT o.*, s.ad AS sinif_ad, y.baslangic, y.bitis, y.sozlesme_no, y.sozlesme_tarihi,
                                   i.ad AS isletme, i.vergi_no, i.sgk_sicil, i.adres AS i_adres, i.telefon AS i_tel,
                                   i.yetkili, i.usta_ogretici, i.personel_sayisi
                            FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                            JOIN isletmeler i ON i.id = y.isletme_id LEFT JOIN siniflar s ON s.id = o.sinif_id
                            WHERE y.id = ?""", (y,))
    belge = belgeler.uret(ornek_db, "isletme_sozlesmesi", y, klasor=tmp_path)

    tablolar = okuyucu.oku(belge)
    form = _form(tablolar)
    tah = aktarim.tahmin_et(form)[0]
    assert tah.anahtar == "yerlestirmeler"

    bos = Database(tmp_path / "bos.db")
    try:
        s = aktarim.aktar(bos, form, tah.anahtar, tah.bas, tah.eslesme)
        assert s.eklenen == 1, (s.hatalar, s.satirlar)
        assert {e.anahtar for e in s.ek} == {"ogrenciler", "isletmeler"}
        assert "ayrıca" in s.ozet_metni()
        o = bos.q1("SELECT o.*, s.ad AS sinif_ad FROM ogrenciler o LEFT JOIN siniflar s ON s.id = o.sinif_id")
        for alan in ("tc", "okul_no", "ad", "soyad", "dogum_tarihi", "adres", "telefon", "veli_ad", "veli_tel", "iban",
                     "sinif_ad"):
            assert o[alan] == kaynak[alan], alan
        i = bos.q1("SELECT * FROM isletmeler")
        for alan, k in (("ad", "isletme"), ("vergi_no", "vergi_no"), ("sgk_sicil", "sgk_sicil"), ("adres", "i_adres"),
                        ("telefon", "i_tel"), ("yetkili", "yetkili"), ("usta_ogretici", "usta_ogretici"),
                        ("personel_sayisi", "personel_sayisi")):
            assert i[alan] == kaynak[k], alan
        r = bos.q1("SELECT * FROM yerlestirmeler")
        for alan in ("baslangic", "bitis", "sozlesme_no", "sozlesme_tarihi"):
            assert r[alan] == kaynak[alan], alan
        assert r["ucret"] and r["ucret"] > 0
    finally:
        bos.close()


def test_yerlestirme_listesindeki_ogrenci_ve_isletme_ayrintilari_da_aktarilir(db):
    bas = ["Okul No", "Adı Soyadı", "Sınıfı", "Veli Telefonu", "Doğum Tarihi", "İşletme Adı", "Vergi No",
           "SGK Sicil No", "Vergi Dairesi", "Usta Öğretici Tel", "Başlama Tarihi"]
    veri = [["601", "Zeynep Ak", "12-A", "0533 000 00 01", "05.05.2008", "Mardin Oto", "1112223334",
             "2.4511.01.01.7654321.047.01.11", "Mardin", "0532 999 88 77", "15.09.2026"]]
    s = aktarim.aktar(db, Tablo("liste.xlsx", "Sayfa1", [bas] + veri), "yerlestirmeler")
    assert s.eklenen == 1
    o = db.q1("SELECT veli_tel, dogum_tarihi FROM ogrenciler WHERE okul_no = '601'")
    assert o["veli_tel"] == "0533 000 00 01" and o["dogum_tarihi"] == "2008-05-05"
    i = db.q1("SELECT sgk_sicil, usta_ogretici_tel FROM isletmeler WHERE vergi_no = '1112223334'")
    assert i["sgk_sicil"].startswith("2.4511") and i["usta_ogretici_tel"] == "0532 999 88 77"
    assert db.q1("SELECT COUNT(*) FROM isletmeler")[0] == 1


def test_deneme_aktarimi_ek_bilgileri_de_geri_alir(db):
    bas = ["Okul No", "Adı Soyadı", "Veli Telefonu", "İşletme Adı", "Başlama Tarihi"]
    t = Tablo("l", "l", [bas, ["701", "Ali Can", "0533 1", "Ece Ltd", "15.09.2026"]])
    s = aktarim.aktar(db, t, "yerlestirmeler", deneme=True)
    assert s.eklenen == 1 and s.ek and s.ek[0].anahtar == "ogrenciler"
    assert db.q1("SELECT COUNT(*) FROM ogrenciler")[0] == 0


def test_toplu_giriste_ek_gecis_yapilmaz(db):
    bas = ["Okul No", "Adı Soyadı", "Veli Telefonu", "İşletme Adı", "Başlama Tarihi"]
    t = Tablo("l", "l", [bas, ["702", "Ali Can", "0533 1", "Ece Ltd", "15.09.2026"]])
    s = aktarim.aktar(db, t, "yerlestirmeler", ek=False)
    assert s.eklenen == 1 and not s.ek
