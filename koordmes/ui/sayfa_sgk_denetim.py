"""SGK listesi karşılaştırma ve SGK hata/ceza riskleri ekranları."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
                               QWidget)

from ..services import okuyucu, sgk_karsilastirma, sgk_risk
from ..services.utils import para
from . import ortak
from .sayfa_aktarim import surukle_dosyalar

RENKLER = {"Kritik": ortak.RENK_KRITIK, "Uyarı": ortak.RENK_UYARI, "Bilgi": ortak.RENK_BILGI}


def _aciklama(metin: str) -> QLabel:
    lbl = QLabel(metin)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color:#555")
    return lbl


def _dugmeler(lay: QHBoxLayout, tanimlar) -> list[QPushButton]:
    out = []
    for metin, fn in tanimlar:
        b = QPushButton(metin)
        b.clicked.connect(fn)
        lay.addWidget(b)
        out.append(b)
    return out


class SgkKarsilastirma(QWidget):
    BASLIKLAR = ["Seviye", "Bulgu", "Öğrenci", "T.C.", "Okul kaydı", "SGK listesi", "Öneri", "Düzeltme",
                 "Olası ceza (TL)"]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.liste: sgk_karsilastirma.SgkListesi | None = None
        self.sonuc: sgk_karsilastirma.KarsilastirmaSonucu | None = None
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.addWidget(_aciklama(
            "e-Bildirge'den aldığınız aylık prim hizmet listesini (APHB), sigortalı/işe giriş listesini veya hizmet "
            "dökümünü (Excel, PDF, Word, HTML, ZIP) yükleyin ya da buraya sürükleyin. Öğrenciler T.C. ile, T.C. "
            "uyuşmazsa ad soyad ile eşleştirilir; eksik/fazla bildirim, belge türü, prim günü, PEK, giriş-çıkış "
            "tarihi ve ad/T.C. farkları listelenir. Okul kaydı yanlışsa seçip 'Düzeltmeleri Uygula' deyin; SGK "
            "tarafı yanlışsa öneriye göre e-Bildirge'de düzeltin."))
        ust = ortak.AkisDuzeni()
        _, self.son_btn = _dugmeler(ust, [("SGK Listesi Yükle...", self.dosya_sec),
                                          ("Son İndirileni Kullan", self.son_indirilen)])
        self.elle = QCheckBox("Dönem:")
        self.elle.setToolTip("İşaretlemezseniz listedeki dönem (yoksa içinde bulunulan ay) kullanılır.")
        ust.addWidget(self.elle)
        self.ay = ortak.AySecici()
        self.ay.setEnabled(False)
        self.elle.toggled.connect(self.ay.setEnabled)
        self.elle.toggled.connect(lambda *_: self.karsilastir())
        self.ay.degisti.connect(lambda *_: self.elle.isChecked() and self.karsilastir())
        ust.addWidget(self.ay)
        self.duzelt_btn, self.excel_btn = _dugmeler(ust, [("Seçili Düzeltmeleri Uygula", self.duzelt),
                                                          ("Excel'e Aktar", self.excel)])
        ust.addStretch()
        lay.addLayout(ust)
        self.kaynak = QLabel()
        self.kaynak.setWordWrap(True)
        lay.addWidget(self.kaynak)
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        self.view.doubleClicked.connect(lambda *_: self.duzelt())
        lay.addWidget(self.view, 1)
        self.ozet = QLabel("Henüz liste yüklenmedi.")
        self.ozet.setWordWrap(True)
        self.ozet.setStyleSheet("font-weight:bold")
        lay.addWidget(self.ozet)
        self.notlar = _aciklama("")
        lay.addWidget(self.notlar)
        self._dugmeleri_guncelle()

    def showEvent(self, e):
        super().showEvent(e)
        son = sgk_karsilastirma.son_liste()
        self.son_btn.setEnabled(son is not None)
        self.son_btn.setToolTip(f"{son[0].name} ({son[1].replace('T', ' ')})" if son else
                                "Bağlantılar ekranında indirilen SGK listesi yok.")

    def dragEnterEvent(self, e):
        if surukle_dosyalar(e):
            e.acceptProposedAction()

    def dropEvent(self, e):
        yollar = surukle_dosyalar(e)
        if yollar:
            e.acceptProposedAction()
            self.yukle(yollar)

    def dosya_sec(self):
        yollar, _ = QFileDialog.getOpenFileNames(self, "SGK listesini seçin", str(Path.home()),
                                                 okuyucu.DOSYA_FILTRESI)
        if yollar:
            self.yukle(yollar)

    def son_indirilen(self):
        son = sgk_karsilastirma.son_liste()
        if son:
            self.yukle([son[0]])

    def yukle(self, yollar) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            liste = sgk_karsilastirma.listeyi_oku(list(yollar))
        finally:
            QApplication.restoreOverrideCursor()
        if not liste.kayitlar:
            ortak.hata(self, "\n".join(liste.hatalar) or "Dosyada SGK listesi bulunamadı.")
            return
        self.liste = liste
        donem = liste.donem
        if donem and not self.elle.isChecked():
            self.ay.blockSignals(True)
            self.ay.ayarla(*donem)
            self.ay.blockSignals(False)
        tur = "aylık prim hizmet listesi" if liste.aphb else "sigortalı / giriş-çıkış listesi"
        self.kaynak.setText(f"<b>{len(liste.kayitlar)} kayıt</b> ({tur}): {', '.join(liste.kaynaklar)}"
                            + (f"<br><span style='color:#a00'>{'; '.join(liste.hatalar)}</span>"
                               if liste.hatalar else ""))
        self.karsilastir()

    def karsilastir(self) -> None:
        if self.liste is None:
            return
        yil, ay = self.ay.deger() if self.elle.isChecked() else (None, None)
        self.sonuc = sgk_karsilastirma.karsilastir(self.db, self.liste, yil, ay)
        farklar = self.sonuc.farklar
        rows = [[f.seviye, f.tur, f.ogrenci, f.tc, f.okul, f.sgk, f.oneri, f.eylem_adi,
                 para(f.tahmini_ceza) if f.tahmini_ceza else ""] for f in farklar]
        self.model.ayarla(rows, list(range(len(farklar))),
                          {i: RENKLER[f.seviye] for i, f in enumerate(farklar) if f.seviye in RENKLER})
        ortak.sutunlari_sigdir(self.view)
        self.ozet.setText(self.sonuc.ozet())
        self.notlar.setText("\n".join(self.sonuc.notlar))
        self._dugmeleri_guncelle()

    def _dugmeleri_guncelle(self):
        self.excel_btn.setEnabled(self.sonuc is not None)
        self.duzelt_btn.setEnabled(bool(self.sonuc and any(f.eylem for f in self.sonuc.farklar)))

    def secili_farklar(self) -> list[sgk_karsilastirma.Fark]:
        if self.sonuc is None:
            return []
        return [self.sonuc.farklar[self.model.kimlik(r)] for r in ortak.secili_satirlar(self.view, self.proxy)]

    def duzelt(self, sormadan: bool = False) -> None:
        secili = [f for f in self.secili_farklar() if f.eylem]
        if not secili:
            ortak.bilgi(self, "Otomatik düzeltmesi olan bulguları (Düzeltme sütunu dolu) seçiniz.")
            return
        if not sormadan and not ortak.onay(self, f"{len(secili)} bulgu için okul kayıtları düzeltilecek:\n\n"
                                           + "\n".join(f"• {f.ogrenci}: {f.eylem_adi}" for f in secili[:15])
                                           + ("\n..." if len(secili) > 15 else "")):
            return
        mesajlar, hatalar = [], []
        for f in secili:
            try:
                mesajlar.append(sgk_karsilastirma.duzelt(self.db, f))
            except Exception as ex:  # noqa: BLE001 - kullanıcıya gösterilir
                hatalar.append(f"{f.ogrenci}: {ex}")
        self.karsilastir()
        if not sormadan:
            ortak.bilgi(self, "\n".join(mesajlar + hatalar))

    def excel(self):
        if self.sonuc is None:
            return
        yol = ortak.kaydet_yolu(self, f"SGK Karşılaştırma {self.sonuc.ay:02d}-{self.sonuc.yil}.xlsx")
        if yol:
            ortak.kaydedildi(self, sgk_karsilastirma.excel_yaz(self.sonuc, yol))


class SgkRiskleri(QWidget):
    BASLIKLAR = ["Seviye", "Konu", "Kişi", "Açıklama", "Öneri", "Son tarih", "Olası ceza (TL)",
                 "Hemen düzeltilirse (TL)", "Düzeltme", "Dayanak"]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.riskler: list[sgk_risk.Risk] = []
        lay = QVBoxLayout(self)
        lay.addWidget(_aciklama(
            "Kayıtlar her açılışta SGK idari para cezası doğurabilecek durumlar için taranır: geciken veya yaklaşan "
            "işe giriş / işten ayrılış bildirgeleri, APHB son günü, 20 yaşını dolduran öğrencilerin belge türü "
            "(7 yerine 42), T.C. hataları, tatilde girilmiş ayrılışlar. Ceza tutarları Ayarlar'daki asgari ücret ve "
            "'SGK İdari Para Cezaları' oranlarıyla hesaplanır; kesin tutar SGK tebligatındadır."))
        ust = ortak.AkisDuzeni()
        _, self.uygula_btn, _ = _dugmeler(ust, [("Yenile", self.yenile), ("Seçili Önerileri Uygula", self.uygula),
                                                ("Excel'e Aktar", self.excel)])
        ust.addStretch()
        lay.addLayout(ust)
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        lay.addWidget(self.view, 1)
        self.ozet = QLabel()
        self.ozet.setWordWrap(True)
        self.ozet.setStyleSheet("font-weight:bold")
        lay.addWidget(self.ozet)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self):
        self.riskler = sgk_risk.analiz(self.db)
        rows = [[r.seviye, r.konu, r.kisi, r.aciklama, r.oneri,
                 r.son_tarih.strftime("%d.%m.%Y") if r.son_tarih else "",
                 para(r.tahmini_ceza) if r.tahmini_ceza else "", para(r.indirimli_ceza) if r.indirimli_ceza else "",
                 r.eylem_adi, r.dayanak] for r in self.riskler]
        self.model.ayarla(rows, list(range(len(rows))),
                          {i: RENKLER[r.seviye] for i, r in enumerate(self.riskler) if r.seviye in RENKLER})
        ortak.sutunlari_sigdir(self.view)
        self.ozet.setText(sgk_risk.ozet(self.riskler))
        self.uygula_btn.setEnabled(any(r.eylem for r in self.riskler))

    def secili_riskler(self) -> list[sgk_risk.Risk]:
        return [self.riskler[self.model.kimlik(r)] for r in ortak.secili_satirlar(self.view, self.proxy)]

    def uygula(self, sormadan: bool = False) -> None:
        secili = [r for r in self.secili_riskler() if r.eylem]
        if not secili:
            ortak.bilgi(self, "Düzeltme sütunu dolu olan satırları seçiniz.")
            return
        if not sormadan and not ortak.onay(self, "Seçilen kayıtlar için şu işlemler yapılacak:\n\n"
                                           + "\n".join(f"• {r.kisi}: {r.eylem_adi}" for r in secili[:15])
                                           + ("\n..." if len(secili) > 15 else "")):
            return
        mesajlar = []
        for r in secili:
            try:
                mesajlar.append(sgk_risk.uygula(self.db, r))
            except Exception as ex:  # noqa: BLE001 - kullanıcıya gösterilir
                mesajlar.append(f"{r.kisi}: {ex}")
        self.yenile()
        if not sormadan:
            ortak.bilgi(self, "\n".join(mesajlar))

    def excel(self):
        yol = ortak.kaydet_yolu(self, "SGK Hata ve Ceza Riskleri.xlsx")
        if yol:
            ortak.kaydedildi(self, sgk_risk.excel_yaz(self.riskler, yol))
