"""Okul ve işletme devamsızlık takibi."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class DevamOzeti:
    ogrenci_id: int
    ad: str
    okul_no: str
    sinif: str
    okul_ozursuz: float
    okul_ozurlu: float
    isletme_ozursuz: float
    isletme_ozurlu: float
    veli_ad: str
    veli_tel: str
    durum: str = "Normal"

    @property
    def toplam_ozursuz(self) -> float:
        return self.okul_ozursuz + self.isletme_ozursuz

    @property
    def toplam(self) -> float:
        return self.okul_ozursuz + self.okul_ozurlu + self.isletme_ozursuz + self.isletme_ozurlu


def ozet(db, bas: date | None = None, bit: date | None = None, sadece_devamsizlar: bool = True) -> list[DevamOzeti]:
    kosul, params = "", []
    if bas:
        kosul += " AND d.tarih >= ?"
        params.append(bas.isoformat())
    if bit:
        kosul += " AND d.tarih <= ?"
        params.append(bit.isoformat())
    # Sadece devamsızlar istenince sıfır kayıtlı öğrencileri SQL'de ele (Ana Sayfa taraması hızlanır)
    ogrenci_kosul = ("o.aktif = 1 AND EXISTS (SELECT 1 FROM devamsizlik dx WHERE dx.ogrenci_id = o.id)"
                     if sadece_devamsizlar else "o.aktif = 1")
    rows = db.q(f"""SELECT o.id, o.ad, o.soyad, o.okul_no, o.veli_ad, o.veli_tel, s.ad AS sinif,
                           COALESCE(SUM(CASE WHEN d.yer = 'Okul' AND d.tur = 'Özürsüz' THEN d.gun END), 0) AS oo,
                           COALESCE(SUM(CASE WHEN d.yer = 'Okul' AND d.tur != 'Özürsüz' THEN d.gun END), 0) AS ou,
                           COALESCE(SUM(CASE WHEN d.yer = 'İşletme' AND d.tur = 'Özürsüz' THEN d.gun END), 0) AS io,
                           COALESCE(SUM(CASE WHEN d.yer = 'İşletme' AND d.tur != 'Özürsüz' THEN d.gun END), 0) AS iu
                    FROM ogrenciler o LEFT JOIN siniflar s ON s.id = o.sinif_id
                    LEFT JOIN devamsizlik d ON d.ogrenci_id = o.id {kosul}
                    WHERE {ogrenci_kosul} GROUP BY o.id ORDER BY s.ad, o.okul_no, o.ad""", params)
    sinir_oz = db.ayar("devamsizlik_ozursuz_sinir")
    sinir_top = db.ayar("devamsizlik_toplam_sinir")
    veli = db.ayar("devamsizlik_veli_esik")
    out = []
    for r in rows:
        x = DevamOzeti(r["id"], f"{r['ad']} {r['soyad']}", r["okul_no"] or "", r["sinif"] or "",
                       r["oo"], r["ou"], r["io"], r["iu"], r["veli_ad"] or "", r["veli_tel"] or "")
        if sadece_devamsizlar and x.toplam == 0:
            continue
        if x.toplam_ozursuz > sinir_oz or x.toplam > sinir_top:
            x.durum = "Sınırı aştı"
        elif x.toplam_ozursuz >= sinir_oz - 2 or x.toplam >= sinir_top - 5:
            x.durum = "Sınıra yakın"
        elif x.toplam_ozursuz >= veli:
            x.durum = "Veli bildirimi"
        out.append(x)
    return out
