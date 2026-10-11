"""Ders programı yardımcı işlemleri.

- Program sürümleri: programın o anki hâli (kilitli hücreler dahil) adıyla saklanır, sonra geri yüklenir.
- Toplu çakma: bir dersi (ör. rehberlik) seçilen sınıfların aynı gün ve saatine kilitli olarak yazar.
- Sınıf öğretmenliği: rehber öğretmeni olmayan sınıflara o sınıfta en çok dersi olan öğretmen atanır.
- Ders devri: ayrılan öğretmenin dersleri yeni öğretmene ya da aynı branştaki öğretmenlere paylaştırılır.
- Yük analizi: öğretmen ve branş bazında haftalık ders yükü, öğretmeni atanmamış dersler.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from ..mevzuat import GUNLER
from . import ekders, program
from .aktarim import norm
from .utils import gunler_listesi


@dataclass
class Sonuc:
    yapilan: int = 0
    mesajlar: list[str] = field(default_factory=list)

    def metin(self, eylem: str) -> str:
        return "\n".join([f"{self.yapilan} {eylem}."] + self.mesajlar[:40]
                         + ([f"... ve {len(self.mesajlar) - 40} not daha"] if len(self.mesajlar) > 40 else []))


# ------------------------------------------------------------------ sürümler

def surum_kaydet(db, ad: str, aciklama: str = "") -> int:
    hucreler = [dict(r) for r in db.q(
        """SELECT ph.atama_id, da.sinif_id, da.ders_id, ph.gun, ph.saat, ph.atolye_id, ph.atolye2_id, ph.kilitli
           FROM program_hucreleri ph JOIN ders_atamalari da ON da.id = ph.atama_id ORDER BY ph.id""")]
    return db.insert("program_surumleri", {"ad": ad.strip() or "Adsız sürüm",
                                           "tarih": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                           "aciklama": aciklama, "veri": json.dumps(hucreler)})


def surumler(db) -> list[dict]:
    out = []
    for r in db.q("SELECT id, ad, tarih, aciklama, veri FROM program_surumleri ORDER BY tarih DESC, id DESC"):
        try:
            n = len(json.loads(r["veri"] or "[]"))
        except ValueError:
            n = 0
        out.append({"id": r["id"], "ad": r["ad"], "tarih": r["tarih"] or "", "aciklama": r["aciklama"] or "",
                    "hucre": n})
    return out


def surum_yukle(db, surum_id: int, once_yedekle: bool = True) -> Sonuc:
    """Sürümdeki hücreleri programa yazar (mevcut program silinir). Ders dağılımı sonradan değiştiyse hücre
    aynı sınıf-ders atamasına eşlenir; karşılığı kalmayanlar atlanır."""
    r = db.q1("SELECT ad, veri FROM program_surumleri WHERE id = ?", (surum_id,))
    if not r:
        raise ValueError("Sürüm bulunamadı")
    hucreler = json.loads(r["veri"] or "[]")
    if once_yedekle and db.q1("SELECT 1 FROM program_hucreleri LIMIT 1"):
        surum_kaydet(db, f"Otomatik: '{r['ad']}' yüklenmeden önceki program")
    atamalar = {a["id"]: a for a in db.q("SELECT id, sinif_id, ders_id, haftalik_saat FROM ders_atamalari")}
    sinif_ders = {(a["sinif_id"], a["ders_id"]): a["id"] for a in atamalar.values()}
    atolyeler = {a["id"] for a in db.q("SELECT id FROM atolyeler")}
    S = db.ayar("gunluk_ders_saati")
    sonuc = Sonuc()
    gorulen: set[tuple[int, int, int]] = set()
    with db.conn:
        db.conn.execute("DELETE FROM program_hucreleri")
        for h in hucreler:
            a = atamalar.get(h.get("atama_id"))
            aid = a["id"] if a and (a["sinif_id"], a["ders_id"]) == (h.get("sinif_id"), h.get("ders_id")) \
                else sinif_ders.get((h.get("sinif_id"), h.get("ders_id")))
            g, s = int(h.get("gun") or 0), int(h.get("saat") or 0)
            if not aid or not (1 <= g <= 5 and 1 <= s <= S) or (aid, g, s) in gorulen:
                sonuc.mesajlar.append(f"Atlandı: {g}. gün {s}. saat (ders dağılımında karşılığı yok)")
                continue
            gorulen.add((aid, g, s))
            db.conn.execute("INSERT INTO program_hucreleri (atama_id, gun, saat, atolye_id, atolye2_id, kilitli) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (aid, g, s, h.get("atolye_id") if h.get("atolye_id") in atolyeler else None,
                             h.get("atolye2_id") if h.get("atolye2_id") in atolyeler else None,
                             int(h.get("kilitli") or 0)))
            sonuc.yapilan += 1
    return sonuc


def surum_sil(db, surum_id: int) -> None:
    db.delete("program_surumleri", surum_id)


# ------------------------------------------------------------------ toplu çakma

def toplu_cak(db, ders_id: int, gun: int, saat: int, sinif_ids: list[int]) -> Sonuc:
    """Dersi seçilen sınıfların aynı saatine kilitli yazar. Aynı saatteki kilitsiz dersler (sınıfın ya da dersin
    öğretmeninin) kaldırılır ve 'Otomatik Yerleştir' ile yeniden yerleşir; kilitli bir ders varsa sınıf atlanır.
    Dersin haftalık saati dolmuşsa başka bir kilitsiz saati boşaltılır."""
    sonuc = Sonuc()
    with db.conn:
        for sid in sinif_ids:
            s = db.q1("SELECT ad, okul_gunleri FROM siniflar WHERE id = ?", (sid,))
            if not s:
                continue
            if gun not in (gunler_listesi(s["okul_gunleri"]) or [1, 2, 3, 4, 5]):
                sonuc.mesajlar.append(f"{s['ad']}: {GUNLER[gun - 1]} sınıfın okul günü değil, atlandı")
                continue
            a = db.q1("""SELECT da.*, d.ad AS ders FROM ders_atamalari da JOIN dersler d ON d.id = da.ders_id
                         WHERE da.sinif_id = ? AND da.ders_id = ?""", (sid, ders_id))
            if not a:
                sonuc.mesajlar.append(f"{s['ad']}: ders dağılımında bu ders yok, atlandı")
                continue
            ogretmenler = [t for t in (a["ogretmen_id"], a["ogretmen2_id"]) if t]
            ph = ",".join("?" for _ in ogretmenler) or "NULL"
            cakisan = db.q(f"""SELECT ph.id, ph.kilitli, ph.atama_id, d.ad AS ders, s.ad AS sinif
                               FROM program_hucreleri ph JOIN ders_atamalari da ON da.id = ph.atama_id
                               JOIN dersler d ON d.id = da.ders_id JOIN siniflar s ON s.id = da.sinif_id
                               WHERE ph.gun = ? AND ph.saat = ? AND (da.sinif_id = ? OR da.ogretmen_id IN ({ph})
                                     OR da.ogretmen2_id IN ({ph}))""",
                           (gun, saat, sid, *ogretmenler, *ogretmenler))
            mevcut = next((c for c in cakisan if c["atama_id"] == a["id"]), None)
            engel = [c for c in cakisan if c["atama_id"] != a["id"] and c["kilitli"]]
            if engel:
                sonuc.mesajlar.append(f"{s['ad']}: bu saatte kilitli '{engel[0]['ders']}' ({engel[0]['sinif']}) "
                                      "var, atlandı")
                continue
            for c in cakisan:
                if c["atama_id"] != a["id"]:
                    db.conn.execute("DELETE FROM program_hucreleri WHERE id = ?", (c["id"],))
                    sonuc.mesajlar.append(f"{s['ad']}: {c['sinif']} sınıfının '{c['ders']}' dersi bu saatten "
                                          "kaldırıldı (yeniden yerleştirin)")
            if mevcut:
                db.conn.execute("UPDATE program_hucreleri SET kilitli = 1 WHERE id = ?", (mevcut["id"],))
                sonuc.yapilan += 1
                continue
            n = db.conn.execute("SELECT COUNT(*) FROM program_hucreleri WHERE atama_id = ?", (a["id"],)).fetchone()[0]
            if n >= (a["haftalik_saat"] or 0):
                fazla = db.conn.execute("SELECT id FROM program_hucreleri WHERE atama_id = ? AND kilitli = 0 "
                                        "ORDER BY gun DESC, saat DESC LIMIT 1", (a["id"],)).fetchone()
                if fazla:
                    db.conn.execute("DELETE FROM program_hucreleri WHERE id = ?", (fazla[0],))
                else:
                    db.conn.execute("UPDATE ders_atamalari SET haftalik_saat = ? WHERE id = ?", (n + 1, a["id"]))
                    sonuc.mesajlar.append(f"{s['ad']}: dersin tüm saatleri kilitliydi; haftalık saat {n + 1} yapıldı")
            db.conn.execute("INSERT INTO program_hucreleri (atama_id, gun, saat, kilitli) VALUES (?, ?, ?, 1)",
                            (a["id"], gun, saat))
            sonuc.yapilan += 1
    return sonuc


# ------------------------------------------------------------------ sınıf öğretmenliği

def sinif_ogretmeni_ata(db, uzerine_yaz: bool = False) -> list[tuple[str, str]]:
    """Rehber öğretmeni olmayan (uzerine_yaz ise tüm) sınıflara, sınıfta rehberlik dersi olan ya da en çok saati
    olan ve başka sınıfın rehberi olmayan aktif öğretmeni atar. (sınıf, öğretmen) listesi döndürür."""
    siniflar = db.q("SELECT id, ad, rehber_ogretmen_id FROM siniflar ORDER BY seviye, ad")
    kullanilan = set() if uzerine_yaz else {s["rehber_ogretmen_id"] for s in siniflar if s["rehber_ogretmen_id"]}
    rehberlik = program.rehberlik_dersleri(db)
    out = []
    with db.conn:
        for s in siniflar:
            if s["rehber_ogretmen_id"] and not uzerine_yaz:
                continue
            adaylar = db.q("""SELECT o.id, o.ad, o.soyad, SUM(da.haftalik_saat) AS saat,
                                     MAX(da.ders_id IN (%s)) AS rehberlik
                              FROM ders_atamalari da JOIN ders_ogretmenleri dog ON dog.atama_id = da.id
                              JOIN ogretmenler o ON o.id = dog.ogretmen_id
                              WHERE da.sinif_id = ? AND o.aktif = 1
                              GROUP BY o.id ORDER BY rehberlik DESC, saat DESC, o.ad"""
                           % (",".join(str(i) for i in rehberlik) or "NULL"), (s["id"],))
            secilen = next((a for a in adaylar if a["id"] not in kullanilan), None)
            if not secilen:
                continue
            kullanilan.add(secilen["id"])
            db.conn.execute("UPDATE siniflar SET rehber_ogretmen_id = ? WHERE id = ?", (secilen["id"], s["id"]))
            db.conn.execute("UPDATE ogretmenler SET sinif_ogretmenligi = ? WHERE id = ?", (s["ad"], secilen["id"]))
            out.append((s["ad"], f"{secilen['ad']} {secilen['soyad']}"))
    return out


# ------------------------------------------------------------------ yük

def ogretmen_yukleri(db) -> dict[int, int]:
    """Öğretmen başına haftalık ders saati; birleştirilmiş dersler bir kez sayılır."""
    yuk: dict[int, int] = defaultdict(int)
    gorulen: set[tuple[int, str]] = set()
    for r in db.q("""SELECT dog.ogretmen_id, da.id, da.haftalik_saat, da.birlestirme FROM ders_atamalari da
                     JOIN ders_ogretmenleri dog ON dog.atama_id = da.id"""):
        g = (r["birlestirme"] or "").strip().casefold()
        if g:
            if (r["ogretmen_id"], g) in gorulen:
                continue
            gorulen.add((r["ogretmen_id"], g))
        yuk[r["ogretmen_id"]] += r["haftalik_saat"] or 0
    return dict(yuk)


@dataclass
class OgretmenYuku:
    ogretmen_id: int
    ad: str
    brans: str
    alan: str
    ders_saati: int
    koordinatorluk: int
    aylik_karsilik: int

    @property
    def toplam(self) -> int:
        return self.ders_saati + self.koordinatorluk

    @property
    def ek_ders(self) -> int:
        return max(0, self.toplam - self.aylik_karsilik)

    @property
    def eksik(self) -> int:
        return max(0, self.aylik_karsilik - self.toplam)


def ogretmen_yuk_tablosu(db) -> list[OgretmenYuku]:
    yuk = ogretmen_yukleri(db)
    koord = {r["ogretmen_id"]: r["s"] for r in db.q(
        "SELECT ogretmen_id, SUM(haftalik_saat) s FROM koordinator_gorevleri GROUP BY ogretmen_id")}
    out = []
    for o in db.q("""SELECT o.*, a.ad AS alan FROM ogretmenler o LEFT JOIN alanlar a ON a.id = o.alan_id
                     WHERE o.aktif = 1 ORDER BY o.brans, o.ad, o.soyad"""):
        out.append(OgretmenYuku(o["id"], f"{o['ad']} {o['soyad']}", o["brans"] or "", o["alan"] or "",
                                yuk.get(o["id"], 0), int(koord.get(o["id"], 0) or 0), ekders.aylik_karsilik(db, o)))
    return out


def brans_ozeti(satirlar: list[OgretmenYuku]) -> list[list]:
    """[branş, öğretmen sayısı, toplam ders, ortalama, en az, en çok, toplam ek ders, karşılığı dolmayan]"""
    gruplar: dict[str, list[OgretmenYuku]] = defaultdict(list)
    for s in satirlar:
        gruplar[s.brans or "(branşı girilmemiş)"].append(s)
    out = []
    for b, lst in sorted(gruplar.items()):
        saatler = [x.ders_saati for x in lst]
        out.append([b, len(lst), sum(saatler), round(sum(saatler) / len(lst), 1), min(saatler), max(saatler),
                    sum(x.ek_ders for x in lst), sum(1 for x in lst if x.eksik)])
    return out


def atanmamis_dersler(db) -> list[list]:
    """[sınıf, ders, haftalık saat, durum] — öğretmeni olmayan veya programa tam yerleşmemiş dersler."""
    out = [[r["sinif"], r["ders"], r["haftalik_saat"], "Öğretmen atanmamış"] for r in db.q(
        """SELECT s.ad AS sinif, d.ad AS ders, da.haftalik_saat FROM ders_atamalari da
           JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id
           WHERE da.ogretmen_id IS NULL AND da.haftalik_saat > 0 ORDER BY s.ad, d.ad""")]
    for etiket, gereken, yerlesen in program.eksik_saatler(db):
        sinif, _, ders = etiket.partition(" - ")
        out.append([sinif, ders, gereken, f"Programda {yerlesen}/{gereken} saat"])
    return out


# ------------------------------------------------------------------ ders devri

def _bos_mu(db, ogretmen_id: int, hucreler: list[tuple[int, int]], S: int) -> bool:
    o = db.q1("SELECT musait_olmayan FROM ogretmenler WHERE id = ?", (ogretmen_id,))
    kapali = program.musaitlik_coz(o["musait_olmayan"] if o else "", S)
    if any(h in kapali for h in hucreler):
        return False
    dolu = {(r["gun"], r["saat"]) for r in db.q(
        """SELECT ph.gun, ph.saat FROM program_hucreleri ph JOIN ders_ogretmenleri dog ON dog.atama_id = ph.atama_id
           WHERE dog.ogretmen_id = ?""", (ogretmen_id,))}
    return not any(h in dolu for h in hucreler)


def devir_adaylari(db, kaynak_id: int) -> list[dict]:
    """Aynı branştaki (branş yoksa aynı alandaki) aktif öğretmenler, yükleriyle."""
    k = db.q1("SELECT brans, alan_id FROM ogretmenler WHERE id = ?", (kaynak_id,))
    if not k:
        return []
    yuk = ogretmen_yukleri(db)
    out = []
    for o in db.q("SELECT id, ad, soyad, brans, alan_id FROM ogretmenler WHERE aktif = 1 AND id != ?", (kaynak_id,)):
        ayni = (norm(o["brans"]) == norm(k["brans"])) if norm(k["brans"]) else \
            (k["alan_id"] is not None and o["alan_id"] == k["alan_id"])
        if ayni:
            out.append({"id": o["id"], "ad": f"{o['ad']} {o['soyad']}", "yuk": yuk.get(o["id"], 0)})
    return sorted(out, key=lambda x: (x["yuk"], x["ad"]))


def ders_devret(db, kaynak_id: int, hedef_id: int | None = None, koordinatorluk: bool = False,
                pasif_yap: bool = False) -> Sonuc:
    """Kaynak öğretmenin ders atamalarını hedef öğretmene; hedef yoksa aynı branştaki öğretmenlere (programdaki
    saatlerinde boş olan ve en az yüklü olana) dağıtır. Programdaki hücreler atamaya bağlı olduğundan yerinde kalır."""
    sonuc = Sonuc()
    S = db.ayar("gunluk_ders_saati")
    atamalar = db.q("""SELECT da.*, s.ad AS sinif, d.ad AS ders FROM ders_atamalari da
                       JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id
                       WHERE da.ogretmen_id = ? OR da.ogretmen2_id = ? ORDER BY da.haftalik_saat DESC, s.ad""",
                    (kaynak_id, kaynak_id))
    adaylar = [] if hedef_id else devir_adaylari(db, kaynak_id)
    if not hedef_id and not adaylar and atamalar:
        raise ValueError("Aynı branşta (branş girilmemişse aynı alanda) aktif öğretmen bulunamadı; dersleri "
                         "devralacak öğretmeni seçin.")
    yuk = {a["id"]: a["yuk"] for a in adaylar}
    adlar = {a["id"]: a["ad"] for a in adaylar}
    if hedef_id:
        h = db.q1("SELECT ad, soyad FROM ogretmenler WHERE id = ?", (hedef_id,))
        adlar[hedef_id] = f"{h['ad']} {h['soyad']}" if h else "?"
    with db.conn:
        for a in atamalar:
            alan = "ogretmen_id" if a["ogretmen_id"] == kaynak_id else "ogretmen2_id"
            diger = a["ogretmen2_id"] if alan == "ogretmen_id" else a["ogretmen_id"]
            hucreler = [(r["gun"], r["saat"]) for r in db.q(
                "SELECT gun, saat FROM program_hucreleri WHERE atama_id = ?", (a["id"],))]
            if hedef_id:
                yeni = hedef_id
            else:
                uygun = [x for x in sorted(yuk, key=lambda t: (yuk[t], adlar[t]))
                         if x != diger and _bos_mu(db, x, hucreler, S)]
                yeni = uygun[0] if uygun else min((x for x in yuk if x != diger), key=lambda t: (yuk[t], adlar[t]),
                                                  default=None)
                if yeni is None:
                    sonuc.mesajlar.append(f"{a['sinif']} - {a['ders']}: uygun öğretmen yok, devredilmedi")
                    continue
                if not uygun:
                    sonuc.mesajlar.append(f"{a['sinif']} - {a['ders']}: {adlar[yeni]} programdaki saatlerde dolu; "
                                          "programı yeniden yerleştirin")
                yuk[yeni] += a["haftalik_saat"] or 0
            if yeni == diger:
                db.conn.execute(f"UPDATE ders_atamalari SET {alan} = NULL WHERE id = ?", (a["id"],))
                if alan == "ogretmen_id":
                    db.conn.execute("UPDATE ders_atamalari SET ogretmen_id = ogretmen2_id, ogretmen2_id = NULL "
                                    "WHERE id = ?", (a["id"],))
            else:
                db.conn.execute(f"UPDATE ders_atamalari SET {alan} = ? WHERE id = ?", (yeni, a["id"]))
            sonuc.yapilan += 1
            sonuc.mesajlar.append(f"{a['sinif']} - {a['ders']} ({a['haftalik_saat']} saat) → {adlar[yeni]}")
        if koordinatorluk and hedef_id:
            n = db.conn.execute("UPDATE koordinator_gorevleri SET ogretmen_id = ? WHERE ogretmen_id = ?",
                                (hedef_id, kaynak_id)).rowcount
            if n:
                sonuc.mesajlar.append(f"{n} koordinatörlük görevi {adlar[hedef_id]} öğretmene devredildi")
        db.conn.execute("UPDATE siniflar SET rehber_ogretmen_id = ? WHERE rehber_ogretmen_id = ?",
                        (hedef_id, kaynak_id))
        if pasif_yap:
            db.conn.execute("UPDATE ogretmenler SET aktif = 0 WHERE id = ?", (kaynak_id,))
    return sonuc
