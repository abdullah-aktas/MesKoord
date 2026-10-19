"""Ders dağılımı ve haftalık ders programı / atölye yerleştirme."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFileDialog, QHeaderView, QInputDialog, QLabel, QListWidget, QMenu, QPushButton,
                               QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout,
                               QWidget)

from ..mevzuat import GUNLER
from ..services import aktarim, degisiklik, excel_io, okuyucu, program
from ..services.program_mevzuat import SEKME_ADIMLAR, SEKME_CERCEVE, SEKME_DAGILIM, SEKME_TABLO
from . import ortak
from .crud import CrudSayfasi
from .sayfa_aktarim import surukle_dosyalar
from .sayfa_cerceve import CerceveSayfasi
from .varliklar import DERS_ATAMALARI


class YerlesmeyenPenceresi(QDialog):
    """Yerleşmeyen her blok için engeller ve öneriler."""

    BASLIKLAR = ["Ders", "Blok", "Özet"]
    PENCERE = "Yerleşmeyen Dersler ve Nedenleri"
    EXCEL_SAYFASI = "Yerleşmeyen Dersler"
    EXCEL_IKINCI = "Blok (saat)"

    @staticmethod
    def ikinci(n) -> tuple[str, object, str]:
        """(tablodaki metin, Excel değeri, ayrıntı başlığındaki açıklama)."""
        return f"{n.uzunluk} saat", n.uzunluk, f"{n.uzunluk} saatlik blok"

    def __init__(self, nedenler: list, baslik: str, notlar: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.nedenler = nedenler
        self.setWindowTitle(self.PENCERE)
        self.resize(980, 620)
        lay = QVBoxLayout(self)
        ust = QLabel(f"<b>{baslik}</b>" + "".join(f"<br>{n}" for n in notlar or []))
        ust.setWordWrap(True)
        lay.addWidget(ust)
        sp = QSplitter(Qt.Vertical)
        self.tablo = QTableWidget(len(nedenler), 3)
        self.tablo.setHorizontalHeaderLabels(self.BASLIKLAR)
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tablo.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        for i, n in enumerate(nedenler):
            for j, v in enumerate([n.etiket, self.ikinci(n)[0], n.ozet]):
                self.tablo.setItem(i, j, QTableWidgetItem(v))
        self.tablo.resizeColumnsToContents()
        self.tablo.currentCellChanged.connect(self._goster)
        sp.addWidget(self.tablo)
        self.ayrinti = QTextBrowser()
        sp.addWidget(self.ayrinti)
        sp.setSizes([260, 320])
        lay.addWidget(sp, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        excel = bb.addButton("Excel'e Aktar", QDialogButtonBox.ActionRole)
        excel.clicked.connect(self.excel)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        if nedenler:
            self.tablo.setCurrentCell(0, 0)

    def _goster(self, satir: int, *_):
        if not 0 <= satir < len(self.nedenler):
            return
        n = self.nedenler[satir]
        html = f"<h3>{n.etiket} ({self.ikinci(n)[2]})</h3><p>{n.ozet}</p><b>Engeller</b><ul>"
        html += "".join(f"<li>{x}</li>" for x in n.nedenler) + "</ul><b>Ne yapmalı?</b><ol>"
        html += "".join(f"<li>{x}</li>" for x in n.oneriler) + "</ol>"
        self.ayrinti.setHtml(html)

    def excel(self):
        yol = ortak.kaydet_yolu(self, f"{self.EXCEL_SAYFASI}.xlsx")
        if not yol:
            return
        x = excel_io.ExcelYazici()
        x.sayfa(self.EXCEL_SAYFASI, [self.BASLIKLAR[0], self.EXCEL_IKINCI, "Özet", "Engeller", "Öneriler"],
                [[n.etiket, self.ikinci(n)[1], n.ozet, "\n".join(n.nedenler), "\n".join(n.oneriler)]
                 for n in self.nedenler], self.PENCERE)
        ortak.kaydedildi(self, x.kaydet(yol))


TIPLER = [("Sınıf", "sinif", "SELECT id, ad FROM siniflar ORDER BY seviye, ad"),
          ("Öğretmen", "ogretmen", "SELECT id, ad || ' ' || soyad FROM ogretmenler WHERE aktif = 1 ORDER BY ad, soyad"),
          ("Mekan (Atölye/Lab.)", "atolye", "SELECT id, ad FROM atolyeler ORDER BY ad")]


def hucre_metni(tip: str, h: dict) -> str:
    ogr = " / ".join(x for x in (f"{h['ogr_ad'] or ''} {h['ogr_soyad'] or ''}".strip(), h.get("ogretmen2")) if x)
    ders = h["kisa_ad"] or h["ders"]
    atl = " / ".join(x for x in (h["atolye"], h.get("atolye2")) if x)
    if tip == "sinif":
        parca = [ders, ogr, atl]
    elif tip == "ogretmen":
        parca = [h["sinif"], ders, atl]
    else:
        parca = [h["sinif"], ders, ogr]
    return "\n".join(p for p in parca if p)


class ProgramTablosu(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        ust = ortak.AkisDuzeni()
        self.tip = QComboBox()
        for ad, _, _ in TIPLER:
            self.tip.addItem(ad)
        self.kimlik = QComboBox()
        self.kimlik.setMinimumWidth(220)
        ust.addWidget(ortak.etiketli("Görünüm:", self.tip))
        ust.addWidget(self.kimlik)
        for metin, fn in [("Belgeden Yükle...", self.belge_sec), ("Ön Denetim", self.on_denetim),
                          ("Otomatik Yerleştir", self.otomatik), ("Neden Yerleşmedi?", self.nedenler),
                          ("Kilitsizleri Temizle", self.temizle), ("Kilitleri Aç", self.kilitleri_ac),
                          ("Kontrol Et", self.kontrol), ("Excel (Tüm Programlar)", self.excel),
                          ("PDF (Bu Tablo)", self.pdf)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        self.gevset = QCheckBox("Kurallar yerleşmeyince gevşet")
        self.gevset.setToolTip("Açıkken 'aynı güne gelmesin' ve koordinatörlük günü kuralları gerektiği kadar "
                               "gevşetilir; kapalıyken parametrelere kesin uyulur. Ayarlar'daki "
                               "'program_kural_gevset' ile aynıdır.")
        self.gevset.setChecked(bool(self.db.ayar("program_kural_gevset")))
        self.gevset.toggled.connect(lambda v: self.db.ayar_yaz("program_kural_gevset", 1 if v else 0))
        ust.addWidget(self.gevset)
        ust.addStretch()
        lay.addLayout(ust)

        sp = QSplitter()
        self.tablo = QTableWidget()
        self.tablo.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tablo.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tablo.customContextMenuRequested.connect(self.menu)
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tablo.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)
        sp.addWidget(self.tablo)
        sag = QWidget()
        sl = QVBoxLayout(sag)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(QLabel("<b>Eksik kalan ders saatleri</b>"))
        self.eksik = QListWidget()
        sl.addWidget(self.eksik)
        self.durum = QLabel()
        self.durum.setWordWrap(True)
        sl.addWidget(self.durum)
        ipucu = QLabel("Yeni program için önerilen sıra: 1) Ders dağılımını girin veya belgeden yükleyin "
                       "2) 'Kilitleri Aç' (belgeden gelen kilitler yerleştirmenin önünü keser) "
                       "3) 'Ön Denetim' 4) gerekirse 'Kurallar yerleşmeyince gevşet' 5) 'Otomatik Yerleştir'. "
                       "Yerleşmeyenler için 'Neden Yerleşmedi?' nedeni ve öneriyi gösterir.\n\n"
                       "Sağ tık: hücreyi kilitle/aç, sil veya boş hücreye ders ekle. Kilitli hücreler otomatik "
                       "yerleştirmede korunur. e-Okul PDF'lerini 'Belgeden Yükle' ile seçin ya da sürükleyin.")
        ipucu.setWordWrap(True)
        ipucu.setStyleSheet("color:#666")
        sl.addWidget(ipucu)
        sp.addWidget(sag)
        sp.setSizes([900, 280])
        lay.addWidget(sp, 1)

        self.tip.currentIndexChanged.connect(self._kimlikleri_doldur)
        self.kimlik.currentIndexChanged.connect(lambda _: self.ciz())
        self.hucreler: dict = {}
        self._belge_kuyruk: list[list] = []
        self._belge_isleniyor = False
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if surukle_dosyalar(e):
            e.acceptProposedAction()

    def dropEvent(self, e):
        yollar = surukle_dosyalar(e)
        if yollar:
            e.acceptProposedAction()
            self.belge_yukle(yollar)

    def belge_sec(self):
        yollar, _ = QFileDialog.getOpenFileNames(self, "Ders programı / dağılım / müsaitlik belgesi seçin",
                                                 str(Path.home()), okuyucu.DOSYA_FILTRESI)
        if yollar:
            self.belge_yukle(yollar)

    def belge_yukle(self, yollar, sormadan: bool = False) -> list:
        yollar = list(yollar)
        if sormadan:
            return self._belge_oku(self.db, yollar, sor=False)
        self._belge_kuyruk.append(yollar)
        self._belge_siradaki()
        return []

    def _belge_oku(self, db, yollar, sor: bool) -> list:
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            sonuclar, hatalar = aktarim.otomatik_aktar(db, yollar)
            degisiklik.kaydet(db, sonuclar)
        finally:
            QApplication.restoreOverrideCursor()
        self._belge_goster(sonuclar, hatalar, sor)
        return sonuclar

    def _belge_siradaki(self) -> None:
        if self._belge_isleniyor or not self._belge_kuyruk:
            return
        yollar = self._belge_kuyruk.pop(0)
        self._belge_isleniyor = True
        self.durum.setText("Belge okunuyor. Ekran kilitlenmez.")

        def is_():
            kopya = self.db.kopya()
            try:
                sonuclar, hatalar = aktarim.otomatik_aktar(kopya, yollar)
                degisiklik.kaydet(kopya, sonuclar)
                return sonuclar, hatalar
            finally:
                kopya.close()

        def bitti(cift):
            self._belge_isleniyor = False
            sonuclar, hatalar = cift
            self._belge_goster(sonuclar, hatalar, True)
            self._belge_siradaki()

        def hata(tb: str):
            self._belge_isleniyor = False
            satir = tb.strip().splitlines()[-1] if tb.strip() else "belge okunamadı"
            ortak.hata(self, f"Belge okunamadı.\n{satir}")
            self._belge_siradaki()

        ortak.arka_planda(is_, bitti, hata)

    def _belge_goster(self, sonuclar, hatalar, sor: bool) -> list:
        self._kimlikleri_doldur()
        self._ana_yenile()
        if not sonuclar:
            ortak.hata(self, "\n".join(hatalar) or "Belgede ders programı verisi bulunamadı.")
            return sonuclar
        metin = "\n".join(f"- {s.ozet_metni()}" for s in sonuclar)
        ozet = degisiklik.metin(sonuclar)
        if ozet:
            metin += "\n\nDeğişen kayıtlar:\n" + ozet
        hatali = [h for s in sonuclar for h in s.hatalar][:10] + hatalar[:10]
        if hatali:
            metin += "\n\nUyarılar:\n" + "\n".join(f"- {h}" for h in hatali)
        eksik = program.eksik_saatler(self.db)
        if not sor:
            return sonuclar
        if eksik and ortak.onay(self, metin + f"\n\n{len(eksik)} dersin saatleri programa tam yerleşmemiş. "
                                       "Kalan saatler otomatik yerleştirilsin mi? (Belgeden gelen saatler kilitli "
                                       "olduğu için korunur.)", "Belgeden Yükleme"):
            self.otomatik(sormadan=True)
        elif not eksik:
            ortak.bilgi(self, metin, "Belgeden Yükleme")
        return sonuclar

    def _ana_yenile(self) -> None:
        pencere = self.window()
        sayfalar = getattr(pencere, "sayfa", None)
        if isinstance(sayfalar, dict):
            ana = sayfalar.get("Ana Sayfa")
            if ana is not None and hasattr(ana, "yenile"):
                ana.yenile()

    def on_denetim(self):
        bulgular = program.on_denetim(self.db)
        if not bulgular:
            ortak.bilgi(self, "Ön denetimde sorun bulunmadı; otomatik yerleştirmeye hazır.", "Ön Denetim")
            return
        ortak.bilgi(self, "\n".join(f"[{b.seviye}] {b.konu}: {b.mesaj}" for b in bulgular[:40])
                    + ("\n\nKritik bulgular düzeltilmeden bazı dersler yerleşemez." if
                       any(b.seviye == "Kritik" for b in bulgular) else ""), "Ön Denetim")

    def kilitleri_ac(self):
        if ortak.onay(self, "Tüm program hücrelerinin kilidi açılsın mı? Sonraki otomatik yerleştirmede yeniden "
                            "düzenlenebilirler."):
            self.db.execute("UPDATE program_hucreleri SET kilitli = 0")
            self.ciz()

    def showEvent(self, e):
        super().showEvent(e)
        self._kimlikleri_doldur()

    def yenile(self):
        self._kimlikleri_doldur()

    def _tip(self) -> tuple[str, str, str]:
        return TIPLER[self.tip.currentIndex()]

    def _kimlikleri_doldur(self):
        secili = self.kimlik.currentData()
        self.kimlik.blockSignals(True)
        self.kimlik.clear()
        for r in self.db.q(self._tip()[2]):
            self.kimlik.addItem(str(r[1]), r[0])
        i = self.kimlik.findData(secili)
        self.kimlik.setCurrentIndex(max(0, i))
        self.kimlik.blockSignals(False)
        self.ciz()

    def ciz(self):
        S = self.db.ayar("gunluk_ders_saati")
        self.tablo.clear()
        self.tablo.setRowCount(S)
        self.tablo.setColumnCount(5)
        self.tablo.setHorizontalHeaderLabels(GUNLER)
        self.tablo.setVerticalHeaderLabels([f"{h}. saat" for h in range(1, S + 1)])
        _, tip, _ = self._tip()
        kid = self.kimlik.currentData()
        self.hucreler = program.program_tablosu(self.db, tip, kid) if kid else {}
        okul_gunleri = None
        if tip == "sinif" and kid:
            from ..services.utils import gunler_listesi
            r = self.db.q1("SELECT okul_gunleri FROM siniflar WHERE id = ?", (kid,))
            okul_gunleri = set(gunler_listesi(r["okul_gunleri"]) or [1, 2, 3, 4, 5])
        for (g, h), x in self.hucreler.items():
            if 1 <= g <= 5 and 1 <= h <= S:
                it = QTableWidgetItem(hucre_metni(tip, x) + ("\n(kilitli)" if x["kilitli"] else ""))
                it.setTextAlignment(Qt.AlignCenter)
                it.setBackground(QBrush(QColor("#fff2b3" if x["kilitli"] else "#e3ecfa")))
                self.tablo.setItem(h - 1, g - 1, it)
        if okul_gunleri is not None:
            for g in range(1, 6):
                if g not in okul_gunleri:
                    for h in range(1, S + 1):
                        it = QTableWidgetItem("İşletme günü")
                        it.setTextAlignment(Qt.AlignCenter)
                        it.setForeground(QBrush(QColor("#888")))
                        it.setBackground(QBrush(QColor("#eeeeee")))
                        self.tablo.setItem(h - 1, g - 1, it)
        self.eksik.clear()
        for etiket, gereken, yerlesen in program.eksik_saatler(self.db):
            self.eksik.addItem(f"{etiket}: {yerlesen}/{gereken}")
        toplam = self.db.q1("SELECT COUNT(*) c FROM program_hucreleri")["c"]
        self.durum.setText(f"Programda {toplam} ders saati var.")

    def menu(self, pos):
        it = self.tablo.indexAt(pos)
        if not it.isValid():
            return
        g, h = it.column() + 1, it.row() + 1
        x = self.hucreler.get((g, h))
        m = QMenu(self)
        if x:
            kilit = m.addAction("Kilidi Aç" if x["kilitli"] else "Kilitle")
            sil = m.addAction("Sil")
            secim = m.exec(self.tablo.viewport().mapToGlobal(pos))
            for hid in x["ids"] if secim in (kilit, sil) else []:
                if secim == kilit:
                    self.db.execute("UPDATE program_hucreleri SET kilitli = ? WHERE id = ?",
                                    (0 if x["kilitli"] else 1, hid))
                else:
                    self.db.delete("program_hucreleri", hid)
            self.ciz()
        elif self._tip()[1] == "sinif":
            ekle = m.addAction("Ders ekle...")
            if m.exec(self.tablo.viewport().mapToGlobal(pos)) == ekle:
                self._ders_ekle(g, h)

    def _ders_ekle(self, g: int, h: int):
        sinif_id = self.kimlik.currentData()
        rows = self.db.q("""SELECT da.id, d.ad, d.atolye_gerekli, d.alan_id, da.atolye_id, da.atolye2_id,
                                   da.ogretmen_id, da.haftalik_saat, (SELECT COUNT(*) FROM program_hucreleri ph WHERE ph.atama_id = da.id) AS y,
                                   COALESCE(o.ad || ' ' || o.soyad, '-') AS ogr
                            FROM ders_atamalari da JOIN dersler d ON d.id = da.ders_id
                            LEFT JOIN ogretmenler o ON o.id = da.ogretmen_id WHERE da.sinif_id = ?""", (sinif_id,))
        adaylar = [r for r in rows if r["y"] < r["haftalik_saat"]]
        if not adaylar:
            ortak.bilgi(self, "Bu sınıfın yerleşmemiş ders saati yok.")
            return
        etiketler = [f"{r['ad']} - {r['ogr']} ({r['y']}/{r['haftalik_saat']})" for r in adaylar]
        sec, ok = QInputDialog.getItem(self, "Ders ekle", "Ders:", etiketler, 0, False)
        if not ok:
            return
        r = adaylar[etiketler.index(sec)]
        uyarilar = program.elle_ekleme_uyarilari(self.db, r["id"], g, h)
        if uyarilar and not ortak.onay(self, "Bu yerleşim parametrelere / kurallara aykırı:\n"
                                       + "\n".join(f"- {u}" for u in uyarilar)
                                       + "\n\nYine de eklensin mi? (Kilitli eklenir; 'Kontrol Et' bu yerleri "
                                         "listeler.)", "Kurala Aykırı Yerleşim"):
            return
        mesgul = self.db.q1("""SELECT o.ad || ' ' || o.soyad AS ad FROM program_hucreleri ph
                               JOIN ders_ogretmenleri dog ON dog.atama_id = ph.atama_id
                               JOIN ogretmenler o ON o.id = dog.ogretmen_id
                               JOIN ders_atamalari da ON da.id = ph.atama_id
                               JOIN ders_atamalari bu ON bu.id = ?
                               WHERE ph.gun = ? AND ph.saat = ?
                                 AND dog.ogretmen_id IN (SELECT ogretmen_id FROM ders_ogretmenleri WHERE atama_id = bu.id)
                                 AND (TRIM(bu.birlestirme) = '' OR LOWER(TRIM(da.birlestirme)) <> LOWER(TRIM(bu.birlestirme)))""",
                            (r["id"], g, h))
        if mesgul:
            ortak.hata(self, f"{mesgul['ad']} bu saatte başka derste.")
            return
        dolu = set()
        for x in self.db.q("SELECT atolye_id, atolye2_id FROM program_hucreleri WHERE gun = ? AND saat = ?", (g, h)):
            dolu |= {x["atolye_id"], x["atolye2_id"]}
        atolye, atolye2 = r["atolye_id"], r["atolye2_id"]
        if not atolye and r["atolye_gerekli"]:
            bos = [a["id"] for a in self.db.q("SELECT id FROM atolyeler WHERE alan_id IS ? OR ? IS NULL",
                                              (r["alan_id"], r["alan_id"])) if a["id"] not in dolu | {atolye2}]
            if not bos:
                ortak.hata(self, "Bu saatte uygun boş atölye/laboratuvar yok.")
                return
            atolye = bos[0]
        if dolu & {atolye, atolye2} - {None}:
            ortak.hata(self, "Atölye bu saatte dolu.")
            return
        self.db.insert("program_hucreleri", {"atama_id": r["id"], "gun": g, "saat": h, "atolye_id": atolye,
                                             "atolye2_id": atolye2, "kilitli": 1})
        self.ciz()

    def otomatik(self, sormadan: bool = False):
        if not sormadan and not ortak.onay(
                self, "Kilitli olmayan tüm ders yerleşimleri silinip yeniden oluşturulacak. Devam edilsin mi?"):
            return
        kilitli = self.db.q1("SELECT COUNT(*) c FROM program_hucreleri WHERE kilitli = 1")["c"]
        if not sormadan and kilitli and ortak.onay(
                self, f"{kilitli} kilitli hücre var; otomatik yerleştirme bunları yerinde tutar ve çoğu zaman "
                      "programı tamamlayamaz.\n\nBelgeden yüklediyseniz önce kilitleri açmanız gerekir. "
                      "Şimdi tüm kilitler açılsın mı?"):
            self.db.execute("UPDATE program_hucreleri SET kilitli = 0")
        kritik = [b for b in program.on_denetim(self.db) if b.seviye == "Kritik"]
        if kritik and not ortak.onay(self, "Ön denetimde yerleşmeyi engelleyebilecek sorunlar var:\n"
                                           + "\n".join(f"- {b.konu}: {b.mesaj}" for b in kritik[:15])
                                           + "\n\nYine de yerleştirilsin mi?"):
            return
        gevset = self.gevset.isChecked()
        self.setEnabled(False)
        self.durum.setText("Yerleştiriliyor, lütfen bekleyiniz...")

        def is_():
            d = self.db.kopya()
            try:
                s = program.programi_olustur(d, gevset=gevset)
                return len(s.hucreler), s.nedenler, s.sure, list(s.notlar)
            finally:
                d.close()

        def bitti(r):
            self.setEnabled(True)
            n, nedenler, sure, notlar = r
            self.ciz()
            self._ana_yenile()
            if nedenler:
                self.son_pencere = YerlesmeyenPenceresi(
                    nedenler, f"{n} saat yerleşti ({sure:.1f} sn). Parametrelere uyularak yerleşemeyen "
                              f"{len(nedenler)} blok var; her birinin nedeni ve çözüm önerisi aşağıdadır.", notlar,
                    self)
                self.son_pencere.open()
            else:
                ortak.bilgi(self, f"Tüm dersler çakışmasız ve parametrelere uygun yerleşti ({n} saat, {sure:.1f} sn)."
                            + "".join(f"\n\nNot: {x}" for x in notlar))

        def hata_(e):
            self.setEnabled(True)
            ortak.hata(self, e)

        ortak.arka_planda(is_, bitti, hata_)

    def nedenler(self):
        self.setEnabled(False)
        self.durum.setText("Yerleşmeme nedenleri hesaplanıyor...")

        def is_():
            d = self.db.kopya()
            try:
                return program.yerlesmeme_nedenleri(d)
            finally:
                d.close()

        def bitti(nedenler):
            self.setEnabled(True)
            self.durum.setText("")
            if not nedenler:
                ortak.bilgi(self, "Bütün ders saatleri programda; yerleşmeyen ders yok.", "Neden Yerleşmedi?")
                return
            self.son_pencere = YerlesmeyenPenceresi(
                nedenler, f"Programda eksik {len(nedenler)} blok var. Engeller bugünkü programa (kilitli ve kilitsiz "
                          "bütün hücreler yerinde kalarak) göre hesaplandı.", parent=self)
            self.son_pencere.open()

        def hata_(e):
            self.setEnabled(True)
            self.durum.setText("")
            ortak.hata(self, e)

        ortak.arka_planda(is_, bitti, hata_)

    def temizle(self):
        if ortak.onay(self, "Kilitli olmayan tüm program hücreleri silinsin mi?"):
            self.db.execute("DELETE FROM program_hucreleri WHERE kilitli = 0")
            self.ciz()

    def kontrol(self):
        c = program.catismalar(self.db)
        e = program.eksik_saatler(self.db)
        k = program.kural_ihlalleri(self.db)
        if not c and not e and not k:
            ortak.bilgi(self, "Çakışma yok, tüm ders saatleri yerleşmiş ve program kısıtlarına uyuyor.")
        else:
            ortak.bilgi(self, "\n".join(c[:30] + [f"Eksik: {a} ({y}/{g})" for a, g, y in e[:30]] + k[:30]))

    def _tablo_satirlari(self, tip: str, kid: int) -> list[list[str]]:
        return tablo_satirlari(self.db, tip, kid)

    def excel(self):
        yol = ortak.kaydet_yolu(self, "Ders Programları.xlsx")
        if not yol:
            return
        x = excel_io.ExcelYazici()
        for ad, tip, sql in TIPLER:
            for r in self.db.q(sql):
                x.sayfa(f"{ad[:3]}-{r[1]}"[:31], ["Saat"] + GUNLER, self._tablo_satirlari(tip, r[0]),
                        baslik=f"{ad}: {r[1]} - Haftalık Ders Programı")
        x.kaydet(yol)
        ortak.kaydedildi(self, yol)

    def pdf(self):
        ad, tip, _ = self._tip()
        kid = self.kimlik.currentData()
        if not kid:
            return
        yol = ortak.kaydet_yolu(self, f"Program - {self.kimlik.currentText()}.pdf", "PDF (*.pdf)")
        if not yol:
            return
        program_pdf(self.db, tip, kid, f"{ad}: {self.kimlik.currentText()}", yol)
        ortak.kaydedildi(self, yol)


def tablo_satirlari(db, tip: str, kid: int) -> list[list[str]]:
    S = db.ayar("gunluk_ders_saati")
    hc = program.program_tablosu(db, tip, kid)
    return [[f"{h}. saat"] + [hucre_metni(tip, hc[(g, h)]).replace("\n", " / ") if (g, h) in hc else ""
                              for g in range(1, 6)] for h in range(1, S + 1)]


def program_pdf(db, tip: str, kid: int, etiket: str, yol: Path) -> Path:
    k = db.kurum()
    satirlar = [[c.replace(" / ", "<br>") for c in s] for s in tablo_satirlari(db, tip, kid)]
    html = ortak.html_tablo(f"{k['ad']}<br>{etiket} - Haftalık Ders Programı", ["Saat"] + GUNLER, satirlar,
                            f"{k['egitim_yili']} Eğitim-Öğretim Yılı")
    return ortak.html_pdf(html, Path(yol))


def _gun_yazi(s: str | None) -> str:
    from ..services.utils import gunler_listesi
    return ", ".join(GUNLER[g - 1][:3] for g in gunler_listesi(s) if 1 <= g <= len(GUNLER))


class NobetSayfasi(QWidget):
    """Öğretmen nöbet günü, nöbet yeri ve e-Okul sınıf öğretmenliği kodu."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Nöbet günü ve yeri ile sınıf öğretmenliği kodu. Sınıf öğretmenliği, e-Okul'daki "
                             "koddur (ör. 12AT); rehber öğretmen ataması sınıflar ekranındadır."))
        self.tablo = QTableWidget(0, 4)
        self.tablo.setHorizontalHeaderLabels(["Öğretmen", "Nöbet Günü", "Nöbet Yeri", "Sınıf Öğretmenliği"])
        self.tablo.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.tablo, 1)
        alt = ortak.AkisDuzeni()
        b = QPushButton("Kaydet")
        b.clicked.connect(self.kaydet)
        alt.addWidget(b)
        self.durum = QLabel()
        alt.addWidget(self.durum)
        alt.addStretch()
        lay.addLayout(alt)

    def showEvent(self, e):
        super().showEvent(e)
        self.yukle()

    def yukle(self):
        rows = self.db.q("""SELECT id, ad, soyad, nobet_gun, nobet_yeri, sinif_ogretmenligi FROM ogretmenler
                            WHERE aktif = 1 ORDER BY ad, soyad""")
        self.tablo.setRowCount(len(rows))
        for i, r in enumerate(rows):
            it = QTableWidgetItem(f"{r['ad']} {r['soyad']}")
            it.setData(Qt.UserRole, r["id"])
            it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.tablo.setItem(i, 0, it)
            cb = QComboBox()
            cb.addItem("—", 0)
            for n, ad in enumerate(GUNLER, 1):
                cb.addItem(ad, n)
            cb.setCurrentIndex(max(0, cb.findData(r["nobet_gun"] or 0)))
            self.tablo.setCellWidget(i, 1, cb)
            self.tablo.setItem(i, 2, QTableWidgetItem(r["nobet_yeri"] or ""))
            self.tablo.setItem(i, 3, QTableWidgetItem(r["sinif_ogretmenligi"] or ""))

    def kaydet(self):
        for i in range(self.tablo.rowCount()):
            it = self.tablo.item(i, 0)
            if it is None:
                continue
            gun = self.tablo.cellWidget(i, 1).currentData()
            self.db.update("ogretmenler", it.data(Qt.UserRole), {
                "nobet_gun": gun or None,
                "nobet_yeri": (self.tablo.item(i, 2).text() if self.tablo.item(i, 2) else "").strip(),
                "sinif_ogretmenligi": (self.tablo.item(i, 3).text() if self.tablo.item(i, 3) else "").strip(),
            })
        self.durum.setText("Nöbet kayıtları kaydedildi.")


class OzelDurumSayfasi(QWidget):
    """Okul/işletme günleri ve ders dağılımındaki ortak öğretmen, mekan, birleştirme."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Okul ve işletme günlerini Pzt, Sal, Çar, Per, Cum yazın (1=Pazartesi … 5=Cuma). "
                             "Boş işletme günü temizlenir. Mekan yoksa oluşturulur. 2. öğretmen, listede "
                             "kayıtlı bir öğretmenin adı soyadı olmalıdır."))
        lay.addWidget(QLabel("<b>Sınıf günleri</b>"))
        self.siniflar = QTableWidget(0, 3)
        self.siniflar.setHorizontalHeaderLabels(["Sınıf", "Okul Günleri", "İşletme Günleri"])
        self.siniflar.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.siniflar, 1)
        lay.addWidget(QLabel("<b>Ortak ders, mekan ve birleştirme</b>"))
        self.atamalar = QTableWidget(0, 6)
        self.atamalar.setHorizontalHeaderLabels(["Sınıf", "Ders", "Öğretmen", "2. Öğretmen", "Mekan", "Birleştirme"])
        self.atamalar.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.atamalar, 2)
        alt = ortak.AkisDuzeni()
        b = QPushButton("Kaydet")
        b.clicked.connect(self.kaydet)
        alt.addWidget(b)
        self.durum = QLabel()
        self.durum.setWordWrap(True)
        alt.addWidget(self.durum)
        alt.addStretch()
        lay.addLayout(alt)

    def showEvent(self, e):
        super().showEvent(e)
        self.yukle()

    def _ro(self, metin: str, kayit: int | None = None) -> QTableWidgetItem:
        it = QTableWidgetItem(metin or "")
        it.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        if kayit is not None:
            it.setData(Qt.UserRole, kayit)
        return it

    def yukle(self):
        siniflar = self.db.q("SELECT id, ad, okul_gunleri, isletme_gunleri FROM siniflar ORDER BY seviye, ad")
        self.siniflar.setRowCount(len(siniflar))
        for i, r in enumerate(siniflar):
            self.siniflar.setItem(i, 0, self._ro(r["ad"], r["id"]))
            self.siniflar.setItem(i, 1, QTableWidgetItem(_gun_yazi(r["okul_gunleri"])))
            self.siniflar.setItem(i, 2, QTableWidgetItem(_gun_yazi(r["isletme_gunleri"])))
        rows = self.db.q("""SELECT da.id, s.ad AS sinif, d.ad AS ders,
                                   TRIM(COALESCE(o.ad, '') || ' ' || COALESCE(o.soyad, '')) AS ogretmen,
                                   TRIM(COALESCE(o2.ad, '') || ' ' || COALESCE(o2.soyad, '')) AS ogretmen2,
                                   COALESCE(a.ad, '') AS atolye, COALESCE(da.birlestirme, '') AS birlestirme
                            FROM ders_atamalari da
                            JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id
                            LEFT JOIN ogretmenler o ON o.id = da.ogretmen_id
                            LEFT JOIN ogretmenler o2 ON o2.id = da.ogretmen2_id
                            LEFT JOIN atolyeler a ON a.id = da.atolye_id
                            ORDER BY s.seviye, s.ad, d.ad""")
        self.atamalar.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.atamalar.setItem(i, 0, self._ro(r["sinif"], r["id"]))
            self.atamalar.setItem(i, 1, self._ro(r["ders"]))
            self.atamalar.setItem(i, 2, self._ro(r["ogretmen"]))
            self.atamalar.setItem(i, 3, QTableWidgetItem(r["ogretmen2"] or ""))
            self.atamalar.setItem(i, 4, QTableWidgetItem(r["atolye"] or ""))
            self.atamalar.setItem(i, 5, QTableWidgetItem(r["birlestirme"] or ""))

    def _hucre(self, tablo: QTableWidget, satir: int, sutun: int) -> str:
        it = tablo.item(satir, sutun)
        return it.text().strip() if it else ""

    def _ogretmen_id(self, ad: str) -> int | None:
        """Boşsa None, bulunamazsa -1."""
        if not ad:
            return None
        for r in self.db.q("SELECT id, ad, soyad FROM ogretmenler"):
            if aktarim.norm(f"{r['ad']} {r['soyad']}") == aktarim.norm(ad):
                return r["id"]
        return -1

    def _mekan_id(self, ad: str) -> int | None:
        if not ad:
            return None
        for r in self.db.q("SELECT id, ad FROM atolyeler"):
            if aktarim.norm(r["ad"]) == aktarim.norm(ad):
                return r["id"]
        return self.db.insert("atolyeler", {"ad": ad})

    def kaydet(self):
        for i in range(self.siniflar.rowCount()):
            it = self.siniflar.item(i, 0)
            if it is None:
                continue
            self.db.update("siniflar", it.data(Qt.UserRole), {
                "okul_gunleri": aktarim.gunler_coz(self._hucre(self.siniflar, i, 1)),
                "isletme_gunleri": aktarim.gunler_coz(self._hucre(self.siniflar, i, 2)),
            })
        bilinmeyen = []
        for i in range(self.atamalar.rowCount()):
            it = self.atamalar.item(i, 0)
            if it is None:
                continue
            vals = {"birlestirme": self._hucre(self.atamalar, i, 5),
                    "atolye_id": self._mekan_id(self._hucre(self.atamalar, i, 4))}
            ogr2 = self._ogretmen_id(self._hucre(self.atamalar, i, 3))
            if ogr2 == -1:
                bilinmeyen.append(self._hucre(self.atamalar, i, 3))
            else:
                birincil = aktarim.norm(self._hucre(self.atamalar, i, 2))
                ayni = aktarim.norm(self._hucre(self.atamalar, i, 3)) == birincil
                vals["ogretmen2_id"] = None if ogr2 is None or ayni else ogr2
            self.db.update("ders_atamalari", it.data(Qt.UserRole), vals)
        self.yukle()
        self.durum.setText("Kaydedildi." if not bilinmeyen else
                           "Kaydedildi. Bulunamayan öğretmen (2. öğretmen yazılmadı): " + ", ".join(bilinmeyen))


class ProgramSayfasi(QTabWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        from .sayfa_program_surec import ProgramSurecSayfasi
        self.addTab(ProgramSurecSayfasi(db), SEKME_ADIMLAR)
        self.addTab(CrudSayfasi(db, DERS_ATAMALARI), SEKME_DAGILIM)
        self.addTab(ProgramTablosu(db), SEKME_TABLO)
        self.addTab(CerceveSayfasi(db), SEKME_CERCEVE)
        self.addTab(NobetSayfasi(db), "Nöbet")
        self.addTab(OzelDurumSayfasi(db), "Özel Durumlar")

    def sekme(self, ad: str) -> QWidget | None:
        for i in range(self.count()):
            if self.tabText(i) == ad:
                self.setCurrentIndex(i)
                return self.widget(i)
        return None

    def program_tablosu(self) -> "ProgramTablosu":
        return next(self.widget(i) for i in range(self.count()) if isinstance(self.widget(i), ProgramTablosu))
