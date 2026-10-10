"""Sunucu ile istemcinin ortak parçaları: değer kodlama, satır nesnesi, sertifika, parola, ayarlar."""
from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import os
import secrets
import socket
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from .. import config

VARSAYILAN_PORT = 47400
KESIF_PORTU = 47401
URUN = config.AD
URUN_ADLARI = (config.AD, config.ESKI_AD)  # ağ tanıtıcısı; eski ad da tanınır
KESIF_ISTEGI = b"MESKOORD-KESIF-1"
KESIF_ISTEKLERI = (KESIF_ISTEGI, b"KOORDMES-KESIF-1")
PROTOKOL = 1
AZAMI_ISTEK = 64 * 1024 * 1024
UZUN_BEKLEME_SN = 25

KIP_TEK, KIP_SUNUCU, KIP_ISTEMCI = "tek", "sunucu", "istemci"


# ---------------------------------------------------------------- değerler

def deger_kodla(v: Any) -> Any:
    if v is None or isinstance(v, (str, int, float)) and not isinstance(v, bool):
        return v
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"b": base64.b64encode(bytes(v)).decode("ascii")}
    if isinstance(v, datetime):
        return v.isoformat(" ")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return str(v)


def deger_coz(v: Any) -> Any:
    if isinstance(v, dict) and "b" in v:
        return base64.b64decode(v["b"])
    return v


def parametre_kodla(p: Any) -> Any:
    if p is None:
        return []
    if isinstance(p, dict):
        return {"d": {k: deger_kodla(v) for k, v in p.items()}}
    return [deger_kodla(v) for v in p]


def parametre_coz(p: Any) -> Any:
    if isinstance(p, dict) and "d" in p:
        return {k: deger_coz(v) for k, v in p["d"].items()}
    return [deger_coz(v) for v in (p or [])]


class Satir:
    """sqlite3.Row gibi davranır: sıra numarası ve (büyük/küçük harf duyarsız) sütun adıyla erişim, keys()."""
    __slots__ = ("_sutunlar", "_degerler", "_dizin")

    def __init__(self, sutunlar: tuple[str, ...], dizin: dict[str, int], degerler: tuple):
        self._sutunlar, self._dizin, self._degerler = sutunlar, dizin, degerler

    def __getitem__(self, k):
        if isinstance(k, str):
            try:
                return self._degerler[self._dizin[k.lower()]]
            except KeyError:
                raise IndexError("No item with that key") from None
        return self._degerler[k]

    def keys(self) -> list[str]:
        return list(self._sutunlar)

    def __iter__(self):
        return iter(self._degerler)

    def __len__(self) -> int:
        return len(self._degerler)

    def __eq__(self, o) -> bool:
        return isinstance(o, Satir) and o._sutunlar == self._sutunlar and o._degerler == self._degerler

    def __hash__(self) -> int:
        return hash((self._sutunlar, self._degerler))

    def __repr__(self) -> str:
        return f"Satir({dict(zip(self._sutunlar, self._degerler))!r})"


def satirlar(sutunlar: list[str] | None, degerler: list[list[Any]]) -> list[Satir]:
    if not sutunlar:
        return []
    s = tuple(sutunlar)
    dizin: dict[str, int] = {}
    for i, ad in enumerate(s):
        dizin.setdefault(ad.lower(), i)
    return [Satir(s, dizin, tuple(deger_coz(v) for v in r)) for r in degerler]


HATA_TURLERI = {"IntegrityError": sqlite3.IntegrityError, "OperationalError": sqlite3.OperationalError,
                "ProgrammingError": sqlite3.ProgrammingError, "DataError": sqlite3.DataError,
                "NotSupportedError": sqlite3.NotSupportedError}


def hata_kodla(e: BaseException) -> dict:
    return {"tur": type(e).__name__, "mesaj": str(e)}


def hata_coz(h: dict) -> Exception:
    return HATA_TURLERI.get(h.get("tur"), sqlite3.DatabaseError)(h.get("mesaj", "Veritabanı hatası"))


def json_baytlari(veri: Any) -> bytes:
    return json.dumps(veri, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# ---------------------------------------------------------------- parola

def parola_ozeti(parola: str, tuz: bytes | None = None) -> str:
    tuz = tuz or secrets.token_bytes(16)
    ozet = hashlib.scrypt(parola.encode("utf-8"), salt=tuz, n=2 ** 14, r=8, p=1, dklen=32)
    return base64.b64encode(tuz).decode() + "$" + base64.b64encode(ozet).decode()


def parola_dogru(parola: str, kayit: str) -> bool:
    try:
        tuz_b64, ozet_b64 = kayit.split("$", 1)
        tuz = base64.b64decode(tuz_b64)
    except ValueError:
        return False
    return hmac.compare_digest(parola_ozeti(parola, tuz), kayit)


def _dpapi(veri: bytes, coz: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    giris = BLOB(len(veri), ctypes.cast(ctypes.create_string_buffer(veri, len(veri)), ctypes.POINTER(ctypes.c_char)))
    cikis = BLOB()
    fn = ctypes.windll.crypt32.CryptUnprotectData if coz else ctypes.windll.crypt32.CryptProtectData
    if not fn(ctypes.byref(giris), None, None, None, None, 0, ctypes.byref(cikis)):
        raise OSError("Windows veri koruması başarısız")
    try:
        return ctypes.string_at(cikis.pbData, cikis.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(cikis.pbData)


def gizle(metin: str) -> str:
    """İstemcinin hatırladığı parolayı Windows kullanıcı hesabına bağlı olarak şifreler (DPAPI)."""
    if not metin:
        return ""
    if os.name == "nt":
        return "dpapi:" + base64.b64encode(_dpapi(metin.encode("utf-8"), False)).decode()
    return "b64:" + base64.b64encode(metin.encode("utf-8")).decode()


def ac(kayit: str) -> str:
    if not kayit:
        return ""
    tur, _, govde = kayit.partition(":")
    try:
        if tur == "dpapi":
            return _dpapi(base64.b64decode(govde), True).decode("utf-8")
        if tur == "b64":
            return base64.b64decode(govde).decode("utf-8")
    except (OSError, ValueError):
        return ""
    return ""


# ---------------------------------------------------------------- sertifika

def sertifika_klasoru() -> Path:
    p = config.data_dir() / "Sunucu"
    p.mkdir(parents=True, exist_ok=True)
    return p


def sertifika_hazirla(klasor: Path | None = None) -> tuple[Path, Path]:
    """Sunucunun kendinden imzalı TLS sertifikası (ilk çalıştırmada üretilir, sonra hep aynı kalır)."""
    klasor = klasor or sertifika_klasoru()
    crt, key = klasor / "sunucu.crt", klasor / "sunucu.key"
    if crt.exists() and key.exists():
        return crt, key
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    anahtar = ec.generate_private_key(ec.SECP256R1())
    ad = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"{URUN} Sunucu {socket.gethostname()}"[:64]),
                    x509.NameAttribute(NameOID.ORGANIZATION_NAME, URUN)])
    simdi = datetime.utcnow() - timedelta(days=1)
    sert = (x509.CertificateBuilder().subject_name(ad).issuer_name(ad).public_key(anahtar.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(simdi)
            .not_valid_after(simdi + timedelta(days=365 * 25))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(socket.gethostname() or "meskoord")]),
                           critical=False)
            .sign(anahtar, hashes.SHA256()))
    key.write_bytes(anahtar.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                          serialization.NoEncryption()))
    crt.write_bytes(sert.public_bytes(serialization.Encoding.PEM))
    return crt, key


def parmak_izi(der: bytes) -> str:
    return hashlib.sha256(der).hexdigest()


def sertifika_parmak_izi(crt: Path) -> str:
    import ssl
    return parmak_izi(ssl.PEM_cert_to_DER_cert(crt.read_text("ascii")))


def dogrulama_kodu(iz: str) -> str:
    """Kullanıcıya gösterilen kısa doğrulama kodu (sunucu ve istemci ekranında aynı olmalı)."""
    return "-".join(iz[i:i + 4].upper() for i in range(0, 16, 4))


# ---------------------------------------------------------------- ayarlar

def varsayilan_kullanici() -> str:
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return "kullanıcı"


@dataclass
class AgAyarlari:
    kip: str = KIP_TEK
    # sunucu
    sunucu_adi: str = field(default_factory=lambda: socket.gethostname())
    port: int = VARSAYILAN_PORT
    parola_ozeti: str = ""
    # istemci
    adres: str = ""
    sunucu_portu: int = VARSAYILAN_PORT
    parmak_izi: str = ""
    kullanici: str = field(default_factory=varsayilan_kullanici)
    parola_gizli: str = ""
    hesap: bool = False          # sunucuda kişisel hesaplar açık: kullanici = kullanıcı adı, parola saklanmaz
    # sunucu bilgisayarı
    tepside_calis: bool = True   # pencere kapatılınca sunucu sistem tepsisinde çalışmayı sürdürür

    @staticmethod
    def yol() -> Path:
        return config.data_dir() / "ag_ayarlari.json"

    @classmethod
    def yukle(cls) -> "AgAyarlari":
        try:
            veri = json.loads(cls.yol().read_text("utf-8"))
        except (OSError, ValueError):
            return cls()
        bilinen = {k: v for k, v in veri.items() if k in cls.__dataclass_fields__}
        return cls(**bilinen)

    def kaydet(self) -> None:
        self.yol().write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @property
    def parola(self) -> str:
        return ac(self.parola_gizli)

    @parola.setter
    def parola(self, deger: str) -> None:
        self.parola_gizli = gizle(deger)


def yerel_adresler() -> list[str]:
    adresler = set()
    try:
        for bilgi in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            adresler.add(bilgi[4][0])
    except OSError:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        adresler.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    return sorted(a for a in adresler if not a.startswith("127."))
