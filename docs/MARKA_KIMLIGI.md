# MesKoord Marka Kimliği Kılavuzu

## 1. Ad

| Kullanım | Metin |
|---|---|
| Ürün adı | **MesKoord** (M ve K büyük, bitişik; "MESKOORD" yalnızca büyük harfli başlıklarda) |
| ASCII yazım (dosya adları) | MesKoord (ör. `MesKoord_Kurulum_1.3.0.exe`) |
| Açıklama | Mesleki Eğitim Koordinasyon ve Yönetim Sistemi |
| Yayıncı / satıcı | `koordmes/__init__.py` → `APP_PUBLISHER` |

**Adın anlamı.** *MesKoord*, **Mes**leki **Koord**inasyon sözcüklerinin başlarından oluşur. Program, okulun
mesleki eğitim işlerini (işletmelerde mesleki eğitim, koordinatörlük, ders programı, SGK, ücret ve devlet katkısı)
okul, işletme ve öğrenci arasında koordine eder. Türkçe söylenişi kolaydır: "mes-kord". İki parçalı yazım,
logotipte iki renkle gösterilir. Türkçe ekler sondaki "d" sesine göre gelir: MesKoord'u, MesKoord'un,
MesKoord'a, MesKoord'da.

**Teknik ad.** 1.3.0'dan beri teknik adlar da MesKoord'dur: `MesKoord.exe`, `C:\Program Files\MesKoord`,
`Belgeler\MesKoord` veri klasörü, `C:\ProgramData\MesKoord` lisans klasörü, lisans dosyalarındaki ürün
tanıtıcısı, güvenlik duvarı kuralı, Windows açılış kaydı ve ağ keşif tanıtıcısı. Önceki ad KoordMES'ti; kurulum ve
program eski adlı klasör ve kayıtları kendiliğinden taşır, "KoordMES" ürün adıyla verilmiş lisansları ve ağ
tanıtıcısını tanımaya devam eder (`koordmes/config.py` → `ESKI_AD`). Kod paketinin adı (`koordmes`) yalnızca
geliştiricinin gördüğü bir ad olarak kalır. Kullanıcının gördüğü her yerde `koordmes/marka.py` → `URUN` kullanılır.

## 2. Simge

![MesKoord simgesi](../dagitim/marka/meskoord_simge_1024.png)

Yuvarlatılmış kare gece mavisi zemin üzerinde soluk bir **atölye dişlisi** mesleki eğitimi anlatır. Dişlinin
içinde kesintisiz tek bir çizgiyle çizilmiş bir **M** vardır:

- M'nin iki tepesindeki beyaz düğümler **okul** ve **işletme**dir.
- M'nin ortadaki çukurunda duran **turkuaz düğüm öğrencidir**. Çizgi iki tarafı onun üzerinden birbirine bağlar:
  koordinasyonun merkezinde öğrenci vardır.
- Turkuaz düğümün çevresindeki ince boşluk onu çizginin önüne çıkarır.

Simge tamamen geometriden çizilir; dışarıdan alınmış görsel, yazı tipi ya da herhangi bir okulun logosu içermez.
16–32 piksellik boyutlarda dişli çizilmez, çizgiler kalınlaşır ve kenar boşluğu kalkar (`GEO_SADE`).

| Dosya | Boyut | Nerede |
|---|---|---|
| `dagitim/marka/meskoord_simge.svg` | vektör | Aslı. Basılı materyal, web, büyük boyutlar |
| `dagitim/marka/meskoord_simge_1024.png` | 1024 px | Sunum, sosyal medya profil resmi |
| `dagitim/marka/meskoord_logo.png` | 320 px yükseklik | Simge + ad + açıklama (açık zemin) |
| `dagitim/marka/tanitim_afisi.png` | 1200×630 | Duyuru, e-posta, web sayfası, sosyal medya |
| `koordmes/gorseller/simge.png` | 512 px | Pencere simgesi, menü, Hakkında, giriş ve lisans pencereleri |
| `koordmes/gorseller/simge_kucuk.png` | 64 px | 16–32 piksel: dişlisiz, kalın çizgili |
| `koordmes/gorseller/logo_yatay.png` | 160 px yükseklik | Yatay logo (açık zemin) |
| `koordmes/gorseller/acilis.png` | 640×360 | Açılış ekranı (alttaki koyu şerit yükleme iletileri içindir) |
| `dagitim/meskoord.ico` | 16–256 px | Exe, kısayol, kurulum dosyası |
| `dagitim/kurulum_buyuk*.bmp`, `kurulum_kucuk*.bmp` | %100/150/200 | Kurulum sihirbazı |

Hepsi `python araclar\marka_olustur.py` ile yeniden üretilir; elle düzenlenmez.

**Kullanım kuralları**

- Simgenin oranı bozulmaz, döndürülmez, renkleri değiştirilmez, üzerine yazı ya da gölge eklenmez.
- Çevresinde en az simge genişliğinin %10'u kadar boşluk bırakılır.
- 32 pikselden küçük kullanımda `simge_kucuk.png` (ya da .ico içindeki küçük boyutlar) kullanılır.
- Simge her zeminde kendi gece mavisi karesiyle kullanılır; M ve düğümler zeminsiz kullanılmaz.

## 3. Ad yazımı (logotip)

"MesKoord" Segoe UI Semibold ile yazılır. **"Mes" ana renkte, "Koord" turkuaz** renktedir. Açık zeminde "Mes"
gece mavisi, "Koord" koyu turkuaz (`VURGU_KOYU`); koyu zeminde "Mes" beyaz, "Koord" açık turkuaz (`VURGU_ACIK`)
olur. Yazının yanında simge solda durur.

## 4. Renkler

| Ad (`marka.py`) | Kod | Kullanım |
|---|---|---|
| `ANA` | `#1B2A63` | Gece mavisi. Sol menü, başlıklar, simge zemini |
| `ANA_KOYU` | `#101943` | Geçişlerin koyu ucu |
| `ANA_ACIK` | `#2B3F8C` | Seçili menü, geçişlerin açık ucu, ikincil yazı |
| `ANA_ORTA` | `#3D56A8` | Düğme üzerine gelme kenarı |
| `VURGU` | `#1FB5A0` | Turkuaz. Seçili menü çizgisi, ayraç, simgedeki öğrenci düğümü |
| `VURGU_KOYU` | `#0B7F6F` | Açık zemin üzerinde vurgu yazısı ("Koord") |
| `VURGU_ACIK` | `#5FE3CD` | Koyu zemin üzerinde vurgu yazısı |
| `ZEMIN` | `#F4F6FB` | Sayfa zemini |
| `CIZGI` | `#CBD3E6` | Kenarlıklar, tablo çizgileri |
| `YAZI` | `#1A2036` | Metin |

Kurallar: Turkuaz yalnızca vurgu içindir, geniş alan boyanmaz. Gece mavisi zemin üzerine beyaz ya da açık
turkuaz yazı, açık zemin üzerine gece mavisi yazı kullanılır. Uyarı ve hata renkleri (kırmızı `#B00020`, yeşil
`#1B5E20`) marka renginin yerine kullanılmaz.

## 5. Yazı

Arayüz ve görsellerde **Segoe UI** (Windows'un sistem yazı tipi): başlıklarda Semibold, metinde Regular.
Basılı resmî belgeler (Word şablonları) resmî yazışma kurallarına uyar (Times New Roman 12).

## 6. Ürün simgesi ile kurum logosu

MesKoord simgesi **resmî belgelere basılmaz**. Her okul kendi logosunu Ayarlar > Kurum Bilgileri > Kurum logosu
bölümünden yükler; Word belgelerine ve PDF raporlarına o basılır. Logo yüklenmemişse belgeler logosuz çıkar.
Programla birlikte hiçbir okulun logosu dağıtılmaz.

## 7. Tanıtım metni (örnek)

> **MesKoord — Mesleki Eğitim Koordinasyon ve Yönetim Sistemi**
> Mesleki ve teknik Anadolu liseleri ile mesleki eğitim merkezleri için. Ders programı ve atölye yerleşimi,
> işletmelerde mesleki eğitim sözleşmeleri, koordinatörlük, SGK bildirgeleri ve e-Bildirge dosyaları, öğrenci
> ücreti ve devlet katkısı, ek ders ve devamsızlık işlemleri tek programda. Okulun bütün bilgisayarlarında aynı
> verilerle eşzamanlı çalışır; veriler okulda kalır.
