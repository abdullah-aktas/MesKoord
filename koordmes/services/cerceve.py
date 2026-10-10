"""MEB MTEGM çerçeve öğretim programları ve sınıflara zorunlu derslerin açılması.

Kaynak: https://meslek.meb.gov.tr/cerceve (okul türü > sınıf seviyesi > alan PDF'i > dal haftalık ders
çizelgesi). Çizelgeler veri/cerceve_programlari.json dosyasında tutulur; her kayıt bir okul türü (MTAL/MEM),
program (ATP, AMP, AMP-11, MEM), sınıf seviyesi, alan, dal ve protokollü olup olmadığına göre tektir.

Ders satırı: [ad, kategori, haftalık saat, parantezli saat, başarılması zorunlu (*)].
  * kategori: Ortak | Meslek | Rehberlik | İşletmede
  * parantezli saat: MEM çizelgelerinde "0-(2)" biçimindeki saat; zorunlu ders saatine girmez
  * (*): yılsonu başarı puanıyla başarılı sayılamayan ders (Ortaöğretim Kurumları Yönetmeliği)

Sınıfa uygulamada okulda okutulan zorunlu dersler (haftalık saati 0'dan büyük, İşletmede kategorisi
dışındaki) ders dağılımına açılır. İşletmelerde mesleki eğitim, seçmeli dersler ve akademik destek
saatleri okulun kararına bırakılır ve yalnızca özette gösterilir.
"""
from __future__ import annotations

import difflib
import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .aktarim import norm
from .utils import gunler_listesi

VERI_DOSYASI = Path(__file__).resolve().parents[1] / "veri" / "cerceve_programlari.json"
SITE = "https://meslek.meb.gov.tr/"
KAYNAK_SAYFA = SITE + "cerceve"

KURUMLAR = {"MTAL": "Mesleki ve Teknik Anadolu Lisesi", "MEM": "Mesleki Eğitim Merkezi"}
PROGRAM_ADLARI = {
    "ATP": "Anadolu Teknik Programı",
    "AMP": "Anadolu Meslek Programı",
    "AMP-11": "Anadolu Meslek Programı (işletmelerde mesleki eğitime 11. sınıfta başlayan okullar)",
    "MEM": "Mesleki Eğitim Merkezi Programı",
}
# siniflar.program -> (okul türü, çerçeve programı)
SINIF_PROGRAMI = {"MTAL-AMP": ("MTAL", "AMP"), "MTAL-AMP-11": ("MTAL", "AMP-11"), "MTAL-ATP": ("MTAL", "ATP"),
                  "MEM": ("MEM", "MEM")}
SEVIYELER = (9, 10, 11, 12)
# 2026 9. sınıf programlarında adı değişen alanlar (dalları aynı); eski adla tanımlı sınıflar için iki yönlü
ALAN_KARSILIKLARI = {"Motorlu Araçlar Teknolojisi": "Otomotiv Teknolojileri",
                     "Matbaa Teknolojisi": "Basım Teknolojileri",
                     "Aile ve Tüketici Hizmetleri": "Sosyal Hizmetler"}
ALAN_KARSILIKLARI.update({v: k for k, v in list(ALAN_KARSILIKLARI.items())})
ISLETMEDE = "İşletmede"
KATEGORI_TURU = {"Ortak": "Kültür", "Rehberlik": "Kültür", "Meslek": "Meslek"}
GUNLUK_ISLETME_SAATI = 8

KISA_ADLAR = {
    "Türk Dili ve Edebiyatı": "TDE", "Din Kültürü ve Ahlak Bilgisi": "DKAB",
    "T.C. İnkılap Tarihi ve Atatürkçülük": "İTA", "Beden Eğitimi ve Spor/Görsel Sanatlar/Müzik": "BES/GS/MÜZ",
    "Sağlık Bilgisi ve Trafik Kültürü": "SBTK", "Rehberlik ve Yönlendirme": "REH",
    "Mesleki Gelişim Atölyesi": "MGA", "Yabancı Dil": "YD",
}


@dataclass(frozen=True)
class CopDers:
    ad: str
    kategori: str
    saat: int
    parantezli_saat: int = 0
    basari_zorunlu: bool = False

    @property
    def okulda(self) -> bool:
        return self.kategori != ISLETMEDE


@dataclass(frozen=True)
class CopProgram:
    kurum: str
    program: str
    seviye: int
    alan: str
    dal: str
    protokol: bool
    yil: str
    kaynak: str
    toplam: int
    secmeli: int
    secmeli_meslek: int
    akademik_destek: int
    dersler: tuple[CopDers, ...]

    @property
    def url(self) -> str:
        return SITE + self.kaynak

    @property
    def zorunlu_dersler(self) -> list[CopDers]:
        return [d for d in self.dersler if d.saat > 0]

    @property
    def okul_dersleri(self) -> list[CopDers]:
        """Okulda okutulan zorunlu dersler; ders dağılımına bunlar açılır."""
        return [d for d in self.zorunlu_dersler if d.okulda]

    @property
    def okul_saati(self) -> int:
        return sum(d.saat for d in self.okul_dersleri)

    @property
    def isletme_saati(self) -> int:
        return sum(d.saat for d in self.zorunlu_dersler if not d.okulda)

    @property
    def isletme_gunu(self) -> int:
        return math.ceil(self.isletme_saati / GUNLUK_ISLETME_SAATI) if self.isletme_saati else 0

    @property
    def program_adi(self) -> str:
        return PROGRAM_ADLARI.get(self.program, self.program) + (" - protokollü" if self.protokol else "")

    @property
    def etiket(self) -> str:
        return f"{self.kurum} {self.seviye}. sınıf {self.alan} / {self.dal} ({self.program_adi})"

    def ozet(self) -> str:
        parca = [f"okulda {self.okul_saati} saat zorunlu ders"]
        if self.isletme_saati:
            parca.append(f"{self.isletme_saati} saat işletmelerde mesleki eğitim (haftada {self.isletme_gunu} gün)")
        if self.secmeli_meslek:
            parca.append(f"{self.secmeli_meslek} saat seçmeli meslek dersi")
        if self.secmeli:
            parca.append(f"{self.secmeli} saat seçmeli ders")
        if self.akademik_destek:
            parca.append(f"{self.akademik_destek} saat akademik destek")
        return ", ".join(parca) + (f"; haftalık toplam {self.toplam} saat" if self.toplam else "")


class VeriYok(RuntimeError):
    pass


def anahtar(s: str | None) -> str:
    s = (s or "").replace("â", "a").replace("Â", "A").replace("î", "i").replace("Î", "İ").replace("û", "u") \
        .replace("Û", "U")
    s = re.sub(r"\b(alani|dali)\b", " ", norm(s))
    return s.replace(" ", "")


def _ders(satir: list) -> CopDers:
    ad, kategori, saat, parantezli, yildiz = (list(satir) + [0, 0, 0])[:5]
    return CopDers(str(ad).strip(), str(kategori), int(saat or 0), int(parantezli or 0), bool(yildiz))


def _program(x: dict) -> CopProgram:
    dersler = tuple(_ders(d) for d in x.get("dersler") or [])
    toplam, secmeli, secmeli_meslek = int(x.get("toplam") or 0), int(x.get("secmeli") or 0), \
        int(x.get("secmeli_meslek") or 0)
    akademik = int(x.get("akademik_destek") or 0)
    if x.get("program") == "ATP" and not akademik:
        # 12. sınıf ATP çizelgelerinde akademik destek toplamı ayrı sütunda; kalan saat akademik destektir
        akademik = max(0, toplam - sum(d.saat for d in dersler) - secmeli - secmeli_meslek)
    return CopProgram(x["kurum"], x["program"], int(x["seviye"]), x["alan"].strip(), x["dal"].strip(),
                      bool(x.get("protokol")), str(x.get("yil") or ""), x.get("kaynak") or "", toplam, secmeli,
                      secmeli_meslek, akademik, dersler)


@lru_cache(maxsize=1)
def _veri() -> tuple[dict, tuple[CopProgram, ...]]:
    if not VERI_DOSYASI.exists():
        raise VeriYok(f"Çerçeve öğretim programı verisi bulunamadı: {VERI_DOSYASI}")
    ham = json.loads(VERI_DOSYASI.read_text("utf-8"))
    return ({k: v for k, v in ham.items() if k != "programlar"},
            tuple(_program(x) for x in ham.get("programlar") or []))


def veri_var() -> bool:
    try:
        return bool(_veri()[1])
    except (VeriYok, ValueError, KeyError):
        return False


def surum() -> str:
    return str(_veri()[0].get("surum") or "")


def programlar() -> tuple[CopProgram, ...]:
    return _veri()[1]


def alanlar(kurum: str) -> list[str]:
    return sorted({p.alan for p in programlar() if p.kurum == kurum}, key=anahtar)


def dallar(kurum: str, alan: str, seviye: int | None = None, program: str | None = None) -> list[str]:
    return sorted({p.dal for p in programlar() if p.kurum == kurum and p.alan == alan
                   and (seviye is None or p.seviye == seviye) and (program is None or p.program == program)},
                  key=anahtar)


def kurum_programlari(kurum: str) -> list[str]:
    return [k for k in PROGRAM_ADLARI if any(p.kurum == kurum and p.program == k for p in programlar())]


def eslestir(ad: str | None, adaylar) -> str | None:
    """Kullanıcının yazdığı alan/dal adını çerçeve programdaki karşılığına eşler ('Bilişim Teknolojileri Alanı',
    'BİLİŞİM TEKNOLOJİLERİ' -> 'Bilişim Teknolojileri'). Birden çok aday çıkarsa eşlemez."""
    k = anahtar(ad)
    if not k:
        return None
    harita = {anahtar(a): a for a in adaylar}
    if k in harita:
        return harita[k]
    kapsayan = [a for kk, a in harita.items() if kk in k or k in kk]
    if len(kapsayan) == 1:
        return kapsayan[0]
    yakin = difflib.get_close_matches(k, list(harita), n=2, cutoff=0.88)
    return harita[yakin[0]] if len(yakin) == 1 else None


def _ayni_cizelge(adaylar: list[CopProgram]) -> bool:
    return len({tuple((d.ad, d.saat) for d in p.zorunlu_dersler) for p in adaylar}) == 1


@dataclass
class Eslesme:
    program: CopProgram | None
    sorun: str = ""
    secenekler: list[CopProgram] = field(default_factory=list)  # aynı sınıfa uyabilecek diğer çizelgeler


def bul(kurum: str, program: str, seviye: int, alan: str | None, dal: str | None = None,
        protokol: bool | None = None) -> Eslesme:
    """Okul türü, program, seviye, alan ve dala göre haftalık ders çizelgesini bulur."""
    if seviye not in SEVIYELER:
        return Eslesme(None, f"{seviye}. sınıf için çerçeve öğretim programı yok (9-12)")
    if not (alan or "").strip():
        return Eslesme(None, "Sınıfın alanı seçilmemiş")
    tum = programlar()
    alan_adi = eslestir(alan, {p.alan for p in tum if p.kurum == kurum})
    if not alan_adi:
        return Eslesme(None, f"'{alan}' alanı {kurum} çerçeve öğretim programlarında bulunamadı")
    adaylar: list[CopProgram] = []
    for a in (alan_adi, ALAN_KARSILIKLARI.get(alan_adi)):
        for prg in (program, "AMP") if program == "AMP-11" else (program,):
            adaylar = adaylar or [p for p in tum if p.kurum == kurum and p.alan == a and p.seviye == seviye
                                  and p.program == prg]
    if not adaylar:
        return Eslesme(None, f"{alan_adi} alanında {seviye}. sınıf {PROGRAM_ADLARI.get(program, program)} "
                             "çizelgesi yok")
    alan_adi = adaylar[0].alan
    if protokol is not None and any(p.protokol == protokol for p in adaylar):
        adaylar = [p for p in adaylar if p.protokol == protokol]
    elif any(not p.protokol for p in adaylar):
        adaylar = [p for p in adaylar if not p.protokol] + [p for p in adaylar if p.protokol]
    dal_adi = eslestir(dal, {p.dal for p in adaylar}) if (dal or "").strip() else None
    if dal_adi:
        uygun = [p for p in adaylar if p.dal == dal_adi]
        return Eslesme(uygun[0], secenekler=uygun)
    birincil = [p for p in adaylar if p.protokol == adaylar[0].protokol]
    if _ayni_cizelge(birincil):
        sorun = f"'{dal}' dalı bulunamadı; bu seviyede dalların çizelgesi aynı" if (dal or "").strip() else ""
        return Eslesme(birincil[0], sorun, adaylar)
    if (dal or "").strip():
        return Eslesme(None, f"'{dal}' dalı {alan_adi} alanının {seviye}. sınıf çizelgelerinde bulunamadı", adaylar)
    return Eslesme(None, f"{alan_adi} alanında {seviye}. sınıf ders çizelgesi dala göre değişiyor; sınıfın dalını "
                         "seçiniz", adaylar)


def sinif_bilgisi(db, sinif_id: int):
    return db.q1("""SELECT s.*, a.ad AS alan, d.ad AS dal FROM siniflar s LEFT JOIN alanlar a ON a.id = s.alan_id
                    LEFT JOIN dallar d ON d.id = s.dal_id WHERE s.id = ?""", (sinif_id,))


def sinif_kurumu(program: str | None) -> tuple[str, str]:
    return SINIF_PROGRAMI.get((program or "").strip().upper(), ("MTAL", "AMP"))


def sinif_programi(db, sinif_id: int, protokol: bool | None = None) -> Eslesme:
    s = sinif_bilgisi(db, sinif_id)
    if s is None:
        return Eslesme(None, "Sınıf bulunamadı")
    kurum, prg = sinif_kurumu(s["program"])
    return bul(kurum, prg, int(s["seviye"] or 0), s["alan"], s["dal"], protokol)


# ----------------------------------------------------------------- sınıfa uygulama

@dataclass
class UygulamaSonucu:
    sinif: str
    program: CopProgram
    eklenen: list[str] = field(default_factory=list)
    guncellenen: list[str] = field(default_factory=list)
    mevcut: list[str] = field(default_factory=list)
    yeni_tanim: list[str] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)

    @property
    def degisti(self) -> bool:
        return bool(self.eklenen or self.guncellenen)

    def mesaj(self) -> str:
        m = [f"{self.sinif}: {len(self.eklenen)} zorunlu ders açıldı"]
        if self.guncellenen:
            m.append(f"{len(self.guncellenen)} dersin saati çerçeve programa göre düzeltildi")
        if self.mevcut:
            m.append(f"{len(self.mevcut)} ders zaten vardı")
        return ", ".join(m) + "."


def _blok(kategori: str, saat: int) -> int:
    if saat <= 2:
        return max(1, saat)
    return 4 if kategori == "Meslek" and saat >= 6 else 2


def _kisa_ad(ad: str) -> str:
    return next((v for k, v in KISA_ADLAR.items() if anahtar(k) == anahtar(ad)), "")


def _ders_tanimi(db, cd: CopDers, alan_id: int | None, tanimlar: dict, atolyeli_alan: bool,
                 yeni_tanim: list[str]) -> int:
    meslek = cd.kategori == "Meslek"
    adaylar = tanimlar.get(anahtar(cd.ad), [])
    for r in sorted(adaylar, key=lambda r: (r["alan_id"] != alan_id, r["alan_id"] is not None)):
        if not meslek or r["alan_id"] in (alan_id, None):
            return r["id"]
    kid = db.conn.execute(
        "INSERT INTO dersler (ad, kisa_ad, alan_id, tur, atolye_gerekli, blok) VALUES (?, ?, ?, ?, ?, ?)",
        (cd.ad, _kisa_ad(cd.ad), alan_id if meslek else None, KATEGORI_TURU.get(cd.kategori, "Kültür"),
         1 if meslek and atolyeli_alan else 0, _blok(cd.kategori, cd.saat))).lastrowid
    tanimlar.setdefault(anahtar(cd.ad), []).append({"id": kid, "alan_id": alan_id if meslek else None})
    yeni_tanim.append(cd.ad)
    return kid


def uygula(db, sinif_id: int, program: CopProgram, secili: set[str] | None = None,
           saatleri_duzelt: bool = True) -> UygulamaSonucu:
    """Çizelgedeki okulda okutulan zorunlu dersleri sınıfın ders dağılımına açar.

    secili verilirse yalnızca bu adlardaki dersler açılır. Var olan atamaların öğretmeni ve atölyesi korunur;
    saatleri_duzelt ile haftalık saati çizelgeden farklı olanlar düzeltilir. Çizelgede olmayan atamalara
    (seçmeli dersler vb.) dokunulmaz."""
    s = sinif_bilgisi(db, sinif_id)
    if s is None:
        raise ValueError("Sınıf bulunamadı")
    sonuc = UygulamaSonucu(s["ad"], program)
    tanimlar: dict[str, list] = {}
    for r in db.q("SELECT id, ad, alan_id FROM dersler"):
        tanimlar.setdefault(anahtar(r["ad"]), []).append(dict(r))
    atolyeli = bool(s["alan_id"]) and db.q1("SELECT 1 FROM atolyeler WHERE alan_id = ?", (s["alan_id"],)) is not None
    mevcut = {}
    for r in db.q("""SELECT da.id, da.ders_id, da.haftalik_saat, d.ad FROM ders_atamalari da
                     JOIN dersler d ON d.id = da.ders_id WHERE da.sinif_id = ?""", (sinif_id,)):
        mevcut.setdefault(anahtar(r["ad"]), r)
    with db.conn:
        for cd in program.okul_dersleri:
            if secili is not None and cd.ad not in secili:
                continue
            var = mevcut.get(anahtar(cd.ad))
            if var is not None:
                if saatleri_duzelt and var["haftalik_saat"] != cd.saat:
                    db.conn.execute("UPDATE ders_atamalari SET haftalik_saat = ? WHERE id = ?", (cd.saat, var["id"]))
                    sonuc.guncellenen.append(f"{cd.ad} ({var['haftalik_saat']} → {cd.saat} saat)")
                else:
                    sonuc.mevcut.append(cd.ad)
                continue
            ders_id = _ders_tanimi(db, cd, s["alan_id"], tanimlar, atolyeli, sonuc.yeni_tanim)
            ogretmen = s["rehber_ogretmen_id"] if cd.kategori == "Rehberlik" else None
            db.conn.execute("INSERT INTO ders_atamalari (sinif_id, ders_id, ogretmen_id, haftalik_saat) "
                            "VALUES (?, ?, ?, ?)", (sinif_id, ders_id, ogretmen, cd.saat))
            sonuc.eklenen.append(f"{cd.ad} ({cd.saat} saat)")
    sonuc.uyarilar = gun_uyarilari(db, s, program)
    return sonuc


def gun_uyarilari(db, sinif, program: CopProgram) -> list[str]:
    okul = gunler_listesi(sinif["okul_gunleri"]) or [1, 2, 3, 4, 5]
    isl = gunler_listesi(sinif["isletme_gunleri"])
    out = []
    if program.isletme_gunu and len(isl) != program.isletme_gunu:
        out.append(f"Çizelgeye göre haftada {program.isletme_gunu} gün işletmelerde mesleki eğitim var; sınıfın "
                   f"işletme günlerini ({len(isl)} gün tanımlı) ve okul günlerini düzenleyiniz.")
    elif not program.isletme_gunu and isl:
        out.append("Bu seviyede işletmelerde mesleki eğitim yok; sınıfın işletme günleri boş olmalı.")
    kapasite = len(okul) * int(db.ayar("gunluk_ders_saati") or 8)
    if program.okul_saati > kapasite:
        out.append(f"{program.okul_saati} saat zorunlu ders {len(okul)} okul gününe sığmıyor (en çok {kapasite} "
                   "saat); okul günlerini veya Mevzuat Parametrelerindeki günlük ders saati sayısını artırınız.")
    return out


def tum_siniflara_uygula(db, saatleri_duzelt: bool = True) -> tuple[list[UygulamaSonucu], list[str]]:
    sonuclar, sorunlar = [], []
    for s in db.q("SELECT id, ad FROM siniflar ORDER BY seviye, ad"):
        e = sinif_programi(db, s["id"])
        if e.program is None:
            sorunlar.append(f"{s['ad']}: {e.sorun}")
            continue
        sonuclar.append(uygula(db, s["id"], e.program, saatleri_duzelt=saatleri_duzelt))
    return sonuclar, sorunlar


# ----------------------------------------------------------------- denetim

@dataclass
class Uyumsuzluk:
    sinif: str
    eksik: list[str] = field(default_factory=list)
    saat_farkli: list[str] = field(default_factory=list)
    sorun: str = ""


def uyumsuzluklar(db) -> list[Uyumsuzluk]:
    """Ders dağılımı çerçeve öğretim programına uymayan sınıflar (eksik zorunlu ders, farklı saat)."""
    if not veri_var():
        return []
    out = []
    atamalar: dict[int, dict[str, int]] = {}
    for r in db.q("""SELECT da.sinif_id, d.ad, SUM(da.haftalik_saat) AS saat FROM ders_atamalari da
                     JOIN dersler d ON d.id = da.ders_id GROUP BY da.sinif_id, d.id"""):
        atamalar.setdefault(r["sinif_id"], {})[anahtar(r["ad"])] = r["saat"]
    for s in db.q("SELECT id, ad FROM siniflar ORDER BY seviye, ad"):
        e = sinif_programi(db, s["id"])
        if e.program is None:
            out.append(Uyumsuzluk(s["ad"], sorun=e.sorun))
            continue
        var = atamalar.get(s["id"], {})
        u = Uyumsuzluk(s["ad"])
        for cd in e.program.okul_dersleri:
            saat = var.get(anahtar(cd.ad))
            if saat is None:
                u.eksik.append(cd.ad)
            elif saat != cd.saat:
                u.saat_farkli.append(f"{cd.ad} ({saat}/{cd.saat})")
        if u.eksik or u.saat_farkli:
            out.append(u)
    return out


# ----------------------------------------------------------------- tanımlar

def sinif_atamalari(db, sinif_id: int) -> dict[str, int]:
    """Sınıfın ders dağılımı: {ders adı anahtarı: haftalık saat}."""
    out: dict[str, int] = {}
    for r in db.q("""SELECT d.ad, da.haftalik_saat FROM ders_atamalari da JOIN dersler d ON d.id = da.ders_id
                     WHERE da.sinif_id = ?""", (sinif_id,)):
        out[anahtar(r["ad"])] = out.get(anahtar(r["ad"]), 0) + int(r["haftalik_saat"] or 0)
    return out


def sinif_dalini_ayarla(db, sinif_id: int, dal: str) -> None:
    """Sınıfın dalını çerçeve programdaki dal adıyla kaydeder (dal tanımı yoksa alanın altına eklenir)."""
    s = sinif_bilgisi(db, sinif_id)
    if s is None or not s["alan_id"]:
        return
    dal_id = next((r["id"] for r in db.q("SELECT id, ad FROM dallar WHERE alan_id = ?", (s["alan_id"],))
                   if anahtar(r["ad"]) == anahtar(dal)), None)
    with db.conn:
        if dal_id is None:
            dal_id = db.conn.execute("INSERT INTO dallar (alan_id, ad) VALUES (?, ?)", (s["alan_id"], dal)).lastrowid
        db.conn.execute("UPDATE siniflar SET dal_id = ? WHERE id = ?", (dal_id, sinif_id))


def tanimlara_ekle(db, alan: str, dal_adlari: list[str] | None = None) -> tuple[int, list[str]]:
    """Çerçeve programdaki alanı (yoksa) ve dallarını Alanlar/Dallar tanımlarına ekler."""
    var = {anahtar(r["ad"]): r["id"] for r in db.q("SELECT id, ad FROM alanlar")}
    alan_id = var.get(anahtar(alan))
    eklenen: list[str] = []
    with db.conn:
        if alan_id is None:
            alan_id = db.conn.execute("INSERT INTO alanlar (ad) VALUES (?)", (alan,)).lastrowid
            eklenen.append(f"{alan} alanı")
        mevcut = {anahtar(r["ad"]) for r in db.q("SELECT ad FROM dallar WHERE alan_id = ?", (alan_id,))}
        for d in dal_adlari or []:
            if anahtar(d) not in mevcut:
                db.conn.execute("INSERT INTO dallar (alan_id, ad) VALUES (?, ?)", (alan_id, d))
                mevcut.add(anahtar(d))
                eklenen.append(f"{d} dalı")
    return alan_id, eklenen
