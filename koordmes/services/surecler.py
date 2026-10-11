"""İş süreçleri ve eylemler.

Eğitim yılı başı, her ay ve yıl sonu yapılması gereken işler adım adım tanımlanır. Her adımın
durumu veritabanından otomatik denetlenir ve tek tıkla çalıştırılabilecek bir eylemi vardır.
Eylemler asistan, süreç ekranı ve veri aktarımı sonrası önerilerde ortak kullanılır.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from .. import config
from ..mevzuat import AYLAR, ISLETMEYE_GIDEN_SINIF_SQL, OKUL_ICI_TURLER
from . import (belgeler, cerceve, denetim, devam, koordinator, mesleki_egitim, program, raporlar, sgk_dosya, sgk_risk,
               sigorta, ucret)
from .utils import ay_araligi, para, tr


@dataclass
class EylemSonucu:
    mesaj: str
    dosyalar: list[Path] = field(default_factory=list)
    git: str | None = None


@dataclass
class Eylem:
    anahtar: str
    etiket: str
    calistir: Callable[..., EylemSonucu] | None = None
    git: str | None = None
    uzun: bool = False
    onay: str = ""
    tarih_ister: bool = False


def _ay(yil: int | None, ay: int | None) -> tuple[int, int]:
    if yil and ay:
        return yil, ay
    b = date.today()
    return b.year, b.month


def onceki_ay(d: date | None = None) -> tuple[int, int]:
    d = d or date.today()
    return (d.year - 1, 12) if d.month == 1 else (d.year, d.month - 1)


def sonraki_ay(yil: int, ay: int) -> tuple[int, int]:
    return (yil + 1, 1) if ay == 12 else (yil, ay + 1)


def _donem(yil: int, ay: int) -> str:
    return f"{AYLAR[ay - 1]} {yil}"


# ------------------------------------------------------------------ eylem uygulamaları

def _program_olustur(db, **_) -> EylemSonucu:
    s = program.programi_olustur(db)
    eksik = program.eksik_saatler(db)
    cat = program.catismalar(db)
    m = f"Ders programı oluşturuldu ({s.sure:.1f} sn). "
    m += "Tüm dersler çakışmasız yerleşti." if not eksik and not cat else \
        f"{len(eksik)} ders tam yerleşmedi, {len(cat)} çakışma var; Ders Programı ekranından kontrol edin."
    return EylemSonucu(m, git="Ders Dağılımı ve Atölye Yerleşimi")


def _cerceve_dersleri(db, **_) -> EylemSonucu:
    sonuclar, sorunlar = cerceve.tum_siniflara_uygula(db)
    m = (f"Çerçeve öğretim programlarına göre {len(sonuclar)} sınıfta {sum(len(s.eklenen) for s in sonuclar)} "
         f"zorunlu ders açıldı, {sum(len(s.guncellenen) for s in sonuclar)} dersin haftalık saati düzeltildi.")
    if sorunlar:
        m += f" Çizelgesi bulunamayan {len(sorunlar)} sınıf: " + "; ".join(sorunlar[:5]) + "."
    uyarilar = [f"{s.sinif}: {u}" for s in sonuclar for u in s.uyarilar]
    if uyarilar:
        m += " " + " ".join(uyarilar[:3])
    if any(s.eklenen for s in sonuclar):
        m += " Yeni açılan derslerin öğretmenlerini Ders Dağılımı ekranından atayınız."
    return EylemSonucu(m, git="Ders Dağılımı ve Atölye Yerleşimi")


def _koordinator(db, **_) -> EylemSonucu:
    s = koordinator.otomatik_gorevlendir(db)
    m = f"{len({g['isletme_id'] for g in s.gorevler})} işletmeye koordinatör öğretmen görevlendirildi " \
        f"({len(s.gorevler)} görev)."
    if s.atanamayan:
        m += f" {len(s.atanamayan)} işletme/grup görevlendirilemedi: " + ", ".join(ih.ad for ih, _ in s.atanamayan[:5])
    if s.alan_disi:
        m += f" {len(s.alan_disi)} görev alanı dışındaki öğretmene verildi (md.88/2-e: bilgilendirme yapılmalı)."
    if s.kapsam_disi:
        m += f" {len(s.kapsam_disi)} işletme kapsam dışı (döner sermaye / il dışı staj)."
    return EylemSonucu(m, git="Koordinatörlük")


def _gorevlendirme_yazilari(db, **_) -> EylemSonucu:
    ids = [r["ogretmen_id"] for r in db.q("SELECT DISTINCT ogretmen_id FROM koordinator_gorevleri")]
    if not ids:
        return EylemSonucu("Önce koordinatör görevlendirmesi yapılmalı.")
    yollar = [belgeler.uret(db, "koordinator_gorevlendirme", t) for t in ids]
    return EylemSonucu(f"{len(yollar)} görevlendirme yazısı hazırlandı.", [yollar[0].parent])


def _ziyaret_plani(db, yil=None, ay=None, **_) -> EylemSonucu:
    yil, ay = _ay(yil, ay)
    n = koordinator.ziyaret_plani_olustur(db, yil, ay)
    yol = raporlar.ziyaret_plani(db, yil, ay)
    return EylemSonucu(f"{_donem(yil, ay)} için {n} ziyaret planlandı (tatiller atlandı).", [yol])


def sozlesme_belge_turu(tur: str) -> str:
    return "ciraklik_sozlesmesi" if tur == "Çıraklık" else "isletme_sozlesmesi"


def _sozlesmeler(db, ids=None, **_) -> EylemSonucu:
    rows = db.q("SELECT id, tur FROM yerlestirmeler WHERE durum = 'Aktif' AND isletme_id IS NOT NULL")
    rows = [r for r in rows if r["tur"] not in OKUL_ICI_TURLER and (ids is None or r["id"] in ids)]
    if not rows:
        return EylemSonucu("Sözleşme üretilecek aktif işletme yerleştirmesi yok.")
    yollar = [belgeler.uret(db, sozlesme_belge_turu(r["tur"]), r["id"]) for r in rows]
    return EylemSonucu(f"{len(yollar)} sözleşme hazırlandı. Sözleşme numaralarını yerleştirme kayıtlarına girmeyi "
                       "unutmayın.", sorted({y.parent for y in yollar}))


def _degerlendirme_formlari(db, **_) -> EylemSonucu:
    rows = [r for r in db.q("SELECT id, tur FROM yerlestirmeler WHERE durum = 'Aktif' AND isletme_id IS NOT NULL")
            if r["tur"] not in OKUL_ICI_TURLER]
    yollar = [belgeler.uret(db, "beceri_degerlendirme", r["id"]) for r in rows]
    return EylemSonucu(f"{len(yollar)} değerlendirme formu hazırlandı.", [yollar[0].parent] if yollar else [])


def _sgk_prim(db, yil=None, ay=None, **_) -> EylemSonucu:
    yil, ay = _ay(yil, ay)
    yol = raporlar.sgk_prim_listesi(db, yil, ay)
    liste = sigorta.aylik_liste(db, yil, ay)
    prim = sum(s.prim for s in liste)
    son = sonraki_ay(yil, ay)
    return EylemSonucu(f"{_donem(yil, ay)} SGK prim hizmet listesi: {len(liste)} öğrenci, toplam prim "
                       f"{para(prim)} TL. MUHSGK son günü {db.ayar('muhsgk_son_gun')}.{son[1]:02d}.{son[0]}.", [yol])


def _sgk_bildirim(db, **_) -> EylemSonucu:
    yol = raporlar.sgk_bildirim_listesi(db)
    b = sigorta.bekleyen_bildirimler(db)
    gec = sum(1 for x in b if x.gecikti)
    return EylemSonucu(f"Bekleyen {len(b)} SGK bildirimi var" + (f", {gec} tanesinin süresi geçti." if gec else ".")
                       + " Bildirdikten sonra SGK ekranında 'Bildirildi' olarak işaretleyin veya e-Bildirge listesini "
                         "aktarın.", [yol], "SGK Sigorta İşlemleri")


def _sgk_xml(db, yil=None, ay=None, bicim="xml", **_) -> EylemSonucu:
    yil, ay = _ay(yil, ay)
    try:
        s = sgk_dosya.aphb_dosyalari(db, yil, ay, config.output_dir() / "SGK", bicim)
    except sgk_dosya.SgkDosyaHatasi as e:
        return EylemSonucu(str(e), git="SGK Sigorta İşlemleri")
    m = f"{_donem(yil, ay)} e-Bildirge V2 aylık prim ve hizmet belgesi ({bicim.upper()}): {s.ozet()}."
    if s.uyarilar:
        m += " " + " ".join(s.uyarilar[:3])
    return EylemSonucu(m + " e-Bildirge V2'ye yükleyip onayladıktan sonra belgeyi 'verildi' işaretleyin.", s.yollar)


def _sgk_bildirge_xml(db, bicim="xml", **_) -> EylemSonucu:
    bekleyen = sigorta.bekleyen_bildirimler(db)
    if not bekleyen:
        return EylemSonucu("Bekleyen işe giriş / işten ayrılış bildirimi yok.")
    yollar, parcalar = [], []
    for tur in ("Giriş", "Çıkış"):
        ids = [b.yerlestirme_id for b in bekleyen if b.tur == tur]
        if not ids:
            continue
        try:
            s = sgk_dosya.bildirge_dosyalari(db, ids, tur, config.output_dir() / "SGK", bicim)
        except sgk_dosya.SgkDosyaHatasi as e:
            parcalar.append(f"{tur}: {e}")
            continue
        yollar += s.yollar
        parcalar.append(f"{'işe giriş' if tur == 'Giriş' else 'işten ayrılış'} {s.kisi} kişi")
    return EylemSonucu("SGK 4A toplu bildirge dosyası: " + ", ".join(parcalar) + ". Yükleyip onayladıktan sonra "
                       "SGK ekranında 'Bildirildi' işaretleyin.", yollar, "SGK Sigorta İşlemleri")


def _isletme_yazilari(db, yil: int, ay: int, klasor: Path | None = None) -> list[Path]:
    liste = ucret.aylik_hesap(db, yil, ay)
    adlar = {s.isletme for s in liste}
    ids = [r["id"] for r in db.q("SELECT id, ad FROM isletmeler") if r["ad"] in adlar]
    return [belgeler.uret(db, "isletme_ucret_bildirimi", i, klasor=klasor, yil=yil, ay=ay) for i in ids]


def _ucret(db, yil=None, ay=None, **_) -> EylemSonucu:
    yil, ay = _ay(yil, ay)
    liste = ucret.aylik_hesap(db, yil, ay)
    ucret.kaydet(db, yil, ay, liste)
    yol = raporlar.ucret_listesi(db, yil, ay)
    yazilar = _isletme_yazilari(db, yil, ay)
    return EylemSonucu(f"{_donem(yil, ay)}: {len(liste)} öğrenci, ödenecek {para(sum(s.odenecek_ucret for s in liste))}"
                       f" TL, devlet katkısı {para(sum(s.devlet_katkisi for s in liste))} TL. {len(yazilar)} işletmeye "
                       "ücret bildirim yazısı hazırlandı.", [yol] + ([yazilar[0].parent] if yazilar else []))


def _dekont(db, yil=None, ay=None, **_) -> EylemSonucu:
    yil, ay = _ay(yil, ay)
    if not db.q1("SELECT 1 FROM aylik_odemeler WHERE donem = ?", (f"{yil:04d}-{ay:02d}",)):
        ucret.kaydet(db, yil, ay, ucret.aylik_hesap(db, yil, ay))
    satir = raporlar.dekont_satirlari(db, yil, ay)
    bekleyen = sum(1 for r in satir if r[-1] == "Dekont yok")
    eksik = sum(1 for r in satir if r[-1] == "Eksik ödeme")
    return EylemSonucu(f"{_donem(yil, ay)} dekont takibi: {len(satir)} öğrenci, {bekleyen} dekont bekleniyor, "
                       f"{eksik} eksik ödeme.", [raporlar.dekont_takip(db, yil, ay)], "Öğrenci Ücreti ve Devlet Katkısı")


def _ekders(db, yil=None, ay=None, **_) -> EylemSonucu:
    yil, ay = _ay(yil, ay)
    _, _, liste = raporlar.ekders_tablosu(db, yil, ay)
    yol = raporlar.ekders_puantaj(db, yil, ay)
    return EylemSonucu(f"{_donem(yil, ay)} ek ders puantajı: {len(liste)} öğretmen, "
                       f"{sum(p.toplam for p in liste):g} saat, tahmini brüt {para(sum(p.brut for p in liste))} TL.",
                       [yol])


def _devam(db, **_) -> EylemSonucu:
    _, liste = raporlar.devam_satirlari(db)
    asan = [x for x in liste if x.durum == "Sınırı aştı"]
    yol = raporlar.devam_ozeti(db)
    m = f"Devamsızlığı olan {len(liste)} öğrenci; {len(asan)} öğrenci sınırı aştı."
    if asan:
        m += " " + ", ".join(f"{x.ad} ({x.sinif})" for x in asan[:5])
    return EylemSonucu(m, [yol], "Devamsızlık ve Değerlendirme")


def _veli(db, klasor: Path | None = None, **_) -> EylemSonucu:
    liste = [x for x in devam.ozet(db) if x.durum in ("Sınırı aştı", "Sınıra yakın", "Veli bildirimi")]
    yollar = [belgeler.uret(db, "devamsizlik_bildirimi", x.ogrenci_id, klasor=klasor) for x in liste]
    return EylemSonucu(f"{len(yollar)} veliye devamsızlık bildirimi hazırlandı.",
                       [yollar[0].parent] if yollar else [])


def _komisyon_karari(db, **_) -> EylemSonucu:
    yol = belgeler.uret(db, "koordinatorluk_komisyon_karari", 1)
    return EylemSonucu("Koordinatörlük planlama komisyonu kararı hazırlandı (md.88/2-b).", [yol])


def _koordinator_bildirimleri(db, **_) -> EylemSonucu:
    ids = [r["isletme_id"] for r in db.q("SELECT DISTINCT isletme_id FROM koordinator_gorevleri")]
    if not ids:
        return EylemSonucu("Önce koordinatör görevlendirmesi yapılmalı.")
    yollar = [belgeler.uret(db, "koordinator_bildirimi", i) for i in ids]
    return EylemSonucu(f"{len(yollar)} işletmeye koordinatör öğretmen bildirim yazısı hazırlandı (md.88/1).",
                       [yollar[0].parent])


def _uygunluk_tutanaklari(db, **_) -> EylemSonucu:
    rows = db.q("""SELECT DISTINCT i.id FROM isletmeler i JOIN yerlestirmeler y ON y.isletme_id = i.id
                   AND y.durum = 'Aktif' WHERE i.uygunluk_tarihi IS NULL OR i.uygunluk_tarihi = ''""")
    if not rows:
        return EylemSonucu("Öğrencisi olan bütün işletmelerin uygunluk tespit tarihi girilmiş. Tek tek tutanak için "
                           "İşletmeler ekranını kullanın.", git="İşletmeler")
    yollar = [belgeler.uret(db, "isletme_uygunluk", r["id"]) for r in rows]
    return EylemSonucu(f"Uygunluk tespiti girilmemiş {len(yollar)} işletme için tutanak hazırlandı (md.142). "
                       "Komisyon incelemesinden sonra tespit tarihini İşletmeler ekranına girin.", [yollar[0].parent])


def _alan_taramasi(db, **_) -> EylemSonucu:
    rows = mesleki_egitim.talep_satirlari(db)
    eksik = [r[0] for r in rows if r[-1] < 0]
    m = f"Alan taraması özeti hazırlandı: {len(rows)} alan."
    if eksik:
        m += " Gelecek yıl için kontenjanı yetersiz alanlar: " + ", ".join(eksik)
    return EylemSonucu(m, [mesleki_egitim.talep_ozeti(db)], "Komisyon ve İzleme İşleri")


def _anket_ozeti(db, **_) -> EylemSonucu:
    n = _say(db, "SELECT COUNT(*) FROM anketler")
    return EylemSonucu(f"{n} anketin değerlendirmesi hazırlandı.", [mesleki_egitim.anket_ozeti(db)],
                       "Komisyon ve İzleme İşleri")


def _hizmetici(db, **_) -> EylemSonucu:
    n = _say(db, "SELECT COUNT(*) FROM hizmetici_egitimler")
    return EylemSonucu(f"Usta öğretici hizmetiçi eğitim programı hazırlandı ({n} eğitim). Okul müdürünün onayına "
                       "sununuz (md.82/2-b).", [mesleki_egitim.hizmetici_programi(db)], "Komisyon ve İzleme İşleri")


def _puan_cizelgesi(db, **_) -> EylemSonucu:
    donemler = mesleki_egitim.donem_sonlari(db)
    if not donemler:
        return EylemSonucu("Dönem sonu tarihleri girilmemiş; Ayarlar > Kurum Bilgileri'nden giriniz.",
                           git="Ayarlar ve Mevzuat Parametreleri")
    sure = int(db.ayar("puan_cizelgesi_gun"))
    parcalar = []
    for no, son in donemler:
        eksik = mesleki_egitim.puan_eksikleri(db, no)
        parcalar.append(f"{no}. dönem (son teslim {tr(son - timedelta(days=sure))}): {len(eksik)} öğrencinin "
                        "işletme notu eksik")
    return EylemSonucu("; ".join(parcalar) + ".", git="Devamsızlık ve Değerlendirme")


def _yedek(db, **_) -> EylemSonucu:
    yol = db.yedekle()
    if not yol.exists():
        return EylemSonucu(f"Veritabanı sunucu bilgisayarında yedeklendi: {yol.name}")
    return EylemSonucu(f"Veritabanı yedeklendi: {yol.name}", [yol.parent])


def _denetim(db, **_) -> EylemSonucu:
    b = denetim.denetle(db)
    return EylemSonucu(denetim.ozet(b) + ". Ayrıntılar Asistan > Veri Denetimi sekmesinde.")


def aylik_kapanis(db, yil: int | None = None, ay: int | None = None) -> EylemSonucu:
    """Bir ayın tüm çıktılarını tek klasörde hazırlar."""
    yil, ay = (yil, ay) if yil and ay else onceki_ay()
    klasor = config.output_dir() / "Aylık Kapanış" / f"{yil}-{ay:02d} {AYLAR[ay - 1]}"
    klasor.mkdir(parents=True, exist_ok=True)
    satirlar, hatalar, dosyalar = [], [], []

    def adim(ad: str, fn: Callable[[], Any]) -> None:
        try:
            r = fn()
            if isinstance(r, Path):
                dosyalar.append(r)
            satirlar.append(f"✓ {ad}")
        except Exception as e:  # bir adımın hatası diğerlerini durdurmaz
            hatalar.append(f"✗ {ad}: {e}")

    liste = ucret.aylik_hesap(db, yil, ay)
    adim("Ücret ve devlet katkısı hesabı kaydedildi", lambda: ucret.kaydet(db, yil, ay, liste))
    adim("SGK aylık prim hizmet listesi",
         lambda: raporlar.sgk_prim_listesi(db, yil, ay, klasor / f"1 SGK Prim Hizmet Listesi {_donem(yil, ay)}.xlsx"))
    adim("Öğrenci ücret ve devlet katkısı listesi",
         lambda: raporlar.ucret_listesi(db, yil, ay, klasor / f"2 Ücret ve Devlet Katkısı {_donem(yil, ay)}.xlsx"))
    adim("İşletmelere ücret bildirim yazıları", lambda: _isletme_yazilari(db, yil, ay, klasor / "İşletme Ücret Yazıları"))
    adim("Dekont takip listesi",
         lambda: raporlar.dekont_takip(db, yil, ay, klasor / f"3 Dekont Takibi {_donem(yil, ay)}.xlsx"))
    adim("Ek ders puantajı",
         lambda: raporlar.ekders_puantaj(db, yil, ay, klasor / f"4 Ek Ders Puantajı {_donem(yil, ay)}.xlsx"))
    adim("Devamsızlık özeti", lambda: raporlar.devam_ozeti(db, klasor / "5 Devamsızlık Özeti.xlsx"))
    adim("Veli devamsızlık bildirimleri", lambda: _veli(db, klasor=klasor / "Veli Bildirimleri"))
    adim("Bekleyen SGK giriş/çıkış bildirimleri",
         lambda: raporlar.sgk_bildirim_listesi(db, klasor / "6 Bekleyen SGK Bildirimleri.xlsx"))
    if sigorta.aylik_liste(db, yil, ay):
        for bicim in ("xml", "excel"):
            adim(f"SGK e-Bildirge V2 aylık prim ve hizmet belgesi ({bicim.upper()})",
                 lambda b=bicim: sgk_dosya.aphb_dosyalari(db, yil, ay, klasor / "SGK e-Bildirge", b).yollar[0])
    sy, sa = sonraki_ay(yil, ay)
    adim(f"{_donem(sy, sa)} ziyaret planı", lambda: (
        koordinator.ziyaret_plani_olustur(db, sy, sa, mevcut_planlananlari_sil=False),
        raporlar.ziyaret_plani(db, sy, sa, klasor / f"7 Ziyaret Planı {_donem(sy, sa)}.xlsx"))[1])
    adim("Veritabanı yedeği", lambda: db.yedekle())

    sgk = sigorta.aylik_liste(db, yil, ay)
    ozet = [f"{db.kurum()['ad']} - {_donem(yil, ay)} aylık kapanış ({datetime.now():%d.%m.%Y %H:%M})", "",
            f"Sigortalı öğrenci: {len(sgk)}, toplam prim: {para(sum(s.prim for s in sgk))} TL",
            f"Ücret alan öğrenci: {len(liste)}, ödenecek: {para(sum(s.odenecek_ucret for s in liste))} TL, "
            f"devlet katkısı: {para(sum(s.devlet_katkisi for s in liste))} TL", ""] + satirlar + hatalar
    son = sonraki_ay(yil, ay)
    ozet += ["", "Yasal süreler:",
             f"- Dekontlar işletmelerden: {db.ayar('dekont_teslim_son_gun')}.{son[1]:02d}.{son[0]}",
             f"- Devlet katkısı sisteme giriş: {db.ayar('dk_sisteme_giris_son_gun')}.{son[1]:02d}.{son[0]}",
             f"- MUHSGK beyanı ve prim ödemesi: {db.ayar('muhsgk_son_gun')}.{son[1]:02d}.{son[0]}"]
    (klasor / "0 Kapanış Özeti.txt").write_text("\n".join(ozet), encoding="utf-8")
    m = f"{_donem(yil, ay)} aylık kapanışı hazırlandı: {len(satirlar)} adım tamam"
    m += f", {len(hatalar)} adım hatalı ({'; '.join(hatalar)})." if hatalar else "."
    return EylemSonucu(m, [klasor])


def yil_sonu(db, tarih: date | None = None, **_) -> EylemSonucu:
    """Aktif yerleştirmeleri ve koordinatörlük görevlerini verilen tarihte sona erdirir."""
    if not tarih:
        return EylemSonucu("Yıl sonu için bitiş tarihi gerekli.")
    t = tarih.isoformat()
    db.yedekle()
    with db.conn:
        n = db.conn.execute("""UPDATE yerlestirmeler SET bitis = ?, durum = 'Sona Erdi'
                               WHERE durum = 'Aktif' AND baslangic <= ? AND (bitis IS NULL OR bitis = '' OR bitis > ?)""",
                            (t, t, t)).rowcount
        db.conn.execute("UPDATE koordinator_gorevleri SET bitis = ? WHERE bitis IS NULL OR bitis = '' OR bitis > ?",
                        (t, t))
        db.conn.execute("DELETE FROM ziyaretler WHERE durum = 'Planlandı' AND tarih > ?", (t,))
    yol = raporlar.sgk_bildirim_listesi(db)
    return EylemSonucu(f"{n} yerleştirme {tr(tarih)} tarihiyle sona erdirildi (önce yedek alındı). İşten ayrılış "
                       f"bildirgelerini {db.ayar('sgk_cikis_bildirim_gun')} gün içinde verin.", [yol],
                       "SGK Sigorta İşlemleri")


def _ust_sinif_adi(ad: str) -> str | None:
    m = re.search(r"\b(9|10|11)\b", ad)
    if not m:
        return None
    return ad[:m.start()] + str(int(m.group(1)) + 1) + ad[m.end():]


def yeni_egitim_yili(db, **_) -> EylemSonucu:
    """Öğrencileri üst sınıfa geçirir, 12. sınıfları mezun (pasif) yapar, eğitim yılını ilerletir."""
    yedek = db.yedekle()
    siniflar = {r["id"]: r for r in db.q("SELECT * FROM siniflar")}
    ada_gore = {r["ad"].lower(): r["id"] for r in siniflar.values()}
    gecen = mezun = 0
    with db.conn:
        for o in db.q("SELECT id, sinif_id FROM ogrenciler WHERE aktif = 1 AND sinif_id IS NOT NULL"):
            s = siniflar.get(o["sinif_id"])
            if not s:
                continue
            if (s["seviye"] or 9) >= 12:
                db.conn.execute("UPDATE ogrenciler SET aktif = 0 WHERE id = ?", (o["id"],))
                mezun += 1
                continue
            yeni = _ust_sinif_adi(s["ad"])
            if not yeni:
                continue
            hedef = ada_gore.get(yeni.lower())
            if not hedef:
                hedef = db.conn.execute(
                    "INSERT INTO siniflar (ad, seviye, program, alan_id, dal_id) VALUES (?, ?, ?, ?, ?)",
                    (yeni, (s["seviye"] or 9) + 1, s["program"], s["alan_id"], s["dal_id"])).lastrowid
                ada_gore[yeni.lower()] = hedef
            db.conn.execute("UPDATE ogrenciler SET sinif_id = ? WHERE id = ?", (hedef, o["id"]))
            gecen += 1
        ey = db.kurum()["egitim_yili"] or ""
        m = re.match(r"^(\d{4})\s*-\s*(\d{4})$", ey)
        yeni_yil = f"{int(m.group(1)) + 1}-{int(m.group(2)) + 1}" if m else ey
        db.conn.execute("UPDATE kurum SET egitim_yili = ? WHERE id = 1", (yeni_yil,))
        db.conn.execute("DELETE FROM koordinator_gorevleri")
        db.conn.execute("DELETE FROM ziyaretler WHERE durum = 'Planlandı'")
    return EylemSonucu(f"{gecen} öğrenci üst sınıfa geçirildi, {mezun} öğrenci mezun olarak pasifleştirildi. Eğitim yılı "
                       f"{yeni_yil} yapıldı; koordinatörlük görevleri temizlendi. Yedek: {yedek.name}. Yeni yıl "
                       "için tatilleri ve yerleştirmeleri güncelleyin; ders dağılımı için 'zorunlu dersleri aç' "
                       "yazarak sınıfların yeni seviyesindeki çerçeve programı derslerini açabilirsiniz.", git="Asistan")


EYLEMLER: dict[str, Eylem] = {e.anahtar: e for e in [
    Eylem("cerceve_dersleri", "Çerçeve programdaki zorunlu dersleri aç", _cerceve_dersleri,
          onay="Her sınıfın seviye, alan ve dalına göre çerçeve öğretim programındaki zorunlu dersleri ders "
               "dağılımına eklenecek; haftalık saati farklı olanlar düzeltilecek. Mevcut öğretmen atamaları ve "
               "çizelgede olmayan dersler korunur. Devam edilsin mi?"),
    Eylem("program_olustur", "Ders programını oluştur", _program_olustur, uzun=True,
          onay="Kilitli olmayan program hücreleri yeniden yerleştirilecek. Devam edilsin mi?"),
    Eylem("koordinator", "Koordinatör görevlendir", _koordinator,
          onay="Mevcut koordinatörlük görevleri silinip yeniden dağıtılacak. Devam edilsin mi?"),
    Eylem("gorevlendirme_yazilari", "Görevlendirme yazılarını hazırla", _gorevlendirme_yazilari),
    Eylem("ziyaret_plani", "Aylık ziyaret planı", _ziyaret_plani),
    Eylem("sozlesmeler", "Sözleşmeleri hazırla", _sozlesmeler),
    Eylem("degerlendirme_formlari", "Değerlendirme formlarını hazırla", _degerlendirme_formlari),
    Eylem("sgk_prim", "SGK prim hizmet listesi", _sgk_prim),
    Eylem("sgk_bildirim", "SGK giriş/çıkış listesi", _sgk_bildirim),
    Eylem("sgk_xml", "e-Bildirge aylık prim ve hizmet belgesi XML", _sgk_xml),
    Eylem("sgk_excel", "e-Bildirge aylık prim ve hizmet belgesi Excel (SGK şablonu)",
          lambda db, **kw: _sgk_xml(db, **{**kw, "bicim": "excel"})),
    Eylem("sgk_bildirge_xml", "SGK işe giriş / işten ayrılış XML", _sgk_bildirge_xml),
    Eylem("sgk_bildirge_excel", "SGK işe giriş / işten ayrılış Excel (SGK şablonu)",
          lambda db, **kw: _sgk_bildirge_xml(db, **{**kw, "bicim": "excel"})),
    Eylem("ucret", "Ücret ve devlet katkısını hesapla", _ucret),
    Eylem("dekont", "Dekont takip listesi", _dekont),
    Eylem("ekders", "Ek ders puantajı", _ekders),
    Eylem("devam", "Devamsızlık özeti", _devam),
    Eylem("veli", "Veli devamsızlık bildirimleri", _veli),
    Eylem("komisyon_karari", "Koordinatörlük komisyon kararı", _komisyon_karari),
    Eylem("koordinator_bildirimleri", "Koordinatörleri işletmelere bildir", _koordinator_bildirimleri),
    Eylem("uygunluk_tutanaklari", "İşletme uygunluk tutanakları", _uygunluk_tutanaklari),
    Eylem("alan_taramasi", "Alan taraması özeti", _alan_taramasi),
    Eylem("anket_ozeti", "Anket değerlendirmesi", _anket_ozeti),
    Eylem("hizmetici", "Hizmetiçi eğitim programı", _hizmetici),
    Eylem("puan_cizelgesi", "Puan çizelgesi durumu", _puan_cizelgesi),
    Eylem("yedek", "Yedek al", _yedek),
    Eylem("denetim", "Veri denetimi", _denetim),
    Eylem("aylik_kapanis", "Aylık kapanışı hazırla", lambda db, yil=None, ay=None, **_: aylik_kapanis(db, yil, ay),
          uzun=True),
    Eylem("yil_sonu", "Yerleştirmeleri sona erdir", yil_sonu, tarih_ister=True,
          onay="Tüm aktif yerleştirmeler seçilen tarihte sona erdirilecek (önce yedek alınır). Devam edilsin mi?"),
    Eylem("yeni_egitim_yili", "Yeni eğitim yılına geç", yeni_egitim_yili,
          onay="Öğrenciler üst sınıfa geçirilecek, 12. sınıflar mezun yapılacak, koordinatörlük görevleri silinecek "
               "(önce yedek alınır). Devam edilsin mi?"),
]}
for _ad in ["Veri Aktarımı", "Ayarlar ve Mevzuat Parametreleri", "Tatil Günleri", "Öğretmenler", "Öğrenciler / Çıraklar",
            "İşletmeler", "Sınıflar / Şubeler", "Ders Dağılımı ve Atölye Yerleşimi", "Yerleştirme ve Sözleşmeler",
            "Koordinatörlük", "SGK Sigorta İşlemleri", "Öğrenci Ücreti ve Devlet Katkısı", "Devamsızlık ve Değerlendirme",
            "Ek Ders Puantajı", "Belge Üretimi", "Komisyon ve İzleme İşleri", "e-Okul Öğrenci Eşitleme (Nakil)",
            "Program Araçları (Kısıt, Sürüm, Devir, Yük)", "Koordinatörlük Formları ve Teslim Takibi",
            "Sınav Planlama ve Görevlendirme"]:
    EYLEMLER[f"git:{_ad}"] = Eylem(f"git:{_ad}", f"{_ad} ekranını aç", git=_ad)


def calistir(db, anahtar: str, **kw) -> EylemSonucu:
    e = EYLEMLER[anahtar]
    if e.git and not e.calistir:
        return EylemSonucu("", git=e.git)
    return e.calistir(db, **kw)


# ------------------------------------------------------------------ süreçler

@dataclass
class Adim:
    baslik: str
    kontrol: Callable[[Any, int, int], tuple[bool | None, str]]
    eylem: str | None = None


@dataclass
class Surec:
    anahtar: str
    baslik: str
    aciklama: str
    adimlar: list[Adim]


def _say(db, sql: str, params=()) -> int:
    return db.q1(sql, params)[0]


def _egitim_yili(db) -> tuple[date, date]:
    ey = db.kurum()["egitim_yili"] or ""
    y = int(ey[:4]) if ey[:4].isdigit() else (date.today().year if date.today().month >= 9 else date.today().year - 1)
    return date(y, 9, 1), date(y + 1, 8, 31)


def _k_kurum(db, *_):
    k = db.kurum()
    eksik = [a for a, kol in [("kurum adı", "ad"), ("müdür", "mudur"), ("SGK sicil", "sgk_isyeri_sicil")] if not k[kol]]
    return (not eksik, "Eksik: " + ", ".join(eksik) if eksik else f"{k['ad']} ({k['tur']})")


def _k_parametre(db, *_):
    return None, (f"Brüt asgari ücret {para(db.ayar('asgari_ucret_brut'))} TL, net {para(db.ayar('asgari_ucret_net'))} TL,"
                  f" katsayı {db.ayar('aylik_katsayi')}, Geçici 12: {'açık' if db.ayar('gecici12_aktif') else 'kapalı'}"
                  " — güncel olduğunu doğrulayın")


def _k_tatil(db, *_):
    b, e = _egitim_yili(db)
    n = _say(db, "SELECT COUNT(*) FROM tatiller WHERE baslangic BETWEEN ? AND ?", (b.isoformat(), e.isoformat()))
    return n >= 3, f"{n} tatil kaydı"


def _k_sayi(tablo: str, ad: str, kosul: str = "1=1"):
    def f(db, *_):
        n = _say(db, f"SELECT COUNT(*) FROM {tablo} WHERE {kosul}")
        return n > 0, f"{n} {ad}" if n else f"{ad.capitalize()} yok; listeyi aktarın"
    return f


def _k_sinif_gunleri(db, *_):
    rows = db.q("""SELECT DISTINCT s.ad FROM siniflar s JOIN ogrenciler o ON o.sinif_id = s.id
                   JOIN yerlestirmeler y ON y.ogrenci_id = o.id AND y.durum = 'Aktif' AND y.isletme_id IS NOT NULL
                   WHERE (s.isletme_gunleri IS NULL OR s.isletme_gunleri = '')""")
    return not rows, ("İşletme günü eksik: " + ", ".join(r["ad"] for r in rows)) if rows else "Tamam"


def _k_isletme(db, *_):
    rows = db.q("""SELECT DISTINCT i.ad FROM isletmeler i JOIN yerlestirmeler y ON y.isletme_id = i.id
                   AND y.durum = 'Aktif' WHERE i.personel_sayisi IS NULL OR i.personel_sayisi = 0
                   OR i.usta_ogretici IS NULL OR i.usta_ogretici = ''""")
    n = _say(db, "SELECT COUNT(*) FROM isletmeler WHERE aktif = 1")
    if not n:
        return False, "İşletme yok"
    return not rows, f"{len(rows)} işletmede personel sayısı/usta öğretici eksik" if rows else f"{n} işletme"


def _k_ders_dagilimi(db, *_):
    n = _say(db, "SELECT COUNT(*) FROM ders_atamalari")
    u = cerceve.uyumsuzluklar(db)
    eksik = [x for x in u if not x.sorun]
    if eksik:
        return False, (f"{len(eksik)} sınıfta zorunlu ders eksik veya saati farklı: "
                       + ", ".join(x.sinif for x in eksik[:4]))
    if not n:
        return False, "Ders dağılımı yok"
    eslesmeyen = [x.sinif for x in u if x.sorun]
    return True, f"{n} ders ataması" + (f"; çizelgesi eşleşmeyen sınıf: {', '.join(eslesmeyen[:4])}"
                                        if eslesmeyen else ", çerçeve programa uygun")


def _k_program(db, *_):
    if not _say(db, "SELECT COUNT(*) FROM program_hucreleri"):
        return False, "Program oluşturulmamış"
    e, c = program.eksik_saatler(db), program.catismalar(db)
    return not e and not c, f"{len(e)} eksik ders, {len(c)} çakışma" if e or c else "Çakışmasız ve tam"


def _k_yerlestirme(db, *_):
    n = _say(db, f"""SELECT COUNT(*) FROM ogrenciler o JOIN siniflar s ON s.id = o.sinif_id WHERE o.aktif = 1
                     AND {ISLETMEYE_GIDEN_SINIF_SQL} AND NOT EXISTS (SELECT 1 FROM yerlestirmeler y
                     WHERE y.ogrenci_id = o.id AND y.durum = 'Aktif')""")
    return n == 0, f"{n} öğrenci yerleştirilmedi" if n else "Tüm öğrenciler yerleştirildi"


def _k_sozlesme(db, *_):
    n = _say(db, """SELECT COUNT(*) FROM yerlestirmeler WHERE durum = 'Aktif' AND isletme_id IS NOT NULL
                    AND tur != 'Okulda Alan Eğitimi' AND (sozlesme_no IS NULL OR sozlesme_no = '')""")
    return n == 0, f"{n} yerleştirmede sözleşme no yok" if n else "Tamam"


def _k_sgk(tur: str | None):
    def f(db, *_):
        b = [x for x in sigorta.bekleyen_bildirimler(db) if tur is None or x.tur == tur]
        gec = sum(1 for x in b if x.gecikti)
        return not b, (f"{len(b)} bekleyen" + (f", {gec} süresi geçmiş" if gec else "")) if b else "Bekleyen yok"
    return f


def _k_koord(db, *_):
    n = _say(db, """SELECT COUNT(DISTINCT y.isletme_id) FROM yerlestirmeler y WHERE y.durum = 'Aktif'
                    AND y.isletme_id IS NOT NULL AND y.tur != 'Okulda Alan Eğitimi' AND NOT EXISTS
                    (SELECT 1 FROM koordinator_gorevleri kg WHERE kg.isletme_id = y.isletme_id)""")
    return n == 0, f"{n} işletmeye görevlendirme yok" if n else "Tüm işletmelere koordinatör atandı"


def _k_ziyaret(kaydir: int = 0):
    def f(db, yil, ay):
        y, a = sonraki_ay(yil, ay) if kaydir else (yil, ay)
        ilk, son = ay_araligi(y, a)
        n = _say(db, "SELECT COUNT(*) FROM ziyaretler WHERE tarih BETWEEN ? AND ?", (ilk.isoformat(), son.isoformat()))
        return n > 0, f"{_donem(y, a)}: {n} ziyaret" if n else f"{_donem(y, a)} planı yok"
    return f


def _k_ziyaret_sonuc(db, yil, ay):
    ilk, son = ay_araligi(yil, ay)
    n = _say(db, "SELECT COUNT(*) FROM ziyaretler WHERE durum = 'Planlandı' AND tarih BETWEEN ? AND ?",
             (ilk.isoformat(), min(son, date.today() - timedelta(days=1)).isoformat()))
    return n == 0, f"Sonucu girilmemiş {n} ziyaret" if n else "Tamam"


def _k_devam_ay(db, yil, ay):
    ilk, son = ay_araligi(yil, ay)
    n = _say(db, "SELECT COUNT(*) FROM devamsizlik WHERE tarih BETWEEN ? AND ?", (ilk.isoformat(), son.isoformat()))
    return (True if n else None), f"{n} devamsızlık kaydı" if n else "Bu ay kayıt yok; e-Okul listesini aktarabilirsiniz"


def _k_bilgi(metin: str):
    return lambda db, yil, ay: (None, metin)


def _k_muhsgk(db, yil, ay):
    sy, sa = sonraki_ay(yil, ay)
    return None, f"MUHSGK son günü {db.ayar('muhsgk_son_gun')}.{sa:02d}.{sy}"


def _k_aphb(db, yil, ay):
    verildi = db.ayar(sgk_risk.aphb_anahtari(yil, ay))
    if verildi:
        return True, f"Verildi ({tr(verildi)})"
    return None, f"Son gün {sgk_risk.aphb_son_gunu(db, yil, ay):%d.%m.%Y}; yükleyince 'verildi' işaretleyin"


def _k_ucret(db, yil, ay):
    n = _say(db, "SELECT COUNT(*) FROM aylik_odemeler WHERE donem = ?", (f"{yil:04d}-{ay:02d}",))
    return n > 0, f"{n} öğrenci kaydedildi" if n else "Dönem kaydedilmedi"


def _k_dekont(db, yil, ay):
    r = db.q1("SELECT COUNT(*) n, COALESCE(SUM(dekont_teslim), 0) t FROM aylik_odemeler WHERE donem = ?",
              (f"{yil:04d}-{ay:02d}",))
    if not r["n"]:
        return False, "Önce ücret dönemi kaydedilmeli"
    return r["t"] >= r["n"], f"{r['t']}/{r['n']} dekont teslim alındı"


def _k_veli(db, *_):
    n = sum(1 for x in devam.ozet(db) if x.durum in ("Sınırı aştı", "Sınıra yakın", "Veli bildirimi"))
    return (None if n else True), f"{n} öğrenci için bildirim gerekebilir" if n else "Gerekmiyor"


def _k_yedek(db, *_):
    yedekler = config.yedek_dosyalari(config.backup_dir())
    if not yedekler:
        return False, "Hiç yedek yok"
    son = datetime.fromtimestamp(yedekler[-1].stat().st_mtime)
    return (datetime.now() - son).days <= 7, f"Son yedek: {son:%d.%m.%Y %H:%M}"


def _k_beceri(db, *_):
    n = _say(db, """SELECT COUNT(DISTINCT y.ogrenci_id) FROM yerlestirmeler y WHERE y.durum = 'Aktif'
                    AND y.isletme_id IS NOT NULL AND y.tur != 'Okulda Alan Eğitimi' AND NOT EXISTS
                    (SELECT 1 FROM beceri_notlari b WHERE b.ogrenci_id = y.ogrenci_id AND b.donem = 2)""")
    return n == 0, f"{n} öğrencinin 2. dönem notu yok" if n else "Tamam"


def _k_aktif_yer(db, *_):
    n = _say(db, "SELECT COUNT(*) FROM yerlestirmeler WHERE durum = 'Aktif'")
    return n == 0, f"{n} aktif yerleştirme" if n else "Aktif yerleştirme kalmadı"


def _k_ders_yili(db, *_):
    k = db.kurum()
    eksik = [ad for ad, kol in [("başlangıç", "ders_yili_baslangic"), ("1. dönem sonu", "birinci_donem_sonu"),
                                ("yıl sonu", "ders_yili_sonu")] if not k[kol]]
    return not eksik, ("Eksik: " + ", ".join(eksik)) if eksik else \
        f"{tr(k['ders_yili_baslangic'])} - {tr(k['ders_yili_sonu'])}"


def _k_uygunluk(db, *_):
    n = _say(db, """SELECT COUNT(DISTINCT i.id) FROM isletmeler i JOIN yerlestirmeler y ON y.isletme_id = i.id
                    AND y.durum = 'Aktif' WHERE i.uygunluk_tarihi IS NULL OR i.uygunluk_tarihi = ''""")
    return n == 0, f"{n} işletmede uygunluk tespiti yok" if n else "Tamam"


def _k_secim(db, *_):
    bekleyen = _say(db, f"""SELECT COUNT(*) FROM ogrenciler o JOIN siniflar s ON s.id = o.sinif_id WHERE o.aktif = 1
                            AND {ISLETMEYE_GIDEN_SINIF_SQL} AND NOT EXISTS (SELECT 1 FROM yerlestirmeler y
                            WHERE y.ogrenci_id = o.id AND y.durum = 'Aktif' AND y.isletme_id IS NOT NULL)""")
    if not bekleyen:
        return True, "İşletmeye gidecek öğrencilerin tamamı yerleşti"
    ort = _say(db, f"""SELECT COUNT(*) FROM ogrenciler o JOIN siniflar s ON s.id = o.sinif_id WHERE o.aktif = 1
                       AND {ISLETMEYE_GIDEN_SINIF_SQL} AND o.basari_ortalamasi IS NULL""")
    return False, f"{bekleyen} öğrenci yerleşmedi" + (f", {ort} öğrencinin başarı ortalaması yok" if ort else "")


def _k_sozlesme_tarihi(db, *_):
    n = _say(db, """SELECT COUNT(*) FROM yerlestirmeler WHERE durum = 'Aktif' AND isletme_id IS NOT NULL
                    AND tur != 'Okulda Alan Eğitimi' AND (sozlesme_tarihi IS NULL OR sozlesme_tarihi = '')""")
    yb = mesleki_egitim.ders_yili_baslangici(db)
    son = f" (son gün {tr(yb + timedelta(days=int(db.ayar('sozlesme_sure_gun'))))})" if yb else ""
    return n == 0, f"{n} yerleştirmede sözleşme tarihi yok{son}" if n else "Tamam"


def _k_plan_onay(db, *_):
    n = _say(db, """SELECT COUNT(DISTINCT i.id) FROM isletmeler i JOIN yerlestirmeler y ON y.isletme_id = i.id
                    AND y.durum = 'Aktif' WHERE i.plan_onay_tarihi IS NULL OR i.plan_onay_tarihi = ''""")
    return n == 0, f"{n} işletmenin eğitim planı onay tarihi yok" if n else "Tamam"


def _k_yillik(tablo: str, ad: str):
    def f(db, *_):
        b, e = _egitim_yili(db)
        n = _say(db, f"SELECT COUNT(*) FROM {tablo} WHERE tarih BETWEEN ? AND ?", (b.isoformat(), e.isoformat()))
        return n > 0, f"Bu eğitim yılında {n} {ad}" if n else f"Bu eğitim yılında {ad} kaydı yok"
    return f


def _k_puan(db, *_):
    donemler = mesleki_egitim.donem_sonlari(db)
    if not donemler:
        return None, "Dönem sonu tarihlerini Kurum Bilgileri'ne girin"
    bugun = date.today()
    no, son = next(((n, s) for n, s in donemler if s >= bugun), donemler[-1])
    eksik = len(mesleki_egitim.puan_eksikleri(db, no))
    teslim = son - timedelta(days=int(db.ayar("puan_cizelgesi_gun")))
    return eksik == 0, f"{no}. dönem son teslim {tr(teslim)}: " + (f"{eksik} öğrencinin notu eksik" if eksik else "tamam")


SURECLER: dict[str, Surec] = {s.anahtar: s for s in [
    Surec("yil_basi", "Eğitim yılı başlangıcı", "Eylül ayında ve dönem başında yapılacak hazırlıklar", [
        Adim("Kurum bilgileri", _k_kurum, "git:Ayarlar ve Mevzuat Parametreleri"),
        Adim("Mevzuat parametreleri (asgari ücret, katsayı)", _k_parametre, "git:Ayarlar ve Mevzuat Parametreleri"),
        Adim("Eğitim yılı tatil günleri", _k_tatil, "git:Tatil Günleri"),
        Adim("Öğretmen listesi", _k_sayi("ogretmenler", "öğretmen", "aktif = 1"), "git:Veri Aktarımı"),
        Adim("Öğrenci listesi (e-Okul)", _k_sayi("ogrenciler", "öğrenci", "aktif = 1"), "git:Veri Aktarımı"),
        Adim("İşletme listesi ve bilgileri", _k_isletme, "git:İşletmeler"),
        Adim("İşletme uygunluk tespiti (md.140-142)", _k_uygunluk, "uygunluk_tutanaklari"),
        Adim("Ders dağılımı (çerçeve öğretim programına göre)", _k_ders_dagilimi, "cerceve_dersleri"),
        Adim("Ders programı ve atölye yerleşimi", _k_program, "program_olustur"),
        Adim("Öğrencilerin işletmelere yerleştirilmesi", _k_yerlestirme, "git:Yerleştirme ve Sözleşmeler"),
        Adim("Sınıfların işletme günleri", _k_sinif_gunleri, "git:Sınıflar / Şubeler"),
        Adim("Sözleşmeler", _k_sozlesme, "sozlesmeler"),
        Adim("SGK işe giriş bildirgeleri", _k_sgk("Giriş"), "sgk_bildirim"),
        Adim("Koordinatör öğretmen görevlendirmesi", _k_koord, "koordinator"),
        Adim("Görevlendirme yazıları", _k_bilgi("Görevlendirme sonrası yazıları hazırlayın"), "gorevlendirme_yazilari"),
        Adim("Koordinatörlerin işletmelere bildirimi (md.88/1)", _k_bilgi("Görevlendirme sonrası yazıları hazırlayın"),
             "koordinator_bildirimleri"),
        Adim("Bu ayın ziyaret planı", _k_ziyaret(), "ziyaret_plani"),
    ]),
    Surec("aylik", "Aylık işlemler", "Her ay sonunda ve izleyen ayın ilk haftalarında yapılacak işler", [
        Adim("Devamsızlıkların işlenmesi", _k_devam_ay, "git:Veri Aktarımı"),
        Adim("Ziyaret sonuçlarının girilmesi", _k_ziyaret_sonuc, "git:Koordinatörlük"),
        Adim("SGK aylık prim hizmet listesi", _k_muhsgk, "sgk_prim"),
        Adim("e-Bildirge V2 aylık prim ve hizmet belgesi XML", _k_aphb, "sgk_xml"),
        Adim("SGK giriş/çıkış bildirimleri", _k_sgk(None), "sgk_bildirim"),
        Adim("Ücret ve devlet katkısı hesabı", _k_ucret, "ucret"),
        Adim("Dekontların toplanması", _k_dekont, "dekont"),
        Adim("Ek ders puantajı", _k_bilgi("KBS'ye girişten önce kontrol edin"), "ekders"),
        Adim("Veli devamsızlık bildirimleri", _k_veli, "veli"),
        Adim("Gelecek ayın ziyaret planı", _k_ziyaret(1), "ziyaret_plani_sonraki"),
        Adim("Veritabanı yedeği", _k_yedek, "yedek"),
    ]),
    Surec("yil_sonu", "Yıl sonu ve yeni yıla geçiş", "Haziran ayında ve yeni eğitim yılından önce", [
        Adim("İşletmede mesleki eğitim notları (2. dönem)", _k_beceri, "degerlendirme_formlari"),
        Adim("Mezun ve işyeri anketleri (md.89/1-ğ)", _k_yillik("anketler", "anket"), "anket_ozeti"),
        Adim("Alan taraması ve gelecek yıl işletme talepleri (md.89/2)", _k_yillik("isletme_talepleri", "talep"),
             "alan_taramasi"),
        Adim("Son ayın kapanışı", _k_ucret, "aylik_kapanis"),
        Adim("Yerleştirmelerin sona erdirilmesi", _k_aktif_yer, "yil_sonu"),
        Adim("SGK işten ayrılış bildirgeleri", _k_sgk("Çıkış"), "sgk_bildirim"),
        Adim("Veritabanı yedeği", _k_yedek, "yedek"),
        Adim("Yeni eğitim yılına geçiş (sınıf atlatma)", _k_bilgi("Yeni yıl başında bir kez çalıştırın"),
             "yeni_egitim_yili"),
    ]),
    Surec("yonetmelik", "Koordinatör müdür yardımcısı görevleri (Yönetmelik)",
          "Ortaöğretim Kurumları Yönetmeliği md.82, 88, 89 ve 134-153 uyarınca yıl boyunca izlenecek işler", [
        Adim("Ders yılı ve dönem tarihleri", _k_ders_yili, "git:Ayarlar ve Mevzuat Parametreleri"),
        Adim("İşletme uygunluk tespiti (md.140-142)", _k_uygunluk, "uygunluk_tutanaklari"),
        Adim("Öğrencilerin seçimi ve işletmelere dağıtımı (md.136)", _k_secim, "git:Komisyon ve İzleme İşleri"),
        Adim("Sözleşmelerin imzalanması (md.143)", _k_sozlesme_tarihi, "sozlesmeler"),
        Adim("Koordinatörlük planlaması ve görevlendirme (md.88/2)", _k_koord, "koordinator"),
        Adim("Koordinatörlük komisyon kararı (md.88/2-b)", _k_bilgi("Görevlendirmeden sonra hazırlayın"),
             "komisyon_karari"),
        Adim("Koordinatör isimlerinin işletmelere bildirimi (md.88/1)",
             _k_bilgi("Görevlendirmeden sonra yazıları hazırlayın"), "koordinator_bildirimleri"),
        Adim("Usta öğretici eğitim planlarının onayı (md.146)", _k_plan_onay, "git:İşletmeler"),
        Adim("Usta öğretici hizmetiçi eğitim programı (md.82/2-b)", _k_yillik("hizmetici_egitimler", "eğitim"),
             "hizmetici"),
        Adim("Puan çizelgeleri (dönem sonundan 5 gün önce, md.89/1-g)", _k_puan, "puan_cizelgesi"),
        Adim("Mezun ve işyeri anketleri (md.89/1-ğ, md.82/2-g)", _k_yillik("anketler", "anket"), "anket_ozeti"),
        Adim("Alan taraması ve işletme talepleri (md.89/2)", _k_yillik("isletme_talepleri", "talep"),
             "alan_taramasi"),
    ]),
]}
EYLEMLER["ziyaret_plani_sonraki"] = Eylem(
    "ziyaret_plani_sonraki", "Gelecek ayın ziyaret planı",
    lambda db, yil=None, ay=None, **kw: _ziyaret_plani(db, *sonraki_ay(*_ay(yil, ay))))


@dataclass
class AdimDurumu:
    adim: Adim
    durum: bool | None
    detay: str


def durumlar(db, surec: str, yil: int | None = None, ay: int | None = None) -> list[AdimDurumu]:
    yil, ay = _ay(yil, ay)
    out = []
    for a in SURECLER[surec].adimlar:
        try:
            d, m = a.kontrol(db, yil, ay)
        except Exception as e:  # denetim hatası adımı bozmamalı
            d, m = False, f"Denetlenemedi: {e}"
        out.append(AdimDurumu(a, d, m))
    return out


def surec_ozeti(db, surec: str, yil: int | None = None, ay: int | None = None) -> tuple[int, int]:
    d = durumlar(db, surec, yil, ay)
    return sum(1 for x in d if x.durum is True), sum(1 for x in d if x.durum is not None)


# ------------------------------------------------------------------ aktarım sonrası öneriler

_SONRAKI: dict[str, list[str]] = {
    "ogrenciler": ["git:Sınıflar / Şubeler", "denetim"],
    "ogretmenler": ["git:Öğretmenler"],
    "isletmeler": ["koordinator", "git:İşletmeler"],
    "siniflar": ["cerceve_dersleri", "git:Sınıflar / Şubeler"],
    "atolyeler": ["program_olustur"],
    "dersler": ["git:Ders Dağılımı ve Atölye Yerleşimi"],
    "ders_atamalari": ["program_olustur", "denetim"],
    "program_hucreleri": ["program_olustur", "git:Ders Dağılımı ve Atölye Yerleşimi"],
    "yerlestirmeler": ["sozlesmeler_yeni", "sgk_bildirim", "sgk_bildirge_xml", "koordinator", "ucret"],
    "koordinator_gorevleri": ["gorevlendirme_yazilari", "ziyaret_plani"],
    "devamsizlik": ["devam", "veli"],
    "beceri_notlari": ["git:Devamsızlık ve Değerlendirme"],
    "tatiller": ["ziyaret_plani"],
    "ek_ders_kayitlari": ["ekders"],
    "ziyaretler": ["git:Koordinatörlük"],
    "dekontlar": ["dekont"],
    "sgk_bildirimleri": ["sgk_bildirim"],
}


def sonraki_adimlar(anahtar: str, yeni_yerlestirmeler: list[int] | None = None) -> list[tuple[str, str]]:
    """Aktarımdan sonra önerilen (etiket, eylem anahtarı) listesi."""
    out = []
    for e in _SONRAKI.get(anahtar, []):
        if e == "sozlesmeler_yeni":
            if yeni_yerlestirmeler:
                out.append((f"Yeni {len(yeni_yerlestirmeler)} yerleştirmenin sözleşmelerini hazırla", e))
            continue
        out.append((EYLEMLER[e].etiket, e))
    return out


EYLEMLER["sozlesmeler_yeni"] = Eylem("sozlesmeler_yeni", "Yeni yerleştirmelerin sözleşmeleri", _sozlesmeler)
