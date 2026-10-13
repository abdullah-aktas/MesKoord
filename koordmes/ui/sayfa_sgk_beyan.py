"""SGK > Aylık Beyan (Adım Adım): ön kontrol, verilen belgenin kaydı, sonradan değişenler için iptal + ek düzeltme."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QLabel, QPushButton, QSplitter, QVBoxLayout, QWidget

from ..mevzuat import AYLAR
from ..services import sgk_beyan, sgk_dosya
from ..services.utils import para
from . import ortak

_RENK = {True: ortak.RENK_TAMAM, False: ortak.RENK_KRITIK, None: ortak.RENK_UYARI}
_FARK_RENK = {"Eklenecek": ortak.RENK_BILGI, "Değişti": ortak.RENK_UYARI, "İptal edilecek": ortak.RENK_KRITIK}


def _aciklama(metin: str) -> QLabel:
    lbl = QLabel(metin)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color:#555")
    return lbl


def _ozet(s: sgk_dosya.AphbSatiri | None) -> str:
    if s is None:
        return "-"
    return f"{s.gun} gün, {para(s.pek)} TL" + (f", {s.eksik_gun} eksik gün" if s.eksik_gun else "")


class AylikBeyan(QWidget):
    KONTROL_BASLIKLARI = ["Durum", "Kontrol", "Ayrıntı"]
    FARK_BASLIKLARI = ["Durum", "Öğrenci", "T.C.", "Belge", "Beyan edilen", "Şimdi", "Açıklama"]

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lay.addWidget(_aciklama(
            "1) Ön kontrolde 'Sorun' kalmayınca Aylık Prim Hizmet Listesi sekmesinden XML'i üretip e-Bildirge V2'ye "
            "yükleyin. 2) Tahakkuku onayladıktan sonra 'Beyanı Kaydet' deyin (başka programla verdiyseniz yüklediğiniz "
            "XML'i 'Beyanı XML'den Al' ile okutun). 3) Belge verildikten sonra işlenen devamsızlık, nakil, geriye "
            "dönük çıkış ya da belge türü değişikliği aşağıda listelenir; bütün belgeyi iptal etmeden yalnızca bu "
            "kişiler için iptal + ek dosyası üretilir. Satıra çift tıklayınca ilgili ekran açılır."))
        ust = ortak.AkisDuzeni()
        self.ay = ortak.AySecici()
        self.ay.degisti.connect(lambda *_: self.yenile())
        ust.addWidget(self.ay)
        for metin, fn, ipucu in [
                ("Yenile", self.yenile, ""),
                ("Beyanı Kaydet (Verildi)", self.kaydet,
                 "e-Bildirge'de onaylanan asıl belgeyi dönemin şu anki listesiyle kaydeder"),
                ("Beyanı XML'den Al...", self.xmlden,
                 "e-Bildirge'ye yüklediğiniz aylık prim ve hizmet belgesi XML'ini (asıl, ek ya da iptal) kaydeder"),
                ("Düzeltme Dosyalarını Üret (İptal + Ek)", self.duzeltme,
                 "Yalnızca değişen kişiler için iptal ve ek belgesi XML'i"),
                ("Düzeltmeyi Kaydet", self.duzeltme_kaydet,
                 "e-Bildirge'de onaylanan iptal ve ek belgelerini beyan kayıtlarına işler"),
                ("Son Beyan Kaydını Sil", self.sil, "Yanlış kaydedilen son belge kaydını geri alır"),
                ("Excel'e Aktar", self.excel, "")]:
            b = QPushButton(metin)
            b.setToolTip(ipucu)
            b.clicked.connect(lambda *_, f=fn: f())
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)

        bolme = QSplitter(Qt.Vertical)
        ust_w = QWidget()
        ul = QVBoxLayout(ust_w)
        ul.setContentsMargins(0, 0, 0, 0)
        self.kontrol_ozeti = QLabel()
        self.kontrol_ozeti.setWordWrap(True)
        self.kontrol_ozeti.setStyleSheet("font-weight:bold")
        ul.addWidget(self.kontrol_ozeti)
        self.kmodel = ortak.TabloModeli(self.KONTROL_BASLIKLARI)
        self.kview, self.kproxy = ortak.tablo_gorunumu(self.kmodel, filtrelenebilir=False)
        self.kview.doubleClicked.connect(lambda _: self._git_kontrol())
        ul.addWidget(self.kview, 1)
        bolme.addWidget(ust_w)

        alt_w = QWidget()
        al = QVBoxLayout(alt_w)
        al.setContentsMargins(0, 0, 0, 0)
        self.beyan_bilgi = QLabel()
        self.beyan_bilgi.setWordWrap(True)
        al.addWidget(self.beyan_bilgi)
        self.fmodel = ortak.TabloModeli(self.FARK_BASLIKLARI)
        self.fview, self.fproxy = ortak.tablo_gorunumu(self.fmodel)
        self.fview.doubleClicked.connect(lambda _: self._git_ogrenci())
        al.addWidget(self.fview, 1)
        self.fark_ozeti = QLabel()
        self.fark_ozeti.setWordWrap(True)
        self.fark_ozeti.setStyleSheet("font-weight:bold")
        al.addWidget(self.fark_ozeti)
        bolme.addWidget(alt_w)
        bolme.setSizes([260, 340])
        lay.addWidget(bolme, 1)
        self.kontroller: list[sgk_beyan.Kontrol] = []
        self.fark: sgk_beyan.BeyanFarki | None = None

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def _donem(self) -> str:
        yil, ay = self.ay.deger()
        return f"{AYLAR[ay - 1]} {yil}"

    def yenile(self):
        yil, ay = self.ay.deger()
        self.kontroller = sgk_beyan.on_kontrol(self.db, yil, ay)
        self.kmodel.ayarla([[k.isaret, k.baslik, k.detay] for k in self.kontroller],
                           list(range(len(self.kontroller))),
                           {i: _RENK[k.durum] for i, k in enumerate(self.kontroller)})
        ortak.sutunlari_sigdir(self.kview, 700)
        self.kontrol_ozeti.setText(f"{self._donem()} ön kontrol: {sgk_beyan.kontrol_ozeti(self.kontroller)}")

        self.fark = sgk_beyan.fark_analizi(self.db, yil, ay)
        self.beyan_bilgi.setText("Kayıtlı belgeler: " + ", ".join(b.etiket for b in self.fark.beyanlar)
                                 if self.fark.beyan_var else
                                 "Bu dönem için kayıtlı belge yok; verilen belgeyi kaydedince sonraki değişiklikler "
                                 "burada izlenir.")
        self.fmodel.ayarla([[f.durum, f.ad, f.tc, f.belge, _ozet(f.eski), _ozet(f.yeni), f.aciklama]
                            for f in self.fark.satirlar], [f.ogrenci_id for f in self.fark.satirlar],
                           {i: _FARK_RENK[f.durum] for i, f in enumerate(self.fark.satirlar)})
        ortak.sutunlari_sigdir(self.fview, 420)
        self.fark_ozeti.setText(self.fark.ozet())

    def _git_kontrol(self):
        satirlar = ortak.secili_satirlar(self.kview, self.kproxy)
        if not satirlar:
            return
        k = self.kontroller[self.kmodel.kimlik(satirlar[0])]
        pencere = self.window()
        if k.git and hasattr(pencere, "git"):
            pencere.git(k.git)

    def _git_ogrenci(self):
        from .crud import FormDialog
        from .varliklar import OGRENCILER
        satirlar = ortak.secili_satirlar(self.fview, self.fproxy)
        oid = self.fmodel.kimlik(satirlar[0]) if satirlar else None
        kayit = self.db.q1("SELECT * FROM ogrenciler WHERE id = ?", (oid,)) if oid else None
        if kayit and FormDialog(self.db, OGRENCILER, dict(kayit), self).exec():
            self.yenile()

    def kaydet(self):
        yil, ay = self.ay.deger()
        sorun = [k.baslik for k in self.kontroller if k.durum is False and k.baslik != "Bu ayın belgesi"]
        metin = (f"{self._donem()} aylık prim ve hizmet belgesi e-Bildirge V2'de onaylandı mı?\n\nDönemin şu anki "
                 "listesi verilen belge olarak kaydedilecek; sonraki değişiklikler bu kayda göre izlenir.")
        if sorun:
            metin += "\n\nÖn kontrolde sorun var: " + ", ".join(sorun)
        if not ortak.onay(self, metin):
            return
        try:
            sgk_beyan.beyan_kaydet(self.db, yil, ay)
        except sgk_dosya.SgkDosyaHatasi as e:
            ortak.hata(self, str(e))
            return
        self.yenile()

    def xmlden(self, yol: str | None = None):
        from .sayfa_sgk_ucret import sgk_klasoru
        if yol is None:
            yol, _ = QFileDialog.getOpenFileName(self, "e-Bildirge belgesi XML", str(sgk_klasoru()),
                                                 "XML Dosyası (*.xml)")
        if not yol:
            return
        try:
            x = sgk_beyan.xml_oku(self.db, yol)
        except sgk_dosya.SgkDosyaHatasi as e:
            ortak.hata(self, str(e))
            return
        bilinmeyen = sum(1 for s in x.satirlar if s.ogrenci_id is None)
        if not ortak.onay(self, f"{AYLAR[x.ay - 1]} {x.yil} {sgk_dosya.MAHIYETLER.get(x.mahiyet, x.mahiyet)} belgesi, "
                                f"{len(x.satirlar)} satır (tahakkuk {x.tahakkuk}) verildi olarak kaydedilsin mi?"
                                + (f"\n\n{bilinmeyen} T.C. öğrenci kayıtlarında bulunamadı." if bilinmeyen else "")):
            return
        try:
            sgk_beyan.beyan_kaydet(self.db, x.yil, x.ay, x.mahiyet, x.satirlar, tahakkuk=x.tahakkuk,
                                   aciklama=f"XML: {Path(yol).name}")
        except sgk_dosya.SgkDosyaHatasi as e:
            ortak.hata(self, str(e))
            return
        self.ay.ayarla(x.yil, x.ay)
        self.yenile()

    def duzeltme(self):
        from .sayfa_sgk_ucret import dosya_sonucu_goster, sgk_klasoru
        yil, ay = self.ay.deger()
        try:
            sonuc = sgk_beyan.duzeltme_dosyalari(self.db, yil, ay, sgk_klasoru())
        except sgk_dosya.SgkDosyaHatasi as e:
            ortak.bilgi(self, str(e))
            return
        dosya_sonucu_goster(self, sonuc, sonuc.uyarilar[0] if sonuc.uyarilar else "", "ebildirge")

    def duzeltme_kaydet(self):
        yil, ay = self.ay.deger()
        if not self.fark or not self.fark.satirlar:
            ortak.bilgi(self, "Kaydedilecek düzeltme yok.")
            return
        if not ortak.onay(self, f"{self._donem()} iptal ve ek belgeleri e-Bildirge'de onaylandı mı? "
                                f"{len(self.fark.iptal_satirlari)} iptal, {len(self.fark.ek_satirlari)} ek satırı "
                                "beyan kayıtlarına işlenecek."):
            return
        try:
            sgk_beyan.duzeltme_kaydet(self.db, yil, ay)
        except sgk_dosya.SgkDosyaHatasi as e:
            ortak.hata(self, str(e))
            return
        self.yenile()

    def sil(self):
        if not self.fark or not self.fark.beyan_var:
            ortak.bilgi(self, "Bu dönem için kayıtlı belge yok.")
            return
        son = self.fark.beyanlar[-1]
        if ortak.onay(self, f"'{son.etiket}' kaydı silinsin mi? (e-Bildirge'deki belgeye dokunulmaz.)"):
            sgk_beyan.beyan_sil(self.db, son.id)
            self.yenile()

    def excel(self):
        yol = ortak.kaydet_yolu(self, f"SGK Aylık Beyan {self._donem()}.xlsx")
        if yol and self.fark is not None:
            ortak.kaydedildi(self, sgk_beyan.excel_yaz(self.fark, self.kontroller, yol))
