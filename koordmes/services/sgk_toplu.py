"""SGK toplu işlemleri.

- Toplu sigorta giriş tarihi: sigortası olmayan (nakil gelen, yeni kayıt) öğrencilere tek tarihle yerleştirme
  (sigorta) kaydı açılır; tür sınıfa göre belirlenir (işletmeye giden sınıflar işletmede mesleki eğitim, diğerleri
  okulda alan eğitimi).
- Toplu çıkış tarihi: açık yerleştirmelere tek tarih ve nedenle bitiş işlenir (dönem sonu, mezuniyet, nakil).
- Aylık prim listesinin dışında kalanlar: aktif öğrenciden kimin neden listede olmadığı.
- Öğrenci bilgi kontrolü: sigortalı öğrencilerde SGK bildirgesi için eksik/yanlış bilgiler.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..mevzuat import FESIH_SAYILAN
from . import sigorta
from .sgk_karsilastirma import yerlestirme_turu_tahmini
from .utils import ay_araligi, iban_gecerli, tarih, tc_gecerli, tr

# Yerleştirme ? tarihinde (ya da sonrasında) açık mı: bitişi girilmemiş aktif kayıt ya da durumu ne olursa olsun
# bitişi o tarihten sonra olan kayıt (ileri tarihli çıkışta durum hemen "Sona Erdi" yapılır, sigorta sürer).
AKTIF_SART = "(((y.bitis IS NULL OR y.bitis = '') AND y.durum = 'Aktif') OR y.bitis >= ?)"


def _sinif_kosulu(sinif_ids: list[int] | None, alias: str = "o") -> tuple[str, list]:
    if sinif_ids is None:
        return "", []
    if not sinif_ids:
        return " AND 0", []
    return f" AND {alias}.sinif_id IN ({', '.join('?' for _ in sinif_ids)})", list(sinif_ids)


@dataclass
class GirisAdayi:
    ogrenci_id: int
    ad: str
    tc: str
    okul_no: str
    sinif: str
    onerilen_tur: str
    son_kayit: str = ""  # varsa önceki (bitmiş) yerleştirme özeti


def giris_adaylari(db, tarih_: date, sinif_ids: list[int] | None = None) -> list[GirisAdayi]:
    """Verilen tarihte sigortası (açık yerleştirmesi) olmayan aktif öğrenciler."""
    kosul, params = _sinif_kosulu(sinif_ids)
    rows = db.q(f"""SELECT o.id, o.ad, o.soyad, o.tc, o.okul_no, s.ad AS sinif FROM ogrenciler o
                    LEFT JOIN siniflar s ON s.id = o.sinif_id
                    WHERE o.aktif = 1 {kosul} AND NOT EXISTS (
                        SELECT 1 FROM yerlestirmeler y WHERE y.ogrenci_id = o.id AND {AKTIF_SART})
                    ORDER BY s.ad, CAST(o.okul_no AS INTEGER), o.ad""", [*params, tarih_.isoformat()])
    out = []
    for r in rows:
        son = db.q1("""SELECT tur, baslangic, bitis FROM yerlestirmeler WHERE ogrenci_id = ?
                       ORDER BY COALESCE(bitis, baslangic) DESC LIMIT 1""", (r["id"],))
        ozet = f"{son['tur']} {tr(son['baslangic'])} - {tr(son['bitis']) or '...'}" if son else ""
        out.append(GirisAdayi(r["id"], f"{r['ad']} {r['soyad']}", r["tc"] or "", r["okul_no"] or "",
                              r["sinif"] or "", yerlestirme_turu_tahmini(db, r["id"]), ozet))
    return out


@dataclass
class IslemSonucu:
    yapilan: int = 0
    atlanan: list[str] = field(default_factory=list)

    def metin(self, eylem: str) -> str:
        s = f"{self.yapilan} öğrenci için {eylem}."
        if self.atlanan:
            s += f"\n{len(self.atlanan)} kayıt atlandı:\n" + "\n".join(self.atlanan[:20])
            if len(self.atlanan) > 20:
                s += f"\n... ve {len(self.atlanan) - 20} kayıt daha"
        return s


def toplu_giris(db, ogrenci_ids: list[int], tarih_: date, tur: str | None = None,
                isletme_id: int | None = None) -> IslemSonucu:
    """Seçilen öğrencilere `tarih_` başlangıçlı yerleştirme açar. tur None ise sınıfa göre belirlenir."""
    sonuc = IslemSonucu()
    t = tarih_.isoformat()
    with db.conn:
        for oid in ogrenci_ids:
            o = db.q1("SELECT ad, soyad FROM ogrenciler WHERE id = ?", (oid,))
            if not o:
                continue
            ad = f"{o['ad']} {o['soyad']}"
            cakisan = db.q1(f"""SELECT y.baslangic, y.bitis FROM yerlestirmeler y WHERE y.ogrenci_id = ?
                                AND {AKTIF_SART}""", (oid, t))
            if cakisan:
                sonuc.atlanan.append(f"{ad}: açık yerleştirmesi var ({tr(cakisan['baslangic'])} başlangıçlı"
                                     + (f", {tr(cakisan['bitis'])} bitişli)" if cakisan["bitis"] else ")"))
                continue
            db.conn.execute("""INSERT INTO yerlestirmeler (ogrenci_id, isletme_id, tur, baslangic, durum)
                               VALUES (?, ?, ?, ?, 'Aktif')""",
                            (oid, isletme_id, tur or yerlestirme_turu_tahmini(db, oid), t))
            sonuc.yapilan += 1
    return sonuc


@dataclass
class CikisAdayi:
    yerlestirme_id: int
    ogrenci_id: int
    ad: str
    tc: str
    okul_no: str
    sinif: str
    tur: str
    isletme: str
    baslangic: date | None
    bitis: date | None


def cikis_adaylari(db, sinif_ids: list[int] | None = None, sadece_tarihsiz: bool = True) -> list[CikisAdayi]:
    """Açık (durumu Aktif) yerleştirmeler; sadece_tarihsiz ise bitiş tarihi girilmemiş olanlar."""
    kosul, params = _sinif_kosulu(sinif_ids)
    if sadece_tarihsiz:
        kosul += " AND (y.bitis IS NULL OR y.bitis = '')"
    rows = db.q(f"""SELECT y.id, y.ogrenci_id, y.tur, y.baslangic, y.bitis, o.ad, o.soyad, o.tc, o.okul_no,
                           s.ad AS sinif, i.ad AS isletme
                    FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                    LEFT JOIN siniflar s ON s.id = o.sinif_id LEFT JOIN isletmeler i ON i.id = y.isletme_id
                    WHERE y.durum = 'Aktif' {kosul}
                    ORDER BY s.ad, CAST(o.okul_no AS INTEGER), o.ad""", params)
    return [CikisAdayi(r["id"], r["ogrenci_id"], f"{r['ad']} {r['soyad']}", r["tc"] or "", r["okul_no"] or "",
                       r["sinif"] or "", r["tur"] or "", r["isletme"] or "", tarih(r["baslangic"]),
                       tarih(r["bitis"])) for r in rows]


def toplu_cikis(db, yerlestirme_ids: list[int], tarih_: date, neden: str) -> IslemSonucu:
    """Yerleştirmelere bitiş tarihi ve nedeni işler; SGK işten ayrılış bildirgeleri bekleyenlere düşer."""
    sonuc = IslemSonucu()
    durum = "Feshedildi" if neden in FESIH_SAYILAN else "Sona Erdi"
    with db.conn:
        for yid in yerlestirme_ids:
            r = db.q1("""SELECT y.baslangic, o.ad, o.soyad FROM yerlestirmeler y
                         JOIN ogrenciler o ON o.id = y.ogrenci_id WHERE y.id = ?""", (yid,))
            if not r:
                continue
            b = tarih(r["baslangic"])
            if b and tarih_ < b:
                sonuc.atlanan.append(f"{r['ad']} {r['soyad']}: çıkış tarihi başlangıçtan ({tr(b)}) önce")
                continue
            db.conn.execute("UPDATE yerlestirmeler SET bitis = ?, durum = ?, fesih_nedeni = ? WHERE id = ?",
                            (tarih_.isoformat(), durum, neden, yid))
            sonuc.yapilan += 1
    return sonuc


def cikisi_islenmisler(db, tarih_: date, sinif_ids: list[int] | None = None) -> list[CikisAdayi]:
    """Bitiş tarihi `tarih_` olan yerleştirmeler (toplu çıkışı geri almak için)."""
    kosul, params = _sinif_kosulu(sinif_ids)
    rows = db.q(f"""SELECT y.id, y.ogrenci_id, y.tur, y.baslangic, y.bitis, o.ad, o.soyad, o.tc, o.okul_no,
                           s.ad AS sinif, i.ad AS isletme
                    FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                    LEFT JOIN siniflar s ON s.id = o.sinif_id LEFT JOIN isletmeler i ON i.id = y.isletme_id
                    WHERE y.bitis = ? {kosul}
                    ORDER BY s.ad, CAST(o.okul_no AS INTEGER), o.ad""", [tarih_.isoformat(), *params])
    return [CikisAdayi(r["id"], r["ogrenci_id"], f"{r['ad']} {r['soyad']}", r["tc"] or "", r["okul_no"] or "",
                       r["sinif"] or "", r["tur"] or "", r["isletme"] or "", tarih(r["baslangic"]),
                       tarih(r["bitis"])) for r in rows]


def cikisi_geri_al(db, yerlestirme_ids: list[int]) -> IslemSonucu:
    """Bitiş tarihini ve fesih nedenini siler, durumu Aktif yapar. SGK'ya çıkışı bildirilmiş ya da sonrasında
    başka yerleştirmesi açılmış kayıtlar atlanır."""
    sonuc = IslemSonucu()
    with db.conn:
        for yid in yerlestirme_ids:
            r = db.q1("""SELECT y.ogrenci_id, y.bitis, y.sigorta_cikis_bildirildi, o.ad, o.soyad
                         FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id WHERE y.id = ?""", (yid,))
            if not r or not r["bitis"]:
                continue
            ad = f"{r['ad']} {r['soyad']}"
            if r["sigorta_cikis_bildirildi"]:
                sonuc.atlanan.append(f"{ad}: işten ayrılış SGK'ya bildirilmiş; önce e-Bildirge'de iptal ettirin, "
                                     "sonra 'Bildirildi' işaretini kaldırın")
                continue
            sonraki = db.q1("""SELECT baslangic FROM yerlestirmeler WHERE ogrenci_id = ? AND id != ?
                               AND baslangic > ? ORDER BY baslangic""", (r["ogrenci_id"], yid, r["bitis"]))
            if sonraki:
                sonuc.atlanan.append(f"{ad}: {tr(sonraki['baslangic'])} başlangıçlı yeni yerleştirmesi var")
                continue
            db.conn.execute("UPDATE yerlestirmeler SET bitis = NULL, durum = 'Aktif', fesih_nedeni = '' "
                            "WHERE id = ?", (yid,))
            sonuc.yapilan += 1
    return sonuc


def bildirge_bekleyenler(db, tarih_: date, tur: str, sinif_ids: list[int] | None = None) -> list[int]:
    """`tarih_` tarihinde başlayan (tur 'Giriş') ya da biten ('Çıkış') ve SGK bildirimi bekleyen yerleştirmeler;
    toplu işe giriş / işten ayrılış XML'i için. İşletme değişikliği gibi bildirim gerektirmeyenler alınmaz."""
    adaylar = [b.yerlestirme_id for b in sigorta.bekleyen_bildirimler(db, tarih_, ileri_gun=0)
               if b.tur == tur and b.olay_tarihi == tarih_ and not b.bildirildi]
    if sinif_ids is None or not adaylar:
        return adaylar
    kosul, params = _sinif_kosulu(sinif_ids)
    soru = ",".join("?" * len(adaylar))
    uygun = {r["id"] for r in db.q(f"""SELECT y.id FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                                       WHERE y.id IN ({soru}) {kosul}""", [*adaylar, *params])}
    return [i for i in adaylar if i in uygun]


# ------------------------------------------------------------------ liste dışı kalanlar

@dataclass
class ListeDisi:
    ogrenci_id: int
    ad: str
    tc: str
    okul_no: str
    sinif: str
    seviye: str  # Liste dışı | Uyarı
    neden: str


def liste_disi_kalanlar(db, yil: int, ay: int) -> list[ListeDisi]:
    """Aylık prim listesine girmeyen aktif öğrenciler ve listede olup bildirgede sorun çıkaracaklar."""
    ilk, son = ay_araligi(yil, ay)
    satirlar = sigorta.aylik_liste(db, yil, ay)
    listede = {s.ogrenci_id: s for s in satirlar}
    yerler: dict[int, list] = {}
    for y in db.q("SELECT ogrenci_id, tur, baslangic, bitis, durum FROM yerlestirmeler ORDER BY baslangic"):
        yerler.setdefault(y["ogrenci_id"], []).append(y)
    out: list[ListeDisi] = []
    for o in db.q("""SELECT o.id, o.ad, o.soyad, o.tc, o.okul_no, o.aktif, s.ad AS sinif FROM ogrenciler o
                     LEFT JOIN siniflar s ON s.id = o.sinif_id
                     ORDER BY s.ad, CAST(o.okul_no AS INTEGER), o.ad"""):
        kayit = lambda seviye, neden: out.append(ListeDisi(o["id"], f"{o['ad']} {o['soyad']}", o["tc"] or "",
                                                           o["okul_no"] or "", o["sinif"] or "", seviye, neden))
        s = listede.get(o["id"])
        if s is None:
            if not o["aktif"]:
                continue
            ys = yerler.get(o["id"], [])
            if not ys:
                kayit("Liste dışı", "Yerleştirme (sigorta) kaydı yok")
            elif all(not y["baslangic"] for y in ys):
                kayit("Liste dışı", "Yerleştirme var ama sigorta başlangıç tarihi girilmemiş")
            else:
                sonraki = [tarih(y["baslangic"]) for y in ys if tarih(y["baslangic"]) and tarih(y["baslangic"]) > son]
                biten = [tarih(y["bitis"]) for y in ys if tarih(y["bitis"]) and tarih(y["bitis"]) < ilk]
                if sonraki:
                    kayit("Liste dışı", f"Sigorta {tr(min(sonraki))} tarihinde başlıyor (dönemden sonra)")
                elif biten:
                    kayit("Liste dışı", f"Sigorta {tr(max(biten))} tarihinde sona ermiş")
                else:
                    kayit("Liste dışı", "Bu döneme denk gelen sigorta günü yok")
            continue
        if not o["aktif"]:
            kayit("Uyarı", "Öğrenci pasif (ayrılmış) ama sigortası bu dönemde sürüyor; çıkış tarihini girin")
        if not s.tc:
            kayit("Uyarı", "T.C. kimlik no boş; aylık prim belgesine yazılamaz")
        elif not tc_gecerli(s.tc):
            kayit("Uyarı", f"T.C. kimlik no geçersiz ({s.tc})")
        if s.gun == 0:
            kayit("Uyarı", f"Prim günü 0 ({s.eksik_gun} eksik gün); belgeye 0 gün ve eksik gün nedeniyle yazılır")
    return out


# ------------------------------------------------------------------ bilgi kontrolü

@dataclass
class BilgiEksigi:
    ogrenci_id: int
    ad: str
    okul_no: str
    sinif: str
    eksikler: list[str]
    uyarilar: list[str] = field(default_factory=list)  # nüfus bilgisi gibi bildirgeyi engellemeyen eksikler
    giris: date | None = None  # son yerleştirmenin SGK giriş / çıkış tarihi
    cikis: date | None = None

    @property
    def sorunlu(self) -> bool:
        return bool(self.eksikler or self.uyarilar)


NUFUS_ALANLARI = [("baba_adi", "baba adı"), ("anne_adi", "anne adı"), ("dogum_yeri", "doğum yeri")]


def bilgi_kontrol(db, sadece_sigortali: bool = True, tumu: bool = False,
                  bugun: date | None = None) -> list[BilgiEksigi]:
    """SGK bildirgeleri ve ücret ödemesi için eksik/yanlış öğrenci bilgileri. tumu ise sorunsuz öğrenciler de
    döner. Ders yılı bittiyse (Kurum Bilgileri) çıkış tarihi girilmemiş açık sigortalar da bildirilir."""
    bugun = bugun or date.today()
    b = bugun.isoformat()
    kosul = (f"""AND EXISTS (SELECT 1 FROM yerlestirmeler y WHERE y.ogrenci_id = o.id AND {AKTIF_SART})"""
             if sadece_sigortali else "")
    rows = db.q(f"""SELECT o.*, s.ad AS sinif,
                           (SELECT COUNT(*) FROM yerlestirmeler y WHERE y.ogrenci_id = o.id
                            AND y.tur != 'Okulda Alan Eğitimi' AND {AKTIF_SART}) AS isletmede
                    FROM ogrenciler o LEFT JOIN siniflar s ON s.id = o.sinif_id
                    WHERE o.aktif = 1 {kosul} ORDER BY s.ad, CAST(o.okul_no AS INTEGER), o.ad""",
                [b] + ([b] if sadece_sigortali else []))
    yerler: dict[int, list] = {}
    for y in db.q("""SELECT ogrenci_id, baslangic, bitis FROM yerlestirmeler
                     ORDER BY COALESCE(NULLIF(bitis, ''), '9999'), baslangic"""):
        yerler.setdefault(y["ogrenci_id"], []).append(y)
    yil_sonu = tarih(db.kurum()["ders_yili_sonu"])
    yil_bitti = bool(yil_sonu and bugun > yil_sonu)
    out = []
    for r in rows:
        ys = yerler.get(r["id"], [])
        son = ys[-1] if ys else None
        giris, cikis = (tarih(son["baslangic"]), tarih(son["bitis"])) if son else (None, None)
        e = []
        if not r["tc"]:
            e.append("T.C. kimlik no yok")
        elif not tc_gecerli(r["tc"]):
            e.append("T.C. kimlik no geçersiz")
        if not r["dogum_tarihi"]:
            e.append("Doğum tarihi yok")
        if not r["cinsiyet"]:
            e.append("Cinsiyet yok")
        if not r["sinif_id"]:
            e.append("Sınıfı yok")
        if r["isletmede"]:
            if not r["iban"]:
                e.append("IBAN yok (ücret ödemesi)")
            elif not iban_gecerli(r["iban"]):
                e.append("IBAN geçersiz")
        if not r["veli_tel"] and not r["telefon"]:
            e.append("Telefon yok")
        if not giris:
            e.append("Sigorta giriş tarihi yok")
        elif yil_bitti and not cikis and giris <= yil_sonu:
            e.append(f"Çıkış tarihi yok (ders yılı {tr(yil_sonu)} tarihinde bitti)")
        u = [ad for k, ad in NUFUS_ALANLARI if not (r[k] or "").strip()]
        uyarilar = [f"Nüfus bilgisi eksik: {', '.join(u)}"] if u else []
        if e or uyarilar or tumu:
            out.append(BilgiEksigi(r["id"], f"{r['ad']} {r['soyad']}", r["okul_no"] or "", r["sinif"] or "", e,
                                   uyarilar, giris, cikis))
    return out
