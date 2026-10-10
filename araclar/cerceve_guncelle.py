"""koordmes/veri/cerceve_programlari.json dosyasını meslek.meb.gov.tr/cerceve ile karşılaştırır.

    python araclar\\cerceve_guncelle.py [--indir KLASOR]

MTAL ve MEM için 9-12. sınıf liste sayfalarını okur; sitede olup veride bulunmayan (yeni yayımlanan)
çerçeve programı PDF'lerini, veride olup sitede artık listelenmeyenleri ve yılı değişenleri raporlar.
--indir verilirse yeni PDF'ler incelenmek üzere o klasöre indirilir. Haftalık ders çizelgeleri PDF'ten
elle doğrulanarak JSON'a işlenmeli, "surum" alanı güncellenmelidir. Fark yoksa çıkış kodu 0'dır.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from koordmes.services import cerceve  # noqa: E402

KURUM_ID = {"MTAL": 1, "MEM": 2}
ISTISNALAR = {
    "upload/cop9/meslekigelisim.pdf": "bütün alanların ortak dersinin programı; haftalık ders çizelgesi yok",
    "upload/cop12_mem/2021_hyvs_mem_cop.pdf": "sitede listeleniyor ancak dosya yok (HTTP 404)",
}
KART = re.compile(r'ribbon[^>]*>\s*<span>\s*(?P<yil>\d{4})\s*</span>.*?href="(?P<pdf>[^"]+\.pdf)".*?<b>(?P<ad>[^<]+)</b>',
                  re.S | re.I)


@dataclass(frozen=True)
class SiteKaydi:
    kurum: str
    seviye: int
    ad: str
    yil: str
    kaynak: str


def _getir(url: str) -> bytes:
    istek = urllib.request.Request(url, headers={"User-Agent": "MesKoord cerceve denetimi"})
    with urllib.request.urlopen(istek, timeout=60) as r:
        return r.read()


def site_kayitlari() -> list[SiteKaydi]:
    out = []
    for kurum, kid in KURUM_ID.items():
        for seviye in cerceve.SEVIYELER:
            sayfa = _getir(f"{cerceve.SITE}cercevelistele.aspx?sinif_kodu={seviye}&kurum_id={kid}")
            metin = sayfa.decode("utf-8", "replace")
            bulunan = {m["pdf"]: m for m in KART.finditer(metin)}
            if not bulunan:
                raise SystemExit(f"{kurum} {seviye}. sınıf liste sayfasında program bulunamadı; site yapısı "
                                 "değişmiş olabilir.")
            out += [SiteKaydi(kurum, seviye, html.unescape(m["ad"]).strip(), m["yil"], pdf.lstrip("/"))
                    for pdf, m in bulunan.items()]
            print(f"{kurum} {seviye}. sınıf: {len(bulunan)} program")
    return out


def karsilastir(site: list[SiteKaydi]) -> tuple[list[SiteKaydi], list[str], list[str]]:
    veri: dict[str, set[str]] = {}
    for p in cerceve.programlar():
        veri.setdefault(p.kaynak, set()).add(p.yil)
    yeni = [s for s in site if s.kaynak not in veri and s.kaynak not in ISTISNALAR]
    sitede = {s.kaynak for s in site}
    kalkan = sorted(k for k in veri if k not in sitede)
    yil = sorted(f"{s.kurum} {s.seviye}. sınıf {s.ad}: veride {'/'.join(sorted(veri[s.kaynak]))}, sitede {s.yil}"
                 for s in site if s.kaynak in veri and s.yil not in veri[s.kaynak])
    return yeni, kalkan, yil


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--indir", type=Path, help="yeni PDF'lerin indirileceği klasör")
    a = ap.parse_args()
    print(f"Veri: {cerceve.VERI_DOSYASI} (sürüm {cerceve.surum()}, {len(cerceve.programlar())} çizelge)")
    site = site_kayitlari()
    yeni, kalkan, yil = karsilastir(site)
    for s in site:
        if s.kaynak in ISTISNALAR:
            print(f"  (atlandı) {s.kurum} {s.seviye}. sınıf {s.ad}: {ISTISNALAR[s.kaynak]}")
    if yeni:
        print(f"\nSitede olup veride olmayan {len(yeni)} PDF:")
        for s in yeni:
            print(f"  {s.kurum} {s.seviye}. sınıf  {s.ad} ({s.yil})  {cerceve.SITE}{s.kaynak}")
    if kalkan:
        print(f"\nVeride olup sitede listelenmeyen {len(kalkan)} PDF (yerine yenisi gelmiş olabilir):")
        print("  " + "\n  ".join(kalkan))
    if yil:
        print(f"\nYılı değişen {len(yil)} program:")
        print("  " + "\n  ".join(yil))
    if a.indir and yeni:
        a.indir.mkdir(parents=True, exist_ok=True)
        for s in yeni:
            hedef = a.indir / s.kaynak.replace("/", "_")
            hedef.write_bytes(_getir(cerceve.SITE + s.kaynak))
        print(f"\n{len(yeni)} PDF {a.indir} klasörüne indirildi.")
    if not (yeni or kalkan or yil):
        print("\nVeri güncel: sitedeki bütün çerçeve programları veride var.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
