"""Kişiye özel belgeleri hazırlayıp her alıcıya kendi belgesini gönderme.

Her gönderim türü alıcıları (öğretmen veya işletme) ve onlara ait dosyaları üretir. Gönderme işi
paylasim modülündedir: e-posta tek oturumda her alıcıya ayrı ileti olarak, WhatsApp kişi kişi açılarak gider.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Callable

from .. import config
from ..mevzuat import AYLAR
from . import belgeler
from .paylasim import Kisi


@dataclass(frozen=True)
class GonderimTuru:
    anahtar: str
    etiket: str
    konu: str
    metin: str
    aylik: bool = False


TURLER: dict[str, GonderimTuru] = {t.anahtar: t for t in [
    GonderimTuru("ogretmen_program", "Öğretmenlere kendi ders programı (PDF)",
                 "{kurum} - Haftalık ders programınız",
                 "Sayın {ad},\n\nEkte {egitim_yili} eğitim-öğretim yılı haftalık ders programınız gönderilmiştir.\n\n"
                 "Saygılarımızla,\n{kurum}"),
    GonderimTuru("koordinator_gorev", "Koordinatör öğretmenlere görevlendirme yazısı",
                 "{kurum} - Koordinatör öğretmen görevlendirmesi",
                 "Sayın {ad},\n\nİşletmelerde mesleki eğitim koordinatör öğretmen görevlendirme yazınız ektedir.\n\n"
                 "Saygılarımızla,\n{kurum}"),
    GonderimTuru("isletme_koordinator", "İşletmelere koordinatör öğretmen bildirimi",
                 "{kurum} - Koordinatör öğretmen bildirimi",
                 "Sayın {ad},\n\nİşletmenizdeki öğrencilerimizin koordinatör öğretmen bilgileri ektedir.\n\n"
                 "Saygılarımızla,\n{kurum}"),
    GonderimTuru("isletme_ucret", "İşletmelere aylık ücret ve devlet katkısı bildirimi",
                 "{kurum} - {donem} öğrenci ücreti ve devlet katkısı",
                 "Sayın {ad},\n\n{donem} dönemine ait öğrenci ücreti ve devlet katkısı bildirimi ektedir. Ücretin "
                 "öğrencinin banka hesabına yatırılıp dekontun okulumuza iletilmesini rica ederiz.\n\n"
                 "Saygılarımızla,\n{kurum}", aylik=True),
    GonderimTuru("isletme_sozlesme", "İşletmelere öğrenci sözleşmeleri",
                 "{kurum} - Öğrenci sözleşmeleri",
                 "Sayın {ad},\n\nİşletmenizde eğitim gören öğrencilerimizin sözleşmeleri ektedir. İmzalanarak "
                 "okulumuza iletilmesini rica ederiz.\n\nSaygılarımızla,\n{kurum}"),
]}


@dataclass
class Gonderi:
    kisi: Kisi
    dosyalar: list[Path] = field(default_factory=list)
    hata: str = ""
    durum: str = ""


def _ogretmen_kisi(r) -> Kisi:
    return Kisi(f"{r['ad']} {r['soyad']}", "Öğretmen", r["eposta"] or "", r["telefon"] or "", f"ogretmen:{r['id']}")


def _isletme_kisi(r) -> Kisi:
    ad = f"{r['yetkili']} - {r['ad']}" if r["yetkili"] else r["ad"]
    return Kisi(ad, "İşletme", r["eposta"] or "", r["telefon"] or "", f"isletme:{r['id']}")


def _ogretmenler(db, sql: str) -> list:
    return db.q(f"SELECT id, ad, soyad, eposta, telefon FROM ogretmenler WHERE id IN ({sql}) ORDER BY ad, soyad")


def _isletmeler(db, sql: str) -> list:
    return db.q(f"SELECT id, ad, yetkili, eposta, telefon FROM isletmeler WHERE id IN ({sql}) ORDER BY ad")


def klasor(tur: str) -> Path:
    p = config.output_dir() / "Toplu Gönderim" / f"{TURLER[tur].etiket[:40]} {datetime.now():%Y-%m-%d %H%M}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _guvenli(s: str) -> str:
    return belgeler._guvenli(s)


def hazirla(db, tur: str, hedef: Path, yil: int | None = None, ay: int | None = None,
            pdf_uret: Callable[[object, str, int, str, Path], Path] | None = None) -> list[Gonderi]:
    """Alıcıları ve her alıcının dosyalarını üretir. Belgesi üretilemeyen alıcı hata ile listelenir."""
    hedef.mkdir(parents=True, exist_ok=True)
    out: list[Gonderi] = []

    def ekle(kisi: Kisi, uret: Callable[[], list[Path]]) -> None:
        g = Gonderi(kisi)
        try:
            g.dosyalar = uret()
        except Exception as e:  # noqa: BLE001 - bir alıcının hatası ötekileri durdurmaz
            g.hata = str(e) or type(e).__name__
        out.append(g)

    if tur == "ogretmen_program":
        if pdf_uret is None:
            raise ValueError("ders programı PDF'i için pdf_uret gerekli")
        for r in _ogretmenler(db, """SELECT ogretmen_id FROM ders_atamalari da JOIN program_hucreleri ph
                                       ON ph.atama_id = da.id WHERE ogretmen_id IS NOT NULL
                                     UNION SELECT ogretmen2_id FROM ders_atamalari da JOIN program_hucreleri ph
                                       ON ph.atama_id = da.id WHERE ogretmen2_id IS NOT NULL"""):
            k = _ogretmen_kisi(r)
            ekle(k, lambda r=r, k=k: [pdf_uret(db, "ogretmen", r["id"], f"Öğretmen: {k.ad}",
                                               hedef / f"Ders Programı - {_guvenli(k.ad)}.pdf")])
    elif tur == "koordinator_gorev":
        for r in _ogretmenler(db, "SELECT ogretmen_id FROM koordinator_gorevleri"):
            ekle(_ogretmen_kisi(r), lambda r=r: [belgeler.uret(db, "koordinator_gorevlendirme", r["id"], hedef)])
    elif tur == "isletme_koordinator":
        for r in _isletmeler(db, "SELECT isletme_id FROM koordinator_gorevleri"):
            ekle(_isletme_kisi(r), lambda r=r: [belgeler.uret(db, "koordinator_bildirimi", r["id"], hedef)])
    elif tur == "isletme_ucret":
        bugun = date.today()
        yil, ay = yil or bugun.year, ay or bugun.month
        for r in _isletmeler(db, "SELECT isletme_id FROM yerlestirmeler WHERE durum = 'Aktif'"):
            ekle(_isletme_kisi(r), lambda r=r: [belgeler.uret(db, "isletme_ucret_bildirimi", r["id"], hedef,
                                                              yil=yil, ay=ay)])
    elif tur == "isletme_sozlesme":
        gruplar: dict[int, list] = defaultdict(list)
        for y in db.q("""SELECT y.id, y.isletme_id, y.tur FROM yerlestirmeler y JOIN ogrenciler o ON o.id = y.ogrenci_id
                         WHERE y.durum = 'Aktif' AND y.isletme_id IS NOT NULL ORDER BY o.ad, o.soyad"""):
            gruplar[y["isletme_id"]].append(y)
        for r in _isletmeler(db, "SELECT isletme_id FROM yerlestirmeler WHERE durum = 'Aktif'"):
            ekle(_isletme_kisi(r), lambda r=r: [
                belgeler.uret(db, "ciraklik_sozlesmesi" if y["tur"] == "Çıraklık" else "isletme_sozlesmesi",
                              y["id"], hedef / _guvenli(r["ad"])) for y in gruplar[r["id"]]])
    else:
        raise ValueError(tur)
    return out


def metinler(db, tur: str, kisi: Kisi, yil: int | None = None, ay: int | None = None,
             konu: str | None = None, metin: str | None = None) -> tuple[str, str]:
    t = TURLER[tur]
    k = db.kurum()
    bugun = date.today()
    donem = f"{AYLAR[(ay or bugun.month) - 1]} {yil or bugun.year}"
    alanlar = {"ad": kisi.ad.split(" - ")[0], "kurum": k["ad"] or "", "egitim_yili": k["egitim_yili"] or "",
               "donem": donem}
    return (konu or t.konu).format_map(_Eksiksiz(alanlar)), (metin or t.metin).format_map(_Eksiksiz(alanlar))


class _Eksiksiz(dict):
    def __missing__(self, anahtar: str) -> str:
        return "{" + anahtar + "}"
