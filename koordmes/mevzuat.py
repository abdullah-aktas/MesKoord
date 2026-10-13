"""Mevzuattan gelen, zamanla değişebilen parametreler.

Her parametre Ayarlar ekranından güncellenebilir. Varsayılanlar 2026 yılı
itibarıyla geçerli değerlerdir; yeni yıl/dönemde güncellenmelidir.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Parametre:
    anahtar: str
    etiket: str
    varsayilan: str
    tip: str  # "float" | "int" | "bool" | "str"
    grup: str
    kaynak: str = ""


PARAMETRELER: list[Parametre] = [
    # --- Asgari ücret ---
    Parametre("asgari_ucret_brut", "Aylık brüt asgari ücret (TL)", "33030.00", "float",
              "Asgari Ücret", "Asgari Ücret Tespit Komisyonu Kararı (01.01.2026-31.12.2026)"),
    Parametre("asgari_ucret_net", "Aylık net asgari ücret (TL)", "28075.50", "float",
              "Asgari Ücret", "Asgari Ücret Tespit Komisyonu Kararı (01.01.2026-31.12.2026)"),

    # --- Öğrenci ücreti (3308 md.25 ve Geçici md.12) ---
    Parametre("gecici12_aktif", "3308 Geçici 12. madde (devlet katkısı) uygulanıyor", "1", "bool",
              "Öğrenci Ücreti ve Devlet Katkısı",
              "3308 Geçici md.12; 5063 sayılı CK ile 2021-2022'den itibaren 5 öğretim yılı uzatıldı. "
              "2026-2027 için yeni uzatma kararını kontrol ediniz."),
    Parametre("ucret_orani_gecici12", "Geçici 12 kapsamında en az ücret oranı (net asgari ücrete)", "0.30",
              "float", "Öğrenci Ücreti ve Devlet Katkısı", "3308 Geçici md.12/1"),
    Parametre("ucret_orani_kalfa_mem12", "Kalfalık yeterliği kazanan MEM 12. sınıf en az ücret oranı", "0.50",
              "float", "Öğrenci Ücreti ve Devlet Katkısı", "3308 md.25/1, Geçici md.12/1"),
    Parametre("ucret_orani_20_ustu", "Md.25: 20 ve üzeri personelli işletmede en az ücret oranı", "0.30",
              "float", "Öğrenci Ücreti ve Devlet Katkısı", "3308 md.25/1 (Geçici 12 uygulanmadığında)"),
    Parametre("ucret_orani_20_alti", "Md.25: 20'den az personelli işletmede en az ücret oranı", "0.15",
              "float", "Öğrenci Ücreti ve Devlet Katkısı", "3308 md.25/1 (Geçici 12 uygulanmadığında)"),
    Parametre("ucret_orani_cirak", "Aday çırak / çırak en az ücret oranı", "0.30",
              "float", "Öğrenci Ücreti ve Devlet Katkısı", "3308 md.25/1"),
    Parametre("personel_esigi", "Personel sayısı eşiği", "20", "int",
              "Öğrenci Ücreti ve Devlet Katkısı", "3308 md.25/1, Geçici md.12/1"),
    Parametre("dk_pay_20_alti", "Devlet katkısı payı - 20'den az personel (MEM dışı)", "0.666667", "float",
              "Öğrenci Ücreti ve Devlet Katkısı", "3308 Geçici md.12/1 (üçte iki)"),
    Parametre("dk_pay_20_ustu", "Devlet katkısı payı - 20 ve üzeri personel (MEM dışı)", "0.333333", "float",
              "Öğrenci Ücreti ve Devlet Katkısı", "3308 Geçici md.12/1 (üçte bir)"),
    Parametre("dk_pay_mem", "Devlet katkısı payı - MEM programı", "1.0", "float",
              "Öğrenci Ücreti ve Devlet Katkısı", "3308 Geçici md.12/1 (tamamı)"),
    Parametre("ucret_gune_orantili", "Ücret/katkı prim gün sayısına (30 gün esası) orantılansın", "1", "bool",
              "Öğrenci Ücreti ve Devlet Katkısı", "Usul ve Esaslar: eksik günlerde orantılı hesap"),
    Parametre("dekont_teslim_son_gun", "İşletmenin ücret dekontunu okula teslim son günü (ayın)", "10", "int",
              "Öğrenci Ücreti ve Devlet Katkısı", "Devlet Katkısı Usul ve Esasları - güncel yazıyı kontrol ediniz"),
    Parametre("dk_sisteme_giris_son_gun", "Devlet katkısının e-Okul/e-Mesem'e giriş son günü (ayın)", "15",
              "int", "Öğrenci Ücreti ve Devlet Katkısı",
              "Devlet Katkısı Usul ve Esasları - güncel yazıyı kontrol ediniz"),

    # --- SGK (5510) ---
    Parametre("sgk_pek_orani", "Prime esas kazanç = brüt asgari ücret x bu oran", "0.50", "float",
              "SGK Sigorta", "5510 md.80/1-k, 3308 md.25"),
    Parametre("sgk_prim_yukumlu", "Prim oranı - bakmakla yükümlü olunan (kısa vadeli)", "0.01", "float",
              "SGK Sigorta", "5510 md.81"),
    Parametre("sgk_prim_yukumlu_degil", "Prim oranı - bakmakla yükümlü olunmayan (%1 KVSK + %5 GSS)", "0.06",
              "float", "SGK Sigorta", "5510 md.81, md.5/b"),
    Parametre("belge_isletme_yukumlu", "Belge türü: işletme/staj - bakmakla yükümlü olunan", "7", "str",
              "SGK Sigorta", "SGK e-Bildirge belge türleri"),
    Parametre("belge_isletme_degil", "Belge türü: işletme/staj - bakmakla yükümlü olunmayan", "42", "str",
              "SGK Sigorta", "SGK e-Bildirge belge türleri"),
    Parametre("belge_okul_yukumlu", "Belge türü: okulda alan/tamamlayıcı eğitim - yükümlü olunan", "49", "str",
              "SGK Sigorta", "SGK e-Bildirge belge türleri"),
    Parametre("belge_okul_degil", "Belge türü: okulda alan/tamamlayıcı eğitim - yükümlü olunmayan", "50", "str",
              "SGK Sigorta", "SGK e-Bildirge belge türleri"),
    Parametre("sgk_cikis_bildirim_gun", "İşten ayrılış bildirgesi süresi (gün)", "10", "int",
              "SGK Sigorta", "5510 md.9"),
    Parametre("sgk_giris_once_gun", "İşe giriş bildirgesi en geç kaç gün önce verilmeli", "1", "int",
              "SGK Sigorta", "5510 md.8 (sigortalılık başlamadan önce)"),
    Parametre("muhsgk_son_gun", "Muhtasar ve prim hizmet beyannamesi son günü (izleyen ayın)", "26", "int",
              "SGK Sigorta", "5510 md.86, SGK uygulaması"),
    Parametre("ozursuz_eksik_gun", "Özürsüz devamsızlık SGK'da eksik gün (kod 15) bildirilsin", "1", "bool",
              "SGK Sigorta", "SGK genelgeleri: eksik gün nedenleri 01,03,04,05,10,11,12,15,21"),
    Parametre("gss_yukumlu_yas", "Lise öğrencisi bakmakla yükümlü sayılma yaş sınırı", "20", "int",
              "SGK Sigorta", "5510 md.3/10-b (lise ve dengi öğrenimde 20 yaş)"),
    Parametre("sgk_ipc_giris_kat", "İPC: işe giriş bildirgesi geç/verilmedi (asgari ücret x)", "1", "float",
              "SGK İdari Para Cezaları", "5510 md.102/1-a"),
    Parametre("sgk_ipc_giris_tespit_kat", "İPC: işe giriş bildirgesi denetimde tespit (asgari ücret x)", "2",
              "float", "SGK İdari Para Cezaları", "5510 md.102/1-a (kayıt dışı tespiti)"),
    Parametre("sgk_ipc_cikis_kat", "İPC: işten ayrılış bildirgesi geç (asgari ücret x)", "0.1", "float",
              "SGK İdari Para Cezaları", "5510 md.102/1-j"),
    Parametre("sgk_ipc_aphb_kisi", "İPC: APHB asıl belge geç - sigortalı başına (asgari ücret x)", "0.2",
              "float", "SGK İdari Para Cezaları", "5510 md.102/1-c"),
    Parametre("sgk_ipc_aphb_azami", "İPC: APHB cezası üst sınırı (asgari ücret x)", "2", "float",
              "SGK İdari Para Cezaları", "5510 md.102/1-c"),
    Parametre("sgk_ipc_ek_belge_kisi", "İPC: ek APHB - sigortalı başına (asgari ücret x)", "0.125", "float",
              "SGK İdari Para Cezaları", "5510 md.102/1-c"),
    Parametre("sgk_ipc_indirim", "Kendiliğinden 30 gün içinde + peşin ödeme: cezanın bu oranı ödenir", "0.1875",
              "float", "SGK İdari Para Cezaları", "5510 md.102/2 (1/4), 5326 md.17/6 peşin ödeme (1/4 indirim)"),
    Parametre("sgk_isyeri_sicil_okul", "Okulda alan eğitimi (belge 49/50) için ayrı SGK işyeri sicil no (26 hane, "
              "boşsa kurum sicili)", "", "str", "SGK Dosyaları", "İl/ilçe MEM ve SGK yazıları"),
    Parametre("sgk_kanun_no", "e-Bildirge kanun numarası (teşvik yoksa 00000)", "00000", "str",
              "SGK Dosyaları", "e-Bildirge V2 XML şeması (KANUN)"),
    Parametre("sgk_meslek_kodu", "Meslek kodu (ISCO-08)", "9901.02", "str", "SGK Dosyaları",
              "SGK meslek kodları: 9901.02 Stajyer (Öğrenci)"),
    Parametre("sgk_csgb_iskolu", "ÇSGB iş kolu kodu", "10", "str", "SGK Dosyaları",
              "6356 s. Kanun iş kolları: 10 Ticaret, büro, eğitim ve güzel sanatlar"),
    Parametre("sgk_gorev_kodu", "İşe giriş görev kodu", "05", "str", "SGK Dosyaları",
              "SGK işe giriş görev kodları: 05 Çırak, stajyer öğrenciler"),
    Parametre("sgk_sigorta_kolu_isletme", "Sigorta kolu: işletmede mesleki eğitim / staj", "19", "str",
              "SGK Dosyaları", "SGK sigortalılık kodları: 19 Stajyer"),
    Parametre("sgk_sigorta_kolu_okul", "Sigorta kolu: okulda alan / tamamlayıcı eğitim", "37", "str",
              "SGK Dosyaları", "SGK sigortalılık kodları: 37 Tamamlayıcı ya da alan eğitimi gören öğrenciler"),
    Parametre("sgk_sigorta_kolu_mem", "Sigorta kolu: MESEM çırak / aday çırak / kalfa", "7", "str",
              "SGK Dosyaları", "SGK sigortalılık kodları: 7 Çırak"),
    Parametre("sgk_cikis_nedeni", "İşten ayrılış nedeni kodu", "22", "str", "SGK Dosyaları",
              "SGK işten çıkış nedenleri: 22 Diğer nedenler"),

    # --- Ek ders ---
    Parametre("aylik_katsayi", "Memur aylık katsayısı", "1.575512", "float",
              "Ek Ders", "HMB 5 Sıra No'lu Genelge (01.07.2026-31.12.2026)"),
    Parametre("ek_ders_gosterge_gunduz", "Ek ders göstergesi - gündüz", "140", "int", "Ek Ders", "657 md.176"),
    Parametre("ek_ders_gosterge_gece", "Ek ders göstergesi - gece", "150", "int", "Ek Ders", "657 md.176"),
    Parametre("aylik_karsilik_ogretmen", "Aylık karşılığı ders - meslek/genel bilgi öğretmeni", "15", "int",
              "Ek Ders", "Ders ve Ek Ders Saatlerine İlişkin Karar md.5/1-c"),
    Parametre("aylik_karsilik_atolye", "Aylık karşılığı ders - atölye ve laboratuvar öğretmeni", "20", "int",
              "Ek Ders", "Ders ve Ek Ders Saatlerine İlişkin Karar md.5/1-ç"),
    Parametre("aylik_karsilik_yonetici", "Aylık karşılığı ders - müdür ve müdür yardımcıları", "6", "int",
              "Ek Ders", "Ders ve Ek Ders Saatlerine İlişkin Karar md.5/1-a"),
    Parametre("max_ek_ders_ogretmen", "Haftalık azami ek ders - meslek/genel bilgi öğretmeni", "15", "int",
              "Ek Ders", "Ders ve Ek Ders Saatlerine İlişkin Karar md.6/1-b"),
    Parametre("max_ek_ders_atolye", "Haftalık azami ek ders - atölye ve laboratuvar öğretmeni", "24", "int",
              "Ek Ders", "Ders ve Ek Ders Saatlerine İlişkin Karar md.6/1-c"),
    Parametre("max_ek_ders_yonetici", "Haftalık azami ek ders - yönetici", "6", "int",
              "Ek Ders", "Ders ve Ek Ders Saatlerine İlişkin Karar md.6/1-a"),

    # --- Koordinatörlük ---
    Parametre("koord_max_mem_buyuksehir", "İşletmelerde meslek eğitimi haftalık azami - MEM, büyükşehir", "24",
              "int", "Koordinatörlük", "Ders ve Ek Ders Saatlerine İlişkin Karar md.15/2-a-1"),
    Parametre("koord_max_mem_diger", "İşletmelerde meslek eğitimi haftalık azami - MEM, diğer", "18", "int",
              "Koordinatörlük", "Ders ve Ek Ders Saatlerine İlişkin Karar md.15/2-a-2"),
    Parametre("koord_max_okul_buyuksehir", "İşletmelerde meslek eğitimi haftalık azami - diğer okul, büyükşehir",
              "20", "int", "Koordinatörlük", "Ders ve Ek Ders Saatlerine İlişkin Karar md.15/2-b-1"),
    Parametre("koord_max_okul_diger", "İşletmelerde meslek eğitimi haftalık azami - diğer okul, diğer", "16",
              "int", "Koordinatörlük", "Ders ve Ek Ders Saatlerine İlişkin Karar md.15/2-b-2"),
    Parametre("koord_gunluk_max", "Bir öğretmene aynı gün verilebilecek azami işletme ek dersi", "8", "int",
              "Koordinatörlük", "Ortaöğretim Kurumları Yönetmeliği (koordinatör görevlendirme)"),
    Parametre("koord_isletme_taban_saat", "Komisyon ölçütü: işletme başına taban saat", "1", "int",
              "Koordinatörlük", "Komisyon kararı (uzaklık, öğrenci sayısı vb.)"),
    Parametre("koord_ogrenci_ek_saat", "Komisyon ölçütü: her N öğrenci için +1 saat (N)", "5", "int",
              "Koordinatörlük", "Komisyon kararı"),
    Parametre("koord_form_teslim_gun", "Günlük rehberlik görev formunun teslim süresi (gün); aylık formlar ay "
              "sonundan itibaren", "5", "int", "Koordinatörlük", "Okul uygulaması"),
    Parametre("koord_uzak_km", "Komisyon ölçütü: bu km'den uzak işletmeye +1 saat", "10", "float",
              "Koordinatörlük", "Komisyon kararı"),
    Parametre("koord_grup_ogrenci", "Aynı işletme ve alanda bir koordinatör öğretmene düşen azami öğrenci", "15",
              "int", "Koordinatörlük", "Ortaöğretim Kurumları Yönetmeliği md.88/2-f"),

    # --- İşletmelerde mesleki eğitim (Ortaöğretim Kurumları Yönetmeliği) ---
    Parametre("usta_ogretici_ogrenci", "Bir usta öğretici / eğitici personele düşen azami öğrenci", "16", "int",
              "İşletmelerde Mesleki Eğitim", "Ortaöğretim Kurumları Yönetmeliği md.135"),
    Parametre("egitim_birimi_esigi", "Eğitim birimi kurulması gereken öğrenci sayısı (ve üzeri)", "10", "int",
              "İşletmelerde Mesleki Eğitim", "Ortaöğretim Kurumları Yönetmeliği md.142/a-3, md.148"),
    Parametre("sozlesme_sure_gun", "Sözleşmelerin ders yılı başından itibaren imzalanma süresi (gün)", "14", "int",
              "İşletmelerde Mesleki Eğitim", "Ortaöğretim Kurumları Yönetmeliği md.143/1 (2. hafta sonu)"),
    Parametre("mem_sozlesme_sure_gun", "MEM: ilk yerleştirmede sözleşme imzalanma süresi (gün)", "60", "int",
              "İşletmelerde Mesleki Eğitim", "Ortaöğretim Kurumları Yönetmeliği md.143 (iki ay)"),
    Parametre("isyeri_degisikligi_gun", "MEM: işyeri değişikliğinde yeni sözleşme süresi (gün)", "14", "int",
              "İşletmelerde Mesleki Eğitim", "Ortaöğretim Kurumları Yönetmeliği md.143 (iki hafta)"),
    Parametre("plan_onay_gun", "Usta öğretici eğitim planının onaya sunulma süresi (gün)", "7", "int",
              "İşletmelerde Mesleki Eğitim", "Ortaöğretim Kurumları Yönetmeliği md.146 (ilk hafta)"),
    Parametre("puan_cizelgesi_gun", "Puan çizelgelerinin dönem sonundan önce teslim süresi (gün)", "5", "int",
              "İşletmelerde Mesleki Eğitim", "Ortaöğretim Kurumları Yönetmeliği md.89/1-g, md.144/1-g"),

    # --- Ders programı ---
    Parametre("gunluk_ders_saati", "Günlük ders saati sayısı", "8", "int", "Ders Programı", "Okul çizelgesi"),
    Parametre("program_sure_limit_sn", "Otomatik yerleştirme süre sınırı (saniye)", "20", "int",
              "Ders Programı", ""),
    Parametre("program_koord_gunu_bos", "Koordinatörlük görev günlerini okulda derse kapat", "1", "bool",
              "Ders Programı", "Ders ve Ek Ders Saatlerine İlişkin Karar md.15 (işletmede geçen gün)"),
    Parametre("program_ogretmen_gunluk_azami", "Bir öğretmene günde en çok ders saati (0: sınırsız)", "0", "int",
              "Ders Programı", "Okul uygulaması"),
    Parametre("program_kapasite_denetimi", "Atölye seçiminde kapasiteyi (öğrenci/grup mevcudu) gözet", "1",
              "bool", "Ders Programı", "Atölye/laboratuvar kapasitesi"),
    Parametre("program_ogle_arasi", "Öğle arası kaçıncı ders saatinden sonra (0: yok); blok dersler öğle arasında "
              "bölünmez", "0", "int", "Ders Programı", "Okul çizelgesi"),
    Parametre("program_ogretmen_ayni_gun", "Bir öğretmenin aynı sınıftaki farklı dersleri aynı güne gelmesin "
              "(rehberlik hariç)", "0", "bool", "Ders Programı", "Okul uygulaması"),
    Parametre("ekders_karsilik_once_gun", "Maaş/ek ders işaretinde aylık karşılığı haftanın ilk gün ve saatlerinden "
              "doldur (kapalıysa ek dersler günlere dengeli dağılır)", "1", "bool", "Ek Ders", "Okul uygulaması"),
    Parametre("ekders_sinif_rehberlik_saat", "Sınıf rehber öğretmenliği haftalık ders görevi (saat)", "2", "int",
              "Ek Ders", "Ders ve Ek Ders Saatlerine İlişkin Karar (sınıf rehber öğretmenliği) - güncel metni "
              "kontrol ediniz"),
    Parametre("ekders_kulup_saat", "Öğrenci kulübü / sosyal etkinlik danışmanlığı haftalık ders görevi (saat)", "2",
              "int", "Ek Ders", "Ders ve Ek Ders Saatlerine İlişkin Karar (ÖSKH / kulüp) - güncel metni kontrol "
              "ediniz"),
    Parametre("ekders_rehberlik_kulup_birlikte", "Sınıf rehberliği olan öğretmenin kulüp saati de sayılsın", "0",
              "bool", "Ek Ders", "Okul uygulaması (kapalıysa yalnız sınıf rehberliği sayılır)"),
    Parametre("ekders_sef_saat", "Alan / atölye / laboratuvar şefliği haftalık ders görevi (saat; şeflere "
              "rehberlik ve kulüp saati yazılmaz)", "0", "int", "Ek Ders",
              "Ders ve Ek Ders Saatlerine İlişkin Karar - okulunuzdaki uygulamayı giriniz"),
    Parametre("ekders_gorevler_puantaja", "Rehberlik, kulüp ve şeflik saatleri aylık ek ders puantajına eklensin",
              "1", "bool", "Ek Ders", "Okul uygulaması"),
    Parametre("program_ogle_tum_bloklar", "Öğle arasında bütün blok dersler bölünmesin (kapalıysa yalnız 'öğle "
              "arasında bölünmez' işaretli dersler)", "1", "bool", "Ders Programı", "Okul uygulaması"),
    Parametre("program_genel_kapali", "Okul geneli ders konmayacak saatler (ör. 5-7,5-8: cuma 7. ve 8. saat)", "",
              "str", "Ders Programı", "Okul çizelgesi"),
    Parametre("program_yarim_gun_saat", "İkili öğretimde sabahçı yarının son saati (0: günlük saatin yarısı)", "0",
              "int", "Ders Programı", "Okul çizelgesi"),
    Parametre("program_ogretmen_yarim_gun", "Öğretmen aynı gün hem sabah hem öğleden sonra derse girmesin", "0",
              "bool", "Ders Programı", "Okul uygulaması"),
    Parametre("program_ogretmen_bos_gun", "Öğretmenlere mümkünse en az bir boş gün kalsın", "0", "bool",
              "Ders Programı", "Okul uygulaması"),
    Parametre("program_ogretmen_bosluk", "Öğretmen boş (pencere) saatlerini en aza indir", "1", "bool",
              "Ders Programı", "Okul uygulaması"),
    Parametre("program_sinif_bosluk", "Sınıf programında boş saat kalmasın", "1", "bool", "Ders Programı",
              "Okul uygulaması"),
    Parametre("program_iyilestirme_tur", "Yerleştirme sonrası iyileştirme turu (0: yapılmaz)", "2", "int",
              "Ders Programı", "Süre sınırı içinde taşıma/yer değiştirme ile boşluklar azaltılır"),
    Parametre("program_kural_gevset", "Kurallara uyularak yerleşmeyen ders kalırsa 'aynı güne gelmesin' ve "
              "koordinatörlük günü kuralları gevşetilsin (kapalıyken parametrelere kesin uyulur; gevşetmenin "
              "sonucu yalnızca öneri olarak bildirilir)", "0", "bool", "Ders Programı", "Okul uygulaması"),
    Parametre("program_beden_muzik_ilk_son", "Beden eğitimi ve müzik dersleri mümkünse haftanın ilk ve son okul "
              "gününe konsun", "1", "bool", "Ders Programı",
              "Ortaöğretim Kurumları Yönetmeliği md.12 (bayrak törenleri)"),
    Parametre("program_teori_sabah", "Teorik dersler öğleden önce, uygulamalı (atölye/lab.) dersler öğleden sonra "
              "olsun (mümkünse)", "1", "bool", "Ders Programı", "Ortaöğretim Kurumları Yönetmeliği md.12"),
    Parametre("program_ders_saatleri", "Ders saatlerinin başlangıç-bitişleri (ör. 08:30-09:10, 09:20-10:00, ...)",
              "", "str", "Ders Programı", "Okul çizelgesi; ders yılı içindeki sınavlarda dersi olan öğretmene o "
              "saatte sınav görevi verilmez"),
    # [EK-PARAMETRE: DERS PROGRAMI]

    # --- Devamsızlık ---
    Parametre("devamsizlik_ozursuz_sinir", "Özürsüz devamsızlık sınırı (gün)", "10", "float",
              "Devamsızlık", "Ortaöğretim Kurumları Yönetmeliği md.36"),
    Parametre("devamsizlik_toplam_sinir", "Toplam devamsızlık sınırı (gün)", "30", "float",
              "Devamsızlık", "Ortaöğretim Kurumları Yönetmeliği md.36"),
    Parametre("devamsizlik_veli_esik", "Veliye yazılı bildirim eşiği - özürsüz (gün)", "5", "float",
              "Devamsızlık", "Okul uygulaması - yönetmeliği kontrol ediniz"),
    # [EK-PARAMETRE: SGK]
    # [EK-PARAMETRE: MES]
]

PARAMETRE_SOZLUK = {p.anahtar: p for p in PARAMETRELER}

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma"]
AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos",
         "Eylül", "Ekim", "Kasım", "Aralık"]

YERLESTIRME_TURLERI = ["İşletmede Mesleki Eğitim", "Staj", "Çıraklık", "Tamamlayıcı Eğitim",
                       "Okulda Alan Eğitimi"]
OKUL_ICI_TURLER = {"Okulda Alan Eğitimi"}

OGRENCI_STATULERI = ["Öğrenci", "Aday Çırak", "Çırak", "Kalfa (MEM 12)", "Açık Lise"]
MEM_STATULERI = {"Aday Çırak", "Çırak", "Kalfa (MEM 12)"}
# MTAL-AMP-11: işletmelerde mesleki eğitime 11. sınıfta başlayan okullar için Anadolu Meslek Programı
# MAOL: Mesleki Açık Öğretim Lisesi (yüz yüze eğitim / işletmede mesleki eğitim alan açık lise öğrencileri)
PROGRAMLAR = ["MTAL-AMP", "MTAL-AMP-11", "MTAL-ATP", "MEM", "MAOL"]


def mem_mi(program: str | None = None, statu: str | None = None, tur: str | None = None) -> bool:
    """Mesleki Eğitim Merkezi (MESEM) öğrencisi: aday çırak, çırak, kalfa ya da çıraklık yerleştirmesi."""
    return (program or "").upper().startswith("MEM") or (statu or "") in MEM_STATULERI or tur == "Çıraklık"


def maol_mi(program: str | None = None, statu: str | None = None) -> bool:
    return (program or "").upper().startswith("MAOL") or (statu or "") == "Açık Lise"
# İşletmeye yerleştirilmesi gereken sınıflar (siniflar tablosu "s" takma adıyla)
ISLETMEYE_GIDEN_SINIF_SQL = ("((s.seviye >= 12 AND COALESCE(s.program, '') NOT LIKE 'MAOL%') OR s.program LIKE 'MEM%' "
                             "OR (s.program = 'MTAL-AMP-11' AND s.seviye >= 11))")


def isletmeye_giden_sinif(program: str | None, seviye: int | None) -> bool:
    """MAOL sınıfları 'yerleştirilmemiş' denetimine girmez; işletmeye giden MAOL öğrencisinin kaydı tek tek açılır."""
    program, seviye = (program or ""), (seviye or 0)
    return (seviye >= 12 and not maol_mi(program)) or mem_mi(program) or (program == "MTAL-AMP-11" and seviye >= 11)
UNVANLAR = ["Öğretmen", "Atölye/Lab. Öğretmeni", "Müdür Yardımcısı", "Koordinatör Müdür Yardımcısı",
            "Müdür Başyardımcısı", "Müdür"]
YONETICI_UNVANLARI = {"Müdür Yardımcısı", "Koordinatör Müdür Yardımcısı", "Müdür Başyardımcısı", "Müdür"}
# Ortaöğretim Kurumları Yönetmeliği md.12: ders programında tercihi dikkate alınacak öğretmenler
ONCELIKLI_TERCIHLER = ["Engelli", "Engelli yakını (bakmakla yükümlü)", "36 ayını doldurmamış çocuğu var",
                       "Süt izni kullanıyor"]
TEDRISAT_TURLERI = ["Tam gün", "Sabahçı", "Öğlenci"]

EKSIK_GUN_NEDENLERI = {
    "01": "İstirahat",
    "03": "Disiplin cezası",
    "04": "Gözaltına alınma",
    "05": "Tutukluluk",
    "10": "Genel hayatı etkileyen olaylar",
    "11": "Doğal afet",
    "12": "Birden fazla neden",
    "15": "Devamsızlık",
    "21": "Diğer ücretsiz izin",
}
FESIH_NEDENLERI = ["Mezuniyet", "Nakil", "Karşılıklı fesih", "3308 sayılı Kanun md.22 hâlleri",
                   "Devamsızlık nedeniyle başarısızlık", "Sağlık durumu", "İşyerine uyum sağlayamama",
                   "İşyeri değişikliği", "Okul değişikliği", "Kayıt silme", "Diğer"]
FESIH_SAYILAN = {"Karşılıklı fesih", "3308 sayılı Kanun md.22 hâlleri", "Devamsızlık nedeniyle başarısızlık",
                 "Sağlık durumu", "İşyerine uyum sağlayamama", "Fesih"}
ANKET_TURLERI = ["Mezun", "İşyeri"]
CALISMA_DURUMLARI = ["Alanında çalışıyor", "Alan dışında çalışıyor", "Yükseköğretime devam ediyor",
                     "Çalışmıyor", "Askerlik", "Bilinmiyor"]

DEVAMSIZLIK_TURLERI = ["Özürsüz", "Özürlü", "Raporlu", "İzinli"]
DEVAMSIZLIK_SGK_KODU = {"Özürsüz": "15", "Raporlu": "01", "Özürlü": "21", "İzinli": "21"}
