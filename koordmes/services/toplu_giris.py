"""Elle veya Excel'den yapıştırarak toplu veri girişi.

Giriş tablosundaki satırlar, aktarım motorunun veri türlerine (öğrenci, işletme, yerleştirme
vb.) dönüştürülüp aynı kurallarla kaydedilir; eksik sınıf, öğrenci ve işletme kayıtları
oluşturulur, boş hücreler mevcut bilgilerin üzerine yazılmaz.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date as date_, datetime as datetime_
from typing import Any

from .. import config
from ..mevzuat import DEVAMSIZLIK_TURLERI, OGRENCI_STATULERI, PROGRAMLAR, UNVANLAR, YERLESTIRME_TURLERI
from . import aktarim
from .aktarim import TANIMLAR, IceAktarmaSonucu, IceAktarmaTanimi, Secenekler
from .okuyucu import Tablo
from .utils import tc_gecerli

EVET_HAYIR = ("E", "H")
TARIH_ALANLARI = {"baslangic", "bitis", "sozlesme_tarihi", "dogum_tarihi", "tarih", "dekont_tarihi",
                  "giris_tarihi", "cikis_tarihi", "bildirim_tarihi"}
SAYI_ALANLARI = {"personel_sayisi", "kontenjan", "mesafe_km", "ucret", "odenen", "haftalik_saat", "saat",
                 "kapasite", "seviye", "gun", "ozursuz", "ozurlu", "blok", "basari_ortalamasi"}
EVET_HAYIR_ALANLARI = {"bakmakla_yukumlu", "kamu_kurumu", "koordinator", "atolye_gerekli"}
SECENEKLER: dict[str, tuple[str, ...]] = {
    "program": tuple(PROGRAMLAR), "statu": tuple(OGRENCI_STATULERI), "unvan": tuple(UNVANLAR),
    "cinsiyet": ("E", "K"), "yer": ("Okul", "İşletme"), "islem": ("Giriş", "Çıkış"),
    **{k: EVET_HAYIR for k in EVET_HAYIR_ALANLARI},
}
TUR_SECENEKLERI: dict[str, tuple[str, ...]] = {
    "yerlestirmeler": tuple(YERLESTIRME_TURLERI), "devamsizlik": tuple(DEVAMSIZLIK_TURLERI),
    "dersler": ("Kültür", "Meslek", "Atölye"), "atolyeler": ("Atölye", "Laboratuvar", "Derslik"),
}
GUN_SECENEKLERI = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma")


def secenekler(veri_turu: str, alan: str) -> tuple[str, ...]:
    if alan == "tur":
        return TUR_SECENEKLERI.get(veri_turu, ())
    if veri_turu == "program_hucreleri" and alan == "gun":
        return GUN_SECENEKLERI
    return SECENEKLER.get(alan, ())


@dataclass(frozen=True)
class Sutun:
    anahtar: str
    baslik: str
    zorunlu: bool = False
    ipucu: str = ""
    secenekler: tuple[str, ...] = ()


@dataclass(frozen=True)
class GirisTuru:
    anahtar: str
    ad: str
    sutunlar: tuple[Sutun, ...]
    bilesenler: tuple[str, ...]
    aciklama: str = ""
    # bileşen -> {giriş sütunu: bileşendeki alan}
    yeniden_adlandir: dict[str, dict[str, str]] = field(default_factory=dict)
    # bu bileşen yalnızca bu sütun dolu satırlar için ve tekilleştirilerek aktarılır
    tekil: dict[str, str] = field(default_factory=dict)

    def baslik(self, anahtar: str) -> str:
        return next((s.baslik for s in self.sutunlar if s.anahtar == anahtar), anahtar)


def _ipucu(anahtar: str) -> str:
    if anahtar in TARIH_ALANLARI:
        return "gg.aa.yyyy"
    if anahtar in EVET_HAYIR_ALANLARI:
        return "E / H"
    return ""


HIZLI = GirisTuru(
    "hizli", "Öğrenci + İşletme Yerleştirme (SGK ve ücret için hızlı giriş)",
    (Sutun("tc", "T.C. Kimlik No", ipucu="11 hane"),
     Sutun("ad_soyad", "Adı Soyadı", True),
     Sutun("sinif", "Sınıf/Şube", ipucu="ör. 11-A"),
     Sutun("program", "Program", ipucu="MEM / MTAL-AMP / MTAL-AMP-11 / MTAL-ATP", secenekler=tuple(PROGRAMLAR)),
     Sutun("statu", "Statü", ipucu="Öğrenci / Aday Çırak / Çırak / Kalfa (MEM 12) / Açık Lise",
           secenekler=tuple(OGRENCI_STATULERI)),
     Sutun("bakmakla_yukumlu", "Bakmakla Yükümlü (E/H)", ipucu="E: belge 7, H: belge 42", secenekler=EVET_HAYIR),
     Sutun("isletme", "İşletme Adı", True),
     Sutun("personel_sayisi", "İşletme Personel Sayısı", ipucu="ücret/devlet katkısı oranı için"),
     Sutun("baslangic", "İşletmeye Başlama Tarihi", True, "gg.aa.yyyy"),
     Sutun("bitis", "Ayrılış Tarihi", ipucu="gg.aa.yyyy, devam ediyorsa boş"),
     Sutun("iban", "Öğrenci IBAN")),
    ("siniflar", "ogrenciler", "yerlestirmeler"),
    "Her satır bir öğrenci. Öğrenci, sınıf ve işletme kayıtları yoksa oluşturulur, varsa boş olmayan "
    "bilgilerle güncellenir. Eylül SGK listesi ve işletme ücret yazıları için gereken bilgiler budur.",
    yeniden_adlandir={"siniflar": {"sinif": "ad"}},
    tekil={"siniflar": "program"},
)


def _tanimdan(anahtar: str) -> GirisTuru:
    t = TANIMLAR[anahtar]
    zorunlu = set.intersection(*(set(g) for g in t.zorunlu)) if t.zorunlu else set()
    return GirisTuru(anahtar, t.etiket,
                     tuple(Sutun(a, g, a in zorunlu, _ipucu(a), secenekler(anahtar, a)) for a, g, _ in t.alanlar),
                     (anahtar,), t.aciklama)


GIRIS_TURLERI: list[GirisTuru] = [HIZLI] + [_tanimdan(k) for k in sorted(TANIMLAR, key=lambda k: TANIMLAR[k].sira)]
GIRIS_SOZLUK = {g.anahtar: g for g in GIRIS_TURLERI}


# ------------------------------------------------------------------ yapıştırılan başlıkları eşleme

def _es_anlamlilar(tur: GirisTuru, anahtar: str) -> list[str]:
    out: list[str] = []
    for b in tur.bilesenler:
        alan = tur.yeniden_adlandir.get(b, {}).get(anahtar, anahtar)
        for a, g, syn in TANIMLAR[b].alanlar:
            if a == alan:
                out += [g, *syn]
    return out


def _esleme_tanimi(tur: GirisTuru) -> IceAktarmaTanimi:
    alanlar = [(s.anahtar, s.baslik, _es_anlamlilar(tur, s.anahtar)) for s in tur.sutunlar]
    anahtarlar = {s.anahtar for s in tur.sutunlar}
    if "ad_soyad" in anahtarlar and "ad" not in anahtarlar:
        ogr = {a: (g, syn) for a, g, syn in TANIMLAR["ogrenciler"].alanlar}
        alanlar += [("ad", *ogr["ad"]), ("soyad", *ogr["soyad"])]
    return IceAktarmaTanimi(f"giris_{tur.anahtar}", tur.ad, alanlar)


def basliklari_esle(tur: GirisTuru, satir: list[Any]) -> dict[int, list[int]] | None:
    """Yapıştırılan ilk satır başlık satırıysa {giriş sütunu: [yapıştırılan sütunlar]} döner.

    Ayrı "Adı" ve "Soyadı" sütunları, girişte tek "Adı Soyadı" sütunu varsa birleştirilir.
    """
    es = aktarim.eslestir(satir, _esleme_tanimi(tur))
    if len(es) < 2 and not (len(satir) == 1 and es):
        return None
    sira = {s.anahtar: i for i, s in enumerate(tur.sutunlar)}
    out: dict[int, list[int]] = {}
    for anahtar, j in es.items():
        if anahtar in sira:
            out.setdefault(sira[anahtar], []).append(j)
    if "ad_soyad" in sira and "ad_soyad" not in es and "ad" in es:
        out[sira["ad_soyad"]] = [es["ad"]] + ([es["soyad"]] if "soyad" in es else [])
    return out or None


def yapistirilan_metin(metin: str) -> list[list[str]]:
    """Excel/tarayıcıdan kopyalanan sekmeyle ayrılmış metni satır ve hücrelere ayırır."""
    satirlar = metin.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while satirlar and not satirlar[-1].strip():
        satirlar.pop()
    return [[h.strip() for h in s.split("\t")] for s in satirlar]


# ------------------------------------------------------------------ denetim

@dataclass
class Bulgu:
    satir: int
    sutun: int
    mesaj: str
    hata: bool = True


def dolu_satirlar(satirlar: list[list[Any]]) -> list[int]:
    return [i for i, r in enumerate(satirlar) if any(aktarim.metin(v) for v in r)]


def denetle(tur: GirisTuru, satirlar: list[list[Any]]) -> list[Bulgu]:
    """Kaydetmeden önce zorunlu alan, T.C. kimlik no, tarih, sayı ve E/H değerlerini denetler."""
    out: list[Bulgu] = []
    for i in dolu_satirlar(satirlar):
        r = satirlar[i]
        for j, s in enumerate(tur.sutunlar):
            v = aktarim.metin(r[j] if j < len(r) else "")
            if not v:
                if s.zorunlu:
                    out.append(Bulgu(i, j, f"{s.baslik} boş"))
                continue
            if s.anahtar == "tc" and not tc_gecerli(v):
                out.append(Bulgu(i, j, "T.C. kimlik no geçersiz"))
            elif s.anahtar in TARIH_ALANLARI and not aktarim.tarih(v):
                out.append(Bulgu(i, j, f"{s.baslik} tarih olarak okunamadı (gg.aa.yyyy)"))
            elif tur.anahtar == "program_hucreleri" and s.anahtar == "gun":
                from . import program_belge
                if program_belge.gun_coz(v) is None:
                    out.append(Bulgu(i, j, "Gün adı okunamadı (Pazartesi … Cuma veya 1-5)"))
            elif s.anahtar in SAYI_ALANLARI and aktarim.sayi(v) is None:
                out.append(Bulgu(i, j, f"{s.baslik} sayı olmalı"))
            elif s.anahtar in EVET_HAYIR_ALANLARI and aktarim.evet(v) is None:
                out.append(Bulgu(i, j, f"{s.baslik} için E veya H yazın"))
            elif s.anahtar == "iban" and not v.replace(" ", "").upper().startswith("TR"):
                out.append(Bulgu(i, j, "IBAN TR ile başlamalı", hata=False))
        if "personel_sayisi" in {s.anahtar for s in tur.sutunlar}:
            j = [s.anahtar for s in tur.sutunlar].index("personel_sayisi")
            prog = next((aktarim.metin(r[k]) for k, s in enumerate(tur.sutunlar)
                         if s.anahtar == "program" and k < len(r)), "")
            if not aktarim.metin(r[j] if j < len(r) else "") and prog.upper() != "MEM":
                out.append(Bulgu(i, j, "Personel sayısı boş: MTAL'de devlet katkısı oranı buna göre belirlenir",
                                 hata=False))
    return out


# ------------------------------------------------------------------ kaydetme

@dataclass
class SatirDurumu:
    durum: str  # eklendi | guncellendi | atlandi | hata
    mesajlar: list[str] = field(default_factory=list)


def kaydet(db, tur: GirisTuru, satirlar: list[list[Any]], deneme: bool = False,
           sec: Secenekler | None = None) -> tuple[list[IceAktarmaSonucu], dict[int, SatirDurumu]]:
    """Dolu satırları bileşen veri türleri sırasıyla aktarır; giriş satırı başına sonuç döner."""
    sec = sec or Secenekler()
    dolu = dolu_satirlar(satirlar)
    if not dolu:
        return [], {}
    if not deneme:
        db.yedekle()
    genislik = len(tur.sutunlar)
    sonuclar: list[IceAktarmaSonucu] = []
    durumlar: dict[int, SatirDurumu] = {}
    oncelik = {"hata": 3, "atlandi": 2, "eklendi": 1, "guncellendi": 0}

    for b in tur.bilesenler:
        tanim = TANIMLAR[b]
        ad_degis = tur.yeniden_adlandir.get(b, {})
        alanlar = {a for a, _, _ in tanim.alanlar}
        eslesme = {ad_degis.get(s.anahtar, s.anahtar): j for j, s in enumerate(tur.sutunlar)
                   if ad_degis.get(s.anahtar, s.anahtar) in alanlar}
        if not aktarim.zorunlu_tamam(tanim, eslesme):
            continue
        kaynak = dolu
        if b in tur.tekil:
            j_kosul = [s.anahtar for s in tur.sutunlar].index(tur.tekil[b])
            j_ad = next(j for a, j in eslesme.items() if a == "ad")
            gorulen, kaynak = set(), []
            for i in dolu:
                r = satirlar[i]
                anahtar = aktarim.norm(aktarim.sinif_adi(r[j_ad] if j_ad < len(r) else ""))
                if aktarim.metin(r[j_kosul] if j_kosul < len(r) else "") and anahtar and anahtar not in gorulen:
                    gorulen.add(anahtar)
                    kaynak.append(i)
            if not kaynak:
                continue
        basliklar = [s.baslik for s in tur.sutunlar]
        veri = [list(satirlar[i][:genislik]) + [""] * (genislik - len(satirlar[i][:genislik])) for i in kaynak]
        sonuc = aktarim.aktar(db, Tablo("Toplu giriş", tanim.etiket, [basliklar] + veri), b, 0, eslesme, sec, deneme,
                              ek=False, baglam=False)
        sonuclar.append(sonuc)
        if b in tur.tekil:
            continue
        for s in sonuc.satirlar:
            i = kaynak[s.no - 1]
            d = durumlar.setdefault(i, SatirDurumu(s.durum))
            if oncelik[s.durum] > oncelik[d.durum]:
                d.durum = s.durum
            if s.mesaj:
                d.mesajlar.append(f"{tanim.etiket}: {s.mesaj}")
    return sonuclar, durumlar


# ------------------------------------------------------------------ belgeden yükleme

@dataclass
class BelgeTablosu:
    tablo: Tablo
    tahmin: aktarim.Tahmin | None
    tur: GirisTuru | None
    satirlar: list[list[str]] = field(default_factory=list)  # giriş türünün sütun sırasıyla

    @property
    def etiket(self) -> str:
        return self.tablo.etiket


def _hucre(v: Any) -> str:
    if isinstance(v, date_) and not isinstance(v, datetime_):
        return v.strftime("%d.%m.%Y")
    return aktarim.metin(v)


def belgeden_satirlar(tur: GirisTuru, tablo: Tablo, bas: int, eslesme: dict[str, int]) -> list[list[str]]:
    """Belgedeki kayıtları giriş tablosunun sütunlarına dizer. Başlık üstündeki/ara satırlardaki sınıf, dönem,
    işletme gibi bilgiler sütunlara işlenir; başlık tekrarı, toplam ve imza satırları alınmaz."""
    tanim = TANIMLAR[tur.anahtar] if tur.anahtar in TANIMLAR else TANIMLAR[tur.bilesenler[-1]]
    out = []
    for _, _, d, _ in aktarim.kayit_satirlari(tablo, tanim, bas, eslesme):
        out.append([_hucre(d.get(s.anahtar)) for s in tur.sutunlar])
    return out


def belgeleri_incele(yollar: list) -> tuple[list[BelgeTablosu], list[str]]:
    """Belgelerdeki tabloların türünü tanır ve kayıtlarını giriş tablosu biçimine çevirir."""
    bulunan, hatalar = aktarim.dosyalari_incele(yollar)
    out = []
    for b in bulunan:
        t = b.en_iyi
        tur = GIRIS_SOZLUK.get(t.anahtar) if t else None
        out.append(BelgeTablosu(b.tablo, t, tur, belgeden_satirlar(tur, b.tablo, t.bas, t.eslesme) if tur else []))
    return out, hatalar


def akilli_kaydet(db, yollar: list, sec: Secenekler | None = None) -> tuple[list[IceAktarmaSonucu], list[str]]:
    """Belgelerdeki tanınan tüm tabloları türlerine göre doğrudan kaydeder (önce yedek alınır)."""
    db.yedekle()
    return aktarim.otomatik_aktar(db, yollar, sec)


# ------------------------------------------------------------------ taslaklar

def _taslak_yolu(tur: GirisTuru):
    p = config.data_dir() / "Taslaklar"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"toplu_giris_{tur.anahtar}.json"


def taslak_kaydet(tur: GirisTuru, satirlar: list[list[Any]]) -> None:
    dolu = [[aktarim.metin(v) for v in satirlar[i]] for i in dolu_satirlar(satirlar)]
    yol = _taslak_yolu(tur)
    if dolu:
        yol.write_text(json.dumps({"sutunlar": [s.anahtar for s in tur.sutunlar], "satirlar": dolu},
                                  ensure_ascii=False), encoding="utf-8")
    elif yol.exists():
        yol.unlink()


def taslak_yukle(tur: GirisTuru) -> list[list[str]]:
    yol = _taslak_yolu(tur)
    if not yol.exists():
        return []
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    sira = {a: j for j, a in enumerate(veri.get("sutunlar", []))}
    return [[r[sira[s.anahtar]] if s.anahtar in sira and sira[s.anahtar] < len(r) else "" for s in tur.sutunlar]
            for r in veri.get("satirlar", [])]
