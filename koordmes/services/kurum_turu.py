"""Kurum adından tür tahmini ve türe göre açılacak resmi sistemler.

Kurum kodu tek başına e-Okul, e-Mesem veya SGK'dan veri indirmez; bu sistemlerin açık
servisi yoktur. Ad, türü seçer. Listeler, programın içindeki tarayıcıda kullanıcı giriş
yaptıktan sonra indirdiği dosyalardan gelir. Aynı kayıtlar elle de girilebilir.
"""
from __future__ import annotations

from .aktarim import norm


def _kelime(metin: str, kelime: str) -> bool:
    return f" {kelime} " in f" {metin} "


def tur_tahmin(ad: str) -> str | None:
    """Okul adından MTAL, MEM, ÇPAL veya MTAL+MEM döndürür. Ad yetersizse None."""
    n = norm(ad)
    if not n:
        return None
    mem = "mesleki egitim merkezi" in n or _kelime(n, "mem") or _kelime(n, "mesem")
    cpal = "cok programl" in n or _kelime(n, "cpal")
    mtal = ("mesleki ve teknik" in n or "mesleki teknik" in n or "teknik anadolu" in n
            or "anadolu teknik" in n or _kelime(n, "mtal"))
    if mem and (mtal or cpal):
        return "MTAL+MEM"
    if mem:
        return "MEM"
    if cpal:
        return "ÇPAL"
    if mtal:
        return "MTAL"
    return None


def sistemler(tur: str) -> list[str]:
    """Tür için program içinde açılacak sistem anahtarları. Hepsi birden değil, sırayla açılır."""
    if tur == "MEM":
        return ["emesem", "eokul", "sgk4a", "ebildirge", "vizite"]
    if tur == "MTAL+MEM":
        return ["eokul", "emesem", "sgk4a", "ebildirge", "vizite"]
    return ["eokul", "sgk4a", "ebildirge", "vizite"]


def aciklama(tur: str) -> str:
    ad = {
        "MTAL": "Mesleki ve teknik Anadolu lisesi",
        "MEM": "Mesleki eğitim merkezi",
        "ÇPAL": "Çok programlı Anadolu lisesi",
        "MTAL+MEM": "Mesleki ve teknik Anadolu lisesi ile mesleki eğitim merkezi",
    }.get(tur or "MTAL", tur or "Kurum")
    return (f"{ad}: ders programı, öğrenci, öğretmen, işletme ve SGK işlemleri bu programda yapılır. "
            "Kurum adı türü seçer; kurum kodu okulu kayıtlara bağlar. "
            "e-Okul, e-Mesem, SGK işe giriş/çıkış, e-Bildirge ve e-Vizite listeleri, programın içindeki "
            "ekranda giriş yaptıktan sonra indirdiğiniz dosyalardan kendiliğinden gelir. "
            "İsterseniz aynı kayıtları ilgili ekranlardan elle de girebilirsiniz.")
