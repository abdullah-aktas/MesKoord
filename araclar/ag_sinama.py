"""Ağ modunu gerçek programla uçtan uca sınar (geliştirici aracı).

Kullanım:  python araclar/ag_sinama.py
Geçici bir veri klasöründe MesKoord'u sunucu olarak başlatır, ayrı bir süreçten istemci olarak bağlanıp
kayıt ekler, sonra programı kapatır. Gerçek kullanıcı verilerine dokunmaz.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

PAROLA = "deneme-parolasi"
PORT = 47555


def main() -> int:
    veri = Path(tempfile.mkdtemp(prefix="meskoord_ag_"))
    os.environ.pop("KOORDMES_DATA", None)
    os.environ["MESKOORD_DATA"] = str(veri)
    from koordmes.ag import protokol as P
    from koordmes.ag.istemci import BaglantiBilgisi, UzakDatabase, sunucu_bilgisi
    from koordmes.ag.kesif import kesfet
    a = P.AgAyarlari(kip=P.KIP_SUNUCU, port=PORT, sunucu_adi="SINAMA-SUNUCU", parola_ozeti=P.parola_ozeti(PAROLA))
    a.kaydet()
    ortam = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    surec = subprocess.Popen([sys.executable, str(KOK / "run.py")], env=ortam)
    try:
        for _ in range(60):
            try:
                iz, bilgi = sunucu_bilgisi("127.0.0.1", PORT, 1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            print("HATA: sunucu açılmadı")
            return 1
        print("sunucu:", bilgi, "doğrulama kodu:", P.dogrulama_kodu(iz))
        print("keşif:", kesfet(1.0, ek_adresler=["127.0.0.1"]))
        db = UzakDatabase(BaglantiBilgisi("127.0.0.1", PORT, PAROLA, iz, "sinama"))
        db.insert("alanlar", {"ad": "Uçtan Uca Sınama"})
        print("kurum:", db.kurum()["ad"], "| alanlar:", [r["ad"] for r in db.q("SELECT ad FROM alanlar")])
        print("yedek:", db.yedekle())
        db.close()
        print("TAMAM")
        return 0
    finally:
        surec.kill()
        surec.wait(10)


if __name__ == "__main__":
    sys.exit(main())
