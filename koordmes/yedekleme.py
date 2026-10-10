"""Zamanlanmış otomatik yedek ve ikinci yedek klasörü (USB bellek ya da ağ klasörü).

Ayarlar bilgisayara özeldir (her bilgisayarda USB sürücü harfi farklı olabilir); veri klasöründeki
`yedek_ayarlari.json` dosyasında durur. Otomatik yedeği veritabanının durduğu bilgisayar alır (tek başına ya da
sunucu); ağa bağlı bilgisayarlar almaz.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from . import config

ARALIKLAR = [(6, "6 saatte bir"), (12, "12 saatte bir"), (24, "Günde bir"), (168, "Haftada bir")]
IKINCI_KLASOR_ADI = "MesKoord_Yedekler"
ESKI_IKINCI_KLASOR_ADI = "KoordMES_Yedekler"
IKINCI_KLASOR_TUT = 30


@dataclass
class YedekAyarlari:
    otomatik: bool = True
    aralik_saat: int = 24
    ikinci_klasor: str = ""
    son_yedek: str = ""
    son_hata: str = ""

    @staticmethod
    def yol() -> Path:
        return config.data_dir() / "yedek_ayarlari.json"

    @classmethod
    def yukle(cls) -> "YedekAyarlari":
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

    def son_yedek_zamani(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.son_yedek)
        except ValueError:
            return None

    def zamani_geldi(self, simdi: datetime | None = None) -> bool:
        if not self.otomatik:
            return False
        son = self.son_yedek_zamani()
        return son is None or (simdi or datetime.now()) - son >= timedelta(hours=max(1, int(self.aralik_saat)))


def ikinci_klasore_kopyala(yedek: Path, klasor: str) -> Path:
    hedef = config.tasi(Path(klasor) / IKINCI_KLASOR_ADI, Path(klasor) / ESKI_IKINCI_KLASOR_ADI)
    hedef.mkdir(parents=True, exist_ok=True)
    kopya = hedef / yedek.name
    shutil.copy2(yedek, kopya)
    from .db import eski_yedekleri_temizle
    eski_yedekleri_temizle(hedef, IKINCI_KLASOR_TUT)
    return kopya


def yedek_alindi(yedek: Path) -> None:
    """Her otomatik yedekten sonra çağrılır: zamanı kaydeder, varsa ikinci klasöre kopyalar."""
    a = YedekAyarlari.yukle()
    a.son_yedek = datetime.now().isoformat(" ", "seconds")
    a.son_hata = ""
    if a.ikinci_klasor:
        try:
            ikinci_klasore_kopyala(yedek, a.ikinci_klasor)
        except OSError as e:
            a.son_hata = (f"{datetime.now():%d.%m.%Y %H:%M} ikinci klasöre kopyalanamadı ({a.ikinci_klasor}): "
                          f"{e.strerror or e}")
    a.kaydet()
