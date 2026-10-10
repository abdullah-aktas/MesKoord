"""Aylık ek ders puantajı (Ders ve Ek Ders Saatlerine İlişkin Karar).

Haftalık hesap: aylık karşılığı ders görevini önce haftanın tüm program dersleri (ilk günden
başlanarak), ardından işletmelerde meslek eğitimi (koordinatörlük) saatleri doldurur; kalan
saatler ek derstir ve haftalık azami ek ders sınırıyla kırpılır. Resmî tatile denk gelen
günlerdeki dersler aylık karşılığından yapılmış sayılır, ancak ek ders olarak ödenmez.
Elle girilen kayıtlar (nöbet, DYK, gece vb.) doğrudan ek ders olarak eklenir.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

from ..mevzuat import YONETICI_UNVANLARI
from .utils import ay_araligi, tarih, tatil_gunleri, yuvarla


def aylik_karsilik(db, ogr) -> int:
    if ogr["aylik_karsilik"] is not None and str(ogr["aylik_karsilik"]) != "":
        return int(ogr["aylik_karsilik"])
    if ogr["unvan"] in YONETICI_UNVANLARI:
        return db.ayar("aylik_karsilik_yonetici")
    if ogr["unvan"] == "Atölye/Lab. Öğretmeni":
        return db.ayar("aylik_karsilik_atolye")
    return db.ayar("aylik_karsilik_ogretmen")


def azami_ek_ders(db, ogr) -> int:
    if ogr["max_ek_ders"] is not None and str(ogr["max_ek_ders"]) != "":
        return int(ogr["max_ek_ders"])
    if ogr["unvan"] in YONETICI_UNVANLARI:
        return db.ayar("max_ek_ders_yonetici")
    if ogr["unvan"] == "Atölye/Lab. Öğretmeni":
        return db.ayar("max_ek_ders_atolye")
    return db.ayar("max_ek_ders_ogretmen")


@dataclass
class Puantaj:
    ogretmen_id: int
    ad: str
    unvan: str
    aylik_karsilik: int
    azami: int
    gunluk: dict[int, float] = field(default_factory=dict)
    ders: float = 0.0
    isletme: float = 0.0
    diger: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    gunduz: float = 0.0
    gece: float = 0.0
    brut: float = 0.0

    @property
    def toplam(self) -> float:
        return self.gunduz + self.gece


def puantaj(db, yil: int, ay: int) -> list[Puantaj]:
    ilk, son = ay_araligi(yil, ay)
    pazartesi = ilk - timedelta(days=ilk.weekday())
    tatiller = tatil_gunleri(db, pazartesi, son + timedelta(days=7))
    katsayi = db.ayar("aylik_katsayi")
    gunduz_ucret = db.ayar("ek_ders_gosterge_gunduz") * katsayi
    gece_ucret = db.ayar("ek_ders_gosterge_gece") * katsayi

    prog: dict[int, Counter] = defaultdict(Counter)
    for r in db.q("""SELECT dog.ogretmen_id, ph.gun, COUNT(DISTINCT ph.saat) AS c FROM program_hucreleri ph
                     JOIN ders_ogretmenleri dog ON dog.atama_id = ph.atama_id
                     GROUP BY dog.ogretmen_id, ph.gun"""):
        prog[r["ogretmen_id"]][r["gun"]] = r["c"]
    koord: dict[int, list] = defaultdict(list)
    for r in db.q("SELECT * FROM koordinator_gorevleri"):
        koord[r["ogretmen_id"]].append((r["gun"], r["haftalik_saat"], tarih(r["baslangic"]), tarih(r["bitis"])))
    elle: dict[int, list] = defaultdict(list)
    for r in db.q("SELECT * FROM ek_ders_kayitlari WHERE tarih BETWEEN ? AND ?", (ilk.isoformat(), son.isoformat())):
        elle[r["ogretmen_id"]].append((tarih(r["tarih"]), r["tur"], float(r["saat"] or 0)))

    out = []
    for o in db.q("SELECT * FROM ogretmenler WHERE aktif = 1 ORDER BY ad, soyad"):
        tid = o["id"]
        p = Puantaj(tid, f"{o['ad']} {o['soyad']}", o["unvan"] or "", aylik_karsilik(db, o), azami_ek_ders(db, o))
        hafta = pazartesi
        while hafta <= son:
            gunler = [hafta + timedelta(days=i) for i in range(5)]
            ders_h = [prog[tid].get(i + 1, 0) for i in range(5)]
            koord_h = [sum(s for g, s, b, e in koord[tid]
                           if g == i + 1 and (b is None or d >= b) and (e is None or d <= e))
                       for i, d in enumerate(gunler)]
            ek_ders_h, ek_isl_h = list(ders_h), list(koord_h)
            kalan = p.aylik_karsilik
            for liste in (ek_ders_h, ek_isl_h):
                for i in range(5):
                    k = min(liste[i], kalan)
                    liste[i] -= k
                    kalan -= k
            kullanilan = 0.0
            for i, d in enumerate(gunler):
                ek_ders, ek_isl = ek_ders_h[i], ek_isl_h[i]
                if d in tatiller:
                    ek_ders = ek_isl = 0
                ek_ders = min(ek_ders, max(0, p.azami - kullanilan))
                kullanilan += ek_ders
                ek_isl = min(ek_isl, max(0, p.azami - kullanilan))
                kullanilan += ek_isl
                if d.month == ay and d.year == yil:
                    p.gunluk[d.day] = p.gunluk.get(d.day, 0) + ek_ders + ek_isl
                    p.ders += ek_ders
                    p.isletme += ek_isl
            hafta += timedelta(days=7)
        p.gunduz = p.ders + p.isletme
        for d, tur, saat in elle[tid]:
            p.gunluk[d.day] = p.gunluk.get(d.day, 0) + saat
            p.diger[tur] += saat
            if tur == "Gece":
                p.gece += saat
            else:
                p.gunduz += saat
        p.brut = yuvarla(p.gunduz * gunduz_ucret + p.gece * gece_ucret)
        if p.toplam or prog[tid] or koord[tid]:
            out.append(p)
    return out
