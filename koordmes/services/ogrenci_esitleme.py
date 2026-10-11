"""e-Okul öğrenci listesiyle eşitleme (nakil gelen / giden öğrenciler).

e-Okul'dan alınan güncel sınıf listeleri (OOK08001R020 vb. her biçim) okul kayıtlarıyla karşılaştırılır:
- Yeni: listede olup okulda olmayan (nakil gelen, yeni kayıt) — kaydedilir.
- Listede yok: listede bulunan sınıflarda okulda aktif olup listede olmayan (nakil giden, kaydı silinen) —
  pasif yapılır, isteğe bağlı açık yerleştirmesi (sigortası) ayrılış tarihiyle kapatılır.
- Yeniden kayıt: okulda pasif olup listede yer alan — aktif yapılır.
- Sınıf değişmiş / bilgi farkı: sınıfı, okul numarası, T.C. ya da adı farklı — listedeki gibi güncellenir.
Eşleştirme Veri Aktarımı ile aynıdır (T.C., okul no + ad, ad soyad).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from . import aktarim
from .aktarim import IceAktarmaSonucu, Secenekler, metin, norm, sinif_adi
from .okuyucu import Tablo

TURLER = ["Yeni", "Listede yok", "Yeniden kayıt", "Sınıf değişmiş", "Bilgi farkı"]
_TANIM = aktarim.TANIMLAR["ogrenciler"]


@dataclass
class ListeKaydi:
    ad: str
    soyad: str
    tc: str
    okul_no: str
    sinif: str
    veri: dict


@dataclass
class EsitlemeSatiri:
    tur: str
    ad: str
    okul_no: str
    tc: str
    okulda: str  # okul kaydındaki sınıf/bilgi
    listede: str
    ogrenci_id: int | None = None
    kayit: ListeKaydi | None = None


@dataclass
class EsitlemeSonucu:
    satirlar: list[EsitlemeSatiri] = field(default_factory=list)
    kapsam: list[str] = field(default_factory=list)  # listede bulunan sınıflar ([] = tüm okul)
    liste_sayisi: int = 0
    notlar: list[str] = field(default_factory=list)

    def sayilar(self) -> Counter:
        return Counter(s.tur for s in self.satirlar)


def listeyi_oku(tablolar: list[Tablo]) -> tuple[list[ListeKaydi], list[str]]:
    """Öğrenci listesi olarak tanınan tablolardaki kayıtlar ve okunamayan tablolar için notlar."""
    kayitlar: list[ListeKaydi] = []
    notlar: list[str] = []
    ak = aktarim._Aktarici(None, Secenekler(), IceAktarmaSonucu())
    for t in tablolar:
        bas, es = aktarim.baslik_bul(t.satirlar, _TANIM)
        sanal = aktarim.sanal_alanlar(t, _TANIM, es) if bas >= 0 else {}
        if bas < 0 or not aktarim.zorunlu_tamam(_TANIM, {**es, **sanal}):
            notlar.append(f"{t.etiket}: öğrenci listesi olarak tanınmadı")
            continue
        for _, _, d, _ in aktarim.kayit_satirlari(t, _TANIM, bas, es):
            ad, soyad = ak._ad_soyad(d)
            no = metin(d.get("okul_no"))
            if not ad or (no and not no.replace("-", "").replace("/", "").isalnum()):
                continue
            kayitlar.append(ListeKaydi(ad, soyad, metin(d.get("tc")), no,
                                       sinif_adi(d.get("sinif")) if metin(d.get("sinif")) else "", d))
    return kayitlar, notlar


def _sinif_anahtari(ad: str) -> str:
    return norm(sinif_adi(ad)) if ad else ""


def karsilastir(db, tablolar: list[Tablo]) -> EsitlemeSonucu:
    kayitlar, notlar = listeyi_oku(tablolar)
    sonuc = EsitlemeSonucu(liste_sayisi=len(kayitlar), notlar=notlar)
    if not kayitlar:
        sonuc.notlar.append("Listede öğrenci bulunamadı.")
        return sonuc
    ak = aktarim._Aktarici(db, Secenekler(olustur=False), IceAktarmaSonucu())
    ogrenciler = {r["id"]: r for r in db.q("""SELECT o.*, s.ad AS sinif FROM ogrenciler o
                                               LEFT JOIN siniflar s ON s.id = o.sinif_id""")}
    kapsam = {_sinif_anahtari(k.sinif) for k in kayitlar if k.sinif}
    sonuc.kapsam = sorted({k.sinif for k in kayitlar if k.sinif})
    if not kapsam:
        sonuc.notlar.append("Listede sınıf bilgisi yok; liste tüm okulun listesi kabul edildi.")
    adlar: dict[str, list[int]] = {}
    for i, x in ogrenciler.items():
        adlar.setdefault(norm(f"{x['ad']} {x['soyad']}"), []).append(i)
    gorulen: dict[int, ListeKaydi] = {}
    for k in kayitlar:
        ad = f"{k.ad} {k.soyad}"
        try:
            oid = ak.ogrenci_bul(dict(k.veri))
        except ValueError:
            oid = None
        if oid is not None:
            o = ogrenciler[oid]
            if norm(ad) != norm(f"{o['ad']} {o['soyad']}") and (not k.okul_no or k.okul_no != (o["okul_no"] or "")):
                # yalnız T.C. tutuyor: ad ve numarası aynı başka kayıt varsa odur, yoksa T.C. yanlış girilmiş
                alt = [i for i in adlar.get(norm(ad), [])
                       if not k.okul_no or (ogrenciler[i]["okul_no"] or "") == k.okul_no]
                sonuc.notlar.append(f"{ad}: T.C. {k.tc} okulda {o['ad']} {o['soyad']} adına kayıtlı; T.C. "
                                    "bilgilerini kontrol edin")
                oid = alt[0] if len(alt) == 1 else None
        if oid is not None and oid in gorulen:
            sonuc.notlar.append(f"{ad}: listede birden çok kez geçiyor ({gorulen[oid].sinif or '-'} / "
                                f"{k.sinif or '-'}); ilk satır esas alındı")
            continue
        if oid is None:
            sonuc.satirlar.append(EsitlemeSatiri("Yeni", ad, k.okul_no, k.tc, "-", k.sinif or "-", None, k))
            continue
        gorulen[oid] = k
        o = ogrenciler[oid]
        okul_ad = f"{o['ad']} {o['soyad']}"
        if not o["aktif"]:
            sonuc.satirlar.append(EsitlemeSatiri("Yeniden kayıt", ad, k.okul_no, k.tc, f"pasif ({o['sinif'] or '-'})",
                                                 k.sinif or "-", oid, k))
            continue
        if k.sinif and _sinif_anahtari(k.sinif) != _sinif_anahtari(o["sinif"] or ""):
            sonuc.satirlar.append(EsitlemeSatiri("Sınıf değişmiş", ad, k.okul_no, k.tc, o["sinif"] or "-", k.sinif,
                                                 oid, k))
            continue
        farklar = []
        if k.tc and k.tc != (o["tc"] or ""):
            farklar.append(("T.C.", o["tc"] or "(boş)", k.tc))
        if k.okul_no and k.okul_no != (o["okul_no"] or ""):
            farklar.append(("No", o["okul_no"] or "(boş)", k.okul_no))
        if norm(ad) != norm(okul_ad):
            farklar.append(("Ad", okul_ad, ad))
        if farklar:
            sonuc.satirlar.append(EsitlemeSatiri(
                "Bilgi farkı", okul_ad, k.okul_no, k.tc, "; ".join(f"{a}: {e}" for a, e, _ in farklar),
                "; ".join(f"{a}: {y}" for a, _, y in farklar), oid, k))
    for oid, o in ogrenciler.items():
        if not o["aktif"] or oid in gorulen:
            continue
        if kapsam and _sinif_anahtari(o["sinif"] or "") not in kapsam:
            continue
        sonuc.satirlar.append(EsitlemeSatiri("Listede yok", f"{o['ad']} {o['soyad']}", o["okul_no"] or "",
                                             o["tc"] or "", o["sinif"] or "-", "-", oid))
    sonuc.satirlar.sort(key=lambda s: (TURLER.index(s.tur), s.okulda if s.tur == "Listede yok" else s.listede,
                                       s.okul_no.zfill(8), s.ad))
    return sonuc


@dataclass
class UygulamaSonucu:
    sayilar: Counter = field(default_factory=Counter)
    hatalar: list[str] = field(default_factory=list)
    kapatilan: int = 0

    def metin(self) -> str:
        etiket = {"Yeni": "yeni öğrenci kaydedildi", "Listede yok": "öğrenci pasif yapıldı",
                  "Yeniden kayıt": "öğrenci yeniden aktif yapıldı", "Sınıf değişmiş": "öğrencinin sınıfı güncellendi",
                  "Bilgi farkı": "öğrencinin bilgisi güncellendi"}
        s = [f"{n} {etiket[t]}" for t, n in self.sayilar.items() if n]
        if self.kapatilan:
            s.append(f"{self.kapatilan} açık yerleştirme (sigorta) ayrılış tarihiyle kapatıldı")
        out = ".\n".join(s) + "." if s else "Değişiklik yapılmadı."
        if self.hatalar:
            out += f"\n\n{len(self.hatalar)} hata:\n" + "\n".join(self.hatalar[:20])
        return out


def uygula(db, satirlar: list[EsitlemeSatiri], ayrilis_tarihi: date | None = None,
           yerlestirme_kapat: bool = True, ogrenci_statusu: str | None = None) -> UygulamaSonucu:
    """Seçilen eşitleme satırlarını uygular. Listede olmayanlar pasif yapılır; ayrilis_tarihi verilir ve
    yerlestirme_kapat ise açık yerleştirmeleri bu tarihle 'Nakil' nedeniyle kapatılır."""
    sonuc = UygulamaSonucu()
    ak = aktarim._Aktarici(db, Secenekler(ogrenci_statusu=ogrenci_statusu), IceAktarmaSonucu(anahtar="ogrenciler"))
    t = (ayrilis_tarihi or date.today()).isoformat()
    db.conn.commit()
    db.conn.execute("BEGIN")
    try:
        for s in satirlar:
            db.conn.execute("SAVEPOINT esitle")
            try:
                if s.tur == "Listede yok":
                    db.conn.execute("UPDATE ogrenciler SET aktif = 0 WHERE id = ?", (s.ogrenci_id,))
                    if yerlestirme_kapat:
                        sonuc.kapatilan += db.conn.execute(
                            """UPDATE yerlestirmeler SET bitis = ?, durum = 'Sona Erdi', fesih_nedeni = 'Nakil'
                               WHERE ogrenci_id = ? AND durum = 'Aktif' AND (bitis IS NULL OR bitis = '' OR bitis > ?)
                               AND (baslangic IS NULL OR baslangic <= ?)""", (t, s.ogrenci_id, t, t)).rowcount
                elif s.kayit is not None:
                    d = dict(s.kayit.veri)
                    if s.tur == "Yeni":
                        if s.kayit.tc:
                            r = db.q1("SELECT ad, soyad FROM ogrenciler WHERE tc = ?", (s.kayit.tc,))
                            if r:
                                raise ValueError(f"T.C. {s.kayit.tc} başka öğrencide kayıtlı ({r['ad']} "
                                                 f"{r['soyad']}); önce T.C. bilgisini düzeltin")
                        durum, mesaj = ak.ogrenci(d)
                        if durum == "atlandi":
                            raise ValueError(mesaj)
                    else:
                        vals = {"ad": s.kayit.ad, "soyad": s.kayit.soyad}
                        if s.kayit.tc:
                            vals["tc"] = s.kayit.tc
                        if s.kayit.okul_no:
                            vals["okul_no"] = s.kayit.okul_no
                        if s.kayit.sinif:
                            vals["sinif_id"] = ak.sinif_id(d.get("sinif") or s.kayit.sinif, d)
                        if s.tur == "Yeniden kayıt":
                            vals["aktif"] = 1
                        if "tc" in vals:
                            r = db.q1("SELECT ad, soyad FROM ogrenciler WHERE tc = ? AND id != ?",
                                      (vals["tc"], s.ogrenci_id))
                            if r:
                                raise ValueError(f"T.C. {vals['tc']} başka öğrencide kayıtlı ({r['ad']} {r['soyad']})")
                        ak._guncelle("ogrenciler", s.ogrenci_id, vals)
                db.conn.execute("RELEASE esitle")
                sonuc.sayilar[s.tur] += 1
            except Exception as e:
                db.conn.execute("ROLLBACK TO esitle")
                db.conn.execute("RELEASE esitle")
                sonuc.hatalar.append(f"{s.ad}: {e}")
    except Exception:
        db.conn.rollback()
        raise
    db.conn.commit()
    return sonuc
