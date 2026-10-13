"""Sınav planlama (sorumluluk, beceri ve ortak sınavlar).

Bir sınav ders + seviye + gruptan oluşur ve birden çok şubenin öğrencisini kapsar. Sınavlar açık seanslara
yerleştirilirken öğrencinin aynı seansta iki sınavı olmaz; günlük sınav sınırı, uygulamalı sınav günü, "aynı güne
gelmesin" kuralları, öğrencilerin kapalı seansları, görevli öğretmen sayısı ve salon kapasitesi gözetilir.
12. sınıf öğrencilerinin sınavları öne alınır, öğrencinin sınavları günlere yayılır, seanslar dengelenir.
Ardından komisyon ve gözcüler görevlendirilir, öğrenciler salonlara ve sıralara dağıtılır.
"""
from __future__ import annotations

import math
import random
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

from . import okuyucu
from .aktarim import (IceAktarmaTanimi, ad_soyad_bol, birlesik_baslik, eslestir, metin, norm, satir_baglamlari,
                      sinif_adi, tr_ad)
from .okuyucu import Tablo
from .utils import gunler_listesi
from .utils import tarih as tarih_coz

SEKILLER = ["Yazılı", "Uygulama", "Sözlü", "Yazılı ve Uygulama"]
DONEM_TURLERI = ["Sorumluluk", "Ortalama Yükseltme", "Tek Ders", "Beceri", "Ortak", "Telafi", "Diğer"]
SORUMLULUK, OYS, TEK_DERS = "Sorumluluk", "OYS", "Tek Ders"
OGRENCI_TURLERI = [SORUMLULUK, OYS, TEK_DERS]
KOMISYON_BASKANI, KOMISYON_UYESI, GOZCU = "Komisyon Başkanı", "Komisyon Üyesi", "Gözcü"
GOREVLER = [KOMISYON_BASKANI, KOMISYON_UYESI, GOZCU]
GELDI, GELMEDI, GIRDI, GIRMEDI = "Geldi", "Gelmedi", "Girdi", "Girmedi"
KURAL_TURLERI = {"ortak_ogrenci": "Ortak öğrencisi varsa aynı güne gelmesin",
                 "kesin": "Kesinlikle aynı güne gelmesin", "ayni_seans": "Aynı seansta yapılsın"}
OTURMA_DUZENLERI = ["Sınıf ve ada göre", "Okul numarasına göre", "Karışık"]
VARSAYILAN_SAATLER = [("09:00", "09:40"), ("10:00", "10:40"), ("11:00", "11:40"), ("13:00", "13:40"),
                      ("14:00", "14:40")]
GUN_ADLARI = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
KRITIK, UYARI, BILGI = "Kritik", "Uyarı", "Bilgi"


def uygulamali(sekil: str | None) -> bool:
    """Uygulamalı sınava giren öğrencinin o gün başka sınavı olmaz."""
    return "uygulama" in norm(sekil)


def salon_gerekir(sekil: str | None) -> bool:
    """Yazılı sınavlar salonda gözcü gözetiminde yapılır; uygulama ve sözlü sınavları komisyon atölyede/sınıfta yapar."""
    return "yazili" in norm(sekil or "Yazılı")


def gozcu_sayisi(ogrenci: int, ogrenci_basina: int) -> int:
    return math.ceil(ogrenci / max(1, ogrenci_basina)) if ogrenci > 0 else 0


def sinav_adi(r: Any) -> str:
    """'Matematik (9. Sınıf)', 'Fizik (10. Sınıf) - B grubu'."""
    ad = r["ders"]
    if r["seviye"]:
        ad += f" ({r['seviye']}. Sınıf)"
    if (r["grup"] or "").strip():
        ad += f" - {r['grup'].strip()} grubu"
    return ad


def gun_adi(t: Any) -> str:
    d = tarih_coz(t)
    return GUN_ADLARI[d.weekday()] if d else ""


def seans_etiketi(r: Any, uzun: bool = True) -> str:
    """'12.10.2026 Pazartesi 2. oturum (10:00-10:40)'."""
    d = tarih_coz(r["tarih"])
    t = d.strftime("%d.%m.%Y") if d else str(r["tarih"])
    saat = f"{r['baslangic']}-{r['bitis']}" if r["baslangic"] else ""
    if not uzun:
        return f"{t} {saat}".strip()
    return f"{t} {gun_adi(d)} {r['sira']}. oturum" + (f" ({saat})" if saat else "")


def ozel_saat(d: Any, sekil: str | None) -> str:
    """Dönemde Uygulama / Sözlü sınavlar için ortak başlama saati verilmişse o saat."""
    n = norm(sekil)
    k = "uygulama_saati" if n == "uygulama" else "sozlu_saati" if n == "sozlu" else None
    return (d[k] or "") if d is not None and k else ""


def egitim_yili(t: Any) -> int | None:
    d = tarih_coz(t)
    return (d.year if d.month >= 9 else d.year - 1) if d else None


def kume_coz(s: str | None) -> set[int]:
    return {int(p) for p in re.split(r"[,;\s]+", s or "") if p.strip().isdigit()}


def _kume_yaz(k: Iterable[int]) -> str:
    return ",".join(str(i) for i in sorted(set(k)))


# ------------------------------------------------------------------ dönemler

def donemler(db) -> list:
    return db.q("SELECT * FROM sinav_donemleri ORDER BY id DESC")


def donem(db, donem_id: int | None):
    return db.q1("SELECT * FROM sinav_donemleri WHERE id = ?", (donem_id,)) if donem_id else None


DERS_YILI_SECENEKLERI = ["Otomatik", "Evet", "Hayır"]


def ders_yili_icinde(db, d: Any) -> bool:
    """Sınavlar ders yılı içinde mi (öğretmenin dersi ve koordinatörlük günü, öğrencinin işletme günü sürüyor mu)?
    'Otomatik': dönem başı (yoksa ilk seans) ders yılı başlangıcından sonra ve Temmuz-Ağustos dışında;
    ders yılı başlangıcı girilmemiş ya da eskimişse Ekim-Haziran arası."""
    if d is None:
        return False
    secim = d["ders_yili_icinde"] or "Otomatik"
    if secim in ("Evet", "Hayır"):
        return secim == "Evet"
    bas = tarih_coz(d["baslangic"])
    if bas is None:
        r = db.q1("SELECT MIN(tarih) t FROM sinav_seanslari WHERE donem_id = ?", (d["id"],))
        bas = tarih_coz(r["t"]) if r else None
    if bas is None or bas.month in (7, 8):
        return False
    from .mesleki_egitim import ders_yili_baslangici
    yil_basi = ders_yili_baslangici(db)
    fark = (bas - yil_basi).days if yil_basi else None
    if fark is not None and -90 < fark < 330:
        return fark >= 0
    return bas.month != 9


def donem_ekle(db, ad: str, tur: str = "Sorumluluk", baslangic: date | str | None = None,
               bitis: date | str | None = None, **ayarlar: Any) -> int:
    if not (ad or "").strip():
        raise ValueError("Dönem adı boş olamaz.")
    vals = {"ad": ad.strip(), "tur": tur, "baslangic": _iso(baslangic), "bitis": _iso(bitis), **ayarlar}
    return db.insert("sinav_donemleri", vals)


def _iso(t: date | str | None) -> str | None:
    d = tarih_coz(t)
    return d.isoformat() if d else None


# ------------------------------------------------------------------ seanslar

def saat_coz(v: Any) -> str | None:
    """'9:00', '09.00', '0900', '9' -> '09:00'."""
    s = metin(v).replace(".", ":").replace(" ", "")
    m = re.fullmatch(r"(\d{1,2})(?::?(\d{2}))?", s)
    if not m:
        return None
    h, dk = int(m.group(1)), int(m.group(2) or 0)
    return f"{h:02d}:{dk:02d}" if h < 24 and dk < 60 else None


def saatleri_coz(s: str) -> list[tuple[str, str]]:
    """'09:00-09:40, 10:00-10:40' -> [('09:00', '09:40'), ('10:00', '10:40')]."""
    out = []
    for p in re.split(r"[,;\n]+", s or ""):
        parca = [x for x in re.split(r"\s*[-–]\s*", p.strip()) if x]
        if len(parca) == 2 and (b := saat_coz(parca[0])) and (e := saat_coz(parca[1])):
            out.append((b, e))
    return out


def tarihleri_uret(bas: date, bit: date, hafta_sonu: bool = False, haric: Iterable[date] = ()) -> list[date]:
    haric = set(haric)
    out, d = [], bas
    while d <= bit:
        if (hafta_sonu or d.weekday() < 5) and d not in haric:
            out.append(d)
        d += timedelta(days=1)
    return out


def seanslari_olustur(db, donem_id: int, tarihler: list[date], saatler: list[tuple[str, str]],
                      sil: bool = True) -> int:
    """Her tarih için verilen saatlerde seans açar. `sil` ise dönemin eski seansları (ve onlara bağlı yerleştirme,
    görevlendirme, salon dağıtımı) silinir; değilse yalnızca olmayan (tarih, sıra) seansları eklenir."""
    tarihler = sorted({tarih_coz(t) for t in tarihler if tarih_coz(t)})
    saatler = [(saat_coz(b) or "", saat_coz(e) or "") for b, e in saatler]
    c = db.conn
    with c:
        if sil:
            alt = "SELECT id FROM sinavlar WHERE donem_id = ?"
            c.execute(f"DELETE FROM sinav_gorevlileri WHERE sinav_id IN ({alt})", (donem_id,))
            c.execute(f"UPDATE sinav_ogrencileri SET salon_id = NULL, sira_no = NULL WHERE sinav_id IN ({alt})",
                      (donem_id,))
            c.execute("UPDATE sinavlar SET seans_id = NULL, cakili = 0 WHERE donem_id = ? AND seans_id IS NOT NULL",
                      (donem_id,))
            c.execute("UPDATE sinav_ogretmenleri SET kapali_seanslar = '' WHERE donem_id = ? AND kapali_seanslar != ''",
                      (donem_id,))
            c.execute("DELETE FROM sinav_seanslari WHERE donem_id = ?", (donem_id,))
        once = c.execute("SELECT COUNT(*) FROM sinav_seanslari WHERE donem_id = ?", (donem_id,)).fetchone()[0]
        c.executemany("INSERT OR IGNORE INTO sinav_seanslari (donem_id, tarih, sira, baslangic, bitis, acik) "
                      "VALUES (?, ?, ?, ?, ?, 1)",
                      [(donem_id, t.isoformat(), i, b, e) for t in tarihler for i, (b, e) in enumerate(saatler, 1)])
        sonra = c.execute("SELECT COUNT(*) FROM sinav_seanslari WHERE donem_id = ?", (donem_id,)).fetchone()[0]
        aralik = c.execute("SELECT MIN(tarih), MAX(tarih) FROM sinav_seanslari WHERE donem_id = ?",
                           (donem_id,)).fetchone()
        if aralik[0]:
            c.execute("UPDATE sinav_donemleri SET baslangic = ?, bitis = ? WHERE id = ?",
                      (aralik[0], aralik[1], donem_id))
    return sonra - once


def seanslar(db, donem_id: int | None, sadece_acik: bool = False) -> list:
    if not donem_id:
        return []
    return db.q("SELECT * FROM sinav_seanslari WHERE donem_id = ?" + (" AND acik = 1" if sadece_acik else "")
                + " ORDER BY tarih, sira", (donem_id,))


def seans_acik_yap(db, seans_id: int, acik: bool) -> None:
    db.execute("UPDATE sinav_seanslari SET acik = ? WHERE id = ?", (int(acik), seans_id))


def seans_saati_ayarla(db, seans_ids: Iterable[int], baslangic: str, bitis: str) -> int:
    """Seçilen seansların başlama / bitiş saatini değiştirir (günden güne farklı saatler için)."""
    b, e = saat_coz(baslangic), saat_coz(bitis)
    if not b or not e or e <= b:
        raise ValueError(f"Saat geçersiz ('{baslangic}' - '{bitis}'). Örnek: 09:00 - 09:40")
    ids = list(dict.fromkeys(seans_ids))
    with db.conn:
        db.conn.executemany("UPDATE sinav_seanslari SET baslangic = ?, bitis = ? WHERE id = ?", [(b, e, i) for i in ids])
    return len(ids)


def seans_ozeti(db, donem_id: int | None) -> dict[int, tuple[int, int]]:
    """Seans -> (sınav sayısı, öğrenci sayısı)."""
    if not donem_id:
        return {}
    return {r["seans_id"]: (r["n"], r["ogr"]) for r in db.q(
        "SELECT s.seans_id, COUNT(DISTINCT s.id) n, COUNT(so.id) ogr FROM sinavlar s "
        "LEFT JOIN sinav_ogrencileri so ON so.sinav_id = s.id WHERE s.donem_id = ? AND s.seans_id IS NOT NULL "
        "GROUP BY s.seans_id", (donem_id,))}


def gun_duzenini_uygula(db, donem_id: int, kaynak_tarih: date | str) -> int:
    """Bir günün açık/kapalı seans düzenini (sıraya göre) dönemin bütün günlerine uygular."""
    t = _iso(kaynak_tarih)
    duzen = {r["sira"]: r["acik"] for r in db.q("SELECT sira, acik FROM sinav_seanslari WHERE donem_id = ? AND "
                                                "tarih = ?", (donem_id, t))}
    if not duzen:
        return 0
    degisen = [(duzen[r["sira"]], r["id"]) for r in seanslar(db, donem_id)
               if r["sira"] in duzen and r["acik"] != duzen[r["sira"]]]
    if degisen:
        with db.conn:
            db.conn.executemany("UPDATE sinav_seanslari SET acik = ? WHERE id = ?", degisen)
    return len(degisen)


# ------------------------------------------------------------------ sınavlar

def _ders_sozlugu(db) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for r in db.q("SELECT id, ad, kisa_ad, alan_id, tur FROM dersler ORDER BY id"):
        for k in (norm(r["ad"]), norm(r["kisa_ad"])):
            if k:
                out.setdefault(k, r)
    return out


def _sinav_varsayilanlari(dersler: dict[str, Any], ders: str) -> dict[str, Any]:
    """Ders tanımlıysa ders_id; meslek/atölye dersinde komisyonun kurulacağı alan."""
    r = dersler.get(norm(ders))
    if r is None:
        return {"ders_id": None, "alan_id": None}
    return {"ders_id": r["id"], "alan_id": r["alan_id"] if r["tur"] in ("Meslek", "Atölye") else None}


_BAGLACLAR = {"VE", "İLE", "VEYA", "DA", "DE"}


def ders_adi_duzelt(s: Any) -> str:
    """'TÜRK DİLİ VE EDEBİYATI' -> 'Türk Dili ve Edebiyatı', 'T.C. İNKILAP TARİHİ' -> 'T.C. İnkılap Tarihi'."""
    s = re.sub(r"\s+", " ", metin(s)).strip(" -–:/,;")
    if not s or s.upper() != s:
        return s
    sozcukler = []
    for w in s.split(" "):
        if re.fullmatch(r"([A-ZÇĞİÖŞÜ]\.)+", w) or len(w) <= 1:
            sozcukler.append(w)
        elif w in _BAGLACLAR:
            sozcukler.append(w.replace("I", "ı").replace("İ", "i").lower())
        else:
            sozcukler.append(tr_ad(w))
    return " ".join(sozcukler)


def sinav_ekle(db, donem_id: int, ders: str, seviye: int | None = None, grup: str = "", sekil: str = "Yazılı",
               sure_dk: int = 40, **ek: Any) -> int:
    """Aynı ders + seviye + grup varsa onun kimliğini döndürür."""
    ders = ders_adi_duzelt(ders)
    if not ders:
        raise ValueError("Ders adı boş olamaz.")
    seviye = int(seviye) if seviye else None
    grup = (grup or "").strip()
    for r in db.q("SELECT id, ders, seviye, grup FROM sinavlar WHERE donem_id = ?", (donem_id,)):
        if (norm(r["ders"]), r["seviye"], norm(r["grup"] or "")) == (norm(ders), seviye, norm(grup)):
            return r["id"]
    vals = {"donem_id": donem_id, "ders": ders, "seviye": seviye, "grup": grup, "sekil": sekil, "sure_dk": sure_dk,
            **_sinav_varsayilanlari(_ders_sozlugu(db), ders), **ek}
    return db.insert("sinavlar", vals)


def sinav_guncelle(db, sinav_id: int, **vals: Any) -> None:
    """Seans değişirse sınavın salon dağıtımı ve kilitsiz görevlileri sıfırlanır."""
    eski = db.q1("SELECT seans_id FROM sinavlar WHERE id = ?", (sinav_id,))
    if eski is None:
        raise ValueError("Sınav bulunamadı.")
    with db.conn:
        if vals:
            db.conn.execute(f"UPDATE sinavlar SET {', '.join(f'{k} = ?' for k in vals)} WHERE id = ?",
                            [*vals.values(), sinav_id])
        if "seans_id" in vals and vals["seans_id"] != eski["seans_id"]:
            _seans_degisti(db.conn, [sinav_id])


def _seans_degisti(c, sinav_ids: list[int]) -> None:
    for i in range(0, len(sinav_ids), 500):
        parca = sinav_ids[i:i + 500]
        ph = ",".join("?" * len(parca))
        c.execute(f"DELETE FROM sinav_gorevlileri WHERE kilitli = 0 AND sinav_id IN ({ph})", parca)
        c.execute(f"UPDATE sinav_ogrencileri SET salon_id = NULL, sira_no = NULL, salon_kilitli = 0 "
                  f"WHERE sinav_id IN ({ph})", parca)


TOPLU_ALANLAR = ("sekil", "sure_dk", "komisyon_sayisi", "gozcu_sayisi", "cakili", "ucretsiz")


def sinavlari_toplu_guncelle(db, sinav_ids: Iterable[int], **vals: Any) -> int:
    """Seçilen sınavların şekil, süre, komisyon/gözcü sayısı, çakılı ve ücretsiz bilgisini birlikte değiştirir
    (sayılarda None = dönem ayarı). Çakılı yalnızca seansı olan sınavlara uygulanır."""
    if set(vals) - set(TOPLU_ALANLAR):
        raise ValueError(f"Toplu değiştirilemeyen alan: {', '.join(sorted(set(vals) - set(TOPLU_ALANLAR)))}")
    ids = list(dict.fromkeys(sinav_ids))
    if not ids or not vals:
        return 0
    diger = {k: v for k, v in vals.items() if k != "cakili"}
    with db.conn:
        for i in range(0, len(ids), 500):
            parca = ids[i:i + 500]
            ph = ",".join("?" * len(parca))
            if diger:
                db.conn.execute(f"UPDATE sinavlar SET {', '.join(f'{k} = ?' for k in diger)} WHERE id IN ({ph})",
                                [*diger.values(), *parca])
            if "cakili" in vals:
                db.conn.execute(f"UPDATE sinavlar SET cakili = ? WHERE seans_id IS NOT NULL AND id IN ({ph})",
                                [int(bool(vals["cakili"])), *parca])
    return len(ids)


def seans_ata(db, sinav_id: int, seans_id: int | None, cakili: bool = True) -> None:
    """Elle seans seçimi; çakılı sınavı otomatik yerleştirme yerinden oynatmaz."""
    sinav_guncelle(db, sinav_id, seans_id=seans_id, cakili=int(bool(cakili and seans_id)))


def sinavlari_sil(db, sinav_ids: list[int]) -> None:
    with db.conn:
        db.conn.executemany("DELETE FROM sinavlar WHERE id = ?", [(i,) for i in sinav_ids])


def sinav_ogrenci_ekle(db, sinav_id: int, ogrenci_ids: Iterable[int], tur: str = "") -> int:
    ids = list(dict.fromkeys(ogrenci_ids))
    mevcut = {r["ogrenci_id"] for r in db.q("SELECT ogrenci_id FROM sinav_ogrencileri WHERE sinav_id = ?",
                                            (sinav_id,))}
    yeni = [(sinav_id, i, tur) for i in ids if i not in mevcut]
    if yeni:
        with db.conn:
            db.conn.executemany("INSERT OR IGNORE INTO sinav_ogrencileri (sinav_id, ogrenci_id, tur) VALUES (?, ?, ?)",
                                yeni)
    return len(yeni)


def ogrenci_katilim_ayarla(db, sinav_id: int, ogrenci_ids: Iterable[int], katilim: str) -> None:
    """katilim: 'Girdi', 'Girmedi' ya da '' (girilmedi)."""
    if katilim not in (GIRDI, GIRMEDI, ""):
        raise ValueError("Katılım 'Girdi', 'Girmedi' ya da boş olabilir.")
    with db.conn:
        db.conn.executemany("UPDATE sinav_ogrencileri SET katilim = ? WHERE sinav_id = ? AND ogrenci_id = ?",
                            [(katilim, sinav_id, o) for o in ogrenci_ids])


def ogrenci_salon_ata(db, sinav_id: int, ogrenci_ids: Iterable[int], salon_id: int | None) -> None:
    """Öğrencileri elle salona alır; otomatik salon dağıtımı bu öğrencilerin salonunu değiştirmez.
    salon_id None ise elle atama kaldırılır."""
    ids = list(ogrenci_ids)
    if salon_id is None:
        vals = [(None, None, 0, sinav_id, o) for o in ids]
    else:
        r = db.q1("SELECT MAX(so.sira_no) m FROM sinav_ogrencileri so JOIN sinavlar s ON s.id = so.sinav_id "
                  "WHERE so.salon_id = ? AND s.seans_id = (SELECT seans_id FROM sinavlar WHERE id = ?)",
                  (salon_id, sinav_id))
        son = (r["m"] if r else None) or 0
        vals = [(salon_id, son + i, 1, sinav_id, o) for i, o in enumerate(ids, 1)]
    with db.conn:
        db.conn.executemany("UPDATE sinav_ogrencileri SET salon_id = ?, sira_no = ?, salon_kilitli = ? "
                            "WHERE sinav_id = ? AND ogrenci_id = ?", vals)


def sinav_salonlari(db, sinav_id: int) -> list[int]:
    """Sınava ayrılmış salonlar (salon dağıtımında önce bunlar doldurulur)."""
    return [r["salon_id"] for r in db.q("SELECT a.salon_id FROM sinav_salon_atamalari a JOIN sinav_salonlari sl "
                                        "ON sl.id = a.salon_id WHERE a.sinav_id = ? ORDER BY sl.sira, sl.id",
                                        (sinav_id,))]


def sinav_salonlari_ayarla(db, sinav_id: int, salon_ids: Iterable[int]) -> None:
    with db.conn:
        db.conn.execute("DELETE FROM sinav_salon_atamalari WHERE sinav_id = ?", (sinav_id,))
        db.conn.executemany("INSERT OR IGNORE INTO sinav_salon_atamalari (sinav_id, salon_id) VALUES (?, ?)",
                            [(sinav_id, s) for s in dict.fromkeys(salon_ids)])


def salonlari_al(db, atolyeler: bool = True, siniflar: bool = False) -> int:
    """Atölye/laboratuvarları (ve istenirse sınıfları) sınav salonu olarak ekler; aynı adlı salon eklenmez."""
    mevcut = {norm(r["ad"]) for r in db.q("SELECT ad FROM sinav_salonlari")}
    sira = db.q1("SELECT MAX(sira) m FROM sinav_salonlari")["m"] or 0
    aday: list[tuple[str, int]] = []
    if atolyeler:
        aday += [(r["ad"], r["kapasite"] or 16) for r in db.q("SELECT ad, kapasite FROM atolyeler ORDER BY ad")]
    if siniflar:
        aday += [(r["ad"], r["n"] or 30) for r in db.q(
            "SELECT si.ad, COUNT(o.id) n FROM siniflar si LEFT JOIN ogrenciler o ON o.sinif_id = si.id AND o.aktif = 1 "
            "GROUP BY si.id ORDER BY si.seviye, si.ad")]
    yeni = []
    for ad, kap in aday:
        if norm(ad) and norm(ad) not in mevcut:
            mevcut.add(norm(ad))
            sira += 1
            yeni.append((ad, kap, sira))
    if yeni:
        with db.conn:
            db.conn.executemany("INSERT INTO sinav_salonlari (ad, kapasite, sira, aktif) VALUES (?, ?, ?, 1)", yeni)
    return len(yeni)


def sinav_ogrenci_cikar(db, sinav_id: int, ogrenci_ids: Iterable[int]) -> int:
    ids = list(ogrenci_ids)
    with db.conn:
        db.conn.executemany("DELETE FROM sinav_ogrencileri WHERE sinav_id = ? AND ogrenci_id = ?",
                            [(sinav_id, i) for i in ids])
    return len(ids)


def sinavlari_birlestir(db, sinav_ids: list[int]) -> int:
    """Seçilen sınavların öğrencilerini ilk sınava taşır, diğerlerini siler. Taşınan öğrenci sayısını döndürür.
    Farklı grup kodları birleşik koda ('EML-ATL') dönüşür; birleştirilen sınavlar açıklamaya yazılır."""
    ids = list(dict.fromkeys(sinav_ids))
    if len(ids) < 2:
        return 0
    hedef, digerleri = ids[0], ids[1:]
    kayit = {r["id"]: r for r in db.q(f"SELECT * FROM sinavlar WHERE id IN ({','.join('?' * len(ids))})", ids)}
    mevcut = {r["ogrenci_id"] for r in db.q("SELECT ogrenci_id FROM sinav_ogrencileri WHERE sinav_id = ?", (hedef,))}
    ph = ",".join("?" * len(digerleri))
    tasinacak = [(r["ogrenci_id"], r["tur"] or "") for r in db.q(
        f"SELECT ogrenci_id, MAX(tur) tur FROM sinav_ogrencileri WHERE sinav_id IN ({ph}) GROUP BY ogrenci_id",
        digerleri) if r["ogrenci_id"] not in mevcut]
    h = kayit.get(hedef)
    vals: dict[str, Any] = {}
    if h is not None:
        gruplar = list(dict.fromkeys(g for g in ((kayit[i]["grup"] or "").strip() for i in ids if i in kayit) if g))
        if len(gruplar) > 1:
            grup = "-".join(gruplar)
            cakisan = [r for r in db.q("SELECT id, ders, seviye, grup FROM sinavlar WHERE donem_id = ?", (h["donem_id"],))
                       if r["id"] not in ids and (norm(r["ders"]), r["seviye"], norm(r["grup"] or "")) ==
                       (norm(h["ders"]), h["seviye"], norm(grup))]
            if not cakisan:
                vals["grup"] = grup
        adlar = [sinav_adi(kayit[i]) for i in digerleri if i in kayit]
        if adlar:
            vals["aciklama"] = " ".join(x for x in ((h["aciklama"] or "").strip(),
                                                    f"Birleştirilen: {', '.join(adlar)}.") if x)
    with db.conn:
        db.conn.executemany("INSERT OR IGNORE INTO sinav_ogrencileri (sinav_id, ogrenci_id, tur) VALUES (?, ?, ?)",
                            [(hedef, o, t) for o, t in tasinacak])
        db.conn.executemany("DELETE FROM sinavlar WHERE id = ?", [(i,) for i in digerleri])
        if vals:
            db.conn.execute(f"UPDATE sinavlar SET {', '.join(f'{k} = ?' for k in vals)} WHERE id = ?",
                            [*vals.values(), hedef])
        _seans_degisti(db.conn, [hedef])
    return len(tasinacak)


def sinav_listesi(db, donem_id: int | None) -> list[dict]:
    """Dönemin sınavları seans sırasıyla; öğrenci sayısı, salonlar, komisyon ve gözcü adlarıyla."""
    if not donem_id:
        return []
    rows = db.q("""SELECT s.*, se.tarih, se.sira, se.baslangic, se.bitis, se.acik, a.ad AS alan,
                          (SELECT COUNT(*) FROM sinav_ogrencileri so WHERE so.sinav_id = s.id) AS ogrenci_sayisi,
                          (SELECT COUNT(*) FROM sinav_ogrencileri so WHERE so.sinav_id = s.id
                                                                       AND so.katilim = 'Girdi') AS girdi,
                          (SELECT COUNT(*) FROM sinav_ogrencileri so WHERE so.sinav_id = s.id
                                                                       AND so.katilim = 'Girmedi') AS girmedi
                   FROM sinavlar s LEFT JOIN sinav_seanslari se ON se.id = s.seans_id
                   LEFT JOIN alanlar a ON a.id = s.alan_id
                   WHERE s.donem_id = ?
                   ORDER BY se.tarih IS NULL, se.tarih, se.sira, s.ders, s.seviye, s.grup""", (donem_id,))
    gorevli: dict[int, list] = defaultdict(list)
    for r in db.q("""SELECT g.id, g.sinav_id, g.gorev, g.ogretmen_id, g.kilitli, g.salon_id, g.durum, g.ucretsiz,
                            o.ad || ' ' || o.soyad AS ad, o.brans, sl.ad AS salon
                     FROM sinav_gorevlileri g JOIN sinavlar s ON s.id = g.sinav_id
                     JOIN ogretmenler o ON o.id = g.ogretmen_id LEFT JOIN sinav_salonlari sl ON sl.id = g.salon_id
                     WHERE s.donem_id = ? ORDER BY g.sinav_id, g.id""", (donem_id,)):
        gorevli[r["sinav_id"]].append(r)
    salon: dict[int, list[str]] = defaultdict(list)
    for r in db.q("""SELECT so.sinav_id, sl.ad, COUNT(*) n FROM sinav_ogrencileri so
                     JOIN sinavlar s ON s.id = so.sinav_id JOIN sinav_salonlari sl ON sl.id = so.salon_id
                     WHERE s.donem_id = ? GROUP BY so.sinav_id, sl.id ORDER BY sl.sira, sl.id""", (donem_id,)):
        salon[r["sinav_id"]].append(f"{r['ad']} ({r['n']})")
    out = []
    for r in rows:
        d = dict(r)
        g = gorevli.get(r["id"], [])
        d["adi"] = sinav_adi(r)
        d["komisyon"] = [x["ad"] for x in sorted((x for x in g if x["gorev"] != GOZCU),
                                                 key=lambda x: x["gorev"] != KOMISYON_BASKANI)]
        d["baskan"] = next((x["ad"] for x in g if x["gorev"] == KOMISYON_BASKANI), "")
        d["gozculer"] = [x["ad"] + (f" ({x['salon']})" if x["salon"] else "") for x in g if x["gorev"] == GOZCU]
        d["gorevliler"] = [dict(x) for x in g]
        d["salonlar"] = ", ".join(salon.get(r["id"], []))
        d["seans"] = seans_etiketi(r) if r["tarih"] else ""
        out.append(d)
    return out


def sinav_ogrencileri(db, sinav_id: int) -> list:
    return db.q("""SELECT so.ogrenci_id, so.salon_id, so.sira_no, so.tur, so.katilim, so.salon_kilitli, o.okul_no,
                          o.tc, o.ad, o.soyad, si.ad AS sinif, si.seviye AS sinif_seviyesi, sl.ad AS salon
                   FROM sinav_ogrencileri so JOIN ogrenciler o ON o.id = so.ogrenci_id
                   LEFT JOIN siniflar si ON si.id = o.sinif_id LEFT JOIN sinav_salonlari sl ON sl.id = so.salon_id
                   WHERE so.sinav_id = ? ORDER BY sl.sira, sl.id, so.sira_no, si.ad, CAST(o.okul_no AS INTEGER),
                   o.ad""", (sinav_id,))


def ogrenci_programi(db, donem_id: int) -> list:
    """Her öğrencinin sınavları (giriş belgesi ve öğrenci listesi için)."""
    return db.q("""SELECT o.id AS ogrenci_id, o.okul_no, o.tc, o.ad, o.soyad, si.ad AS sinif,
                          s.id AS sinav_id, s.ders, s.seviye, s.grup, s.sekil, s.sure_dk,
                          se.tarih, se.sira, se.baslangic, se.bitis, sl.ad AS salon, so.sira_no, so.tur, so.katilim
                   FROM sinav_ogrencileri so JOIN sinavlar s ON s.id = so.sinav_id
                   JOIN ogrenciler o ON o.id = so.ogrenci_id LEFT JOIN siniflar si ON si.id = o.sinif_id
                   LEFT JOIN sinav_seanslari se ON se.id = s.seans_id
                   LEFT JOIN sinav_salonlari sl ON sl.id = so.salon_id
                   WHERE s.donem_id = ?
                   ORDER BY si.ad, CAST(o.okul_no AS INTEGER), o.ad, o.soyad, o.id, se.tarih IS NULL, se.tarih,
                            se.sira""", (donem_id,))


def plani_temizle(db, donem_id: int, cakili_dahil: bool = False) -> int:
    kosul = "" if cakili_dahil else " AND cakili = 0"
    ids = [r["id"] for r in db.q(f"SELECT id FROM sinavlar WHERE donem_id = ? AND seans_id IS NOT NULL{kosul}",
                                 (donem_id,))]
    with db.conn:
        db.conn.execute(f"UPDATE sinavlar SET seans_id = NULL, cakili = 0 WHERE donem_id = ?{kosul}", (donem_id,))
        _seans_degisti(db.conn, ids)
    return len(ids)


# ------------------------------------------------------------------ öğretmenler, öğrenci kapalı seansları, kurallar

def idareci_mi(unvan: str | None) -> bool:
    return "mudur" in norm(unvan)


KAPALI_NEDENLERI = {"nobet": "okul nöbeti", "musait": "ders programında müsait değil",
                    "koordinator": "koordinatörlük görev günü", "ders": "o saatte dersi var"}


def _dakika(s: str | None) -> int | None:
    s = saat_coz(s) if s else None
    return int(s[:2]) * 60 + int(s[3:]) if s else None


def ders_saatleri(db) -> list[tuple[int, int]]:
    """'program_ders_saatleri' parametresindeki ders saatleri (dakika olarak başlangıç, bitiş; 1. ders ilk sırada)."""
    out = []
    for b, e in saatleri_coz(db.ayar("program_ders_saatleri") or ""):
        bd, ed = _dakika(b), _dakika(e)
        if bd is not None and ed is not None and ed > bd:
            out.append((bd, ed))
    return out


def kapali_seans_nedenleri(db, donem_id: int,
                           ogretmen_ids: Iterable[int] | None = None) -> dict[int, dict[int, str]]:
    """Öğretmen -> {seans: neden}: okul nöbeti ve ders programında tamamen müsait olmadığı gün; sınavlar ders yılı
    içindeyse ayrıca koordinatörlük görev günü ve (ders saatleri girilmişse) dersinin seansa denk geldiği saatler."""
    from .program import musaitlik_coz
    sl = [(r["id"], tarih_coz(r["tarih"]), _dakika(r["baslangic"]), _dakika(r["bitis"]))
          for r in seanslar(db, donem_id)]
    if not sl:
        return {}
    S = int(db.ayar("gunluk_ders_saati") or 8)
    secili = set(ogretmen_ids) if ogretmen_ids is not None else None
    ders_yili = ders_yili_icinde(db, donem(db, donem_id))
    koord: dict[int, list] = defaultdict(list)
    dersler: dict[int, set[tuple[int, int]]] = defaultdict(set)
    saatler = ders_saatleri(db) if ders_yili else []
    if ders_yili:
        for r in db.q("SELECT ogretmen_id, gun, baslangic, bitis FROM koordinator_gorevleri"):
            koord[r["ogretmen_id"]].append((r["gun"], tarih_coz(r["baslangic"]), tarih_coz(r["bitis"])))
        if saatler:
            for r in db.q("SELECT do.ogretmen_id, h.gun, h.saat FROM program_hucreleri h "
                          "JOIN ders_ogretmenleri do ON do.atama_id = h.atama_id"):
                dersler[r["ogretmen_id"]].add((r["gun"], r["saat"]))
    out: dict[int, dict[int, str]] = {}
    for r in db.q("SELECT id, nobet_gun, musait_olmayan FROM ogretmenler WHERE aktif = 1"):
        t_id = r["id"]
        if secili is not None and t_id not in secili:
            continue
        kapali = musaitlik_coz(r["musait_olmayan"], S)
        musait_degil = {g for g in range(1, 8) if all((g, h) in kapali for h in range(1, S + 1))}
        nobet = int(r["nobet_gun"]) if r["nobet_gun"] else None
        k: dict[int, str] = {}
        for sid, t, bas, bit in sl:
            if t is None:
                continue
            g = t.weekday() + 1
            if g == nobet:
                k[sid] = "nobet"
            elif g in musait_degil:
                k[sid] = "musait"
            elif any(kg == g and (kb is None or t >= kb) and (ke is None or t <= ke) for kg, kb, ke in koord[t_id]):
                k[sid] = "koordinator"
            elif dersler[t_id] and bas is not None and bit is not None and any(
                    (g, i + 1) in dersler[t_id] and b < bit and bas < e for i, (b, e) in enumerate(saatler)):
                k[sid] = "ders"
        if k:
            out[t_id] = k
    return out


def nobet_kapali_seanslar(db, donem_id: int, ogretmen_ids: Iterable[int] | None = None) -> dict[int, set[int]]:
    """Öğretmenin görev alamayacağı seanslar (nedenleri: `kapali_seans_nedenleri`)."""
    return {t: set(k) for t, k in kapali_seans_nedenleri(db, donem_id, ogretmen_ids).items()}


def eksik_kapali_seanslar(db, donem_id: int) -> dict[int, dict[int, str]]:
    """Görev alan öğretmenlerin henüz kapalı seanslarına işlenmemiş nöbet/koordinatörlük/ders seansları."""
    mevcut = {r["ogretmen_id"]: (kume_coz(r["kapali_seanslar"]), r["gorev_alir"]) for r in db.q(
        "SELECT ogretmen_id, kapali_seanslar, gorev_alir FROM sinav_ogretmenleri WHERE donem_id = ?", (donem_id,))}
    out = {}
    for t, k in kapali_seans_nedenleri(db, donem_id).items():
        if t not in mevcut or not mevcut[t][1]:
            continue
        kume = mevcut[t][0]
        eksik = {s: n for s, n in k.items() if s not in kume}
        if eksik:
            out[t] = eksik
    return out


def ogretmenleri_hazirla(db, donem_id: int) -> int:
    """Dönem için öğretmen satırlarını açar: etkin öğretmenler görev alır; müdür ve yardımcıları almaz. Yeni
    satırlarda görev alamayacağı seanslar (nöbet, müsaitlik, koordinatörlük, ders saati) kapalı gelir."""
    mevcut = {r["ogretmen_id"] for r in db.q("SELECT ogretmen_id FROM sinav_ogretmenleri WHERE donem_id = ?",
                                             (donem_id,))}
    adaylar = [r for r in db.q("SELECT id, unvan FROM ogretmenler WHERE aktif = 1 ORDER BY id") if r["id"] not in mevcut]
    if not adaylar:
        return 0
    kapali = nobet_kapali_seanslar(db, donem_id, [r["id"] for r in adaylar])
    yeni = [(donem_id, r["id"], 0 if idareci_mi(r["unvan"]) else 1, _kume_yaz(kapali.get(r["id"], ())))
            for r in adaylar]
    with db.conn:
        db.conn.executemany("INSERT OR IGNORE INTO sinav_ogretmenleri (donem_id, ogretmen_id, gorev_alir, "
                            "kapali_seanslar) VALUES (?, ?, ?, ?)", yeni)
    return len(yeni)


def nobetten_doldur(db, donem_id: int, ogretmen_ids: Iterable[int] | None = None) -> int:
    """Nöbet, müsaitlik, koordinatörlük ve ders saatlerine denk gelen seansları öğretmenlerin kapalı seanslarına
    ekler (var olanlar korunur). Kapalı seansı değişen öğretmen sayısını döndürür."""
    ogretmenleri_hazirla(db, donem_id)
    kapali = nobet_kapali_seanslar(db, donem_id, ogretmen_ids)
    mevcut = {r["ogretmen_id"]: kume_coz(r["kapali_seanslar"]) for r in db.q(
        "SELECT ogretmen_id, kapali_seanslar FROM sinav_ogretmenleri WHERE donem_id = ?", (donem_id,))}
    degisen = [(_kume_yaz(mevcut.get(t, set()) | k), donem_id, t) for t, k in kapali.items()
               if not k <= mevcut.get(t, set())]
    if degisen:
        with db.conn:
            db.conn.executemany("UPDATE sinav_ogretmenleri SET kapali_seanslar = ? WHERE donem_id = ? AND "
                                "ogretmen_id = ?", degisen)
    return len(degisen)


def ogretmen_listesi(db, donem_id: int) -> list:
    return db.q("""SELECT o.id, o.ad, o.soyad, o.brans, o.unvan, o.alan_id, st.gorev_alir, st.gunluk_azami,
                          st.kapali_seanslar, st.onceki_gorev,
                          (SELECT COUNT(*) FROM sinav_gorevlileri g JOIN sinavlar s ON s.id = g.sinav_id
                           WHERE g.ogretmen_id = o.id AND s.donem_id = st.donem_id) AS gorev_sayisi
                   FROM sinav_ogretmenleri st JOIN ogretmenler o ON o.id = st.ogretmen_id
                   WHERE st.donem_id = ? AND o.aktif = 1 ORDER BY o.ad, o.soyad""", (donem_id,))


def ogretmen_ayarla(db, donem_id: int, ogretmen_id: int, **vals: Any) -> None:
    """vals: gorev_alir, gunluk_azami (None = dönem varsayılanı), kapali_seanslar (kimlik kümesi veya metin),
    onceki_gorev (bu dönemden önce aynı yıl içinde aldığı sınav görevi sayısı)."""
    if "kapali_seanslar" in vals and not isinstance(vals["kapali_seanslar"], str):
        vals["kapali_seanslar"] = _kume_yaz(vals["kapali_seanslar"])
    db.execute("INSERT OR IGNORE INTO sinav_ogretmenleri (donem_id, ogretmen_id) VALUES (?, ?)",
               (donem_id, ogretmen_id))
    if vals:
        db.execute(f"UPDATE sinav_ogretmenleri SET {', '.join(f'{k} = ?' for k in vals)} "
                   "WHERE donem_id = ? AND ogretmen_id = ?", [*vals.values(), donem_id, ogretmen_id])


def ogrenci_kapali_seanslar(db, donem_id: int, ogrenci_id: int) -> set[int]:
    return {r["seans_id"] for r in db.q("SELECT seans_id FROM sinav_ogrenci_kapali WHERE donem_id = ? AND "
                                        "ogrenci_id = ?", (donem_id, ogrenci_id))}


def ogrenci_kapali_ayarla(db, donem_id: int, ogrenci_id: int, seans_ids: Iterable[int]) -> None:
    with db.conn:
        db.conn.execute("DELETE FROM sinav_ogrenci_kapali WHERE donem_id = ? AND ogrenci_id = ?",
                        (donem_id, ogrenci_id))
        db.conn.executemany("INSERT OR IGNORE INTO sinav_ogrenci_kapali (donem_id, ogrenci_id, seans_id) "
                            "VALUES (?, ?, ?)", [(donem_id, ogrenci_id, s) for s in sorted(set(seans_ids))])


def kurallar(db, donem_id: int | None) -> list:
    return db.q("SELECT * FROM sinav_kurallari WHERE donem_id = ? ORDER BY id", (donem_id,)) if donem_id else []


def kural_ekle(db, donem_id: int, ders1: str, ders2: str, tur: str = "ortak_ogrenci") -> int:
    """tur: 'ortak_ogrenci' (ortak öğrencisi varsa aynı güne gelmesin), 'kesin' (öğrencisine bakılmaksızın aynı
    güne gelmesin), 'ayni_seans' (aynı seviyedeki sınavları aynı seansta yapılsın). Aynı iki ders için tek kural
    tutulur; türü farklıysa güncellenir."""
    if tur not in KURAL_TURLERI:
        raise ValueError("Geçersiz kural türü.")
    ders1, ders2 = ders_adi_duzelt(ders1), ders_adi_duzelt(ders2)
    if not ders1 or not ders2 or norm(ders1) == norm(ders2):
        raise ValueError("Birbirinden farklı iki ders seçiniz.")
    for r in kurallar(db, donem_id):
        if {norm(r["ders1"]), norm(r["ders2"])} == {norm(ders1), norm(ders2)}:
            if (r["tur"] or "ortak_ogrenci") != tur:
                db.update("sinav_kurallari", r["id"], {"tur": tur})
            return r["id"]
    return db.insert("sinav_kurallari", {"donem_id": donem_id, "ders1": ders1, "ders2": ders2, "tur": tur})


def kural_sil(db, kural_id: int) -> None:
    db.delete("sinav_kurallari", kural_id)


def gun_kurallari(db, donem_id: int | None) -> list:
    return db.q("SELECT * FROM sinav_gun_kurallari WHERE donem_id = ? ORDER BY id", (donem_id,)) if donem_id else []


def gun_kurali_ekle(db, donem_id: int, tarihler: Iterable[date | str], ders: str | None = None,
                    seviye: int | None = None, kapsam: str = "sinav") -> int:
    """Dersin / seviyenin sınavları yalnız verilen günlerde yapılır. kapsam 'sinav': sınavın seviyesi,
    'ogrenci': sınava giren öğrencinin sınıf seviyesi (ör. 12. sınıf öğrencilerinin sınavları belirli günlerde)."""
    t = sorted({_iso(x) for x in tarihler if _iso(x)})
    ders = ders_adi_duzelt(ders) if ders else ""
    if not t:
        raise ValueError("En az bir sınav günü seçin.")
    if not ders and not seviye:
        raise ValueError("Kural için ders ya da sınıf seviyesi seçin.")
    if kapsam not in ("sinav", "ogrenci"):
        raise ValueError("Geçersiz kural kapsamı.")
    return db.insert("sinav_gun_kurallari", {"donem_id": donem_id, "ders": ders or None, "seviye": seviye or None,
                                             "kapsam": kapsam, "tarihler": ",".join(t)})


def gun_kurali_sil(db, kural_id: int) -> None:
    db.delete("sinav_gun_kurallari", kural_id)


def gun_kurali_etiketi(r: Any) -> str:
    kim = " ".join(x for x in (r["ders"] or "", f"{r['seviye']}. sınıf" if r["seviye"] else "") if x)
    if r["seviye"] and r["kapsam"] == "ogrenci":
        kim = (f"{r['ders']} - " if r["ders"] else "") + f"{r['seviye']}. sınıf öğrencileri"
    gunler = ", ".join(tarih_coz(t).strftime("%d.%m") for t in (r["tarihler"] or "").split(",") if tarih_coz(t))
    return f"{kim}: yalnız {gunler}"


def nobetciler(db, donem_id: int | None) -> dict[str, Any]:
    """Sınav günü -> nöbetçi müdür yardımcısı kaydı (ad ile)."""
    if not donem_id:
        return {}
    return {r["tarih"]: r for r in db.q("SELECT n.*, o.ad || ' ' || o.soyad AS ad, o.unvan FROM sinav_nobetci n "
                                        "JOIN ogretmenler o ON o.id = n.ogretmen_id WHERE n.donem_id = ?", (donem_id,))}


def nobetci_ayarla(db, donem_id: int, tarih: date | str, ogretmen_id: int | None) -> None:
    t = _iso(tarih)
    if not t:
        raise ValueError("Tarih geçersiz.")
    with db.conn:
        db.conn.execute("DELETE FROM sinav_nobetci WHERE donem_id = ? AND tarih = ?", (donem_id, t))
        if ogretmen_id:
            db.conn.execute("INSERT INTO sinav_nobetci (donem_id, tarih, ogretmen_id) VALUES (?, ?, ?)",
                            (donem_id, t, ogretmen_id))


def brans_uyar(brans: str | None, ders: str | None) -> bool:
    """Branş ile ders adı birbirini içeriyor mu ('Matematik' ~ 'Matematik', 'Tarih' ~ 'T.C. İnkılap Tarihi...')."""
    a, b = norm(brans).split(), norm(ders).split()
    return bool(a and b) and (_icerir(a, b) or _icerir(b, a))


def _icerir(kisa: list[str], uzun: list[str]) -> bool:
    L = len(kisa)
    return any(all(uzun[i + j] == kisa[j] or (len(kisa[j]) >= 4 and uzun[i + j].startswith(kisa[j]))
                   for j in range(L)) for i in range(len(uzun) - L + 1))


# ------------------------------------------------------------------ e-Okul OOK12001R012 aktarımı

_OKUL_NO = ["okul no", "ogrenci no", "no", "numara", "numarasi", "okul numarasi", "ogrenci numarasi", "ogr no",
            "okul nosu", "ogrenci okul no"]
_SORUMLU = IceAktarmaTanimi("sinav_sorumlu", "Sorumlu Dersi Olan Öğrenciler ve Dersleri", [
    ("okul_no", "Öğrenci No", _OKUL_NO),
    ("tc", "T.C. Kimlik No", ["tc", "tckn", "tc no", "tc kimlik", "tc kimlik no", "t c kimlik no", "kimlik no",
                              "tc kimlik numarasi", "kimlik numarasi"]),
    ("ad", "Adı", ["ad", "adi", "ogrenci adi", "ogrencinin adi", "isim"]),
    ("soyad", "Soyadı", ["soyad", "soyadi", "ogrenci soyadi", "ogrencinin soyadi", "soyisim"]),
    ("ad_soyad", "Adı Soyadı", ["adi soyadi", "ad soyad", "ad soyadi", "adi ve soyadi", "ogrenci adi soyadi",
                                "ogrencinin adi soyadi", "ogrenci", "ogrenci ad soyad", "ad ve soyad",
                                "ogrencinin adi ve soyadi", "adsoyad"]),
    ("sinif", "Sınıf/Şube", ["sinif", "sinifi", "sube", "subesi", "sinif sube", "sinifi subesi", "sinif ve sube",
                             "sinifi ve subesi", "sinif sube adi", "ogrencinin sinifi", "ogrenci sinifi",
                             "bulundugu sinif", "su anki sinifi"]),
    ("ders", "Ders", ["ders", "dersi", "dersler", "ders adi", "dersin adi", "ders ad", "sorumlu ders",
                      "sorumlu dersi", "sorumlu dersler", "sorumlu dersleri", "sorumlu oldugu ders",
                      "sorumlu oldugu dersler", "sorumlu oldugu dersin adi", "sorumlu oldugu ders adi",
                      "basarisiz ders", "basarisiz dersler", "basarisiz oldugu ders", "basarisiz oldugu dersler"]),
    ("seviye", "Dersin Sınıf Seviyesi", ["seviye", "seviyesi", "sinif seviyesi", "ders seviyesi", "dersin seviyesi",
                                         "dersin sinifi", "dersin sinif seviyesi", "ders sinifi",
                                         "ders sinif seviyesi", "sinif duzeyi", "duzey", "duzeyi",
                                         "sorumlu oldugu sinif", "sorumlu sinif", "alindigi sinif",
                                         "dersin alindigi sinif", "dersin okutuldugu sinif"]),
    ("grup", "Grup", ["grup", "grubu", "grup kodu", "grup adi", "ders grubu", "sinav grubu"]),
], zorunlu=[["ders", "okul_no"], ["ders", "ad_soyad"], ["ders", "ad"], ["ders", "tc"]])
_KIMLIK_ALANLARI = ("okul_no", "tc", "ad", "soyad", "ad_soyad", "sinif")
_ESANLAMLI = {a: {norm(x) for x in [g, *syn]} for a, g, syn in _SORUMLU.alanlar}
_SINIF = r"s[ıiIİ]n[ıiIİ]f\w*"
_SEVIYE_KALIPLARI = [
    re.compile(rf"\(\s*(9|10|11|12)\s*\.?\s*(?:{_SINIF})?\s*\)", re.I),
    re.compile(rf"^\s*(9|10|11|12)\s*\.?\s*{_SINIF}\s*[-–:/]?\s*", re.I),
    re.compile(rf"\s*[-–/:]\s*(9|10|11|12)\s*\.?\s*(?:{_SINIF})?\s*$", re.I),
    re.compile(rf"\s+(9|10|11|12)\s*\.?\s*(?:{_SINIF})?\s*$", re.I),
]


@dataclass
class SorumluKaydi:
    satir: int
    ders: str
    seviye: int | None = None
    grup: str = ""
    okul_no: str = ""
    tc: str = ""
    ad: str = ""
    soyad: str = ""
    ad_soyad: str = ""
    sinif: str = ""

    @property
    def ogrenci_etiketi(self) -> str:
        ad = f"{self.ad} {self.soyad}".strip() or self.ad_soyad
        ek = ", ".join(x for x in (f"No: {self.okul_no}" if self.okul_no else "", self.sinif) if x)
        return f"{tr_ad(ad) or 'Adsız'}" + (f" ({ek})" if ek else "")


@dataclass
class AktarimSonucu:
    kayit: int = 0
    sinav_eklenen: int = 0
    sinav_mevcut: int = 0
    ogrenci_eklenen: int = 0
    ogrenci_mevcut: int = 0
    yeni_ogrenci: int = 0
    yeni_sinif: int = 0
    elenen: int = 0
    eslesmeyen: list[str] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)

    def ozet(self) -> str:
        s = (f"{self.kayit} sorumlu ders satırı okundu. "
             + (f"Tek ders koşulunu (12. sınıf ve tek dersi olan) sağlamayan {self.elenen} öğrenci alınmadı. "
                if self.elenen else "") + f"{self.sinav_eklenen} yeni sınav açıldı"
             f"{f', {self.sinav_mevcut} sınav zaten vardı' if self.sinav_mevcut else ''}. "
             f"Sınavlara {self.ogrenci_eklenen} öğrenci kaydı eklendi"
             f"{f' ({self.ogrenci_mevcut} kayıt zaten vardı)' if self.ogrenci_mevcut else ''}.")
        if self.yeni_ogrenci:
            s += f" {self.yeni_ogrenci} öğrenci" + (f" ve {self.yeni_sinif} sınıf" if self.yeni_sinif else "") + \
                 " yeni oluşturuldu."
        if self.eslesmeyen:
            s += f" {len(self.eslesmeyen)} öğrenci okul kayıtlarında bulunamadı."
        return s


def ders_ve_seviye(s: str) -> tuple[str, int | None]:
    """'MATEMATİK (9. Sınıf)', '9. SINIF MATEMATİK', 'Fizik - 10', 'Kimya 11' -> ('Matematik', 9) ..."""
    s = re.sub(r"\s+", " ", metin(s)).strip()
    for k in _SEVIYE_KALIPLARI:
        m = k.search(s)
        if m:
            kalan = (s[:m.start()] + " " + s[m.end():]).strip()
            if norm(kalan):
                return ders_adi_duzelt(kalan), int(m.group(1))
    return ders_adi_duzelt(s), None


def seviye_coz(v: Any) -> int | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return int(v) if 9 <= v <= 12 or 1 <= v <= 8 else None
    m = re.search(r"\b(1[0-2]|[1-9])\b", norm(v))
    return int(m.group(1)) if m else None


def _ders_parcalari(hucre: str) -> list[str]:
    out, derinlik, parca = [], 0, ""
    for ch in metin(hucre):
        if ch in "([":
            derinlik += 1
        elif ch in ")]":
            derinlik = max(0, derinlik - 1)
        if ch in "\n;," and derinlik == 0:
            out.append(parca)
            parca = ""
        else:
            parca += ch
    out.append(parca)
    return [p.strip() for p in out if norm(p)]


def _etiketli_kimlik(row: list[Any]) -> dict[str, str]:
    """'Öğrenci No: 123', 'Adı Soyadı :' + 'ALİ VELİ' gibi etiket-değer hücreleri."""
    hucreler = [metin(h) for h in row if metin(h)]
    out: dict[str, str] = {}
    i = 0
    while i < len(hucreler):
        h = hucreler[i]
        if ":" in h:
            etiket, deger = h.split(":", 1)
            if not deger.strip() and i + 1 < len(hucreler) and ":" not in hucreler[i + 1]:
                deger = hucreler[i + 1]
                i += 1
            n = norm(etiket)
            alan = next((a for a in _KIMLIK_ALANLARI if n in _ESANLAMLI[a]), None)
            if alan and deger.strip() and alan not in out:
                out[alan] = deger.strip()
        i += 1
    return out


def _etiketli_satir(row: list[Any]) -> bool:
    return any(":" in metin(h) for h in row)


def _baslik_satiri(rows: list[list[Any]], tara: int = 40) -> tuple[int, dict[str, int]]:
    """'Ders' sütunu olan ve en çok alanı eşleşen satır; iki satırlı başlıklar da denenir ('Öğrenci No: 5' gibi
    etiketli satırlar başlık sayılmaz)."""
    en_iyi: tuple[int, dict[str, int]] = (-1, {})
    for i in range(min(tara, len(rows))):
        if _etiketli_satir(rows[i]):
            continue
        es = eslestir(rows[i], _SORUMLU)
        if i > 0 and not _etiketli_satir(rows[i - 1]) and sum(1 for h in rows[i - 1] if metin(h)) >= 2:
            es2 = eslestir(birlesik_baslik(rows[i - 1], rows[i]), _SORUMLU)
            if len(es2) > len(es):
                es = es2
        if "ders" in es and len(es) > len(en_iyi[1]):
            en_iyi = (i, es)
    return en_iyi


def sorumlu_kayitlari(tablo: Tablo) -> tuple[list[SorumluKaydi], list[str]]:
    """OOK12001R012 tablosundan (öğrenci, ders, seviye, grup) kayıtları. Öğrenci hücreleri boş satırlardaki dersler
    bir önceki öğrenciye aittir; öğrenci bilgisi 'Öğrenci No: ...' biçiminde ara satırda da olabilir."""
    rows = tablo.satirlar
    bas, es = _baslik_satiri(rows)
    if bas < 0:
        return [], [f"{tablo.ad or Path(tablo.kaynak).name}: 'Ders' sütunu bulunamadı."]
    baglam = satir_baglamlari(tablo)
    baglam_sinif = next((b["sinif"] for i, b in sorted(baglam.items(), reverse=True) if i < bas and "sinif" in b), "")
    for i in range(bas - 1, -1, -1):
        onceki = _etiketli_kimlik(rows[i])
        if onceki:
            break
    else:
        onceki = {}
    kayitlar: list[SorumluKaydi] = []
    uyarilar: list[str] = []
    gecerli: dict[str, str] | None = onceki if any(onceki.get(k) for k in ("okul_no", "tc", "ad", "ad_soyad")) \
        else None

    def h(row: list[Any], k: str) -> str:
        j = es.get(k)
        return metin(row[j]) if j is not None and j < len(row) else ""

    for i in range(bas + 1, len(rows)):
        row = rows[i]
        if not any(metin(x) for x in row):
            continue
        if "sinif" in baglam.get(i, {}):
            baglam_sinif = baglam[i]["sinif"]
        ders_hucre = h(row, "ders")
        if norm(ders_hucre) in _ESANLAMLI["ders"]:
            continue
        kimlik = {k: h(row, k) for k in _KIMLIK_ALANLARI}
        if not any(kimlik[k] for k in ("okul_no", "tc", "ad", "ad_soyad")):
            etiketli = _etiketli_kimlik(row)
            if any(etiketli.get(k) for k in ("okul_no", "tc", "ad", "ad_soyad")):
                kimlik = {k: etiketli.get(k, "") for k in _KIMLIK_ALANLARI}
                if not ders_hucre or ":" in ders_hucre:
                    gecerli = {**kimlik, "sinif": kimlik["sinif"] or baglam_sinif}
                    continue
        if any(kimlik[k] for k in ("okul_no", "tc", "ad", "ad_soyad")):
            if re.match(r"^(genel )?toplam", norm(kimlik["okul_no"] or kimlik["ad_soyad"] or kimlik["ad"])):
                gecerli = None
                continue
            gecerli = {**kimlik, "sinif": kimlik["sinif"] or baglam_sinif}
        if not ders_hucre:
            continue
        if gecerli is None:
            uyarilar.append(f"Satır {i + 1}: '{ders_hucre}' dersinin öğrencisi belirlenemedi.")
            continue
        sev_hucre = seviye_coz(h(row, "seviye")) if h(row, "seviye") else None
        for parca in _ders_parcalari(ders_hucre):
            ders, sev = ders_ve_seviye(parca)
            if not ders:
                continue
            kayitlar.append(SorumluKaydi(
                i + 1, ders, sev_hucre or sev, h(row, "grup"), metin(gecerli.get("okul_no")),
                re.sub(r"\D", "", metin(gecerli.get("tc"))), tr_ad(gecerli.get("ad")), tr_ad(gecerli.get("soyad")),
                tr_ad(gecerli.get("ad_soyad")), sinif_adi(gecerli.get("sinif")) if gecerli.get("sinif") else ""))
    return kayitlar, uyarilar


class _OgrenciBulucu:
    """Okul no, T.C. kimlik no ve ad soyad (gerekirse sınıfla) eşleştirme."""

    def __init__(self, db):
        self.db = db
        self.no: dict[str, list[int]] = defaultdict(list)
        self.tc: dict[str, list[int]] = defaultdict(list)
        self.ad: dict[str, list[int]] = defaultdict(list)
        self.sinif_adi: dict[int, str] = {}
        self.aktif: dict[int, int] = {}
        for r in db.q("SELECT o.id, o.tc, o.okul_no, o.ad, o.soyad, o.aktif, si.ad AS sinif FROM ogrenciler o "
                      "LEFT JOIN siniflar si ON si.id = o.sinif_id ORDER BY o.aktif DESC, o.id"):
            self._indeksle(r["id"], metin(r["okul_no"]), metin(r["tc"]), f"{r['ad']} {r['soyad']}", r["sinif"] or "")
            self.aktif[r["id"]] = r["aktif"]
        self.siniflar: dict[str, int] = {}
        for r in db.q("SELECT id, ad FROM siniflar ORDER BY id"):
            self.siniflar.setdefault(norm(r["ad"]), r["id"])
            self.siniflar.setdefault(norm(sinif_adi(r["ad"])), r["id"])

    def _indeksle(self, oid: int, no: str, tc: str, ad: str, sinif: str) -> None:
        if no:
            self.no[no.lstrip("0") or no].append(oid)
        if tc:
            self.tc[tc].append(oid)
        if norm(ad):
            self.ad[norm(ad)].append(oid)
        self.sinif_adi[oid] = norm(sinif_adi(sinif))

    @staticmethod
    def _ad(k: SorumluKaydi) -> str:
        return norm(f"{k.ad} {k.soyad}") if k.ad else norm(k.ad_soyad)

    def bul(self, k: SorumluKaydi) -> int | None:
        adlar = self.ad.get(self._ad(k), [])
        if k.okul_no:
            ids = self.no.get(k.okul_no.lstrip("0") or k.okul_no, [])
            if len(ids) == 1 and (not adlar or ids[0] in adlar):
                return ids[0]
            ortak = [i for i in ids if i in adlar]
            if ortak:
                return ortak[0]
        if k.tc and len(self.tc.get(k.tc, [])) == 1:
            return self.tc[k.tc][0]
        if len(adlar) == 1:
            return adlar[0]
        if len(adlar) > 1 and k.sinif:
            ayni = [i for i in adlar if self.sinif_adi.get(i) == norm(k.sinif)]
            if len(ayni) == 1:
                return ayni[0]
            etkin = [i for i in (ayni or adlar) if self.aktif.get(i)]
            if len(etkin) == 1:
                return etkin[0]
        return None

    def olustur(self, c, k: SorumluKaydi, sonuc: AktarimSonucu) -> int:
        ad, soyad = (k.ad, k.soyad) if k.ad else ad_soyad_bol(k.ad_soyad)
        sinif_id = None
        if k.sinif:
            sinif_id = self.siniflar.get(norm(k.sinif))
            if sinif_id is None:
                m = re.match(r"(\d{1,2})", k.sinif)
                seviye = int(m.group(1)) if m and 9 <= int(m.group(1)) <= 12 else 9
                sinif_id = c.execute("INSERT INTO siniflar (ad, seviye) VALUES (?, ?)", (k.sinif, seviye)).lastrowid
                self.siniflar[norm(k.sinif)] = sinif_id
                sonuc.yeni_sinif += 1
        oid = c.execute("INSERT INTO ogrenciler (ad, soyad, tc, okul_no, sinif_id, aktif) VALUES (?, ?, ?, ?, ?, 1)",
                        (ad, soyad, k.tc, k.okul_no, sinif_id)).lastrowid
        self._indeksle(oid, k.okul_no, k.tc, f"{ad} {soyad}", k.sinif)
        self.aktif[oid] = 1
        return oid


def _tek_ders_suz(db, bulucu: _OgrenciBulucu, kayitlar: list[SorumluKaydi]) -> tuple[list[SorumluKaydi], int]:
    """Yalnız tek dersten sorumlu 12. sınıf öğrencilerinin kayıtları; elenen öğrenci sayısıyla."""
    seviye = {r["id"]: r["seviye"] for r in db.q("SELECT o.id, si.seviye FROM ogrenciler o "
                                                 "LEFT JOIN siniflar si ON si.id = o.sinif_id")}
    gruplar: dict[tuple, list[tuple[SorumluKaydi, int | None]]] = defaultdict(list)
    for k in kayitlar:
        oid = bulucu.bul(k)
        gruplar[("id", oid) if oid else ("ad", k.ogrenci_etiketi)].append((k, oid))
    kalan: list[SorumluKaydi] = []
    elenen = 0
    for liste in gruplar.values():
        k0, oid = liste[0]
        sv = seviye.get(oid) if oid else None
        if sv is None:
            m = re.match(r"(\d{1,2})", k0.sinif or "")
            sv = int(m.group(1)) if m else None
        if sv == 12 and len({(norm(k.ders), k.seviye) for k, _ in liste}) == 1:
            kalan += [k for k, _ in liste]
        else:
            elenen += 1
    return kalan, elenen


def sorumlulari_kaydet(db, donem_id: int, kayitlar: list[SorumluKaydi], olustur: bool = False,
                       tur: str = SORUMLULUK, grup_kodu: str = "", ayri: bool = True,
                       tek_ders: bool = False) -> AktarimSonucu:
    """Kayıtları sınavlara işler. Aynı ders + seviye + grup tek sınavdır; yeniden aktarım kayıt çoğaltmaz.
    tur: öğrencinin sınav türü (Sorumluluk / OYS / Tek Ders). grup_kodu dosyadaki bütün sınavların grubuna eklenir
    (ör. okul türü 'EML'). ayri ise OYS sınavları sorumluluk sınavlarından ayrı ('OYS' grubu) açılır. tek_ders ise
    yalnız tek dersten sorumlu 12. sınıf öğrencileri alınır."""
    sonuc = AktarimSonucu(kayit=len(kayitlar))
    bulucu = _OgrenciBulucu(db)
    if tek_ders:
        kayitlar, sonuc.elenen = _tek_ders_suz(db, bulucu, kayitlar)
    ek_grup = [x for x in ((grup_kodu or "").strip(),) if x]
    son_grup = ["OYS"] if tur == OYS and ayri else []
    dersler = _ders_sozlugu(db)
    mevcut = {(norm(r["ders"]), r["seviye"], norm(r["grup"] or "")): r["id"]
              for r in db.q("SELECT id, ders, seviye, grup FROM sinavlar WHERE donem_id = ? ORDER BY id", (donem_id,))}
    var_olan = {(r["sinav_id"], r["ogrenci_id"]) for r in db.q(
        "SELECT so.sinav_id, so.ogrenci_id FROM sinav_ogrencileri so JOIN sinavlar s ON s.id = so.sinav_id "
        "WHERE s.donem_id = ?", (donem_id,))}
    gorulen: set[tuple] = set()
    eslesmeyen: dict[str, None] = {}
    eklenecek: list[tuple[int, int, str]] = []
    tur_yaz: list[tuple[str, int, int]] = []
    c = db.conn
    with c:
        for k in kayitlar:
            oid = bulucu.bul(k)
            if oid is None:
                if not olustur or not (k.ad or k.ad_soyad):
                    eslesmeyen[k.ogrenci_etiketi] = None
                    continue
                oid = bulucu.olustur(c, k, sonuc)
                sonuc.yeni_ogrenci += 1
            grup = "-".join(ek_grup + [x for x in (k.grup.strip(),) if x] + son_grup)
            anahtar = (norm(k.ders), k.seviye, norm(grup))
            sid = mevcut.get(anahtar)
            if sid is None:
                v = _sinav_varsayilanlari(dersler, k.ders)
                sid = c.execute("INSERT INTO sinavlar (donem_id, ders, seviye, grup, alan_id, ders_id) "
                                "VALUES (?, ?, ?, ?, ?, ?)",
                                (donem_id, k.ders, k.seviye, grup, v["alan_id"], v["ders_id"])).lastrowid
                mevcut[anahtar] = sid
                sonuc.sinav_eklenen += 1
            elif anahtar not in gorulen:
                sonuc.sinav_mevcut += 1
            gorulen.add(anahtar)
            if (sid, oid) in var_olan:
                sonuc.ogrenci_mevcut += 1
                tur_yaz.append((tur, sid, oid))
                continue
            var_olan.add((sid, oid))
            eklenecek.append((sid, oid, tur))
        if eklenecek:
            c.executemany("INSERT OR IGNORE INTO sinav_ogrencileri (sinav_id, ogrenci_id, tur) VALUES (?, ?, ?)",
                          eklenecek)
        if tur_yaz:
            c.executemany("UPDATE sinav_ogrencileri SET tur = ? WHERE sinav_id = ? AND ogrenci_id = ? "
                          "AND ifnull(tur, '') = ''", tur_yaz)
    sonuc.ogrenci_eklenen = len(eklenecek)
    sonuc.eslesmeyen = list(eslesmeyen)
    return sonuc


def eokul_sorumlu_aktar(db, donem_id: int, yol: Path | str, olustur: bool = False, **secenek: Any) -> AktarimSonucu:
    """e-Okul OOK12001R012 'Sorumlu Dersi Olan Öğrenciler ve Dersleri' raporunu (xls/xlsx/csv/html/pdf) aktarır.
    secenek: tur, grup_kodu, ayri, tek_ders (bkz. sorumlulari_kaydet)."""
    kayitlar: list[SorumluKaydi] = []
    uyarilar: list[str] = []
    for t in okuyucu.oku(yol):
        k, u = sorumlu_kayitlari(t)
        kayitlar += k
        if k:
            uyarilar += u
    if not kayitlar:
        s = AktarimSonucu()
        s.uyarilar = uyarilar or ["Dosyada öğrenci ve ders sütunları bulunamadı. OOK12001R012 raporunu Excel olarak "
                                  "kaydedip yeniden deneyin."]
        return s
    sonuc = sorumlulari_kaydet(db, donem_id, kayitlar, olustur, **secenek)
    sonuc.uyarilar = uyarilar + sonuc.uyarilar
    return sonuc


# ------------------------------------------------------------------ planlama verisi

@dataclass
class _Ogretmen:
    id: int
    ad: str
    brans: str
    alan_id: int | None
    gorev_alir: bool
    azami: int
    kapali: frozenset[int]


@dataclass
class _Ogrenci:
    id: int
    ad: str
    sinif: str
    seviye: int | None
    okul_no: str = ""
    isletme: frozenset[int] = frozenset()


class _Veri:
    """Dönemin planlama/denetim için gereken bütün kayıtları (tek seferde okunur)."""

    def __init__(self, db, donem_id: int):
        d = donem(db, donem_id)
        if d is None:
            raise ValueError("Sınav dönemi bulunamadı.")
        self.donem = d
        self.ogr_azami = max(1, d["ogrenci_gunluk_azami"] or 2)
        self.ogt_azami = max(1, d["ogretmen_gunluk_azami"] or 3)
        self.komisyon = max(0, d["komisyon_uye_sayisi"] if d["komisyon_uye_sayisi"] is not None else 2)
        self.gozcu_basina = max(1, d["gozcu_ogrenci_sayisi"] or 25)
        self.seanslar = seanslar(db, donem_id)
        self.seans = {r["id"]: r for r in self.seanslar}
        self.sinavlar = db.q("SELECT * FROM sinavlar WHERE donem_id = ? ORDER BY id", (donem_id,))
        self.sinav = {r["id"]: r for r in self.sinavlar}
        self.sinav_ogr: dict[int, list[int]] = defaultdict(list)
        self.yerlesim: dict[tuple[int, int], tuple[int | None, int | None]] = {}
        self.salon_kilitli: set[tuple[int, int]] = set()
        for r in db.q("SELECT so.sinav_id, so.ogrenci_id, so.salon_id, so.sira_no, so.salon_kilitli "
                      "FROM sinav_ogrencileri so JOIN sinavlar s ON s.id = so.sinav_id WHERE s.donem_id = ? "
                      "ORDER BY so.id", (donem_id,)):
            self.sinav_ogr[r["sinav_id"]].append(r["ogrenci_id"])
            self.yerlesim[(r["sinav_id"], r["ogrenci_id"])] = (r["salon_id"], r["sira_no"])
            if r["salon_kilitli"] and r["salon_id"]:
                self.salon_kilitli.add((r["sinav_id"], r["ogrenci_id"]))
        self.ders_yili = ders_yili_icinde(db, d)
        self.ogrenci: dict[int, _Ogrenci] = {}
        for r in db.q("""SELECT o.id, o.ad, o.soyad, o.okul_no, si.ad AS sinif, si.seviye, si.isletme_gunleri
                         FROM ogrenciler o LEFT JOIN siniflar si ON si.id = o.sinif_id
                         WHERE o.id IN (SELECT so.ogrenci_id FROM sinav_ogrencileri so
                                        JOIN sinavlar s ON s.id = so.sinav_id WHERE s.donem_id = ?)""", (donem_id,)):
            ad = f"{r['ad']} {r['soyad']}".strip() + (f" ({r['okul_no']})" if r["okul_no"] else "")
            isl = frozenset(gunler_listesi(r["isletme_gunleri"])) if self.ders_yili else frozenset()
            self.ogrenci[r["id"]] = _Ogrenci(r["id"], ad, r["sinif"] or "", r["seviye"], metin(r["okul_no"]), isl)
        self.ogr_kapali: dict[int, set[int]] = defaultdict(set)
        for r in db.q("SELECT ogrenci_id, seans_id FROM sinav_ogrenci_kapali WHERE donem_id = ?", (donem_id,)):
            self.ogr_kapali[r["ogrenci_id"]].add(r["seans_id"])
        self.ogretmen: dict[int, _Ogretmen] = {}
        for r in db.q("""SELECT o.id, o.ad, o.soyad, o.brans, o.alan_id, o.unvan, st.gorev_alir, st.gunluk_azami,
                                st.kapali_seanslar
                         FROM ogretmenler o LEFT JOIN sinav_ogretmenleri st
                              ON st.ogretmen_id = o.id AND st.donem_id = ?
                         WHERE o.aktif = 1 ORDER BY o.id""", (donem_id,)):
            alir = r["gorev_alir"] if r["gorev_alir"] is not None else (0 if idareci_mi(r["unvan"]) else 1)
            self.ogretmen[r["id"]] = _Ogretmen(
                r["id"], f"{r['ad']} {r['soyad']}", r["brans"] or "", r["alan_id"], bool(alir),
                max(1, r["gunluk_azami"] or self.ogt_azami),
                frozenset(kume_coz(r["kapali_seanslar"]) & set(self.seans)))
        self.kurallar = [(norm(r["ders1"]), norm(r["ders2"]), r["ders1"], r["ders2"], r["tur"] or "ortak_ogrenci")
                         for r in kurallar(db, donem_id)]
        self.gun_kurallari = [(norm(r["ders"]) if r["ders"] else None, r["seviye"], r["kapsam"] or "sinav",
                               {t for t in (r["tarihler"] or "").split(",") if t}) for r in gun_kurallari(db, donem_id)]
        self.salonlar = db.q("SELECT * FROM sinav_salonlari WHERE aktif = 1 ORDER BY sira, id")
        self.salon_kapasitesi = sum(max(0, r["kapasite"] or 0) for r in self.salonlar)
        etkin = {r["id"] for r in self.salonlar}
        self.sinav_salon: dict[int, list[int]] = defaultdict(list)
        for r in db.q("SELECT a.sinav_id, a.salon_id FROM sinav_salon_atamalari a JOIN sinavlar s ON s.id = a.sinav_id "
                      "JOIN sinav_salonlari sl ON sl.id = a.salon_id WHERE s.donem_id = ? ORDER BY sl.sira, sl.id",
                      (donem_id,)):
            if r["salon_id"] in etkin:
                self.sinav_salon[r["sinav_id"]].append(r["salon_id"])
        self.gorevliler = db.q("SELECT g.* FROM sinav_gorevlileri g JOIN sinavlar s ON s.id = g.sinav_id "
                               "WHERE s.donem_id = ? ORDER BY g.id", (donem_id,))
        self.nitelik = self._nitelikler(db)

    def izinli_gunler(self, sinav: Any) -> set[str] | None:
        """Gün kurallarına göre sınavın yapılabileceği tarihler (kural yoksa None)."""
        out: set[str] | None = None
        for ders, seviye, kapsam, tarihler in self.gun_kurallari:
            if ders and ders != norm(sinav["ders"]):
                continue
            if seviye:
                if kapsam == "ogrenci":
                    if not any(self.ogrenci.get(o) and self.ogrenci[o].seviye == seviye
                               for o in self.sinav_ogr.get(sinav["id"], ())):
                        continue
                elif sinav["seviye"] != seviye:
                    continue
            out = set(tarihler) if out is None else out & tarihler
        return out

    def kural_ciftleri(self) -> list[tuple[int, int, str]]:
        """(sınav, sınav, kural türü): 'ortak_ogrenci' ortak öğrencisi olan, 'ayni_seans' aynı seviyedeki sınavlar."""
        ders_sinav: dict[str, list] = defaultdict(list)
        for s in self.sinavlar:
            ders_sinav[norm(s["ders"])].append(s)
        out = []
        for d1, d2, _, _, tur in self.kurallar:
            for a in ders_sinav.get(d1, []):
                for b in ders_sinav.get(d2, []):
                    if a["id"] == b["id"]:
                        continue
                    if tur == "ayni_seans" and a["seviye"] and b["seviye"] and a["seviye"] != b["seviye"]:
                        continue
                    if tur == "ortak_ogrenci" and set(self.sinav_ogr.get(a["id"], ())).isdisjoint(
                            self.sinav_ogr.get(b["id"], ())):
                        continue
                    out.append((a["id"], b["id"], tur))
        return out

    def komisyon_sayisi(self, sinav: Any) -> int:
        return max(0, sinav["komisyon_sayisi"]) if sinav["komisyon_sayisi"] is not None else self.komisyon

    def _nitelikler(self, db) -> dict[int, dict[int, int]]:
        """Sınav -> {öğretmen: öncelik}: 1 dersi okutan, 2 aynı alan, 3 branşı dersle uyuşan."""
        okutan: dict[Any, set[int]] = defaultdict(set)
        for r in db.q("SELECT d.id, d.ad, da.ogretmen_id, da.ogretmen2_id FROM ders_atamalari da "
                      "JOIN dersler d ON d.id = da.ders_id"):
            for t in (r["ogretmen_id"], r["ogretmen2_id"]):
                if t:
                    okutan[norm(r["ad"])].add(t)
                    okutan[("id", r["id"])].add(t)
        out: dict[int, dict[int, int]] = {}
        for s in self.sinavlar:
            p: dict[int, int] = {}
            for t in okutan.get(norm(s["ders"]), set()) | okutan.get(("id", s["ders_id"]), set()):
                if t in self.ogretmen:
                    p[t] = 1
            for t in self.ogretmen.values():
                if t.id in p:
                    continue
                if s["alan_id"] and t.alan_id == s["alan_id"]:
                    p[t.id] = 2
                elif brans_uyar(t.brans, s["ders"]):
                    p[t.id] = 3
            out[s["id"]] = p
        return out

    def gorev_ihtiyaci(self, sinav: Any, ogrenci: int, salon_sayisi: int = 0) -> tuple[int, int]:
        """(komisyon, gözcü) sayısı; sınava özel sayı verilmişse o, yoksa dönem ayarı."""
        kom = self.komisyon_sayisi(sinav)
        if sinav["gozcu_sayisi"] is not None:
            return kom, max(0, sinav["gozcu_sayisi"]) if ogrenci else 0
        if not salon_gerekir(sinav["sekil"]) or not ogrenci:
            return kom, 0
        return kom, salon_sayisi or gozcu_sayisi(ogrenci, self.gozcu_basina)


# ------------------------------------------------------------------ otomatik yerleştirme

W_AYNI_GUN = 12.0
W_12_GUN = 8.0
W_12_SEANS = 1.0
W_ERKEN = 0.02
W_DENGE = 1.0
W_KOMISYON = 30.0
W_BOSLUK = 2.0
W_ISLETME = 25.0

NEDENLER = {
    "kapali": "açık seans yok",
    "ogrenci_kapali": "öğrencilerin kapalı seansları",
    "gun_kurali": "sınav günü kuralı (izin verilen günlerde uygun seans yok)",
    "cakisma": "öğrencilerin aynı seansta başka sınavı var",
    "gunluk": "öğrencilerin günlük sınav sınırı dolu",
    "uygulama": "uygulamalı sınav günü kuralı (o gün başka sınav olamaz)",
    "kural": "'aynı güne gelmesin' kuralı",
    "ayni_seans": "'aynı seansta yapılsın' kuralı",
    "bagli": "bağlı sınav kuralı (yazılının ertesi sınav gününün ilk seansı)",
    "ogretmen": "görevli öğretmen sayısı yetmiyor",
    "salon": "salon kapasitesi yetmiyor",
}
ONERILER = {
    "kapali": "'Seans Çizelgesi' sekmesinde kapalı seansları açın ya da dönem bitişini uzatıp seansları yeniden "
              "oluşturun.",
    "ogrenci_kapali": "'Sınavlar ve Öğrenciler' sekmesinde öğrencilerin kapalı seanslarını azaltın.",
    "gun_kurali": "'Öğretmenler > Gün Kuralları' bölümünde bu sınavın yapılabileceği günleri genişletin.",
    "cakisma": "Çakışan sınavlardan birini başka seansa alın ya da sınav günlerine bir oturum daha ekleyin.",
    "gunluk": "Dönem ayarındaki 'öğrencinin günlük sınav sayısı' sınırını artırın ya da sınav günü ekleyin.",
    "uygulama": "Uygulamalı sınava giren öğrencinin o gün başka sınavı olamaz; sınav günü ekleyin.",
    "kural": "'Aynı güne gelmesin' kuralını gözden geçirin ya da sınav günü ekleyin.",
    "ayni_seans": "'Aynı seansta yapılsın' kuralındaki sınavların ortak öğrencisi olmamalı; kuralı kontrol edin.",
    "bagli": "Bağlı sınavda yazılının ertesi sınav gününün ilk seansı açık ve uygun olmalı; bağlantıyı kontrol edin.",
    "ogretmen": "'Öğretmenler' sekmesinde görev alan öğretmen sayısını veya günlük görev sınırını artırın, kapalı "
                "seansları azaltın ya da sınava özel komisyon/gözcü sayısını düşürün.",
    "salon": "'Salonlar' sekmesinde salon ekleyin veya kapasiteleri artırın.",
}


@dataclass
class SinavNedeni:
    """Yerleşemeyen sınavın ayrıntılı nedeni: hangi engel kaç seansı kapattı, kimlerle çakıştı, ne yapılmalı."""
    sinav_id: int
    etiket: str
    ogrenci: int
    ozet: str
    nedenler: list[str] = field(default_factory=list)
    oneriler: list[str] = field(default_factory=list)

    def metin(self) -> str:
        satirlar = [f"{self.etiket} ({self.ogrenci} öğrenci): {self.ozet}"]
        satirlar += [f"  • {n}" for n in self.nedenler]
        satirlar += [f"  → {o}" for o in self.oneriler]
        return "\n".join(satirlar)


@dataclass
class _PSinav:
    id: int
    ogr: list[int]
    n: int
    uyg: bool
    salon: bool
    gorev: int
    n12: int
    sabit: int | None
    yasak: set[int]
    nitelikli: frozenset[int]
    k: int
    dn: str
    gun_yasak: set[int] = field(default_factory=set)
    gun_cak: set[int] = field(default_factory=set)
    ayni: set[int] = field(default_factory=set)
    bagli: int | None = None
    bagli_ters: list[int] = field(default_factory=list)
    komsu: set[int] = field(default_factory=set)
    dom: list[int] = field(default_factory=list)
    dom_gun: dict[int, list[int]] = field(default_factory=dict)
    isletme: dict[int, int] = field(default_factory=dict)  # haftanın günü -> o gün işletmede olan öğrenci


class _Planlayici:
    def __init__(self, v: _Veri, rng: random.Random, koru: bool = False, gun_siniri: int | None = None):
        """koru: seansı olan sınavlar çakılıymış gibi yerinde kalır. gun_siniri: bu gün sırasından sonraki
        seanslar kapalı sayılır (en az gün araması)."""
        self.v, self.rng = v, rng
        self.azami = v.ogr_azami
        sl = v.seanslar
        self.seans_id = [r["id"] for r in sl]
        sidx = {sid: i for i, sid in enumerate(self.seans_id)}
        gunler = sorted({r["tarih"] for r in sl})
        gidx = {t: i for i, t in enumerate(gunler)}
        self.S, self.G = len(sl), len(gunler)
        self.gun = [gidx[r["tarih"]] for r in sl]
        self.hafta_gunu = [tarih_coz(r["tarih"]).weekday() + 1 for r in sl]
        self.acik = [bool(r["acik"]) and (gun_siniri is None or self.gun[i] <= gun_siniri) for i, r in enumerate(sl)]
        sayac: Counter = Counter()
        self.gun_sira = []
        for r in sl:
            self.gun_sira.append(sayac[r["tarih"]])
            sayac[r["tarih"]] += 1
        ilk_acik: dict[int, int] = {}
        for i in range(self.S):
            if self.acik[i]:
                ilk_acik.setdefault(self.gun[i], i)
        self.sonraki_ilk = [next((ilk_acik[g] for g in range(d + 1, self.G) if g in ilk_acik), -1)
                            for d in range(self.G)]

        gorevli = [t for t in v.ogretmen.values() if t.gorev_alir]
        self.ogretmen_var = bool(gorevli)
        self.musait = [frozenset(t.id for t in gorevli if sid not in t.kapali) for sid in self.seans_id]
        self.kap = [len(m) for m in self.musait]
        self.gun_kap = [0] * self.G
        for t in gorevli:
            say = Counter(self.gun[i] for i in range(self.S) if self.acik[i] and self.seans_id[i] not in t.kapali)
            for d, n in say.items():
                self.gun_kap[d] += min(n, t.azami)
        self.salon_kap = v.salon_kapasitesi

        oidx: dict[int, int] = {}
        self.x: list[_PSinav] = []
        self.ogrencisiz: list[int] = []
        for r in v.sinavlar:
            ogr = v.sinav_ogr.get(r["id"], [])
            if not ogr:
                self.ogrencisiz.append(r["id"])
                continue
            ids = [oidx.setdefault(o, len(oidx)) for o in ogr]
            yasak = {sidx[s] for o in ogr for s in v.ogr_kapali.get(o, ()) if s in sidx}
            izin = v.izinli_gunler(r)
            gun_yasak = {i for i, s in enumerate(sl) if s["tarih"] not in izin} if izin is not None else set()
            kom, goz = v.gorev_ihtiyaci(r, len(ogr))
            nit = frozenset(v.nitelik.get(r["id"], {}))
            sabit = sidx.get(r["seans_id"]) if (r["cakili"] or koru) and r["seans_id"] in sidx else None
            n12 = sum(1 for o in ogr if v.ogrenci.get(o) and v.ogrenci[o].seviye == 12)
            isletme = Counter(g for o in ogr if v.ogrenci.get(o) for g in v.ogrenci[o].isletme)
            self.x.append(_PSinav(r["id"], ids, len(ids), uygulamali(r["sekil"]),
                                  salon_gerekir(r["sekil"]) or bool(v.sinav_salon.get(r["id"])), kom + goz, n12,
                                  sabit, yasak, nit, min(kom, len(nit)), norm(r["ders"]), gun_yasak,
                                  isletme=dict(isletme)))
        self.N = len(oidx)
        self.ogr_id = sorted(oidx, key=oidx.__getitem__)
        self.ogr_sinav: list[list[int]] = [[] for _ in range(self.N)]
        for e, x in enumerate(self.x):
            for st in x.ogr:
                self.ogr_sinav[st].append(e)
        for e, x in enumerate(self.x):
            x.komsu = {f for st in x.ogr for f in self.ogr_sinav[st] if f != e}
            if x.sabit is not None:
                x.dom = [x.sabit]
            else:
                x.dom = [s for s in range(self.S) if self.acik[s] and s not in x.yasak and s not in x.gun_yasak]
            for s in x.dom:
                x.dom_gun.setdefault(self.gun[s], []).append(s)
        eidx = {x.id: e for e, x in enumerate(self.x)}
        for a, b, tur in v.kural_ciftleri():
            e, f = eidx.get(a), eidx.get(b)
            if e is None or f is None:
                continue
            hedef = "ayni" if tur == "ayni_seans" else "gun_cak"
            getattr(self.x[e], hedef).add(f)
            getattr(self.x[f], hedef).add(e)
        for r in v.sinavlar:
            e, f = eidx.get(r["id"]), eidx.get(r["bagli_sinav_id"])
            if e is not None and f is not None and e != f:
                self.x[e].bagli = f
                self.x[f].bagli_ters.append(e)
        for e, x in enumerate(self.x):
            x.komsu |= x.gun_cak | x.ayni | set(x.bagli_ters) | ({x.bagli} if x.bagli is not None else set())
        acik_seans = sum(self.acik) or 1
        self.ort = max(1.0, sum(x.n for x in self.x) / acik_seans)
        self._sifirla()

    # --- durum ---
    def _sifirla(self) -> None:
        self.yer = [-1] * len(self.x)
        self.os: list[dict[int, int]] = [{} for _ in range(self.N)]
        self.og: list[dict[int, int]] = [{} for _ in range(self.N)]
        self.ou: list[dict[int, int]] = [{} for _ in range(self.N)]
        self.seans_sinav: list[set[int]] = [set() for _ in range(self.S)]
        self.seans_n = [0] * self.S
        self.seans_salon = [0] * self.S
        self.seans_gorev = [0] * self.S
        self.gun_gorev = [0] * self.G

    def yerlestir(self, e: int, s: int) -> None:
        x = self.x[e]
        self.yer[e] = s
        d = self.gun[s]
        for st in x.ogr:
            c = self.os[st]
            c[s] = c.get(s, 0) + 1
            g = self.og[st]
            g[d] = g.get(d, 0) + 1
            if x.uyg:
                u = self.ou[st]
                u[d] = u.get(d, 0) + 1
        self.seans_sinav[s].add(e)
        self.seans_n[s] += x.n
        if x.salon:
            self.seans_salon[s] += x.n
        self.seans_gorev[s] += x.gorev
        self.gun_gorev[d] += x.gorev

    def kaldir(self, e: int) -> None:
        s = self.yer[e]
        if s < 0:
            return
        x = self.x[e]
        d = self.gun[s]
        for st in x.ogr:
            for c, k in ((self.os[st], s), (self.og[st], d)) + (((self.ou[st], d),) if x.uyg else ()):
                if c.get(k, 0) <= 1:
                    c.pop(k, None)
                else:
                    c[k] -= 1
        self.seans_sinav[s].discard(e)
        self.seans_n[s] -= x.n
        if x.salon:
            self.seans_salon[s] -= x.n
        self.seans_gorev[s] -= x.gorev
        self.gun_gorev[d] -= x.gorev
        self.yer[e] = -1

    def _geri_yukle(self, yer: list[int]) -> None:
        self._sifirla()
        for e, s in enumerate(yer):
            if s >= 0:
                self.yerlestir(e, s)

    # --- kısıtlar ve maliyet ---
    def engel(self, e: int, s: int) -> str | None:
        x = self.x[e]
        if x.sabit is None:
            if not self.acik[s]:
                return "kapali"
            if s in x.yasak:
                return "ogrenci_kapali"
            if s in x.gun_yasak:
                return "gun_kurali"
        d = self.gun[s]
        az = self.azami
        os_, og, ou = self.os, self.og, self.ou
        for st in x.ogr:
            if s in os_[st]:
                return "cakisma"
            g = og[st].get(d, 0)
            if g:
                if g >= az:
                    return "gunluk"
                if x.uyg or ou[st].get(d):
                    return "uygulama"
        for f in x.gun_cak:
            y = self.yer[f]
            if y >= 0 and self.gun[y] == d:
                return "kural"
        for f in x.ayni:
            y = self.yer[f]
            if y >= 0 and y != s:
                return "ayni_seans"
        if x.bagli is not None:
            y = self.yer[x.bagli]
            if y >= 0 and self.sonraki_ilk[self.gun[y]] != s:
                return "bagli"
        for f in x.bagli_ters:
            y = self.yer[f]
            if self.sonraki_ilk[d] < 0 or (y >= 0 and y != self.sonraki_ilk[d]):
                return "bagli"
        if self.ogretmen_var and (self.seans_gorev[s] + x.gorev > self.kap[s]
                                  or self.gun_gorev[d] + x.gorev > self.gun_kap[d]):
            return "ogretmen"
        if self.salon_kap and x.salon and self.seans_salon[s] + x.n > self.salon_kap:
            return "salon"
        return None

    def maliyet(self, e: int, s: int) -> float:
        x = self.x[e]
        d = self.gun[s]
        og, os_, gun, gs = self.og, self.os, self.gun, self.gun_sira
        sira = gs[s]
        ayni = bosluk = 0
        for st in x.ogr:
            n = og[st].get(d, 0)
            if n:
                ayni += n
                for s2 in os_[st]:
                    if gun[s2] == d and s2 != s:
                        bosluk += abs(sira - gs[s2]) - 1
        c = W_AYNI_GUN * ayni + W_BOSLUK * bosluk + W_ERKEN * x.n * s
        if x.isletme:
            c += W_ISLETME * x.isletme.get(self.hafta_gunu[s], 0)
        if x.n12:
            c += x.n12 * (W_12_GUN * d + W_12_SEANS * self.gun_sira[s])
        L = self.seans_n[s]
        c += W_DENGE * (2 * L * x.n + x.n * x.n) / (2 * self.ort)
        if x.k and self.ogretmen_var:
            m = self.musait[s]
            av = x.nitelikli & m
            if len(av) < x.k:
                c += W_KOMISYON * (x.k - len(av))
            for f in self.seans_sinav[s]:
                y = self.x[f]
                if f != e and y.k and not x.nitelikli.isdisjoint(y.nitelikli):
                    ortak = len(av | (y.nitelikli & m))
                    if ortak < x.k + y.k:
                        c += W_KOMISYON * (x.k + y.k - ortak)
        return c

    def toplam_maliyet(self) -> float:
        c = 0.0
        for g in self.og:
            c += W_AYNI_GUN * sum(n * (n - 1) / 2 for n in g.values())
        for o in self.os:
            if len(o) > 1:
                k = sorted(o)
                for i, a in enumerate(k):
                    for b in k[i + 1:]:
                        if self.gun[a] == self.gun[b]:
                            c += W_BOSLUK * max(0, abs(self.gun_sira[a] - self.gun_sira[b]) - 1)
        for e, x in enumerate(self.x):
            s = self.yer[e]
            if s < 0:
                continue
            c += W_ERKEN * x.n * s + x.n12 * (W_12_GUN * self.gun[s] + W_12_SEANS * self.gun_sira[s])
            c += W_ISLETME * x.isletme.get(self.hafta_gunu[s], 0)
            if x.k and self.ogretmen_var:
                m = self.musait[s]
                av = x.nitelikli & m
                c += W_KOMISYON * max(0, x.k - len(av))
                for f in self.seans_sinav[s]:
                    y = self.x[f]
                    if f > e and y.k and not x.nitelikli.isdisjoint(y.nitelikli):
                        c += W_KOMISYON * max(0, x.k + y.k - len(av | (y.nitelikli & m)))
        c += W_DENGE * sum(L * L for L in self.seans_n) / (2 * self.ort)
        return c

    def _en_iyi(self, e: int) -> int | None:
        en, en_s = math.inf, None
        rnd = self.rng.random
        for s in self.x[e].dom:
            if self.engel(e, s) is None:
                c = self.maliyet(e, s) + rnd() * 1e-3
                if c < en:
                    en, en_s = c, s
        return en_s

    def _gun_uygun(self, e: int, d: int) -> int:
        return sum(1 for s in self.x[e].dom_gun.get(d, ()) if self.engel(e, s) is None)

    # --- kurulum: DSatur benzeri açgözlü sıralama ---
    def kur(self) -> set[int]:
        self._sifirla()
        bekleyen = set()
        for e, x in enumerate(self.x):
            if x.sabit is not None:
                self.yerlestir(e, x.sabit)
            else:
                bekleyen.add(e)
        gun_say = {e: {d: self._gun_uygun(e, d) for d in self.x[e].dom_gun} for e in bekleyen}
        kalan = {e: sum(g.values()) for e, g in gun_say.items()}
        rnd = {e: self.rng.random() for e in bekleyen}
        yerlesmeyen: set[int] = set()
        while bekleyen:
            e = min(bekleyen, key=lambda e: (kalan[e], -len(self.x[e].komsu), -(self.x[e].n12 > 0), -self.x[e].n,
                                             rnd[e]))
            bekleyen.discard(e)
            s = self._en_iyi(e)
            if s is None:
                yerlesmeyen.add(e)
                continue
            self.yerlestir(e, s)
            d = self.gun[s]
            for f in self.x[e].komsu:
                if f in bekleyen and d in gun_say[f]:
                    yeni = self._gun_uygun(f, d)
                    kalan[f] += yeni - gun_say[f][d]
                    gun_say[f][d] = yeni
        return yerlesmeyen

    # --- onarım: yerleşemeyen sınava yer açma (tabu destekli en az çatışma) ---
    def _engelleyenler(self, e: int, s: int) -> set[int] | None:
        x = self.x[e]
        if x.sabit is None and (not self.acik[s] or s in x.yasak or s in x.gun_yasak):
            return None
        d = self.gun[s]
        if x.bagli_ters and self.sonraki_ilk[d] < 0:
            return None
        bl: set[int] = set()
        for f in x.ayni:
            if self.yer[f] >= 0 and self.yer[f] != s:
                bl.add(f)
        if x.bagli is not None and self.yer[x.bagli] >= 0 and self.sonraki_ilk[self.gun[self.yer[x.bagli]]] != s:
            bl.add(x.bagli)
        for f in x.bagli_ters:
            if self.yer[f] >= 0 and self.yer[f] != self.sonraki_ilk[d]:
                bl.add(f)
        for st in x.ogr:
            gunluk = []
            for f in self.ogr_sinav[st]:
                y = self.yer[f]
                if f == e or y < 0:
                    continue
                if y == s:
                    bl.add(f)
                elif self.gun[y] == d:
                    if x.uyg or self.x[f].uyg:
                        bl.add(f)
                    else:
                        gunluk.append(f)
            kalan_gunluk = [f for f in gunluk if f not in bl]
            fazla = len(kalan_gunluk) + 1 - self.azami
            if fazla > 0:
                bl.update(sorted(kalan_gunluk, key=lambda f: self.x[f].n)[:fazla])
        for f in x.gun_cak:
            y = self.yer[f]
            if y >= 0 and self.gun[y] == d:
                bl.add(f)
        if any(self.x[f].sabit is not None for f in bl):
            return None
        gorev = self.seans_gorev[s] - sum(self.x[f].gorev for f in bl if self.yer[f] == s) + x.gorev
        salon = self.seans_salon[s] - sum(self.x[f].n for f in bl if self.yer[f] == s and self.x[f].salon) + \
            (x.n if x.salon else 0)
        if self.ogretmen_var or self.salon_kap:
            for f in sorted(self.seans_sinav[s] - bl, key=lambda f: -self.x[f].n):
                gorev_asim = self.ogretmen_var and gorev > self.kap[s]
                salon_asim = self.salon_kap and x.salon and salon > self.salon_kap
                if not gorev_asim and not salon_asim:
                    break
                if self.x[f].sabit is not None:
                    continue
                bl.add(f)
                gorev -= self.x[f].gorev
                salon -= self.x[f].n if self.x[f].salon else 0
            if (self.ogretmen_var and gorev > self.kap[s]) or (self.salon_kap and x.salon and salon > self.salon_kap):
                return None
            gun_gorev = self.gun_gorev[d] - sum(self.x[f].gorev for f in bl if self.gun[self.yer[f]] == d) + x.gorev
            if self.ogretmen_var and gun_gorev > self.gun_kap[d]:
                return None
        return bl

    def onar(self, yerlesmeyen: set[int], bitis: float, azami_tur: int) -> set[int]:
        U = set(yerlesmeyen)
        umutsuz: set[int] = set()
        tabu: dict[int, int] = {}
        en_iyi = (len(U), self.toplam_maliyet(), list(self.yer))
        tur = 0
        while U - umutsuz and tur < azami_tur and time.monotonic() < bitis:
            tur += 1
            e = self.rng.choice(sorted(U - umutsuz))
            aday = None
            for s in self.x[e].dom:
                bl = self._engelleyenler(e, s)
                if bl is None:
                    continue
                puan = sum(1.0 + (4.0 if tabu.get(f, -100) > tur - 15 else 0.0) + 0.05 * len(self.x[f].komsu)
                           for f in bl) + self.rng.random() * 0.5
                if aday is None or puan < aday[0]:
                    aday = (puan, s, bl)
            if aday is None:
                umutsuz.add(e)
                continue
            _, s, bl = aday
            for f in bl:
                self.kaldir(f)
                U.add(f)
            self.yerlestir(e, s)
            U.discard(e)
            tabu[e] = tur
            for f in sorted(bl, key=lambda f: (-len(self.x[f].komsu), self.x[f].id)):
                t = self._en_iyi(f)
                if t is not None:
                    self.yerlestir(f, t)
                    U.discard(f)
            if len(U) < en_iyi[0]:
                en_iyi = (len(U), self.toplam_maliyet(), list(self.yer))
        if len(U) > en_iyi[0]:
            self._geri_yukle(en_iyi[2])
            U = {e for e, s in enumerate(self.yer) if s < 0}
        return U

    # --- iyileştirme: sınavı daha az maliyetli seansa taşıma ---
    def iyilestir(self, bitis: float, azami_tur: int) -> int:
        tasinabilir = [e for e, x in enumerate(self.x) if x.sabit is None and self.yer[e] >= 0]
        if not tasinabilir:
            return 0
        iyilesme, durgun, tur = 0, 0, 0
        while tur < azami_tur and durgun < 2 * len(tasinabilir) and time.monotonic() < bitis:
            tur += 1
            e = self.rng.choice(tasinabilir)
            s0 = self.yer[e]
            self.kaldir(e)
            en_s, en_c = s0, self.maliyet(e, s0)
            for s in self.x[e].dom:
                if s != s0 and self.engel(e, s) is None:
                    c = self.maliyet(e, s)
                    if c < en_c - 1e-6:
                        en_s, en_c = s, c
            self.yerlestir(e, en_s)
            if en_s != s0:
                iyilesme += 1
                durgun = 0
            else:
                durgun += 1
        return iyilesme

    def neden(self, e: int) -> str:
        x = self.x[e]
        if not x.dom:
            if not any(self.acik):
                return NEDENLER["kapali"]
            acik = {s for s in range(self.S) if self.acik[s]}
            return NEDENLER["gun_kurali"] if acik - x.yasak else NEDENLER["ogrenci_kapali"]
        say = Counter(self.engel(e, s) for s in self.x[e].dom)
        say.pop(None, None)
        return ", ".join(NEDENLER[k] for k, _ in say.most_common(2)) or "uygun seans bulunamadı"

    def _ad(self, f: int) -> str:
        return sinav_adi(self.v.sinav[self.x[f].id])

    def tani(self, e: int) -> SinavNedeni:
        """Her seansı neyin kapattığını sayar; engel olan sınavları, sınav yükü açık günlere sığmayan öğrencileri,
        görevli/salon açığını ve yapılabilecekleri listeler."""
        x, v = self.x[e], self.v
        say: Counter = Counter()
        if x.sabit is None:
            for s in range(self.S):
                if not self.acik[s]:
                    say["kapali"] += 1
                elif s in x.yasak:
                    say["ogrenci_kapali"] += 1
                elif s in x.gun_yasak:
                    say["gun_kurali"] += 1
        diger: dict[str, Counter] = defaultdict(Counter)
        bos_gorev = bos_salon = 0
        for s in x.dom:
            k = self.engel(e, s)
            if k is None:
                continue
            say[k] += 1
            d = self.gun[s]
            if k in ("cakisma", "gunluk", "uygulama"):
                diger[k].update({f for st in x.ogr for f in self.ogr_sinav[st] if f != e and self.yer[f] >= 0 and (
                    self.yer[f] == s if k == "cakisma" else self.gun[self.yer[f]] == d)})
            elif k == "kural":
                diger[k].update(f for f in x.gun_cak if self.yer[f] >= 0 and self.gun[self.yer[f]] == d)
            elif k == "ayni_seans":
                diger[k].update(f for f in x.ayni if self.yer[f] >= 0 and self.yer[f] != s)
            elif k == "ogretmen":
                bos_gorev = max(bos_gorev, min(self.kap[s] - self.seans_gorev[s], self.gun_kap[d] - self.gun_gorev[d]))
            elif k == "salon":
                bos_salon = max(bos_salon, self.salon_kap - self.seans_salon[s])
        acik_gun = Counter(self.gun[s] for s in range(self.S) if self.acik[s])
        kapasite = sum(min(self.azami, n) for n in acik_gun.values())
        yuklu = []
        for st in x.ogr:
            sinavlar = self.ogr_sinav[st]
            u = sum(1 for f in sinavlar if self.x[f].uyg)
            gerek = u + math.ceil((len(sinavlar) - u) / self.azami)
            if len(sinavlar) > kapasite or gerek > len(acik_gun):
                yuklu.append((st, len(sinavlar), gerek))

        nedenler = []
        for k, n in say.most_common():
            satir = f"{NEDENLER[k][0].upper()}{NEDENLER[k][1:]}: {n} seans"
            if diger.get(k):
                adlar = [self._ad(f) for f, _ in diger[k].most_common(3)]
                satir += f" (engel olan: {', '.join(adlar)}{' ...' if len(diger[k]) > 3 else ''})"
            elif k == "ogretmen":
                satir += (f" (sınav {x.gorev} görevli ister; uygun seanslarda en çok {max(0, bos_gorev)} öğretmen "
                          f"boşta)")
            elif k == "salon":
                satir += (f" ({x.n} öğrenci; uygun seanslarda en çok {max(0, bos_salon)} kişilik yer boş, toplam "
                          f"salon kapasitesi {self.salon_kap})")
            nedenler.append(satir)
        for st, n, g in yuklu[:3]:
            o = v.ogrenci.get(self.ogr_id[st])
            ad = f"{o.ad} ({o.sinif})" if o and o.sinif else (o.ad if o else "Bir öğrenci")
            nedenler.append(f"{ad}: {n} sınavı var; günde en çok {self.azami} sınavla en az {g} sınav günü gerekir, "
                            f"açık sınav günü {len(acik_gun)}.")
        if len(yuklu) > 3:
            nedenler.append(f"Sınav yükü sığmayan {len(yuklu) - 3} öğrenci daha var.")

        if yuklu:
            ozet = f"{len(yuklu)} öğrencinin sınav yükü açık sınav günlerine sığmıyor."
        elif not x.dom:
            ozet = "Sınavın girebileceği açık seans yok."
        elif say:
            ilk = NEDENLER[say.most_common(1)[0][0]]
            ozet = f"{len(x.dom)} aday seansın hiçbirine yerleşemedi; başlıca engel: {ilk}."
        else:
            ozet = "Uygun seans bulunamadı."
        oneriler = []
        if yuklu:
            oneriler.append("Sınav günü ekleyin veya öğrencinin günlük sınav sınırını artırın; gerekirse öğrencinin "
                            "bazı sınavlarını sonraki döneme bırakın.")
        oneriler += [ONERILER[k] for k, _ in say.most_common() if ONERILER[k] not in oneriler]
        return SinavNedeni(x.id, self._ad(e), x.n, ozet, nedenler, oneriler)


@dataclass
class PlanSonucu:
    toplam: int = 0
    yerlesen: int = 0
    cakili: int = 0
    korunan: int = 0
    ogrencisiz: int = 0
    yerlesemeyen: list[tuple[int, str, str]] = field(default_factory=list)  # (sınav, ad, neden)
    nedenler: list[SinavNedeni] = field(default_factory=list)
    degisen: int = 0
    maliyet: float = 0.0
    sure: float = 0.0
    notlar: list[str] = field(default_factory=list)

    def ozet(self) -> str:
        s = (f"{self.toplam} sınavdan {self.yerlesen} tanesi seanslara yerleştirildi"
             f"{f' ({self.cakili} çakılı sınav yerinde bırakıldı)' if self.cakili else ''}"
             f"{f' ({self.korunan} yerleşmiş sınav korundu)' if self.korunan else ''}.")
        if self.yerlesemeyen:
            s += f" {len(self.yerlesemeyen)} sınav yerleştirilemedi."
        if self.ogrencisiz:
            s += f" Öğrencisi olmayan {self.ogrencisiz} sınav planlanmadı."
        return s + f" Süre: {self.sure:.1f} sn."


def planla(db, donem_id: int, sure_limit: float = 10.0, seed: int | None = None, koru: bool = False) -> PlanSonucu:
    """Çakılı olmayan sınavları seanslara yerleştirir. Yerleşemeyenlerin seansı boş kalır ve nedeni raporlanır.
    koru ise seansa yerleşmiş sınavlar yerinde kalır, yalnız yerleşmemişler yerleştirilir."""
    bas = time.monotonic()
    bitis = bas + max(0.5, sure_limit)
    v = _Veri(db, donem_id)
    sonuc = PlanSonucu(toplam=len(v.sinavlar))
    rng = random.Random(seed)
    p = _Planlayici(v, rng, koru=koru)
    if not p.S:
        raise ValueError("Bu dönem için seans yok. Önce 'Seans Çizelgesi' sekmesinden seansları oluşturun.")
    if not any(p.acik):
        raise ValueError("Açık seans yok. Seans çizelgesinden en az bir seansı açın.")
    if not p.ogretmen_var:
        sonuc.notlar.append("Görev alacak öğretmen tanımlı değil; görevli sayısı denetlenmedi.")
    if not p.salon_kap:
        sonuc.notlar.append("Etkin salon tanımlı değil; salon kapasitesi denetlenmedi.")
    for e, x in enumerate(p.x):
        if x.sabit is None and v.sinav[x.id]["cakili"]:
            sonuc.notlar.append(f"{sinav_adi(v.sinav[x.id])}: çakılı seansı bulunamadı, yeniden yerleştirildi.")

    yerlesmeyen = p.kur()
    M = len(p.x)
    if yerlesmeyen:
        yerlesmeyen = p.onar(yerlesmeyen, bitis, 60 * M + 200)
    p.iyilestir(bitis, 25 * M + 100)

    eski = {r["id"]: r["seans_id"] for r in v.sinavlar}
    yeni: dict[int, int | None] = {}
    for e, x in enumerate(p.x):
        yeni[x.id] = p.seans_id[p.yer[e]] if p.yer[e] >= 0 else None
    for sid in p.ogrencisiz:
        if not (v.sinav[sid]["cakili"] or koru):
            yeni[sid] = None
    degisen = [sid for sid, s in yeni.items() if s != eski[sid] and not (v.sinav[sid]["cakili"] and
                                                                         v.sinav[sid]["seans_id"] in v.seans)]
    etkilenen_seans = {eski[sid] for sid in degisen} | {yeni[sid] for sid in degisen}
    etkilenen_seans.discard(None)
    salon_sifir = sorted({r["id"] for r in v.sinavlar if r["seans_id"] in etkilenen_seans} - set(degisen))
    c = db.conn
    with c:
        c.executemany("UPDATE sinavlar SET seans_id = ?, cakili = 0 WHERE id = ?",
                      [(yeni[sid], sid) for sid in degisen])
        for i in range(0, len(degisen), 500):
            parca = degisen[i:i + 500]
            ph = ','.join('?' * len(parca))
            c.execute(f"DELETE FROM sinav_gorevlileri WHERE kilitli = 0 AND sinav_id IN ({ph})", parca)
            c.execute(f"UPDATE sinav_ogrencileri SET salon_id = NULL, sira_no = NULL, salon_kilitli = 0 "
                      f"WHERE sinav_id IN ({ph})", parca)
        for i in range(0, len(salon_sifir), 500):
            parca = salon_sifir[i:i + 500]
            c.execute(f"UPDATE sinav_ogrencileri SET salon_id = NULL, sira_no = NULL "
                      f"WHERE salon_kilitli = 0 AND sinav_id IN ({','.join('?' * len(parca))})", parca)
    sonuc.degisen = len(degisen)
    sonuc.korunan = sum(1 for x in p.x if x.sabit is not None and not v.sinav[x.id]["cakili"])
    sonuc.cakili = sum(1 for x in p.x if x.sabit is not None) - sonuc.korunan
    sonuc.ogrencisiz = len(p.ogrencisiz)
    sonuc.yerlesen = sum(1 for s in p.yer if s >= 0)
    sirali = sorted(yerlesmeyen, key=lambda e: p.x[e].id)
    sonuc.yerlesemeyen = [(p.x[e].id, sinav_adi(v.sinav[p.x[e].id]), p.neden(e)) for e in sirali]
    sonuc.nedenler = [p.tani(e) for e in sirali]
    sonuc.maliyet = round(p.toplam_maliyet(), 1)
    if yerlesmeyen:
        sonuc.notlar += _ek_analiz(v, seed, koru, time.monotonic() + min(8.0, max(2.0, sure_limit / 2)))
    sonuc.sure = time.monotonic() - bas
    return sonuc


def _sanal_gunler(v: _Veri, k: int) -> tuple[list[dict], date]:
    """Son açık sınav gününün oturum düzeniyle sonraki k iş gününe sanal seanslar (yalnız deneme için)."""
    acik = [r for r in v.seanslar if r["acik"]]
    son = max(r["tarih"] for r in acik)
    desen = [r for r in acik if r["tarih"] == son]
    t = tarih_coz(son)
    yeni: list[dict] = []
    for _ in range(k):
        t += timedelta(days=1)
        while t.weekday() >= 5:
            t += timedelta(days=1)
        for r in desen:
            yeni.append({"id": -1 - len(yeni), "tarih": t.isoformat(), "sira": r["sira"],
                         "baslangic": r["baslangic"], "bitis": r["bitis"], "acik": 1})
    return yeni, t


def _ek_analiz(v: _Veri, seed: int | None, koru: bool, bitis: float) -> list[str]:
    """Sınav yerleşemediğinde: kaç sınav günü daha eklenirse ya da öğrencinin günlük sınırı bir artarsa bütün
    sınavların sığdığı (plan değişmez)."""
    import copy

    def sigar(v2: _Veri) -> bool:
        p = _Planlayici(v2, random.Random(seed), koru=koru)
        U = p.kur()
        if U:
            U = p.onar(U, min(bitis, time.monotonic() + 3.0), 30 * len(p.x) + 100)
        return not U

    notlar = []
    if not any(r["acik"] for r in v.seanslar):
        return notlar
    for k in (1, 2, 3, 5):
        if time.monotonic() >= bitis:
            break
        yeni, son = _sanal_gunler(v, k)
        v2 = copy.copy(v)
        v2.seanslar = list(v.seanslar) + yeni
        v2.seans = {**v.seans, **{r["id"]: r for r in yeni}}
        if sigar(v2):
            notlar.append(f"Öneri: dönem {k} sınav günü uzatılırsa (son gün {son:%d.%m.%Y} {GUN_ADLARI[son.weekday()]}, "
                          f"son günün oturum düzeniyle; resmî tatilleri kontrol edin) bütün sınavlar yerleşiyor.")
            break
    else:
        if time.monotonic() < bitis:
            notlar.append("Dönemi 5 sınav günü uzatmak da yetmiyor; yerleşemeyen sınavların nedenlerine bakın.")
    if time.monotonic() < bitis:
        v3 = copy.copy(v)
        v3.ogr_azami = v.ogr_azami + 1
        if sigar(v3):
            notlar.append(f"Öneri: öğrencinin günlük sınav sınırı {v.ogr_azami} yerine {v.ogr_azami + 1} yapılırsa "
                          f"bütün sınavlar mevcut günlere sığıyor.")
    return notlar


def yerlesmeme_nedenleri(db, donem_id: int) -> list[SinavNedeni]:
    """Seansı olmayan (öğrencisi olan) sınavların mevcut plana göre neden yerleşemediği. Veritabanını değiştirmez."""
    v = _Veri(db, donem_id)
    p = _Planlayici(v, random.Random(0), koru=True)
    for e, x in enumerate(p.x):
        if x.sabit is not None:
            p.yerlestir(e, x.sabit)
    return [p.tani(e) for e, x in enumerate(p.x) if x.sabit is None]


@dataclass
class EnAzGunSonucu:
    gun: int | None = None
    toplam_gun: int = 0
    son_tarih: str | None = None
    denemeler: list[tuple[int, int, int]] = field(default_factory=list)  # (gün sayısı, yerleşen, sınav)
    sure: float = 0.0

    def ozet(self) -> str:
        if self.gun is None:
            return (f"Sınavlar dönemin {self.toplam_gun} sınav gününe de sığdırılamadı; önce 'Sınavları Yerleştir' "
                    f"ile yerleşemeyen sınavların nedenlerine bakın.")
        s = (f"Sınavlar en az {self.gun} sınav gününde yapılabilir (dönemde {self.toplam_gun} sınav günü var; son gün "
             f"{tarih_coz(self.son_tarih).strftime('%d.%m.%Y')} {gun_adi(self.son_tarih)}).")
        if self.gun < self.toplam_gun:
            s += " Gerekirse son günlerin seanslarını kapatıp planı yeniden yapabilirsiniz."
        return s + f" Plan değiştirilmedi. Süre: {self.sure:.1f} sn."


def en_az_gun(db, donem_id: int, sure_limit: float = 20.0, seed: int | None = None) -> EnAzGunSonucu:
    """Bütün sınavların sığdığı en az sınav günü sayısını arar (ilk k sınav günü). Veritabanını değiştirmez."""
    bas = time.monotonic()
    v = _Veri(db, donem_id)
    tam = _Planlayici(v, random.Random(seed))
    gunler = sorted({r["tarih"] for r in v.seanslar})
    acik_gunler = sorted({tam.gun[i] for i in range(tam.S) if tam.acik[i]})
    if not acik_gunler:
        raise ValueError("Açık seans yok. Seans çizelgesinden en az bir seansı açın.")
    sonuc = EnAzGunSonucu(toplam_gun=len(acik_gunler))
    if not tam.x:
        raise ValueError("Öğrencisi olan sınav yok.")
    alt = max([1] + [math.ceil(len(s) / tam.azami) for s in tam.ogr_sinav] +
              [sum(1 for g in acik_gunler if g <= tam.gun[x.sabit]) for x in tam.x if x.sabit is not None])
    alt = min(alt, len(acik_gunler))
    tur = 2 + max(1, math.ceil(math.log2(len(acik_gunler) - alt + 1)))
    pay = max(0.3, sure_limit / tur)
    M = len(tam.x)

    def sigar(k: int) -> bool:
        p = _Planlayici(v, random.Random(seed), gun_siniri=acik_gunler[k - 1])
        U = p.kur()
        if U:
            U = p.onar(U, time.monotonic() + pay, 60 * M + 200)
        sonuc.denemeler.append((k, M - len(U), M))
        return not U

    if not sigar(len(acik_gunler)):
        sonuc.sure = time.monotonic() - bas
        return sonuc
    lo, hi = alt, len(acik_gunler)
    while lo < hi:
        orta = (lo + hi) // 2
        if sigar(orta):
            hi = orta
        else:
            lo = orta + 1
    sonuc.gun = hi
    sonuc.son_tarih = gunler[acik_gunler[hi - 1]]
    sonuc.sure = time.monotonic() - bas
    return sonuc


# ------------------------------------------------------------------ görevlendirme

@dataclass
class GorevSonucu:
    atanan: int = 0
    kilitli: int = 0
    sinav: int = 0
    eksik: list[str] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)
    yuk: dict[int, int] = field(default_factory=dict)

    def ozet(self) -> str:
        s = f"{self.sinav} sınava {self.atanan} görev verildi"
        if self.kilitli:
            s += f" ({self.kilitli} kilitli görev korundu)"
        s += "."
        if self.yuk:
            s += f" Öğretmen başına görev: en az {min(self.yuk.values())}, en çok {max(self.yuk.values())}."
        if self.eksik:
            s += f" {len(self.eksik)} sınavda görevli eksik."
        return s


def gorevlileri_ata(db, donem_id: int, seed: int | None = None) -> GorevSonucu:
    """Yerleşmiş her sınava komisyon (ilki başkan) ve gözcü atar; kilitli görevler korunur.
    Komisyon: dersi okutan > aynı alan > branşı uyan öğretmen; gözcü: tercihen dersle ilgisi olmayan öğretmen.
    Öğretmen kapalı seansında, aynı seansta ikinci kez ve günlük sınırın üstünde görev almaz; görevler en az
    yüklü öğretmene, eşitlikte o gün bitişik seansta görevi olana verilir. Yıllık görev sınırını dolduranlar
    ancak başka öğretmen yoksa görev alır."""
    ogretmenleri_hazirla(db, donem_id)
    v = _Veri(db, donem_id)
    rng = random.Random(seed)
    sonuc = GorevSonucu()
    alanlar = {t.id: t for t in v.ogretmen.values() if t.gorev_alir}
    mesgul: dict[int, set[int]] = defaultdict(set)
    gunluk: dict[int, Counter] = defaultdict(Counter)
    oturum: dict[int, dict[str, set[int]]] = defaultdict(lambda: defaultdict(set))
    yuk: Counter = Counter({t: 0 for t in alanlar})
    yillik_azami = v.donem["yillik_azami_gorev"]
    onceki = _onceki_gorevler(db, v.donem) if yillik_azami else Counter()
    kilitli: dict[int, list] = defaultdict(list)
    for g in v.gorevliler:
        if not g["kilitli"]:
            continue
        s = v.sinav.get(g["sinav_id"])
        kilitli[g["sinav_id"]].append(g)
        sonuc.kilitli += 1
        if s and s["seans_id"] in v.seans:
            se = v.seans[s["seans_id"]]
            mesgul[g["ogretmen_id"]].add(s["seans_id"])
            gunluk[g["ogretmen_id"]][se["tarih"]] += 1
            oturum[g["ogretmen_id"]][se["tarih"]].add(se["sira"])
            yuk[g["ogretmen_id"]] += 1
    salon_sira = {r["id"]: (r["sira"], r["id"]) for r in v.salonlar}
    sinav_salon: dict[int, list[int]] = defaultdict(list)
    for (sid, _), (salon, _) in v.yerlesim.items():
        if salon and salon not in sinav_salon[sid]:
            sinav_salon[sid].append(salon)

    planli = [s for s in v.sinavlar if s["seans_id"] in v.seans and v.sinav_ogr.get(s["id"])]
    planli.sort(key=lambda s: (v.seans[s["seans_id"]]["tarih"], v.seans[s["seans_id"]]["sira"],
                               len(v.nitelik.get(s["id"], {})), s["id"]))
    yeni: list[tuple[int, int, str, int | None]] = []

    def uygun(t: int, seans_id: int, tarih: str) -> bool:
        o = alanlar[t]
        return seans_id not in o.kapali and seans_id not in mesgul[t] and gunluk[t][tarih] < o.azami

    def ata(t: int, sinav_id: int, gorev: str, seans_id: int, tarih: str, salon: int | None = None) -> None:
        yeni.append((sinav_id, t, gorev, salon))
        mesgul[t].add(seans_id)
        gunluk[t][tarih] += 1
        oturum[t][tarih].add(v.seans[seans_id]["sira"])
        yuk[t] += 1

    def asim(t: int) -> int:
        return int(bool(yillik_azami) and onceki[t] + yuk[t] >= yillik_azami)

    for s in planli:
        sid, seans_id = s["id"], s["seans_id"]
        tarih = v.seans[seans_id]["tarih"]
        o_sira = v.seans[seans_id]["sira"]

        def bitisik(t: int) -> int:
            return 0 if {o_sira - 1, o_sira + 1} & oturum[t][tarih] else 1

        nit = v.nitelik.get(sid, {})
        mevcut = kilitli.get(sid, [])
        baskan_var = any(g["gorev"] == KOMISYON_BASKANI for g in mevcut)
        kom_mevcut = sum(1 for g in mevcut if g["gorev"] != GOZCU)
        goz_mevcut = [g for g in mevcut if g["gorev"] == GOZCU]
        salonlar = sorted(sinav_salon.get(sid, []), key=lambda x: salon_sira.get(x, (0, x)))
        kom_gerek, goz_gerek = v.gorev_ihtiyaci(s, len(v.sinav_ogr[sid]), len(salonlar))
        adaylar = [t for t in alanlar if uygun(t, seans_id, tarih)]
        sira = {t: rng.random() for t in adaylar}
        secilen: list[int] = []
        for t in sorted(adaylar, key=lambda t: (nit.get(t, 9), asim(t), yuk[t], bitisik(t), sira[t])):
            if len(secilen) >= kom_gerek - kom_mevcut:
                break
            secilen.append(t)
        alan_disi = [t for t in secilen if t not in nit]
        if alan_disi:
            sonuc.uyarilar.append(f"{sinav_adi(s)}: yeterli alan/branş öğretmeni yok, komisyona "
                                  f"{', '.join(alanlar[t].ad for t in alan_disi)} alındı.")
        for i, t in enumerate(secilen):
            ata(t, sid, KOMISYON_BASKANI if i == 0 and not baskan_var else KOMISYON_UYESI, seans_id, tarih)
        eksik = []
        if kom_mevcut + len(secilen) < kom_gerek:
            eksik.append(f"{kom_gerek - kom_mevcut - len(secilen)} komisyon üyesi")
        goz_ihtiyac = goz_gerek - len(goz_mevcut)
        if goz_ihtiyac > 0:
            dolu_salon = {g["salon_id"] for g in goz_mevcut}
            bos_salon = [x for x in salonlar if x not in dolu_salon]
            goz_aday = sorted((t for t in adaylar if t not in secilen and uygun(t, seans_id, tarih)),
                              key=lambda t: (0 if t not in nit else 1, asim(t), yuk[t], bitisik(t), sira[t]))
            for i, t in enumerate(goz_aday[:goz_ihtiyac]):
                ata(t, sid, GOZCU, seans_id, tarih, bos_salon[i] if i < len(bos_salon) else None)
            if len(goz_aday) < goz_ihtiyac:
                eksik.append(f"{goz_ihtiyac - len(goz_aday)} gözcü")
        if eksik:
            sonuc.eksik.append(f"{sinav_adi(s)} ({seans_etiketi(v.seans[seans_id], uzun=False)}): "
                               f"{' ve '.join(eksik)} bulunamadı.")
    c = db.conn
    with c:
        ph = "SELECT id FROM sinavlar WHERE donem_id = ?"
        c.execute(f"DELETE FROM sinav_gorevlileri WHERE kilitli = 0 AND sinav_id IN ({ph})", (donem_id,))
        c.executemany("INSERT INTO sinav_gorevlileri (sinav_id, ogretmen_id, gorev, salon_id, kilitli) "
                      "VALUES (?, ?, ?, ?, 0)", yeni)
    sonuc.atanan = len(yeni)
    sonuc.sinav = len(planli)
    sonuc.yuk = {t: n for t, n in yuk.items()}
    return sonuc


def _onceki_gorevler(db, d: Any) -> Counter:
    """Öğretmen -> aynı eğitim yılının diğer sınav dönemlerindeki görevleri + elle girilen önceki görev sayısı."""
    say: Counter = Counter({r["ogretmen_id"]: r["onceki_gorev"] or 0 for r in db.q(
        "SELECT ogretmen_id, onceki_gorev FROM sinav_ogretmenleri WHERE donem_id = ?", (d["id"],))})
    yil = egitim_yili(d["baslangic"])
    if yil is None:
        return say
    diger = [r["id"] for r in db.q("SELECT id, baslangic FROM sinav_donemleri WHERE id != ?", (d["id"],))
             if egitim_yili(r["baslangic"]) == yil]
    if diger:
        for r in db.q(f"SELECT g.ogretmen_id, COUNT(*) n FROM sinav_gorevlileri g JOIN sinavlar s ON s.id = g.sinav_id "
                      f"WHERE s.donem_id IN ({','.join('?' * len(diger))}) AND ifnull(g.durum, '') != 'Gelmedi' "
                      f"GROUP BY g.ogretmen_id", diger):
            say[r["ogretmen_id"]] += r["n"]
    return say


def _gorev_uyarilari(db, v: _Veri, sinav_id: int, ogretmen_id: int, gorev: str, haric: Iterable[int] = ()) -> list[str]:
    s = v.sinav.get(sinav_id)
    o = v.ogretmen.get(ogretmen_id)
    ad = o.ad if o else f"Öğretmen {ogretmen_id}"
    haric = set(haric)
    out = []
    if o is None or not o.gorev_alir:
        out.append(f"{ad} bu dönemde görev almayan öğretmenlerden.")
    if s is not None and gorev != GOZCU and ogretmen_id not in v.nitelik.get(sinav_id, {}):
        out.append(f"{ad}: branşı/alanı {s['ders']} dersiyle uyuşmuyor.")
    seans_id = s["seans_id"] if s is not None and s["seans_id"] in v.seans else None
    if seans_id is not None:
        etiket = seans_etiketi(v.seans[seans_id], False)
        tarih = v.seans[seans_id]["tarih"]
        if o and seans_id in o.kapali:
            out.append(f"{ad}: {etiket} öğretmenin kapalı seansı.")
        ayni = gun = 0
        for g in v.gorevliler:
            gs = v.sinav.get(g["sinav_id"])
            if g["id"] in haric or g["ogretmen_id"] != ogretmen_id or gs is None or gs["seans_id"] not in v.seans:
                continue
            ayni += gs["seans_id"] == seans_id
            gun += v.seans[gs["seans_id"]]["tarih"] == tarih
        if ayni:
            out.append(f"{ad}: aynı seansta başka görevi var ({etiket}).")
        if o and gun + 1 > o.azami:
            out.append(f"{ad}: {tarih_coz(tarih).strftime('%d.%m.%Y')} günü {gun + 1}. görevi (sınır {o.azami}).")
    azami = v.donem["yillik_azami_gorev"]
    if azami:
        n = _onceki_gorevler(db, v.donem)[ogretmen_id] + sum(
            1 for g in v.gorevliler if g["ogretmen_id"] == ogretmen_id and g["id"] not in haric)
        if n + 1 > azami:
            out.append(f"{ad}: yıllık sınav görevi sınırı aşılıyor ({n + 1}/{azami}); fazla görev ücrete girmez.")
    return out


def _gorevli(db, gorevli_id: int):
    r = db.q1("SELECT g.*, s.donem_id FROM sinav_gorevlileri g JOIN sinavlar s ON s.id = g.sinav_id WHERE g.id = ?",
              (gorevli_id,))
    if r is None:
        raise ValueError("Görev kaydı bulunamadı.")
    return r


def gorevli_ekle(db, sinav_id: int, ogretmen_id: int, gorev: str, salon_id: int | None = None) -> list[str]:
    """Elle görevlendirme (kilitli; otomatik atama değiştirmez). Engel olan durumlar (kapalı seans, aynı seansta
    ikinci görev, günlük/yıllık sınır, görev almayan öğretmen, branş dışı komisyon) uyarı olarak döner.
    Yeni komisyon başkanı eklenirse eski başkan üye olur."""
    if gorev not in GOREVLER:
        raise ValueError("Geçersiz görev.")
    s = db.q1("SELECT donem_id FROM sinavlar WHERE id = ?", (sinav_id,))
    if s is None:
        raise ValueError("Sınav bulunamadı.")
    uyarilar = _gorev_uyarilari(db, _Veri(db, s["donem_id"]), sinav_id, ogretmen_id, gorev)
    with db.conn:
        if gorev == KOMISYON_BASKANI:
            db.conn.execute("UPDATE sinav_gorevlileri SET gorev = ? WHERE sinav_id = ? AND gorev = ?",
                            (KOMISYON_UYESI, sinav_id, KOMISYON_BASKANI))
        db.conn.execute("INSERT INTO sinav_gorevlileri (sinav_id, ogretmen_id, gorev, salon_id, kilitli) "
                        "VALUES (?, ?, ?, ?, 1)", (sinav_id, ogretmen_id, gorev, salon_id))
    return uyarilar


def gorevli_sil(db, gorevli_ids: Iterable[int]) -> None:
    with db.conn:
        db.conn.executemany("DELETE FROM sinav_gorevlileri WHERE id = ?", [(i,) for i in gorevli_ids])


def gorevli_degistir(db, gorevli_id: int, ogretmen_id: int | None = None, diger_id: int | None = None) -> list[str]:
    """Görevi başka öğretmene verir ya da (diger_id) iki görevin öğretmenlerini değiştirir. Görevler kilitlenir;
    engeller uyarı olarak döner."""
    g = _gorevli(db, gorevli_id)
    v = _Veri(db, g["donem_id"])
    if diger_id is not None:
        h = _gorevli(db, diger_id)
        uyarilar = _gorev_uyarilari(db, v, g["sinav_id"], h["ogretmen_id"], g["gorev"], {g["id"], h["id"]}) + \
            _gorev_uyarilari(db, v, h["sinav_id"], g["ogretmen_id"], h["gorev"], {g["id"], h["id"]})
        degisim = [(h["ogretmen_id"], g["id"]), (g["ogretmen_id"], h["id"])]
    elif ogretmen_id:
        uyarilar = _gorev_uyarilari(db, v, g["sinav_id"], ogretmen_id, g["gorev"], {g["id"]})
        degisim = [(ogretmen_id, g["id"])]
    else:
        raise ValueError("Yeni öğretmen ya da değiştirilecek ikinci görev seçilmedi.")
    with db.conn:
        db.conn.executemany("UPDATE sinav_gorevlileri SET ogretmen_id = ?, kilitli = 1 WHERE id = ?", degisim)
    return list(dict.fromkeys(uyarilar))


def gorevli_guncelle(db, gorevli_ids: Iterable[int], **vals: Any) -> None:
    """vals: kilitli, durum ('' / 'Geldi' / 'Gelmedi'), ucretsiz, gorev, salon_id."""
    if set(vals) - {"kilitli", "durum", "ucretsiz", "gorev", "salon_id"}:
        raise ValueError("Görev kaydında değiştirilemeyen alan.")
    if vals.get("durum", "") not in ("", GELDI, GELMEDI) or vals.get("gorev", GOZCU) not in GOREVLER:
        raise ValueError("Geçersiz görev bilgisi.")
    ids = list(gorevli_ids)
    if ids and vals:
        with db.conn:
            db.conn.executemany(f"UPDATE sinav_gorevlileri SET {', '.join(f'{k} = ?' for k in vals)} WHERE id = ?",
                                [(*vals.values(), i) for i in ids])


def gorevli_adaylari(db, sinav_id: int) -> list[dict]:
    """Sınavın seansında görev verilebilecek öğretmenler: uygunluk, dersle ilişki, dönemdeki ve o günkü görev sayısı."""
    s = db.q1("SELECT donem_id FROM sinavlar WHERE id = ?", (sinav_id,))
    if s is None:
        return []
    v = _Veri(db, s["donem_id"])
    sinav_ = v.sinav[sinav_id]
    seans_id = sinav_["seans_id"] if sinav_["seans_id"] in v.seans else None
    tarih = v.seans[seans_id]["tarih"] if seans_id else None
    yuk: Counter = Counter()
    gun: Counter = Counter()
    mesgul: set[int] = set()
    for g in v.gorevliler:
        yuk[g["ogretmen_id"]] += 1
        gs = v.sinav.get(g["sinav_id"])
        if seans_id and gs is not None and gs["seans_id"] in v.seans:
            gun[g["ogretmen_id"]] += v.seans[gs["seans_id"]]["tarih"] == tarih
            if gs["seans_id"] == seans_id:
                mesgul.add(g["ogretmen_id"])
    nit = v.nitelik.get(sinav_id, {})
    iliski = {1: "Dersi okutuyor", 2: "Aynı alan", 3: "Branşı uyuyor"}
    out = []
    for t in v.ogretmen.values():
        if not t.gorev_alir:
            durum = "Görev almaz"
        elif seans_id and seans_id in t.kapali:
            durum = "Kapalı seans"
        elif t.id in mesgul:
            durum = "Aynı seansta görevli"
        elif seans_id and gun[t.id] >= t.azami:
            durum = "Günlük sınır dolu"
        else:
            durum = "Uygun"
        out.append({"id": t.id, "ad": t.ad, "brans": t.brans, "durum": durum, "uygun": durum == "Uygun",
                    "iliski": iliski.get(nit.get(t.id), ""), "oncelik": nit.get(t.id, 9), "gorev_sayisi": yuk[t.id],
                    "gunluk": gun[t.id]})
    out.sort(key=lambda r: (not r["uygun"], r["oncelik"], r["gorev_sayisi"], norm(r["ad"])))
    return out


def gorev_ucretleri(db, donem_id: int) -> list[dict]:
    """Öğretmen başına sınav görevi ek ders ücreti dökümü. Gelmediği, ücretsiz işaretli (görev ya da sınav) ve yıllık
    görev sınırını aşan görevler ücrete girmez; her görev dönemde belirtilen ek ders saati kadar sayılır."""
    d = donem(db, donem_id)
    if d is None:
        raise ValueError("Sınav dönemi bulunamadı.")
    kom_saat = d["komisyon_ucret_saat"] if d["komisyon_ucret_saat"] is not None else 1
    goz_saat = d["gozcu_ucret_saat"] if d["gozcu_ucret_saat"] is not None else 1
    azami = d["yillik_azami_gorev"]
    onceki = _onceki_gorevler(db, d)
    out: dict[int, dict] = {}
    for r in db.q("""SELECT g.ogretmen_id, g.gorev, g.durum, g.ucretsiz, s.ucretsiz AS sinav_ucretsiz, s.ders, s.seviye,
                            s.grup, o.ad, o.soyad, o.brans, se.tarih, se.sira, se.baslangic, se.bitis
                     FROM sinav_gorevlileri g JOIN sinavlar s ON s.id = g.sinav_id
                     JOIN ogretmenler o ON o.id = g.ogretmen_id JOIN sinav_seanslari se ON se.id = s.seans_id
                     WHERE s.donem_id = ? ORDER BY o.ad, o.soyad, o.id, se.tarih, se.sira""", (donem_id,)):
        t = r["ogretmen_id"]
        k = out.setdefault(t, {"ogretmen_id": t, "ad": f"{r['ad']} {r['soyad']}", "brans": r["brans"] or "",
                               "onceki": onceki.get(t, 0), "komisyon": 0, "gozcu": 0, "gelmedi": 0, "ucretsiz": 0,
                               "sinir_disi": 0, "ucretli_komisyon": 0, "ucretli_gozcu": 0, "saat": 0.0,
                               "gorevler": []})
        komisyon = r["gorev"] != GOZCU
        k["komisyon" if komisyon else "gozcu"] += 1
        if r["durum"] == GELMEDI:
            durum = "Gelmedi"
            k["gelmedi"] += 1
        elif r["ucretsiz"] or r["sinav_ucretsiz"]:
            durum = "Ücretsiz"
            k["ucretsiz"] += 1
        elif azami and k["onceki"] + k["ucretli_komisyon"] + k["ucretli_gozcu"] >= azami:
            durum = "Yıllık sınır dışı"
            k["sinir_disi"] += 1
        else:
            durum = "Ücretli"
            k["ucretli_komisyon" if komisyon else "ucretli_gozcu"] += 1
            k["saat"] += kom_saat if komisyon else goz_saat
        k["gorevler"].append({**dict(r), "ucret_durumu": durum, "saat": (kom_saat if komisyon else goz_saat)
                              if durum == "Ücretli" else 0})
    return list(out.values())


# ------------------------------------------------------------------ salon ve sıra dağıtımı

def _karistir(gruplar: list[list[int]]) -> list[int]:
    """Gruplardan sırayla eleman alarak ardışık iki elemanın farklı gruptan olmasını sağlar (mümkün olduğunca)."""
    kuyruk = [list(g) for g in gruplar if g]
    out: list[int] = []
    onceki = -1
    while kuyruk:
        sira = sorted(range(len(kuyruk)), key=lambda i: -len(kuyruk[i]))
        i = next((i for i in sira if i != onceki), sira[0])
        out.append(kuyruk[i].pop(0))
        if not kuyruk[i]:
            kuyruk.pop(i)
            onceki = -1
        else:
            onceki = i
    return out


def _oturma_anahtari(v: _Veri, duzen: str) -> dict[int, Any]:
    if duzen == OTURMA_DUZENLERI[1]:
        return {o.id: (0, int(o.okul_no), o.ad) if o.okul_no.isdigit() else (1, 0, o.okul_no + o.ad)
                for o in v.ogrenci.values()}
    if duzen == OTURMA_DUZENLERI[2]:
        rng = random.Random(v.donem["id"])
        return {o: rng.random() for o in sorted(v.ogrenci)}
    return {o.id: (o.sinif, o.ad) for o in v.ogrenci.values()}


def salonlara_yerlestir(db, donem_id: int, duzen: str | None = None) -> str:
    """Her seansta yazılı sınavların (ve salon ayrılmış uygulama/sözlü sınavların) öğrencilerini salonlara kapasiteye
    göre dağıtır. Elle salona alınan öğrenciler yerinde kalır; sınava ayrılmış salonlar önce o sınavla doldurulur,
    kalanlar sıradaki ortak salonlara yerleşir. Bir salonda birden çok sınav varsa yan yana oturanlar farklı
    sınavlardan olur. Sıra no, salon içindeki oturma yeridir. duzen: OTURMA_DUZENLERI (None = dönem ayarı)."""
    v = _Veri(db, donem_id)
    if not v.salonlar:
        raise ValueError("Etkin salon tanımlı değil. 'Salonlar' sekmesinden salon ekleyin.")
    duzen = duzen or v.donem["oturma_duzeni"] or OTURMA_DUZENLERI[0]
    anahtar = _oturma_anahtari(v, duzen)
    kapasite = {r["id"]: max(0, r["kapasite"] or 0) for r in v.salonlar}
    seans_sinav: dict[int, list] = defaultdict(list)
    for s in v.sinavlar:
        if s["seans_id"] in v.seans and (salon_gerekir(s["sekil"]) or v.sinav_salon.get(s["id"])) and \
                v.sinav_ogr.get(s["id"]):
            seans_sinav[s["seans_id"]].append(s)
    guncelle: list[tuple[int | None, int | None, int, int, int]] = []
    tasan: list[str] = []
    yerlesen = 0
    salon_kullanim = 0
    for seans_id in sorted(seans_sinav, key=lambda x: (v.seans[x]["tarih"], v.seans[x]["sira"])):
        sinavlar = sorted(seans_sinav[seans_id], key=lambda s: (-len(v.sinav_ogr[s["id"]]), s["id"]))
        kalan = dict(kapasite)
        koltuk: dict[int, list[tuple[int, int, int]]] = defaultdict(list)
        bekleyen: list[tuple[int, int]] = []
        artan: list[tuple[int, int]] = []
        for s in sinavlar:
            kuyruk = []
            for o in sorted(v.sinav_ogr[s["id"]], key=lambda o: anahtar.get(o, ("", ""))):
                salon = v.yerlesim[(s["id"], o)][0]
                if (s["id"], o) in v.salon_kilitli and salon in kalan:
                    koltuk[salon].append((s["id"], o, 1))
                    kalan[salon] -= 1
                else:
                    kuyruk.append(o)
            for salon in v.sinav_salon.get(s["id"], []):
                bos = max(0, kalan[salon])
                koltuk[salon] += [(s["id"], o, 0) for o in kuyruk[:bos]]
                kalan[salon] -= len(kuyruk[:bos])
                kuyruk = kuyruk[bos:]
            (bekleyen if salon_gerekir(s["sekil"]) else artan).extend((s["id"], o) for o in kuyruk)
        ayrilmis = {salon for s in sinavlar for salon in v.sinav_salon.get(s["id"], [])}
        bas = 0
        for r in v.salonlar:
            if bas >= len(bekleyen):
                break
            if r["id"] in ayrilmis:
                continue
            parca = bekleyen[bas:bas + max(0, kalan[r["id"]])]
            bas += len(parca)
            koltuk[r["id"]] += [(sid, o, 0) for sid, o in parca]
        for r in v.salonlar:
            liste = koltuk.get(r["id"])
            if not liste:
                continue
            salon_kullanim += 1
            gruplar: dict[int, list[int]] = defaultdict(list)
            for i, (sid, _, _) in enumerate(liste):
                gruplar[sid].append(i)
            for no, i in enumerate(_karistir(list(gruplar.values())), 1):
                sid, o, kilit = liste[i]
                guncelle.append((r["id"], no, kilit, sid, o))
                yerlesen += 1
        kalanlar = bekleyen[bas:] + artan
        if kalanlar:
            guncelle += [(None, None, 0, sid, o) for sid, o in kalanlar]
            tasan.append(f"{seans_etiketi(v.seans[seans_id], uzun=False)}: {len(kalanlar)} öğrenci salonlara "
                         f"sığmadı (kapasite {v.salon_kapasitesi}).")
    with db.conn:
        db.conn.execute("UPDATE sinav_ogrencileri SET salon_id = NULL, sira_no = NULL, salon_kilitli = 0 "
                        "WHERE sinav_id IN (SELECT id FROM sinavlar WHERE donem_id = ?)", (donem_id,))
        db.conn.executemany("UPDATE sinav_ogrencileri SET salon_id = ?, sira_no = ?, salon_kilitli = ? "
                            "WHERE sinav_id = ? AND ogrenci_id = ?", guncelle)
    m = f"{len(seans_sinav)} seansta {yerlesen} öğrenci salonlara yerleştirildi ({salon_kullanim} salon oturumu)."
    if tasan:
        m += "\n\nKapasite aşımı:\n" + "\n".join(tasan)
    return m


# ------------------------------------------------------------------ denetim

@dataclass
class Bulgu:
    seviye: str
    mesaj: str
    sinav_id: int | None = None


def denetle(db, donem_id: int) -> list[Bulgu]:
    v = _Veri(db, donem_id)
    out: list[Bulgu] = []
    planli = {s["id"]: s for s in v.sinavlar if s["seans_id"] in v.seans}
    ogr_sinav: dict[int, list[int]] = defaultdict(list)
    for sid, ogr in v.sinav_ogr.items():
        for o in ogr:
            ogr_sinav[o].append(sid)

    for s in v.sinavlar:
        ad = sinav_adi(s)
        if not v.sinav_ogr.get(s["id"]):
            out.append(Bulgu(BILGI, f"{ad}: sınavın öğrencisi yok.", s["id"]))
        elif s["id"] not in planli:
            out.append(Bulgu(UYARI, f"{ad}: seansa yerleştirilmemiş ({len(v.sinav_ogr[s['id']])} öğrenci).", s["id"]))
        elif not v.seans[s["seans_id"]]["acik"]:
            out.append(Bulgu(UYARI, f"{ad}: kapalı seansta ({seans_etiketi(v.seans[s['seans_id']], False)}).",
                             s["id"]))

    def tarih_(sid: int) -> str:
        return v.seans[planli[sid]["seans_id"]]["tarih"]

    for sid, s in planli.items():
        izin = v.izinli_gunler(s)
        if izin is not None and tarih_(sid) not in izin and v.sinav_ogr.get(sid):
            out.append(Bulgu(KRITIK, f"{sinav_adi(s)}: sınav günü kuralına aykırı gün "
                                     f"({tarih_coz(tarih_(sid)).strftime('%d.%m.%Y')}).", sid))
        b = planli.get(s["bagli_sinav_id"])
        if b is not None:
            ilk = next((r for r in v.seanslar if r["acik"] and r["tarih"] > tarih_(b["id"])), None)
            if ilk is None or ilk["id"] != s["seans_id"]:
                out.append(Bulgu(KRITIK, f"{sinav_adi(s)}: bağlı olduğu {sinav_adi(b)} sınavından sonraki sınav "
                                         f"gününün ilk seansında değil.", sid))
    for a, b, tur in v.kural_ciftleri():
        if a not in planli or b not in planli or tur == "ortak_ogrenci":
            continue
        sa, sb = planli[a], planli[b]
        if tur == "kesin" and tarih_(a) == tarih_(b):
            out.append(Bulgu(KRITIK, f"{sinav_adi(sa)} ve {sinav_adi(sb)} aynı gün "
                                     f"({tarih_coz(tarih_(a)).strftime('%d.%m.%Y')}); 'kesinlikle aynı güne gelmesin' "
                                     f"kuralı.", a))
        elif tur == "ayni_seans" and sa["seans_id"] != sb["seans_id"]:
            out.append(Bulgu(KRITIK, f"{sinav_adi(sa)} ve {sinav_adi(sb)} farklı seanslarda; 'aynı seansta yapılsın' "
                                     f"kuralı.", a))

    ortak_kural = [k for k in v.kurallar if k[4] == "ortak_ogrenci"]
    kural_cift = {(a, b) for a, b, *_ in ortak_kural} | {(b, a) for a, b, *_ in ortak_kural}
    for o, sinavlar in ogr_sinav.items():
        ogr = v.ogrenci.get(o)
        kim = ogr.ad if ogr else str(o)
        p = [sid for sid in sinavlar if sid in planli]
        seans_grup: dict[int, list[int]] = defaultdict(list)
        gun_grup: dict[str, list[int]] = defaultdict(list)
        for sid in p:
            seans_grup[planli[sid]["seans_id"]].append(sid)
            gun_grup[tarih_(sid)].append(sid)
            if planli[sid]["seans_id"] in v.ogr_kapali.get(o, ()):
                out.append(Bulgu(KRITIK, f"{kim}: {sinav_adi(planli[sid])} sınavı öğrencinin kapalı seansında.", sid))
        for seans_id, g in seans_grup.items():
            if len(g) > 1:
                out.append(Bulgu(KRITIK, f"{kim}: aynı seansta {len(g)} sınav ({', '.join(sinav_adi(planli[x]) for x in g)}"
                                         f"; {seans_etiketi(v.seans[seans_id], False)}).", g[0]))
        for t, g in gun_grup.items():
            gun = tarih_coz(t).strftime("%d.%m.%Y")
            if len(g) > v.ogr_azami:
                out.append(Bulgu(KRITIK, f"{kim}: {gun} günü {len(g)} sınav (sınır {v.ogr_azami}).", g[0]))
            if len(g) > 1:
                uyg = [x for x in g if uygulamali(planli[x]["sekil"])]
                if uyg:
                    out.append(Bulgu(KRITIK, f"{kim}: {gun} günü uygulamalı {sinav_adi(planli[uyg[0]])} sınavıyla "
                                             f"birlikte başka sınav var.", uyg[0]))
                for i, a in enumerate(g):
                    for b in g[i + 1:]:
                        if (norm(planli[a]["ders"]), norm(planli[b]["ders"])) in kural_cift:
                            out.append(Bulgu(KRITIK, f"{kim}: {planli[a]['ders']} ve {planli[b]['ders']} aynı gün "
                                                     f"({gun}); 'aynı güne gelmesin' kuralı.", a))

    gorev_seans: dict[tuple[int, int], list] = defaultdict(list)
    gorev_gun: dict[tuple[int, str], int] = Counter()
    sinav_gorev: dict[int, list] = defaultdict(list)
    for g in v.gorevliler:
        sinav_gorev[g["sinav_id"]].append(g)
        s = planli.get(g["sinav_id"])
        if s is None:
            continue
        gorev_seans[(g["ogretmen_id"], s["seans_id"])].append(g)
        gorev_gun[(g["ogretmen_id"], v.seans[s["seans_id"]]["tarih"])] += 1
    for (t, seans_id), g in gorev_seans.items():
        o = v.ogretmen.get(t)
        ad = o.ad if o else f"Öğretmen {t}"
        if len(g) > 1:
            out.append(Bulgu(KRITIK, f"{ad}: aynı seansta {len(g)} görev ({seans_etiketi(v.seans[seans_id], False)}).",
                             g[0]["sinav_id"]))
        if o and seans_id in o.kapali:
            out.append(Bulgu(KRITIK, f"{ad}: kapalı seansında görevli ({seans_etiketi(v.seans[seans_id], False)}).",
                             g[0]["sinav_id"]))
        if o is None or not o.gorev_alir:
            out.append(Bulgu(UYARI, f"{ad}: görev almayan/etkin olmayan öğretmene görev verilmiş.", g[0]["sinav_id"]))
    for (t, gun), n in gorev_gun.items():
        o = v.ogretmen.get(t)
        if o and n > o.azami:
            out.append(Bulgu(UYARI, f"{o.ad}: {tarih_coz(gun).strftime('%d.%m.%Y')} günü {n} görev (sınır {o.azami})."))

    salon_say: dict[int, set] = defaultdict(set)
    for (sid, _), (salon, _) in v.yerlesim.items():
        if salon:
            salon_say[sid].add(salon)
    for sid, s in planli.items():
        n = len(v.sinav_ogr.get(sid, []))
        if not n:
            continue
        g = sinav_gorev.get(sid, [])
        kom_gerek, goz_gerek = v.gorev_ihtiyaci(s, n, len(salon_say.get(sid, ())))
        kom = [x for x in g if x["gorev"] != GOZCU]
        if len(kom) < kom_gerek:
            out.append(Bulgu(UYARI, f"{sinav_adi(s)}: komisyon eksik ({len(kom)}/{kom_gerek}).", sid))
        elif kom and not any(x["gorev"] == KOMISYON_BASKANI for x in kom):
            out.append(Bulgu(UYARI, f"{sinav_adi(s)}: komisyon başkanı yok.", sid))
        goz = sum(1 for x in g if x["gorev"] == GOZCU)
        if goz < goz_gerek:
            out.append(Bulgu(UYARI, f"{sinav_adi(s)}: gözcü eksik ({goz}/{goz_gerek}).", sid))

    if v.salonlar:
        kapasite = {r["id"]: r["kapasite"] or 0 for r in v.salonlar}
        seans_toplam: Counter = Counter()
        salon_doluluk: Counter = Counter()
        salonsuz: Counter = Counter()
        for (sid, o), (salon, _) in v.yerlesim.items():
            s = planli.get(sid)
            if s is None or not salon_gerekir(s["sekil"]):
                continue
            seans_toplam[s["seans_id"]] += 1
            if salon:
                salon_doluluk[(s["seans_id"], salon)] += 1
            else:
                salonsuz[s["seans_id"]] += 1
        for seans_id, n in seans_toplam.items():
            if n > v.salon_kapasitesi:
                out.append(Bulgu(KRITIK, f"{seans_etiketi(v.seans[seans_id], False)}: {n} öğrenci, salon kapasitesi "
                                         f"{v.salon_kapasitesi}."))
            if salonsuz[seans_id] and salonsuz[seans_id] < n:
                out.append(Bulgu(UYARI, f"{seans_etiketi(v.seans[seans_id], False)}: {salonsuz[seans_id]} öğrencinin "
                                        f"salonu belirlenmemiş."))
        for (seans_id, salon), n in salon_doluluk.items():
            if n > kapasite.get(salon, 0):
                out.append(Bulgu(KRITIK, f"{seans_etiketi(v.seans[seans_id], False)}: salon kapasitesi aşılmış "
                                         f"({n}/{kapasite.get(salon, 0)})."))
    sira = {KRITIK: 0, UYARI: 1, BILGI: 2}
    out.sort(key=lambda b: sira.get(b.seviye, 3))
    return out
