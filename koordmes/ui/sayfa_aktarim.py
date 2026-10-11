"""Veri aktarımı sihirbazı: Excel, Word, PDF, CSV, HTML, ODS ve JSON dosyalarından veri alma."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QHeaderView,
                               QLabel, QListWidget, QListWidgetItem, QPushButton, QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..mevzuat import OGRENCI_STATULERI
from ..services import aktarim, okuyucu, surecler
from ..services.aktarim import TANIMLAR, IceAktarmaSonucu, Secenekler
from ..services.okuyucu import Tablo
from . import eylem, ortak

DURUM_ADI = {"eklendi": "Eklendi", "guncellendi": "Güncellendi", "atlandi": "Atlandı", "hata": "Hata"}
DURUM_RENGI = {"eklendi": ortak.RENK_TAMAM, "guncellendi": ortak.RENK_BILGI, "atlandi": ortak.RENK_UYARI,
               "hata": ortak.RENK_KRITIK}


def sutun_harfi(j: int) -> str:
    s = ""
    j += 1
    while j:
        j, r = divmod(j - 1, 26)
        s = chr(65 + r) + s
    return s


def surukle_dosyalar(e) -> list[str]:
    md = e.mimeData()
    if not md.hasUrls():
        return []
    return [u.toLocalFile() for u in md.urls() if u.isLocalFile() and Path(u.toLocalFile()).is_file()]


@dataclass
class _Oge:
    tablo: Tablo
    tahminler: list = field(default_factory=list)
    anahtar: str | None = None
    bas: int = 0
    eslesme: dict[str, int] = field(default_factory=dict)
    durum: str = ""

    @property
    def hazir(self) -> bool:
        return bool(self.anahtar) and aktarim.hazir_mi(self.tablo, self.anahtar, self.eslesme)


class AktarimSayfasi(QWidget):
    def __init__(self, db, pencere=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.pencere = pencere
        self.ogeler: list[_Oge] = []
        self._yukleniyor = False
        self._oneriler: list[tuple[str, str, dict]] = []
        self.setAcceptDrops(True)

        lay = QVBoxLayout(self)
        lbl = QLabel("e-Okul, MEBBİS, e-Mesem, e-Bildirge, banka dekont listeleri veya kendi tablolarınızı içeren "
                     "<b>Excel (xlsx/xls), Word (docx), PDF, CSV/TXT, HTML, ODS ve JSON</b> dosyalarını ekleyin ya da "
                     "bu ekrana sürükleyip bırakın. Her dosyadaki tablolar bulunur, veri türü ve sütunlar otomatik "
                     "tanınır. Eşlemeyi kontrol edip <b>Önizle</b> ile deneyin, ardından <b>Aktar</b>. Aktarımdan önce "
                     "otomatik yedek alınır; eksik sınıf, öğrenci, işletme gibi ilişkili kayıtlar da oluşturulur.")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)

        ust = QHBoxLayout()
        for metin, fn in [("Dosya Ekle...", self.dosya_sec), ("Listeyi Temizle", self.temizle)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch(1)
        for metin, fn in [("Seçili Tür İçin Boş Şablon", lambda: self.sablon(False)),
                          ("Tüm Türler İçin Şablon", lambda: self.sablon(True))]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        lay.addLayout(ust)

        ana = QSplitter(Qt.Vertical)
        ust_bolme = QSplitter(Qt.Horizontal)

        sol = QWidget()
        sl = QVBoxLayout(sol)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(QLabel("<b>Bulunan tablolar</b> (işaretliler toplu aktarılır)"))
        self.liste = QListWidget()
        self.liste.currentRowChanged.connect(self._goster)
        sl.addWidget(self.liste, 1)
        ust_bolme.addWidget(sol)

        sag = QWidget()
        rl = QVBoxLayout(sag)
        rl.setContentsMargins(0, 0, 0, 0)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Veri türü:"))
        self.tur = QComboBox()
        self.tur.addItem("— Aktarma —", None)
        for k in sorted(TANIMLAR, key=lambda k: TANIMLAR[k].sira):
            self.tur.addItem(TANIMLAR[k].etiket, k)
        self.tur.currentIndexChanged.connect(self._tur_degisti)
        r1.addWidget(self.tur, 1)
        r1.addWidget(QLabel("Başlık satırı:"))
        self.bas = QSpinBox()
        self.bas.setRange(1, 1)
        self.bas.valueChanged.connect(self._bas_degisti)
        r1.addWidget(self.bas)
        rl.addLayout(r1)
        self.aciklama = QLabel()
        self.aciklama.setWordWrap(True)
        rl.addWidget(self.aciklama)

        r2 = QHBoxLayout()
        self.guncelle = QCheckBox("Mevcut kayıtları güncelle")
        self.guncelle.setChecked(True)
        self.olustur = QCheckBox("Eksik öğrenci/işletme/sınıf kayıtlarını oluştur")
        self.olustur.setChecked(True)
        r2.addWidget(self.guncelle)
        r2.addWidget(self.olustur)
        r2.addStretch(1)
        rl.addLayout(r2)
        r3 = QHBoxLayout()
        self.tarih_lbl = QLabel()
        self.tarih = QDateEdit(QDate.currentDate())
        self.tarih.setCalendarPopup(True)
        self.tarih.setDisplayFormat("dd.MM.yyyy")
        self.yer_lbl = QLabel("Devamsızlık yeri (dosyada yoksa):")
        self.yer = QComboBox()
        self.yer.addItems(["Okul", "İşletme", "Otomatik"])
        self.yer.setItemData(2, "Tarih, öğrencinin sınıfının işletme günlerinden birine denk geliyorsa İşletme, "
                                "değilse Okul devamsızlığı sayılır.", Qt.ToolTipRole)
        self.aralik = QCheckBox("Yalnızca şu tarihler arası:")
        self.aralik.setToolTip("e-Okul ayrıntılı devamsızlık raporu (OOK08001R060) tüm yılı içerir; yalnızca seçilen "
                               "aralıktaki devamsızlıklar işlenir.")
        self.aralik_bas = QDateEdit(QDate(QDate.currentDate().year(), QDate.currentDate().month(), 1))
        self.aralik_bit = QDateEdit(QDate.currentDate())
        for w in (self.aralik_bas, self.aralik_bit):
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd.MM.yyyy")
        self.donem_lbl = QLabel("Dönem (dosyada yoksa):")
        self.donem = ortak.AySecici()
        self.statu_lbl = QLabel("Statü (dosyada yoksa):")
        self.statu = QComboBox()
        self.statu.addItem("— Değiştirme / otomatik —", None)
        for s in OGRENCI_STATULERI:
            self.statu.addItem(s, s)
        self.statu.setToolTip("MAOL 'Yüz Yüze Eğitim Öğrenci Listesi' dosyaları kendiliğinden 'Açık Lise' "
                              "statüsüyle aktarılır.")
        for w in (self.tarih_lbl, self.tarih, self.yer_lbl, self.yer, self.aralik, self.aralik_bas, self.aralik_bit,
                  self.donem_lbl, self.donem, self.statu_lbl, self.statu):
            r3.addWidget(w)
        r3.addStretch(1)
        rl.addLayout(r3)

        ic = QSplitter(Qt.Vertical)
        self.esleme = QTableWidget(0, 3)
        self.esleme.setHorizontalHeaderLabels(["Alan", "Dosyadaki sütun", "Örnek değer"])
        self.esleme.verticalHeader().setVisible(False)
        self.esleme.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.esleme.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.esleme.horizontalHeader().setStretchLastSection(True)
        self.esleme.setColumnWidth(1, 260)
        ic.addWidget(self.esleme)
        self.onizleme_model = ortak.TabloModeli([])
        self.onizleme, self._onizleme_proxy = ortak.tablo_gorunumu(self.onizleme_model, False)
        self.onizleme.setSortingEnabled(False)
        ic.addWidget(self.onizleme)
        ic.setSizes([300, 220])
        rl.addWidget(ic, 1)
        ust_bolme.addWidget(sag)
        ust_bolme.setStretchFactor(0, 1)
        ust_bolme.setStretchFactor(1, 3)
        ust_bolme.setSizes([330, 900])
        ana.addWidget(ust_bolme)

        alt = QWidget()
        al = QVBoxLayout(alt)
        al.setContentsMargins(0, 0, 0, 0)
        dug = QHBoxLayout()
        for metin, fn in [("Önizle (deneme, kaydetmez)", lambda: self.aktar_secili(True)),
                          ("Seçili Tabloyu Aktar", lambda: self.aktar_secili(False)),
                          ("İşaretlileri Önizle", lambda: self.aktar_isaretli(True)),
                          ("İşaretlilerin Tümünü Aktar", lambda: self.aktar_isaretli(False))]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            dug.addWidget(b)
        dug.addStretch(1)
        al.addLayout(dug)
        self.ozet = QLabel("Henüz aktarım yapılmadı.")
        self.ozet.setWordWrap(True)
        self.ozet.setTextInteractionFlags(Qt.TextSelectableByMouse)
        al.addWidget(self.ozet)
        self.oneri_kutu = QHBoxLayout()
        al.addLayout(self.oneri_kutu)
        self.sonuc_model = ortak.TabloModeli(["Kaynak", "Kayıt", "Durum", "Kayıt özeti", "Açıklama"])
        self.sonuc, self.sonuc_proxy = ortak.tablo_gorunumu(self.sonuc_model)
        al.addWidget(self.sonuc, 1)
        ana.addWidget(alt)
        ana.setStretchFactor(0, 3)
        ana.setStretchFactor(1, 2)
        lay.addWidget(ana, 1)
        self._secenek_gorunurlugu(None)

    # ------------------------------------------------------------------ dosyalar

    def dragEnterEvent(self, e):
        if surukle_dosyalar(e):
            e.acceptProposedAction()

    def dropEvent(self, e):
        yollar = surukle_dosyalar(e)
        if yollar:
            self.dosyalari_ekle(yollar)
            e.acceptProposedAction()

    def dosya_sec(self):
        yollar, _ = QFileDialog.getOpenFileNames(self, "Aktarılacak dosyaları seçin", str(Path.home()),
                                                 okuyucu.DOSYA_FILTRESI)
        if yollar:
            self.dosyalari_ekle(yollar)

    def dosyalari_ekle(self, yollar: list) -> int:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            bulunan, hatalar = aktarim.dosyalari_incele(yollar)
        finally:
            QApplication.restoreOverrideCursor()
        ilk = len(self.ogeler)
        for b in bulunan:
            o = _Oge(b.tablo, b.tahminler)
            if b.en_iyi:
                o.anahtar, o.bas, o.eslesme = b.en_iyi.anahtar, b.en_iyi.bas, dict(b.en_iyi.eslesme)
            self.ogeler.append(o)
            it = QListWidgetItem()
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if o.hazir else Qt.Unchecked)
            self.liste.addItem(it)
            self._oge_metni(len(self.ogeler) - 1)
        if hatalar:
            ortak.hata(self, "Okunamayan dosyalar:\n" + "\n".join(hatalar))
        if bulunan:
            self.liste.setCurrentRow(ilk)
        elif not hatalar:
            ortak.bilgi(self, "Seçilen dosyalarda tablo bulunamadı.")
        return len(bulunan)

    def temizle(self):
        self.ogeler.clear()
        self.liste.clear()
        self._goster(-1)

    def sablon(self, hepsi: bool):
        anahtar = None if hepsi else self.tur.currentData()
        if not hepsi and not anahtar:
            ortak.bilgi(self, "Önce bir veri türü seçin.")
            return
        ad = "Aktarım Şablonları (Tüm Türler).xlsx" if hepsi else f"Şablon - {TANIMLAR[anahtar].etiket}.xlsx"
        yol = ortak.kaydet_yolu(self, ad.replace("/", "-"))
        if yol:
            aktarim.sablon_olustur(anahtar, yol)
            ortak.kaydedildi(self, yol)

    # ------------------------------------------------------------------ seçili tablo

    def _secili(self) -> _Oge | None:
        i = self.liste.currentRow()
        return self.ogeler[i] if 0 <= i < len(self.ogeler) else None

    def _oge_metni(self, i: int) -> None:
        o, it = self.ogeler[i], self.liste.item(i)
        veri = max(0, len(o.tablo.satirlar) - o.bas - 1)
        if o.anahtar:
            tur = TANIMLAR[o.anahtar].etiket
            alt = f"→ {tur} ({veri} kayıt)" if o.hazir else f"→ {tur}: gerekli sütunlar eksik"
        else:
            alt = "→ Tanınmadı, veri türünü seçin"
        baglam = aktarim.baglam_ozeti(o.tablo)
        if baglam:
            alt += f"\nBelgeden: {baglam}"
        if o.durum:
            alt += f"\n✔ {o.durum}"
        it.setText(f"{o.tablo.etiket}\n{alt}")
        it.setForeground(QBrush(QColor("#1b5e20" if o.hazir else "#8a6d3b" if o.anahtar else "#777")))

    def _goster(self, i: int) -> None:
        o = self.ogeler[i] if 0 <= i < len(self.ogeler) else None
        self._yukleniyor = True
        try:
            self.tur.setCurrentIndex(max(0, self.tur.findData(o.anahtar)) if o else 0)
            self.bas.setRange(1, max(1, len(o.tablo.satirlar)) if o else 1)
            self.bas.setValue(o.bas + 1 if o else 1)
        finally:
            self._yukleniyor = False
        self._esleme_doldur()
        self._onizleme_doldur()

    def _tur_degisti(self, _=None):
        if self._yukleniyor:
            return
        o = self._secili()
        if not o:
            self._secenek_gorunurlugu(self.tur.currentData())
            return
        o.anahtar = self.tur.currentData()
        if o.anahtar:
            bas, es = aktarim.baslik_bul(o.tablo.satirlar, TANIMLAR[o.anahtar])
            o.bas, o.eslesme = (bas, es) if bas >= 0 else (0, {})
        else:
            o.eslesme = {}
        self._yukleniyor = True
        self.bas.setValue(o.bas + 1)
        self._yukleniyor = False
        self._degisti()

    def _bas_degisti(self, v: int):
        if self._yukleniyor:
            return
        o = self._secili()
        if not o:
            return
        o.bas = v - 1
        if o.anahtar and o.bas < len(o.tablo.satirlar):
            o.eslesme = aktarim.satir_eslestir(o.tablo.satirlar, o.bas, TANIMLAR[o.anahtar])
        self._degisti()

    def _degisti(self):
        i = self.liste.currentRow()
        if 0 <= i < len(self.ogeler):
            o = self.ogeler[i]
            self.liste.item(i).setCheckState(Qt.Checked if o.hazir else Qt.Unchecked)
            self._oge_metni(i)
        self._esleme_doldur()
        self._onizleme_doldur()

    def _secenek_gorunurlugu(self, anahtar: str | None):
        t = TANIMLAR.get(anahtar) if anahtar else None
        tarih = bool(t and t.tarih_etiketi)
        self.tarih_lbl.setText((t.tarih_etiketi if t else "") + ":")
        for w in (self.tarih_lbl, self.tarih):
            w.setVisible(tarih)
        for w in (self.yer_lbl, self.yer, self.aralik, self.aralik_bas, self.aralik_bit):
            w.setVisible(anahtar == "devamsizlik")
        for w in (self.donem_lbl, self.donem):
            w.setVisible(anahtar == "dekontlar")
        for w in (self.statu_lbl, self.statu):
            w.setVisible(anahtar == "ogrenciler")

    def _ornek(self, o: _Oge, j: int) -> str:
        for row in o.tablo.satirlar[o.bas + 1:o.bas + 30]:
            if j < len(row) and aktarim.metin(row[j]):
                return aktarim.metin(row[j])[:80]
        return ""

    def _esleme_doldur(self):
        o = self._secili()
        anahtar = o.anahtar if o else None
        self._secenek_gorunurlugu(anahtar)
        self.esleme.setRowCount(0)
        if not o or not anahtar:
            self.aciklama.setText("Listeden bir tablo seçin ve veri türünü belirleyin." if not o else
                                  "Bu tablo aktarılmayacak. Aktarmak için veri türü seçin.")
            return
        t = TANIMLAR[anahtar]
        zorunlu = {k for g in t.zorunlu for k in g}
        basliklar = o.tablo.satirlar[o.bas] if o.bas < len(o.tablo.satirlar) else []
        secenekler = ["— (yok)"] + [f"{sutun_harfi(j)}: {aktarim.metin(basliklar[j]) if j < len(basliklar) else ''}"[:60]
                                    for j in range(o.tablo.sutun_sayisi)]
        durum = ("<span style='color:#1b5e20'>Gerekli sütunlar tamam.</span>" if o.hazir else
                 f"<span style='color:#b00020'>Gerekli sütunlar eksik: {aktarim.zorunlu_metni(t)}</span>")
        ek = ""
        if o.hazir:
            parcalar = [f"<b>{TANIMLAR[g.anahtar].etiket}</b>: "
                        + ", ".join(TANIMLAR[g.anahtar].baslik(a) for a in g.bilgi)
                        for g in aktarim.ek_gecisler(o.tablo.satirlar, o.bas, anahtar, o.eslesme)]
            if parcalar:
                ek = "<br>Tablodaki diğer bilgiler de işlenecek — " + "; ".join(parcalar)
        self.aciklama.setText(f"{t.aciklama} {durum}{ek}".strip())
        kalin = QFont()
        kalin.setBold(True)
        sanal = aktarim.sanal_alanlar(o.tablo, t, o.eslesme)
        baglam_ters = {alan: k for k, alan in aktarim.baglam_alanlari(t).items()}
        baglam_deger = {**{k: v for b in aktarim.satir_baglamlari(o.tablo).values() for k, v in b.items()},
                        **aktarim.on_baglam(o.tablo, o.bas)}
        self.esleme.setRowCount(len(t.alanlar))
        for r, (a, g, _) in enumerate(t.alanlar):
            it = QTableWidgetItem(g + (" *" if a in zorunlu else ""))
            it.setFlags(Qt.ItemIsEnabled)
            if a in zorunlu:
                it.setFont(kalin)
            self.esleme.setItem(r, 0, it)
            cb = QComboBox()
            cb.addItems(secenekler)
            j = o.eslesme.get(a)
            cb.setCurrentIndex(j + 1 if j is not None and j + 1 < len(secenekler) else 0)
            cb.currentIndexChanged.connect(lambda idx, a=a, r=r: self._esleme_degisti(a, r, idx))
            self.esleme.setCellWidget(r, 1, cb)
            if j is None and a in sanal:
                metin = f"(belge başlığından: {baglam_deger.get(baglam_ters[a], '')}"
                metin += ", ara satırlara göre değişir)" if len(aktarim.satir_baglamlari(o.tablo)) > 1 else ")"
                ornek = QTableWidgetItem(metin)
            else:
                ornek = QTableWidgetItem(self._ornek(o, j) if j is not None else "")
            ornek.setFlags(Qt.ItemIsEnabled)
            self.esleme.setItem(r, 2, ornek)

    def _esleme_degisti(self, alan: str, r: int, idx: int):
        o = self._secili()
        if not o:
            return
        if idx <= 0:
            o.eslesme.pop(alan, None)
        else:
            for k, v in list(o.eslesme.items()):
                if v == idx - 1 and k != alan:
                    o.eslesme.pop(k)
            o.eslesme[alan] = idx - 1
        i = self.liste.currentRow()
        self.liste.item(i).setCheckState(Qt.Checked if o.hazir else Qt.Unchecked)
        self._oge_metni(i)
        self._esleme_doldur()
        self._onizleme_doldur()

    def _onizleme_doldur(self):
        o = self._secili()
        if not o:
            self.onizleme_model.basliklar = []
            self.onizleme_model.ayarla([])
            return
        n = o.tablo.sutun_sayisi
        kullanilan = {j: TANIMLAR[o.anahtar].baslik(a) for a, j in o.eslesme.items()} if o.anahtar else {}
        if o.hazir:
            for g in aktarim.ek_gecisler(o.tablo.satirlar, o.bas, o.anahtar, o.eslesme):
                for a in g.bilgi:
                    kullanilan.setdefault(g.eslesme[a], f"{TANIMLAR[g.anahtar].baslik(a)} (ek)")
        self.onizleme_model.basliklar = ["Satır"] + [
            sutun_harfi(j) + (f" → {kullanilan[j]}" if j in kullanilan else "") for j in range(n)]
        rows = [[i + 1] + [aktarim.metin(v) for v in list(r) + [None] * (n - len(r))][:n]
                for i, r in enumerate(o.tablo.satirlar[:300])]
        renk = {o.bas: ortak.RENK_BILGI} if o.anahtar and o.bas < len(rows) else {}
        self.onizleme_model.ayarla(rows, renkler=renk)
        ortak.sutunlari_sigdir(self.onizleme, 220)

    # ------------------------------------------------------------------ aktarım

    def _secenekler(self) -> Secenekler:
        q = self.tarih.date()
        gun = lambda w: date(w.date().year(), w.date().month(), w.date().day())
        aralik = self.aralik.isVisible() and self.aralik.isChecked()
        return Secenekler(guncelle=self.guncelle.isChecked(), olustur=self.olustur.isChecked(),
                          tarih=date(q.year(), q.month(), q.day()) if self.tarih.isVisible() else None,
                          devamsizlik_yeri=self.yer.currentText(),
                          donem=self.donem.deger() if self.donem.isVisible() else None,
                          ogrenci_statusu=self.statu.currentData() if self.statu.isVisible() else None,
                          bas=gun(self.aralik_bas) if aralik else None, bit=gun(self.aralik_bit) if aralik else None)

    def aktar_secili(self, deneme: bool):
        o = self._secili()
        if not o:
            ortak.bilgi(self, "Önce dosya ekleyip listeden bir tablo seçin.")
            return
        if not o.hazir:
            ortak.bilgi(self, "Veri türünü seçin ve gerekli sütunları eşleyin.")
            return
        self._calistir([o], deneme)

    def aktar_isaretli(self, deneme: bool):
        secilen = [o for i, o in enumerate(self.ogeler) if self.liste.item(i).checkState() == Qt.Checked and o.hazir]
        if not secilen:
            ortak.bilgi(self, "Aktarıma hazır işaretli tablo yok.")
            return
        self._calistir(sorted(secilen, key=lambda o: TANIMLAR[o.anahtar].sira), deneme)

    def _calistir(self, ogeler: list[_Oge], deneme: bool):
        tek_secenek = len(ogeler) == 1 or len({o.anahtar for o in ogeler}) == 1
        sec_ortak = self._secenekler() if tek_secenek else None
        QApplication.setOverrideCursor(Qt.WaitCursor)
        sonuclar: list[tuple[_Oge, IceAktarmaSonucu]] = []
        hatalar: list[str] = []
        try:
            if not deneme:
                self.db.yedekle()
            for o in ogeler:
                sec = sec_ortak or Secenekler(guncelle=self.guncelle.isChecked(), olustur=self.olustur.isChecked(),
                                              devamsizlik_yeri=self.yer.currentText())
                try:
                    s = aktarim.aktar(self.db, o.tablo, o.anahtar, o.bas, o.eslesme, sec, deneme)
                    sonuclar.append((o, s))
                    if not deneme:
                        o.durum = f"{s.eklenen} eklendi, {s.guncellenen} güncellendi"
                except Exception as e:
                    hatalar.append(f"{o.tablo.etiket}: {e}")
        finally:
            QApplication.restoreOverrideCursor()
        for i in range(len(self.ogeler)):
            self._oge_metni(i)
        self._sonuclari_goster(sonuclar, hatalar, deneme)

    def _sonuclari_goster(self, sonuclar, hatalar, deneme: bool):
        rows, renk = [], {}
        for o, s in sonuclar:
            for r in s.satirlar:
                renk[len(rows)] = DURUM_RENGI.get(r.durum)
                rows.append([o.tablo.etiket, r.no, DURUM_ADI.get(r.durum, r.durum), r.ozet, r.mesaj])
        self.sonuc_model.ayarla(rows, renkler={k: v for k, v in renk.items() if v is not None})
        ortak.sutunlari_sigdir(self.sonuc, 300)
        satirlar = [s.ozet_metni() for _, s in sonuclar] + [f"HATA: {h}" for h in hatalar]
        bas = "<b>Önizleme sonucu (veritabanına kaydedilmedi):</b>" if deneme else \
            "<b>Aktarım tamamlandı (öncesinde yedek alındı):</b>"
        self.ozet.setText(bas + "<br>" + "<br>".join(satirlar))

        while self.oneri_kutu.count():
            w = self.oneri_kutu.takeAt(0).widget()
            if w:
                w.deleteLater()
        if deneme:
            return
        oneriler: list[tuple[str, str, dict]] = []
        gorulen = set()
        for _, s in sonuclar:
            if not (s.eklenen or s.guncellenen):
                continue
            yeni_yer = list(s.yeni.get("yerlestirmeler", []))
            for etiket, e in surecler.sonraki_adimlar(s.anahtar, yeni_yer):
                if e in gorulen:
                    continue
                gorulen.add(e)
                oneriler.append((etiket, e, {"ids": yeni_yer} if e == "sozlesmeler_yeni" else {}))
        if oneriler:
            self.oneri_kutu.addWidget(QLabel("<b>Sonraki adımlar:</b>"))
            for etiket, e, kw in oneriler:
                b = QPushButton(etiket)
                b.clicked.connect(lambda _=False, e=e, kw=kw: self._oneri_calistir(e, kw))
                self.oneri_kutu.addWidget(b)
            self.oneri_kutu.addStretch(1)

    def _oneri_calistir(self, anahtar: str, kw: dict):
        eylem.calistir(self, self.db, anahtar, lambda s: eylem.sonuc_goster(self, self.pencere, s), **kw)
