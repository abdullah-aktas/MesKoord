"""SGK hata ve idari para cezası (İPC) risklerinin tespiti ve öneriler.

Kayıtlar 5510 sayılı Kanun md.8, 9, 86 ve 102'ye göre taranır: geciken veya yaklaşan işe giriş /
işten ayrılış bildirgeleri, aylık prim ve hizmet belgesi (APHB) son günü, yaşı nedeniyle artık
bakmakla yükümlü sayılmayan öğrenciler (belge 7 yerine 42), bildirge verilmesini engelleyen T.C.
hataları, tatilde girilmiş ayrılışlar ve tutarsız bildirim işaretleri. Her bulguya olası ceza tutarı
(asgari ücrete bağlı) ve kendiliğinden düzeltmede ödenecek indirimli tutar eklenir.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

from . import sigorta
from .utils import ay_araligi, para, tarih, tc_gecerli

SEVIYE_SIRASI = {"Kritik": 0, "Uyarı": 1, "Bilgi": 2}
YAKIN_GUN = 7
_TATIL_BILDIRILMEZ = re.compile(r"yar[ıi]\s?y[ıi]l|ara tatil|s[öo]mestr", re.I)


@dataclass
class Risk:
    seviye: str  # Kritik | Uyarı | Bilgi
    konu: str
    kisi: str
    aciklama: str
    oneri: str
    dayanak: str = ""
    son_tarih: date | None = None
    tahmini_ceza: float = 0.0
    indirimli_ceza: float = 0.0
    ogrenci_id: int | None = None
    yerlestirme_id: int | None = None
    eylem: str = ""  # bildirildi:Giriş | bildirildi:Çıkış | aphb:YYYY-MM | yukumlu_kaldir

    @property
    def eylem_adi(self) -> str:
        if self.eylem.startswith("bildirildi:"):
            return f"'{self.eylem.split(':')[1]} bildirildi' işaretle"
        if self.eylem.startswith("aphb:"):
            return "'APHB verildi' işaretle"
        return {"yukumlu_kaldir": "Bakmakla yükümlü işaretini kaldır"}.get(self.eylem, "")


def _tl(x: float) -> str:
    return f"{para(x)} TL"


def _yas(dogum: date, gun: date) -> int:
    return gun.year - dogum.year - ((gun.month, gun.day) < (dogum.month, dogum.day))


def _yas_doldugu_gun(dogum: date, yas: int) -> date:
    try:
        return dogum.replace(year=dogum.year + yas)
    except ValueError:  # 29 Şubat
        return date(dogum.year + yas, 3, 1)


def _onceki_ay(d: date, kac: int = 1) -> tuple[int, int]:
    y, a = d.year, d.month - kac
    while a < 1:
        y, a = y - 1, a + 12
    return y, a


def aphb_anahtari(yil: int, ay: int) -> str:
    return f"aphb_verildi_{yil:04d}-{ay:02d}"


def aphb_verildi(db, yil: int, ay: int) -> date | None:
    return tarih(db.ayar(aphb_anahtari(yil, ay)))


def aphb_isaretle(db, yil: int, ay: int, tarih_: date | None = None) -> None:
    db.ayar_yaz(aphb_anahtari(yil, ay), (tarih_ or date.today()).isoformat())


def aphb_isaretini_kaldir(db, yil: int, ay: int) -> None:
    """'APHB verildi' işaretini kaldırır (iptal edilen ya da yanlışlıkla işaretlenen belge)."""
    db.ayar_yaz(aphb_anahtari(yil, ay), "")


def aphb_son_gunu(db, yil: int, ay: int) -> date:
    y, a = (yil, ay + 1) if ay < 12 else (yil + 1, 1)
    son = ay_araligi(y, a)[1]
    return date(y, a, min(int(db.ayar("muhsgk_son_gun")), son.day))


def analiz(db, bugun: date | None = None) -> list[Risk]:
    bugun = bugun or date.today()
    au = db.ayar("asgari_ucret_brut")
    indirim = db.ayar("sgk_ipc_indirim")
    ceza_giris = au * db.ayar("sgk_ipc_giris_kat")
    ceza_giris_tespit = au * db.ayar("sgk_ipc_giris_tespit_kat")
    ceza_cikis = au * db.ayar("sgk_ipc_cikis_kat")
    ceza_ek = au * db.ayar("sgk_ipc_ek_belge_kisi")
    out: list[Risk] = []

    # --- işe giriş / işten ayrılış bildirgeleri ---
    for b in sigorta.bekleyen_bildirimler(db, bugun, ileri_gun=YAKIN_GUN):
        giris = b.tur == "Giriş"
        ceza = ceza_giris if giris else ceza_cikis
        ad = "İşe giriş bildirgesi" if giris else "İşten ayrılış bildirgesi"
        dayanak = "5510 md.8, md.102/1-a" if giris else "5510 md.9, md.102/1-j"
        if b.gecikti:
            gecen = (bugun - b.son_tarih).days
            kendiliginden = gecen <= 30
            indirimli = ceza * indirim if kendiliginden else ceza * 0.75
            oneri = (f"Bugün verin. Yasal sürenin bitiminden itibaren 30 gün içinde ({b.son_tarih + timedelta(days=30):%d.%m.%Y}"
                     f"e kadar) kendiliğinden verilirse ceza 1/4'e iner; peşin ödemede ~{_tl(indirimli)}."
                     if kendiliginden else
                     f"30 günlük indirim süresi geçti; yine de hemen verin. Peşin ödemede ~{_tl(indirimli)}.")
            if giris:
                oneri += f" Denetimde tespit edilirse ceza 2 katı (~{_tl(ceza_giris_tespit)}) olur ve geçmiş primler " \
                         "gecikme zammıyla istenir."
            out.append(Risk("Kritik", f"{ad} gecikti", b.ogrenci,
                            f"{b.sinif} - {b.isletme or 'okul'}: {'başlangıç' if giris else 'ayrılış'} "
                            f"{b.olay_tarihi:%d.%m.%Y}, son gün {b.son_tarih:%d.%m.%Y} ({gecen} gün geçti), "
                            f"belge {b.belge_turu}.", oneri, dayanak, b.son_tarih, round(ceza, 2),
                            round(indirimli, 2), yerlestirme_id=b.yerlestirme_id, eylem=f"bildirildi:{b.tur}"))
        else:
            kalan = (b.son_tarih - bugun).days
            out.append(Risk("Uyarı", f"{ad} yaklaşıyor", b.ogrenci,
                            f"{b.sinif} - {b.isletme or 'okul'}: son gün {b.son_tarih:%d.%m.%Y} ({kalan} gün kaldı).",
                            f"Süresinde verin; gecikirse ceza ~{_tl(ceza)}. Verdiyseniz 'bildirildi' işaretleyin.",
                            dayanak, b.son_tarih, yerlestirme_id=b.yerlestirme_id, eylem=f"bildirildi:{b.tur}"))

    rows = db.q("""SELECT y.*, o.tc, o.ad, o.soyad, o.dogum_tarihi, o.bakmakla_yukumlu, s.ad AS sinif,
                          i.ad AS isletme
                   FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                   LEFT JOIN siniflar s ON s.id = o.sinif_id LEFT JOIN isletmeler i ON i.id = y.isletme_id
                   WHERE y.baslangic IS NOT NULL""")
    aktif = [r for r in rows if tarih(r["baslangic"]) and tarih(r["baslangic"]) <= bugun + timedelta(days=YAKIN_GUN)
             and (not r["bitis"] or tarih(r["bitis"]) is None or tarih(r["bitis"]) >= bugun)]
    giris_once = db.ayar("sgk_giris_once_gun")

    # --- T.C. kimlik no ---
    gorulen: set[int] = set()
    for r in aktif:
        if r["ogrenci_id"] in gorulen:
            continue
        gorulen.add(r["ogrenci_id"])
        if not tc_gecerli(r["tc"]):
            out.append(Risk("Kritik", "T.C. kimlik no eksik/geçersiz", f"{r['ad']} {r['soyad']}",
                            f"{r['sinif'] or ''}: '{r['tc'] or ''}' ile SGK bildirgesi verilemez.",
                            "e-Okul'daki T.C. kimlik numarasını öğrenci kartına girin; bildirge verilemezse "
                            f"sigortasız çalışma sayılır (ceza ~{_tl(ceza_giris)}).", "5510 md.8",
                            tahmini_ceza=round(ceza_giris, 2), ogrenci_id=r["ogrenci_id"]))
    tc_say: dict[str, list[str]] = defaultdict(list)
    for o in db.q("SELECT tc, ad, soyad FROM ogrenciler WHERE tc != '' AND aktif = 1"):
        tc_say[o["tc"]].append(f"{o['ad']} {o['soyad']}")
    for tc, adlar in tc_say.items():
        if len(adlar) > 1:
            out.append(Risk("Kritik", "Aynı T.C. birden çok öğrencide", ", ".join(adlar), f"T.C. {tc}",
                            "Mükerrer veya yanlış girilmiş kaydı düzeltin; SGK'ya yanlış kişi bildirilebilir.",
                            "5510 md.8"))

    # --- bakmakla yükümlülük (GSS) yaşı ---
    yas_siniri = int(db.ayar("gss_yukumlu_yas"))
    pek_aylik = sigorta.gunluk_pek(db) * 30
    fark_oran = db.ayar("sgk_prim_yukumlu_degil") - db.ayar("sgk_prim_yukumlu")
    gorulen.clear()
    for r in aktif:
        if r["ogrenci_id"] in gorulen or not r["bakmakla_yukumlu"]:
            continue
        gorulen.add(r["ogrenci_id"])
        d = tarih(r["dogum_tarihi"])
        ad = f"{r['ad']} {r['soyad']}"
        if d is None:
            out.append(Risk("Bilgi", "Doğum tarihi yok", ad, f"{r['sinif'] or ''}: bakmakla yükümlü işaretli; "
                            f"{yas_siniri} yaş kontrolü yapılamıyor.", "Doğum tarihini öğrenci kartına girin.",
                            "5510 md.3/10", ogrenci_id=r["ogrenci_id"]))
            continue
        dolum = _yas_doldugu_gun(d, yas_siniri)
        aylik_fark = pek_aylik * fark_oran
        if dolum <= bugun:
            gecen_ay = (bugun.year - dolum.year) * 12 + bugun.month - dolum.month
            out.append(Risk(
                "Kritik", f"{yas_siniri} yaşını doldurdu: belge türü değişmeli", ad,
                f"{r['sinif'] or ''}: {dolum:%d.%m.%Y} tarihinde {yas_siniri} yaşını doldurdu; ana/babası üzerinden "
                f"bakmakla yükümlü sayılmaz. Belge {db.ayar('belge_isletme_yukumlu')} yerine "
                f"{db.ayar('belge_isletme_degil')} (prim %{db.ayar('sgk_prim_yukumlu') * 100:g} yerine "
                f"%{db.ayar('sgk_prim_yukumlu_degil') * 100:g}); aylık prim farkı ~{_tl(aylik_fark)}.",
                "Öğrenci kartında 'bakmakla yükümlü' işaretini kaldırın. Geçmiş aylar eski belgeyle bildirildiyse "
                f"iptal ve ek belge verin (ek belge cezası ~{_tl(ceza_ek)}; kendiliğinden ~{_tl(ceza_ek * indirim)})"
                + (f"; yaklaşık {gecen_ay} aylık prim farkı (~{_tl(aylik_fark * gecen_ay)}) gecikme zammıyla ödenir."
                   if gecen_ay else "."),
                "5510 md.3/10-b, md.81", dolum, round(ceza_ek, 2) if gecen_ay else 0.0,
                round(ceza_ek * indirim, 2) if gecen_ay else 0.0, r["ogrenci_id"], r["id"], "yukumlu_kaldir"))
        elif dolum <= bugun + timedelta(days=45):
            out.append(Risk("Uyarı", f"{yas_siniri} yaşını dolduracak", ad,
                            f"{r['sinif'] or ''}: {dolum:%d.%m.%Y} tarihinde {yas_siniri} yaşını dolduruyor.",
                            "O tarihten sonraki bildirimler bakmakla yükümlü olunmayan belgeyle yapılmalı; tarihte "
                            "öğrenci kartındaki işareti kaldırın.", "5510 md.3/10-b", dolum,
                            ogrenci_id=r["ogrenci_id"], yerlestirme_id=r["id"]))

    # --- tutarsız bildirim işaretleri, tatilde ayrılış, geç verilmiş bildirgeler ---
    tatiller = [(t["ad"], tarih(t["baslangic"]), tarih(t["bitis"]) or tarih(t["baslangic"]))
                for t in db.q("SELECT ad, baslangic, bitis FROM tatiller")]
    for r in rows:
        ad = f"{r['ad']} {r['soyad']}"
        bas, bit = tarih(r["baslangic"]), tarih(r["bitis"])
        if r["sigorta_cikis_bildirildi"] and not bit:
            out.append(Risk("Uyarı", "Çıkış bildirilmiş ama yerleştirme açık", ad,
                            f"{r['isletme'] or 'okul'}: bitiş tarihi yok, prim listesinde gün yazılmaya devam ediyor.",
                            "Ayrıldıysa bitiş tarihini girin; devam ediyorsa yeniden işe giriş bildirgesi verin "
                            f"(sigortasız çalışma cezası ~{_tl(ceza_giris)}).", "5510 md.8-9",
                            ogrenci_id=r["ogrenci_id"], yerlestirme_id=r["id"]))
        if bit and not r["sigorta_cikis_bildirildi"]:
            tatil = next((t for t in tatiller if t[1] and t[2] and t[1] <= bit <= t[2]
                          and _TATIL_BILDIRILMEZ.search(t[0] or "")), None)
            if tatil:
                out.append(Risk("Uyarı", "Tatilde işten ayrılış", ad,
                                f"Bitiş {bit:%d.%m.%Y} '{tatil[0]}' içinde.",
                                "Ara tatil ve yarıyıl tatilinde işten ayrılış bildirilmez. Öğrenci tatilden "
                                "sonra devam edecekse bitiş tarihini silin.", "SGK genelgesi (öğrenci sigortası)",
                                ogrenci_id=r["ogrenci_id"], yerlestirme_id=r["id"]))
        bildirim = tarih(r["sigorta_giris_bildirim_tarihi"])
        if (r["sigorta_giris_bildirildi"] and bas and bildirim and bas >= bugun - timedelta(days=365)
                and bildirim > bas - timedelta(days=giris_once)):
            gec = (bildirim - bas).days + giris_once
            out.append(Risk("Bilgi", "İşe giriş geç bildirilmiş", ad,
                            f"Başlangıç {bas:%d.%m.%Y}, bildirim {bildirim:%d.%m.%Y} ({gec} gün geç).",
                            f"SGK idari para cezası tebliğ edebilir (~{_tl(ceza_giris)}; kendiliğinden verildiği için "
                            f"1/4, peşin ~{_tl(ceza_giris * indirim)}). Tebligat gelirse 15 gün içinde peşin ödeyin.",
                            "5510 md.102/1-a, 102/2", tahmini_ceza=round(ceza_giris * 0.25, 2),
                            indirimli_ceza=round(ceza_giris * indirim, 2), ogrenci_id=r["ogrenci_id"],
                            yerlestirme_id=r["id"]))

    # --- aylık prim ve hizmet belgesi ---
    for kac in (2, 1):
        yil, ay = _onceki_ay(bugun, kac)
        if db.ayar(aphb_anahtari(yil, ay)):
            continue
        liste = sigorta.aylik_liste(db, yil, ay)
        if not liste:
            continue
        son = aphb_son_gunu(db, yil, ay)
        n = len({s.ogrenci_id for s in liste})
        ceza = min(n * au * db.ayar("sgk_ipc_aphb_kisi"), au * db.ayar("sgk_ipc_aphb_azami"))
        if bugun > son:
            out.append(Risk("Kritik", f"{ay:02d}/{yil} APHB verildi mi?", f"{n} sigortalı",
                            f"Son gün {son:%d.%m.%Y} geçti; programda 'verildi' işaretlenmemiş.",
                            "Verdiyseniz 'APHB verildi' işaretleyin. Vermediyseniz hemen verin (kendiliğinden "
                            f"verilirse ceza 1/4'e iner, peşin ~{_tl(ceza * indirim)}). Eksik günleri ve belge "
                            "türlerini SGK > Liste Karşılaştırma ile kontrol edin.", "5510 md.86, md.102/1-c",
                            son, round(ceza, 2), round(ceza * indirim, 2), eylem=f"aphb:{yil:04d}-{ay:02d}"))
        elif (son - bugun).days <= YAKIN_GUN:
            eksik = sum(1 for s in liste if s.eksik_gun)
            out.append(Risk("Uyarı", f"{ay:02d}/{yil} APHB son günü yaklaşıyor", f"{n} sigortalı",
                            f"Son gün {son:%d.%m.%Y} ({(son - bugun).days} gün kaldı)"
                            + (f"; {eksik} öğrencide eksik gün var." if eksik else "."),
                            f"Aylık Prim Hizmet Listesi'ni Excel'e aktarıp e-Bildirge'ye yükleyin; geç verilirse ceza "
                            f"~{_tl(ceza)}. Eksik gün belgelerini (devamsızlık tutanakları) dosyada saklayın.",
                            "5510 md.86, md.102/1-c", son, eylem=f"aphb:{yil:04d}-{ay:02d}"))
    out.sort(key=lambda r: (SEVIYE_SIRASI.get(r.seviye, 9), r.son_tarih or date.max, r.konu, r.kisi))
    return out


def ozet(riskler: list[Risk]) -> str:
    if not riskler:
        return "SGK açısından risk bulunmadı."
    n = defaultdict(int)
    for r in riskler:
        n[r.seviye] += 1
    s = ", ".join(f"{n[k]} {k.lower()}" for k in ("Kritik", "Uyarı", "Bilgi") if n[k])
    toplam = sum(r.tahmini_ceza for r in riskler)
    indirimli = sum(r.indirimli_ceza or r.tahmini_ceza for r in riskler)
    if toplam:
        s += f". Olası idari para cezası ~{_tl(toplam)}; önerilere göre hemen düzeltilirse ~{_tl(indirimli)}."
    return s


def uygula(db, risk: Risk) -> str:
    """Bulgunun düzeltme eylemini uygular."""
    e = risk.eylem
    if e.startswith("bildirildi:") and risk.yerlestirme_id:
        tur = e.split(":")[1]
        sigorta.bildirildi_isaretle(db, risk.yerlestirme_id, tur)
        return f"{risk.kisi}: {tur.lower()} bildirildi olarak işaretlendi"
    if e.startswith("aphb:"):
        y, a = (int(x) for x in e.split(":")[1].split("-"))
        aphb_isaretle(db, y, a)
        return f"{a:02d}/{y} APHB verildi olarak işaretlendi"
    if e == "yukumlu_kaldir" and risk.ogrenci_id:
        db.update("ogrenciler", risk.ogrenci_id, {"bakmakla_yukumlu": 0})
        return f"{risk.kisi}: bakmakla yükümlü işareti kaldırıldı"
    raise ValueError("Bu bulgu için otomatik düzeltme yok")


def excel_yaz(riskler: list[Risk], yol) -> object:
    from .excel_io import ExcelYazici
    x = ExcelYazici()
    x.sayfa("SGK Riskleri", ["Seviye", "Konu", "Kişi", "Açıklama", "Öneri", "Dayanak", "Son Tarih",
                             "Olası Ceza (TL)", "Hemen Düzeltilirse (TL)"],
            [[r.seviye, r.konu, r.kisi, r.aciklama, r.oneri, r.dayanak,
              r.son_tarih.strftime("%d.%m.%Y") if r.son_tarih else "", r.tahmini_ceza or "",
              r.indirimli_ceza or ""] for r in riskler],
            baslik="SGK Hata ve Ceza Riskleri", alt_bilgi=[ozet(riskler)])
    return x.kaydet(yol)
