"""MesKoord marka görsellerini geometriden çizer (dış görsel kullanılmaz).

Simge: yuvarlatılmış kare gece mavisi zemin üzerinde soluk bir atölye dişlisi (mesleki eğitim) ve onun içinde
kesintisiz tek bir çizgiyle çizilmiş M harfi. M'nin iki tepesindeki beyaz düğümler okul ile işletme, ortadaki
çukurda duran turkuaz düğüm öğrencidir: koordinasyon iki tarafı öğrenci üzerinden birbirine bağlar. Turkuaz
düğümün çevresindeki boşluk onu çizginin önüne çıkarır. Bütün ölçüler 1024 birimlik tuvale göredir (GEO); SVG
aslı aynı ölçülerle yazılır.

Üretilenler:
  koordmes/gorseller/simge.png, simge_kucuk.png, logo_yatay.png, acilis.png
  dagitim/meskoord.ico, dagitim/kurulum_buyuk*.bmp, dagitim/kurulum_kucuk*.bmp
  dagitim/marka/meskoord_simge.svg, meskoord_simge_1024.png, meskoord_logo.png, tanitim_afisi.png
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
from koordmes import marka  # noqa: E402

FONT = Path("C:/Windows/Fonts")

# 1024 birimlik tuval
GEO = {
    "kenar": 32, "yaricap": 228,
    "disli": {"merkez": (512, 520), "dis": 404, "kok": 356, "ic": 304, "sayi": 12, "ust": 0.17, "alt": 0.29,
              "opaklik": 30},
    "m": ((288, 744), (334, 322), (512, 606), (690, 322), (736, 744)),
    "kalinlik": 92, "tepe": 70, "vadi": 84, "bosluk": 28,
}
# 16-32 piksel: dişli yok, kalın çizgi, kenar boşluğu yok
GEO_SADE = {
    "kenar": 0, "yaricap": 214, "disli": None,
    "m": ((212, 812), (272, 262), (512, 636), (752, 262), (812, 812)),
    "kalinlik": 150, "tepe": 92, "vadi": 118, "bosluk": 40,
}


def renk(h: str, a: int = 255) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a


def yazi_tipi(boyut: int, agirlik: str = "normal") -> ImageFont.FreeTypeFont:
    adlar = {"normal": ("segoeui.ttf", "arial.ttf"), "yari": ("seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"),
             "kalin": ("segoeuib.ttf", "arialbd.ttf"), "ince": ("segoeuil.ttf", "segoeui.ttf", "arial.ttf")}[agirlik]
    for ad in adlar:
        if (FONT / ad).exists():
            return ImageFont.truetype(str(FONT / ad), boyut)
    return ImageFont.load_default(boyut)


def disli_noktalari(g: dict) -> list[tuple[float, float]]:
    cx, cy = g["merkez"]
    p = 2 * math.pi / g["sayi"]
    out = []
    for i in range(g["sayi"]):
        a = i * p - math.pi / 2
        for aci, r in ((a - g["alt"] * p, g["kok"]), (a - g["ust"] * p, g["dis"]),
                       (a + g["ust"] * p, g["dis"]), (a + g["alt"] * p, g["kok"])):
            out.append((cx + r * math.cos(aci), cy + r * math.sin(aci)))
        for j in range(1, 4):  # iki diş arasındaki kök yayı
            aci = a + g["alt"] * p + j * (1 - 2 * g["alt"]) * p / 4
            out.append((cx + g["kok"] * math.cos(aci), cy + g["kok"] * math.sin(aci)))
    return out


def disli_maskesi(S: int, g: dict) -> Image.Image:
    k = S / 1024
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    d.polygon([(x * k, y * k) for x, y in disli_noktalari(g)], fill=255)
    cx, cy, r = g["merkez"][0] * k, g["merkez"][1] * k, g["ic"] * k
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)
    return m


def daire(S: int, merkez: tuple[float, float], r: float) -> Image.Image:
    k = S / 1024
    m = Image.new("L", (S, S), 0)
    x, y = merkez[0] * k, merkez[1] * k
    ImageDraw.Draw(m).ellipse((x - r * k, y - r * k, x + r * k, y + r * k), fill=255)
    return m


def m_maskesi(S: int, g: dict) -> Image.Image:
    k = S / 1024
    m = Image.new("L", (S, S), 0)
    d = ImageDraw.Draw(m)
    noktalar = [(x * k, y * k) for x, y in g["m"]]
    w = g["kalinlik"] * k
    d.line(noktalar, fill=255, width=round(w), joint="curve")
    for x, y in noktalar:
        d.ellipse((x - w / 2, y - w / 2, x + w / 2, y + w / 2), fill=255)
    for i in (1, 3):
        m = ImageChops.lighter(m, daire(S, g["m"][i], g["tepe"]))
    vadi = g["m"][2]
    return ImageChops.subtract(m, daire(S, vadi, g["vadi"] + g["bosluk"]))


def gecis(boyut: tuple[int, int], r1: str, r2: str, capraz: bool = True) -> Image.Image:
    """r1'den r2'ye doğrusal geçiş (çapraz: sol üstten sağ alta)."""
    w, h = boyut
    kucuk = Image.new("RGBA", (64, 64))
    a, b = renk(r1), renk(r2)
    px = kucuk.load()
    for y in range(64):
        for x in range(64):
            t = (x + y) / 126 if capraz else y / 63
            px[x, y] = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(4))
    return kucuk.resize((w, h), Image.BICUBIC)


def simge(boyut: int, sade: bool = False, olcek: int = 4) -> Image.Image:
    g = GEO_SADE if sade else GEO
    S = boyut * olcek
    k = S / 1024
    zemin_maske = Image.new("L", (S, S), 0)
    e = g["kenar"] * k
    ImageDraw.Draw(zemin_maske).rounded_rectangle((e, e, S - e, S - e), g["yaricap"] * k, fill=255)
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    im.paste(gecis((S, S), marka.ANA_ACIK, marka.ANA_KOYU), (0, 0), zemin_maske)
    if g["disli"]:
        dm = disli_maskesi(S, g["disli"]).point(lambda v: v * g["disli"]["opaklik"] // 255)
        im.paste(Image.new("RGBA", (S, S), (255, 255, 255, 255)), (0, 0), ImageChops.multiply(dm, zemin_maske))
    im.paste(Image.new("RGBA", (S, S), (255, 255, 255, 255)), (0, 0), m_maskesi(S, g))
    im.paste(gecis((S, S), marka.VURGU_ACIK, marka.VURGU), (0, 0), daire(S, g["m"][2], g["vadi"]))
    return im.resize((boyut, boyut), Image.LANCZOS)


def svg() -> str:
    g = GEO
    e, r = g["kenar"], g["yaricap"]
    dg = g["disli"]
    cx, cy = dg["merkez"]
    disli = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in disli_noktalari(dg)) + " Z " + \
            f"M{cx - dg['ic']} {cy} a{dg['ic']} {dg['ic']} 0 1 0 {2 * dg['ic']} 0 " \
            f"a{dg['ic']} {dg['ic']} 0 1 0 {-2 * dg['ic']} 0 Z"
    cizgi = " ".join(f"{x},{y}" for x, y in g["m"])
    (x1, y1), (vx, vy), (x3, y3) = g["m"][1], g["m"][2], g["m"][3]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="1024" height="1024">
  <title>{marka.URUN}</title>
  <defs>
    <linearGradient id="zemin" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{marka.ANA_ACIK}"/><stop offset="1" stop-color="{marka.ANA_KOYU}"/>
    </linearGradient>
    <linearGradient id="turkuaz" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{marka.VURGU_ACIK}"/><stop offset="1" stop-color="{marka.VURGU}"/>
    </linearGradient>
    <mask id="bosluk" maskUnits="userSpaceOnUse" x="0" y="0" width="1024" height="1024">
      <rect width="1024" height="1024" fill="#fff"/>
      <circle cx="{vx}" cy="{vy}" r="{g['vadi'] + g['bosluk']}" fill="#000"/>
    </mask>
  </defs>
  <rect x="{e}" y="{e}" width="{1024 - 2 * e}" height="{1024 - 2 * e}" rx="{r}" fill="url(#zemin)"/>
  <path d="{disli}" fill="#fff" fill-opacity="{dg['opaklik'] / 255:.3f}" fill-rule="evenodd"/>
  <g mask="url(#bosluk)" fill="#fff">
    <polyline points="{cizgi}" fill="none" stroke="#fff" stroke-width="{g['kalinlik']}" stroke-linejoin="round"
              stroke-linecap="round"/>
    <circle cx="{x1}" cy="{y1}" r="{g['tepe']}"/>
    <circle cx="{x3}" cy="{y3}" r="{g['tepe']}"/>
  </g>
  <circle cx="{vx}" cy="{vy}" r="{g['vadi']}" fill="url(#turkuaz)"/>
</svg>
"""


def yazi_genisligi(d: ImageDraw.ImageDraw, metin: str, font) -> int:
    sol, _, sag, _ = d.textbbox((0, 0), metin, font=font)
    return sag - sol


def ad_yaz(d: ImageDraw.ImageDraw, xy: tuple[float, float], font, govde, vurgu) -> int:
    """'MesKoord' yazısı: 'Mes' gövde, 'Koord' vurgu renginde. Yazının genişliğini döndürür."""
    x, y = xy
    d.text((x, y), marka.URUN_ON, font=font, fill=govde)
    d.text((x + d.textlength(marka.URUN_ON, font=font), y), marka.URUN_SON, font=font, fill=vurgu)
    return yazi_genisligi(d, marka.URUN, font)


def ortala(d: ImageDraw.ImageDraw, xy: tuple[int, int], metin: str, font, dolgu) -> None:
    sol, ust, sag, alt = d.textbbox((0, 0), metin, font=font)
    d.text((xy[0] - (sag - sol) / 2 - sol, xy[1] - (alt - ust) / 2 - ust), metin, font=font, fill=dolgu)


def logo_yatay(yukseklik: int = 160) -> Image.Image:
    font = yazi_tipi(round(yukseklik * 0.52), "yari")
    alt = yazi_tipi(round(yukseklik * 0.135))
    olcu = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    w = yukseklik + round(yukseklik * 0.18) + max(yazi_genisligi(olcu, marka.URUN, font),
                                                   yazi_genisligi(olcu, marka.SLOGAN, alt)) + 8
    im = Image.new("RGBA", (w, yukseklik), (0, 0, 0, 0))
    im.alpha_composite(simge(yukseklik))
    d = ImageDraw.Draw(im)
    x = yukseklik + round(yukseklik * 0.18)
    ad_yaz(d, (x, yukseklik * 0.02), font, renk(marka.ANA), renk(marka.VURGU_KOYU))
    d.text((x + 3, yukseklik * 0.72), marka.SLOGAN, font=alt, fill=renk(marka.ANA_ACIK))
    return im


def acilis() -> Image.Image:
    W, H = 640, 360
    im = Image.new("RGBA", (W, H), renk("#FFFFFF"))
    im.paste(gecis((W, H - 52), "#FFFFFF", "#E9EEF8"), (0, 0))
    d = ImageDraw.Draw(im)
    s = simge(196)
    im.alpha_composite(s, (46, (H - 52 - 196) // 2))
    ad_yaz(d, (272, 82), yazi_tipi(66, "yari"), renk(marka.ANA), renk(marka.VURGU_KOYU))
    d.rounded_rectangle((276, 178, 596, 182), 2, fill=renk(marka.VURGU))
    f = yazi_tipi(16)
    d.text((276, 194), "Mesleki Eğitim Koordinasyon", font=f, fill=renk(marka.ANA_ACIK))
    d.text((276, 216), "ve Yönetim Sistemi", font=f, fill=renk(marka.ANA_ACIK))
    d.rectangle((0, H - 52, W, H), fill=renk(marka.ANA))
    d.rectangle((0, H - 55, W, H - 52), fill=renk(marka.VURGU))
    return im


def kurulum_buyuk(olcek: float) -> Image.Image:
    W, H = round(164 * olcek), round(314 * olcek)
    im = gecis((W, H), marka.ANA_ACIK, marka.ANA_KOYU, capraz=False)
    s = simge(round(104 * olcek))
    im.alpha_composite(s, ((W - s.size[0]) // 2, round(40 * olcek)))
    d = ImageDraw.Draw(im)
    f = yazi_tipi(round(26 * olcek), "yari")
    genislik = yazi_genisligi(d, marka.URUN, f)
    ad_yaz(d, ((W - genislik) / 2, round(160 * olcek)), f, (255, 255, 255, 255), renk(marka.VURGU_ACIK))
    d.rectangle((round(36 * olcek), round(206 * olcek), W - round(36 * olcek), round(208 * olcek)),
                fill=renk(marka.VURGU))
    f = yazi_tipi(round(10 * olcek))
    for i, s in enumerate(("Mesleki Eğitim", "Koordinasyon ve", "Yönetim Sistemi")):
        ortala(d, (W // 2, round((228 + 16 * i) * olcek)), s, f, (255, 255, 255, 230))
    return im.convert("RGB")


def kurulum_kucuk(boyut: int) -> Image.Image:
    im = Image.new("RGBA", (boyut, boyut), (255, 255, 255, 255))
    im.alpha_composite(simge(boyut - 4), (2, 2))
    return im.convert("RGB")


def afis() -> Image.Image:
    W, H = 1200, 630
    im = gecis((W, H), marka.ANA_ACIK, marka.ANA_KOYU)
    d = ImageDraw.Draw(im)
    # arka planda soluk dişli izi
    S = 900
    iz = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    iz.paste(Image.new("RGBA", (S, S), (255, 255, 255, 12)), (0, 0), disli_maskesi(S, GEO["disli"]))
    im.alpha_composite(iz, (W - 560, -200))
    s = simge(340)
    im.alpha_composite(s, (90, (H - 340) // 2 - 10))
    ad_yaz(d, (488, 150), yazi_tipi(108, "yari"), (255, 255, 255, 255), renk(marka.VURGU_ACIK))
    d.rounded_rectangle((494, 300, 1110, 306), 3, fill=renk(marka.VURGU))
    d.text((494, 322), marka.SLOGAN, font=yazi_tipi(30), fill=(255, 255, 255, 255))
    f2 = yazi_tipi(22)
    for i, s in enumerate(("Ders programı • İşletmelerde mesleki eğitim • SGK ve e-Bildirge",
                           "Öğrenci ücreti ve devlet katkısı • Ek ders • Devamsızlık",
                           "Resmî belgeler • e-Okul / e-Mesem aktarımı",
                           "Çok kullanıcılı • Kurum lisanslı • Veriler okulda kalır")):
        d.text((494, 384 + 34 * i), s, font=f2, fill=renk(marka.VURGU_ACIK))
    return im.convert("RGB")


def main() -> int:
    out = marka.KLASOR
    out.mkdir(exist_ok=True)
    simge(512).save(marka.SIMGE)
    simge(64, sade=True, olcek=8).save(marka.SIMGE_KUCUK)
    logo_yatay(160).save(marka.LOGO_YATAY)
    acilis().save(marka.ACILIS)

    dag = KOK / "dagitim"
    m = dag / "marka"
    m.mkdir(exist_ok=True)
    for eski in ("hunerver_simge.svg", "hunerver_simge_1024.png", "hunerver_logo.png"):
        (m / eski).unlink(missing_ok=True)
    (m / "meskoord_simge.svg").write_text(svg(), encoding="utf-8")
    simge(1024).save(m / "meskoord_simge_1024.png")
    logo_yatay(320).save(m / "meskoord_logo.png")
    afis().save(m / "tanitim_afisi.png")

    boyutlar = (16, 20, 24, 32, 40, 48, 64, 128, 256)
    resimler = [simge(b, sade=b <= 32, olcek=16 if b <= 32 else 4) for b in boyutlar]
    resimler[-1].save(dag / "meskoord.ico", sizes=[(b, b) for b in boyutlar], append_images=resimler[:-1])
    for ek, olcek in (("", 1.0), ("_150", 1.5), ("_200", 2.0)):
        kurulum_buyuk(olcek).save(dag / f"kurulum_buyuk{ek}.bmp")
    for ek, boyut in (("", 55), ("_150", 83), ("_200", 110)):
        kurulum_kucuk(boyut).save(dag / f"kurulum_kucuk{ek}.bmp")
    for p in (*marka.GORSELLER, dag / "meskoord.ico", m / "meskoord_simge.svg", m / "tanitim_afisi.png"):
        print(p.relative_to(KOK))
    return 0


if __name__ == "__main__":
    sys.exit(main())
