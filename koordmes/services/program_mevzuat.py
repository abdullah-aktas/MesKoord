"""Ders programının mevzuata uygunluğu, norm kadro, iş adımları ve e-Okul eşgüdümü.

Dayanaklar:
  * Ortaöğretim Kurumları Yönetmeliği md.12: program öğretmenler kurulunda görüşülür, müdür onaylar, imza karşılığı
    tebliğ edilir; engelli, engelli yakını, 36 ayını doldurmamış çocuğu olan ve süt izni kullanan öğretmenlerin
    tercihleri dikkate alınır; beden eğitimi ve müzik haftanın ilk ve son iş gününe konur; uygulamalı meslek dersleri
    ardışık saatlerde, aynı gün teori ve uygulama varsa teori öğleden önce yapılır; MEM teorik eğitimi haftada en az
    1, en fazla 2 gündür (md.12/3).
  * Ders ve Ek Ders Saatlerine İlişkin Karar md.5 (aylık karşılığı), md.6 (azami ek ders), md.15 (işletmelerde meslek
    eğitimi haftalık ve günlük azami).
  * MEB Yönetici ve Öğretmen Norm Kadro Yönetmeliği md.18 (genel bilgi ve meslek dersleri), md.19 (atölye ve
    laboratuvar, işletmelerde meslek eğitimi dâhil), md.21 (rehberlik), md.22 (alan ders yükü = saat x grup;
    yöneticilerin okuttuğu dersler düşülür; MEM şubeleri gruplara bölünmez).
Norm hesabı okul verisinden yapılan tahmindir; resmî norm MEBBİS'te belirlenir.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..mevzuat import GUNLER, YONETICI_UNVANLARI, mem_mi
from . import ekders, program
from .aktarim import norm
from .utils import gunler_listesi

PROGRAM_SAYFASI = "Ders Dağılımı ve Atölye Yerleşimi"
ARACLAR_SAYFASI = "Program Araçları (Kısıt, Sürüm, Devir, Yük)"
SEKME_ADIMLAR = "İş Adımları ve Mevzuat"
SEKME_DAGILIM = "Ders Dağılımı (Sınıf-Ders-Öğretmen)"
SEKME_TABLO = "Sınıf / Öğretmen / Mekan"
SEKME_CERCEVE = "Çerçeve Öğretim Programları"

KARAR = "Ders ve Ek Ders Saatlerine İlişkin Karar"
OKY = "Ortaöğretim Kurumları Yönetmeliği"
NORM = "Norm Kadro Yönetmeliği"


@dataclass
class MevzuatBulgusu:
    seviye: str  # Kritik | Uyarı | Bilgi
    konu: str
    mesaj: str
    dayanak: str = ""
    git: str = ""  # "Sayfa adı" ya da "Sayfa adı/Sekme adı"


def _sirala(out: list[MevzuatBulgusu]) -> list[MevzuatBulgusu]:
    return sorted(out, key=lambda b: {"Kritik": 0, "Uyarı": 1, "Bilgi": 2}[b.seviye])


def _bugun() -> str:
    return date.today().isoformat()


def _gun_adi(g: int) -> str:
    return GUNLER[g - 1] if 1 <= g <= len(GUNLER) else f"{g}. gün"


# ------------------------------------------------------------------ ders yükü (Karar md.5, 6, 15; OKY md.12)

def yuk_denetimi(db) -> list[MevzuatBulgusu]:
    from . import koordinator
    from .program_araclari import ogretmen_yukleri
    out: list[MevzuatBulgusu] = []
    yuk = ogretmen_yukleri(db)
    ime_azami = koordinator.haftalik_azami(db)
    gunluk = db.ayar("koord_gunluk_max")
    ime: dict[int, int] = defaultdict(int)
    ime_gun: dict[tuple[int, int], int] = defaultdict(int)
    for r in db.q("""SELECT ogretmen_id, gun, haftalik_saat FROM koordinator_gorevleri
                     WHERE bitis IS NULL OR bitis = '' OR bitis >= ?""", (_bugun(),)):
        ime[r["ogretmen_id"]] += r["haftalik_saat"] or 0
        ime_gun[(r["ogretmen_id"], r["gun"])] += r["haftalik_saat"] or 0
    dagilim_var = bool(db.q1("SELECT 1 FROM ders_atamalari LIMIT 1"))
    for o in db.q("SELECT * FROM ogretmenler WHERE aktif = 1 ORDER BY ad, soyad"):
        ad = f"{o['ad']} {o['soyad']}"
        ders, isletme = yuk.get(o["id"], 0), ime.get(o["id"], 0)
        gorev = sum(n for _, n in ekders.gorev_saatleri(db, o))
        toplam = ders + isletme + gorev
        karsilik, azami = ekders.aylik_karsilik(db, o), ekders.azami_ek_ders(db, o)
        yonetici = (o["unvan"] or "") in YONETICI_UNVANLARI
        dokum = f"ders {ders}" + (f", işletmelerde meslek eğitimi {isletme}" if isletme else "") + \
                (f", rehberlik/kulüp/şeflik {gorev}" if gorev else "")
        if toplam > karsilik + azami:
            out.append(MevzuatBulgusu(
                "Kritik", "Ders yükü", f"{ad} ({o['unvan']}): haftada {toplam} saat ({dokum}). Aylık karşılığı "
                f"{karsilik} + azami ek ders {azami} = {karsilik + azami} saat; {toplam - karsilik - azami} saat "
                "verilemez/ödenemez. Dersin bir kısmını başka öğretmene devredin.",
                f"{KARAR} md.5, md.6", f"{ARACLAR_SAYFASI}/Ders Devri"))
        elif dagilim_var and not yonetici and toplam < karsilik:
            out.append(MevzuatBulgusu(
                "Uyarı", "Ders yükü", f"{ad}: haftada {toplam} saat ({dokum}); aylık karşılığı {karsilik} saat "
                "dolmuyor. Eksik saat için ders dağılımını gözden geçirin (norm fazlası ya da görevlendirme "
                "gerekebilir).", f"{KARAR} md.5", f"{ARACLAR_SAYFASI}/Yük Analizi"))
        if isletme > ime_azami:
            out.append(MevzuatBulgusu(
                "Kritik", "İşletmelerde meslek eğitimi", f"{ad}: haftada {isletme} saat işletmelerde meslek eğitimi; "
                f"okulunuz için azami {ime_azami} saat.", f"{KARAR} md.15", "Koordinatörlük"))
        for g in range(1, 6):
            if gunluk and ime_gun.get((o["id"], g), 0) > gunluk:
                out.append(MevzuatBulgusu(
                    "Kritik", "İşletmelerde meslek eğitimi", f"{ad}: {_gun_adi(g)} günü "
                    f"{ime_gun[(o['id'], g)]} saat işletmelerde meslek eğitimi; günde en çok {gunluk} saat verilir.",
                    f"{KARAR} md.15", "Koordinatörlük"))
        if (o["oncelikli_tercih"] or "").strip() and not (o["musait_olmayan"] or "").strip():
            out.append(MevzuatBulgusu(
                "Uyarı", "Öğretmen tercihi", f"{ad} ({o['oncelikli_tercih']}): ders programında tercihi dikkate "
                "alınmalı; tercih ettiği boş saatleri 'Müsait Olmadığı Saatler' alanına işleyin.",
                f"{OKY} md.12", "Öğretmenler"))
    return out


# ------------------------------------------------------------------ program (OKY md.12)

def _hucreler(db):
    return db.q("""SELECT ph.atama_id, ph.gun, ph.saat, da.sinif_id, s.ad AS sinif, s.okul_gunleri, s.program,
                          d.ad AS ders, d.atolye_gerekli, d.tur AS ders_tur, COALESCE(da.blok, d.blok, 1) AS blok
                   FROM program_hucreleri ph JOIN ders_atamalari da ON da.id = ph.atama_id
                   JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id""")


def program_denetimi(db) -> list[MevzuatBulgusu]:
    out: list[MevzuatBulgusu] = []
    S = db.ayar("gunluk_ders_saati")
    ogle = db.ayar("program_ogle_arasi")
    ogle = ogle if 0 < ogle < S else S // 2
    hucreler = _hucreler(db)
    gunler: dict[int, set[int]] = defaultdict(set)
    saatler: dict[tuple[int, int], list[int]] = defaultdict(list)
    sinif_gun: dict[tuple[int, int], dict[str, list[int]]] = defaultdict(lambda: {"teori": [], "uygulama": []})
    bilgi = {}
    for h in hucreler:
        bilgi[h["atama_id"]] = h
        gunler[h["atama_id"]].add(h["gun"])
        saatler[(h["atama_id"], h["gun"])].append(h["saat"])
        tur = "uygulama" if program.uygulamali_mi(h["atolye_gerekli"], h["ders_tur"]) else "teori"
        sinif_gun[(h["sinif_id"], h["gun"])][tur].append(h["saat"])
    ilk_son_ihlal = []
    for aid, gs in gunler.items():
        h = bilgi[aid]
        if not program.ilk_son_gun_dersi(h["ders"]):
            continue
        okul = gunler_listesi(h["okul_gunleri"]) or [1, 2, 3, 4, 5]
        if len(okul) > 2 and gs - {okul[0], okul[-1]}:
            ilk_son_ihlal.append(f"{h['sinif']} - {h['ders']} ({', '.join(_gun_adi(g) for g in sorted(gs))})")
    if ilk_son_ihlal:
        out.append(MevzuatBulgusu(
            "Uyarı", "Beden eğitimi / müzik", "Haftanın ilk ve son okul gününe konmamış: " + "; ".join(ilk_son_ihlal[:8])
            + (" …" if len(ilk_son_ihlal) > 8 else "") + ". Kilitleri açıp yeniden yerleştirin ya da elle taşıyın.",
            f"{OKY} md.12 (bayrak törenleri)", f"{PROGRAM_SAYFASI}/{SEKME_TABLO}"))
    ardisik = []
    for (aid, g), hs in saatler.items():
        h = bilgi[aid]
        if (h["blok"] or 1) > 1 and program.uygulamali_mi(h["atolye_gerekli"], h["ders_tur"]):
            hs = sorted(hs)
            if hs[-1] - hs[0] + 1 != len(hs):
                ardisik.append(f"{h['sinif']} - {h['ders']} ({_gun_adi(g)} {', '.join(map(str, hs))}. saat)")
    if ardisik:
        out.append(MevzuatBulgusu(
            "Uyarı", "Uygulamalı meslek dersi", "Ardışık saatlerde değil: " + "; ".join(ardisik[:8]) +
            (" …" if len(ardisik) > 8 else ""), f"{OKY} md.12", f"{PROGRAM_SAYFASI}/{SEKME_TABLO}"))
    ters = []
    adlar = {h["sinif_id"]: h["sinif"] for h in hucreler}
    for (sid, g), x in sinif_gun.items():
        if x["teori"] and x["uygulama"] and max(x["teori"]) > ogle and min(x["uygulama"]) <= ogle:
            ters.append(f"{adlar[sid]} {_gun_adi(g)}")
    if ters:
        out.append(MevzuatBulgusu(
            "Bilgi", "Teori / uygulama", "Aynı gün teorik ders öğleden sonraya, uygulamalı ders öğleden önceye "
            "düşmüş: " + ", ".join(ters[:10]) + (" …" if len(ters) > 10 else "") + ". 'Teorik dersler öğleden önce' "
            "parametresi açıkken yeniden yerleştirme bunu azaltır.", f"{OKY} md.12",
            f"{PROGRAM_SAYFASI}/{SEKME_TABLO}"))
    return out


def sinif_denetimi(db) -> list[MevzuatBulgusu]:
    out: list[MevzuatBulgusu] = []
    rehbersiz = []
    for r in db.q("SELECT id, ad, program, okul_gunleri, rehber_ogretmen_id FROM siniflar ORDER BY seviye, ad"):
        n = len(gunler_listesi(r["okul_gunleri"]) or [1, 2, 3, 4, 5])
        if mem_mi(r["program"]) and not 1 <= n <= 2:
            out.append(MevzuatBulgusu("Kritik", "MEM teorik eğitim günü", f"{r['ad']}: okulda haftada {n} gün; MEM "
                                      "teorik eğitimi en az 1, en fazla 2 gün olur.", f"{OKY} md.12/3",
                                      "Sınıflar / Şubeler"))
        if not r["rehber_ogretmen_id"]:
            rehbersiz.append(r["ad"])
    if rehbersiz:
        out.append(MevzuatBulgusu("Bilgi", "Sınıf rehber öğretmeni", "Sınıf rehber öğretmeni atanmamış: "
                                  + ", ".join(rehbersiz) + " (otomatik atama: Program Araçları > Sınıf "
                                  "Öğretmenliği).", "", f"{ARACLAR_SAYFASI}/Sınıf Öğretmenliği"))
    return out


# ------------------------------------------------------------------ norm kadro (tahmini)

def norm_genel(saat: float) -> int:
    """Norm md.18: 6-31 saate kadar 1, 31-42 saate kadar 2, fazlası her 21 saate 1 (+ artan en az 15 saate 1)."""
    if saat < 6:
        return 0
    if saat < 31:
        return 1
    if saat <= 42:
        return 2
    n, artan = divmod(saat, 21)
    return int(n) + (1 if artan >= 15 else 0)


def norm_atolye(saat: float) -> int:
    """Norm md.19: 15-41'e kadar 1, ... 161-201'e kadar 5, fazlası her 40 saate 1 (+ artan en az 20 saate 1)."""
    if saat < 15:
        return 0
    for sinir, n in ((41, 1), (81, 2), (121, 3), (161, 4)):
        if saat < sinir:
            return n
    if saat <= 201:
        return 5
    n, artan = divmod(saat, 40)
    return int(n) + (1 if artan >= 20 else 0)


def grup_sayisi(seviye: int | None, mevcut: int) -> int:
    """Norm md.22/1-ç: atölye/laboratuvarda grup çalışması yapılan alan/dal derslerinde şube grup sayısı."""
    if (seviye or 9) <= 9:
        return 1 if mevcut < 21 else 2 if mevcut < 31 else 3
    return 1 if mevcut < 17 else 2 if mevcut < 25 else 3 if mevcut < 33 else 4


def mudur_yardimcisi_normu(ogrenci: int) -> int:
    return 0 if ogrenci <= 0 else min(5, (ogrenci - 1) // 500 + 1)


def rehberlik_normu(ogrenci: int) -> int:
    """Norm md.21/2-c ve 3: 150 ve üzeri öğrencide 1, her 500 öğrencide 1 ilave."""
    return 0 if ogrenci < 150 else 1 + ogrenci // 500


@dataclass
class NormSatiri:
    brans: str
    tur: str
    ders_yuku: float
    norm: int
    mevcut: int
    aciklama: str = ""

    @property
    def fark(self) -> int:
        return self.mevcut - self.norm


def norm_kadro(db) -> list[NormSatiri]:
    from .koordinator import atolye_ogretmeni_mi
    mevcutlar = program.sinif_mevcutlari(db)
    rehberlik = program.rehberlik_dersleri(db)
    genel: dict[str, float] = defaultdict(float)
    atolye: dict[str, float] = defaultdict(float)
    gorulen: set[str] = set()
    for r in db.q("""SELECT da.*, d.ad AS ders, d.brans AS ders_brans, d.atolye_gerekli, d.tur AS ders_tur,
                            s.seviye, s.program, o.brans AS ogr_brans, o.unvan
                     FROM ders_atamalari da JOIN dersler d ON d.id = da.ders_id JOIN siniflar s ON s.id = da.sinif_id
                     LEFT JOIN ogretmenler o ON o.id = da.ogretmen_id"""):
        if (r["unvan"] or "") in YONETICI_UNVANLARI or r["ders_id"] in rehberlik:
            continue
        anahtar = (r["birlestirme"] or "").strip().casefold()
        if anahtar:
            if anahtar in gorulen:
                continue
            gorulen.add(anahtar)
        brans = (r["ders_brans"] or r["ogr_brans"] or "").strip() or "(branşı girilmemiş)"
        uyg = program.uygulamali_mi(r["atolye_gerekli"], r["ders_tur"])
        grup = 1
        if uyg and not mem_mi(r["program"]):
            grup = grup_sayisi(r["seviye"], mevcutlar.get(r["sinif_id"], 0))
        if r["ogretmen2_id"]:
            grup = max(grup, 2)
        (atolye if uyg else genel)[brans] += (r["haftalik_saat"] or 0) * grup
    ogretmenler = db.q("SELECT * FROM ogretmenler WHERE aktif = 1")
    for r in db.q("""SELECT k.haftalik_saat, o.brans FROM koordinator_gorevleri k JOIN ogretmenler o
                     ON o.id = k.ogretmen_id WHERE k.bitis IS NULL OR k.bitis = '' OR k.bitis >= ?""", (_bugun(),)):
        atolye[(r["brans"] or "").strip() or "(branşı girilmemiş)"] += r["haftalik_saat"] or 0
    sayac: dict[str, list] = defaultdict(list)
    for o in ogretmenler:
        if (o["unvan"] or "") not in YONETICI_UNVANLARI:
            sayac[(o["brans"] or "").strip() or "(branşı girilmemiş)"].append(o)
    out: list[NormSatiri] = []
    for brans in sorted(set(genel) | set(atolye) | set(sayac)):
        if "rehber" in norm(brans):
            continue
        g, a = genel.get(brans, 0.0), atolye.get(brans, 0.0)
        kisiler = sayac.get(brans, [])
        atolyeci = sum(1 for o in kisiler if atolye_ogretmeni_mi(o))
        if a and (a >= g or atolyeci * 2 > len(kisiler)):
            out.append(NormSatiri(brans, "Atölye ve laboratuvar (md.19)", g + a, norm_atolye(g + a), len(kisiler),
                                  f"atölye/lab. {a:g} + teorik {g:g} saat (İME dâhil)"))
        else:
            out.append(NormSatiri(brans, "Genel bilgi ve meslek dersleri (md.18)", g + a, norm_genel(g + a),
                                  len(kisiler)))
    ogrenci = sum(mevcutlar.values())
    my = sum(1 for o in ogretmenler if (o["unvan"] or "") in YONETICI_UNVANLARI - {"Müdür"})
    out.append(NormSatiri("Müdür yardımcısı", "Yönetici (md.10)", ogrenci, mudur_yardimcisi_normu(ogrenci), my,
                          f"{ogrenci} öğrenci/çırak (ilave normlar: pansiyon, MEM vb. ayrıca değerlendirilir)"))
    rehber = sum(1 for o in ogretmenler if "rehber" in norm(o["brans"]))
    out.append(NormSatiri("Rehberlik", "Rehberlik (md.21)", ogrenci, rehberlik_normu(ogrenci), rehber,
                          f"{ogrenci} öğrenci/çırak"))
    return out


def norm_bulgulari(satirlar: list[NormSatiri]) -> list[MevzuatBulgusu]:
    out = []
    for s in satirlar:
        if s.fark < 0:
            out.append(MevzuatBulgusu("Uyarı", "Norm kadro", f"{s.brans}: haftalık ders yükü {s.ders_yuku:g} saat, "
                                      f"tahmini norm {s.norm}, mevcut {s.mevcut} — {-s.fark} öğretmen ihtiyacı "
                                      "(ücretli/görevlendirme gerekebilir).", f"{NORM} md.18-22"))
        elif s.fark > 0 and s.tur.startswith(("Genel", "Atölye")):
            out.append(MevzuatBulgusu("Bilgi", "Norm kadro", f"{s.brans}: tahmini norm {s.norm}, mevcut {s.mevcut} — "
                                      f"{s.fark} norm fazlası olabilir.", f"{NORM} md.18-22"))
    return out


def mevzuat_denetimi(db) -> list[MevzuatBulgusu]:
    return _sirala(sinif_denetimi(db) + yuk_denetimi(db) + program_denetimi(db) + norm_bulgulari(norm_kadro(db)))


# ------------------------------------------------------------------ iş adımları (YABİL SDD iş adımlarından)

@dataclass
class IsAdimi:
    no: int
    baslik: str
    durum: bool | None  # True tamam, False eksik, None bilgi / isteğe bağlı
    detay: str
    git: str = ""


def is_adimlari(db) -> list[IsAdimi]:
    from . import cerceve
    S = db.ayar("gunluk_ders_saati")
    k = db.kurum()
    siniflar = db.q("SELECT id, ad, program, okul_gunleri, rehber_ogretmen_id FROM siniflar")
    ogretmenler = db.q("SELECT * FROM ogretmenler WHERE aktif = 1")
    rows = db.q("""SELECT da.id, da.ogretmen_id, da.haftalik_saat, d.atolye_gerekli, s.ad AS sinif, d.ad AS ders
                   FROM ders_atamalari da JOIN dersler d ON d.id = da.ders_id JOIN siniflar s ON s.id = da.sinif_id""")
    hucre = db.q1("SELECT COUNT(*) c FROM program_hucreleri")["c"]
    kilitli = db.q1("SELECT COUNT(*) c FROM program_hucreleri WHERE kilitli = 1")["c"]
    adimlar: list[IsAdimi] = []

    def ekle(baslik: str, durum, detay: str, git: str = "") -> None:
        adimlar.append(IsAdimi(len(adimlar) + 1, baslik, durum, detay, git))

    ekle("Kurum, eğitim yılı ve günlük ders saati", bool((k["ad"] or "").strip() and S),
         f"{k['ad'] or 'Kurum adı girilmemiş'} — {k['egitim_yili']} — günde {S} ders saati",
         "Ayarlar ve Mevzuat Parametreleri")
    mem_hata = [r["ad"] for r in siniflar if mem_mi(r["program"])
                and not 1 <= len(gunler_listesi(r["okul_gunleri"]) or [1, 2, 3, 4, 5]) <= 2]
    ekle("Sınıflar / şubeler; okul ve işletme günleri (MEM 1-2 gün)", bool(siniflar) and not mem_hata,
         f"{len(siniflar)} şube" + (f"; MEM okul günü hatalı: {', '.join(mem_hata)}" if mem_hata else ""),
         "Sınıflar / Şubeler")
    tercihsiz = [f"{o['ad']} {o['soyad']}" for o in ogretmenler
                 if (o["oncelikli_tercih"] or "").strip() and not (o["musait_olmayan"] or "").strip()]
    bransiz = sum(1 for o in ogretmenler if not (o["brans"] or "").strip())
    ekle("Öğretmenler; unvan, branş, müsaitlik ve öncelikli tercihler (md.12)", bool(ogretmenler) and not tercihsiz,
         f"{len(ogretmenler)} öğretmen" + (f"; branşı boş {bransiz}" if bransiz else "")
         + (f"; tercihi işlenmemiş: {', '.join(tercihsiz)}" if tercihsiz else ""), "Öğretmenler")
    uyumsuz = cerceve.uyumsuzluklar(db) if cerceve.veri_var() else []
    ekle("Ders dağılımı çerçeve öğretim programına uygun", bool(rows) and not uyumsuz,
         (f"{len(rows)} sınıf-ders ataması" if rows else "Ders dağılımı boş")
         + (f"; uyumsuz sınıf: {', '.join(u.sinif for u in uyumsuz[:6])}" if uyumsuz else ""),
         f"{PROGRAM_SAYFASI}/{SEKME_CERCEVE}")
    ogretmensiz = [f"{r['sinif']} - {r['ders']}" for r in rows if not r["ogretmen_id"] and r["haftalik_saat"]]
    ekle("Öğretmenlere ders atama ('Tamam': öğretmensiz ders kalmadı)", bool(rows) and not ogretmensiz,
         (f"Öğretmensiz {len(ogretmensiz)} ders: " + ", ".join(ogretmensiz[:5])) if ogretmensiz
         else "Bütün derslere öğretmen atanmış", f"{PROGRAM_SAYFASI}/{SEKME_DAGILIM}")
    mekan_yok = [a.etiket for a in program.atamalari_oku(db)
                 if a.uygulamali and a.odalar == [None] and a.saat] if rows else []
    atolye_sayisi = db.q1("SELECT COUNT(*) c FROM atolyeler")["c"]
    ekle("Fiziki mekânlar (atölye / laboratuvar / derslik)", not mekan_yok,
         f"{atolye_sayisi} mekân" + (f"; mekânı olmayan uygulamalı ders: {', '.join(mekan_yok[:5])}"
                                    if mekan_yok else ""), "Atölye / Laboratuvarlar")
    yuk_kritik = [b for b in yuk_denetimi(db) if b.seviye == "Kritik"]
    ekle("Ders yükü mevzuata uygun (aylık karşılık, azami ek ders, İME)", not yuk_kritik,
         f"{len(yuk_kritik)} kritik bulgu" if yuk_kritik else "Aşım yok", f"{ARACLAR_SAYFASI}/Yük Analizi")
    kisit = []
    if db.ayar("program_ogle_arasi"):
        kisit.append(f"öğle arası {db.ayar('program_ogle_arasi')}. saatten sonra")
    if db.ayar("program_ogretmen_gunluk_azami"):
        kisit.append(f"öğretmen günde en çok {db.ayar('program_ogretmen_gunluk_azami')} saat")
    if db.ayar("program_koord_gunu_bos"):
        kisit.append("koordinatörlük günü boş")
    if (db.ayar("program_genel_kapali") or "").strip():
        kisit.append(f"genel kapalı saatler {db.ayar('program_genel_kapali')}")
    gruplar = db.q1("SELECT COUNT(*) c FROM program_ders_gruplari WHERE aktif = 1")["c"]
    if gruplar:
        kisit.append(f"{gruplar} 'aynı güne gelmesin' grubu")
    kisit.append("kurallar gevşetilebilir" if db.ayar("program_kural_gevset") else "parametrelere kesin uyulur")
    ekle("Sınırlamalar ve dağıtım parametreleri", None, "; ".join(kisit), f"{ARACLAR_SAYFASI}/Kısıtlar")
    ekle("Meslek derslerini çakma / kilitleme (isteğe bağlı)", None,
         f"{kilitli} kilitli hücre" if kilitli else "Kilitli hücre yok", f"{ARACLAR_SAYFASI}/Toplu Çakma")
    on = program.on_denetim(db)
    kritik = [b for b in on if b.seviye == "Kritik"]
    ekle("TEST: ön denetim (sınıf, öğretmen, mekân, blok)", not kritik,
         f"{len(kritik)} kritik, {sum(1 for b in on if b.seviye == 'Uyarı')} uyarı" if on else "Sorun yok",
         f"{PROGRAM_SAYFASI}/{SEKME_TABLO}")
    eksik = program.eksik_saatler(db)
    ekle("DAĞITIM: otomatik yerleştirme", bool(hucre) and not eksik,
         "Henüz dağıtım yapılmadı" if not hucre else
         (f"{len(eksik)} dersin saati eksik — 'Neden Yerleşmedi?' ile nedenleri görün" if eksik
          else f"Bütün dersler yerleşti ({hucre} saat)"), f"{PROGRAM_SAYFASI}/{SEKME_TABLO}")
    sorunlar = (program.catismalar(db) + program.kural_ihlalleri(db)) if hucre else []
    ekle("KONTROL: çakışma ve kural ihlali yok", bool(hucre) and not sorunlar,
         f"{len(sorunlar)} sorun" if sorunlar else ("Program yok" if not hucre else "Temiz"),
         f"{PROGRAM_SAYFASI}/{SEKME_TABLO}")
    md12 = program_denetimi(db) if hucre else []
    ekle("Yönetmelik md.12 uyumu (beden/müzik günü, uygulamalı ardışık, teori-uygulama)",
         (not [b for b in md12 if b.seviye != "Bilgi"]) if hucre else None,
         "; ".join(b.konu for b in md12) or ("Uygun" if hucre else "Program yok"), f"{PROGRAM_SAYFASI}/{SEKME_ADIMLAR}")
    rehbersiz = [r["ad"] for r in siniflar if not r["rehber_ogretmen_id"]]
    ekle("Sınıf rehber öğretmenleri (sınıf öğretmenliği)", bool(siniflar) and not rehbersiz,
         f"Atanmamış: {', '.join(rehbersiz[:8])}" if rehbersiz else "Hepsi atanmış",
         f"{ARACLAR_SAYFASI}/Sınıf Öğretmenliği")
    surum = db.q1("SELECT ad, tarih FROM program_surumleri ORDER BY id DESC LIMIT 1")
    ekle("Program sürümünü kaydet / yedek al", bool(surum),
         f"Son sürüm: {surum['ad']} ({surum['tarih'] or ''})" if surum else "Kayıtlı sürüm yok",
         f"{ARACLAR_SAYFASI}/Program Sürümleri")
    ekle("e-Okul'a giriş; öğretmenler kurulu, müdür onayı ve imza karşılığı tebliğ (md.12)", None,
         "'e-Okul Çizelgesi' ile görevlendirme ve haftalık programı e-Okul'a girin, 'e-Okul ile Karşılaştır' ile "
         "doğrulayın; 'Tebliğ ve Onay Belgesi'ni imzalatın, el programlarını dağıtın.", f"{PROGRAM_SAYFASI}/{SEKME_ADIMLAR}")
    return adimlar


# ------------------------------------------------------------------ e-Okul eşgüdümü

EOKUL_PROGRAM_BASLIKLARI = ["Sınıf/Şube", "Gün", "Ders Saati (1, 2, ...)", "Ders Adı", "Kısa Ad",
                            "Öğretmen Adı Soyadı", "2. Öğretmen (grup/ortak ders)", "Atölye/Lab./Derslik"]
EOKUL_GOREV_BASLIKLARI = ["Sınıf/Şube", "Ders Adı", "Kısa Ad", "Haftalık Saat", "Öğretmen Adı Soyadı",
                          "e-Okul Kısaltması", "2. Öğretmen", "Sabit Atölye/Lab."]


def eokul_gorevlendirme(db) -> list[list]:
    from .eokul_program import ogretmen_kodu
    out = []
    for r in db.q("""SELECT s.ad AS sinif, d.ad AS ders, d.kisa_ad, da.haftalik_saat,
                            TRIM(COALESCE(o.ad, '') || ' ' || COALESCE(o.soyad, '')) AS ogretmen,
                            TRIM(COALESCE(o2.ad, '') || ' ' || COALESCE(o2.soyad, '')) AS ogretmen2, a.ad AS atolye
                     FROM ders_atamalari da JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id
                     LEFT JOIN ogretmenler o ON o.id = da.ogretmen_id LEFT JOIN ogretmenler o2 ON o2.id = da.ogretmen2_id
                     LEFT JOIN atolyeler a ON a.id = da.atolye_id ORDER BY s.seviye, s.ad, d.ad"""):
        out.append([r["sinif"], r["ders"], r["kisa_ad"] or "", r["haftalik_saat"], r["ogretmen"],
                    ogretmen_kodu(r["ogretmen"]) if r["ogretmen"] else "", r["ogretmen2"], r["atolye"] or ""])
    return out


def eokul_program_satirlari(db) -> list[list]:
    out = []
    for r in db.q("""SELECT s.ad AS sinif, ph.gun, ph.saat, d.ad AS ders, d.kisa_ad,
                            TRIM(COALESCE(o.ad, '') || ' ' || COALESCE(o.soyad, '')) AS ogretmen,
                            TRIM(COALESCE(o2.ad, '') || ' ' || COALESCE(o2.soyad, '')) AS ogretmen2,
                            TRIM(COALESCE(a.ad, '') || CASE WHEN a2.ad IS NULL THEN '' ELSE ' / ' || a2.ad END) AS mekan
                     FROM program_hucreleri ph JOIN ders_atamalari da ON da.id = ph.atama_id
                     JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id
                     LEFT JOIN ogretmenler o ON o.id = da.ogretmen_id LEFT JOIN ogretmenler o2 ON o2.id = da.ogretmen2_id
                     LEFT JOIN atolyeler a ON a.id = ph.atolye_id LEFT JOIN atolyeler a2 ON a2.id = ph.atolye2_id
                     ORDER BY s.seviye, s.ad, ph.gun, ph.saat"""):
        out.append([r["sinif"], _gun_adi(r["gun"]), r["saat"], r["ders"], r["kisa_ad"] or "", r["ogretmen"],
                    r["ogretmen2"], r["mekan"]])
    return out


def eokul_tutarliligi(db) -> list[str]:
    """e-Okul'a girişten önce giderilmesi gereken tutarsızlıklar."""
    from . import cerceve
    from .eokul_program import ogretmen_kodu
    out = []
    for r in db.q("""SELECT s.ad AS sinif, d.ad AS ders FROM ders_atamalari da JOIN siniflar s ON s.id = da.sinif_id
                     JOIN dersler d ON d.id = da.ders_id WHERE da.ogretmen_id IS NULL AND da.haftalik_saat > 0
                     ORDER BY s.ad, d.ad"""):
        out.append(f"Öğretmeni atanmamış ders: {r['sinif']} - {r['ders']}")
    for etiket, gereken, yerlesen in program.eksik_saatler(db):
        out.append(f"Programda eksik saat: {etiket} ({yerlesen}/{gereken})")
    kodlar: dict[str, list[str]] = defaultdict(list)
    for o in db.q("SELECT ad, soyad FROM ogretmenler WHERE aktif = 1"):
        kod = ogretmen_kodu(f"{o['ad']} {o['soyad']}")
        if kod:
            kodlar[kod].append(f"{o['ad']} {o['soyad']}")
    for kod, adlar in sorted(kodlar.items()):
        if len(adlar) > 1:
            out.append(f"Aynı e-Okul kısaltması ({kod}): {', '.join(adlar)} — e-Okul çizelgesinde karışmaması için "
                       "derslerin açıklama satırındaki tam adları kontrol edin")
    if cerceve.veri_var():
        for u in cerceve.uyumsuzluklar(db):
            ayrinti = "; ".join(x for x in (", ".join(u.eksik[:4]), ", ".join(u.saat_farkli[:4]), u.sorun) if x)
            out.append(f"Çerçeve programa uymayan ders dağılımı: {u.sinif} ({ayrinti})")
    return out


def eokul_cizelgesi(db, yol: Path | str) -> Path:
    from .excel_io import ExcelYazici
    k = db.kurum()
    x = ExcelYazici()
    x.sayfa("Ders Görevlendirme", EOKUL_GOREV_BASLIKLARI, eokul_gorevlendirme(db),
            f"{k['ad']} - {k['egitim_yili']} Ders Görevlendirme (e-Okul ders/öğretmen ataması için)")
    x.sayfa("Haftalık Program", EOKUL_PROGRAM_BASLIKLARI, eokul_program_satirlari(db),
            f"{k['ad']} - {k['egitim_yili']} Haftalık Ders Programı (e-Okul girişi için)")
    sorunlar = eokul_tutarliligi(db)
    x.sayfa("Tutarlılık", ["Giderilecek durum"], [[s] for s in sorunlar] or [["Sorun bulunmadı"]],
            "e-Okul girişinden önce kontrol")
    return x.kaydet(yol)


@dataclass
class EokulKarsilastirma:
    eslesen: int
    farklar: list[str]
    okunan: int
    hatalar: list[str]

    @property
    def ozet(self) -> str:
        if not self.okunan:
            return "Belgede e-Okul haftalık ders programı bulunamadı."
        return (f"e-Okul'dan {self.okunan} ders saati okundu; {self.eslesen} saat programla aynı, "
                f"{len(self.farklar)} fark var.")


def _baslik_indeksi(satir: list) -> dict[str, int] | None:
    n = [norm(x) for x in satir]
    bul = {}
    for i, h in enumerate(n):
        if h.startswith("sinif") and "sinif" not in bul:
            bul["sinif"] = i
        elif h == "gun":
            bul["gun"] = i
        elif h.startswith("ders saati"):
            bul["saat"] = i
        elif h == "ders adi":
            bul["ders"] = i
        elif h == "kisa ad":
            bul["kisa"] = i
        elif h.startswith("ogretmen adi"):
            bul["ogretmen"] = i
    return bul if {"sinif", "gun", "saat", "ders"} <= set(bul) else None


def _eokul_satirlari(tablolar) -> list[tuple[str, int, int, str, str, str]]:
    from .program_belge import gun_coz
    out = []
    for t in tablolar:
        rows = t.satirlar
        for i, satir in enumerate(rows[:6]):
            ix = _baslik_indeksi(list(satir))
            if not ix:
                continue
            for r in rows[i + 1:]:
                r = list(r) + [""] * 10

                def al(k):
                    return r[ix[k]] if k in ix else ""
                g = gun_coz(al("gun"))
                try:
                    h = int(float(str(al("saat")).strip()))
                except ValueError:
                    continue
                if not g or g > 5 or not str(al("sinif")).strip():
                    continue
                out.append((norm(al("sinif")), g, h, norm(al("ders")), norm(al("kisa")), norm(al("ogretmen"))))
            break
    return out


def eokul_karsilastir(db, yollar: list[Path | str]) -> EokulKarsilastirma:
    """e-Okul'dan alınan sınıf/öğretmen programı çizelgesini (PDF/Excel) programla karşılaştırır; veri yazmaz."""
    from . import eokul_program, okuyucu
    tablolar, hatalar = okuyucu.oku_coklu(yollar)
    duz = []
    i = 0
    while i < len(tablolar):
        n, uretilen = eokul_program.eokul_dilimi(tablolar, i)
        duz += uretilen if n else [tablolar[i]]
        i += max(n, 1)
    eokul = _eokul_satirlari(duz)
    bizim: dict[tuple[str, int, int], list[tuple[str, str, str, str]]] = defaultdict(list)
    for r in db.q("""SELECT s.ad AS sinif, ph.gun, ph.saat, d.ad AS ders, d.kisa_ad,
                            TRIM(COALESCE(o.ad, '') || ' ' || COALESCE(o.soyad, '')) AS ogretmen,
                            TRIM(COALESCE(o2.ad, '') || ' ' || COALESCE(o2.soyad, '')) AS ogretmen2
                     FROM program_hucreleri ph JOIN ders_atamalari da ON da.id = ph.atama_id
                     JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id
                     LEFT JOIN ogretmenler o ON o.id = da.ogretmen_id LEFT JOIN ogretmenler o2 ON o2.id = da.ogretmen2_id"""):
        bizim[(norm(r["sinif"]), r["gun"], r["saat"])].append(
            (norm(r["ders"]), norm(r["kisa_ad"]), norm(r["ogretmen"]), norm(r["ogretmen2"])))
    adlar = {norm(r["ad"]): r["ad"] for r in db.q("SELECT ad FROM siniflar")}
    eslesen, farklar, gorulen = 0, [], set()
    for sinif, g, h, ders, kisa, ogr in eokul:
        anahtar = (sinif, g, h)
        gorulen.add(anahtar)
        yer = f"{adlar.get(sinif, sinif)} {_gun_adi(g)} {h}. saat"
        bizde = bizim.get(anahtar, [])
        if not bizde:
            farklar.append(f"{yer}: e-Okul'da {ders or kisa} var, programda boş")
            continue
        ayni_ders = [x for x in bizde if ders in (x[0], x[1]) or (kisa and kisa in (x[0], x[1]))]
        if not ayni_ders:
            farklar.append(f"{yer}: e-Okul'da {ders or kisa}, programda {', '.join(x[0] for x in bizde)}")
        elif ogr and not any(ogr in (x[2], x[3]) for x in ayni_ders):
            farklar.append(f"{yer}: öğretmen farklı (e-Okul: {ogr}, program: {ayni_ders[0][2] or '-'})")
        else:
            eslesen += 1
    siniflar = {s for s, _, _ in gorulen}
    for (sinif, g, h), x in sorted(bizim.items()):
        if sinif in siniflar and (sinif, g, h) not in gorulen:
            farklar.append(f"{adlar.get(sinif, sinif)} {_gun_adi(g)} {h}. saat: programda {x[0][0]} var, e-Okul'da boş")
    return EokulKarsilastirma(eslesen, farklar, len(eokul), hatalar)


# ------------------------------------------------------------------ tebliğ

TEBLIG_BASLIKLARI = ["Sıra", "Adı Soyadı", "Branş", "Haftalık Ders", "Aylık Karşılığı", "Ek Ders", "Tebliğ Tarihi",
                     "İmza"]


def teblig_satirlari(db) -> list[list]:
    """Haftalık programın imza karşılığı tebliği için öğretmen listesi (OKY md.12)."""
    out = []
    for i, h in enumerate(ekders.tum_isaretler(db), 1):
        out.append([i, h.ad, h.brans, f"{h.toplam:g}", f"{h.maas:g}", f"{h.ucret:g}", "", ""])
    return out


def teblig_metni(db) -> str:
    k = db.kurum()
    return (f"{k['ad']} {k['egitim_yili']} eğitim-öğretim yılı haftalık ders programı, Ortaöğretim Kurumları "
            "Yönetmeliği'nin 12. maddesi gereğince öğretmenler kurulunda görüşülmüş, okul müdürünce onaylanmış ve "
            "aşağıda imzası bulunan öğretmenlere tebliğ edilmiştir.")
