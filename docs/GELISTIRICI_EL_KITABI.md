# MesKoord Geliştirici, Bakım ve Dağıtım El Kitabı

Bu el kitabı, MesKoord'un bakımını, arıza gidermesini, geliştirilmesini, sürüm çıkarılmasını ve döner sermaye
üzerinden lisanslanarak satılmasını devralan **bilişim teknolojileri / bilgisayar öğretmenleri** için yazılmıştır.
Python bilen bir öğretmenin bu belgeyle programı tek başına sürdürebilmesi hedeflenmiştir.

> Belgedeki komutlar proje klasöründe (`D:\KoordMes` veya projeyi nereye kopyaladıysanız) PowerShell ya da
> Komut İstemi'nde çalıştırılır. `python` yerine sanal ortamı kullanmak için `.venv\Scripts\python.exe` yazılır.

---

## İçindekiler

1. [Devir alınca ilk gün yapılacaklar](#1-devir-alınca-ilk-gün-yapılacaklar)
2. [Program nedir, nasıl çalışır](#2-program-nedir-nasıl-çalışır)
3. [Geliştirme ortamının kurulması](#3-geliştirme-ortamının-kurulması)
4. [Kod düzeni ve kurallar](#4-kod-düzeni-ve-kurallar)
5. [Sık yapılan geliştirmeler (tarifler)](#5-sık-yapılan-geliştirmeler-tarifler)
6. [Testler](#6-testler)
7. [Sürüm çıkarma ve dağıtım](#7-sürüm-çıkarma-ve-dağıtım)
8. [Lisans sistemi (teknik)](#8-lisans-sistemi-teknik)
9. [Döner sermaye satış ve lisans işlemleri](#9-döner-sermaye-satış-ve-lisans-işlemleri)
10. [Destek ve arıza giderme](#10-destek-ve-arıza-giderme)
11. [Yıllık bakım takvimi](#11-yıllık-bakım-takvimi)
12. [Güvenlik ve kişisel veriler (KVKK)](#12-güvenlik-ve-kişisel-veriler-kvkk)
13. [Hukuki ve idari kontrol listesi](#13-hukuki-ve-idari-kontrol-listesi)
14. [Devir teslim kontrol listesi](#14-devir-teslim-kontrol-listesi)
15. [Bilinen sınırlar ve yol haritası](#15-bilinen-sınırlar-ve-yol-haritası)
16. [Çok kullanıcılı çalışma (ağ modu)](#16-çok-kullanıcılı-çalışma-ağ-modu)
17. [Marka kimliği ve görseller](#17-marka-kimliği-ve-görseller)
18. [Kullanıcı hesapları, işlem günlüğü, otomatik yedek ve sistem tepsisi](#18-kullanıcı-hesapları-işlem-günlüğü-otomatik-yedek-ve-sistem-tepsisi)
19. [Ortaöğretim Kurumları Yönetmeliği işleri](#19-ortaöğretim-kurumları-yönetmeliği-işleri)

---

## 1. Devir alınca ilk gün yapılacaklar

1. Kaynak kodu (bu klasörün tamamı, `.venv`, `build`, `dist`, `cikti` hariç) ve **git geçmişini** teslim alın.
2. **Özel imza anahtarını** (`ozel_anahtar_KM1.pem`) ve şifresini teslim alın. İki ayrı USB bellekte ve
   kilitli dolapta saklanmalıdır. Ayrıntı: [8.6](#86-anahtar-güvenliği-kaybolma-ve-ele-geçirilme).
3. **Lisans kayıt defterini** (`lisanslar.csv`) ve `Verilen_Lisanslar` klasörünü teslim alın.
4. [Bölüm 3](#3-geliştirme-ortamının-kurulması)'e göre geliştirme ortamını kurun, `python -m pytest -q` ile
   bütün testlerin geçtiğini görün.
5. `build_exe.bat` ile bir deneme paketi üretin, `python araclar\kurulum_sina.py` ile kurulumu sınayın.
6. [Bölüm 14](#14-devir-teslim-kontrol-listesi)'teki tutanağı imzalayın.

---

## 2. Program nedir, nasıl çalışır

MesKoord; mesleki ve teknik Anadolu liseleri ile mesleki eğitim merkezleri için ders programı, atölye yerleşimi,
işletmelerde mesleki eğitim (yerleştirme, sözleşme, koordinatörlük), SGK prim listesi, öğrenci ücreti ve devlet
katkısı, ek ders, devamsızlık ve resmî belge üretimi yapan bir **Windows masaüstü programıdır**. İnternet
sunucusu yoktur; her okulun verisi kendi bilgisayarında durur. Okulda birden çok bilgisayar varsa biri
**sunucu** olur, diğerleri yerel ağ üzerinden ona bağlanıp aynı veriyle eşzamanlı çalışır
([Bölüm 16](#16-çok-kullanıcılı-çalışma-ağ-modu)).

### 2.1 Kullanılan teknolojiler

| Bileşen                 | Sürüm              | Görevi                                         |
| ----------------------- | ------------------ | ---------------------------------------------- |
| Python                  | 3.11 (64 bit)      | Programlama dili                               |
| PySide6 (Qt for Python) | **6.10.2 (sabit)** | Arayüz ve gömülü tarayıcı (QtWebEngine)        |
| SQLite                  | Python ile gelir   | Veritabanı (tek dosya)                         |
| openpyxl, xlrd          |                    | Excel okuma/yazma                              |
| python-docx             |                    | Word belgeleri (sözleşme, yazı)                |
| pdfplumber              |                    | PDF'den tablo okuma                            |
| cryptography            |                    | Lisans imzasının doğrulanması (Ed25519)        |
| PyInstaller             |                    | Programı `.exe` hâline getirme                 |
| Inno Setup 6            |                    | Kurulum dosyası (`MesKoord_Kurulum_X.Y.Z.exe`) |
| pytest                  |                    | Otomatik testler                               |

**PySide6 neden 6.10.2'ye sabit?** 6.11.x sürümlerindeki tarayıcı bileşeni, karakter kodlaması ISO-8859-9 /
windows-1254 olan sayfalarda (SGK işe giriş/çıkış ekranı) çöküyor. `requirements.txt` içindeki sabitlemeyi,
yeni sürümde SGK 4A sayfasının açıldığını elle denemeden kaldırmayın.

### 2.2 Klasör yapısı

```
KoordMes/
├─ run.py                     Programın başlangıç noktası (açılış ekranı, ağ kipi, lisans, ana pencere)
├─ koordmes/
│  ├─ __init__.py             Sürüm numarası, program adı, yayıncı
│  ├─ config.py               Veri klasörlerinin yerleri
│  ├─ db.py                   Veritabanı şeması, eski veritabanlarına kolon ekleme, yedekleme
│  ├─ hesaplar.py             Kullanıcı hesapları, roller, bağlantı düzeyinde yetki ve işlem günlüğü
│  ├─ yedekleme.py            Zamanlanmış otomatik yedek ayarları, ikinci yedek klasörüne kopya
│  ├─ mevzuat.py              Asgari ücret, oranlar vb. parametreler ve sabit listeler
│  ├─ lisans.py               Lisans doğrulama, deneme süresi, AÇIK ANAHTAR, satıcı bilgileri
│  ├─ marka.py                Marka kimliği: ürün adı, renkler, logo/simge yolları, arayüz stili, kurum logosu
│  ├─ gorseller/              Logo, simge ve açılış görselleri (araclar/marka_olustur.py üretir)
│  ├─ veri/cerceve_programlari.json  MEB çerçeve öğretim programlarının haftalık ders çizelgeleri (bkz. 5.9)
│  ├─ ag/                     ÇOK KULLANICILI ÇALIŞMA (arayüzden bağımsız, testli)
│  │  ├─ protokol.py          Ortak kodlama, satır nesnesi, TLS sertifikası, parola özeti, ag_ayarlari.json
│  │  ├─ sunucu.py            KoordSunucu (HTTPS + oturum başına SQLite bağlantısı), SunucuDatabase
│  │  ├─ istemci.py           UzakBaglanti/UzakDatabase (sqlite3 yerine geçer), OlayDinleyici
│  │  └─ kesif.py             Ağdaki sunucuları UDP yayınıyla bulma
│  ├─ services/               İŞ MANTIĞI (arayüzden bağımsız, testli)
│  │  ├─ aktarim.py           Excel/CSV/PDF/HTML listelerini tanıyıp veritabanına aktarma
│  │  ├─ okuyucu.py           Dosya biçimlerini tabloya çevirme
│  │  ├─ toplu_giris.py       Toplu Veri Girişi ekranının denetim/kaydetme mantığı
│  │  ├─ baglanti.py          e-Okul/e-Mesem/SGK adresleri, indirilen dosyaların işlenmesi
│  │  ├─ sigorta.py           SGK aylık prim hizmet listesi, belge türü, gün sayısı
│  │  ├─ ucret.py             Öğrenci ücreti ve devlet katkısı
│  │  ├─ ekders.py, devam.py  Ek ders puantajı, devamsızlık
│  │  ├─ program.py           Ders programı yerleştirme algoritması
│  │  ├─ cerceve.py           Çerçeve öğretim programı çizelgeleri; sınıfa zorunlu dersleri açma
│  │  ├─ koordinator.py       Koordinatör görevlendirme ve ziyaret planı
│  │  ├─ mesleki_egitim.py    Yönetmelik işleri: öğrenci seçimi, puan çizelgesi, alan taraması, anket, hizmetiçi
│  │  ├─ belgeler.py          Word şablonları ve belge üretimi
│  │  ├─ surecler.py          Aylık kapanış, yıl başı/sonu süreçleri, "eylemler"
│  │  ├─ asistan.py           Türkçe komut yorumlayıcı (Asistan ekranı)
│  │  ├─ denetim.py           Veri tutarlılık denetimi
│  │  └─ raporlar.py, takvim.py, excel_io.py, ornek_veri.py, utils.py
│  └─ ui/                     ARAYÜZ (PySide6)
│     ├─ ana_pencere.py       Ekran listesi (yapi), ekrana sığdırma, Güvenli Çıkış, canlı yenileme; yeni sayfalar buraya
│     ├─ yan_menu.py          Sol menü: akordeon gruplar, menüde arama (Ctrl+K), simge şeridi (Ctrl+B)
│     ├─ ag_baslat.py         Açılışta kipe göre veritabanını açar (tek / sunucu / istemci), hata pencereleri
│     ├─ ag_koprusu.py        Ağ olaylarını Qt sinyallerine çevirir (ana pencere bununla yenilenir)
│     ├─ sayfa_ag.py          "Çok Kullanıcılı Çalışma (Ağ)" ekranı
│     ├─ giris.py             Kullanıcı girişi ve parola değiştirme pencereleri
│     ├─ sayfa_kullanicilar.py Ayarlar > Kullanıcılar ve Ayarlar > İşlem Günlüğü sekmeleri
│     ├─ tepsi.py             Sistem tepsisi, Windows açılışında başlama, tek örnek denetimi
│     ├─ lisans_penceresi.py  Lisans bilgisi, yükleme, talep pencereleri
│     ├─ sayfa_*.py           Her menü ekranı
│     ├─ crud.py, varliklar.py Öğrenci/öğretmen/işletme gibi tanım ekranları (genel tablo-form yapısı)
│     ├─ ortak.py             Ortak yardımcılar (mesaj kutuları, renkler, PDF, satır kıran AkisDuzeni)
│     └─ eylem.py             Uzun işlemleri arka planda çalıştırma
├─ tests/                     Otomatik testler (pytest)
├─ araclar/                   GELİŞTİRİCİ VE DÖNER SERMAYE ARAÇLARI (okullara dağıtılmaz)
│  ├─ surum_hazirla.py        Tek komutla dağıtım paketi
│  ├─ kurulum_sina.py         Kurulum dosyasını gerçek kurulumla sınama
│  ├─ lisans_yonetici.py/.bat Lisans üretme aracı (YALNIZCA döner sermaye bilgisayarında)
│  ├─ marka_olustur.py        MesKoord simge, logo, kurulum ve tanıtım görsellerini geometriden üretir
│  ├─ kilavuz_pdf.py          docs/*.md belgelerinden PDF üretir (kılavuzun PDF'ini pakete ekler)
│  ├─ cerceve_guncelle.py     Çerçeve programı verisini meslek.meb.gov.tr/cerceve ile karşılaştırır
│  └─ ag_sinama.py            Ağ kipini gerçek programla uçtan uca sınar
├─ dagitim/
│  ├─ MesKoord.iss            Inno Setup kurulum betiği (güvenlik duvarı kuralı dahil)
│  ├─ LISANS_SOZLESMESI.txt   Son kullanıcı lisans sözleşmesi (kurulumda gösterilir)
│  ├─ meskoord.ico            Exe ve kurulum simgesi
│  ├─ kurulum_*.bmp           Kurulum sihirbazı görselleri (100/150/200 % ölçek)
│  └─ marka/                  Simgenin vektör aslı (meskoord_simge.svg), 1024 px simge, logo ve tanıtım afişi
├─ docs/GELISTIRICI_EL_KITABI.md  Bu belge
├─ docs/DEVIR_TESLIM.md       Devralanlar için özet, açık işler, ilk hafta planı, tutanak
├─ docs/KULLANIM_KILAVUZU.md  Son kullanıcı kılavuzu (programda Yardım > Kullanım Kılavuzu / F1; pakete PDF olarak da girer)
├─ docs/TANITIM.md            Programın tanıtımı (okul idaresi, satış)
├─ docs/MARKA_KIMLIGI.md      Logo, renk ve yazı kullanım kuralları
├─ MesKoord.spec              PyInstaller paketleme tarifi
├─ build_exe.bat              Paketleme kısayolu (surum_hazirla.py'yi çağırır)
├─ requirements.txt           Bağımlılıklar (sürümleri sabit olanlara dikkat)
├─ SURUM_NOTLARI.md           Her sürümde ne değiştiği
└─ README.md                  Kısa özet (kuruluma BENIOKU.txt olarak girer)
```

### 2.3 Verilerin yeri (okul bilgisayarında)

Program kurulduğu klasöre (`C:\Program Files\MesKoord`) **veri yazmaz**. Bütün veriler kullanıcının
`Belgeler\MesKoord` klasöründedir; program kaldırılsa da silinmez:

| Yol                   | İçerik                                                                                                                       |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `meskoord.db`         | Bütün veriler (SQLite). Bilgisayar değişince bu klasörü kopyalamak yeterlidir.                                               |
| `Yedekler\`           | Otomatik ve elle alınan yedekler (`meskoord_YYYYAAGG_SSDDss.db`)                                                             |
| `Ciktilar\`           | Üretilen Excel, Word, PDF dosyaları                                                                                          |
| `Sablonlar\`          | Word belge şablonları (kullanıcı düzenleyebilir; silinirse yeniden üretilir)                                                 |
| `Indirilenler\`       | e-Okul/e-Mesem/SGK ekranından indirilen listeler                                                                             |
| `Taslaklar\`          | Toplu Veri Girişi ekranının kaydedilmemiş taslakları                                                                         |
| `Tarayici\`           | Gömülü tarayıcının önbelleği (şifre ve oturum çerezi saklanmaz)                                                              |
| `lisans.lic`          | Kullanıcının program içinden yüklediği lisans                                                                                |
| `hata_gunlugu.txt`    | Beklenmeyen hataların ayrıntısı (destek için ilk bakılacak yer)                                                              |
| `ag_ayarlari.json`    | Çalışma biçimi (tek/sunucu/istemci), sunucu parolasının özeti, istemcinin sunucu adresi, kişisel hesap kipi, tepside çalışma |
| `yedek_ayarlari.json` | Otomatik yedek açık mı, sıklığı, ikinci yedek klasörü, son yedek zamanı ve son kopyalama hatası                              |
| `Sunucu\`             | Sunucunun TLS sertifikası ve anahtarı (silinirse yenisi üretilir; istemciler yeniden doğrular)                               |
| `onbellek\`           | Kurum logosunun önbellek kopyası                                                                                             |

Kurulumla gelen lisanslar `C:\ProgramData\MesKoord\*.lic` içindedir. Geliştirme ve testte veri klasörü
`MESKOORD_DATA` ortam değişkeniyle başka yere yönlendirilebilir. Bütün ortam değişkenleri `config.ortam(ad)`
ile okunur: önce `MESKOORD_<ad>`, yoksa eski `KOORDMES_<ad>` geçerlidir.

#### Eski addan (KoordMES) geçiş

1.3.0 öncesinde teknik adlar "KoordMES" idi. Taşıma kodu kaldırılmamalıdır; her taşıma "yeni yoksa eskiyi
yeniden adlandır, olmazsa eskiyle çalış" kuralına uyar (`config.tasi(yeni, eski)`):

- `config.data_dir()`: `Belgeler\KoordMES` → `Belgeler\MesKoord`. Klasör kilitliyse (açık bir çıktı vb.) eski
  klasör kullanılır, sonraki açılışta yeniden denenir. Karar süreç boyunca önbelleklenir (`_secilen`).
- `config.db_path()`: `koordmes.db` → `meskoord.db`. Yanında `-wal`/`-journal` dosyası varsa (yarım kalmış işlem)
  taşınmaz, eski adla açılır; artık `-shm` silinir.
- Yedekler: yeni yedekler `meskoord_` önekiyle yazılır; `config.yedek_dosyalari()` iki öneki birlikte listeler
  ve tarihe göre sıralar, temizlik ikisini birlikte sayar. İkinci yedek klasörü `KoordMES_Yedekler` →
  `MesKoord_Yedekler` (`yedekleme.ikinci_klasore_kopyala`).
- Lisans: `ProgramData\KoordMES` de aranır; `urun` alanı "KoordMES" olan lisanslar geçerlidir
  (`lisans.ESKI_URUNLER`). Deneme işareti için `.koordmes_kurulum` da okunur, en erken tarih esas alınır.
  Lisans yönetim klasörü `Belgeler\KoordMES_Lisans_Yonetimi` → `Belgeler\MesKoord_Lisans_Yonetimi`.
- Arayüz ayarları: yeni `QSettings("MesKoord", "arayuz")` boşsa eski anahtarlar kopyalanır
  (`ana_pencere.arayuz_ayarlari`).
- Windows açılış kaydı: paketli programda her açılışta `tepsi.otomatik_baslatmayi_guncelle()` eski `KoordMES`
  Run değerini siler, `MesKoord` değerini güncel exe yoluyla yazar.
- Ağ: sunucu `/bilgi` ve keşifte "MesKoord" der; eski keşif isteğini (`KOORDMES-KESIF-1`) de yanıtlar, istemci
  iki ürün adını da kabul eder (`protokol.URUN_ADLARI`, `KESIF_ISTEKLERI`). Var olan sunucu sertifikası
  korunur, istemcilerin parmak izi doğrulaması bozulmaz.
- Kurulum (`dagitim/MesKoord.iss` → `[Code]`): eski `...\KoordMES` kurulum klasörü seçiliyse yanındaki
  `MesKoord` klasörüne geçer, çalışan eski exe kapatılır, eski klasördeki ve `ProgramData\KoordMES` içindeki
  lisanslar `ProgramData\MesKoord`'a taşınır, eski klasör silinir, eski güvenlik duvarı kuralı ve Run değeri
  yenisiyle değiştirilir. AppId değişmediği için Windows bunu aynı programın güncellemesi sayar.
- Sınama: `tests/test_ad_gecisi.py`.

### 2.4 Katmanlar ve veri akışı

```
Kullanıcı ──> ui/sayfa_*.py ──> services/*.py ──> db.py (SQLite)
                     │                 │
                     │                 └─> mevzuat.py parametreleri (db.ayar("asgari_ucret_brut") ...)
                     └─> ortak.py, eylem.py (mesajlar, arka plan işleri)
```

- **Hesap ve kural kodu her zaman `services/` içinde** olur; arayüz yalnızca çağırır ve gösterir. Böylece
  hesaplar arayüz açmadan test edilebilir.
- Servisler veritabanına yalnızca `db.q/q1/execute/insert/update/delete` ve `db.conn.execute/executemany/
commit/rollback`, `with db.conn:` ile erişir. Ağ kipinde `db` bir `UzakDatabase`'dir ve bu yüzü birebir
  taklit eder; **başka sqlite3 özelliği (create_function, iterdump, row_factory değiştirme vb.) kullanmayın**,
  kullanırsanız `MESKOORD_TEST_UZAK=1` testleri bozulur (bkz. [6](#6-testler)).
- Arka plan iş parçacığında veritabanı gerekiyorsa `db.kopya()` kullanın (bağlantı paylaşılmaz).
- Zamanla değişen her sayı (asgari ücret, oranlar, prim tavanları) `mevzuat.py` içindeki `PARAMETRELER`
  listesindedir ve okulda **Ayarlar > Mevzuat Parametreleri** ekranından değiştirilebilir. Koda sayı gömmeyin.

---

## 3. Geliştirme ortamının kurulması

1. **Python 3.11 (64 bit)** kurun: <https://www.python.org/downloads/windows/> — kurulumda
   "Add python.exe to PATH" işaretlenmelidir.
2. **Git** kurun: `winget install Git.Git`
3. Bir düzenleyici kurun (Visual Studio Code veya Cursor).
4. **Inno Setup 6** kurun (yalnızca kurulum dosyası üretecek bilgisayarda): `winget install JRSoftware.InnoSetup`
5. Proje klasöründe sanal ortamı hazırlayın:

```powershell
cd D:\KoordMes
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

6. Programı çalıştırın: `.venv\Scripts\python.exe run.py`
7. Testleri çalıştırın: `.venv\Scripts\python.exe -m pytest -q` (yaklaşık 4 dakika; hepsi geçmelidir)

> **Gerçek okul verisiyle geliştirme yapmayın.** Kendi bilgisayarınızda `Ayarlar > Veri ve Yedekleme >
Örnek Veri Yükle` ile örnek veri kullanın ya da `MESKOORD_DATA` ile ayrı bir klasör seçin:
> `$env:MESKOORD_DATA="D:\MesKoord_Deneme"; .venv\Scripts\python.exe run.py`

### 3.1 Git ile çalışma

Proje kendi git deposunda tutulmalıdır (henüz yoksa proje klasöründe `git init` ile oluşturun).

- Her iş için ayrı dal açın: `git switch -c ozellik/ebildirge-xml`
- Testler geçmeden ana dala (`main`) birleştirmeyin.
- Sürüm çıkınca etiketleyin: `git tag v1.1.0`
- Depoya **asla** konmayacaklar (`.gitignore` engeller): `*.pem` (özel anahtar), `*.lic` (kurum lisansları),
  gerçek okul veritabanları, `dist/`, `cikti/`.
- Uzak depo olarak MEB'in izin verdiği kurumsal bir alan ya da özel (gizli) bir depo kullanın. Kod satışa
  konu olduğundan herkese açık depoya yüklemeyin.

---

## 4. Kod düzeni ve kurallar

- **Adlandırma Türkçedir** (`ogrenciler`, `aylik_hesap`, `kaydet`). Türkçe karakter değişken adında kullanılmaz;
  kullanıcıya görünen metinlerde tam Türkçe kullanılır.
- Arayüz metinleri resmî ve anlaşılır olmalı; kısaltma ve İngilizce terim kullanılmaz.
- Yeni hesap/kural = önce `services/` içinde fonksiyon + `tests/` içinde test, sonra arayüz.
- Yorum satırı yalnızca kodun kendisinden anlaşılamayan bir kısıtı açıklamak için yazılır
  (ör. "6.11.x tarayıcı bileşeni windows-1254 sayfalarda çöküyor").
- Mevzuata dayanan her parametrenin `kaynak` alanına dayanağını yazın (kanun, madde, karar tarihi).
- Veritabanı değişiklikleri **geriye uyumlu** olmalı: okullardaki eski veritabanları yeni sürümle açıldığında
  bozulmamalı (bkz. [5.3](#53-veritabanına-kolon-veya-tablo-eklemek)).
- Kullanıcı verisini silen/değiştiren her toplu işlemden önce `db.yedekle()` çağrılır.

---

## 5. Sık yapılan geliştirmeler (tarifler)

### 5.1 Yeni yıl mevzuat güncellemesi (asgari ücret vb.)

1. `koordmes/mevzuat.py` içinde ilgili `Parametre(...)` satırının `varsayilan` değerini ve `kaynak` açıklamasını
   güncelleyin (ör. `asgari_ucret_brut`, `asgari_ucret_net`).
2. `tests/test_hesaplar.py` içindeki beklenen tutarları yeni değerlere göre güncelleyin, testleri çalıştırın.
3. **Önemli:** `varsayilan` yalnızca **yeni kurulan** veritabanlarına yazılır. Okullardaki mevcut
   veritabanları eski değeri korur. İki yol vardır:
   - Sürüm notunda ve duyuruda okullardan **Ayarlar > Mevzuat Parametreleri**'nde değeri güncellemelerini
     isteyin, **veya**
   - `db.py` içindeki `_init_schema` sonunda, değeri hâlâ eski varsayılan olan veritabanlarını güncelleyen bir
     geçiş yazın. Örnek:

```python
# db.py, _init_schema içinde, ayarlar eklendikten sonra
self.conn.execute("UPDATE ayarlar SET deger = ? WHERE anahtar = 'asgari_ucret_brut' AND deger = ?",
                  ("YENI_DEGER", "33030.00"))
```

Bu yöntemde okulun bilerek değiştirdiği değerlere dokunulmaz; yalnızca eski varsayılan duruyorsa güncellenir. 4. Yeni sürüm çıkarın ([Bölüm 7](#7-sürüm-çıkarma-ve-dağıtım)).

### 5.2 Yeni bir menü ekranı eklemek

1. `koordmes/ui/sayfa_yeni.py` oluşturun; `QWidget`'tan türeyen ve `(db, parent=None)` alan bir sınıf yazın.
   Hesap kodunu `services/` içine koyun.
2. `koordmes/ui/ana_pencere.py` içinde içe aktarın ve `yapi` listesine ekleyin:

```python
("İŞLETMELERDE MESLEKİ EĞİTİM", [
    ...
    ("Yeni Ekran Adı", lambda: YeniSayfa(db)),
]),
```

   Ekran adı menüde, aramada, `git("Yeni Ekran Adı")` çağrısında ve son açık ekranın hatırlanmasında anahtar
   olarak kullanılır; benzersiz olmalıdır. Yeni bir **grup** eklerseniz `ui/yan_menu.py` içindeki `SIMGELER`'e
   grubun Segoe MDL2 kod noktasını ve yedek karakterini yazın.
3. Düğme satırlarında `QHBoxLayout` yerine `ortak.AkisDuzeni()` kullanın: sığmayan düğmeler alt satıra geçer,
   ekranın en küçük genişliği büyümez. Etiket + açılır liste çiftlerini `ortak.etiketli("Etiket:", kutu)` ile
   tek parça yapın. Uzun içerikli açılır listelerde `setSizeAdjustPolicy(AdjustToMinimumContentsLengthWithIcon)`,
   değişken uzunluktaki özet etiketlerinde `setWordWrap(True)` kullanın. Hedef: ekranlar 1024×600'de (dar
   menüyle) ve 1280×720'de (geniş menüyle) yatay kaydırma göstermemeli.
4. `tests/test_ui_smoke.py` bütün menü ekranlarını kendiliğinden açar; testleri çalıştırın.

### 5.3 Veritabanına kolon veya tablo eklemek

- **Yeni tablo:** `db.py` içindeki `SCHEMA` metnine `CREATE TABLE IF NOT EXISTS ...` ekleyin. Eski
  veritabanları açılınca tablo kendiliğinden oluşur.
- **Var olan tabloya kolon:** `SCHEMA` içindeki `CREATE TABLE`'a kolonu ekleyin **ve** `EK_KOLONLAR` listesine
  `("tablo", "kolon", "TÜR")` satırını ekleyin. Program açılırken eksik kolon `ALTER TABLE` ile eklenir.
- Kolon silmeyin veya adını değiştirmeyin; gerekirse yenisini ekleyip eskisini kullanmayı bırakın.
- Varlık ekranlarında (öğrenci, işletme…) görünmesi için `ui/varliklar.py` içindeki tanıma alanı ekleyin.
- İçe aktarmada tanınması için `services/aktarim.py` içindeki `TANIMLAR`'a alan ve eş anlamlı başlıkları ekleyin.

### 5.4 Yeni bir içe aktarma (Excel listesi) türü

`services/aktarim.py` içindeki `TANIMLAR` sözlüğüne bir `IceAktarmaTanimi` ekleyin: tablo adı, alanlar
(`(anahtar, etiket, eş_anlamlı_başlıklar)`), zorunlu alan grupları. Toplu Veri Girişi ekranı bu tanımlardan
kendiliğinden yeni bir giriş türü üretir (`services/toplu_giris.py` → `_tanimdan`). `tests/test_aktarim.py`
içine örnek bir dosya ile test ekleyin.

### 5.5 Yeni bir Word belgesi (sözleşme, yazı)

`services/belgeler.py`:

1. Şablonu üreten `_sablon_xxx(yol)` fonksiyonunu yazın; şablonda `{alan_adi}` biçiminde yer tutucular kullanın.
2. `BELGE_TURLERI` listesine `BelgeTuru("anahtar", "Görünen Ad", "kaynak", _sablon_xxx)` ekleyin. `kaynak`;
   `yerlestirme`, `ogretmen`, `ziyaret`, `ogrenci`, `isletme_ay` değerlerinden biridir ve yer tutucuları dolduran
   bağlam fonksiyonunu belirler.
3. Okullar şablonları `Belgeler\MesKoord\Sablonlar` içinde Word ile düzenleyebilir; şablonu değiştirdiyseniz
   kullanıcıların eski şablonu silmesi gerektiğini sürüm notuna yazın.

### 5.6 Asistan'a yeni komut veya eylem

- Çalıştırılabilir işlemler `services/surecler.py` içindeki `EYLEMLER` sözlüğündedir
  (`Eylem(anahtar, etiket, fonksiyon, onay=..., uzun=...)`).
- Türkçe komutun hangi eyleme gideceği `services/asistan.py` → `yorumla()` içinde `_var(n, "anahtar kelime", ...)`
  kontrolleriyle belirlenir. `n`, Türkçe karakterleri sadeleştirilmiş küçük harfli komuttur (`norm()`).
- `tests/test_asistan.py` içine komut örneği ekleyin.

### 5.7 e-Okul / e-Mesem / SGK adresi değişirse

`services/baglanti.py` → `SISTEMLER` listesindeki adresi güncelleyin. Giriş sayfası alan adları
`GIRIS_ALAN_ADLARI` içindedir (`giris.turkiye.gov.tr`, `mebbis.meb.gov.tr`).

### 5.8 Kullanım kılavuzunu güncellemek

Tek kaynak `docs/KULLANIM_KILAVUZU.md`'dir. Program bu dosyayı _Yardım > Kullanım Kılavuzu_ (F1) penceresinde
gösterir (`ui/kilavuz.py`; `##` ve `###` başlıkları içindekiler listesine girer), sürüm paketi de PDF'ini
üretip kuruluma ekler. Ekran veya düğme adı değiştiğinde kılavuzu da güncelleyin;
`tests/test_ui_kilavuz.py` her menü ekranının adının kılavuzda geçtiğini denetler. PDF'leri elle üretmek için:
`python araclar\kilavuz_pdf.py` (çıktı `cikti\Belgeler\`).

### 5.9 Çerçeve öğretim programları (MEB ders çizelgeleri)

Veri `koordmes/veri/cerceve_programlari.json` dosyasıdır; pakete `MesKoord.spec` → `datas` ile girer ve
`run.py --kendini-sina` yüklendiğini denetler. Her kayıt bir haftalık ders çizelgesidir:

| Alan                       | Anlamı                                                                                   |
| -------------------------- | ---------------------------------------------------------------------------------------- |
| `kurum`, `seviye`          | `MTAL` / `MEM`, 9-12                                                                     |
| `program`                  | `ATP` (Anadolu teknik), `AMP` (Anadolu meslek), `AMP-11` (işletmeye 11'de başlayan), `MEM` |
| `alan`, `dal`, `protokol`  | MEB'deki adlar; aynı alan/dal/seviye için protokollü ve protokolsüz çizelge olabilir      |
| `yil`, `kaynak`            | Programın yılı ve `https://meslek.meb.gov.tr/` altındaki PDF yolu                        |
| `secmeli`, `secmeli_meslek`, `akademik_destek`, `toplam` | Haftalık saat toplamları                                   |
| `dersler`                  | `[ad, kategori, saat, parantezli_saat, basari_zorunlu]`; kategori `Ortak` / `Meslek` / `Rehberlik` / `İşletmede` |

MEM'deki "0-(2)" gibi parantezli saatler zorunlu ders saatine girmez ve ders dağılımına açılmaz.
MTAL 12. sınıf ATP'de akademik destek PDF'te ayrı satır olmadığı için yüklenirken
`toplam − dersler − seçmeli` olarak hesaplanır (`cerceve._program`).

Kod `services/cerceve.py`'dedir: `bul()` okul türü/program/seviye/alan/dal ile çizelgeyi bulur (Türkçe
karakter, "alanı/dalı" eki ve yazım farkları tolere edilir; 2026'da 9. sınıfta adı değişen alanlar
`ALAN_KARSILIKLARI`'ndadır; 12. sınıfta AMP-11 yerine AMP kullanılır). `uygula()` okulda okutulan zorunlu
dersleri sınıfın `ders_atamalari`'na ekler ya da saatini düzeltir; çizelgede olmayan atamaları silmez,
öğretmen/atölye atamalarına dokunmaz, `İşletmede` dersleri eklemez. Sınıf programı ↔ çizelge programı
eşlemesi `SINIF_PROGRAMI`'ndadır; hangi sınıfın işletmeye gittiği `mevzuat.isletmeye_giden_sinif()` ile
tek yerden belirlenir. Arayüz `ui/sayfa_cerceve.py`'dedir; sınıf formu kaydedilince `Varlik.form_sonrasi`
kancasıyla zorunlu ders penceresi açılır.

**Güncelleme (her eğitim yılı başında, ayrıca MEB yeni program yayımladığında):**

```powershell
.venv\Scripts\python.exe araclar\cerceve_guncelle.py --indir .tmp_data\yeni_cop
```

Araç sitedeki bütün liste sayfalarını okur; yeni yayımlanan, kaldırılan ve yılı değişen PDF'leri listeler,
yenileri indirir. Yeni çizelgeleri PDF'ten JSON'a işleyin (ders adları ve saatleri PDF'teki haftalık ders
çizelgesiyle birebir olmalı), `surum` alanını güncelleyin, `pytest tests/test_cerceve.py` çalıştırın.
Haftalık ders çizelgesi içermeyen PDF'ler aracın `ISTISNALAR` sözlüğüne açıklamasıyla eklenir.

---

## 6. Testler

```powershell
.venv\Scripts\python.exe -m pytest -q                      # hepsi (~4 dk)
.venv\Scripts\python.exe -m pytest -q tests/test_lisans.py # yalnızca lisans
.venv\Scripts\python.exe -m pytest -q -k sgk               # adında "sgk" geçenler
```

- Her test geçici bir veri klasörü ve veritabanı kullanır (`tests/conftest.py` → `db`, `ornek_db`); gerçek
  verinize dokunmaz.
- Arayüz testleri pencere göstermeden (`QT_QPA_PLATFORM=offscreen`) çalışır. Bu kipte Qt yazı tiplerini
  bulamadığından `conftest.py` `QT_QPA_FONTDIR`'i Windows yazı tipi klasörüne yönlendirir.
- **Ağ kipinde tam sınama:** aşağıdaki komut bütün testleri, veritabanı geçici bir ağ sunucusundaymış gibi
  (`db` yerine `UzakDatabase`) çalıştırır. Veritabanıyla ilgili kod değiştirdiyseniz sürümden önce çalıştırın:
  ```powershell
  $env:MESKOORD_TEST_UZAK="1"; .venv\Scripts\python.exe -m pytest -q; Remove-Item Env:MESKOORD_TEST_UZAK
  ```
  Gerçek programla uçtan uca sınama: `.venv\Scripts\python.exe araclar\ag_sinama.py`
- **Testler geçmeden sürüm çıkarılmaz**; `surum_hazirla.py` testleri kendisi çalıştırır ve başarısız olursa durur.
- Hesaplarda (SGK gün sayısı, belge türü, ücret, devlet katkısı) yaptığınız her düzeltmeye, hatayı yakalayan bir
  test ekleyin.
- Adlara dikkat: `tests/test_hesaplar.py` **hesaplamaların** (SGK, ücret, ek ders) testidir;
  **kullanıcı hesapları**, roller ve işlem günlüğü `tests/test_kullanici_hesaplari.py`'de, ilgili ekranlar,
  otomatik yedek ve tepsi `tests/test_ui_hesaplar_tepsi.py`'dedir.

---

## 7. Sürüm çıkarma ve dağıtım

### 7.1 Sürüm numarası

`X.Y.Z` biçimi kullanılır (`koordmes/__init__.py` → `__version__`):

- **Z (yama):** hata düzeltme, parametre güncellemesi → 1.0.0 → 1.0.1
- **Y (küçük):** yeni ekran/özellik, eski verilerle uyumlu → 1.0.1 → 1.1.0
- **X (büyük):** köklü değişiklik → 2.0.0

### 7.2 Paket hazırlama (tek komut)

```powershell
build_exe.bat --surum 1.1.0
```

Bu komut sırasıyla:

1. Sürüm numarasını yazar, `SURUM_NOTLARI.md`'ye yeni başlık açar (değişiklikleri siz yazarsınız),
2. Ön denetim yapar (açık anahtar var mı, proje klasöründe `.pem` var mı, yayıncı/satıcı bilgileri dolu mu),
3. Bütün testleri çalıştırır,
4. PyInstaller ile `dist\MesKoord\` klasör paketini üretir (`MesKoord.spec`),
5. Üçüncü taraf lisans bildirimlerini, lisans sözleşmesini, `BENIOKU.txt`'yi ve kullanım kılavuzunun PDF'ini
   (`docs/KULLANIM_KILAVUZU.md`'den, `araclar\kilavuz_pdf.py` ile) pakete ekler,
6. Paketlenmiş programı `--kendini-sina` ile çalıştırıp bütün bileşenlerin pakette olduğunu doğrular,
7. `cikti\MesKoord_1.1.0\` içine **kurulum dosyasını**, **taşınabilir zip'i**, `SHA256SUMS.txt`, sürüm notunu
   ve kurulum dosyası üretildiyse **`surum.json`**'u (güncelleme bilgisi, 7.7) yazar.

Ardından kurulumu sınayın:

```powershell
.venv\Scripts\python.exe araclar\kurulum_sina.py
```

Bu araç geçici bir sınama lisansıyla sessiz kurulum yapar, lisansın kendiliğinden yüklendiğini, programın
kendi denetimini geçtiğini ve kaldırmanın düzgün çalıştığını kontrol eder, sonra her şeyi temizler.

Son olarak programı normal açıp birkaç ekranı elle deneyin (özellikle değiştirdiğiniz yerleri) ve git'te
etiketleyin: `git tag v1.1.0`.

### 7.3 İlk dağıtımdan önce bir kez doldurulacaklar

`surum_hazirla.py` bunlar boşsa uyarır:

| Dosya                           | Alan                                 | Örnek                                          |
| ------------------------------- | ------------------------------------ | ---------------------------------------------- |
| `koordmes/__init__.py`          | `APP_PUBLISHER`                      | `"Atatürk MTAL Döner Sermaye İşletmesi"`       |
| `koordmes/__init__.py`          | `GUNCELLEME_ADRESI` (7.7)            | `surum.json`'un yayımlandığı https adresi      |
| `koordmes/lisans.py`            | `SATICI` (ad, telefon, e-posta, web) | Lisans penceresinde ve talep ekranında görünür |
| `dagitim/LISANS_SOZLESMESI.txt` | `[KÖŞELİ PARANTEZLİ]` yerler         | Hukuk biriminin onayından geçirin              |

### 7.4 Okula ne gönderilir, okul nasıl kurar

Okula gönderilecek klasör:

```
MesKoord_1.1.0/
├─ MesKoord_Kurulum_1.1.0.exe
└─ KM-2026-0007_123456_Ataturk_MTAL.lic   (o okulun lisansı)
```

- Okul, `.lic` dosyası kurulum dosyasıyla **aynı klasördeyken** kurulumu çalıştırır; lisans
  `C:\ProgramData\MesKoord` içine kopyalanır ve o bilgisayarın bütün kullanıcıları için geçerli olur.
  Aynı klasör (USB bellek veya okul ağındaki paylaşım) okulun bütün bilgisayarlarında kullanılabilir.
- **Sessiz kurulum** (laboratuvar, çok sayıda bilgisayar):
  `MesKoord_Kurulum_1.1.0.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART`
- **Yönetici yetkisi yoksa:** kurulumda "Yalnızca benim için" seçilir ya da taşınabilir zip bir klasöre
  açılıp `MesKoord.exe` çalıştırılır (lisans program içinden yüklenir).
- **Güncelleme:** yeni kurulum dosyası eskisinin üzerine kurulur. Veriler ve lisans korunur; eski sürümün
  kütüphaneleri temizlenir. Kurulum öncesi program kapatılmalıdır (kurulum kapatmayı önerir).
- Dosyanın bozulmadığını/değiştirilmediğini doğrulamak için: `certutil -hashfile MesKoord_Kurulum_1.1.0.exe SHA256`
  çıktısı `SHA256SUMS.txt` ile aynı olmalıdır.

### 7.5 Kod imzalama (önerilir)

İmzasız `.exe` dosyalarında Windows SmartScreen "Windows bilgisayarınızı korudu" uyarısı verir ve bazı
virüs programları PyInstaller paketlerini yanlışlıkla şüpheli bulabilir. Kurumsal bir **kod imzalama
sertifikası** alınırsa (kamu kurumları için Kamu SM'nin sunduğu seçenekler araştırılabilir) şu ortam değişkeni
tanımlanır; `surum_hazirla.py` hem `MesKoord.exe`'yi hem kurulum dosyasını kendiliğinden imzalar:

```powershell
$env:MESKOORD_IMZA_KOMUTU = 'signtool sign /f C:\Sertifika\kod.pfx /p SIFRE /fd sha256 /tr http://timestamp.digicert.com /td sha256 "{dosya}"'
build_exe.bat
```

### 7.6 Paketleme ayrıntıları

- Paket **klasör (onedir)** biçimindedir: `MesKoord.exe` + `_internal\`. Tek dosya (onefile) kullanılmaz;
  tarayıcı bileşeni her açılışta yüzlerce MB geçici dosya açardı ve Qt kütüphanelerinin (LGPL) kullanıcı
  tarafından değiştirilebilir ayrı dosyalar olarak kalması gerekir.
- Exe'nin dosya özelliklerindeki sürüm/yayıncı bilgisi `MesKoord.spec` içinde `__init__.py`'den okunur.
- `araclar/` klasörü pakete **hiçbir zaman** girmez (`excludes=["araclar"]`).
- Inno Setup betiğindeki `AppId` GUID'i **asla değiştirilmez**; değişirse yeni sürüm eskisinin üzerine
  kurulmaz, iki ayrı program görünür.
- Yeni bir Python paketi eklediyseniz ve paketlenmiş program onu bulamıyorsa (`--kendini-sina` HATA verir),
  `MesKoord.spec` içindeki `hiddenimports`'a ekleyin; `run.py` → `kendini_sina` içine de bir denetim satırı
  ekleyin.

### 7.7 Kendiliğinden güncelleme (surum.json)

Program açılıştan 20 saniye sonra, günde en çok bir kez `GUNCELLEME_ADRESI`'ndeki `surum.json`'u okur
(`services/guncelleme.py`). Yalnızca HTTPS (ve sınama için `file:`) adresleri kabul edilir; kurum veya kişi
bilgisi gönderilmez. Yeni sürüm varsa kullanıcıya "İndir ve Kur" sorulur; kurulum dosyası
`Belgeler\MesKoord\Guncelleme`'ye iner, SHA256 özeti `surum.json`'dakiyle karşılaştırılır, uyuşmazsa silinir.
Uyuşursa kurulum başlatılır ve program kapanır. Adres boşsa program hiç denetlemez.

**Bir kez yapılacak:** Ücretsiz yol GitHub Releases'tir. Sürüm dosyalarının şifresiz indirilebilmesi için
depo açık (public) olmalıdır; kaynak kodu açmak istemiyorsanız yalnızca sürümler için ayrı, boş bir açık depo
kullanın. Sonra `__init__.py`'ye yazın:

```python
GUNCELLEME_ADRESI = "https://github.com/KULLANICI/meskoord-surumler/releases/latest/download/surum.json"
```

Okul web sitesi veya başka bir HTTPS sunucusu da olur; o zaman kurulum dosyası `surum.json` ile aynı klasöre
konur. Bu adresi içeren ilk sürümü okullara **elle** dağıtın; sonrakiler kendiliğinden duyurulur.

**Her sürümde:**

1. `build_exe.bat --surum 1.4.0`; çıktıda `surum.json` oluşur. Kurulum dosyasının adresi
   `GUNCELLEME_ADRESI`'nden türetilir (GitHub'da `releases/download/v1.4.0/...`); farklıysa
   `--indirme-adresi https://.../MesKoord_Kurulum_1.4.0.exe` verin.
2. GitHub'da `v1.4.0` etiketli yeni bir sürüm (Release) açıp `MesKoord_Kurulum_1.4.0.exe` ile `surum.json`'u
   birlikte yayımlayın. Komut satırından: `gh release create v1.4.0
   cikti\MesKoord_1.4.0\MesKoord_Kurulum_1.4.0.exe cikti\MesKoord_1.4.0\surum.json -F SURUM_NOTLARI.md`.
3. Bir okul bilgisayarında **Yardım > Güncellemeleri Denetle...** ile sınayın.

Okul ağında çalışıyorsa sunucu ile istemciler aynı sürümde olmalıdır; güncelleme penceresi bunu hatırlatır.

---

## 8. Lisans sistemi (teknik)

### 8.1 Model

- **Kurum lisansı:** Lisans, okulun **MEB kurum koduna** verilir ve o okulun bütün bilgisayarlarında geçerlidir.
  Bilgisayar/donanım kilidi yoktur (okullarda bilgisayar sık değişir).
- **Kurum adı ve kodu lisansa kilitlenir:** Lisans yüklenince Ayarlar'daki kurum adı ve kodu lisanstaki değerle
  değiştirilir ve düzenlenemez. Programın ürettiği bütün resmî belgelere bu ad/kod yazıldığından, bir okulun
  lisansını başka okulun kullanması pratikte işe yaramaz. Asıl koruma budur.
- **Süreli** (genellikle eğitim-öğretim yılı sonu, 31 Ağustos) veya **süresiz** lisans verilebilir.
- Lisanssız ilk kullanımda **30 gün deneme**; süreli lisans bitince **30 gün ek süre** (uyarıyla çalışır);
  sonra yalnızca lisans yükleme / veri yedekleme penceresi açılır. **Veriler asla silinmez veya kilitlenmez.**

### 8.2 Lisans dosyası

Lisans dosyası (`.lic`) okunabilir bir JSON metnidir; içindeki `imza` alanı Ed25519 dijital imzasıdır:

```json
{
  "anahtar": "KM1",
  "baslangic": "2026-09-01",
  "bitis": "2027-08-31",
  "duzenleme": "2026-10-05",
  "duzenleyen": "Atatürk MTAL Döner Sermaye İşletmesi",
  "il": "Ankara",
  "ilce": "Çankaya",
  "kapsam": "Kurum lisansı - kurumun bütün bilgisayarlarında kullanılabilir",
  "kurum_adi": "Atatürk Mesleki ve Teknik Anadolu Lisesi",
  "kurum_kodu": "123456",
  "lisans_no": "KM-2026-0001",
  "surum": 1,
  "urun": "MesKoord",
  "imza": "base64..."
}
```

- `urun` 1.3.0 öncesinde verilen lisanslarda "KoordMES"tir; program ikisini de kabul eder
  (`lisans.ESKI_URUNLER`). Yeni lisanslar "MesKoord" yazar ve 1.3.0 öncesi sürümlerde tanınmaz.
- İmza, `imza` dışındaki alanların anahtar sırasına göre dizilmiş JSON'u üzerinden atılır (`lisans.kanonik`).
  Tek harf değişirse imza tutmaz.
- Aynı içerik e-posta ile kolay gönderilsin diye tek satırlık **lisans koduna** da çevrilir: `KMLIS1.` + base64.
  E-postada satırlara bölünse de program birleştirip okur.
- `anahtar` alanı hangi açık anahtarla doğrulanacağını gösterir (anahtar değişimi için, bkz. 8.6).

### 8.3 Program lisansı nerede arar

`koordmes/lisans.py` → `arama_yollari()`; geçerli olanlardan **bitişi en geç olan** kullanılır:

1. `Belgeler\MesKoord\lisans.lic` (program içinden "Lisans Dosyası Yükle/Kodu Yapıştır" ile)
2. `C:\ProgramData\MesKoord\*.lic` (kurulum dosyasının yanındaki lisanslar buraya kopyalanır)
3. Program klasöründeki `*.lic` (taşınabilir zip kullananlar için)
4. Ağ kipinde istemciyse: sunucunun lisans metinleri (`lisans.SUNUCU_LISANSLARI`). Sunucu bağlanan her
   istemciye kendi geçerli lisanslarını gönderir; istemci imzayı kendisi doğrular, diske yazmaz. Böylece
   lisansı yalnızca sunucuya yüklemek yeterlidir.

### 8.4 Durumlar

| Durum      | Ne zaman                                        | Program                                                          |
| ---------- | ----------------------------------------------- | ---------------------------------------------------------------- |
| `lisansli` | Geçerli lisans, süre içinde                     | Normal; son 30 günde durum çubuğunda kırmızı uyarı               |
| `tolerans` | Süre bitti, 30 gün geçmedi                      | Açılışta uyarı penceresi, sonra normal çalışır                   |
| `deneme`   | Lisans yok, ilk kullanımdan beri 30 gün geçmedi | Normal; başlıkta "Deneme sürümü - N gün"                         |
| `kapali`   | Deneme veya ek süre bitti                       | Yalnızca lisans penceresi (yükle, talep oluştur, yedekle, çıkış) |

Ek korumalar:

- **Deneme başlangıcı** hem veritabanına (`ayarlar.lisans_deneme_baslangic`) hem veri klasöründeki gizli
  `.meskoord_kurulum` dosyasına yazılır; en erken tarih geçerlidir.
- **Tarih geri alma:** Programın en son çalıştığı tarih (`ayarlar.lisans_son_gorulme`) saklanır. Bilgisayar
  tarihi bundan 3 günden fazla gerideyse saklanan tarih esas alınır ve kullanıcı uyarılır.

### 8.5 Sınırlar (dürüst değerlendirme)

Python programları tersine mühendisliğe karşı tam korunamaz; kararlı biri lisans denetimini paket içinden
devre dışı bırakabilir. Bu sistem **dürüst kullanıcıyı yönlendirmek ve kopyalamayı zahmetli/anlamsız kılmak**
için tasarlanmıştır; asıl caydırıcılık kurum adının resmî belgelere kilitlenmesi ve lisans sözleşmesidir.
Daha güçlü koruma istenirse paketleme Nuitka (C'ye derleme) ile yapılabilir; bu ayrı bir çalışmadır.

### 8.6 Anahtar güvenliği, kaybolma ve ele geçirilme

- **Özel anahtar** (`ozel_anahtar_KM1.pem`) lisans üretmeye yarar; **yalnızca döner sermaye bilgisayarında**
  `Belgeler\MesKoord_Lisans_Yonetimi` klasöründe ve iki ayrı USB yedekte durur. Proje klasörüne, e-postaya,
  bulut sürücüye konmaz. Şifreyle korunmalıdır: Lisans Yöneticisi > "Anahtar ve Doğrulama" >
  "Özel Anahtar Şifresini Değiştir".
- **Açık anahtar** programın içindedir (`lisans.py` → `ACIK_ANAHTARLAR`); gizli değildir.
- **Anahtar kaybolursa** (yedek de yoksa): Mevcut lisanslar çalışmaya devam eder, ama yeni lisans üretilemez.
  Yeni anahtar üretin (`python araclar\lisans_yonetici.py anahtar-olustur --kimlik KM2 --sifreli --koda-yaz`),
  yeni sürüm çıkarın; eski `KM1` satırını **silmeyin** ki eski lisanslar geçerli kalsın.
- **Anahtar başkasının eline geçerse:** Yeni anahtar (`KM2`) üretin, `lisans.py` içinden `KM1`'i silin, yeni
  sürüm çıkarın ve bütün geçerli lisansları kayıt defterinden `KM2` ile yeniden üretip okullara gönderin
  (eski anahtarla imzalanmış her lisans yeni sürümde geçersiz olur).

---

## 9. Döner sermaye satış ve lisans işlemleri

### 9.1 Lisans Yöneticisi

`araclar\lisans_yonetici.bat` dosyasına çift tıklanınca açılır (yalnızca özel anahtarın bulunduğu döner sermaye
bilgisayarında). Üç sekmesi vardır:

- **Lisans Üret:** Okulun gönderdiği talep metni üstteki kutuya yapıştırılınca form kendiliğinden dolar.
  Başlangıç/bitiş (varsayılan: içinde bulunulan eğitim yılının 31 Ağustos'u) veya "Süresiz", fatura/makbuz no
  ve tutar girilir, **Lisans Üret**'e basılır.
- **Verilen Lisanslar:** Kayıt defteri (`lisanslar.csv`, Excel'de açılabilir).
- **Anahtar ve Doğrulama:** Bir `.lic` dosyasının geçerliliğini denetleme, anahtar şifresi.

Komut satırı karşılığı (toplu işler için):

```powershell
.venv\Scripts\python.exe araclar\lisans_yonetici.py uret --kurum-kodu 123456 --kurum-adi "Atatürk MTAL" --il Ankara --ilce Çankaya --bitis 31.08.2027 --fatura-no "2026/15" --tutar 2500
.venv\Scripts\python.exe araclar\lisans_yonetici.py liste
.venv\Scripts\python.exe araclar\lisans_yonetici.py dogrula "dosya.lic"
```

Üretilen dosyalar `Belgeler\MesKoord_Lisans_Yonetimi\Verilen_Lisanslar\` içindedir:
`KM-2026-0007_123456_Ataturk_MTAL.lic` (lisans) ve `..._KOD.txt` (kurulum talimatı + lisans kodu).

### 9.2 Satış akışı

1. **Talep:** Okul programı kurar (30 gün deneme). Yardım > Lisans Bilgileri > **Lisans Talebi Oluştur** ile
   kurum bilgilerini (MEBBİS'teki resmî ad ve kurum kodu) doldurur, talep metnini e-postayla/resmî yazıyla gönderir.
2. **Kontrol:** Kurum kodu ve adı MEBBİS'ten doğrulanır (lisansa kilitlenecek ve belgelerde görünecek).
3. **Ödeme:** Döner sermaye fiyat tarifesine göre fatura kesilir, tahsilat yapılır.
4. **Lisans:** Lisans Yöneticisi'nde fatura no ile üretilir.
5. **Teslim:** `.lic` ve `_KOD.txt` okula gönderilir. Okul ya kurulum dosyasının yanına koyar ya da program
   içinden yükler.
6. **Kayıt:** `lisanslar.csv` her lisansta kendiliğinden güncellenir; muhasebe kayıtlarıyla ayda bir eşleştirin.

### 9.3 Yenileme ve değişiklikler

- **Yıllık yenileme:** Ağustos başında, bitişi 31 Ağustos olan okullara hatırlatma gönderin
  (`lisanslar.csv`'yi bitiş tarihine göre süzün). Yeni lisans aynı kurum koduyla, yeni süreyle üretilir;
  okul yükleyince yenisi geçerli olur.
- **Kurum adı değişti / yanlış yazıldı:** Aynı süreyle yeni lisans üretin, kayıt defterinde eskisinin `not`
  sütununa "X nolu lisansla değiştirildi" yazın.
- **Okul kapandı/birleşti:** Yeni kurum kodu için yeni lisans gerekir.
- İptal edilen bir lisansı programın tanımaması için uzaktan bir mekanizma yoktur (çevrim dışı sistem); bu
  yüzden süreli lisans tercih edin.

### 9.4 Yedekleme (döner sermaye bilgisayarı)

`Belgeler\MesKoord_Lisans_Yonetimi` klasörünün tamamını (özel anahtar, `ayarlar.json`, `lisanslar.csv`,
`Verilen_Lisanslar`) her lisans üretiminden sonra veya en az ayda bir USB'ye yedekleyin.

---

## 10. Destek ve arıza giderme

**İlk bakılacak yer:** okul bilgisayarında `Belgeler\MesKoord\hata_gunlugu.txt`. Kurulu programın eksiksiz
olup olmadığı: `"C:\Program Files\MesKoord\MesKoord.exe" --kendini-sina C:\rapor.txt` → `C:\rapor.txt`.

| Belirti                                                  | Neden / Çözüm                                                                                                                                                                                                                                                                |
| -------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Lisans imzası geçersiz"                                 | Dosya elle değiştirilmiş veya kod eksik kopyalanmış. Orijinal `.lic`'i yeniden gönderin.                                                                                                                                                                                     |
| "Tanınmayan bir anahtarla imzalanmış"                    | Okulda eski sürüm var, lisans yeni anahtarla üretilmiş. Güncel sürümü kurdurun.                                                                                                                                                                                              |
| Lisans yüklendi ama "Deneme sürümü" yazıyor              | Lisans başlangıç tarihi ileride olabilir; Yardım > Lisans Bilgileri'ndeki mesajı okuyun.                                                                                                                                                                                     |
| "Bilgisayarın tarihi ... önce görünüyor"                 | Windows tarih/saati yanlış. Düzeltilince uyarı kalkar. Tarih bir ara yanlışlıkla **ileri** ayarlanıp program o tarihte açıldıysa, veritabanında `DELETE FROM ayarlar WHERE anahtar='lisans_son_gorulme'` çalıştırın (önce yedek alın; DB Browser for SQLite kullanılabilir). |
| Kurum adı değiştirilemiyor                               | Lisanslı kurumda bilerek kilitlidir. Ad yanlışsa yeni lisans üretin (9.3).                                                                                                                                                                                                   |
| SGK işe giriş/çıkış sayfası açılmıyor veya sekme çöküyor | PySide6 sürümü 6.10.2 değilse oluşur (`requirements.txt`). Kullanıcı "Edge/Chrome'da Aç" ile devam edebilir; Downloads izleme seçeneği indirilen Excel'leri yine aktarır.                                                                                                    |
| e-Okul/SGK oturumu her açılışta yeniden isteniyor        | Bilerek böyledir: şifre ve oturum çerezi diske yazılmaz.                                                                                                                                                                                                                     |
| "Windows bilgisayarınızı korudu" uyarısı                 | Kod imzası yok. "Ek bilgi > Yine de çalıştır"; kalıcı çözüm kod imzalama (7.5).                                                                                                                                                                                              |
| Virüs programı exe'yi siliyor                            | PyInstaller paketlerinde görülen yanlış alarm. Kod imzalama; geçici olarak program klasörü için istisna.                                                                                                                                                                     |
| Kurulum "yönetici yetkisi" istiyor                       | "Yalnızca benim için" seçeneği veya taşınabilir zip (7.4).                                                                                                                                                                                                                   |
| Veriler kayboldu / yanlış işlem yapıldı                  | Ayarlar > Veri ve Yedekleme > **Yedekten Geri Yükle**; `Yedekler` klasöründe tarihli yedekler vardır. Geri yükleme önce mevcut durumu da yedekler.                                                                                                                           |
| Bilgisayar değişiyor                                     | Eski bilgisayarda `Belgeler\MesKoord` klasörünü yenisine kopyalayın, programı kurun. Lisansı yeniden yükleyin veya kurulumu `.lic` ile yapın.                                                                                                                                |
| Birden fazla kullanıcı aynı veriyle çalışmak istiyor     | **Çok Kullanıcılı Çalışma (Ağ)** ekranı: bir bilgisayar sunucu, diğerleri istemci (bölüm 16). `meskoord.db`'yi ağ paylaşımına koyup iki bilgisayardan açmayın; veri bozabilir.                                                                                               |
| İstemci "Sunucuya bağlanılamadı" diyor                   | Sunucu bilgisayarı açık ve MesKoord orada çalışıyor mu? İki bilgisayar aynı ağda mı (`ping sunucu-adresi`)? Güvenlik duvarı kuralı (16.4) var mı? Sunucu bilgisayarının IP'si değişmiş olabilir; ağ ekranında yeniden "Ağdaki Sunucuları Bul".                               |
| "Sunucunun kimlik sertifikası değişmiş"                  | Sunucuda `Belgeler\MesKoord\Sunucu` silindiyse ya da sunucu başka bilgisayara taşındıysa normaldir: sunucu ekranındaki doğrulama koduyla karşılaştırıp kabul edin. Taşınma yoksa bağlanmayın, ağı denetleyin.                                                                |
| "Sunucudaki MesKoord sürümü ..., bu bilgisayardaki ..."  | Ağdaki bütün bilgisayarlara aynı sürüm kurulmalıdır; önce sunucuyu güncelleyin.                                                                                                                                                                                              |
| Belge şablonu bozuldu                                    | `Belgeler\MesKoord\Sablonlar` içindeki ilgili `.docx`'i silin; program yeniden üretir.                                                                                                                                                                                       |
| "Bu işlem için yetkiniz yok"                             | Kullanıcı hesapları açık ve kişinin rolü izin vermiyor. Okulun Yönetici hesabı sahibi _Ayarlar > Kullanıcılar_'da rolü değiştirir.                                                                                                                                           |
| Okuldaki bütün Yönetici parolaları unutuldu              | 18.4'teki kurtarma adımları.                                                                                                                                                                                                                                                 |
| Sunucu pencereyi kapatınca kapanmıyor                    | Bilerek tepside çalışır (18.5). Kapatmak: tepsi simgesi > sağ tık > Güvenli Çıkış. İstenmiyorsa ağ ekranında "Pencere kapatılınca sistem tepsisinde çalışmayı sürdür" kaldırılır.                                                                                            |
| Program açılmıyor, hiçbir pencere çıkmıyor               | Bir örnek zaten tepside çalışıyor olabilir; ikinci açılış yalnızca onu öne getirir. Görev Yöneticisi'nde `MesKoord.exe` kontrol edilir.                                                                                                                                      |
| İkinci yedek klasörüne kopyalanamıyor uyarısı            | USB takılı değil ya da ağ klasörüne yazma izni yok. Asıl yedek yine alınmıştır; `yedek_ayarlari.json` → `son_hata` ayrıntıyı içerir.                                                                                                                                         |
| Hesaplanan tutarlar yanlış                               | Önce **Ayarlar > Mevzuat Parametreleri** güncel mi bakın (asgari ücret, Geçici 12). Sonra öğrencinin program/statü/başlangıç tarihi ve işletmenin personel sayısı. Hata kodda ise testle birlikte düzeltin.                                                                  |

Hata bildirimi alırken okuldan şunları isteyin: program sürümü (Yardım > Hakkında), ekran görüntüsü,
`hata_gunlugu.txt`, gerekiyorsa **kişisel veriler çıkarılmış** örnek dosya. Gerçek öğrenci verisi içeren
veritabanını e-postayla istemeyin (bkz. 12).

---

## 11. Yıllık bakım takvimi

| Ne zaman               | İş                                                                                                                                                                                                      |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Aralık sonu / Ocak** | Yeni asgari ücret (`asgari_ucret_brut`, `asgari_ucret_net`) → `mevzuat.py` + sürüm (5.1). Öğrencinin SGK prime esas kazancı brüt asgari ücret × `sgk_pek_orani` (0,50) olarak kendiliğinden hesaplanır. |
| **Ocak ve Temmuz**     | Memur aylık katsayısı (`aylik_katsayi`) → ek ders ücreti.                                                                                                                                               |
| **Haziran-Ağustos**    | 3308 Geçici 12. madde (devlet katkısı) uzatma durumu, yeni eğitim yılı mevzuat değişiklikleri; yeni yıl sürümü.                                                                                         |
| **Ağustos**            | Bitişi 31 Ağustos olan lisanslar için yenileme hatırlatması (9.3). Çerçeve öğretim programları: `araclar\cerceve_guncelle.py` ile MEB'deki yeni çizelgeler kontrolü (5.9).                              |
| **Eylül**              | Okullardan gelen kurulum/lisans talepleri; e-Okul/e-Mesem/SGK ekranlarında değişiklik var mı kontrolü (bağlantı ekranı ve içe aktarma).                                                                 |
| **Her 6 ayda bir**     | Bağımlılık güncellemesi: `pip list --outdated`; güncelledikten sonra testler + SGK 4A sayfası elle deneme. PySide6 sabitlemesine dikkat (2.1).                                                          |
| **Her ay**             | Döner sermaye yönetim klasörü yedeği (9.4); `lisanslar.csv` ↔ muhasebe eşleştirmesi.                                                                                                                    |
| **Her sürümde**        | `SURUM_NOTLARI.md`, testler, `kurulum_sina.py`, git etiketi, okullara duyuru.                                                                                                                           |

---

## 12. Güvenlik ve kişisel veriler (KVKK)

- Program öğrenci TC kimlik no, IBAN, adres gibi **kişisel veriler** işler. Bu veriler yalnızca okulun
  bilgisayarında (`Belgeler\MesKoord`) durur; program hiçbir sunucuya veri göndermez, kullanım istatistiği
  (telemetri) toplamaz. Bu özellik korunmalıdır: programa veri gönderen bir özellik eklenecekse önce hukuki
  değerlendirme yapılmalı ve lisans sözleşmesi güncellenmelidir.
- Veri sorumlusu okuldur. Döner sermaye (satıcı) okul verisine erişmez; destek verirken de gerçek veri
  istenmemelidir. Ekran paylaşımlı uzaktan destekte okul yetkilisi bilgisayar başında olmalıdır.
- e-Okul/e-Mesem/SGK şifreleri program tarafından saklanmaz; gömülü tarayıcı oturum çerezlerini diske yazmaz
  (`sayfa_baglanti.py` → `NoPersistentCookies`). Bu davranışı değiştirmeyin.
- Geliştirme ve testte yalnızca örnek veri (`services/ornek_veri.py`) kullanılır; depoya gerçek veri konmaz.
- Özel imza anahtarı (8.6) ve lisans kayıt defteri (okulların iletişim bilgileri) gizli tutulur.
- **Ağ kipi:** veri yalnızca okulun yerel ağında, TLS ile şifreli ve sunucu parolasıyla korunarak dolaşır.
  Sunucu parolası yalnızca scrypt özeti olarak saklanır; istemcinin hatırladığı parola Windows DPAPI ile o
  kullanıcı hesabına bağlı şifrelenir. Güvenlik duvarı kuralı yalnızca yerel alt ağdan bağlantıya izin verir.
  Sunucu internete açılmamalı (modemde port yönlendirme yapılmamalı); bu kurallar gevşetilmemelidir.
- **Kullanıcı hesapları ve işlem günlüğü:** kişisel parolalar scrypt özeti olarak saklanır, özet sütunu
  programın kendi bağlantılarında okunamaz. İşlem günlüğünde T.C. kimlik no, IBAN, telefon, adres, e-posta ve
  doğum tarihi \*\*\* olarak tutulur (`hesaplar.GIZLI_KOLONLAR`); yeni bir kişisel veri kolonu eklenirse bu
  listeye de eklenmelidir. Günlük 2 yıl saklanır (`GUNLUK_SAKLAMA_GUN`).

---

## 13. Hukuki ve idari kontrol listesi

> Bu bölüm hukuki görüş değildir; satışa başlamadan önce okul idaresi, döner sermaye işletme müdürlüğü,
> il millî eğitim müdürlüğü ve gerekirse hukuk müşavirliği ile **doğrulanması gereken** konuları listeler.

- [ ] **Eser sahipliği ve hakların devri (5846 sayılı FSEK):** Programı geliştiren(ler) ile döner sermaye
      işletmesi arasında, programın mali haklarının (çoğaltma, yayma, satış) işletmeye devrini veya
      kullandırılmasını düzenleyen yazılı bir sözleşme/onay. Program görev kapsamında mı, kişisel emekle mi
      geliştirildi; bu durum hak sahipliğini etkiler.
- [ ] **Döner sermaye mevzuatı:** Yazılım lisansı satışının işletmenin faaliyet konusu içinde olduğu,
      gerekli onayların (işletme müdürlüğü / yönetim kurulu / il MEM) alındığı.
- [ ] **Fiyat tarifesi:** Lisans bedelinin (yıllık / süresiz, okul türüne göre) onaylı tarifeye bağlanması.
- [ ] **Fatura / makbuz ve vergi:** Lisans satışının nasıl faturalandırılacağı (e-Arşiv vb.), KDV durumu.
- [ ] **Üretime katılan personele pay** dağıtımı yapılacaksa ilgili mevzuata uygunluk.
- [ ] **Lisans sözleşmesi** (`dagitim/LISANS_SOZLESMESI.txt`): köşeli parantezli yerler dolduruldu, hukuk
      birimince gözden geçirildi.
- [ ] **Açık kaynak lisansları:** PySide6/Qt **LGPLv3** ile kullanılır. Yükümlülükler: Qt kütüphaneleri ayrı
      DLL olarak kalır (onedir paket bunu sağlar), lisans bildirimi pakettedir (`UCUNCU_TARAF_LISANSLARI.txt`,
      `surum_hazirla.py` üretir), Qt'nin değiştirilmemiş olması. Qt'nin kaynak kodu değiştirilirse ek
      yükümlülük doğar; değiştirmeyin.
- [ ] **KVKK:** Okullara verilecek bilgilendirmede programın veriyi yerel tuttuğu açıkça yazılı (sözleşme md. 5).
- [ ] **Sorumluluk sınırı:** Programın yardımcı araç olduğu, resmî bildirimlerden okulun sorumlu olduğu
      sözleşmede ve programda (Hakkında) belirtilmiş.

---

## 14. Devir teslim kontrol listesi

| #   | Teslim edilen                                                                                          | Teslim alan kontrol etti |
| --- | ------------------------------------------------------------------------------------------------------ | ------------------------ |
| 1   | Kaynak kod + git geçmişi (uzak depo erişimi dahil)                                                     | ☐                        |
| 2   | Özel imza anahtarı: 2 USB yedek + şifre (kapalı zarfta)                                                | ☐                        |
| 3   | `MesKoord_Lisans_Yonetimi` klasörü (`lisanslar.csv`, `Verilen_Lisanslar`, `ayarlar.json`)              | ☐                        |
| 4   | Son sürüm paketleri (`cikti\MesKoord_X.Y.Z`)                                                           | ☐                        |
| 5   | Kod imzalama sertifikası ve şifresi (varsa)                                                            | ☐                        |
| 6   | Destek e-posta hesabı / telefon hattı bilgileri                                                        | ☐                        |
| 7   | Satış yapılan okulların listesi ve açık destek talepleri                                               | ☐                        |
| 8   | Döner sermaye onay yazıları, fiyat tarifesi, hak devri sözleşmesi                                      | ☐                        |
| 9   | Teslim alan, geliştirme ortamını kurdu ve testler geçti                                                | ☐                        |
| 10  | Teslim alan, deneme paketi üretti ve `kurulum_sina.py` başarılı                                        | ☐                        |
| 11  | Teslim alan, Lisans Yöneticisi ile deneme lisansı üretip doğruladı (kayıt defterinde "deneme" notuyla) | ☐                        |

Teslim eden: ................................ Teslim alan: ................................ Tarih: ..../..../........

---

## 15. Bilinen sınırlar ve yol haritası

**Bilinen sınırlar**

- Çok kullanıcılı çalışmada sunucu bilgisayarı açık ve MesKoord orada çalışır durumda olmalıdır (ayrı bir
  Windows hizmeti değildir; Windows oturumu açılınca tepside kendiliğinden başlayabilir, bkz. 18.5). Sunucu
  kapanınca istemciler yeniden bağlanmayı bekler.
- Roller tablo düzeyindedir (ör. "Personel kurum bilgilerini değiştiremez"); satır düzeyi kural (ör. "yalnızca
  kendi işletmeleri") yoktur.
- Yetki ve günlük programın kendi bağlantılarında uygulanır. Veritabanı dosyasına doğrudan erişebilen biri
  (dosyayı DB Browser ile açan) bunları atlayabilir; dosyanın kendisi Windows klasör izinleriyle korunur.
- Aynı anda yazmalar SQLite kilitleriyle sıraya girer; okul ölçeğinde (onlarca kullanıcı) yeterlidir, yüzlerce
  eşzamanlı kullanıcı için tasarlanmamıştır.
- Lisans çevrim dışıdır: verilmiş bir lisans uzaktan iptal edilemez (süreli lisans tercih nedeni).
- Python paketleri tersine mühendisliğe karşı tam korunamaz (8.5).
- e-Okul, e-Mesem ve SGK ekranları değiştiğinde içe aktarma başlık eşleştirmeleri güncellenmelidir.

**Önerilen geliştirmeler (öncelik sırasıyla)**

e-Bildirge V2 aylık XML'i, 4A toplu işe giriş/çıkış XML'i (`services/sgk_dosya.py`), güncelleme denetimi
(7.7), e-posta/WhatsApp paylaşımı ve toplu gönderim (`services/paylasim.py`, `services/toplu_gonderim.py`)
yapıldı.

1. **Kod imzalama** (7.5).
2. Lisans Yöneticisi'ne yenileme hatırlatma listesi ve kayıt defterinden toplu yeniden üretim.
3. Ağ sunucusunun Windows hizmeti olarak (oturum açılmadan) çalışabilmesi. Bugün Windows oturumu açılınca
   tepside başlar (18.5); çoğu okul için yeterlidir.
4. Toplu gönderime velilere devamsızlık bildirimi (telefon numarası olanlara WhatsApp).

---

## 16. Çok kullanıcılı çalışma (ağ modu)

### 16.1 Okulda kurulum (kullanıcıya anlatılacak)

1. Bütün bilgisayarlara **aynı sürüm** MesKoord kurulur (kurulum güvenlik duvarı iznini kendisi ekler).
2. Verilerin duracağı bilgisayarda (genellikle koordinatör müdür yardımcısı): **Sistem > Çok Kullanıcılı
   Çalışma (Ağ)** > "Sunucu olsun" > en az 6 karakterli bir **sunucu parolası** > _Kaydet ve Yeniden Başlat_.
   Ekranda bu bilgisayarın adresi ve **doğrulama kodu** görünür.
3. Diğer bilgisayarlarda aynı ekran > "Ağdaki sunucuya bağlansın" > _Ağdaki Sunucuları Bul_ (ya da adresi elle
   yazın) > adınız ve sunucu parolası > _Bağlantıyı Sına_. Çıkan doğrulama kodu sunucudakiyle aynıysa onaylayın
   > _Kaydet ve Yeniden Başlat_.
4. Daha önce bir istemcide veri girildiyse: o bilgisayarda Ayarlar > Veri Yönetimi'nden yedek alınır, sunucuda
   _Yedekten Geri Yükle_ ile yüklenir (geri yükleme önce sunucudaki mevcut veriyi yedekler).
5. Lisans yalnızca sunucuya yüklenir; istemciler sunucunun lisansını kullanır.

Durum çubuğunun solunda bağlantı durumu ve çevrim içi kullanıcı sayısı görünür (üzerine gelince kimlerin bağlı
olduğu listelenir). Başka bir kullanıcının kaydettiği değişiklik açık ekranlarda yaklaşık yarım saniye içinde
görünür; durum çubuğunda "Güncellendi: Ayşe değişiklik yaptı" yazar. Aynı kaydı iki kişi aynı anda düzenlerse
farklı alanlar birleştirilir, aynı alan değiştiyse kullanıcıya hangisinin geçerli olacağı sorulur
(`ui/crud.py` → `FormDialog._degisenler`).

### 16.2 Mimari

```
 İstemci bilgisayar                                   Sunucu bilgisayar
 ┌──────────────────────────┐   HTTPS (TLS 1.2+)     ┌───────────────────────────────────────┐
 │ ui + services            │   port 47400           │ MesKoord penceresi (SunucuDatabase)   │
 │   db = UzakDatabase ─────┼──── /sql  ───────────► │ KoordSunucu (iş parçacığı)            │
 │   OlayDinleyici ─────────┼──── /bekle (uzun) ◄─── │   oturum başına ayrı sqlite3 bağlantı │
 └──────────────────────────┘   UDP 47401 keşif      │   meskoord.db (WAL kipi)              │
                                                      └───────────────────────────────────────┘
```

- **Oturum başına SQLite bağlantısı:** Her istemci penceresi ve her arka plan işi (`db.kopya()`) sunucuda kendi
  bağlantısını alır. `BEGIN/SAVEPOINT/COMMIT`, `with db.conn:` ve hata durumunda geri alma yerel çalışmayla
  birebir aynıdır; eşzamanlı yazmaları SQLite kilidi (30 sn bekleme) sıraya koyar. Veritabanı WAL kipine
  alınır, okuyanlar yazanı beklemez.
- **`UzakBaglanti`** `sqlite3.Connection` yüzünü taklit eder; komutlar toplu (`/sql`, `islemler` listesi)
  gider, `Satir` nesneleri `sqlite3.Row` gibi davranır, hatalar aynı sqlite3 istisna türleriyle döner.
  `Database.execute` (komut + kaydet) tek gidiş-dönüştür.
- **Bildirim:** Sunucu, kaydedilen her işlemin değiştirdiği tabloları bir "olay" olarak yayınlar. İstemcinin
  `OlayDinleyici` iş parçacığı `/bekle` ile 25 sn'ye kadar bekler; olay gelince `AgKoprusu.degisti` sinyali ana
  pencerede `_canli_yenile`'yi tetikler (açık bir pencere/menü varsa yenileme ertelenir). Sunucu bilgisayarının
  kendi değişiklikleri `SunucuDatabase` (izlenen bağlantı) ile yayınlanır. Kendi değişikliğimiz için bildirim
  gelmez (`ISTEMCI_NO`).
- **Sayfa yenileme kuralı:** `ana_pencere.sayfayi_yenile` sayfada sırasıyla `canli_yenile()`, `yenile()` ya da
  `doldur()` arar. Yeni bir ekran yazıyorsanız bunlardan birini verin; kullanıcının yazdığı veriyi silecek
  ekranları (`CANLI_YENILEME_DISI`) listeye ekleyin.
- **Yarım kalan işlemler:** 120 sn işlem yapmayan açık transaction geri alınır; 15 dk görünmeyen oturum kapanır.
  İstemci oturumu düşerse işlem yoksa sessizce yeniden giriş yapar, işlem varsa "geri alındı" hatası verir.
- **Güvenlik:** kendinden imzalı EC P-256 sertifika (`Belgeler\MesKoord\Sunucu`), istemcide SHA-256 parmak izi
  sabitlemesi (ilk bağlantıda kullanıcı doğrulama koduyla onaylar), scrypt parola özeti, hatalı parolada 1 sn
  gecikme ve 5 dk içinde 10 hatada kilit, `ATTACH/DETACH/VACUUM/load_extension` yasak.
- **Yedek:** İstemcide "Şimdi Yedekle" sunucuda otomatik yedek alır; oturum Yönetici ise (ya da hesaplar
  kapalıysa) bir kopyasını istemcinin `Yedekler` klasörüne indirir, diğer rollerde yedek sunucuda kalır
  (`X-Yedek-Sunucuda` başlığı, istemcide `SunucudakiYedek`). Geri yükleme yalnızca Yönetici içindir;
  sunucuda doğrulanır, önce mevcut veri yedeklenir, herkes yenilenir.
- **Kimlik:** Oturum açılırken hesaplar açıksa kullanıcı adı ve kişisel parola `hesaplar.dogrula` ile,
  kapalıysa sunucu parolasıyla denetlenir. 403 yanıtındaki `hesap` alanı istemciye hangi giriş biçiminin
  beklendiğini söyler (`ParolaHatasi.hesap`); istemci buna göre kişisel giriş penceresine geçer. Oturumun
  `Kimlik`'i sunucudaki bağlantısına uygulanır (bkz. 18.1).

### 16.3 Protokolü değiştirirken

- Uyumsuz bir değişiklikte `ag/protokol.py` → `PROTOKOL` artırılır. İstemci sunucunun `SCHEMA_VERSION`'ı ve
  sürümün ilk iki hanesi farklıysa bağlanmaz; yeni kolon eklediğiniz her sürümde Y (küçük sürüm) artırın.
- Değişiklikten sonra: `tests/test_ag.py`, `tests/test_ui_ag.py`, `MESKOORD_TEST_UZAK=1` ile tam test ve
  `araclar\ag_sinama.py`.

### 16.4 Güvenlik duvarı ve ağ

- Kurulum `netsh advfirewall firewall add rule name="MesKoord" ... program=MesKoord.exe remoteip=localsubnet`
  ile kural ekler, kaldırınca siler. Taşınabilir zip kullananlarda kural yoktur; Windows ilk sunucu açılışında
  izin sorar ("Özel ağlar" işaretlenmeli).
- Okulun ağı farklı alt ağlara (VLAN) bölünmüşse keşif (UDP yayını) diğer alt ağa geçmez; adres elle yazılır ve
  güvenlik duvarı kuralında `remoteip` okulun ağ aralığıyla genişletilir.
- Sunucu bilgisayarına sabit IP (ya da DHCP rezervasyonu) verilmesi ve uyku modunun kapatılması önerilir.

---

## 17. Marka kimliği ve görseller

Ayrıntılı kurallar: `docs/MARKA_KIMLIGI.md`.

- Bütün görseller dış görsel kullanılmadan geometriden çizilir. `python araclar\marka_olustur.py`
  çalıştırılınca `koordmes/gorseller/*.png`, `dagitim/meskoord.ico`, `dagitim/kurulum_*.bmp` ve
  `dagitim/marka/` içindeki simge (SVG ve 1024 px), logo ve tanıtım afişi yeniden üretilir. Ölçüler aracın
  başındaki `GEO` (ayrıntılı) ve `GEO_SADE` (16–32 piksel) sözlüklerindedir.
- Renkler ve arayüz stili `koordmes/marka.py` içindedir (`ANA`, `VURGU` ...). Koda renk kodu gömmeyin,
  `marka` sabitlerini kullanın.
- **Kurum logosu:** Programı kullanan okul kendi logosunu Ayarlar > Kurum Bilgileri'nden yükler; Word belgelerine
  (`{{kurum_logosu}}` yer tutucusu) ve PDF raporlarına basılır. Yüklenmemişse belgeler logosuz çıkar. Ürün
  simgesi (MesKoord) ile kurum logosu birbirine karıştırılmaz; programla hiçbir okulun logosu dağıtılmaz.

---

## 18. Kullanıcı hesapları, işlem günlüğü, otomatik yedek ve sistem tepsisi

### 18.1 Yetki: bağlantı düzeyinde

Servis ve ekran kodu kullanıcıyı bilmez. Her veritabanı bağlantısı açılırken `hesaplar.baglantiyi_hazirla(conn,
kimlik)` çağrılır:

- `conn.set_authorizer(hesaplar.yetkilendirici(rol))`: SQLite her okuma/yazma için geri çağrıyı sorar.
  - Yönetici: her şey.
  - Personel: `kurum`, `ayarlar` (`YONETICI_TABLOLARI`) ve `kullanicilar` tablolarına yazamaz (kendi
    parola sütunları hariç; başkasının parolasını değiştirmeyi geçici bir tetikleyici engeller). `DROP` ve
    `ALTER` yapamaz.
  - Salt okunur: hiçbir yazma.
  - Herkes için: `kullanicilar.parola_ozeti` okunamaz (boş döner), `ATTACH/DETACH` ve geçici tetikleyici
    oluşturma/silme yasak, `islem_gunlugu`'na doğrudan yazılamaz.
- Reddedilen işlem `sqlite3.DatabaseError("not authorized")` verir; `hesaplar.yetki_hatasi_mi(e)` bunu tanır.
  `run.py` → `hata_yakala` kullanıcıya "Bu işlem için yetkiniz yok" gösterir.
- `Kimlik` (ad, rol, kullanıcı adı, bilgisayar, `hesapli`) `db.kimlik`'tedir. `Database(yol, kimlik)`,
  `db.kopya()` (arka plan işleri) ve `geri_yukle` aynı kimliği yeniden uygular. Ağda sunucu her oturumun
  kendi bağlantısına oturumun kimliğini uygular; istemci yetkiyi atlatamaz.
- Ekranlardaki gizleme/salt okunur yapma (`sayfa_ayarlar._yetki_uygula`, Kullanıcılar sekmesi) yalnızca
  kullanıcı kolaylığıdır.
- Hesaplar kapalıyken (`kullanicilar`'da etkin kayıt yok) herkes `Kimlik.varsayilan` ile Yöneticidir; ağda
  sunucu parolası sorulur. İlk etkin Yönetici hesabı oluşturulunca hesaplar açılır.

Yeni rol ya da kural: `yetkilendirici()` ve `ROLLER/ROL_ACIKLAMALARI`; testi
`tests/test_kullanici_hesaplari.py`'ye ekleyin (yerel ve ağ senaryosu ayrı ayrı vardır).

### 18.2 İşlem günlüğü

- Her bağlantıya, o kullanıcının adı ve bilgisayarı gömülü **geçici (TEMP) tetikleyiciler** kurulur
  (`kg_{tablo}_{i|u|d}`). Veritabanı dosyasına kalıcı tetikleyici eklenmez; eski sürümler ve başka araçlar
  dosyayı aynen açar. `GUNLUGE_GIRMEYEN` dışındaki **bütün tablolar** kendiliğinden günlüğe girer; yeni
  tablo için ek iş gerekmez.
- Değişiklikte yalnızca gerçekten değişen sütunlar `ayrinti`'ye JSON olarak (`{"kolon": [eski, yeni]}`)
  yazılır; değer değişmediyse kayıt düşülmez. `ayarlar` UPSERT ile yazıldığından aynı değer yeniden
  kaydedilince günlük şişmez.
- `kayit` sütunu kaydın okunur adıdır (`KAYIT_ADI`; tanımsız tablolarda `ad` sütunu, o da yoksa boş;
  kaydın numarası her zaman `kayit_id`'dedir).
- Kişisel veri kolonları (`GIZLI_KOLONLAR`) `***` yazılır, değerler 80 karakterde kesilir.
- Eski kayıtlar açılışta `hesaplar.gunlugu_temizle` ile silinir (`GUNLUK_SAKLAMA_GUN` = 730).
- Ekran: `ui/sayfa_kullanicilar.py` → `IslemGunluguSekmesi`; kolon etiketleri `varliklar.py`'deki alan
  etiketlerinden kendiliğinden gelir.

### 18.3 Giriş akışı

- Tek bilgisayar / sunucu: `run.py` lisanstan sonra `giris.kullanici_girisi(db)` çağırır; hesaplar açıksa
  `yerel_giris` kullanıcı adı/parola sorar, `db.kimlik_ata(kimlik)` bağlantıya uygular. Parolası sıfırlanmış
  kullanıcı (`parola_degistirmeli`) önce kendi parolasını belirler.
- İstemci: `ag_baslat._istemci` sunucunun yanıtına göre sunucu parolası ya da kişisel giriş sorar;
  `ag_ayarlari.json` → `hesap` bir sonraki açılışta doğrudan doğru pencereyi açar. Kişisel parola diske
  yazılmaz.
- "Kullanıcı Değiştir" programı yeniden başlatır (en basit ve güvenli yol: bütün ekranlar yeni yetkiyle
  kurulur).

### 18.4 Bütün Yönetici parolaları unutulursa

1. Programı her yerde kapatın (sunucuda tepsi simgesi > Güvenli Çıkış).
2. `Belgeler\MesKoord\meskoord.db` dosyasının bir kopyasını alın.
3. DB Browser for SQLite ile `meskoord.db`'yi açıp `UPDATE kullanicilar SET aktif = 0;` çalıştırın ve
   kaydedin. Hesaplar kapanır, program açılışta parola sormaz.
4. MesKoord'u açın, _Ayarlar > Kullanıcılar > Kullanıcı Hesaplarını Aç..._ ile Yöneticinin **aynı kullanıcı
   adıyla** yeni parola belirleyin (hesap yeniden etkinleşir). Diğer personeli "Düzenle..." ile yeniden
   etkinleştirin.

### 18.5 Otomatik yedek, sistem tepsisi, Windows açılışında başlama

- **Otomatik yedek** (`yedekleme.py`): ayarlar veri klasöründe `yedek_ayarlari.json`'dadır (veritabanında
  değil; her bilgisayarın kendi diski ve USB'si için). `ana_pencere._otomatik_yedek` açılıştan 90 sn sonra ve
  her 10 dakikada bir `zamani_geldi()`'yi sorar; istemcide çalışmaz (yedeği sunucu alır). Her otomatik
  `db.yedekle()` sonunda `yedekleme.yedek_alindi` son yedek zamanını yazar ve ikinci klasöre
  (`<seçilen>\MesKoord_Yedekler`, en yeni 30) kopyalar; hata `son_hata`'ya yazılır ve Veri ve Yedekleme
  sekmesinde kırmızı görünür.
- **Tek örnek** (`tepsi.TekOrnek`): `QLocalServer` adı Windows kullanıcısı + veri klasöründen türetilir.
  İkinci açılış çalışan örneğe "göster" der ve çıkar; aynı veritabanında iki sunucu ve port çakışması olmaz.
  Testlerde farklı `MESKOORD_DATA` farklı ad verir.
- **Tepsi** (`tepsi.Tepsi`): yalnızca sunucu kipinde ve ağ ekranında "Pencere kapatılınca sistem tepsisinde
  çalışmayı sürdür" (`ag_ayarlari.json` → `tepside_calis`) açıksa kurulur. `AnaPencere.closeEvent` pencereyi
  gizler; gerçek çıkış `guvenli_cikis()` ile olur (sol alt düğme, Ctrl+Q, tepsi menüsü). Hesaplar açıkken
  gizli pencere tepsiden açılırken giriş yeniden sorulur (`tepsiden_ac`). Windows kapanırken
  `commitDataRequest` pencerenin kapanmasına izin verir.
- **Windows açılışında başlama**: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` → `MesKoord` değeri,
  komut `MesKoord.exe --arka-plan`. Ağ ekranındaki kutuyla yazılır/silinir; sunucu dışındaki kiplere
  geçilince silinir; kaldırma (Inno Setup `[Registry]` `uninsdeletevalue`) da siler. `--arka-plan`
  açılışında pencere ve açılış ekranı gösterilmez, giriş sorulmaz; hesaplar açıksa bağlantı geçici olarak
  "Sunucu (arka plan)" adlı salt okunur kimlikle durur, pencere tepsiden açılınca gerçek kullanıcı girer.
  Diğer bilgisayarların oturumları bundan etkilenmez (her oturum kendi kimliğiyle çalışır).

## 19. Ortaöğretim Kurumları Yönetmeliği işleri

Yönetmeliğin 82, 88, 89 ve 134-153 üncü maddelerinden gelen kurallar. Testleri `tests/test_yonetmelik.py`.

### 19.1 Veri

| Yer                           | Eklenen                                                                                                                                  |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Yeni tablolar                 | `isletme_talepleri` (alan taraması / işletme talepleri), `anketler` (mezun/işyeri izleme), `hizmetici_egitimler` (usta öğretici eğitimi) |
| `kurum`                       | `ders_yili_baslangic`, `birinci_donem_sonu`, `ders_yili_sonu` (ISO tarih; Ayarlar > Kurum Bilgileri)                                     |
| `ogretmenler`                 | `atolye_lab` (koordinatörlükte öncelik; unvanı "Atölye/Lab. Öğretmeni" olan da öncelikli sayılır)                                        |
| `ogrenciler`                  | `basari_ortalamasi`, `agir_disiplin`, `oncelikli` (son ikisi `GIZLI_KOLONLAR`'da: günlüğe \*\*\* yazılır)                                |
| `isletmeler`                  | `usta_ogretici_sayisi`, `usta_belgesi`, `egitim_birimi`, `il_disi`, `doner_sermaye`, `uygunluk_tarihi`, `plan_onay_tarihi`               |
| `yerlestirmeler.fesih_nedeni` | Serbest metin kalır; ekranda `mevzuat.FESIH_NEDENLERI` listesi. Listede olmayan eski değerler `crud.py` tarafından korunur               |

Sayısal sınırlar koda gömülmez; `mevzuat.PARAMETRELER`: `koord_grup_ogrenci` (15), ve "İşletmelerde Mesleki
Eğitim" grubu: `usta_ogretici_ogrenci` (16), `egitim_birimi_esigi` (10), `sozlesme_sure_gun` (14),
`mem_sozlesme_sure_gun` (60), `isyeri_degisikligi_gun` (14), `plan_onay_gun` (7), `puan_cizelgesi_gun` (5).

### 19.2 Kod

- **Koordinatörlük** (`services/koordinator.py`): `isletme_ihtiyaclari()` öğrencileri (işletme, alan) çiftine
  göre gruplar ve `koord_grup_ogrenci`'lik parçalara böler; her parça bir `IsletmeIhtiyaci`'dır (`grup`
  etiketi). Döner sermaye işletmeleri ve il dışı staj yerleri `kapsam_disi` listesine düşer.
  `otomatik_gorevlendir()` bütün öğretmenleri aday alır; puanlamada alan dışı +200, atölye dışı +50 ceza
  vardır; alan dışı atamalar `GorevSonucu.alan_disi`'nde döner.
- **Öğrenci seçimi** (`services/mesleki_egitim.py`): `adaylar()` → `sirala(liste, kontenjan)`. Önce öncelikli
  öğrenciler kontenjandan düşer, sonra ortalamaya göre Gönderilecek/Yedek; ortalaması girilmemiş ve ağır
  disiplin cezalı öğrenciler ayrı durumla sona eklenir. Excel `secim_excel`, Word tutanak `secim_tutanagi`.
- **Denetim** (`services/denetim.py`): `_yonetmelik_yerlestirme` (md.143 sözleşme süresi, MEM işyeri
  değişikliği, fesih nedeni, md.134 gün düzeni, puan çizelgesi) ve `_yonetmelik_isletme` (md.135 usta
  öğretici/eğitim birimi, uygunluk tespiti, plan onayı, döner sermaye, 15 öğrenci sınırı, alan dışı
  koordinatör). Bulguların `git` hedefi menü ekranı adı olmalıdır (testle denetlenir).
- **Takvim** (`services/takvim.py` → `_yonetmelik_sureleri`): kurum tarihlerinden puan çizelgesi ve sözleşme
  hatırlatmaları; tarih girilmemişse sessizce atlanır.
- **Belgeler** (`services/belgeler.py`): yeni `BELGE_TURLERI` kaynakları `isletme` (işletme başına),
  `isletme_koord` (koordinatörü olan işletmeler), `kurum` (okul geneli tek belge) ve `secim` (yalnızca
  Komisyon ekranından; hazır bağlam ister). `uret(db, anahtar, kimlik, ..., baglam=None)`: `baglam`
  verilirse veritabanından bağlam kurulmaz. Belge Üretimi ekranı yalnızca `KAYNAK_SQL`'de olan kaynakları
  listeler.
- **Süreç** (`services/surecler.py`): `"yonetmelik"` süreci ve eylemler `komisyon_karari`,
  `koordinator_bildirimleri`, `uygunluk_tutanaklari`, `alan_taramasi`, `anket_ozeti`, `hizmetici`,
  `puan_cizelgesi`. Asistan komutları `asistan.yorumla()` içindedir.
- **Ekran** (`ui/sayfa_komisyon.py`): `KomisyonSayfasi` dört sekme; `isletme_sayfasi()` İşletmeler tanım
  ekranına iki belge düğmesi ekler (`dataclasses.replace(ISLETMELER, eylemler=...)`).

Yönetmelik değişirse önce `mevzuat.py` parametresi yeterli mi bakın; madde numarası metinleri `varliklar.py`
ipuçlarında, denetim mesajlarında ve şablonlardadır (`rg "md\.1[34]"` ile bulunur).
