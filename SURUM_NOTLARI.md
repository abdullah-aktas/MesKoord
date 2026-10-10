# MesKoord Sürüm Notları

## 1.4.0

- **e-Okul ders programı PDF'leri doğrudan tanınır:** e-Okul'dan alınan sınıf programı ve öğretmen programı
  PDF'leri "Belgeden Yükle" ile (ya da sürükleyerek) yüklenince sınıflar, öğretmenler, dersler, ortak
  öğretmenler, mekanlar, okul ve işletme günleri ile bütün ders saatleri kilitli olarak yerleşir.
  Öğretmen sayfalarındaki nöbet günü, nöbet yeri ve sınıf öğretmenliği de alınır. "9 T A" ve "9 T B" gibi
  şubeler ayrı sınıf olarak kalır; MSM sınıfları MEM programına alınır.
- **Ders Programı'na Nöbet ve Özel Durumlar sekmeleri:** nöbet günü/yeri ve sınıf öğretmenliği; sınıfların
  okul ve işletme günleri, ikinci öğretmen, mekan ve birleştirme düzenlenir. Görünüm listesinde "Mekan
  (Atölye/Lab.)" programı da vardır.
- **Kurum türü addan seçilir:** Kurum Adı yazılırken Mesleki ve Teknik Anadolu Lisesi, Mesleki Eğitim
  Merkezi, yeni eklenen **Çok Programlı Anadolu Lisesi** ya da MTAL ve MEM birlikte kendiliğinden seçilir;
  elle seçim korunur. Ad ve kod kaydedilince türün kullandığı e-Okul, e-Mesem ve SGK ekranları program içinde
  sırayla açılabilir ("Sistemlerden verileri getir").
- **SGK e-Vizite** bağlantı ekranına eklendi. Giriş algılama hızlandı (sekme girişten hemen sonra "Bağlı" olur).
- **SGK dosyasını programdan çıkmadan yükleme:** e-Bildirge aylık XML'i veya işe giriş/çıkış XML'i üretilince
  "Program İçinde ... Aç ve Yükle" düğmesi ilgili sistemi açar; dosya seçme penceresi üretilen dosyayla gelir.
- **Değişiklik bildirimi:** indirilen veya yüklenen listelerde kaç öğrenci, öğretmen, işletme, yerleştirme ve
  SGK kaydının eklendiği ya da güncellendiği Ana Sayfa'da "Son veri değişikliği" olarak görünür.
- **Ekran donmaz:** belgeden program yükleme ve e-Okul / e-Mesem / SGK'dan inen listelerin aktarımı arka
  planda yapılır; birden çok dosya sırayla işlenir.
- **Paylaş (e-posta / WhatsApp):** her "Kaydedildi" penceresinde ve SGK dosyası penceresinde "Paylaş" düğmesi.
  Alıcılar kayıtlı öğretmen, işletme, usta öğretici, veli ve öğrencilerden seçilir. E-posta posta
  programında ekli açılır ya da programdan doğrudan gönderilir (şifre saklanmaz). WhatsApp'ta dosya panoya
  kopyalanır ve kişinin sohbeti açılır; Ctrl+V ile yapıştırılır.
- **Toplu Gönderim (GENEL menüsü):** her öğretmene kendi ders programı veya görevlendirme yazısı, her işletmeye
  kendi koordinatör bildirimi, aylık ücret ve devlet katkısı bildirimi ya da öğrenci sözleşmeleri kişi başına
  üretilir; e-posta ile tek seferde (her alıcıya ayrı ileti) ya da WhatsApp ile kişi kişi gönderilir.
- **Güncelleme denetimi:** program günde en çok bir kez yeni sürüm olup olmadığına bakar ve "İndir ve Kur"
  önerir; indirilen kurulum dosyası SHA256 ile doğrulanır. Yardım > Güncellemeleri Denetle... ve Açılışta
  Güncellemeleri Denetle seçenekleri. (Güncelleme adresi tanımlanmamış kurulumlarda denetim yapılmaz.)

## 1.3.0

- **Yeni ad ve simge: MesKoord** (Mesleki Koordinasyon). Simge: atölye dişlisi içinde okul ile işletmeyi
  öğrenci üzerinden bağlayan tek çizgili M; renkler gece mavisi ve turkuaz. Program penceresi, menü, açılış
  ekranı, kurulum sihirbazı, kısayollar ve belgeler yeni adı kullanır. Önceki marka görselleri ve programla
  dağıtılan okul logosu kaldırıldı; belgelerde yalnızca okulun Ayarlar'dan yüklediği kendi logosu kullanılır.
  Teknik adlar da değişti: veri klasörü `Belgeler\MesKoord`, program `C:\Program Files\MesKoord\MesKoord.exe`,
  lisans klasörü `C:\ProgramData\MesKoord`, güvenlik duvarı kuralı, Windows açılış kaydı ve ağ tanıtıcısı
  "MesKoord". Güncelleme her şeyi kendiliğinden taşır: eski `Belgeler\KoordMES` klasörü (veritabanı,
  yedekler, şablonlar, çıktılar) ilk açılışta yeni adına geçer, USB/ağ yedek klasörü `MesKoord_Yedekler` olur,
  eski kurulum klasörü ve kısayollar kaldırılır, lisans dosyaları ve pencere ayarları aktarılır. "KoordMES"
  adıyla verilmiş lisanslar geçerliliğini korur; bundan sonra verilen lisanslar "MesKoord" ürün adını taşır ve
  1.3.0 öncesi sürümlerde tanınmaz. Görev çubuğuna sabitlenmiş eski simge yenisiyle değiştirilmelidir.
  Ağ kipinde 1.3.0 sunucusu eski istemcilerin keşif isteğini yanıtlar, ancak eski istemciler sürüm farkı
  nedeniyle zaten bağlanmaz; okuldaki bütün bilgisayarlar birlikte güncellenmelidir.
- **Yeni sol menü ve ekrana sığma:** menü grupları simgeli ve açılır-kapanır; bir grup açılınca ötekiler
  kapanır. Menüde arama (Ctrl+K), dar simge şeridine indirme (Ctrl+B; şeritte grup simgesi açılır liste
  gösterir), son açık ekranı hatırlama. 1280 pikselden dar ekranlarda menü dar başlar. Ekranlardaki uzun düğme
  satırları pencere daraldıkça alt satıra geçer; bütün ekranlar 1024×600 boyutunda yatay kaydırma olmadan
  kullanılabilir.
- **e-Okul / e-Mesem belgelerinden otomatik veri alma:** indirilen her belge (Excel, HTML olan .xls, PDF, Word,
  ZIP) içeriğine bakılarak tanınır. Belgenin üst satırlarındaki ve PDF sayfa başlıklarındaki sınıf, dönem,
  tarih gibi bilgiler satırlara eklenir; sınıf sütunu olmayan sınıf listeleri de doğru sınıfa aktarılır.
- **Toplu Veri Girişi > Belge Yükle:** belgeyi seçin ya da ekrana sürükleyin. "Akıllı Kaydet" belgedeki her
  listeyi türüne göre ilişkili kayıtlarıyla doğrudan kaydeder (öncesinde yedek alınır); isterseniz seçili liste
  kontrol için giriş tablosuna alınır.
- **SGK > Liste Karşılaştırma:** e-Bildirge'den alınan aylık prim hizmet listesi, sigortalı listesi ya da hizmet
  dökümü okul kayıtlarıyla karşılaştırılır. Bildirilmemiş öğrenci, okulda olmayan sigortalı, belge türü, prim
  günü, prime esas kazanç, giriş/çıkış tarihi, ad soyad ve T.C. farkları öneriyle listelenir; okul tarafındaki
  hatalar tek tıkla düzeltilir, Excel'e aktarılır.
- **SGK > Risk ve Öneriler:** geç ya da yaklaşan giriş/çıkış bildirgeleri (tahmini idari para cezası ve
  kendiliğinden bildirim indirimiyle), geçersiz/mükerrer T.C., GSS yaş sınırını aşan "bakmakla yükümlü"
  öğrenciler, tatile denk gelen ayrılışlar, bitişi girilmemiş çıkışlar, verilmemiş aylık prim hizmet belgeleri.
  Öneriler seçilip uygulanabilir; kritik riskler Veri Denetimi'nde görünür; Asistan'da "sgk ceza riskleri".
  Yeni mevzuat parametreleri: idari para cezası katsayıları ve indirim oranı.
- **SGK'ya yüklenecek XML ve Excel dosyaları:**
  - Aylık Prim Hizmet Listesi: e-Bildirge V2 aylık prim ve hizmet belgesi XML'i (asıl / ek / iptal; tahakkuk
    nedeni son güne göre otomatik). Dosya SGK'nın XML şemasıyla program içinde doğrulanır. Aynı bilgiler SGK
    Excel şablonu düzeninde de üretilir.
  - İşe Giriş / İşten Ayrılış: seçili bildirimler için 4A toplu işe giriş ve toplu işten ayrılış XML'leri ile
    SGK Excel şablonu düzeninde dosyalar (ayrılışta bulunduğumuz ve önceki dönem bilgileri hesaplanır).
  - Aylık kapanış dönemin XML ve Excel dosyalarını da hazırlar; Asistan'da "ekim e-bildirge xml",
    "sgk giriş çıkış xml". Veri Denetimi 26 hane olmayan işyeri sicil numarasını bildirir.
  - Yeni "SGK Dosyaları" parametre grubu: okulda alan eğitimi için ayrı işyeri sicili, kanun no, meslek kodu,
    ÇSGB iş kolu, görev kodu, sigorta kolları, işten ayrılış nedeni.
- **Ders programı belgeden:** hazır sınıf/öğretmen/atölye programları, okulun çarşaf programı, ders dağılımı
  matrisleri ve öğretmen müsaitlik çizelgeleri (Excel, PDF, Word) Ders Programı ekranındaki "Belgeden Yükle"
  ile, Veri Aktarımı'yla ya da Toplu Veri Girişi'yle yüklenir. Sınıf, ders, öğretmen, atölye, ders dağılımı ve
  müsaitlik tanımlanır; programdaki saatler kilitli yerleşir, kalanlar otomatik yerleştirilir. Yeni veri türü:
  "Haftalık Ders Programı (Gün-Saat)".
- **Program yerleştirme:**
  - İki öğretmenli (grup / çiftli) dersler: ikinci öğretmen de bağlanır; sınıf mevcudu tek atölyeye sığmazsa
    sınıf iki gruba bölünüp aynı saatte iki atölyeye yerleşir (ya da seçilen 2. atölyeye).
  - Birleştirilmiş dersler (ör. iki şubenin beden eğitimi): aynı saatte yerleşir, öğretmene ve ek ders
    puantajına bir kez yazılır, çakışma sayılmaz.
  - Atölye seçiminde sınıf mevcudu ve atölye kapasitesi; koordinatörlük görev günleri (gerekirse açılır);
    öğretmene günlük azami ders saati.
  - "Ön Denetim": yerleştirmeden önce sığmayan sınıf/öğretmen saatleri, atölye kapasitesi ve sayısı, blok ve
    birleştirme hataları. "Kilitleri Aç" düğmesi.
  - Ek ders puantajı, koordinatörlük görevlendirmesi, öğretmen kartı ve Veri Denetimi ikinci öğretmeni hesaba
    katar.
- **Uyumluluk:** ders dağılımı ve program tablolarına yeni kolonlar eklendi. Sunucu ve bağlanan bütün
  bilgisayarlar 1.3.0'a birlikte yükseltilmelidir; eski veriler kendiliğinden yeni yapıya geçer.

## 1.2.0

- **Kişisel kullanıcı hesapları:** okul personelinin her biri kendi kullanıcı adı ve parolasıyla girer.
  Üç rol vardır: Yönetici (her şey), Personel (günlük veri girişi; kurum bilgileri, mevzuat ayarları ve hesaplar
  hariç) ve Salt okunur (yalnızca görüntüleme ve rapor). Yetkiler veritabanı bağlantısı düzeyinde uygulanır;
  ağdaki bilgisayarlarda da geçerlidir. Hesaplar isteğe bağlıdır (Ayarlar > Kullanıcılar); açılmazsa program
  eskisi gibi çalışır.
- **İşlem günlüğü:** kim, hangi bilgisayardan, ne zaman, hangi kaydı ekledi/değiştirdi/sildi ve neyi neyle
  değiştirdi (Ayarlar > İşlem Günlüğü). Günlük program içinden değiştirilemez; T.C. kimlik no, IBAN, telefon ve
  adres gibi kişisel veriler \*\*\* olarak yazılır; 2 yıl saklanır; Excel'e aktarılabilir.
- **Zamanlanmış otomatik yedek:** 6/12/24 saatte ya da haftada bir; her yedeğin bir kopyası ikinci bir klasöre
  (USB bellek, ağ klasörü) de alınabilir (Ayarlar > Veri ve Yedekleme).
- **Sunucu arka planda:** sunucu bilgisayarında pencere kapatılınca program sistem tepsisinde çalışmayı sürdürür,
  diğer bilgisayarların bağlantısı kesilmez. İsteğe bağlı olarak Windows oturumu açılınca kendiliğinden arka
  planda başlar. Program ikinci kez açılmaz, çalışan pencere öne gelir.
- Dosya menüsünde Parolamı Değiştir ve Kullanıcı Değiştir; durum çubuğunda girişteki kullanıcı.
- Ağdaki bilgisayarlar veritabanı yedeğini sunucuda alır; yedek dosyasını indirmek ve geri yüklemek yöneticiye
  özeldir.
- **Ortaöğretim Kurumları Yönetmeliği (md.82, 88, 89, 134-153):**
  - Koordinatör görevlendirmesi: koordinatör başına aynı işletmede en çok 15 öğrenci (gruplar bölünür),
    önce alan ve atölye/laboratuvar öğretmenleri, alan dışı görevlendirme raporu; döner sermaye işletmeleri
    ve il dışı staj yerleri kapsam dışı.
  - Yeni **Komisyon ve İzleme İşleri** ekranı: yıl sonu başarı ortalamasına göre öğrenci seçimi (md.136;
    öncelikli öğrenciler, ağır disiplin cezası olanlar ayrılır) ve komisyon tutanağı; alan taraması /
    işletme talepleri; mezun ve işyeri anketleri; usta öğretici hizmetiçi eğitim programı.
  - Yeni Word belgeleri: işletme uygunluk tespit tutanağı, koordinatörlerin işletmelere bildirimi,
    koordinatörlük planlama komisyonu kararı, öğrenci seçim tutanağı. Ziyaret formuna beş yönetmelik maddesi
    eklendi (mevcut kurulumlarda "Şablonları Varsayılana Döndür" gerekir).
  - Yeni denetim ve hatırlatmalar: sözleşmenin ders yılının ikinci haftasında imzalanması (md.143), MEM'de
    işyeri değişikliği süresi, MTAL'de 3 gün işletme + 2 gün okul (md.134), usta öğretici başına 16 öğrenci
    ve 10+ öğrencide eğitim birimi (md.135), eğitim planı onayı (md.146), puan çizelgelerinin dönem
    sonundan 5 gün önce teslimi.
  - Yerleştirme sona erdirmede yönetmelikteki fesih nedenleri listesi.
  - Yeni alanlar: kurumda ders yılı ve dönem tarihleri; öğretmende atölye/laboratuvar öğretmeni; öğrencide
    yıl sonu başarı ortalaması (Excel'den de aktarılır), ağır disiplin cezası, öncelikli öğrenci; işletmede
    usta öğretici sayısı, usta belgesi, eğitim birimi, il dışı, döner sermaye, uygunluk ve plan onay tarihi.
  - Asistan'da "Koordinatör müdür yardımcısı görevleri (Yönetmelik)" süreci ve yeni komutlar.
- **Çerçeve öğretim programları:** MEB MTEGM'nin (meslek.meb.gov.tr/cerceve) MTAL ve MEM çerçeve
  programlarındaki 96 alanın 9-12. sınıf haftalık ders çizelgeleri programla gelir.
  - Sınıf kaydedilince ya da seviyesi, programı, alanı veya dalı değişince okul türü, program, seviye, alan ve
    dala göre zorunlu dersler önerilir ve tek tıkla ders dağılımına açılır; saati farklı dersler düzeltilir,
    öğretmen atamaları korunur, gerekli ders tanımları (meslek dersleri alanına bağlı) kendiliğinden eklenir.
  - Ders Programı ekranında yeni "Çerçeve Öğretim Programları" sekmesi: okul/sınıf/program/alan/dal seçerek
    çizelgeyi görme, sınıfa uygulama, alanı ve dallarını tanımlara ekleme, kaynak PDF, Excel.
  - Sınıflar ve Ders Dağılımı ekranlarında "Çerçeve Programdaki Zorunlu Dersleri Aç" (seçili / tüm sınıflar);
    Asistan'da "zorunlu dersleri aç" komutu; yıl başı sürecinde ders dağılımı adımı çizelgeye göre denetlenir.
  - Veri Denetimi: zorunlu dersi eksik ya da haftalık saati farklı sınıflar, çizelgesi belirlenemeyen sınıflar,
    işletme/okul gün sayısının çizelgeye uymaması.
  - Yeni sınıf programı **MTAL-AMP-11** (işletmelerde mesleki eğitime 11. sınıfta başlayan okullar).
- **Uyumluluk:** veritabanına beş tablo ve yeni kolonlar eklendi. Sunucu ve bağlanan bütün bilgisayarlar 1.2.0'a birlikte
  yükseltilmelidir; eski veriler kendiliğinden yeni yapıya geçer.

## 1.1.0

- **Çok kullanıcılı çalışma:** bir bilgisayar sunucu olur, okuldaki diğer bilgisayarlar yerel ağ üzerinden
  bağlanıp aynı verilerle eşzamanlı çalışır. Değişiklikler diğer ekranlara anında yansır; aynı kaydı iki kişi
  değiştirirse program birleştirir ya da sorar. Bağlantı şifreli (TLS) ve parolalıdır; sunucu ağda kendiliğinden
  bulunur, kimliği doğrulama koduyla onaylanır. Lisans yalnızca sunucuya yüklenir.
- **Marka kimliği:** Derik MTAL logosu program simgesi, menü, açılış ekranı, Hakkında, kurulum sihirbazı ve
  tanıtım afişinde; yeni lacivert-altın arayüz.
- **Kurum logosu:** okul kendi logosunu yükler; Word belgelerine ve PDF raporlarına basılır.
- **Ekrana sığma:** pencere ilk açılışta ekran boyutuna göre ayarlanır, sayfalar kaydırılabilir; son konum
  hatırlanır.
- **Güvenli Çıkış:** menüde, Dosya menüsünde ve Ctrl+Q ile; arka plan işlerinin bitmesini bekler, taslakları
  kaydeder, isteğe bağlı yedek alır.
- **Belgeden tam aktarım:** sözleşme/form belgelerindeki öğrenci, veli, işletme, usta öğretici, ücret ve tarih
  bilgileri ilgili kayıtlara birlikte aktarılır; listedeki ek sütunlar (ör. yerleştirme listesindeki öğrenci
  telefonu, işletme adresi) da işlenir.
- Kurulum, Windows güvenlik duvarına yalnızca yerel ağdan bağlantıya izin veren kural ekler.

## 1.0.0

- İlk kurumsal sürüm.
- Kurum lisansı: MEB kurum koduna verilen imzalı lisans dosyası, 30 gün deneme, süre bitiminde 30 gün ek süre.
- Kurulum dosyası (Inno Setup) ve taşınabilir zip; kurulum dosyasının yanındaki lisans kendiliğinden yüklenir.
- Toplu Veri Girişi ekranı (Excel'den/e-Okul'dan yapıştırma, denetim, önizleme, taslak).
- e-Okul / e-Mesem / SGK bağlantı ekranı (kullanıcı kendi şifresiyle girer, indirilen listeler aktarılır).
