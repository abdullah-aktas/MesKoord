"""Tarih, para ve doğrulama yardımcıları."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any, Iterable


def tarih(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def tr(d: Any) -> str:
    d = tarih(d)
    return d.strftime("%d.%m.%Y") if d else ""


def ay_araligi(yil: int, ay: int) -> tuple[date, date]:
    return date(yil, ay, 1), date(yil, ay, calendar.monthrange(yil, ay)[1])


def gunler_listesi(s: str | None) -> list[int]:
    if not s:
        return []
    out = []
    for p in str(s).replace(";", ",").split(","):
        p = p.strip()
        if p.isdigit() and 1 <= int(p) <= 7:
            out.append(int(p))
    return sorted(set(out))


def tarih_araliginda(d: date, bas: date | None, bit: date | None) -> bool:
    return (bas is None or d >= bas) and (bit is None or d <= bit)


def tatil_gunleri(db, bas: date, bit: date) -> set[date]:
    out: set[date] = set()
    for r in db.q("SELECT baslangic, bitis FROM tatiller WHERE bitis >= ? AND baslangic <= ?",
                  (bas.isoformat(), bit.isoformat())):
        b, e = tarih(r["baslangic"]), tarih(r["bitis"])
        if not b or not e:
            continue
        d = max(b, bas)
        while d <= min(e, bit):
            out.add(d)
            d += timedelta(days=1)
    return out


def is_gunleri(bas: date, bit: date) -> Iterable[date]:
    d = bas
    while d <= bit:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def para(x: float | None) -> str:
    if x is None:
        return ""
    s = f"{x:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def yuvarla(x: float) -> float:
    return float(f"{x + 1e-9:.2f}")


def tc_gecerli(tc: str | None) -> bool:
    if not tc:
        return False
    tc = str(tc).strip()
    if len(tc) != 11 or not tc.isdigit() or tc[0] == "0":
        return False
    d = [int(c) for c in tc]
    if ((sum(d[0:9:2]) * 7 - sum(d[1:8:2])) % 10) != d[9]:
        return False
    return sum(d[:10]) % 10 == d[10]


def iban_gecerli(iban: str | None) -> bool:
    """TR IBAN biçimi ve ISO 7064 mod 97 denetimi."""
    if not iban:
        return False
    s = str(iban).replace(" ", "").upper()
    if len(s) != 26 or not s.startswith("TR") or not s[2:].isdigit():
        return False
    sayisal = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return int(sayisal) % 97 == 1


def ad_soyad(row) -> str:
    return f"{row['ad']} {row['soyad']}".strip()


def ilerideki_is_gunu(d: date, tatiller: set[date] | None = None) -> date:
    """Tatil veya hafta sonuna denk gelen son günü izleyen ilk iş gününe kaydırır."""
    tatiller = tatiller or set()
    while d.weekday() >= 5 or d in tatiller:
        d += timedelta(days=1)
    return d
