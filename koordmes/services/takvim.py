"""Yasal süre hatırlatmaları ve veri tutarlılık uyarıları (Ana sayfa)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import devam, sigorta
from .utils import ay_araligi, ilerideki_is_gunu, tatil_gunleri, tc_gecerli, tr
from ..mevzuat import AYLAR


@dataclass
class Uyari:
    seviye: str  # "Kritik" | "Uyarı" | "Bilgi"
    konu: str
    mesaj: str
    tarih: date | None = None


def _onceki_ay(d: date) -> tuple[int, int]:
    return (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)


def _kalan_seviye(kalan: int) -> str:
    return "Kritik" if kalan <= 2 else "Uyarı" if kalan <= 7 else "Bilgi"


def _yonetmelik_sureleri(db, bugun: date, out: list[Uyari]) -> None:
    """Puan çizelgesi teslimi (md.89/1-g, md.144/1-g) ve sözleşme imza süresi (md.143/1)."""
    from . import mesleki_egitim
    sure = int(db.ayar("puan_cizelgesi_gun"))
    for p in mesleki_egitim.puan_teslimleri(db, bugun):
        if not p.eksik:
            continue
        kalan = (p.son_teslim - bugun).days
        if kalan >= 0:
            out.append(Uyari(_kalan_seviye(kalan), "Değerlendirme",
                             f"{p.donem}. dönem işletme puan çizelgeleri dönem sonundan {sure} gün önce teslim "
                             f"edilmeli; {len(p.eksik)} öğrencinin notu eksik. Son gün: {tr(p.son_teslim)} "
                             f"({kalan} gün kaldı)", p.son_teslim))
        else:
            out.append(Uyari("Kritik", "Değerlendirme",
                             f"{p.donem}. dönem puan çizelgesi teslim süresi geçti ({tr(p.son_teslim)}); "
                             f"{len(p.eksik)} öğrencinin işletme notu eksik.", p.son_teslim))
    yb = mesleki_egitim.ders_yili_baslangici(db)
    if not yb:
        return
    son = yb + timedelta(days=int(db.ayar("sozlesme_sure_gun")))
    if yb - timedelta(days=14) <= bugun <= son:
        n = db.q1("""SELECT COUNT(*) c FROM yerlestirmeler WHERE durum = 'Aktif' AND isletme_id IS NOT NULL
                     AND tur != 'Okulda Alan Eğitimi' AND (sozlesme_tarihi IS NULL OR sozlesme_tarihi = '')""")["c"]
        if n:
            kalan = (son - bugun).days
            out.append(Uyari(_kalan_seviye(kalan), "Sözleşme",
                             f"Sözleşmeler yeni ders yılının ikinci haftası sonuna kadar imzalanmalı (md.143); "
                             f"{n} yerleştirmede sözleşme tarihi yok. Son gün: {tr(son)} ({kalan} gün kaldı)", son))


def uyarilar(db, bugun: date | None = None) -> list[Uyari]:
    bugun = bugun or date.today()
    out: list[Uyari] = []
    ilk, son = ay_araligi(bugun.year, bugun.month)
    tatiller = tatil_gunleri(db, ilk, son + timedelta(days=10))
    oy, oa = _onceki_ay(bugun)
    onceki = f"{AYLAR[oa - 1]} {oy}"

    def sureli(konu: str, gun: int, mesaj: str) -> None:
        son_gun = ilerideki_is_gunu(date(bugun.year, bugun.month, min(gun, son.day)), tatiller)
        kalan = (son_gun - bugun).days
        if kalan < 0:
            return
        seviye = "Kritik" if kalan <= 2 else "Uyarı" if kalan <= 7 else "Bilgi"
        out.append(Uyari(seviye, konu, f"{mesaj} Son gün: {tr(son_gun)} ({kalan} gün kaldı)", son_gun))

    sureli("SGK", db.ayar("muhsgk_son_gun"),
           f"{onceki} dönemi öğrenci aylık prim ve hizmet belgesi (MUHSGK) verilmeli ve prim ödenmeli.")
    sureli("Devlet Katkısı", db.ayar("dekont_teslim_son_gun"),
           f"{onceki} dönemi öğrenci ücret dekontları işletmelerden toplanmalı.")
    sureli("Devlet Katkısı", db.ayar("dk_sisteme_giris_son_gun"),
           f"{onceki} dönemi devlet katkısı bilgileri e-Okul / e-Mesem'e girilmeli.")

    for b in sigorta.bekleyen_bildirimler(db, bugun):
        if b.gecikti:
            seviye = "Kritik"
        elif (b.son_tarih - bugun).days <= 3:
            seviye = "Uyarı"
        else:
            seviye = "Bilgi"
        islem = "işe giriş" if b.tur == "Giriş" else "işten ayrılış"
        durum = "SÜRESİ GEÇTİ" if b.gecikti else f"son gün {tr(b.son_tarih)}"
        out.append(Uyari(seviye, "SGK", f"{b.ogrenci} ({b.sinif}) {islem} bildirgesi - {durum}", b.son_tarih))

    for x in devam.ozet(db):
        if x.durum == "Sınırı aştı":
            out.append(Uyari("Kritik", "Devamsızlık", f"{x.ad} ({x.sinif}) devamsızlık sınırını aştı "
                                                      f"(özürsüz {x.toplam_ozursuz:g}, toplam {x.toplam:g} gün)"))
        elif x.durum in ("Sınıra yakın", "Veli bildirimi"):
            out.append(Uyari("Uyarı", "Devamsızlık", f"{x.ad} ({x.sinif}) {x.durum.lower()} "
                                                     f"(özürsüz {x.toplam_ozursuz:g}, toplam {x.toplam:g} gün)"))

    hafta_sonu = bugun + timedelta(days=7)
    n = db.q1("SELECT COUNT(*) c FROM ziyaretler WHERE durum = 'Planlandı' AND tarih BETWEEN ? AND ?",
              (bugun.isoformat(), hafta_sonu.isoformat()))["c"]
    if n:
        out.append(Uyari("Bilgi", "Koordinatörlük", f"Önümüzdeki 7 günde {n} planlı işletme ziyareti var."))
    n = db.q1("SELECT COUNT(*) c FROM ziyaretler WHERE durum = 'Planlandı' AND tarih < ?", (bugun.isoformat(),))["c"]
    if n:
        out.append(Uyari("Uyarı", "Koordinatörlük", f"Tarihi geçmiş ve sonucu girilmemiş {n} ziyaret var."))

    for r in db.q("""SELECT o.ad, o.soyad, i.ad AS isletme FROM yerlestirmeler y
                     JOIN ogrenciler o ON o.id = y.ogrenci_id LEFT JOIN isletmeler i ON i.id = y.isletme_id
                     WHERE y.durum = 'Aktif' AND y.tur != 'Okulda Alan Eğitimi'
                       AND (y.sozlesme_no IS NULL OR y.sozlesme_no = '')"""):
        out.append(Uyari("Uyarı", "Sözleşme", f"{r['ad']} {r['soyad']} - {r['isletme'] or '?'}: sözleşme numarası yok."))
    for r in db.q("""SELECT DISTINCT i.ad FROM isletmeler i JOIN yerlestirmeler y ON y.isletme_id = i.id
                     WHERE y.durum = 'Aktif' AND (i.personel_sayisi IS NULL OR i.personel_sayisi = 0)"""):
        out.append(Uyari("Uyarı", "İşletme", f"{r['ad']}: personel sayısı girilmemiş (ücret/devlet katkısı oranını etkiler)."))
    gecersiz = [f"{r['ad']} {r['soyad']}" for r in db.q(
        """SELECT DISTINCT o.ad, o.soyad, o.tc FROM ogrenciler o JOIN yerlestirmeler y ON y.ogrenci_id = o.id
           WHERE o.aktif = 1""") if not tc_gecerli(r["tc"])]
    if gecersiz:
        out.append(Uyari("Uyarı", "Öğrenci", f"Sigortalı {len(gecersiz)} öğrencinin T.C. kimlik numarası geçersiz/eksik: "
                                             + ", ".join(gecersiz[:5]) + (" ..." if len(gecersiz) > 5 else "")))
    _yonetmelik_sureleri(db, bugun, out)

    k = db.kurum()
    if not k["ad"]:
        out.append(Uyari("Bilgi", "Ayarlar", "Kurum bilgileri girilmemiş (Ayarlar > Kurum Bilgileri)."))

    sira = {"Kritik": 0, "Uyarı": 1, "Bilgi": 2}
    out.sort(key=lambda u: (sira[u.seviye], u.tarih or date.max))
    return out
