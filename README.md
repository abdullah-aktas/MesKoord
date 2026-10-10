# MesKoord — Mesleki Eğitim Koordinasyon ve Yönetim Sistemi

Mesleki ve Teknik Anadolu Liseleri (MTAL) ile Mesleki Eğitim Merkezleri (MEM) için öğretmen ve
idarecilerin mevzuattan doğan iş ve işlemlerini tek bir masaüstü uygulamasında toplayan yazılım.
Tüm veriler okulunuzun bilgisayarında yerel bir SQLite veritabanında tutulur; internet bağlantısı gerekmez.
Okuldaki birden çok bilgisayar aynı verilerle eşzamanlı çalışabilir (bkz. _Birden çok bilgisayarda çalışma_).

Geliştiren: Derik Mesleki ve Teknik Anadolu Lisesi · Lisans: Derik MTAL Döner Sermaye İşletmesi

## Modüller

| Menü                              | Yaptığı iş                                                                                                                                                                                                                                                                                                                                                                                                                  |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Asistan                           | Türkçe komutlarla tüm işlemler, günün yapılacakları, yıl başı / aylık / yıl sonu süreç adımları, veri denetimi, sürükle-bırak dosya aktarımı                                                                                                                                                                                                                                                                                |
| Ana Sayfa                         | Özet sayılar ve yaklaşan yasal süreler (MUHSGK, dekont, SGK giriş/çıkış, devamsızlık, ziyaret)                                                                                                                                                                                                                                                                                                                              |
| Toplu Veri Girişi                 | Excel benzeri tablo: yazarak veya Excel/e-Okul ekranından kopyala-yapıştır ile giriş, başlıkların otomatik eşlenmesi, kaydetmeden önce denetim ve önizleme, otomatik taslak; **Belge Yükle** ile belgedeki listeleri tanıyıp doğrudan kaydetme. "Öğrenci + İşletme Yerleştirme" türü tek satırda öğrenci, sınıf, işletme ve yerleştirmeyi birlikte kaydeder                                                                 |
| Veri Aktarımı                     | Excel, Word, PDF, CSV, HTML, ODS ve JSON dosyalarından 17 veri türünü otomatik tanıyarak aktarma                                                                                                                                                                                                                                                                                                                            |
| e-Okul / e-Mesem / SGK Bağlantısı | Program içinden bu sitelere kendi şifrenizle giriş; indirilen listelerin otomatik aktarımı                                                                                                                                                                                                                                                                                                                                  |
| Tanımlar                          | Öğrenci/çırak, öğretmen, işletme, sınıf, alan/dal, ders, atölye, tatil günleri                                                                                                                                                                                                                                                                                                                                              |
| Ders Programı                     | MEB çerçeve öğretim programlarına göre zorunlu derslerin sınıflara açılması, ders dağılımı, hazır program / dağılım / müsaitlik belgelerinden (Excel, PDF, Word) otomatik tanımlama, otomatik program ve atölye yerleşimi (iki öğretmenli grup dersleri, iki atölyeye bölme, birleştirilmiş sınıflar, atölye kapasitesi, koordinatörlük günü, günlük azami saat), ön denetim, kilitli hücreler, çakışma kontrolü, Excel/PDF |
| Yerleştirme ve Sözleşmeler        | İşletmelerde mesleki eğitim / çıraklık yerleştirmesi, toplu yerleştirme, sözleşme belgeleri                                                                                                                                                                                                                                                                                                                                 |
| Koordinatörlük                    | Ortaöğretim Kurumları Yönetmeliği md.88'e göre otomatik koordinatör görevlendirme (15 öğrenci grubu, alan/atölye önceliği), görevlendirme yazıları, işletmelere bildirim, komisyon kararı, aylık ziyaret planı ve raporları                                                                                                                                                                                                 |
| Komisyon ve İzleme İşleri         | Başarı ortalamasına göre öğrenci seçimi ve tutanağı (md.136), alan taraması / işletme talepleri, mezun ve işyeri anketleri, usta öğretici hizmetiçi eğitimi; işletme uygunluk tutanağı                                                                                                                                                                                                                                      |
| SGK Sigorta İşlemleri             | Aylık prim listesi (prim günü, eksik gün, belge türü, PEK, prim tutarı), bekleyen giriş/çıkış bildirimleri, e-Bildirge listesiyle okul kayıtlarının karşılaştırılması ve düzeltilmesi, idari para cezası ve hatalı bildirim risklerinin tespiti ve öneriler, e-Bildirge V2 aylık prim ve hizmet belgesi ile 4A toplu işe giriş / işten ayrılış XML ve Excel dosyaları                                                       |
| Öğrenci Ücreti ve Devlet Katkısı  | 3308 sayılı Kanun md. 25 ve Geçici md. 12'ye göre asgari ücret ve devlet katkısı hesabı, dekont takibi ve eksik ödeme tespiti                                                                                                                                                                                                                                                                                               |
| Devamsızlık ve Değerlendirme      | Okul ve işletme devamsızlığı, sınır uyarıları, beceri notları                                                                                                                                                                                                                                                                                                                                                               |
| Ek Ders Puantajı                  | Programdan ve koordinatörlükten haftalık ek ders hesabı, elle ek ders kayıtları                                                                                                                                                                                                                                                                                                                                             |
| Evrak                             | Word şablonlarından belge üretimi, evrak kayıt defteri                                                                                                                                                                                                                                                                                                                                                                      |
| Ayarlar                           | Kurum bilgileri ve kurum logosu, mevzuat parametreleri, yedekleme/geri yükleme ve zamanlanmış otomatik yedek (ikinci klasöre kopya), kişisel kullanıcı hesapları ve roller, işlem günlüğü, örnek veri                                                                                                                                                                                                                       |
| Çok Kullanıcılı Çalışma (Ağ)      | Bu bilgisayarı sunucu yapma ya da ağdaki sunucuya bağlama, çevrim içi kullanıcılar; sunucunun sistem tepsisinde çalışması ve Windows açılışında başlaması                                                                                                                                                                                                                                                                   |

## Kurulum ve çalıştırma

`MesKoord_Kurulum_X.Y.Z.exe` dosyasını çalıştırın. Okulunuza verilen lisans dosyası (`.lic`) kurulum
dosyasıyla aynı klasördeyse lisans kendiliğinden yüklenir; değilse programda **Yardım > Lisans Bilgileri**'nden
"Lisans Dosyası Yükle" veya "Lisans Kodunu Yapıştır" kullanın.

**Lisans:** MesKoord kurum bazında lisanslanır; bir lisans, MEB kurum koduyla belirtilen okulun bütün
bilgisayarlarında geçerlidir. Lisans yüklenmeden 30 gün denenebilir. Lisans almak için Yardım > Lisans
Bilgileri > **Lisans Talebi Oluştur**. Lisanslı kurumun adı ve kodu Ayarlar'a kilitlenir ve üretilen belgelerde
bu bilgiler yer alır. Verileriniz lisans süresi bitse de silinmez.

Bilgisayar laboratuvarına sessiz kurulum: `MesKoord_Kurulum_X.Y.Z.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART`

Pencere ilk açılışta ekranınıza sığacak şekilde açılır; sonraki açılışlarda son boyut ve konum hatırlanır.
Programı sol alttaki **Güvenli Çıkış** düğmesiyle (ya da Ctrl+Q) kapatın: arka plandaki işlerin bitmesi
beklenir, taslaklar kaydedilir ve isterseniz çıkmadan önce yedek alınır.

**Belgeler:**

| Belge                                                  | Kimin için                                                                                       |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| [Kullanım Kılavuzu](docs/KULLANIM_KILAVUZU.md)         | Bütün personel; programda **Yardım > Kullanım Kılavuzu** (F1), kurulumda `KULLANIM_KILAVUZU.pdf` |
| [Tanıtım](docs/TANITIM.md)                             | Okul yönetimi, ilçe/il, tanıtım ve satın alma kararı                                             |
| [Devir Teslim Dosyası](docs/DEVIR_TESLIM.md)           | Projeyi devralan bilişim personeli ve yazılımcılar (buradan başlayın)                            |
| [Geliştirici El Kitabı](docs/GELISTIRICI_EL_KITABI.md) | Geliştirme, bakım, sürüm çıkarma ve lisans üretimi                                               |

PDF kopyaları: `python araclar\kilavuz_pdf.py` (çıktı `cikti\Belgeler\`).

## Birden çok bilgisayarda çalışma

1. Bütün bilgisayarlara aynı sürüm MesKoord kurulur.
2. Verilerin duracağı bilgisayarda: **Sistem > Çok Kullanıcılı Çalışma (Ağ)** > _Sunucu olsun_ > sunucu
   parolası belirleyin > _Kaydet ve Programı Yeniden Başlat_. Ekranda bir **doğrulama kodu** görünür.
3. Diğer bilgisayarlarda aynı ekranda: _Ağdaki sunucuya bağlansın_ > _Ağdaki Sunucuları Bul_ (veya sunucunun
   adresini yazın) > adınız ve sunucu parolası > _Bağlantıyı Sına_. Gösterilen kod sunucudakiyle aynıysa
   onaylayın > _Kaydet ve Programı Yeniden Başlat_.
4. Lisansı yalnızca sunucuya yüklemeniz yeterlidir.

Herkes aynı anda çalışabilir; birinin kaydettiği değişiklik diğer bilgisayarların açık ekranlarında hemen
görünür. Aynı kaydı iki kişi aynı anda değiştirirse farklı alanlar birleştirilir, aynı alan için hangisinin
geçerli olacağı sorulur. Bağlantı şifrelidir, veriler okulun ağından dışarı çıkmaz. Sunucu bilgisayarının açık
ve MesKoord'un orada çalışır durumda olması gerekir; sunucuyu kapatmadan önce diğer kullanıcılara haber verin
(program kimlerin bağlı olduğunu gösterir). Sunucuda pencere kapatılınca program sistem tepsisinde çalışmayı
sürdürür; isteğe bağlı olarak Windows oturumu açılınca kendiliğinden başlar.

**Kişisel kullanıcı hesapları (isteğe bağlı):** _Ayarlar > Kullanıcılar_'da açılır. Her personel kendi
kullanıcı adı ve parolasıyla girer; rolüne göre (Yönetici, Personel, Salt okunur) yetkisi olur. Kimin hangi
kaydı ne zaman değiştirdiği _Ayarlar > İşlem Günlüğü_'nde görünür.

## Veri klasörü

Veriler `Belgeler\MesKoord` klasöründe tutulur (farklı bir klasör için `MESKOORD_DATA` ortam
değişkeni tanımlanabilir):

- `meskoord.db`: veritabanı
- `Ciktilar`: üretilen Word, Excel ve PDF dosyaları (`Aylık Kapanış\YYYY-AA Ay` alt klasörleri dahil)
- `Sablonlar`: belge şablonları
- `Yedekler`: elle ve otomatik alınan yedekler (Ayarlar > Veri ve Yedekleme)
- `hata_gunlugu.txt`: beklenmeyen hataların ayrıntısı (destek isterken gönderin)

Program açıkken otomatik yedek alır (varsayılan günde bir); bir USB belleği ya da ağ klasörünü ikinci yedek
klasörü olarak seçmeniz önerilir. Programı denemek için Ayarlar > Veri ve Yedekleme > "Örnek veri yükle"
kullanılabilir (mevcut verileri siler).

## İlk kullanım sırası

1. **Ayarlar > Kurum Bilgileri**: kurum türü (MTAL/MEM), büyükşehir durumu, müdür ve koordinatör müdür
   yardımcısı, SGK işyeri sicil numarası, eğitim öğretim yılı.
2. **Ayarlar > Mevzuat Parametreleri**: asgari ücret, katsayı ve oranları kontrol edin.
3. **Veri Aktarımı**: e-Okul/MEBBİS/e-Mesem'den aldığınız öğrenci, öğretmen ve işletme listelerini
   pencereye sürükleyin. Veri türü ve sütunlar otomatik tanınır; boş şablonlar aynı sayfadan indirilebilir.
4. Sınıfların okul ve işletme günlerini, öğretmenlerin müsait olmadığı saatleri girin.
5. **Ders Programı**: sınıfların alan ve dalına göre çerçeve programdaki zorunlu dersleri açın, öğretmenleri
   atayıp "Otomatik Yerleştir" ile programı ve atölye yerleşimini üretin.
6. **Yerleştirme**: öğrencileri işletmelere yerleştirip sözleşmeleri üretin.
7. **Koordinatörlük**: "Otomatik Görevlendir" ile görevleri dağıtın, ziyaret planını oluşturun.
8. Her ay: Asistan'a _geçen ayın kapanışını hazırla_ yazın (veya Süreçler > Aylık Kapanışı Hazırla).

Bu sıranın tamamı Asistan ekranının **Süreçler** sekmesinde, her adımın durumu veritabanından otomatik
denetlenerek listelenir; adıma çift tıklamak ilgili işlemi çalıştırır.

## Asistan

Uygulama Asistan ekranıyla açılır ve önce günün gündemini gösterir: süresi yaklaşan veya geçen yasal
işlemler, eksik adımlar ve önerilen işlemler. Komutlar serbest Türkçe yazılır; yanıtlardaki bağlantılar
tıklanabilir (dosyayı aç, ekrana git, işlemi çalıştır, kişi/işletme kartını göster). Örnekler:

| Komut                                         | Sonuç                                                                                                                        |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| bugün ne yapmalıyım                           | Uyarılar ve önerilen adımlar                                                                                                 |
| geçen ayın kapanışını hazırla                 | SGK, ücret, dekont, ek ders, devamsızlık listeleri, işletme ve veli yazıları, gelecek ay ziyaret planı ve yedek tek klasörde |
| ekim sgk listesi · sgk bildirimleri           | SGK prim hizmet listesi / bekleyen giriş-çıkış bildirgeleri                                                                  |
| sgk ceza riskleri · sgk listesi karşılaştır   | SGK ceza ve hata riskleri, öneriler / e-Bildirge listesi karşılaştırma ekranı                                                |
| ekim e-bildirge xml · sgk giriş çıkış xml     | e-Bildirge V2 aylık prim ve hizmet belgesi / 4A toplu işe giriş-işten ayrılış XML dosyası ("excel şablonu" yazılırsa Excel)  |
| ücret hesapla · dekontlar · ek ders puantajı  | İlgili dönemin Excel listesi                                                                                                 |
| devamsızlık · veli bildirimleri               | Devamsızlık özeti, sınırı aşanların velilerine yazılar                                                                       |
| koordinatör görevlendir · ziyaret planı kasım | Görev dağıtımı / aylık ziyaret planı                                                                                         |
| programı oluştur · sözleşmeleri hazırla       | Ders programı ve atölye yerleşimi / sözleşmeler                                                                              |
| denetim                                       | Eksik/hatalı T.C., IBAN, sözleşme, SGK süresi, kontenjan, ders yükü, çakışma vb. bulgular                                    |
| yıl başı · aylık süreç · yıl sonu 26.06.2027  | Süreç kontrol listeleri; tarih yazılırsa yerleştirmeleri sona erdirir                                                        |
| yeni eğitim yılı                              | Sınıf atlatma, mezunları pasif yapma, görevleri sıfırlama (önce yedek)                                                       |
| 12-A · Ahmet Yılmaz · işletme adı · T.C.      | Sınıf, öğrenci, öğretmen veya işletme kartı                                                                                  |

Ay adı yazılmazsa geçmiş dönemi ilgilendiren işler (SGK, ücret, dekont) önceki ay için yapılır; yılı
yazılmayan ay içinde bulunulan eğitim yılına göre yorumlanır.

## Veri aktarımı

Desteklenen biçimler: **xlsx, xlsm, xls, ods, csv, txt, docx, pdf, html/htm, json**. Biçim dosya
uzantısına değil içeriğe bakılarak tanınır; örneğin e-Okul'un aslında HTML olan `.xls` dosyaları da
okunur. Bir dosyadaki tüm sayfalar ve tablolar ayrı ayrı bulunur; PDF'te sayfalara bölünmüş tablolar
birleştirilir, Word ve PDF'teki "Etiket: Değer" biçimli formlar tek kayıt olarak okunur. Sözleşme gibi
belgelerde öğrenci, veli, işletme, usta öğretici, ücret ve tarih bilgileri bölümlerine göre ayrılarak ilgili
kayıtlara birlikte aktarılır; bir listedeki ek sütunlar (örneğin yerleştirme listesindeki öğrenci telefonu
veya işletme adresi) da işlenir.

Tanınan veri türleri: öğretmenler, işletmeler, sınıflar, atölyeler, dersler, tatiller, öğrenciler,
ders dağılımı, haftalık ders programı (gün-saat), işletme yerleştirmeleri, koordinatörlük görevleri, devamsızlık (günlük veya e-Okul
toplamı), işletme notları, elle ek ders, ziyaretler, ücret dekontları ve SGK e-Bildirge listeleri.

Aktarım sırasında yapılan ilişkili işlemler:

- Eksik sınıf, alan, dal, işletme, öğrenci ve öğretmen kayıtları oluşturulur; "11. Sınıf / A Şubesi"
  gibi yazımlar "11-A" biçimine getirilir, büyük harfli adlar düzeltilir.
- Öğrenci işletme değiştirmişse eski yerleştirme bir gün öncesinde kapatılır.
- e-Bildirge listesindeki öğrencilerin SGK giriş/çıkış bildirimleri işaretlenir.
- Dekont listesi işlenirken ödenen tutar hesaplanan ücretle karşılaştırılır, eksik ödemeler raporlanır.
- e-Okul toplam devamsızlık listeleri önceki toplu kayıtların yerine geçer.
- Belgenin üst satırlarındaki ve PDF sayfa başlıklarındaki sınıf, dönem, tarih bilgileri satırlara eklenir.
- Ders programı ızgaraları, ders dağılımı matrisleri ve öğretmen müsaitlik çizelgeleri düz listeye çevrilip
  aktarılır; programdaki saatler kilitli yerleşir.
- SGK aylık prim hizmet listeleri SGK > Liste Karşılaştırma ekranına yönlendirilir.
- Aktarımdan sonra sıradaki işler önerilir (yeni yerleştirmelerin sözleşmeleri, SGK listesi,
  koordinatör görevlendirme vb.).

**Önizle** düğmesi aktarımı veritabanına yazmadan dener. Gerçek aktarımdan önce otomatik yedek alınır;
satırlardan biri hatalıysa yalnızca o satır atlanır.

## Mevzuat parametreleri

Asgari ücret, aylık katsayı, ek ders göstergeleri, SGK oranları, belge türleri, ücret oranları,
koordinatörlük ve ek ders sınırları gibi tüm sayısal değerler **Ayarlar > Mevzuat Parametreleri**
sayfasında, dayanaklarıyla birlikte listelenir ve değiştirilebilir. Değerler mevzuat değiştikçe
(özellikle her yıl başında ve Ocak/Temmuz katsayı dönemlerinde) güncellenmelidir.

**Önemli:** 3308 sayılı Kanun Geçici 12. madde kapsamındaki ücret oranı ve devlet katkısı
uygulamasının 2026-2027 eğitim öğretim yılında da sürüp sürmediğini kontrol edin. Uygulama sona
ermişse "3308 Geçici 12. madde (devlet katkısı) uygulanıyor" parametresini kapatın; hesaplar md. 25'e
göre yapılır.

## Belge şablonları

Sözleşme, görevlendirme yazısı, ziyaret formu, devamsızlık bildirimi gibi belgeler `Sablonlar`
klasöründeki Word dosyalarından üretilir. Şablonlar ilk açılışta otomatik oluşturulur; Word ile
açıp kurumunuzun veya MEB'in resmî formatına göre düzenleyebilirsiniz. Metindeki `{{alan_adi}}`
biçimindeki yer tutucular belge üretilirken doldurulur. Bir şablonu silerseniz program onu
varsayılan haliyle yeniden oluşturur.

Okulunuzun logosunu **Ayarlar > Kurum Bilgileri > Kurum logosu**'ndan yükleyin; belgelerin ve PDF
raporların başına basılır. Kendi düzenlediğiniz şablonlarda logonun yerini `{{kurum_logosu}}` yazan ayrı bir
paragrafla belirleyebilirsiniz.

## Sınırlamalar

- Program e-Bildirge, MEBBİS, e-Okul veya KBS'ye doğrudan veri göndermez. SGK bildirimleri için
  e-Bildirge'ye kullanıcının yükleyeceği XML ve SGK şablonu düzeninde Excel dosyaları; ek ders puantajı için
  Excel listeleri hazırlanır.
- Taranmış (resim) PDF'lerden metin okunamaz; bu tür belgeler için Excel veya metin içeren PDF kullanın.
- Hesaplamalar yardımcı niteliktedir; resmî işlem öncesinde güncel mevzuata göre kontrol edilmelidir.
