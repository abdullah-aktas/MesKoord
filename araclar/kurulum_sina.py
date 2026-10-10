"""Hazırlanan kurulum dosyasını gerçek bir kurulumla sınar (surum_hazirla.py'den sonra çalıştırın).

    python araclar\\kurulum_sina.py

Geçici bir klasöre sınama lisansı üretir, kurulumu sessiz ve kullanıcıya özel yapar, lisansın
ProgramData'ya kopyalanıp tanındığını ve kurulan programın kendi denetimini geçtiğini kontrol eder,
ardından programı kaldırır ve sınama lisansını siler. Kayıt defterine (lisanslar.csv) bir şey yazmaz.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from koordmes import __version__, config  # noqa: E402


def main() -> int:
    kurulum = KOK / "cikti" / f"MesKoord_{__version__}" / f"MesKoord_Kurulum_{__version__}.exe"
    if not kurulum.is_file():
        raise SystemExit(f"{kurulum} yok; önce araclar\\surum_hazirla.py çalıştırın.")
    T = Path(tempfile.mkdtemp(prefix="meskoord_kurulum_"))
    hatalar = []
    try:
        yon = T / "yonetim"
        yon.mkdir()
        belgeler = Path.home() / "Documents"
        gercek = Path(config.ortam("LISANS_DIZINI") or next(
            (d for d in (belgeler / "MesKoord_Lisans_Yonetimi", belgeler / "KoordMES_Lisans_Yonetimi") if d.is_dir()),
            belgeler / "MesKoord_Lisans_Yonetimi"))
        for pem in gercek.glob("ozel_anahtar_*.pem"):
            shutil.copy(pem, yon)
        for dosya in ("ayarlar.json",):
            if (gercek / dosya).exists():
                shutil.copy(gercek / dosya, yon)
        os.environ.pop("KOORDMES_LISANS_DIZINI", None)
        os.environ["MESKOORD_LISANS_DIZINI"] = str(yon)
        spec = importlib.util.spec_from_file_location("ly", KOK / "araclar" / "lisans_yonetici.py")
        ly = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ly)
        _, lic = ly.lisans_uret("999999", "KURULUM SINAMA OKULU", date.today(), date.today(), duzenleyen="sınama")

        paket = T / "paket"
        paket.mkdir()
        shutil.copy(kurulum, paket)
        shutil.copy(lic, paket)
        hedef = T / "kur"
        r = subprocess.run([str(paket / kurulum.name), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                            "/CURRENTUSER", f"/DIR={hedef}", "/MERGETASKS=!masaustu"], timeout=900)
        print("kurulum çıkış kodu:", r.returncode)
        for ad in ("MesKoord.exe", "LISANS_SOZLESMESI.txt", "UCUNCU_TARAF_LISANSLARI.txt", "KULLANIM_KILAVUZU.pdf",
                   "BENIOKU.txt"):
            if not (hedef / ad).is_file():
                hatalar.append(f"kurulan klasörde {ad} yok")
        kopya = Path(os.environ["PROGRAMDATA"]) / config.AD / lic.name
        if not kopya.is_file():
            hatalar.append("kurulum dosyasının yanındaki lisans ProgramData'ya kopyalanmadı")

        os.environ.pop("KOORDMES_DATA", None)
        os.environ["MESKOORD_DATA"] = str(T / "veri")
        from koordmes import lisans
        bulunan, _ = lisans.bul()
        if not bulunan or bulunan.kurum_kodu != "999999":
            hatalar.append("kurulumla gelen lisans program tarafından görülmedi")

        rapor = T / "rapor.txt"
        subprocess.run([str(hedef / "MesKoord.exe"), "--kendini-sina", str(rapor)], timeout=180)
        metin = rapor.read_text("utf-8") if rapor.exists() else "rapor yok\nHATA"
        print(metin)
        if "HATA" in metin:
            hatalar.append("kurulan program kendi denetiminden geçemedi")

        subprocess.run([str(hedef / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], timeout=300)
        for _ in range(30):
            if not (hedef / "MesKoord.exe").exists():
                break
            time.sleep(1)
        if (hedef / "MesKoord.exe").exists():
            hatalar.append("kaldırma programı dosyaları silmedi")
        if not kopya.is_file():
            hatalar.append("kaldırınca lisans da silindi (korunmalıydı)")
        kopya.unlink(missing_ok=True)
        try:
            kopya.parent.rmdir()
        except OSError:
            pass
    finally:
        shutil.rmtree(T, ignore_errors=True)
    if hatalar:
        print("BAŞARISIZ:\n- " + "\n- ".join(hatalar))
        return 1
    print("BAŞARILI: kurulum, lisansın kendiliğinden yüklenmesi, kendi denetimi ve kaldırma sorunsuz.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
