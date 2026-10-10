"""Kurum lisansı: imzalı lisans dosyasının doğrulanması, deneme süresi ve lisans talebi.

Lisans, okul/kurumun MEB kurum koduna verilir ve o kurumdaki bütün bilgisayarlarda kullanılabilir.
Lisans dosyası döner sermaye işletmesindeki Lisans Yöneticisi ile Ed25519 özel anahtarıyla imzalanır;
program yalnızca aşağıdaki açık anahtarlarla imzayı doğrular. Lisanslı kurumun adı ve kodu
Ayarlar'a kilitlenir ve üretilen bütün resmî belgelere bu bilgiler yazılır.
"""
from __future__ import annotations

import base64
import json
import os
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from . import APP_NAME, __version__, config

URUN = APP_NAME
ESKI_URUNLER = (config.ESKI_AD,)  # 1.3.0 öncesi verilen lisanslar geçerliliğini korur
DOSYA_ADI = "lisans.lic"
KOD_ONEKI = "KMLIS1."
DENEME_GUN = 30
TOLERANS_GUN = 30
TARIH_SAPMA_GUN = 3

# Anahtar kimliği -> Ed25519 açık anahtarı (base64). Yeni anahtar eklenince eskisi silinmez;
# silinirse o anahtarla verilmiş bütün lisanslar geçersiz olur.
ACIK_ANAHTARLAR: dict[str, str] = {
    "KM1": "xqZtL2EZkMO7KzbuXM4gyaW4MG/8hlWLElLsz1XD7Xw=",
}

# Lisans penceresinde ve talep metninde görünen satıcı bilgileri; paket hazırlanmadan önce doldurulur.
SATICI = {
    "ad": "Derik Mesleki ve Teknik Anadolu Lisesi Döner Sermaye İşletmesi",
    "telefon": "",
    "eposta": "",
    "web": "",
}

ZORUNLU_ALANLAR = ("urun", "lisans_no", "kurum_kodu", "kurum_adi", "baslangic", "anahtar", "imza")

LISANSLI, TOLERANS, DENEME, KAPALI = "lisansli", "tolerans", "deneme", "kapali"

AYAR_DENEME = "lisans_deneme_baslangic"
AYAR_SON_GORULME = "lisans_son_gorulme"
ISARET_DOSYASI = ".meskoord_kurulum"
ESKI_ISARET_DOSYASI = ".koordmes_kurulum"


class LisansHatasi(ValueError):
    pass


def _tarih(s: str, alan: str) -> date:
    try:
        return date.fromisoformat(str(s).strip())
    except ValueError:
        raise LisansHatasi(f"Lisans dosyasındaki '{alan}' tarihi geçersiz: {s!r}") from None


@dataclass(frozen=True)
class Lisans:
    veri: dict
    kaynak: Path | None = None

    @property
    def lisans_no(self) -> str:
        return self.veri["lisans_no"]

    @property
    def kurum_kodu(self) -> str:
        return str(self.veri["kurum_kodu"]).strip()

    @property
    def kurum_adi(self) -> str:
        return self.veri["kurum_adi"].strip()

    @property
    def baslangic(self) -> date:
        return _tarih(self.veri["baslangic"], "baslangic")

    @property
    def bitis(self) -> date | None:
        b = str(self.veri.get("bitis") or "").strip()
        return _tarih(b, "bitis") if b else None

    @property
    def sure_metni(self) -> str:
        b = self.bitis
        return f"{self.baslangic:%d.%m.%Y} - {b:%d.%m.%Y}" if b else f"{self.baslangic:%d.%m.%Y} - süresiz"

    def ozet(self) -> str:
        satirlar = [f"Lisans No: {self.lisans_no}", f"Kurum: {self.kurum_adi} ({self.kurum_kodu})"]
        yer = " / ".join(x for x in (self.veri.get("il", ""), self.veri.get("ilce", "")) if x)
        if yer:
            satirlar.append(f"İl / İlçe: {yer}")
        satirlar.append(f"Geçerlilik: {self.sure_metni}")
        if self.veri.get("kapsam"):
            satirlar.append(f"Kapsam: {self.veri['kapsam']}")
        if self.veri.get("duzenleyen"):
            satirlar.append(f"Düzenleyen: {self.veri['duzenleyen']}")
        return "\n".join(satirlar)


# ---------------------------------------------------------------------- imza

def kanonik(veri: dict) -> bytes:
    d = {k: v for k, v in veri.items() if k != "imza"}
    return json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def imzala(veri: dict, ozel_anahtar, anahtar_kimligi: str) -> dict:
    """Lisans Yöneticisi ve testler kullanır; programın kendisi imzalamaz."""
    d = {k: v for k, v in veri.items() if k != "imza"}
    d["urun"] = URUN
    d["anahtar"] = anahtar_kimligi
    d["imza"] = base64.b64encode(ozel_anahtar.sign(kanonik(d))).decode("ascii")
    return d


def dogrula(veri: dict, kaynak: Path | None = None) -> Lisans:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if not isinstance(veri, dict):
        raise LisansHatasi("Lisans içeriği okunamadı.")
    eksik = [a for a in ZORUNLU_ALANLAR if not str(veri.get(a) or "").strip()]
    if eksik:
        raise LisansHatasi("Lisans dosyası eksik: " + ", ".join(eksik))
    if veri["urun"] not in (URUN, *ESKI_URUNLER):
        raise LisansHatasi(f"Bu lisans {veri['urun']} ürününe ait.")
    acik = ACIK_ANAHTARLAR.get(veri["anahtar"])
    if not acik:
        raise LisansHatasi("Lisans tanınmayan bir anahtarla imzalanmış. Programın güncel sürümünü kurun "
                           "veya lisansı veren birimle görüşün.")
    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode(acik)).verify(base64.b64decode(veri["imza"]),
                                                                          kanonik(veri))
    except (InvalidSignature, ValueError):
        raise LisansHatasi("Lisans imzası geçersiz: dosya değiştirilmiş veya sahte.") from None
    lis = Lisans(veri, kaynak)
    lis.baslangic, lis.bitis  # tarihler okunabilir olmalı
    return lis


# ---------------------------------------------------------------------- dosya ve kod

def kodla(veri: dict) -> str:
    """E-postayla gönderilebilen tek satırlık lisans kodu."""
    ham = json.dumps(veri, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return KOD_ONEKI + base64.urlsafe_b64encode(ham).decode("ascii").rstrip("=")


def coz(metin: str) -> dict:
    """Lisans dosyası içeriğini (JSON) veya lisans kodunu çözer."""
    metin = (metin or "").strip().lstrip("\ufeff")
    if not metin:
        raise LisansHatasi("Lisans metni boş.")
    if metin.startswith("{"):
        try:
            return json.loads(metin)
        except json.JSONDecodeError:
            raise LisansHatasi("Lisans dosyası bozuk.") from None
    kod = "".join(metin.split())
    i = kod.find(KOD_ONEKI)
    if i < 0:
        raise LisansHatasi(f"Lisans kodu '{KOD_ONEKI}' ile başlamalıdır.")
    govde = kod[i + len(KOD_ONEKI):]
    try:
        return json.loads(base64.urlsafe_b64decode(govde + "=" * (-len(govde) % 4)).decode("utf-8"))
    except ValueError:
        raise LisansHatasi("Lisans kodu eksik veya hatalı kopyalanmış.") from None


def dosya_metni(veri: dict) -> str:
    return json.dumps(veri, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def oku(yol: Path) -> Lisans:
    try:
        metin = Path(yol).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        raise LisansHatasi(f"Lisans dosyası okunamadı: {e}") from None
    return dogrula(coz(metin), Path(yol))


def program_klasoru() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def ortak_klasor() -> Path:
    return Path(os.environ.get("PROGRAMDATA") or r"C:\ProgramData") / APP_NAME


def arama_yollari() -> list[Path]:
    """Kullanıcının yüklediği lisans, kurulumla bilgisayara konan lisanslar (kurulum dosyasının yanındaki
    bütün .lic dosyaları ProgramData'ya kopyalanır; eski ProgramData\\KoordMES de okunur) ve program
    klasöründeki lisanslar."""
    yollar = [config.data_dir() / DOSYA_ADI]
    ortak = ortak_klasor()
    for klasor in (ortak, ortak.with_name(config.ESKI_AD), program_klasoru()):
        if klasor.is_dir():
            yollar.extend(sorted(klasor.glob("*.lic")))
    return yollar


# Ağdaki sunucudan gelen lisans metinleri (istemci bilgisayarda diske yazılmaz; imzası burada doğrulanır)
SUNUCU_LISANSLARI: list[str] = []


def lisans_metinleri() -> list[str]:
    """Bu bilgisayarda bulunan geçerli lisansların metinleri (sunucu istemcilere bunları gönderir)."""
    out = []
    for yol in dict.fromkeys(arama_yollari()):
        if yol.is_file():
            try:
                out.append(dosya_metni(oku(yol).veri))
            except LisansHatasi:
                pass
    return out


def bul() -> tuple[Lisans | None, list[str]]:
    """Geçerli imzalı lisanslardan bitişi en geç olanı döndürür."""
    bulunan: list[Lisans] = []
    hatalar: list[str] = []
    for yol in dict.fromkeys(arama_yollari()):
        if yol.is_file():
            try:
                bulunan.append(oku(yol))
            except LisansHatasi as e:
                hatalar.append(f"{yol}: {e}")
    for metin in SUNUCU_LISANSLARI:
        try:
            bulunan.append(dogrula(coz(metin)))
        except LisansHatasi as e:
            hatalar.append(f"sunucu lisansı: {e}")
    if not bulunan:
        return None, hatalar
    return max(bulunan, key=lambda l: (l.bitis is None, l.bitis or date.min, l.baslangic)), hatalar


def kaydet(kaynak: str | Path) -> Lisans:
    """Lisansı (dosya yolu ya da lisans kodu/metni) doğrular ve kullanıcının veri klasörüne kopyalar."""
    lis = oku(kaynak) if isinstance(kaynak, Path) else dogrula(coz(kaynak))
    hedef = config.data_dir() / DOSYA_ADI
    hedef.write_text(dosya_metni(lis.veri), encoding="utf-8")
    return Lisans(lis.veri, hedef)


# ---------------------------------------------------------------------- durum

@dataclass(frozen=True)
class Durum:
    seviye: str
    lisans: Lisans | None
    kalan_gun: int | None
    mesaj: str
    tarih_uyarisi: str = ""

    @property
    def calisir(self) -> bool:
        return self.seviye != KAPALI

    @property
    def pencere_eki(self) -> str:
        if self.seviye == LISANSLI:
            return f"Lisanslı: {self.lisans.kurum_adi}"
        if self.seviye == TOLERANS:
            return f"Lisans süresi doldu - {self.kalan_gun} gün içinde yenileyin"
        if self.seviye == DENEME:
            return f"Deneme sürümü - {self.kalan_gun} gün kaldı"
        return "Lisanssız"


def _isaret_tarihi() -> date | None:
    tarihler = []
    for ad in (ISARET_DOSYASI, ESKI_ISARET_DOSYASI):
        try:
            tarihler.append(date.fromisoformat((config.data_dir() / ad).read_text(encoding="ascii").strip()))
        except (OSError, ValueError):
            pass
    return min(tarihler, default=None)


def etkin_tarih(db, bugun: date | None = None) -> tuple[date, str]:
    """Bilgisayarın tarihi geri alınarak süre uzatılamasın diye en son görülen tarihi esas alır."""
    bugun = bugun or date.today()
    try:
        son = date.fromisoformat(str(db.ayar(AYAR_SON_GORULME) or ""))
    except ValueError:
        son = None
    if son and bugun < son - timedelta(days=TARIH_SAPMA_GUN):
        return son, (f"Bilgisayarın tarihi ({bugun:%d.%m.%Y}) programın en son çalıştığı tarihten "
                     f"({son:%d.%m.%Y}) önce görünüyor. Lisans hesabında {son:%d.%m.%Y} esas alındı; "
                     "Windows tarih ve saatini düzeltin.")
    if son is None or bugun > son:
        _ayar_yazmayi_dene(db, AYAR_SON_GORULME, bugun.isoformat())
    return max(bugun, son or bugun), ""


def _ayar_yazmayi_dene(db, anahtar: str, deger: str) -> None:
    """Ayar yazma yetkisi olmayan hesapta (personel, salt okunur) lisans denetimi yine çalışsın."""
    try:
        db.ayar_yaz(anahtar, deger)
    except sqlite3.DatabaseError:
        pass


def deneme_baslangici(db, bugun: date) -> date:
    adaylar = [bugun]
    try:
        adaylar.append(date.fromisoformat(str(db.ayar(AYAR_DENEME) or "")))
    except ValueError:
        pass
    if (d := _isaret_tarihi()) is not None:
        adaylar.append(d)
    bas = min(adaylar)
    if str(db.ayar(AYAR_DENEME) or "") != bas.isoformat():
        _ayar_yazmayi_dene(db, AYAR_DENEME, bas.isoformat())
    if _isaret_tarihi() != bas:
        try:
            (config.data_dir() / ISARET_DOSYASI).write_text(bas.isoformat(), encoding="ascii")
        except OSError:
            pass
    return bas


def durum(db, bugun: date | None = None) -> Durum:
    gun, uyari = etkin_tarih(db, bugun)
    lis, hatalar = bul()
    if lis is not None:
        if gun < lis.baslangic:
            lis_mesaj = f"Lisans {lis.baslangic:%d.%m.%Y} tarihinde başlayacak."
        elif lis.bitis is None or gun <= lis.bitis:
            kalan = (lis.bitis - gun).days if lis.bitis else None
            return Durum(LISANSLI, lis, kalan, f"{lis.kurum_adi} adına lisanslıdır ({lis.sure_metni}).", uyari)
        elif gun <= lis.bitis + timedelta(days=TOLERANS_GUN):
            kalan = (lis.bitis + timedelta(days=TOLERANS_GUN) - gun).days
            return Durum(TOLERANS, lis, kalan,
                         f"Lisans süresi {lis.bitis:%d.%m.%Y} tarihinde doldu. Program {kalan} gün daha "
                         "çalışacak; lisansınızı yenileyin.", uyari)
        else:
            return Durum(KAPALI, lis, 0, f"Lisans süresi {lis.bitis:%d.%m.%Y} tarihinde doldu. Programı "
                                         "kullanmaya devam etmek için lisansınızı yenileyin.", uyari)
    else:
        lis_mesaj = ("Lisans dosyası geçersiz: " + hatalar[0]) if hatalar else "Lisans yüklenmemiş."
    bas = deneme_baslangici(db, gun)
    kalan = DENEME_GUN - (gun - bas).days
    if kalan > 0:
        return Durum(DENEME, lis, kalan, f"{lis_mesaj} Deneme süresinin bitmesine {kalan} gün var.", uyari)
    return Durum(KAPALI, lis, 0, f"{lis_mesaj} {DENEME_GUN} günlük deneme süresi doldu.", uyari)


def kurum_uygula(db, lis: Lisans | None) -> None:
    """Lisanslı kurumun adını ve kodunu kurum bilgilerine yazar; il ve ilçe boşsa onları da doldurur."""
    if lis is None:
        return
    k = db.kurum()
    d = {"ad": lis.kurum_adi, "kurum_kodu": lis.kurum_kodu}
    for alan in ("il", "ilce"):
        if lis.veri.get(alan) and not (k[alan] or "").strip():
            d[alan] = lis.veri[alan]
    if any((k[a] or "") != v for a, v in d.items()):
        try:
            db.update("kurum", 1, d)
        except sqlite3.DatabaseError:
            pass  # yetkisi olmayan hesap; yönetici girişinde yazılır


def talep_metni(db, iletisim: dict | None = None) -> str:
    k = db.kurum()
    iletisim = iletisim or {}
    satirlar = [
        f"{URUN} LİSANS TALEBİ",
        f"Talep tarihi: {datetime.now():%d.%m.%Y %H:%M}",
        f"Program sürümü: {__version__}",
        f"Kurum kodu: {iletisim.get('kurum_kodu', k['kurum_kodu'] or '')}",
        f"Kurum adı: {iletisim.get('kurum_adi', k['ad'] or '')}",
        f"Kurum türü: {k['tur'] or ''}",
        f"İl: {iletisim.get('il', k['il'] or '')}",
        f"İlçe: {iletisim.get('ilce', k['ilce'] or '')}",
        f"Yetkili: {iletisim.get('yetkili', k['mudur'] or '')}",
        f"Telefon: {iletisim.get('telefon', k['telefon'] or '')}",
        f"E-posta: {iletisim.get('eposta', k['eposta'] or '')}",
    ]
    lis, _ = bul()
    if lis:
        satirlar.append(f"Mevcut lisans: {lis.lisans_no} ({lis.sure_metni})")
    return "\n".join(satirlar) + "\n"


TALEP_ALANLARI = {"kurum kodu": "kurum_kodu", "kurum adı": "kurum_adi", "il": "il", "ilçe": "ilce",
                  "yetkili": "yetkili", "telefon": "telefon", "e-posta": "eposta", "mevcut lisans": "mevcut"}


def talep_coz(metin: str) -> dict[str, str]:
    """Lisans Yöneticisi, kurumdan gelen talep metnini formu doldurmak için okur."""
    d: dict[str, str] = {}
    for satir in (metin or "").splitlines():
        if ":" in satir:
            a, v = satir.split(":", 1)
            k = TALEP_ALANLARI.get(a.strip().replace("İ", "i").replace("I", "ı").lower())
            if k:
                d[k] = v.strip()
    return d
