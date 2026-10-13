"""Okul kayıtları ile SGK listelerinin (e-Bildirge aylık prim ve hizmet belgesi, 4A işe giriş/ayrılış
listeleri) karşılaştırılması.

SGK'dan indirilen liste okunur (Excel, PDF, HTML...), sayfa başlığındaki dönem ve belge türü de
alınır. Her sigortalı okul kaydıyla T.C. kimlik no, yoksa ad-soyad benzerliğiyle eşleştirilir; T.C.,
ad-soyad, belge türü, prim günü, prime esas kazanç, giriş/çıkış tarihi farkları ve iki taraftan birinde
olmayan kişiler öneriyle birlikte listelenir. Bazı farklar tek tıkla okul kaydına işlenebilir.
"""
from __future__ import annotations

import difflib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .. import config
from ..mevzuat import isletmeye_giden_sinif, mem_mi
from . import aktarim, okuyucu, sigorta
from .aktarim import IceAktarmaTanimi, metin, norm, sayi, tr_ad
from .okuyucu import Tablo
from .utils import ay_araligi, para, tc_gecerli

SGK_LISTESI = IceAktarmaTanimi("sgk_liste", "SGK Sigortalı / Hizmet Listesi", [
    ("tc", "T.C. Kimlik No", ["tc", "tc kimlik no", "tckn", "kimlik no", "tc no", "tc kimlik numarasi",
                              "sigortali tc kimlik no", "sigortalinin tc kimlik no", "sosyal guvenlik no",
                              "sigortali sicil no", "kimlik numarasi", "tc kimlik"]),
    ("ad", "Adı", ["ad", "adi", "sigortalinin adi", "sigortali adi", "isim"]),
    ("soyad", "Soyadı", ["soyad", "soyadi", "sigortalinin soyadi", "sigortali soyadi"]),
    ("ad_soyad", "Adı Soyadı", ["adi soyadi", "ad soyad", "ad soyadi", "sigortalinin adi soyadi",
                                "sigortali adi soyadi", "adi ve soyadi"]),
    ("gun", "Prim Ödeme Günü", ["prim odeme gunu", "prim gun", "prim gunu", "gun", "gun sayisi",
                                "prim odeme gun sayisi", "pog", "hizmet gunu", "prim odeme gun", "prim gun sayisi"]),
    ("pek", "Prime Esas Kazanç", ["prime esas kazanc", "pek", "spek", "hak edilen ucret",
                                  "prime esas kazanc tutari", "sgk matrahi", "prime esas kazanc tl"]),
    ("belge_turu", "Belge Türü", ["belge turu", "belge cesidi", "belge kodu", "belge turu kodu"]),
    ("giris_tarihi", "İşe Giriş Tarihi", ["ise giris tarihi", "giris tarihi", "ise giris", "giris", "giris gunu",
                                          "sigorta baslangic tarihi", "sigortali baslama tarihi"]),
    ("cikis_tarihi", "İşten Çıkış Tarihi", ["isten cikis tarihi", "cikis tarihi", "isten ayrilis tarihi",
                                            "ayrilis tarihi", "cikis", "cikis gunu", "isten ayrilis"]),
    ("eksik_gun", "Eksik Gün Sayısı", ["eksik gun sayisi", "eksik gun"]),
    ("eksik_neden", "Eksik Gün Nedeni", ["eksik gun nedeni", "eksik gun neden kodu", "eksik gun kodu"]),
    ("donem", "Dönem", ["donem", "hizmet donemi", "yil ay", "belge donemi", "ait oldugu donem"]),
], [["tc"]])

def _tl(x: float) -> str:
    return f"{para(x)} TL"


@dataclass
class SgkKaydi:
    tc: str
    ad: str
    soyad: str
    gun: int | None = None
    pek: float | None = None
    belge_turu: str = ""
    giris: date | None = None
    cikis: date | None = None
    eksik_gun: int | None = None
    eksik_neden: str = ""
    donem: tuple[int, int] | None = None
    kaynak: str = ""

    @property
    def ad_soyad(self) -> str:
        return f"{self.ad} {self.soyad}".strip()


@dataclass
class SgkListesi:
    kayitlar: list[SgkKaydi] = field(default_factory=list)
    hatalar: list[str] = field(default_factory=list)
    kaynaklar: list[str] = field(default_factory=list)
    aphb: bool = False  # gün/PEK/belge türü içeren aylık hizmet belgesi (değilse 4A giriş/çıkış listesi)

    @property
    def donem(self) -> tuple[int, int] | None:
        c = Counter(k.donem for k in self.kayitlar if k.donem)
        return c.most_common(1)[0][0] if c else None


def aphb_mi(es: dict[str, int]) -> bool:
    """Eşleme aylık prim ve hizmet belgesi listesine mi ait? (Yalnızca 'Gün' sütunu devamsızlıkta da olur.)"""
    return "pek" in es or "belge_turu" in es or ("gun" in es and ("eksik_gun" in es or "eksik_neden" in es))


def sgk_tablosu(tablo: Tablo) -> tuple[int, dict[str, int]] | None:
    """Tablo bir SGK sigortalı listesiyse (başlık satırı, eşleme)."""
    if tablo.form:
        return None
    bas, es = aktarim.baslik_bul(tablo.satirlar, SGK_LISTESI)
    if bas < 0 or "tc" not in es:
        return None
    aphb = aphb_mi(es)
    if not aphb and "giris_tarihi" not in es and "cikis_tarihi" not in es:
        return None
    if not aphb:
        # yalnızca giriş/çıkış tarihi olan liste: işletme yerleştirme listesiyle karışmasın diye SGK ipucu aranır
        metinler = [tablo.kaynak, tablo.ad] + [metin(h) for r in tablo.satirlar[:bas + 1] for h in r]
        if not any(ip in norm(" ".join(metinler)).split() for ip in ("sgk", "sigorta", "sigortali", "bildirge",
                                                                       "4a", "tescil", "ebildirge")):
            return None
    return bas, es


def _gun_tarihi(v: Any, donem: tuple[int, int] | None) -> date | None:
    """'15.10.2026' veya APHB'deki ayın günü (15) -> tarih."""
    d = aktarim.tarih(v)
    if d:
        return d
    s = sayi(v)
    if s and donem and 1 <= s <= 31:
        try:
            return date(donem[0], donem[1], int(s))
        except ValueError:
            return None
    return None


def _belge(v: Any) -> str:
    s = metin(v)
    rakam = "".join(c for c in s.split("-")[0] if c.isdigit())
    return str(int(rakam)) if rakam else ""


def tablodan_kayitlar(tablo: Tablo, bas: int, es: dict[str, int]) -> list[SgkKaydi]:
    baglamlar = aktarim.satir_baglamlari(tablo)
    gecerli = aktarim.on_baglam(tablo, bas)
    out = []
    for i in range(bas + 1, len(tablo.satirlar)):
        if i in baglamlar:
            gecerli.update(baglamlar[i])
            continue
        r = tablo.satirlar[i]
        d = {k: (r[j] if j < len(r) else None) for k, j in es.items()}
        tc = "".join(c for c in metin(d.get("tc")) if c.isdigit())
        if len(tc) != 11:
            continue  # başlık tekrarı, toplam veya alt bilgi satırı
        ad, soyad = tr_ad(d.get("ad")), tr_ad(d.get("soyad"))
        if not ad and metin(d.get("ad_soyad")):
            ad, soyad = aktarim.ad_soyad_bol(tr_ad(d["ad_soyad"]))
        donem = aktarim.ay_coz(d.get("donem")) if metin(d.get("donem")) else None
        if not donem and gecerli.get("ay"):
            donem = aktarim.ay_coz(gecerli["ay"])
        g, ek = sayi(d.get("gun")), sayi(d.get("eksik_gun"))
        out.append(SgkKaydi(
            tc, ad, soyad, int(g) if g is not None else None, sayi(d.get("pek")),
            _belge(d.get("belge_turu")) or _belge(gecerli.get("belge_turu")),
            _gun_tarihi(d.get("giris_tarihi"), donem), _gun_tarihi(d.get("cikis_tarihi"), donem),
            int(ek) if ek is not None else None, metin(d.get("eksik_neden")).split(" ")[0], donem,
            f"{tablo.etiket} satır {i + 1}"))
    return out


def tablolardan_liste(tablolar: list[Tablo]) -> SgkListesi:
    sonuc = SgkListesi()
    for t in tablolar:
        bul = sgk_tablosu(t)
        if not bul:
            continue
        kayitlar = tablodan_kayitlar(t, *bul)
        if kayitlar:
            sonuc.kayitlar += kayitlar
            sonuc.kaynaklar.append(t.etiket)
            sonuc.aphb |= aphb_mi(bul[1])
    return sonuc


def listeyi_oku(yollar: list[Path | str]) -> SgkListesi:
    tablolar, hatalar = okuyucu.oku_coklu(yollar)
    sonuc = tablolardan_liste(tablolar)
    sonuc.hatalar = hatalar
    if not sonuc.kayitlar and not hatalar:
        sonuc.hatalar.append("Dosyada T.C. kimlik no ve prim günü/PEK/belge türü/giriş-çıkış tarihi sütunları "
                             "olan bir SGK listesi bulunamadı.")
    return sonuc


# ------------------------------------------------------------------ son indirilen liste

def _son_dosya() -> Path:
    return config.data_dir() / "sgk_son_liste.json"


def son_listeyi_kaydet(yol: Path | str, tablolar: list[Tablo]) -> bool:
    """İndirilen dosya SGK listesiyse yolunu karşılaştırma ekranı için saklar."""
    if not any(sgk_tablosu(t) for t in tablolar):
        return False
    try:
        _son_dosya().write_text(json.dumps({"yol": str(yol), "zaman": datetime.now().isoformat(timespec="seconds")},
                                           ensure_ascii=False), encoding="utf-8")
    except OSError:
        return False
    return True


def son_liste() -> tuple[Path, str] | None:
    try:
        v = json.loads(_son_dosya().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    yol = Path(v.get("yol", ""))
    return (yol, v.get("zaman", "")) if yol.is_file() else None


# ------------------------------------------------------------------ karşılaştırma

@dataclass
class Fark:
    seviye: str  # Kritik | Uyarı | Bilgi
    tur: str
    ogrenci: str
    tc: str
    okul: str
    sgk: str
    oneri: str
    ogrenci_id: int | None = None
    yerlestirme_id: int | None = None
    eylem: str = ""  # tc_duzelt | ad_duzelt | yukumlu_duzelt | giris_isaretle | cikis_isaretle | baslangic_duzelt
    deger: Any = None
    tahmini_ceza: float = 0.0

    @property
    def eylem_adi(self) -> str:
        return EYLEM_ADLARI.get(self.eylem, "")


EYLEM_ADLARI = {
    "tc_duzelt": "Okul kaydındaki T.C.'yi SGK'daki ile değiştir",
    "ad_duzelt": "Okul kaydındaki adı SGK'daki gibi yaz",
    "yukumlu_duzelt": "Bakmakla yükümlü bilgisini SGK belge türüne göre düzelt",
    "giris_isaretle": "Yerleştirmeyi 'işe giriş bildirildi' olarak işaretle",
    "cikis_isaretle": "Yerleştirmeyi 'işten ayrılış bildirildi' olarak işaretle",
    "baslangic_duzelt": "Yerleştirme başlangıcını SGK giriş tarihi yap",
    "yerlestirme_olustur": "SGK giriş/çıkış tarihleriyle yerleştirme (sigorta) kaydı oluştur",
}
SEVIYE_SIRASI = {"Kritik": 0, "Uyarı": 1, "Bilgi": 2}


@dataclass
class KarsilastirmaSonucu:
    yil: int
    ay: int
    farklar: list[Fark] = field(default_factory=list)
    sgk_sayisi: int = 0
    okul_sayisi: int = 0
    eslesen: int = 0
    notlar: list[str] = field(default_factory=list)

    @property
    def tahmini_ceza(self) -> float:
        return round(sum(f.tahmini_ceza for f in self.farklar), 2)

    def ozet(self) -> str:
        c = Counter(f.seviye for f in self.farklar)
        s = (f"{self.ay:02d}/{self.yil}: SGK listesinde {self.sgk_sayisi}, okul kayıtlarında {self.okul_sayisi} "
             f"sigortalı; {self.eslesen} eşleşti. ")
        if not self.farklar:
            return s + "Fark bulunmadı."
        s += ", ".join(f"{c[k]} {k.lower()}" for k in ("Kritik", "Uyarı", "Bilgi") if c[k]) + " bulgu."
        if self.tahmini_ceza:
            s += f" Düzeltilmezse olası idari para cezası: ~{_tl(self.tahmini_ceza)}."
        return s


def _yerlestirme(db, ogrenci_id: int, yil: int, ay: int):
    ilk, son = ay_araligi(yil, ay)
    return db.q1("""SELECT * FROM yerlestirmeler WHERE ogrenci_id = ? AND baslangic IS NOT NULL AND baslangic <= ?
                    AND (bitis IS NULL OR bitis = '' OR bitis >= ?) ORDER BY baslangic DESC""",
                 (ogrenci_id, son.isoformat(), ilk.isoformat()))


def _tarih_metni(d: date | None) -> str:
    return d.strftime("%d.%m.%Y") if d else "-"


def _sgk_tarihleri(k) -> dict:
    return {"giris": k.giris, "cikis": k.cikis, "belge": k.belge_turu}


def yerlestirme_turu_tahmini(db, ogrenci_id: int, belge: str | None = None) -> str:
    """SGK belge türü (49/50 okulda, 7/42 işletmede) yoksa öğrencinin sınıfı ve statüsünden yerleştirme türü."""
    o = db.q1("""SELECT o.statu, s.program, s.seviye FROM ogrenciler o LEFT JOIN siniflar s ON s.id = o.sinif_id
                 WHERE o.id = ?""", (ogrenci_id,))
    cirak = bool(o) and mem_mi(o["program"], o["statu"])
    okul_belgeleri = {str(db.ayar("belge_okul_yukumlu")), str(db.ayar("belge_okul_degil"))}
    if belge and str(belge) in okul_belgeleri:
        return "Okulda Alan Eğitimi"
    if belge or (o and isletmeye_giden_sinif(o["program"], o["seviye"])):
        return "Çıraklık" if cirak else "İşletmede Mesleki Eğitim"
    return "Okulda Alan Eğitimi"


def karsilastir(db, liste: SgkListesi, yil: int | None = None, ay: int | None = None) -> KarsilastirmaSonucu:
    if not (yil and ay):
        d = liste.donem
        if d:
            yil, ay = d
        else:
            bugun = date.today()
            yil, ay = (bugun.year, bugun.month - 1) if bugun.month > 1 else (bugun.year - 1, 12)
    sonuc = KarsilastirmaSonucu(yil, ay)
    if liste.donem is None:
        sonuc.notlar.append(f"Listede dönem bilgisi bulunamadı; {ay:02d}/{yil} dönemi kabul edildi.")
    kayitlar = [k for k in liste.kayitlar if k.donem in (None, (yil, ay))]
    atlanan = len(liste.kayitlar) - len(kayitlar)
    if atlanan:
        sonuc.notlar.append(f"Başka dönemlere ait {atlanan} satır karşılaştırmaya alınmadı.")
    au = db.ayar("asgari_ucret_brut")
    ceza_giris, ceza_cikis = au * db.ayar("sgk_ipc_giris_kat"), au * db.ayar("sgk_ipc_cikis_kat")
    ceza_ek = au * db.ayar("sgk_ipc_ek_belge_kisi")
    indirim = db.ayar("sgk_ipc_indirim")

    okul = sigorta.aylik_liste(db, yil, ay)
    okul_tc: dict[str, list[sigorta.SigortaSatiri]] = defaultdict(list)
    okul_id: dict[int, list[sigorta.SigortaSatiri]] = defaultdict(list)
    for s in okul:
        okul_id[s.ogrenci_id].append(s)
        if s.tc:
            okul_tc[s.tc].append(s)
    ogrenciler = db.q("SELECT o.id, o.tc, o.ad, o.soyad, s.ad AS sinif FROM ogrenciler o "
                      "LEFT JOIN siniflar s ON s.id = o.sinif_id")
    by_tc = {o["tc"]: o for o in ogrenciler if o["tc"]}
    by_ad: dict[str, list] = defaultdict(list)
    for o in ogrenciler:
        by_ad[norm(f"{o['ad']} {o['soyad']}")].append(o)
    adlar = list(by_ad)

    sonuc.sgk_sayisi = len({k.tc for k in kayitlar})
    sonuc.okul_sayisi = len({s.ogrenci_id for s in okul})
    eslesen_ogrenciler: set[int] = set()
    farklar = sonuc.farklar

    for (tc, bt), n in Counter((k.tc, k.belge_turu) for k in kayitlar).items():
        if n > 1 and liste.aphb:
            k = next(x for x in kayitlar if x.tc == tc)
            farklar.append(Fark("Uyarı", "Mükerrer satır", k.ad_soyad, tc, "-", f"{n} satır (belge {bt or '?'})",
                                "Aynı kişi aynı belge türüyle birden çok kez bildirilmiş görünüyor. Asıl ve ek "
                                "belgeler birlikte indirildiyse sorun yoktur; değilse fazladan prim ödenmiştir, "
                                "iptal belgesi verin."))

    for k in kayitlar:
        if not tc_gecerli(k.tc):
            farklar.append(Fark("Kritik", "T.C. geçersiz", k.ad_soyad, k.tc, "-", k.tc,
                                "SGK listesindeki T.C. kimlik no doğrulamadan geçmiyor. Dosyada sütun kayması "
                                "olabilir; listeyi kontrol edin."))
            continue
        o = by_tc.get(k.tc)
        if o is None and k.ad:
            n = norm(k.ad_soyad)
            adaylar = by_ad.get(n) or [x for a in difflib.get_close_matches(n, adlar, n=1, cutoff=0.88)
                                       for x in by_ad[a]]
            if len(adaylar) == 1:
                o = adaylar[0]
                okul_tc_gecerli = bool(o["tc"]) and tc_gecerli(o["tc"])
                farklar.append(Fark(
                    "Kritik", "T.C. farklı", f"{o['ad']} {o['soyad']}", k.tc, o["tc"] or "(boş)", k.tc,
                    ("Okul kaydındaki T.C. eksik veya geçersiz. SGK'daki T.C. ile düzeltin." if not okul_tc_gecerli
                     else "İki T.C. de geçerli: öğrenci yerine başka biri bildirilmiş olabilir. e-Okul/nüfus "
                          "kaydından doğrusunu teyit edin. SGK'daki yanlışsa işten ayrılış ve doğru T.C. ile işe "
                          "giriş bildirgesi verin; okuldaki yanlışsa okul kaydını düzeltin."),
                    o["id"], eylem="tc_duzelt", deger=k.tc))
        if o is None:
            farklar.append(Fark(
                "Uyarı", "Okul kayıtlarında yok", k.ad_soyad, k.tc, "-", f"belge {k.belge_turu or '?'}, "
                f"{k.gun if k.gun is not None else '?'} gün",
                "Bu kişi MesKoord'da kayıtlı değil. Öğrenciniz ise e-Okul listesini aktarın (Veri Aktarımı); "
                "değilse okul işyerinden yanlışlıkla bildirilmiş olabilir: işten ayrılış bildirgesi verin ve fazla "
                "bildirilen günler için iptal belgesi düzenleyin."))
            continue
        sonuc.eslesen += 1
        eslesen_ogrenciler.add(o["id"])
        ad_okul = f"{o['ad']} {o['soyad']}"
        if k.ad and norm(ad_okul) != norm(k.ad_soyad) and o["tc"] == k.tc:
            farklar.append(Fark("Uyarı", "Ad/soyad farklı", ad_okul, k.tc, ad_okul, k.ad_soyad,
                                "SGK kayıtları nüfus (MERNİS) bilgisinden gelir. Okul kaydındaki yazım farklıysa "
                                "SGK'daki gibi düzeltin; resmi yazılarda ad uyuşmazlığı sorun çıkarır.",
                                o["id"], eylem="ad_duzelt", deger=(k.ad, k.soyad)))
        satirlar = okul_id.get(o["id"], [])
        y = _yerlestirme(db, o["id"], yil, ay)
        if not satirlar:
            if liste.aphb and (k.gun or 0) > 0:
                farklar.append(Fark(
                    "Kritik", "Okulda işletmede değil", ad_okul, k.tc, f"{ay:02d}/{yil} döneminde yerleştirme yok",
                    f"{k.gun} gün, belge {k.belge_turu or '?'}",
                    "SGK'da sigortalı görünüyor ama okul kayıtlarına göre bu ay işletmede/okulda alan eğitiminde "
                    "değil. Yerleştirme kaydı eksikse ekleyin (Toplu Veri Girişi). Öğrenci ayrıldıysa işten ayrılış "
                    f"bildirgesi verilmemiş olabilir (geç ayrılış cezası ~{_tl(ceza_cikis)}) ve fazla prim "
                    "ödenmiştir.", o["id"], eylem="yerlestirme_olustur" if k.giris else "",
                    deger=_sgk_tarihleri(k), tahmini_ceza=round(ceza_cikis, 2)))
            elif k.giris and not liste.aphb:
                farklar.append(Fark("Uyarı", "Okulda yerleştirme yok", ad_okul, k.tc, "-",
                                    f"giriş {_tarih_metni(k.giris)}" + (f", çıkış {_tarih_metni(k.cikis)}"
                                                                         if k.cikis else ""),
                                    "SGK'ya işe giriş bildirilmiş ama okulda bu döneme ait yerleştirme yok. "
                                    "SGK tarihleriyle yerleştirme oluşturun veya bildirimi kontrol edin.", o["id"],
                                    eylem="yerlestirme_olustur", deger=_sgk_tarihleri(k)))
            continue
        s = next((x for x in satirlar if x.belge_turu == k.belge_turu), satirlar[0])
        if liste.aphb and k.belge_turu and k.belge_turu != s.belge_turu:
            yukumlu_sgk = k.belge_turu in (str(db.ayar("belge_isletme_yukumlu")), str(db.ayar("belge_okul_yukumlu")))
            farklar.append(Fark(
                "Kritik", "Belge türü farklı", ad_okul, k.tc, s.belge_turu, k.belge_turu,
                "Belge türü öğrencinin anne/babası üzerinden genel sağlık sigortalı (bakmakla yükümlü) olup "
                "olmamasına göre değişir; prim oranı %1 ile %6 arasında değişir. Durumu teyit edin: okul kaydı "
                "yanlışsa düzeltin; SGK'ya yanlış belge verildiyse iptal ve ek belge verin "
                f"(ek belge cezası ~{_tl(ceza_ek)}, kendiliğinden verilirse ~{_tl(ceza_ek * indirim)}).",
                o["id"], y["id"] if y else None, "yukumlu_duzelt", 1 if yukumlu_sgk else 0, round(ceza_ek, 2)))
        if liste.aphb and k.gun is not None and k.gun != s.gun:
            eksik = k.gun < s.gun
            farklar.append(Fark(
                "Uyarı" if abs(k.gun - s.gun) <= 2 else "Kritik", "Prim günü farklı", ad_okul, k.tc,
                f"{s.gun} gün" + (f" ({s.eksik_gun} eksik gün, kod {s.eksik_neden})" if s.eksik_gun else ""),
                f"{k.gun} gün" + (f" ({k.eksik_gun} eksik, kod {k.eksik_neden})" if k.eksik_gun else ""),
                ("SGK'ya okulun hesapladığından az gün bildirilmiş. Devamsızlık (eksik gün) ve başlangıç/bitiş "
                 "tarihlerini kontrol edin; eksik bildirim varsa ek belge verin "
                 f"(ceza ~{_tl(ceza_ek)}, kendiliğinden ~{_tl(ceza_ek * indirim)})." if eksik else
                 "SGK'ya okulun hesapladığından fazla gün bildirilmiş. Özürsüz devamsızlıklar eksik gün olarak "
                 "düşülmemiş veya ayrılış tarihi işlenmemiş olabilir; fazla bildirilen günler için iptal belgesi "
                 "verin. Okul kaydı eksikse devamsızlık/tarihleri düzeltin."),
                o["id"], y["id"] if y else None, tahmini_ceza=round(ceza_ek, 2) if eksik else 0.0))
        if liste.aphb and k.pek is not None and abs(k.pek - s.pek) > 1 and (k.gun is None or k.gun == s.gun):
            farklar.append(Fark("Uyarı", "PEK farklı", ad_okul, k.tc, _tl(s.pek), _tl(k.pek),
                                "Öğrencinin prime esas kazancı brüt asgari ücretin %50'sinin günlük tutarı × prim "
                                "günüdür. Bildirilen tutar farklı: asgari ücret parametresini ve bildirimi kontrol "
                                "edin.", o["id"], y["id"] if y else None))
        if k.giris and s.giris_tarihi and k.giris != s.giris_tarihi:
            farklar.append(Fark("Uyarı", "Giriş tarihi farklı", ad_okul, k.tc, _tarih_metni(s.giris_tarihi),
                                _tarih_metni(k.giris),
                                "Yerleştirme başlangıcı SGK işe giriş tarihiyle aynı olmalıdır. Okul kaydı yanlışsa "
                                "başlangıç tarihini düzeltin; SGK'daki yanlışsa işe giriş bildirgesinin düzeltilmesi "
                                "için SGK'ya başvurun.", o["id"], y["id"] if y else None, "baslangic_duzelt", k.giris))
        if k.cikis and s.cikis_tarihi and k.cikis != s.cikis_tarihi:
            farklar.append(Fark("Uyarı", "Çıkış tarihi farklı", ad_okul, k.tc, _tarih_metni(s.cikis_tarihi),
                                _tarih_metni(k.cikis),
                                "Yerleştirme bitiş tarihi SGK işten ayrılış tarihiyle aynı olmalıdır.",
                                o["id"], y["id"] if y else None))
        elif k.cikis and not s.cikis_tarihi:
            farklar.append(Fark("Uyarı", "Okulda çıkış yok", ad_okul, k.tc, "devam ediyor", _tarih_metni(k.cikis),
                                "SGK'ya işten ayrılış bildirilmiş ama okulda yerleştirme açık. Ayrıldıysa "
                                "yerleştirmeye bitiş tarihi girin; ayrılmadıysa yeniden işe giriş bildirgesi verin "
                                f"(sigortasız çalışma cezası ~{_tl(ceza_giris)}).", o["id"], y["id"] if y else None,
                                tahmini_ceza=0.0))
        if y is not None:
            if k.giris and not y["sigorta_giris_bildirildi"]:
                farklar.append(Fark("Bilgi", "Giriş bildirimi işaretsiz", ad_okul, k.tc, "bildirilmedi",
                                    f"giriş {_tarih_metni(k.giris)}",
                                    "SGK'da işe giriş görünüyor; okulda bildirim işaretlenmemiş.", o["id"], y["id"],
                                    "giris_isaretle", k.giris))
            if k.cikis and y["bitis"] and not y["sigorta_cikis_bildirildi"]:
                farklar.append(Fark("Bilgi", "Çıkış bildirimi işaretsiz", ad_okul, k.tc, "bildirilmedi",
                                    f"çıkış {_tarih_metni(k.cikis)}",
                                    "SGK'da işten ayrılış görünüyor; okulda bildirim işaretlenmemiş.", o["id"],
                                    y["id"], "cikis_isaretle", k.cikis))

    if liste.aphb:
        beklenen = [s for s in okul if s.ogrenci_id not in eslesen_ogrenciler]
    else:
        girisler = [k.giris for k in kayitlar if k.giris]
        if girisler:
            ilk, son = min(girisler), max(girisler)
            beklenen = [s for s in okul if s.ogrenci_id not in eslesen_ogrenciler and s.giris_tarihi
                        and ilk <= s.giris_tarihi <= son]
        else:
            beklenen = []
    for s in beklenen:
        y = _yerlestirme(db, s.ogrenci_id, yil, ay)
        bildirildi = bool(y and y["sigorta_giris_bildirildi"])
        farklar.append(Fark(
            "Kritik", "SGK listesinde yok", f"{s.ad} {s.soyad}", s.tc, f"{s.gun} gün, belge {s.belge_turu} "
            f"({', '.join(s.isletmeler) or s.sinif})", "-",
            ("Okul kayıtlarına göre bu dönemde sigortalı olmalı ama SGK listesinde yok. "
             + ("Okulda işe giriş bildirildi olarak işaretli: bildirgenin gerçekten onaylandığını ve aylık prim "
                "belgesine eklendiğini kontrol edin; eklenmediyse ek belge verin "
                f"(~{_tl(ceza_ek)})." if bildirildi else
                f"İşe giriş bildirgesi verilmediyse hemen verin (ceza ~{_tl(ceza_giris)}; kendiliğinden ve "
                f"peşin ödemede ~{_tl(ceza_giris * indirim)}; denetimde tespit edilirse 2 katı) ve aylık prim "
                "belgesine ekleyin.")),
            s.ogrenci_id, y["id"] if y else None,
            tahmini_ceza=round(ceza_ek if bildirildi else ceza_giris, 2)))
    farklar.sort(key=lambda f: (SEVIYE_SIRASI.get(f.seviye, 9), f.tur, f.ogrenci))
    return sonuc


def duzelt(db, fark: Fark) -> str:
    """Farkın önerdiği düzeltmeyi okul kaydına uygular; yapılan işlemi döndürür."""
    e, v = fark.eylem, fark.deger
    if e == "tc_duzelt":
        r = db.q1("SELECT id, ad, soyad FROM ogrenciler WHERE tc = ? AND id != ?", (v, fark.ogrenci_id))
        if r:
            raise ValueError(f"Bu T.C. başka bir öğrencide kayıtlı: {r['ad']} {r['soyad']}")
        db.update("ogrenciler", fark.ogrenci_id, {"tc": v})
        return f"{fark.ogrenci}: T.C. {v} olarak düzeltildi"
    if e == "ad_duzelt":
        db.update("ogrenciler", fark.ogrenci_id, {"ad": v[0], "soyad": v[1]})
        return f"{fark.ogrenci}: ad {v[0]} {v[1]} olarak düzeltildi"
    if e == "yukumlu_duzelt":
        db.update("ogrenciler", fark.ogrenci_id, {"bakmakla_yukumlu": int(v)})
        return f"{fark.ogrenci}: bakmakla yükümlü = {'Evet' if v else 'Hayır'}"
    if e in ("giris_isaretle", "cikis_isaretle") and fark.yerlestirme_id:
        sigorta.bildirildi_isaretle(db, fark.yerlestirme_id, "Giriş" if e == "giris_isaretle" else "Çıkış", v)
        return f"{fark.ogrenci}: bildirim işaretlendi"
    if e == "baslangic_duzelt" and fark.yerlestirme_id:
        db.update("yerlestirmeler", fark.yerlestirme_id, {"baslangic": v.isoformat()})
        return f"{fark.ogrenci}: başlangıç {v.strftime('%d.%m.%Y')} yapıldı"
    if e == "yerlestirme_olustur" and fark.ogrenci_id and v and v.get("giris"):
        giris, cikis = v["giris"], v.get("cikis")
        cakisan = db.q1("""SELECT id FROM yerlestirmeler WHERE ogrenci_id = ? AND baslangic IS NOT NULL
                           AND baslangic <= ? AND (bitis IS NULL OR bitis = '' OR bitis >= ?)""",
                        (fark.ogrenci_id, (cikis or giris).isoformat(), giris.isoformat()))
        if cakisan:
            raise ValueError("Öğrencinin bu tarihlerle çakışan bir yerleştirmesi zaten var")
        tur = yerlestirme_turu_tahmini(db, fark.ogrenci_id, v.get("belge"))
        vals = {"ogrenci_id": fark.ogrenci_id, "tur": tur, "baslangic": giris.isoformat(),
                "sigorta_giris_bildirildi": 1, "sigorta_giris_bildirim_tarihi": giris.isoformat()}
        if cikis:
            vals.update({"bitis": cikis.isoformat(), "durum": "Sona Erdi", "sigorta_cikis_bildirildi": 1,
                         "sigorta_cikis_bildirim_tarihi": cikis.isoformat()})
        db.insert("yerlestirmeler", vals)
        return (f"{fark.ogrenci}: {tur} kaydı {_tarih_metni(giris)}"
                + (f" - {_tarih_metni(cikis)}" if cikis else "") + " tarihleriyle oluşturuldu")
    raise ValueError("Bu bulgu için otomatik düzeltme yok")


def excel_yaz(sonuc: KarsilastirmaSonucu, yol: Path | str) -> Path:
    from .excel_io import ExcelYazici
    x = ExcelYazici()
    x.sayfa("SGK Karşılaştırma", ["Seviye", "Bulgu", "Öğrenci", "T.C.", "Okul kaydı", "SGK listesi", "Öneri",
                                  "Olası ceza (TL)"],
            [[f.seviye, f.tur, f.ogrenci, f.tc, f.okul, f.sgk, f.oneri, f.tahmini_ceza or ""] for f in sonuc.farklar],
            baslik=f"Okul Kayıtları - SGK Listesi Karşılaştırması ({sonuc.ay:02d}/{sonuc.yil})",
            alt_bilgi=[sonuc.ozet(), *sonuc.notlar])
    return x.kaydet(yol)
