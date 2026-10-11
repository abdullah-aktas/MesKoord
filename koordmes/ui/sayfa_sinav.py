"""Sınav planlama: dönem, seans çizelgesi, sınavlar ve öğrenciler, öğretmenler, salonlar, planlama ve çıktılar."""
from __future__ import annotations

import re
from collections import Counter
from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog,
                               QDialogButtonBox, QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
                               QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
                               QPlainTextEdit, QPushButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from .. import config
from ..mevzuat import AYLAR
from ..services import okuyucu, sinav, sinav_belge
from ..services.aktarim import norm
from ..services.belgeler import _guvenli
from ..services.utils import tarih, tatil_gunleri, tr
from . import ortak
from .crud import Alan, CrudSayfasi, FormDialog, Varlik, combo_deger, fk_combo

RENK_PASIF = QColor("#e9ecef")

DONEM_VARLIK = Varlik("sinav_donemleri", "Sınav Dönemi", [
    Alan("ad", "Dönem adı", zorunlu=True),
    Alan("tur", "Sınav türü", "choice", True, secenekler=sinav.DONEM_TURLERI, varsayilan="Sorumluluk"),
    Alan("baslangic", "Başlangıç tarihi", "date"),
    Alan("bitis", "Bitiş tarihi", "date"),
    Alan("ogrenci_gunluk_azami", "Öğrencinin günde en çok sınavı", "int", varsayilan=2,
         ipucu="Uygulamalı sınav olan gün öğrenciye başka sınav konmaz."),
    Alan("ogretmen_gunluk_azami", "Öğretmenin günde en çok görevi", "int", varsayilan=3,
         ipucu="Öğretmenler sekmesinden öğretmene özel sınır verilebilir."),
    Alan("komisyon_uye_sayisi", "Komisyon üye sayısı (başkan dahil)", "int", varsayilan=2),
    Alan("gozcu_ogrenci_sayisi", "Bir gözcüye düşen öğrenci sayısı", "int", varsayilan=25,
         ipucu="Salon dağıtımı yapılmışsa her salona bir gözcü verilir."),
    Alan("oturma_duzeni", "Salonda oturma düzeni", "choice", True, secenekler=sinav.OTURMA_DUZENLERI,
         varsayilan=sinav.OTURMA_DUZENLERI[0]),
    Alan("uygulama_saati", "Uygulama sınavları ortak başlama saati",
         ipucu="Doluysa belgelerde uygulama sınavlarının saati olarak bu yazılır (ör. 13:30). Boşsa seansın saati."),
    Alan("sozlu_saati", "Sözlü sınavları ortak başlama saati",
         ipucu="Doluysa belgelerde sözlü sınavların saati olarak bu yazılır (ör. 14:00). Boşsa seansın saati."),
    Alan("komisyon_ucret_saat", "Komisyon görevi ek ders saati", "float", varsayilan=1,
         ipucu="Sınav görev ücret çizelgesinde her komisyon görevi bu kadar ek ders saati sayılır."),
    Alan("gozcu_ucret_saat", "Gözcülük ek ders saati", "float", varsayilan=1),
    Alan("yillik_azami_gorev", "Yıllık ücretli görev sınırı (0 = sınırsız)", "int", varsayilan=0,
         ipucu="Aynı eğitim yılındaki önceki dönemlerin görevleri de sayılır; sınırı aşan görev ücrete girmez ve "
               "görevlendirmede son sıraya düşer."),
    Alan("baslik_aciklama", "Belge başlığı (Başlık ve Onay Bilgisi)",
         ipucu="Boşsa '<eğitim yılı> Eğitim-Öğretim Yılı <dönem adı>' yazılır."),
    Alan("duzenleyen", "Düzenleyen"),
    Alan("duzenleyen_unvan", "Düzenleyenin unvanı", varsayilan="Müdür Yardımcısı"),
    Alan("onaylayan", "Onaylayan", ipucu="Boşsa kurum bilgilerindeki okul müdürü."),
    Alan("onaylayan_unvan", "Onaylayanın unvanı", varsayilan="Okul Müdürü"),
    Alan("aciklama", "Açıklama", "multiline"),
])


def _salonlari_al(sayfa, _ids: list[int]) -> None:
    secenekler = ["Atölye ve laboratuvarlar", "Sınıflar", "Atölyeler ve sınıflar"]
    secim, ok = QInputDialog.getItem(sayfa, "Salonları Al", "Sınav salonu olarak eklenecek yerler (aynı adlı salon "
                                                            "eklenmez):", secenekler, 0, False)
    if not ok:
        return
    i = secenekler.index(secim)
    n = sinav.salonlari_al(sayfa.db, atolyeler=i != 1, siniflar=i != 0)
    sayfa.yenile()
    ortak.bilgi(sayfa, f"{n} salon eklendi. Kapasiteleri ve doldurma sırasını kontrol edin.")


SALON_VARLIK = Varlik("sinav_salonlari", "Sınav Salonları", [
    Alan("ad", "Salon adı", zorunlu=True),
    Alan("kapasite", "Kapasite (öğrenci)", "int", varsayilan=30),
    Alan("sira", "Doldurma sırası", "int", varsayilan=0, ipucu="Öğrenciler küçük sıradaki salondan başlayarak yerleşir."),
    Alan("aktif", "Kullanılır", "bool", varsayilan=1),
], siralama="sira, id",
    aciklama="Yazılı sınavların öğrencileri bu salonlara sırayla dağıtılır; bir seanstaki yazılı sınavların toplam "
             "öğrencisi kullanılan salonların kapasitesini aşamaz. Uygulama ve sözlü sınavlar salon gerektirmez; "
             "bir sınava salon ayrılırsa ('Sınavlar ve Öğrenciler' > 'Salonlar...') o sınavın öğrencileri önce o "
             "salona oturur.",
    eylemler=[("Atölye / Sınıflardan Al...", _salonlari_al)])


def _son_satir(tb: str) -> str:
    satir = (tb.strip().splitlines() or [""])[-1]
    return satir.split(": ", 1)[-1] if re.match(r"^\w+(Error|Exception|Hatasi)\b", satir) else satir


def _qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _pydate(q: QDate) -> date:
    return date(q.year(), q.month(), q.day())


def _tarih_kutusu() -> QDateEdit:
    w = QDateEdit()
    w.setCalendarPopup(True)
    w.setDisplayFormat("dd.MM.yyyy")
    w.setDate(QDate.currentDate())
    return w


def _sayi_kutusu(azami: int = 30) -> QSpinBox:
    """-1 = dönem ayarı."""
    w = QSpinBox()
    w.setRange(-1, azami)
    w.setSpecialValueText("Dönem ayarı")
    w.setValue(-1)
    return w


def _sayi(w: QSpinBox) -> int | None:
    return None if w.value() < 0 else w.value()


def _varsayilan_donem_adi() -> str:
    b = date.today()
    y = b.year if b.month >= 9 else b.year - 1
    return f"{y}-{y + 1} Eğitim Öğretim Yılı {AYLAR[b.month - 1]} Dönemi Sorumluluk Sınavları"


def _metin_listesi(baslik: str, satirlar: list[str], azami: int = 40) -> list[str]:
    if not satirlar:
        return []
    out = ["", baslik] + [f"- {s}" for s in satirlar[:azami]]
    if len(satirlar) > azami:
        out.append(f"... ve {len(satirlar) - azami} satır daha")
    return out


class SeansSecDialog(QDialog):
    """İşaretli seanslar seçilir (öğretmenin ya da öğrencinin sınava/göreve gelemeyeceği seanslar)."""

    def __init__(self, seanslar: list, secili: set[int], baslik: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(baslik)
        self.resize(460, 560)
        lay = QVBoxLayout(self)
        lbl = QLabel("İşaretli seanslarda sınav / görev verilmez.")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        self.liste = QListWidget()
        for r in seanslar:
            it = QListWidgetItem(sinav.seans_etiketi(r) + ("" if r["acik"] else "  [kapalı seans]"))
            it.setData(Qt.UserRole, r["id"])
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            it.setCheckState(Qt.Checked if r["id"] in secili else Qt.Unchecked)
            self.liste.addItem(it)
        self.liste.itemDoubleClicked.connect(
            lambda it: it.setCheckState(Qt.Unchecked if it.checkState() == Qt.Checked else Qt.Checked))
        lay.addWidget(self.liste, 1)
        h = QHBoxLayout()
        for metin, durum in (("Seçilenleri İşaretle", Qt.Checked), ("Seçilenlerin İşaretini Kaldır", Qt.Unchecked)):
            b = QPushButton(metin)
            b.clicked.connect(lambda _=False, d=durum: self._secilenler(d))
            h.addWidget(b)
        temizle = QPushButton("Hiçbiri")
        temizle.clicked.connect(lambda: [self.liste.item(i).setCheckState(Qt.Unchecked)
                                         for i in range(self.liste.count())])
        h.addWidget(temizle)
        lay.addLayout(h)
        self.liste.setSelectionMode(QAbstractItemView.ExtendedSelection)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Tamam")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _secilenler(self, durum) -> None:
        for it in self.liste.selectedItems():
            it.setCheckState(durum)

    def secili(self) -> set[int]:
        return {self.liste.item(i).data(Qt.UserRole) for i in range(self.liste.count())
                if self.liste.item(i).checkState() == Qt.Checked}


class OgrenciSecDialog(QDialog):
    def __init__(self, db, haric: set[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sınava Öğrenci Ekle")
        self.resize(520, 600)
        lay = QVBoxLayout(self)
        ust = QHBoxLayout()
        self.ara = QLineEdit()
        self.ara.setPlaceholderText("Ad, soyad veya okul no ile ara...")
        self.ara.setClearButtonEnabled(True)
        self.sinif = QComboBox()
        self.sinif.addItem("(Bütün sınıflar)", None)
        ust.addWidget(self.ara, 2)
        ust.addWidget(self.sinif, 1)
        lay.addLayout(ust)
        self.liste = QListWidget()
        self.liste.setSelectionMode(QAbstractItemView.ExtendedSelection)
        siniflar: list[str] = []
        for r in db.q("""SELECT o.id, o.okul_no, o.ad, o.soyad, si.ad AS sinif FROM ogrenciler o
                         LEFT JOIN siniflar si ON si.id = o.sinif_id
                         ORDER BY si.ad, CAST(o.okul_no AS INTEGER), o.ad, o.soyad"""):
            if r["id"] in haric:
                continue
            it = QListWidgetItem(f"{r['okul_no'] or '-'}  {r['ad']} {r['soyad']}" +
                                 (f"  ({r['sinif']})" if r["sinif"] else ""))
            it.setData(Qt.UserRole, r["id"])
            it.setData(Qt.UserRole + 1, r["sinif"] or "")
            self.liste.addItem(it)
            if r["sinif"] and r["sinif"] not in siniflar:
                siniflar.append(r["sinif"])
        for s in siniflar:
            self.sinif.addItem(s, s)
        lay.addWidget(self.liste, 1)
        self.durum = QLabel()
        lay.addWidget(self.durum)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Seçilenleri Ekle")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.ara.textChanged.connect(lambda _: self._suz())
        self.sinif.currentIndexChanged.connect(lambda _: self._suz())
        self.liste.itemDoubleClicked.connect(lambda _: self.accept())
        self._suz()

    def _suz(self) -> None:
        aranan = norm(self.ara.text())
        sinif = self.sinif.currentData()
        gorunen = 0
        for i in range(self.liste.count()):
            it = self.liste.item(i)
            gizle = bool((sinif and it.data(Qt.UserRole + 1) != sinif) or (aranan and aranan not in norm(it.text())))
            it.setHidden(gizle)
            gorunen += not gizle
        self.durum.setText(f"{gorunen} öğrenci listeleniyor. Birden çok öğrenci Ctrl / Shift ile seçilebilir.")

    def secilenler(self) -> list[int]:
        return [it.data(Qt.UserRole) for it in self.liste.selectedItems() if not it.isHidden()]


class SinavDialog(QDialog):
    def __init__(self, db, donem_id: int, kayit: dict | None = None, parent=None):
        super().__init__(parent)
        self.db, self.donem_id, self.kayit = db, donem_id, kayit
        self.sinav_id: int | None = kayit["id"] if kayit else None
        self.setWindowTitle("Sınav - " + ("Düzenle" if kayit else "Yeni Sınav"))
        self.setMinimumWidth(520)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.ders = QLineEdit()
        adlar = sorted({r["ad"] for r in db.q("SELECT ad FROM dersler")} |
                       {r["ders"] for r in db.q("SELECT DISTINCT ders FROM sinavlar")}, key=norm)
        tamamla = QCompleter(adlar, self)
        tamamla.setCaseSensitivity(Qt.CaseInsensitive)
        tamamla.setFilterMode(Qt.MatchContains)
        self.ders.setCompleter(tamamla)
        self.seviye = QSpinBox()
        self.seviye.setRange(0, 12)
        self.seviye.setSpecialValueText("—")
        self.grup = QLineEdit()
        self.grup.setPlaceholderText("Aynı dersin ayrı sınavları için (ör. A, B)")
        self.sekil = QComboBox()
        self.sekil.addItems(sinav.SEKILLER)
        self.sure = QSpinBox()
        self.sure.setRange(5, 600)
        self.sure.setSuffix(" dk")
        self.sure.setValue(40)
        self.alan = fk_combo(db, "SELECT id, ad FROM alanlar ORDER BY ad", False)
        self.alan.setToolTip("Meslek dersi sınavının komisyonu öncelikle bu alanın öğretmenlerinden kurulur.")
        self.seans = QComboBox()
        self.seans.addItem("(Otomatik planlamada yerleştirilsin)", None)
        for r in sinav.seanslar(db, donem_id):
            self.seans.addItem(sinav.seans_etiketi(r) + ("" if r["acik"] else "  [kapalı seans]"), r["id"])
        self.cakili = QCheckBox("Çakılı (otomatik planlama bu sınavın seansını değiştirmez)")
        self.komisyon, self.gozcu = _sayi_kutusu(), _sayi_kutusu()
        self.komisyon.setToolTip("Bu sınavın komisyon üye sayısı (başkan dahil). 'Dönem ayarı' = dönemdeki sayı.")
        self.gozcu.setToolTip("Bu sınavın gözcü sayısı. 'Dönem ayarı' = öğrenci sayısına / salonlara göre.")
        self.bagli = QComboBox()
        self.bagli.addItem("(Yok)", None)
        for r in db.q("SELECT id, ders, seviye, grup FROM sinavlar WHERE donem_id = ? ORDER BY ders, seviye, grup",
                      (donem_id,)):
            if not kayit or r["id"] != kayit["id"]:
                self.bagli.addItem(sinav.sinav_adi(r), r["id"])
        self.bagli.setToolTip("Sözlü sınav bağlı olduğu yazılı sınavdan sonraki sınav gününün ilk seansına konur.")
        self.ucretsiz = QCheckBox("Ücretsiz (bu sınavın görevleri ek ders ücretine girmez)")
        self.aciklama = QLineEdit()
        form.addRow("Ders *", self.ders)
        form.addRow("Sınıf seviyesi", self.seviye)
        form.addRow("Grup", self.grup)
        form.addRow("Sınav şekli", self.sekil)
        form.addRow("Süre", self.sure)
        form.addRow("Alan", self.alan)
        form.addRow("Seans", self.seans)
        form.addRow("", self.cakili)
        form.addRow("Komisyon üye sayısı", self.komisyon)
        form.addRow("Gözcü sayısı", self.gozcu)
        form.addRow("Bağlı olduğu sınav", self.bagli)
        form.addRow("", self.ucretsiz)
        form.addRow("Açıklama", self.aciklama)
        lay.addLayout(form)
        if kayit:
            self.ders.setText(kayit["ders"])
            self.seviye.setValue(int(kayit["seviye"] or 0))
            self.grup.setText(kayit["grup"] or "")
            i = self.sekil.findText(kayit["sekil"] or "Yazılı")
            if i < 0:
                self.sekil.addItem(kayit["sekil"])
                i = self.sekil.count() - 1
            self.sekil.setCurrentIndex(i)
            self.sure.setValue(int(kayit["sure_dk"] or 40))
            self.alan.setCurrentIndex(max(0, self.alan.findData(kayit["alan_id"])))
            self.seans.setCurrentIndex(max(0, self.seans.findData(kayit["seans_id"])))
            self.cakili.setChecked(bool(kayit["cakili"]))
            self.komisyon.setValue(-1 if kayit.get("komisyon_sayisi") is None else kayit["komisyon_sayisi"])
            self.gozcu.setValue(-1 if kayit.get("gozcu_sayisi") is None else kayit["gozcu_sayisi"])
            self.bagli.setCurrentIndex(max(0, self.bagli.findData(kayit.get("bagli_sinav_id"))))
            self.ucretsiz.setChecked(bool(kayit.get("ucretsiz")))
            self.aciklama.setText(kayit["aciklama"] or "")
        self.cakili.setEnabled(self.seans.currentData() is not None)
        self.seans.currentIndexChanged.connect(self._seans_degisti)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Kaydet")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(self._kaydet)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _seans_degisti(self, _i: int) -> None:
        secili = self.seans.currentData() is not None
        self.cakili.setEnabled(secili)
        self.cakili.setChecked(secili)

    def _kaydet(self) -> None:
        ders = sinav.ders_adi_duzelt(self.ders.text())
        if not ders:
            ortak.hata(self, "Ders adı boş bırakılamaz.")
            return
        seviye = self.seviye.value() or None
        grup = self.grup.text().strip()
        anahtar = (norm(ders), seviye, norm(grup))
        for r in self.db.q("SELECT id, ders, seviye, grup FROM sinavlar WHERE donem_id = ?", (self.donem_id,)):
            if r["id"] != self.sinav_id and (norm(r["ders"]), r["seviye"], norm(r["grup"] or "")) == anahtar:
                ortak.hata(self, "Bu dönemde aynı ders, seviye ve grupta bir sınav zaten var. Farklı bir grup adı "
                                 "verin ya da sınavları birleştirin.")
                return
        seans_id = self.seans.currentData()
        cakili = int(bool(seans_id) and self.cakili.isChecked())
        alan_id = combo_deger(self.alan)
        ayar = {"komisyon_sayisi": _sayi(self.komisyon), "gozcu_sayisi": _sayi(self.gozcu),
                "bagli_sinav_id": self.bagli.currentData(), "ucretsiz": int(self.ucretsiz.isChecked())}
        try:
            if self.sinav_id:
                sinav.sinav_guncelle(self.db, self.sinav_id, ders=ders, seviye=seviye, grup=grup,
                                     sekil=self.sekil.currentText(), sure_dk=self.sure.value(), alan_id=alan_id,
                                     aciklama=self.aciklama.text().strip(), seans_id=seans_id, cakili=cakili, **ayar)
            else:
                ek = {"aciklama": self.aciklama.text().strip()}
                if alan_id is not None:
                    ek["alan_id"] = alan_id
                self.sinav_id = sinav.sinav_ekle(self.db, self.donem_id, ders, seviye, grup,
                                                 self.sekil.currentText(), self.sure.value(), **ek)
                sinav.sinav_guncelle(self.db, self.sinav_id, **ayar)
                if seans_id:
                    sinav.seans_ata(self.db, self.sinav_id, seans_id, bool(cakili))
        except Exception as e:
            ortak.hata(self, f"Kayıt yapılamadı:\n{e}")
            return
        self.accept()


class TopluDuzenleDialog(QDialog):
    """Seçilen sınavların işaretlenen alanlarını birlikte değiştirir."""

    def __init__(self, n: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Toplu Düzenle - {n} sınav")
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lbl = QLabel("Yalnız işaretlenen alanlar değiştirilir.")
        lbl.setStyleSheet("color:#555")
        lay.addWidget(lbl)
        grid = QGridLayout()
        self.sekil = QComboBox()
        self.sekil.addItems(sinav.SEKILLER)
        self.sure = QSpinBox()
        self.sure.setRange(5, 600)
        self.sure.setSuffix(" dk")
        self.sure.setValue(40)
        self.komisyon, self.gozcu = _sayi_kutusu(), _sayi_kutusu()
        self.cakili, self.ucretsiz = QComboBox(), QComboBox()
        for cb in (self.cakili, self.ucretsiz):
            cb.addItems(["Evet", "Hayır"])
        self.alanlar = {"sekil": ("Sınav şekli", self.sekil), "sure_dk": ("Süre", self.sure),
                        "komisyon_sayisi": ("Komisyon üye sayısı", self.komisyon),
                        "gozcu_sayisi": ("Gözcü sayısı", self.gozcu), "cakili": ("Çakılı", self.cakili),
                        "ucretsiz": ("Ücretsiz", self.ucretsiz)}
        self.isaret: dict[str, QCheckBox] = {}
        for i, (ad, (etiket, w)) in enumerate(self.alanlar.items()):
            cb = QCheckBox(etiket)
            w.setEnabled(False)
            cb.toggled.connect(w.setEnabled)
            self.isaret[ad] = cb
            grid.addWidget(cb, i, 0)
            grid.addWidget(w, i, 1)
        lay.addLayout(grid)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Uygula")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def degerler(self) -> dict:
        out = {}
        for ad, (_, w) in self.alanlar.items():
            if not self.isaret[ad].isChecked():
                continue
            if isinstance(w, QSpinBox):
                out[ad] = w.value() if ad == "sure_dk" else _sayi(w)
            else:
                out[ad] = int(w.currentText() == "Evet") if ad in ("cakili", "ucretsiz") else w.currentText()
        return out


class _Sekme(QWidget):
    def __init__(self, sayfa: "SinavSayfasi"):
        super().__init__()
        self.sayfa, self.db = sayfa, sayfa.db

    @property
    def donem_id(self) -> int | None:
        return self.sayfa.donem_id

    def donem_gerekli(self) -> int | None:
        did = self.donem_id
        if not did:
            ortak.bilgi(self, "Önce sağ üstteki 'Yeni Dönem' düğmesiyle bir sınav dönemi oluşturun.")
        return did

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def canli_yenile(self) -> None:
        self.sayfa.donemleri_doldur()
        self.yenile()

    def yenile(self) -> None:
        raise NotImplementedError


# ------------------------------------------------------------------ seans çizelgesi

class SeansSekmesi(_Sekme):
    def __init__(self, sayfa):
        super().__init__(sayfa)
        self._yuklu_donem: object = object()
        self._tarihler: list[str] = []
        self._seans: dict[int, object] = {}
        self._ozet: dict[int, tuple[int, int]] = {}
        self._sutun_saati: dict[int, tuple] = {}
        lay = QVBoxLayout(self)
        lbl = QLabel("Sınav günlerini ve oturum saatlerini belirleyip seansları oluşturun. Çizelgede işareti "
                     "kaldırılan seansa sınav konmaz (ör. öğle arası, toplantı saati).")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#555")
        lay.addWidget(lbl)
        ust = ortak.AkisDuzeni()
        self.bas = _tarih_kutusu()
        self.bit = _tarih_kutusu()
        self.hafta_sonu = QCheckBox("Hafta sonu dahil")
        self.tatil = QCheckBox("Tatil günlerini atla")
        self.tatil.setChecked(True)
        self.haric = QLineEdit()
        self.haric.setPlaceholderText("ör. 29.10.2026, 30.10.2026")
        self.haric.setMinimumWidth(220)
        ust.addWidget(ortak.etiketli("Başlangıç:", self.bas))
        ust.addWidget(ortak.etiketli("Bitiş:", self.bit))
        ust.addWidget(self.hafta_sonu)
        ust.addWidget(self.tatil)
        ust.addWidget(ortak.etiketli("Sınav yapılmayacak günler:", self.haric))
        lay.addLayout(ust)

        orta = QHBoxLayout()
        saat_kutu = QGroupBox("Oturum saatleri")
        sv = QVBoxLayout(saat_kutu)
        self.saatler = QTableWidget(0, 2)
        self.saatler.setHorizontalHeaderLabels(["Başlangıç", "Bitiş"])
        self.saatler.horizontalHeader().setStretchLastSection(True)
        self.saatler.setMinimumWidth(220)
        sv.addWidget(self.saatler, 1)
        h = QHBoxLayout()
        b = QPushButton("Oturum Ekle")
        b.clicked.connect(self.saat_ekle)
        h.addWidget(b)
        b = QPushButton("Oturum Sil")
        b.clicked.connect(self.saat_sil)
        h.addWidget(b)
        sv.addLayout(h)
        self.b_olustur = QPushButton("Seansları Oluştur")
        self.b_olustur.setStyleSheet("font-weight:bold")
        self.b_olustur.clicked.connect(self.olustur)
        sv.addWidget(self.b_olustur)
        orta.addWidget(saat_kutu, 0)

        cizelge_kutu = QGroupBox("Seans çizelgesi (işaretli seanslarda sınav yapılabilir)")
        cv = QVBoxLayout(cizelge_kutu)
        self.cizelge = QTableWidget()
        self.cizelge.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cizelge.itemChanged.connect(self._hucre_degisti)
        cv.addWidget(self.cizelge, 1)
        h = QHBoxLayout()
        b = QPushButton("Seçili Günün Düzenini Tüm Günlere Uygula")
        b.setToolTip("Seçili gündeki açık/kapalı oturumlar bütün günlere aynen uygulanır.")
        b.clicked.connect(self.duzeni_uygula)
        h.addWidget(b)
        b = QPushButton("Tümünü Aç")
        b.clicked.connect(self.tumunu_ac)
        h.addWidget(b)
        b = QPushButton("Seçili Seansların Saati...")
        b.setToolTip("Seçili hücrelerdeki seansların başlama / bitiş saatini değiştirir (günden güne farklı saat).")
        b.clicked.connect(self.saat_degistir)
        h.addWidget(b)
        h.addStretch()
        cv.addLayout(h)
        self.durum = QLabel()
        cv.addWidget(self.durum)
        orta.addWidget(cizelge_kutu, 1)
        lay.addLayout(orta, 1)

    def yenile(self) -> None:
        did = self.donem_id
        rows = sinav.seanslar(self.db, did)
        if did != self._yuklu_donem:
            self._yuklu_donem = did
            self._ayarlari_yukle(did, rows)
        for w in (self.b_olustur, self.cizelge):
            w.setEnabled(bool(did))
        self._cizelge_doldur(rows)

    def _ayarlari_yukle(self, did: int | None, rows: list) -> None:
        d = sinav.donem(self.db, did)
        bas = tarih(d["baslangic"]) if d else None
        bit = tarih(d["bitis"]) if d else None
        if not bas:
            bugun = date.today()
            bas = bugun + timedelta(days=(7 - bugun.weekday()) % 7 or 7)
        if not bit or bit < bas:
            bit = bas + timedelta(days=4)
        self.bas.setDate(_qdate(bas))
        self.bit.setDate(_qdate(bit))
        saat: dict[int, tuple[str, str]] = {}
        for r in rows:
            saat.setdefault(r["sira"], (r["baslangic"] or "", r["bitis"] or ""))
        liste = [saat[k] for k in sorted(saat)] or list(sinav.VARSAYILAN_SAATLER)
        self.saatler.setRowCount(0)
        for b, e in liste:
            self._saat_satiri(b, e)

    def _saat_satiri(self, b: str, e: str) -> None:
        i = self.saatler.rowCount()
        self.saatler.insertRow(i)
        self.saatler.setItem(i, 0, QTableWidgetItem(b))
        self.saatler.setItem(i, 1, QTableWidgetItem(e))

    def saat_ekle(self) -> None:
        n = self.saatler.rowCount()
        son = self.saatler.item(n - 1, 1).text() if n and self.saatler.item(n - 1, 1) else ""
        b = sinav.saat_coz(son)
        if b:
            h, m = map(int, b.split(":"))
            h, m = (h + 1, m) if m >= 40 else (h, m + 20)
            b = f"{min(h, 23):02d}:{m % 60:02d}"
            e = f"{min(h + (m + 40) // 60, 23):02d}:{(m + 40) % 60:02d}"
            self._saat_satiri(b, e)
        else:
            self._saat_satiri("", "")

    def saat_sil(self) -> None:
        for r in sorted({i.row() for i in self.saatler.selectedIndexes()}, reverse=True):
            self.saatler.removeRow(r)

    def _saatleri_oku(self) -> list[tuple[str, str]] | None:
        out = []
        for i in range(self.saatler.rowCount()):
            b = (self.saatler.item(i, 0).text() if self.saatler.item(i, 0) else "").strip()
            e = (self.saatler.item(i, 1).text() if self.saatler.item(i, 1) else "").strip()
            if not b and not e:
                continue
            bb, ee = sinav.saat_coz(b), sinav.saat_coz(e)
            if not bb or not ee or ee <= bb:
                ortak.hata(self, f"{i + 1}. oturumun saati geçersiz ('{b}' - '{e}'). Örnek: 09:00 - 09:40")
                return None
            out.append((bb, ee))
        if not out:
            ortak.hata(self, "En az bir oturum saati girin (ör. 09:00 - 09:40).")
            return None
        if sorted(out) != out or any(out[i][1] > out[i + 1][0] for i in range(len(out) - 1)):
            ortak.hata(self, "Oturumlar saat sırasıyla girilmeli ve birbiriyle çakışmamalı.")
            return None
        return out

    def _haric_tarihler(self) -> set[date] | None:
        out = set()
        for p in re.split(r"[,;\s]+", self.haric.text().strip()):
            if not p:
                continue
            d = tarih(p)
            if not d:
                ortak.hata(self, f"'{p}' tarih olarak anlaşılamadı. Örnek: 29.10.2026")
                return None
            out.add(d)
        return out

    def olustur(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        saatler = self._saatleri_oku()
        if saatler is None:
            return
        bas, bit = _pydate(self.bas.date()), _pydate(self.bit.date())
        if bit < bas:
            ortak.hata(self, "Bitiş tarihi başlangıçtan önce olamaz.")
            return
        if (bit - bas).days > 120:
            ortak.hata(self, "Sınav dönemi en çok 120 gün olabilir.")
            return
        haric = self._haric_tarihler()
        if haric is None:
            return
        if self.tatil.isChecked():
            haric |= tatil_gunleri(self.db, bas, bit)
        tarihler = sinav.tarihleri_uret(bas, bit, self.hafta_sonu.isChecked(), haric)
        if not tarihler:
            ortak.hata(self, "Seçilen aralıkta sınav yapılabilecek gün yok.")
            return
        sil = True
        mevcut = sinav.seanslar(self.db, did)
        if mevcut:
            kutu = QMessageBox(self)
            kutu.setWindowTitle("Seansları Oluştur")
            kutu.setIcon(QMessageBox.Question)
            kutu.setText(f"Bu dönemde {len(mevcut)} seans var.\n\n'Baştan Oluştur' eski seansları siler; sınavların "
                         "seans yerleşimi, görevlendirmeler, salon dağıtımı ve öğretmenlerin kapalı seansları da "
                         "silinir.\n'Eksikleri Ekle' yalnızca olmayan gün ve oturumları ekler.")
            bastan = kutu.addButton("Baştan Oluştur", QMessageBox.DestructiveRole)
            ekle = kutu.addButton("Eksikleri Ekle", QMessageBox.AcceptRole)
            kutu.addButton("Vazgeç", QMessageBox.RejectRole)
            kutu.exec()
            if kutu.clickedButton() == bastan:
                sil = True
            elif kutu.clickedButton() == ekle:
                sil = False
            else:
                return
        n = sinav.seanslari_olustur(self.db, did, tarihler, saatler, sil=sil)
        self.sayfa.donemleri_doldur()
        self._cizelge_doldur(sinav.seanslar(self.db, did))
        self.durum.setText(self.durum.text() + f"  —  {n} seans eklendi.")

    def _cizelge_doldur(self, rows: list) -> None:
        tarihler = sorted({r["tarih"] for r in rows})
        siralar = sorted({r["sira"] for r in rows})
        self._tarihler = tarihler
        hucre = {(r["tarih"], r["sira"]): r for r in rows}
        self._seans = {r["id"]: r for r in rows}
        self._ozet = sinav.seans_ozeti(self.db, self.donem_id)
        self.cizelge.blockSignals(True)
        self.cizelge.clear()
        self.cizelge.setRowCount(len(tarihler))
        self.cizelge.setColumnCount(len(siralar))
        basliklar = []
        self._sutun_saati = {}
        for s in siralar:
            ilk = Counter((r["baslangic"], r["bitis"]) for r in rows if r["sira"] == s).most_common(1)[0][0]
            self._sutun_saati[s] = ilk
            basliklar.append(f"{s}. oturum" + (f"\n{ilk[0]}-{ilk[1]}" if ilk[0] else ""))
        self.cizelge.setHorizontalHeaderLabels(basliklar)
        self.cizelge.setVerticalHeaderLabels([f"{tr(t)} {sinav.gun_adi(t)}" for t in tarihler])
        for i, t in enumerate(tarihler):
            for j, s in enumerate(siralar):
                r = hucre.get((t, s))
                it = QTableWidgetItem()
                if r is None:
                    it.setFlags(Qt.NoItemFlags)
                else:
                    it.setData(Qt.UserRole, r["id"])
                    it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                    self._hucre_gorunumu(it, bool(r["acik"]))
                self.cizelge.setItem(i, j, it)
        self.cizelge.resizeRowsToContents()
        self.cizelge.resizeColumnsToContents()
        self.cizelge.blockSignals(False)
        acik = sum(1 for r in rows if r["acik"])
        self.durum.setText(f"{len(tarihler)} gün, {len(rows)} seans ({acik} açık)." if rows else
                           "Henüz seans yok. Tarihleri ve oturum saatlerini girip 'Seansları Oluştur'a basın.")

    def _hucre_gorunumu(self, it: QTableWidgetItem, acik: bool) -> None:
        it.setCheckState(Qt.Checked if acik else Qt.Unchecked)
        r = self._seans.get(it.data(Qt.UserRole))
        satirlar = ["Açık" if acik else "Kapalı"]
        if r is not None:
            if (r["baslangic"], r["bitis"]) != self._sutun_saati.get(r["sira"]) and r["baslangic"]:
                satirlar.append(f"{r['baslangic']}-{r['bitis']}")
            n, m = self._ozet.get(r["id"], (0, 0))
            if n:
                satirlar.append(f"{n} sınav / {m} öğr.")
        it.setText("\n".join(satirlar))
        it.setBackground(ortak.RENK_TAMAM if acik else RENK_PASIF)

    def saat_degistir(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        ids = [it.data(Qt.UserRole) for it in self.cizelge.selectedItems() if it.data(Qt.UserRole) is not None]
        if not ids:
            ortak.bilgi(self, "Önce çizelgeden saati değiştirilecek seansları seçin (Ctrl ile çoklu seçim).")
            return
        r = self._seans[ids[0]]
        metin, ok = QInputDialog.getText(self, "Seans Saati", f"Seçilen {len(ids)} seansın saati (başlama-bitiş):",
                                         text=f"{r['baslangic'] or ''}-{r['bitis'] or ''}")
        if not ok:
            return
        saatler = sinav.saatleri_coz(metin)
        if len(saatler) != 1:
            ortak.hata(self, "Saat 09:00-09:40 biçiminde girilmeli.")
            return
        try:
            sinav.seans_saati_ayarla(self.db, ids, *saatler[0])
        except ValueError as e:
            ortak.hata(self, str(e))
            return
        self._cizelge_doldur(sinav.seanslar(self.db, did))

    def _hucre_degisti(self, it: QTableWidgetItem) -> None:
        sid = it.data(Qt.UserRole)
        if sid is None:
            return
        acik = it.checkState() == Qt.Checked
        sinav.seans_acik_yap(self.db, sid, acik)
        self.cizelge.blockSignals(True)
        self._hucre_gorunumu(it, acik)
        self.cizelge.blockSignals(False)
        rows = sinav.seanslar(self.db, self.donem_id)
        self.durum.setText(f"{len(self._tarihler)} gün, {len(rows)} seans ({sum(1 for r in rows if r['acik'])} açık).")

    def duzeni_uygula(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        satir = self.cizelge.currentRow()
        if satir < 0 or satir >= len(self._tarihler):
            ortak.bilgi(self, "Önce çizelgeden düzeni örnek alınacak günü seçin.")
            return
        n = sinav.gun_duzenini_uygula(self.db, did, self._tarihler[satir])
        self._cizelge_doldur(sinav.seanslar(self.db, did))
        self.durum.setText(self.durum.text() + f"  —  {n} seans güncellendi.")

    def tumunu_ac(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        self.db.execute("UPDATE sinav_seanslari SET acik = 1 WHERE donem_id = ? AND acik = 0", (did,))
        self._cizelge_doldur(sinav.seanslar(self.db, did))


# ------------------------------------------------------------------ sınavlar ve öğrenciler

class SinavlarSekmesi(_Sekme):
    BASLIKLAR = ["Ders", "Seviye", "Grup", "Şekil", "Süre (dk)", "Öğrenci", "Seans", "Çakılı", "Komisyon / Gözcü",
                 "Ayrılmış Salon", "Yoklama", "Alan"]

    def __init__(self, sayfa):
        super().__init__(sayfa)
        self._kayitlar: dict[int, dict] = {}
        lay = QVBoxLayout(self)
        ust = ortak.AkisDuzeni()
        b = QPushButton("e-Okul'dan Aktar...")
        b.setToolTip("e-Okul 'Sorumluluk Sınavına Girecek Öğrenciler' (OOK12001R012) listesi ya da öğrenci ve "
                     "ders sütunları olan herhangi bir Excel / PDF / Word tablosu. Aktarım tekrarlanabilir.")
        b.clicked.connect(self.aktar)
        ust.addWidget(b)
        self.tur = QComboBox()
        self.tur.addItems(sinav.OGRENCI_TURLERI)
        self.tur.setToolTip("Sorumluluk: sorumlu dersler. OYS: ortalama yükseltme sınavı. Tek Ders: yalnız bir dersten "
                            "kalan 12. sınıf öğrencileri (birden çok dersi olanlar elenir).")
        ust.addWidget(ortak.etiketli("Liste türü:", self.tur))
        self.grup_kodu = QLineEdit()
        self.grup_kodu.setPlaceholderText("ör. EML")
        self.grup_kodu.setMaximumWidth(90)
        self.grup_kodu.setToolTip("Sınav Grup Kodu: bu dosyadan gelen sınavların grubuna eklenir (ör. ayrı okul / "
                                  "program dosyaları). Aynı ders farklı kodlarla gelirse 'Birleştir' ile "
                                  "'EML-ATL' gibi birleşik koda dönüşür.")
        ust.addWidget(ortak.etiketli("Grup kodu:", self.grup_kodu))
        self.oys_ayri = QCheckBox("OYS ayrı sınav")
        self.oys_ayri.setChecked(True)
        self.oys_ayri.setToolTip("İşaretliyse OYS öğrencileri sorumluluk sınavından ayrı ('OYS' grubunda) sınava girer.")
        ust.addWidget(self.oys_ayri)
        self.olustur = QCheckBox("Bulunamayan öğrencileri oluştur")
        self.olustur.setToolTip("Okul kayıtlarında bulunamayan öğrenciler (gerekirse sınıflarıyla) oluşturulur.")
        ust.addWidget(self.olustur)
        for metin, fn in (("Yeni Sınav", self.yeni), ("Düzenle", self.duzenle), ("Toplu Düzenle...", self.toplu),
                          ("Salonlar...", self.salonlar), ("Birleştir", self.birlestir), ("Sil", self.sil)):
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        self.ara = QLineEdit()
        self.ara.setPlaceholderText("Ara...")
        self.ara.setClearButtonEnabled(True)
        self.ara.setMinimumWidth(180)
        ust.addWidget(self.ara)
        lay.addLayout(ust)

        bolucu = QSplitter(Qt.Vertical)
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        self.view.doubleClicked.connect(lambda _: self.duzenle())
        self.view.selectionModel().selectionChanged.connect(lambda *_: self._ogrencileri_doldur())
        self.ara.textChanged.connect(self.proxy.setFilterFixedString)
        bolucu.addWidget(self.view)

        alt = QWidget()
        av = QVBoxLayout(alt)
        av.setContentsMargins(0, 0, 0, 0)
        ah = QHBoxLayout()
        self.alt_baslik = QLabel()
        self.alt_baslik.setStyleSheet("font-weight:bold")
        ah.addWidget(self.alt_baslik, 1)
        for metin, fn in (("Öğrenci Ekle...", self.ogrenci_ekle), ("Seçilenleri Çıkar", self.ogrenci_cikar),
                          ("Kapalı Seanslar...", self.ogrenci_kapali), ("Salona Ata...", self.salona_ata),
                          ("Girdi", lambda: self.katilim(sinav.GIRDI)), ("Girmedi", lambda: self.katilim(sinav.GIRMEDI)),
                          ("Yoklamayı Sil", lambda: self.katilim(""))):
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ah.addWidget(b)
        av.addLayout(ah)
        self.omodel = ortak.TabloModeli(["Okul No", "Ad Soyad", "Sınıf", "Türü", "Salon", "Sıra No", "Katılım",
                                         "Kapalı Seans"])
        self.oview, self.oproxy = ortak.tablo_gorunumu(self.omodel)
        av.addWidget(self.oview, 1)
        bolucu.addWidget(alt)
        bolucu.setStretchFactor(0, 3)
        bolucu.setStretchFactor(1, 2)
        lay.addWidget(bolucu, 1)
        self.durum = QLabel()
        lay.addWidget(self.durum)
        self._ilk = True

    def secili_ids(self) -> list[int]:
        return [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)]

    def yenile(self) -> None:
        did = self.donem_id
        secili = self.secili_ids()
        rows = sinav.sinav_listesi(self.db, did)
        self._kayitlar = {r["id"]: r for r in rows}
        renk = {i: ortak.RENK_UYARI for i, r in enumerate(rows) if not r["ogrenci_sayisi"]}
        ayrilmis: dict[int, list[str]] = {}
        for r in self.db.q("SELECT a.sinav_id, sl.ad FROM sinav_salon_atamalari a JOIN sinav_salonlari sl "
                           "ON sl.id = a.salon_id JOIN sinavlar s ON s.id = a.sinav_id WHERE s.donem_id = ? "
                           "ORDER BY sl.sira, sl.id", (did,)):
            ayrilmis.setdefault(r["sinav_id"], []).append(r["ad"])

        def sayi(v) -> str:
            return "dönem" if v is None else str(v)

        self.model.ayarla([[r["ders"], r["seviye"] or "", r["grup"] or "", r["sekil"] or "", r["sure_dk"] or "",
                            r["ogrenci_sayisi"], r["seans"], "Evet" if r["cakili"] else "",
                            "" if r["komisyon_sayisi"] is None and r["gozcu_sayisi"] is None else
                            f"{sayi(r['komisyon_sayisi'])} / {sayi(r['gozcu_sayisi'])}",
                            ", ".join(ayrilmis.get(r["id"], [])),
                            f"{r['ogrenci_sayisi'] - r['girmedi']} girdi / {r['girmedi']} girmedi"
                            if r["girdi"] or r["girmedi"] else "", r["alan"] or ""]
                           for r in rows], [r["id"] for r in rows], renk)
        if self._ilk and rows:
            ortak.sutunlari_sigdir(self.view)
            self._ilk = False
        if secili:
            for i in range(self.proxy.rowCount()):
                if self.model.kimlik(self.proxy.mapToSource(self.proxy.index(i, 0)).row()) == secili[0]:
                    self.view.selectRow(i)
                    break
        ogr = sum(r["ogrenci_sayisi"] for r in rows)
        self.durum.setText(f"{len(rows)} sınav, {ogr} öğrenci-sınav kaydı." if did else
                           "Sınav dönemi seçilmedi. Sağ üstten 'Yeni Dönem' ile dönem oluşturun.")
        self._ogrencileri_doldur()

    def _secili_sinav(self) -> dict | None:
        ids = self.secili_ids()
        return self._kayitlar.get(ids[0]) if ids else None

    def _ogrencileri_doldur(self) -> None:
        s = self._secili_sinav()
        if s is None:
            self.alt_baslik.setText("Öğrencilerini görmek için yukarıdan bir sınav seçin.")
            self.omodel.ayarla([], [])
            return
        kapali: dict[int, int] = {}
        for r in self.db.q("SELECT ogrenci_id, COUNT(*) n FROM sinav_ogrenci_kapali WHERE donem_id = ? "
                           "GROUP BY ogrenci_id", (self.donem_id,)):
            kapali[r["ogrenci_id"]] = r["n"]
        rows = sinav.sinav_ogrencileri(self.db, s["id"])
        self.alt_baslik.setText(f"{s['adi']} — {len(rows)} öğrenci")
        self.omodel.ayarla([[r["okul_no"] or "", f"{r['ad']} {r['soyad']}", r["sinif"] or "", r["tur"] or "",
                             (r["salon"] or "") + (" (elle)" if r["salon_kilitli"] and r["salon"] else ""),
                             r["sira_no"] or "", r["katilim"] or "", kapali.get(r["ogrenci_id"], "") or ""]
                            for r in rows], [r["ogrenci_id"] for r in rows],
                           {i: ortak.RENK_UYARI for i, r in enumerate(rows) if r["katilim"] == sinav.GIRMEDI})

    def aktar(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        yol, _ = QFileDialog.getOpenFileName(self, "Sorumlu öğrenci listesi (e-Okul)", "", okuyucu.DOSYA_FILTRESI)
        if not yol:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            tur = self.tur.currentText()
            s = sinav.eokul_sorumlu_aktar(self.db, did, yol, olustur=self.olustur.isChecked(), tur=tur,
                                          grup_kodu=self.grup_kodu.text().strip(), ayri=self.oys_ayri.isChecked(),
                                          tek_ders=tur == sinav.TEK_DERS)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            ortak.hata(self, f"Dosya aktarılamadı:\n{e}")
            return
        QApplication.restoreOverrideCursor()
        satirlar = [s.ozet()]
        satirlar += _metin_listesi("Okul kayıtlarında bulunamayan öğrenciler:", s.eslesmeyen, 30)
        if s.eslesmeyen:
            satirlar += ["", "Bu öğrencileri önce öğrenci listesine aktarın ya da 'Bulunamayan öğrencileri oluştur' "
                             "seçeneğiyle dosyayı yeniden aktarın (aktarım tekrarlanabilir)."]
        satirlar += _metin_listesi("Uyarılar:", s.uyarilar, 15)
        ortak.bilgi(self, "\n".join(satirlar), "e-Okul Aktarımı")
        self.yenile()

    def yeni(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        d = SinavDialog(self.db, did, None, self)
        if d.exec():
            self.yenile()

    def duzenle(self) -> None:
        s = self._secili_sinav()
        if s is None:
            return
        if SinavDialog(self.db, self.donem_id, s, self).exec():
            self.yenile()

    def toplu(self) -> None:
        ids = self.secili_ids()
        if not ids:
            ortak.bilgi(self, "Önce değiştirilecek sınavları seçin (Ctrl / Shift ile çoklu seçim).")
            return
        d = TopluDuzenleDialog(len(ids), self)
        if d.exec() and d.degerler():
            sinav.sinavlari_toplu_guncelle(self.db, ids, **d.degerler())
            self.yenile()

    def salonlar(self) -> None:
        s = self._secili_sinav()
        if s is None:
            ortak.bilgi(self, "Önce salon ayrılacak sınavı seçin.")
            return
        rows = self.db.q("SELECT id, ad, kapasite FROM sinav_salonlari WHERE aktif = 1 ORDER BY sira, id")
        if not rows:
            ortak.bilgi(self, "Etkin salon yok. Önce 'Salonlar' sekmesinden salon ekleyin.")
            return
        secili = set(sinav.sinav_salonlari(self.db, s["id"]))
        d = QDialog(self)
        d.setWindowTitle(f"{s['adi']} - ayrılmış salonlar")
        d.resize(380, 420)
        lay = QVBoxLayout(d)
        lbl = QLabel("Salon dağıtımında bu sınavın öğrencileri önce işaretli salonlara oturur; bu salonlara o seansta "
                     "başka sınavın öğrencisi konmaz. Uygulama / sözlü sınavlar için atölye seçilebilir.")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        liste = QListWidget()
        for r in rows:
            it = QListWidgetItem(f"{r['ad']} ({r['kapasite'] or 0} kişilik)")
            it.setData(Qt.UserRole, r["id"])
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            it.setCheckState(Qt.Checked if r["id"] in secili else Qt.Unchecked)
            liste.addItem(it)
        lay.addWidget(liste, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Tamam")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        lay.addWidget(bb)
        if d.exec():
            sinav.sinav_salonlari_ayarla(self.db, s["id"], [liste.item(i).data(Qt.UserRole) for i in range(liste.count())
                                                            if liste.item(i).checkState() == Qt.Checked])
            self.yenile()

    def _secili_ogrenciler(self) -> list[int]:
        return [self.omodel.kimlik(r) for r in ortak.secili_satirlar(self.oview, self.oproxy)]

    def salona_ata(self) -> None:
        s, ids = self._secili_sinav(), self._secili_ogrenciler()
        if s is None or not ids:
            ortak.bilgi(self, "Önce aşağıdaki listeden salona alınacak öğrencileri seçin.")
            return
        if not s["seans_id"]:
            ortak.bilgi(self, "Sınav henüz bir seansa yerleşmedi; salon ataması seanstan sonra yapılır.")
            return
        rows = self.db.q("SELECT id, ad FROM sinav_salonlari WHERE aktif = 1 ORDER BY sira, id")
        etiketler = ["(Elle atamayı kaldır)"] + [r["ad"] for r in rows]
        secim, ok = QInputDialog.getItem(self, "Salona Ata", f"Seçilen {len(ids)} öğrencinin salonu (otomatik salon "
                                                             "dağıtımı bu öğrencilere dokunmaz):", etiketler, 1 if rows
                                         else 0, False)
        if ok:
            i = etiketler.index(secim)
            sinav.ogrenci_salon_ata(self.db, s["id"], ids, rows[i - 1]["id"] if i else None)
            self.yenile()

    def katilim(self, durum: str) -> None:
        s, ids = self._secili_sinav(), self._secili_ogrenciler()
        if s is None or not ids:
            ortak.bilgi(self, "Önce aşağıdaki listeden öğrencileri seçin.")
            return
        sinav.ogrenci_katilim_ayarla(self.db, s["id"], ids, durum)
        self.yenile()

    def birlestir(self) -> None:
        ids = self.secili_ids()
        if len(ids) < 2:
            ortak.bilgi(self, "Birleştirilecek en az iki sınavı seçin (Ctrl ile çoklu seçim).")
            return
        hedef = self._kayitlar[ids[0]]
        if not ortak.onay(self, f"Seçilen {len(ids)} sınavın öğrencileri '{hedef['adi']}' sınavında toplanacak, "
                                f"diğer {len(ids) - 1} sınav silinecek. Devam edilsin mi?"):
            return
        n = sinav.sinavlari_birlestir(self.db, ids)
        self.yenile()
        ortak.bilgi(self, f"{n} öğrenci '{hedef['adi']}' sınavına taşındı.")

    def sil(self) -> None:
        ids = self.secili_ids()
        if not ids:
            return
        if ortak.onay(self, f"Seçilen {len(ids)} sınav, öğrenci listeleri ve görevlendirmeleriyle silinsin mi?"):
            sinav.sinavlari_sil(self.db, ids)
            self.yenile()

    def ogrenci_ekle(self) -> None:
        s = self._secili_sinav()
        if s is None:
            ortak.bilgi(self, "Önce öğrenci eklenecek sınavı seçin.")
            return
        mevcut = {self.omodel.kimlik(i) for i in range(self.omodel.rowCount())}
        d = OgrenciSecDialog(self.db, mevcut, self)
        if d.exec() and d.secilenler():
            sinav.sinav_ogrenci_ekle(self.db, s["id"], d.secilenler())
            self.yenile()

    def ogrenci_cikar(self) -> None:
        s = self._secili_sinav()
        ids = [self.omodel.kimlik(r) for r in ortak.secili_satirlar(self.oview, self.oproxy)]
        if s is None or not ids:
            return
        if ortak.onay(self, f"Seçilen {len(ids)} öğrenci '{s['adi']}' sınavından çıkarılsın mı?"):
            sinav.sinav_ogrenci_cikar(self.db, s["id"], ids)
            self.yenile()

    def ogrenci_kapali(self) -> None:
        did = self.donem_id
        satirlar = ortak.secili_satirlar(self.oview, self.oproxy)
        if not did or not satirlar:
            ortak.bilgi(self, "Önce aşağıdaki listeden öğrenciyi seçin.")
            return
        seanslar = sinav.seanslar(self.db, did)
        if not seanslar:
            ortak.bilgi(self, "Bu dönemde seans yok. Önce 'Seans Çizelgesi' sekmesinden seansları oluşturun.")
            return
        oid = self.omodel.kimlik(satirlar[0])
        ad = self.omodel.rows[satirlar[0]][1]
        d = SeansSecDialog(seanslar, sinav.ogrenci_kapali_seanslar(self.db, did, oid),
                           f"{ad} - sınava giremeyeceği seanslar", self)
        if d.exec():
            sinav.ogrenci_kapali_ayarla(self.db, did, oid, d.secili())
            self._ogrencileri_doldur()


# ------------------------------------------------------------------ öğretmenler ve kurallar

class GunKuraliDialog(QDialog):
    def __init__(self, dersler: list[str], tarihler: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sınav Günü Kuralı")
        self.resize(420, 520)
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.ders = QComboBox()
        self.ders.setEditable(True)
        self.ders.setInsertPolicy(QComboBox.NoInsert)
        self.ders.addItems([""] + dersler)
        self.seviye = QSpinBox()
        self.seviye.setRange(0, 12)
        self.seviye.setSpecialValueText("—")
        self.kapsam = QComboBox()
        self.kapsam.addItem("Sınavın seviyesi", "sinav")
        self.kapsam.addItem("Öğrencinin sınıf seviyesi", "ogrenci")
        self.kapsam.setToolTip("Öğrencinin sınıf seviyesi: ör. 12. sınıf öğrencilerinin girdiği bütün sınavlar.")
        form.addRow("Ders (boş = hepsi)", self.ders)
        form.addRow("Seviye", self.seviye)
        form.addRow("Seviyeye göre", self.kapsam)
        lay.addLayout(form)
        lay.addWidget(QLabel("Sınavların yapılabileceği günler:"))
        self.gunler = QListWidget()
        for t in tarihler:
            it = QListWidgetItem(f"{tr(t)} {sinav.gun_adi(t)}")
            it.setData(Qt.UserRole, t)
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            self.gunler.addItem(it)
        lay.addWidget(self.gunler, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Ekle")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def tarihler(self) -> list[str]:
        return [self.gunler.item(i).data(Qt.UserRole) for i in range(self.gunler.count())
                if self.gunler.item(i).checkState() == Qt.Checked]


class OgretmenlerSekmesi(_Sekme):
    BASLIKLAR = ["Ad Soyad", "Branş", "Unvan", "Görev Alır", "Günlük En Çok Görev", "Kapalı Seans", "Önceki Görev",
                 "Görev Sayısı"]

    def __init__(self, sayfa):
        super().__init__(sayfa)
        lay = QVBoxLayout(self)
        self.bilgi = QLabel()
        self.bilgi.setWordWrap(True)
        self.bilgi.setStyleSheet("color:#555")
        lay.addWidget(self.bilgi)
        bolucu = QSplitter(Qt.Horizontal)

        sol = QWidget()
        sl = QVBoxLayout(sol)
        sl.setContentsMargins(0, 0, 0, 0)
        ust = ortak.AkisDuzeni()
        for metin, fn, ipucu in (
                ("Görev Alır", lambda: self.gorev_alir(True), ""), ("Görev Almaz", lambda: self.gorev_alir(False), ""),
                ("Günlük Sınır...", self.gunluk_sinir, ""), ("Kapalı Seanslar...", self.kapali_seanslar, ""),
                ("Nöbet / Müsaitlikten Doldur", self.nobetten_doldur,
                 "Okul nöbet günü ve ders programında tamamen müsait olmadığı günlerin seansları kapalı seanslara "
                 "eklenir (seçili yoksa bütün öğretmenler)."),
                ("Önceki Görev...", self.onceki_gorev, "Aynı eğitim yılında bu dönemden önce aldığı sınav görevi "
                                                       "sayısı (yıllık ücretli görev sınırı için).")):
            b = QPushButton(metin)
            b.setToolTip(ipucu)
            b.clicked.connect(fn)
            ust.addWidget(b)
        self.ara = QLineEdit()
        self.ara.setPlaceholderText("Ara...")
        self.ara.setClearButtonEnabled(True)
        ust.addWidget(self.ara)
        sl.addLayout(ust)
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        self.view.doubleClicked.connect(lambda _: self.kapali_seanslar())
        self.ara.textChanged.connect(self.proxy.setFilterFixedString)
        sl.addWidget(self.view, 1)
        self.durum = QLabel()
        sl.addWidget(self.durum)
        bolucu.addWidget(sol)

        sag = QTabWidget()
        kural = QWidget()
        kl = QVBoxLayout(kural)
        lbl = QLabel("İki dersin sınavları için kural: ortak öğrencisi varsa aynı güne gelmesin, kesinlikle aynı güne "
                     "gelmesin ya da (aynı seviyedekiler) aynı seansta yapılsın.")
        lbl.setWordWrap(True)
        kl.addWidget(lbl)
        grid = QGridLayout()
        self.ders1, self.ders2 = QComboBox(), QComboBox()
        for i, cb in enumerate((self.ders1, self.ders2)):
            cb.setEditable(True)
            cb.setInsertPolicy(QComboBox.NoInsert)
            grid.addWidget(QLabel(f"{i + 1}. ders:"), i, 0)
            grid.addWidget(cb, i, 1)
        self.kural_turu = QComboBox()
        for k, v in sinav.KURAL_TURLERI.items():
            self.kural_turu.addItem(v, k)
        grid.addWidget(QLabel("Kural:"), 2, 0)
        grid.addWidget(self.kural_turu, 2, 1)
        kl.addLayout(grid)
        b = QPushButton("Kural Ekle")
        b.clicked.connect(self.kural_ekle)
        kl.addWidget(b)
        self.kurallar = QListWidget()
        kl.addWidget(self.kurallar, 1)
        b = QPushButton("Seçili Kuralı Sil")
        b.clicked.connect(self.kural_sil)
        kl.addWidget(b)
        sag.addTab(kural, "Ders Kuralları")

        gun = QWidget()
        gl = QVBoxLayout(gun)
        lbl = QLabel("Dersin ya da sınıf seviyesinin sınavları yalnız seçilen günlerde yapılır (ör. 12. sınıflar "
                     "ilk iki gün).")
        lbl.setWordWrap(True)
        gl.addWidget(lbl)
        b = QPushButton("Gün Kuralı Ekle...")
        b.clicked.connect(self.gun_kurali_ekle)
        gl.addWidget(b)
        self.gun_kurallari = QListWidget()
        gl.addWidget(self.gun_kurallari, 1)
        b = QPushButton("Seçili Gün Kuralını Sil")
        b.clicked.connect(self.gun_kurali_sil)
        gl.addWidget(b)
        sag.addTab(gun, "Gün Kuralları")

        nobet = QWidget()
        nl = QVBoxLayout(nobet)
        lbl = QLabel("Her sınav günü için nöbetçi müdür yardımcısı (takvimde ve öğretmen imza cetvelinde yazılır). "
                     "Çift tıklayarak değiştirin.")
        lbl.setWordWrap(True)
        nl.addWidget(lbl)
        self.nobetciler = QListWidget()
        self.nobetciler.itemDoubleClicked.connect(lambda _: self.nobetci_sec())
        nl.addWidget(self.nobetciler, 1)
        b = QPushButton("Nöbetçi Seç...")
        b.clicked.connect(self.nobetci_sec)
        nl.addWidget(b)
        sag.addTab(nobet, "Nöbetçi Müdür Yrd.")
        bolucu.addWidget(sag)
        bolucu.setStretchFactor(0, 3)
        bolucu.setStretchFactor(1, 1)
        lay.addWidget(bolucu, 1)
        self._ilk = True
        self._dersler: list[str] = []

    def yenile(self) -> None:
        did = self.donem_id
        d = sinav.donem(self.db, did)
        if d is None:
            self.bilgi.setText("Sınav dönemi seçilmedi. Sağ üstten 'Yeni Dönem' ile dönem oluşturun.")
            self.model.ayarla([], [])
            for w in (self.kurallar, self.gun_kurallari, self.nobetciler):
                w.clear()
            self.durum.setText("")
            return
        varsayilan = d["ogretmen_gunluk_azami"] or 3
        self.bilgi.setText(
            f"Etkin öğretmenler görev alır; müdür ve müdür yardımcıları başlangıçta görev almaz. Bir öğretmen günde en "
            f"çok {varsayilan} görev alır (dönem ayarı; öğretmene özel sınır verilebilir). Komisyon öncelikle dersi "
            f"okutan, sonra aynı alandaki, sonra branşı uyan öğretmenlerden kurulur.")
        sinav.ogretmenleri_hazirla(self.db, did)
        rows = sinav.ogretmen_listesi(self.db, did)
        self.model.ayarla([[f"{r['ad']} {r['soyad']}", r["brans"] or "", r["unvan"] or "",
                            "Evet" if r["gorev_alir"] else "Hayır",
                            r["gunluk_azami"] if r["gunluk_azami"] else f"{varsayilan} (dönem)",
                            len(sinav.kume_coz(r["kapali_seanslar"])) or "", r["onceki_gorev"] or "",
                            r["gorev_sayisi"]] for r in rows],
                          [r["id"] for r in rows],
                          {i: RENK_PASIF for i, r in enumerate(rows) if not r["gorev_alir"]})
        if self._ilk and rows:
            ortak.sutunlari_sigdir(self.view)
            self._ilk = False
        alan = sum(1 for r in rows if r["gorev_alir"])
        self.durum.setText(f"{len(rows)} öğretmen, {alan} tanesi görev alıyor.")
        dersler = sorted({r["ders"] for r in self.db.q("SELECT DISTINCT ders FROM sinavlar WHERE donem_id = ?",
                                                        (did,))}, key=norm)
        for cb in (self.ders1, self.ders2):
            metin = cb.currentText()
            cb.clear()
            cb.addItems(dersler)
            cb.setCurrentText(metin)
        self._dersler = dersler
        self.kurallar.clear()
        for r in sinav.kurallar(self.db, did):
            it = QListWidgetItem(f"{r['ders1']}  ↔  {r['ders2']}\n   "
                                 f"{sinav.KURAL_TURLERI.get(r['tur'] or 'ortak_ogrenci', '')}")
            it.setData(Qt.UserRole, r["id"])
            self.kurallar.addItem(it)
        self.gun_kurallari.clear()
        for r in sinav.gun_kurallari(self.db, did):
            it = QListWidgetItem(sinav.gun_kurali_etiketi(r))
            it.setData(Qt.UserRole, r["id"])
            self.gun_kurallari.addItem(it)
        nobet = sinav.nobetciler(self.db, did)
        self.nobetciler.clear()
        for t in sorted({r["tarih"] for r in sinav.seanslar(self.db, did)}):
            it = QListWidgetItem(f"{tr(t)} {sinav.gun_adi(t)}:  " + (nobet[t]["ad"] if t in nobet else "—"))
            it.setData(Qt.UserRole, t)
            self.nobetciler.addItem(it)

    def _secili(self) -> list[int]:
        return [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)]

    def gorev_alir(self, alir: bool) -> None:
        did, ids = self.donem_id, self._secili()
        if not did or not ids:
            ortak.bilgi(self, "Önce listeden öğretmen seçin.")
            return
        for t in ids:
            sinav.ogretmen_ayarla(self.db, did, t, gorev_alir=int(alir))
        self.yenile()

    def gunluk_sinir(self) -> None:
        did, ids = self.donem_id, self._secili()
        if not did or not ids:
            ortak.bilgi(self, "Önce listeden öğretmen seçin.")
            return
        n, ok = QInputDialog.getInt(self, "Günlük Sınır", f"Seçilen {len(ids)} öğretmenin günde en çok görev sayısı "
                                                          "(0 = dönem ayarı):", 0, 0, 20)
        if ok:
            for t in ids:
                sinav.ogretmen_ayarla(self.db, did, t, gunluk_azami=n or None)
            self.yenile()

    def kapali_seanslar(self) -> None:
        did, ids = self.donem_id, self._secili()
        if not did or not ids:
            ortak.bilgi(self, "Önce listeden öğretmen seçin.")
            return
        seanslar = sinav.seanslar(self.db, did)
        if not seanslar:
            ortak.bilgi(self, "Bu dönemde seans yok. Önce 'Seans Çizelgesi' sekmesinden seansları oluşturun.")
            return
        r = self.db.q1("SELECT kapali_seanslar FROM sinav_ogretmenleri WHERE donem_id = ? AND ogretmen_id = ?",
                       (did, ids[0]))
        ad = self.model.rows[ortak.secili_satirlar(self.view, self.proxy)[0]][0]
        baslik = f"{ad} - görev alamayacağı seanslar" if len(ids) == 1 else \
            f"Seçilen {len(ids)} öğretmenin görev alamayacağı seanslar"
        d = SeansSecDialog(seanslar, sinav.kume_coz(r["kapali_seanslar"] if r else ""), baslik, self)
        if d.exec():
            for t in ids:
                sinav.ogretmen_ayarla(self.db, did, t, kapali_seanslar=d.secili())
            self.yenile()

    def nobetten_doldur(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        if not sinav.seanslar(self.db, did):
            ortak.bilgi(self, "Bu dönemde seans yok. Önce 'Seans Çizelgesi' sekmesinden seansları oluşturun.")
            return
        n = sinav.nobetten_doldur(self.db, did, self._secili() or None)
        self.yenile()
        ortak.bilgi(self, f"{n} öğretmenin kapalı seanslarına nöbet / müsait olmadığı günler eklendi.")

    def onceki_gorev(self) -> None:
        did, ids = self.donem_id, self._secili()
        if not did or not ids:
            ortak.bilgi(self, "Önce listeden öğretmen seçin.")
            return
        n, ok = QInputDialog.getInt(self, "Önceki Görev", f"Seçilen {len(ids)} öğretmenin bu eğitim yılında önceki "
                                                          "dönemlerde aldığı sınav görevi sayısı:", 0, 0, 500)
        if ok:
            for t in ids:
                sinav.ogretmen_ayarla(self.db, did, t, onceki_gorev=n)
            self.yenile()

    def kural_ekle(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        try:
            sinav.kural_ekle(self.db, did, self.ders1.currentText(), self.ders2.currentText(),
                             self.kural_turu.currentData())
        except ValueError as e:
            ortak.hata(self, str(e))
            return
        self.yenile()

    def kural_sil(self) -> None:
        it = self.kurallar.currentItem()
        if it is not None:
            sinav.kural_sil(self.db, it.data(Qt.UserRole))
            self.yenile()

    def gun_kurali_ekle(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        tarihler = sorted({r["tarih"] for r in sinav.seanslar(self.db, did)})
        if not tarihler:
            ortak.bilgi(self, "Bu dönemde seans yok. Önce 'Seans Çizelgesi' sekmesinden seansları oluşturun.")
            return
        d = GunKuraliDialog(self._dersler, tarihler, self)
        if not d.exec():
            return
        try:
            sinav.gun_kurali_ekle(self.db, did, d.tarihler(), d.ders.currentText().strip() or None,
                                  d.seviye.value() or None, d.kapsam.currentData())
        except ValueError as e:
            ortak.hata(self, str(e))
            return
        self.yenile()

    def gun_kurali_sil(self) -> None:
        it = self.gun_kurallari.currentItem()
        if it is not None:
            sinav.gun_kurali_sil(self.db, it.data(Qt.UserRole))
            self.yenile()

    def nobetci_sec(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        it = self.nobetciler.currentItem()
        if it is None:
            ortak.bilgi(self, "Önce listeden sınav gününü seçin.")
            return
        rows = self.db.q("SELECT id, ad || ' ' || soyad AS ad, unvan FROM ogretmenler WHERE aktif = 1 "
                         "ORDER BY unvan NOT LIKE '%Müdür%', ad, soyad")
        etiketler = ["(Yok)"] + [f"{r['ad']}" + (f" ({r['unvan']})" if r["unvan"] else "") for r in rows]
        secim, ok = QInputDialog.getItem(self, "Nöbetçi Müdür Yardımcısı", it.text().split(":")[0], etiketler, 0,
                                         False)
        if ok:
            i = etiketler.index(secim)
            sinav.nobetci_ayarla(self.db, did, it.data(Qt.UserRole), rows[i - 1]["id"] if i else None)
            self.yenile()


# ------------------------------------------------------------------ planlama

class GorevlilerDialog(QDialog):
    """Bir sınavın komisyon ve gözcüleri: elle ekleme, değiştirme, yer değiştirme, kilit, gelme durumu ve ücret."""

    def __init__(self, db, donem_id: int, sinav_id: int, parent=None):
        super().__init__(parent)
        self.db, self.donem_id, self.sinav_id = db, donem_id, sinav_id
        self.resize(820, 460)
        lay = QVBoxLayout(self)
        self.baslik = QLabel()
        self.baslik.setStyleSheet("font-weight:bold")
        lay.addWidget(self.baslik)
        ust = ortak.AkisDuzeni()
        for metin, fn in (("Başkan Ekle...", lambda: self.ekle(sinav.KOMISYON_BASKANI)),
                          ("Üye Ekle...", lambda: self.ekle(sinav.KOMISYON_UYESI)),
                          ("Gözcü Ekle...", lambda: self.ekle(sinav.GOZCU)), ("Değiştir...", self.degistir),
                          ("Yer Değiştir...", self.yer_degistir), ("Sil", self.sil),
                          ("Kilitle", lambda: self.guncelle(kilitli=1)), ("Kilidi Aç", lambda: self.guncelle(kilitli=0)),
                          ("Geldi", lambda: self.guncelle(durum=sinav.GELDI)),
                          ("Gelmedi", lambda: self.guncelle(durum=sinav.GELMEDI)),
                          ("Ücretsiz", lambda: self.guncelle(ucretsiz=1)), ("Ücretli", lambda: self.guncelle(ucretsiz=0))):
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        lay.addLayout(ust)
        self.model = ortak.TabloModeli(["Görev", "Öğretmen", "Branş", "Salon", "Kilitli", "Durum", "Ücret"])
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        lay.addWidget(self.view, 1)
        self.uyari = QLabel()
        self.uyari.setWordWrap(True)
        self.uyari.setStyleSheet("color:#a15c00")
        lay.addWidget(self.uyari)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.button(QDialogButtonBox.Close).setText("Kapat")
        bb.rejected.connect(self.accept)
        lay.addWidget(bb)
        self.yenile()

    def yenile(self) -> None:
        self.kayit = next((r for r in sinav.sinav_listesi(self.db, self.donem_id) if r["id"] == self.sinav_id), None)
        if self.kayit is None:
            self.model.ayarla([], [])
            return
        self.setWindowTitle(f"Görevliler - {self.kayit['adi']}")
        self.baslik.setText(f"{self.kayit['adi']}  —  {self.kayit['seans'] or 'seansa yerleşmedi'}")
        g = sorted(self.kayit["gorevliler"], key=lambda x: (sinav.GOREVLER.index(x["gorev"]), x["id"]))
        self.model.ayarla([[x["gorev"], x["ad"], x["brans"] or "", x["salon"] or "", "Evet" if x["kilitli"] else "",
                            x["durum"] or "", "Ücretsiz" if x["ucretsiz"] else ""] for x in g], [x["id"] for x in g],
                          {i: ortak.RENK_UYARI for i, x in enumerate(g) if x["durum"] == sinav.GELMEDI})

    def _secili(self) -> list[int]:
        return [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)]

    def _uyar(self, uyarilar: list[str]) -> None:
        self.uyari.setText(("Uyarı: " + " ".join(uyarilar)) if uyarilar else "")

    def _aday_sec(self, baslik: str) -> int | None:
        adaylar = sinav.gorevli_adaylari(self.db, self.sinav_id)
        if not adaylar:
            ortak.bilgi(self, "Görev verilebilecek öğretmen yok.")
            return None
        etiketler = [f"{a['ad']} ({a['brans'] or '-'}) — {a['durum']}" + (f", {a['iliski']}" if a["iliski"] else "")
                     + f", {a['gorev_sayisi']} görev" for a in adaylar]
        secim, ok = QInputDialog.getItem(self, baslik, "Öğretmen (uygun olanlar üstte):", etiketler, 0, False)
        return adaylar[etiketler.index(secim)]["id"] if ok else None

    def ekle(self, gorev: str) -> None:
        if self.kayit is None or not self.kayit["seans_id"]:
            ortak.bilgi(self, "Sınav seansa yerleşmeden görevli eklenemez.")
            return
        t = self._aday_sec(f"{gorev} Ekle")
        if t is None:
            return
        salon_id = None
        if gorev == sinav.GOZCU:
            salonlar = self.db.q("SELECT DISTINCT sl.id, sl.ad FROM sinav_ogrencileri so JOIN sinav_salonlari sl "
                                 "ON sl.id = so.salon_id WHERE so.sinav_id = ? ORDER BY sl.sira, sl.id",
                                 (self.sinav_id,))
            if salonlar:
                etiketler = ["(Salonsuz)"] + [r["ad"] for r in salonlar]
                secim, ok = QInputDialog.getItem(self, "Gözcü Salonu", "Salon:", etiketler, 1, False)
                if not ok:
                    return
                i = etiketler.index(secim)
                salon_id = salonlar[i - 1]["id"] if i else None
        self._uyar(sinav.gorevli_ekle(self.db, self.sinav_id, t, gorev, salon_id))
        self.yenile()

    def degistir(self) -> None:
        ids = self._secili()
        if not ids:
            ortak.bilgi(self, "Önce listeden görevi seçin.")
            return
        t = self._aday_sec("Görevi Başka Öğretmene Ver")
        if t is not None:
            self._uyar(sinav.gorevli_degistir(self.db, ids[0], ogretmen_id=t))
            self.yenile()

    def yer_degistir(self) -> None:
        ids = self._secili()
        if not ids or self.kayit is None:
            ortak.bilgi(self, "Önce listeden görevi seçin.")
            return
        diger = [(g, r) for r in sinav.sinav_listesi(self.db, self.donem_id)
                 if r["tarih"] and r["tarih"] == self.kayit["tarih"] for g in r["gorevliler"] if g["id"] != ids[0]]
        if not diger:
            ortak.bilgi(self, "Aynı gün yer değiştirilebilecek başka görev yok.")
            return
        etiketler = [f"{g['ad']} — {g['gorev']}, {r['adi']} ({sinav.seans_etiketi(r, uzun=False)})" for g, r in diger]
        secim, ok = QInputDialog.getItem(self, "Yer Değiştir", "Seçili görevin öğretmeniyle yer değiştirecek görev:",
                                         etiketler, 0, False)
        if ok:
            self._uyar(sinav.gorevli_degistir(self.db, ids[0], diger_id=diger[etiketler.index(secim)][0]["id"]))
            self.yenile()

    def sil(self) -> None:
        ids = self._secili()
        if ids and ortak.onay(self, f"Seçilen {len(ids)} görev silinsin mi?"):
            sinav.gorevli_sil(self.db, ids)
            self.yenile()

    def guncelle(self, **vals) -> None:
        ids = self._secili()
        if not ids:
            ortak.bilgi(self, "Önce listeden görevi seçin.")
            return
        sinav.gorevli_guncelle(self.db, ids, **vals)
        self.yenile()


class PlanlamaSekmesi(_Sekme):
    BASLIKLAR = ["Tarih", "Gün", "Saat", "Ders", "Seviye", "Grup", "Şekil", "Öğrenci", "Salonlar", "Komisyon",
                 "Gözcüler", "Çakılı"]

    def __init__(self, sayfa):
        super().__init__(sayfa)
        self._bulgular: dict[int, str] = {}
        self._calisiyor = False
        lay = QVBoxLayout(self)
        ust = ortak.AkisDuzeni()
        self.sure = QSpinBox()
        self.sure.setRange(2, 600)
        self.sure.setValue(10)
        self.sure.setSuffix(" sn")
        self.sure.setToolTip("Otomatik yerleştirmenin en uzun çalışma süresi.")
        ust.addWidget(ortak.etiketli("Süre sınırı:", self.sure))
        self.koru = QCheckBox("Yalnız yerleşmemişleri yerleştir")
        self.koru.setToolTip("Seansa yerleşmiş sınavlar yerinde kalır; yalnız yerleşmemiş sınavlar boşluklara konur.")
        ust.addWidget(self.koru)
        self.dugmeler: list[QPushButton] = []
        for metin, fn, ipucu in (
                ("Hepsini Yap", lambda: self.planla(True),
                 "Sınavları yerleştirir, görevlileri atar ve öğrencileri salonlara dağıtır."),
                ("Sınavları Yerleştir", lambda: self.planla(False), "Çakılı olmayan sınavları seanslara yerleştirir."),
                ("Görevlileri Ata", self.gorevlileri_ata, "Komisyon ve gözcüleri atar; kilitli görevler korunur."),
                ("Salonlara Yerleştir", self.salonlara_yerlestir, "Yazılı sınav öğrencilerini salon ve sıralara dağıtır."),
                ("Denetle", self.denetle, "Planı bütün kurallara göre denetler."),
                ("Görevliler...", self.gorevliler, "Seçili sınavın komisyon ve gözcülerini elle düzenler; gelmeyen ve "
                                                   "ücretsiz görevleri işaretler."),
                ("Seansını Değiştir...", self.seans_degistir, "Seçili sınavı elle başka seansa alır ve çakılı yapar."),
                ("Çakılı / Serbest", self.cakili_degistir, "Çakılı sınavın seansını otomatik planlama değiştirmez."),
                ("En Az Gün", self.en_az_gun, "Sınavların sığdığı en az sınav günü sayısını hesaplar; planı "
                                              "değiştirmez."),
                ("Planı Temizle", self.temizle, "Çakılı olmayan sınavların seans yerleşimini siler.")):
            b = QPushButton(metin)
            b.setToolTip(ipucu)
            b.clicked.connect(fn)
            ust.addWidget(b)
            self.dugmeler.append(b)
        self.dugmeler[0].setStyleSheet("font-weight:bold")
        lay.addLayout(ust)
        bolucu = QSplitter(Qt.Vertical)
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        self.view.doubleClicked.connect(lambda _: self.seans_degistir())
        bolucu.addWidget(self.view)
        self.sonuc = QPlainTextEdit()
        self.sonuc.setReadOnly(True)
        self.sonuc.setPlaceholderText("İşlem sonuçları ve denetim bulguları burada görünür. Renkler: kırmızı = "
                                      "yerleşmemiş, sarı = denetimde sorun bulunan, mavi = çakılı sınav.")
        bolucu.addWidget(self.sonuc)
        bolucu.setStretchFactor(0, 3)
        bolucu.setStretchFactor(1, 1)
        lay.addWidget(bolucu, 1)
        self.durum = QLabel()
        lay.addWidget(self.durum)
        self._ilk = True
        self._yuklu_donem: object = object()

    def yenile(self) -> None:
        did = self.donem_id
        if did != self._yuklu_donem:
            self._yuklu_donem = did
            self._bulgular = {}
            self.sonuc.clear()
        secili = self._secili()
        rows = sinav.sinav_listesi(self.db, did)
        d = sinav.donem(self.db, did)
        self._kayitlar = {r["id"]: r for r in rows}
        renk = {}
        for i, r in enumerate(rows):
            if not r["seans_id"] and r["ogrenci_sayisi"]:
                renk[i] = ortak.RENK_KRITIK
            elif r["id"] in self._bulgular:
                renk[i] = ortak.RENK_UYARI
            elif r["cakili"]:
                renk[i] = ortak.RENK_BILGI
        self.model.ayarla([[tr(r["tarih"]), sinav.gun_adi(r["tarih"]) if r["tarih"] else "",
                            (r["tarih"] and sinav.ozel_saat(d, r["sekil"])) or
                            (f"{r['baslangic']}-{r['bitis']}" if r["baslangic"] else
                             (f"{r['sira']}. oturum" if r["sira"] else "")),
                            r["ders"], r["seviye"] or "", r["grup"] or "", r["sekil"] or "", r["ogrenci_sayisi"],
                            r["salonlar"], ", ".join(r["komisyon"]), ", ".join(r["gozculer"]),
                            "Evet" if r["cakili"] else ""] for r in rows], [r["id"] for r in rows], renk)
        if self._ilk and rows:
            ortak.sutunlari_sigdir(self.view)
            self._ilk = False
        if secili:
            for i in range(self.proxy.rowCount()):
                if self.model.kimlik(self.proxy.mapToSource(self.proxy.index(i, 0)).row()) == secili[0]:
                    self.view.selectRow(i)
                    break
        planli = sum(1 for r in rows if r["seans_id"])
        bos = sum(1 for r in rows if not r["seans_id"] and r["ogrenci_sayisi"])
        self.durum.setText(f"{len(rows)} sınav: {planli} tanesi seansa yerleşmiş" +
                           (f", {bos} tanesi yerleşmemiş." if bos else ".") if did else "Sınav dönemi seçilmedi.")

    def _secili(self) -> list[int]:
        return [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)]

    def _yaz(self, satirlar: list[str]) -> None:
        self.sonuc.setPlainText("\n".join(satirlar).strip())

    def _mesgul(self, evet: bool) -> None:
        self._calisiyor = evet
        for b in self.dugmeler:
            b.setEnabled(not evet)
        if evet:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    @staticmethod
    def _plan_metni(s: sinav.PlanSonucu) -> list[str]:
        out = [s.ozet()]
        out += _metin_listesi("Yerleştirilemeyen sınavlar (nedeniyle):", [f"{ad}: {neden}" for _, ad, neden in
                                                                        s.yerlesemeyen])
        out += _metin_listesi("Notlar:", s.notlar)
        return out

    @staticmethod
    def _gorev_metni(g: sinav.GorevSonucu) -> list[str]:
        return [g.ozet()] + _metin_listesi("Görevlisi eksik sınavlar:", g.eksik) + \
            _metin_listesi("Uyarılar:", g.uyarilar)

    def _on_kosul(self) -> int | None:
        did = self.donem_gerekli()
        if not did or self._calisiyor:
            return None
        if not sinav.seanslar(self.db, did, sadece_acik=True):
            ortak.bilgi(self, "Bu dönemde açık seans yok. Önce 'Seans Çizelgesi' sekmesinden seansları oluşturun.")
            return None
        if not self.db.q1("SELECT 1 FROM sinavlar WHERE donem_id = ? LIMIT 1", (did,)):
            ortak.bilgi(self, "Bu dönemde sınav yok. 'Sınavlar ve Öğrenciler' sekmesinden e-Okul listesini aktarın "
                              "ya da sınav ekleyin.")
            return None
        return did

    def planla(self, hepsi: bool) -> None:
        did = self._on_kosul()
        if not did:
            return
        db, sure, koru = self.db, self.sure.value(), self.koru.isChecked()

        def is_():
            k = db.kopya()
            try:
                s = sinav.planla(k, did, sure_limit=sure, koru=koru)
                if not hepsi:
                    return s, None, None
                g = sinav.gorevlileri_ata(k, did)
                try:
                    salon = sinav.salonlara_yerlestir(k, did)
                except ValueError as e:
                    salon = str(e)
                return s, g, salon
            finally:
                k.close()

        def bitti(sonuc):
            self._mesgul(False)
            s, g, salon = sonuc
            satirlar = self._plan_metni(s)
            if g is not None:
                satirlar += [""] + self._gorev_metni(g)
            if salon:
                satirlar += ["", salon]
            self._bulgular = {}
            self._yaz(satirlar)
            self.yenile()

        def hata(tb: str):
            self._mesgul(False)
            ortak.hata(self, "Planlama yapılamadı:\n" + _son_satir(tb))
            self.yenile()

        self._mesgul(True)
        self.sonuc.setPlainText("Sınavlar yerleştiriliyor...")
        ortak.arka_planda(is_, bitti, hata)

    def gorevlileri_ata(self) -> None:
        did = self._on_kosul()
        if not did:
            return
        if not self.db.q1("SELECT 1 FROM sinavlar WHERE donem_id = ? AND seans_id IS NOT NULL LIMIT 1", (did,)):
            ortak.bilgi(self, "Seansa yerleşmiş sınav yok. Önce 'Sınavları Yerleştir'e basın.")
            return
        self._mesgul(True)
        try:
            g = sinav.gorevlileri_ata(self.db, did)
        except Exception as e:
            self._mesgul(False)
            ortak.hata(self, f"Görevlendirme yapılamadı:\n{e}")
            return
        self._mesgul(False)
        self._yaz(self._gorev_metni(g))
        self.yenile()

    def salonlara_yerlestir(self) -> None:
        did = self._on_kosul()
        if not did:
            return
        self._mesgul(True)
        try:
            metin = sinav.salonlara_yerlestir(self.db, did)
        except ValueError as e:
            self._mesgul(False)
            ortak.bilgi(self, str(e))
            return
        except Exception as e:
            self._mesgul(False)
            ortak.hata(self, f"Salon dağıtımı yapılamadı:\n{e}")
            return
        self._mesgul(False)
        self._yaz([metin])
        self.yenile()

    def denetle(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        bulgular = sinav.denetle(self.db, did)
        self._bulgular = {}
        for b in bulgular:
            if b.sinav_id and b.seviye != sinav.BILGI:
                self._bulgular.setdefault(b.sinav_id, b.seviye)
        if not bulgular:
            self._yaz(["Denetim tamam: sorun bulunmadı."])
        else:
            say = {s: sum(1 for b in bulgular if b.seviye == s) for s in (sinav.KRITIK, sinav.UYARI, sinav.BILGI)}
            self._yaz([", ".join(f"{n} {s.lower()}" for s, n in say.items() if n) + " bulundu.", ""] +
                      [f"[{b.seviye}] {b.mesaj}" for b in bulgular])
        self.yenile()

    def gorevliler(self) -> None:
        did, ids = self.donem_id, self._secili()
        if not did or not ids:
            ortak.bilgi(self, "Önce listeden sınav seçin.")
            return
        GorevlilerDialog(self.db, did, ids[0], self).exec()
        self.yenile()

    def en_az_gun(self) -> None:
        did = self._on_kosul()
        if not did:
            return
        db, sure = self.db, self.sure.value()

        def is_():
            k = db.kopya()
            try:
                return sinav.en_az_gun(k, did, sure_limit=sure)
            finally:
                k.close()

        def bitti(s):
            self._mesgul(False)
            self._yaz([s.ozet(), ""] + [f"{g} gün: {y}/{m} sınav yerleşti" for g, y, m in s.denemeler])

        def hata(tb: str):
            self._mesgul(False)
            ortak.hata(self, "En az gün hesaplanamadı:\n" + _son_satir(tb))

        self._mesgul(True)
        self.sonuc.setPlainText("En az sınav günü hesaplanıyor...")
        ortak.arka_planda(is_, bitti, hata)

    def seans_degistir(self) -> None:
        did, ids = self.donem_id, self._secili()
        if not did or not ids:
            ortak.bilgi(self, "Önce listeden sınav seçin.")
            return
        seanslar = sinav.seanslar(self.db, did)
        if not seanslar:
            ortak.bilgi(self, "Bu dönemde seans yok. Önce 'Seans Çizelgesi' sekmesinden seansları oluşturun.")
            return
        r = self._kayitlar[ids[0]]
        etiketler = ["(Seanstan çıkar)"] + [sinav.seans_etiketi(s) + ("" if s["acik"] else "  [kapalı seans]")
                                            for s in seanslar]
        mevcut = next((i + 1 for i, s in enumerate(seanslar) if s["id"] == r["seans_id"]), 0)
        secim, ok = QInputDialog.getItem(self, "Seansını Değiştir", f"{r['adi']} ({r['ogrenci_sayisi']} öğrenci):",
                                         etiketler, mevcut, False)
        if not ok:
            return
        i = etiketler.index(secim)
        sid = seanslar[i - 1]["id"] if i else None
        sinav.seans_ata(self.db, r["id"], sid, cakili=bool(sid))
        self.denetle() if self._bulgular else self.yenile()

    def cakili_degistir(self) -> None:
        ids = self._secili()
        if not ids:
            ortak.bilgi(self, "Önce listeden sınav seçin.")
            return
        for i in ids:
            r = self._kayitlar[i]
            if r["seans_id"]:
                sinav.sinav_guncelle(self.db, i, cakili=0 if r["cakili"] else 1)
        self.yenile()

    def temizle(self) -> None:
        did = self.donem_gerekli()
        if not did or self._calisiyor:
            return
        if ortak.onay(self, "Çakılı olmayan sınavların seans yerleşimi, görevlendirmeleri (kilitli olanlar hariç) ve "
                            "salon dağıtımı silinsin mi? Çakılı sınavlar yerinde kalır."):
            n = sinav.plani_temizle(self.db, did)
            self._bulgular = {}
            self._yaz([f"{n} sınavın seans yerleşimi temizlendi."])
            self.yenile()


# ------------------------------------------------------------------ çıktılar

class CiktilarSekmesi(_Sekme):
    def __init__(self, sayfa):
        super().__init__(sayfa)
        lay = QVBoxLayout(self)
        self.bilgi = QLabel()
        self.bilgi.setWordWrap(True)
        self.bilgi.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.bilgi)
        kutu = QGroupBox("Belgeler")
        grid = QGridLayout(kutu)
        for i, (ad, fn) in enumerate(sinav_belge.CIKTILAR):
            b = QPushButton(ad)
            b.clicked.connect(lambda _=False, f=fn: self.uret(f))
            grid.addWidget(b, i // 2, i % 2)
        lay.addWidget(kutu)
        h = QHBoxLayout()
        b = QPushButton("Tüm Çıktıları Üret")
        b.setStyleSheet("font-weight:bold")
        b.clicked.connect(self.hepsi)
        h.addWidget(b)
        b = QPushButton("Klasörü Aç")
        b.clicked.connect(self.klasoru_ac)
        h.addWidget(b)
        h.addStretch()
        lay.addLayout(h)
        lay.addStretch()

    def yenile(self) -> None:
        d = sinav.donem(self.db, self.donem_id)
        if d is None:
            self.bilgi.setText("Sınav dönemi seçilmedi. Sağ üstten 'Yeni Dönem' ile dönem oluşturun.")
            return
        yol = config.output_dir() / "Sınav Planlama" / (_guvenli(d["ad"]) or f"Dönem {d['id']}")
        self.bilgi.setText(f"Çıktılar şu klasöre kaydedilir:\n{yol}\n\nTakvim ve giriş belgeleri için sınavların "
                           "seanslara, görevlendirme belgeleri için görevlilerin, yoklama listeleri için öğrencilerin "
                           "salonlara yerleştirilmiş olması gerekir ('Planlama' sekmesi).")

    def uret(self, fn) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            yol = fn(self.db, did)
        except ValueError as e:
            QApplication.restoreOverrideCursor()
            ortak.bilgi(self, str(e))
            return
        except PermissionError:
            QApplication.restoreOverrideCursor()
            ortak.hata(self, "Dosya yazılamadı. Aynı adlı belge Word veya Excel'de açıksa kapatıp yeniden deneyin.")
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            ortak.hata(self, f"Belge üretilemedi:\n{e}")
            return
        QApplication.restoreOverrideCursor()
        ortak.kaydedildi(self, yol)

    def hepsi(self) -> None:
        did = self.donem_gerekli()
        if not did:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            yollar, hatalar = sinav_belge.hepsini_uret(self.db, did)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            ortak.hata(self, f"Belgeler üretilemedi:\n{e}")
            return
        QApplication.restoreOverrideCursor()
        if hatalar:
            ortak.bilgi(self, f"{len(yollar)} belge üretildi. Üretilemeyenler:\n- " + "\n- ".join(hatalar))
        if yollar:
            ortak.kaydedildi(self, yollar[0].parent, coklu=True)

    def klasoru_ac(self) -> None:
        did = self.donem_gerekli()
        if did:
            ortak.dosya_ac(sinav_belge.klasor(self.db, did))


# ------------------------------------------------------------------ sayfa

class SinavSayfasi(QTabWidget):
    """Sorumluluk / beceri / ortak sınavların planlanması."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        kose = QWidget()
        h = QHBoxLayout(kose)
        h.setContentsMargins(4, 2, 4, 2)
        h.addWidget(QLabel("Sınav dönemi:"))
        self.donem = QComboBox()
        self.donem.setMinimumWidth(280)
        self.donem.currentIndexChanged.connect(lambda _: self._donem_degisti())
        h.addWidget(self.donem)
        for metin, fn in (("Yeni Dönem", self.donem_yeni), ("Düzenle", self.donem_duzenle), ("Sil", self.donem_sil)):
            b = QPushButton(metin)
            b.clicked.connect(fn)
            h.addWidget(b)
        self.setCornerWidget(kose, Qt.TopRightCorner)
        self.seans = SeansSekmesi(self)
        self.sinavlar = SinavlarSekmesi(self)
        self.ogretmenler = OgretmenlerSekmesi(self)
        self.salonlar = CrudSayfasi(db, SALON_VARLIK)
        self.planlama = PlanlamaSekmesi(self)
        self.ciktilar = CiktilarSekmesi(self)
        self.addTab(self.seans, "Seans Çizelgesi")
        self.addTab(self.sinavlar, "Sınavlar ve Öğrenciler")
        self.addTab(self.ogretmenler, "Öğretmenler")
        self.addTab(self.salonlar, "Salonlar")
        self.addTab(self.planlama, "Planlama")
        self.addTab(self.ciktilar, "Çıktılar")
        self.donemleri_doldur()

    @property
    def donem_id(self) -> int | None:
        return self.donem.currentData()

    def donemleri_doldur(self, sec: int | None = None) -> None:
        secili = sec if sec is not None else self.donem_id
        self.donem.blockSignals(True)
        self.donem.clear()
        for r in sinav.donemler(self.db):
            self.donem.addItem(r["ad"], r["id"])
        if self.donem.count() == 0:
            self.donem.addItem("(Dönem yok)", None)
        i = self.donem.findData(secili) if secili is not None else -1
        self.donem.setCurrentIndex(max(0, i))
        self.donem.blockSignals(False)

    def _donem_degisti(self) -> None:
        w = self.currentWidget()
        if w is not None and hasattr(w, "yenile"):
            w.yenile()

    def yenile(self) -> None:
        self.donemleri_doldur()
        self._donem_degisti()

    def donem_yeni(self) -> None:
        d = FormDialog(self.db, DONEM_VARLIK, None, self, {"ad": _varsayilan_donem_adi(), "tur": "Sorumluluk"})
        if d.exec():
            self.donemleri_doldur(d.kayit_id)
            self._donem_degisti()

    def donem_duzenle(self) -> None:
        r = sinav.donem(self.db, self.donem_id)
        if r is None:
            ortak.bilgi(self, "Düzenlenecek sınav dönemi yok. 'Yeni Dönem' ile oluşturun.")
            return
        if FormDialog(self.db, DONEM_VARLIK, dict(r), self).exec():
            self.donemleri_doldur()
            self._donem_degisti()

    def donem_sil(self) -> None:
        r = sinav.donem(self.db, self.donem_id)
        if r is None:
            return
        n = self.db.q1("SELECT COUNT(*) n FROM sinavlar WHERE donem_id = ?", (r["id"],))["n"]
        if not ortak.onay(self, f"'{r['ad']}' dönemi; seansları, {n} sınavı, öğrenci listeleri ve görevlendirmeleriyle "
                                "birlikte silinsin mi? Bu işlem geri alınamaz."):
            return
        self.db.delete("sinav_donemleri", r["id"])
        self.donemleri_doldur()
        self._donem_degisti()
