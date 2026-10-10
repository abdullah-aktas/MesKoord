# MesKoord — Mesleki Eğitim Koordinasyon ve Yönetim Sistemi

**Tanıtım ve Bilgilendirme Belgesi** · Sürüm 1.3.0

> Mesleki ve Teknik Anadolu Liseleri (MTAL) ile Mesleki Eğitim Merkezleri (MEM) için; ders programından
> koordinatörlüğe, SGK bildirgesinden öğrenci ücretine kadar mevzuattan doğan iş ve işlemleri tek
> programda toplayan, okulun kendi bilgisayarında çalışan masaüstü yazılımı.

Geliştiren: **Derik Mesleki ve Teknik Anadolu Lisesi** · Yayıncı ve lisans veren: **Derik MTAL Döner Sermaye İşletmesi**

---

## 1. Hangi sorunu çözer?

Mesleki eğitim veren okullarda koordinatör müdür yardımcıları ve öğretmenler her ay aynı verileri farklı
yerlere tekrar tekrar yazar:

- e-Okul ve e-Mesem'deki öğrenci listeleri Excel'e aktarılır, işletme bilgileriyle elle eşleştirilir.
- Her ay SGK prim hizmet listesi için prim günü, eksik gün ve belge türü tek tek hesaplanır.
- İşletmelerin ödeyeceği öğrenci ücreti ve devlet katkısı, 3308 sayılı Kanun'a göre ayrı ayrı hesaplanır.
- Koordinatör görevlendirmeleri, ziyaret planları, ek ders puantajları ve sözleşmeler Word'de yeniden yazılır.
- Yasal süreler (SGK giriş-çıkış, MUHSGK, dekont teslimi) akılda veya kâğıtta takip edilir.

MesKoord bu verileri **bir kez** alır (e-Okul/e-Mesem/Excel listelerinden ya da kopyala-yapıştırla) ve
bütün hesapları, listeleri ve resmî belgeleri bu tek kaynaktan üretir.

## 2. Kimler kullanır?

| Kullanıcı | Programda en çok kullandığı yerler |
|---|---|
| **Koordinatör müdür yardımcısı** | Yerleştirme ve sözleşmeler, SGK, öğrenci ücreti, aylık kapanış, koordinatörlük görevlendirmesi |
| **Okul / kurum müdürü** | Ana sayfa özetleri, yasal süre uyarıları, imzaya gelen belgeler |
| **Koordinatör öğretmen** | Ziyaret planı ve ziyaret kayıtları, işletme notları, devamsızlık girişi |
| **Alan / bölüm şefi** | Ders dağılımı, atölye yerleşimi, işletme kontenjanları |
| **Ek ders / maaş işlerini yürüten personel** | Ek ders puantajı |
| **Okul bilişim sorumlusu** | Kurulum, çok kullanıcılı çalışma, yedekleme, lisans |

## 3. Neler yapar?

### Veri girişi ve aktarım
- **Toplu Veri Girişi:** Excel benzeri tabloya yazarak ya da Excel/e-Okul ekranından **kopyala-yapıştır** ile
  giriş. Sütun başlıkları kendiliğinden eşlenir, kaydetmeden önce hatalar gösterilir, yarım kalan iş taslak
  olarak saklanır. Tek satırda öğrenci + sınıf + işletme + yerleştirme birlikte kaydedilebilir.
- **Veri Aktarımı:** Excel (xlsx, xls, ods), CSV, Word, PDF, HTML ve JSON dosyalarından 17 veri türünü
  **içeriğine bakarak** tanır. Dosyayı pencereye sürüklemek yeterlidir. Önce önizleme yapılabilir; gerçek
  aktarımdan önce otomatik yedek alınır.
- **e-Okul / e-Mesem / SGK Bağlantısı:** Bu siteler program içindeki tarayıcıda, kullanıcının **kendi
  şifresiyle** açılır; indirilen listeler kendiliğinden aktarılır. Şifre ve oturum bilgisi saklanmaz.

### Mesleki eğitim süreçleri
- **Ders Programı:** Ders dağılımı, otomatik ders programı ve atölye/laboratuvar yerleşimi; kilitli hücreler,
  öğretmen müsaitliği ve çakışma kontrolü; Excel ve PDF çıktısı.
- **Yerleştirme ve Sözleşmeler:** İşletmelerde mesleki eğitim ve çıraklık yerleştirmeleri, toplu yerleştirme,
  sözleşme belgelerinin otomatik üretimi.
- **Koordinatörlük:** Ortaöğretim Kurumları Yönetmeliği md.88'e göre otomatik koordinatör görevlendirme
  (koordinatör başına en çok 15 öğrenci, önce alan ve atölye öğretmenleri), görevlendirme yazıları,
  işletmelere bildirim yazıları, komisyon kararı, aylık ziyaret planı ve ziyaret raporları.
- **Komisyon ve İzleme İşleri:** Yıl sonu başarı ortalamasına göre öğrenci seçimi ve komisyon tutanağı
  (md.136), işletme uygunluk tespit tutanağı, alan taraması ve işletme talepleri, mezun ve işyeri anketleri,
  usta öğretici hizmetiçi eğitim programı. Sözleşme, eğitim planı onayı, usta öğretici sayısı ve puan
  çizelgesi süreleri yönetmeliğe göre denetlenir ve hatırlatılır.
- **SGK Sigorta İşlemleri:** Aylık prim hizmet listesi (prim günü, eksik gün, belge türü, prime esas kazanç,
  prim tutarı), bekleyen işe giriş/çıkış bildirimleri.
- **Öğrenci Ücreti ve Devlet Katkısı:** 3308 sayılı Kanun md. 25 ve Geçici md. 12'ye göre işletme bazında
  ödenecek ücret, devlet katkısı, dekont takibi ve eksik ödeme tespiti.
- **Devamsızlık ve Değerlendirme:** Okul ve işletme devamsızlığı, sınır aşımı uyarıları, beceri notları,
  veli bildirim yazıları.
- **Ek Ders Puantajı:** Ders programı ve koordinatörlük görevlerinden haftalık ek ders hesabı; nöbet, DYK gibi
  elle eklenen kayıtlar.
- **Evrak:** Word şablonlarından belge üretimi (okul kendi şablonunu düzenleyebilir), evrak kayıt defteri.

### Asistan
Program **Asistan** ekranıyla açılır ve önce günün gündemini gösterir: süresi yaklaşan ya da geçen yasal
işlemler, eksik adımlar, önerilen işler. Komutlar serbest Türkçe yazılır:

| Yazılan | Sonuç |
|---|---|
| `bugün ne yapmalıyım` | Uyarılar ve önerilen adımlar |
| `geçen ayın kapanışını hazırla` | SGK, ücret, dekont, ek ders, devamsızlık listeleri, işletme/veli yazıları, ziyaret planı ve yedek tek klasörde |
| `ekim sgk listesi` | O ayın SGK prim hizmet listesi |
| `denetim` | Eksik/hatalı T.C., IBAN, sözleşme, SGK süresi, kontenjan, ders yükü, çakışma bulguları |
| `yeni eğitim yılı` | Sınıf atlatma, mezunları pasife alma, görevleri sıfırlama (önce yedek alınır) |

### Yıl boyu süreç takibi
Yıl başı, her ay ve yıl sonu yapılması gerekenler Asistan'ın **Süreçler** sekmesinde listelenir. Her adımın
tamamlanıp tamamlanmadığı veritabanından kendiliğinden denetlenir; adıma çift tıklamak işi başlatır.

## 4. Okuldaki bütün bilgisayarlarda aynı veri

- Okuldaki bir bilgisayar **sunucu** olur, diğerleri yerel ağ üzerinden ona bağlanır. İnternet gerekmez.
- Herkes aynı anda çalışır; birinin kaydettiği değişiklik diğer bilgisayarların açık ekranlarında
  **yaklaşık yarım saniyede** görünür.
- Aynı kaydı iki kişi aynı anda değiştirirse farklı alanlar birleştirilir, aynı alan için hangi değerin
  geçerli olacağı sorulur.
- Kimlerin bağlı olduğu ekranda görünür. Bağlantı koparsa program kendiliğinden yeniden bağlanır.
- Sunucu bilgisayarında pencere kapatılsa da program sistem tepsisinde çalışmayı sürdürür; istenirse Windows
  açılınca kendiliğinden başlar. Böylece diğer bilgisayarların bağlantısı gün boyu kesilmez.
- **Kişisel kullanıcı hesapları (isteğe bağlı):** her personel kendi kullanıcı adı ve parolasıyla girer.
  Roller: **Yönetici** (her şey), **Personel** (günlük veri girişi; kurum bilgileri, mevzuat ayarları ve
  hesaplar hariç), **Salt okunur** (görüntüleme ve rapor; ör. müdür, denetim).
- **İşlem günlüğü:** kim, hangi bilgisayardan, ne zaman, hangi kaydı ekledi, değiştirdi ya da sildi; neyi
  neyle değiştirdi. Günlük program içinden değiştirilemez.
- Lisans yalnızca sunucuya yüklenir.

## 5. Veri güvenliği ve kişisel veriler

- Bütün veriler okulun kendi bilgisayarında (`Belgeler\MesKoord`) tek bir veritabanı dosyasında durur.
  Program **hiçbir sunucuya veri göndermez**, kullanım istatistiği toplamaz.
- Ağ bağlantısı **şifrelidir (TLS)**, sunucu parolasıyla korunur ve yalnızca okulun yerel ağında çalışır.
  Bağlanan bilgisayar sunucunun kimliğini bir doğrulama koduyla onaylar.
- e-Okul, e-Mesem ve SGK şifreleri programa kaydedilmez.
- Program kaldırılsa ya da lisans süresi bitse de veriler silinmez.
- İstenildiğinde tek tıkla yedek alınır; toplu işlemlerden ve geri yüklemeden önce yedek kendiliğinden alınır.
- **Zamanlanmış otomatik yedek** (varsayılan günde bir); her yedeğin bir kopyası USB belleğe ya da okulun ağ
  klasörüne de alınabilir.
- Kullanıcı hesapları açıksa parolalar yalnızca geri döndürülemez özet olarak saklanır; işlem günlüğünde
  T.C. kimlik no, IBAN, telefon ve adres gibi kişisel veriler gizlenir (\*\*\*).

## 6. Mevzuat değişikliklerine uyum

Asgari ücret, memur aylık katsayısı, ek ders göstergeleri, SGK oranları, belge türleri, ücret oranları,
koordinatörlük ve ek ders sınırları gibi **tüm sayısal değerler** *Ayarlar > Mevzuat Parametreleri*
ekranında dayanaklarıyla listelenir ve okul tarafından güncellenebilir. Yeni yıl değerleri program
güncellemeleriyle de gönderilir.

## 7. Teknik gereksinimler

| Gereksinim | Değer |
|---|---|
| İşletim sistemi | Windows 10 veya Windows 11, 64 bit |
| Disk alanı | Program için yaklaşık 600 MB, veriler için birkaç yüz MB yeterli |
| Bellek | 4 GB (8 GB önerilir; e-Okul/SGK ekranları gömülü tarayıcı kullanır) |
| Ekran | 1366×768 ve üzeri (pencere ekrana kendiliğinden sığar) |
| İnternet | Gerekmez. Yalnızca e-Okul/e-Mesem/SGK ekranları için gerekir. |
| Çok kullanıcılı çalışma | Aynı yerel ağ; sunucuda TCP 47400 ve UDP 47401 (kurulum güvenlik duvarı iznini kendisi ekler) |
| Kurulum | `MesKoord_Kurulum_X.Y.Z.exe` (yönetici yetkisi yoksa "Yalnızca benim için" ya da taşınabilir zip). Laboratuvar için sessiz kurulum desteklenir. |

## 8. Lisanslama

- **Kurum lisansı:** Lisans, okulun MEB kurum koduna verilir ve o okulun **bütün bilgisayarlarında** geçerlidir.
  Bilgisayar sayısı sınırı yoktur.
- **30 gün ücretsiz deneme:** Program lisanssız olarak 30 gün tam özellikli denenebilir.
- **Lisans talebi:** Program içinden *Yardım > Lisans Bilgileri > Lisans Talebi Oluştur* ile hazırlanan
  metin lisans verene gönderilir; gelen `.lic` dosyası kurulum dosyasının yanına konur ya da program içinden
  yüklenir.
- Lisanslı kurumun adı ve kodu programa kilitlenir ve üretilen bütün belgelerde yer alır.
- Süreli lisans bittiğinde 30 gün ek süre tanınır; sonrasında da veriler silinmez, yedek alınabilir.

## 9. Sınırlamalar (açıkça bilinmesi gerekenler)

- Program e-Bildirge, MEBBİS, e-Okul veya KBS'ye **doğrudan veri göndermez**. SGK bildirimleri ve ek ders
  puantajı, ilgili sistemlere girilecek bilgileri içeren Excel listeleri olarak hazırlanır.
- Taranmış (resim) PDF'lerden metin okunamaz.
- Hesaplamalar yardımcı niteliktedir; resmî işlemden önce güncel mevzuata göre kontrol edilmelidir.
- Çok kullanıcılı çalışmada sunucu bilgisayarının açık ve MesKoord'un orada çalışıyor olması gerekir.

## 10. Belgeler

| Belge | Kimin için |
|---|---|
| `docs/KULLANIM_KILAVUZU.md` (programda *Yardım > Kullanım Kılavuzu*) | Programı kullanan öğretmen ve idareciler |
| `README.md` | Kısa özet ve kurulum |
| `docs/DEVIR_TESLIM.md` | Programı devralacak bilişim öğretmenleri ve yazılımcılar |
| `docs/GELISTIRICI_EL_KITABI.md` | Bakım, geliştirme, sürüm çıkarma ve lisans üretimi ayrıntıları |
| `docs/MARKA_KIMLIGI.md` | Logo, renk ve ad kullanım kuralları |

## 11. İletişim

Lisans, destek ve eğitim talepleri için: **Derik Mesleki ve Teknik Anadolu Lisesi Döner Sermaye İşletmesi**
(telefon ve e-posta bilgileri programın *Yardım > Lisans Bilgileri* penceresinde yer alır).
