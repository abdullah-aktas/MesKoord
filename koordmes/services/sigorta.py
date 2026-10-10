"""5510 sayılı Kanun kapsamında öğrenci sigorta işlemleri.

- Prime esas kazanç: brüt asgari ücretin %50'si (5510 md.80/1-k, 3308 md.25), günlük = aylık/30.
- Prim oranı: bakmakla yükümlü olunan %1, olunmayan %6 (%1 KVSK + %5 GSS).
- Belge türü: işletme/staj 7 / 42, okulda alan-tamamlayıcı eğitim 49 / 50.
- Prim gün sayısı: tam ayda ayın kaç çektiğine bakılmaksızın 30; ay içinde başlayan/biten
  için parmak hesabı; özürsüz devamsızlık eksik gün (kod 15) olarak düşülür.
- Ara tatil, yarıyıl ve yaz tatillerinde işten ayrılış bildirgesi verilmez.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from ..mevzuat import DEVAMSIZLIK_SGK_KODU, OKUL_ICI_TURLER
from .utils import ay_araligi, tarih

DEVAM_ARALIK_GUN = 15


def prim_gun_sayisi(gunler: set[date], yil: int, ay: int) -> int:
    """Bir ay içinde sigortalı olunan takvim günlerinden prim ödeme gün sayısını hesaplar."""
    ilk, son = ay_araligi(yil, ay)
    if not gunler:
        return 0
    if ilk in gunler and son in gunler and len(gunler) == son.day:
        return 30
    return min(30, len(gunler))


def kapsanan_gunler(bas: date | None, bit: date | None, yil: int, ay: int) -> set[date]:
    ilk, son = ay_araligi(yil, ay)
    if bas is None or bas > son or (bit is not None and bit < ilk):
        return set()
    d, e = max(bas, ilk), min(bit or son, son)
    out = set()
    while d <= e:
        out.add(d)
        d += timedelta(days=1)
    return out


def prim_gun(bas: date | None, bit: date | None, yil: int, ay: int) -> int:
    return prim_gun_sayisi(kapsanan_gunler(bas, bit, yil, ay), yil, ay)


def eksik_gunler(db, ogrenci_id: int, gunler: set[date]) -> tuple[int, str]:
    """Kapsanan günlerdeki SGK'ya eksik gün bildirilecek devamsızlıklar: (gün, neden kodu)."""
    if not gunler or not db.ayar("ozursuz_eksik_gun"):
        return 0, ""
    rows = db.q("SELECT tarih, tur, gun FROM devamsizlik WHERE ogrenci_id = ? AND sgk_eksik = 1 "
                "AND tarih BETWEEN ? AND ?", (ogrenci_id, min(gunler).isoformat(), max(gunler).isoformat()))
    toplam = 0.0
    kodlar = set()
    for r in rows:
        d = tarih(r["tarih"])
        if d in gunler:
            toplam += float(r["gun"] or 0)
            kodlar.add(DEVAMSIZLIK_SGK_KODU.get(r["tur"], "15"))
    gun = int(math.floor(toplam + 1e-9))
    if gun == 0:
        return 0, ""
    return gun, ("12" if len(kodlar) > 1 else next(iter(kodlar)))


def belge_turu(db, yerlestirme_turu: str, bakmakla_yukumlu: bool) -> str:
    if yerlestirme_turu in OKUL_ICI_TURLER:
        return str(db.ayar("belge_okul_yukumlu" if bakmakla_yukumlu else "belge_okul_degil"))
    return str(db.ayar("belge_isletme_yukumlu" if bakmakla_yukumlu else "belge_isletme_degil"))


def prim_orani(db, bakmakla_yukumlu: bool) -> float:
    return db.ayar("sgk_prim_yukumlu" if bakmakla_yukumlu else "sgk_prim_yukumlu_degil")


def gunluk_pek(db) -> float:
    return db.ayar("asgari_ucret_brut") * db.ayar("sgk_pek_orani") / 30.0


@dataclass
class SigortaSatiri:
    ogrenci_id: int
    tc: str
    ad: str
    soyad: str
    sinif: str
    belge_turu: str
    gun: int
    eksik_gun: int
    eksik_neden: str
    pek: float
    oran: float
    prim: float
    giris_tarihi: date | None
    cikis_tarihi: date | None
    isletmeler: list[str] = field(default_factory=list)


def _yerlestirmeler(db, bas: date, bit: date):
    return db.q(
        """SELECT y.*, o.tc, o.ad, o.soyad, o.bakmakla_yukumlu, s.ad AS sinif, i.ad AS isletme
           FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
           LEFT JOIN siniflar s ON s.id = o.sinif_id LEFT JOIN isletmeler i ON i.id = y.isletme_id
           WHERE y.baslangic IS NOT NULL AND y.baslangic <= ? AND (y.bitis IS NULL OR y.bitis = '' OR y.bitis >= ?)
           ORDER BY s.ad, o.okul_no, o.ad""", (bit.isoformat(), bas.isoformat()))


def aylik_liste(db, yil: int, ay: int) -> list[SigortaSatiri]:
    ilk, son = ay_araligi(yil, ay)
    gruplar: dict[tuple[int, str], dict] = {}
    pek_gunluk = gunluk_pek(db)
    for y in _yerlestirmeler(db, ilk, son):
        yukumlu = bool(y["bakmakla_yukumlu"])
        bt = belge_turu(db, y["tur"], yukumlu)
        key = (y["ogrenci_id"], bt)
        g = gruplar.setdefault(key, {"row": y, "gunler": set(), "isletmeler": [], "yukumlu": yukumlu,
                                     "bas": [], "bit": []})
        b, e = tarih(y["baslangic"]), tarih(y["bitis"])
        g["gunler"] |= kapsanan_gunler(b, e, yil, ay)
        g["bas"].append(b)
        g["bit"].append(e)
        if y["isletme"] and y["isletme"] not in g["isletmeler"]:
            g["isletmeler"].append(y["isletme"])

    out = []
    for (ogr_id, bt), g in gruplar.items():
        if not g["gunler"]:
            continue
        r = g["row"]
        gun = prim_gun_sayisi(g["gunler"], yil, ay)
        eksik, neden = eksik_gunler(db, ogr_id, g["gunler"])
        eksik = min(eksik, gun)
        net_gun = gun - eksik
        oran = prim_orani(db, g["yukumlu"])
        pek = round(pek_gunluk * net_gun, 2)
        giris = min(g["bas"]) if min(g["bas"]) >= ilk else None
        bitisler = [x for x in g["bit"] if x is not None]
        cikis = max(bitisler) if bitisler and None not in g["bit"] and max(bitisler) <= son else None
        out.append(SigortaSatiri(ogr_id, r["tc"] or "", r["ad"], r["soyad"], r["sinif"] or "", bt,
                                 net_gun, eksik, neden, pek, oran, round(pek * oran, 2), giris, cikis,
                                 g["isletmeler"]))
    return out


def belge_turu_ozeti(satirlar: list[SigortaSatiri]) -> list[tuple[str, int, int, float, float]]:
    """Belge türüne göre (belge, kişi, gün, PEK, prim) toplamları."""
    agg: dict[str, list] = defaultdict(lambda: [0, 0, 0.0, 0.0])
    for s in satirlar:
        a = agg[s.belge_turu]
        a[0] += 1
        a[1] += s.gun
        a[2] += s.pek
        a[3] += s.prim
    return [(bt, a[0], a[1], round(a[2], 2), round(a[3], 2)) for bt, a in sorted(agg.items())]


@dataclass
class Bildirim:
    yerlestirme_id: int
    tur: str  # "Giriş" | "Çıkış"
    ogrenci: str
    tc: str
    sinif: str
    isletme: str
    olay_tarihi: date
    son_tarih: date
    gecikti: bool
    belge_turu: str


def bekleyen_bildirimler(db, bugun: date | None = None, ileri_gun: int = 30) -> list[Bildirim]:
    bugun = bugun or date.today()
    rows = db.q(
        """SELECT y.*, o.tc, o.ad, o.soyad, o.bakmakla_yukumlu, s.ad AS sinif, i.ad AS isletme
           FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
           LEFT JOIN siniflar s ON s.id = o.sinif_id LEFT JOIN isletmeler i ON i.id = y.isletme_id
           WHERE y.baslangic IS NOT NULL""")
    by_ogr: dict[int, list] = defaultdict(list)
    for r in rows:
        by_ogr[r["ogrenci_id"]].append(r)

    giris_once = db.ayar("sgk_giris_once_gun")
    cikis_sure = db.ayar("sgk_cikis_bildirim_gun")
    out: list[Bildirim] = []
    for r in rows:
        b, e = tarih(r["baslangic"]), tarih(r["bitis"])
        digerleri = [x for x in by_ogr[r["ogrenci_id"]] if x["id"] != r["id"]]
        bt = belge_turu(db, r["tur"], bool(r["bakmakla_yukumlu"]))
        ad = f"{r['ad']} {r['soyad']}"
        if not r["sigorta_giris_bildirildi"] and b and b <= bugun + timedelta(days=ileri_gun):
            devam = any(tarih(x["baslangic"]) and tarih(x["baslangic"]) < b and
                        (tarih(x["bitis"]) is None or tarih(x["bitis"]) >= b - timedelta(days=DEVAM_ARALIK_GUN))
                        for x in digerleri)
            if not devam:
                son = b - timedelta(days=giris_once)
                out.append(Bildirim(r["id"], "Giriş", ad, r["tc"] or "", r["sinif"] or "", r["isletme"] or "",
                                    b, son, bugun > son, bt))
        if e and not r["sigorta_cikis_bildirildi"] and e <= bugun + timedelta(days=ileri_gun):
            devam = any(tarih(x["baslangic"]) and e < tarih(x["baslangic"]) <= e + timedelta(days=DEVAM_ARALIK_GUN)
                        or (tarih(x["baslangic"]) and tarih(x["baslangic"]) <= e and
                            (tarih(x["bitis"]) is None or tarih(x["bitis"]) > e))
                        for x in digerleri)
            if not devam:
                son = e + timedelta(days=cikis_sure)
                out.append(Bildirim(r["id"], "Çıkış", ad, r["tc"] or "", r["sinif"] or "", r["isletme"] or "",
                                    e, son, bugun > son, bt))
    out.sort(key=lambda x: x.son_tarih)
    return out


def bildirildi_isaretle(db, yerlestirme_id: int, tur: str, tarih_: date | None = None) -> None:
    t = (tarih_ or date.today()).isoformat()
    if tur == "Giriş":
        db.update("yerlestirmeler", yerlestirme_id, {"sigorta_giris_bildirildi": 1, "sigorta_giris_bildirim_tarihi": t})
    else:
        db.update("yerlestirmeler", yerlestirme_id, {"sigorta_cikis_bildirildi": 1, "sigorta_cikis_bildirim_tarihi": t})
