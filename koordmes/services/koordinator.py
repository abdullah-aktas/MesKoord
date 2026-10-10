"""İşletmelerde mesleki eğitim koordinatörlük görevlendirmesi ve ziyaret planı.

Dayanak: Ortaöğretim Kurumları Yönetmeliği (koordinatör öğretmen görevlendirilmesi) ve
Ders ve Ek Ders Saatlerine İlişkin Karar md.15:
  * Görev; işletmenin uzaklığı, ulaşım, işletme ve öğrenci sayısı ölçütleriyle komisyonca planlanır.
  * Bir öğretmene aynı gün için 8 saatten fazla ek ders görevi verilmez.
  * Haftalık azami: MEM büyükşehir 24 / diğer 18; diğer okullar büyükşehir 20 / diğer 16 saat.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from .program import musaitlik_coz
from .utils import ay_araligi, gunler_listesi, tarih, tatil_gunleri


def haftalik_azami(db) -> int:
    k = db.kurum()
    mem = (k["tur"] or "").upper() == "MEM"
    bs = bool(k["buyuksehir"])
    if mem:
        return db.ayar("koord_max_mem_buyuksehir" if bs else "koord_max_mem_diger")
    return db.ayar("koord_max_okul_buyuksehir" if bs else "koord_max_okul_diger")


@dataclass
class IsletmeIhtiyaci:
    """Bir koordinatör öğretmene verilecek iş: aynı işletme ve alandaki en çok 15 öğrenci (md.88/2-f)."""
    isletme_id: int
    isletme_adi: str
    guzergah: str
    mesafe_km: float
    ogrenci_sayisi: int
    alanlar: set[int]
    gunler: set[int]
    saat: int
    grup: str = ""

    @property
    def ad(self) -> str:
        return f"{self.isletme_adi} ({self.grup})" if self.grup else self.isletme_adi


ATOLYE_UNVANI = "Atölye/Lab. Öğretmeni"


def atolye_ogretmeni_mi(o) -> bool:
    return bool(o["atolye_lab"]) or (o["unvan"] or "") == ATOLYE_UNVANI


def isletme_ihtiyaclari(db, gun: date | None = None,
                        kapsam_disi: list[tuple[str, str]] | None = None) -> list[IsletmeIhtiyaci]:
    """Koordinatör görevlendirilecek işletme-alan grupları. Okul döner sermaye işletmeleri (md.88/8) ve il dışındaki
    staj yerleri (md.88/2-g) görevlendirmeye girmez; bunlar verilirse `kapsam_disi` listesine eklenir."""
    gun = gun or date.today()
    rows = db.q(
        """SELECT i.id, i.ad, i.guzergah, i.mesafe_km, i.doner_sermaye, i.il_disi, y.tur, o.id AS ogr,
                  s.alan_id, a.ad AS alan_adi, s.isletme_gunleri
           FROM yerlestirmeler y JOIN isletmeler i ON i.id = y.isletme_id
           JOIN ogrenciler o ON o.id = y.ogrenci_id LEFT JOIN siniflar s ON s.id = o.sinif_id
           LEFT JOIN alanlar a ON a.id = s.alan_id
           WHERE y.tur != 'Okulda Alan Eğitimi' AND y.durum = 'Aktif'
             AND (y.baslangic IS NULL OR y.baslangic <= ?) AND (y.bitis IS NULL OR y.bitis = '' OR y.bitis >= ?)
           ORDER BY i.id, s.alan_id, o.id""",
        (gun.isoformat(), gun.isoformat()))
    disarida: dict[str, str] = {}
    gruplar: dict[tuple[int, int | None], dict] = {}
    for r in rows:
        if r["doner_sermaye"]:
            disarida[r["ad"]] = "Okulun döner sermaye işletmesi; koordinatör öğretmen görevlendirilmez (md.88/8)"
            continue
        if r["il_disi"] and r["tur"] == "Staj":
            disarida[r["ad"]] = "İl dışında staj; koordinatör öğretmen görevlendirilmez (md.88/2-g)"
            continue
        g = gruplar.setdefault((r["id"], r["alan_id"]), {
            "ad": r["ad"], "alan_adi": r["alan_adi"] or "", "guzergah": r["guzergah"] or "",
            "mesafe": r["mesafe_km"] or 0, "ogr": {}})
        gunler = set(gunler_listesi(r["isletme_gunleri"]) or [1, 2, 3, 4, 5])
        g["ogr"].setdefault(r["ogr"], set()).update(gunler)
    if kapsam_disi is not None:
        kapsam_disi.extend(sorted(disarida.items()))
    taban = db.ayar("koord_isletme_taban_saat")
    n = max(1, db.ayar("koord_ogrenci_ek_saat"))
    uzak = db.ayar("koord_uzak_km")
    boyut = max(1, db.ayar("koord_grup_ogrenci"))
    alan_sayisi: dict[int, int] = defaultdict(int)
    for iid, _ in gruplar:
        alan_sayisi[iid] += 1
    out = []
    for (iid, alan_id), g in gruplar.items():
        ogr = list(g["ogr"].items())
        parcalar = [ogr[i:i + boyut] for i in range(0, len(ogr), boyut)]
        for k, parca in enumerate(parcalar, 1):
            etiket = g["alan_adi"] if alan_sayisi[iid] > 1 else ""
            if len(parcalar) > 1:
                etiket = f"{etiket} {k}. grup".strip()
            saat = taban + (len(parca) - 1) // n + (1 if g["mesafe"] and g["mesafe"] > uzak else 0)
            gunler = set().union(*(x[1] for x in parca))
            out.append(IsletmeIhtiyaci(iid, g["ad"], g["guzergah"], float(g["mesafe"]), len(parca),
                                       {alan_id} if alan_id else set(), gunler, int(saat), etiket))
    return out


def ogretmen_bos_gunleri(db) -> dict[int, set[int]]:
    S = db.ayar("gunluk_ders_saati")
    dolu: dict[int, set[int]] = defaultdict(set)
    for r in db.q("""SELECT DISTINCT dog.ogretmen_id, ph.gun FROM program_hucreleri ph
                     JOIN ders_ogretmenleri dog ON dog.atama_id = ph.atama_id"""):
        dolu[r["ogretmen_id"]].add(r["gun"])
    out = {}
    for r in db.q("SELECT id, musait_olmayan FROM ogretmenler WHERE aktif = 1 AND koordinator = 1"):
        kapali = musaitlik_coz(r["musait_olmayan"], S)
        tam_kapali = {g for g in range(1, 6) if all((g, h) in kapali for h in range(1, S + 1))}
        out[r["id"]] = set(range(1, 6)) - dolu[r["id"]] - tam_kapali
    return out


@dataclass
class GorevSonucu:
    gorevler: list[dict] = field(default_factory=list)
    atanamayan: list[tuple[IsletmeIhtiyaci, str]] = field(default_factory=list)
    yukler: dict[int, int] = field(default_factory=dict)
    kapsam_disi: list[tuple[str, str]] = field(default_factory=list)
    alan_disi: list[str] = field(default_factory=list)


def otomatik_gorevlendir(db, baslangic: date | None = None, bitis: date | None = None,
                         kaydet: bool = True) -> GorevSonucu:
    """Görev önceliği md.88/2-e: önce alanın atölye ve laboratuvar öğretmenleri, sonra alan öğretmenleri, yetmezse
    diğer öğretmenler. Alanı dışında görevlendirilenler `alan_disi` listesinde döner (bilgilendirme yapılmalı)."""
    sonuc = GorevSonucu()
    ihtiyac = isletme_ihtiyaclari(db, baslangic, sonuc.kapsam_disi)
    bos = ogretmen_bos_gunleri(db)
    ogretmenler = {r["id"]: r for r in db.q("SELECT * FROM ogretmenler WHERE aktif = 1 AND koordinator = 1")}
    haftalik_max = haftalik_azami(db)
    gunluk_max = db.ayar("koord_gunluk_max")

    yuk: dict[int, int] = defaultdict(int)
    gun_yuk: dict[tuple[int, int], int] = defaultdict(int)
    gun_guzergah: dict[tuple[int, int], set[str]] = defaultdict(set)

    def alan_disinda(t: int, ih: IsletmeIhtiyaci) -> bool:
        return bool(ih.alanlar) and ogretmenler[t]["alan_id"] not in ih.alanlar

    def adaylar(ih: IsletmeIhtiyaci):
        for t in ogretmenler:
            for g in sorted(bos.get(t, set()) & ih.gunler):
                if yuk[t] + ih.saat <= haftalik_max and gun_yuk[(t, g)] + ih.saat <= gunluk_max:
                    yield t, g

    sirali = sorted(ihtiyac, key=lambda x: (sum(1 for t, _ in adaylar(x) if not alan_disinda(t, x)),
                                            x.guzergah, -x.saat))
    for ih in sirali:
        secenekler = list(adaylar(ih))
        if not secenekler:
            neden = "Uygun boş günü olan öğretmen yok veya haftalık/günlük sınır doldu"
            sonuc.atanamayan.append((ih, neden))
            continue

        def puan(tg):
            t, g = tg
            p = yuk[t] * 2.0
            if ih.guzergah and ih.guzergah in gun_guzergah[(t, g)]:
                p -= 6
            elif gun_yuk[(t, g)] > 0:
                p -= 2
            if alan_disinda(t, ih):
                p += 200
            elif not atolye_ogretmeni_mi(ogretmenler[t]):
                p += 50
            return p

        t, g = min(secenekler, key=puan)
        if alan_disinda(t, ih):
            o = ogretmenler[t]
            sonuc.alan_disi.append(f"{o['ad']} {o['soyad']} → {ih.ad}")
        yuk[t] += ih.saat
        gun_yuk[(t, g)] += ih.saat
        if ih.guzergah:
            gun_guzergah[(t, g)].add(ih.guzergah)
        sonuc.gorevler.append({"ogretmen_id": t, "isletme_id": ih.isletme_id, "gun": g, "haftalik_saat": ih.saat,
                               "baslangic": baslangic.isoformat() if baslangic else None,
                               "bitis": bitis.isoformat() if bitis else None})
    sonuc.yukler = dict(yuk)
    if kaydet:
        with db.conn:
            db.conn.execute("DELETE FROM koordinator_gorevleri")
            for gr in sonuc.gorevler:
                db.conn.execute("""INSERT INTO koordinator_gorevleri (ogretmen_id, isletme_id, gun, haftalik_saat,
                                   baslangic, bitis) VALUES (:ogretmen_id, :isletme_id, :gun, :haftalik_saat,
                                   :baslangic, :bitis)""", gr)
    return sonuc


def gorev_ozeti(db) -> list[dict]:
    """Öğretmen bazında koordinatörlük görev özeti."""
    rows = db.q("""SELECT kg.*, o.ad, o.soyad, i.ad AS isletme, i.guzergah
                   FROM koordinator_gorevleri kg JOIN ogretmenler o ON o.id = kg.ogretmen_id
                   JOIN isletmeler i ON i.id = kg.isletme_id ORDER BY o.ad, o.soyad, kg.gun, i.guzergah""")
    by_t: dict[int, dict] = {}
    for r in rows:
        t = by_t.setdefault(r["ogretmen_id"], {"ogretmen_id": r["ogretmen_id"], "ogretmen": f"{r['ad']} {r['soyad']}",
                                               "gunler": defaultdict(list), "toplam": 0})
        t["gunler"][r["gun"]].append((r["isletme"], r["haftalik_saat"]))
        t["toplam"] += r["haftalik_saat"]
    return list(by_t.values())


def ziyaret_plani_olustur(db, yil: int, ay: int, mevcut_planlananlari_sil: bool = True) -> int:
    ilk, son = ay_araligi(yil, ay)
    tatiller = tatil_gunleri(db, ilk, son)
    if mevcut_planlananlari_sil:
        db.execute("DELETE FROM ziyaretler WHERE durum = 'Planlandı' AND tarih BETWEEN ? AND ?",
                   (ilk.isoformat(), son.isoformat()))
    mevcut = {(r["ogretmen_id"], r["isletme_id"], r["tarih"])
              for r in db.q("SELECT ogretmen_id, isletme_id, tarih FROM ziyaretler WHERE tarih BETWEEN ? AND ?",
                            (ilk.isoformat(), son.isoformat()))}
    sayi = 0
    with db.conn:
        for gr in db.q("SELECT * FROM koordinator_gorevleri"):
            gb, ge = tarih(gr["baslangic"]), tarih(gr["bitis"])
            d = ilk
            while d <= son:
                if d.isoweekday() == gr["gun"] and d not in tatiller and (gb is None or d >= gb) \
                        and (ge is None or d <= ge):
                    key = (gr["ogretmen_id"], gr["isletme_id"], d.isoformat())
                    if key not in mevcut:
                        db.conn.execute("INSERT INTO ziyaretler (ogretmen_id, isletme_id, tarih, durum) "
                                        "VALUES (?, ?, ?, 'Planlandı')", key)
                        sayi += 1
                d += timedelta(days=1)
    return sayi


def ziyaret_istatistigi(db, yil: int, ay: int) -> list[dict]:
    ilk, son = ay_araligi(yil, ay)
    rows = db.q("""SELECT o.ad || ' ' || o.soyad AS ogretmen,
                          SUM(z.durum = 'Planlandı') AS planlandi, SUM(z.durum = 'Yapıldı') AS yapildi,
                          SUM(z.durum = 'Yapılmadı') AS yapilmadi, COUNT(*) AS toplam
                   FROM ziyaretler z JOIN ogretmenler o ON o.id = z.ogretmen_id
                   WHERE z.tarih BETWEEN ? AND ? GROUP BY z.ogretmen_id ORDER BY ogretmen""",
                (ilk.isoformat(), son.isoformat()))
    return [dict(r) for r in rows]


def saat_hesabi_aciklama(db) -> str:
    return (f"İşletme başına {db.ayar('koord_isletme_taban_saat')} saat + her "
            f"{db.ayar('koord_ogrenci_ek_saat')} öğrenci için +1 saat + {db.ayar('koord_uzak_km'):g} km'den "
            f"uzaksa +1 saat. Aynı işletme ve alanda en çok {db.ayar('koord_grup_ogrenci')} öğrenciye bir "
            f"koordinatör; öncelik alanın atölye/lab. öğretmenlerinde (md.88). Haftalık azami {haftalik_azami(db)} "
            f"saat, günlük azami {db.ayar('koord_gunluk_max')} saat.")
