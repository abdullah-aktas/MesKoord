"""Öğrenci, öğretmen, işletme ve SGK aktarımlarındaki eklenen ve güncellenen kayıtların özeti."""
from __future__ import annotations

from datetime import datetime

ANAHTAR = "son_veri_degisikligi"

IZLENEN = {
    "ogrenciler": "öğrenci",
    "ogretmenler": "öğretmen",
    "isletmeler": "işletme",
    "yerlestirmeler": "yerleştirme",
    "sgk_bildirimleri": "SGK bildirimi",
    "siniflar": "sınıf",
    "ders_atamalari": "ders ataması",
    "program_hucreleri": "ders programı saati",
}


def metin(sonuclar) -> str:
    satirlar: list[str] = []

    def yuru(s) -> None:
        ad = IZLENEN.get(getattr(s, "anahtar", ""))
        if ad and (s.eklenen or s.guncellenen):
            satirlar.append(f"{ad}: {s.eklenen} yeni, {s.guncellenen} güncellenen")
        for e in getattr(s, "ek", ()) or ():
            yuru(e)

    for s in sonuclar:
        yuru(s)
    return "\n".join(satirlar)


def yaz(db, govde: str) -> str:
    govde = (govde or "").strip()
    if not govde:
        return ""
    deger = datetime.now().strftime("%d.%m.%Y %H:%M") + "\n" + govde
    db.execute("INSERT INTO meta (anahtar, deger) VALUES (?, ?) "
               "ON CONFLICT(anahtar) DO UPDATE SET deger = excluded.deger", (ANAHTAR, deger))
    return deger


def kaydet(db, sonuclar, ek: str = "") -> str:
    govde = metin(sonuclar)
    if ek:
        govde = (govde + "\n" + ek).strip() if govde else ek.strip()
    return yaz(db, govde)


def oku(db) -> str:
    r = db.q1("SELECT deger FROM meta WHERE anahtar = ?", (ANAHTAR,))
    return (r["deger"] if r else "") or ""
