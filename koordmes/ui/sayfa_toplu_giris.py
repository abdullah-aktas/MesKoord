"""Excel benzeri toplu veri giriş ekranı: yazma, Excel/e-Okul'dan yapıştırma, belge yükleme, denetleme ve
kaydetme."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem, QPushButton, QStyledItemDelegate, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ..services import aktarim, okuyucu, surecler, toplu_giris
from ..services.toplu_giris import GIRIS_SOZLUK, GIRIS_TURLERI, GirisTuru
from . import eylem, ortak
from .sayfa_aktarim import surukle_dosyalar

BOS_SATIR = 50
DURUM_ADI = {"eklendi": "Eklendi", "guncellendi": "Güncellendi", "atlandi": "Atlandı", "hata": "Hata"}
DURUM_RENGI = {"eklendi": ortak.RENK_TAMAM, "guncellendi": ortak.RENK_TAMAM, "atlandi": ortak.RENK_UYARI,
               "hata": ortak.RENK_KRITIK}


class _SecenekDelegesi(QStyledItemDelegate):
    """Seçenekli sütunlarda yazılabilir açılır liste gösterir."""

    def __init__(self, ekran: "TopluGirisSayfasi"):
        super().__init__(ekran)
        self.ekran = ekran

    def createEditor(self, parent, option, index):
        sec = self.ekran.secenekler(index.column())
        if not sec:
            return super().createEditor(parent, option, index)
        cb = QComboBox(parent)
        cb.setEditable(True)
        cb.addItems(["", *sec])
        return cb

    def setEditorData(self, editor, index):
        if isinstance(editor, QComboBox):
            editor.setCurrentText(index.data() or "")
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText())
        else:
            super().setModelData(editor, model, index)


class _GirisTablosu(QTableWidget):
    def __init__(self, ekran: "TopluGirisSayfasi"):
        super().__init__()
        self.ekran = ekran
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed |
                             QAbstractItemView.AnyKeyPressed)

    def keyPressEvent(self, e):
        if e.matches(QKeySequence.Paste):
            self.ekran.yapistir()
        elif e.matches(QKeySequence.Copy):
            self.ekran.kopyala()
        elif e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.state() != QAbstractItemView.EditingState:
            self.ekran.secili_hucreleri_temizle()
        elif e.key() == Qt.Key_D and e.modifiers() & Qt.ControlModifier:
            self.ekran.asagi_doldur()
        else:
            super().keyPressEvent(e)


class _BelgeDialog(QDialog):
    """Belgede bulunan listeler ve ne yapılacağı: akıllı kaydet veya tabloya al."""

    def __init__(self, parent, taninan: list, taninmayan: list, hatalar: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Belge Yükle")
        self.resize(720, 420)
        self.secim = ""
        self.taninan = taninan
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<b>Belgede {len(taninan)} liste tanındı.</b> Akıllı Kaydet, her listeyi türüne göre "
                             "(öğrenci, işletme, yerleştirme, devamsızlık, ders dağılımı…) ilişkili kayıtlarıyla "
                             "birlikte doğrudan kaydeder; öncesinde yedek alınır. İsterseniz seçili listeyi giriş "
                             "tablosuna alıp kontrol ettikten sonra kaydedebilirsiniz."))
        lay.itemAt(0).widget().setWordWrap(True)
        self.liste = QListWidget()
        for b in taninan:
            baglam = aktarim.baglam_ozeti(b.tablo)
            it = QListWidgetItem(f"{b.etiket}\n→ {b.tur.ad}: {len(b.satirlar)} kayıt"
                                 + (f"   (belgeden: {baglam})" if baglam else ""))
            self.liste.addItem(it)
        for b in taninmayan:
            it = QListWidgetItem(f"{b.etiket}\n→ türü tanınmadı (Veri Aktarımı ekranında elle seçilebilir)")
            it.setFlags(Qt.NoItemFlags)
            self.liste.addItem(it)
        self.liste.setCurrentRow(0)
        lay.addWidget(self.liste, 1)
        if hatalar:
            h = QLabel("<span style='color:#b00020'>" + "<br>".join(hatalar) + "</span>")
            h.setWordWrap(True)
            lay.addWidget(h)
        dug = QHBoxLayout()
        dug.addStretch(1)
        kaydet = QPushButton("Akıllı Kaydet (tümünü)")
        kaydet.setDefault(True)
        kaydet.setStyleSheet("font-weight:bold")
        kaydet.clicked.connect(lambda: self._bitir("kaydet"))
        tablo = QPushButton("Seçili Listeyi Tabloya Al")
        tablo.clicked.connect(lambda: self._bitir("tablo"))
        vazgec = QPushButton("Vazgeç")
        vazgec.clicked.connect(self.reject)
        for w in (kaydet, tablo, vazgec):
            dug.addWidget(w)
        lay.addLayout(dug)

    @property
    def secili(self):
        i = self.liste.currentRow()
        return self.taninan[i] if 0 <= i < len(self.taninan) else self.taninan[0]

    def _bitir(self, secim: str) -> None:
        self.secim = secim
        self.accept()


class TopluGirisSayfasi(QWidget):
    def __init__(self, db, pencere=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.pencere = pencere
        self.tur: GirisTuru = GIRIS_TURLERI[0]
        self._dolduruluyor = False
        self._taslak_zamanlayici = QTimer(self)
        self._taslak_zamanlayici.setSingleShot(True)
        self._taslak_zamanlayici.setInterval(800)
        self._taslak_zamanlayici.timeout.connect(self._taslak_kaydet)

        lay = QVBoxLayout(self)
        r1 = QHBoxLayout()
        r1.addWidget(QLabel("<b>Giriş türü:</b>"))
        self.tur_secici = QComboBox()
        for g in GIRIS_TURLERI:
            self.tur_secici.addItem(g.ad, g.anahtar)
        self.tur_secici.currentIndexChanged.connect(self._tur_degisti)
        r1.addWidget(self.tur_secici, 1)
        lay.addLayout(r1)
        self.aciklama = QLabel()
        self.aciklama.setWordWrap(True)
        lay.addWidget(self.aciklama)
        ipucu = QLabel("<b>Belge Yükle</b> ile (veya belgeyi bu ekrana sürükleyerek) e-Okul/e-Mesem listelerini, "
                       "Excel/PDF/Word belgelerini tanıtıp doğrudan kaydedebilirsiniz. "
                       "Hücrelere doğrudan yazabilir ya da Excel'de veya e-Okul/e-Mesem ekranında satırları seçip "
                       "kopyalayarak (Ctrl+C) bir hücreye tıklayıp <b>Ctrl+V</b> ile yapıştırabilirsiniz. "
                       "Kopyaladığınız alan başlık satırını da içeriyorsa sütunlar sıralarına bakılmaksızın "
                       "kendiliğinden eşlenir. <b>Ctrl+D</b> seçili hücreleri en üstteki değerle doldurur. "
                       "Girdiğiniz bilgiler taslak olarak saklanır; program kapansa da kaybolmaz.")
        ipucu.setWordWrap(True)
        ipucu.setStyleSheet("color:#555")
        lay.addWidget(ipucu)

        r2 = ortak.AkisDuzeni()
        b = QPushButton("Belge Yükle...")
        b.setStyleSheet("font-weight:bold")
        b.setToolTip("e-Okul/e-Mesem/e-Bildirge'den indirilen veya elinizdeki Excel, PDF, Word, HTML, CSV, ZIP "
                     "belgesini seçin (ya da bu ekrana sürükleyin). Türü ve sütunları tanınır; isterseniz doğrudan "
                     "kaydedilir, isterseniz bu tabloya alınıp kontrol edilir.")
        b.clicked.connect(self.belge_sec)
        r2.addWidget(b)
        for metin, fn in [("Yapıştır (Ctrl+V)", self.yapistir), ("Aşağı Doldur (Ctrl+D)", self.asagi_doldur),
                          (f"+{BOS_SATIR} Satır", lambda: self._satir_ekle(BOS_SATIR)),
                          ("Seçili Satırları Sil", self.secili_satirlari_sil), ("Tümünü Temizle", self.temizle)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            r2.addWidget(b)
        r2.addStretch(1)
        for metin, fn in [("Kontrol Et", self.kontrol), ("Önizle (kaydetmez)", lambda: self.kaydet(True))]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            r2.addWidget(b)
        self.kaydet_btn = QPushButton("Kaydet")
        self.kaydet_btn.setStyleSheet("font-weight:bold")
        self.kaydet_btn.clicked.connect(lambda: self.kaydet(False))
        r2.addWidget(self.kaydet_btn)
        lay.addLayout(r2)

        self.tablo = _GirisTablosu(self)
        self.tablo.setItemDelegate(_SecenekDelegesi(self))
        self.tablo.itemChanged.connect(self._hucre_degisti)
        lay.addWidget(self.tablo, 1)

        self.ozet = QLabel()
        self.ozet.setWordWrap(True)
        self.ozet.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.ozet)
        self.oneri_kutu = QHBoxLayout()
        lay.addLayout(self.oneri_kutu)
        self.setAcceptDrops(True)
        self._tur_degisti()

    # ------------------------------------------------------------------ tablo

    @property
    def _durum_sutunu(self) -> int:
        return len(self.tur.sutunlar)

    def secenekler(self, j: int) -> tuple[str, ...]:
        return self.tur.sutunlar[j].secenekler if j < len(self.tur.sutunlar) else ()

    def _tur_degisti(self, _=None) -> None:
        if self.tablo.columnCount():
            self._taslak_kaydet()
        self.tur = GIRIS_SOZLUK[self.tur_secici.currentData()]
        self.aciklama.setText(self.tur.aciklama or f"Her satır bir {self.tur.ad.lower()} kaydıdır.")
        self._dolduruluyor = True
        self.tablo.clear()
        self.tablo.setColumnCount(len(self.tur.sutunlar) + 1)
        for j, s in enumerate(self.tur.sutunlar):
            it = QTableWidgetItem(s.baslik + (" *" if s.zorunlu else ""))
            it.setToolTip(" - ".join(x for x in (s.baslik, "zorunlu" if s.zorunlu else "", s.ipucu,
                                                 "seçenekler: " + ", ".join(s.secenekler) if s.secenekler else "")
                                     if x))
            self.tablo.setHorizontalHeaderItem(j, it)
        self.tablo.setHorizontalHeaderItem(self._durum_sutunu, QTableWidgetItem("Durum / Açıklama"))
        self._dolduruluyor = False
        self._yukle(toplu_giris.taslak_yukle(self.tur))
        self.tablo.resizeColumnsToContents()
        for j in range(self.tablo.columnCount()):
            self.tablo.setColumnWidth(j, max(110, min(self.tablo.columnWidth(j), 260)))
        self.tablo.setColumnWidth(self._durum_sutunu, 380)
        self.ozet.setText("")
        self._onerileri_temizle()

    def _yukle(self, satirlar: list[list[str]]) -> None:
        self._dolduruluyor = True
        try:
            self.tablo.setRowCount(0)
            self.tablo.setRowCount(max(BOS_SATIR, len(satirlar) + 20))
            for i, r in enumerate(satirlar):
                for j, v in enumerate(r[:len(self.tur.sutunlar)]):
                    if v:
                        self.tablo.setItem(i, j, QTableWidgetItem(str(v)))
        finally:
            self._dolduruluyor = False
        if satirlar:
            self.ozet.setText(f"Kaydedilmemiş taslaktan {len(satirlar)} satır yüklendi.")

    def _deger(self, i: int, j: int) -> str:
        it = self.tablo.item(i, j)
        return it.text().strip() if it else ""

    def satirlar(self) -> list[list[str]]:
        n = len(self.tur.sutunlar)
        return [[self._deger(i, j) for j in range(n)] for i in range(self.tablo.rowCount())]

    def _yaz(self, i: int, j: int, v: str) -> None:
        if j >= len(self.tur.sutunlar):
            return
        if i >= self.tablo.rowCount():
            self.tablo.setRowCount(i + 20)
        it = self.tablo.item(i, j)
        if it is None:
            self.tablo.setItem(i, j, QTableWidgetItem(v))
        else:
            it.setText(v)

    def _satir_ekle(self, n: int) -> None:
        self.tablo.setRowCount(self.tablo.rowCount() + n)

    def _son_dolu(self) -> int:
        dolu = toplu_giris.dolu_satirlar(self.satirlar())
        return dolu[-1] if dolu else -1

    def _hucre_degisti(self, it: QTableWidgetItem) -> None:
        if self._dolduruluyor or it.column() == self._durum_sutunu:
            return
        self._satir_durumunu_sil(it.row())
        if it.row() >= self.tablo.rowCount() - 5:
            self._satir_ekle(20)
        self._taslak_zamanlayici.start()

    def _taslak_kaydet(self) -> None:
        toplu_giris.taslak_kaydet(self.tur, self.satirlar())

    # ------------------------------------------------------------------ belge yükleme

    def dragEnterEvent(self, e):
        if surukle_dosyalar(e):
            e.acceptProposedAction()

    def dropEvent(self, e):
        yollar = surukle_dosyalar(e)
        if yollar:
            e.acceptProposedAction()
            self.belge_yukle(yollar)

    def belge_sec(self) -> None:
        yollar, _ = QFileDialog.getOpenFileNames(self, "Yüklenecek belgeleri seçin", str(Path.home()),
                                                 okuyucu.DOSYA_FILTRESI)
        if yollar:
            self.belge_yukle(yollar)

    def belge_yukle(self, yollar: list[str], secim: str | None = None) -> None:
        """Belgedeki listeleri tanır; kullanıcıya doğrudan kaydetmeyi veya tabloya almayı sunar.
        secim: 'kaydet' | 'tablo' (sormadan; testler ve eylemler için)."""
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            belgeler, hatalar = toplu_giris.belgeleri_incele(yollar)
        finally:
            QApplication.restoreOverrideCursor()
        taninan = [b for b in belgeler if b.tur and b.satirlar]
        taninmayan = [b for b in belgeler if not b.tur]
        if not taninan:
            mesaj = "Belgede tanınan bir veri listesi bulunamadı."
            if hatalar:
                mesaj += "\n\n" + "\n".join(hatalar)
            if belgeler and self.pencere is not None and ortak.onay(
                    self, mesaj + "\n\nBelge, sütunları elle eşleyebileceğiniz Veri Aktarımı ekranında açılsın mı?"):
                w = self.pencere.git("Veri Aktarımı")
                if w is not None:
                    w.dosyalari_ekle(yollar)
            elif not belgeler or self.pencere is None:
                ortak.bilgi(self, mesaj)
            return
        if secim is None:
            dlg = _BelgeDialog(self, taninan, taninmayan, hatalar)
            if not dlg.exec():
                return
            secim, secili = dlg.secim, dlg.secili
        else:
            secili = taninan[0]
        if secim == "kaydet":
            self._akilli_kaydet(yollar, taninmayan)
        else:
            self._tabloya_al(secili)

    def _tabloya_al(self, b: "toplu_giris.BelgeTablosu") -> None:
        i = self.tur_secici.findData(b.tur.anahtar)
        if i != self.tur_secici.currentIndex():
            self.tur_secici.setCurrentIndex(i)
        bas = self._son_dolu() + 1
        self._dolduruluyor = True
        try:
            for k, r in enumerate(b.satirlar):
                for j, v in enumerate(r):
                    if v:
                        self._yaz(bas + k, j, v)
        finally:
            self._dolduruluyor = False
        self._satir_ekle(20)
        self._taslak_kaydet()
        self.kontrol()
        baglam = aktarim.baglam_ozeti(b.tablo)
        self.ozet.setText(f"<b>{b.etiket}</b> belgesinden {len(b.satirlar)} satır <b>{b.tur.ad}</b> olarak "
                          f"{bas + 1}. satırdan itibaren alındı" + (f" (belgeden: {baglam})" if baglam else "")
                          + ". Kontrol sonuçlarına bakıp <b>Kaydet</b>'e basın.<br>" + self.ozet.text())

    def _akilli_kaydet(self, yollar: list[str], taninmayan: list) -> None:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            sonuclar, hatalar = toplu_giris.akilli_kaydet(self.db, yollar)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            ortak.hata(self, f"Kaydedilemedi: {e}")
            return
        QApplication.restoreOverrideCursor()
        satirlar = [s.ozet_metni() for s in sonuclar]
        for s in sonuclar:
            for h in s.hatalar[:5]:
                satirlar.append(f"<span style='color:#b00020'>{h}</span>")
            if len(s.hatalar) > 5:
                satirlar.append(f"<span style='color:#b00020'>… {len(s.hatalar) - 5} hata daha</span>")
        satirlar += [f"<span style='color:#8a6d3b'>{h}</span>" for h in hatalar]
        self.ozet.setText("<b>Belge akıllı kaydedildi (öncesinde yedek alındı):</b><br>" + "<br>".join(satirlar))
        self._onerileri_goster(sonuclar)
        if taninmayan and self.pencere is not None:
            b = QPushButton(f"Tanınmayan {len(taninmayan)} tabloyu Veri Aktarımı'nda aç")
            b.clicked.connect(lambda: self._aktarimda_ac(yollar))
            if not self.oneri_kutu.count():
                self.oneri_kutu.addStretch(1)
            self.oneri_kutu.insertWidget(self.oneri_kutu.count() - 1, b)

    def _aktarimda_ac(self, yollar: list[str]) -> None:
        w = self.pencere.git("Veri Aktarımı") if self.pencere is not None else None
        if w is not None:
            w.dosyalari_ekle(yollar)

    # ------------------------------------------------------------------ pano ve düzenleme

    def yapistir(self) -> None:
        satirlar = toplu_giris.yapistirilan_metin(QApplication.clipboard().text())
        if not satirlar:
            ortak.bilgi(self, "Panoda yapıştırılacak metin yok. Excel'de hücreleri seçip Ctrl+C ile kopyalayın.")
            return
        es = toplu_giris.basliklari_esle(self.tur, satirlar[0])
        self._dolduruluyor = True
        try:
            if es:
                bas = self._son_dolu() + 1
                veri = [r for r in satirlar[1:] if any(r)]
                for k, r in enumerate(veri):
                    for j, kaynak in es.items():
                        self._yaz(bas + k, j, " ".join(r[x] for x in kaynak if x < len(r) and r[x]))
                adlar = ", ".join(self.tur.sutunlar[j].baslik for j in sorted(es))
                mesaj = f"Başlıklar tanındı ({adlar}). {len(veri)} satır {bas + 1}. satırdan itibaren eklendi."
            else:
                i0, j0 = max(self.tablo.currentRow(), 0), max(self.tablo.currentColumn(), 0)
                secili = self.tablo.selectedIndexes()
                if len(satirlar) == 1 and len(satirlar[0]) == 1 and len(secili) > 1:
                    for ix in secili:
                        self._yaz(ix.row(), ix.column(), satirlar[0][0])
                    mesaj = f"{len(secili)} hücreye aynı değer yazıldı."
                else:
                    for k, r in enumerate(satirlar):
                        for m, v in enumerate(r):
                            self._yaz(i0 + k, j0 + m, v)
                    mesaj = f"{len(satirlar)} satır {i0 + 1}. satırdan itibaren yapıştırıldı."
        finally:
            self._dolduruluyor = False
        if self.tablo.rowCount() - self._son_dolu() < 10:
            self._satir_ekle(20)
        self.ozet.setText(mesaj + " Kaydetmeden önce <b>Kontrol Et</b> ile denetleyebilirsiniz.")
        self._taslak_zamanlayici.start()

    def kopyala(self) -> None:
        secili = self.tablo.selectedIndexes()
        if not secili:
            return
        satirlar = sorted({ix.row() for ix in secili})
        sutunlar = sorted({ix.column() for ix in secili})
        metin = "\n".join("\t".join(self._deger(i, j) for j in sutunlar) for i in satirlar)
        QApplication.clipboard().setText(metin)

    def secili_hucreleri_temizle(self) -> None:
        self._dolduruluyor = True
        for ix in self.tablo.selectedIndexes():
            it = self.tablo.item(ix.row(), ix.column())
            if it and ix.column() != self._durum_sutunu:
                it.setText("")
        self._dolduruluyor = False
        self._taslak_zamanlayici.start()

    def asagi_doldur(self) -> None:
        secili = self.tablo.selectedIndexes()
        if len(secili) < 2:
            ortak.bilgi(self, "Doldurmak için aynı sütunda birden fazla hücre seçin; en üstteki değer "
                              "aşağıdakilere yazılır.")
            return
        sutunlar: dict[int, list[int]] = {}
        for ix in secili:
            sutunlar.setdefault(ix.column(), []).append(ix.row())
        self._dolduruluyor = True
        for j, satirlar in sutunlar.items():
            satirlar.sort()
            v = self._deger(satirlar[0], j)
            for i in satirlar[1:]:
                self._yaz(i, j, v)
        self._dolduruluyor = False
        self._taslak_zamanlayici.start()

    def secili_satirlari_sil(self) -> None:
        satirlar = sorted({ix.row() for ix in self.tablo.selectedIndexes()}, reverse=True)
        if not satirlar:
            ortak.bilgi(self, "Önce silinecek satırları seçin.")
            return
        for i in satirlar:
            self.tablo.removeRow(i)
        if self.tablo.rowCount() < BOS_SATIR:
            self._satir_ekle(BOS_SATIR - self.tablo.rowCount())
        self._taslak_kaydet()

    def temizle(self) -> None:
        if toplu_giris.dolu_satirlar(self.satirlar()) and not ortak.onay(self, "Tablodaki tüm satırlar silinsin mi?"):
            return
        self._yukle([])
        self._taslak_kaydet()
        self.ozet.setText("")
        self._onerileri_temizle()

    # ------------------------------------------------------------------ renkler ve durum

    def _satir_durumunu_sil(self, i: int) -> None:
        self._dolduruluyor = True
        for j in range(self.tablo.columnCount()):
            it = self.tablo.item(i, j)
            if it:
                it.setBackground(QBrush())
                it.setToolTip("")
        if self.tablo.item(i, self._durum_sutunu):
            self.tablo.item(i, self._durum_sutunu).setText("")
        self._dolduruluyor = False

    def _durum_yaz(self, i: int, metin: str, renk) -> None:
        it = self.tablo.item(i, self._durum_sutunu)
        if it is None:
            it = QTableWidgetItem()
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.tablo.setItem(i, self._durum_sutunu, it)
        it.setText(metin)
        it.setToolTip(metin)
        if renk is not None:
            it.setBackground(renk)

    def _tum_durumlari_sil(self) -> None:
        for i in range(self.tablo.rowCount()):
            self._satir_durumunu_sil(i)

    def kontrol(self) -> bool:
        satirlar = self.satirlar()
        dolu = toplu_giris.dolu_satirlar(satirlar)
        self._tum_durumlari_sil()
        if not dolu:
            self.ozet.setText("Tabloda veri yok.")
            return False
        bulgular = toplu_giris.denetle(self.tur, satirlar)
        self._dolduruluyor = True
        satir_mesaj: dict[int, list[str]] = {}
        for b in bulgular:
            it = self.tablo.item(b.satir, b.sutun)
            if it is None:
                it = QTableWidgetItem("")
                self.tablo.setItem(b.satir, b.sutun, it)
            it.setBackground(ortak.RENK_KRITIK if b.hata else ortak.RENK_UYARI)
            it.setToolTip(b.mesaj)
            satir_mesaj.setdefault(b.satir, []).append(("" if b.hata else "Uyarı: ") + b.mesaj)
        for i in dolu:
            hatali = any(b.hata for b in bulgular if b.satir == i)
            self._durum_yaz(i, "; ".join(satir_mesaj.get(i, [])) or "Uygun",
                            ortak.RENK_KRITIK if hatali else ortak.RENK_UYARI if i in satir_mesaj else ortak.RENK_TAMAM)
        self._dolduruluyor = False
        hata = len({b.satir for b in bulgular if b.hata})
        uyari = len({b.satir for b in bulgular if not b.hata} - {b.satir for b in bulgular if b.hata})
        self.ozet.setText(f"{len(dolu)} satır denetlendi: {len(dolu) - hata - uyari} uygun, "
                          f"<span style='color:#b00020'>{hata} hatalı</span>, {uyari} uyarılı. "
                          "Hücrenin üzerine gelince açıklama görünür.")
        return hata == 0

    def kaydet(self, deneme: bool) -> None:
        satirlar = self.satirlar()
        if not toplu_giris.dolu_satirlar(satirlar):
            ortak.bilgi(self, "Kaydedilecek satır yok.")
            return
        if not self.kontrol() and not deneme and not ortak.onay(
                self, "Bazı satırlarda hata var (kırmızı hücreler). Hatalı satırlar atlanabilir veya eksik "
                      "kaydedilebilir. Yine de kaydedilsin mi?"):
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            sonuclar, durumlar = toplu_giris.kaydet(self.db, self.tur, satirlar, deneme)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            ortak.hata(self, f"Kaydedilemedi: {e}")
            return
        QApplication.restoreOverrideCursor()

        self._dolduruluyor = True
        for i, d in durumlar.items():
            metin = DURUM_ADI.get(d.durum, d.durum) + (": " + "; ".join(d.mesajlar) if d.mesajlar else "")
            self._durum_yaz(i, ("[Önizleme] " if deneme else "") + metin, DURUM_RENGI.get(d.durum))
        self._dolduruluyor = False
        sayac = {k: sum(1 for d in durumlar.values() if d.durum == k) for k in DURUM_ADI}
        bas = "<b>Önizleme (kaydedilmedi):</b>" if deneme else "<b>Kaydedildi (öncesinde yedek alındı):</b>"
        self.ozet.setText(f"{bas} {sayac['eklendi']} yeni, {sayac['guncellendi']} güncellendi, "
                          f"{sayac['atlandi']} atlandı, {sayac['hata']} hatalı.<br>"
                          + "<br>".join(s.ozet_metni() for s in sonuclar))
        if deneme:
            return
        self._onerileri_goster(sonuclar)
        basarili = [i for i, d in durumlar.items() if d.durum in ("eklendi", "guncellendi")]
        if basarili and ortak.onay(self, f"{len(basarili)} satır kaydedildi. Kaydedilen satırlar tablodan "
                                         "temizlensin mi? (Hatalı veya atlanan satırlar düzeltmeniz için kalır.)"):
            kalan = [r for i, r in enumerate(satirlar) if i not in set(basarili) and any(r)]
            durum_kalan = [self._deger(i, self._durum_sutunu) for i, r in enumerate(satirlar)
                           if i not in set(basarili) and any(r)]
            self._yukle(kalan)
            self._dolduruluyor = True
            for i, m in enumerate(durum_kalan):
                if m:
                    self._durum_yaz(i, m, ortak.RENK_KRITIK)
            self._dolduruluyor = False
        self._taslak_kaydet()

    # ------------------------------------------------------------------ sonraki adımlar

    def _onerileri_temizle(self) -> None:
        while self.oneri_kutu.count():
            w = self.oneri_kutu.takeAt(0).widget()
            if w:
                w.deleteLater()

    def _onerileri_goster(self, sonuclar) -> None:
        self._onerileri_temizle()
        oneriler, gorulen = [], set()
        for s in sonuclar:
            if not (s.eklenen or s.guncellenen):
                continue
            yeni_yer = list(s.yeni.get("yerlestirmeler", []))
            for etiket, e in surecler.sonraki_adimlar(s.anahtar, yeni_yer):
                if e not in gorulen:
                    gorulen.add(e)
                    oneriler.append((etiket, e, {"ids": yeni_yer} if e == "sozlesmeler_yeni" else {}))
        if not oneriler:
            return
        self.oneri_kutu.addWidget(QLabel("<b>Sonraki adımlar:</b>"))
        for etiket, e, kw in oneriler:
            b = QPushButton(etiket)
            b.clicked.connect(lambda _=False, e=e, kw=kw: eylem.calistir(
                self, self.db, e, lambda s: eylem.sonuc_goster(self, self.pencere, s), **kw))
            self.oneri_kutu.addWidget(b)
        self.oneri_kutu.addStretch(1)
