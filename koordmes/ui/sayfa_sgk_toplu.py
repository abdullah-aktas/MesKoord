"""SGK toplu işlemleri: toplu giriş/çıkış tarihi, aylık listenin dışında kalanlar, öğrenci bilgi kontrolü."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QCheckBox, QComboBox, QDateEdit, QLabel, QPushButton, QVBoxLayout, QWidget

from ..mevzuat import AYLAR, FESIH_NEDENLERI, YERLESTIRME_TURLERI
from ..services import excel_io, sgk_toplu
from ..services.utils import tr
from . import ortak


def _aciklama(metin: str) -> QLabel:
    lbl = QLabel(metin)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color:#555")
    return lbl


def _tarih_secici() -> QDateEdit:
    d = QDateEdit(QDate.currentDate())
    d.setCalendarPopup(True)
    d.setDisplayFormat("dd.MM.yyyy")
    return d


def _qdate(d: QDateEdit) -> date:
    q = d.date()
    return date(q.year(), q.month(), q.day())


class _SinifFiltresi(QComboBox):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setMinimumWidth(160)

    def doldur(self):
        secili = self.currentData()
        self.blockSignals(True)
        self.clear()
        self.addItem("(Tüm sınıflar)", None)
        for r in self.db.q("SELECT id, ad FROM siniflar ORDER BY seviye, ad"):
            self.addItem(r["ad"], r["id"])
        self.setCurrentIndex(max(0, self.findData(secili)))
        self.blockSignals(False)

    def kimlikler(self) -> list[int] | None:
        return [self.currentData()] if self.currentData() is not None else None


class _ListeSekmesi(QWidget):
    """Üstte araç çubuğu, altta seçilebilir tablo; Excel'e aktarma ortak."""
    BASLIKLAR: list[str] = []
    DOSYA = "Liste.xlsx"

    def __init__(self, db, aciklama: str, parent=None):
        super().__init__(parent)
        self.db = db
        self.lay = QVBoxLayout(self)
        self.lay.addWidget(_aciklama(aciklama))
        self.ust = ortak.AkisDuzeni()
        self.lay.addLayout(self.ust)
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        self.lay.addWidget(self.view, 1)
        self.durum = QLabel()
        self.lay.addWidget(self.durum)

    def dugmeler(self, ogeler):
        for metin, fn in ogeler:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            self.ust.addWidget(b)
        self.ust.addStretch()

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def secili(self) -> list:
        return [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)]

    def excel(self):
        yol = ortak.kaydet_yolu(self, self.DOSYA)
        if yol:
            ortak.kaydedildi(self, excel_io.tablo_yaz(yol, self.BASLIKLAR, self.model.rows, self.DOSYA[:-5]))


class TopluGirisTarihi(_ListeSekmesi):
    BASLIKLAR = ["Sınıf", "No", "Ad Soyad", "T.C.", "Önerilen Tür", "Önceki Kayıt"]
    DOSYA = "Sigortası Olmayan Öğrenciler.xlsx"

    def __init__(self, db, parent=None):
        super().__init__(db, "Sigortası (açık yerleştirmesi) olmayan aktif öğrenciler — nakil gelenler, yeni kayıtlar, "
                             "dönem başında yeniden başlayanlar. Seçilenlere tek tarihle sigorta başlangıcı açılır; tür "
                             "'otomatik' ise işletmeye giden sınıflarda işletmede mesleki eğitim, diğerlerinde okulda "
                             "alan eğitimi kabul edilir. Açılan kayıtlar 'İşe Giriş / İşten Ayrılış' sekmesinde "
                             "bildirim bekleyenlere düşer. Seçim yoksa listedeki tüm öğrencilere uygulanır.", parent)
        self.sinif = _SinifFiltresi(db)
        self.sinif.currentIndexChanged.connect(lambda _: self.yenile())
        self.ust.addWidget(ortak.etiketli("Sınıf:", self.sinif))
        self.tarih = _tarih_secici()
        self.tarih.dateChanged.connect(lambda _: self.yenile())
        self.ust.addWidget(ortak.etiketli("Giriş tarihi:", self.tarih))
        self.tur = QComboBox()
        self.tur.addItem("Tür: otomatik (sınıfa göre)", None)
        for t in YERLESTIRME_TURLERI:
            self.tur.addItem(t, t)
        self.ust.addWidget(self.tur)
        self.dugmeler([("Giriş Tarihini İşle", self.uygula), ("Excel'e Aktar", self.excel)])

    def yenile(self):
        self.sinif.doldur()
        self.liste = sgk_toplu.giris_adaylari(self.db, _qdate(self.tarih), self.sinif.kimlikler())
        self.model.ayarla([[a.sinif, a.okul_no, a.ad, a.tc, a.onerilen_tur, a.son_kayit] for a in self.liste],
                          [a.ogrenci_id for a in self.liste])
        ortak.sutunlari_sigdir(self.view)
        self.durum.setText(f"{len(self.liste)} öğrencinin sigortası yok.")

    def uygula(self):
        ids = self.secili() or [a.ogrenci_id for a in self.liste]
        if not ids:
            ortak.bilgi(self, "Sigortası olmayan öğrenci yok.")
            return
        t = _qdate(self.tarih)
        if not ortak.onay(self, f"{len(ids)} öğrenciye {tr(t)} tarihli sigorta girişi açılsın mı?"):
            return
        s = sgk_toplu.toplu_giris(self.db, ids, t, self.tur.currentData())
        self.yenile()
        ortak.bilgi(self, s.metin("sigorta girişi açıldı"))


class TopluCikisTarihi(_ListeSekmesi):
    BASLIKLAR = ["Sınıf", "No", "Ad Soyad", "T.C.", "Tür", "İşletme", "Başlangıç", "Bitiş"]
    DOSYA = "Açık Sigorta Kayıtları.xlsx"

    def __init__(self, db, parent=None):
        super().__init__(db, "Açık yerleştirmelere (sigortalara) tek tarihle çıkış işlenir: dönem sonu, mezuniyet, "
                             "nakil giden, kayıt silme. Çıkış işlenen kayıtlar 'İşe Giriş / İşten Ayrılış' sekmesinde "
                             "işten ayrılış bildirimi bekleyenlere düşer (ara tatil, yarıyıl ve yaz tatillerinde "
                             "ayrılış bildirilmez). Seçim yoksa listedeki tüm kayıtlara uygulanır.", parent)
        self.sinif = _SinifFiltresi(db)
        self.sinif.currentIndexChanged.connect(lambda _: self.yenile())
        self.ust.addWidget(ortak.etiketli("Sınıf:", self.sinif))
        self.tarihsiz = QCheckBox("Yalnızca bitiş tarihi girilmemişler")
        self.tarihsiz.setChecked(True)
        self.tarihsiz.toggled.connect(lambda _: self.yenile())
        self.ust.addWidget(self.tarihsiz)
        self.tarih = _tarih_secici()
        self.ust.addWidget(ortak.etiketli("Çıkış tarihi:", self.tarih))
        self.neden = QComboBox()
        self.neden.addItem("Süre bitti (dönem sonu)", "")
        for n in FESIH_NEDENLERI:
            self.neden.addItem(n, n)
        self.ust.addWidget(ortak.etiketli("Neden:", self.neden))
        self.dugmeler([("Çıkış Tarihini İşle", self.uygula), ("Excel'e Aktar", self.excel)])

    def yenile(self):
        self.sinif.doldur()
        self.liste = sgk_toplu.cikis_adaylari(self.db, self.sinif.kimlikler(), self.tarihsiz.isChecked())
        self.model.ayarla([[c.sinif, c.okul_no, c.ad, c.tc, c.tur, c.isletme, tr(c.baslangic), tr(c.bitis)]
                           for c in self.liste], [c.yerlestirme_id for c in self.liste])
        ortak.sutunlari_sigdir(self.view)
        self.durum.setText(f"{len(self.liste)} açık sigorta kaydı.")

    def uygula(self):
        ids = self.secili() or [c.yerlestirme_id for c in self.liste]
        if not ids:
            ortak.bilgi(self, "Açık sigorta kaydı yok.")
            return
        t = _qdate(self.tarih)
        if not ortak.onay(self, f"{len(ids)} kayda {tr(t)} tarihli çıkış ({self.neden.currentText()}) işlensin mi?"):
            return
        s = sgk_toplu.toplu_cikis(self.db, ids, t, self.neden.currentData())
        self.yenile()
        ortak.bilgi(self, s.metin("çıkış tarihi işlendi"))


class ListeDisiKalanlar(_ListeSekmesi):
    BASLIKLAR = ["Sınıf", "No", "Ad Soyad", "T.C.", "Durum", "Neden"]
    DOSYA = "Aylık Prim Listesi Dışında Kalanlar.xlsx"

    def __init__(self, db, parent=None):
        super().__init__(db, "Seçilen ayın prim hizmet listesine girmeyen aktif öğrenciler ve nedenleri; listede olup "
                             "belgede sorun çıkaracak kayıtlar 'Uyarı' olarak gösterilir. Bildirge vermeden önce "
                             "kontrol edin.", parent)
        self.ay = ortak.AySecici()
        self.ay.degisti.connect(lambda *_: self.yenile())
        self.ust.addWidget(self.ay)
        self.dugmeler([("Excel'e Aktar", self.excel)])

    def yenile(self):
        self.liste = sgk_toplu.liste_disi_kalanlar(self.db, *self.ay.deger())
        self.model.ayarla([[x.sinif, x.okul_no, x.ad, x.tc, x.seviye, x.neden] for x in self.liste],
                          [x.ogrenci_id for x in self.liste],
                          {i: ortak.RENK_UYARI if x.seviye == "Uyarı" else ortak.RENK_BILGI
                           for i, x in enumerate(self.liste)})
        ortak.sutunlari_sigdir(self.view, 420)
        yil, ay = self.ay.deger()
        n = sum(1 for x in self.liste if x.seviye == "Liste dışı")
        self.durum.setText(f"{AYLAR[ay - 1]} {yil}: {n} öğrenci liste dışında, "
                           f"{len(self.liste) - n} uyarı.")

    def excel(self):
        yil, ay = self.ay.deger()
        yol = ortak.kaydet_yolu(self, f"Prim Listesi Dışında Kalanlar {AYLAR[ay - 1]} {yil}.xlsx")
        if yol:
            ortak.kaydedildi(self, excel_io.tablo_yaz(yol, self.BASLIKLAR, self.model.rows,
                                                      f"Aylık Prim Listesi Dışında Kalanlar - {AYLAR[ay - 1]} {yil}"))


class BilgiKontrolu(_ListeSekmesi):
    BASLIKLAR = ["Sınıf", "No", "Ad Soyad", "Eksik / Hatalı Bilgiler"]
    DOSYA = "Öğrenci Bilgi Kontrolü.xlsx"

    def __init__(self, db, parent=None):
        super().__init__(db, "SGK bildirgeleri ve ücret ödemesi için eksik ya da hatalı öğrenci bilgileri (T.C. kimlik "
                             "no, doğum tarihi, cinsiyet, sınıf, IBAN, telefon). Satıra çift tıklayıp öğrenci kaydını "
                             "düzeltin ya da e-Okul listesini Veri Aktarımı'ndan yeniden yükleyin.", parent)
        self.sigortali = QCheckBox("Yalnızca sigortalı öğrenciler")
        self.sigortali.setChecked(True)
        self.sigortali.toggled.connect(lambda _: self.yenile())
        self.ust.addWidget(self.sigortali)
        self.dugmeler([("Excel'e Aktar", self.excel)])
        self.view.doubleClicked.connect(lambda _: self.duzenle())

    def yenile(self):
        self.liste = sgk_toplu.bilgi_kontrol(self.db, self.sigortali.isChecked())
        self.model.ayarla([[x.sinif, x.okul_no, x.ad, ", ".join(x.eksikler)] for x in self.liste],
                          [x.ogrenci_id for x in self.liste])
        ortak.sutunlari_sigdir(self.view, 520)
        self.durum.setText(f"{len(self.liste)} öğrencide eksik/hatalı bilgi var." if self.liste
                           else "Eksik bilgi bulunmadı.")

    def duzenle(self):
        from .crud import FormDialog
        from .varliklar import OGRENCILER
        ids = self.secili()
        if not ids:
            return
        kayit = self.db.q1("SELECT * FROM ogrenciler WHERE id = ?", (ids[0],))
        if kayit and FormDialog(self.db, OGRENCILER, dict(kayit), self).exec():
            self.yenile()
