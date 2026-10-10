"""Dağıtıma hazır MesKoord sürümü üretir.

    python araclar\\surum_hazirla.py                  # mevcut sürümü paketler
    python araclar\\surum_hazirla.py --surum 1.1.0    # sürüm numarasını yükseltip paketler
    python araclar\\surum_hazirla.py --testsiz        # testleri atlar (önerilmez)

Çıktı: cikti\\MesKoord_<sürüm>\\
    MesKoord_Kurulum_<sürüm>.exe   okullara gönderilen kurulum dosyası (Inno Setup kuruluysa)
    MesKoord_<sürüm>_Tasinabilir.zip  kurulumsuz kullanım / yönetici yetkisi olmayan bilgisayarlar
    SHA256SUMS.txt, SURUM_NOTLARI.txt

İsteğe bağlı kod imzalama: MESKOORD_IMZA_KOMUTU (eski adı KOORDMES_IMZA_KOMUTU da olur) ortam değişkenine {dosya} yer tutuculu komut yazın, örn.
    signtool sign /f C:\\sertifika.pfx /p SIFRE /fd sha256 /tr http://timestamp.digicert.com /td sha256 "{dosya}"
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
INIT = KOK / "koordmes" / "__init__.py"
DIST = KOK / "dist" / "MesKoord"
CIKTI = KOK / "cikti"
DAGITIM = KOK / "dagitim"
CALISMA = KOK / "build" / "dagitim"
NOTLAR = KOK / "SURUM_NOTLARI.md"
KOK_PAKETLER = ["PySide6-Essentials", "PySide6-Addons", "openpyxl", "python-docx", "xlrd", "pdfplumber",
                "cryptography"]
LGPL_NOTU = """\
Qt for Python (PySide6) ve Qt kütüphaneleri GNU Lesser General Public License v3 (LGPLv3) ile
lisanslanmıştır. MesKoord bu kütüphaneleri değiştirmeden ve dinamik bağlı olarak kullanır; Qt DLL
dosyaları program klasörünün _internal\\PySide6 alt klasöründe ayrı dosyalar olarak bulunur ve
kullanıcı tarafından LGPLv3 uyumlu başka bir sürümle değiştirilebilir.
Kaynak kod: https://code.qt.io  ·  Lisans metni: https://www.gnu.org/licenses/lgpl-3.0.html

Qt WebEngine, Chromium projesini ve onun üçüncü taraf bileşenlerini içerir. Bu bileşenlerin lisans
bildirimleri: https://doc.qt.io/qt-6/qtwebengine-licensing.html

Program, PyInstaller ile paketlenmiştir (GPLv2, paketlenen programlar için istisnalı):
https://pyinstaller.org/en/stable/license.html
"""


def adim(metin: str) -> None:
    print(f"\n==> {metin}", flush=True)


def surum_oku() -> str:
    return re.search(r'__version__\s*=\s*"([^"]+)"', INIT.read_text("utf-8")).group(1)


def yayinci_oku() -> str:
    return re.search(r'APP_PUBLISHER\s*=\s*"([^"]+)"', INIT.read_text("utf-8")).group(1)


def guncelleme_adresi_oku() -> str:
    m = re.search(r'^GUNCELLEME_ADRESI\s*=\s*"([^"]*)"', INIT.read_text("utf-8"), re.M)
    return m.group(1) if m else ""


def surum_yaz(yeni: str) -> None:
    if not re.fullmatch(r"\d+\.\d+\.\d+", yeni):
        raise SystemExit("Sürüm X.Y.Z biçiminde olmalı (örn. 1.2.0).")
    INIT.write_text(re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{yeni}"', INIT.read_text("utf-8")),
                    encoding="utf-8")
    metin = NOTLAR.read_text("utf-8") if NOTLAR.exists() else "# MesKoord Sürüm Notları\n"
    if f"## {yeni}" not in metin:
        bas, _, son = metin.partition("\n")
        metin = f"{bas}\n\n## {yeni}\n- (Bu sürümdeki değişiklikleri yazın)\n{son}"
        NOTLAR.write_text(metin, encoding="utf-8")
        print(f"SURUM_NOTLARI.md içine '{yeni}' başlığı eklendi; değişiklikleri yazmayı unutmayın.")


def on_denetim() -> list[str]:
    sys.path.insert(0, str(KOK))
    from koordmes import lisans
    uyarilar = []
    if not lisans.ACIK_ANAHTARLAR:
        raise SystemExit("koordmes/lisans.py içinde açık anahtar yok; hiçbir lisans doğrulanamaz.")
    pem = [p for p in KOK.rglob("*.pem") if ".venv" not in p.parts]
    if pem:
        raise SystemExit("Proje klasöründe özel anahtar (.pem) var, pakete sızabilir: " + ", ".join(map(str, pem)))
    if not any(lisans.SATICI.values()):
        uyarilar.append("koordmes/lisans.py SATICI bilgileri boş: lisans penceresinde iletişim bilgisi görünmez.")
    if yayinci_oku() in ("KoordMES", "MesKoord"):
        uyarilar.append("koordmes/__init__.py APP_PUBLISHER döner sermaye işletmesinin adı değil; adı yazın.")
    if "[OKUL ADI]" in (DAGITIM / "LISANS_SOZLESMESI.txt").read_text("utf-8"):
        uyarilar.append("dagitim/LISANS_SOZLESMESI.txt içindeki [köşeli parantezli] yerler doldurulmamış.")
    if not guncelleme_adresi_oku():
        uyarilar.append("koordmes/__init__.py GUNCELLEME_ADRESI boş: okullardaki program yeni sürümü kendisi "
                        "duyuramaz (surum.json yine üretilir).")
    return uyarilar


def calistir(komut: list[str], **kw) -> None:
    print("   " + " ".join(f'"{k}"' if " " in k else k for k in komut), flush=True)
    subprocess.run(komut, cwd=KOK, check=True, **kw)


def imzala(dosya: Path) -> None:
    komut = os.environ.get("MESKOORD_IMZA_KOMUTU") or os.environ.get("KOORDMES_IMZA_KOMUTU")
    if komut:
        print(f"   imzalanıyor: {dosya.name}")
        subprocess.run(komut.replace("{dosya}", str(dosya)), shell=True, check=True)


def bagimliliklar(kokler: list[str]) -> list[metadata.Distribution]:
    gorulen: dict[str, metadata.Distribution] = {}
    kuyruk = list(kokler)
    while kuyruk:
        ad = kuyruk.pop()
        anahtar = re.sub(r"[-_.]+", "-", ad).lower()
        if anahtar in gorulen:
            continue
        try:
            d = metadata.distribution(ad)
        except metadata.PackageNotFoundError:
            continue
        gorulen[anahtar] = d
        for gerek in d.requires or []:
            if "extra ==" in gerek:
                continue
            if ";" in gerek and "sys_platform" in gerek and "win32" not in gerek and "!=" not in gerek:
                continue
            kuyruk.append(re.split(r"[ ;<>=!~\[(]", gerek.strip(), maxsplit=1)[0])
    return sorted(gorulen.values(), key=lambda d: d.metadata["Name"].lower())


def ucuncu_taraf_metni() -> str:
    parcalar = ["MesKoord - ÜÇÜNCÜ TARAF YAZILIM LİSANSLARI", "=" * 60, "", LGPL_NOTU, "=" * 60, ""]
    for d in bagimliliklar(KOK_PAKETLER):
        m = d.metadata
        lisans = m.get("License-Expression") or (m.get("License") or "").splitlines()[0:1]
        lisans = lisans if isinstance(lisans, str) else (lisans[0] if lisans else "")
        siniflar = [c.split("::")[-1].strip() for c in m.get_all("Classifier") or [] if c.startswith("License ::")]
        parcalar += [f"{m['Name']} {m['Version']}", f"  Lisans: {lisans or ', '.join(siniflar) or 'paket bilgisine bakınız'}",
                     f"  Adres: {m.get('Home-page') or next((u.split(',', 1)[-1].strip() for u in m.get_all('Project-URL') or []), '')}"]
        for f in d.files or []:
            ad = f.name.upper()
            if ad.startswith(("LICENSE", "LICENCE", "COPYING", "NOTICE")) and f.suffix in ("", ".txt", ".md", ".rst"):
                try:
                    metin = Path(f.locate()).read_text(encoding="utf-8", errors="replace").strip()
                    parcalar += ["", f"  --- {f.name} ---", metin]
                except (OSError, FileNotFoundError):
                    pass
        parcalar += ["", "-" * 60, ""]
    return "\n".join(parcalar) + "\n"


def iscc_bul() -> Path | None:
    adaylar = [os.environ.get("INNO_ISCC", ""), shutil.which("iscc") or ""]
    for kok in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        if kok:
            adaylar.append(os.path.join(kok, "Inno Setup 6", "ISCC.exe"))
    return next((Path(a) for a in adaylar if a and Path(a).is_file()), None)


def bom_ile(kaynak: Path, hedef: Path) -> Path:
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(kaynak.read_text("utf-8"), encoding="utf-8-sig")
    return hedef


def sha256(yol: Path) -> str:
    h = hashlib.sha256()
    with yol.open("rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def surum_notu(surum: str) -> str:
    if not NOTLAR.exists():
        return ""
    m = re.search(rf"^## {re.escape(surum)}\b.*?(?=^## |\Z)", NOTLAR.read_text("utf-8"), re.S | re.M)
    return m.group(0).strip() + "\n" if m else ""


def main() -> int:
    p = argparse.ArgumentParser(description="MesKoord dağıtım paketi hazırlar")
    p.add_argument("--surum", help="Yeni sürüm numarası (X.Y.Z)")
    p.add_argument("--testsiz", action="store_true")
    p.add_argument("--kurulumsuz", action="store_true", help="Inno Setup adımını atla")
    p.add_argument("--indirme-adresi", default="",
                   help="Kurulum dosyasının yayımlanacağı tam adres (surum.json içine yazılır). Verilmezse "
                        "GUNCELLEME_ADRESI'nden türetilir.")
    ns = p.parse_args()
    py = sys.executable

    if ns.surum:
        surum_yaz(ns.surum)
    surum = surum_oku()
    adim(f"MesKoord {surum} hazırlanıyor")
    uyarilar = on_denetim()
    for u in uyarilar:
        print(f"   UYARI: {u}")

    if not ns.testsiz:
        adim("Testler")
        calistir([py, "-m", "pytest", "-q", "-p", "no:cacheprovider"])

    adim("PyInstaller paketi (dist\\MesKoord)")
    calistir([py, "-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "WARN", "MesKoord.spec"])
    exe = DIST / "MesKoord.exe"

    adim("Belgeler ve lisans bildirimleri")
    (DIST / "UCUNCU_TARAF_LISANSLARI.txt").write_text(ucuncu_taraf_metni(), encoding="utf-8-sig")
    bom_ile(DAGITIM / "LISANS_SOZLESMESI.txt", DIST / "LISANS_SOZLESMESI.txt")
    bom_ile(KOK / "README.md", DIST / "BENIOKU.txt")
    calistir([py, str(KOK / "araclar" / "kilavuz_pdf.py"), "--hedef", str(DIST), "--yalniz", "KULLANIM_KILAVUZU"])
    if NOTLAR.exists():
        bom_ile(NOTLAR, DIST / "SURUM_NOTLARI.txt")

    adim("Paketin kendini sınaması")
    with tempfile.TemporaryDirectory() as td:
        rapor = Path(td) / "rapor.txt"
        r = subprocess.run([str(exe), "--kendini-sina", str(rapor)], timeout=180,
                           env={**os.environ, "MESKOORD_DATA": td})
        print(rapor.read_text("utf-8") if rapor.exists() else "   rapor üretilmedi")
        if r.returncode != 0:
            raise SystemExit("Paketlenmiş program kendi denetiminden geçemedi; yukarıdaki HATA satırlarına bakın.")
    imzala(exe)

    hedef = CIKTI / f"MesKoord_{surum}"
    if hedef.exists():
        shutil.rmtree(hedef)
    hedef.mkdir(parents=True)

    adim("Taşınabilir zip")
    zip_yolu = Path(shutil.make_archive(str(hedef / f"MesKoord_{surum}_Tasinabilir"), "zip", DIST.parent,
                                        DIST.name))
    print(f"   {zip_yolu.name}  {zip_yolu.stat().st_size / 1e6:.0f} MB")

    kurulum = None
    if not ns.kurulumsuz:
        adim("Kurulum dosyası (Inno Setup)")
        iscc = iscc_bul()
        if iscc is None:
            print("   Inno Setup 6 bulunamadı; yalnızca taşınabilir zip üretildi.\n"
                  "   Kurmak için:  winget install JRSoftware.InnoSetup")
        else:
            sozlesme = bom_ile(DAGITIM / "LISANS_SOZLESMESI.txt", CALISMA / "LISANS_SOZLESMESI.txt")
            iss = bom_ile(DAGITIM / "MesKoord.iss", DAGITIM / "_derleme.iss")
            try:
                calistir([str(iscc), "/Q", f"/DAppVersion={surum}", f"/DAppPublisher={yayinci_oku()}",
                          f"/DSourceDir={DIST}", f"/DOutputDir={hedef}", f"/DLicenseText={sozlesme}", str(iss)])
            finally:
                iss.unlink(missing_ok=True)
            kurulum = hedef / f"MesKoord_Kurulum_{surum}.exe"
            imzala(kurulum)
            print(f"   {kurulum.name}  {kurulum.stat().st_size / 1e6:.0f} MB")

    (hedef / "SURUM_NOTLARI.txt").write_text(surum_notu(surum) or f"MesKoord {surum}\n", encoding="utf-8-sig")
    (hedef / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(f)}  {f.name}\n" for f in sorted(hedef.iterdir()) if f.suffix in (".exe", ".zip")),
        encoding="utf-8")
    if kurulum is not None:
        sys.path.insert(0, str(KOK))
        from koordmes.services import guncelleme
        indir_adresi = ns.indirme_adresi or guncelleme.indirme_adresi(guncelleme_adresi_oku(), kurulum.name, surum)
        (hedef / "surum.json").write_text(
            guncelleme.surum_json(surum, indir_adresi, sha256(kurulum), surum_notu(surum)), encoding="utf-8")
        adim("Güncelleme bilgisi (surum.json)")
        print(f"   Yayımlayın: {kurulum.name} → {indir_adresi or '(adres verilmedi: --indirme-adresi)'}")
        print(f"   ve surum.json → {guncelleme_adresi_oku() or '(GUNCELLEME_ADRESI boş)'}")
        print("   surum.json kurulum dosyasından SONRA yüklenmeli; okullar ancak o zaman yeni sürümü görür.")

    adim("TAMAMLANDI")
    print(f"   {hedef}")
    for u in uyarilar:
        print(f"   UYARI: {u}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
