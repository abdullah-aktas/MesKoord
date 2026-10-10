"""Çerçeve öğretim programları: haftalık ders çizelgelerini görüntüleme ve sınıflara zorunlu dersleri açma."""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
                               QHeaderView, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from ..services import cerceve, excel_io
from ..services.cerceve import CopProgram
from . import ortak

KATEGORI_ETIKETI = {"Ortak": "Ortak ders", "Meslek": "Meslek dersi", "Rehberlik": "Rehberlik",
                    cerceve.ISLETMEDE: "İşletmede"}
BASLIKLAR = ["Ders", "Kategori", "Haftalık Saat", "Açıklama"]
RENK_OZET = QColor("#eef1f5")
RENK_ISLETME = QColor("#e8f4ea")
RENK_FARK = QColor("#fff3cd")


def _cumle(s: str) -> str:
    return s[:1].upper() + s[1:] + "." if s else ""


def _not(d: cerceve.CopDers) -> str:
    parca = []
    if d.basari_zorunlu:
        parca.append("(*) yılsonu başarı puanıyla geçilemez")
    if d.parantezli_saat:
        parca.append(f"parantezli {d.parantezli_saat} saat zorunlu ders saatine girmez")
    if not d.okulda:
        parca.append("sınıfın işletme günlerinde yapılır; ders dağılımına açılmaz")
    return "; ".join(parca)


def _ozet_satirlari(p: CopProgram) -> list[tuple[str, str]]:
    out = [("Seçmeli meslek dersleri", p.secmeli_meslek), ("Seçmeli dersler", p.secmeli),
           ("Akademik destek", p.akademik_destek)]
    return [(ad, str(s)) for ad, s in out if s] + [("Haftalık toplam", str(p.toplam or ""))]


class CizelgeTablosu(QTableWidget):
    """Bir haftalık ders çizelgesi; secilebilir ise okulda okutulan zorunlu derslerin yanında onay kutusu olur."""

    def __init__(self, secilebilir: bool = False, parent=None):
        super().__init__(parent)
        self.secilebilir = secilebilir
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.dersler: dict[int, cerceve.CopDers] = {}

    def doldur(self, p: CopProgram | None, mevcut: dict[str, int] | None = None) -> None:
        self.clear()
        self.dersler = {}
        self.setColumnCount(len(BASLIKLAR))
        self.setHorizontalHeaderLabels(BASLIKLAR)
        if p is None:
            self.setRowCount(0)
            return
        satirlar = [d for d in p.dersler if d.saat or d.parantezli_saat]
        ozet = _ozet_satirlari(p)
        self.setRowCount(len(satirlar) + len(ozet))
        for i, d in enumerate(satirlar):
            saat = str(d.saat) + (f" ({d.parantezli_saat})" if d.parantezli_saat else "")
            aciklama = _not(d)
            renk = None if d.okulda else RENK_ISLETME
            if mevcut is not None and d.okulda and d.saat:
                var = mevcut.get(cerceve.anahtar(d.ad))
                if var is None:
                    durum = "ders dağılımına açılacak"
                elif var != d.saat:
                    durum, renk = f"dağılımda {var} saat; {d.saat} saate düzeltilecek", RENK_FARK
                else:
                    durum = "dağılımda var"
                aciklama = "; ".join(x for x in (durum, aciklama) if x)
            hucreler = [QTableWidgetItem(d.ad), QTableWidgetItem(KATEGORI_ETIKETI.get(d.kategori, d.kategori)),
                        QTableWidgetItem(saat), QTableWidgetItem(aciklama)]
            hucreler[2].setTextAlignment(Qt.AlignCenter)
            if self.secilebilir and d.okulda and d.saat:
                hucreler[0].setFlags(hucreler[0].flags() | Qt.ItemIsUserCheckable)
                hucreler[0].setCheckState(Qt.Checked)
                self.dersler[i] = d
            for c, it in enumerate(hucreler):
                if renk is not None:
                    it.setBackground(QBrush(renk))
                self.setItem(i, c, it)
        for j, (ad, deger) in enumerate(ozet, len(satirlar)):
            for c, metin in enumerate([ad, "", deger, ""]):
                it = QTableWidgetItem(metin)
                it.setBackground(QBrush(RENK_OZET))
                if c == 2:
                    it.setTextAlignment(Qt.AlignCenter)
                self.setItem(j, c, it)
        self.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

    def secili_dersler(self) -> set[str]:
        return {d.ad for i, d in self.dersler.items() if self.item(i, 0).checkState() == Qt.Checked}


def kaynagi_ac(p: CopProgram | None) -> None:
    QDesktopServices.openUrl(QUrl(p.url if p and p.kaynak else cerceve.KAYNAK_SAYFA))


class ZorunluDersDialog(QDialog):
    """Sınıfın seviye, alan ve dalına göre çerçeve programdaki zorunlu dersleri önizleyip ders dağılımına açar."""

    def __init__(self, db, sinif_id: int, eslesme: cerceve.Eslesme, parent=None):
        super().__init__(parent)
        self.db, self.sinif_id = db, sinif_id
        self.sinif = cerceve.sinif_bilgisi(db, sinif_id)
        self.secenekler = eslesme.secenekler or ([eslesme.program] if eslesme.program else [])
        self.sonuc: cerceve.UygulamaSonucu | None = None
        self.setWindowTitle(f"{self.sinif['ad']} - Çerçeve Öğretim Programındaki Zorunlu Dersler")
        self.resize(900, 620)
        lay = QVBoxLayout(self)
        self.baslik = QLabel()
        self.baslik.setWordWrap(True)
        lay.addWidget(self.baslik)
        if eslesme.sorun:
            uy = QLabel(eslesme.sorun)
            uy.setWordWrap(True)
            uy.setStyleSheet("color:#8a4b00")
            lay.addWidget(uy)
        ust = QHBoxLayout()
        ust.addWidget(QLabel("Haftalık ders çizelgesi:"))
        self.secim = QComboBox()
        for p in self.secenekler:
            self.secim.addItem(f"{p.dal} - {p.program_adi} ({p.yil})", p)
        if eslesme.program in self.secenekler:
            self.secim.setCurrentIndex(self.secenekler.index(eslesme.program))
        ust.addWidget(self.secim, 1)
        pdf = QPushButton("Kaynak PDF'i Aç")
        pdf.clicked.connect(lambda: kaynagi_ac(self.program))
        ust.addWidget(pdf)
        lay.addLayout(ust)
        self.tablo = CizelgeTablosu(secilebilir=True)
        lay.addWidget(self.tablo, 1)
        self.ozet = QLabel()
        self.ozet.setWordWrap(True)
        lay.addWidget(self.ozet)
        self.duzelt = QCheckBox("Ders dağılımındaki haftalık saati çizelgeden farklı olan dersleri düzelt")
        self.duzelt.setChecked(True)
        lay.addWidget(self.duzelt)
        self.dal_kaydet = QCheckBox()
        lay.addWidget(self.dal_kaydet)
        bb = QDialogButtonBox()
        ac = bb.addButton("Zorunlu Dersleri Aç", QDialogButtonBox.AcceptRole)
        ac.setDefault(True)
        bb.addButton("Vazgeç", QDialogButtonBox.RejectRole)
        bb.accepted.connect(self._uygula)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.secim.currentIndexChanged.connect(lambda _: self._goster())
        self._goster()

    @property
    def program(self) -> CopProgram | None:
        return self.secim.currentData()

    def _goster(self) -> None:
        p = self.program
        self.baslik.setText(f"<b>{self.sinif['ad']}</b> &mdash; {p.etiket if p else ''}<br>"
                            "İşaretli dersler sınıfın ders dağılımına açılır; öğretmen ve atölye atamaları sonradan "
                            "yapılır. Seçmeli dersler ve akademik destek saatleri okulca belirlenir.")
        self.tablo.doldur(p, cerceve.sinif_atamalari(self.db, self.sinif_id))
        uyarilar = cerceve.gun_uyarilari(self.db, self.sinif, p) if p else []
        self.ozet.setText((_cumle(p.ozet()) if p else "") +
                          "".join(f"<br><span style='color:#8a4b00'>{u}</span>" for u in uyarilar))
        sinif_dali = cerceve.anahtar(self.sinif["dal"])
        dal_farkli = bool(p) and len({x.dal for x in self.secenekler}) > 1 and cerceve.anahtar(p.dal) != sinif_dali
        self.dal_kaydet.setVisible(dal_farkli)
        self.dal_kaydet.setChecked(dal_farkli)
        if p:
            self.dal_kaydet.setText(f"Sınıfın dalını '{p.dal}' olarak kaydet")

    def _uygula(self) -> None:
        p = self.program
        if p is None:
            return
        try:
            if self.dal_kaydet.isVisibleTo(self) and self.dal_kaydet.isChecked():
                cerceve.sinif_dalini_ayarla(self.db, self.sinif_id, p.dal)
            self.sonuc = cerceve.uygula(self.db, self.sinif_id, p, self.tablo.secili_dersler(),
                                        self.duzelt.isChecked())
        except Exception as e:
            ortak.hata(self, f"Dersler açılamadı:\n{e}")
            return
        self.accept()


def sonuc_metni(s: cerceve.UygulamaSonucu) -> str:
    m = [s.mesaj()]
    if s.eklenen:
        m.append("Açılan dersler:\n- " + "\n- ".join(s.eklenen))
    if s.guncellenen:
        m.append("Saati düzeltilenler:\n- " + "\n- ".join(s.guncellenen))
    if s.yeni_tanim:
        m.append(f"{len(s.yeni_tanim)} ders Dersler tanımlarına eklendi (blok ve atölye gereksinimini "
                 "Tanımlar > Dersler ekranından kontrol edebilirsiniz).")
    m += s.uyarilar
    if s.eklenen:
        m.append("Öğretmen atamalarını Ders Dağılımı sekmesinden yapınız.")
    return "\n\n".join(m)


def zorunlu_dersleri_ac(parent, db, sinif_id: int, program: CopProgram | None = None,
                        sessiz_eslesmezse: bool = False) -> cerceve.UygulamaSonucu | None:
    """Sınıf için zorunlu ders diyaloğunu açar. program verilmezse sınıfın çizelgesi kendiliğinden bulunur."""
    if not cerceve.veri_var():
        if not sessiz_eslesmezse:
            ortak.hata(parent, f"Çerçeve öğretim programı verisi bulunamadı:\n{cerceve.VERI_DOSYASI}")
        return None
    eslesme = cerceve.Eslesme(program, secenekler=[program]) if program else cerceve.sinif_programi(db, sinif_id)
    if not eslesme.secenekler and eslesme.program is None:
        if not sessiz_eslesmezse:
            ortak.bilgi(parent, f"{eslesme.sorun}.\n\nSınıfın programını, alanını ve dalını kontrol ediniz veya "
                                "Ders Programı > Çerçeve Öğretim Programları sekmesinden çizelgeyi seçip sınıfa "
                                "uygulayınız.", "Çerçeve öğretim programı")
        return None
    dlg = ZorunluDersDialog(db, sinif_id, eslesme, parent)
    if dlg.exec() != QDialog.Accepted or dlg.sonuc is None:
        return None
    ortak.bilgi(parent, sonuc_metni(dlg.sonuc), "Zorunlu dersler")
    return dlg.sonuc


# ----------------------------------------------------------------- tanım ekranı kancaları

IZLENEN = ("seviye", "program", "alan_id", "dal_id")


def sinif_kaydedildi(sayfa, db, sinif_id: int, degerler: dict, eski: dict | None) -> None:
    """Yeni sınıf açılınca veya sınıfın seviye/program/alan/dalı değişince zorunlu dersleri önerir."""
    if not degerler.get("alan_id"):
        return
    if eski is not None and all(degerler.get(k) == eski.get(k) for k in IZLENEN):
        return
    zorunlu_dersleri_ac(sayfa, db, sinif_id, sessiz_eslesmezse=not cerceve.veri_var())


def siniflar_eylemi(sayfa, ids: list[int]) -> None:
    _secili_siniflara(sayfa, sayfa.db, ids)


def ders_dagilimi_eylemi(sayfa, _ids: list[int]) -> None:
    sinif = sayfa.filtre.currentData() if sayfa.filtre else None
    _secili_siniflara(sayfa, sayfa.db, [sinif] if sinif else [])


def _secili_siniflara(sayfa, db, ids: list[int]) -> None:
    if len(ids) == 1:
        if zorunlu_dersleri_ac(sayfa, db, ids[0]):
            sayfa.yenile()
        return
    hepsi = not ids
    if not ortak.onay(sayfa, ("Tüm sınıflarda" if hepsi else f"Seçili {len(ids)} sınıfta") +
                      " seviye, alan ve dala göre çerçeve öğretim programındaki zorunlu dersler ders dağılımına "
                      "açılacak ve haftalık saati farklı olanlar düzeltilecek. Mevcut öğretmen atamaları korunur."
                      "\n\nDevam edilsin mi?"):
        return
    sonuclar, sorunlar = [], []
    for r in db.q("SELECT id, ad FROM siniflar ORDER BY seviye, ad"):
        if not hepsi and r["id"] not in ids:
            continue
        e = cerceve.sinif_programi(db, r["id"])
        if e.program is None:
            sorunlar.append(f"{r['ad']}: {e.sorun}")
        else:
            sonuclar.append(cerceve.uygula(db, r["id"], e.program))
    m = [s.mesaj() for s in sonuclar] or ["Hiçbir sınıfa ders açılmadı."]
    m += [f"{s.sinif}: {u}" for s in sonuclar for u in s.uyarilar]
    if sorunlar:
        m.append("\nÇizelgesi belirlenemeyen sınıflar (tek tek seçip açabilirsiniz):\n- " + "\n- ".join(sorunlar))
    ortak.bilgi(sayfa, "\n".join(m), "Zorunlu dersler")
    sayfa.yenile()


# ----------------------------------------------------------------- göz atma sekmesi

class CerceveSayfasi(QWidget):
    """meslek.meb.gov.tr/cerceve çizelgelerini okul türü > sınıf > program > alan > dal sırasıyla gösterir."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        aciklama = QLabel(
            "MEB Mesleki ve Teknik Eğitim Genel Müdürlüğü çerçeve öğretim programlarındaki haftalık ders "
            "çizelgeleri. Okul türünü, sınıf seviyesini, programı, alanı ve dalı seçiniz; çizelgedeki zorunlu "
            "dersleri bir sınıfa uygulayabilir, alanı ve dallarını tanımlara ekleyebilirsiniz.")
        aciklama.setWordWrap(True)
        aciklama.setStyleSheet("color:#555")
        lay.addWidget(aciklama)

        ust = ortak.AkisDuzeni()
        self.kurum = QComboBox()
        for k, ad in cerceve.KURUMLAR.items():
            self.kurum.addItem(f"{k} - {ad}", k)
        self.seviye = QComboBox()
        for s in cerceve.SEVIYELER:
            self.seviye.addItem(f"{s}. sınıf", s)
        self.program_cb = QComboBox()
        self.alan = QComboBox()
        self.alan.setMinimumWidth(260)
        self.dal = QComboBox()
        self.dal.setMinimumWidth(220)
        self.protokol = QCheckBox("Protokollü program")
        for etiket, w in [("Okul:", self.kurum), ("Sınıf:", self.seviye), ("Program:", self.program_cb),
                          ("Alan:", self.alan), ("Dal:", self.dal)]:
            ust.addWidget(ortak.etiketli(etiket, w))
        ust.addWidget(self.protokol)
        ust.addStretch()
        lay.addLayout(ust)

        self.bilgi = QLabel()
        self.bilgi.setWordWrap(True)
        lay.addWidget(self.bilgi)
        self.tablo = CizelgeTablosu()
        lay.addWidget(self.tablo, 1)

        alt = ortak.AkisDuzeni()
        self.sinif = QComboBox()
        self.sinif.setMinimumWidth(160)
        alt.addWidget(ortak.etiketli("Uygulanacak sınıf:", self.sinif))
        for metin, fn in [("Sınıfa Uygula...", self.sinifa_uygula), ("Sınıfın Çizelgesini Göster", self.siniftan),
                          ("Alanı ve Dallarını Tanımlara Ekle", self.tanimlara_ekle),
                          ("Kaynak PDF'i Aç", lambda: kaynagi_ac(self.secili)), ("Excel'e Aktar", self.excel)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            alt.addWidget(b)
        alt.addStretch()
        lay.addLayout(alt)
        self.kaynak = QLabel()
        self.kaynak.setStyleSheet("color:#666")
        lay.addWidget(self.kaynak)

        self.secili: CopProgram | None = None
        self._doluyor = False
        self.kurum.currentIndexChanged.connect(lambda _: self._kurum_degisti())
        for cb in (self.seviye, self.program_cb, self.alan):
            cb.currentIndexChanged.connect(lambda _: self._dallari_doldur())
        self.dal.currentIndexChanged.connect(lambda _: self._goster())
        self.protokol.toggled.connect(lambda _: self._goster())
        if not cerceve.veri_var():
            self.bilgi.setText(f"<b>Çerçeve öğretim programı verisi bulunamadı:</b> {cerceve.VERI_DOSYASI}")
            return
        tur = (db.kurum()["tur"] or "MTAL").upper()
        self.kurum.setCurrentIndex(1 if tur == "MEM" else 0)
        self._kurum_degisti()
        self.kaynak.setText(f"Kaynak: {cerceve.KAYNAK_SAYFA} · Veri sürümü: {cerceve.surum()} · "
                            f"{len(cerceve.programlar())} haftalık ders çizelgesi")

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self) -> None:
        secili = self.sinif.currentData()
        self.sinif.clear()
        for r in self.db.q("SELECT id, ad FROM siniflar ORDER BY seviye, ad"):
            self.sinif.addItem(r["ad"], r["id"])
        i = self.sinif.findData(secili)
        self.sinif.setCurrentIndex(max(0, i))

    def _doldur(self, cb: QComboBox, ogeler: list[tuple[str, object]], tercih=None) -> None:
        onceki = tercih if tercih is not None else cb.currentData()
        cb.blockSignals(True)
        cb.clear()
        for metin, veri in ogeler:
            cb.addItem(metin, veri)
        i = cb.findData(onceki)
        cb.setCurrentIndex(max(0, i))
        cb.blockSignals(False)

    def _kurum_degisti(self, alan: str | None = None) -> None:
        k = self.kurum.currentData()
        self._doldur(self.program_cb, [(cerceve.PROGRAM_ADLARI[p], p) for p in cerceve.kurum_programlari(k)])
        self._doldur(self.alan, [(a, a) for a in cerceve.alanlar(k)], alan)
        self._dallari_doldur()

    def _dallari_doldur(self, dal: str | None = None) -> None:
        k, s, p, a = self.kurum.currentData(), self.seviye.currentData(), self.program_cb.currentData(), \
            self.alan.currentData()
        self._doldur(self.dal, [(d, d) for d in cerceve.dallar(k, a, s, p)] if a else [], dal)
        self._goster()

    def _adaylar(self) -> list[CopProgram]:
        k, s, p, a, d = (self.kurum.currentData(), self.seviye.currentData(), self.program_cb.currentData(),
                         self.alan.currentData(), self.dal.currentData())
        return [x for x in cerceve.programlar()
                if x.kurum == k and x.seviye == s and x.program == p and x.alan == a and x.dal == d]

    def _goster(self) -> None:
        adaylar = self._adaylar()
        protokollu = {x.protokol for x in adaylar}
        self.protokol.blockSignals(True)
        self.protokol.setEnabled(len(protokollu) > 1)
        if len(protokollu) == 1:
            self.protokol.setChecked(protokollu == {True})
        self.protokol.blockSignals(False)
        self.secili = next((x for x in adaylar if x.protokol == self.protokol.isChecked()), None) or \
            (adaylar[0] if adaylar else None)
        self.tablo.doldur(self.secili)
        if self.secili is None:
            k, s, p, a = (self.kurum.currentData(), self.seviye.currentData(), self.program_cb.currentText(),
                          self.alan.currentData())
            self.bilgi.setText(f"{a or 'Seçilen alan'} için {s}. sınıf {p} çizelgesi yok." if a else "")
            return
        x = self.secili
        self.bilgi.setText(f"<b>{x.etiket}</b><br>{_cumle(x.ozet())} Çerçeve öğretim programı yılı: {x.yil}.")

    def ayarla(self, p: CopProgram) -> None:
        self.kurum.blockSignals(True)
        self.kurum.setCurrentIndex(self.kurum.findData(p.kurum))
        self.kurum.blockSignals(False)
        self.seviye.blockSignals(True)
        self.seviye.setCurrentIndex(self.seviye.findData(p.seviye))
        self.seviye.blockSignals(False)
        self._kurum_degisti(p.alan)
        self._doldur(self.program_cb, [(cerceve.PROGRAM_ADLARI[x], x) for x in cerceve.kurum_programlari(p.kurum)],
                     p.program)
        self._dallari_doldur(p.dal)
        self.protokol.setChecked(p.protokol)

    def siniftan(self) -> None:
        sid = self.sinif.currentData()
        if not sid:
            return
        e = cerceve.sinif_programi(self.db, sid)
        p = e.program or (e.secenekler[0] if e.secenekler else None)
        if p is None:
            ortak.bilgi(self, e.sorun)
            return
        self.ayarla(p)
        if e.sorun:
            self.bilgi.setText(self.bilgi.text() + f"<br><span style='color:#8a4b00'>{e.sorun}</span>")

    def sinifa_uygula(self) -> None:
        sid = self.sinif.currentData()
        if not sid:
            ortak.hata(self, "Önce Tanımlar > Sınıflar / Şubeler ekranından sınıf tanımlayınız.")
            return
        if self.secili is None:
            ortak.hata(self, "Uygulanacak çizelgeyi seçiniz.")
            return
        s = cerceve.sinif_bilgisi(self.db, sid)
        if (s["seviye"] or 0) != self.secili.seviye and not ortak.onay(
                self, f"{s['ad']} sınıfının seviyesi {s['seviye']}, seçilen çizelge {self.secili.seviye}. sınıf. "
                      "Yine de uygulansın mı?"):
            return
        zorunlu_dersleri_ac(self, self.db, sid, self.secili)

    def tanimlara_ekle(self) -> None:
        a = self.alan.currentData()
        if not a:
            return
        dallar = cerceve.dallar(self.kurum.currentData(), a)
        if not ortak.onay(self, f"'{a}' alanı ve {len(dallar)} dalı ({', '.join(dallar)}) Alanlar ve Dallar "
                                "tanımlarına eklensin mi? Var olanlar yeniden eklenmez."):
            return
        _, eklenen = cerceve.tanimlara_ekle(self.db, a, dallar)
        ortak.bilgi(self, ("Eklendi: " + ", ".join(eklenen)) if eklenen else "Alan ve dalları zaten tanımlı.")

    def excel(self) -> None:
        x = self.secili
        if x is None:
            return
        yol = ortak.kaydet_yolu(self, f"Haftalık Ders Çizelgesi - {x.alan} - {x.dal} - {x.seviye}. Sınıf.xlsx")
        if not yol:
            return
        satirlar = [[self.tablo.item(r, c).text() if self.tablo.item(r, c) else "" for c in range(4)]
                    for r in range(self.tablo.rowCount())]
        excel_io.tablo_yaz(yol, BASLIKLAR, satirlar, baslik=f"{x.etiket} - Haftalık Ders Çizelgesi")
        ortak.kaydedildi(self, yol)
