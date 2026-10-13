"""Sorumluluk / tek ders sınavı süreci: e-Okul listesinden sonuçların e-Okul'a girilmesine kadar iş adımları,
akıllı öneriler (ders kuralları, sınav birleştirme), tek tıkla bütün plan, görev ücretlerinin ek ders puantajına
aktarılması ve Ana Sayfa hatırlatmaları."""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date

from . import sinav
from .aktarim import norm
from .utils import tarih as tarih_coz
from .utils import tr

SINAV_SAYFASI = "Sınav Planlama ve Görevlendirme"
EKDERS_SAYFASI = "Ek Ders Puantajı"
SEKME_ADIMLAR = "İş Adımları"
SEKME_SEANS = "Seans Çizelgesi"
SEKME_SINAVLAR = "Sınavlar ve Öğrenciler"
SEKME_OGRETMENLER = "Öğretmenler"
SEKME_SALONLAR = "Salonlar"
SEKME_PLANLAMA = "Planlama"
SEKME_CIKTILAR = "Çıktılar"
DONEM_AYARI = "Dönem Ayarları"

EOKUL_LISTE = ("e-Okul > Ortaöğretim Kurum İşlemleri > Sorumluluk/Tasdikname İşlemleri > Sorumluluk ve OYS "
               "Puanları ekranında yazıcı simgesi > 'OOK12001R012 Sorumlu Dersi Olan Öğrenciler ve Dersleri "
               "(Önceki Sınıflar)' raporu > Excel (Sadece Veri) olarak kaydedin; 'Sınavlar ve Öğrenciler' sekmesinde "
               "'e-Okul'dan Aktar...' ile seçin.")
EOKUL_SONUC = ("Sınavdan sonra puanları e-Okul > Ortaöğretim Kurum İşlemleri > Sorumluluk/Tasdikname İşlemleri > "
               "Sorumluluk ve OYS Puanları ekranına girin; sınav kâğıtları, tutanaklar ve imza listelerini arşivleyin.")
EKDERS_TUR = "Sınav Görevi"

ILISKILI_DERSLER = [("Matematik dersleri", ("matematik", "geometri")),
                    ("Fen bilimleri dersleri", ("fizik", "kimya", "biyoloji")),
                    ("Türkçe dersleri", ("edebiyat", "dil ve anlatim"))]


@dataclass
class IsAdimi:
    no: int
    baslik: str
    durum: bool | None  # True tamam, False eksik, None bilgi / isteğe bağlı
    detay: str
    git: str = ""  # sekme adı, DONEM_AYARI ya da menüdeki sayfa adı


@dataclass
class KuralOnerisi:
    ders1: str
    ders2: str
    ortak: int
    neden: str


@dataclass
class BirlestirmeOnerisi:
    sinav_ids: list[int]
    etiket: str
    gruplar: list[str]
    ogrenci: int


@dataclass
class EkDersAktarimi:
    satir: int = 0
    ogretmen: int = 0
    saat: float = 0.0
    disarida: list[str] = field(default_factory=list)

    def ozet(self) -> str:
        if not self.satir:
            return "Ek ders puantajına aktarılacak ücretli sınav görevi yok."
        s = (f"{self.ogretmen} öğretmenin {self.saat:g} saatlik sınav görevi, görev günlerine göre ek ders "
             f"puantajına ('{EKDERS_TUR}') aktarıldı ({self.satir} kayıt). Önceki aktarım varsa yenisiyle değiştirildi.")
        if self.disarida:
            s += " Ücrete girmeyen görevler: " + "; ".join(self.disarida[:5]) + (" ..." if len(self.disarida) > 5 else "")
        return s


# ------------------------------------------------------------------ öneriler

def kural_onerileri(db, donem_id: int) -> list[KuralOnerisi]:
    """Ortak öğrencisi olan ilişkili dersler (matematik-geometri, fizik-kimya-biyoloji, edebiyat-dil ve anlatım)
    için henüz tanımlanmamış 'aynı güne gelmesin' kuralları."""
    ders_ogr: dict[str, tuple[str, set[int]]] = {}
    for r in db.q("SELECT s.ders, so.ogrenci_id FROM sinavlar s JOIN sinav_ogrencileri so ON so.sinav_id = s.id "
                  "WHERE s.donem_id = ?", (donem_id,)):
        ders_ogr.setdefault(norm(r["ders"]), (r["ders"], set()))[1].add(r["ogrenci_id"])
    mevcut = {frozenset((norm(r["ders1"]), norm(r["ders2"]))) for r in sinav.kurallar(db, donem_id)}
    out = []
    for neden, anahtarlar in ILISKILI_DERSLER:
        dersler = sorted(d for d in ders_ogr if any(a in d for a in anahtarlar))
        for i, a in enumerate(dersler):
            for b in dersler[i + 1:]:
                if frozenset((a, b)) in mevcut:
                    continue
                ortak = len(ders_ogr[a][1] & ders_ogr[b][1])
                if ortak:
                    out.append(KuralOnerisi(ders_ogr[a][0], ders_ogr[b][0], ortak, neden))
    return out


def kural_onerilerini_ekle(db, donem_id: int) -> int:
    oneriler = kural_onerileri(db, donem_id)
    for o in oneriler:
        sinav.kural_ekle(db, donem_id, o.ders1, o.ders2, "ortak_ogrenci")
    return len(oneriler)


def birlestirme_onerileri(db, donem_id: int) -> list[BirlestirmeOnerisi]:
    """Aynı ders, seviye ve şekilde farklı grup kodlarıyla açılmış sınavlar (ör. EML ve ATL listelerinden gelen
    'Matematik 9'): tek sınav yapılırsa görevli ve seans tasarrufu sağlanır. Ayrı tutulan OYS sınavları önerilmez."""
    gruplar: dict[tuple, list] = defaultdict(list)
    for r in sinav.sinav_listesi(db, donem_id):
        if norm(r["grup"] or "") == "oys" or not r["ogrenci_sayisi"]:
            continue
        gruplar[(norm(r["ders"]), r["seviye"], norm(r["sekil"] or "Yazılı"))].append(r)
    out = []
    for liste in gruplar.values():
        if len(liste) < 2:
            continue
        liste.sort(key=lambda r: (-r["ogrenci_sayisi"], r["id"]))
        etiket = liste[0]["ders"] + (f" ({liste[0]['seviye']}. Sınıf)" if liste[0]["seviye"] else "")
        out.append(BirlestirmeOnerisi([r["id"] for r in liste], etiket, [r["grup"] or "(grupsuz)" for r in liste],
                                      sum(r["ogrenci_sayisi"] for r in liste)))
    return out


# ------------------------------------------------------------------ ek ders puantajına aktarım

def _ekders_etiketi(donem_id: int) -> str:
    return f"[Sınav dönemi #{donem_id}]"


def ekderse_aktar(db, donem_id: int) -> EkDersAktarimi:
    """Ücretli sınav görevlerini öğretmen ve gün bazında ek ders kayıtlarına ('Sınav Görevi') yazar; aynı dönemin
    önceki aktarımı silinip yeniden yazılır (tekrar basmak çift kayıt üretmez)."""
    d = sinav.donem(db, donem_id)
    if d is None:
        raise ValueError("Sınav dönemi bulunamadı.")
    saat: dict[tuple[int, str], float] = defaultdict(float)
    adet: Counter = Counter()
    sonuc = EkDersAktarimi()
    for k in sinav.gorev_ucretleri(db, donem_id):
        for g in k["gorevler"]:
            if g["ucret_durumu"] == "Ücretli" and g["saat"]:
                saat[(k["ogretmen_id"], g["tarih"])] += g["saat"]
                adet[(k["ogretmen_id"], g["tarih"])] += 1
            elif g["ucret_durumu"] != "Ücretli":
                sonuc.disarida.append(f"{k['ad']} {tr(g['tarih'])} ({g['ucret_durumu'].lower()})")
    etiket = _ekders_etiketi(donem_id)
    satirlar = [(t, tarih, EKDERS_TUR, s, f"{etiket} {d['ad']}: {adet[(t, tarih)]} görev")
                for (t, tarih), s in sorted(saat.items())]
    with db.conn:
        db.conn.execute("DELETE FROM ek_ders_kayitlari WHERE tur = ? AND aciklama LIKE ?", (EKDERS_TUR, etiket + "%"))
        db.conn.executemany("INSERT INTO ek_ders_kayitlari (ogretmen_id, tarih, tur, saat, aciklama) "
                            "VALUES (?, ?, ?, ?, ?)", satirlar)
    sonuc.satir = len(satirlar)
    sonuc.ogretmen = len({t for t, _ in saat})
    sonuc.saat = sum(saat.values())
    return sonuc


def ekders_durumu(db, donem_id: int) -> tuple[float, float]:
    """(puantaja aktarılmış saat, ücretli görevlerin güncel toplam saati)."""
    aktarilan = db.q1("SELECT COALESCE(SUM(saat), 0) s FROM ek_ders_kayitlari WHERE tur = ? AND aciklama LIKE ?",
                      (EKDERS_TUR, _ekders_etiketi(donem_id) + "%"))["s"]
    gereken = sum(k["saat"] for k in sinav.gorev_ucretleri(db, donem_id))
    return float(aktarilan or 0), float(gereken)


# ------------------------------------------------------------------ hepsini yap

def hepsini_yap(db, donem_id: int, sure_limit: float = 10.0,
                koru: bool = False) -> tuple[sinav.PlanSonucu, list[str]]:
    """Öğretmenlerin nöbet/koordinatörlük/ders saatlerini kapalı seanslara işler, sınavları yerleştirir, görevlileri
    atar, öğrencileri salonlara dağıtır ve planı denetler. (plan sonucu, rapor satırları)."""
    satirlar: list[str] = []
    n = sinav.nobetten_doldur(db, donem_id)
    if n:
        satirlar.append(f"{n} öğretmenin nöbet / koordinatörlük / ders saatleri kapalı seanslarına işlendi.")
    s = sinav.planla(db, donem_id, sure_limit=sure_limit, koru=koru)
    satirlar.append(s.ozet())
    g = sinav.gorevlileri_ata(db, donem_id)
    satirlar.append(g.ozet())
    satirlar += [f"  - {x}" for x in g.eksik[:10]]
    try:
        satirlar.append(sinav.salonlara_yerlestir(db, donem_id))
    except ValueError as e:
        satirlar.append(str(e))
    bulgular = sinav.denetle(db, donem_id)
    say = Counter(b.seviye for b in bulgular)
    satirlar.append(f"Denetim: {say[sinav.KRITIK]} kritik, {say[sinav.UYARI]} uyarı, {say[sinav.BILGI]} bilgi.")
    satirlar += [f"  - {b.mesaj}" for b in bulgular if b.seviye == sinav.KRITIK][:10]
    return s, satirlar


def guncel_donem(db, bugun: date | None = None) -> int | None:
    """Hatırlatma ve asistan için: sürmekte olan ya da en yakın tarihli sınav dönemi, yoksa en son açılan."""
    bugun = bugun or date.today()
    en: tuple | None = None
    for r in sinav.donemler(db):
        bas, bit = tarih_coz(r["baslangic"]), tarih_coz(r["bitis"])
        if bas is None:
            continue
        uzaklik = 0 if bas <= bugun <= (bit or bas) else min(abs((bas - bugun).days), abs(((bit or bas) - bugun).days))
        if en is None or uzaklik < en[0]:
            en = (uzaklik, r["id"])
    if en is not None:
        return en[1]
    r = db.q1("SELECT id FROM sinav_donemleri ORDER BY id DESC LIMIT 1")
    return r["id"] if r else None


# ------------------------------------------------------------------ iş adımları

def _gorev_eksikleri(v: sinav._Veri) -> list[str]:
    """Seansa yerleşmiş sınavlarda komisyonu / gözcüsü eksik olanlar."""
    gorev: dict[int, Counter] = defaultdict(Counter)
    for g in v.gorevliler:
        gorev[g["sinav_id"]][g["gorev"] == sinav.GOZCU] += 1
    salon: dict[int, set] = defaultdict(set)
    for (sid, _), (sl, _) in v.yerlesim.items():
        if sl:
            salon[sid].add(sl)
    out = []
    for s in v.sinavlar:
        n = len(v.sinav_ogr.get(s["id"], ()))
        if not n or s["seans_id"] not in v.seans:
            continue
        kom, goz = v.gorev_ihtiyaci(s, n, len(salon[s["id"]]))
        if gorev[s["id"]][False] < kom or gorev[s["id"]][True] < goz:
            out.append(sinav.sinav_adi(s))
    return out


def _ogrenci_sorunlari(db, donem_id: int, tur: str) -> list[str]:
    """Okuldan ayrılmış öğrenciler; tek ders döneminde 12. sınıf olmayan ya da birden çok sınavı olanlar."""
    rows = db.q("""SELECT o.id, o.ad, o.soyad, o.aktif, si.seviye, COUNT(DISTINCT so.sinav_id) n
                   FROM sinav_ogrencileri so JOIN sinavlar s ON s.id = so.sinav_id
                   JOIN ogrenciler o ON o.id = so.ogrenci_id LEFT JOIN siniflar si ON si.id = o.sinif_id
                   WHERE s.donem_id = ? GROUP BY o.id ORDER BY o.ad, o.soyad""", (donem_id,))
    out = [f"{r['ad']} {r['soyad']}: okuldan ayrılmış (pasif)" for r in rows if not r["aktif"]]
    if norm(tur) == norm(sinav.TEK_DERS):
        out += [f"{r['ad']} {r['soyad']}: 12. sınıf değil" for r in rows if r["aktif"] and r["seviye"]
                and r["seviye"] != 12]
        out += [f"{r['ad']} {r['soyad']}: {r['n']} sınavı var (tek ders sınavı tek ders içindir)" for r in rows
                if r["n"] > 1]
    return out


def is_adimlari(db, donem_id: int | None, bugun: date | None = None) -> list[IsAdimi]:
    """Sınav sürecinin adımları ve her adımın veritabanından denetlenen durumu."""
    bugun = bugun or date.today()
    adimlar: list[IsAdimi] = []

    def ekle(baslik: str, durum: bool | None, detay: str, git: str = "") -> None:
        adimlar.append(IsAdimi(len(adimlar) + 1, baslik, durum, detay, git))

    d = sinav.donem(db, donem_id)
    if d is None:
        ekle("Sınav dönemi açma", False, "Sağ üstteki 'Yeni Dönem' ile dönemi (ör. 'Eylül Sorumluluk Sınavları'), "
                                         "türünü ve tarihlerini girin.", DONEM_AYARI)
        ekle("e-Okul'dan sorumlu öğrenci listesi", None, EOKUL_LISTE, SEKME_SINAVLAR)
        return adimlar
    bas, bit = tarih_coz(d["baslangic"]), tarih_coz(d["bitis"])
    ders_yili = sinav.ders_yili_icinde(db, d)
    ekle("Sınav dönemi, türü ve tarihleri", bool(bas and bit),
         f"{d['ad']} — {d['tur'] or ''} — {tr(bas) or '?'} / {tr(bit) or '?'}; ders yılı içinde: "
         f"{'evet' if ders_yili else 'hayır'} ({d['ders_yili_icinde'] or 'Otomatik'})"
         + ("" if bas and bit else "; başlangıç ve bitiş tarihlerini girin"), DONEM_AYARI)

    v = sinav._Veri(db, donem_id)
    ogrencili = [s for s in v.sinavlar if v.sinav_ogr.get(s["id"])]
    kayit = sum(len(x) for x in v.sinav_ogr.values())
    ekle("e-Okul'dan sorumlu öğrenci listesini aktarma", bool(ogrencili),
         f"{len(v.sinavlar)} sınav, {len(v.ogrenci)} öğrenci, {kayit} öğrenci-sınav kaydı." if ogrencili
         else EOKUL_LISTE, SEKME_SINAVLAR)

    sorun = _ogrenci_sorunlari(db, donem_id, d["tur"] or "")
    ekle("Öğrenci durumu (okuldan ayrılan, tek ders koşulu)", not sorun if ogrencili else None,
         ("; ".join(sorun[:5]) + (f" ... ({len(sorun)} öğrenci)" if len(sorun) > 5 else "")) if sorun
         else "Sorun yok." if ogrencili else "Önce öğrenci listesini aktarın.", SEKME_SINAVLAR)

    sekil = Counter(s["sekil"] or "Yazılı" for s in ogrencili)
    birlestir = birlestirme_onerileri(db, donem_id)
    ekle("Sınav şekli, süresi ve birleştirme", None if birlestir else (True if ogrencili else None),
         ", ".join(f"{k}: {n}" for k, n in sekil.items()) +
         (f". Birleştirilebilecek {len(birlestir)} sınav grubu var: " +
          ", ".join(f"{b.etiket} [{' + '.join(b.gruplar)}]" for b in birlestir[:4]) if birlestir else ""),
         SEKME_SINAVLAR)

    acik = [r for r in v.seanslar if r["acik"]]
    acik_gun = Counter(r["tarih"] for r in acik)
    ogr_yuk: Counter = Counter()
    ogr_uyg: Counter = Counter()
    for s in ogrencili:
        for o in v.sinav_ogr[s["id"]]:
            ogr_yuk[o] += 1
            ogr_uyg[o] += sinav.uygulamali(s["sekil"])
    gerek = max((ogr_uyg[o] + math.ceil((n - ogr_uyg[o]) / v.ogr_azami) for o, n in ogr_yuk.items()), default=0)
    en_cok = max(ogr_yuk.values(), default=0)
    ekle("Seans çizelgesi (sınav günleri ve oturumlar)", bool(acik) and gerek <= len(acik_gun),
         f"{len(acik_gun)} sınav günü, {len(acik)} açık oturum. En çok sınavı olan öğrencinin {en_cok} sınavı var; "
         f"günde {v.ogr_azami} sınavla en az {gerek} sınav günü gerekir."
         + (" Sınav günü ekleyin ya da günlük sınırı artırın." if gerek > len(acik_gun) else "")
         if acik else "Seans yok: tarih aralığı ve oturum saatleriyle 'Seansları Oluştur'a basın.", SEKME_SEANS)

    alanlar = [t for t in v.ogretmen.values() if t.gorev_alir]
    eksik_kapali = sinav.eksik_kapali_seanslar(db, donem_id)
    neden_say = Counter(n for k in eksik_kapali.values() for n in k.values())
    gorev_ihtiyaci = sum(sum(v.gorev_ihtiyaci(s, len(v.sinav_ogr[s["id"]]))) for s in ogrencili)
    saat_yok = ders_yili and not sinav.ders_saatleri(db) and bool(db.q1("SELECT 1 FROM program_hucreleri LIMIT 1"))
    detay = (f"Görev alan {len(alanlar)} öğretmen; tahmini görev sayısı {gorev_ihtiyaci}"
             f" (öğretmen başına ~{gorev_ihtiyaci / max(1, len(alanlar)):.1f}).")
    if eksik_kapali:
        detay += (f" {len(eksik_kapali)} öğretmenin görev alamayacağı seanslar işlenmemiş ("
                  + ", ".join(f"{sinav.KAPALI_NEDENLERI[k]}: {n}" for k, n in neden_say.items())
                  + "); 'Nöbet / Müsaitlikten Doldur'a basın.")
    if saat_yok:
        detay += (" Sınavlar ders yılı içinde ama ders saatleri girilmemiş: dersi olan öğretmen o saatte görev "
                  "alabilir. Ayarlar > Ders Programı > 'Ders saatlerinin başlangıç-bitişleri'ni girin.")
    ekle("Öğretmenler: görev alanlar ve görev alamayacakları seanslar", bool(alanlar) and not eksik_kapali
         and not saat_yok, detay, SEKME_OGRETMENLER)

    kural_oneri = kural_onerileri(db, donem_id)
    ekle("Ders ve gün kuralları", None if kural_oneri else True,
         f"{len(v.kurallar)} ders kuralı, {len(v.gun_kurallari)} gün kuralı."
         + (f" Önerilen 'aynı güne gelmesin' kuralları: " +
            ", ".join(f"{o.ders1} - {o.ders2} ({o.ortak} ortak öğrenci)" for o in kural_oneri[:4])
            if kural_oneri else ""), SEKME_OGRETMENLER)

    yazili = [s for s in ogrencili if sinav.salon_gerekir(s["sekil"])]
    en_buyuk = max((len(v.sinav_ogr[s["id"]]) for s in yazili), default=0)
    ekle("Salonlar ve kapasite", (bool(v.salonlar) and en_buyuk <= v.salon_kapasitesi) if yazili else None,
         f"{len(v.salonlar)} salon, toplam {v.salon_kapasitesi} kişilik; en kalabalık yazılı sınav {en_buyuk} öğrenci."
         if v.salonlar else "Salon yok: 'Salonlar' sekmesinde 'Atölye / Sınıflardan Al...' ile ekleyin.",
         SEKME_SALONLAR)

    yerlesmeyen = [s for s in ogrencili if s["seans_id"] not in v.seans]
    ekle("Sınavları seanslara yerleştirme", bool(ogrencili) and not yerlesmeyen,
         (f"{len(yerlesmeyen)} sınav yerleşmemiş: " + ", ".join(sinav.sinav_adi(s) for s in yerlesmeyen[:4])
          + ". 'Neden Yerleşmedi?' ile ayrıntılı nedeni görün.") if yerlesmeyen
         else f"{len(ogrencili)} sınavın hepsi seansta." if ogrencili else "Sınav yok.", SEKME_PLANLAMA)

    gorev_eksik = _gorev_eksikleri(v)
    planli = [s for s in ogrencili if s["seans_id"] in v.seans]
    ekle("Komisyon ve gözcü görevlendirme", (not gorev_eksik) if planli else None,
         (f"Görevlisi eksik {len(gorev_eksik)} sınav: " + ", ".join(gorev_eksik[:4])) if gorev_eksik
         else f"{len(v.gorevliler)} görev verildi." if planli else "Önce sınavları yerleştirin.", SEKME_PLANLAMA)

    salonsuz = [s for s in yazili if s["seans_id"] in v.seans and any(
        not v.yerlesim.get((s["id"], o), (None, None))[0] for o in v.sinav_ogr[s["id"]])]
    ekle("Öğrencileri salon ve sıralara yerleştirme", (not salonsuz) if planli and yazili else None,
         (f"Salonu belirlenmemiş öğrencisi olan {len(salonsuz)} sınav var.") if salonsuz
         else "Tamam." if planli and yazili else "Yazılı sınav yerleşince yapılır.", SEKME_PLANLAMA)

    bulgular = sinav.denetle(db, donem_id) if planli else []
    say = Counter(b.seviye for b in bulgular)
    ekle("Planı denetleme", (None if say[sinav.UYARI] else True) if planli and not say[sinav.KRITIK]
         else (False if planli else None),
         f"{say[sinav.KRITIK]} kritik, {say[sinav.UYARI]} uyarı, {say[sinav.BILGI]} bilgi." if planli
         else "Plan yapılınca denetlenir.", SEKME_PLANLAMA)

    imza = bool((d["duzenleyen"] or "").strip() and (d["onaylayan"] or "").strip())
    ekle("Onay ve imza bilgileri (düzenleyen / onaylayan)", imza,
         f"Düzenleyen: {d['duzenleyen'] or '-'}, onaylayan: {d['onaylayan'] or '-'}." if imza
         else "Dönem ayarlarında düzenleyen (müdür yardımcısı) ve onaylayan (okul müdürü) bilgilerini girin.",
         DONEM_AYARI)

    ekle("Belgeler: sınav takvimi ilanı, görevlendirme yazıları, giriş belgeleri, tutanaklar", None,
         "Çıktılar sekmesinde 'Tüm Çıktıları Üret'; sınav takvimini ilan edin, görevlendirme yazılarını "
         "öğretmenlere imza karşılığı tebliğ edin, giriş belgelerini öğrencilere verin.", SEKME_CIKTILAR)

    girilmemis = db.q1("""SELECT COUNT(*) c FROM sinav_ogrencileri so JOIN sinavlar s ON s.id = so.sinav_id
                          JOIN sinav_seanslari se ON se.id = s.seans_id
                          WHERE s.donem_id = ? AND se.tarih < ? AND ifnull(so.katilim, '') = ''""",
                       (donem_id, bugun.isoformat()))["c"]
    bitti = bool(bit and bit < bugun)
    ekle("Sınav günü: öğrenci yoklaması ve gelmeyen görevliler", (girilmemis == 0) if bitti else None,
         f"Yapılmış sınavlarda girip girmediği işlenmemiş {girilmemis} öğrenci kaydı var." if girilmemis
         else "Sınav günlerinde 'Sınavlar ve Öğrenciler' sekmesinden girmeyenleri, 'Görevliler...' ile gelmeyen "
              "öğretmenleri işaretleyin (gelmeyen görevli ücrete girmez).", SEKME_SINAVLAR)

    aktarilan, gereken = ekders_durumu(db, donem_id) if v.gorevliler else (0.0, 0.0)
    ekle("Görev ücretlerini ek ders puantajına aktarma", (abs(aktarilan - gereken) < 1e-6) if gereken else None,
         f"Ücretli görev {gereken:g} saat; puantaja aktarılan {aktarilan:g} saat."
         + (" 'Ek Derse Aktar'a basın." if gereken and abs(aktarilan - gereken) >= 1e-6 else "")
         if gereken else "Ücretli görev yok.", EKDERS_SAYFASI)

    ekle("Sonuçların e-Okul'a girilmesi ve arşiv", None, EOKUL_SONUC)
    return adimlar


# ------------------------------------------------------------------ Ana Sayfa hatırlatmaları

def _seviye(kalan: int) -> str:
    return "Kritik" if kalan <= 2 else "Uyarı" if kalan <= 7 else "Bilgi"


def hatirlatmalar(db, bugun: date) -> list[tuple[str, str, date | None]]:
    """(seviye, mesaj, tarih): yaklaşan sınav döneminde yerleşmemiş sınav / eksik görevli / kritik denetim bulgusu;
    biten dönemde ek ders aktarımı, yoklama ve e-Okul'a puan girişi."""
    out: list[tuple[str, str, date | None]] = []
    for d in sinav.donemler(db):
        bas, bit = tarih_coz(d["baslangic"]), tarih_coz(d["bitis"])
        if bas is None:
            continue
        bit = bit or bas
        kalan = (bas - bugun).days
        if 0 <= kalan <= 14 or bas <= bugun <= bit:
            v = sinav._Veri(db, d["id"])
            ogrencili = [s for s in v.sinavlar if v.sinav_ogr.get(s["id"])]
            seviye = _seviye(max(0, kalan))
            if not ogrencili:
                out.append((seviye, f"{d['ad']}: sınav listesi boş; e-Okul'dan sorumlu öğrenci listesini aktarın.",
                            bas))
                continue
            yerlesmeyen = [s for s in ogrencili if s["seans_id"] not in v.seans]
            if yerlesmeyen:
                out.append((seviye, f"{d['ad']}: {len(yerlesmeyen)} sınav seansa yerleşmemiş (sınavlar {tr(bas)} "
                                    f"tarihinde başlıyor).", bas))
            eksik = _gorev_eksikleri(v)
            if eksik:
                out.append((seviye, f"{d['ad']}: {len(eksik)} sınavda komisyon/gözcü eksik.", bas))
            kritik = [b for b in sinav.denetle(db, d["id"]) if b.seviye == sinav.KRITIK] if not yerlesmeyen else []
            if kritik:
                out.append((seviye, f"{d['ad']}: planda {len(kritik)} kritik sorun var (ör. {kritik[0].mesaj}).",
                            bas))
            if not (yerlesmeyen or eksik or kritik) and kalan >= 0:
                out.append(("Bilgi", f"{d['ad']} {tr(bas)} tarihinde başlıyor: sınav takvimini ilan edin, "
                                     f"görevlendirme yazılarını tebliğ edin.", bas))
        elif bit < bugun and (bugun - bit).days <= 30:
            aktarilan, gereken = ekders_durumu(db, d["id"])
            if gereken and abs(aktarilan - gereken) >= 1e-6:
                out.append(("Uyarı", f"{d['ad']}: sınav görev ücretleri ({gereken:g} saat) ek ders puantajına "
                                     f"aktarılmadı ya da değişti.", bit))
            out.append(("Bilgi", f"{d['ad']} bitti: puanları e-Okul'a girin, sınav evrakını arşivleyin.", bit))
    return out
