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
  * Öğretmen günlük azami ders saati (parametre) aşılmaz; koordinatörlük günleri boş bırakılır (parametre).
  * Kilitli hücreler korunur.
  * Sınıfın ders konmayacak saatleri, okul geneli kapalı saatler ve ikili öğretimde sabahçı/öğlenci yarısı boş
    kalır; blok dersler öğle arasında bölünmez (parametre / ders işareti).
  * (Parametreyle) öğretmen aynı gün hem sabah hem öğleden sonra derse girmez.
  * Aynı güne gelmemesi istenen ders grupları ve (parametreyle) bir öğretmenin aynı sınıftaki farklı dersleri
    ayrı günlere yerleşir; rehberlik dersleri bu kuraldan muaftır.
  Kurallar kendiliğinden gevşetilmez; yerleşmeyen her blok için engeller ve öneriler raporlanır. Gevşetme yalnızca
  'program_kural_gevset' parametresi açıksa yapılır, kapalıysa kaç bloğun daha yerleşebileceği bilgi olarak verilir.
Tercihler (esnek): aynı dersin blokları farklı günlere, sınıf ve öğretmen programında boşluk olmaması, öğretmene
boş gün kalması, beden eğitimi/müziğin haftanın ilk ve son gününe, teorik derslerin öğleden önce ve uygulamalı
derslerin öğleden sonra konması (Ortaöğretim Kurumları Yönetmeliği md.12). Yerleştirmeden sonra iyileştirme
turlarında bloklar kesin kurallar bozulmadan daha iyi yerlere taşınır.
"""
from __future__ import annotations

import math
import random
import re
import time
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field, replace
from datetime import date

from ..mevzuat import GUNLER, PARAMETRE_SOZLUK
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
    desen: list[int] = field(default_factory=list)
    ogle_bolunmez: bool = True
    uygulamali: bool = False
    ilk_son_gun: bool = False  # beden eğitimi / müzik

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
class YerlesmemeNedeni:
    etiket: str
    uzunluk: int
    ozet: str
    nedenler: list[str] = field(default_factory=list)
    oneriler: list[str] = field(default_factory=list)

    @property
    def metin(self) -> str:
        satirlar = [f"{self.etiket} ({self.uzunluk} saatlik blok): {self.ozet}"]
        satirlar += [f"  • {n}" for n in self.nedenler]
        satirlar += [f"  → {o}" for o in self.oneriler]
        return "\n".join(satirlar)


@dataclass
class CozumSonucu:
    hucreler: list[tuple[int, int, int, int | None, int | None, bool]]  # atama, gun, saat, atolye, atolye2, kilitli
    yerlesmeyen: list[tuple[Atama, int]] = field(default_factory=list)
    sure: float = 0.0
    iterasyon: int = 0
    notlar: list[str] = field(default_factory=list)
    nedenler: list[YerlesmemeNedeni] = field(default_factory=list)


def ayar_adi(anahtar: str) -> str:
    p = PARAMETRE_SOZLUK.get(anahtar)
    return f"Ayarlar > {p.grup} > “{p.etiket}”" if p else anahtar


# anahtar: (başlık, birim, öneri). Birim 'gün' olanlar gün düzeyinde, 'saat dilimi' olanlar başlangıç saati
# düzeyinde sayılır.
NEDENLER = {
    "okul_gunu": ("Sınıfın okul günü değil (işletme günü)", "gün",
                  "Sınıfın okul günlerini artırın ya da dersin haftalık saatini/blok uzunluğunu okul günlerine "
                  "sığacak şekilde azaltın (Tanımlar > Sınıflar / Şubeler)."),
    "ayni_ders_gunu": ("Bu dersin başka bir bloğu zaten o günde", "gün",
                       "Blok sayısı okul günü sayısını geçmiyor; bloklar ayrı günlere konmak zorunda. Blok uzunluğunu "
                       "artırın ya da blok desenini değiştirin."),
    "azami": ("Öğretmenin günlük azami ders saati doluyor", "gün",
              f"{ayar_adi('program_ogretmen_gunluk_azami')} değerini artırın ya da öğretmenin bazı derslerini "
              "devredin (Program Araçları > Ders Devri)."),
    "ayni_gun": ("Aynı güne gelmemesi gereken başka bir ders o günde", "gün",
                 "Program Araçları > Kısıtlar'daki 'aynı güne gelmesin' grubunu gözden geçirin ya da "
                 f"{ayar_adi('program_kural_gevset')} ile gerektiğinde gevşetmeye izin verin."),
    "ogle": ("Blok öğle arasında bölünüyor", "saat dilimi",
             f"Blok uzunluğunu küçültün, dersin 'öğle arasında bölünmez' işaretini kaldırın ya da "
             f"{ayar_adi('program_ogle_tum_bloklar')} parametresini kapatın."),
    "yarim_gun": ("Öğretmen aynı gün öbür yarıda derste (sabah/öğle kuralı)", "saat dilimi",
                  f"{ayar_adi('program_ogretmen_yarim_gun')} parametresini kapatın ya da öğretmenin derslerini "
                  "azaltın."),
    "genel_kapali": ("Okul geneli ders konmayacak saat", "saat dilimi",
                     f"{ayar_adi('program_genel_kapali')} listesini daraltın."),
    "sinif_kapali": ("Sınıfın ders konmayacak saati / öğretim şekli (sabahçı-öğlenci)", "saat dilimi",
                     "Sınıfın 'Ders Konmayacak Saatler' alanını ya da öğretim şeklini gözden geçirin."),
    "koord": ("Öğretmenin koordinatörlük (işletmelerde mesleki eğitim) günü", "saat dilimi",
              "Koordinatörlük görev gününü değiştirin, dersi başka öğretmene verin ya da "
              f"{ayar_adi('program_kural_gevset')} ile gerektiğinde bu günlerin derse açılmasına izin verin."),
    "ogretmen_musait": ("Öğretmen müsait değil", "saat dilimi",
                        "Öğretmenin 'Müsait Olmadığı Saatler' alanını daraltın (Tanımlar > Öğretmenler)."),
    "sinif_dolu": ("Sınıfın o saatte başka dersi var", "saat dilimi",
                   "Sınıfın haftalık ders toplamını ve kilitli hücrelerini gözden geçirin; kilitleri açıp yeniden "
                   "yerleştirin."),
    "ogretmen_dolu": ("Öğretmen o saatte başka derste", "saat dilimi",
                      "Öğretmenin yükü uygun saatlerine sığmıyor: dersi başka öğretmene devredin, müsaitliğini "
                      "genişletin ya da kilitli hücrelerini açın."),
    "mekan_dolu": ("Uygun atölye/laboratuvar boş değil", "saat dilimi",
                   "Derse başka bir uygun mekân tanımlayın (alanın atölyeleri), sabit atölyeyi kaldırın ya da "
                   "mekân yükünü azaltın."),
    "blok_uzun": ("Blok günlük ders saatinden uzun", "gün",
                  "Blok uzunluğunu günlük ders saatine indirin."),
}
_DINAMIK = {"sinif_dolu", "ogretmen_dolu", "mekan_dolu", "ayni_ders_gunu", "azami", "ayni_gun", "yarim_gun"}


def desen_coz(metin: str | None) -> list[int]:
    """'2+2+1', '2-1', '4,4,2' -> [2, 2, 1]."""
    return [int(x) for x in re.findall(r"\d+", str(metin or "")) if int(x) > 0]


def bloklara_bol(saat: int, blok: int, desen: list[int] | None = None) -> list[int]:
    if saat <= 0:
        return []
    parcalar: list[int] = []
    for p in desen or []:
        if sum(parcalar) + p > saat:
            break
        parcalar.append(p)
    kalan = saat - sum(parcalar)
    blok = max(1, blok or 1)
    parcalar += [blok] * (kalan // blok)
    if kalan % blok:
        parcalar.append(kalan % blok)
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
                 ayni_gun_degil: dict[int, set[int]] | None = None, ogle_arasi: int = 0,
                 ogretmen_yarim_gun: int = 0, tercih: dict | None = None, adlar: dict | None = None,
                 koord_kapali: dict[int, set[tuple[int, int]]] | None = None,
                 genel_kapali: set[tuple[int, int]] | None = None):
        """ogretmen_yarim_gun > 0: öğretmen aynı gün bu saatin hem öncesinde hem sonrasında derse girmez.
        koord_kapali ve genel_kapali yalnızca yerleşmeme nedenlerini adlandırmak içindir; kısıt olarak
        ogretmen_kapali / sinif_kapali içinde verilmiş olmalıdır."""
        self.S = saat_sayisi
        self.G = gun_sayisi
        self.azami = gunluk_azami or 0
        self.ogle = ogle_arasi if 0 < (ogle_arasi or 0) < saat_sayisi else 0
        self.yarim = ogretmen_yarim_gun if 0 < (ogretmen_yarim_gun or 0) < saat_sayisi else 0
        self.ayni_gun = ayni_gun_degil or {}
        self.tercih = {"ogretmen_bosluk": True, "sinif_bosluk": True, "bos_gun": False, "ilk_son": False,
                       "teori_sabah": False, "iyilestirme": 0, **(tercih or {})}
        self.adlar = adlar or {}
        self.rng = random.Random(seed)
        tum = list(range(1, gun_sayisi + 1))
        gunler = {k: {g for g in v if 1 <= g <= gun_sayisi} for k, v in sinif_gunleri.items()}
        self.sinif_gunleri = gunler
        self.gunler = {a.id: [g for g in tum if all(g in gunler.get(c, set(tum)) for c in a.siniflar)]
                       for a in atamalar}
        sinif_kapali = sinif_kapali or {}
        self.ogretmen_kapali = ogretmen_kapali
        self.sinif_kapali = sinif_kapali
        self.koord_kapali = koord_kapali or {}
        self.genel_kapali = genel_kapali or set()
        self.kapali = {a.id: set().union(*(ogretmen_kapali.get(t, set()) for t in a.ogretmenler),
                                         *(sinif_kapali.get(c, set()) for c in a.siniflar))
                       for a in atamalar}
        self.musait_gun = {t: sum(1 for g in tum if any((g, h) not in k for h in range(1, saat_sayisi + 1)))
                           for t, k in ogretmen_kapali.items()}
        self.atama_map = {a.id: a for a in atamalar}
        self.teorili = {c for a in atamalar if not a.uygulamali for c in a.siniflar}
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
            parcalar = bloklara_bol(kalan, a.blok, a.desen)
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
        if self.ogle and a.ogle_bolunmez and s <= self.ogle < s + L - 1:
            return False
        if self.yarim and a.ogretmenler and s <= self.yarim < s + L - 1:
            return False
        kapali = self.kapali.get(a.id)
        return not kapali or all((g, h) not in kapali for h in range(s, s + L))

    def _obur_yari(self, g: int, s: int, L: int) -> range:
        return range(self.yarim + 1, self.S + 1) if s + L - 1 <= self.yarim else range(1, self.yarim + 1)

    def _yarim_dolu(self, a: Atama, g: int, s: int, L: int) -> bool:
        if not self.yarim:
            return False
        return any((t, g, h) in self.ogr_occ for t in a.ogretmenler for h in self._obur_yari(g, s, L))

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
                if self._yarim_dolu(a, g, s, L):
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

    def _son_bos_gun(self, t: int, g: int) -> bool:
        """Öğretmen g gününe ilk kez ders alırsa hiç boş günü kalmaz mı?"""
        kullanilan = sum(1 for d in range(1, self.G + 1) if d != g and self.ogr_gun[(t, d)])
        return kullanilan + 1 >= self.musait_gun.get(t, self.G)

    def _sinifta_uygulamali(self, a: Atama, g: int) -> bool:
        return any((x := self.sinif_occ.get((c, g, h))) is not None and x.atama.uygulamali
                   for c in a.siniflar for h in range(1, self.S + 1))

    def _ogleden_sonra_uygulama(self, a: Atama) -> bool:
        return self.tercih["teori_sabah"] and a.uygulamali and any(c in self.teorili for c in a.siniflar)

    def _tercih_puani(self, a: Atama, g: int, s: int, L: int) -> float:
        T, p = self.tercih, 0.0
        if T["ilk_son"] and a.ilk_son_gun:
            gunler = self.gunler.get(a.id) or []
            if len(gunler) > 2 and g not in (gunler[0], gunler[-1]):
                p += 4.0
        if T["teori_sabah"]:
            ogle = self.ogle or self.S // 2
            if self._ogleden_sonra_uygulama(a) and s <= ogle:
                p += 1.5
            elif not a.uygulamali and s + L - 1 > ogle and self._sinifta_uygulamali(a, g):
                p += 1.5
        return p

    def _puan(self, b: Blok, g: int, s: int) -> float:
        a, L = b.atama, b.uzunluk
        T = self.tercih
        sinif_yuk = sum(1 for h in range(1, self.S + 1) if (a.sinif_id, g, h) in self.sinif_occ)
        puan = sinif_yuk * 1.0
        for t in a.ogretmenler:
            if not self.ogr_gun[(t, g)]:
                puan += 2.5
                if T["bos_gun"] and self._son_bos_gun(t, g):
                    puan += 6.0
            elif T["ogretmen_bosluk"] and not any((t, g, h) in self.ogr_occ for h in (s - 1, s + L)):
                puan += 1.0
        if T["sinif_bosluk"]:
            komsu = (a.sinif_id, g, s - 1) in self.sinif_occ or (a.sinif_id, g, s + L) in self.sinif_occ
            if sinif_yuk:
                puan += -1.5 if komsu else 2.0
            if not self._ogleden_sonra_uygulama(a):
                bos_once = sum(1 for h in range(1, s) if (a.sinif_id, g, h) not in self.sinif_occ)
                puan += 0.8 * bos_once
        puan += 0.1 * s
        if self.atama_gun[(a.id, g)] > 0:
            puan += 5.0
        return puan + self._tercih_puani(a, g, s, L) + self.rng.random() * 0.3

    # --- iyileştirme ---
    def _gun_maliyeti(self, siniflar, ogretmenler, g: int) -> float:
        T, S, m = self.tercih, self.S, 0.0
        if T["sinif_bosluk"]:
            for c in siniflar:
                dolu = [h for h in range(1, S + 1) if (c, g, h) in self.sinif_occ]
                if dolu:
                    kapali = self.sinif_kapali.get(c, ())
                    m += 2.0 * sum(1 for h in range(dolu[0], dolu[-1] + 1)
                                   if (c, g, h) not in self.sinif_occ and (g, h) not in kapali)
                    m += 0.8 * sum(1 for h in range(1, dolu[0]) if (g, h) not in kapali)
        for t in ogretmenler:
            dolu = [h for h in range(1, S + 1) if (t, g, h) in self.ogr_occ]
            if dolu:
                m += 4.0 if T["bos_gun"] else 2.5
                if T["ogretmen_bosluk"]:
                    m += sum(1 for h in range(dolu[0], dolu[-1] + 1) if (t, g, h) not in self.ogr_occ)
        return m

    def _blok_maliyeti(self, b: Blok) -> float:
        g, s = b.yer[0], b.yer[1]
        return (5.0 if self.atama_gun[(b.atama.id, g)] > 1 else 0.0) + self._tercih_puani(b.atama, g, s, b.uzunluk)

    def _iyilestir(self, t0: float, sure_limit: float) -> int:
        """Kesin kurallar içinde blokları daha düşük maliyetli yerlere taşır; taşınan blok sayısını döndürür."""
        tasinan = 0
        adaylar = [b for b in self.bloklar if not b.kilitli and b.yer]
        for _ in range(self.tercih["iyilestirme"]):
            self.rng.shuffle(adaylar)
            degisen = 0
            for b in adaylar:
                if time.time() - t0 > sure_limit:
                    return tasinan
                a, eski = b.atama, b.yer
                gunler = self.gunler.get(a.id, [])
                gun_m = {g: self._gun_maliyeti(a.siniflar, a.ogretmenler, g) for g in gunler}
                once_blok = self._blok_maliyeti(b)
                self._kaldir(b)
                en_iyi, en_iyi_fark = None, -1e-6
                for g, s, oda, oda2 in list(self._secenekler(b)):
                    if (g, s) == eski[:2]:
                        continue
                    self._yerlestir(b, g, s, oda, oda2)
                    gunset = {eski[0], g}
                    sonra = sum(self._gun_maliyeti(a.siniflar, a.ogretmenler, d) for d in gunset)
                    fark = sonra + self._blok_maliyeti(b) - sum(gun_m.get(d, 0.0) for d in gunset) - once_blok
                    self._kaldir(b)
                    if fark < en_iyi_fark:
                        en_iyi, en_iyi_fark = (g, s, oda, oda2), fark
                self._yerlestir(b, *(en_iyi or eski))
                if en_iyi:
                    degisen += 1
            tasinan += degisen
            if not degisen:
                break
        return tasinan

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
                if self.yarim:
                    for t in a.ogretmenler:
                        for h in self._obur_yari(g, s, L):
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
        notlar = []
        if self.tercih["iyilestirme"]:
            tasinan = self._iyilestir(t0, sure_limit)
            if tasinan:
                notlar.append(f"İyileştirme turlarında {tasinan} blok, kesin kurallar korunarak boşlukları ve "
                              "tercih ihlallerini azaltan yerlere taşındı.")
        yerlesmeyen = [x for x in self.bloklar if not x.kilitli and not x.yer]
        sonuc = self._sonuc(yerlesmeyen, t0, it)
        sonuc.notlar += notlar
        return sonuc

    def _sonuc(self, yerlesmeyen: list[Blok], t0: float, it: int) -> CozumSonucu:
        hucreler = []
        for b in self.bloklar:
            if b.yer:
                g, s, oda, oda2 = b.yer
                for h in range(s, s + b.uzunluk):
                    for k in b.atama.kimlikler:
                        hucreler.append((k, g, h, oda, oda2, b.kilitli))
        return CozumSonucu(hucreler, [(b.atama, b.uzunluk) for b in yerlesmeyen], time.time() - t0, it,
                           nedenler=[self.neden(b) for b in yerlesmeyen])

    # --- yerleşmeme nedenleri ---
    def _ad(self, tur: str, kimlik) -> str:
        return self.adlar.get((tur, kimlik)) or f"#{kimlik}"

    def _saat_engelleri(self, a: Atama, g: int, s: int, L: int) -> list[tuple[str, str]]:
        gun = GUNLER[g - 1] if g <= len(GUNLER) else f"{g}. gün"
        out: list[tuple[str, str]] = []
        if self.ogle and a.ogle_bolunmez and s <= self.ogle < s + L - 1:
            out.append(("ogle", f"{s}.-{s + L - 1}. saat öğle arasını ({self.ogle}. saatten sonra) böler"))
        if self.yarim and a.ogretmenler:
            if s <= self.yarim < s + L - 1:
                out.append(("yarim_gun", f"{s}.-{s + L - 1}. saat sabah ve öğleden sonrayı birleştirir"))
            else:
                for t in a.ogretmenler:
                    dolu = [h for h in self._obur_yari(g, s, L) if (t, g, h) in self.ogr_occ]
                    if dolu:
                        out.append(("yarim_gun", f"{self._ad('t', t)}: {gun} {dolu[0]}. saatte derste"))
        for h in range(s, s + L):
            yer = f"{gun} {h}. saat"
            genel = (g, h) in self.genel_kapali
            if genel:
                out.append(("genel_kapali", yer))
            for c in a.siniflar:
                if not genel and (g, h) in self.sinif_kapali.get(c, ()):
                    out.append(("sinif_kapali", f"{self._ad('c', c)}: {yer}"))
                x = self.sinif_occ.get((c, g, h))
                if x:
                    out.append(("sinif_dolu", f"{self._ad('c', c)} {yer}: {x.atama.etiket}"
                                + (" (kilitli)" if x.kilitli else "")))
            for t in a.ogretmenler:
                if (g, h) in self.koord_kapali.get(t, ()):
                    out.append(("koord", f"{self._ad('t', t)}: {gun}"))
                elif (g, h) in self.ogretmen_kapali.get(t, ()):
                    out.append(("ogretmen_musait", f"{self._ad('t', t)}: {yer}"))
                x = self.ogr_occ.get((t, g, h))
                if x:
                    out.append(("ogretmen_dolu", f"{self._ad('t', t)} {yer}: {x.atama.etiket}"
                                + (" (kilitli)" if x.kilitli else "")))
        for odalar in (a.odalar, a.odalar2):
            if not odalar or odalar == [None]:
                continue
            var, _ = self._bos_oda(odalar, g, s, L)
            if not var:
                adlar = ", ".join(dict.fromkeys(self._ad("o", o) for o in odalar if o))
                out.append(("mekan_dolu", f"{gun} {s}.-{s + L - 1}. saat: {adlar}"))
        return out

    def neden(self, b: Blok) -> YerlesmemeNedeni:
        """Bloğun her gün ve başlangıç saati için engellerini sayar; en sık engellerden açıklama ve öneri üretir."""
        a, L = b.atama, b.uzunluk
        sayac: Counter = Counter()
        ornek: dict[str, list[str]] = defaultdict(list)

        def ekle(k: str, m: str) -> None:
            sayac[k] += 1
            if m not in ornek[k]:
                ornek[k].append(m)

        uygun_gun = set(self.gunler.get(a.id, []))
        kesin = self._kesin_ayri_gun(a)
        dilim = 0
        if L > self.S:
            ekle("blok_uzun", f"{L} saatlik blok, günde {self.S} ders saati")
        for g in range(1, self.G + 1):
            gun = GUNLER[g - 1] if g <= len(GUNLER) else f"{g}. gün"
            if L > self.S:
                break
            if g not in uygun_gun:
                disarida = [self._ad("c", c) for c in a.siniflar if g not in self.sinif_gunleri.get(c, {g})]
                ekle("okul_gunu", f"{gun}: {', '.join(disarida) or 'sınıf'}")
                continue
            gun_engeli = False
            if kesin and self.atama_gun[(a.id, g)] > 0:
                ekle("ayni_ders_gunu", gun)
                gun_engeli = True
            if self.azami:
                for t in a.ogretmenler:
                    if self.ogr_gun[(t, g)] + L > self.azami:
                        ekle("azami", f"{self._ad('t', t)}: {gun} {self.ogr_gun[(t, g)]} saat dersli, sınır "
                                      f"{self.azami}")
                        gun_engeli = True
            if self._ayni_gun_dolu(a, g):
                diger = [self.atama_map[x].etiket for x in self.ayni_gun.get(a.id, ())
                         if self.gun_dolu[(x, g)] > 0 and x in self.atama_map]
                ekle("ayni_gun", f"{gun}: {', '.join(diger)}")
                gun_engeli = True
            if gun_engeli:
                continue
            for s in range(1, self.S - L + 2):
                dilim += 1
                engeller = self._saat_engelleri(a, g, s, L)
                for k in {k for k, _ in engeller}:
                    sayac[k] += 1
                for k, m in engeller:
                    if m not in ornek[k]:
                        ornek[k].append(m)

        if not sayac:
            ozet = "Kurallara uygun yer var; süre sınırı içinde sıra gelmedi. Süre sınırını artırıp yeniden deneyin."
            oneriler = [f"{ayar_adi('program_sure_limit_sn')} değerini artırın."]
        elif set(sayac) <= _DINAMIK - {"azami", "yarim_gun"} and dilim:
            ozet = ("Kurallara göre uygun saatler var, ancak hepsi başka derslerle dolu. Çakışan dersler aşağıda; "
                    "kilitleri açıp süre sınırını artırarak yeniden deneyin ya da çakışan dersin öğretmenini/"
                    "mekânını değiştirin.")
            oneriler = [f"{ayar_adi('program_sure_limit_sn')} değerini artırın."]
        else:
            ilk = next((k for k, _ in sayac.most_common() if k != "okul_gunu"), "okul_gunu")
            ozet = f"Başlıca engel: {NEDENLER[ilk][0][0].lower()}{NEDENLER[ilk][0][1:]}."
            oneriler = []
        nedenler = []
        for k, n in sorted(sayac.most_common(), key=lambda x: x[0] == "okul_gunu"):
            baslik, birim, oneri = NEDENLER[k]
            kapsam = f"{n}/{dilim} saat diliminde" if birim == "saat dilimi" and dilim else f"{n} {birim}"
            orn = ornek[k][:4]
            nedenler.append(f"{baslik} ({kapsam}): " + "; ".join(orn) + (" …" if len(ornek[k]) > 4 else ""))
            if oneri not in oneriler:
                oneriler.append(oneri)
        return YerlesmemeNedeni(a.etiket, L, ozet, nedenler, oneriler[:5])


# ----------------------------------------------------------------- DB katmanı

def sinif_mevcutlari(db) -> dict[int, int]:
    return {r["sinif_id"]: r["n"] for r in db.q("""SELECT sinif_id, COUNT(*) n FROM ogrenciler
                                                  WHERE aktif = 1 AND sinif_id IS NOT NULL GROUP BY sinif_id""")}


def _atama_satirlari(db):
    return db.q("""SELECT da.*, d.ad AS ders, d.blok AS ders_blok, d.atolye_gerekli, d.alan_id AS ders_alan,
                          d.blok_deseni AS ders_desen, d.ogle_bolunmez AS ders_ogle_bolunmez, d.tur AS ders_tur,
                          s.ad AS sinif, s.alan_id AS sinif_alan
                   FROM ders_atamalari da JOIN dersler d ON d.id = da.ders_id
                   JOIN siniflar s ON s.id = da.sinif_id ORDER BY da.id""")


def ilk_son_gun_dersi(ad: str | None) -> bool:
    """Ortaöğretim Kurumları Yönetmeliği md.12: haftanın ilk ve son iş gününe konacak dersler."""
    from .aktarim import norm
    n = norm(ad or "")
    return "beden egitimi" in n or "muzik" in n


def uygulamali_mi(atolye_gerekli, tur: str | None) -> bool:
    return bool(atolye_gerekli) or (tur or "") == "Atölye"


def atamalari_oku(db) -> list[Atama]:
    """Ders atamalarını çözücü girdisine çevirir: mekân adayları (kapasiteye göre sıralı), grup dersinde ikinci
    mekân, birleştirilmiş derslerin tek blokta toplanması."""
    atolyeler = db.q("SELECT id, alan_id, kapasite FROM atolyeler ORDER BY id")
    kap = {a["id"]: int(a["kapasite"] or 0) for a in atolyeler}
    mevcut = sinif_mevcutlari(db) if db.ayar("program_kapasite_denetimi") else {}
    ogle_tum = bool(db.ayar("program_ogle_tum_bloklar"))
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
                  r["ogretmen2_id"], odalar2, ders_id=r["ders_id"],
                  desen=desen_coz(r["blok_deseni"] or r["ders_desen"]),
                  ogle_bolunmez=ogle_tum or bool(r["ogle_bolunmez"] or r["ders_ogle_bolunmez"]),
                  uygulamali=uygulamali_mi(r["atolye_gerekli"], r["ders_tur"]),
                  ilk_son_gun=ilk_son_gun_dersi(r["ders"]))
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
                         [t for a in lst[1:] for t in (a.ogretmen_id, a.ogretmen2_id) if t], ana.ders_id,
                         ana.desen, any(a.ogle_bolunmez for a in lst), any(a.uygulamali for a in lst),
                         any(a.ilk_son_gun for a in lst)))
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


def yarim_gun_sonu(db, S: int) -> int:
    y = db.ayar("program_yarim_gun_saat")
    return y if 0 < y < S else S // 2


def genel_kapali_saatler(db, S: int) -> set[tuple[int, int]]:
    return musaitlik_coz(db.ayar("program_genel_kapali"), S)


def sinif_kapali_saatleri(db, S: int) -> dict[int, set[tuple[int, int]]]:
    """Sınıfın ders konmayacak saatleri + okul geneli kapalı saatler + ikili öğretimde öbür yarı."""
    genel = genel_kapali_saatler(db, S)
    yarim = yarim_gun_sonu(db, S)
    out = {}
    for r in db.q("SELECT id, kapali_saatler, tedrisat FROM siniflar"):
        k = musaitlik_coz(r["kapali_saatler"], S) | genel
        tedrisat = (r["tedrisat"] or "").strip()
        if tedrisat == "Sabahçı":
            k |= {(g, h) for g in range(1, 6) for h in range(yarim + 1, S + 1)}
        elif tedrisat == "Öğlenci":
            k |= {(g, h) for g in range(1, 6) for h in range(1, yarim + 1)}
        if k:
            out[r["id"]] = k
    return out


def cozucu_girdisi(db) -> dict:
    """Ayarlar ve tanımlardan çözücünün bütün kesin kural ve tercihlerini toplar."""
    S = db.ayar("gunluk_ders_saati")
    atamalar = atamalari_oku(db)
    siniflar = db.q("SELECT id, ad, okul_gunleri FROM siniflar")
    ogretmenler = db.q("SELECT id, ad, soyad, musait_olmayan FROM ogretmenler")
    adlar = {("c", r["id"]): r["ad"] for r in siniflar}
    adlar.update({("t", r["id"]): f"{r['ad']} {r['soyad']}" for r in ogretmenler})
    adlar.update({("o", r["id"]): r["ad"] for r in db.q("SELECT id, ad FROM atolyeler")})
    return {
        "S": S, "atamalar": atamalar, "adlar": adlar,
        "sinif_gunleri": {r["id"]: gunler_listesi(r["okul_gunleri"]) or [1, 2, 3, 4, 5] for r in siniflar},
        "ogretmen_kapali": {r["id"]: musaitlik_coz(r["musait_olmayan"], S) for r in ogretmenler},
        "koord": _koordinatorluk_gunleri(db, S) if db.ayar("program_koord_gunu_bos") else {},
        "sinif_kapali": sinif_kapali_saatleri(db, S),
        "genel": genel_kapali_saatler(db, S),
        "azami": db.ayar("program_ogretmen_gunluk_azami"),
        "ogle": db.ayar("program_ogle_arasi"),
        "yarim": yarim_gun_sonu(db, S) if db.ayar("program_ogretmen_yarim_gun") else 0,
        "kurallar": gun_kurallari(atamalar, ders_gruplari(db), db.ayar("program_ogretmen_ayni_gun"),
                                  rehberlik_dersleri(db)),
        "tercih": {"ogretmen_bosluk": bool(db.ayar("program_ogretmen_bosluk")),
                   "sinif_bosluk": bool(db.ayar("program_sinif_bosluk")),
                   "bos_gun": bool(db.ayar("program_ogretmen_bos_gun")),
                   "ilk_son": bool(db.ayar("program_beden_muzik_ilk_son")),
                   "teori_sabah": bool(db.ayar("program_teori_sabah")),
                   "iyilestirme": max(0, db.ayar("program_iyilestirme_tur") or 0)},
    }


def cozucu_kur(girdi: dict, kilitli: list, seed: int | None = None, koord_bos: bool = True,
               gun_kurali: bool = True) -> Cozucu:
    kapali, koord = girdi["ogretmen_kapali"], girdi["koord"] if koord_bos else {}
    if koord:
        kapali = {t: kapali.get(t, set()) | koord.get(t, set()) for t in set(kapali) | set(koord)}
    return Cozucu(girdi["atamalar"], 5, girdi["S"], girdi["sinif_gunleri"], kapali, kilitli, seed, girdi["azami"],
                  girdi["sinif_kapali"], girdi["kurallar"] if gun_kurali else {}, girdi["ogle"],
                  ogretmen_yarim_gun=girdi["yarim"], tercih=girdi["tercih"], adlar=girdi["adlar"],
                  koord_kapali=koord, genel_kapali=girdi["genel"])


def programi_olustur(db, sure_limit: float | None = None, seed: int | None = None,
                     kilitlileri_koru: bool = True, gevset: bool | None = None) -> CozumSonucu:
    """gevset None ise program_kural_gevset ayarı kullanılır; True/False bu çalıştırmayı geçici ezer."""
    sure_limit = sure_limit if sure_limit is not None else db.ayar("program_sure_limit_sn")
    gevset = bool(db.ayar("program_kural_gevset")) if gevset is None else gevset
    girdi = cozucu_girdisi(db)
    kilitli = []
    if kilitlileri_koru:
        kilitli = [(r["atama_id"], r["gun"], r["saat"], r["atolye_id"], r["atolye2_id"])
                   for r in db.q("SELECT * FROM program_hucreleri WHERE kilitli = 1")]

    def coz(koord_bos: bool, gun_kurali: bool, limit: float = sure_limit) -> CozumSonucu:
        return cozucu_kur(girdi, kilitli, seed, koord_bos, gun_kurali).coz(limit)

    kurallar, koord = bool(girdi["kurallar"]), bool(girdi["koord"])
    sonuc = coz(True, True)
    if sonuc.yerlesmeyen and (kurallar or koord) and gevset:
        if kurallar:
            gevsek = coz(True, False)
            if len(gevsek.yerlesmeyen) < len(sonuc.yerlesmeyen):
                gevsek.notlar.append("Aynı güne gelmemesi istenen dersler bu kurala uyularak tümüyle yerleşmedi; "
                                     "kural gerektiği kadar gevşetildi ('Kontrol Et' kurala uymayan günleri "
                                     "listeler).")
                sonuc, kurallar = gevsek, False
        if koord and sonuc.yerlesmeyen:
            ikinci = coz(False, kurallar)
            if len(ikinci.yerlesmeyen) < len(sonuc.yerlesmeyen):
                ikinci.notlar = sonuc.notlar + ["Koordinatörlük günleri boş bırakılınca bazı dersler yerleşmedi; "
                                                "bu günler gerektiği kadar derse açıldı (Veri Denetimi çakışan "
                                                "öğretmenleri listeler)."]
                sonuc = ikinci
    elif sonuc.yerlesmeyen and (kurallar or koord):
        # Kısa deneme (en fazla 2 sn): uzun ikinci çözüm zayıf bilgisayarları yorar
        deneme = coz(False, False, min(sure_limit, 2))
        fark = len(sonuc.yerlesmeyen) - len(deneme.yerlesmeyen)
        neler = " ve ".join(x for x, var in (("'aynı güne gelmesin' kuralları", kurallar),
                                             ("koordinatörlük günlerinin boş bırakılması", koord)) if var)
        if fark > 0:
            sonuc.notlar.append(f"Parametrelere kesin uyuldu, hiçbir kural gevşetilmedi. {neler} gevşetilseydi "
                                f"{fark} blok daha yerleşebilirdi. Buna izin vermek isterseniz tablonun üstündeki "
                                f"'Kurallar yerleşmeyince gevşet' kutusunu işaretleyin veya "
                                f"{ayar_adi('program_kural_gevset')} parametresini açın; ya da aşağıdaki "
                                "nedenleri giderin.")
        else:
            sonuc.notlar.append(f"Parametrelere kesin uyuldu. {neler} gevşetilse de yerleşmeyen ders azalmıyor; "
                                "engel ders, öğretmen veya mekân yükünden kaynaklanıyor (nedenlere bakın).")
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
                              COALESCE(da.blok, d.blok, 1) AS blok,
                              COALESCE(da.ogle_bolunmez, 0) + COALESCE(d.ogle_bolunmez, 0) AS ogle_bolunmez
                       FROM program_hucreleri ph JOIN ders_atamalari da ON da.id = ph.atama_id
                       JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id""")
    out = []
    kapali = sinif_kapali_saatleri(db, S)
    for h in hucreler:
        if (h["gun"], h["saat"]) in kapali.get(h["sinif_id"], set()):
            out.append(f"Sınıfın kapalı saati: {h['sinif']} - {h['ders']} {h['gun']}. gün {h['saat']}. saat")
    ogle = db.ayar("program_ogle_arasi")
    if 0 < ogle < S:
        ogle_tum = db.ayar("program_ogle_tum_bloklar")
        yer = {(h["atama_id"], h["gun"], h["saat"]) for h in hucreler}
        for h in hucreler:
            if h["saat"] == ogle and (h["blok"] or 1) > 1 and (ogle_tum or h["ogle_bolunmez"]) \
                    and (h["atama_id"], h["gun"], ogle + 1) in yer:
                out.append(f"Öğle arasında bölünen blok: {h['sinif']} - {h['ders']} {h['gun']}. gün")
    if db.ayar("program_ogretmen_yarim_gun"):
        yarim = yarim_gun_sonu(db, S)
        for r in db.q("""SELECT o.ad || ' ' || o.soyad AS ad, ph.gun, MIN(ph.saat) AS ilk, MAX(ph.saat) AS son
                         FROM program_hucreleri ph JOIN ders_ogretmenleri dog ON dog.atama_id = ph.atama_id
                         JOIN ogretmenler o ON o.id = dog.ogretmen_id
                         GROUP BY dog.ogretmen_id, ph.gun ORDER BY o.ad, ph.gun"""):
            if r["ilk"] <= yarim < r["son"]:
                out.append(f"Öğretmen aynı gün hem sabah hem öğleden sonra derste: {r['ad']} - "
                           f"{GUNLER[r['gun'] - 1] if 1 <= r['gun'] <= 5 else r['gun']}")
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
    out += _ek_on_denetim(db, rows, S, sinif_kapali, koord)
    out.sort(key=lambda b: {"Kritik": 0, "Uyarı": 1, "Bilgi": 2}[b.seviye])
    return out


def _ek_on_denetim(db, rows, S: int, sinif_kapali: dict, koord: dict) -> list[OnDenetimBulgusu]:
    """Öğretmensiz ders, MEM teorik gün sayısı ve hiçbir güne sığmayan bloklar."""
    out: list[OnDenetimBulgusu] = []
    for r in rows:
        if not r["ogretmen_id"] and (r["haftalik_saat"] or 0) > 0:
            out.append(OnDenetimBulgusu("Uyarı", "Öğretmen", f"{r['sinif']} - {r['ders']}: öğretmeni atanmamış. Ders "
                                        "yine yerleşir; ancak e-Okul'a aktarım ve ek ders için öğretmen gerekir."))
    from ..mevzuat import mem_mi
    for r in db.q("SELECT id, ad, program, okul_gunleri FROM siniflar"):
        n = len(gunler_listesi(r["okul_gunleri"]) or [1, 2, 3, 4, 5])
        if mem_mi(r["program"]) and not 1 <= n <= 2:
            out.append(OnDenetimBulgusu("Kritik", "MEM", f"{r['ad']}: MEM teorik eğitimi haftada {n} gün; en az 1, en "
                                        "fazla 2 gün olmalı (Ortaöğretim Kurumları Yönetmeliği md.12/3). Sınıfın "
                                        "okul ve işletme günlerini düzeltin."))
    ogle = db.ayar("program_ogle_arasi")
    ogle = ogle if 0 < ogle < S else 0
    ogle_tum = db.ayar("program_ogle_tum_bloklar")
    yarim = yarim_gun_sonu(db, S) if db.ayar("program_ogretmen_yarim_gun") else 0
    girdi_gunler = {r["id"]: gunler_listesi(r["okul_gunleri"]) or [1, 2, 3, 4, 5]
                    for r in db.q("SELECT id, okul_gunleri FROM siniflar")}
    ogr_kapali = {r["id"]: musaitlik_coz(r["musait_olmayan"], S) | koord.get(r["id"], set())
                  for r in db.q("SELECT id, musait_olmayan FROM ogretmenler")}
    for a in atamalari_oku(db):
        parcalar = bloklara_bol(a.saat, a.blok, a.desen)
        if not parcalar or max(parcalar) > S:
            continue
        L = max(parcalar)
        kapali = set().union(*(sinif_kapali.get(c, set()) for c in a.siniflar),
                             *(ogr_kapali.get(t, set()) for t in a.ogretmenler))
        gunler = [g for g in range(1, 6) if all(g in girdi_gunler.get(c, [1, 2, 3, 4, 5]) for c in a.siniflar)]

        def sigar(g: int, s: int) -> bool:
            if ogle and (ogle_tum or a.ogle_bolunmez) and s <= ogle < s + L - 1:
                return False
            if yarim and a.ogretmenler and s <= yarim < s + L - 1:
                return False
            return all((g, h) not in kapali for h in range(s, s + L))

        uygun = [g for g in gunler if any(sigar(g, s) for s in range(1, S - L + 2))]
        if not uygun:
            out.append(OnDenetimBulgusu("Kritik", "Blok", f"{a.etiket}: {L} saatlik blok hiçbir okul gününde ardışık "
                                        "boş saate sığmıyor (sınıfın ders konmayacak saatleri, öğretmen müsaitliği, "
                                        "koordinatörlük günü, öğle arası veya sabah/öğle kuralı)."))
        elif len(parcalar) > 1 and len(uygun) < min(len(parcalar), len(gunler)):
            out.append(OnDenetimBulgusu("Uyarı", "Blok", f"{a.etiket}: {len(parcalar)} blok var, {L} saatlik blok "
                                        f"yalnızca {len(uygun)} güne sığıyor; bloklar aynı güne düşebilir veya "
                                        "yerleşmeyebilir."))
    return out


def yerlesmeme_nedenleri(db) -> list[YerlesmemeNedeni]:
    """Mevcut programda eksik kalan saatlerin neden yerleşemediği (elle düzenlemelerden sonra da çalışır)."""
    girdi = cozucu_girdisi(db)
    kilitli = [(r["atama_id"], r["gun"], r["saat"], r["atolye_id"], r["atolye2_id"])
               for r in db.q("SELECT * FROM program_hucreleri")]
    c = cozucu_kur(girdi, kilitli)
    return [c.neden(b) for b in c.bloklar if not b.kilitli]


def elle_ekleme_uyarilari(db, atama_id: int, g: int, h: int) -> list[str]:
    """Sınıf tablosunda elle ders eklerken kurala aykırılıklar (çakışma ayrıca denetlenir)."""
    S = db.ayar("gunluk_ders_saati")
    r = db.q1("""SELECT da.*, s.ad AS sinif, s.okul_gunleri, d.ad AS ders FROM ders_atamalari da
                 JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id WHERE da.id = ?""",
              (atama_id,))
    if not r:
        return []
    gun = GUNLER[g - 1] if 1 <= g <= 5 else f"{g}. gün"
    out = []
    if g not in (gunler_listesi(r["okul_gunleri"]) or [1, 2, 3, 4, 5]):
        out.append(f"{gun}, {r['sinif']} sınıfının okul günü değil (işletme günü).")
    if (g, h) in genel_kapali_saatler(db, S):
        out.append(f"{gun} {h}. saat okul genelinde ders konmayacak saat.")
    elif (g, h) in sinif_kapali_saatleri(db, S).get(r["sinif_id"], set()):
        out.append(f"{gun} {h}. saat {r['sinif']} için ders konmayacak saat (veya öğretim şekline aykırı).")
    koord = _koordinatorluk_gunleri(db, S) if db.ayar("program_koord_gunu_bos") else {}
    azami = db.ayar("program_ogretmen_gunluk_azami")
    yarim = yarim_gun_sonu(db, S) if db.ayar("program_ogretmen_yarim_gun") else 0
    for t in {r["ogretmen_id"], r["ogretmen2_id"]} - {None}:
        o = db.q1("SELECT ad, soyad, musait_olmayan FROM ogretmenler WHERE id = ?", (t,))
        if not o:
            continue
        ad = f"{o['ad']} {o['soyad']}"
        if (g, h) in koord.get(t, set()):
            out.append(f"{ad}: {gun} koordinatörlük (işletmelerde mesleki eğitim) günü.")
        elif (g, h) in musaitlik_coz(o["musait_olmayan"], S):
            out.append(f"{ad}: {gun} {h}. saat müsait değil.")
        saatler = [x["saat"] for x in db.q("""SELECT DISTINCT ph.saat FROM program_hucreleri ph
                                              JOIN ders_ogretmenleri dog ON dog.atama_id = ph.atama_id
                                              WHERE dog.ogretmen_id = ? AND ph.gun = ?""", (t, g))]
        if azami and len(set(saatler) | {h}) > azami:
            out.append(f"{ad}: {gun} günlük azami {azami} ders saati aşılır.")
        if yarim and any((x <= yarim) != (h <= yarim) for x in saatler):
            out.append(f"{ad}: aynı gün hem sabah hem öğleden sonra derse girmiş olur.")
    ogle = db.ayar("program_ogle_arasi")
    blok = r["blok"] or (db.q1("SELECT blok FROM dersler WHERE id = ?", (r["ders_id"],)) or {"blok": 1})["blok"]
    if 0 < ogle < S and (blok or 1) > 1 and h in (ogle, ogle + 1):
        komsu = ogle + 1 if h == ogle else ogle
        if db.q1("SELECT 1 FROM program_hucreleri WHERE atama_id = ? AND gun = ? AND saat = ?", (atama_id, g, komsu)):
            out.append("Blok ders öğle arasında bölünmüş olur.")
    atamalar = atamalari_oku(db)
    kurallar = gun_kurallari(atamalar, ders_gruplari(db), db.ayar("program_ogretmen_ayni_gun"),
                             rehberlik_dersleri(db))
    bu = next((a for a in atamalar if atama_id in a.kimlikler), None)
    if bu and kurallar.get(bu.id):
        harita = {a.id: a for a in atamalar}
        gunu_dolu = {x["atama_id"] for x in db.q("SELECT DISTINCT atama_id FROM program_hucreleri WHERE gun = ?", (g,))}
        for diger in kurallar[bu.id]:
            if gunu_dolu & set(harita[diger].kimlikler):
                out.append(f"Aynı güne gelmemeli: {harita[diger].etiket} zaten {gun} gününde.")
    return out
