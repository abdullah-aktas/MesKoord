"""Asistan: Türkçe komutları yorumlar, işlemleri çalıştırır, kişi/işletme/sınıf bilgisi verir.

Örnekler: "bugün ne yapmalıyım", "ekim sgk listesi", "geçen ayın kapanışını hazırla",
"programı oluştur", "Ahmet Yılmaz nerede", "9-A", "Usta Oto Servis", "denetim".
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ..mevzuat import AYLAR, GUNLER
from . import denetim, ekders, koordinator, sgk_risk, surecler, takvim
from .aktarim import isletme_anahtari, norm, sinif_adi, tarih
from .surecler import EYLEMLER, onceki_ay, sonraki_ay
from .utils import para, tr


@dataclass
class Yanit:
    metin: str
    dosyalar: list[Path] = field(default_factory=list)
    oneriler: list[tuple[str, str]] = field(default_factory=list)  # (etiket, eylem anahtarı)
    git: str | None = None
    eylem: str | None = None  # onay/arka plan/tarih gerektiren, arayüzün çalıştıracağı eylem
    eylem_kw: dict[str, Any] = field(default_factory=dict)


KISA_GUN = ["Pzt", "Sal", "Çar", "Per", "Cum"]
DURUM_ISARETI = {True: "✔", False: "⚠", None: "ℹ"}


def h(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


ORNEKLER = [
    "bugün ne yapmalıyım", "denetim", "geçen ayın kapanışını hazırla", "ekim sgk listesi", "sgk giriş bildirimleri",
    "sgk ceza riskleri", "ekim e-bildirge xml", "sgk giriş çıkış xml",
    "ücret hesapla", "dekontlar", "ek ders puantajı", "devamsızlık", "veli bildirimleri", "ziyaret planı kasım",
    "koordinatör görevlendir", "görevlendirme yazıları", "programı oluştur", "sözleşmeleri hazırla", "yedek al",
    "yıl sonu 26.06.2027", "yeni eğitim yılı", "dosya aktar", "parametreler", "istatistik",
    "Ahmet Yılmaz", "12-A", "Usta Oto Servis",
]


# ------------------------------------------------------------------ dönem çözümleme

def _egitim_yili_ayi(ay: int, bugun: date) -> int:
    """Yılı yazılmayan ay, içinde bulunulan eğitim yılına (Eylül-Ağustos) göre yorumlanır; yaz aylarında takvim yılı."""
    if bugun.month in (7, 8):
        return bugun.year
    bas = bugun.year if bugun.month >= 9 else bugun.year - 1
    return bas if ay >= 9 else bas + 1


def donem_bul(n: str, bugun: date, varsayilan: str = "onceki") -> tuple[int, int]:
    yil_m = re.search(r"\b(20\d\d)\b", n)
    for i, ay in enumerate(AYLAR, 1):
        if re.search(rf"\b{norm(ay)}\w*", n):
            return (int(yil_m.group(1)) if yil_m else _egitim_yili_ayi(i, bugun)), i
    if "gecen ay" in n or "onceki ay" in n:
        return onceki_ay(bugun)
    if "gelecek ay" in n or "sonraki ay" in n or "onumuzdeki ay" in n:
        return sonraki_ay(bugun.year, bugun.month)
    if "bu ay" in n:
        return bugun.year, bugun.month
    if varsayilan == "onceki":
        return onceki_ay(bugun)
    return bugun.year, bugun.month


def _var(n: str, *kaliplar: str) -> bool:
    return any(k in n for k in kaliplar)


# ------------------------------------------------------------------ yorumlama

def yorumla(db, komut: str, bugun: date | None = None) -> Yanit:
    bugun = bugun or date.today()
    n = norm(komut)
    if not n:
        return Yanit("Bir komut yazın veya dosya sürükleyin. Örnek: <i>bugün ne yapmalıyım</i>")

    if _var(n, "yardim", "neler yapabilir", "ne yapabilir", "komut", "nasil kullan"):
        return yardim()
    if n in ("merhaba", "selam", "gunaydin", "iyi gunler", "ozet", "durum", "genel durum") or \
            _var(n, "bugun", "ne yapmali", "yapilacak", "gundem", "uyari", "hatirlat"):
        return gundem(db, bugun)
    if _var(n, "sinav", "sorumluluk", "tek ders"):
        if re.search(r"(^|\s)ek ?ders", n) or _var(n, "ucret", "puantaj"):
            return _hemen(db, "sinav_ekders")
        if _var(n, "planla", "yerlestir", "hazirla", "olustur", "gorevli", "dagit", "hepsini yap"):
            return _eylem("sinav_planla", "Güncel sınav döneminde sınavlar seanslara yerleştirilecek, komisyon ve "
                                          "gözcüler atanacak, öğrenciler salonlara dağıtılacak.")
        return _hemen(db, "sinav_adimlari")
    if _var(n, "denetim", "denetle", "kontrol et", "tutarsiz", "eksik bilgi", "veri kontrol", "hatali kayit"):
        return _denetim(db)
    if _var(n, "yonetmelik", "koordinator mudur yardimcisi gorev", "kmy gorev"):
        return surec_metni(db, "yonetmelik", bugun)
    if _var(n, "ogrenci secim", "secim komisyon", "ogrencileri sirala", "ogrenci siralama", "md 136"):
        return Yanit("İşletmeye gönderilecek öğrencilerin sıralaması (md.136) için Komisyon ve İzleme İşleri "
                     "ekranındaki <b>Öğrenci Seçimi</b> sekmesini açıyorum.", git="Komisyon ve İzleme İşleri")
    if _var(n, "komisyon karar", "planlama komisyon"):
        return _hemen(db, "komisyon_karari")
    if _var(n, "isletmelere bildir", "koordinator bildirim", "isimleri bildir"):
        return _hemen(db, "koordinator_bildirimleri")
    if "uygunluk" in n:
        return _hemen(db, "uygunluk_tutanaklari")
    if _var(n, "alan tarama", "isletme talep"):
        return _hemen(db, "alan_taramasi")
    if _var(n, "anket", "mezun izleme"):
        return _hemen(db, "anket_ozeti")
    if _var(n, "hizmetici", "hizmet ici", "usta ogretici egitim"):
        return _hemen(db, "hizmetici")
    if _var(n, "puan cizelge"):
        return _hemen(db, "puan_cizelgesi")
    if _var(n, "kapanis", "ay sonu", "aylik islem", "tum rapor", "butun rapor"):
        yil, ay = donem_bul(n, bugun)
        return _eylem("aylik_kapanis", f"<b>{AYLAR[ay - 1]} {yil}</b> aylık kapanışı hazırlanıyor (SGK, ücret, dekont, "
                                       "ek ders, devamsızlık, veli yazıları, gelecek ay ziyaret planı, yedek)…",
                      yil=yil, ay=ay)
    if _var(n, "yeni yil", "yeni egitim", "sinif atlat", "sinif gecir", "ust sinif"):
        return _eylem("yeni_egitim_yili", "Yeni eğitim yılına geçiş için onayınız gerekiyor.")
    if _var(n, "yil sonu", "donem sonu", "sona erdir", "yerlestirmeleri bitir"):
        t = _tarih_bul(komut)
        if t:
            return _eylem("yil_sonu", f"Aktif yerleştirmeler <b>{tr(t)}</b> tarihinde sona erdirilecek.", tarih=t)
        return surec_metni(db, "yil_sonu", bugun, "Bitiş tarihini de yazarsanız yerleştirmeleri sona erdiririm "
                                                  "(ör. <i>yıl sonu 26.06.2027</i>).")
    if _var(n, "yil basi", "egitim yili baslangic", "eylul hazirlik", "baslangic islem"):
        return surec_metni(db, "yil_basi", bugun)
    if _var(n, "aylik surec", "aylik kontrol", "bu ay ne"):
        yil, ay = donem_bul(n, bugun)
        return surec_metni(db, "aylik", bugun, yil=yil, ay=ay)
    sgk_mi = "sgk" in n.split() or _var(n, "sigorta", "prim", "muhsgk", "bildirge", "ise giris", "isten ayril")
    if sgk_mi and _var(n, "karsilastir", "fark", "uyusma", "e-bildirge liste", "ebildirge liste"):
        return Yanit("e-Bildirge'den aldığınız listeyi <b>SGK Sigorta İşlemleri &gt; Liste Karşılaştırma</b> "
                     "sekmesine yükleyin veya sürükleyin; okul kayıtlarıyla farklar ve düzeltme önerileri listelenir.",
                     git="SGK Sigorta İşlemleri")
    if sgk_mi and _var(n, "on kontrol", "hazirlik kontrol", "belge kontrol"):
        yil, ay = donem_bul(n, bugun)
        return _hemen(db, "sgk_on_kontrol", yil=yil, ay=ay)
    if sgk_mi and _var(n, "duzelt", "iptal", "ek belge"):
        yil, ay = donem_bul(n, bugun)
        return _hemen(db, "sgk_duzeltme", yil=yil, ay=ay)
    if sgk_mi and _var(n, "verildi", "onaylandi", "beyan kaydet"):
        yil, ay = donem_bul(n, bugun)
        return _eylem("sgk_beyan_kaydet", f"<b>{AYLAR[ay - 1]} {yil}</b> aylık prim ve hizmet belgesi verildi olarak "
                                          "kaydedilecek.", yil=yil, ay=ay)
    if sgk_mi and _var(n, "risk", "ceza", "hata", "oneri"):
        return _sgk_riskleri(db, bugun)
    if sgk_mi and _var(n, "xml", "sablon", "yuklenecek"):
        bicim = "_excel" if not _var(n, "xml") else ("_excel" if "excel" in n else "_xml")
        if _var(n, "giris", "cikis", "ayrilis"):
            return _hemen(db, "sgk_bildirge" + bicim)
        yil, ay = donem_bul(n, bugun)
        return _hemen(db, "sgk" + bicim, yil=yil, ay=ay)
    if sgk_mi:
        if _var(n, "bildir", "giris", "cikis", "ayrilis"):
            return _hemen(db, "sgk_bildirim")
        yil, ay = donem_bul(n, bugun)
        return _hemen(db, "sgk_prim", yil=yil, ay=ay)
    if "dekont" in n:
        yil, ay = donem_bul(n, bugun)
        return _hemen(db, "dekont", yil=yil, ay=ay)
    if _var(n, "ek ders", "ekders", "puantaj"):
        yil, ay = donem_bul(n, bugun, "bu" if bugun.day >= 20 else "onceki")
        return _hemen(db, "ekders", yil=yil, ay=ay)
    if _var(n, "ucret", "devlet katkisi"):
        yil, ay = donem_bul(n, bugun)
        return _hemen(db, "ucret", yil=yil, ay=ay)
    if "veli" in n:
        return _hemen(db, "veli")
    if "devam" in n:
        return _hemen(db, "devam")
    if "ziyaret" in n:
        yil, ay = donem_bul(n, bugun, "bu")
        return _hemen(db, "ziyaret_plani", yil=yil, ay=ay)
    if _var(n, "gorevlendirme yazi", "gorev yazi", "gorevlendirme belge"):
        return _hemen(db, "gorevlendirme_yazilari")
    if _var(n, "koordinator gorevlendir", "gorevlendir", "koordinatorleri dagit", "koordinator ata"):
        return _eylem("koordinator", "Koordinatörlük görevleri yeniden dağıtılacak.")
    if _var(n, "cerceve", "zorunlu ders", "ogretim program"):
        return _eylem("cerceve_dersleri", "Çerçeve öğretim programlarına göre sınıfların zorunlu dersleri ders "
                                          "dağılımına açılacak.")
    if "program" in n and _var(n, "olustur", "hazirla", "yap", "yerlestir", "coz", "dagit"):
        return _eylem("program_olustur", "Ders programı ve atölye yerleşimi hesaplanıyor (en fazla "
                                         f"{db.ayar('program_sure_limit_sn')} sn)…")
    if _var(n, "sozlesme"):
        return _hemen(db, "sozlesmeler")
    if _var(n, "degerlendirme form", "beceri form", "not formu"):
        return _hemen(db, "degerlendirme_formlari")
    if "yedek" in n:
        return _hemen(db, "yedek")
    if _var(n, "aktar", "ice al", "dosya", "yukle", "excel", "pdf", "word"):
        return Yanit("Dosyalarınızı (Excel, Word, PDF, CSV, HTML) bu pencereye sürükleyin veya <b>Dosya Ekle</b> "
                     "düğmesini kullanın. Veri türünü (öğrenci, işletme, devamsızlık, dekont, SGK bildirgesi…) "
                     "kendim tanırım; aktarmadan önce deneme yapıp sonucu gösteririm.", git="Veri Aktarımı")
    if _var(n, "parametre", "asgari ucret", "katsayi", "mevzuat", "ayar"):
        return _parametreler(db)
    if _var(n, "istatistik", "sayilar", "kac ogrenci", "kac isletme", "rakam"):
        return _istatistik(db)
    if "program" in n:
        return Yanit("Ders programını görüntülemek için Ders Programı ekranını açıyorum. Yeniden oluşturmak için "
                     "<i>programı oluştur</i> yazın.", git="Ders Dağılımı ve Atölye Yerleşimi")
    return ara(db, komut)


def _tarih_bul(komut: str) -> date | None:
    m = re.search(r"\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4}|\d{4}-\d{2}-\d{2}", komut)
    return tarih(m.group(0)) if m else None


def _eylem(anahtar: str, metin: str, **kw) -> Yanit:
    return Yanit(metin, eylem=anahtar, eylem_kw=kw)


def _hemen(db, anahtar: str, **kw) -> Yanit:
    try:
        s = surecler.calistir(db, anahtar, **kw)
    except Exception as e:
        return Yanit(f"<span style='color:#a00'>İşlem yapılamadı: {h(e)}</span>")
    return Yanit(h(s.mesaj), s.dosyalar, [], s.git)


def eylem_sonucu_yaniti(s: surecler.EylemSonucu) -> Yanit:
    return Yanit(h(s.mesaj), s.dosyalar, [], s.git)


# ------------------------------------------------------------------ hazır yanıtlar

def yardim() -> Yanit:
    gruplar = [
        ("Gündem", ["bugün ne yapmalıyım", "denetim", "yıl başı", "aylık süreç", "yıl sonu"]),
        ("Aylık işler", ["geçen ayın kapanışını hazırla", "ekim sgk listesi", "sgk bildirimleri",
                         "sgk ceza riskleri", "sgk listesi karşılaştır", "ekim sgk ön kontrol",
                         "ekim e-bildirge xml", "ekim sgk belgesi verildi", "ekim sgk düzeltme",
                         "sgk giriş çıkış xml", "e-bildirge excel şablonu", "ücret hesapla",
                         "dekontlar", "ek ders puantajı", "devamsızlık", "veli bildirimleri"]),
        ("Koordinatörlük", ["koordinatör görevlendir", "görevlendirme yazıları", "ziyaret planı kasım",
                            "işletmelere bildir", "komisyon kararı"]),
        ("Yönetmelik", ["yönetmelik görevleri", "öğrenci seçimi", "uygunluk tutanakları", "puan çizelgesi",
                        "alan taraması", "anket", "hizmetiçi eğitim"]),
        ("Program ve belgeler", ["zorunlu dersleri aç", "programı oluştur", "sözleşmeleri hazırla",
                                 "değerlendirme formları"]),
        ("Sorumluluk / tek ders sınavı", ["sınav iş adımları", "sınavları planla", "sınav ücretlerini ek derse aktar"]),
        ("Veri", ["dosya aktar", "yedek al", "parametreler", "istatistik"]),
        ("Sorgu", ["Ahmet Yılmaz (öğrenci/öğretmen adı)", "12-A (sınıf)", "işletme adı", "T.C. veya okul no"]),
    ]
    s = "Yapabileceklerim (yazmanız yeterli; tıklanabilir):<br>"
    for g, lst in gruplar:
        s += f"<b>{g}:</b> " + " · ".join(f"<a href='komut:{h(x.split(' (')[0])}'>{h(x)}</a>" for x in lst) + "<br>"
    s += "Dosyaları pencereye sürükleyerek Excel, Word, PDF, CSV veya HTML'den veri aktarabilirsiniz."
    return Yanit(s)


def gundem(db, bugun: date) -> Yanit:
    k = db.kurum()
    u = takvim.uyarilar(db, bugun)
    kritik = [x for x in u if x.seviye == "Kritik"]
    s = f"<b>{h(k['ad'] or 'Kurum')}</b> — {tr(bugun)} {GUNLER[bugun.weekday()] if bugun.weekday() < 5 else ''}<br>"
    if u:
        s += f"{len(kritik)} kritik, {len(u) - len(kritik)} diğer uyarı:<ul>"
        renk = {"Kritik": "#a00", "Uyarı": "#a60", "Bilgi": "#246"}
        for x in u[:10]:
            s += f"<li><span style='color:{renk[x.seviye]}'>[{x.seviye}]</span> {h(x.konu)}: {h(x.mesaj)}</li>"
        s += "</ul>" + (f"…ve {len(u) - 10} uyarı daha (Ana Sayfa).<br>" if len(u) > 10 else "")
    else:
        s += "Bekleyen yasal süre veya uyarı yok.<br>"
    yil, ay = onceki_ay(bugun) if bugun.day <= 15 else (bugun.year, bugun.month)
    oneriler: list[tuple[str, str]] = []
    for sur in ("yil_basi", "aylik"):
        for d in surecler.durumlar(db, sur, yil, ay):
            if d.durum is False and d.adim.eylem and len(oneriler) < 5:
                oneriler.append((f"{d.adim.baslik}: {d.detay}", d.adim.eylem))
    if oneriler:
        s += "<b>Önerdiğim adımlar:</b>"
    return Yanit(s, oneriler=oneriler)


def surec_metni(db, surec: str, bugun: date, ek: str = "", yil: int | None = None, ay: int | None = None) -> Yanit:
    sur = surecler.SURECLER[surec]
    yil, ay = (yil, ay) if yil and ay else (onceki_ay(bugun) if surec == "aylik" else (bugun.year, bugun.month))
    s = f"<b>{h(sur.baslik)}</b>" + (f" — {AYLAR[ay - 1]} {yil}" if surec == "aylik" else "") + f": {h(sur.aciklama)}<ul>"
    oneriler = []
    for d in surecler.durumlar(db, surec, yil, ay):
        renk = {True: "#2a7", False: "#c70", None: "#36a"}[d.durum]
        s += (f"<li><span style='color:{renk}'>{DURUM_ISARETI[d.durum]}</span> {h(d.adim.baslik)} — "
              f"{h(d.detay)}</li>")
        if d.durum is not True and d.adim.eylem:
            oneriler.append((d.adim.baslik, d.adim.eylem))
    s += "</ul>" + ek
    y = Yanit(s, oneriler=oneriler[:8])
    y.eylem_kw = {"yil": yil, "ay": ay}
    return y


def _denetim(db) -> Yanit:
    b = denetim.denetle(db)
    s = f"<b>Veri denetimi:</b> {h(denetim.ozet(b))}.<ul>"
    renk = {"Kritik": "#a00", "Uyarı": "#a60", "Bilgi": "#246"}
    for x in b[:15]:
        link = f" <a href='git:{h(x.git)}'>düzelt</a>" if x.git else ""
        s += f"<li><span style='color:{renk[x.seviye]}'>[{x.seviye}]</span> {h(x.metin)}{link}</li>"
    s += "</ul>" + ("Tamamı Veri Denetimi sekmesinde." if len(b) > 15 else "")
    return Yanit(s)


def _sgk_riskleri(db, bugun: date) -> Yanit:
    r = sgk_risk.analiz(db, bugun)
    s = f"<b>SGK hata ve ceza riskleri:</b> {h(sgk_risk.ozet(r))}<ul>"
    renk = {"Kritik": "#a00", "Uyarı": "#a60", "Bilgi": "#246"}
    for x in r[:12]:
        s += (f"<li><span style='color:{renk[x.seviye]}'>[{x.seviye}]</span> <b>{h(x.konu)}</b> — {h(x.kisi)}: "
              f"{h(x.oneri)}</li>")
    s += "</ul>" + ("Tamamı ve tek tıkla düzeltme: SGK Sigorta İşlemleri &gt; Risk ve Öneriler." if r else "")
    return Yanit(s, git="SGK Sigorta İşlemleri" if r else None)


def _parametreler(db) -> Yanit:
    satir = [("Brüt asgari ücret", f"{para(db.ayar('asgari_ucret_brut'))} TL"),
             ("Net asgari ücret", f"{para(db.ayar('asgari_ucret_net'))} TL"),
             ("Memur aylık katsayısı", db.ayar("aylik_katsayi")),
             ("3308 Geçici 12. madde", "Uygulanıyor" if db.ayar("gecici12_aktif") else "Uygulanmıyor"),
             ("Öğrenci ücret oranı (Geçici 12)", f"%{db.ayar('ucret_orani_gecici12') * 100:g}"),
             ("SGK PEK oranı", f"%{db.ayar('sgk_pek_orani') * 100:g}"),
             ("Koordinatör haftalık azami (kurumunuz için)", koordinator.haftalik_azami(db))]
    s = "<b>Geçerli mevzuat parametreleri:</b><ul>" + "".join(f"<li>{h(a)}: <b>{h(b)}</b></li>" for a, b in satir)
    s += "</ul>Değiştirmek için Ayarlar ekranını açtım."
    return Yanit(s, git="Ayarlar ve Mevzuat Parametreleri")


def _istatistik(db) -> Yanit:
    q = lambda sql: db.q1(sql)[0]
    satir = [
        ("Aktif öğrenci", q("SELECT COUNT(*) FROM ogrenciler WHERE aktif = 1")),
        ("İşletmede eğitim gören", q("""SELECT COUNT(DISTINCT ogrenci_id) FROM yerlestirmeler WHERE durum = 'Aktif'
                                        AND isletme_id IS NOT NULL AND tur != 'Okulda Alan Eğitimi'""")),
        ("Aktif işletme", q("SELECT COUNT(DISTINCT isletme_id) FROM yerlestirmeler WHERE durum = 'Aktif'")),
        ("Öğretmen", q("SELECT COUNT(*) FROM ogretmenler WHERE aktif = 1")),
        ("Koordinatör öğretmen", q("SELECT COUNT(DISTINCT ogretmen_id) FROM koordinator_gorevleri")),
        ("Sınıf / şube", q("SELECT COUNT(*) FROM siniflar")),
        ("Haftalık programdaki ders saati", q("SELECT COUNT(*) FROM program_hucreleri")),
    ]
    return Yanit("<b>Genel durum:</b><ul>" + "".join(f"<li>{h(a)}: <b>{b}</b></li>" for a, b in satir) + "</ul>")


# ------------------------------------------------------------------ arama ve bilgi kartları

_DOLGU = {"ara", "bul", "kim", "nerede", "hakkinda", "bilgi", "bilgisi", "goster", "ogrenci", "ogretmen", "isletme",
          "sinif", "sube", "firma", "nedir", "ver", "listele", "kimdir", "hangi", "ne", "bana", "lutfen", "programi"}


def ara(db, komut: str) -> Yanit:
    n = norm(komut)
    terim = " ".join(t for t in n.split() if t not in _DOLGU)
    if not terim:
        return Yanit("Ne aramamı istediğinizi anlayamadım. <a href='komut:yardım'>Yardım</a> yazabilirsiniz.")
    sonuc: list[tuple[str, int, str]] = []
    for r in db.q("SELECT id, ad, soyad, okul_no, tc FROM ogrenciler"):
        if terim in norm(f"{r['ad']} {r['soyad']}") or terim in (r["okul_no"] or "", r["tc"] or ""):
            sonuc.append(("ogrenci", r["id"], f"{r['ad']} {r['soyad']}"))
    for r in db.q("SELECT id, ad, soyad, tc FROM ogretmenler"):
        if terim in norm(f"{r['ad']} {r['soyad']}") or terim == (r["tc"] or ""):
            sonuc.append(("ogretmen", r["id"], f"{r['ad']} {r['soyad']}"))
    ia = isletme_anahtari(terim)
    for r in db.q("SELECT id, ad FROM isletmeler"):
        if ia and ia in isletme_anahtari(r["ad"]):
            sonuc.append(("isletme", r["id"], r["ad"]))
    sa = norm(sinif_adi(komut.strip()))
    for r in db.q("SELECT id, ad FROM siniflar"):
        if norm(r["ad"]) in (terim, sa) or norm(sinif_adi(r["ad"])) == sa:
            sonuc.append(("sinif", r["id"], r["ad"]))
    if not sonuc:
        return Yanit(f"<i>{h(komut)}</i> için bir komut veya kayıt bulamadım. "
                     "<a href='komut:yardım'>Yardım</a> yazarak yapabileceklerimi görebilirsiniz.")
    if len(sonuc) == 1 or (len(sonuc) <= 3 and len({s[0] for s in sonuc}) == len(sonuc)):
        return Yanit("<hr>".join(kart(db, t, i) for t, i, _ in sonuc))
    tur_ad = {"ogrenci": "Öğrenci", "ogretmen": "Öğretmen", "isletme": "İşletme", "sinif": "Sınıf"}
    s = f"{len(sonuc)} kayıt bulundu, ayrıntı için tıklayın:<ul>"
    for t, i, ad in sonuc[:25]:
        s += f"<li>{tur_ad[t]}: <a href='kart:{t}:{i}'>{h(ad)}</a></li>"
    return Yanit(s + "</ul>")


def kart(db, tur: str, kid: int) -> str:
    return {"ogrenci": ogrenci_karti, "ogretmen": ogretmen_karti, "isletme": isletme_karti,
            "sinif": sinif_karti}[tur](db, kid)


def _gun_adlari(s: str | None) -> str:
    return ", ".join(GUNLER[int(g) - 1] for g in (s or "").split(",") if g.strip().isdigit() and 1 <= int(g) <= 5)


def ogrenci_karti(db, oid: int) -> str:
    o = db.q1("""SELECT o.*, s.ad AS sinif, s.program, s.okul_gunleri, s.isletme_gunleri
                 FROM ogrenciler o LEFT JOIN siniflar s ON s.id = o.sinif_id WHERE o.id = ?""", (oid,))
    s = (f"<b>Öğrenci: {h(o['ad'])} {h(o['soyad'])}</b> {'' if o['aktif'] else '(pasif)'}<br>"
         f"No: {h(o['okul_no'])} · Sınıf: {h(o['sinif'])} ({h(o['program'])}) · Statü: {h(o['statu'])} · "
         f"T.C.: {h(o['tc'])}<br>Veli: {h(o['veli_ad'])} {h(o['veli_tel'])}")
    if o["isletme_gunleri"]:
        s += f"<br>Okul günleri: {_gun_adlari(o['okul_gunleri'])} · İşletme günleri: {_gun_adlari(o['isletme_gunleri'])}"
    for y in db.q("""SELECT y.*, i.ad AS isletme, i.usta_ogretici, i.telefon FROM yerlestirmeler y
                     LEFT JOIN isletmeler i ON i.id = y.isletme_id WHERE y.ogrenci_id = ? ORDER BY y.baslangic DESC""",
                  (oid,)):
        k = db.q1("""SELECT o.id, o.ad || ' ' || o.soyad AS ad, kg.gun FROM koordinator_gorevleri kg
                     JOIN ogretmenler o ON o.id = kg.ogretmen_id WHERE kg.isletme_id = ?""", (y["isletme_id"],))
        ad = (f"<a href='kart:isletme:{y['isletme_id']}'>{h(y['isletme'])}</a>" if y["isletme_id"]
              else h(y["tur"]))
        s += (f"<br>• <b>{ad}</b> ({h(y['tur'])}, {h(y['durum'])}): {tr(y['baslangic'])} – "
              f"{tr(y['bitis']) or '…'}; sözleşme no: {h(y['sozlesme_no']) or '<i>yok</i>'}; SGK giriş: "
              f"{'bildirildi' if y['sigorta_giris_bildirildi'] else '<b>bildirilmedi</b>'}")
        if y["usta_ogretici"]:
            s += f"; usta öğretici: {h(y['usta_ogretici'])}"
        if k:
            s += (f"; koordinatör: <a href='kart:ogretmen:{k['id']}'>{h(k['ad'])}</a> "
                  f"({GUNLER[k['gun'] - 1] if k['gun'] <= 5 else k['gun']})")
    d = db.q1("""SELECT COALESCE(SUM(CASE WHEN tur = 'Özürsüz' THEN gun END), 0) oz, COALESCE(SUM(gun), 0) top
                 FROM devamsizlik WHERE ogrenci_id = ?""", (oid,))
    s += f"<br>Devamsızlık: özürsüz {d['oz']:g}, toplam {d['top']:g} gün"
    n = db.q1("SELECT * FROM beceri_notlari WHERE ogrenci_id = ? ORDER BY donem DESC", (oid,))
    if n:
        s += f" · Son not ({n['donem']}. dönem): işletme {n['isletme_notu'] or '-'}, koordinatör {n['koordinator_notu'] or '-'}"
    return s + " · <a href='git:Öğrenciler / Çıraklar'>kaydı aç</a>"


def ogretmen_karti(db, tid: int) -> str:
    o = db.q1("SELECT o.*, a.ad AS alan FROM ogretmenler o LEFT JOIN alanlar a ON a.id = o.alan_id WHERE o.id = ?",
              (tid,))
    ders = db.q("""SELECT ph.gun, COUNT(DISTINCT ph.saat) c FROM program_hucreleri ph
                   JOIN ders_ogretmenleri dog ON dog.atama_id = ph.atama_id
                   WHERE dog.ogretmen_id = ? GROUP BY ph.gun""", (tid,))
    toplam = sum(r["c"] for r in ders)
    s = (f"<b>Öğretmen: {h(o['ad'])} {h(o['soyad'])}</b> — {h(o['unvan'])}, {h(o['brans'])} ({h(o['alan'])})<br>"
         f"Haftalık ders: {toplam} saat (" + ", ".join(f"{KISA_GUN[r['gun'] - 1]} {r['c']}" for r in ders if r['gun'] <= 5)
         + f") · Aylık karşılık: {ekders.aylik_karsilik(db, o)} · Azami ek ders: {ekders.azami_ek_ders(db, o)}")
    gor = db.q("""SELECT kg.gun, kg.haftalik_saat, i.id, i.ad FROM koordinator_gorevleri kg
                  JOIN isletmeler i ON i.id = kg.isletme_id WHERE kg.ogretmen_id = ? ORDER BY kg.gun""", (tid,))
    if gor:
        s += (f"<br>Koordinatörlük ({sum(g['haftalik_saat'] for g in gor)} saat): "
              + "; ".join(f"{GUNLER[g['gun'] - 1] if g['gun'] <= 5 else g['gun']}: "
                          f"<a href='kart:isletme:{g['id']}'>{h(g['ad'])}</a> ({g['haftalik_saat']})" for g in gor))
    b = date.today()
    p = next((x for x in ekders.puantaj(db, b.year, b.month) if x.ogretmen_id == tid), None)
    if p:
        s += f"<br>{AYLAR[b.month - 1]} ek ders: {p.toplam:g} saat, tahmini brüt {para(p.brut)} TL"
    if o["musait_olmayan"]:
        s += f"<br>Müsait olmadığı zamanlar: {h(o['musait_olmayan'])}"
    return s + " · <a href='git:Öğretmenler'>kaydı aç</a>"


def isletme_karti(db, iid: int) -> str:
    i = db.q1("SELECT i.*, a.ad AS alan FROM isletmeler i LEFT JOIN alanlar a ON a.id = i.alan_id WHERE i.id = ?",
              (iid,))
    ogr = db.q("""SELECT o.id, o.ad, o.soyad, s.ad AS sinif, y.tur FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                  LEFT JOIN siniflar s ON s.id = o.sinif_id WHERE y.isletme_id = ? AND y.durum = 'Aktif'
                  ORDER BY s.ad, o.ad""", (iid,))
    s = (f"<b>İşletme: {h(i['ad'])}</b> ({h(i['alan'])})<br>Yetkili: {h(i['yetkili'])} · Tel: {h(i['telefon'])} · "
         f"Personel: {i['personel_sayisi'] or '<b>girilmemiş</b>'} · Usta öğretici: "
         f"{h(i['usta_ogretici']) or '<b>yok</b>'}<br>Adres: {h(i['adres'])} · Güzergah: {h(i['guzergah'])} "
         f"({i['mesafe_km'] or 0:g} km)")
    s += f"<br>Aktif öğrenci ({len(ogr)}" + (f"/{i['kontenjan']}" if i["kontenjan"] else "") + "): " + \
         (", ".join(f"<a href='kart:ogrenci:{r['id']}'>{h(r['ad'])} {h(r['soyad'])}</a> ({h(r['sinif'])})"
                    for r in ogr) or "-")
    for g in db.q("""SELECT o.id, o.ad || ' ' || o.soyad AS ad, kg.gun, kg.haftalik_saat FROM koordinator_gorevleri kg
                     JOIN ogretmenler o ON o.id = kg.ogretmen_id WHERE kg.isletme_id = ?""", (iid,)):
        s += (f"<br>Koordinatör: <a href='kart:ogretmen:{g['id']}'>{h(g['ad'])}</a> — "
              f"{GUNLER[g['gun'] - 1] if g['gun'] <= 5 else g['gun']}, {g['haftalik_saat']} saat")
    z = db.q("SELECT tarih, durum FROM ziyaretler WHERE isletme_id = ? ORDER BY tarih DESC LIMIT 4", (iid,))
    if z:
        s += "<br>Son ziyaretler: " + ", ".join(f"{tr(r['tarih'])} ({h(r['durum'])})" for r in z)
    return s + " · <a href='git:İşletmeler'>kaydı aç</a>"


def sinif_karti(db, sid: int) -> str:
    c = db.q1("""SELECT s.*, a.ad AS alan, o.ad || ' ' || o.soyad AS rehber FROM siniflar s
                 LEFT JOIN alanlar a ON a.id = s.alan_id LEFT JOIN ogretmenler o ON o.id = s.rehber_ogretmen_id
                 WHERE s.id = ?""", (sid,))
    ogr = db.q("""SELECT o.id, o.ad, o.soyad, o.okul_no, (SELECT i.ad FROM yerlestirmeler y JOIN isletmeler i
                  ON i.id = y.isletme_id WHERE y.ogrenci_id = o.id AND y.durum = 'Aktif') AS isletme
                  FROM ogrenciler o WHERE o.sinif_id = ? AND o.aktif = 1 ORDER BY o.okul_no""", (sid,))
    saat = db.q1("""SELECT COALESCE(SUM(haftalik_saat), 0) FROM ders_atamalari WHERE sinif_id = ?""", (sid,))[0]
    s = (f"<b>Sınıf: {h(c['ad'])}</b> — {h(c['program'])}, {h(c['alan'])}; rehber öğretmen: {h(c['rehber']) or '-'}<br>"
         f"Okul günleri: {_gun_adlari(c['okul_gunleri'])}" +
         (f" · İşletme günleri: {_gun_adlari(c['isletme_gunleri'])}" if c["isletme_gunleri"] else "") +
         f" · Haftalık ders: {saat} saat<br>Öğrenciler ({len(ogr)}): ")
    s += ", ".join(f"{h(r['okul_no'])} <a href='kart:ogrenci:{r['id']}'>{h(r['ad'])} {h(r['soyad'])}</a>"
                   + (f" [{h(r['isletme'])}]" if r["isletme"] else "")
                   for r in ogr[:40]) or "-"
    return s + " · <a href='git:Ders Dağılımı ve Atölye Yerleşimi'>programı aç</a>"


def eylem_etiketi(anahtar: str) -> str:
    e = EYLEMLER.get(anahtar)
    return e.etiket if e else anahtar
