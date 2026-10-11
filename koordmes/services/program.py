"""Haftalık ders programı ve atölye/laboratuvar yerleştirme.

Kısıtlar (kesin):
  * Bir sınıf, bir öğretmen ve bir atölye aynı saatte tek derste olabilir.
  * Sınıf yalnızca okul günlerinde (işletme günleri hariç) ders alır.
  * Öğretmenin müsait olmadığı saatlere ders konmaz.
  * Atölye gerektiren dersler ilgili alanın atölye/laboratuvarına yerleşir; sınıf mevcuduna yeten mekân önce denenir.
  * İki öğretmenli (grup) derslerde iki öğretmen aynı saatte boş olmalı; sınıf iki gruba bölünüyorsa (2. atölye
    girilmiş ya da mevcut tek atölyeye sığmıyorsa) iki ayrı mekân aynı saatte ayrılır.
  * Birleştirilmiş dersler (aynı birleştirme anahtarı: ör. 9-A ve 9-B beden eğitimi) tüm sınıf ve öğretmenleriyle
    aynı saate yerleşir.
  * Blok dersler (ör. 4 saatlik atölye) bölünmeden ardışık saatlere yerleşir.
  * Öğretmen günlük azami ders saati (parametre) aşılmaz; koordinatörlük günleri boş bırakılır (parametre;
    yerleşmeyen ders kalırsa bu kural gevşetilir ve bildirilir).
  * Kilitli hücreler korunur.
  * Sınıfın ders konmayacak saatleri boş kalır; blok dersler öğle arasında bölünmez (parametre).
  * Aynı güne gelmemesi istenen ders grupları ve (parametreyle) bir öğretmenin aynı sınıftaki farklı dersleri
    ayrı günlere yerleşir; rehberlik dersleri bu kuraldan muaftır. Yerleşmeyen ders kalırsa bu kurallar gevşetilir
    ve bildirilir.
Tercihler (esnek): aynı dersin blokları farklı günlere, sınıf programında boşluk
olmaması, öğretmen günlerinin toplu olması (koordinatörlük için boş gün kalması).
"""
from __future__ import annotations

import math
import random
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, replace
from datetime import date

from .utils import gunler_listesi


@dataclass
class Atama:
    id: int
    sinif_id: int
    ogretmen_id: int | None
    saat: int
    blok: int
    odalar: list[int | None]
    etiket: str = ""
    ogretmen2_id: int | None = None
    odalar2: list[int] = field(default_factory=list)  # doluysa sınıfın ikinci grubu için ayrı mekân gerekir
    uyeler: list[int] = field(default_factory=list)  # birleştirilmiş derste birlikte yerleşen atamalar
    ek_siniflar: list[int] = field(default_factory=list)
    ek_ogretmenler: list[int] = field(default_factory=list)
    ders_id: int | None = None

    def __post_init__(self):
        self.siniflar = tuple(dict.fromkeys([self.sinif_id, *self.ek_siniflar]))
        self.ogretmenler = tuple(t for t in dict.fromkeys([self.ogretmen_id, self.ogretmen2_id,
                                                           *self.ek_ogretmenler]) if t)
        self.kimlikler = tuple(self.uyeler or [self.id])


@dataclass(eq=False)
class Blok:
    atama: Atama
    uzunluk: int
    yer: tuple[int, int, int | None, int | None] | None = None  # (gun, baslangic_saati, atolye, atolye2)
    kilitli: bool = False


@dataclass
class CozumSonucu:
    hucreler: list[tuple[int, int, int, int | None, int | None, bool]]  # atama, gun, saat, atolye, atolye2, kilitli
    yerlesmeyen: list[tuple[Atama, int]] = field(default_factory=list)
    sure: float = 0.0
    iterasyon: int = 0
    notlar: list[str] = field(default_factory=list)


def bloklara_bol(saat: int, blok: int) -> list[int]:
    blok = max(1, blok or 1)
    if saat <= 0:
        return []
    parcalar = [blok] * (saat // blok)
    if saat % blok:
        parcalar.append(saat % blok)
    return parcalar


def musaitlik_coz(metin: str | None, saat_sayisi: int) -> set[tuple[int, int]]:
    """'1-*,3-5,3-6,*-1' biçimini {(gun, saat)} kümesine çevirir ('*-1': her günün 1. saati)."""
    out: set[tuple[int, int]] = set()
    for parca in (metin or "").replace(";", ",").split(","):
        parca = parca.strip()
        if "-" not in parca:
            continue
        g, s = (x.strip() for x in parca.split("-", 1))
        if g == "*":
            gunler = range(1, 6)
        elif g.isdigit():
            gunler = [int(g)]
        else:
            continue
        if s == "*":
            out |= {(gi, h) for gi in gunler for h in range(1, saat_sayisi + 1)}
        elif s.isdigit():
            out |= {(gi, int(s)) for gi in gunler}
    return out


def musaitlik_metni(kapali: set[tuple[int, int]], saat_sayisi: int) -> str:
    """{(gun, saat)} kümesini '1-*,3-5' biçimine çevirir (tüm gün kapalıysa '*')."""
    parca = []
    for g in sorted({g for g, _ in kapali}):
        saatler = sorted(h for gg, h in kapali if gg == g)
        if set(range(1, saat_sayisi + 1)) <= set(saatler):
            parca.append(f"{g}-*")
        else:
            parca += [f"{g}-{h}" for h in saatler]
    return ",".join(parca)


class Cozucu:
    def __init__(self, atamalar: list[Atama], gun_sayisi: int, saat_sayisi: int,
                 sinif_gunleri: dict[int, list[int]], ogretmen_kapali: dict[int, set[tuple[int, int]]],
                 kilitli: list[tuple] | None = None, seed: int | None = None, gunluk_azami: int = 0,
                 sinif_kapali: dict[int, set[tuple[int, int]]] | None = None,
                 ayni_gun_degil: dict[int, set[int]] | None = None, ogle_arasi: int = 0):
        self.S = saat_sayisi
        self.G = gun_sayisi
        self.azami = gunluk_azami or 0
        self.ogle = ogle_arasi if 0 < (ogle_arasi or 0) < saat_sayisi else 0
        self.ayni_gun = ayni_gun_degil or {}
        self.rng = random.Random(seed)
        tum = list(range(1, gun_sayisi + 1))
        gunler = {k: {g for g in v if 1 <= g <= gun_sayisi} for k, v in sinif_gunleri.items()}
        self.gunler = {a.id: [g for g in tum if all(g in gunler.get(c, set(tum)) for c in a.siniflar)]
                       for a in atamalar}
        sinif_kapali = sinif_kapali or {}
        self.kapali = {a.id: set().union(*(ogretmen_kapali.get(t, set()) for t in a.ogretmenler),
                                         *(sinif_kapali.get(c, set()) for c in a.siniflar))
                       for a in atamalar}
        self.atama_map = {a.id: a for a in atamalar}
        uye_map: dict[int, Atama] = {}
        for a in atamalar:
            for k in a.kimlikler:
                if k not in uye_map or len(a.kimlikler) > 1:
                    uye_map[k] = a
        self.sinif_occ: dict[tuple[int, int, int], Blok] = {}
        self.ogr_occ: dict[tuple[int, int, int], Blok] = {}
        self.oda_occ: dict[tuple[int, int, int], Blok] = {}
        self.ogr_gun: dict[tuple[int, int], int] = defaultdict(int)
        self.atama_gun: dict[tuple[int, int], int] = defaultdict(int)
        self.gun_dolu: dict[tuple[int, int], int] = defaultdict(int)  # kilitliler dahil (atama, gün) blok sayısı
        self.bloklar: list[Blok] = []
        self.blok_sayisi: dict[int, int] = {}

        kilitli_sayac: dict[int, int] = defaultdict(int)
        gorulen: set[tuple[int, int, int]] = set()
        for k in kilitli or []:
            atama_id, g, h, oda = k[:4]
            oda2 = k[4] if len(k) > 4 else None
            a = uye_map.get(atama_id)
            if not a or (a.id, g, h) in gorulen:
                continue
            gorulen.add((a.id, g, h))
            b = Blok(a, 1, kilitli=True)
            self.bloklar.append(b)
            self._yerlestir(b, g, h, oda, oda2, gun_say=False)
            kilitli_sayac[a.id] += 1

        for a in atamalar:
            kalan = max(0, a.saat - kilitli_sayac[a.id])
            parcalar = bloklara_bol(kalan, a.blok)
            self.blok_sayisi[a.id] = len(parcalar)
            for L in parcalar:
                self.bloklar.append(Blok(a, L))

    # --- doluluk işlemleri ---
    def _yerlestir(self, b: Blok, g: int, s: int, oda: int | None, oda2: int | None = None,
                   gun_say: bool = True) -> None:
        a = b.atama
        for h in range(s, s + b.uzunluk):
            for c in a.siniflar:
                self.sinif_occ[(c, g, h)] = b
            for t in a.ogretmenler:
                self.ogr_occ[(t, g, h)] = b
            if oda:
                self.oda_occ[(oda, g, h)] = b
            if oda2:
                self.oda_occ[(oda2, g, h)] = b
        for t in a.ogretmenler:
            self.ogr_gun[(t, g)] += b.uzunluk
        b.yer = (g, s, oda, oda2)
        self.gun_dolu[(a.id, g)] += 1
        if gun_say:
            self.atama_gun[(a.id, g)] += 1

    def _kaldir(self, b: Blok) -> None:
        if not b.yer:
            return
        g, s, oda, oda2 = b.yer
        a = b.atama
        for h in range(s, s + b.uzunluk):
            for c in a.siniflar:
                self.sinif_occ.pop((c, g, h), None)
            for t in a.ogretmenler:
                self.ogr_occ.pop((t, g, h), None)
            if oda:
                self.oda_occ.pop((oda, g, h), None)
            if oda2:
                self.oda_occ.pop((oda2, g, h), None)
        for t in a.ogretmenler:
            self.ogr_gun[(t, g)] -= b.uzunluk
        self.atama_gun[(a.id, g)] -= 1
        self.gun_dolu[(a.id, g)] -= 1
        b.yer = None

    def _kesin_ayri_gun(self, a: Atama) -> bool:
        return self.blok_sayisi.get(a.id, 0) <= len(self.gunler.get(a.id, []))

    def _uygun_saat(self, a: Atama, g: int, s: int, L: int) -> bool:
        if self.ogle and s <= self.ogle < s + L - 1:
            return False
        kapali = self.kapali.get(a.id)
        return not kapali or all((g, h) not in kapali for h in range(s, s + L))

    def _ayni_gun_dolu(self, a: Atama, g: int) -> bool:
        return any(self.gun_dolu[(x, g)] > 0 for x in self.ayni_gun.get(a.id, ()))

    def _azami_asilir(self, a: Atama, g: int, L: int) -> bool:
        return bool(self.azami) and any(self.ogr_gun[(t, g)] + L > self.azami for t in a.ogretmenler)

    def _bos_oda(self, odalar, g: int, s: int, L: int, haric: int | None = None):
        """(bulundu, oda): listedeki ilk boş mekân; liste [None] ise mekân gerekmez."""
        for oda in odalar:
            if oda is None:
                return True, None
            if oda != haric and all((oda, g, h) not in self.oda_occ for h in range(s, s + L)):
                return True, oda
        return False, None

    def _secenekler(self, b: Blok):
        a, L = b.atama, b.uzunluk
        kesin = self._kesin_ayri_gun(a)
        for g in self.gunler.get(a.id, []):
            if kesin and self.atama_gun[(a.id, g)] > 0:
                continue
            if self._azami_asilir(a, g, L) or self._ayni_gun_dolu(a, g):
                continue
            for s in range(1, self.S - L + 2):
                if not self._uygun_saat(a, g, s, L):
                    continue
                saatler = range(s, s + L)
                if any((c, g, h) in self.sinif_occ for c in a.siniflar for h in saatler):
                    continue
                if any((t, g, h) in self.ogr_occ for t in a.ogretmenler for h in saatler):
                    continue
                var, oda = self._bos_oda(a.odalar, g, s, L)
                if not var:
                    continue
                oda2 = None
                if a.odalar2:
                    var, oda2 = self._bos_oda(a.odalar2, g, s, L, haric=oda)
                    if not var or oda2 is None:
                        continue
                yield g, s, oda, oda2

    def _puan(self, b: Blok, g: int, s: int) -> float:
        a, L = b.atama, b.uzunluk
        sinif_yuk = sum(1 for h in range(1, self.S + 1) if (a.sinif_id, g, h) in self.sinif_occ)
        puan = sinif_yuk * 1.0
        for t in a.ogretmenler:
            puan += 0.0 if self.ogr_gun[(t, g)] else 2.5
        komsu = (a.sinif_id, g, s - 1) in self.sinif_occ or (a.sinif_id, g, s + L) in self.sinif_occ
        if sinif_yuk:
            puan += -1.5 if komsu else 2.0
        bos_once = sum(1 for h in range(1, s) if (a.sinif_id, g, h) not in self.sinif_occ)
        puan += 0.8 * bos_once + 0.1 * s
        if self.atama_gun[(a.id, g)] > 0:
            puan += 5.0
        return puan + self.rng.random() * 0.3

    def _oda_catismasi(self, odalar, g: int, s: int, L: int, haric: int | None = None):
        en_iyi_oda, en_iyi_cat = None, None
        for oda in odalar:
            if oda is not None and oda == haric:
                continue
            oc: set[Blok] = set()
            if oda:
                for h in range(s, s + L):
                    x = self.oda_occ.get((oda, g, h))
                    if x:
                        oc.add(x)
            if en_iyi_cat is None or len(oc) < len(en_iyi_cat):
                en_iyi_oda, en_iyi_cat = oda, oc
        return en_iyi_oda, en_iyi_cat

    def _catisma_secenekleri(self, b: Blok, tahliye_sayaci: dict):
        a, L = b.atama, b.uzunluk
        for g in self.gunler.get(a.id, []):
            if self._azami_asilir(a, g, L):
                continue
            gun_cat: set[Blok] = set()
            if self._kesin_ayri_gun(a):
                gun_cat |= {x for x in self.bloklar if x.atama.id == a.id and x.yer and x.yer[0] == g
                            and not x.kilitli}
            if self._ayni_gun_dolu(a, g):
                diger = self.ayni_gun[a.id]
                gun_cat |= {x for x in self.bloklar if x.atama.id in diger and x.yer and x.yer[0] == g}
            for s in range(1, self.S - L + 2):
                if not self._uygun_saat(a, g, s, L):
                    continue
                cat: set[Blok] = set(gun_cat)
                for h in range(s, s + L):
                    for c in a.siniflar:
                        x = self.sinif_occ.get((c, g, h))
                        if x:
                            cat.add(x)
                    for t in a.ogretmenler:
                        x = self.ogr_occ.get((t, g, h))
                        if x:
                            cat.add(x)
                oda, oc = self._oda_catismasi(a.odalar, g, s, L)
                if oc is None:
                    continue
                cat |= oc
                oda2 = None
                if a.odalar2:
                    oda2, oc2 = self._oda_catismasi(a.odalar2, g, s, L, haric=oda)
                    if oda2 is None:
                        continue
                    cat |= oc2
                if any(x.kilitli for x in cat):
                    continue
                maliyet = sum(1 + 0.5 * tahliye_sayaci[id(x)] for x in cat) + self.rng.random() * 0.5
                yield maliyet, g, s, oda, oda2, cat

    def coz(self, sure_limit: float = 20.0, max_iter: int = 200_000) -> CozumSonucu:
        t0 = time.time()
        bekleyen = [b for b in self.bloklar if not b.kilitli]
        if not bekleyen:
            return self._sonuc([], t0, 0)
        alan = {id(b): sum(1 for _ in self._secenekler(b)) for b in bekleyen}
        bekleyen.sort(key=lambda b: (alan[id(b)], -b.uzunluk * len(b.atama.siniflar)))
        kuyruk = deque(bekleyen)
        basarisiz: list[Blok] = []
        tahliye: dict[int, int] = defaultdict(int)
        en_iyi = len(kuyruk) + 1
        en_iyi_yerler: dict[int, tuple] = {}
        it = 0
        while kuyruk and it < max_iter and time.time() - t0 < sure_limit:
            it += 1
            b = kuyruk.popleft()
            secenekler = list(self._secenekler(b))
            if secenekler:
                g, s, oda, oda2 = min(secenekler, key=lambda x: self._puan(b, x[0], x[1]))
                self._yerlestir(b, g, s, oda, oda2)
            else:
                cats = list(self._catisma_secenekleri(b, tahliye))
                if not cats:
                    basarisiz.append(b)
                    continue
                _, g, s, oda, oda2, cat = min(cats, key=lambda x: x[0])
                for x in cat:
                    self._kaldir(x)
                    tahliye[id(x)] += 1
                    kuyruk.append(x)
                self._yerlestir(b, g, s, oda, oda2)
            kalan = len(kuyruk) + len(basarisiz)
            if kalan < en_iyi:
                en_iyi = kalan
                en_iyi_yerler = {id(x): x.yer for x in self.bloklar if not x.kilitli}

        if kuyruk and en_iyi_yerler:
            for x in self.bloklar:
                if not x.kilitli and x.yer:
                    self._kaldir(x)
            for x in self.bloklar:
                yer = en_iyi_yerler.get(id(x))
                if not x.kilitli and yer:
                    self._yerlestir(x, *yer)
        yerlesmeyen = [x for x in self.bloklar if not x.kilitli and not x.yer]
        return self._sonuc(yerlesmeyen, t0, it)

    def _sonuc(self, yerlesmeyen: list[Blok], t0: float, it: int) -> CozumSonucu:
        hucreler = []
        for b in self.bloklar:
            if b.yer:
                g, s, oda, oda2 = b.yer
                for h in range(s, s + b.uzunluk):
                    for k in b.atama.kimlikler:
                        hucreler.append((k, g, h, oda, oda2, b.kilitli))
        return CozumSonucu(hucreler, [(b.atama, b.uzunluk) for b in yerlesmeyen], time.time() - t0, it)


# ----------------------------------------------------------------- DB katmanı

def sinif_mevcutlari(db) -> dict[int, int]:
    return {r["sinif_id"]: r["n"] for r in db.q("""SELECT sinif_id, COUNT(*) n FROM ogrenciler
                                                  WHERE aktif = 1 AND sinif_id IS NOT NULL GROUP BY sinif_id""")}


def _atama_satirlari(db):
    return db.q("""SELECT da.*, d.ad AS ders, d.blok AS ders_blok, d.atolye_gerekli, d.alan_id AS ders_alan,
                          s.ad AS sinif, s.alan_id AS sinif_alan
                   FROM ders_atamalari da JOIN dersler d ON d.id = da.ders_id
                   JOIN siniflar s ON s.id = da.sinif_id ORDER BY da.id""")


def atamalari_oku(db) -> list[Atama]:
    """Ders atamalarını çözücü girdisine çevirir: mekân adayları (kapasiteye göre sıralı), grup dersinde ikinci
    mekân, birleştirilmiş derslerin tek blokta toplanması."""
    atolyeler = db.q("SELECT id, alan_id, kapasite FROM atolyeler ORDER BY id")
    kap = {a["id"]: int(a["kapasite"] or 0) for a in atolyeler}
    mevcut = sinif_mevcutlari(db) if db.ayar("program_kapasite_denetimi") else {}
    tekil: list[tuple[Atama, str]] = []
    for r in _atama_satirlari(db):
        n = mevcut.get(r["sinif_id"], 0)
        havuz: list[int] = []
        if r["atolye_gerekli"] and not r["atolye_id"]:
            alan = r["ders_alan"] or r["sinif_alan"]
            havuz = [a["id"] for a in atolyeler if alan and a["alan_id"] == alan] or [a["id"] for a in atolyeler]
        bolunur = bool(r["atolye2_id"] or (r["ogretmen2_id"] and havuz and n and len(havuz) >= 2
                                           and max(kap[i] for i in havuz) < n))
        gerek = math.ceil(n / 2) if bolunur else n

        def sirala(odalar: list[int]) -> list[int]:
            if not n:
                return odalar
            yeten = sorted((i for i in odalar if kap[i] >= gerek), key=lambda i: kap[i])
            return yeten + sorted((i for i in odalar if kap[i] < gerek), key=lambda i: -kap[i])

        if r["atolye_id"]:
            odalar: list[int | None] = [r["atolye_id"]]
        elif havuz:
            odalar = list(sirala(havuz))
        else:
            odalar = [None]
        odalar2 = [r["atolye2_id"]] if r["atolye2_id"] else (sirala(havuz) if bolunur else [])
        a = Atama(r["id"], r["sinif_id"], r["ogretmen_id"], int(r["haftalik_saat"] or 0),
                  int(r["blok"] or r["ders_blok"] or 1), odalar, f"{r['sinif']} - {r['ders']}",
                  r["ogretmen2_id"], odalar2, ders_id=r["ders_id"])
        tekil.append((a, (r["birlestirme"] or "").strip().casefold()))

    gruplar: dict[str, list[Atama]] = defaultdict(list)
    out: list[Atama] = []
    for a, anahtar in tekil:
        (gruplar[anahtar] if anahtar else out).append(a)
    for lst in gruplar.values():
        if len(lst) == 1:
            out.append(lst[0])
            continue
        ana = lst[0]
        ortak = min(a.saat for a in lst)
        mekanli = [a for a in lst if a.odalar != [None]]
        odalar = mekanli[0].odalar if mekanli else [None]
        odalar2 = mekanli[1].odalar if len(mekanli) > 1 else ana.odalar2
        out.append(Atama(-ana.id, ana.sinif_id, ana.ogretmen_id, ortak, ana.blok, odalar,
                         " + ".join(a.etiket for a in lst), ana.ogretmen2_id, [o for o in odalar2 if o],
                         [a.id for a in lst], [a.sinif_id for a in lst[1:]],
                         [t for a in lst[1:] for t in (a.ogretmen_id, a.ogretmen2_id) if t], ana.ders_id))
        out += [replace(a, saat=a.saat - ortak) for a in lst if a.saat > ortak]
    return out


def _koordinatorluk_gunleri(db, S: int) -> dict[int, set[tuple[int, int]]]:
    out: dict[int, set[tuple[int, int]]] = defaultdict(set)
    bugun = date.today().isoformat()
    for r in db.q("""SELECT ogretmen_id, gun FROM koordinator_gorevleri
                     WHERE bitis IS NULL OR bitis = '' OR bitis >= ?""", (bugun,)):
        out[r["ogretmen_id"]] |= {(r["gun"], h) for h in range(1, S + 1)}
    return out


def ders_gruplari(db) -> list[set[int]]:
    """Etkin 'aynı güne gelmesin' ders grupları (ders kimlikleri)."""
    out = []
    for r in db.q("SELECT dersler FROM program_ders_gruplari WHERE aktif = 1"):
        g = {int(x) for x in str(r["dersler"] or "").split(",") if x.strip().isdigit()}
        if len(g) > 1:
            out.append(g)
    return out


def rehberlik_dersleri(db) -> set[int]:
    from .aktarim import norm
    return {r["id"] for r in db.q("SELECT id, ad FROM dersler") if "rehberlik" in norm(r["ad"])}


def gun_kurallari(atamalar: list[Atama], gruplar: list[set[int]], ogretmen_ayni_gun: bool,
                  muaf: set[int]) -> dict[int, set[int]]:
    """Aynı güne yerleşmemesi gereken atamalar: aynı sınıfta, farklı derslerden ve ya aynı ders grubunda ya da
    (kural açıksa) aynı öğretmenin (muaf dersler hariç) dersleri."""
    sinifta: dict[int, list[Atama]] = defaultdict(list)
    for a in atamalar:
        for c in a.siniflar:
            sinifta[c].append(a)
    out: dict[int, set[int]] = defaultdict(set)
    for lst in sinifta.values():
        for i, a in enumerate(lst):
            for b in lst[i + 1:]:
                if a.id == b.id or a.ders_id is None or b.ders_id is None or a.ders_id == b.ders_id:
                    continue
                kural = any(a.ders_id in g and b.ders_id in g for g in gruplar)
                if not kural and ogretmen_ayni_gun and a.ders_id not in muaf and b.ders_id not in muaf:
                    kural = bool(set(a.ogretmenler) & set(b.ogretmenler))
                if kural:
                    out[a.id].add(b.id)
                    out[b.id].add(a.id)
    return dict(out)


def sinif_kapali_saatleri(db, S: int) -> dict[int, set[tuple[int, int]]]:
    return {r["id"]: k for r in db.q("SELECT id, kapali_saatler FROM siniflar")
            if (k := musaitlik_coz(r["kapali_saatler"], S))}


def programi_olustur(db, sure_limit: float | None = None, seed: int | None = None,
                     kilitlileri_koru: bool = True) -> CozumSonucu:
    S = db.ayar("gunluk_ders_saati")
    sure_limit = sure_limit if sure_limit is not None else db.ayar("program_sure_limit_sn")
    atamalar = atamalari_oku(db)
    sinif_gunleri = {r["id"]: gunler_listesi(r["okul_gunleri"]) or [1, 2, 3, 4, 5]
                     for r in db.q("SELECT id, okul_gunleri FROM siniflar")}
    kapali = {r["id"]: musaitlik_coz(r["musait_olmayan"], S)
              for r in db.q("SELECT id, musait_olmayan FROM ogretmenler")}
    kilitli = []
    if kilitlileri_koru:
        kilitli = [(r["atama_id"], r["gun"], r["saat"], r["atolye_id"], r["atolye2_id"])
                   for r in db.q("SELECT * FROM program_hucreleri WHERE kilitli = 1")]
    azami = db.ayar("program_ogretmen_gunluk_azami")
    sinif_kapali = sinif_kapali_saatleri(db, S)
    ogle = db.ayar("program_ogle_arasi")
    kurallar = gun_kurallari(atamalar, ders_gruplari(db), db.ayar("program_ogretmen_ayni_gun"),
                             rehberlik_dersleri(db))

    def coz(kap, ayni_gun):
        return Cozucu(atamalar, 5, S, sinif_gunleri, kap, kilitli, seed, azami, sinif_kapali, ayni_gun,
                      ogle).coz(sure_limit)

    koord = _koordinatorluk_gunleri(db, S) if db.ayar("program_koord_gunu_bos") else {}
    tum_kapali = {t: kapali.get(t, set()) | koord.get(t, set()) for t in set(kapali) | set(koord)}
    sonuc = coz(tum_kapali, kurallar)
    if kurallar and sonuc.yerlesmeyen:
        gevsek = coz(tum_kapali, {})
        if len(gevsek.yerlesmeyen) < len(sonuc.yerlesmeyen):
            gevsek.notlar.append("Aynı güne gelmemesi istenen dersler bu kurala uyularak tümüyle yerleşmedi; kural "
                                 "gerektiği kadar gevşetildi ('Kontrol Et' kurala uymayan günleri listeler).")
            sonuc, kurallar = gevsek, {}
    if koord and sonuc.yerlesmeyen:
        ikinci = coz(kapali, kurallar)
        if len(ikinci.yerlesmeyen) < len(sonuc.yerlesmeyen):
            ikinci.notlar = sonuc.notlar + ["Koordinatörlük günleri boş bırakılınca bazı dersler yerleşmedi; bu "
                                            "günler gerektiği kadar derse açıldı (Veri Denetimi çakışan "
                                            "öğretmenleri listeler)."]
            sonuc = ikinci
    with db.conn:
        db.conn.execute("DELETE FROM program_hucreleri" + (" WHERE kilitli = 0" if kilitlileri_koru else ""))
        db.conn.executemany(
            "INSERT INTO program_hucreleri (atama_id, gun, saat, atolye_id, atolye2_id, kilitli) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            [(a, g, h, o, o2) for a, g, h, o, o2, k in sonuc.hucreler if not k])
    return sonuc


def program_tablosu(db, tip: str, kimlik: int) -> dict[tuple[int, int], dict]:
    """tip: 'sinif' | 'ogretmen' | 'atolye'. {(gun, saat): hücre bilgisi} döndürür. Birleştirilmiş derslerde
    aynı saatteki satırlar tek hücrede toplanır (sınıflar '9-A + 9-B'; 'ids' tüm hücre kimlikleri)."""
    kosul = {"sinif": "da.sinif_id = ?", "ogretmen": "(da.ogretmen_id = ? OR da.ogretmen2_id = ?)",
             "atolye": "(ph.atolye_id = ? OR ph.atolye2_id = ?)"}[tip]
    rows = db.q(f"""SELECT ph.id, ph.gun, ph.saat, ph.kilitli, ph.atama_id, d.ad AS ders, d.kisa_ad,
                           s.ad AS sinif, o.ad AS ogr_ad, o.soyad AS ogr_soyad, a.ad AS atolye,
                           o2.ad || ' ' || o2.soyad AS ogretmen2, a2.ad AS atolye2, da.birlestirme
                    FROM program_hucreleri ph JOIN ders_atamalari da ON da.id = ph.atama_id
                    JOIN dersler d ON d.id = da.ders_id JOIN siniflar s ON s.id = da.sinif_id
                    LEFT JOIN ogretmenler o ON o.id = da.ogretmen_id
                    LEFT JOIN ogretmenler o2 ON o2.id = da.ogretmen2_id
                    LEFT JOIN atolyeler a ON a.id = ph.atolye_id
                    LEFT JOIN atolyeler a2 ON a2.id = ph.atolye2_id
                    WHERE {kosul} ORDER BY s.ad""", (kimlik,) * kosul.count("?"))
    out: dict[tuple[int, int], dict] = {}
    for r in rows:
        k = (r["gun"], r["saat"])
        if k in out:
            x = out[k]
            x["ids"].append(r["id"])
            if r["sinif"] not in x["sinif"].split(" + "):
                x["sinif"] += f" + {r['sinif']}"
            continue
        out[k] = {**dict(r), "ids": [r["id"]]}
    return out


def catismalar(db) -> list[str]:
    """Aynı birleştirme grubundaki dersler birlikte yapıldığı için çakışma sayılmaz."""
    grup = "COALESCE(NULLIF(LOWER(TRIM(da.birlestirme)), ''), 'a' || da.id)"
    out = []
    for etiket, sql in [
        ("Sınıf", """SELECT s.ad AS ad, ph.gun, ph.saat, COUNT(*) c FROM program_hucreleri ph
                     JOIN ders_atamalari da ON da.id = ph.atama_id JOIN siniflar s ON s.id = da.sinif_id
                     GROUP BY da.sinif_id, ph.gun, ph.saat HAVING c > 1"""),
        ("Öğretmen", f"""SELECT o.ad || ' ' || o.soyad AS ad, ph.gun, ph.saat, COUNT(DISTINCT {grup}) c
                         FROM program_hucreleri ph JOIN ders_atamalari da ON da.id = ph.atama_id
                         JOIN ders_ogretmenleri dog ON dog.atama_id = da.id
                         JOIN ogretmenler o ON o.id = dog.ogretmen_id
                         GROUP BY dog.ogretmen_id, ph.gun, ph.saat HAVING c > 1"""),
        ("Atölye", f"""SELECT a.ad AS ad, x.gun, x.saat, COUNT(DISTINCT x.grup) c FROM (
                           SELECT ph.atolye_id AS oda, ph.gun, ph.saat, {grup} AS grup FROM program_hucreleri ph
                           JOIN ders_atamalari da ON da.id = ph.atama_id WHERE ph.atolye_id IS NOT NULL
                           UNION ALL
                           SELECT ph.atolye2_id, ph.gun, ph.saat, {grup} FROM program_hucreleri ph
                           JOIN ders_atamalari da ON da.id = ph.atama_id WHERE ph.atolye2_id IS NOT NULL) x
                       JOIN atolyeler a ON a.id = x.oda
                       GROUP BY x.oda, x.gun, x.saat HAVING c > 1"""),
    ]:
        for r in db.q(sql):
            out.append(f"{etiket} çakışması: {r['ad']} - {r['gun']}. gün {r['saat']}. saat ({r['c']} ders)")
    return out


def kural_ihlalleri(db) -> list[str]:
    """Programın sınıf kapalı saatleri, öğle arası ve aynı gün kurallarına uymayan yerleri."""
    S = db.ayar("gunluk_ders_saati")
    hucreler = db.q("""SELECT ph.atama_id, ph.gun, ph.saat, da.sinif_id, s.ad AS sinif, d.ad AS ders,
                              COALESCE(da.blok, d.blok, 1) AS blok
                       FROM program_hucreleri ph JOIN ders_atamalari da ON da.id = ph.atama_id
                       JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id""")
    out = []
    kapali = sinif_kapali_saatleri(db, S)
    for h in hucreler:
        if (h["gun"], h["saat"]) in kapali.get(h["sinif_id"], set()):
            out.append(f"Sınıfın kapalı saati: {h['sinif']} - {h['ders']} {h['gun']}. gün {h['saat']}. saat")
    ogle = db.ayar("program_ogle_arasi")
    if 0 < ogle < S:
        yer = {(h["atama_id"], h["gun"], h["saat"]) for h in hucreler}
        for h in hucreler:
            if h["saat"] == ogle and (h["blok"] or 1) > 1 and (h["atama_id"], h["gun"], ogle + 1) in yer:
                out.append(f"Öğle arasında bölünen blok: {h['sinif']} - {h['ders']} {h['gun']}. gün")
    atamalar = atamalari_oku(db)
    kurallar = gun_kurallari(atamalar, ders_gruplari(db), db.ayar("program_ogretmen_ayni_gun"),
                             rehberlik_dersleri(db))
    if kurallar:
        gunler: dict[int, set[int]] = defaultdict(set)
        for h in hucreler:
            gunler[h["atama_id"]].add(h["gun"])
        harita = {a.id: a for a in atamalar}
        atama_gunleri = {a.id: set().union(*(gunler.get(k, set()) for k in a.kimlikler)) for a in atamalar}
        for a_id, digerleri in kurallar.items():
            for b_id in digerleri:
                if a_id < b_id:
                    ortak = atama_gunleri[a_id] & atama_gunleri[b_id]
                    if ortak:
                        out.append(f"Aynı güne gelmemeli: {harita[a_id].etiket} / {harita[b_id].etiket} "
                                   f"({', '.join(f'{g}. gün' for g in sorted(ortak))})")
    return out


def eksik_saatler(db) -> list[tuple[str, int, int]]:
    """(atama etiketi, gereken saat, yerleşen saat) - eksik kalanlar."""
    rows = db.q("""SELECT s.ad || ' - ' || d.ad AS etiket, da.haftalik_saat AS gereken,
                          (SELECT COUNT(*) FROM program_hucreleri ph WHERE ph.atama_id = da.id) AS yerlesen
                   FROM ders_atamalari da JOIN dersler d ON d.id = da.ders_id JOIN siniflar s ON s.id = da.sinif_id
                   ORDER BY s.ad, d.ad""")
    return [(r["etiket"], r["gereken"], r["yerlesen"]) for r in rows if r["yerlesen"] < r["gereken"]]


# ----------------------------------------------------------------- ön denetim

@dataclass
class OnDenetimBulgusu:
    seviye: str  # Kritik | Uyarı | Bilgi
    konu: str
    mesaj: str


def on_denetim(db) -> list[OnDenetimBulgusu]:
    """Program oluşturulmadan önce çözümü imkânsız kılan veya zorlaştıran durumları bulur."""
    S = db.ayar("gunluk_ders_saati")
    azami = db.ayar("program_ogretmen_gunluk_azami")
    out: list[OnDenetimBulgusu] = []
    siniflar = {r["id"]: r for r in db.q("SELECT id, ad, okul_gunleri FROM siniflar")}
    gun_sayisi = {k: len(gunler_listesi(r["okul_gunleri"]) or [1, 2, 3, 4, 5]) for k, r in siniflar.items()}
    rows = _atama_satirlari(db)
    if not rows:
        return [OnDenetimBulgusu("Kritik", "Ders dağılımı", "Ders dağılımı boş; önce sınıf-ders-öğretmen "
                                 "atamalarını girin veya belgeden yükleyin.")]

    sinif_yuk: dict[int, int] = defaultdict(int)
    gorulen_grup: set[str] = set()
    ogr_yuk: dict[int, int] = defaultdict(int)
    for r in rows:
        sinif_yuk[r["sinif_id"]] += r["haftalik_saat"] or 0
        g = (r["birlestirme"] or "").strip().casefold()
        if g and g in gorulen_grup:
            continue
        if g:
            gorulen_grup.add(g)
        for t in {r["ogretmen_id"], r["ogretmen2_id"]} - {None}:
            ogr_yuk[t] += r["haftalik_saat"] or 0
    sinif_kapali = sinif_kapali_saatleri(db, S)
    for sid, yuk in sinif_yuk.items():
        okul = set(gunler_listesi(siniflar[sid]["okul_gunleri"]) or [1, 2, 3, 4, 5])
        kapasite = gun_sayisi[sid] * S - sum(1 for g, h in sinif_kapali.get(sid, set()) if g in okul and h <= S)
        if yuk > kapasite:
            out.append(OnDenetimBulgusu("Kritik", "Sınıf", f"{siniflar[sid]['ad']}: haftalık {yuk} saat ders, okul "
                                        f"günlerinde yalnızca {kapasite} saat var."))

    ogretmenler = {r["id"]: r for r in db.q("SELECT id, ad, soyad, musait_olmayan FROM ogretmenler")}
    koord = _koordinatorluk_gunleri(db, S) if db.ayar("program_koord_gunu_bos") else {}
    for t, yuk in ogr_yuk.items():
        o = ogretmenler.get(t)
        if not o:
            continue
        kapali = musaitlik_coz(o["musait_olmayan"], S) | koord.get(t, set())
        bos = 5 * S - len({k for k in kapali if 1 <= k[0] <= 5 and 1 <= k[1] <= S})
        if azami:
            bos = min(bos, sum(min(azami, S - sum(1 for h in range(1, S + 1) if (g, h) in kapali))
                               for g in range(1, 6)))
        if yuk > bos:
            out.append(OnDenetimBulgusu("Kritik", "Öğretmen", f"{o['ad']} {o['soyad']}: haftalık {yuk} saat dersi var,"
                                        f" müsaitlik/koordinatörlük/günlük azami sınırlarıyla yalnızca {bos} saat "
                                        "verilebilir."))
        elif yuk > bos * 0.9:
            out.append(OnDenetimBulgusu("Uyarı", "Öğretmen", f"{o['ad']} {o['soyad']}: {yuk}/{bos} saat; neredeyse "
                                        "hiç esneklik yok, yerleştirme zorlaşabilir."))

    atolyeler = {r["id"]: r for r in db.q("SELECT id, ad, alan_id, kapasite FROM atolyeler")}
    mevcut = sinif_mevcutlari(db)
    for a in atamalari_oku(db):
        if not a.saat:
            continue
        n = sum(mevcut.get(c, 0) for c in a.siniflar)
        if a.odalar and a.odalar[0] and n and db.ayar("program_kapasite_denetimi"):
            kap = (atolyeler[a.odalar[0]]["kapasite"] or 0) + (
                max((atolyeler[o]["kapasite"] or 0) for o in a.odalar2) if a.odalar2 else 0)
            if kap and kap < n:
                out.append(OnDenetimBulgusu("Uyarı", "Mekân", f"{a.etiket}: {n} öğrenci, en uygun mekân kapasitesi "
                                            f"{kap}. İkinci öğretmen ve ikinci atölye girerek sınıfı gruplara "
                                            "bölebilirsiniz."))
        if a.blok > S:
            out.append(OnDenetimBulgusu("Kritik", "Blok", f"{a.etiket}: {a.blok} saatlik blok günlük {S} ders saatine "
                                        "sığmaz."))
    oda_yuk: dict[int, int] = defaultdict(int)
    for a in atamalari_oku(db):
        if len(a.odalar) == 1 and a.odalar[0]:
            oda_yuk[a.odalar[0]] += a.saat
        if len(a.odalar2) == 1:
            oda_yuk[a.odalar2[0]] += a.saat
    for oda, yuk in oda_yuk.items():
        if yuk > 5 * S:
            out.append(OnDenetimBulgusu("Kritik", "Mekân", f"{atolyeler[oda]['ad']}: haftalık {yuk} saat ders bu "
                                        f"mekâna bağlı, haftada {5 * S} saat var."))
    for g in gorulen_grup:
        saatler = {r["haftalik_saat"] for r in rows if (r["birlestirme"] or "").strip().casefold() == g}
        if len(saatler) > 1:
            out.append(OnDenetimBulgusu("Bilgi", "Birleştirme", f"'{g}' birleştirmesindeki derslerin haftalık saatleri "
                                        f"farklı ({', '.join(map(str, sorted(saatler)))}); ortak kısım birlikte, "
                                        "kalan saatler ayrı yerleşir."))
    out.sort(key=lambda b: {"Kritik": 0, "Uyarı": 1, "Bilgi": 2}[b.seviye])
    return out
