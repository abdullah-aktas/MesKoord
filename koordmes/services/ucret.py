"""3308 md.25 ve Geçici md.12'ye göre öğrenci ücreti ve devlet katkısı hesabı."""
from __future__ import annotations

from dataclasses import dataclass

from ..mevzuat import OKUL_ICI_TURLER
from .sigorta import eksik_gunler, kapsanan_gunler, prim_gun_sayisi
from .utils import ay_araligi, tarih, yuvarla

MEM_STATULERI = {"Aday Çırak", "Çırak", "Kalfa (MEM 12)"}


def mem_mi(program: str | None, statu: str | None) -> bool:
    return (program or "").upper().startswith("MEM") or (statu in MEM_STATULERI)


def en_az_ucret_orani(db, mem: bool, statu: str | None, personel: int) -> tuple[float, str]:
    esik = db.ayar("personel_esigi")
    if statu == "Kalfa (MEM 12)":
        return db.ayar("ucret_orani_kalfa_mem12"), "Kalfalık yeterliği kazanan MEM 12. sınıf"
    if db.ayar("gecici12_aktif"):
        return db.ayar("ucret_orani_gecici12"), "3308 Geçici md.12"
    if mem or statu in ("Aday Çırak", "Çırak"):
        return db.ayar("ucret_orani_cirak"), "3308 md.25 (aday çırak/çırak)"
    if personel >= esik:
        return db.ayar("ucret_orani_20_ustu"), f"3308 md.25 ({esik} ve üzeri personel)"
    return db.ayar("ucret_orani_20_alti"), f"3308 md.25 ({esik}'den az personel)"


def devlet_katkisi_payi(db, mem: bool, personel: int, kamu: bool) -> tuple[float, str]:
    if kamu:
        return 0.0, "Kamu kurumuna devlet katkısı ödenmez"
    if not db.ayar("gecici12_aktif"):
        return 0.0, "Geçici md.12 uygulanmıyor"
    if mem:
        return db.ayar("dk_pay_mem"), "MEM programı (tamamı)"
    if personel < db.ayar("personel_esigi"):
        return db.ayar("dk_pay_20_alti"), "20'den az personel (üçte iki)"
    return db.ayar("dk_pay_20_ustu"), "20 ve üzeri personel (üçte bir)"


@dataclass
class UcretSatiri:
    yerlestirme_id: int
    ogrenci_id: int
    ogrenci: str
    tc: str
    sinif: str
    program: str
    statu: str
    isletme: str
    personel: int
    kamu: bool
    gun: int
    oran: float
    oran_aciklama: str
    aylik_en_az: float
    en_az_ucret: float
    odenecek_ucret: float
    dk_pay: float
    dk_aciklama: str
    devlet_katkisi: float
    isletme_payi: float
    iban: str


def aylik_hesap(db, yil: int, ay: int) -> list[UcretSatiri]:
    ilk, son = ay_araligi(yil, ay)
    net = db.ayar("asgari_ucret_net")
    orantili = db.ayar("ucret_gune_orantili")
    rows = db.q(
        """SELECT y.*, o.tc, o.ad, o.soyad, o.statu, o.iban, s.ad AS sinif, s.program,
                  i.ad AS isletme, i.personel_sayisi, i.kamu_kurumu
           FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
           LEFT JOIN siniflar s ON s.id = o.sinif_id LEFT JOIN isletmeler i ON i.id = y.isletme_id
           WHERE y.baslangic IS NOT NULL AND y.baslangic <= ? AND (y.bitis IS NULL OR y.bitis = '' OR y.bitis >= ?)
           ORDER BY i.ad, s.ad, o.ad""", (son.isoformat(), ilk.isoformat()))
    out = []
    for r in rows:
        if r["tur"] in OKUL_ICI_TURLER or not r["isletme_id"]:
            continue
        gunler = kapsanan_gunler(tarih(r["baslangic"]), tarih(r["bitis"]), yil, ay)
        gun = prim_gun_sayisi(gunler, yil, ay)
        eksik, _ = eksik_gunler(db, r["ogrenci_id"], gunler)
        gun = max(0, gun - eksik)
        if gun == 0:
            continue
        mem = mem_mi(r["program"], r["statu"])
        personel = int(r["personel_sayisi"] or 0)
        kamu = bool(r["kamu_kurumu"])
        oran, oran_ack = en_az_ucret_orani(db, mem, r["statu"], personel)
        aylik_en_az = net * oran
        carpan = gun / 30.0 if orantili else 1.0
        en_az = yuvarla(aylik_en_az * carpan)
        sozlesme = float(r["ucret"] or 0)
        odenecek = yuvarla(max(sozlesme * carpan, en_az))
        pay, pay_ack = devlet_katkisi_payi(db, mem, personel, kamu)
        dk = yuvarla(en_az * pay)
        out.append(UcretSatiri(
            r["id"], r["ogrenci_id"], f"{r['ad']} {r['soyad']}", r["tc"] or "", r["sinif"] or "",
            r["program"] or "", r["statu"] or "", r["isletme"] or "", personel, kamu, gun, oran, oran_ack,
            yuvarla(aylik_en_az), en_az, odenecek, pay, pay_ack, dk, yuvarla(odenecek - dk), r["iban"] or ""))
    return out


def kaydet(db, yil: int, ay: int, satirlar: list[UcretSatiri]) -> None:
    donem = f"{yil:04d}-{ay:02d}"
    for s in satirlar:
        db.conn.execute(
            """INSERT INTO aylik_odemeler (donem, yerlestirme_id, gun, en_az_ucret, odenecek_ucret, devlet_katkisi)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(donem, yerlestirme_id) DO UPDATE SET gun = excluded.gun,
                 en_az_ucret = excluded.en_az_ucret, odenecek_ucret = excluded.odenecek_ucret,
                 devlet_katkisi = excluded.devlet_katkisi""",
            (donem, s.yerlestirme_id, s.gun, s.en_az_ucret, s.odenecek_ucret, s.devlet_katkisi))
    db.conn.commit()
