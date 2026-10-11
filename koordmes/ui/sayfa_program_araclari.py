"""Ders programı araçları: kısıtlar, toplu çakma, sürümler, sınıf öğretmenliği, ders devri, yük analizi."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QSpinBox, QSplitter, QTabWidget,
                               QVBoxLayout, QWidget)

from ..mevzuat import GUNLER
from ..services import excel_io, program
from ..services import program_araclari as pa
from . import ortak


def _aciklama(metin: str) -> QLabel:
    lbl = QLabel(metin)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color:#555")
    return lbl


def _isaretli_liste() -> QListWidget:
    lst = QListWidget()
    lst.setSelectionMode(QListWidget.ExtendedSelection)
    return lst


def _isaretle(lst: QListWidget, metin: str, veri, secili: bool) -> None:
    it = QListWidgetItem(metin)
    it.setData(Qt.UserRole, veri)
    it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
    it.setCheckState(Qt.Checked if secili else Qt.Unchecked)
    lst.addItem(it)


def _isaretliler(lst: QListWidget) -> list:
    return [lst.item(i).data(Qt.UserRole) for i in range(lst.count()) if lst.item(i).checkState() == Qt.Checked]


def _tumunu(lst: QListWidget, durum: bool) -> None:
    for i in range(lst.count()):
        lst.item(i).setCheckState(Qt.Checked if durum else Qt.Unchecked)


def _ogretmen_doldur(cb: QComboBox, db, bos: str | None = None) -> None:
    secili = cb.currentData()
    cb.blockSignals(True)
    cb.clear()
    if bos is not None:
        cb.addItem(bos, None)
    for r in db.q("SELECT id, ad || ' ' || soyad AS ad, brans FROM ogretmenler WHERE aktif = 1 ORDER BY ad, soyad"):
        cb.addItem(f"{r['ad']}" + (f" ({r['brans']})" if r["brans"] else ""), r["id"])
    cb.setCurrentIndex(max(0, cb.findData(secili)))
    cb.blockSignals(False)


class DersGrubuPenceresi(QDialog):
    def __init__(self, db, kayit: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Aynı Güne Gelmeyecek Dersler")
        self.resize(420, 520)
        lay = QVBoxLayout(self)
        self.ad = QLineEdit((kayit or {}).get("ad", ""))
        self.ad.setPlaceholderText("Grup adı (ör. Sayısal dersler)")
        lay.addWidget(ortak.etiketli("Ad:", self.ad))
        self.aktif = QCheckBox("Etkin")
        self.aktif.setChecked(bool((kayit or {}).get("aktif", 1)))
        lay.addWidget(self.aktif)
        lay.addWidget(QLabel("Bir sınıfta bu derslerden ikisi aynı güne konmaz:"))
        self.dersler = _isaretli_liste()
        secili = {int(x) for x in str((kayit or {}).get("dersler") or "").split(",") if x.strip().isdigit()}
        for r in db.q("SELECT id, ad FROM dersler ORDER BY ad"):
            _isaretle(self.dersler, r["ad"], r["id"], r["id"] in secili)
        lay.addWidget(self.dersler, 1)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._tamam)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _tamam(self):
        if len(_isaretliler(self.dersler)) < 2:
            ortak.hata(self, "En az iki ders seçin.")
            return
        self.accept()

    def deger(self) -> dict:
        return {"ad": self.ad.text().strip() or "Ders grubu", "aktif": int(self.aktif.isChecked()),
                "dersler": ",".join(str(i) for i in _isaretliler(self.dersler))}


class KisitlarSekmesi(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lay.addWidget(_aciklama(
            "Otomatik yerleştirmenin uyacağı ek kurallar. Sınıfa ders konmayacak saatler (ör. her günün 1. saati, "
            "cuma öğleden sonra) 'Tanımlar > Sınıflar / Şubeler' formundaki 'Ders Konmayacak Saatler' alanından "
            "işaretlenir. Kurallara uyularak tüm dersler yerleşemezse kural gerektiği kadar gevşetilir ve "
            "'Kural Denetimi' uymayan yerleri listeler."))
        ust = ortak.AkisDuzeni()
        self.ogle = QSpinBox()
        self.ogle.setRange(0, 12)
        self.ogle.setSpecialValueText("Yok")
        self.ogle.setToolTip("Bu saatten sonra öğle arası verilir; blok dersler öğle arasında bölünmez.")
        ust.addWidget(ortak.etiketli("Öğle arası şu saatten sonra:", self.ogle))
        self.ayni_gun = QCheckBox("Bir öğretmenin aynı sınıftaki farklı dersleri aynı güne konmasın "
                                  "(rehberlik dersi hariç)")
        ust.addWidget(self.ayni_gun)
        b = QPushButton("Kaydet")
        b.clicked.connect(self.kaydet)
        ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)

        sp = QSplitter()
        sol = QWidget()
        sl = QVBoxLayout(sol)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(QLabel("<b>Aynı güne gelmeyecek ders grupları</b>"))
        dug = ortak.AkisDuzeni()
        for metin, fn in [("Yeni Grup", self.yeni), ("Düzenle", self.duzenle), ("Sil", self.sil)]:
            x = QPushButton(metin)
            x.clicked.connect(fn)
            dug.addWidget(x)
        dug.addStretch()
        sl.addLayout(dug)
        self.model = ortak.TabloModeli(["Grup", "Dersler", "Etkin"])
        self.view, self.proxy = ortak.tablo_gorunumu(self.model, False)
        self.view.doubleClicked.connect(lambda _: self.duzenle())
        sl.addWidget(self.view, 1)
        sp.addWidget(sol)
        sag = QWidget()
        rl = QVBoxLayout(sag)
        rl.setContentsMargins(0, 0, 0, 0)
        b = QPushButton("Kural Denetimi")
        b.clicked.connect(self.denetle)
        rl.addWidget(b)
        self.ihlal = QListWidget()
        rl.addWidget(self.ihlal, 1)
        sp.addWidget(sag)
        sp.setSizes([650, 450])
        lay.addWidget(sp, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self):
        self.ogle.setMaximum(max(1, self.db.ayar("gunluk_ders_saati") - 1))
        self.ogle.setValue(self.db.ayar("program_ogle_arasi") or 0)
        self.ayni_gun.setChecked(bool(self.db.ayar("program_ogretmen_ayni_gun")))
        adlar = {r["id"]: r["ad"] for r in self.db.q("SELECT id, ad FROM dersler")}
        rows = self.db.q("SELECT * FROM program_ders_gruplari ORDER BY ad")
        satirlar = []
        for r in rows:
            ids = [int(x) for x in str(r["dersler"] or "").split(",") if x.strip().isdigit()]
            satirlar.append([r["ad"], ", ".join(adlar[i] for i in ids if i in adlar), "Evet" if r["aktif"] else ""])
        self.model.ayarla(satirlar, [r["id"] for r in rows])
        ortak.sutunlari_sigdir(self.view, 380)

    def kaydet(self):
        self.db.ayar_yaz("program_ogle_arasi", self.ogle.value())
        self.db.ayar_yaz("program_ogretmen_ayni_gun", int(self.ayni_gun.isChecked()))
        ortak.bilgi(self, "Kurallar kaydedildi. 'Ders Dağılımı ve Atölye Yerleşimi' sayfasında 'Otomatik Yerleştir' "
                          "ile program yeniden oluşturulduğunda uygulanır.")

    def _secili(self) -> int | None:
        r = ortak.secili_satirlar(self.view, self.proxy)
        return self.model.kimlik(r[0]) if r else None

    def yeni(self):
        dlg = DersGrubuPenceresi(self.db, None, self)
        if dlg.exec():
            self.db.insert("program_ders_gruplari", dlg.deger())
            self.yenile()

    def duzenle(self):
        kid = self._secili()
        if kid is None:
            return
        dlg = DersGrubuPenceresi(self.db, dict(self.db.q1("SELECT * FROM program_ders_gruplari WHERE id = ?",
                                                          (kid,))), self)
        if dlg.exec():
            self.db.update("program_ders_gruplari", kid, dlg.deger())
            self.yenile()

    def sil(self):
        kid = self._secili()
        if kid is not None and ortak.onay(self, "Seçili ders grubu silinsin mi?"):
            self.db.delete("program_ders_gruplari", kid)
            self.yenile()

    def denetle(self):
        self.ihlal.clear()
        out = program.kural_ihlalleri(self.db)
        self.ihlal.addItems(out or ["Program kurallara uyuyor."])


class TopluCakmaSekmesi(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lay.addWidget(_aciklama(
            "Bir dersi (ör. Rehberlik ve Yönlendirme) seçilen sınıfların aynı gün ve saatine kilitli olarak yazar. "
            "O saatteki kilitsiz dersler kaldırılır; 'Otomatik Yerleştir' bunları yeniden yerleştirir. Saatte kilitli "
            "ders olan sınıflar atlanır."))
        ust = ortak.AkisDuzeni()
        self.ders = QComboBox()
        self.ders.setMinimumWidth(240)
        self.ders.currentIndexChanged.connect(lambda _: self._siniflar())
        ust.addWidget(ortak.etiketli("Ders:", self.ders))
        self.gun = QComboBox()
        self.gun.addItems(GUNLER[:5])
        ust.addWidget(ortak.etiketli("Gün:", self.gun))
        self.saat = QSpinBox()
        self.saat.setRange(1, 12)
        self.saat.setSuffix(". saat")
        ust.addWidget(ortak.etiketli("Saat:", self.saat))
        for metin, fn in [("Tümünü Seç", lambda: _tumunu(self.liste, True)),
                          ("Hiçbirini Seçme", lambda: _tumunu(self.liste, False)), ("Çak", self.cak)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        self.liste = _isaretli_liste()
        lay.addWidget(self.liste, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self):
        secili = self.ders.currentData()
        self.ders.blockSignals(True)
        self.ders.clear()
        rehber = program.rehberlik_dersleri(self.db)
        rows = self.db.q("""SELECT d.id, d.ad, COUNT(da.id) n FROM dersler d JOIN ders_atamalari da ON da.ders_id = d.id
                            GROUP BY d.id ORDER BY d.ad""")
        for r in rows:
            self.ders.addItem(f"{r['ad']} ({r['n']} sınıf)", r["id"])
        i = self.ders.findData(secili)
        if i < 0:
            i = next((k for k, r in enumerate(rows) if r["id"] in rehber), 0)
        self.ders.setCurrentIndex(i)
        self.ders.blockSignals(False)
        self.saat.setMaximum(self.db.ayar("gunluk_ders_saati"))
        self._siniflar()

    def _siniflar(self):
        self.liste.clear()
        ders = self.ders.currentData()
        if ders is None:
            return
        for r in self.db.q("""SELECT s.id, s.ad, o.ad || ' ' || o.soyad AS ogr FROM ders_atamalari da
                              JOIN siniflar s ON s.id = da.sinif_id LEFT JOIN ogretmenler o ON o.id = da.ogretmen_id
                              WHERE da.ders_id = ? ORDER BY s.seviye, s.ad""", (ders,)):
            _isaretle(self.liste, f"{r['ad']}  —  {r['ogr'] or 'öğretmen atanmamış'}", r["id"], True)

    def cak(self):
        ders, siniflar = self.ders.currentData(), _isaretliler(self.liste)
        if ders is None or not siniflar:
            ortak.bilgi(self, "Ders ve en az bir sınıf seçin.")
            return
        s = pa.toplu_cak(self.db, ders, self.gun.currentIndex() + 1, self.saat.value(), siniflar)
        ortak.bilgi(self, s.metin("sınıfa ders çakıldı"))


class SurumlerSekmesi(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lay.addWidget(_aciklama(
            "Programın o anki hâlini (kilitli hücreler dahil) adıyla saklayın; denemelerden sonra istediğiniz sürüme "
            "dönün. Yüklemeden önce mevcut program otomatik olarak ayrı bir sürüm olarak saklanır."))
        ust = ortak.AkisDuzeni()
        for metin, fn in [("Şimdiki Programı Kaydet", self.kaydet), ("Seçili Sürümü Yükle", self.yukle),
                          ("Sil", self.sil)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        self.model = ortak.TabloModeli(["Sürüm", "Tarih", "Hücre", "Açıklama"])
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        self.view.doubleClicked.connect(lambda _: self.yukle())
        lay.addWidget(self.view, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self):
        s = pa.surumler(self.db)
        self.model.ayarla([[x["ad"], x["tarih"], x["hucre"], x["aciklama"]] for x in s], [x["id"] for x in s])
        ortak.sutunlari_sigdir(self.view)

    def _secili(self) -> int | None:
        r = ortak.secili_satirlar(self.view, self.proxy)
        return self.model.kimlik(r[0]) if r else None

    def kaydet(self):
        if not self.db.q1("SELECT 1 FROM program_hucreleri LIMIT 1"):
            ortak.bilgi(self, "Programda kayıtlı ders yok.")
            return
        ad, ok = QInputDialog.getText(self, "Sürüm Kaydet", "Sürüm adı:")
        if not ok:
            return
        aciklama, _ = QInputDialog.getText(self, "Sürüm Kaydet", "Açıklama (isteğe bağlı):")
        pa.surum_kaydet(self.db, ad, aciklama)
        self.yenile()

    def yukle(self):
        sid = self._secili()
        if sid is None or not ortak.onay(self, "Mevcut program silinip seçili sürüm yüklensin mi? (Mevcut program "
                                               "önce otomatik sürüm olarak saklanır.)"):
            return
        s = pa.surum_yukle(self.db, sid)
        self.yenile()
        ortak.bilgi(self, s.metin("ders saati yüklendi"))

    def sil(self):
        sid = self._secili()
        if sid is not None and ortak.onay(self, "Seçili sürüm silinsin mi?"):
            pa.surum_sil(self.db, sid)
            self.yenile()


class SinifOgretmenligiSekmesi(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lay.addWidget(_aciklama(
            "Sınıf rehber öğretmenleri ders dağılımından atanır: sınıfta rehberlik dersine giren, yoksa en çok saati "
            "olan ve başka sınıfın rehberi olmayan öğretmen seçilir. Tek tek değiştirmek için 'Sınıflar / Şubeler' "
            "formunu kullanın."))
        ust = ortak.AkisDuzeni()
        for metin, fn in [("Boş Olanlara Ata", lambda: self.ata(False)),
                          ("Tümünü Yeniden Ata", lambda: self.ata(True)), ("Excel'e Aktar", self.excel)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        self.model = ortak.TabloModeli(["Sınıf", "Rehber Öğretmen", "Mevcut", "Sınıfa Giren Öğretmen"])
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        lay.addWidget(self.view, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def _satirlar(self) -> list[list]:
        return [[r["ad"], r["rehber"] or "", r["mevcut"], r["giren"]] for r in self.db.q(
            """SELECT s.ad, o.ad || ' ' || o.soyad AS rehber,
                      (SELECT COUNT(*) FROM ogrenciler g WHERE g.sinif_id = s.id AND g.aktif = 1) AS mevcut,
                      (SELECT COUNT(DISTINCT dog.ogretmen_id) FROM ders_atamalari da
                       JOIN ders_ogretmenleri dog ON dog.atama_id = da.id WHERE da.sinif_id = s.id) AS giren
               FROM siniflar s LEFT JOIN ogretmenler o ON o.id = s.rehber_ogretmen_id ORDER BY s.seviye, s.ad""")]

    def yenile(self):
        rows = self._satirlar()
        self.model.ayarla(rows, None, {i: ortak.RENK_UYARI for i, r in enumerate(rows) if not r[1]})
        ortak.sutunlari_sigdir(self.view)

    def ata(self, tumu: bool):
        if tumu and not ortak.onay(self, "Tüm sınıfların rehber öğretmeni yeniden belirlensin mi?"):
            return
        out = pa.sinif_ogretmeni_ata(self.db, tumu)
        self.yenile()
        ortak.bilgi(self, "\n".join([f"{len(out)} sınıfa rehber öğretmen atandı."]
                                    + [f"{s}: {o}" for s, o in out[:40]]))

    def excel(self):
        yol = ortak.kaydet_yolu(self, "Sınıf Rehber Öğretmenleri.xlsx")
        if yol:
            ortak.kaydedildi(self, excel_io.tablo_yaz(yol, self.model.basliklar, self._satirlar(),
                                                      "Sınıf Rehber Öğretmenleri"))


class DersDevriSekmesi(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lay.addWidget(_aciklama(
            "Ayrılan (tayin, emeklilik, görevlendirme) öğretmenin derslerini tek seferde devreder. Devralacak öğretmen "
            "seçilmezse dersler aynı branştaki öğretmenlere, programdaki saatlerinde boş olan ve en az yüklü olana "
            "paylaştırılır. Programdaki ders saatleri yerinde kalır."))
        ust = ortak.AkisDuzeni()
        self.kaynak = QComboBox()
        self.kaynak.setMinimumWidth(240)
        self.kaynak.currentIndexChanged.connect(lambda _: self._dersler())
        ust.addWidget(ortak.etiketli("Ayrılan öğretmen:", self.kaynak))
        self.hedef = QComboBox()
        self.hedef.setMinimumWidth(240)
        ust.addWidget(ortak.etiketli("Devralacak:", self.hedef))
        self.koord = QCheckBox("Koordinatörlük görevlerini de devret")
        ust.addWidget(self.koord)
        self.pasif = QCheckBox("Ayrılan öğretmeni pasif yap")
        self.pasif.setChecked(True)
        ust.addWidget(self.pasif)
        b = QPushButton("Devret")
        b.clicked.connect(self.devret)
        ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        sp = QSplitter()
        self.dersler = QListWidget()
        sp.addWidget(self.dersler)
        self.adaylar = QListWidget()
        sp.addWidget(self.adaylar)
        lay.addWidget(sp, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self):
        _ogretmen_doldur(self.kaynak, self.db)
        _ogretmen_doldur(self.hedef, self.db, "(Aynı branştakilere paylaştır)")
        self._dersler()

    def _dersler(self):
        self.dersler.clear()
        self.adaylar.clear()
        t = self.kaynak.currentData()
        if t is None:
            return
        rows = self.db.q("""SELECT s.ad AS sinif, d.ad AS ders, da.haftalik_saat FROM ders_atamalari da
                            JOIN siniflar s ON s.id = da.sinif_id JOIN dersler d ON d.id = da.ders_id
                            WHERE da.ogretmen_id = ? OR da.ogretmen2_id = ? ORDER BY s.ad, d.ad""", (t, t))
        self.dersler.addItem(f"Dersleri ({sum(r['haftalik_saat'] or 0 for r in rows)} saat):")
        self.dersler.addItems([f"  {r['sinif']} - {r['ders']} ({r['haftalik_saat']} saat)" for r in rows])
        aday = pa.devir_adaylari(self.db, t)
        self.adaylar.addItem("Aynı branştaki öğretmenler (haftalık yük):" if aday
                             else "Aynı branşta öğretmen yok; devralacak öğretmeni seçin.")
        self.adaylar.addItems([f"  {a['ad']}: {a['yuk']} saat" for a in aday])

    def devret(self):
        k, h = self.kaynak.currentData(), self.hedef.currentData()
        if k is None:
            return
        if h == k:
            ortak.hata(self, "Ayrılan ve devralan öğretmen aynı olamaz.")
            return
        if self.koord.isChecked() and h is None:
            ortak.hata(self, "Koordinatörlük görevlerini devretmek için devralacak öğretmeni seçin.")
            return
        if not ortak.onay(self, f"{self.kaynak.currentText()} öğretmenin dersleri devredilsin mi?"):
            return
        try:
            s = pa.ders_devret(self.db, k, h, self.koord.isChecked(), self.pasif.isChecked())
        except ValueError as e:
            ortak.hata(self, str(e))
            return
        self.yenile()
        ortak.bilgi(self, s.metin("ders devredildi"))


class YukAnaliziSekmesi(QWidget):
    OGR = ["Öğretmen", "Branş", "Alan", "Ders Saati", "Koordinatörlük", "Toplam", "Aylık Karşılık", "Ek Ders",
           "Karşılık Eksiği"]
    BRANS = ["Branş", "Öğretmen", "Toplam Ders", "Ortalama", "En Az", "En Çok", "Toplam Ek Ders",
             "Karşılığı Dolmayan"]
    ATANMAMIS = ["Sınıf", "Ders", "Haftalık Saat", "Durum"]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lay.addWidget(_aciklama(
            "Ders dağılımına göre öğretmen ve branş bazında haftalık yük (birleştirilmiş dersler bir kez sayılır). "
            "Karşılığı dolmayan öğretmenler sarı, öğretmeni atanmamış ya da programa tam yerleşmemiş dersler alttaki "
            "tabloda listelenir."))
        ust = ortak.AkisDuzeni()
        for metin, fn in [("Yenile", self.yenile), ("Excel'e Aktar", self.excel)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        sekme = QTabWidget()
        self.m_ogr = ortak.TabloModeli(self.OGR)
        self.m_brans = ortak.TabloModeli(self.BRANS)
        self.m_ata = ortak.TabloModeli(self.ATANMAMIS)
        self.gorunumler = []
        for ad, m in [("Öğretmenler", self.m_ogr), ("Branşlar", self.m_brans), ("Eksik Kalan Dersler", self.m_ata)]:
            v, _ = ortak.tablo_gorunumu(m)
            self.gorunumler.append(v)
            sekme.addTab(v, ad)
        lay.addWidget(sekme, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def _veriler(self):
        yuk = pa.ogretmen_yuk_tablosu(self.db)
        ogr = [[y.ad, y.brans, y.alan, y.ders_saati, y.koordinatorluk, y.toplam, y.aylik_karsilik, y.ek_ders,
                y.eksik] for y in yuk]
        return ogr, pa.brans_ozeti(yuk), pa.atanmamis_dersler(self.db)

    def yenile(self):
        ogr, brans, ata = self._veriler()
        self.m_ogr.ayarla(ogr, None, {i: ortak.RENK_UYARI for i, r in enumerate(ogr) if r[-1]})
        self.m_brans.ayarla(brans)
        self.m_ata.ayarla(ata)
        for v in self.gorunumler:
            ortak.sutunlari_sigdir(v)

    def excel(self):
        yol = ortak.kaydet_yolu(self, "Öğretmen Ders Yükü Analizi.xlsx")
        if not yol:
            return
        ogr, brans, ata = self._veriler()
        x = excel_io.ExcelYazici()
        x.sayfa("Öğretmenler", self.OGR, ogr, "Öğretmen Haftalık Ders Yükü")
        x.sayfa("Branşlar", self.BRANS, brans, "Branş Özeti")
        x.sayfa("Eksik Kalan Dersler", self.ATANMAMIS, ata, "Öğretmeni Atanmamış / Programa Yerleşmemiş Dersler")
        ortak.kaydedildi(self, x.kaydet(yol))


class ProgramAraclariSayfasi(QTabWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        for ad, cls in [("Kısıtlar", KisitlarSekmesi), ("Toplu Çakma", TopluCakmaSekmesi),
                        ("Program Sürümleri", SurumlerSekmesi), ("Sınıf Öğretmenliği", SinifOgretmenligiSekmesi),
                        ("Ders Devri", DersDevriSekmesi), ("Yük Analizi", YukAnaliziSekmesi)]:
            self.addTab(cls(db), ad)
