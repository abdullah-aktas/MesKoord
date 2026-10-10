"""docs/ altındaki Markdown belgelerinden PDF üretir (kılavuzun basılı/e-posta kopyası için).

    python araclar\\kilavuz_pdf.py                       # bütün belgeler -> cikti\\Belgeler\\
    python araclar\\kilavuz_pdf.py --hedef dist\\MesKoord --yalniz KULLANIM_KILAVUZU

surum_hazirla.py kullanım kılavuzunun PDF'ini pakete bu araçla ekler.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
BELGELER = {
    "KULLANIM_KILAVUZU": "MesKoord Kullanım Kılavuzu",
    "TANITIM": "MesKoord Tanıtım ve Bilgilendirme",
    "DEVIR_TESLIM": "MesKoord Devir Teslim ve Bilgilendirme Dosyası",
    "GELISTIRICI_EL_KITABI": "MesKoord Geliştirici, Bakım ve Dağıtım El Kitabı",
}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--hedef", default=str(KOK / "cikti" / "Belgeler"))
    p.add_argument("--yalniz", nargs="*", choices=list(BELGELER), help="Yalnızca bu belgeler")
    ns = p.parse_args()

    sys.path.insert(0, str(KOK))
    if sys.platform == "win32" and os.environ.get("QT_QPA_PLATFORM") == "offscreen":
        # offscreen eklentisi Windows yazı tiplerini görmez; harfler PDF'e kutu olarak basılır.
        del os.environ["QT_QPA_PLATFORM"]
    from PySide6.QtGui import QGuiApplication, QTextDocument
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])  # noqa: F841  yazı tipleri için gerekli
    from koordmes.ui.kilavuz import belge, pdf_yaz

    hedef = Path(ns.hedef)
    hedef.mkdir(parents=True, exist_ok=True)
    for ad in ns.yalniz or BELGELER:
        kaynak = KOK / "docs" / f"{ad}.md"
        doc = belge(kaynak.read_text("utf-8"))
        doc.setMetaInformation(QTextDocument.DocumentTitle, BELGELER[ad])
        yol = pdf_yaz(doc, hedef / f"{ad}.pdf")
        print(f"   {yol}  ({yol.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
