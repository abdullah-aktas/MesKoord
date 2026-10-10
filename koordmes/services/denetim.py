"""Veri denetimi: eksik, hatalı veya mevzuata aykırı kayıtların taranması."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from ..mevzuat import FESIH_SAYILAN, OKUL_ICI_TURLER, isletmeye_giden_sinif
from . import cerceve, ekders, koordinator, program, sgk_risk, sigorta
from .utils import gunler_listesi, iban_gecerli, tarih, tc_gecerli

SIRA = {"Kritik": 0, "Uyarı": 1, "Bilgi": 2}


@dataclass
class Bulgu:
    seviye: str  # Kritik | Uyarı | Bilgi
    kategori: str
    mesaj: str
    git: str | None = None
    ornekler: list[str] = field(default_factory=list)

    @property
    def metin(self) -> str:
        if not self.ornekler:
            return self.mesaj
        ek = ", ".join(self.ornekler[:6]) + (f" ve {len(self.ornekler) - 6} diğer" if len(self.ornekler) > 6 else "")
        return f"{self.mesaj}: {ek}"


def _ad(r) -> str:
    return f"{r['ad']} {r['soyad']}".strip()


def denetle(db, bugun: date | None = None) -> list[Bulgu]:
    bugun = bugun or date.today()
    out: list[Bulgu] = []

    def ekle(seviye, kategori, mesaj, ornekler=None, git=None):
        if ornekler is None or ornekler:
            out.append(Bulgu(seviye, kategori, f"{mesaj} ({len(ornekler)})" if ornekler else mesaj, git,
                             list(ornekler or [])))

    k = db.kurum()
    eksik = [ad for ad, kol in [("kurum adı", "ad"), ("müdür", "mudur"), ("SGK işyeri sicil no", "sgk_isyeri_sicil"),
                                ("koordinatör müdür yardımcısı", "koordinator_mudur_yrd")] if not k[kol]]
    if eksik:
        ekle("Uyarı", "Kurum", "Kurum bilgilerinde eksik: " + ", ".join(eksik), git="Ayarlar ve Mevzuat Parametreleri")
    if k["sgk_isyeri_sicil"] and len(re.sub(r"\D", "", k["sgk_isyeri_sicil"])) != 26:
        ekle("Uyarı", "Kurum", "SGK işyeri sicil no 26 hane değil; SGK XML/Excel dosyaları üretilemez",
             git="Ayarlar ve Mevzuat Parametreleri")

    # --- öğrenciler ---
    ogr = db.q("""SELECT o.*, s.ad AS sinif, s.seviye, s.program,
                         EXISTS(SELECT 1 FROM yerlestirmeler y WHERE y.ogrenci_id = o.id AND y.durum = 'Aktif'
                                AND y.isletme_id IS NOT NULL AND y.tur NOT IN ('Okulda Alan Eğitimi')) AS isletmede
                  FROM ogrenciler o LEFT JOIN siniflar s ON s.id = o.sinif_id WHERE o.aktif = 1""")
    G = "Öğrenciler / Çıraklar"
    ekle("Kritik", "Öğrenci", "İşletmedeki öğrencilerde T.C. kimlik no eksik/geçersiz (SGK bildirimi yapılamaz)",
         [_ad(r) for r in ogr if r["isletmede"] and not tc_gecerli(r["tc"])], G)
    ekle("Uyarı", "Öğrenci", "T.C. kimlik no eksik/geçersiz",
         [_ad(r) for r in ogr if not r["isletmede"] and not tc_gecerli(r["tc"])], G)
    tc_say = Counter(r["tc"] for r in ogr if r["tc"])
    ekle("Kritik", "Öğrenci", "Aynı T.C. kimlik no birden fazla öğrencide",
         [f"{_ad(r)} ({r['tc']})" for r in ogr if r["tc"] and tc_say[r["tc"]] > 1], G)
    ekle("Uyarı", "Öğrenci", "İşletmedeki öğrencilerde IBAN eksik (ücret ödemesi için gerekli)",
         [_ad(r) for r in ogr if r["isletmede"] and not r["iban"]], G)
    ekle("Uyarı", "Öğrenci", "IBAN hatalı (TR IBAN denetiminden geçmedi)",
         [_ad(r) for r in ogr if r["iban"] and not iban_gecerli(r["iban"])], G)
    ekle("Uyarı", "Öğrenci", "Sınıfı/şubesi girilmemiş öğrenci", [_ad(r) for r in ogr if not r["sinif_id"]], G)
    ekle("Bilgi", "Öğrenci", "Veli telefonu eksik (devamsızlık bildirimi için)",
         [_ad(r) for r in ogr if not r["veli_tel"]], G)
    ekle("Uyarı", "Yerleştirme", "İşletmeye yerleştirilmemiş 12. sınıf / MEM öğrencisi",
         [f"{_ad(r)} ({r['sinif']})" for r in ogr if not r["isletmede"] and r["sinif_id"]
          and isletmeye_giden_sinif(r["program"], r["seviye"])], "Yerleştirme ve Sözleşmeler")

    # --- yerleştirmeler ---
    yer = db.q("""SELECT y.*, o.ad, o.soyad, i.ad AS isletme, s.isletme_gunleri, s.ad AS sinif, s.program,
                         (SELECT COUNT(*) FROM yerlestirmeler y2 WHERE y2.ogrenci_id = y.ogrenci_id
                          AND y2.id != y.id AND y2.isletme_id IS NOT NULL AND y2.baslangic < y.baslangic) AS onceki
                  FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                  LEFT JOIN isletmeler i ON i.id = y.isletme_id LEFT JOIN siniflar s ON s.id = o.sinif_id
                  WHERE y.durum = 'Aktif'""")
    G = "Yerleştirme ve Sözleşmeler"
    isletmede = [r for r in yer if r["tur"] not in OKUL_ICI_TURLER]
    ekle("Kritik", "Yerleştirme", "Başlangıç tarihi olmayan yerleştirme", [_ad(r) for r in yer if not r["baslangic"]], G)
    ekle("Kritik", "Yerleştirme", "Bitiş tarihi başlangıçtan önce",
         [_ad(r) for r in yer if r["bitis"] and r["baslangic"] and r["bitis"] < r["baslangic"]], G)
    ekle("Kritik", "Yerleştirme", "İşletmesi seçilmemiş işletme yerleştirmesi",
         [_ad(r) for r in isletmede if not r["isletme_id"]], G)
    by_ogr = defaultdict(list)
    for r in isletmede:
        by_ogr[r["ogrenci_id"]].append(r)
    cakisan = []
    for lst in by_ogr.values():
        for i, a in enumerate(lst):
            for b in lst[i + 1:]:
                ab, ae, bb, be = tarih(a["baslangic"]), tarih(a["bitis"]), tarih(b["baslangic"]), tarih(b["bitis"])
                if ab and bb and (ae is None or ae >= bb) and (be is None or be >= ab):
                    cakisan.append(f"{_ad(a)} ({a['isletme']} / {b['isletme']})")
    ekle("Kritik", "Yerleştirme", "Aynı öğrencinin tarihleri çakışan iki aktif yerleştirmesi", cakisan, G)
    ekle("Uyarı", "Sözleşme", "Sözleşme numarası girilmemiş", [_ad(r) for r in isletmede if not r["sozlesme_no"]], G)
    ekle("Kritik", "Sözleşme", "Sözleşme tarihi işe başlama tarihinden sonra (sözleşme başlamadan imzalanmalı)",
         [_ad(r) for r in isletmede if r["sozlesme_tarihi"] and r["baslangic"]
          and r["sozlesme_tarihi"] > r["baslangic"]], G)
    ekle("Uyarı", "Sınıf", "İşletmede öğrencisi olan ama işletme günleri tanımlanmamış sınıf",
         sorted({r["sinif"] for r in isletmede if r["sinif"] and not r["isletme_gunleri"]}), "Sınıflar / Şubeler")
    gec = [b for b in sigorta.bekleyen_bildirimler(db, bugun) if b.gecikti]
    ekle("Kritik", "SGK", "Süresi geçmiş SGK bildirimi", [f"{b.ogrenci} ({b.tur})" for b in gec],
         "SGK Sigorta İşlemleri")
    riskler = [r for r in sgk_risk.analiz(db, bugun) if r.seviye != "Bilgi"
               and "bildirgesi" not in r.konu and "T.C." not in r.konu]
    for konu in dict.fromkeys(r.konu for r in riskler):
        lst = [r for r in riskler if r.konu == konu]
        ekle(lst[0].seviye, "SGK", f"{konu} (ayrıntı: SGK > Risk ve Öneriler)", [r.kisi for r in lst],
             "SGK Sigorta İşlemleri")
    _yonetmelik_yerlestirme(db, bugun, isletmede, ekle)

    # --- işletmeler ---
    isl = db.q("""SELECT i.*, COUNT(y.id) AS n, SUM(y.tur = 'Staj') AS staj, MIN(y.baslangic) AS ilk_baslangic,
                         EXISTS(SELECT 1 FROM koordinator_gorevleri kg WHERE kg.isletme_id = i.id) AS gorevli
                  FROM isletmeler i JOIN yerlestirmeler y ON y.isletme_id = i.id AND y.durum = 'Aktif'
                  GROUP BY i.id""")
    G = "İşletmeler"
    ekle("Uyarı", "İşletme", "Usta öğretici / eğitici personel tanımlanmamış (yasal zorunluluk)",
         [r["ad"] for r in isl if not r["usta_ogretici"]], G)
    ekle("Uyarı", "İşletme", "Personel sayısı girilmemiş (ücret oranı ve devlet katkısını etkiler)",
         [r["ad"] for r in isl if not r["personel_sayisi"]], G)
    ekle("Uyarı", "İşletme", "Kontenjanı aşılmış işletme",
         [f"{r['ad']} ({r['n']}/{r['kontenjan']})" for r in isl if r["kontenjan"] and r["n"] > r["kontenjan"]], G)
    ekle("Bilgi", "İşletme", "Vergi numarası eksik", [r["ad"] for r in isl if not r["vergi_no"]], G)
    kapsam_disi = {r["id"] for r in isl if r["doner_sermaye"] or (r["il_disi"] and r["staj"] == r["n"])}
    ekle("Kritik", "Koordinatörlük", "Koordinatör öğretmen görevlendirilmemiş işletme",
         [r["ad"] for r in isl if not r["gorevli"] and r["id"] not in kapsam_disi], "Koordinatörlük")
    _yonetmelik_isletme(db, bugun, isl, ekle)

    # --- öğretmen ve program ---
    G = "Ders Dağılımı ve Atölye Yerleşimi"
    yuk = {r["id"]: r for r in db.q("""SELECT o.*, (SELECT COUNT(DISTINCT ph.gun * 100 + ph.saat)
                                                    FROM program_hucreleri ph JOIN ders_ogretmenleri dog
                                                    ON dog.atama_id = ph.atama_id WHERE dog.ogretmen_id = o.id) AS ders
                                       FROM ogretmenler o WHERE o.aktif = 1""")}
    asan = [f"{_ad(r)} ({r['ders']} saat)" for r in yuk.values()
            if r["ders"] > ekders.aylik_karsilik(db, r) + ekders.azami_ek_ders(db, r)]
    ekle("Uyarı", "Öğretmen", "Haftalık ders yükü aylık karşılık + azami ek ders sınırını aşıyor", asan, G)
    sinir = koordinator.haftalik_azami(db)
    ekle("Uyarı", "Koordinatörlük", f"Haftalık koordinatörlük saati sınırı ({sinir}) aşılmış",
         [f"{t['ogretmen']} ({t['toplam']})" for t in koordinator.gorev_ozeti(db) if t["toplam"] > sinir],
         "Koordinatörlük")
    dersli = {(r["ogretmen_id"], r["gun"]) for r in db.q(
        """SELECT DISTINCT dog.ogretmen_id, ph.gun FROM program_hucreleri ph
           JOIN ders_ogretmenleri dog ON dog.atama_id = ph.atama_id""")}
    gunler = ["", "Pzt", "Sal", "Çar", "Per", "Cum"]
    ekle("Uyarı", "Koordinatörlük", "Koordinatörlük günü ders programıyla çakışan öğretmen",
         sorted({f"{_ad(yuk[r['ogretmen_id']])} ({gunler[r['gun']] if r['gun'] <= 5 else r['gun']})"
                 for r in db.q("SELECT * FROM koordinator_gorevleri")
                 if (r["ogretmen_id"], r["gun"]) in dersli and r["ogretmen_id"] in yuk}), "Koordinatörlük")
    ekle("Kritik", "Program", "Ders programında çakışma", program.catismalar(db), G)
    ekle("Uyarı", "Program", "Programa tam yerleşmemiş ders",
         [f"{e} ({y}/{g})" for e, g, y in program.eksik_saatler(db)], G)
    uyum = cerceve.uyumsuzluklar(db)
    kisalt = lambda lst: ", ".join(lst[:3]) + ("…" if len(lst) > 3 else "")
    ekle("Uyarı", "Program", "Çerçeve öğretim programındaki zorunlu ders, ders dağılımında yok",
         [f"{u.sinif} ({kisalt(u.eksik)})" for u in uyum if u.eksik], G)
    ekle("Uyarı", "Program", "Haftalık saati çerçeve öğretim programından farklı ders (dağılımdaki/olması gereken)",
         [f"{u.sinif} ({kisalt(u.saat_farkli)})" for u in uyum if u.saat_farkli], G)
    ekle("Bilgi", "Program", "Çerçeve öğretim programı belirlenemeyen sınıf (program, alan ve dalını kontrol edin)",
         [f"{u.sinif} ({u.sorun})" for u in uyum if u.sorun], "Sınıflar / Şubeler")
    ekle("Uyarı", "Program", "Öğretmeni atanmamış ders",
         [f"{r['s']} - {r['d']}" for r in db.q("""SELECT s.ad AS s, d.ad AS d FROM ders_atamalari da
                                                  JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id
                                                  WHERE da.ogretmen_id IS NULL""")], G)

    # --- takvim ve parametreler ---
    yil = int((k["egitim_yili"] or f"{bugun.year}")[:4]) if (k["egitim_yili"] or "")[:4].isdigit() else bugun.year
    n_tatil = db.q1("SELECT COUNT(*) c FROM tatiller WHERE baslangic BETWEEN ? AND ?",
                    (f"{yil}-09-01", f"{yil + 1}-08-31"))["c"]
    if n_tatil < 3:
        ekle("Uyarı", "Takvim", f"{yil}-{yil + 1} eğitim yılı tatil günleri eksik (SGK gün, ek ders ve ziyaret "
                                "planı tatillere göre hesaplanır)", git="Tatil Günleri")
    eksik_tarih = [ad for ad, kol in [("ders yılı başlangıcı", "ders_yili_baslangic"),
                                      ("1. dönem sonu", "birinci_donem_sonu"), ("ders yılı sonu", "ders_yili_sonu")]
                   if not k[kol]]
    if eksik_tarih:
        ekle("Bilgi", "Takvim", "Kurum bilgilerinde " + ", ".join(eksik_tarih) + " girilmemiş (sözleşme süresi ve "
                                "puan çizelgesi hatırlatmaları bu tarihlere göre yapılır)",
             git="Ayarlar ve Mevzuat Parametreleri")
    if db.ayar("gecici12_aktif"):
        ekle("Bilgi", "Mevzuat", "3308 Geçici 12. madde açık: bu eğitim yılında da uygulandığını doğrulayın",
             git="Ayarlar ve Mevzuat Parametreleri")
    out.sort(key=lambda b: (SIRA[b.seviye], b.kategori))
    return out


def _yonetmelik_yerlestirme(db, bugun: date, isletmede, ekle) -> None:
    """Ortaöğretim Kurumları Yönetmeliği md.134 (gün dağılımı) ve md.143 (sözleşme süreleri, fesih)."""
    from . import mesleki_egitim
    G = "Yerleştirme ve Sözleşmeler"
    yil_basi = mesleki_egitim.ders_yili_baslangici(db)
    gecikmis = []
    for r in isletmede:
        bas = tarih(r["baslangic"])
        if r["sozlesme_tarihi"] or not r["isletme_id"] or not bas:
            continue
        mem = (r["program"] or "") == "MEM"
        if mem and r["onceki"]:
            son = bas + timedelta(days=int(db.ayar("isyeri_degisikligi_gun")))
        else:
            ilk = max(bas, yil_basi) if yil_basi else bas
            son = ilk + timedelta(days=int(db.ayar("mem_sozlesme_sure_gun" if mem else "sozlesme_sure_gun")))
        if bugun > son:
            gecikmis.append(f"{_ad(r)} (son gün {son:%d.%m.%Y})")
    ekle("Kritik", "Sözleşme", "Sözleşme imza süresi geçtiği hâlde sözleşme tarihi girilmemiş (md.143)", gecikmis, G)

    sure = int(db.ayar("isyeri_degisikligi_gun"))
    bekleyen = []
    for r in db.q("""SELECT o.ad, o.soyad, MAX(y.bitis) AS bitis FROM ogrenciler o
                     JOIN siniflar s ON s.id = o.sinif_id JOIN yerlestirmeler y ON y.ogrenci_id = o.id
                     WHERE o.aktif = 1 AND s.program = 'MEM' AND y.durum != 'Aktif'
                       AND y.fesih_nedeni = 'İşyeri değişikliği' AND NOT EXISTS (
                           SELECT 1 FROM yerlestirmeler y2 WHERE y2.ogrenci_id = o.id AND y2.durum = 'Aktif'
                           AND y2.isletme_id IS NOT NULL) GROUP BY o.id"""):
        b = tarih(r["bitis"])
        if b:
            bekleyen.append((bugun > b + timedelta(days=sure), f"{_ad(r)} (son gün {b + timedelta(days=sure):%d.%m.%Y})"))
    ekle("Kritik", "Sözleşme", f"MEM: işyeri değişikliğinden sonra {sure} gün içinde yeni sözleşme yapılmamış (md.143)",
         [m for g, m in bekleyen if g], G)
    ekle("Uyarı", "Sözleşme", f"MEM: işyeri değiştiren öğrenci için {sure} gün içinde yeni sözleşme yapılmalı (md.143)",
         [m for g, m in bekleyen if not g], G)
    ekle("Bilgi", "Sözleşme", "Fesih nedeni yönetmelikteki hâllerden biri olarak seçilmemiş (md.143: 3308 md.22, "
                              "devamsızlık, sağlık veya karşılıklı fesih)",
         [f"{r['ad']} {r['soyad']} ({r['fesih_nedeni'] or 'boş'})" for r in db.q(
             """SELECT o.ad, o.soyad, y.fesih_nedeni FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                WHERE y.durum = 'Feshedildi' AND o.aktif = 1""")
          if r["fesih_nedeni"] not in FESIH_SAYILAN - {"Fesih"}], G)

    gunler = []
    cakisan = []
    for s in db.q("""SELECT DISTINCT s.ad, s.program, s.okul_gunleri, s.isletme_gunleri FROM siniflar s
                     JOIN ogrenciler o ON o.sinif_id = s.id JOIN yerlestirmeler y ON y.ogrenci_id = o.id
                     WHERE y.durum = 'Aktif' AND y.isletme_id IS NOT NULL
                       AND y.tur = 'İşletmede Mesleki Eğitim'"""):
        isl, okul = set(gunler_listesi(s["isletme_gunleri"])), set(gunler_listesi(s["okul_gunleri"]))
        if not isl:
            continue
        if isl & okul:
            cakisan.append(s["ad"])
        elif (s["program"] or "") != "MEM" and not ({len(isl), len(okul)} == {2, 3}):
            gunler.append(f"{s['ad']} ({len(isl)} gün işletme + {len(okul)} gün okul)")
    ekle("Uyarı", "Sınıf", "Okul günleri ile işletme günleri çakışıyor", cakisan, "Sınıflar / Şubeler")
    ekle("Uyarı", "Sınıf", "İşletmede mesleki eğitim haftada 3 gün işletme + 2 gün okul (veya 2+3) olmalı (md.134)",
         gunler, "Sınıflar / Şubeler")

    for p in mesleki_egitim.puan_teslimleri(db, bugun, gun_once=0):
        if bugun > p.son_teslim and p.eksik:
            ekle("Kritik", "Değerlendirme", f"{p.donem}. dönem puan çizelgesi teslim süresi geçti "
                                            f"({p.son_teslim:%d.%m.%Y}, md.89/1-g); işletme notu eksik öğrenci",
                 p.eksik, "Devamsızlık ve Değerlendirme")


def _yonetmelik_isletme(db, bugun: date, isl, ekle) -> None:
    """Ortaöğretim Kurumları Yönetmeliği md.88, 135, 140-142, 146, 148, 152."""
    G = "İşletmeler"
    sinir = int(db.ayar("usta_ogretici_ogrenci"))
    ekle("Uyarı", "İşletme", f"Bir usta öğretici / eğitici personele {sinir} öğrenciden fazlası düşüyor (md.135)",
         [f"{r['ad']} ({r['n']} öğrenci / {r['usta_ogretici_sayisi'] or 1} usta öğretici)" for r in isl
          if r["n"] > sinir * max(1, r["usta_ogretici_sayisi"] or 1)], G)
    esik = int(db.ayar("egitim_birimi_esigi"))
    ekle("Uyarı", "İşletme", f"{esik} ve üzeri öğrencisi olduğu hâlde eğitim birimi kurulmamış (md.142, md.148)",
         [f"{r['ad']} ({r['n']} öğrenci)" for r in isl if r["n"] >= esik and not r["egitim_birimi"]], G)
    ekle("Uyarı", "İşletme", "Uygunluk tespit tarihi girilmemiş (işletme belirleme komisyonu, md.140-142)",
         [r["ad"] for r in isl if not r["uygunluk_tarihi"]], G)
    ekle("Bilgi", "İşletme", "Usta öğreticinin ustalık / iş pedagojisi belgesi işaretlenmemiş (md.152)",
         [r["ad"] for r in isl if r["usta_ogretici"] and not r["usta_belgesi"]], G)
    gun = int(db.ayar("plan_onay_gun"))
    ekle("Uyarı", "İşletme", f"Usta öğretici eğitim planı ilk {gun} gün içinde onaya sunulmamış (md.146)",
         [r["ad"] for r in isl if not r["plan_onay_tarihi"] and tarih(r["ilk_baslangic"])
          and bugun > tarih(r["ilk_baslangic"]) + timedelta(days=gun)], G)
    ekle("Bilgi", "Koordinatörlük", "Okul döner sermaye işletmesine koordinatör görevlendirilmiş (md.88/8)",
         [r["ad"] for r in isl if r["doner_sermaye"] and r["gorevli"]], "Koordinatörlük")

    gerekli = Counter(ih.isletme_id for ih in koordinator.isletme_ihtiyaclari(db, bugun))
    mevcut = Counter(r["isletme_id"] for r in db.q("SELECT DISTINCT isletme_id, ogretmen_id FROM koordinator_gorevleri"))
    adlar = {r["id"]: r["ad"] for r in isl}
    ekle("Uyarı", "Koordinatörlük", f"Aynı işletme ve alanda {db.ayar('koord_grup_ogrenci')} öğrenciden fazlasına "
                                    "tek koordinatör öğretmen (md.88/2-f)",
         [f"{adlar.get(i, i)} ({mevcut[i]}/{n} öğretmen)" for i, n in gerekli.items() if 0 < mevcut[i] < n],
         "Koordinatörlük")
    ekle("Bilgi", "Koordinatörlük", "Alanı dışındaki işletmede görevli koordinatör; usul ve esaslar hakkında "
                                    "bilgilendirilmeli (md.88/2-e)",
         sorted({f"{r['ad']} {r['soyad']} → {r['isletme']}" for r in db.q(
             """SELECT o.ad, o.soyad, i.ad AS isletme FROM koordinator_gorevleri kg
                JOIN ogretmenler o ON o.id = kg.ogretmen_id JOIN isletmeler i ON i.id = kg.isletme_id
                WHERE i.alan_id IS NOT NULL AND o.alan_id IS NOT NULL AND o.alan_id != i.alan_id""")}),
         "Koordinatörlük")


def ozet(bulgular: list[Bulgu]) -> str:
    say = Counter(b.seviye for b in bulgular)
    if not bulgular:
        return "Denetimde sorun bulunmadı."
    return ", ".join(f"{say[s]} {s.lower()}" for s in ("Kritik", "Uyarı", "Bilgi") if say[s]) + " bulgu"
