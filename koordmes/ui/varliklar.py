"""Tanım tablolarının ekran tanımları."""
from __future__ import annotations

from ..mevzuat import (ANKET_TURLERI, CALISMA_DURUMLARI, DEVAMSIZLIK_TURLERI, FESIH_NEDENLERI, OGRENCI_STATULERI,
                       PROGRAMLAR, UNVANLAR, YERLESTIRME_TURLERI)
from .crud import Alan, Varlik
from .sayfa_cerceve import ders_dagilimi_eylemi, sinif_kaydedildi, siniflar_eylemi

ALAN_FK = "SELECT id, ad FROM alanlar ORDER BY ad"
DAL_FK = "SELECT d.id, COALESCE(a.ad, '') || ' / ' || d.ad FROM dallar d LEFT JOIN alanlar a ON a.id = d.alan_id ORDER BY 2"
SINIF_FK = "SELECT id, ad FROM siniflar ORDER BY seviye, ad"
OGRETMEN_FK = "SELECT id, ad || ' ' || soyad FROM ogretmenler ORDER BY ad, soyad"
OGRENCI_FK = ("SELECT o.id, o.ad || ' ' || o.soyad || ' (' || COALESCE(s.ad, '') || ' / ' || COALESCE(o.okul_no, '') "
              "|| ')' FROM ogrenciler o LEFT JOIN siniflar s ON s.id = o.sinif_id ORDER BY s.ad, o.okul_no, o.ad")
ISLETME_FK = "SELECT id, ad FROM isletmeler ORDER BY ad"
ATOLYE_FK = "SELECT id, ad FROM atolyeler ORDER BY ad"
DERS_FK = "SELECT id, ad FROM dersler ORDER BY ad"
GUN_SECENEK = ["1", "2", "3", "4", "5"]

ALANLAR = Varlik("alanlar", "Alanlar", [
    Alan("ad", "Alan Adı", zorunlu=True), Alan("kod", "Kod")], "ad")

DALLAR = Varlik("dallar", "Dallar", [
    Alan("alan_id", "Alan", "fk", True, fk_sql=ALAN_FK), Alan("ad", "Dal Adı", zorunlu=True)], "alan_id, ad",
    filtre_alani="alan_id")

SINIFLAR = Varlik("siniflar", "Sınıflar / Şubeler", [
    Alan("ad", "Sınıf/Şube", zorunlu=True, ipucu="ör. 12-A"),
    Alan("seviye", "Seviye", "int", varsayilan=9),
    Alan("program", "Program", "choice", True, PROGRAMLAR, varsayilan="MTAL-AMP",
         ipucu="MTAL-AMP-11: işletmelerde mesleki eğitime 11. sınıfta başlayan okullar için Anadolu Meslek "
               "Programı. Program, seviye, alan ve dal çerçeve öğretim programındaki zorunlu dersleri belirler."),
    Alan("alan_id", "Alan", "fk", fk_sql=ALAN_FK),
    Alan("dal_id", "Dal", "fk", fk_sql=DAL_FK,
         ipucu="10. sınıftan itibaren ders çizelgesi dala göre değişir."),
    Alan("okul_gunleri", "Okul Günleri", "days", varsayilan="1,2,3,4,5",
         ipucu="Sınıfın okulda ders gördüğü günler. Ders programı yalnızca bu günlere yerleşir."),
    Alan("isletme_gunleri", "İşletme Günleri", "days", varsayilan="",
         ipucu="İşletmede mesleki eğitim günleri. Koordinatör ziyaretleri bu günlere planlanır."),
    Alan("rehber_ogretmen_id", "Rehber Öğretmen", "fk", fk_sql=OGRETMEN_FK),
], "seviye, ad", aciklama="12. sınıf MTAL öğrencileri için genellikle 2 gün okul + 3 gün işletme; MEM için 1 gün "
                          "okul + 4 gün işletme günleri tanımlayınız. Sınıf kaydedilince seviye, program, alan ve "
                          "dala göre çerçeve öğretim programındaki zorunlu dersler ders dağılımına açılmak üzere "
                          "önerilir.",
    eylemler=[("Çerçeve Programdaki Zorunlu Dersleri Aç", siniflar_eylemi)], form_sonrasi=sinif_kaydedildi)

OGRETMENLER = Varlik("ogretmenler", "Öğretmenler ve Yöneticiler", [
    Alan("tc", "T.C. Kimlik No", "tc", listede=False),
    Alan("ad", "Adı", zorunlu=True), Alan("soyad", "Soyadı", zorunlu=True),
    Alan("brans", "Branş"), Alan("alan_id", "Alan", "fk", fk_sql=ALAN_FK),
    Alan("unvan", "Unvan", "choice", True, UNVANLAR, varsayilan="Öğretmen"),
    Alan("telefon", "Telefon"), Alan("eposta", "E-posta", listede=False),
    Alan("aylik_karsilik", "Aylık Karşılığı Ders (boş=unvana göre)", "text", listede=False,
         ipucu="Boş bırakılırsa mevzuat parametresindeki değer kullanılır."),
    Alan("max_ek_ders", "Azami Haftalık Ek Ders (boş=unvana göre)", "text", listede=False),
    Alan("koordinator", "Koordinatör olabilir", "bool", varsayilan=1),
    Alan("atolye_lab", "Alanı atölye ve laboratuvar öğretmenliği", "bool", listede=False,
         ipucu="Koordinatörlük görevinde önceliklidir (Ortaöğretim Kurumları Yönetmeliği md.88/2-e). "
               "Unvanı 'Atölye/Lab. Öğretmeni' olanlar ayrıca işaretlenmese de öncelikli sayılır."),
    Alan("musait_olmayan", "Müsait Olmadığı Saatler", "slots", listede=False),
    Alan("aktif", "Aktif", "bool", varsayilan=1),
], "ad, soyad", filtre_alani="alan_id")

OGRENCILER = Varlik("ogrenciler", "Öğrenciler / Çıraklar", [
    Alan("okul_no", "Okul No"), Alan("tc", "T.C. Kimlik No", "tc"),
    Alan("ad", "Adı", zorunlu=True), Alan("soyad", "Soyadı", zorunlu=True),
    Alan("sinif_id", "Sınıf", "fk", fk_sql=SINIF_FK),
    Alan("statu", "Statü", "choice", True, OGRENCI_STATULERI, varsayilan="Öğrenci"),
    Alan("bakmakla_yukumlu", "Bakmakla yükümlü olunan (GSS anne/babadan)", "bool", varsayilan=1,
         ipucu="İşaretli: SGK prim %1 (belge 7/49). İşaretsiz: %6 (belge 42/50)."),
    Alan("dogum_tarihi", "Doğum Tarihi", "date", listede=False),
    Alan("cinsiyet", "Cinsiyet", "choice", secenekler=["E", "K"], listede=False),
    Alan("telefon", "Telefon", listede=False), Alan("veli_ad", "Veli Adı Soyadı"),
    Alan("veli_tel", "Veli Telefon"), Alan("iban", "IBAN", listede=False),
    Alan("adres", "Adres", "multiline", listede=False),
    Alan("basari_ortalamasi", "Alt Sınıf Yılsonu Başarı Ortalaması", "float", listede=False,
         ipucu="İşletmeye gönderilecek öğrencilerin sıralamasında kullanılır (md.136)."),
    Alan("agir_disiplin", "Kısa süreli uzaklaştırmadan ağır disiplin cezası var", "bool", listede=False,
         ipucu="İşaretli öğrenci, işletme seçim sıralamasında 'koşulu sağlamıyor' olarak ayrılır (md.136)."),
    Alan("oncelikli", "Sıralamaya girmeden gönderilir (şehit/gazi çocuğu, koruma/eğitim tedbiri)", "bool",
         listede=False, ipucu="Şehit ve gazi çocukları, 5395 sayılı Kanun kapsamında koruma/eğitim tedbiri kararı "
                              "ve 2828 sayılı Kanun kapsamındaki öğrenciler (md.136). Kişisel veridir; "
                              "işlem günlüğünde gizlenir."),
    Alan("aktif", "Aktif", "bool", varsayilan=1),
], "sinif_id, okul_no, ad", filtre_alani="sinif_id")

ISLETMELER = Varlik("isletmeler", "İşletmeler", [
    Alan("ad", "İşletme Adı", zorunlu=True), Alan("alan_id", "Alan", "fk", fk_sql=ALAN_FK),
    Alan("yetkili", "Yetkili"), Alan("telefon", "Telefon"), Alan("eposta", "E-posta", listede=False),
    Alan("vergi_no", "Vergi No", listede=False), Alan("sgk_sicil", "SGK Sicil No", listede=False),
    Alan("personel_sayisi", "Personel Sayısı", "int",
         ipucu="20'den az / 20 ve üzeri ayrımı ücret ve devlet katkısı oranını belirler."),
    Alan("kamu_kurumu", "Kamu kurumu (devlet katkısı ödenmez)", "bool"),
    Alan("guzergah", "Güzergah/Bölge"), Alan("mesafe_km", "Okula Uzaklık (km)", "float"),
    Alan("ilce", "İlçe", listede=False), Alan("adres", "Adres", "multiline", listede=False),
    Alan("usta_ogretici", "Usta Öğretici / Eğitici Personel"), Alan("usta_ogretici_tel", "Usta Öğretici Tel", listede=False),
    Alan("usta_ogretici_sayisi", "Usta Öğretici / Eğitici Personel Sayısı", "int", listede=False, varsayilan=1,
         ipucu="Bir usta öğretici/eğitici personele en çok 16 öğrenci düşer (md.135)."),
    Alan("usta_belgesi", "Usta öğreticinin ustalık / iş pedagojisi belgesi var", "bool", listede=False,
         ipucu="Usta öğreticilerin ustalık belgesi veya iş pedagojisi eğitimi almış olması gerekir (md.152)."),
    Alan("egitim_birimi", "Eğitim birimi kurulmuş", "bool", listede=False,
         ipucu="10 ve daha fazla öğrenciye eğitim yaptıran işletme eğitim birimi kurar (md.142/a-3, md.148)."),
    Alan("il_disi", "İl sınırları dışında", "bool", listede=False,
         ipucu="İl dışında staj yapan öğrenciler için koordinatör öğretmen görevlendirilmez (md.88/2-g); "
               "işletmede konaklama ve yemek imkânı aranır (md.142/a-6)."),
    Alan("doner_sermaye", "Okulun döner sermaye işletmesi", "bool", listede=False,
         ipucu="Okul döner sermaye işletmesindeki öğrenciler için koordinatör öğretmen görevlendirilmez (md.88/8)."),
    Alan("uygunluk_tarihi", "Uygunluk Tespit Tarihi (komisyon)", "date",
         ipucu="İşletme belirleme komisyonunun uygunluk tespit tarihi (md.140-142). Tutanağı İşletmeler "
               "ekranındaki 'Uygunluk Tespit Tutanağı' düğmesiyle üretebilirsiniz."),
    Alan("plan_onay_tarihi", "Eğitim Planı Onay Tarihi", "date", listede=False,
         ipucu="Usta öğreticinin hazırladığı eğitim planı ilk hafta içinde okul müdürünün onayına sunulur (md.146)."),
    Alan("iban", "IBAN", listede=False), Alan("kontenjan", "Kontenjan", "int"),
    Alan("aktif", "Aktif", "bool", varsayilan=1),
], "ad", filtre_alani="alan_id")

ATOLYELER = Varlik("atolyeler", "Atölye / Laboratuvarlar", [
    Alan("ad", "Adı", zorunlu=True), Alan("tur", "Tür", "choice", True, ["Atölye", "Laboratuvar", "Derslik"], varsayilan="Atölye"),
    Alan("alan_id", "Alan", "fk", fk_sql=ALAN_FK), Alan("kapasite", "Kapasite", "int", varsayilan=16),
], "ad")

DERSLER = Varlik("dersler", "Dersler", [
    Alan("ad", "Ders Adı", zorunlu=True), Alan("kisa_ad", "Kısa Ad"),
    Alan("alan_id", "Alan", "fk", fk_sql=ALAN_FK),
    Alan("tur", "Tür", "choice", True, ["Kültür", "Meslek", "Atölye"], varsayilan="Meslek"),
    Alan("atolye_gerekli", "Atölye/Lab. gerektirir", "bool"),
    Alan("blok", "Blok (ardışık saat)", "int", varsayilan=2, ipucu="Ör. 4: ders 4'er saatlik bloklar halinde yerleşir."),
], "ad", filtre_alani="alan_id")

DERS_ATAMALARI = Varlik("ders_atamalari", "Ders Dağılımı", [
    Alan("sinif_id", "Sınıf", "fk", True, fk_sql=SINIF_FK),
    Alan("ders_id", "Ders", "fk", True, fk_sql=DERS_FK),
    Alan("ogretmen_id", "Öğretmen", "fk", fk_sql=OGRETMEN_FK),
    Alan("haftalik_saat", "Haftalık Saat", "int", True, varsayilan=2),
    Alan("blok", "Blok (boş=dersin bloğu)", "int", ipucu="0 bırakılırsa dersin blok değeri kullanılır."),
    Alan("atolye_id", "Sabit Atölye/Lab.", "fk", fk_sql=ATOLYE_FK,
         ipucu="Boş bırakılırsa atölye gerektiren derslere alanın atölyelerinden uygun olan seçilir."),
    Alan("ogretmen2_id", "2. Öğretmen (grup/çiftli)", "fk", fk_sql=OGRETMEN_FK,
         ipucu="İki öğretmenle aynı saatte yapılan ders (grup dersi). Sınıf mevcudu tek atölyeye sığmıyorsa "
               "sınıf iki gruba bölünüp ikinci atölyeye de yerleştirilir."),
    Alan("atolye2_id", "2. Atölye/Lab. (grup)", "fk", fk_sql=ATOLYE_FK, listede=False,
         ipucu="Grup dersinde ikinci grubun sabit atölyesi. Boşsa gerektiğinde alanın atölyelerinden seçilir."),
    Alan("birlestirme", "Birleştirme Grubu",
         ipucu="Aynı grup adını alan dersler (ör. BED-9) farklı sınıflarda aynı saatte birlikte yapılır; "
               "öğretmene bir kez yazılır."),
], "sinif_id, ders_id", filtre_alani="sinif_id",
    eylemler=[("Çerçeve Programdaki Zorunlu Dersleri Aç (seçili sınıf / tüm sınıflar)", ders_dagilimi_eylemi)])

YERLESTIRMELER = Varlik("yerlestirmeler", "Öğrenci - İşletme Yerleştirmeleri", [
    Alan("ogrenci_id", "Öğrenci", "fk", True, fk_sql=OGRENCI_FK),
    Alan("isletme_id", "İşletme", "fk", fk_sql=ISLETME_FK),
    Alan("tur", "Tür", "choice", True, YERLESTIRME_TURLERI, varsayilan="İşletmede Mesleki Eğitim"),
    Alan("baslangic", "Başlangıç", "date", True), Alan("bitis", "Bitiş", "date"),
    Alan("sozlesme_no", "Sözleşme No"), Alan("sozlesme_tarihi", "Sözleşme Tarihi", "date", listede=False),
    Alan("ucret", "Sözleşme Aylık Ücreti (0=yasal alt sınır)", "float", listede=False),
    Alan("sigorta_giris_bildirildi", "SGK Giriş Bildirildi", "bool"),
    Alan("sigorta_giris_bildirim_tarihi", "Giriş Bildirim Tarihi", "date", listede=False),
    Alan("sigorta_cikis_bildirildi", "SGK Çıkış Bildirildi", "bool"),
    Alan("sigorta_cikis_bildirim_tarihi", "Çıkış Bildirim Tarihi", "date", listede=False),
    Alan("durum", "Durum", "choice", True, ["Aktif", "Sona Erdi", "Feshedildi"], varsayilan="Aktif"),
    Alan("fesih_nedeni", "Fesih/Ayrılış Nedeni", "choice", secenekler=FESIH_NEDENLERI, listede=False,
         ipucu="Sözleşme yalnızca 3308 md.22 hâllerinde, devamsızlık nedeniyle başarısızlıkta veya sağlık "
               "nedeniyle tek taraflı; diğer durumlarda karşılıklı feshedilir (md.143)."),
], "baslangic DESC, id DESC", filtre_alani="isletme_id",
    aciklama="Okulda alan eğitimi gören öğrenciler için işletme seçmeden 'Okulda Alan Eğitimi' türünde kayıt "
             "açınız (SGK belge türü 49/50). Ara tatil, yarıyıl ve yaz tatillerinde bitiş tarihi girilmez.")

KOORDINATOR_GOREVLERI = Varlik("koordinator_gorevleri", "Koordinatörlük Görevleri", [
    Alan("ogretmen_id", "Öğretmen", "fk", True, fk_sql=OGRETMEN_FK),
    Alan("isletme_id", "İşletme", "fk", True, fk_sql=ISLETME_FK),
    Alan("gun", "Gün (1=Pzt ... 5=Cuma)", "choice", True, GUN_SECENEK, varsayilan="1"),
    Alan("haftalik_saat", "Haftalık Saat", "int", True, varsayilan=1),
    Alan("baslangic", "Başlangıç", "date"), Alan("bitis", "Bitiş", "date"),
], "ogretmen_id, gun", filtre_alani="ogretmen_id")

ZIYARETLER = Varlik("ziyaretler", "İşletme Ziyaretleri", [
    Alan("tarih", "Tarih", "date", True),
    Alan("ogretmen_id", "Öğretmen", "fk", fk_sql=OGRETMEN_FK),
    Alan("isletme_id", "İşletme", "fk", True, fk_sql=ISLETME_FK),
    Alan("durum", "Durum", "choice", True, ["Planlandı", "Yapıldı", "Yapılmadı"], varsayilan="Planlandı"),
    Alan("tespitler", "Tespitler", "multiline"), Alan("oneriler", "Öneriler", "multiline"),
], "tarih, ogretmen_id", filtre_alani="ogretmen_id")

DEVAMSIZLIK = Varlik("devamsizlik", "Devamsızlık Kayıtları", [
    Alan("ogrenci_id", "Öğrenci", "fk", True, fk_sql=OGRENCI_FK),
    Alan("tarih", "Tarih", "date", True),
    Alan("tur", "Tür", "choice", True, DEVAMSIZLIK_TURLERI, varsayilan="Özürsüz"),
    Alan("yer", "Yer", "choice", True, ["İşletme", "Okul"], varsayilan="İşletme"),
    Alan("gun", "Gün (0,5 = yarım gün)", "float", True, varsayilan=1),
    Alan("sgk_eksik", "SGK'ya eksik gün bildirilsin", "bool", varsayilan=1,
         ipucu="Özürsüz devamsızlıkta ücret ödenmeyen günler için eksik gün (kod 15) bildirilir."),
    Alan("aciklama", "Açıklama"),
], "tarih DESC", filtre_alani="ogrenci_id")

BECERI_NOTLARI = Varlik("beceri_notlari", "İşletmede Mesleki Eğitim Notları", [
    Alan("ogrenci_id", "Öğrenci", "fk", True, fk_sql=OGRENCI_FK),
    Alan("donem", "Dönem", "choice", True, ["1", "2"], varsayilan="1"),
    Alan("isletme_notu", "İşletme (Usta Öğretici) Notu", "float"),
    Alan("koordinator_notu", "Koordinatör Öğretmen Notu", "float"),
    Alan("tarih", "Tarih", "date"), Alan("aciklama", "Açıklama"),
], "ogrenci_id, donem", filtre_alani="ogrenci_id")

EK_DERS_KAYITLARI = Varlik("ek_ders_kayitlari", "Elle Ek Ders Kayıtları", [
    Alan("ogretmen_id", "Öğretmen", "fk", True, fk_sql=OGRETMEN_FK),
    Alan("tarih", "Tarih", "date", True),
    Alan("tur", "Tür", "choice", True, ["Gündüz", "Gece", "Nöbet", "Planlama/Bakım-Onarım", "DYK", "Belleticilik",
                                        "Sınav Görevi", "Diğer"], varsayilan="Gündüz"),
    Alan("saat", "Saat", "float", True, varsayilan=1), Alan("aciklama", "Açıklama"),
], "tarih DESC", filtre_alani="ogretmen_id",
    aciklama="Ders programı ve koordinatörlük görevleri puantaja otomatik eklenir. Buraya yalnızca programda "
             "olmayan ek dersleri (nöbet, planlama/bakım-onarım, gece, DYK vb.) giriniz.")

TATILLER = Varlik("tatiller", "Tatil Günleri", [
    Alan("ad", "Açıklama", zorunlu=True), Alan("baslangic", "Başlangıç", "date", True),
    Alan("bitis", "Bitiş", "date", True)], "baslangic",
    aciklama="Resmî tatiller ve ara tatiller. Ziyaret planı ve ek ders puantajında dikkate alınır.")

EVRAK = Varlik("evrak", "Evrak Kayıt Defteri", [
    Alan("tarih", "Tarih", "date", True), Alan("sayi", "Sayı"), Alan("konu", "Konu", zorunlu=True),
    Alan("tur", "Tür", "choice", True, ["Gelen", "Giden"], varsayilan="Giden"), Alan("dosya", "Dosya Yolu"),
], "tarih DESC")

ISLETME_TALEPLERI = Varlik("isletme_talepleri", "Alan Taraması ve İşletme Talepleri", [
    Alan("tarih", "Tarih", "date", True),
    Alan("isletme_id", "İşletme", "fk", True, fk_sql=ISLETME_FK),
    Alan("alan_id", "Alan", "fk", fk_sql=ALAN_FK), Alan("dal", "Dal"),
    Alan("talep_sayisi", "Talep Edilen Öğrenci", "int", True, varsayilan=1),
    Alan("ogretmen_id", "Taramayı Yapan Öğretmen", "fk", fk_sql=OGRETMEN_FK),
    Alan("aciklama", "Açıklama", "multiline"),
], "tarih DESC", filtre_alani="alan_id",
    aciklama="Koordinatör öğretmenlerin ziyaretlerde tespit ettiği işletme öğrenci talepleri ve alan taraması "
             "sonuçları (Ortaöğretim Kurumları Yönetmeliği md.89/2, md.82/2-ğ). Henüz listede olmayan işletmeyi "
             "önce İşletmeler ekranından 'Aktif' işaretini kaldırarak ekleyebilirsiniz.")

ANKETLER = Varlik("anketler", "Mezun ve İşyeri Anketleri", [
    Alan("tarih", "Tarih", "date", True),
    Alan("tur", "Anket Türü", "choice", True, ANKET_TURLERI, varsayilan="Mezun"),
    Alan("ogrenci_id", "Mezun / Öğrenci", "fk", fk_sql=OGRENCI_FK),
    Alan("isletme_id", "İşletme", "fk", fk_sql=ISLETME_FK),
    Alan("ogretmen_id", "Uygulayan Öğretmen", "fk", fk_sql=OGRETMEN_FK),
    Alan("calisma_durumu", "Mezunun Durumu", "choice", secenekler=CALISMA_DURUMLARI),
    Alan("memnuniyet", "Memnuniyet (1-5)", "choice", secenekler=["1", "2", "3", "4", "5"]),
    Alan("e_ortama_aktarildi", "Elektronik ortama aktarıldı", "bool"),
    Alan("gorusler", "Görüş ve Öneriler", "multiline"),
], "tarih DESC", filtre_alani="ogretmen_id",
    aciklama="Mezunların izlenmesi ve işyeri anketleri (Ortaöğretim Kurumları Yönetmeliği md.89/1-ğ, md.82/2-g). "
             "Sonuçları 'Değerlendirme (Excel)' ile özetleyebilirsiniz.")

HIZMETICI_EGITIMLER = Varlik("hizmetici_egitimler", "Usta Öğretici Hizmetiçi Eğitim Programı", [
    Alan("tarih", "Tarih", "date", True), Alan("konu", "Konu", zorunlu=True),
    Alan("isletme_id", "İşletme (boş = ortak)", "fk", fk_sql=ISLETME_FK),
    Alan("katilimcilar", "Katılımcılar (usta öğretici / eğitici personel)", "multiline"),
    Alan("egitici", "Eğitimi Veren"), Alan("yer", "Yer"),
    Alan("sure_saat", "Süre (saat)", "float", varsayilan=2),
    Alan("durum", "Durum", "choice", True, ["Planlandı", "Yapıldı", "İptal"], varsayilan="Planlandı"),
], "tarih", aciklama="Usta öğretici ve eğitici personele yönelik hizmetiçi eğitim planı (Ortaöğretim Kurumları "
                     "Yönetmeliği md.82/2-b, md.144/1-ç). 'Program (Excel)' ile okul müdürüne sunulacak listeyi "
                     "hazırlayabilirsiniz.")
