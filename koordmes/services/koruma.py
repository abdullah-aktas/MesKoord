"""Ceza koruması: kayıt girilirken "şimdi ne yapılmalı, son gün ne" rehberi ve arka planda izlenen kritik süreler.

Program SGK ve mevzuat sürelerini kullanıcının bilmesini beklemez:
- Yerleştirme (sigorta) kaydedilince işe giriş / işten ayrılış bildirgesinin gerekip gerekmediği, son günü, gecikirse
  olası idari para cezası, belge türü ve sigorta kolu, MESEM çıraklık sözleşmesinin son imza günü ve açık lise
  (MAOL) öğrencisinin başka işte sigortalı olup olmadığı tek pencerede söylenir; bildirge dosyası hemen üretilebilir.
- Ana pencere bu modülün `kritikler` listesini düzenli aralıkla tarar; süresi geçen ya da bugün/yarın dolan işler
  ekranın üstünde ve Windows bildiriminde gösterilir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from ..mevzuat import OKUL_ICI_TURLER, maol_mi, mem_mi
from . import mesleki_egitim, sigorta, takvim
from .sgk_risk import _TATIL_BILDIRILMEZ
from .utils import para, tarih, tc_gecerli, tr


@dataclass
class Rehber:
    baslik: str
    satirlar: list[str] = field(default_factory=list)
    xml_tur: str | None = None  # "Giriş" | "Çıkış": bildirge dosyası üretilebilir
    yerlestirme_ids: list[int] = field(default_factory=list)
    kritik: bool = False

    @property
    def metin(self) -> str:
        return "\n\n".join(self.satirlar)


def _cezalar(db, tur: str) -> tuple[float, float]:
    au = db.ayar("asgari_ucret_brut")
    ceza = au * db.ayar("sgk_ipc_giris_kat" if tur == "Giriş" else "sgk_ipc_cikis_kat")
    return ceza, ceza * db.ayar("sgk_ipc_indirim")


def _bildirim_satiri(db, b: sigorta.Bildirim, bugun: date) -> tuple[str, bool]:
    ad = "İşe giriş" if b.tur == "Giriş" else "İşten ayrılış"
    ceza, indirimli = _cezalar(db, b.tur)
    kalan = (b.son_tarih - bugun).days
    if kalan < 0:
        return (f"⚠ {ad} bildirgesinin süresi GEÇTİ (son gün {tr(b.son_tarih)}). Bugün e-Bildirge'den verin. Olası "
                f"idari para cezası ~{para(ceza)} TL; süre bitiminden itibaren 30 gün içinde kendiliğinden verilirse "
                f"dörtte bire iner, peşin ödemede ~{para(indirimli)} TL."), True
    ne_zaman = "BUGÜN" if kalan == 0 else f"en geç {tr(b.son_tarih)} ({kalan} gün kaldı)"
    kural = ("sigortalılık başlamadan önce verilir" if b.tur == "Giriş" else
             f"ayrılıştan itibaren {db.ayar('sgk_cikis_bildirim_gun')} gün içinde verilir")
    return (f"{ad} bildirgesi {ne_zaman} verilmeli ({kural}). Gecikirse olası ceza ~{para(ceza)} TL. Belge türü "
            f"{b.belge_turu}."), kalan <= 1


def yerlestirme_rehberi(db, yid: int, onceki: dict | None = None, bugun: date | None = None) -> Rehber | None:
    """Kaydedilen yerleştirme için yapılacaklar; söylenecek bir şey yoksa None."""
    bugun = bugun or date.today()
    r = db.q1("""SELECT y.*, o.ad, o.soyad, o.tc, o.statu, o.baska_sigortali, s.program
                 FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                 LEFT JOIN siniflar s ON s.id = o.sinif_id WHERE y.id = ?""", (yid,))
    if r is None:
        return None
    onceki = onceki or {}
    ad = f"{r['ad']} {r['soyad']}"
    mem, maol = mem_mi(r["program"], r["statu"], r["tur"]), maol_mi(r["program"], r["statu"])
    grup = "MESEM çırağı" if mem else "Açık lise (MAOL) öğrencisi" if maol else "Öğrenci"
    rh = Rehber(f"{ad} - SGK ve sözleşme işleri", yerlestirme_ids=[yid])
    if not tc_gecerli(r["tc"]):
        rh.satirlar.append(f"⚠ T.C. kimlik numarası geçersiz ('{r['tc'] or ''}'): SGK bildirgesi verilemez ve öğrenci "
                           "sigortasız sayılır. Öğrenci kartını hemen düzeltin.")
        rh.kritik = True

    bekleyen = {(b.yerlestirme_id, b.tur): b for b in sigorta.bekleyen_bildirimler(db, bugun, ileri_gun=400)}
    yeni_bas = not onceki or (onceki.get("baslangic") or "") != (r["baslangic"] or "")
    yeni_bit = bool(r["bitis"]) and (onceki.get("bitis") or "") != (r["bitis"] or "")
    if r["baslangic"] and yeni_bas and not r["sigorta_giris_bildirildi"]:
        b = bekleyen.get((yid, "Giriş"))
        if b:
            s, k = _bildirim_satiri(db, b, bugun)
            rh.satirlar.append(s)
            rh.kritik |= k
            rh.xml_tur = "Giriş"
        else:
            rh.satirlar.append("Aynı öğrencinin kaydı kesintisiz sürdüğü için (15 gün içinde işletme değişikliği) "
                               "yeni işe giriş bildirgesi gerekmez.")
    if yeni_bit and not r["sigorta_cikis_bildirildi"]:
        bit = tarih(r["bitis"])
        tatil = next((t["ad"] for t in db.q("SELECT ad, baslangic, bitis FROM tatiller")
                      if bit and tarih(t["baslangic"]) and tarih(t["baslangic"]) <= bit <= (tarih(t["bitis"]) or bit)
                      and _TATIL_BILDIRILMEZ.search(t["ad"] or "")), None)
        b = bekleyen.get((yid, "Çıkış"))
        if tatil:
            rh.satirlar.append(f"⚠ Bitiş tarihi '{tatil}' içinde. Ara tatil ve yarıyıl tatilinde işten ayrılış "
                               "bildirilmez; öğrenci tatilden sonra devam edecekse bitiş tarihini silin.")
            rh.kritik = True
        elif b:
            s, k = _bildirim_satiri(db, b, bugun)
            rh.satirlar.append(s)
            rh.kritik |= k
            rh.xml_tur = rh.xml_tur or "Çıkış"
        else:
            rh.satirlar.append("Öğrencinin yeni kaydı 15 gün içinde başladığı için işten ayrılış bildirilmez.")

    if r["isletme_id"] and not r["sozlesme_tarihi"] and r["tur"] not in OKUL_ICI_TURLER and r["durum"] == "Aktif":
        sure = next((s for s in mesleki_egitim.sozlesme_sureleri(db) if s.yerlestirme_id == yid), None)
        if sure:
            ne = "Çıraklık sözleşmesi (MESEM)" if mem else "İşletme sözleşmesi"
            gecti = sure.son < bugun
            rh.satirlar.append(f"{'⚠ ' if gecti else ''}{ne} en geç {tr(sure.son)} imzalanmalı (md.143)"
                               + ("; SÜRE GEÇTİ." if gecti else ".")
                               + " İmzalanınca kayda sözleşme tarihini girin; Word sözleşmesi bu ekrandaki "
                               "düğmeyle üretilir.")
            rh.kritik |= gecti
    if maol and not r["baska_sigortali"] and r["tur"] not in OKUL_ICI_TURLER:
        rh.satirlar.append("Açık lise (MAOL) öğrencisi: kendi işyerinden 4A/4B/4C sigortalı çalışıyorsa öğrenci "
                           "kartında 'Başka bir işte sigortalı' kutusunu işaretleyin; genel sağlık sigortası primi "
                           "ayrıca ödenmez (belge 7/49). SGK 4A'da işe giriş hata verirse bu öğrenciyi tek tek girin.")
    if not rh.satirlar:
        return None
    rh.satirlar.insert(0, f"{grup}: {ad} ({r['tur']}, başlangıç {tr(r['baslangic'])}"
                       + (f", bitiş {tr(r['bitis'])}" if r["bitis"] else "") + ")")
    return rh


def toplu_rehber(db, ids: list[int], tur: str, bugun: date | None = None) -> Rehber | None:
    """Toplu giriş / çıkış işlendikten sonra: kaç bildirge gerekiyor, en erken son gün, ceza."""
    bugun = bugun or date.today()
    secili = set(ids)
    liste = [b for b in sigorta.bekleyen_bildirimler(db, bugun, ileri_gun=400)
             if b.yerlestirme_id in secili and b.tur == tur and not b.bildirildi]
    if not liste:
        return None
    ad = "işe giriş" if tur == "Giriş" else "işten ayrılış"
    en_erken = min(b.son_tarih for b in liste)
    kalan = (en_erken - bugun).days
    ceza, indirimli = _cezalar(db, tur)
    rh = Rehber(f"SGK {ad} bildirgeleri", yerlestirme_ids=[b.yerlestirme_id for b in liste], xml_tur=tur,
                kritik=kalan <= 1)
    rh.satirlar.append(f"{len(liste)} öğrenci için {ad} bildirgesi verilmeli. En erken son gün {tr(en_erken)}"
                       + (" - SÜRE GEÇTİ, bugün verin." if kalan < 0 else " (BUGÜN)." if kalan == 0 else
                          f" ({kalan} gün kaldı)."))
    rh.satirlar.append(f"Gecikmede kişi başı olası ceza ~{para(ceza)} TL (kendiliğinden ve 30 gün içinde ~"
                       f"{para(indirimli)} TL). Dosyayı şimdi üretip SGK 4A'ya yükleyin, onaydan sonra 'Bildirildi' "
                       "işaretleyin.")
    return rh


@dataclass
class Kritik:
    anahtar: str
    mesaj: str
    git: str


def kritikler(db, bugun: date | None = None) -> list[Kritik]:
    """Üst bant ve Windows bildirimi için: süresi geçmiş ya da bugün/yarın dolan işler."""
    bugun = bugun or date.today()
    out = []
    for u in takvim.uyarilar(db, bugun):
        acil = u.seviye == "Kritik" or (u.tarih is not None and u.tarih <= bugun + timedelta(days=1)
                                        and u.konu in ("SGK", "SGK Ceza Riski", "MESEM", "Sözleşme"))
        if acil:
            out.append(Kritik(f"{u.konu}|{u.mesaj}", f"{u.konu}: {u.mesaj}", u.git))
    return out
