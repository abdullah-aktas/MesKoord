"""Çıktıları e-posta ve WhatsApp ile paylaşma.

E-posta üç yoldan gider:
- Bilgisayardaki posta programı (Outlook, Thunderbird...): dosya ekli yeni ileti açılır, kullanıcı gönderir.
- Programdan doğrudan (SMTP): sunucu ve kullanıcı adı bu bilgisayarda saklanır, şifre her oturumda sorulur
  ve diske yazılmaz. Toplu gönderim bu yolu kullanır.
- İkisi de yoksa: tarayıcıdaki posta sayfası konu ve metinle açılır, dosya panoya kopyalanır.

WhatsApp masaüstü programların dosyayı kendiliğinden göndermesine izin vermez. Dosya panoya kopyalanır,
WhatsApp (yüklü değilse WhatsApp Web) seçilen kişinin sohbetiyle açılır; kullanıcı Ctrl+V ile yapıştırır.
"""
from __future__ import annotations

import json
import mimetypes
import re
import smtplib
import ssl
import sys
from dataclasses import asdict, dataclass, field
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from .. import config

BUYUK_EK_MB = 20


class PaylasimHatasi(RuntimeError):
    pass


@dataclass
class Kisi:
    ad: str
    rol: str
    eposta: str = ""
    telefon: str = ""
    anahtar: str = ""

    @property
    def etiket(self) -> str:
        ek = " · ".join(x for x in (self.eposta, self.telefon) if x)
        return f"{self.ad} ({self.rol})" + (f" — {ek}" if ek else "")


def eposta_gecerli(s: str | None) -> bool:
    return bool(re.fullmatch(r"[^@\s,;<>]+@[^@\s,;<>]+\.[A-Za-z]{2,}", (s or "").strip()))


def whatsapp_no(tel: str | None) -> str:
    """Türkiye numarasını uluslararası biçime çevirir: 0532 123 45 67 → 905321234567. Tanınmazsa ''."""
    rakam = re.sub(r"\D", "", tel or "")
    if rakam.startswith("00"):
        rakam = rakam[2:]
    if len(rakam) == 11 and rakam.startswith("0"):
        rakam = "90" + rakam[1:]
    elif len(rakam) == 10 and rakam.startswith("5"):
        rakam = "90" + rakam
    return rakam if 11 <= len(rakam) <= 15 and not rakam.startswith("0") else ""


def whatsapp_adresleri(no: str, metin: str) -> tuple[str, str]:
    """(WhatsApp masaüstü adresi, WhatsApp Web adresi)."""
    parca = [f"phone={no}"] if no else []
    if metin:
        parca.append("text=" + quote(metin))
    sorgu = "&".join(parca)
    return f"whatsapp://send?{sorgu}", f"https://web.whatsapp.com/send?{sorgu}"


def mailto_adresi(alicilar: list[str], konu: str, metin: str) -> str:
    return f"mailto:{quote(','.join(alicilar), safe='@,')}?subject={quote(konu)}&body={quote(metin)}"


def gmail_adresi(alicilar: list[str], konu: str, metin: str) -> str:
    return (f"https://mail.google.com/mail/?view=cm&fs=1&to={quote(','.join(alicilar), safe='@,')}"
            f"&su={quote(konu)}&body={quote(metin)}")


def kisiler(db) -> list[Kisi]:
    """E-posta veya telefonu kayıtlı öğretmen, işletme yetkilisi, usta öğretici, veli ve öğrenciler."""
    out: list[Kisi] = []
    for r in db.q("SELECT id, ad, soyad, eposta, telefon FROM ogretmenler WHERE aktif = 1 ORDER BY ad, soyad"):
        out.append(Kisi(f"{r['ad']} {r['soyad']}", "Öğretmen", r["eposta"] or "", r["telefon"] or "",
                        f"ogretmen:{r['id']}"))
    for r in db.q("SELECT id, ad, yetkili, eposta, telefon, usta_ogretici, usta_ogretici_tel FROM isletmeler "
                  "WHERE aktif = 1 ORDER BY ad"):
        ad = f"{r['yetkili']} - {r['ad']}" if r["yetkili"] else r["ad"]
        out.append(Kisi(ad, "İşletme", r["eposta"] or "", r["telefon"] or "", f"isletme:{r['id']}"))
        if r["usta_ogretici"] and r["usta_ogretici_tel"]:
            out.append(Kisi(f"{r['usta_ogretici']} - {r['ad']}", "Usta öğretici", "", r["usta_ogretici_tel"],
                            f"usta:{r['id']}"))
    for r in db.q("""SELECT o.id, o.ad, o.soyad, o.veli_ad, o.veli_tel, o.telefon, s.ad sinif FROM ogrenciler o
                     LEFT JOIN siniflar s ON s.id = o.sinif_id WHERE o.aktif = 1 ORDER BY s.ad, o.ad, o.soyad"""):
        ogr = f"{r['ad']} {r['soyad']}" + (f" ({r['sinif']})" if r["sinif"] else "")
        if r["veli_tel"]:
            out.append(Kisi(f"{r['veli_ad'] or 'Veli'} - {ogr}", "Veli", "", r["veli_tel"], f"veli:{r['id']}"))
        if r["telefon"]:
            out.append(Kisi(ogr, "Öğrenci", "", r["telefon"], f"ogrenci:{r['id']}"))
    return [k for k in out if eposta_gecerli(k.eposta) or whatsapp_no(k.telefon)]


def toplam_mb(dosyalar: list[Path]) -> float:
    return sum(Path(d).stat().st_size for d in dosyalar if Path(d).is_file()) / 1e6


def varsayilan_metin(db, dosyalar: list[Path]) -> tuple[str, str]:
    k = db.kurum() if db is not None else None
    kurum = (k["ad"] if k else "") or ""
    adlar = ", ".join(Path(d).name for d in dosyalar)
    konu = f"{kurum} - {Path(dosyalar[0]).stem}" if kurum and len(dosyalar) == 1 else (kurum or "MesKoord") + " belgeleri"
    metin = f"Merhaba,\n\nEkte {adlar} gönderilmiştir.\n\nSaygılarımızla,\n{kurum}".rstrip()
    return konu, metin


# ------------------------------------------------------------------ posta programı (Simple MAPI)

def varsayilan_posta_programi() -> str:
    """Windows'ta tanımlı varsayılan posta programının adı (Outlook, Thunderbird...). Yoksa ''."""
    if sys.platform != "win32":
        return ""
    import winreg
    for kok in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(kok, r"SOFTWARE\Clients\Mail") as k:
                ad = winreg.QueryValueEx(k, "")[0]
                if ad and "windows mail" not in ad.lower():
                    return ad
        except OSError:
            continue
    return ""


MAPI_HATALARI = {1: "kullanıcı iletiyi kapattı", 2: "posta programı iletiyi açamadı", 3: "posta programında oturum açılamadı",
                 11: "ek dosya bulunamadı", 15: "dosya eklenemedi", 25: "alıcı adresi tanınmadı"}


def posta_programiyla_ac(dosyalar: list[Path], alicilar: list[str], konu: str, metin: str) -> None:
    """Varsayılan posta programında dosya ekli yeni ileti açar. İleti penceresi kapanana kadar bekler;
    arayüz donmasın diye arka planda çağrılır."""
    if sys.platform != "win32":
        raise PaylasimHatasi("posta programıyla gönderme yalnızca Windows'ta çalışır")
    import ctypes
    from ctypes import POINTER, Structure, c_ulong, c_void_p, c_wchar_p

    class Alici(Structure):
        _fields_ = [("ulReserved", c_ulong), ("ulRecipClass", c_ulong), ("lpszName", c_wchar_p),
                    ("lpszAddress", c_wchar_p), ("ulEIDSize", c_ulong), ("lpEntryID", c_void_p)]

    class Dosya(Structure):
        _fields_ = [("ulReserved", c_ulong), ("flFlags", c_ulong), ("nPosition", c_ulong),
                    ("lpszPathName", c_wchar_p), ("lpszFileName", c_wchar_p), ("lpFileType", c_void_p)]

    class Ileti(Structure):
        _fields_ = [("ulReserved", c_ulong), ("lpszSubject", c_wchar_p), ("lpszNoteText", c_wchar_p),
                    ("lpszMessageType", c_wchar_p), ("lpszDateReceived", c_wchar_p),
                    ("lpszConversationID", c_wchar_p), ("flFlags", c_ulong), ("lpOriginator", POINTER(Alici)),
                    ("nRecipCount", c_ulong), ("lpRecips", POINTER(Alici)), ("nFileCount", c_ulong),
                    ("lpFiles", POINTER(Dosya))]

    try:
        mapi = ctypes.WinDLL("mapi32.dll")
        gonder = mapi.MAPISendMailW
    except (OSError, AttributeError) as e:
        raise PaylasimHatasi("bilgisayarda posta programı bağlantısı (MAPI) yok") from e
    gonder.restype = c_ulong
    gonder.argtypes = [ctypes.c_size_t, ctypes.c_size_t, POINTER(Ileti), c_ulong, c_ulong]
    a_dizi = (Alici * max(1, len(alicilar)))()
    for i, a in enumerate(alicilar):
        a_dizi[i] = Alici(0, 1, a, f"SMTP:{a}", 0, None)
    d_dizi = (Dosya * max(1, len(dosyalar)))()
    for i, d in enumerate(dosyalar):
        d_dizi[i] = Dosya(0, 0, 0xFFFFFFFF, str(Path(d).resolve()), Path(d).name, None)
    ileti = Ileti(0, konu, metin, None, None, None, 0, None, len(alicilar), a_dizi if alicilar else None,
                  len(dosyalar), d_dizi if dosyalar else None)
    kod = gonder(0, 0, ctypes.byref(ileti), 0x1 | 0x8, 0)  # MAPI_LOGON_UI | MAPI_DIALOG
    if kod not in (0, 1):
        raise PaylasimHatasi(MAPI_HATALARI.get(kod, f"posta programı hata kodu {kod}"))


# ------------------------------------------------------------------ programdan doğrudan gönderim (SMTP)

HAZIR_SUNUCULAR = {
    "Gmail": ("smtp.gmail.com", 587, "STARTTLS"),
    "Outlook / Hotmail / Office 365": ("smtp.office365.com", 587, "STARTTLS"),
    "Yandex": ("smtp.yandex.com", 465, "SSL"),
}


@dataclass
class PostaAyarlari:
    sunucu: str = ""
    port: int = 587
    guvenlik: str = "STARTTLS"  # STARTTLS | SSL
    kullanici: str = ""
    gonderen_ad: str = ""

    @staticmethod
    def yol() -> Path:
        return config.data_dir() / "posta_ayarlari.json"

    @classmethod
    def yukle(cls) -> "PostaAyarlari":
        try:
            veri = json.loads(cls.yol().read_text("utf-8"))
        except (OSError, ValueError):
            return cls()
        return cls(**{k: v for k, v in veri.items() if k in cls.__dataclass_fields__})

    def kaydet(self) -> None:
        self.yol().write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def hazir(self) -> bool:
        return bool(self.sunucu and self.port and eposta_gecerli(self.kullanici))


def ileti(ayar: PostaAyarlari, alicilar: list[str], konu: str, metin: str, dosyalar: list[Path]) -> EmailMessage:
    m = EmailMessage()
    m["From"] = formataddr((ayar.gonderen_ad, ayar.kullanici)) if ayar.gonderen_ad else ayar.kullanici
    m["To"] = ", ".join(alicilar)
    m["Subject"] = konu
    m.set_content(metin)
    for d in dosyalar:
        d = Path(d)
        tur, _ = mimetypes.guess_type(d.name)
        ana, alt = (tur or "application/octet-stream").split("/", 1)
        m.add_attachment(d.read_bytes(), maintype=ana, subtype=alt, filename=d.name)
    return m


@dataclass
class GonderimSonucu:
    gonderilen: list[str] = field(default_factory=list)
    hatalar: list[tuple[str, str]] = field(default_factory=list)


def smtp_gonder(ayar: PostaAyarlari, parola: str, iletiler: list[EmailMessage],
                ilerleme: Callable[[int, int], None] | None = None, zaman_asimi: int = 30) -> GonderimSonucu:
    """İletileri tek oturumda gönderir. Şifre yalnızca bu çağrıda kullanılır, saklanmaz."""
    if not ayar.hazir:
        raise PaylasimHatasi("posta ayarları eksik: sunucu, port ve gönderen e-posta adresi gerekli")
    baglam = ssl.create_default_context()
    try:
        if ayar.guvenlik == "SSL":
            s = smtplib.SMTP_SSL(ayar.sunucu, ayar.port, timeout=zaman_asimi, context=baglam)
        else:
            s = smtplib.SMTP(ayar.sunucu, ayar.port, timeout=zaman_asimi)
            s.starttls(context=baglam)
        s.login(ayar.kullanici, parola)
    except smtplib.SMTPAuthenticationError as e:
        raise PaylasimHatasi("e-posta kullanıcı adı veya şifre kabul edilmedi. Gmail için hesap şifresi değil, "
                             "Google hesabında oluşturulan 'uygulama şifresi' kullanılır.") from e
    except (OSError, smtplib.SMTPException) as e:
        raise PaylasimHatasi(f"posta sunucusuna bağlanılamadı: {e}") from e
    sonuc = GonderimSonucu()
    try:
        for i, m in enumerate(iletiler):
            kime = m["To"]
            try:
                s.send_message(m)
                sonuc.gonderilen.append(kime)
            except smtplib.SMTPException as e:
                sonuc.hatalar.append((kime, str(e)))
            if ilerleme:
                ilerleme(i + 1, len(iletiler))
    finally:
        try:
            s.quit()
        except smtplib.SMTPException:
            pass
    return sonuc
