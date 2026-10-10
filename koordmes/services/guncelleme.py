"""Yeni sürüm denetimi.

Program, `GUNCELLEME_ADRESI`ndeki küçük `surum.json` dosyasını okur. Gönderilen tek bilgi isteğin kendisidir;
kurum, kullanıcı veya veri bilgisi gönderilmez. Yeni sürüm varsa kurulum dosyası indirilir, SHA256 özeti
`surum.json`daki değerle karşılaştırılır ve uyuşursa kurulum başlatılır. Veriler ve lisans kurulumda korunur.

surum.json örneği (araclar/surum_hazirla.py üretir):
    {"surum": "1.4.0", "indir": "https://.../MesKoord_Kurulum_1.4.0.exe", "sha256": "...", "notlar": "..."}
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from .. import GUNCELLEME_ADRESI, __version__, config

IZINLI_SEMALAR = ("https", "file")


class GuncellemeHatasi(RuntimeError):
    pass


def adres() -> str:
    return config.ortam("GUNCELLEME_ADRESI") or GUNCELLEME_ADRESI


def surum_sayisi(s: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", s or "")[:3]) or (0,)


def daha_yeni(aday: str, simdiki: str = __version__) -> bool:
    return surum_sayisi(aday) > surum_sayisi(simdiki)


@dataclass
class YeniSurum:
    surum: str
    indir: str
    sha256: str = ""
    notlar: str = ""


def _ac(url: str, zaman_asimi: float):
    if urlparse(url).scheme not in IZINLI_SEMALAR:
        raise GuncellemeHatasi(f"güvenli olmayan adres: {url}")
    istek = urllib.request.Request(url, headers={"User-Agent": f"MesKoord/{__version__}"})
    return urllib.request.urlopen(istek, timeout=zaman_asimi)  # noqa: S310 - şema yukarıda sınırlandı


def denetle(url: str | None = None, simdiki: str = __version__, zaman_asimi: float = 8) -> YeniSurum | None:
    """Yeni sürüm varsa bilgisini, yoksa None döndürür. Adres tanımlı değilse None."""
    url = url if url is not None else adres()
    if not url:
        return None
    try:
        with _ac(url, zaman_asimi) as y:
            veri = json.loads(y.read(65536).decode("utf-8-sig"))
    except GuncellemeHatasi:
        raise
    except (OSError, ValueError) as e:
        raise GuncellemeHatasi(f"sürüm bilgisi alınamadı: {e}") from e
    surum, indir = str(veri.get("surum") or ""), str(veri.get("indir") or "")
    if not re.fullmatch(r"\d+\.\d+\.\d+", surum) or urlparse(indir).scheme not in IZINLI_SEMALAR:
        raise GuncellemeHatasi("sürüm bilgisi dosyası geçersiz")
    if not daha_yeni(surum, simdiki):
        return None
    return YeniSurum(surum, indir, str(veri.get("sha256") or "").lower(), str(veri.get("notlar") or ""))


def klasor() -> Path:
    p = config.data_dir() / "Guncelleme"
    p.mkdir(parents=True, exist_ok=True)
    return p


def indir(yeni: YeniSurum, hedef_klasor: Path | None = None,
          ilerleme: Callable[[int, int], None] | None = None, zaman_asimi: float = 30) -> Path:
    """Kurulum dosyasını indirir ve SHA256 özetini doğrular. Uyuşmazsa dosya silinir."""
    hedef_klasor = hedef_klasor or klasor()
    ad = Path(urlparse(yeni.indir).path).name or f"MesKoord_Kurulum_{yeni.surum}.exe"
    hedef = hedef_klasor / ad
    gecici = hedef.with_name(hedef.name + ".indiriliyor")
    h = hashlib.sha256()
    try:
        with _ac(yeni.indir, zaman_asimi) as y, gecici.open("wb") as f:
            toplam = int(y.headers.get("Content-Length") or 0) if hasattr(y, "headers") and y.headers else 0
            alinan = 0
            for parca in iter(lambda: y.read(1 << 16), b""):
                f.write(parca)
                h.update(parca)
                alinan += len(parca)
                if ilerleme:
                    ilerleme(alinan, toplam)
    except (OSError, ValueError) as e:
        gecici.unlink(missing_ok=True)
        raise GuncellemeHatasi(f"kurulum dosyası indirilemedi: {e}") from e
    if yeni.sha256 and h.hexdigest() != yeni.sha256:
        gecici.unlink(missing_ok=True)
        raise GuncellemeHatasi("indirilen dosya doğrulanamadı (SHA256 uyuşmuyor); kurulmadı")
    gecici.replace(hedef)
    return hedef


def surum_json(surum: str, indir_adresi: str, sha256: str, notlar: str) -> str:
    return json.dumps({"surum": surum, "indir": indir_adresi, "sha256": sha256, "notlar": notlar[:4000]},
                      ensure_ascii=False, indent=2)


def indirme_adresi(guncelleme_adresi: str, dosya_adi: str, surum: str) -> str:
    """surum.json adresinden kurulum dosyasının adresini türetir. GitHub 'releases/latest/download' adresinde
    sürüm etiketine (v1.4.0) göre adres verilir."""
    if not guncelleme_adresi:
        return ""
    if "/releases/latest/download/" in guncelleme_adresi:
        kok = guncelleme_adresi.split("/releases/latest/download/")[0]
        return f"{kok}/releases/download/v{surum}/{dosya_adi}"
    return guncelleme_adresi.rsplit("/", 1)[0] + "/" + dosya_adi


@dataclass
class GuncellemeAyarlari:
    otomatik: bool = True
    son_denetim: str = ""
    atlanan: str = ""

    @staticmethod
    def yol() -> Path:
        return config.data_dir() / "guncelleme_ayarlari.json"

    @classmethod
    def yukle(cls) -> "GuncellemeAyarlari":
        try:
            veri = json.loads(cls.yol().read_text("utf-8"))
        except (OSError, ValueError):
            return cls()
        return cls(**{k: v for k, v in veri.items() if k in cls.__dataclass_fields__})

    def kaydet(self) -> None:
        try:
            self.yol().write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def zamani_geldi(self, simdi: datetime | None = None) -> bool:
        if not self.otomatik or not adres():
            return False
        try:
            son = datetime.fromisoformat(self.son_denetim)
        except ValueError:
            return True
        return (simdi or datetime.now()) - son >= timedelta(hours=20)
