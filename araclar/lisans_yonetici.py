"""MesKoord Lisans Yöneticisi - yalnızca döner sermaye işletmesinde/lisansı veren birimde çalıştırılır.

Bu araç ve özel anahtar ASLA okullara dağıtılan pakete konmaz.

Arayüzle:          python araclar/lisans_yonetici.py
Komut satırıyla:   python araclar/lisans_yonetici.py uret --kurum-kodu 123456 --kurum-adi "..." --bitis 2027-08-31
                   python araclar/lisans_yonetici.py anahtar-olustur --koda-yaz
                   python araclar/lisans_yonetici.py dogrula dosya.lic
                   python araclar/lisans_yonetici.py liste
                   python araclar/lisans_yonetici.py sifre-degistir
"""
from __future__ import annotations

import argparse
import base64
import csv
import getpass
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from koordmes import config, lisans  # noqa: E402

KAYIT_ALANLARI = ["lisans_no", "duzenleme", "kurum_kodu", "kurum_adi", "il", "ilce", "baslangic", "bitis",
                  "fatura_no", "tutar", "yetkili", "telefon", "eposta", "not", "dosya"]
VARSAYILAN_KIMLIK = "KM1"


def yonetim_dizini() -> Path:
    ozel = config.ortam("LISANS_DIZINI")
    if ozel:
        d = Path(ozel)
    else:
        belgeler = Path.home() / "Documents"
        d = config.tasi(belgeler / "MesKoord_Lisans_Yonetimi", belgeler / "KoordMES_Lisans_Yonetimi")
    d.mkdir(parents=True, exist_ok=True)
    return d


def ayarlar_yolu() -> Path:
    return yonetim_dizini() / "ayarlar.json"


def ayarlar() -> dict:
    try:
        return json.loads(ayarlar_yolu().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ayar_yaz(**kw) -> None:
    a = ayarlar()
    a.update(kw)
    ayarlar_yolu().write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")


def anahtar_yolu(kimlik: str) -> Path:
    return yonetim_dizini() / f"ozel_anahtar_{kimlik}.pem"


def etkin_kimlik() -> str:
    return ayarlar().get("anahtar_kimligi", VARSAYILAN_KIMLIK)


def acik_anahtar_metni(ozel: Ed25519PrivateKey) -> str:
    ham = ozel.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(ham).decode("ascii")


def _pem(ozel: Ed25519PrivateKey, sifre: str | None) -> bytes:
    sifreleme = (serialization.BestAvailableEncryption(sifre.encode("utf-8")) if sifre
                 else serialization.NoEncryption())
    return ozel.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, sifreleme)


def koda_yaz(kimlik: str, acik: str) -> Path:
    """Açık anahtarı koordmes/lisans.py içindeki ACIK_ANAHTARLAR sözlüğüne ekler."""
    yol = KOK / "koordmes" / "lisans.py"
    metin = yol.read_text(encoding="utf-8")
    if f'"{kimlik}"' in metin.split("ACIK_ANAHTARLAR", 1)[1].split("}", 1)[0]:
        raise SystemExit(f"{kimlik} kimlikli anahtar koordmes/lisans.py içinde zaten var.")
    metin = metin.replace("ACIK_ANAHTARLAR: dict[str, str] = {\n",
                          f'ACIK_ANAHTARLAR: dict[str, str] = {{\n    "{kimlik}": "{acik}",\n', 1)
    yol.write_text(metin, encoding="utf-8")
    return yol


def anahtar_olustur(kimlik: str, sifre: str | None) -> tuple[Path, str]:
    yol = anahtar_yolu(kimlik)
    if yol.exists():
        raise SystemExit(f"{yol} zaten var. Mevcut anahtarın üzerine yazılmaz; farklı bir --kimlik verin.")
    ozel = Ed25519PrivateKey.generate()
    yol.write_bytes(_pem(ozel, sifre))
    ayar_yaz(anahtar_kimligi=kimlik)
    return yol, acik_anahtar_metni(ozel)


def ozel_anahtar_yukle(kimlik: str | None = None, sifre_sor=None) -> tuple[Ed25519PrivateKey, str]:
    kimlik = kimlik or etkin_kimlik()
    yol = anahtar_yolu(kimlik)
    if not yol.exists():
        raise SystemExit(f"Özel anahtar bulunamadı: {yol}\nYedeğinizdeki ozel_anahtar_{kimlik}.pem dosyasını "
                         f"{yonetim_dizini()} klasörüne kopyalayın.")
    pem = yol.read_bytes()
    try:
        ozel = serialization.load_pem_private_key(pem, password=None)
    except TypeError:
        sifre = (sifre_sor or (lambda: getpass.getpass("Özel anahtar şifresi: ")))()
        if not sifre:
            raise SystemExit("Şifre girilmedi.")
        try:
            ozel = serialization.load_pem_private_key(pem, password=sifre.encode("utf-8"))
        except ValueError:
            raise SystemExit("Özel anahtar şifresi yanlış.") from None
    acik = acik_anahtar_metni(ozel)
    if lisans.ACIK_ANAHTARLAR.get(kimlik) != acik:
        raise SystemExit(f"Bu özel anahtar programdaki '{kimlik}' açık anahtarıyla eşleşmiyor. Bu anahtarla "
                         "verilen lisansları program kabul etmez.")
    return ozel, kimlik


def sifre_degistir(kimlik: str | None, eski_sor, yeni: str | None) -> Path:
    ozel, kimlik = ozel_anahtar_yukle(kimlik, eski_sor)
    yol = anahtar_yolu(kimlik)
    yol.write_bytes(_pem(ozel, yeni))
    return yol


def kayit_yolu() -> Path:
    return yonetim_dizini() / "lisanslar.csv"


def kayitlar() -> list[dict]:
    if not kayit_yolu().exists():
        return []
    with kayit_yolu().open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def sonraki_lisans_no(yil: int | None = None) -> str:
    yil = yil or date.today().year
    onek = f"KM-{yil}-"
    sayilar = [int(k["lisans_no"][len(onek):]) for k in kayitlar()
               if k.get("lisans_no", "").startswith(onek) and k["lisans_no"][len(onek):].isdigit()]
    return f"{onek}{max(sayilar, default=0) + 1:04d}"


def _dosya_adi(s: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", s, flags=re.UNICODE).strip("_")
    return s[:60] or "kurum"


def lisans_uret(kurum_kodu: str, kurum_adi: str, baslangic: date, bitis: date | None, il: str = "",
                ilce: str = "", fatura_no: str = "", tutar: str = "", yetkili: str = "", telefon: str = "",
                eposta: str = "", not_: str = "", duzenleyen: str | None = None, sifre_sor=None) -> tuple[dict, Path]:
    kurum_kodu, kurum_adi = kurum_kodu.strip(), " ".join(kurum_adi.split())
    if not kurum_kodu.isdigit():
        raise SystemExit("Kurum kodu yalnızca rakamlardan oluşmalıdır (MEB kurum kodu).")
    if not kurum_adi:
        raise SystemExit("Kurum adı boş olamaz.")
    if bitis and bitis < baslangic:
        raise SystemExit("Bitiş tarihi başlangıçtan önce olamaz.")
    ozel, kimlik = ozel_anahtar_yukle(sifre_sor=sifre_sor)
    duzenleyen = duzenleyen if duzenleyen is not None else ayarlar().get("duzenleyen", "")
    veri = {
        "surum": 1,
        "lisans_no": sonraki_lisans_no(),
        "kurum_kodu": kurum_kodu,
        "kurum_adi": kurum_adi,
        "il": il.strip(),
        "ilce": ilce.strip(),
        "kapsam": "Kurum lisansı - kurumun bütün bilgisayarlarında kullanılabilir",
        "baslangic": baslangic.isoformat(),
        "bitis": bitis.isoformat() if bitis else "",
        "duzenleme": date.today().isoformat(),
        "duzenleyen": duzenleyen.strip(),
    }
    veri = lisans.imzala(veri, ozel, kimlik)
    lisans.dogrula(veri)

    klasor = yonetim_dizini() / "Verilen_Lisanslar"
    klasor.mkdir(exist_ok=True)
    taban = f"{veri['lisans_no']}_{kurum_kodu}_{_dosya_adi(kurum_adi)}"
    yol = klasor / f"{taban}.lic"
    yol.write_text(lisans.dosya_metni(veri), encoding="utf-8")
    (klasor / f"{taban}_KOD.txt").write_text(teslim_metni(veri), encoding="utf-8")

    yeni = not kayit_yolu().exists()
    with kayit_yolu().open("a", encoding="utf-8-sig" if yeni else "utf-8", newline="") as f:
        w = csv.DictWriter(f, KAYIT_ALANLARI, delimiter=";")
        if yeni:
            w.writeheader()
        w.writerow({"lisans_no": veri["lisans_no"], "duzenleme": veri["duzenleme"], "kurum_kodu": kurum_kodu,
                    "kurum_adi": kurum_adi, "il": veri["il"], "ilce": veri["ilce"], "baslangic": veri["baslangic"],
                    "bitis": veri["bitis"] or "süresiz", "fatura_no": fatura_no, "tutar": tutar, "yetkili": yetkili,
                    "telefon": telefon, "eposta": eposta, "not": not_, "dosya": yol.name})
    return veri, yol


def teslim_metni(veri: dict) -> str:
    lis = lisans.Lisans(veri)
    return (f"MESKOORD LİSANSI\n\n{lis.ozet()}\n\n"
            "KURULUM\n"
            "1. Yöntem (önerilen): .lic dosyasını MesKoord_Kurulum_*.exe dosyasıyla aynı klasöre koyup kurulumu\n"
            "   çalıştırın. Lisans o bilgisayarın bütün kullanıcıları için kendiliğinden yüklenir. Aynı klasör\n"
            "   (USB bellek veya okul ağındaki paylaşım) kurumdaki bütün bilgisayarlarda kullanılabilir.\n"
            "2. Yöntem: Program açıkken Yardım > Lisans Bilgileri > 'Lisans Dosyası Yükle' ile .lic dosyasını\n"
            "   seçin ya da aşağıdaki lisans kodunun tamamını kopyalayıp 'Lisans Kodunu Yapıştır'a yapıştırın.\n\n"
            f"LİSANS KODU\n{lisans.kodla(veri)}\n")


def _tarih_al(s: str | None) -> date | None:
    if not s or s.strip().lower() in ("", "suresiz", "süresiz"):
        return None
    s = s.strip()
    for bicim in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, bicim).date()
        except ValueError:
            pass
    raise SystemExit(f"Tarih anlaşılamadı: {s} (GG.AA.YYYY veya YYYY-AA-GG yazın)")


def egitim_yili_bitisi(bugun: date | None = None) -> date:
    bugun = bugun or date.today()
    return date(bugun.year + (1 if bugun.month >= 9 else 0), 8, 31)


# ---------------------------------------------------------------------- arayüz

def arayuz() -> int:
    from PySide6.QtCore import QDate, Qt
    from PySide6.QtWidgets import (QApplication, QCheckBox, QDateEdit, QFileDialog, QFormLayout, QHBoxLayout,
                                   QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                                   QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    def sifre_sor():
        s, ok = QInputDialog.getText(None, "Özel anahtar şifresi", "Özel anahtar şifresi:", QLineEdit.Password)
        return s if ok else ""

    def calistir(fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except SystemExit as e:
            QMessageBox.warning(pencere, "Lisans Yöneticisi", str(e))
        return None

    pencere = QTabWidget()
    pencere.setWindowTitle("MesKoord Lisans Yöneticisi - YALNIZCA DÖNER SERMAYE")
    pencere.resize(900, 640)

    # --- lisans üret
    sayfa = QWidget()
    lay = QVBoxLayout(sayfa)
    lay.addWidget(QLabel("Kurumun gönderdiği lisans talebini aşağıya yapıştırırsanız form kendiliğinden dolar."))
    talep = QPlainTextEdit()
    talep.setPlaceholderText("MesKoord LİSANS TALEBİ metni...")
    talep.setMaximumHeight(110)
    lay.addWidget(talep)
    f = QFormLayout()
    alan = {k: QLineEdit() for k in ("kurum_kodu", "kurum_adi", "il", "ilce", "yetkili", "telefon", "eposta",
                                     "fatura_no", "tutar", "not", "duzenleyen")}
    alan["duzenleyen"].setText(ayarlar().get("duzenleyen", ""))
    bas, bit = QDateEdit(QDate.currentDate()), QDateEdit()
    eb = egitim_yili_bitisi()
    bit.setDate(QDate(eb.year, eb.month, eb.day))
    for d in (bas, bit):
        d.setCalendarPopup(True)
        d.setDisplayFormat("dd.MM.yyyy")
    suresiz = QCheckBox("Süresiz")
    suresiz.toggled.connect(lambda v: bit.setEnabled(not v))
    satir_bit = QHBoxLayout()
    satir_bit.addWidget(bit)
    satir_bit.addWidget(suresiz)
    satir_bit.addStretch()
    for k, etiket in [("kurum_kodu", "MEB Kurum Kodu *"), ("kurum_adi", "Kurum Adı *"), ("il", "İl"),
                      ("ilce", "İlçe")]:
        f.addRow(etiket, alan[k])
    f.addRow("Başlangıç", bas)
    f.addRow("Bitiş", satir_bit)
    for k, etiket in [("yetkili", "Yetkili"), ("telefon", "Telefon"), ("eposta", "E-posta"),
                      ("fatura_no", "Fatura / Makbuz No"), ("tutar", "Tutar (TL)"), ("not", "Not"),
                      ("duzenleyen", "Düzenleyen (döner sermaye işletmesi)")]:
        f.addRow(etiket, alan[k])
    lay.addLayout(f)
    sonuc = QPlainTextEdit()
    sonuc.setReadOnly(True)

    def talepten_doldur():
        for k, v in lisans.talep_coz(talep.toPlainText()).items():
            if k in alan and v:
                alan[k].setText(v)

    talep.textChanged.connect(talepten_doldur)

    def uret():
        if not alan["kurum_kodu"].text().strip() or not alan["kurum_adi"].text().strip():
            QMessageBox.warning(pencere, "Eksik bilgi", "Kurum kodu ve kurum adı zorunludur.")
            return
        bitis = None if suresiz.isChecked() else bit.date().toPython()
        ozet = (f"{alan['kurum_adi'].text()} ({alan['kurum_kodu'].text()})\n"
                f"{bas.date().toPython():%d.%m.%Y} - {bitis.strftime('%d.%m.%Y') if bitis else 'süresiz'}\n\n"
                "Kurum kodu ve adı lisansa kilitlenir; resmî belgelerde bu ad görünür. Doğru mu?")
        if QMessageBox.question(pencere, "Lisans üretilsin mi?", ozet) != QMessageBox.Yes:
            return
        ayar_yaz(duzenleyen=alan["duzenleyen"].text().strip())
        r = calistir(lisans_uret, alan["kurum_kodu"].text(), alan["kurum_adi"].text(), bas.date().toPython(),
                     bitis, il=alan["il"].text(), ilce=alan["ilce"].text(), fatura_no=alan["fatura_no"].text(),
                     tutar=alan["tutar"].text(), yetkili=alan["yetkili"].text(), telefon=alan["telefon"].text(),
                     eposta=alan["eposta"].text(), not_=alan["not"].text(),
                     duzenleyen=alan["duzenleyen"].text(), sifre_sor=sifre_sor)
        if r:
            veri, yol = r
            sonuc.setPlainText(teslim_metni(veri) + f"\nDosya: {yol}")
            liste_doldur()
            QMessageBox.information(pencere, "Lisans üretildi",
                                    f"{veri['lisans_no']} üretildi.\n\n{yol}\n\nKurum'a .lic dosyasını ve "
                                    "_KOD.txt dosyasını gönderin.")

    alt = QHBoxLayout()
    b = QPushButton("Lisans Üret")
    b.setStyleSheet("font-weight:bold; padding:6px 18px")
    b.clicked.connect(uret)
    alt.addWidget(b)
    b2 = QPushButton("Verilen Lisanslar Klasörünü Aç")
    b2.clicked.connect(lambda: os.startfile(str(yonetim_dizini() / "Verilen_Lisanslar"))
                       if (yonetim_dizini() / "Verilen_Lisanslar").exists() else None)
    alt.addWidget(b2)
    alt.addStretch()
    lay.addLayout(alt)
    lay.addWidget(sonuc, 1)
    pencere.addTab(sayfa, "Lisans Üret")

    # --- kayıt defteri
    sayfa2 = QWidget()
    lay2 = QVBoxLayout(sayfa2)
    tablo = QTableWidget()
    tablo.setEditTriggers(QTableWidget.NoEditTriggers)
    lay2.addWidget(tablo)

    def liste_doldur():
        k = kayitlar()
        tablo.setColumnCount(len(KAYIT_ALANLARI))
        tablo.setHorizontalHeaderLabels(KAYIT_ALANLARI)
        tablo.setRowCount(len(k))
        for i, r in enumerate(reversed(k)):
            for j, a in enumerate(KAYIT_ALANLARI):
                tablo.setItem(i, j, QTableWidgetItem(r.get(a, "")))
        tablo.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

    liste_doldur()
    b3 = QPushButton("Kayıt Defterini Excel'de Aç (lisanslar.csv)")
    b3.clicked.connect(lambda: os.startfile(str(kayit_yolu())) if kayit_yolu().exists() else None)
    lay2.addWidget(b3, alignment=Qt.AlignLeft)
    pencere.addTab(sayfa2, "Verilen Lisanslar")

    # --- doğrula / anahtar
    sayfa3 = QWidget()
    lay3 = QVBoxLayout(sayfa3)
    bilgi = QLabel()
    bilgi.setWordWrap(True)
    bilgi.setTextInteractionFlags(Qt.TextSelectableByMouse)
    lay3.addWidget(bilgi)

    def bilgi_yaz():
        kimlik = etkin_kimlik()
        var = anahtar_yolu(kimlik).exists()
        bilgi.setText(f"<b>Yönetim klasörü:</b> {yonetim_dizini()}<br><b>Etkin anahtar:</b> {kimlik} "
                      f"({'var' if var else '<span style=color:#b00020>BULUNAMADI</span>'})<br><br>"
                      "Özel anahtar dosyasını (ozel_anahtar_*.pem) en az iki ayrı USB belleğe yedekleyin ve "
                      "kilitli dolapta saklayın. Kaybolursa yeni lisans üretilemez; başkasının eline geçerse "
                      "sahte lisans üretilebilir.")

    bilgi_yaz()

    def dogrula_sec():
        yol, _ = QFileDialog.getOpenFileName(pencere, "Lisans dosyası", str(yonetim_dizini()), "Lisans (*.lic)")
        if yol:
            try:
                QMessageBox.information(pencere, "Geçerli", lisans.oku(Path(yol)).ozet())
            except lisans.LisansHatasi as e:
                QMessageBox.warning(pencere, "Geçersiz", str(e))

    def sifre_degistir_ui():
        yeni, ok = QInputDialog.getText(pencere, "Yeni şifre", "Yeni şifre (boş bırakılırsa şifre kaldırılır):",
                                        QLineEdit.Password)
        if not ok:
            return
        if yeni:
            tekrar, ok = QInputDialog.getText(pencere, "Yeni şifre", "Yeni şifre (tekrar):", QLineEdit.Password)
            if not ok or tekrar != yeni:
                QMessageBox.warning(pencere, "Şifre", "Şifreler aynı değil.")
                return
        if calistir(sifre_degistir, None, sifre_sor, yeni or None):
            QMessageBox.information(pencere, "Şifre", "Özel anahtar şifresi güncellendi. Yedeklerinizi de yenileyin.")

    for metin, fn in [("Bir Lisans Dosyasını Doğrula...", dogrula_sec),
                      ("Özel Anahtar Şifresini Değiştir...", sifre_degistir_ui),
                      ("Yönetim Klasörünü Aç", lambda: os.startfile(str(yonetim_dizini())))]:
        bb = QPushButton(metin)
        bb.clicked.connect(fn)
        lay3.addWidget(bb, alignment=Qt.AlignLeft)
    lay3.addStretch()
    pencere.addTab(sayfa3, "Anahtar ve Doğrulama")

    pencere.show()
    return app.exec()


# ---------------------------------------------------------------------- komut satırı

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        return arayuz()
    p = argparse.ArgumentParser(prog="lisans_yonetici", description="MesKoord Lisans Yöneticisi")
    alt = p.add_subparsers(dest="komut", required=True)
    a = alt.add_parser("anahtar-olustur", help="Yeni imza anahtarı üretir")
    a.add_argument("--kimlik", default=VARSAYILAN_KIMLIK)
    a.add_argument("--sifreli", action="store_true", help="Özel anahtarı şifreyle korur (önerilir)")
    a.add_argument("--koda-yaz", action="store_true", help="Açık anahtarı koordmes/lisans.py'ye ekler")
    u = alt.add_parser("uret", help="Lisans üretir")
    u.add_argument("--kurum-kodu", required=True)
    u.add_argument("--kurum-adi", required=True)
    u.add_argument("--il", default="")
    u.add_argument("--ilce", default="")
    u.add_argument("--baslangic", default=date.today().isoformat())
    g = u.add_mutually_exclusive_group()
    g.add_argument("--bitis", help="GG.AA.YYYY veya YYYY-AA-GG; verilmezse eğitim-öğretim yılı sonu (31 Ağustos)")
    g.add_argument("--suresiz", action="store_true")
    for x in ("fatura-no", "tutar", "yetkili", "telefon", "eposta", "not", "duzenleyen"):
        u.add_argument(f"--{x}", default=None if x == "duzenleyen" else "")
    d = alt.add_parser("dogrula", help="Bir lisans dosyasını doğrular")
    d.add_argument("dosya")
    alt.add_parser("liste", help="Verilen lisansları listeler")
    s = alt.add_parser("sifre-degistir", help="Özel anahtarın şifresini değiştirir veya ekler")
    s.add_argument("--kimlik")
    ns = p.parse_args(argv)

    if ns.komut == "anahtar-olustur":
        sifre = None
        if ns.sifreli:
            sifre = getpass.getpass("Yeni şifre: ")
            if sifre != getpass.getpass("Yeni şifre (tekrar): "):
                raise SystemExit("Şifreler aynı değil.")
        yol, acik = anahtar_olustur(ns.kimlik, sifre)
        print(f"Özel anahtar: {yol}\nAçık anahtar ({ns.kimlik}): {acik}")
        if ns.koda_yaz:
            print(f"Açık anahtar eklendi: {koda_yaz(ns.kimlik, acik)}")
        else:
            print(f'koordmes/lisans.py ACIK_ANAHTARLAR sözlüğüne ekleyin:  "{ns.kimlik}": "{acik}",')
        print("ÖZEL ANAHTARI EN AZ İKİ AYRI USB BELLEĞE YEDEKLEYİN.")
    elif ns.komut == "uret":
        bitis = None if ns.suresiz else (_tarih_al(ns.bitis) if ns.bitis else egitim_yili_bitisi())
        veri, yol = lisans_uret(ns.kurum_kodu, ns.kurum_adi, _tarih_al(ns.baslangic), bitis, il=ns.il,
                                ilce=ns.ilce, fatura_no=ns.fatura_no, tutar=ns.tutar, yetkili=ns.yetkili,
                                telefon=ns.telefon, eposta=ns.eposta, not_=getattr(ns, "not"),
                                duzenleyen=ns.duzenleyen)
        print(teslim_metni(veri))
        print(f"Dosya: {yol}")
    elif ns.komut == "dogrula":
        try:
            print(lisans.oku(Path(ns.dosya)).ozet())
        except lisans.LisansHatasi as e:
            print(f"GEÇERSİZ: {e}")
            return 1
    elif ns.komut == "liste":
        for k in kayitlar():
            print(f"{k['lisans_no']}  {k['kurum_kodu']}  {k['kurum_adi']}  {k['baslangic']} - {k['bitis']}  "
                  f"{k.get('fatura_no', '')}")
    elif ns.komut == "sifre-degistir":
        yeni = getpass.getpass("Yeni şifre (boş = şifresiz): ")
        if yeni and yeni != getpass.getpass("Yeni şifre (tekrar): "):
            raise SystemExit("Şifreler aynı değil.")
        print(f"Güncellendi: {sifre_degistir(ns.kimlik, None, yeni or None)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
