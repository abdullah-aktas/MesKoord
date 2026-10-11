"""Aylık ek ders puantajı ve haftalık maaş / ek ders (M/Ü) işaretleri (Ders ve Ek Ders Saatlerine İlişkin Karar).

Haftalık hesap: aylık karşılığı ders görevini önce haftanın tüm program dersleri (ilk günden
başlanarak ya da ek dersler günlere dengeli dağılacak biçimde), ardından işletmelerde meslek eğitimi
(koordinatörlük) saatleri, en son sınıf rehberliği / kulüp / şeflik görev saatleri doldurur; kalan
saatler ek derstir ve haftalık azami ek ders sınırıyla kırpılır. Resmî tatile denk gelen
günlerdeki dersler aylık karşılığından yapılmış sayılır, ancak ek ders olarak ödenmez.
Elle girilen kayıtlar (nöbet, DYK, gece vb.) doğrudan ek ders olarak eklenir.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from ..mevzuat import GUNLER, YONETICI_UNVANLARI
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


def karsilik_dagit(saatler: list[float], karsilik: float, once_gun: bool = True) -> list[float]:
    """Günlük saatlerin aylık karşılığına sayılan kısmı. once_gun ise karşılık ilk günlerden doldurulur; değilse
    karşılığı aşan (ek ders) saatler günlere olabildiğince eşit dağılır."""
    if once_gun:
        out = []
        for s in saatler:
            k = min(s, max(0, karsilik))
            out.append(k)
            karsilik -= k
        return out
    ek = [0.0] * len(saatler)
    fazla = max(0.0, sum(saatler) - max(0, karsilik))
    while fazla > 1e-9:
        i = min((i for i in range(len(saatler)) if ek[i] < saatler[i]), key=lambda i: (ek[i], -i))
        adim = min(1.0, fazla, saatler[i] - ek[i])
        ek[i] += adim
        fazla -= adim
    return [s - e for s, e in zip(saatler, ek)]


def gorev_saatleri(db, ogr) -> list[tuple[str, int]]:
    """Haftalık ders görevine sayılan sınıf rehberliği, kulüp ve şeflik saatleri: [(görev, saat)]. Şeflere rehberlik
    ve kulüp saati yazılmaz; rehberliği olana kulüp saati yalnız parametre açıksa yazılır."""
    if ogr["sef"]:
        n = db.ayar("ekders_sef_saat")
        return [("Alan/atölye/laboratuvar şefliği", n)] if n else []
    out = []
    siniflar = [r["ad"] for r in db.q("SELECT ad FROM siniflar WHERE rehber_ogretmen_id = ? ORDER BY seviye, ad",
                                      (ogr["id"],))]
    rehber = ", ".join(siniflar) or (ogr["sinif_ogretmenligi"] or "").strip()
    n = db.ayar("ekders_sinif_rehberlik_saat")
    if rehber and n:
        out.append((f"Sınıf rehber öğretmenliği ({rehber})", n))
    k = db.ayar("ekders_kulup_saat")
    if (ogr["kulup"] or "").strip() and k and (not out or db.ayar("ekders_rehberlik_kulup_birlikte")):
        out.append((f"Kulüp: {ogr['kulup'].strip()}", k))
    return out


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
    gorev: float = 0.0
    diger: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    gunduz: float = 0.0
    gece: float = 0.0
    brut: float = 0.0

    @property
    def toplam(self) -> float:
        return self.gunduz + self.gece


def _program_saatleri(db) -> dict[int, Counter]:
    prog: dict[int, Counter] = defaultdict(Counter)
    for r in db.q("""SELECT dog.ogretmen_id, ph.gun, COUNT(DISTINCT ph.saat) AS c FROM program_hucreleri ph
                     JOIN ders_ogretmenleri dog ON dog.atama_id = ph.atama_id
                     GROUP BY dog.ogretmen_id, ph.gun"""):
        prog[r["ogretmen_id"]][r["gun"]] = r["c"]
    return prog


def puantaj(db, yil: int, ay: int) -> list[Puantaj]:
    ilk, son = ay_araligi(yil, ay)
    pazartesi = ilk - timedelta(days=ilk.weekday())
    tatiller = tatil_gunleri(db, pazartesi, son + timedelta(days=7))
    katsayi = db.ayar("aylik_katsayi")
    gunduz_ucret = db.ayar("ek_ders_gosterge_gunduz") * katsayi
    gece_ucret = db.ayar("ek_ders_gosterge_gece") * katsayi
    once_gun = db.ayar("ekders_karsilik_once_gun")
    gorevler_dahil = db.ayar("ekders_gorevler_puantaja")

    prog = _program_saatleri(db)
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
        gorev = sum(s for _, s in gorev_saatleri(db, o)) if gorevler_dahil else 0
        hafta = pazartesi
        while hafta <= son:
            gunler = [hafta + timedelta(days=i) for i in range(5)]
            ders_h = [prog[tid].get(i + 1, 0) for i in range(5)]
            koord_h = [sum(s for g, s, b, e in koord[tid]
                           if g == i + 1 and (b is None or d >= b) and (e is None or d <= e))
                       for i, d in enumerate(gunler)]
            kalan = p.aylik_karsilik
            m = karsilik_dagit(ders_h, kalan, once_gun)
            kalan -= sum(m)
            ek_ders_h = [x - y for x, y in zip(ders_h, m)]
            m = karsilik_dagit(koord_h, kalan, once_gun)
            kalan -= sum(m)
            ek_isl_h = [x - y for x, y in zip(koord_h, m)]
            acik = [i for i, d in enumerate(gunler) if d not in tatiller]
            gorev_gun = acik[-1] if acik else None
            ek_gorev_h = max(0, gorev - max(0, kalan))
            kullanilan = 0.0
            for i, d in enumerate(gunler):
                ek_ders, ek_isl = ek_ders_h[i], ek_isl_h[i]
                ek_gor = ek_gorev_h if i == gorev_gun else 0
                if d in tatiller:
                    ek_ders = ek_isl = 0
                ek_ders = min(ek_ders, max(0, p.azami - kullanilan))
                kullanilan += ek_ders
                ek_isl = min(ek_isl, max(0, p.azami - kullanilan))
                kullanilan += ek_isl
                ek_gor = min(ek_gor, max(0, p.azami - kullanilan))
                kullanilan += ek_gor
                if d.month == ay and d.year == yil:
                    p.gunluk[d.day] = p.gunluk.get(d.day, 0) + ek_ders + ek_isl + ek_gor
                    p.ders += ek_ders
                    p.isletme += ek_isl
                    p.gorev += ek_gor
            hafta += timedelta(days=7)
        p.gunduz = p.ders + p.isletme + p.gorev
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


# ------------------------------------------------------------------ haftalık M/Ü işaretleri

MAAS, UCRET, ODENMEZ = "M", "Ü", "-"


@dataclass
class HaftalikIsaret:
    """Öğretmenin haftalık programındaki her ders saatinin aylık karşılığından (M) mı, ek ders ücretinden (Ü) mi
    yapıldığı; azami ek dersi aşan saatler ödenmez (-). kalemler: (kalem, saat, maaş, ücret)."""
    ogretmen_id: int
    ad: str
    brans: str
    unvan: str
    aylik_karsilik: int
    azami: int
    hucreler: dict[tuple[int, int], str] = field(default_factory=dict)
    kalemler: list[tuple[str, float, float, float]] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)

    @property
    def toplam(self) -> float:
        return sum(k[1] for k in self.kalemler)

    @property
    def maas(self) -> float:
        return sum(k[2] for k in self.kalemler)

    @property
    def ucret(self) -> float:
        return sum(k[3] for k in self.kalemler)

    @property
    def odenmeyen(self) -> float:
        return self.toplam - self.maas - self.ucret


def _aktif_koordinatorluk(db, ogretmen_id: int, bugun: date | None = None) -> list:
    bugun = (bugun or date.today()).isoformat()
    return db.q("""SELECT k.*, i.ad AS isletme FROM koordinator_gorevleri k
                   LEFT JOIN isletmeler i ON i.id = k.isletme_id
                   WHERE k.ogretmen_id = ? AND (k.bitis IS NULL OR k.bitis = '' OR k.bitis >= ?)
                   ORDER BY k.gun, i.ad""", (ogretmen_id, bugun))


def haftalik_isaretler(db, ogretmen_id: int, once_gun: bool | None = None) -> HaftalikIsaret:
    o = db.q1("SELECT * FROM ogretmenler WHERE id = ?", (ogretmen_id,))
    if not o:
        raise ValueError("Öğretmen bulunamadı")
    once_gun = db.ayar("ekders_karsilik_once_gun") if once_gun is None else once_gun
    h = HaftalikIsaret(o["id"], f"{o['ad']} {o['soyad']}", o["brans"] or "", o["unvan"] or "",
                       aylik_karsilik(db, o), azami_ek_ders(db, o))
    satirlar = db.q("""SELECT ph.gun, ph.saat, da.id AS atama, COALESCE(NULLIF(LOWER(TRIM(da.birlestirme)), ''),
                              'a' || da.id) AS grup, d.ad AS ders, s.ad AS sinif
                       FROM program_hucreleri ph JOIN ders_ogretmenleri dog ON dog.atama_id = ph.atama_id
                       JOIN ders_atamalari da ON da.id = ph.atama_id JOIN dersler d ON d.id = da.ders_id
                       JOIN siniflar s ON s.id = da.sinif_id
                       WHERE dog.ogretmen_id = ? AND ph.gun BETWEEN 1 AND 5 ORDER BY ph.gun, ph.saat""", (o["id"],))
    gruplar: dict[tuple[int, int], set] = defaultdict(set)
    for r in satirlar:
        gruplar[(r["gun"], r["saat"])].add(r["grup"])
    for (g, s), x in sorted(gruplar.items()):
        if len(x) > 1:
            h.uyarilar.append(f"Çakışma: {GUNLER[g - 1]} {s}. saatte {len(x)} ayrı ders var")
    ders_h = [sum(1 for g, _ in gruplar if g == i + 1) for i in range(5)]
    koord = _aktif_koordinatorluk(db, o["id"])
    koord_h = [sum(k["haftalik_saat"] or 0 for k in koord if k["gun"] == i + 1) for i in range(5)]
    for g in sorted({k["gun"] for k in koord}) if db.ayar("program_koord_gunu_bos") else []:
        if 1 <= g <= 5 and ders_h[g - 1]:
            h.uyarilar.append(f"Koordinatörlük günü ({GUNLER[g - 1]}) programda {ders_h[g - 1]} saat ders var")
    gorevler = gorev_saatleri(db, o)

    kalan = h.aylik_karsilik
    m_ders = karsilik_dagit(ders_h, kalan, once_gun)
    kalan -= sum(m_ders)
    m_koord = karsilik_dagit(koord_h, kalan, once_gun)
    kalan -= sum(m_koord)
    ucret_kalan = h.azami

    def ode(n: float) -> float:
        nonlocal ucret_kalan
        u = min(n, max(0, ucret_kalan))
        ucret_kalan -= u
        return u

    m_toplam = u_toplam = 0
    for i in range(5):
        saatler = sorted(s for g, s in gruplar if g == i + 1)
        for j, s in enumerate(saatler):
            if j < m_ders[i]:
                h.hucreler[(i + 1, s)] = MAAS
                m_toplam += 1
            elif ode(1):
                h.hucreler[(i + 1, s)] = UCRET
                u_toplam += 1
            else:
                h.hucreler[(i + 1, s)] = ODENMEZ
    h.kalemler.append(("Ders (haftalık program)", sum(ders_h), m_toplam, u_toplam))
    if sum(koord_h):
        gunler = ", ".join(f"{GUNLER[i]} {koord_h[i]}" for i in range(5) if koord_h[i])
        h.kalemler.append((f"İşletmelerde mesleki eğitim ({gunler})", sum(koord_h), sum(m_koord),
                           ode(sum(koord_h) - sum(m_koord))))
    for ad, n in gorevler:
        m = min(n, max(0, kalan))
        kalan -= m
        h.kalemler.append((ad, n, m, ode(n - m)))

    if o["sef"] and (o["kulup"] or o["sinif_ogretmenligi"] or db.q1(
            "SELECT 1 FROM siniflar WHERE rehber_ogretmen_id = ?", (o["id"],))):
        h.uyarilar.append("Şef olduğu için sınıf rehberliği ve kulüp saati yazılmadı")
    elif (o["kulup"] or "").strip() and not any(k.startswith("Kulüp") for k, _ in gorevler) \
            and db.ayar("ekders_kulup_saat"):
        h.uyarilar.append("Kulüp saati yazılmadı: sınıf rehberliği olan öğretmene yalnız rehberlik saati yazılır")
    if (o["sinif_ogretmenligi"] or "").strip() and not db.q1("SELECT 1 FROM siniflar WHERE rehber_ogretmen_id = ?",
                                                           (o["id"],)):
        h.uyarilar.append(f"Sınıf öğretmenliği kodu ({o['sinif_ogretmenligi']}) var, ancak Sınıflar ekranında hiçbir "
                          "sınıfın rehber öğretmeni değil")
    if h.toplam < h.aylik_karsilik:
        h.uyarilar.append(f"Aylık karşılığı dolmuyor: haftada {h.toplam:g} saat, karşılık {h.aylik_karsilik}")
    if h.odenmeyen:
        h.uyarilar.append(f"Haftalık azami ek ders ({h.azami}) aşılıyor: {h.odenmeyen:g} saat ödenmez")
    return h


def tum_isaretler(db) -> list[HaftalikIsaret]:
    """Programda dersi, koordinatörlüğü ya da rehberlik/kulüp/şeflik görevi olan aktif öğretmenler."""
    out = []
    for o in db.q("SELECT id FROM ogretmenler WHERE aktif = 1 ORDER BY ad, soyad"):
        h = haftalik_isaretler(db, o["id"])
        if h.toplam:
            out.append(h)
    return out


def isaretleri_kontrol(db) -> list[tuple[str, str]]:
    """[(öğretmen, uyarı)] — çakışma, karşılık eksiği, azami aşımı, rehberlik / kulüp / şeflik tutarsızlıkları."""
    return [(h.ad, u) for h in tum_isaretler(db) for u in h.uyarilar]
