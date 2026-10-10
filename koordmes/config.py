"""Uygulama klasörleri (veritabanı, çıktılar, şablonlar).

1.3.0'da teknik ad KoordMES'ten MesKoord'a geçti. Eski adlı klasör ve dosyalar ilk açılışta yeni adlarına
taşınır; taşınamazsa (dosya başka bir programda açıksa) eski adıyla çalışılmaya devam edilir, veri kaybolmaz.
"""
from __future__ import annotations

import os
from pathlib import Path

AD = "MesKoord"
ESKI_AD = "KoordMES"
DB_ADI, ESKI_DB_ADI = "meskoord.db", "koordmes.db"
YEDEK_ONEKI = "meskoord_"
YEDEK_ONEKLERI = (YEDEK_ONEKI, "koordmes_")

_secilen: dict[str, Path] = {}


def ortam(ad: str) -> str:
    """MESKOORD_<ad> ortam değişkeni; yoksa eski KOORDMES_<ad>."""
    return os.environ.get(f"MESKOORD_{ad}") or os.environ.get(f"KOORDMES_{ad}") or ""


def tasi(yeni: Path, eski: Path) -> Path:
    """Yeni adlı yol yoksa eski adlıyı yeni adına taşır; taşınamazsa eskisini döndürür."""
    if yeni.exists() or not eski.exists():
        return yeni
    try:
        eski.rename(yeni)
        return yeni
    except OSError:
        return eski


def data_dir() -> Path:
    override = ortam("DATA")
    if override:
        base = Path(override)
    else:
        docs = Path.home() / "Documents"
        kok = docs if docs.exists() else Path.home()
        if str(kok) not in _secilen:  # taşıma kararı süreç boyunca bir kez verilir
            _secilen[str(kok)] = tasi(kok / AD, kok / ESKI_AD)
        base = _secilen[str(kok)]
    base.mkdir(parents=True, exist_ok=True)
    return base


def db_path() -> Path:
    d = data_dir()
    yeni, eski = d / DB_ADI, d / ESKI_DB_ADI
    if yeni.exists() or not eski.exists():
        return yeni
    if any(Path(f"{eski}{ek}").exists() for ek in ("-wal", "-journal")):
        return eski  # yarım kalmış işlem günlüğü varsa dosyalar birbirinden ayrılmasın
    try:
        eski.rename(yeni)
    except OSError:
        return eski
    Path(f"{eski}-shm").unlink(missing_ok=True)
    return yeni


def output_dir() -> Path:
    p = data_dir() / "Ciktilar"
    p.mkdir(parents=True, exist_ok=True)
    return p


def templates_dir() -> Path:
    p = data_dir() / "Sablonlar"
    p.mkdir(parents=True, exist_ok=True)
    return p


def backup_dir() -> Path:
    p = data_dir() / "Yedekler"
    p.mkdir(parents=True, exist_ok=True)
    return p


def yedek_adi(zaman) -> str:
    return f"{YEDEK_ONEKI}{zaman:%Y%m%d_%H%M%S_%f}"[:-3] + ".db"


def yedek_dosyalari(klasor: Path) -> list[Path]:
    """Otomatik yedekler, eskiden yeniye (eski ve yeni adlı yedekler birlikte)."""
    out = [p for onek in YEDEK_ONEKLERI for p in klasor.glob(f"{onek}*.db")]
    return sorted(out, key=lambda p: p.name.split("_", 1)[1])
