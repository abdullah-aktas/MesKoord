"""Excel rapor üretimi (ekranlar, asistan ve aylık kapanış ortak kullanır)."""
from __future__ import annotations

import calendar
from pathlib import Path
from typing import Any

from .. import config
from ..mevzuat import AYLAR, EKSIK_GUN_NEDENLERI, GUNLER
from . import devam, ekders, koordinator, sigorta, ucret
from .excel_io import ExcelYazici, tablo_yaz
from .utils import ay_araligi, tarih, tr

Satirlar = list[list[Any]]


def _yol(yol: Path | str | None, ad: str) -> Path:
    return Path(yol) if yol else config.output_dir() / f"{ad}.xlsx"


def _donem(yil: int, ay: int) -> str:
    return f"{AYLAR[ay - 1]} {yil}"


# ------------------------------------------------------------------ SGK

SGK_BASLIKLAR = ["T.C. Kimlik No", "Adı", "Soyadı", "Sınıf", "Belge Türü", "Prim Gün", "Eksik Gün", "Eksik Gün Nedeni",
                 "Prime Esas Kazanç", "Prim Oranı", "Prim Tutarı", "Giriş Tarihi", "Çıkış Tarihi", "İşletme"]


def sgk_satirlari(db, yil: int, ay: int) -> tuple[Satirlar, list[sigorta.SigortaSatiri]]:
    liste = sigorta.aylik_liste(db, yil, ay)
    rows = [[s.tc, s.ad, s.soyad, s.sinif, s.belge_turu, s.gun, s.eksik_gun,
             f"{s.eksik_neden} - {EKSIK_GUN_NEDENLERI.get(s.eksik_neden, '')}" if s.eksik_neden else "",
             s.pek, f"%{s.oran * 100:g}", s.prim, tr(s.giris_tarihi), tr(s.cikis_tarihi), ", ".join(s.isletmeler)]
            for s in liste]
    return rows, liste


def sgk_prim_listesi(db, yil: int, ay: int, yol: Path | str | None = None) -> Path:
    rows, liste = sgk_satirlari(db, yil, ay)
    k = db.kurum()
    x = ExcelYazici()
    x.sayfa("Prim Hizmet Listesi", SGK_BASLIKLAR, rows,
            baslik=f"{k['ad']} - {_donem(yil, ay)} Öğrenci Aylık Prim ve Hizmet Listesi "
                   f"(İşyeri Sicil: {k['sgk_isyeri_sicil']})")
    oz = sigorta.belge_turu_ozeti(liste)
    x.sayfa("Belge Türü Özeti", ["Belge Türü", "Kişi", "Gün", "PEK Toplamı", "Prim Toplamı"], [list(o) for o in oz])
    for bt in sorted({s.belge_turu for s in liste}):
        x.sayfa(f"Belge {bt}", SGK_BASLIKLAR, [r for r, s in zip(rows, liste) if s.belge_turu == bt])
    return x.kaydet(_yol(yol, f"SGK Aylık Prim Hizmet Listesi {_donem(yil, ay)}"))


BILDIRIM_BASLIKLAR = ["İşlem", "Öğrenci", "Okul No", "T.C. Kimlik No", "Sınıf", "İşletme", "Belge Türü",
                      "Olay Tarihi", "Son Bildirim", "Durum"]


def _bildirim_durumu(b: sigorta.Bildirim) -> str:
    if b.bildirildi:
        return f"Bildirildi {tr(b.bildirim_tarihi)}".strip()
    return "SÜRESİ GEÇTİ" if b.gecikti else "Bekliyor"


def bildirim_satirlari(db, dahil_bildirilen: bool = False) -> tuple[Satirlar, list[sigorta.Bildirim]]:
    liste = sigorta.bekleyen_bildirimler(db, dahil_bildirilen=dahil_bildirilen)
    return [[b.tur, b.ogrenci, b.okul_no, b.tc, b.sinif, b.isletme, b.belge_turu, tr(b.olay_tarihi),
             tr(b.son_tarih), _bildirim_durumu(b)] for b in liste], liste


def sgk_bildirim_listesi(db, yol: Path | str | None = None) -> Path:
    rows, _ = bildirim_satirlari(db)
    return tablo_yaz(_yol(yol, "SGK Giriş-Çıkış Bildirim Listesi"), BILDIRIM_BASLIKLAR, rows,
                     baslik="Bekleyen SGK İşe Giriş / İşten Ayrılış Bildirimleri")


# ------------------------------------------------------------------ ücret ve dekont

UCRET_BASLIKLAR = ["Öğrenci", "T.C. Kimlik No", "Sınıf", "Program", "İşletme", "Personel", "Gün", "Oran", "Dayanak",
                   "Yasal Alt Sınır", "Ödenecek Ücret", "DK Payı", "Devlet Katkısı", "İşletme Payı", "IBAN"]


def ucret_satirlari(db, yil: int, ay: int) -> tuple[Satirlar, list[ucret.UcretSatiri]]:
    liste = ucret.aylik_hesap(db, yil, ay)
    return [[s.ogrenci, s.tc, s.sinif, s.program, s.isletme, s.personel, s.gun, f"%{s.oran * 100:g}", s.oran_aciklama,
             s.en_az_ucret, s.odenecek_ucret, f"{s.dk_pay:.4g}", s.devlet_katkisi, s.isletme_payi, s.iban]
            for s in liste], liste


def ucret_listesi(db, yil: int, ay: int, yol: Path | str | None = None) -> Path:
    rows, liste = ucret_satirlari(db, yil, ay)
    x = ExcelYazici()
    x.sayfa("Öğrenci Listesi", UCRET_BASLIKLAR, rows,
            baslik=f"{db.kurum()['ad']} - {_donem(yil, ay)} Öğrenci Ücret ve Devlet Katkısı Listesi")
    isletme: dict[str, list] = {}
    for s in liste:
        a = isletme.setdefault(s.isletme, [s.isletme, s.personel, 0, 0.0, 0.0])
        a[2] += 1
        a[3] += s.odenecek_ucret
        a[4] += s.devlet_katkisi
    x.sayfa("İşletme Özeti", ["İşletme", "Personel", "Öğrenci", "Ödenecek Ücret", "Devlet Katkısı"],
            list(isletme.values()))
    d_rows = dekont_satirlari(db, yil, ay)
    if d_rows:
        x.sayfa("Dekont Takibi", DEKONT_BASLIKLAR, d_rows)
    return x.kaydet(_yol(yol, f"Öğrenci Ücret ve Devlet Katkısı {_donem(yil, ay)}"))


DEKONT_BASLIKLAR = ["Öğrenci", "Sınıf", "İşletme", "Gün", "Ödenecek Ücret", "Ödenen", "Dekont", "Dekont Tarihi",
                    "Fark", "Durum"]


def dekont_satirlari(db, yil: int, ay: int) -> Satirlar:
    return [r for _, r in dekont_kayitlari(db, yil, ay)]


def dekont_kayitlari(db, yil: int, ay: int) -> list[tuple[int, list[Any]]]:
    """(aylik_odemeler.id, satır) listesi."""
    rows = db.q("""SELECT o.ad || ' ' || o.soyad AS ogrenci, s.ad AS sinif, i.ad AS isletme, a.*
                   FROM aylik_odemeler a JOIN yerlestirmeler y ON y.id = a.yerlestirme_id
                   JOIN ogrenciler o ON o.id = y.ogrenci_id LEFT JOIN siniflar s ON s.id = o.sinif_id
                   LEFT JOIN isletmeler i ON i.id = y.isletme_id WHERE a.donem = ? ORDER BY i.ad, o.ad""",
                (f"{yil:04d}-{ay:02d}",))
    out = []
    for r in rows:
        odenen, beklenen = r["odenen_ucret"], r["odenecek_ucret"]
        fark = round(odenen - beklenen, 2) if odenen is not None and beklenen is not None else None
        durum = ("Dekont yok" if not r["dekont_teslim"] else "Eksik ödeme" if fark is not None and fark < -0.01
                 else "Tamam")
        out.append((r["id"], [r["ogrenci"], r["sinif"], r["isletme"], r["gun"], beklenen, odenen,
                              "Teslim" if r["dekont_teslim"] else "Bekleniyor", tr(r["dekont_tarihi"]), fark, durum]))
    return out


def dekont_takip(db, yil: int, ay: int, yol: Path | str | None = None) -> Path:
    return tablo_yaz(_yol(yol, f"Dekont Takip Listesi {_donem(yil, ay)}"), DEKONT_BASLIKLAR,
                     dekont_satirlari(db, yil, ay), baslik=f"{db.kurum()['ad']} - {_donem(yil, ay)} Dekont Takibi")


# ------------------------------------------------------------------ ek ders

def ekders_tablosu(db, yil: int, ay: int) -> tuple[list[str], Satirlar, list[ekders.Puantaj]]:
    gun_sayisi = calendar.monthrange(yil, ay)[1]
    basliklar = ["Öğretmen", "Unvan", "Aylık Karşılık", "Azami Ek"] + [str(d) for d in range(1, gun_sayisi + 1)] + \
                ["Ders (Ek)", "İşl. Meslek Eğt.", "Rehberlik/Kulüp", "Elle Girilen", "Gündüz", "Gece", "Toplam",
                 "Tahmini Brüt (TL)"]
    liste = ekders.puantaj(db, yil, ay)
    satirlar = []
    for p in liste:
        gunler = [p.gunluk.get(d) or None for d in range(1, gun_sayisi + 1)]
        satirlar.append([p.ad, p.unvan, p.aylik_karsilik, p.azami]
                        + [int(g) if g and float(g).is_integer() else g for g in gunler]
                        + [p.ders, p.isletme, p.gorev, sum(p.diger.values()), p.gunduz, p.gece, p.toplam, p.brut])
    return basliklar, satirlar, liste


def ekders_puantaj(db, yil: int, ay: int, yol: Path | str | None = None) -> Path:
    b, s, _ = ekders_tablosu(db, yil, ay)
    return tablo_yaz(_yol(yol, f"Ek Ders Puantajı {_donem(yil, ay)}"), b, s,
                     baslik=f"{db.kurum()['ad']} - {_donem(yil, ay)} Ek Ders Puantajı",
                     alt_bilgi=[f"Düzenleyen: ........................    Onaylayan: {db.kurum()['mudur']}"])


# ------------------------------------------------------------------ devamsızlık

DEVAM_BASLIKLAR = ["Öğrenci", "No", "Sınıf", "Okul Özürsüz", "Okul Özürlü", "İşletme Özürsüz", "İşletme Özürlü",
                   "Toplam Özürsüz", "Toplam", "Durum", "Veli", "Veli Tel"]


def devam_satirlari(db) -> tuple[Satirlar, list[devam.DevamOzeti]]:
    liste = devam.ozet(db)
    return [[x.ad, x.okul_no, x.sinif, x.okul_ozursuz, x.okul_ozurlu, x.isletme_ozursuz, x.isletme_ozurlu,
             x.toplam_ozursuz, x.toplam, x.durum, x.veli_ad, x.veli_tel] for x in liste], liste


def devam_ozeti(db, yol: Path | str | None = None) -> Path:
    rows, _ = devam_satirlari(db)
    return tablo_yaz(_yol(yol, "Devamsızlık Özeti"), DEVAM_BASLIKLAR, rows, baslik="Öğrenci Devamsızlık Özeti")


# ------------------------------------------------------------------ koordinatörlük

ZIYARET_BASLIKLAR = ["Tarih", "Gün", "Koordinatör Öğretmen", "İşletme", "Güzergah", "Adres", "Durum"]


def ziyaret_satirlari(db, yil: int, ay: int) -> Satirlar:
    ilk, son = ay_araligi(yil, ay)
    rows = db.q("""SELECT z.tarih, o.ad || ' ' || o.soyad AS ogr, i.ad AS isletme, i.guzergah, i.adres, z.durum
                   FROM ziyaretler z LEFT JOIN ogretmenler o ON o.id = z.ogretmen_id
                   LEFT JOIN isletmeler i ON i.id = z.isletme_id WHERE z.tarih BETWEEN ? AND ?
                   ORDER BY o.ad, z.tarih""", (ilk.isoformat(), son.isoformat()))
    out = []
    for r in rows:
        d = tarih(r["tarih"])
        out.append([tr(d), GUNLER[d.weekday()] if d and d.weekday() < 5 else "", r["ogr"], r["isletme"],
                    r["guzergah"], r["adres"], r["durum"]])
    return out


def ziyaret_plani(db, yil: int, ay: int, yol: Path | str | None = None) -> Path:
    return tablo_yaz(_yol(yol, f"Ziyaret Planı {_donem(yil, ay)}"), ZIYARET_BASLIKLAR, ziyaret_satirlari(db, yil, ay),
                     baslik=f"{db.kurum()['ad']} - {_donem(yil, ay)} İşletme Ziyaret Planı")


def koordinator_satirlari(db) -> tuple[list[str], Satirlar]:
    sinir = koordinator.haftalik_azami(db)
    rows = []
    for t in koordinator.gorev_ozeti(db):
        satir = [t["ogretmen"]]
        for g in range(1, 6):
            satir.append("\n".join(f"{i} ({s})" for i, s in t["gunler"].get(g, [])))
        satir += [t["toplam"], sinir]
        rows.append(satir)
    return ["Öğretmen"] + GUNLER + ["Haftalık Toplam", "Sınır"], rows


def koordinator_dagilimi(db, yol: Path | str | None = None) -> Path:
    b, rows = koordinator_satirlari(db)
    return tablo_yaz(_yol(yol, "Koordinatörlük Görev Dağılımı"), b, rows, baslik="Koordinatörlük Görev Dağılımı")
