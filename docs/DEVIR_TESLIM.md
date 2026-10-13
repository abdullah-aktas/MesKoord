# MesKoord Devir Teslim ve Bilgilendirme Dosyası

**Kime:** Programın bakımını, geliştirilmesini ve dağıtımını devralacak bilişim teknolojileri öğretmenleri ve
yazılımcılar.
**Amaç:** Programı ilk kez gören birinin bir günde genel resmi kavraması, bir haftada tek başına hata
düzeltip sürüm çıkarabilmesi.
**Durum tarihi:** Ekim 2026 · **Sürüm:** 1.3.0

Bu dosya bir **yol haritasıdır**; ayrıntılar için her başlıkta
[Geliştirici El Kitabı](GELISTIRICI_EL_KITABI.md)'nın ilgili bölümüne bağlantı verilmiştir.

---

## İçindekiler

1. [Belge haritası](#1-belge-haritası)
2. [Program bir sayfada](#2-program-bir-sayfada)
3. [Mimari ve temel tasarım kararları](#3-mimari-ve-temel-tasarım-kararları)
4. [Kod haritası: hangi iş için nereye bakılır](#4-kod-haritası-hangi-iş-için-nereye-bakılır)
5. [Devredilen varlıklar ve gizli bilgiler](#5-devredilen-varlıklar-ve-gizli-bilgiler)
6. [Mevcut durum ve açık işler](#6-mevcut-durum-ve-açık-işler)
7. [İlk hafta planı](#7-ilk-hafta-planı)
8. [Rutin bakım işleri](#8-rutin-bakım-işleri)
9. [Değiştirirken dikkat: kırılması kolay yerler](#9-değiştirirken-dikkat-kırılması-kolay-yerler)
10. [Geliştirici için sık sorulan sorular](#10-geliştirici-için-sık-sorulan-sorular)
11. [Yol haritası](#11-yol-haritası)
12. [Devir teslim tutanağı](#12-devir-teslim-tutanağı)

---

## 1. Belge haritası

| Belge | Okuyucu | İçerik |
|---|---|---|
| `docs/DEVIR_TESLIM.md` (bu dosya) | Devralan bilişimci / yazılımcı | Genel resim, varlıklar, açık işler, ilk hafta planı, tutanak |
| `docs/GELISTIRICI_EL_KITABI.md` | Devralan bilişimci / yazılımcı | Kurulum, kod kuralları, tarifler, test, sürüm, lisans, destek, KVKK, ağ mimarisi |
| `docs/KULLANIM_KILAVUZU.md` | Okuldaki kullanıcılar | Ekran ekran kullanım, görev bazlı hızlı başlangıç, aylık takvim, sık sorulanlar |
| `docs/TANITIM.md` | Okul idaresi, satış, il/ilçe MEM | Programın tanıtımı, gereksinimler, lisanslama |
| `docs/MARKA_KIMLIGI.md` | Görsel/tanıtım işleri | Logo, renk, ad kullanım kuralları |
| `README.md` | Herkes | Kısa özet; pakete `BENIOKU.txt` olarak da girer |
| `SURUM_NOTLARI.md` | Herkes | Her sürümde ne değişti |

Kullanım kılavuzu programın içinden de açılır (**Yardım > Kullanım Kılavuzu**, F1). Kaynağı
`docs/KULLANIM_KILAVUZU.md` dosyasıdır; bu dosyayı güncellemek yeterlidir, paketleme onu programa ve kuruluma
kendiliğinden ekler. PDF kopyası: `python araclar\kilavuz_pdf.py`.

---

## 2. Program bir sayfada

| | |
|---|---|
| **Ne** | MTAL ve MEM'ler için mesleki eğitim iş ve işlemlerini (ders programı, yerleştirme, koordinatörlük, SGK, öğrenci ücreti/devlet katkısı, devamsızlık, ek ders, resmî belgeler) yürüten Windows masaüstü programı |
| **Kim kullanır** | Koordinatör müdür yardımcısı, müdür, koordinatör öğretmenler, alan şefleri, ek ders işlerini yürüten personel |
| **Nerede çalışır** | Okulun kendi bilgisayarlarında; internet sunucusu yok. İsteğe bağlı olarak okul ağında bir bilgisayar sunucu, diğerleri istemci |
| **Dil / çatı** | Python 3.11, PySide6 6.10.2 (Qt), SQLite |
| **Büyüklük** | Program yaklaşık 14.500 satır, testler yaklaşık 1.600 satır (128 test), geliştirici araçları yaklaşık 900 satır Python |
| **Dağıtım** | PyInstaller (klasör paketi, ~600 MB) + Inno Setup kurulum dosyası + taşınabilir zip |
| **Lisans** | Kurum koduna verilen, Ed25519 ile imzalı, çevrim dışı doğrulanan `.lic` dosyası; 30 gün deneme |
| **Satış** | Derik MTAL Döner Sermaye İşletmesi üzerinden (süreç: [El Kitabı 9](GELISTIRICI_EL_KITABI.md#9-döner-sermaye-satış-ve-lisans-işlemleri)) |
| **Testler** | `python -m pytest -q` → 128 test, yaklaşık 4 dakika, Ekim 2026 itibarıyla hepsi geçiyor (ağ kipinde de) |

---

## 3. Mimari ve temel tasarım kararları

```
            ┌────────────────────────────── run.py ──────────────────────────────┐
            │ açılış ekranı → ag_baslat (tek / sunucu / istemci) → lisans → pencere │
            └──────────────────────────────────────────────────────────────────────┘
 Kullanıcı ─► ui/sayfa_*.py ─► services/*.py ─► db (Database | SunucuDatabase | UzakDatabase)
                  │                 │                         │
                  │                 └─► mevzuat.py            └─► meskoord.db (SQLite, WAL)
                  └─► ortak.py / eylem.py (mesaj, arka plan işi)
```

Bir sonraki geliştiricinin "neden böyle yapılmış?" sorusunu yanıtlayan kararlar:

| Karar | Gerekçe | Sonucu / dikkat |
|---|---|---|
| **Masaüstü + yerel SQLite**, bulut yok | Okul verisi (T.C., IBAN) okulda kalsın, KVKK yükü düşük, internet kesintisinden etkilenmesin | Yedekleme okulun sorumluluğu; program bunu kolaylaştırır |
| **İş mantığı `services/`, arayüz `ui/`** | Hesaplar arayüz açmadan test edilebilsin | Yeni hesap önce servis + test, sonra ekran |
| **Mevzuat sayıları `mevzuat.py` → `PARAMETRELER`** | Asgari ücret, katsayı vb. her yıl değişir; okul sürüm beklemeden güncelleyebilsin | Koda sayı gömülmez |
| **Ağ kipi: SQL'in HTTPS ile sunucuya taşınması** (`UzakBaglanti` sqlite3 bağlantısını taklit eder) | Servis ve arayüz kodu tek satır değişmeden ağda çalışsın | Servisler yalnızca `q/q1/execute/insert/update/delete`, `conn.execute/commit/rollback` kullanmalı; `create_function`, `iterdump` vb. ağda çalışmaz |
| **Sunucuda oturum başına ayrı SQLite bağlantısı** | `BEGIN/SAVEPOINT/ROLLBACK` davranışı yerelle birebir aynı olsun; kilitler yazmaları sıraya koysun | Okul ölçeği (onlarca kullanıcı) için yeterli |
| **Uzun bekleme (long-poll) ile canlı yenileme** | Ek kütüphane (websocket) olmadan anlık bildirim | Ekranlar `canli_yenile/yenile/doldur` yöntemlerinden birini sağlamalı |
| **Kendinden imzalı TLS + parmak izi sabitleme + doğrulama kodu** | Okulda sertifika altyapısı yok; ortadaki adam saldırısına karşı ilk bağlantıda kullanıcı onayı | Sunucu taşınınca istemciler kodu yeniden onaylar |
| **Yetki ve işlem günlüğü bağlantı düzeyinde** (`hesaplar.py`: SQLite yetkilendirme geri çağrısı + bağlantıya özel geçici tetikleyiciler) | Servis ve ekran kodu değişmeden her yazma denetlensin ve günlüğe girsin; ağda sunucudaki oturum bağlantısında uygulandığı için istemci atlatamaz | Veritabanı dosyasına kalıcı tetikleyici eklenmez; yeni tablo kendiliğinden günlüğe girer. Ekranlardaki yetki gizlemeleri yalnızca kolaylıktır, asıl engel bağlantıdadır |
| **Çevrim dışı imzalı lisans, kurum adının belgelere kilitlenmesi** | Okullar internetsiz çalışabilsin; asıl caydırıcılık resmî belgelerdeki kurum adı | Uzaktan iptal yok, süreli lisans tercih edilir |
| **PySide6 6.10.2'ye sabit** | 6.11.x tarayıcı bileşeni windows-1254 kodlamalı SGK sayfasında çöküyor | Güncellemeden önce SGK 4A sayfası elle denenir |
| **Klasör (onedir) paket** | Tarayıcı bileşeni tek dosyada her açılışta yüzlerce MB açardı; LGPL gereği Qt DLL'leri ayrı kalmalı | `araclar/` hiçbir zaman pakete girmez |
| **Türkçe adlandırma** | Bakımı yapacak öğretmenlerin kodu kolay okuması | Değişken adlarında Türkçe karakter yok, arayüz metinleri tam Türkçe |

Ayrıntılı katmanlar ve ağ protokolü: [El Kitabı 2](GELISTIRICI_EL_KITABI.md#2-program-nedir-nasıl-çalışır),
[El Kitabı 16](GELISTIRICI_EL_KITABI.md#16-çok-kullanıcılı-çalışma-ağ-modu).

---

## 4. Kod haritası: hangi iş için nereye bakılır

| Yapılacak iş | Dosya |
|---|---|
| Asgari ücret, katsayı, oran güncellemesi | `koordmes/mevzuat.py` → `PARAMETRELER` ([tarif 5.1](GELISTIRICI_EL_KITABI.md#51-yeni-yıl-mevzuat-güncellemesi-asgari-ücret-vb)) |
| SGK prim günü, eksik gün, belge türü hatası | `koordmes/services/sigorta.py` + `tests/test_hesaplar.py` |
| SGK XML/Excel dosyası reddedildi (e-Bildirge V2 APHB, 4A toplu işe giriş/işten ayrılış) | `koordmes/services/sgk_dosya.py` + `tests/test_sgk_dosya.py`; SGK şeması değişirse yenisini `koordmes/veri/sgk/EBildirgeV2.xsd` üzerine koyun (e.sgk.gov.tr > Uygulamalar > E-Bildirge V2) |
| SGK aylık beyan kaydı, beyandan sonra değişenler (iptal + ek düzeltme), belge ve toplu çıkış ön kontrolleri | `koordmes/services/sgk_beyan.py` (tablolar `sgk_beyanlari`, `sgk_beyan_satirlari`) + `koordmes/ui/sayfa_sgk_beyan.py` + `tests/test_sgk_beyan.py` |
| Öğrenci ücreti / devlet katkısı hatası | `koordmes/services/ucret.py` |
| Ek ders hesabı | `koordmes/services/ekders.py` |
| Ders programı yerleştirme algoritması | `koordmes/services/program.py` |
| Koordinatör görevlendirme (15 öğrenci grubu, alan/atölye önceliği, kapsam dışı işletmeler), ziyaret planı | `koordmes/services/koordinator.py` |
| Yönetmelik işleri: öğrenci seçimi (md.136), puan çizelgesi teslim günleri, alan taraması, anket, hizmetiçi eğitim | `koordmes/services/mesleki_egitim.py`, ekran `koordmes/ui/sayfa_komisyon.py` (+ `tests/test_yonetmelik.py`) |
| Yönetmelik süre ve sınır denetimleri (md.134, 135, 143, 146 vb.) | `koordmes/services/denetim.py` → `_yonetmelik_yerlestirme`, `_yonetmelik_isletme`; hatırlatmalar `services/takvim.py` → `_yonetmelik_sureleri` |
| e-Okul/e-Mesem listesi tanınmıyor (yeni sütun adı) | `koordmes/services/aktarim.py` → `TANIMLAR` (eş anlamlı başlıklar) |
| Dosya biçimi okunamıyor | `koordmes/services/okuyucu.py` |
| Toplu Veri Girişi ekranının kuralları | `koordmes/services/toplu_giris.py`, ekran `koordmes/ui/sayfa_toplu_giris.py` |
| e-Okul/e-Mesem/SGK adresi değişti | `koordmes/services/baglanti.py` → `SISTEMLER` |
| Word belgesi / şablon ekleme | `koordmes/services/belgeler.py` → `BELGE_TURLERI` |
| Asistan'a yeni komut | `koordmes/services/asistan.py` → `yorumla()`, eylemler `services/surecler.py` → `EYLEMLER` |
| Yıl başı / aylık / yıl sonu süreç adımları | `koordmes/services/surecler.py` |
| Veri denetimi kuralları | `koordmes/services/denetim.py` |
| Yeni tablo/kolon | `koordmes/db.py` → `SCHEMA` ve `EK_KOLONLAR` ([tarif 5.3](GELISTIRICI_EL_KITABI.md#53-veritabanına-kolon-veya-tablo-eklemek)) |
| Tanım ekranına alan ekleme (öğrenci, işletme…) | `koordmes/ui/varliklar.py` (form ve liste `ui/crud.py`'den kendiliğinden üretilir) |
| Yeni menü ekranı | `koordmes/ui/ana_pencere.py` → `yapi` listesi ([tarif 5.2](GELISTIRICI_EL_KITABI.md#52-yeni-bir-menü-ekranı-eklemek)) |
| Ağ sunucusu / istemcisi | `koordmes/ag/sunucu.py`, `koordmes/ag/istemci.py`, `koordmes/ag/protokol.py` |
| Açılışta tek/sunucu/istemci seçimi ve hata pencereleri | `koordmes/ui/ag_baslat.py` |
| Kullanıcı hesapları, roller, yetki kuralları, işlem günlüğü | `koordmes/hesaplar.py` (+ `tests/test_kullanici_hesaplari.py`); ekranlar `ui/giris.py`, `ui/sayfa_kullanicilar.py` |
| Rolün yapabildiklerini değiştirmek | `hesaplar.py` → `yetkilendirici()` ve `YONETICI_TABLOLARI`; ekran gizlemeleri `ui/sayfa_ayarlar.py` → `_yetki_uygula` |
| Günlükte kayıt adının nasıl görüneceği, gizlenen kişisel veriler | `hesaplar.py` → `KAYIT_ADI`, `GIZLI_KOLONLAR` |
| Zamanlanmış otomatik yedek, ikinci yedek klasörü | `koordmes/yedekleme.py`, zamanlayıcı `ui/ana_pencere.py` → `_otomatik_yedek` |
| Sistem tepsisi, Windows açılışında başlama, tek örnek | `koordmes/ui/tepsi.py`, bağlantısı `run.py` |
| Lisans doğrulama, deneme süresi, satıcı bilgileri | `koordmes/lisans.py` |
| Renk, logo, ürün adı | `koordmes/marka.py`, görseller `araclar/marka_olustur.py` ile üretilir |
| Kullanım kılavuzu metni | `docs/KULLANIM_KILAVUZU.md` |
| Sürüm paketi | `araclar/surum_hazirla.py` (`build_exe.bat`), `MesKoord.spec`, `dagitim/MesKoord.iss` |
| Lisans üretimi (yalnızca döner sermaye bilgisayarı) | `araclar/lisans_yonetici.py` / `.bat` |

---

## 5. Devredilen varlıklar ve gizli bilgiler

| Varlık | Nerede durmalı | Gizlilik | Kaybolursa |
|---|---|---|---|
| Kaynak kod (`D:\KoordMes`, `.venv/build/dist/cikti` hariç) | Kurumsal / özel git deposu + yedek | Ticari sır (satışa konu) | Son paketten kod geri alınamaz; **mutlaka depoda tutulmalı** |
| **Özel imza anahtarı** `ozel_anahtar_KM1.pem` + şifresi | Döner sermaye bilgisayarı `Belgeler\MesKoord_Lisans_Yonetimi` + 2 ayrı USB, şifre kapalı zarfta | **Çok gizli** | Yeni lisans üretilemez; yeni anahtar + yeni sürüm gerekir ([El Kitabı 8.6](GELISTIRICI_EL_KITABI.md#86-anahtar-güvenliği-kaybolma-ve-ele-geçirilme)) |
| Lisans kayıt defteri `lisanslar.csv`, `Verilen_Lisanslar\`, `ayarlar.json` | Aynı yönetim klasörü + aylık USB yedeği | Gizli (okul iletişim bilgileri) | Hangi okula ne verildiği bilinmez; muhasebe kayıtlarından yeniden kurulur |
| Açık anahtar | `koordmes/lisans.py` → `ACIK_ANAHTARLAR` | Gizli değil | Koddadır; **eski anahtar satırı asla silinmez** |
| Sürüm paketleri | `cikti\MesKoord_X.Y.Z\` | — | Kaynak koddan yeniden üretilir |
| Kod imzalama sertifikası (alınırsa) | Ayrı, şifreli | Gizli | Yeniden başvuru |
| Marka görselleri (MesKoord) | `araclar/marka_olustur.py`, vektör aslı `dagitim/marka/meskoord_simge.svg` | — | Araç çalıştırılarak yeniden üretilir |
| Döner sermaye onayları, fiyat tarifesi, hak devri sözleşmesi | Okul arşivi | Resmî | — |

> Özel anahtar ve `.lic` dosyaları **hiçbir zaman** proje klasörüne, e-postaya, bulut sürücüye veya git
> deposuna konmaz (`.gitignore` engeller; `surum_hazirla.py` proje klasöründe `.pem` görürse durur).

---

## 6. Mevcut durum ve açık işler

**Çalışan ve testli:** bütün menü ekranları, içe aktarma (17 veri türü), toplu veri girişi, ağ kipi
(sunucu/istemci, canlı yenileme, çakışma birleştirme), kişisel kullanıcı hesapları ve roller, işlem
günlüğü, zamanlanmış otomatik yedek, sistem tepsisi ve Windows açılışında başlama, lisans sistemi, kurulum
ve sessiz kurulum, paketin kendini sınaması, Ortaöğretim Kurumları Yönetmeliği (md.82, 88, 89, 134-153)
işleri. Son tam test: **128/128 geçti**, `MESKOORD_TEST_UZAK=1` ile ağ kipinde de 128/128 (Ekim 2026). Sistem tepsisi ve Windows açılışında başlama yalnızca yardımcı
düzeyinde test edilir; gerçek bir Windows oturumunda elle denenmelidir (bkz. açık iş 7).

**Satıştan önce tamamlanması gerekenler** (devralan kişinin ilk işleri):

| # | İş | Nerede | Neden önemli |
|---|---|---|---|
| 1 | **Kaynak kodu kendi git deposuna almak** | `D:\KoordMes` içinde `git init`, ilk kayıt, özel uzak depo | Şu an klasör hiçbir depoda izlenmiyor; sürüm geçmişi yok, kayıp riski var |
| 2 | Satıcı telefon / e-posta / web bilgisi | `koordmes/lisans.py` → `SATICI` | Boş; lisans penceresinde ve talep metninde iletişim bilgisi görünmüyor |
| 3 | Lisans sözleşmesindeki boşluklar | `dagitim/LISANS_SOZLESMESI.txt`: `[OKUL ADI]`, `[ADRES]`, `[TELEFON]`, `[E-POSTA]`, `[ÇALIŞMA SAATLERİ]`, `[HAK SAHİBİ]`, `[İL]` | Kurulumda gösteriliyor; hukuk biriminin onayı gerekli |
| 4 | Hukuki ve idari onaylar | [El Kitabı 13](GELISTIRICI_EL_KITABI.md#13-hukuki-ve-idari-kontrol-listesi) | Hak devri, döner sermaye onayı, fiyat tarifesi |
| 5 | 2026-2027 mevzuat değerlerinin kontrolü | Ayarlar > Mevzuat Parametreleri; özellikle 3308 Geçici 12. madde | Uygulama süresi her yıl uzatılıyor/değişiyor |
| 6 | Kod imzalama (önerilir) | [El Kitabı 7.5](GELISTIRICI_EL_KITABI.md#75-kod-imzalama-önerilir) | SmartScreen ve virüs programı yanlış alarmları |
| 7 | 1.2.0 paketinin iki bilgisayarda elle denenmesi | Kurulu paket: sunucuda "Windows açılışında başlat" + oturumu kapatıp açma, tepsiden açma/çıkış, hesaplar açıkken istemciden kişisel giriş | Tepsi ve otomatik başlama otomatik testlerle tam sınanamıyor |

**Klasördeki geçici öğeler:** `.tmp_data\` (deneme şablonları), `build\`, `dist\`, `cikti\` silinebilir ve
yeniden üretilebilir; depoya girmez.

---

## 7. İlk hafta planı

| Gün | Yapılacak | Başarı ölçütü |
|---|---|---|
| 1 | Bu dosyayı ve kullanım kılavuzunu okuyun. Programı örnek veriyle açın (*Ayarlar > Veri ve Yedekleme > Örnek Veri Yükle*), Asistan'a `bugün ne yapmalıyım` ve `geçen ayın kapanışını hazırla` yazın | Kapanış klasörü üretildi, ekranların ne yaptığı anlaşıldı |
| 1 | Git deposunu kurun (açık iş 1) | `git log` ilk kaydı gösteriyor |
| 2 | Geliştirme ortamı ([El Kitabı 3](GELISTIRICI_EL_KITABI.md#3-geliştirme-ortamının-kurulması)), `python -m pytest -q` | 128 test geçti |
| 2 | `MESKOORD_TEST_UZAK=1` ile testleri ağ kipinde çalıştırın | Hepsi geçti |
| 3 | `services/sigorta.py` ve `services/ucret.py`'yi testleriyle birlikte okuyun; bir hesabı elle doğrulayın | SGK ve ücret mantığı anlaşıldı |
| 3 | İki bilgisayarla (ya da `araclar\ag_sinama.py` ile) ağ kipini deneyin | Bir bilgisayardaki kayıt diğerinde göründü |
| 4 | Küçük bir değişiklik yapın (ör. `aktarim.py`'ye bir eş anlamlı başlık) + test | Test eklendi ve geçti |
| 5 | `build_exe.bat --surum 1.2.1` ile deneme paketi, `python araclar\kurulum_sina.py` | Kurulum dosyası üretildi, sınama başarılı (deneme sürüm numarasını geri alın) |
| 5 | Lisans Yöneticisi ile "deneme" notlu lisans üretip doğrulayın | Lisans programa yüklendi |

---

## 8. Rutin bakım işleri

| Ne zaman | İş |
|---|---|
| Ocak | Yeni asgari ücret → `mevzuat.py` + sürüm |
| Ocak ve Temmuz | Memur aylık katsayısı (ek ders ücreti) |
| Haziran–Ağustos | 3308 Geçici 12. madde durumu, yeni yıl mevzuatı, yeni yıl sürümü |
| Ağustos | 31 Ağustos'ta biten lisanslara yenileme hatırlatması |
| Eylül | e-Okul/e-Mesem/SGK ekran ve liste biçimi değişikliklerinin kontrolü |
| 6 ayda bir | Bağımlılık güncellemesi (PySide6 sabitlemesine dikkat) |
| Her ay | Lisans yönetim klasörü yedeği, `lisanslar.csv` ↔ muhasebe eşleştirmesi |
| Her sürüm | `SURUM_NOTLARI.md`, testler, `kurulum_sina.py`, git etiketi, okullara duyuru, gerekiyorsa kullanım kılavuzu güncellemesi |

Ayrıntı: [El Kitabı 11](GELISTIRICI_EL_KITABI.md#11-yıllık-bakım-takvimi).

---

## 9. Değiştirirken dikkat: kırılması kolay yerler

1. **Veritabanı geriye uyumluluğu:** Okullardaki eski veritabanları yeni sürümle açılır. Kolon silinmez ve
   adı değiştirilmez; yeni kolon `EK_KOLONLAR`'a da yazılır.
2. **Ağ uyumluluğu:** İstemci, sunucunun `SCHEMA_VERSION`'ı ve sürümün ilk iki hanesi farklıysa bağlanmaz.
   Kolon eklenen her sürümde küçük sürüm (Y) artırılır; okullara "önce sunucuyu güncelleyin" denir.
3. **`sqlite3` özel özellikleri:** Servislerde `create_function`, `iterdump`, `row_factory` değiştirme
   kullanılmaz; ağ kipinde çalışmaz.
4. **Canlı yenileme:** Yeni ekran `canli_yenile()`, `yenile()` ya da `doldur()` sağlamalı; kullanıcının
   yazdığını silecek ekranlar `ana_pencere.CANLI_YENILEME_DISI` listesine eklenmeli.
5. **Toplu işlemlerden önce yedek:** Kullanıcı verisini silen/değiştiren her toplu işlemden önce `db.yedekle()`.
6. **Inno Setup `AppId`** asla değiştirilmez.
7. **Lisans açık anahtarları:** Eski anahtar satırı silinirse o anahtarla verilmiş bütün lisanslar geçersiz olur.
8. **e-Okul/SGK oturum bilgisi:** Gömülü tarayıcı çerez ve şifre saklamaz (`NoPersistentCookies`); bu
   davranış KVKK gereği korunmalı.
9. **PySide6 sürümü:** 6.10.2'den yükseltmeden önce SGK işe giriş/çıkış sayfası elle denenmeli.
10. **Yetki ve günlük:** Veritabanı bağlantısı açan her yer `Database(yol, kimlik)` ya da `db.kopya()`
    kullanmalı; çıplak `sqlite3.connect` yetki ve günlüğü atlar (yalnızca `hesaplar.py`'deki giriş
    doğrulama ve günlük temizliği bilerek böyle yapar). Program kendisi arka planda bir ayar yazıyorsa
    yetkisiz rolde hata vermemesi için `lisans._ayar_yazmayi_dene` gibi sessizce geçmeli.

---

## 10. Geliştirici için sık sorulan sorular

**Gerçek okul verisiyle mi deneyeyim?** Hayır. `MESKOORD_DATA` ile ayrı klasör ve örnek veri kullanın:
`$env:MESKOORD_DATA="D:\MesKoord_Deneme"; .venv\Scripts\python.exe run.py`

**Bir okul hata bildirdi, ilk ne isterim?** Sürüm (Yardım > Hakkında), ekran görüntüsü ve
`Belgeler\MesKoord\hata_gunlugu.txt`. Gerçek veritabanını e-postayla istemeyin.

**Paketlenmiş program bir modülü bulamıyor.** `MesKoord.spec` → `hiddenimports`'a ekleyin, `run.py` →
`kendini_sina` listesine denetim satırı koyun.

**Hesap sonucu yanlış.** Önce okulun Mevzuat Parametreleri güncel mi bakın; sonra öğrencinin
program/statü/başlangıç tarihi ve işletmenin personel sayısı. Kod hatasıysa hatayı yakalayan bir testle düzeltin.

**Okulda iki bilgisayar `meskoord.db`'yi ağ paylaşımından açmak istiyor.** Yapılmamalı (veri bozulabilir);
Çok Kullanıcılı Çalışma (sunucu/istemci) kullanılmalı.

**Kılavuzu nasıl güncellerim?** `docs/KULLANIM_KILAVUZU.md`'yi düzenleyin. Program açıkken *Yardım >
Kullanım Kılavuzu* yeni metni gösterir; sürüm paketine kendiliğinden girer.

Diğer arızalar: [El Kitabı 10](GELISTIRICI_EL_KITABI.md#10-destek-ve-arıza-giderme).

---

## 11. Yol haritası

1.2.0'da tamamlananlar: kişisel kullanıcı hesapları ve roller, işlem günlüğü, zamanlanmış otomatik yedek
ve ikinci yedek klasörü, sunucunun sistem tepsisinde çalışması ve Windows açılışında başlaması;
Ortaöğretim Kurumları Yönetmeliğine göre koordinatörlük planlaması (md.88), öğrenci seçimi (md.136),
işletme uygunluk ve usta öğretici denetimleri (md.135, 140-146), sözleşme ve puan çizelgesi süreleri,
alan taraması, anketler, hizmetiçi eğitim ve Komisyon ve İzleme İşleri ekranı.

Yönetmelikle ilgili olası geliştirmeler: e-Mesem/e-Okul'dan yıl sonu başarı ortalamasının doğrudan
alınması (şimdilik Excel aktarımı), anket formlarının çevrim içi doldurulması (bilinçli olarak yapılmadı:
internet sunucusu yok).

Öncelik sırasıyla önerilen geliştirmeler:

1. **e-Bildirge V2 XML çıktısı** ve **SGK 4A toplu işe giriş/çıkış XML'i.**
2. **Güncelleme denetimi** (kişisel veri göndermeden son sürüm numarasını okuma).
3. **Kod imzalama.**
4. **Ekran düzeyinde ince yetki** (gerekirse): ör. koordinatör öğretmenin yalnızca kendi işletmelerini
   değiştirmesi. Bugünkü roller tablo düzeyindedir; satır düzeyi kural `hesaplar.yetkilendirici` ile
   yapılamaz, servis katmanında denetim gerekir.

---

## 12. Devir teslim tutanağı

Ayrıntılı kontrol listesi: [El Kitabı 14](GELISTIRICI_EL_KITABI.md#14-devir-teslim-kontrol-listesi).

| # | Teslim edilen | Açıklama | Teslim alan kontrol etti |
|---|---|---|---|
| 1 | Kaynak kod ve git deposu erişimi | Uzak depo adresi: .................................... | ☐ |
| 2 | Özel imza anahtarı (2 USB) ve şifresi (kapalı zarf) | Anahtar kimliği: KM1 | ☐ |
| 3 | `MesKoord_Lisans_Yonetimi` klasörü | `lisanslar.csv`, `Verilen_Lisanslar`, `ayarlar.json` | ☐ |
| 4 | Son sürüm paketleri | `cikti\MesKoord_1.2.0` | ☐ |
| 5 | Kod imzalama sertifikası (varsa) ve şifresi | | ☐ |
| 6 | Destek e-posta hesabı / telefon hattı | | ☐ |
| 7 | Lisans verilen okulların listesi ve açık destek talepleri | | ☐ |
| 8 | Döner sermaye onay yazıları, fiyat tarifesi, hak devri sözleşmesi | | ☐ |
| 9 | Geliştirme ortamı kuruldu, testler geçti | Test sayısı: ...... / ...... | ☐ |
| 10 | Deneme paketi üretildi, `kurulum_sina.py` başarılı | | ☐ |
| 11 | Deneme lisansı üretilip doğrulandı | Lisans no: .................. | ☐ |
| 12 | Bu dosyadaki açık işler (bölüm 6) üzerinde konuşuldu | Sorumlu ve tarih: .................. | ☐ |

| | Teslim eden | Teslim alan |
|---|---|---|
| Adı Soyadı | | |
| Unvanı / Görevi | | |
| Tarih | ..../..../........ | ..../..../........ |
| İmza | | |

Onaylayan (Okul Müdürü / Döner Sermaye İşletme Müdürü): ................................
