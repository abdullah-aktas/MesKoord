"""Ders programı iş adımları, mevzuat denetimi, norm kadro, maaş/ücret işaretleri ve e-Okul eşgüdümü."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFileDialog, QHeaderView, QLabel,
                               QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget)

from ..mevzuat import GUNLER
from ..services import ekders, okuyucu, program
from ..services import program_mevzuat as pm
from . import ortak

DURUM = {True: ("Tamam", "#e3f4e1"), False: ("Eksik", "#fde2e1"), None: ("Bilgi", "#eef1f5")}
SEVIYE_RENK = {"Kritik": "#fde2e1", "Uyarı": "#fff2cc", "Bilgi": "#eef1f5"}
ISARET = {ekders.MAAS: "M", ekders.UCRET: "Ü", ekders.ODENMEZ: "Ödenmez"}


def _aciklama(metin: str) -> QLabel:
    lbl = QLabel(metin)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color:#555")
    return lbl


def _hucre(metin, renk: str | None = None, veri=None) -> QTableWidgetItem:
    it = QTableWidgetItem(str(metin))
    if renk:
        it.setBackground(QBrush(QColor(renk)))
    if veri is not None:
        it.setData(Qt.UserRole, veri)
    return it


def _tablo(basliklar: list[str], esnek: int) -> QTableWidget:
    t = QTableWidget(0, len(basliklar))
    t.setHorizontalHeaderLabels(basliklar)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setWordWrap(True)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
    t.horizontalHeader().setSectionResizeMode(esnek, QHeaderView.Stretch)
    t.verticalHeader().setVisible(False)
    return t


class ProgramSurecSayfasi(QWidget):
    ADIM_BASLIK = ["No", "İş Adımı", "Durum", "Açıklama"]
    BULGU_BASLIK = ["Seviye", "Konu", "Açıklama", "Dayanak"]
    NORM_BASLIK = ["Branş / Görev", "Norm Türü", "Ders Yükü", "Tahmini Norm", "Mevcut", "Fark", "Açıklama"]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lay.addWidget(_aciklama(
            "Ders programı bu sırayla hazırlanır. Her adımın durumu kendiliğinden denetlenir; satıra çift tıklayınca "
            "ilgili ekran açılır. Dağıtım parametrelere kesin uyar; yerleşmeyen her ders için neden ve öneri "
            "verilir. Mevzuat denetimi Ders ve Ek Ders Saatlerine İlişkin Karar (md.5, 6, 15), Ortaöğretim "
            "Kurumları Yönetmeliği (md.12) ve Norm Kadro Yönetmeliği'ne (md.18-22) göre yapılır."))
        ust = ortak.AkisDuzeni()
        for metin, fn in [("Yenile", self.yenile), ("Dağıtımı Başlat", self.dagit),
                          ("Neden Yerleşmedi?", self.nedenler), ("e-Okul Çizelgesi (Excel)", self.eokul_cizelgesi),
                          ("e-Okul ile Karşılaştır...", self.eokul_karsilastir),
                          ("Tebliğ ve Onay Belgesi (PDF)", self.teblig), ("Denetim Raporu (Excel)", self.rapor)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        self.ozet = QLabel()
        self.ozet.setWordWrap(True)
        lay.addWidget(self.ozet)

        sp = QSplitter(Qt.Vertical)
        self.adimlar = _tablo(self.ADIM_BASLIK, 3)
        self.adimlar.cellDoubleClicked.connect(lambda i, _: self._git_satir(self.adimlar, i))
        sp.addWidget(self.adimlar)
        alt = QTabWidget()
        self.bulgular = _tablo(self.BULGU_BASLIK, 2)
        self.bulgular.cellDoubleClicked.connect(lambda i, _: self._git_satir(self.bulgular, i))
        alt.addTab(self.bulgular, "Mevzuat Denetimi")
        self.norm = _tablo(self.NORM_BASLIK, 6)
        norm_kap = QWidget()
        nl = QVBoxLayout(norm_kap)
        nl.setContentsMargins(0, 0, 0, 0)
        nl.addWidget(_aciklama("Okulunuzdaki ders dağılımından hesaplanan tahmini norm. Alan ders yükü = haftalık "
                               "saat x grup sayısı (atölye/lab. derslerinde mevcuda göre, MEM şubeleri bölünmez); "
                               "yöneticilerin okuttuğu dersler ve rehberlik dersleri düşülür, işletmelerde meslek "
                               "eğitimi atölye normuna eklenir. Resmî norm MEBBİS'te belirlenir."))
        nl.addWidget(self.norm, 1)
        alt.addTab(norm_kap, "Norm Kadro (tahmini)")
        alt.addTab(self._isaret_sekmesi(), "Maaş / Ücret İşaretleri")
        sp.addWidget(alt)
        sp.setSizes([330, 300])
        lay.addWidget(sp, 1)
        self._yuklendi = False

    # --- maaş / ücret ---
    def _isaret_sekmesi(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        ust = ortak.AkisDuzeni()
        self.isaret_ogretmen = QComboBox()
        self.isaret_ogretmen.setMinimumWidth(240)
        self.isaret_ogretmen.currentIndexChanged.connect(lambda _: self._isaret_ciz())
        ust.addWidget(ortak.etiketli("Öğretmen:", self.isaret_ogretmen))
        ust.addStretch()
        lay.addLayout(ust)
        lay.addWidget(_aciklama("Programdaki her saatin aylık karşılığından (M) mı, ek ders ücretinden (Ü) mi "
                                "yapıldığı. Azami ek dersi aşan saatler ödenmez. Karşılık önce haftanın ilk gün ve "
                                "saatlerinden doldurulur (Ayarlar > Ek Ders)."))
        self.isaret = QTableWidget()
        self.isaret.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.isaret.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.isaret, 1)
        self.isaret_ozet = QLabel()
        self.isaret_ozet.setWordWrap(True)
        lay.addWidget(self.isaret_ozet)
        return w

    def _ogretmenleri_doldur(self):
        secili = self.isaret_ogretmen.currentData()
        self.isaret_ogretmen.blockSignals(True)
        self.isaret_ogretmen.clear()
        for r in self.db.q("SELECT id, ad || ' ' || soyad AS ad FROM ogretmenler WHERE aktif = 1 ORDER BY ad, soyad"):
            self.isaret_ogretmen.addItem(r["ad"], r["id"])
        self.isaret_ogretmen.setCurrentIndex(max(0, self.isaret_ogretmen.findData(secili)))
        self.isaret_ogretmen.blockSignals(False)
        self._isaret_ciz()

    def _isaret_ciz(self):
        S = self.db.ayar("gunluk_ders_saati")
        self.isaret.clear()
        self.isaret.setRowCount(S)
        self.isaret.setColumnCount(5)
        self.isaret.setHorizontalHeaderLabels(GUNLER)
        self.isaret.setVerticalHeaderLabels([f"{h}. saat" for h in range(1, S + 1)])
        tid = self.isaret_ogretmen.currentData()
        if not tid:
            self.isaret_ozet.setText("")
            return
        h = ekders.haftalik_isaretler(self.db, tid)
        tablo = program.program_tablosu(self.db, "ogretmen", tid)
        renk = {ekders.MAAS: "#e3ecfa", ekders.UCRET: "#e3f4e1", ekders.ODENMEZ: "#fde2e1"}
        for (g, s), isaret in h.hucreler.items():
            x = tablo.get((g, s))
            metin = (f"{x['sinif']} {x['kisa_ad'] or x['ders']}\n" if x else "") + ISARET.get(isaret, isaret)
            it = _hucre(metin, renk.get(isaret))
            it.setTextAlignment(Qt.AlignCenter)
            if 1 <= s <= S and 1 <= g <= 5:
                self.isaret.setItem(s - 1, g - 1, it)
        kalem = "; ".join(f"{k}: {n:g} saat (M {m:g}, Ü {u:g})" for k, n, m, u in h.kalemler)
        self.isaret_ozet.setText(f"Aylık karşılığı {h.aylik_karsilik}, azami ek ders {h.azami}. Toplam {h.toplam:g} "
                                 f"saat: maaş {h.maas:g}, ücret {h.ucret:g}, ödenmez {h.odenmeyen:g}. {kalem}"
                                 + ("".join(f"\n⚠ {u}" for u in h.uyarilar)))

    # --- yükleme ---
    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            adimlar = pm.is_adimlari(self.db)
            bulgular = pm.mevzuat_denetimi(self.db)
            normlar = pm.norm_kadro(self.db)
        finally:
            QApplication.restoreOverrideCursor()
        self.adimlar.setRowCount(len(adimlar))
        for i, a in enumerate(adimlar):
            metin, renk = DURUM[a.durum]
            for j, v in enumerate([a.no, a.baslik, metin, a.detay]):
                self.adimlar.setItem(i, j, _hucre(v, renk if j == 2 else None, a.git))
        self.adimlar.resizeRowsToContents()
        self.bulgular.setRowCount(len(bulgular))
        for i, b in enumerate(bulgular):
            for j, v in enumerate([b.seviye, b.konu, b.mesaj, b.dayanak]):
                self.bulgular.setItem(i, j, _hucre(v, SEVIYE_RENK[b.seviye] if j == 0 else None, b.git))
        self.bulgular.resizeRowsToContents()
        self.norm.setRowCount(len(normlar))
        for i, n in enumerate(normlar):
            renk = "#fde2e1" if n.fark < 0 else ("#fff2cc" if n.fark > 0 else None)
            for j, v in enumerate([n.brans, n.tur, f"{n.ders_yuku:g}", n.norm, n.mevcut, f"{n.fark:+d}", n.aciklama]):
                self.norm.setItem(i, j, _hucre(v, renk if j == 5 else None))
        tamam = sum(1 for a in adimlar if a.durum is True)
        zorunlu = sum(1 for a in adimlar if a.durum is not None)
        kritik = sum(1 for b in bulgular if b.seviye == "Kritik")
        self.ozet.setText(f"<b>{tamam}/{zorunlu} adım tamam.</b> Mevzuat denetimi: {kritik} kritik, "
                          f"{sum(1 for b in bulgular if b.seviye == 'Uyarı')} uyarı, "
                          f"{sum(1 for b in bulgular if b.seviye == 'Bilgi')} bilgi.")
        self._ogretmenleri_doldur()
        self._veri = (adimlar, bulgular, normlar)

    # --- gezinme ---
    def _git_satir(self, tablo: QTableWidget, satir: int):
        it = tablo.item(satir, 0)
        hedef = it.data(Qt.UserRole) if it else ""
        if hedef:
            self.git(hedef)

    def _program_sayfasi(self):
        w = self.parentWidget()
        while w is not None and not hasattr(w, "program_tablosu"):
            w = w.parentWidget()
        return w

    def git(self, hedef: str) -> QWidget | None:
        sayfa, _, sekme = hedef.partition("/")
        pencere = self.window()
        w = None
        if sayfa == pm.PROGRAM_SAYFASI:
            w = self._program_sayfasi()
        elif hasattr(pencere, "git"):
            w = pencere.git(sayfa)
        if sekme and isinstance(w, QTabWidget):
            for i in range(w.count()):
                if w.tabText(i) == sekme:
                    w.setCurrentIndex(i)
                    return w.widget(i)
        return w

    # --- eylemler ---
    def dagit(self):
        ps = self._program_sayfasi()
        if ps is None:
            return
        ps.sekme(pm.SEKME_TABLO)
        ps.program_tablosu().otomatik()

    def nedenler(self):
        ps = self._program_sayfasi()
        if ps is not None:
            ps.sekme(pm.SEKME_TABLO)
            ps.program_tablosu().nedenler()

    def eokul_cizelgesi(self):
        sorunlar = pm.eokul_tutarliligi(self.db)
        if sorunlar and not ortak.onay(self, f"e-Okul girişinden önce giderilmesi önerilen {len(sorunlar)} durum var "
                                             "(çizelgenin 'Tutarlılık' sayfasında listelenir):\n"
                                       + "\n".join(f"- {s}" for s in sorunlar[:12])
                                       + ("\n…" if len(sorunlar) > 12 else "") + "\n\nÇizelge yine de hazırlansın mı?",
                                       "e-Okul Çizelgesi"):
            return
        yol = ortak.kaydet_yolu(self, "e-Okul Ders Görevlendirme ve Program.xlsx")
        if yol:
            ortak.kaydedildi(self, pm.eokul_cizelgesi(self.db, yol))

    def eokul_karsilastir(self, yollar: list | None = None) -> pm.EokulKarsilastirma | None:
        if not yollar:
            yollar, _ = QFileDialog.getOpenFileNames(self, "e-Okul sınıf/öğretmen programı çizelgesini seçin",
                                                     str(Path.home()), okuyucu.DOSYA_FILTRESI)
        if not yollar:
            return None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            k = pm.eokul_karsilastir(self.db, list(yollar))
        finally:
            QApplication.restoreOverrideCursor()
        metin = k.ozet
        if k.farklar:
            metin += "\n\n" + "\n".join(f"- {f}" for f in k.farklar[:40]) + ("\n…" if len(k.farklar) > 40 else "")
        if k.hatalar:
            metin += "\n\nOkunamayan: " + "; ".join(k.hatalar[:5])
        ortak.bilgi(self, metin, "e-Okul ile Karşılaştırma")
        return k

    def teblig(self):
        satirlar = pm.teblig_satirlari(self.db)
        if not satirlar:
            ortak.hata(self, "Programda dersi olan öğretmen yok; önce dağıtımı yapın.")
            return
        yol = ortak.kaydet_yolu(self, "Ders Programı Tebliğ ve Onay Belgesi.pdf", "PDF (*.pdf)")
        if not yol:
            return
        k = self.db.kurum()
        alt = (f"{pm.teblig_metni(self.db)}<br><br>Öğretmenler kurulu tarihi: ....../....../...........<br><br>"
               f"<div style='text-align:right'>ONAY<br>....../....../...........<br><br>{k['mudur'] or ''}<br>"
               "Okul Müdürü</div>")
        html = ortak.html_tablo(f"{k['ad']}<br>{k['egitim_yili']} Haftalık Ders Programı Tebliğ ve Onay Belgesi",
                                pm.TEBLIG_BASLIKLARI, satirlar, alt)
        ortak.kaydedildi(self, ortak.html_pdf(html, Path(yol), yatay=False))

    def rapor(self):
        if not getattr(self, "_veri", None):
            self.yenile()
        yol = ortak.kaydet_yolu(self, "Ders Programı Denetim Raporu.xlsx")
        if not yol:
            return
        from ..services import excel_io
        adimlar, bulgular, normlar = self._veri
        x = excel_io.ExcelYazici()
        x.sayfa("İş Adımları", self.ADIM_BASLIK, [[a.no, a.baslik, DURUM[a.durum][0], a.detay] for a in adimlar],
                "Ders Programı İş Adımları")
        x.sayfa("Mevzuat", self.BULGU_BASLIK, [[b.seviye, b.konu, b.mesaj, b.dayanak] for b in bulgular],
                "Mevzuat Denetimi")
        x.sayfa("Norm", self.NORM_BASLIK, [[n.brans, n.tur, n.ders_yuku, n.norm, n.mevcut, n.fark, n.aciklama]
                                           for n in normlar], "Tahmini Norm Kadro")
        ortak.kaydedildi(self, x.kaydet(yol))
