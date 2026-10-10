# MesKoord Kullanım Kılavuzu

**Mesleki Eğitim Koordinasyon ve Yönetim Sistemi** · Sürüm 1.3.0

Bu kılavuz, MesKoord'u kullanan okul müdürü, koordinatör müdür yardımcısı, koordinatör öğretmen, alan şefi
ve diğer personel için yazılmıştır. Kılavuz program içinde de açılır: **Yardım > Kullanım Kılavuzu** ya da
**F1** tuşu. Sol taraftaki içindekiler listesinden konuya atlayabilir, üstteki kutuya yazarak arama
yapabilir, _PDF Olarak Kaydet_ ile çıktı alabilirsiniz.

Kılavuzda ekran ve düğme adları programdaki gibi **kalın** ya da "tırnak içinde" yazılmıştır.

---

## 1. Programı tanıyalım

MesKoord, mesleki eğitimle ilgili verileri (öğrenci, öğretmen, işletme, sınıf, ders, yerleştirme,
devamsızlık…) **bir kez** alır. SGK listesi, öğrenci ücreti, ders programı, koordinatör görevlendirmesi,
ek ders puantajı, sözleşmeler ve resmî yazıların hepsi bu tek kaynaktan üretilir.

- Bütün veriler okulunuzun bilgisayarında, `Belgeler\MesKoord` klasöründe durur. İnternet gerekmez; program
  hiçbir yere veri göndermez.
- **1.3.0'dan önceki sürümü kullananlar:** programın eski adı KoordMES'ti. Güncellemeyi kurup programı ilk
  açtığınızda `Belgeler\KoordMES` klasörü kendiliğinden `Belgeler\MesKoord` olur; program
  `C:\Program Files\MesKoord` klasörüne geçer, lisansınız, ayarlarınız ve "Windows açılışında başlat" seçeneği
  korunur. Görev çubuğuna sabitlediğiniz eski simgeyi kaldırıp yenisini sabitleyin. Eski klasör o sırada başka
  bir programda açıksa (ör. Excel'de bir çıktı) taşınamaz; program eski klasörle çalışmayı sürdürür ve bir
  sonraki açılışta yeniden dener.
- Okuldaki birden çok bilgisayar aynı verilerle **aynı anda** çalışabilir (bkz. bölüm 9).
- İsterseniz okul personelinin her biri **kendi kullanıcı adı ve parolasıyla** girer; herkesin yetkisi
  rolüne göre belirlenir ve kimin hangi kaydı değiştirdiği **işlem günlüğünde** görünür (bkz. bölüm 9).
- Hesaplar, _Ayarlar > Mevzuat Parametreleri_ ekranındaki değerlere (asgari ücret, oranlar, sınırlar)
  göre yapılır. Bu değerleri okulunuz güncelleyebilir.

> Hesaplamalar yardımcı niteliktedir. Resmî bildirim ve ödemelerden önce sonuçları güncel mevzuata göre
> kontrol ediniz.

## 2. Kurulum, lisans ve ilk açılış

### Kurulum

1. `MesKoord_Kurulum_X.Y.Z.exe` dosyasını çalıştırın. Okulunuza verilen lisans dosyası (`.lic`) kurulum
   dosyasıyla **aynı klasördeyse** lisans kendiliğinden yüklenir.
2. Yönetici yetkiniz yoksa kurulumda **"Yalnızca benim için"** seçeneğini kullanın.
3. Kurulum, Windows güvenlik duvarına yalnızca okul ağından bağlantıya izin veren bir kural ekler (çok
   kullanıcılı çalışma için).
4. Yeni sürüm eskisinin üzerine kurulur; verileriniz ve lisansınız korunur. Kurmadan önce programı kapatın.

**Güncelleme:** Program açıldıktan kısa süre sonra, günde en çok bir kez yeni sürüm olup olmadığına bakar
(kurum veya kişi bilgisi gönderilmez). Yeni sürüm varsa "İndir ve Kur" der; kurulum dosyası indirilir,
doğrulanır ve program kapanıp kurulum başlar. Elle denetlemek için **Yardım > Güncellemeleri Denetle...**;
kapatmak için **Yardım > Açılışta Güncellemeleri Denetle** işaretini kaldırın. Ağda çalışıyorsanız önce
sunucu bilgisayarı, sonra diğerlerini güncelleyin.

Bilgisayar laboratuvarına sessiz kurulum (bilişim sorumlusu için):
`MesKoord_Kurulum_X.Y.Z.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART`

### Lisans

- Program lisans yüklenmeden **30 gün** tam özellikli denenebilir. Pencere başlığında
  "Deneme sürümü - N gün kaldı" yazar.
- Lisans **kurum bazındadır**: MEB kurum kodunuzla verilen bir lisans okulunuzun bütün bilgisayarlarında
  geçerlidir. Ağda çalışılıyorsa lisansı yalnızca sunucu bilgisayara yüklemek yeterlidir.
- Lisans almak için **Yardım > Lisans Bilgileri...** > "Lisans Talebi Oluştur..." düğmesine basın.
  "MEB Kurum Kodu" ve "Kurum Adı" zorunludur; MEBBİS'teki **resmî adı** yazın, çünkü bu ad lisansa
  kilitlenir ve bütün belgelerde yer alır. Oluşan talep metnini "Panoya Kopyala" ya da "Dosyaya Kaydet..."
  ile alıp lisans verene gönderin.
- Size gelen lisansı yüklemenin iki yolu vardır:
  - "Lisans Dosyası Yükle...": `.lic` dosyasını seçin.
  - "Lisans Kodunu Yapıştır...": **KMLIS1.** ile başlayan kodun tamamını yapıştırın.
- Lisans yüklenince _Ayarlar > Kurum Bilgileri_ ekranındaki **Kurum Adı** ve **Kurum Kodu** lisanstaki
  değerle değişir ve düzenlenemez hâle gelir.
- Süreli lisans bitince 30 gün ek süre tanınır ("Lisans süresi doldu - N gün içinde yenileyin"). Ek süre
  de biterse yalnızca lisans penceresi açılır; bu pencerede "Verilerimi Yedekle" ve "Veri Klasörünü Aç"
  düğmeleri vardır. **Verileriniz hiçbir durumda silinmez.**

### Ekran düzeni

- **Sol menü:** Ekranlar simgeli gruplar hâlinde sıralanır (Genel, Tanımlar, Ders Programı, İşletmelerde
  Mesleki Eğitim, Personel, Evrak, Sistem).
  - Grup adına tıklayınca grup açılır ya da kapanır. Bir grup açılınca öteki gruplar kendiliğinden kapanır;
    menü küçük ekranda da kaydırmadan sığar. Açık ekranın grubunun simgesi turkuaz görünür.
  - **Menüde ara (Ctrl+K):** menünün üstündeki kutuya ekran adından bir parça yazın ("ücret", "sgk",
    "puantaj"). Türkçe karakter gerekmez. Enter ilk sonucu açar, Esc kutuyu temizler, aşağı ok menüye geçer.
  - **Menüyü daralt (Ctrl+B ya da logonun yanındaki ≡ düğmesi):** menü dar bir simge şeridine iner, sayfalara
    daha çok yer kalır. Şeritte bir grup simgesine tıklayınca o grubun ekranları açılır liste olarak gelir;
    büyüteç simgesi menüyü geçici olarak açıp aramaya geçer. Tercih hatırlanır. Ekran genişliği 1280
    pikselden azsa menü ilk açılışta dar gelir.
  - Program son kapandığında açık olan ekranla başlar (ilk açılışta **Asistan**).
- **Sol alt köşe:** "Güvenli Çıkış" düğmesi.
- **Üst menü:** "Dosya" altında "Şimdi Yedekle" ve "Güvenli Çıkış" (Ctrl+Q); kullanıcı hesapları açıksa
  "Parolamı Değiştir..." ve "Kullanıcı Değiştir (Oturumu Kapat)" da buradadır. "Görünüm" altında "Menüde Ara"
  (Ctrl+K) ve "Menüyü Daralt" (Ctrl+B). "Yardım" altında "Kullanım Kılavuzu" (F1), "Lisans Bilgileri..." ve
  "Hakkında".
- **Düğme satırları:** Pencere daraldıkça ekranlardaki düğmeler alt satıra geçer; hiçbir düğme ekran dışında
  kalmaz.
- **Durum çubuğu (alt satır):**
  - Solda çalışma biçimi yazar: "● Tek bilgisayar", "Sunucu açık • N kullanıcı çevrim içi" ya da
    "... sunucusuna bağlı". Tıklayınca ağ ekranı açılır.
  - Kullanıcı hesapları açıksa girişteki kişi ve rolü yazar ("Kullanıcı: Ayşe Yılmaz (Personel)").
    Tıklayınca hesap ekranı açılır.
  - Ortada veritabanının yeri yazar.
  - Sağda lisans durumu yazar. Bitişe 30 gün veya daha az kaldıysa kırmızıya döner.
- **Sürükle-bırak:** Bir Excel, Word ya da PDF dosyasını pencerenin herhangi bir yerine bırakırsanız
  **Veri Aktarımı** ekranı açılır ve dosya oraya eklenir.
- **Pencere boyutu:** Pencere ilk açılışta ekranınıza sığacak şekilde açılır. Sonraki açılışlarda son
  boyutu ve konumu hatırlanır.

### Güvenli Çıkış

Programı her zaman **"Güvenli Çıkış"** düğmesiyle, Dosya menüsünden ya da **Ctrl+Q** ile kapatın.

- Arka planda süren bir iş varsa bitmesi beklenir.
- Toplu Veri Girişi ekranındaki taslaklar kaydedilir.
- "Çıkmadan önce veritabanını yedekle" kutusu işaretliyse yedek alınır. Bu tercih bir sonraki çıkışta
  hatırlanır.
- Bilgisayarınız sunucuysa ve bağlı kullanıcılar varsa, kimlerin bağlantısının kesileceği gösterilir.
- Sunucu bilgisayarında pencerenin sağ üstündeki çarpı programı kapatmaz, **sistem tepsisine** indirir
  (saatin yanındaki simge); böylece diğer bilgisayarların bağlantısı kesilmez. Programı kapatmak için
  Güvenli Çıkış'ı ya da tepsi simgesine sağ tıklayıp "Güvenli Çıkış"ı kullanın (bkz. bölüm 9).

## 3. Bütün liste ekranlarında ortak kullanım

Öğrenciler, öğretmenler, işletmeler, yerleştirmeler, devamsızlık kayıtları gibi ekranların hepsi aynı
düzendedir. Bir kez öğrenmeniz yeterlidir.

- **"Ara..."** kutusuna yazdığınız metin bütün sütunlarda aranır.
- Bazı ekranlarda üstte bir **filtre** vardır (ör. "Sınıf:", "Alan:", "İşletme:"). "(Tümü)" bütün kayıtları
  gösterir. Filtre seçiliyken **Yeni** dediğinizde o alan formda hazır gelir. Örneğin "Sınıf: 12-A"
  seçiliyken eklenen öğrenci 12-A'ya kaydedilir.
- Düğmeler:
  - **"Yeni"**: kayıt ekler.
  - **"Düzenle"**: seçili kaydı açar. Satıra çift tıklamak da aynı işi yapar.
  - **"Sil"**: seçili kayıtları siler. Birden çok satır seçebilirsiniz; bağlı kayıtlar da silinebilir.
  - **"Excel'e Aktar"**: ekranda görünen (aranmış/süzülmüş) satırları Excel'e yazar.
- Sütun başlığına tıklayınca liste o sütuna göre sıralanır. Altta kayıt sayısı görünür.
- **Formda:**
  - Zorunlu alanların yanında **\*** vardır.
  - İsteğe bağlı tarih alanlarında önce yanındaki kutuyu işaretleyin, sonra tarihi seçin.
  - Sınıf, öğretmen, işletme gibi seçim kutularına **yazarak arama** yapabilirsiniz.
  - T.C. kimlik numarası geçersizse kaydetmeden önce uyarılırsınız.
- **Aynı kaydı başka biri de değiştirdiyse** (ağda): farklı alanlardaki değişiklikler birleştirilir. Aynı
  alanı ikiniz de değiştirdiyseniz "Eşzamanlı değişiklik" penceresi hangisinin geçerli olacağını sorar.

**Renkler:** Kırmızı/pembe = kritik veya süresi geçmiş, sarı = uyarı, mavi = bilgi, yeşil = tamam.

**Kaydedilen dosyalar:** Excel, Word ve PDF dosyaları `Belgeler\MesKoord\Ciktilar` klasörüne kaydedilir.
Kayıttan sonra açılan pencerede "Aç" ya da "Klasörü Aç" ile dosyaya ulaşabilirsiniz.

## 4. İlk kullanım: adım adım kurulum sırası

Programı okulunuzda ilk kez kullanmaya başlarken bu sırayı izleyin. Aynı liste **Asistan > Süreçler** sekmesinde
"Eğitim yılı başlangıcı" olarak durur ve her adımın tamamlanıp tamamlanmadığı kendiliğinden işaretlenir.

1. **Ayarlar > Kurum Bilgileri:**
   - Kurum türünü (MTAL / MEM / MTAL+MEM) ve büyükşehir durumunu seçin.
   - Müdür ve koordinatör müdür yardımcısının adını, SGK işyeri sicil numarasını ve eğitim-öğretim yılını yazın.
   - İsterseniz kurum logosunu yükleyin.
2. **Ayarlar > Mevzuat Parametreleri:** Asgari ücret, memur aylık katsayısı ve 3308 Geçici 12. madde
   durumunu kontrol edin.
3. **Tatil Günleri:** Eğitim yılının resmî tatillerini ve ara tatillerini girin (en az 3 kayıt). SGK gün
   sayısı, ek ders ve ziyaret planı bunlara göre hesaplanır.
4. **Listeleri aktarın:** e-Okul, MEBBİS ve e-Mesem'den aldığınız öğrenci, öğretmen ve işletme listelerini
   pencereye sürükleyin. Ayrıntı için bölüm 5'te **Veri Aktarımı** ve **Toplu Veri Girişi** başlıklarına bakın.
5. **Sınıflar / Şubeler:** Her sınıfın programını, alanını, dalını, okul günlerini ve işletme günlerini
   girin. Kaydedince çerçeve öğretim programındaki zorunlu dersler önerilir (bölüm 6, Sınıflar / Şubeler).
6. **Öğretmenler:** Öğretmenlerin müsait olmadığı saatleri girin.
7. **Ders Dağılımı ve Atölye Yerleşimi:** Zorunlu dersler açıldıktan sonra öğretmenleri atayın, seçmeli
   dersleri ekleyin ve **"Otomatik Yerleştir"** ile programı üretin.
8. **Yerleştirme ve Sözleşmeler:** Öğrencileri işletmelere yerleştirin ve sözleşmeleri üretin.
9. **Koordinatörlük:** **"Otomatik Görevlendir"** ile görevleri dağıtın, görevlendirme yazılarını ve ziyaret
   planını üretin.
10. **SGK Sigorta İşlemleri:** İşe giriş bildirgesi bekleyen öğrencileri kontrol edin.

> Programı önce denemek isterseniz _Ayarlar > Veri ve Yedekleme_ sekmesindeki
> "Örnek Veri Yükle (mevcut veriler silinir)" düğmesini kullanın. Bu işlem mevcut verileri siler (önce
> yedek alınır); gerçek veri girmeye başladıktan sonra kullanmayın.

## 5. Görevinize göre hızlı başlangıç

### Koordinatör müdür yardımcısı

| Ne zaman                                | Ne yapılır                                                                                                            | Nerede                                                                     |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Eylül                                   | Listelerin aktarımı, yerleştirme, sözleşme, SGK işe giriş, koordinatör görevlendirme                                  | Asistan > Süreçler > "Eğitim yılı başlangıcı"                              |
| Yıl boyu                                | Yönetmelikten gelen görevler (uygunluk tespiti, komisyon kararı, bildirimler, puan çizelgeleri, anket, alan taraması) | Asistan > Süreçler > "Koordinatör müdür yardımcısı görevleri (Yönetmelik)" |
| Öğrenciler işletmeye gönderilmeden önce | Başarı ortalamasına göre öğrenci seçimi ve komisyon tutanağı (md.136)                                                 | **Komisyon ve İzleme İşleri** > "Öğrenci Seçimi"                           |
| Her ayın başı                           | Önceki ayın kapanışı: SGK listesi, ücret, dekont, ek ders, devamsızlık, veli yazıları, ziyaret planı                  | Asistan'a `geçen ayın kapanışını hazırla` yazın                            |
| Her gün                                 | Yaklaşan yasal süreler                                                                                                | **Ana Sayfa** ve Asistan gündemi                                           |
| Öğrenci işletmeden ayrılınca            | Yerleştirmeyi sona erdirme ve SGK çıkış bildirimi                                                                     | **Yerleştirme ve Sözleşmeler** > "Seçilenleri Sona Erdir..."               |
| Ayda bir                                | Veri denetimi                                                                                                         | Asistan > "Veri Denetimi" sekmesi                                          |
| Haziran                                 | Yıl sonu işlemleri                                                                                                    | Asistan > Süreçler > "Yıl sonu ve yeni yıla geçiş"                         |

### Koordinatör öğretmen

1. **Koordinatörlük > Ziyaret Planı ve Raporları** sekmesinde dönemi seçin; size ait ziyaretleri görmek
   için "Öğretmen:" filtresinden adınızı seçin.
2. Ziyaretten sonra kaydı açıp **Durum**'u "Yapıldı" yapın; **Tespitler** ve **Öneriler** alanlarını doldurun
   (ya da "Yapıldı Olarak İşaretle").
3. "Ziyaret Formu Üret (Word)" ile ziyaret formunu alın.
4. İşletmeden gelen devamsızlıkları **Devamsızlık ve Değerlendirme > Devamsızlık Kayıtları** sekmesine,
   dönem sonu notlarını "İşletmede Mesleki Eğitim Notları" sekmesine girin.

### Okul / kurum müdürü

- **Ana Sayfa**'da özet sayılar ve yasal süre uyarıları görünür.
- Asistan'a `bugün ne yapmalıyım` ya da `istatistik` yazın.
- Belgelerdeki müdür adı _Ayarlar > Kurum Bilgileri_ ekranından gelir.

### Alan / bölüm şefi

- **Dersler**, **Atölye / Laboratuvarlar** ve **Ders Dağılımı ve Atölye Yerleşimi** ekranları.
- İşletmelerin **Kontenjan** ve **Usta Öğretici** bilgileri (**İşletmeler** ekranı).

### Ek ders işlerini yürüten personel

- **Ek Ders Puantajı > Aylık Puantaj**: dönemi seçin, "Excel'e Aktar (Puantaj)".
- Programda olmayan nöbet, DYK, gece dersi gibi kayıtları "Elle Ek Ders Kayıtları" sekmesine girin.

### Okulun bilişim sorumlusu

- Kurulum ve güncellemeler (bölüm 2), **Çok Kullanıcılı Çalışma (Ağ)** (bölüm 9), yedekleme (bölüm 10),
  sorun giderme (bölüm 13).

## 6. Ekranlar

### Asistan

Programın açılış ekranıdır. Solda sohbet bölümü, sağda "Süreçler" ve "Veri Denetimi" sekmeleri vardır.

**Sohbet bölümü**

- Açılışta günün gündemi gösterilir: süresi yaklaşan ya da geçen yasal işler, eksik adımlar, önerilen işler.
- Komut kutusuna ne yapmak istediğinizi Türkçe yazıp **Enter**'a basın. Yazarken öneriler çıkar.
  Komutların listesi bölüm 7'dedir. Kutuya `yardım` yazarsanız bütün komutlar tıklanabilir hâlde listelenir.
- Hızlı düğmeler: "Bugün", "Denetim", "Aylık kapanış", "SGK", "Ücret", "Ek ders", "Devamsızlık", "Yardım".
- Yanıtlardaki bağlantılar tıklanabilir: dosyayı açar, ekrana götürür, işlemi çalıştırır ya da kişi,
  işletme veya sınıf kartını gösterir.
- Bir öğrencinin, öğretmenin, işletmenin adını, bir sınıfı (`12-A`), T.C. ya da okul numarasını yazarsanız
  ilgili **bilgi kartı** açılır.
- **Dosya ekleme:** Dosyaları bu ekrana sürükleyin ya da "Dosya Ekle..." düğmesine basın.
  1. Asistan dosyalardaki tabloları ve türlerini listeler.
  2. Kaydetmeden bir deneme sonucu gösterir.
  3. "▸ Aktar (önce yedek alınır)" bağlantısına basarsanız aktarır. Sütunları düzeltmek isterseniz
     "▸ Aktarım ekranında incele / sütunları düzelt" bağlantısını kullanın.
- "Temizle" sohbeti siler.

> Dikkat: SGK listeleri, dekont, ek ders, ücret, devamsızlık, veli bildirimleri, ziyaret planı,
> görevlendirme yazıları, sözleşmeler ve yedek komutları **onay sormadan** çalışıp dosya üretir. Veri
> silen ya da baştan dağıtan işlemler (program oluşturma, koordinatör görevlendirme, yıl sonu, yeni eğitim
> yılı) ise önce onay ister.

**"Süreçler" sekmesi**

- Üstteki listeden süreci seçin: "Eğitim yılı başlangıcı", "Aylık işlemler" ya da "Yıl sonu ve yeni yıla
  geçiş". Aylık işlemlerde dönem de seçilir.
- Her adımın durumu kendiliğinden denetlenir: ✔ tamam, ⚠ eksik, ℹ bilgi. Programın yapamadığı adımlarda
  "(elle yapılır)" yazar.
- Adıma **çift tıklayın** ya da seçip "Seçili Adımı Çalıştır" düğmesine basın; işlem çalışır ya da ilgili
  ekran açılır. "Aylık Kapanışı Hazırla" düğmesi bütün aylık çıktıları birlikte üretir.
- Adımların tam listesi bölüm 8'dedir.

**"Veri Denetimi" sekmesi**

- "Verileri Denetle" düğmesi kayıtlardaki eksik, hatalı ve mevzuata aykırı durumları listeler. Sonuç
  "N kritik, N uyarı, N bilgi bulgu" biçiminde özetlenir.
- Bir bulguya çift tıklayınca düzeltmeniz gereken ekran açılır.
- Denetlenen başlıca durumlar:
  - İşletmedeki öğrencide eksik veya geçersiz T.C. (SGK bildirimi yapılamaz)
  - Aynı T.C.'nin iki öğrencide olması
  - Eksik veya hatalı IBAN
  - Sınıfı girilmemiş öğrenci
  - İşletmeye yerleştirilmemiş 12. sınıf / MEM öğrencisi
  - Başlangıç tarihi olmayan, tarihleri çakışan ya da işletmesi seçilmemiş yerleştirme
  - Sözleşme numarası eksikliği, sözleşme tarihinin işe başlamadan sonra olması
  - Süresi geçmiş SGK bildirimi
  - Usta öğreticisi ya da personel sayısı girilmemiş işletme
  - Kontenjanı aşılmış işletme
  - Koordinatörü atanmamış işletme
  - Ders yükü veya koordinatörlük sınırının aşılması
  - Ders programında çakışma
  - Eksik tatil günleri

### Ana Sayfa

- Başlıkta kurum adı ve eğitim-öğretim yılı yazar.
- **"Son veri değişikliği"** kutusu, e-Okul / e-Mesem / SGK'dan indirilen veya belgeden yüklenen son listede
  kaç öğrenci, öğretmen, işletme, yerleştirme ve SGK kaydının eklendiğini ya da güncellendiğini gösterir.
- Kartlar: "Aktif Öğrenci", "İşletmede Eğitim Gören", "Aktif İşletme", "Öğretmen", "Koordinatör Öğretmen",
  "Bekleyen SGK Bildirimi".
- **"Yasal süreler ve uyarılar"** tablosunda şunlar listelenir:
  - Önceki ayın MUHSGK beyanı, dekont toplama ve devlet katkısı girişinin son günleri. Kalan süre 2 gün
    veya azsa Kritik, 7 gün veya azsa Uyarı olarak gösterilir. Son gün tatile denk gelirse sonraki iş
    gününe kayar.
  - Bekleyen veya süresi geçmiş SGK işe giriş/çıkış bildirimleri.
  - Devamsızlık sınırını aşan ya da sınıra yaklaşan öğrenciler.
  - Önümüzdeki 7 gündeki ziyaretler ve sonucu girilmemiş geçmiş ziyaretler.
  - Sözleşme numarası, personel sayısı, T.C. ve kurum bilgisi eksikleri.
- "Yenile" düğmesi listeyi yeniler; ekran her açıldığında da yenilenir.

### Toplu Veri Girişi

Çok sayıda kaydı Excel'deki gibi bir tabloya yazarak ya da yapıştırarak girmek için kullanılır.

1. **"Giriş türü:"** listesinden ne gireceğinizi seçin.
2. Verileri girin:
   - Hücrelere doğrudan yazabilirsiniz.
   - Excel'de ya da e-Okul/e-Mesem ekranında satırları seçip **Ctrl+C** ile kopyalayın, tabloda bir
     hücreye tıklayıp **Ctrl+V** ile yapıştırın.
   - Kopyaladığınız alan başlık satırını da içeriyorsa sütunlar, sıraları farklı olsa bile kendiliğinden
     eşlenir.
   - **"Belge Yükle..."** ile (ya da belgeyi ekrana sürükleyerek) e-Okul, e-Mesem, e-Bildirge'den indirilen ya
     da elinizdeki Excel, PDF, Word, HTML, CSV, ZIP belgesini seçin. Belgedeki her liste türüne göre tanınır;
     sayfa başlığındaki sınıf, dönem, ders gibi bilgiler de satırlara eklenir. Açılan pencerede
     **"Akıllı Kaydet (tümünü)"** her listeyi ilişkili kayıtlarıyla birlikte doğrudan kaydeder (öncesinde yedek
     alınır); **"Seçili Listeyi Tabloya Al"** listeyi kontrol etmeniz için giriş tablosuna yerleştirir.
3. **"Kontrol Et"** ile denetleyin. Hatalı hücreler kırmızı, uyarılı hücreler sarı olur. Hücrenin üzerine
   gelince açıklaması görünür; uygun satırlara "Uygun" yazılır.
4. İsterseniz **"Önizle (kaydetmez)"** ile sonucu kaydetmeden görün.
5. **"Kaydet"**'e basın. Kayıttan önce otomatik yedek alınır. Var olan kayıtlar (aynı T.C., okul no, ad)
   güncellenir, yeni olanlar eklenir.
6. Kaydedilen satırların tablodan temizlenmesini onaylayın. Hatalı satırlar düzeltmeniz için kalır.
7. Altta beliren **"Sonraki adımlar:"** düğmeleri sizi sıradaki işe götürür. Örneğin yerleştirmeden sonra
   sözleşme, SGK listesi ve ücret hesabı önerilir.

**Kısayollar:**

| Tuş                            | İşlevi                                                   |
| ------------------------------ | -------------------------------------------------------- |
| Ctrl+V                         | Yapıştırır                                               |
| Ctrl+C                         | Seçili hücreleri kopyalar                                |
| Ctrl+D                         | Aşağı doldurur: seçili hücrelere en üstteki değeri yazar |
| Delete / Backspace             | Seçili hücreleri temizler                                |
| Herhangi bir tuş veya çift tık | Hücreyi düzenlemeye başlar                               |

Diğer düğmeler: "+50 Satır", "Seçili Satırları Sil", "Tümünü Temizle".

**Taslak:** Yazdıklarınız kendiliğinden taslak olarak saklanır. Program kapansa da kaybolmaz; ekranı
yeniden açtığınızda "Kaydedilmemiş taslaktan N satır yüklendi." yazar.

**En hızlı başlangıç:** Listenin ilk türü olan **"Öğrenci + İşletme Yerleştirme (SGK ve ücret için hızlı
giriş)"** tek satırda öğrenciyi, sınıfını, işletmesini ve yerleştirmesini birlikte kaydeder. Eksik
öğrenci, sınıf ve işletme kayıtları kendiliğinden oluşturulur. Eylül SGK listesi ve işletme ücret yazıları
için gereken bilgiler bunlardır. Sütunlar:

| Sütun                       | Açıklama                                      |
| --------------------------- | --------------------------------------------- |
| T.C. Kimlik No              | 11 hane                                       |
| Adı Soyadı \*               |                                               |
| Sınıf/Şube                  | ör. 11-A                                      |
| Program                     | MEM / MTAL-AMP / MTAL-ATP                     |
| Statü                       | Öğrenci / Aday Çırak / Çırak / Kalfa (MEM 12) |
| Bakmakla Yükümlü (E/H)      | E: SGK belge 7, H: belge 42                   |
| İşletme Adı \*              |                                               |
| İşletme Personel Sayısı     | Ücret ve devlet katkısı oranını belirler      |
| İşletmeye Başlama Tarihi \* | gg.aa.yyyy                                    |
| Ayrılış Tarihi              | Devam ediyorsa boş bırakın                    |
| Öğrenci IBAN                |                                               |

Diğer giriş türleri:

- Tanım kayıtları:
  - Öğretmenler
  - İşletmeler
  - Sınıflar / Şubeler
  - Atölye / Laboratuvarlar
  - Dersler
  - Tatil Günleri
  - Öğrenciler / Çıraklar
- Program ve yerleştirme:
  - Ders Dağılımı (Sınıf-Ders-Öğretmen)
  - Haftalık Ders Programı (Gün-Saat): hazır programın saatleri kilitli olarak yerleşir
  - İşletme Yerleştirmeleri (Öğrenci-İşletme)
  - Koordinatörlük Görevleri
- Takip kayıtları:
  - Devamsızlık
  - İşletmede Mesleki Eğitim Notları
  - Elle Ek Ders Kayıtları
  - İşletme Ziyaretleri
- Ödeme ve SGK:
  - Ücret Dekontları (işletme ödemeleri)
  - SGK İşe Giriş / Ayrılış Bildirgeleri

Sütun başlığının üzerine gelince alanın zorunlu olup olmadığı, biçimi ("gg.aa.yyyy", "E / H") ve
seçenekleri görünür.

### Veri Aktarımı

Hazır dosyalardan toplu aktarım içindir. Desteklenen biçimler: Excel (xlsx, xlsm, xls), ODS, CSV/TXT,
Word (docx), PDF, HTML ve JSON. Dosya türü uzantıya değil içeriğe bakılarak tanınır; örneğin e-Okul'un
aslında HTML olan `.xls` dosyaları da okunur.

1. **"Dosya Ekle..."** ile dosyaları seçin ya da ekrana sürükleyin. Bir dosyadaki bütün sayfalar ve
   tablolar soldaki **"Bulunan tablolar"** listesine ayrı ayrı gelir.
2. Her tablonun altında tanınan tür yazar: "→ Öğrenciler / Çıraklar (N kayıt)". Tanınmayan tablolarda
   "→ Tanınmadı, veri türünü seçin" yazar.
3. Bir tabloyu seçin; sağda **"Veri türü:"** ve **"Başlık satırı:"** değerlerini kontrol edin.
4. **Eşleme tablosunda** her alanın dosyadaki hangi sütundan alınacağını görürsünüz. Yanlışsa açılır
   listeden düzeltin. Zorunlu alanlar kalın ve \* işaretlidir. Gerekli sütunlar eksikse kırmızı uyarı çıkar.
5. Gerekirse şu seçenekleri ayarlayın:
   - "Mevcut kayıtları güncelle" (varsayılan açık).
   - "Eksik öğrenci/işletme/sınıf kayıtlarını oluştur" (varsayılan açık).
   - Dosyada yoksa kullanılacak değerler: yerleştirmede başlangıç tarihi, devamsızlıkta tarih ve yer,
     dekontta dönem.
6. **"Önizle (deneme, kaydetmez)"** ile deneyin. Sonuç tablosunda her satır için "Eklendi",
   "Güncellendi", "Atlandı" ya da "Hata" görünür.
7. **"Seçili Tabloyu Aktar"** ya da işaretli tabloların hepsi için **"İşaretlilerin Tümünü Aktar"**. İşaretli
   tablolar doğru sırayla aktarılır (önce sınıf ve işletme, sonra öğrenci, sonra yerleştirme). Aktarımdan
   önce otomatik yedek alınır; hatalı satırlar atlanır, diğerleri aktarılır.

Tanınan 17 veri türü:

- Tanım kayıtları:
  - Öğretmenler
  - İşletmeler
  - Sınıflar / Şubeler
  - Atölye / Laboratuvarlar
  - Dersler
  - Tatil Günleri
  - Öğrenciler / Çıraklar
- Program ve yerleştirme:
  - Ders Dağılımı
  - Haftalık Ders Programı (Gün-Saat)
  - İşletme Yerleştirmeleri
  - Koordinatörlük Görevleri
- Takip kayıtları:
  - Devamsızlık
  - İşletmede Mesleki Eğitim Notları
  - Elle Ek Ders Kayıtları
  - İşletme Ziyaretleri
- Ödeme ve SGK:
  - Ücret Dekontları
  - SGK İşe Giriş / Ayrılış Bildirgeleri

Aktarım sırasında kendiliğinden yapılanlar:

- Eksik sınıf, alan, dal, işletme, öğrenci ve öğretmen kayıtları oluşturulur.
- "11. Sınıf / A Şubesi" gibi yazımlar "11-A" biçimine getirilir; büyük harfli adlar düzeltilir.
- İşletme değiştiren öğrencinin eski yerleştirmesi bir gün öncesinde kapatılır.
- e-Bildirge listesindeki öğrencilerin SGK giriş/çıkışları işaretlenir.
- Dekont listesinde ödenen tutar hesaplanan ücretle karşılaştırılır, eksik ödemeler işaretlenir.
- e-Okul toplam devamsızlık listesi önceki toplu kayıtların yerine geçer.
- Belgenin üst satırlarındaki ya da PDF sayfa başlığındaki sınıf, dönem, tarih gibi bilgiler tablodaki her
  satıra eklenir (ör. sınıf sütunu olmayan e-Okul sınıf listeleri).
- Ders programı ızgaraları, ders dağılımı matrisleri ve öğretmen müsaitlik çizelgeleri düz listeye çevrilip
  ilgili türe aktarılır (bkz. Ders Dağılımı ve Atölye Yerleşimi > "Belgeden Yükle").
- Aylık prim hizmet listesi ve hizmet dökümü gibi SGK listeleri aktarılmaz, karşılaştırma için SGK Sigorta
  İşlemleri > Liste Karşılaştırma'ya yönlendirilir.

**Boş şablon:** Elinizde hazır liste yoksa "Seçili Tür İçin Boş Şablon" ya da "Tüm Türler İçin Şablon" ile
doğru başlıklı boş Excel dosyası alın, doldurup geri sürükleyin.

### e-Okul / e-Mesem / SGK Bağlantısı

Resmî sistemleri program içindeki tarayıcıda açar ve oradan indirdiğiniz listeleri kendiliğinden aktarır.

1. Üstteki düğmelerden birine basın: **"e-Okul"**, **"e-Mesem"**, **"e-Bildirge V2"**,
   **"SGK İşe Giriş / Çıkış"** ya da **"SGK e-Vizite"**. Sistem kendi sekmesinde açılır. _Ayarlar > Kurum
   Bilgileri_'ndeki **"Sistemlerden verileri getir"** düğmesi, kurum türünüzün kullandığı sistemleri sırayla
   açar (MEM'de önce e-Mesem, diğerlerinde önce e-Okul).
2. Girişi **kendi şifrenizle** yapın. MesKoord şifrelerinizi görmez ve saklamaz; program kapanınca
   oturumlar da kapanır.
3. Giriş algılanınca sekme başlığında "● " ve durum satırında "Bağlı" yazar. Algılanmazsa sekmedeki
   **"Girişi Yaptım"** düğmesine basın.
4. Sistemden ihtiyacınız olan listeyi (öğrenci listesi, öğrenci-işletme listesi, devamsızlık, bildirge
   listesi…) Excel olarak indirin. "İndirilen listeleri otomatik aktar" işaretliyse liste aktarılır ve alttaki
   **"İndirilen dosyalar"** tablosunda sonucu görünür.
5. Dosyayı aktarmadan önce incelemek isterseniz satırı seçip "Seçili Dosyayı Aktarım Ekranında İncele"
   düğmesine basın.

Notlar:

- "Edge/Chrome ile indirilen Excel listelerini de al" işaretliyse, bilgisayarın İndirilenler klasörüne yeni
  inen Excel/CSV/HTML tabloları da yakalanır.
- Bir sayfa program içinde açılamazsa "Edge/Chrome'da Aç" düğmesini kullanın; indirdiğiniz listeler
  yukarıdaki seçenek sayesinde yine aktarılır.
- e-Bildirge V2'de dosya seçme penceresi MesKoord çıktı klasöründe açılır. SGK ekranında XML üretip
  **"Program İçinde e-Bildirge V2'yi Aç ve Yükle"** (ya da İşe Giriş / Çıkış için aynı düğme) seçilirse
  pencere doğrudan o dosyayla açılır.
- Liste aktarımı arka planda yapılır; büyük dosyalarda da ekran donmaz. Birden çok dosya inerse sırayla işlenir.
- İndirilen dosyalar `Belgeler\MesKoord\Indirilenler\<Sistem adı>` klasöründe saklanır ("İndirilenler
  Klasörü" düğmesi).

### Toplu Gönderim (E-posta / WhatsApp)

Her öğretmene ve işletmeye **kendi** belgesini gönderir. Belgeler kişi başına ayrı üretilir; e-posta her
alıcıya ayrı ileti olarak gider, kimse başkasının adresini ya da belgesini görmez.

1. **Gönderim** listesinden seçin: öğretmenlere kendi ders programı (PDF), koordinatör öğretmenlere
   görevlendirme yazısı, işletmelere koordinatör öğretmen bildirimi, işletmelere aylık ücret ve devlet katkısı
   bildirimi (ay seçilir) ya da işletmelere öğrenci sözleşmeleri.
2. **"Belgeleri Hazırla"**'ya basın. Tabloda her alıcının e-postası, telefonu ve dosyaları görünür. E-posta
   ve telefonu olmayanlar "E-posta ve telefon yok" yazar; Öğretmenler veya İşletmeler ekranından tamamlayın.
3. Konu ve mesajı düzenleyin. `{ad}` alıcının adıyla, `{donem}` seçilen ayla, `{kurum}` okul adıyla değişir.
4. Gönderin:
   - **"E-posta ile Hepsine Gönder"**: programdan doğrudan gönderir. İlk kullanımda **"E-posta Ayarları..."**
     açılır: Gmail, Outlook/Office 365 veya Yandex seçip okulun e-posta adresini yazın. Şifre gönderirken
     sorulur, diske yazılmaz, program kapanınca unutulur. Gmail'de hesap şifresi değil, Google hesabı >
     Güvenlik > **Uygulama şifreleri**'nden alınan şifre kullanılır. "Kendime Deneme İletisi Gönder" ile
     ayarı sınayın.
   - **"Sıradakini Posta Programında Aç"**: Outlook gibi posta programında sıradaki alıcının iletisi ekli
     açılır; siz gönderirsiniz.
   - **"WhatsApp: Sıradakini Aç"**: sıradaki alıcının belgesi panoya kopyalanır ve WhatsApp (yüklü değilse
     WhatsApp Web) o kişinin sohbetiyle açılır. Sohbete tıklayıp **Ctrl+V** ile yapıştırın ve gönderin, sonra
     sıradaki için düğmeye yeniden basın. WhatsApp, programların dosyayı kendiliğinden göndermesine izin
     vermediği için son adımı siz yaparsınız.
5. "Durum" sütununda kime gönderildiği görünür. Belgeler `Belgeler\MesKoord\Ciktilar\Toplu Gönderim`
   klasöründe kalır.

**Tek bir çıktıyı paylaşmak:** Excel, PDF veya Word çıktısı kaydedilince açılan pencerede
**"Paylaş (e-posta / WhatsApp)..."** düğmesi vardır. Alıcıları kayıtlı öğretmen, işletme, usta öğretici,
veli ve öğrencilerden işaretleyin ya da "Diğer alıcılar"a adres veya telefon yazın. WhatsApp'ta bir gruba
göndermek için kimseyi işaretlemeden "WhatsApp ile Gönder"e basın, açılan WhatsApp'ta grubu seçip Ctrl+V
yapın. Birden çok belge birlikte üretildiyse son üretilenler işaretli gelir.

### Öğrenciler / Çıraklar

Öğrenci ve çırak bilgileri. Filtre: "Sınıf:".

Alanlar:

- Okul No, T.C. Kimlik No, Adı \*, Soyadı \*, Sınıf.
- Statü \*: Öğrenci / Aday Çırak / Çırak / Kalfa (MEM 12).
- **"Bakmakla yükümlü olunan (GSS anne/babadan)":** İşaretliyse SGK primi %1'dir (belge 7/49).
  İşaretsizse %6'dır (belge 42/50).
- Doğum Tarihi, Cinsiyet, Telefon, Veli Adı Soyadı, Veli Telefon, IBAN, Adres.
- **"Alt Sınıf Yılsonu Başarı Ortalaması"**, **"Kısa süreli uzaklaştırmadan ağır disiplin cezası var"** ve
  **"Sıralamaya girmeden gönderilir (şehit/gazi çocuğu, koruma/eğitim tedbiri)"**: İşletmeye gönderilecek
  öğrencilerin sıralamasında kullanılır (Yönetmelik md.136; bkz. **Komisyon ve İzleme İşleri**). Ortalamayı
  e-Okul listesinden **Veri Aktarımı** ya da **Toplu Veri Girişi** ile toplu yükleyebilirsiniz ("Yılsonu
  Başarı Puanı" sütunu tanınır). Son iki bilgi kişisel veridir; işlem günlüğünde gizlenir.
- Aktif.

Mezun olan ya da ayrılan öğrenciyi silmek yerine **Aktif** işaretini kaldırın; geçmiş kayıtları korunur.

### Öğretmenler

Öğretmen ve yöneticiler. Filtre: "Alan:".

Alanlar:

- T.C., Adı \*, Soyadı \*, Branş, Alan.
- Unvan \*: Öğretmen / Atölye/Lab. Öğretmeni / Müdür Yardımcısı / Koordinatör Müdür Yardımcısı /
  Müdür Başyardımcısı / Müdür.
- Telefon, E-posta.
- **"Aylık Karşılığı Ders (boş=unvana göre)"** ve **"Azami Haftalık Ek Ders (boş=unvana göre)"**: Boş
  bırakılırsa mevzuat parametresindeki değer kullanılır.
- **"Koordinatör olabilir":** İşaretsiz öğretmene otomatik koordinatörlük verilmez.
- **"Alanı atölye ve laboratuvar öğretmenliği":** Koordinatörlük görevinde önceliklidir (Yönetmelik
  md.88/2-e). Unvanı "Atölye/Lab. Öğretmeni" olanlar ayrıca işaretlenmese de öncelikli sayılır.
- **"Müsait Olmadığı Saatler":** "Tablodan seç..." düğmesiyle açılan çizelgede ders verilemeyecek saatleri
  işaretleyin. Gün adına basmak o günün bütün saatlerini işaretler. Elle de yazabilirsiniz: `1-*`
  Pazartesi bütün gün, `3-5` Çarşamba 5. saat demektir.
- Aktif.

### İşletmeler

Filtre: "Alan:".

Alanlar:

- İşletme Adı \*, Alan, Yetkili, Telefon, E-posta, Vergi No, SGK Sicil No.
- **Personel Sayısı:** 20'den az ya da 20 ve üzeri olması ücret oranını ve devlet katkısını belirler;
  mutlaka girin.
- **"Kamu kurumu (devlet katkısı ödenmez)".**
- Güzergah/Bölge ve Okula Uzaklık (km): Koordinatör saat hesabında kullanılır.
- İlçe, Adres.
- Usta Öğretici / Eğitici Personel ve telefonu: yasal zorunluluktur; sözleşmeye yazılır.
- **Usta Öğretici / Eğitici Personel Sayısı:** Bir usta öğreticiye en çok 16 öğrenci düşer (md.135).
- **"Usta öğreticinin ustalık / iş pedagojisi belgesi var"** (md.152).
- **"Eğitim birimi kurulmuş":** 10 ve üzeri öğrencisi olan işletmede gereklidir (md.142, md.148).
- **"İl sınırları dışında":** İl dışındaki staj yerlerine koordinatör görevlendirilmez (md.88/2-g).
- **"Okulun döner sermaye işletmesi":** Koordinatör görevlendirilmez (md.88/8).
- **Uygunluk Tespit Tarihi (komisyon)** ve **Eğitim Planı Onay Tarihi:** İşletme belirleme komisyonunun
  tespit tarihi (md.140-142) ve usta öğreticinin eğitim planının onay tarihi (ilk hafta içinde, md.146).
  Girilmezse Veri Denetiminde uyarı verilir.
- IBAN.
- **Kontenjan:** Aşılırsa denetimde uyarı verilir. Öğrenci seçiminde varsayılan kontenjan alanın aktif
  işletmelerinin kontenjan toplamıdır.
- Aktif.

Eylem düğmeleri: **"Uygunluk Tespit Tutanağı (Word)"** (md.142'deki sekiz ölçütlü tutanak; programdaki
bilgiler "Kayıtlı Bilgi" sütununa yazılır) ve **"Koordinatör Bildirim Yazısı (Word)"** (işletmeye
koordinatör öğretmenlerin adını, ziyaret gününü ve öğrencileri bildiren yazı, md.88/1).

### Sınıflar / Şubeler

Alanlar:

- Sınıf/Şube \* (ör. 12-A), Seviye.
- Program \*: MTAL-AMP / MTAL-AMP-11 / MTAL-ATP / MEM. MTAL-AMP-11, işletmelerde mesleki eğitime 11. sınıfta
  başlayan okulların Anadolu meslek programıdır (11. sınıfta 2 gün işletme).
- Alan, Dal. 10. sınıftan itibaren ders çizelgesi dala göre değiştiği için dal da seçilmelidir.
- **Okul Günleri:** Ders programı yalnızca bu günlere yerleşir.
- **İşletme Günleri:** Koordinatör ziyaretleri bu günlere planlanır.
- Rehber Öğretmen.

MTAL'de işletmelerde mesleki eğitim haftada 3 gün işletme + 2 gün okul (ya da 2 gün işletme + 3 gün okul)
şeklinde yapılır (md.134); MEM için genellikle 1 gün okul + 4 gün işletme tanımlanır. Okul ve işletme günleri
çakışırsa ya da MTAL'de gün dağılımı bu kurala uymazsa Veri Denetimi uyarır.

**Zorunlu derslerin kendiliğinden açılması:** Yeni bir sınıf kaydedildiğinde ya da sınıfın seviyesi,
programı, alanı veya dalı değiştirildiğinde program, MEB çerçeve öğretim programındaki haftalık ders
çizelgesini bulur ve **"Çerçeve Öğretim Programındaki Zorunlu Dersler"** penceresini açar. Pencerede:

- Sınıfın okulda okutulacak zorunlu dersleri (ortak dersler, meslek dersleri, rehberlik) haftalık saatleriyle
  işaretli gelir; açmak istemediğiniz dersin işaretini kaldırabilirsiniz.
- Ders dağılımında zaten bulunan dersler "dağılımda var", saati farklı olanlar sarı renkle gösterilir.
  "Haftalık saati çizelgeden farklı olan dersleri düzelt" işaretliyse saatleri çizelgeye göre düzeltilir.
- İşletmelerde mesleki eğitim (yeşil satırlar), seçmeli dersler ve akademik destek saatleri ders dağılımına
  açılmaz; bunlar okulca belirlenir. Sınıfın okul/işletme günleri çizelgeye uymuyorsa uyarı yazılır.
- Sınıfın dalı seçilmemişse "Haftalık ders çizelgesi" listesinden dalı seçin; "Sınıfın dalını ... olarak
  kaydet" işaretliyse dal sınıfa da kaydedilir.
- "Kaynak PDF'i Aç" düğmesi çizelgenin alındığı MEB PDF'ini açar.

**"Zorunlu Dersleri Aç"** dendiğinde dersler Ders Dağılımı'na öğretmensiz eklenir (Rehberlik ve Yönlendirme
dersine sınıfın rehber öğretmeni atanır). Dersler tanımlarında yoksa Dersler listesine eklenir; meslek
dersleri sınıfın alanına bağlanır. Var olan öğretmen ve atölye atamaları korunur, çizelgede olmayan dersler
silinmez. Sınıflar listesinde **"Çerçeve Programdaki Zorunlu Dersleri Aç"** düğmesi seçili sınıflar için
(seçim yoksa tüm sınıflar için) aynı işlemi yapar.

### Alanlar

Alan Adı \* ve Kod.

### Dallar

Alan \* ve Dal Adı \*. Filtre: "Alan:".

### Dersler

Alanlar:

- Ders Adı \*, Kısa Ad, Alan.
- Tür \*: Kültür / Meslek / Atölye.
- "Atölye/Lab. gerektirir".
- **"Blok (ardışık saat)":** Örneğin 4 yazılırsa ders 4'er saatlik bloklar hâlinde yerleşir.

### Atölye / Laboratuvarlar

Adı \*, Tür \* (Atölye / Laboratuvar / Derslik), Alan ve Kapasite. Atölye gerektiren dersler, aynı alanın
uygun atölyelerine yerleştirilir.

### Tatil Günleri

Açıklama \*, Başlangıç \* ve Bitiş \*. Resmî tatiller ve ara tatiller; ziyaret planı, SGK günü ve ek ders
puantajında dikkate alınır. Her eğitim yılı başında girin.

### Ders Dağılımı ve Atölye Yerleşimi

İki sekmesi vardır.

**"Ders Dağılımı (Sınıf-Ders-Öğretmen)" sekmesi**

Her satır bir sınıfın bir dersidir. Filtre: "Sınıf:".

- Sınıf \*, Ders \*, Öğretmen.
- Haftalık Saat \*.
- "Blok (boş=dersin bloğu)".
- "Sabit Atölye/Lab.": Boş bırakılırsa uygun atölye kendiliğinden seçilir.
- "2. Öğretmen (grup/çiftli)": İki öğretmenle aynı saatte yapılan dersler içindir. Ders iki öğretmenin de
  programına yazılır, ikisi de o saatte başka derse verilmez. Sınıf mevcudu alanın en büyük atölyesine
  sığmıyorsa sınıf iki gruba bölünür ve ders aynı saatte iki atölyeye yerleşir.
- "2. Atölye/Lab. (grup)": İkinci grubun her zaman aynı atölyede olmasını istiyorsanız seçin.
- "Birleştirme Grubu": Farklı sınıfların birlikte yapılan dersine (ör. iki şubenin beden eğitimi) aynı grup
  adını yazın (ör. BED-9). Bu dersler aynı saatlere yerleşir, öğretmene ve ek ders puantajına bir kez yazılır,
  çakışma sayılmaz.

Toplu giriş için **Toplu Veri Girişi** ya da **Veri Aktarımı**'ndaki "Ders Dağılımı" türünü kullanabilirsiniz.
Ders dağılımını sıfırdan girmek yerine **"Çerçeve Programdaki Zorunlu Dersleri Aç"** düğmesini kullanın:
"Sınıf:" filtresinde bir sınıf seçiliyse o sınıfın penceresi açılır, seçili değilse bütün sınıflara
seviye, alan ve dallarına göre zorunlu dersler açılır. Ardından yalnızca öğretmenleri atamanız yeterlidir.

**"Haftalık Program / Atölye Yerleşimi" sekmesi**

1. **"Görünüm:"** listesinden Sınıf, Öğretmen ya da Atölye/Lab. seçin, yanındaki listeden hangisini
   göreceğinizi belirleyin.
2. **"Belgeden Yükle..."** (ya da belgeyi sekmeye sürükleyin): elinizdeki ders programını, ders dağılımı
   çizelgesini veya öğretmen müsaitlik listesini Excel, PDF ya da Word olarak yükleyin. Tanınan biçimler:
   - Sınıf, öğretmen ya da atölye programı ızgarası (günler sütunda ya da satırda, bir sayfada birden çok
     program olabilir). Hücrede ders, öğretmen ve atölye alt alta, parantez içinde ya da köşeli parantezde
     yazabilir ("Matematik / A.YILMAZ", "WEB (A.Kaya) [Bilişim Lab.]").
   - Bütün okulun çarşaf programı (sınıflar satırda, gün ve saatler sütunda).
   - Ders dağılımı matrisi (sınıflar sütunda, dersler ya da öğretmenler satırda, hücrede haftalık saat).
   - Öğretmen müsaitlik çizelgesi (X ile işaretli günler / saatler) ya da "Çarşamba", "Salı 5-8",
     "Pzt öğleden sonra" gibi yazılmış liste.

   Sınıflar, dersler, öğretmenler ve atölyeler eksikse tanımlanır; ders dağılımı ve haftalık saatler
   oluşturulur; programdaki saatler **kilitli** olarak yerleşir. Kalan saatler varsa otomatik
   yerleştirmeyi önerir. Aynı belgeleri Veri Aktarımı ve Toplu Veri Girişi'ne de yükleyebilirsiniz.

3. **"Ön Denetim"** yerleştirmeden önce yerleşmeyi engelleyecek sorunları listeler: ders dağılımı boş,
   sınıfın haftalık saati okul günlerine sığmıyor, öğretmenin dersi müsait saatlerine, koordinatörlük
   günlerine ya da günlük azami ders sınırına sığmıyor, sınıf mevcudu atölyelere sığmıyor, atölye ihtiyacı
   atölye sayısını aşıyor, blok ders günlük saatten uzun, birleştirilen derslerin saatleri farklı.
4. **"Otomatik Yerleştir"** kilitli olmayan bütün dersleri silip yeniden yerleştirir (onay ister; ön
   denetimde kritik sorun varsa önce onları gösterir). Şunlar dikkate alınır:
   - Öğretmen müsaitliği, sınıfın okul günleri, blok uzunlukları.
   - İki öğretmenli (grup) dersler: iki öğretmen de bağlanır; gerektiğinde ikinci atölye kullanılır.
   - Birleştirilmiş dersler: aynı saatte birlikte yerleşir.
   - Atölye kapasitesi: "Atölye seçiminde kapasiteyi (öğrenci/grup mevcudu) gözet" açıksa sınıf mevcuduna
     yeten en küçük atölye.
   - "Koordinatörlük görev günlerini okulda derse kapat" açıksa koordinatörlük günleri. Bu durumda yerleşmeyen
     ders kalırsa program bu günleri gerektiği kadar açar ve sonuçta not düşer.
   - "Bir öğretmene günde en çok ders saati" (0 ise sınırsız).

   Bu üç ayar Ayarlar > Mevzuat Parametreleri'ndedir.

   Sonuçta ya "Tüm dersler çakışmasız yerleşti" yazar ya da yerleşemeyen bloklar listelenir.

5. **Elle düzeltme (sağ tık):**
   - Dolu hücrede "Kilitle", "Kilidi Aç" ve "Sil" seçenekleri vardır (birleştirilmiş derste bütün sınıflar
     için birlikte uygulanır).
   - Boş hücrede, Sınıf görünümündeyken, "Ders ekle..." seçeneği vardır; iki öğretmenin de boş olduğu ve
     atölyenin dolu olmadığı denetlenir.
   - Kilitli hücreler sarı görünür ve otomatik yerleştirmede yerinde kalır. **"Kilitleri Aç"** bütün
     kilitleri kaldırır.
6. Sağ paneldeki "Eksik kalan ders saatleri" listesi yerleşmeyen saatleri gösterir. Hücrelerde ikinci
   öğretmen ve ikinci atölye "/" ile, birleştirilmiş sınıflar "9-A + 9-B" biçiminde görünür.
7. "Kontrol Et" çakışmaları ve eksikleri listeler. "Kilitsizleri Temizle" kilitsiz hücreleri siler.
8. Çıktılar:
   - **"Excel (Tüm Programlar)"**: her sınıf, öğretmen ve atölye için ayrı sayfa.
   - **"PDF (Bu Tablo)"**: kurum logolu, yatay A4.

Yerleşemeyen ders kalırsa öğretmenin müsait olmadığı saatleri, sınıfın okul günlerini, atölye sayısını ya
da blok uzunluklarını gözden geçirin.

**"Çerçeve Öğretim Programları" sekmesi**

[meslek.meb.gov.tr/cerceve](https://meslek.meb.gov.tr/cerceve) adresindeki MTAL ve MEM çerçeve öğretim
programlarının haftalık ders çizelgeleri programla birlikte gelir; internet bağlantısı gerekmez.

1. **Okul** (MTAL / MEM), **Sınıf** (9-12), **Program** (Anadolu teknik, Anadolu meslek, 11. sınıfta işletmeye
   başlayan Anadolu meslek, MEM), **Alan** ve **Dal** seçin. Bir alanın hem protokollü hem protokolsüz
   programı varsa "Protokollü program" kutusu etkinleşir.
2. Çizelgede dersler, kategorileri ve haftalık saatleri; altında seçmeli ders, akademik destek ve haftalık
   toplam saat görünür. (\*) işaretli dersler yılsonu başarı puanıyla geçilemeyen derslerdir.
3. **"Sınıfın Çizelgesini Göster"**: alttaki listede seçili sınıfın çizelgesine gider.
   **"Sınıfa Uygula..."**: gösterilen çizelgenin zorunlu derslerini seçili sınıfa açar.
4. **"Alanı ve Dallarını Tanımlara Ekle"**: seçili alanı ve bütün dallarını Alanlar / Dallar tanımlarına
   MEB'deki adlarıyla ekler. Sınıf tanımlamadan önce kullanılırsa adlar çizelgeyle birebir eşleşir.
5. "Kaynak PDF'i Aç" ve "Excel'e Aktar" ile çizelgeyi inceleyebilir ya da yazdırabilirsiniz.

Veri Denetimi, ders dağılımında çerçeve programdaki zorunlu dersi eksik ya da haftalık saati farklı olan
sınıfları ve çizelgesi belirlenemeyen (alanı/dalı eksik ya da tanınmayan) sınıfları listeler. Asistan'a
"zorunlu dersleri aç" yazarak bütün sınıflara zorunlu dersleri açabilirsiniz.

### Yerleştirme ve Sözleşmeler

Öğrencilerin işletmelere yerleştirilmesi. Filtre: "İşletme:".

Alanlar:

- Öğrenci \*, İşletme.
- Tür \*: İşletmede Mesleki Eğitim / Staj / Çıraklık / Tamamlayıcı Eğitim / Okulda Alan Eğitimi.
- Başlangıç \*, Bitiş.
- Sözleşme No, Sözleşme Tarihi.
- "Sözleşme Aylık Ücreti (0=yasal alt sınır)".
- SGK giriş ve çıkış bildirildi işaretleri ve tarihleri.
- Durum \*: Aktif / Sona Erdi / Feshedildi.
- Fesih/Ayrılış Nedeni (listeden seçilir).

Sözleşmeler ders yılı sonu ile yeni ders yılının ikinci haftası sonu arasında imzalanır; MEM'de ilk
yerleştirmede iki ay, işyeri değişikliğinde iki hafta süre vardır (md.143). Süre geçtiği hâlde **Sözleşme
Tarihi** boş olan yerleştirmeler Veri Denetiminde kritik olarak listelenir. Süre, _Ayarlar > Kurum
Bilgileri_'ndeki **Ders Yılı Başlangıcı**'na göre hesaplanır.

Okulda alan eğitimi gören öğrenciler için işletme seçmeden **"Okulda Alan Eğitimi"** türünde kayıt açın
(SGK belge türü 49/50). Ara tatil, yarıyıl ve yaz tatillerinde bitiş tarihi girilmez.

Eylem düğmeleri:

- **"Sözleşme Üret (Word)":** Seçili yerleştirmeler için sözleşme üretir. Tür "Çıraklık" ise çıraklık
  sözleşmesi kullanılır. "Okulda Alan Eğitimi" için sözleşme üretilmez.
- **"Çıraklık Sözleşmesi (MEM)"** ve **"Değerlendirme Formu".**
- **"Sınıfı Toplu Yerleştir...":**
  - Sınıf, tür, isteğe bağlı işletme, başlangıç tarihi ve sözleşme no ön eki seçilir.
  - Ön ek "2026/" yazılırsa numaralar 2026/001, 2026/002… olur.
  - O türde aktif yerleştirmesi olmayan aktif öğrenciler için kayıt açılır.
- **"Seçilenleri Sona Erdir...":**
  - Neden seçilir: Mezuniyet / Nakil / Karşılıklı fesih / 3308 sayılı Kanun md.22 hâlleri / Devamsızlık
    nedeniyle başarısızlık / Sağlık durumu / İşyerine uyum sağlayamama / İşyeri değişikliği / Okul
    değişikliği / Kayıt silme / Diğer. Sözleşme yalnızca md.22 hâllerinde, devamsızlık nedeniyle
    başarısızlıkta veya sağlık nedeniyle tek taraflı feshedilir; diğer durumlarda karşılıklı fesih yapılır
    (md.143). Fesih sayılan nedenlerde Durum "Feshedildi", diğerlerinde "Sona Erdi" olur.
  - Bitiş tarihi bugün olur.
  - SGK işten ayrılış bildirgesi **SGK Sigorta İşlemleri** ekranında listelenir.
  - "İşyeri değişikliği" seçilen MEM öğrencisi iki hafta içinde yeni işletmeye yerleştirilmezse Veri
    Denetimi uyarır.
- **"Öğrenci Seçimi (md.136)...":** **Komisyon ve İzleme İşleri** ekranının öğrenci seçimi sekmesini açar.

Belgeler `Ciktilar\<Belge adı>\<Öğrenci>_<İşletme>.docx` olarak kaydedilir.

### Koordinatörlük

Üç sekmesi vardır.

**"Görev Dağılımı" sekmesi**

- **"Otomatik Görevlendir":** Mevcut görevleri silip yeniden dağıtır (onay ister). Ortaöğretim Kurumları
  Yönetmeliğinin 88 inci maddesine göre çalışır:
  - Aynı işletme ve aynı alandaki en çok 15 öğrenciye bir koordinatör öğretmen verilir; daha kalabalık
    işletmeler "1. grup", "2. grup" diye bölünür. Farklı alanların öğrencileri ayrı gruptur.
  - Öncelik alanın atölye ve laboratuvar öğretmenlerindedir; yetmezse alan öğretmenlerine, onlar da
    yetmezse diğer öğretmenlere görev verilir. Alanı dışında görevlendirilenler sonuç iletisinde listelenir
    (usul ve esaslar hakkında bilgilendirilmelidir).
  - Okulun döner sermaye işletmesine ve il dışındaki staj yerlerine görev verilmez; bunlar
    "Görevlendirilemeyen işletmeler" listesinde nedeniyle görünür.
  - Her gruba gereken saat komisyon ölçütleriyle hesaplanır: taban saat, her 5 öğrenci için +1 saat, 10
    km'den uzaksa +1 saat. Ölçütler Ayarlar'dan değiştirilebilir.
  - Görevler, öğretmenin ders programında boş olan ve öğrencilerin işletmede olduğu günlere verilir.
  - Haftalık ve günlük azami saat sınırları uygulanır.
- Tabloda her öğretmenin günlere göre saatleri, haftalık toplamı ve sınırı görünür. Sınırı aşan satır
  kırmızıdır.
- Sağda "Görevlendirilemeyen işletmeler" ve "İşletme ihtiyaçları" listeleri vardır.
- **"Görevlendirme Yazıları (Word)"** her öğretmen için görevlendirme yazısı üretir.
- **"İşletmelere Bildirim (Word)"** görevli öğretmenlerin adlarını her işletmeye bildiren yazıyı üretir
  (md.88/1).
- **"Komisyon Kararı (Word)"** planlama ölçütlerini ve bütün görev dağılımını içeren koordinatörlük
  planlama komisyonu kararını hazırlar (md.88/2-b).
- "Excel'e Aktar" dağılım tablosunu kaydeder.

**"Görevleri Düzenle" sekmesi**

Görevleri elle eklemek ya da değiştirmek içindir. Alanlar:

- Öğretmen \*, İşletme \*.
- Gün \* (1=Pazartesi … 5=Cuma).
- Haftalık Saat \*.
- Başlangıç, Bitiş.

**"Ziyaret Planı ve Raporları" sekmesi**

1. Dönemi seçip **"Aylık Planı Oluştur"**'a basın. O ayın ziyaretleri tatil günleri atlanarak planlanır;
   aynı aydaki eski "Planlandı" kayıtları yenilenir.
2. "Plan Çizelgesi (Excel)" planı Excel'e yazar. Sağ üstte "Planlı / Yapıldı / Yapılmadı" sayıları görünür.
3. Ziyaretten sonra kaydı açıp Durum, Tespitler ve Öneriler alanlarını doldurun. Hızlı işaretlemek için
   "Yapıldı Olarak İşaretle" ya da "Yapılmadı Olarak İşaretle" düğmelerini kullanın.
4. **"Ziyaret Formu Üret (Word)":** İşletme bilgileri, öğrenci listesi, tespitler ve kontrol listesiyle
   ziyaret ve rehberlik formu üretir. Kontrol listesinde yönetmelikteki maddeler de vardır: iş dosyası
   kontrolü, devamsızlığın iki iş günü içinde bildirimi, günde 8 saatten fazla çalıştırmama, eğitim
   birimi/donanım ve uyum sorunu. (Daha önce kurulmuş bir bilgisayarda yeni maddeler için _Belge Üretimi >
   "Şablonları Varsayılana Döndür"_ yapın; kendi düzenlediğiniz şablonlar varsa önce yedekleyin.)

### Komisyon ve İzleme İşleri

Koordinatör müdür yardımcısının Ortaöğretim Kurumları Yönetmeliğinden gelen komisyon ve izleme işleri.
Dört sekmesi vardır.

**"Öğrenci Seçimi (md.136)" sekmesi**

1. Alanı, isterseniz sınıf seviyesini seçin. **Kontenjan** kendiliğinden alanın aktif işletmelerinin
   kontenjan toplamı olur; değiştirebilirsiniz (0 = sınırsız).
2. **"Sırala"**:
   - Şehit/gazi çocukları ve koruma/eğitim tedbiri kararı bulunanlar sıralamaya girmeden yerleşir (mavi).
   - Kısa süreli uzaklaştırmadan ağır disiplin cezası olanlar "Koşulu sağlamıyor" olarak ayrılır (kırmızı).
   - Kalanlar alt sınıf yılsonu başarı ortalamasına göre sıralanır; kontenjan kadarı "Gönderilecek" (yeşil),
     diğerleri "Yedek" olur. Ortalaması girilmemiş öğrenciler sarıyla ayrıca gösterilir.
3. **"Excel'e Aktar"** sıralamayı, **"Komisyon Tutanağı (Word)"** öğrenci seçim komisyonu tutanağını üretir.

Öncelik ve disiplin bilgileri kişisel veridir; listeleri yalnızca komisyonla paylaşın.

**"Alan Taraması / İşletme Talepleri" sekmesi**

Koordinatör öğretmenlerin ziyaretlerde tespit ettiği öğrenci talepleri (md.89/2, md.82/2-ğ). Alanlar:
Tarih \*, İşletme \*, Alan, Dal, Talep Edilen Öğrenci \*, Taramayı Yapan Öğretmen, Açıklama.
**"Alan Özeti (Excel)"** her alan için talep, mevcut kontenjan, işletmedeki öğrenci ve gelecek yılın aday
sayısını (11. sınıflar) karşılaştırır; fark eksi ise yeni işletme bulunmalıdır.

**"Mezun ve İşyeri Anketleri" sekmesi**

Mezunların izlenmesi ve işyeri anketleri (md.89/1-ğ, md.82/2-g). Alanlar: Tarih \*, Anket Türü \* (Mezun /
İşyeri), Mezun / Öğrenci, İşletme, Uygulayan Öğretmen, Mezunun Durumu, Memnuniyet (1-5), "Elektronik ortama
aktarıldı", Görüş ve Öneriler. **"Değerlendirme (Excel)"** mezun durum dağılımını ve memnuniyet
ortalamalarını çıkarır.

**"Usta Öğretici Hizmetiçi Eğitim" sekmesi**

Usta öğretici ve eğitici personele yönelik eğitim planı (md.82/2-b, md.144/1-ç). Alanlar: Tarih \*, Konu \*,
İşletme (boş = ortak), Katılımcılar, Eğitimi Veren, Yer, Süre, Durum. **"Program (Excel)"** okul müdürünün
onayına sunulacak programı hazırlar.

### SGK Sigorta İşlemleri

Dört sekmesi vardır.

**"İşe Giriş / İşten Ayrılış" sekmesi**

- Bekleyen işe giriş ve işten ayrılış bildirimlerini, önümüzdeki 30 günde olacaklarla birlikte listeler.
  Sütunlar: İşlem, Öğrenci, T.C., Sınıf, İşletme, Belge Türü, Olay Tarihi, Son Bildirim, Durum.
- Süresi geçenler kırmızıdır ve Durum sütununda "SÜRESİ GEÇTİ" yazar.
- Kurallar:
  - İşe giriş bildirgesi sigortalılık başlamadan önce verilir.
  - İşten ayrılış bildirgesi ayrılıştan itibaren 10 gün içinde verilir.
  - Ara tatil, yarıyıl ve yaz tatillerinde ayrılış bildirilmez.
  - İşletme değişikliğinde (15 gün içinde yeni kayıt varsa) bildirim gerekmez.
- **"SGK XML Üret"** seçili satırlar için (seçim yoksa listedeki tüm satırlar için) SGK'nın 4A toplu işe giriş
  ve toplu işten ayrılış XML dosyalarını hazırlar; giriş ve çıkışlar ayrı dosyaya yazılır. Dosyaları
  e-Bildirge > 4A Sigortalı İşe Giriş / İşten Ayrılış ekranlarının "toplu" seçeneğinden yükleyin.
  **"SGK Excel Üret"** aynı bilgileri SGK'nın Excel şablonuyla aynı hücre düzeninde yazar (şablona kopyalayıp
  SGK makrosuyla XML'e çevirmek isteyenler için).
  - Sigorta kolu: işletmede mesleki eğitim / staj 19, okulda alan / tamamlayıcı eğitim 37, MESEM çırak 7.
  - Görev kodu 05, meslek kodu 9901.02 (Stajyer - Öğrenci), ÇSGB iş kolu 10, işten ayrılış nedeni 22.
  - İşten ayrılış dosyasında bulunduğumuz dönemin belge türü, hak edilen ücreti (prime esas kazanç) ve eksik
    günü hesaplanarak yazılır. Önceki ayın aylık prim hizmet belgesi henüz verilmemişse önceki dönem bilgisi de
    doldurulur.
  - Geçersiz T.C. kimlik numarası olan ya da tarihi eksik öğrenciler dosyaya alınmaz; uyarılarda listelenir.
- Bildirimi e-Bildirge'de yaptıktan sonra satırları seçip **"Seçilenleri 'Bildirildi' İşaretle"**'ye basın.
  e-Bildirge'den aldığınız bildirge listesini **Veri Aktarımı**'ndan yüklerseniz kayıtlar kendiliğinden
  işaretlenir.

**"Aylık Prim Hizmet Listesi" sekmesi**

- Dönemi seçin. Her öğrenci için şunlar hesaplanır:
  - Belge türü
  - Prim gün ve eksik gün (nedeniyle)
  - Prime esas kazanç
  - Prim oranı ve tutarı
  - Giriş ve çıkış tarihleri
- Altta belge türlerine göre özet görünür.
- **"Excel'e Aktar (kontrol listesi)"** e-Bildirge'ye girilecek bilgileri okunur bir listede hazırlar.
  Dosyada "Prim Hizmet Listesi", "Belge Türü Özeti" ve her belge türü için ayrı sayfa vardır.
- **e-Bildirge V2 dosyası** satırında belge mahiyetini (Asıl / Ek / İptal) ve tahakkuk nedenini seçin.
  Tahakkuk "otomatik" bırakılırsa belge son günü geçmemişse A (yasal süresi içinde), geçmişse B yazılır.
  - **"XML Üret"** e-Bildirge V2'ye yüklenecek aylık prim ve hizmet belgesi XML'ini hazırlar. Dosya SGK'nın
    yayımladığı XML şemasıyla (EBildirgeV2.xsd) program içinde doğrulanır; uymayan bir alan varsa uyarı verilir.
    Her belge türü (7, 42, 49, 50) ayrı bölümde yer alır.
  - **"Excel Üret (SGK şablonu)"** aynı bilgileri SGK'nın "Excel'den XML" şablonuyla aynı hücre düzeninde
    yazar.
  - Dosyalar Belgeler klasöründeki "SGK" klasörüne kaydedilir. Okulda alan eğitimi ayrı bir işyeri
    sicilinden bildiriliyorsa Mevzuat Parametreleri > "SGK Dosyaları" grubundaki ayrı sicil numarasını girin;
    o zaman okul ve işletme belgeleri için iki ayrı dosya üretilir.
  - İşyeri sicil numarası Ayarlar > Kurum Bilgileri'ne 26 hane olarak yazılmalıdır (ilk 21 hane sicil,
    sonraki 2 hane kontrol no, son 3 hane aracı no). Boşluk ve noktalar dikkate alınmaz.
  - Kanun numarası (teşvik yoksa 00000), meslek kodu, sigorta kolları, görev kodu ve ayrılış nedeni aynı
    parametre grubundan değiştirilebilir.
  - Belgeyi yükleyip onayladıktan sonra Risk ve Öneriler sekmesinde "APHB verildi" önerisini uygulayın.
- Hesap kuralları bölüm 11'dedir. Beyan son günü izleyen ayın 26'sıdır.

**"Liste Karşılaştırma" sekmesi**

e-Bildirge'den aldığınız aylık prim hizmet listesini (APHB), sigortalı / işe giriş listesini ya da hizmet
dökümünü okulun kayıtlarıyla karşılaştırır.

1. **"SGK Listesi Yükle..."** ile dosyayı (Excel, PDF, Word, HTML, ZIP) seçin ya da sekmeye sürükleyin.
   e-Okul / e-Mesem / SGK Bağlantısı ekranından indirdiğiniz son liste için **"Son İndirileni Kullan"**'a basın.
2. Dönem listeden okunur. Başka bir ayla karşılaştırmak için "Dönem:" kutusunu işaretleyip ayı seçin.
3. Öğrenciler T.C. kimlik numarasıyla, T.C. uyuşmazsa ad soyadla eşleştirilir. Şu farklar listelenir:
   SGK'da olmayan (bildirilmemiş) öğrenci, okulda olmayan sigortalı, belge türü, prim gün sayısı, prime esas
   kazanç, giriş / çıkış tarihi, ad soyad ve T.C. farkları. Her satırda hangi tarafın yanlış olabileceği ve
   ne yapılacağı yazar.
4. Okul kaydı yanlışsa satırları seçip **"Seçili Düzeltmeleri Uygula"**'ya basın (çift tık da olur); SGK
   tarafı yanlışsa öneriye göre e-Bildirge'de düzeltin. **"Excel'e Aktar"** farkları dosyaya yazar.

Veri Aktarımı ya da Toplu Veri Girişi'ne yüklenen SGK hizmet listeleri de bu sekmeye yönlendirilir.

**"Risk ve Öneriler" sekmesi**

Kayıtları SGK idari para cezası ve hatalı bildirim riskleri açısından tarar; her bulgu için ne yapılacağını,
dayanağını, son tarihini ve tahmini cezayı gösterir. Kritik satırlar kırmızı, uyarılar sarıdır.

- Süresi geçmiş ya da 7 gün içinde dolacak işe giriş / işten ayrılış bildirgeleri. Tahmini ceza, brüt
  asgari ücret üzerinden; kendiliğinden ve 30 gün içinde verilirse dörtte bire (peşin ödemede daha da) indirilmiş
  tutarla birlikte gösterilir.
- Geçersiz ya da birden çok öğrencide kullanılan T.C. kimlik numarası.
- Genel sağlık sigortası yaş sınırını aşmış ya da 45 gün içinde aşacak "bakmakla yükümlü" öğrenciler; doğum
  tarihi eksik olanlar.
- Çıkışı bildirilmiş ama bitiş tarihi girilmemiş yerleştirmeler; ara tatil ya da yarıyıl tatiline denk gelen
  bitiş tarihleri.
- Son bir yılda geç verilmiş giriş bildirgeleri (ceza tebligatı gelebilir).
- Son iki ayın verilmemiş aylık prim hizmet belgesi.

Satırları seçip **"Seçili Önerileri Uygula"**'ya basarak "bildirildi" işaretleme, aylık prim hizmet belgesinin
verildiğini kaydetme ya da "bakmakla yükümlü" işaretini kaldırma gibi düzeltmeleri tek seferde yapabilirsiniz.
Ceza ve indirim oranları Ayarlar > Mevzuat Parametreleri'ndeki SGK parametrelerinden okunur. Kritik riskler
Veri Denetimi'nde de görünür; Asistan'a "sgk ceza riskleri" yazarak özetini
alabilirsiniz.

### Öğrenci Ücreti ve Devlet Katkısı

İki sekmesi vardır.

**"Ücret ve Devlet Katkısı" sekmesi**

1. Dönemi seçin. Her öğrenci için şunlar hesaplanır:
   - Program, işletme personel sayısı ve gün sayısı
   - Uygulanan oran ve dayanağı
   - Yasal alt sınır ve ödenecek ücret
   - Devlet katkısı ve işletme payı
2. Üstteki bilgi satırında net asgari ücret ve 3308 Geçici 12. maddenin uygulanıp uygulanmadığı yazar.
3. **"Dönemi Kaydet"**: Dekont takibi bu kayıtlar üzerinden yapılır; her ay mutlaka kaydedin.
4. **"Excel'e Aktar"**: "Öğrenci Listesi" ve "İşletme Özeti" sayfaları.
5. **"İşletmelere Ücret Yazısı (Word)"**: Her işletmeye öğrencileri, gün sayılarını, ödeyeceği tutarı ve
   dekont teslim son gününü bildiren yazı.

İşletmeler ücreti izleyen ayın 10'una kadar öder. Devlet katkısı e-Okul/e-Mesem'e ayın 15'ine kadar girilir.

**"Dekont Takibi" sekmesi**

- Dönemi seçin. Kaydedilmemişse "Dönemi Hesapla ve Kaydet" ile başlayın.
- İşletmeden dekont gelince satırları seçip "Seçilenler: Dekont Teslim Alındı"'ya basın. Devlet katkısını
  sisteme girince "Seçilenler: Devlet Katkısı Sisteme Girildi"'ye basın.
- Banka ya da işletme dekont listesini (Excel, PDF, Word) **Veri Aktarımı**'ndan yüklerseniz ödenen
  tutarlar işlenir ve eksik ödemeler kendiliğinden işaretlenir.
- Durum renkleri: "Dekont yok" sarı, "Eksik ödeme" kırmızı, "Tamam" yeşil.

### Devamsızlık ve Değerlendirme

Üç sekmesi vardır.

**"Devamsızlık Özeti" sekmesi**

- Her öğrencinin okul ve işletme devamsızlığı (özürsüz/özürlü) ve toplamları listelenir.
- Varsayılan sınırlar: özürsüz 10 gün, toplam 30 gün. Durum sütununda şunlar yazar:
  - **"Sınırı aştı"** (kırmızı)
  - **"Sınıra yakın"** (sarı): özürsüzde 2 gün veya daha az, toplamda 5 gün veya daha az kaldıysa
  - **"Veli bildirimi"** (mavi): özürsüz devamsızlık 5 günü bulduysa
- Öğrencileri seçip **"Seçilenlere Veli Bildirimi (Word)"** ile veli yazısı üretin.

**"Devamsızlık Kayıtları" sekmesi**

Günlük devamsızlık girişi içindir. Alanlar:

- Öğrenci \*, Tarih \*.
- Tür \*: Özürsüz / Özürlü / Raporlu / İzinli.
- Yer \*: İşletme / Okul.
- "Gün (0,5 = yarım gün)".
- "SGK'ya eksik gün bildirilsin": Özürsüz devamsızlıkta ücret ödenmeyen günler için eksik gün bildirilir.
- Açıklama.

e-Okul'un toplam devamsızlık listesini **Veri Aktarımı** ile de yükleyebilirsiniz.

**"İşletmede Mesleki Eğitim Notları" sekmesi**

Alanlar: Öğrenci, Dönem (1/2), İşletme (Usta Öğretici) Notu, Koordinatör Öğretmen Notu, Tarih, Açıklama.

### Ek Ders Puantajı

İki sekmesi vardır.

**"Aylık Puantaj" sekmesi**

- Dönemi seçin. Her öğretmen için ayın her günündeki ders saatleri hesaplanır:
  - Ders programındaki dersler ve koordinatörlük görevleri önce aylık karşılığı doldurur; kalan saatler
    ek derstir.
  - Resmî tatildeki dersler ödenmez.
- Tabloda gündüz, gece, toplam ve tahmini brüt tutar görünür.
- **"Excel'e Aktar (Puantaj)"**: KBS'ye girişten önce kontrol için puantaj çizelgesi.

> Kesin ödeme KBS'de yapılır; bu tablo puantaj hazırlığı içindir.

**"Elle Ek Ders Kayıtları" sekmesi**

Programda olmayan ek dersleri girmek içindir. Alanlar:

- Öğretmen \*, Tarih \*.
- Tür \*: Gündüz / Gece / Nöbet / Planlama/Bakım-Onarım / DYK / Belleticilik / Sınav Görevi / Diğer.
- Saat \*, Açıklama.

### Belge Üretimi

Word şablonlarından toplu belge üretir.

1. **"Belge türü:"** seçin:
   - İşletmelerde Mesleki Eğitim Sözleşmesi
   - Çıraklık Sözleşmesi (MEM)
   - İşletmede Mesleki Eğitim Değerlendirme Formu
   - Koordinatör Öğretmen Görevlendirme Yazısı
   - İşletme Ziyaret ve Rehberlik Formu
   - Veliye Devamsızlık Bildirimi
   - İşletmeye Aylık Ücret Bildirimi (dönem de seçilir)
   - İşletmeye Koordinatör Öğretmen Bildirimi
   - İşletme Uygunluk Tespit Tutanağı
   - Koordinatörlük Planlama Komisyonu Kararı (okul geneli, tek belge)

   Öğrenci Seçim Komisyonu Tutanağı, sıralamaya bağlı olduğu için **Komisyon ve İzleme İşleri** ekranından
   üretilir.

2. Listeden kayıtları seçin ya da "Tümünü Seç"'e basın.
3. **"Seçilenler İçin Üret"**. Belgeler `Ciktilar\<Belge türü>\` klasörüne yazılır; "Çıktı Klasörü" ile
   açabilirsiniz.

Şablonları kendi resmî biçiminize göre düzenlemek için bölüm 12'ye bakın ("Şablonu Word'de Aç",
"Şablon Klasörü", "Şablonları Varsayılana Döndür").

### Evrak Kayıt Defteri

Gelen ve giden evrakın kaydı. Alanlar: Tarih \*, Sayı, Konu \*, Tür \* (Gelen / Giden) ve Dosya Yolu.
Liste yeniden eskiye sıralanır.

### Ayarlar ve Mevzuat Parametreleri

Beş sekmesi vardır: Kurum Bilgileri, Mevzuat Parametreleri, Veri ve Yedekleme, Kullanıcılar ve İşlem
Günlüğü. Kullanıcı hesapları açıksa ilk iki sekmeyi yalnızca **Yönetici** değiştirebilir; diğer roller
değerleri görür.

**"Kurum Bilgileri" sekmesi**

- Kurum türü, büyükşehir durumu, Kurum Adı, Kurum Kodu, İl, İlçe, müdür, koordinatör müdür yardımcısı,
  SGK işyeri sicil no, adres, telefon, e-posta, eğitim-öğretim yılı. Bu bilgiler bütün belgelere yazılır.
- **Kurum türü** Kurum Adı yazılırken kendiliğinden seçilir: Mesleki ve Teknik Anadolu Lisesi, Mesleki
  Eğitim Merkezi, Çok Programlı Anadolu Lisesi ya da MTAL ve MEM birlikte. Listeden elle seçerseniz seçiminiz
  korunur. Çok programlı Anadolu lisesi çerçeve program ve koordinatör saat sınırlarında MTAL gibi işlem görür.
- Kurum Adı ve Kodu kaydedilince program, türünüzün kullandığı e-Okul, e-Mesem ve SGK ekranlarını program
  içinde açmayı önerir (**"Sistemlerden verileri getir"** düğmesi de aynı işi yapar). Kurum kodu tek başına
  veri indirmez: listeler, bu sistemlere kendi şifrenizle girip indirdiğinizde gelir. Kayıtları ilgili
  ekranlardan elle de girebilirsiniz.
- **Ders Yılı Başlangıcı, 1. Dönem Sonu, Ders Yılı Sonu** (gg.aa.yyyy): Sözleşme imza süresi (md.143) ve
  puan çizelgelerinin dönem sonundan 5 gün önce teslimi (md.89/1-g, md.144/1-g) hatırlatmaları bu
  tarihlere göre yapılır. Her eğitim yılı başında güncelleyin.
- Lisans yüklüyse Kurum Adı ve Kurum Kodu lisanstan gelir ve değiştirilemez.
- **Kurum logosu:** "Logo Seç..." ile PNG veya JPG logo yükleyin (tercihen kare ve saydam zeminli). Logo
  Word belgelerinin ve PDF raporların başına basılır. Logo veritabanında saklandığından ağdaki bütün
  bilgisayarlar aynı logoyu kullanır.

**"Mevzuat Parametreleri" sekmesi**

- Bütün sayısal değerler dayanaklarıyla listelenir. Yalnızca **"Değer"** sütunu düzenlenir; sonra
  "Kaydet"'e basın. Ondalık için virgül kullanabilirsiniz. Evet/hayır değerlerinde 1 = evet, 0 = hayır.
- "Varsayılanlara Dön" bütün değerleri programın varsayılanlarına döndürür.
- Gruplar:
  - Asgari Ücret
  - Öğrenci Ücreti ve Devlet Katkısı
  - SGK Sigorta
  - Ek Ders
  - Koordinatörlük (koordinatör başına azami 15 öğrenci dâhil)
  - İşletmelerde Mesleki Eğitim (usta öğretici başına 16 öğrenci, eğitim birimi eşiği 10, sözleşme ve
    eğitim planı süreleri, puan çizelgesi teslim süresi)
  - Ders Programı
  - Devamsızlık

Her yıl **Ocak**'ta asgari ücreti, **Ocak ve Temmuz**'da memur aylık katsayısını, eğitim yılı başında da
**3308 Geçici 12. madde** durumunu kontrol edin. Uygulama sona ermişse "3308 Geçici 12. madde (devlet
katkısı) uygulanıyor" değerini 0 yapın; hesaplar md. 25'e göre yapılır.

**"Veri ve Yedekleme" sekmesi**

- Veritabanı, çıktı, şablon ve yedek klasörlerinin yerleri. "Veri Klasörünü Aç" düğmesi.
- **"Şimdi Yedekle"** ve **"Yedekten Geri Yükle..."** (bkz. bölüm 10).
- **Otomatik yedek:** "Otomatik yedek al" kutusu, yedek sıklığı (6 saatte bir, 12 saatte bir, günde bir,
  haftada bir) ve **ikinci yedek klasörü** (bkz. bölüm 10).
- "Örnek Veri Yükle (mevcut veriler silinir)": yalnızca deneme için.
- Geri yükleme ve örnek veri yükleme yalnızca Yönetici içindir.

**"Kullanıcılar" sekmesi**

Kişisel kullanıcı hesaplarını açar ve yönetir. Ayrıntılı anlatım bölüm 9'dadır ("Kişisel kullanıcı
hesapları").

**"İşlem Günlüğü" sekmesi**

Kim, hangi bilgisayardan, ne zaman, hangi kaydı **ekledi, değiştirdi ya da sildi**; değişiklikte hangi
alanın eski ve yeni değeri neydi.

- Üstten tarih aralığını ve kullanıcıyı seçin, isterseniz arama kutusuna öğrenci, işletme ya da kayıt türü
  yazın; "Listele"ye basın. "Excel'e Aktar" listeyi dosyaya alır.
- T.C. kimlik no, IBAN, telefon, adres, e-posta, doğum tarihi ile öğrencinin öncelik ve disiplin bilgileri
  günlüğe **\*\*\*** olarak yazılır; yalnızca değiştiği görünür.
- Günlük program içinden değiştirilemez ve silinemez. Son **2 yılın** kayıtları saklanır.
- Kullanıcı hesapları açıksa günlüğü yalnızca Yönetici görür.

### Çok Kullanıcılı Çalışma (Ağ)

Bu bilgisayarın tek başına mı, sunucu olarak mı, yoksa ağdaki sunucuya bağlanarak mı çalışacağı burada
seçilir. Ayrıntılı anlatım bölüm 9'dadır.

## 7. Asistan komutları

Komutlar büyük-küçük harf ve Türkçe karakter fark etmeksizin anlaşılır. Ay adı yazılmazsa geçmiş dönemi
ilgilendiren işler (SGK, ücret, dekont) **önceki ay** için yapılır. Yılı yazılmayan ay, içinde bulunulan
eğitim yılına göre yorumlanır: eylül–aralık eğitim yılının ilk yılı, ocak–haziran ikinci yılı sayılır.
"geçen ay", "bu ay", "gelecek ay" ifadeleri de anlaşılır.

| Yazılan (örnek)                                   | Sonuç                                                                              |
| ------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `yardım`                                          | Bütün komutlar tıklanabilir liste hâlinde                                          |
| `bugün ne yapmalıyım` · `gündem` · `özet`         | Uyarılar ve önerilen adımlar                                                       |
| `denetim`                                         | Veri denetimi; ilk 15 bulgu "düzelt" bağlantılarıyla                               |
| `geçen ayın kapanışını hazırla` · `ekim kapanış`  | Aylık kapanış klasörü (bölüm 8)                                                    |
| `ekim sgk listesi`                                | O ayın SGK prim hizmet listesi                                                     |
| `sgk bildirimleri` · `işe giriş`                  | Bekleyen SGK giriş/çıkış listesi                                                   |
| `sgk ceza riskleri` · `sgk hataları`              | SGK ceza ve hatalı bildirim riskleri, öneri ve tahmini cezalarla                   |
| `sgk listesi karşılaştır`                         | SGK listesini okul kayıtlarıyla karşılaştırma ekranını açar                        |
| `ücret hesapla`                                   | Ücret ve devlet katkısı: dönem kaydedilir, Excel ve işletme yazıları üretilir      |
| `dekontlar`                                       | Dekont takip listesi                                                               |
| `ek ders puantajı`                                | Ek ders puantajı (ayın 20'sinden sonra o ay, öncesinde önceki ay)                  |
| `devamsızlık`                                     | Devamsızlık özeti                                                                  |
| `veli bildirimleri`                               | Sınırı aşan öğrencilerin velilerine yazılar                                        |
| `ziyaret planı kasım`                             | Aylık ziyaret planı                                                                |
| `koordinatör görevlendir`                         | Görevleri yeniden dağıtır (onay ister)                                             |
| `görevlendirme yazıları`                          | Görevlendirme yazıları                                                             |
| `işletmelere bildir`                              | Koordinatör isimlerini işletmelere bildiren yazılar (md.88/1)                      |
| `komisyon kararı`                                 | Koordinatörlük planlama komisyonu kararı (md.88/2-b)                               |
| `yönetmelik görevleri`                            | Koordinatör müdür yardımcısının yönetmelikten gelen işleri (süreç listesi)         |
| `öğrenci seçimi`                                  | Öğrenci seçim/sıralama ekranı (md.136)                                             |
| `uygunluk tutanakları`                            | Tespiti girilmemiş işletmeler için uygunluk tutanakları (md.142)                   |
| `puan çizelgesi`                                  | Dönemlere göre son teslim günü ve notu eksik öğrenci sayısı                        |
| `alan taraması` · `anket` · `hizmetiçi eğitim`    | Alan taraması özeti, anket değerlendirmesi, hizmetiçi eğitim programı (Excel)      |
| `zorunlu dersleri aç` · `çerçeve programı`        | Çerçeve öğretim programındaki zorunlu dersleri bütün sınıflara açar (onay ister)   |
| `programı oluştur`                                | Ders programı ve atölye yerleşimi (onay ister)                                     |
| `sözleşmeleri hazırla` · `değerlendirme formları` | Belgeler                                                                           |
| `yedek al`                                        | Veritabanı yedeği                                                                  |
| `yıl başı` · `aylık süreç` · `yıl sonu`           | Süreç kontrol listeleri                                                            |
| `yıl sonu 26.06.2027`                             | Bütün aktif yerleştirmeleri o tarihte sona erdirir (onay ister)                    |
| `yeni eğitim yılı`                                | Sınıf atlatma, mezunları pasife alma, görevleri sıfırlama (önce yedek, onay ister) |
| `dosya aktar`                                     | Veri Aktarımı ekranını açar                                                        |
| `parametreler` · `asgari ücret`                   | Temel parametreleri gösterir, Ayarlar'ı açar                                       |
| `istatistik`                                      | Öğrenci, işletme, öğretmen, sınıf sayıları                                         |
| `12-A` · `Ahmet Yılmaz` · işletme adı · T.C.      | Sınıf, öğrenci, öğretmen veya işletme kartı                                        |

**Bilgi kartlarında ne var?**

- **Öğrenci:** sınıf, statü, T.C., veli, yerleştirmeler (sözleşme no, SGK giriş durumu, usta öğretici,
  koordinatör), devamsızlık, notlar.
- **Öğretmen:** haftalık ders, aylık karşılık, azami ek ders, koordinatörlükler, bu ayın ek dersi.
- **İşletme:** yetkili, personel, usta öğretici, öğrenciler ve kontenjan, koordinatör, son ziyaretler.
- **Sınıf:** program, alan, rehber öğretmen, günler, öğrenciler ve işletmeleri.

## 8. Yıl boyu süreçler ve aylık kapanış

### Eğitim yılı başlangıcı (Eylül)

1. Kurum bilgileri
2. Mevzuat parametreleri (asgari ücret, katsayı)
3. Eğitim yılı tatil günleri
4. Öğretmen listesi
5. Öğrenci listesi (e-Okul)
6. İşletme listesi ve bilgileri (personel sayısı, usta öğretici)
7. İşletme uygunluk tespiti (md.140-142)
8. Ders dağılımı (çerçeve öğretim programına göre; bütün sınıflarda zorunlu dersler açık mı)
9. Ders programı ve atölye yerleşimi
10. Öğrencilerin işletmelere yerleştirilmesi
11. Sınıfların işletme günleri
12. Sözleşmeler
13. SGK işe giriş bildirgeleri
14. Koordinatör öğretmen görevlendirmesi
15. Görevlendirme yazıları
16. Koordinatörlerin işletmelere bildirimi (md.88/1)
17. Bu ayın ziyaret planı

### Koordinatör müdür yardımcısı görevleri (Yönetmelik)

Asistan > Süreçler listesindeki bu süreç, Ortaöğretim Kurumları Yönetmeliğinin 82, 88, 89 ve 134-153 üncü
maddelerinden gelen işleri yıl boyunca izler: ders yılı ve dönem tarihleri, işletme uygunluk tespiti,
öğrenci seçimi (md.136), sözleşmeler (md.143), koordinatörlük planlaması ve komisyon kararı, isimlerin
işletmelere bildirimi, usta öğretici eğitim planlarının onayı (md.146), hizmetiçi eğitim programı,
puan çizelgeleri, mezun/işyeri anketleri ve alan taraması. Her adımın durumu kendiliğinden denetlenir ve
tek tıkla çalıştırılabilir.

### Aylık işlemler

1. Devamsızlıkların işlenmesi
2. Ziyaret sonuçlarının girilmesi
3. SGK aylık prim hizmet listesi (MUHSGK son günü gösterilir)
4. SGK giriş/çıkış bildirimleri
5. Ücret ve devlet katkısı hesabı
6. Dekontların toplanması
7. Ek ders puantajı (KBS'ye girişten önce kontrol edin)
8. Veli devamsızlık bildirimleri
9. Gelecek ayın ziyaret planı
10. Veritabanı yedeği (son yedek 7 günden eskiyse uyarır)

### Aylık kapanış

Asistan'a `geçen ayın kapanışını hazırla` yazmanız ya da **Süreçler** sekmesinde "Aylık Kapanışı Hazırla"
düğmesine basmanız yeterlidir. Bütün çıktılar tek klasörde toplanır:
`Ciktilar\Aylık Kapanış\<YYYY-AA Ay>\`

| Dosya                                     | İçerik                                                        |
| ----------------------------------------- | ------------------------------------------------------------- |
| `0 Kapanış Özeti.txt`                     | Özet ve yasal süreler (dekont, devlet katkısı girişi, MUHSGK) |
| `1 SGK Prim Hizmet Listesi <Ay Yıl>.xlsx` | e-Bildirge'ye girilecek liste                                 |
| `2 Ücret ve Devlet Katkısı <Ay Yıl>.xlsx` | Öğrenci listesi ve işletme özeti                              |
| `İşletme Ücret Yazıları\`                 | Her işletmeye ücret yazısı                                    |
| `3 Dekont Takibi <Ay Yıl>.xlsx`           | Dekont durumu                                                 |
| `4 Ek Ders Puantajı <Ay Yıl>.xlsx`        | Puantaj çizelgesi                                             |
| `5 Devamsızlık Özeti.xlsx`                | Devamsızlık durumu                                            |
| `Veli Bildirimleri\`                      | Sınırı aşanların velilerine yazılar                           |
| `6 Bekleyen SGK Bildirimleri.xlsx`        | Giriş/çıkış bildirimleri                                      |
| `7 Ziyaret Planı <Sonraki Ay Yıl>.xlsx`   | Gelecek ayın ziyaret planı                                    |

Kapanış sırasında veritabanı yedeği de alınır. Bir adımda hata olursa diğer adımlar yine çalışır; özette
✓ / ✗ ile gösterilir.

### Yıl sonu ve yeni yıla geçiş (Haziran)

1. İşletmede mesleki eğitim notları (2. dönem): değerlendirme formları.
2. Son ayın kapanışı.
3. Yerleştirmelerin sona erdirilmesi:
   - Önce tarih sorulur; bütün aktif yerleştirmeler o tarihte sona erer.
   - Koordinatörlük görevlerine aynı bitiş tarihi yazılır.
   - Sonraki planlı ziyaretler silinir.
4. SGK işten ayrılış bildirgeleri.
5. Veritabanı yedeği.
6. Yeni eğitim yılına geçiş (yeni yıl başında **bir kez** çalıştırın):
   - Öğrenciler üst sınıfa geçirilir (11-A → 12-A).
   - 12. sınıflar mezun yapılır.
   - Koordinatörlük görevleri silinir.
   - Eğitim yılı bir ileri alınır.
   - İşlemden önce yedek alınır.

## 9. Okuldaki birden çok bilgisayarda çalışma

Okuldaki bir bilgisayar **sunucu** olur; veriler yalnızca onda durur. Diğer bilgisayarlar okul ağı
üzerinden ona bağlanır. Herkes aynı anda çalışır; birinin kaydettiği değişiklik diğer bilgisayarların açık
ekranlarında hemen görünür ve durum çubuğunda "Güncellendi: Ayşe değişiklik yaptı" yazar.

### Sunucuyu kurmak

1. Bütün bilgisayarlara **aynı sürüm** MesKoord kurulur.
2. Verilerin duracağı bilgisayarda (genellikle koordinatör müdür yardımcısının bilgisayarı) işlemleri
   yapın:
   - **Çok Kullanıcılı Çalışma (Ağ)** ekranını açın.
   - **"Sunucu olsun (veriler bu bilgisayarda; diğer bilgisayarlar buna bağlanır)"** seçeneğini seçin.
   - "Sunucunun görünen adı" alanını kontrol edin.
   - En az 6 karakterli bir **sunucu parolası** iki kez yazın.
   - **"Kaydet ve Programı Yeniden Başlat"** düğmesine basın.
3. Program yeniden açılınca aynı ekranda bu bilgisayarın **adresi** ve **doğrulama kodu** görünür. Bunları
   diğer bilgisayarlarda kullanacaksınız.
4. Lisansı yalnızca sunucuya yüklemeniz yeterlidir.

### Diğer bilgisayarları bağlamak

1. **Çok Kullanıcılı Çalışma (Ağ)** ekranında **"Ağdaki sunucuya bağlansın (verileri sunucudan
   kullanır)"** seçeneğini seçin.
2. **"Ağdaki Sunucuları Bul"**'a basıp listeden sunucuyu seçin; bulunamazsa sunucunun adresini elle yazın
   (ör. 192.168.1.20).
3. **"Adınız"** alanına diğer kullanıcılara görünecek adınızı yazın. **Sunucu parolasını** girin. İsterseniz
   "Parolayı bu Windows hesabında şifreli olarak hatırla" kutusunu işaretleyin. Sunucuda kişisel kullanıcı
   hesapları açıksa alanların adı **"Kullanıcı adınız"** ve **"Parolanız"** olur: okulun size verdiği
   kullanıcı adını ve kendi parolanızı yazın (kişisel parola hatırlanmaz).
4. **"Bağlantıyı Sına"**'ya basın. "Sunucunun kimliğini doğrulayın" penceresinde görünen kod, sunucu
   ekranındaki doğrulama koduyla **aynıysa** Evet deyin. Farklıysa bağlanmayın ve bilişim sorumlusuna
   haber verin.
5. **"Kaydet ve Programı Yeniden Başlat"**.

Bu bilgisayarda daha önce veri girildiyse, o veriler silinmez ama kullanılmaz. Gerekiyorsa önce
_Ayarlar > Veri ve Yedekleme > Şimdi Yedekle_ ile yedek alın, sonra sunucuda "Yedekten Geri Yükle..." ile
yükleyin.

### Günlük çalışmada bilinmesi gerekenler

- **Kimler bağlı?** Durum çubuğundaki ağ yazısının üzerine gelin ya da ağ ekranındaki tabloya bakın.
- **Aynı kaydı iki kişi düzenlerse:** farklı alanlar birleştirilir; aynı alan için size sorulur.
- **Bağlantı koparsa:** durum çubuğunda kırmızıyla "bağlantı yok — yeniden deneniyor" yazar. Bağlantı
  gelince program kendiliğinden yeniden bağlanır. O sırada kaydetmeye çalıştığınız işlemi bağlantı
  gelince yeniden yapın.
- **Sunucu bilgisayarı açık ve MesKoord orada çalışır durumda olmalıdır.** Sunucuyu kapatmadan önce diğer
  kullanıcılara haber verin; Güvenli Çıkış penceresi kimlerin bağlı olduğunu gösterir.
- Sunucu bilgisayarının **uyku moduna geçmemesi** ve mümkünse **sabit IP adresi** olması önerilir.
- Bağlantı şifrelidir ve okulun ağından dışarı çıkmaz. Sunucu internete açılmamalıdır.
- `meskoord.db` dosyasını ağ paylaşımına koyup iki bilgisayardan açmayın; veri bozulabilir. Her zaman bu
  ekrandaki sunucu/istemci yöntemini kullanın.

### Sunucunun arka planda çalışması

Sunucu bilgisayarının ağ ekranında iki seçenek vardır:

- **"Pencere kapatılınca sistem tepsisinde çalışmayı sürdür"** (önerilen, varsayılan olarak açık): sunucuyu
  kullanan kişi pencereyi kapatsa da MesKoord saatin yanındaki tepside çalışmayı sürdürür, diğer
  bilgisayarların bağlantısı kesilmez. Tepsi simgesine çift tıklamak pencereyi yeniden açar; simgenin
  üzerinde bağlantı durumu ve çevrim içi kullanıcı sayısı yazar. Programı tamamen kapatmak için simgeye sağ
  tıklayıp **"Güvenli Çıkış"**ı seçin.
- **"Windows oturumu açılınca MesKoord'u arka planda başlat"**: bilgisayar açılıp Windows oturumu açılınca
  MesKoord pencere göstermeden tepside başlar, sunucu kendiliğinden hizmete girer. Sabah sunucuyu açmayı
  unutma sorunu ortadan kalkar. Kullanıcı hesapları açıksa pencere tepsiden açılırken kullanıcı adı ve
  parola sorulur.

MesKoord ikinci kez açılmak istenirse yeni bir kopya başlamaz; çalışan pencere öne gelir.

### Kişisel kullanıcı hesapları

Hesaplar **isteğe bağlıdır**. Açılmazsa program eskisi gibi çalışır: bilgisayarı kullanan herkes bütün
işlemleri yapabilir; işlem günlüğünde Windows kullanıcı adı ya da bağlanırken yazılan ad görünür. Okulda
birden çok kişi çalışıyorsa hesapların açılması önerilir.

**Roller**

| Rol         | Yapabildikleri                                                                                                                                                       |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Yönetici    | Bütün işlemler: kullanıcı hesapları, kurum bilgileri, mevzuat parametreleri, yedekten geri yükleme, işlem günlüğü                                                    |
| Personel    | Bütün veri girişleri, aktarım, hesaplar ve belge üretimi. Kullanıcı hesaplarını, kurum bilgilerini ve mevzuat parametrelerini değiştiremez; yedekten geri yükleyemez |
| Salt okunur | Ekranları görür, listeleri ve belgeleri dosyaya alır; hiçbir kaydı değiştiremez (ör. okul müdürü, denetim)                                                           |

Yetkisi olmayan bir işlem denendiğinde "Bu işlem için yetkiniz yok." uyarısı çıkar ve hiçbir şey
değişmez.

**Hesapları açmak (bir kez, sunucu bilgisayarında ya da tek bilgisayarda):**

1. _Ayarlar > Kullanıcılar_ sekmesinde **"Kullanıcı Hesaplarını Aç..."** düğmesine basın.
2. Kendi adınızı, kullanıcı adınızı (ör. `ayse.yilmaz`) ve en az 6 karakterli parolanızı yazın. Bu ilk hesap
   **Yönetici** olur.
3. **"Yeni Kullanıcı..."** ile diğer personeli ekleyin: ad soyad, kullanıcı adı, rol ve geçici parola. "İlk
   girişte kendi parolasını belirlesin" işaretliyse kişi ilk girişte kendi parolasını seçer.
4. Kullanıcı adlarını ve geçici parolaları kişilere ayrı ayrı iletin.

Bundan sonra program açılışta kullanıcı adı ve parola sorar. Ağdaki bilgisayarlar da bir sonraki
bağlanışta sunucu parolası yerine kişisel giriş ister.

**Günlük işler:**

- **Parolamı değiştirmek:** Dosya > "Parolamı Değiştir..." ya da durum çubuğundaki kullanıcı adına tıklayın.
- **Bilgisayardan kalkarken / başkası çalışacakken:** Dosya > "Kullanıcı Değiştir (Oturumu Kapat)".
  Program yeniden açılır ve giriş sorar.
- **Parolasını unutan personel:** Yönetici, _Ayarlar > Kullanıcılar_'da kişiyi seçip **"Parolasını
  Sıfırla..."** ile geçici parola verir.
- **Görev değişikliği:** "Düzenle..." ile rolü değiştirin.
- **Okuldan ayrılan personel:** "Düzenle..." ile hesabı **pasifleştirin** ("Hesap etkin" kutusunu
  kaldırın). Hesap silinmez; geçmiş işlemleri işlem günlüğünde adıyla kalır.
- En az bir etkin Yönetici hesabı her zaman kalır; program son yöneticinin pasifleştirilmesine ya da rolünün
  düşürülmesine izin vermez. Yönetici parolasını unutmamak için okulda **iki Yönetici** hesabı olması
  önerilir.
- **"Hesapları Kapat..."** bütün hesapları pasifleştirir ve programı hesapsız çalışmaya döndürür.

## 10. Yedekleme ve verilerin korunması

- **Elle yedek:** Dosya > "Şimdi Yedekle" ya da _Ayarlar > Veri ve Yedekleme > Şimdi Yedekle_. Asistan'a
  `yedek al` yazmak da olur.
- **Kendiliğinden alınan yedekler:**
  - Toplu kayıttan önce
  - Veri aktarımından önce
  - Geri yüklemeden önce
  - Örnek veri yüklemeden önce
  - Yerleştirmeleri sona erdirmeden ve yeni eğitim yılına geçişten önce
  - Aylık kapanışta
  - İsterseniz her Güvenli Çıkış'ta
  - **Zamanlanmış otomatik yedek:** program açıkken (sunucu tepside çalışırken de) seçilen sıklıkta;
    varsayılan günde bir
- Yedekler `Belgeler\MesKoord\Yedekler` klasöründe tarih-saat adıyla (`meskoord_YYYYAAGG_SSDDss.db`)
  durur. Otomatik yedeklerin en yeni 100 tanesi saklanır.
- **Otomatik yedek ayarları:** _Ayarlar > Veri ve Yedekleme_ sekmesinde "Otomatik yedek al" kutusu ve
  sıklığı. Bu ayar veritabanının durduğu bilgisayarda (tek bilgisayar ya da sunucu) yapılır; ağa bağlı
  bilgisayarlarda gerekmez.
- **İkinci yedek klasörü:** "Seç..." ile bir USB bellek ya da okulun güvenli ağ klasörü seçilirse her
  otomatik yedeğin bir kopyası oradaki `MesKoord_Yedekler` klasörüne de alınır (en yeni 30 kopya
  saklanır). Kopyalanamazsa (ör. USB takılı değil) sekmede kırmızı uyarı görünür; yedek yine de asıl
  klasöre alınmıştır.
- **Ağda:** İstemci bilgisayarda "Şimdi Yedekle" sunucuda yedek alır; Yönetici ise ayrıca bir kopyasını
  kendi `Yedekler` klasörüne indirir. Diğer rollerde yedek yalnızca sunucuda kalır.
- **Geri yükleme:** _Ayarlar > Veri ve Yedekleme > Yedekten Geri Yükle..._ ile yedeği seçin. Mevcut durum
  önce yedeklenir. Ağda geri yükleme bütün kullanıcıların verisini değiştirir. Kullanıcı hesapları açıksa
  yalnızca Yönetici geri yükleyebilir.
- **Önerilen alışkanlık:** İkinci yedek klasörünü ayarlayın ya da ayda en az bir kez `Yedekler`
  klasöründeki en yeni dosyayı bir USB belleğe kopyalayın. Bilgisayar arızasına karşı tek koruma budur.
- **Bilgisayar değiştirirken:** Eski bilgisayardaki `Belgeler\MesKoord` klasörünün tamamını yenisine
  kopyalayın ve programı kurun.

## 11. Hesaplamalar nasıl yapılıyor?

Aşağıdaki değerlerin hepsi _Ayarlar > Mevzuat Parametreleri_ ekranından değiştirilebilir; parantez içinde
varsayılanlar yazılıdır.

### Öğrenci ücreti

Yasal alt sınır, **net asgari ücret × oran** olarak hesaplanır. Oran, aşağıdaki kurallardan **ilk uyan**
ile belirlenir:

1. Statü "Kalfa (MEM 12)" ise kalfa oranı (%50).
2. 3308 Geçici 12. madde uygulanıyorsa Geçici 12 oranı (%30).
3. MEM öğrencisi, aday çırak ya da çırak ise çırak oranı (%30).
4. İşletmede 20 ve üzeri personel varsa %30, 20'den az personel varsa %15 (md. 25).

Sözleşmede daha yüksek bir ücret yazılıysa o tutar esas alınır. Ay içinde başlayan ya da biten öğrencide
ücret gün sayısına (30 gün esası) orantılanır.

### Devlet katkısı

- Kamu kurumu işletmelerde ve Geçici 12. madde uygulanmıyorsa ödenmez.
- MEM programında katkı tamdır.
- Diğer programlarda 20'den az personelli işletmede üçte iki, 20 ve üzeri personelli işletmede üçte bir
  oranında ödenir.

### SGK prim hizmet listesi

- **Prime esas kazanç:** brüt asgari ücret × %50 / 30 × prim günü.
- **Prim oranı ve belge türü:**
  - Bakmakla yükümlü olunan öğrencide %1; belge 7 (işletme/staj) ya da 49 (okulda alan/tamamlayıcı eğitim).
  - Bakmakla yükümlü olunmayan öğrencide %6; belge 42 ya da 50.
- **Prim günü:** Tam ayda 30 gündür. Ay içinde başlayan veya bitenlerde takvim günü sayılır. SGK'ya eksik
  gün olarak bildirilecek devamsızlıklar düşülür.
- **Eksik gün kodları:** özürsüz 15, raporlu 01, özürlü/izinli 21. Birden çok neden varsa 12.
- **Süreler:**
  - İşe giriş bildirgesi sigortalılıktan önce verilir.
  - İşten ayrılış bildirgesi 10 gün içinde verilir.
  - Beyan izleyen ayın 26'sına kadar yapılır.
- **SGK dosyaları:** e-Bildirge V2 XML'inde ad ve soyad en çok 18, işyeri ünvanı ve adresi en çok 50
  karakterdir; daha uzunları kısaltılır ve uyarı verilir. Prime esas kazanç noktalı ondalıkla, giriş ve çıkış
  günleri GGAA biçiminde yazılır. Aylık kapanış da aynı dönemin XML ve Excel dosyalarını "SGK e-Bildirge"
  klasörüne koyar.

### Ek ders

- Gündüz saat ücreti: 140 × memur aylık katsayısı. Gece saat ücreti 150 gösterge üzerinden hesaplanır.
- Aylık karşılığı ders: öğretmen 15, atölye/laboratuvar öğretmeni 20, yönetici 6. Öğretmen kartında farklı
  değer yazılıysa o geçerlidir.
- Programdaki dersler ve koordinatörlük önce aylık karşılığı doldurur, kalanı ek derstir.

### Koordinatörlük

- **Haftalık azami saat:**
  - MEM büyükşehirde 24, diğer yerlerde 18.
  - Diğer okullar büyükşehirde 20, diğer yerlerde 16.
- **Günlük azami:** 8 saat.
- **İşletme başına saat:** 1 saat taban, her 5 öğrenci için +1, 10 km'den uzaksa +1.
- **Grup:** Bir koordinatöre aynı işletmede en çok **15 öğrenci** verilir (md.88/2-f). Öğrenciler işletme ve
  alana göre gruplanır; 15'i aşan gruplar bölünür ve her parçaya ayrı koordinatör atanır.
- **Öncelik:** Önce öğrencinin alanındaki öğretmenler, bunlar arasında atölye/laboratuvar öğretmenleri
  seçilir (md.88/2-e). Alanda uygun öğretmen yoksa başka alandan öğretmen atanır ve raporda belirtilir.
- **Kapsam dışı:** Döner sermaye kapsamındaki işletmelere (md.88/8) ve il dışında staj yapan öğrencilere
  (md.88/2-g) koordinatör atanmaz.

### Devamsızlık

- Özürsüz devamsızlık sınırı 10 gün, toplam devamsızlık sınırı 30 gün.
- Özürsüz devamsızlık 5 güne ulaşınca veliye yazılı bildirim önerilir.

## 12. Belge şablonlarını düzenlemek

Sözleşme, görevlendirme yazısı, ziyaret formu, veli bildirimi ve ücret yazısı `Belgeler\MesKoord\Sablonlar`
klasöründeki Word dosyalarından üretilir. Şablonları kurumunuzun ya da MEB'in resmî biçimine göre
düzenleyebilirsiniz.

1. **Belge Üretimi** ekranında belge türünü seçip **"Şablonu Word'de Aç"**'a basın.
2. Metni ve biçimi değiştirin. **`{{...}}`** biçimindeki yer tutucular belge üretilirken doldurulur;
   bunları silmeyin ya da adlarını değiştirmeyin.
3. Kaydedip Word'ü kapatın. Sonraki üretimde yeni şablon kullanılır.

Bir şablonu bozarsanız dosyayı silin; program onu varsayılan hâliyle yeniden oluşturur. Bütün şablonları
sıfırlamak için **"Şablonları Varsayılana Döndür"** düğmesini kullanın (yaptığınız değişiklikler kaybolur).

**Sık kullanılan yer tutucular:**

| Yer tutucu                                                                                                      | Değeri                                                                          |
| --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `{{kurum_logosu}}`                                                                                              | Kurum logosu (tek başına bir paragrafta olmalı; logo yoksa paragraf kaldırılır) |
| `{{kurum_adi}}`, `{{kurum_il}}`, `{{kurum_ilce}}`, `{{kurum_kodu}}`                                             | Kurum bilgileri                                                                 |
| `{{mudur}}`, `{{koordinator_mudur_yrd}}`, `{{egitim_yili}}`, `{{bugun}}`                                        | İmza ve tarih bilgileri                                                         |
| `{{ogrenci_ad_soyad}}`, `{{ogrenci_tc}}`, `{{ogrenci_no}}`, `{{sinif}}`, `{{alan}}`, `{{dal}}`                  | Öğrenci                                                                         |
| `{{veli_ad}}`, `{{veli_tel}}`                                                                                   | Veli                                                                            |
| `{{isletme_adi}}`, `{{isletme_adres}}`, `{{isletme_yetkili}}`, `{{usta_ogretici}}`, `{{personel_sayisi}}`       | İşletme                                                                         |
| `{{baslangic}}`, `{{bitis}}`, `{{sozlesme_no}}`, `{{sozlesme_tarihi}}`, `{{egitim_gunleri}}`, `{{koordinator}}` | Sözleşme                                                                        |
| `{{ucret}}`, `{{en_az_ucret}}`                                                                                  | Sözleşme ücreti / yasal alt sınır                                               |
| `{{ogretmen_ad_soyad}}`, `{{gorev_listesi}}`, `{{haftalik_toplam}}`                                             | Görevlendirme yazısı                                                            |
| `{{ziyaret_tarihi}}`, `{{ogrenci_listesi}}`, `{{tespitler}}`, `{{oneriler}}`                                    | Ziyaret formu                                                                   |
| `{{okul_ozursuz}}`, `{{isletme_ozursuz}}`, `{{devamsizlik_toplam}}`, `{{sinir_ozursuz}}`                        | Veli bildirimi                                                                  |
| `{{donem}}`, `{{toplam_ucret}}`, `{{toplam_dk}}`, `{{dekont_son_gun}}`                                          | İşletmeye ücret yazısı                                                          |

## 13. Sık sorulan sorular ve sorun giderme

**Program açılırken "Sunucuya bağlanılamadı" diyor.**
Şunları kontrol edin:

- Sunucu bilgisayarı açık mı ve MesKoord orada çalışıyor mu?
- İki bilgisayar aynı ağda mı?
- Sunucunun adresi değişmiş olabilir; ağ ekranında "Ağdaki Sunucuları Bul" ile yeniden seçin.

"Yeniden Dene" ile tekrar deneyebilirsiniz. "Bu Bilgisayarın Verisiyle Aç" seçilirse o oturumda yapılan
değişiklikler sunucuya **gitmez**; bunu yalnızca zorunlu durumlarda kullanın.

**"Sunucunun kimlik sertifikası değişmiş" uyarısı çıktı.**
Sunucu başka bir bilgisayara taşındıysa ya da yeniden kurulduysa normaldir. Yeni kodu sunucu ekranındaki
doğrulama koduyla karşılaştırıp onaylayın. Böyle bir değişiklik yapılmadıysa bağlanmayın ve bilişim
sorumlusuna haber verin.

**"Sunucudaki MesKoord sürümü ..., bu bilgisayardaki ..." uyarısı çıktı.**
Ağdaki bütün bilgisayarlarda aynı sürüm olmalıdır. Önce sunucuyu, sonra diğerlerini güncelleyin.

**"Veritabanı meşgul" uyarısı çıktı.**
Başka bir kullanıcı ya da uzun bir işlem (ör. aylık kapanış) o sırada yazıyordur. Biraz sonra yeniden deneyin.

**"Bu işlem için yetkiniz yok" uyarısı çıktı.**
Kullanıcı hesapları açık ve rolünüz bu işleme izin vermiyor. Gerekiyorsa okuldaki Yönetici hesabı
sahibinden rolünüzü değiştirmesini isteyin. Girişteki hesabınız durum çubuğunda yazar.

**Parolamı unuttum.**
Okuldaki Yönetici hesabı sahibi _Ayarlar > Kullanıcılar_'da "Parolasını Sıfırla..." ile size geçici parola
verir. Okuldaki bütün Yönetici parolaları unutulduysa bilişim sorumlusuna başvurun (geliştirici el
kitabında anlatılır).

**Sunucu bilgisayarında pencereyi kapattım ama program kapanmadı.**
Bilerek böyledir: diğer bilgisayarların bağlantısı kesilmesin diye program saatin yanındaki tepside
çalışır. Kapatmak için tepsi simgesine sağ tıklayıp "Güvenli Çıkış"ı seçin.

**Kurum adını değiştiremiyorum.**
Lisanslı kurumlarda kurum adı ve kodu lisansa kilitlidir. Ad yanlışsa lisans verenden düzeltilmiş lisans isteyin.

**Hesaplanan ücret ya da SGK tutarı yanlış görünüyor.**
Sırayla şunları kontrol edin:

1. _Mevzuat Parametreleri_ güncel mi (asgari ücret, Geçici 12. madde)?
2. Öğrencinin programı, statüsü ve "Bakmakla yükümlü" işareti doğru mu?
3. Yerleştirmenin başlangıç ve bitiş tarihleri doğru mu?
4. İşletmenin personel sayısı ve "Kamu kurumu" işareti doğru mu?

**Excel listemi Veri Aktarımı tanımadı.**
Başlık satırını ("Başlık satırı:") ve veri türünü elle seçin, eşleme tablosunda sütunları eşleyin. Ya da
"Seçili Tür İçin Boş Şablon" ile şablon alıp verileri ona kopyalayın.

**PDF'teki tablo okunmadı.**
Taranmış (resim) PDF'lerden metin okunamaz. Aynı listenin Excel ya da metin içeren PDF hâlini kullanın.

**SGK işe giriş/çıkış sayfası program içinde açılmıyor.**
Sekmedeki "Edge/Chrome'da Aç" düğmesini kullanın. "Edge/Chrome ile indirilen Excel listelerini de al"
işaretliyse indirdiğiniz listeler yine aktarılır.

**e-Okul / SGK her açılışta yeniden giriş istiyor.**
Bilerek böyledir: güvenliğiniz için şifre ve oturum bilgisi saklanmaz.

**"Windows bilgisayarınızı korudu" uyarısı çıktı.**
"Ek bilgi" > "Yine de çalıştır" ile devam edebilirsiniz. Kurumunuzun bilişim sorumlusuna danışın.

**Yanlışlıkla veri sildim ya da yanlış aktarım yaptım.**
_Ayarlar > Veri ve Yedekleme > Yedekten Geri Yükle..._ ile işlemden hemen önceki tarihli yedeği seçin.

**Belge şablonu bozuldu.**
`Belgeler\MesKoord\Sablonlar` içindeki ilgili dosyayı silin ya da "Şablonları Varsayılana Döndür" düğmesini
kullanın.

**Destek isterken ne göndermeliyim?**

- Program sürümü (Yardım > Hakkında).
- Hatanın ekran görüntüsü.
- `Belgeler\MesKoord\hata_gunlugu.txt` dosyası.

Öğrenci bilgisi içeren veritabanını e-postayla göndermeyin.

## 14. Kısayollar ve klasörler

| Kısayol                                      | İşlevi                                 |
| -------------------------------------------- | -------------------------------------- |
| F1                                           | Kullanım kılavuzu                      |
| Ctrl+Q                                       | Güvenli Çıkış                          |
| Ctrl+K                                       | Menüde ara                             |
| Ctrl+B                                       | Menüyü daralt / genişlet               |
| Enter (Asistan)                              | Komutu gönderir                        |
| Çift tık (liste)                             | Kaydı düzenler                         |
| Çift tık (süreç adımı / denetim bulgusu)     | İşlemi çalıştırır / ilgili ekranı açar |
| Ctrl+V / Ctrl+C / Ctrl+D (Toplu Veri Girişi) | Yapıştır / kopyala / aşağı doldur      |
| Delete (Toplu Veri Girişi)                   | Seçili hücreleri temizler              |
| Sağ tık (ders programı)                      | Kilitle, kilidi aç, sil, ders ekle     |

Bütün klasörler `Belgeler\MesKoord` altındadır:

| Klasör / dosya        | İçerik                                                         |
| --------------------- | -------------------------------------------------------------- |
| `meskoord.db`         | Bütün veriler                                                  |
| `Ciktilar\`           | Üretilen Excel, Word ve PDF dosyaları (`Aylık Kapanış\` dahil) |
| `Sablonlar\`          | Word belge şablonları                                          |
| `Yedekler\`           | Yedekler                                                       |
| `Indirilenler\`       | e-Okul/e-Mesem/SGK ekranından indirilen listeler               |
| `Taslaklar\`          | Toplu Veri Girişi taslakları                                   |
| `yedek_ayarlari.json` | Otomatik yedek sıklığı ve ikinci yedek klasörü                 |
| `hata_gunlugu.txt`    | Beklenmeyen hataların ayrıntısı (destek için)                  |

## 15. Sınırlamalar

- Program e-Bildirge, MEBBİS, e-Okul veya KBS'ye **doğrudan veri göndermez**. SGK bildirimleri ve ek ders
  puantajı, ilgili sistemlere girilecek bilgileri içeren Excel listeleri olarak hazırlanır.
- Taranmış (resim) PDF'lerden metin okunamaz.
- Çok kullanıcılı çalışmada sunucu bilgisayarının açık olması gerekir.
- Hesaplamalar yardımcı niteliktedir; resmî işlemden önce güncel mevzuata göre kontrol edilmelidir.
