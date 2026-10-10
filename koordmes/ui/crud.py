"""Tanım tabloları için genel listeleme/ekleme/düzenleme/silme ekranı."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

from PySide6.QtCore import QDate, QItemSelectionModel, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QCompleter, QDateEdit, QDialog, QDialogButtonBox,
                               QDoubleSpinBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QVBoxLayout,
                               QWidget)

from ..mevzuat import GUNLER
from ..services import excel_io
from ..services.program import musaitlik_coz
from ..services.utils import gunler_listesi, tarih, tc_gecerli, tr
from . import ortak


@dataclass
class Alan:
    ad: str
    etiket: str
    tur: str = "text"  # text|int|float|date|bool|choice|fk|multiline|days|slots|tc
    zorunlu: bool = False
    secenekler: list[str] | None = None
    fk_sql: str | None = None  # "SELECT id, etiket FROM ..."
    varsayilan: Any = None
    listede: bool = True
    ipucu: str = ""


@dataclass
class Varlik:
    tablo: str
    baslik: str
    alanlar: list[Alan]
    siralama: str = "id"
    filtre_alani: str | None = None
    aciklama: str = ""
    eylemler: list[tuple[str, Callable[["CrudSayfasi", list[int]], None]]] = field(default_factory=list)
    kayit_sonrasi: Callable[[Any, int, dict], None] | None = None
    # (sayfa, db, kayıt id, kaydedilen değerler, düzenlemeden önceki kayıt veya None) - form kapandıktan sonra
    form_sonrasi: Callable[[QWidget, Any, int, dict, dict | None], None] | None = None


class GunSecici(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.kutular = []
        for g in GUNLER:
            cb = QCheckBox(g[:3])
            self.kutular.append(cb)
            lay.addWidget(cb)
        lay.addStretch()

    def deger(self) -> str:
        return ",".join(str(i + 1) for i, cb in enumerate(self.kutular) if cb.isChecked())

    def ayarla(self, s: str | None) -> None:
        secili = set(gunler_listesi(s))
        for i, cb in enumerate(self.kutular):
            cb.setChecked(i + 1 in secili)


class MusaitlikDialog(QDialog):
    def __init__(self, metin: str, saat_sayisi: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Müsait olmayan saatler (işaretli = ders verilemez)")
        self.S = saat_sayisi
        lay = QVBoxLayout(self)
        grid = QGridLayout()
        kapali = musaitlik_coz(metin, saat_sayisi)
        self.kutular: dict[tuple[int, int], QCheckBox] = {}
        for g, ad in enumerate(GUNLER, 1):
            btn = QPushButton(ad)
            btn.clicked.connect(lambda _=False, gg=g: self._gun_degistir(gg))
            grid.addWidget(btn, 0, g)
        for h in range(1, saat_sayisi + 1):
            grid.addWidget(QLabel(f"{h}. saat"), h, 0)
            for g in range(1, 6):
                cb = QCheckBox()
                cb.setChecked((g, h) in kapali)
                self.kutular[(g, h)] = cb
                grid.addWidget(cb, h, g, alignment=Qt.AlignCenter)
        lay.addLayout(grid)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _gun_degistir(self, g: int) -> None:
        hepsi = all(self.kutular[(g, h)].isChecked() for h in range(1, self.S + 1))
        for h in range(1, self.S + 1):
            self.kutular[(g, h)].setChecked(not hepsi)

    def metin(self) -> str:
        parcalar = []
        for g in range(1, 6):
            saatler = [h for h in range(1, self.S + 1) if self.kutular[(g, h)].isChecked()]
            if len(saatler) == self.S:
                parcalar.append(f"{g}-*")
            else:
                parcalar += [f"{g}-{h}" for h in saatler]
        return ",".join(parcalar)


class MusaitlikAlani(QWidget):
    def __init__(self, saat_sayisi: int, parent=None):
        super().__init__(parent)
        self.S = saat_sayisi
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.ed = QLineEdit()
        self.ed.setPlaceholderText("ör. 1-* (Pazartesi tüm gün), 3-5, 3-6")
        btn = QPushButton("Tablodan seç...")
        btn.clicked.connect(self._ac)
        lay.addWidget(self.ed)
        lay.addWidget(btn)

    def _ac(self):
        d = MusaitlikDialog(self.ed.text(), self.S, self)
        if d.exec():
            self.ed.setText(d.metin())


class TarihAlani(QWidget):
    def __init__(self, zorunlu: bool, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.cb = None if zorunlu else QCheckBox()
        self.de = QDateEdit()
        self.de.setCalendarPopup(True)
        self.de.setDisplayFormat("dd.MM.yyyy")
        self.de.setDate(QDate.currentDate())
        if self.cb:
            self.cb.toggled.connect(self.de.setEnabled)
            self.cb.setChecked(False)
            self.de.setEnabled(False)
            lay.addWidget(self.cb)
        lay.addWidget(self.de)
        lay.addStretch()

    def deger(self) -> str | None:
        if self.cb and not self.cb.isChecked():
            return None
        d = self.de.date()
        return date(d.year(), d.month(), d.day()).isoformat()

    def ayarla(self, v) -> None:
        d = tarih(v)
        if d:
            self.de.setDate(QDate(d.year, d.month, d.day))
            if self.cb:
                self.cb.setChecked(True)
        elif self.cb:
            self.cb.setChecked(False)


def fk_combo(db, sql: str, zorunlu: bool) -> QComboBox:
    cb = QComboBox()
    cb.setEditable(True)
    cb.setInsertPolicy(QComboBox.NoInsert)
    if not zorunlu:
        cb.addItem("—", None)
    for r in db.q(sql):
        cb.addItem(str(r[1]), r[0])
    comp = cb.completer()
    comp.setFilterMode(Qt.MatchContains)
    comp.setCompletionMode(QCompleter.PopupCompletion)
    return cb


def combo_deger(cb: QComboBox):
    i = cb.findText(cb.currentText())
    return cb.itemData(i) if i >= 0 else None


class FormDialog(QDialog):
    def __init__(self, db, varlik: Varlik, kayit: dict | None = None, parent=None, sabit: dict | None = None):
        super().__init__(parent)
        self.db, self.varlik, self.kayit = db, varlik, kayit
        self.setWindowTitle(f"{varlik.baslik} - {'Düzenle' if kayit else 'Yeni Kayıt'}")
        self.setMinimumWidth(560)
        dis = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        ic = QWidget()
        form = QFormLayout(ic)
        scroll.setWidget(ic)
        dis.addWidget(scroll)
        self.widgetlar: dict[str, QWidget] = {}
        S = db.ayar("gunluk_ders_saati")
        for a in varlik.alanlar:
            w = self._widget(a, S)
            deger = (kayit or {}).get(a.ad, a.varsayilan) if kayit else (sabit or {}).get(a.ad, a.varsayilan)
            self._yaz(a, w, deger)
            self.widgetlar[a.ad] = w
            etiket = a.etiket + (" *" if a.zorunlu else "")
            if a.ipucu:
                w.setToolTip(a.ipucu)
            form.addRow(etiket, w)
        self._ilk_degerler = self.degerler() if kayit else None
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText("Kaydet")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(self._kaydet)
        bb.rejected.connect(self.reject)
        dis.addWidget(bb)
        self.resize(620, min(760, 120 + 38 * len(varlik.alanlar)))

    def _widget(self, a: Alan, S: int) -> QWidget:
        if a.tur == "int":
            w = QSpinBox()
            w.setRange(0, 10_000_000)
            return w
        if a.tur == "float":
            w = QDoubleSpinBox()
            w.setRange(0, 1e9)
            w.setDecimals(2)
            return w
        if a.tur == "date":
            return TarihAlani(a.zorunlu)
        if a.tur == "bool":
            return QCheckBox()
        if a.tur == "choice":
            w = QComboBox()
            w.setEditable(False)
            if not a.zorunlu:
                w.addItem("")
            w.addItems(a.secenekler or [])
            return w
        if a.tur == "fk":
            return fk_combo(self.db, a.fk_sql, a.zorunlu)
        if a.tur == "multiline":
            w = QPlainTextEdit()
            w.setFixedHeight(80)
            return w
        if a.tur == "days":
            return GunSecici()
        if a.tur == "slots":
            return MusaitlikAlani(S)
        w = QLineEdit()
        if a.tur == "tc":
            w.setMaxLength(11)
            w.setInputMask("")
        return w

    def _yaz(self, a: Alan, w, v) -> None:
        if a.tur == "int":
            w.setValue(int(v or 0))
        elif a.tur == "float":
            w.setValue(float(v or 0))
        elif a.tur == "date":
            w.ayarla(v)
        elif a.tur == "bool":
            w.setChecked(bool(v))
        elif a.tur == "choice":
            i = w.findText(str(v or ""))
            if i < 0 and v not in (None, ""):
                w.addItem(str(v))
                i = w.count() - 1
            w.setCurrentIndex(max(0, i))
        elif a.tur == "fk":
            i = w.findData(v)
            w.setCurrentIndex(i if i >= 0 else 0)
        elif a.tur == "multiline":
            w.setPlainText(str(v or ""))
        elif a.tur == "days":
            w.ayarla(v)
        elif a.tur == "slots":
            w.ed.setText(str(v or ""))
        else:
            w.setText("" if v is None else str(v))

    def _oku(self, a: Alan, w):
        if a.tur == "int":
            return w.value()
        if a.tur == "float":
            return w.value()
        if a.tur == "date":
            return w.deger()
        if a.tur == "bool":
            return 1 if w.isChecked() else 0
        if a.tur == "choice":
            return w.currentText()
        if a.tur == "fk":
            return combo_deger(w)
        if a.tur == "multiline":
            return w.toPlainText().strip()
        if a.tur == "days":
            return w.deger()
        if a.tur == "slots":
            return w.ed.text().strip()
        return w.text().strip()

    def degerler(self) -> dict:
        return {a.ad: self._oku(a, self.widgetlar[a.ad]) for a in self.varlik.alanlar}

    def _kaydet(self) -> None:
        d = self.degerler()
        eksik = [a.etiket for a in self.varlik.alanlar if a.zorunlu and d[a.ad] in (None, "")]
        if eksik:
            ortak.hata(self, "Zorunlu alanlar boş bırakılamaz:\n- " + "\n- ".join(eksik))
            return
        for a in self.varlik.alanlar:
            if a.tur == "tc" and d[a.ad] and not tc_gecerli(d[a.ad]):
                if not ortak.onay(self, f"{a.etiket} geçerli görünmüyor ({d[a.ad]}). Yine de kaydedilsin mi?"):
                    return
        try:
            if self.kayit:
                kid = self.kayit["id"]
                degisen = self._degisenler(d)
                if degisen is None:
                    return
                if degisen:
                    self.db.update(self.varlik.tablo, kid, degisen)
            else:
                kid = self.db.insert(self.varlik.tablo, d)
            if self.varlik.kayit_sonrasi:
                self.varlik.kayit_sonrasi(self.db, kid, d)
        except Exception as e:
            ortak.hata(self, f"Kayıt yapılamadı:\n{e}")
            return
        self.kayit_id, self.kaydedilen = kid, d
        self.accept()

    def _degisenler(self, d: dict) -> dict | None:
        """Yalnızca kullanıcının değiştirdiği alanları döndürür. Aynı kaydı başka bir bilgisayar bu arada
        değiştirdiyse: farklı alanlar birleştirilir, aynı alanlar için kullanıcıya sorulur (None: vazgeçti)."""
        guncel = self.db.q1(f"SELECT * FROM {self.varlik.tablo} WHERE id = ?", (self.kayit["id"],))
        if guncel is None:
            ortak.hata(self, "Bu kayıt siz düzenlerken başka bir kullanıcı tarafından silinmiş.")
            return None
        sutunlar = set(guncel.keys())
        degisen = {k: v for k, v in d.items() if v != self._ilk_degerler.get(k)}
        cakisan = [a.etiket for a in self.varlik.alanlar
                   if a.ad in degisen and a.ad in sutunlar and a.ad in self.kayit and guncel[a.ad] != self.kayit[a.ad]]
        if cakisan and not ortak.onay(
                self, "Bu kayıt siz düzenlerken başka bir kullanıcı tarafından da değiştirildi.\n\n"
                      "Her iki tarafın değiştirdiği alanlar: " + ", ".join(cakisan) +
                      "\n\nBu alanlara sizin girdiğiniz değerler yazılsın mı? (Diğer alanlardaki değişiklikler korunur.)",
                "Eşzamanlı değişiklik"):
            return None
        return degisen


class CrudSayfasi(QWidget):
    def __init__(self, db, varlik: Varlik, parent=None):
        super().__init__(parent)
        self.db, self.varlik = db, varlik
        self.ek_kosul: tuple[str, list] = ("", [])
        self.sabit: dict = {}
        lay = QVBoxLayout(self)
        if varlik.aciklama:
            lbl = QLabel(varlik.aciklama)
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color:#555")
            lay.addWidget(lbl)
        ust = QHBoxLayout()
        self.ara = QLineEdit()
        self.ara.setPlaceholderText("Ara...")
        self.ara.setClearButtonEnabled(True)
        ust.addWidget(self.ara, 2)
        self.filtre = None
        if varlik.filtre_alani:
            fa = next(a for a in varlik.alanlar if a.ad == varlik.filtre_alani)
            ust.addWidget(QLabel(fa.etiket + ":"))
            self.filtre = QComboBox()
            self.filtre.currentIndexChanged.connect(lambda _: self.yenile())
            ust.addWidget(self.filtre, 1)
        for metin, fn in [("Yeni", self.yeni), ("Düzenle", self.duzenle), ("Sil", self.sil),
                          ("Excel'e Aktar", self.excel)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        lay.addLayout(ust)
        if varlik.eylemler:
            alt = ortak.AkisDuzeni()
            for metin, fn in varlik.eylemler:
                b = QPushButton(metin)
                b.clicked.connect(lambda _=False, f=fn: f(self, self.secili_kimlikler()))
                alt.addWidget(b)
            alt.addStretch()
            lay.addLayout(alt)
        self.liste_alanlari = [a for a in varlik.alanlar if a.listede]
        self.model = ortak.TabloModeli([a.etiket for a in self.liste_alanlari])
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        self.view.doubleClicked.connect(lambda _: self.duzenle())
        self.ara.textChanged.connect(self.proxy.setFilterFixedString)
        lay.addWidget(self.view, 1)
        self.durum = QLabel()
        lay.addWidget(self.durum)
        self._ilk = True

    def _filtre_doldur(self) -> None:
        if not self.filtre:
            return
        fa = next(a for a in self.varlik.alanlar if a.ad == self.varlik.filtre_alani)
        secili = self.filtre.currentData()
        self.filtre.blockSignals(True)
        self.filtre.clear()
        self.filtre.addItem("(Tümü)", None)
        for r in self.db.q(fa.fk_sql):
            self.filtre.addItem(str(r[1]), r[0])
        i = self.filtre.findData(secili)
        self.filtre.setCurrentIndex(max(0, i))
        self.filtre.blockSignals(False)

    def _gosterim(self, a: Alan, v, fk_map: dict) -> Any:
        if a.tur == "fk":
            return fk_map.get(a.ad, {}).get(v, "")
        if a.tur == "bool":
            return "Evet" if v else ""
        if a.tur == "date":
            return tr(v)
        if a.tur == "days":
            return ", ".join(GUNLER[g - 1][:3] for g in gunler_listesi(v) if g <= 5)
        if a.tur == "float" and v is not None:
            return float(v)
        return v

    def yenile(self) -> None:
        if self._ilk:
            self._filtre_doldur()
        fk_map = {a.ad: {r[0]: str(r[1]) for r in self.db.q(a.fk_sql)} for a in self.varlik.alanlar if a.tur == "fk"}
        kosul, params = self.ek_kosul
        where = []
        if kosul:
            where.append(kosul)
        if self.filtre and self.filtre.currentData() is not None:
            where.append(f"{self.varlik.filtre_alani} = ?")
            params = [*params, self.filtre.currentData()]
        sql = f"SELECT * FROM {self.varlik.tablo}" + (" WHERE " + " AND ".join(where) if where else "") + \
              f" ORDER BY {self.varlik.siralama}"
        rows = self.db.q(sql, params)
        self.kayitlar = {r["id"]: dict(r) for r in rows}
        self.model.ayarla([[self._gosterim(a, r[a.ad], fk_map) for a in self.liste_alanlari] for r in rows],
                          [r["id"] for r in rows])
        if self._ilk:
            ortak.sutunlari_sigdir(self.view)
            self._ilk = False
        self.durum.setText(f"{len(rows)} kayıt")

    def showEvent(self, e):
        super().showEvent(e)
        self._filtre_doldur()
        self.yenile()

    def canli_yenile(self) -> None:
        """Başka bilgisayardaki değişiklikten sonra: seçimi ve kaydırma konumunu koruyarak yeniler."""
        secili = set(self.secili_kimlikler())
        kaydirma = self.view.verticalScrollBar().value()
        self._filtre_doldur()
        self.yenile()
        if secili:
            sm = self.view.selectionModel()
            for r in range(self.proxy.rowCount()):
                if self.model.kimlik(self.proxy.mapToSource(self.proxy.index(r, 0)).row()) in secili:
                    sm.select(self.proxy.index(r, 0), QItemSelectionModel.Select | QItemSelectionModel.Rows)
        self.view.verticalScrollBar().setValue(kaydirma)

    def secili_kimlikler(self) -> list[int]:
        return [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)]

    def yeni(self) -> None:
        sabit = dict(self.sabit)
        if self.filtre and self.filtre.currentData() is not None:
            sabit[self.varlik.filtre_alani] = self.filtre.currentData()
        self._formu_ac(FormDialog(self.db, self.varlik, None, self, sabit), None)

    def duzenle(self) -> None:
        ids = self.secili_kimlikler()
        if not ids:
            return
        eski = self.kayitlar[ids[0]]
        self._formu_ac(FormDialog(self.db, self.varlik, eski, self), eski)

    def _formu_ac(self, dlg: FormDialog, eski: dict | None) -> None:
        if not dlg.exec():
            return
        self.yenile()
        if self.varlik.form_sonrasi:
            self.varlik.form_sonrasi(self, self.db, dlg.kayit_id, dlg.kaydedilen, eski)
            self.yenile()

    def sil(self) -> None:
        ids = self.secili_kimlikler()
        if not ids:
            return
        if not ortak.onay(self, f"{len(ids)} kayıt silinecek. Emin misiniz?\n(Bağlı kayıtlar da silinebilir.)"):
            return
        try:
            for i in ids:
                self.db.delete(self.varlik.tablo, i)
        except Exception as e:
            QMessageBox.critical(self, "Silinemedi", str(e))
        self.yenile()

    def excel(self) -> None:
        yol = ortak.kaydet_yolu(self, f"{self.varlik.baslik}.xlsx")
        if not yol:
            return
        satirlar = []
        for r in range(self.proxy.rowCount()):
            satirlar.append([self.proxy.index(r, c).data(Qt.UserRole) for c in range(self.proxy.columnCount())])
        excel_io.tablo_yaz(yol, self.model.basliklar, satirlar, baslik=self.varlik.baslik)
        ortak.kaydedildi(self, yol)
