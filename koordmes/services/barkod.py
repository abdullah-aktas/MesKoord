"""Code 128 barkod (yalnızca rakam, C kümesi) ve bağımlılıksız PNG çizimi."""
from __future__ import annotations

import struct
import zlib

# Değer 0..106 için çubuk/boşluk genişlikleri (ilk hane çubuk). 105: C başlangıcı, 106: bitiş.
DESENLER = (
    "212222", "222122", "222221", "121223", "121322", "131222", "122213", "122312", "132212", "221213",
    "221312", "231212", "112232", "122132", "122231", "113222", "123122", "123221", "223211", "221132",
    "221231", "213212", "223112", "312131", "311222", "321122", "321221", "312212", "322112", "322211",
    "212123", "212321", "232121", "111323", "131123", "131321", "112313", "132113", "132311", "211313",
    "231113", "231311", "112133", "112331", "132131", "113123", "113321", "133121", "313121", "211331",
    "231131", "213113", "213311", "213131", "311123", "311321", "331121", "312113", "312311", "332111",
    "314111", "221411", "431111", "111224", "111422", "121124", "121421", "141122", "141221", "112214",
    "112412", "122114", "122411", "142112", "142211", "241211", "221114", "413111", "241112", "134111",
    "111242", "121142", "121241", "114212", "124112", "124211", "411212", "421112", "421211", "212141",
    "214121", "412121", "111143", "111341", "131141", "114113", "114311", "411113", "411311", "113141",
    "114131", "311141", "411131", "211412", "211214", "211232", "2331112",
)
BASLA_C, BITIR = 105, 106
SESSIZ_BOLGE = 10  # modül


def degerler(kod: str) -> list[int]:
    """Çift sayıda rakamdan oluşan kodun C kümesi değerleri (başlangıç, veri, sağlama, bitiş)."""
    if not kod.isdigit() or len(kod) % 2:
        raise ValueError("Barkod çift sayıda rakamdan oluşmalı")
    veri = [int(kod[i:i + 2]) for i in range(0, len(kod), 2)]
    saglama = (BASLA_C + sum(i * v for i, v in enumerate(veri, 1))) % 103
    return [BASLA_C, *veri, saglama, BITIR]


def moduller(kod: str) -> list[int]:
    """Soldan sağa modül dizisi (1 = siyah), sessiz bölgeler dahil."""
    out = [0] * SESSIZ_BOLGE
    for v in degerler(kod):
        for i, w in enumerate(DESENLER[v]):
            out += [1 if i % 2 == 0 else 0] * int(w)
    return out + [0] * SESSIZ_BOLGE


def png(kod: str, modul_px: int = 3, yukseklik: int = 70) -> bytes:
    """Gri tonlamalı PNG baytları."""
    satir = bytes(0 if m else 255 for m in moduller(kod) for _ in range(modul_px))
    ham = b"".join(b"\x00" + satir for _ in range(yukseklik))

    def parca(tur: bytes, veri: bytes) -> bytes:
        return struct.pack(">I", len(veri)) + tur + veri + struct.pack(">I", zlib.crc32(tur + veri) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + parca(b"IHDR", struct.pack(">IIBBBBB", len(satir), yukseklik, 8, 0, 0, 0, 0))
            + parca(b"IDAT", zlib.compress(ham, 9)) + parca(b"IEND", b""))


def coz(moduller_: list[int]) -> str:
    """Modül dizisinden kodu geri okur (sınama ve okuyucu doğrulaması için)."""
    m = list(moduller_)
    while m and m[0] == 0:
        m.pop(0)
    while m and m[-1] == 0:
        m.pop()
    genislikler, onceki, n = [], m[0], 0
    for x in m:
        if x == onceki:
            n += 1
        else:
            genislikler.append(n)
            onceki, n = x, 1
    genislikler.append(n)
    tablo = {d: i for i, d in enumerate(DESENLER)}
    vals = []
    i = 0
    while i < len(genislikler):
        boy = 7 if len(genislikler) - i == 7 else 6
        vals.append(tablo["".join(str(w) for w in genislikler[i:i + boy])])
        i += boy
    if vals[0] != BASLA_C or vals[-1] != BITIR:
        raise ValueError("Başlangıç/bitiş deseni yok")
    veri, saglama = vals[1:-2], vals[-2]
    if (BASLA_C + sum(i * v for i, v in enumerate(veri, 1))) % 103 != saglama:
        raise ValueError("Sağlama hatalı")
    return "".join(f"{v:02d}" for v in veri)
