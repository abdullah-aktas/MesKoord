"""SGK sigorta işlemleri ile öğrenci ücreti / devlet katkısı ekranları."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget

from .. import config
from ..mevzuat import AYLAR
from ..services import baglanti, belgeler, raporlar, sgk_dosya, sigorta, ucret
from ..services.baglanti import SISTEM_SOZLUK
from ..services.utils import para
from . import ortak
from .sayfa_sgk_denetim import SgkKarsilastirma, SgkRiskleri
from .sayfa_sgk_toplu import BilgiKontrolu, ListeDisiKalanlar, TopluCikisTarihi, TopluGirisTarihi


def sgk_klasoru() -> Path:
    return config.output_dir() / "SGK"


def dosya_sonucu_goster(parent, sonuc: sgk_dosya.DosyaSonucu, aciklama: str, sistem: str = "") -> None:
    box = QMessageBox(parent)
    box.setWindowTitle("SGK dosyası hazır")
    box.setIcon(QMessageBox.Warning if any("şemasına uymuyor" in u for u in sonuc.uyarilar) else
                QMessageBox.Information)
    box.setText(f"{sonuc.ozet()}\n\n" + "\n".join(str(y) for y in sonuc.yollar) + f"\n\n{aciklama}")
    if sonuc.uyarilar:
        box.setDetailedText("\n".join(sonuc.uyarilar))
        box.setInformativeText(f"{len(sonuc.uyarilar)} uyarı var (Ayrıntıları Göster).")
    yukle = None
    pencere = parent.window() if parent is not None else None
    if sistem and hasattr(pencere, "git"):
        yukle = box.addButton(f"Program İçinde {SISTEM_SOZLUK[sistem].ad}'i Aç ve Yükle", QMessageBox.AcceptRole)
    klasor = box.addButton("Klasörü Aç", QMessageBox.ActionRole)
    paylas_btn = box.addButton("Paylaş...", QMessageBox.ActionRole)
    box.addButton("Kapat", QMessageBox.RejectRole)
    box.exec()
    if yukle is not None and box.clickedButton() == yukle:
        baglanti.yuklenecek_ayarla(sonuc.yollar)
        ekran = pencere.git("e-Okul / e-Mesem / SGK Bağlantısı")
        if ekran is not None and hasattr(ekran, "ac"):
            ekran.ac(sistem)
            pencere.statusBar().showMessage(f"{SISTEM_SOZLUK[sistem].ad}'e giriş yapın; dosya seçme penceresi "
                                            f"{sonuc.yollar[0].name} ile açılacak.", 20000)
    elif box.clickedButton() == klasor:
        ortak.klasorde_goster(sonuc.yollar[0])
    elif box.clickedButton() == paylas_btn:
        from .paylas import PaylasPenceresi
        PaylasPenceresi(parent, list(sonuc.yollar)).exec()


class AylikPrimListesi(QWidget):
    BASLIKLAR = raporlar.SGK_BASLIKLAR

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        ust = QHBoxLayout()
        self.ay = ortak.AySecici()
        self.ay.degisti.connect(lambda *_: self.yenile())
        ust.addWidget(self.ay)
        b = QPushButton("Excel'e Aktar (kontrol listesi)")
        b.clicked.connect(self.excel)
        ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        sgk = ortak.AkisDuzeni()
        self.mahiyet = QComboBox()
        for kod, ad in sgk_dosya.MAHIYETLER.items():
            self.mahiyet.addItem(f"{ad} ({kod})", kod)
        self.tahakkuk = QComboBox()
        self.tahakkuk.addItem("Tahakkuk: otomatik (son güne göre)", None)
        for kod, ad in sgk_dosya.TAHAKKUK_NEDENLERI.items():
            self.tahakkuk.addItem(f"{kod} - {ad}", kod)
        self.tahakkuk.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.tahakkuk.setMinimumContentsLength(30)
        sgk.addWidget(ortak.etiketli("e-Bildirge V2 dosyası:", self.mahiyet))
        sgk.addWidget(self.tahakkuk)
        for metin, bicim, ipucu in [
                ("XML Üret", "xml", "e-Bildirge V2 > Belge Girişi > XML ile belge yükleme için (SGK şemasıyla "
                                    "doğrulanır)"),
                ("Excel Üret (SGK şablonu)", "excel", "SGK'nın 'Excel'den XML' şablonuyla aynı hücre düzeni")]:
            b = QPushButton(metin)
            b.setToolTip(ipucu)
            b.clicked.connect(lambda *_, x=bicim: self.sgk_dosyasi(x))
            sgk.addWidget(b)
        sgk.addStretch()
        lay.addLayout(sgk)
        self.bilgi = QLabel()
        self.bilgi.setWordWrap(True)
        self.bilgi.setStyleSheet("color:#555")
        lay.addWidget(self.bilgi)
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
        self.bilgi.setText(
            f"Prime esas kazanç: brüt asgari ücret ({para(self.db.ayar('asgari_ucret_brut'))} TL) x "
            f"%{self.db.ayar('sgk_pek_orani') * 100:g} / 30 x gün. Prim: bakmakla yükümlü olunan "
            f"%{self.db.ayar('sgk_prim_yukumlu') * 100:g} (belge 7/49), olunmayan "
            f"%{self.db.ayar('sgk_prim_yukumlu_degil') * 100:g} (belge 42/50). Tam ayda 30 gün; ay içinde "
            f"başlayan/bitenlerde parmak hesabı. Beyan son günü izleyen ayın {self.db.ayar('muhsgk_son_gun')}'sı.")
        rows, self.liste = raporlar.sgk_satirlari(self.db, *self.ay.deger())
        self.model.ayarla(rows)
        ortak.sutunlari_sigdir(self.view)
        oz = sigorta.belge_turu_ozeti(self.liste)
        self.ozet.setText("   |   ".join(f"Belge {bt}: {n} kişi, {g} gün, PEK {para(pek)} TL, prim {para(p)} TL"
                                         for bt, n, g, pek, p in oz) or "Bu dönem için sigortalı öğrenci yok.")

    def excel(self):
        yil, ay = self.ay.deger()
        yol = ortak.kaydet_yolu(self, f"SGK Aylık Prim Hizmet Listesi {AYLAR[ay - 1]} {yil}.xlsx")
        if yol:
            ortak.kaydedildi(self, raporlar.sgk_prim_listesi(self.db, yil, ay, yol))

    def sgk_dosyasi(self, bicim: str, klasor: Path | None = None, sessiz: bool = False):
        yil, ay = self.ay.deger()
        try:
            sonuc = sgk_dosya.aphb_dosyalari(self.db, yil, ay, klasor or sgk_klasoru(), bicim,
                                             self.mahiyet.currentData(), self.tahakkuk.currentData())
        except sgk_dosya.SgkDosyaHatasi as e:
            if not sessiz:
                ortak.hata(self, str(e))
            return None
        if not sessiz:
            dosya_sonucu_goster(self, sonuc, "e-Bildirge V2'de dönemi seçip dosyayı yükleyin; tahakkuk fişini "
                                             "onayladıktan sonra Risk ve Öneriler sekmesinde belgeyi 'verildi' "
                                             "işaretleyin.", "ebildirge" if bicim == "xml" else "")
        return sonuc


class GirisCikisBildirimleri(QWidget):
    BASLIKLAR = raporlar.BILDIRIM_BASLIKLAR

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lbl = QLabel("İşe giriş bildirgesi sigortalılık başlamadan önce, işten ayrılış bildirgesi ayrılıştan itibaren "
                     f"{db.ayar('sgk_cikis_bildirim_gun')} gün içinde verilir. Ara tatil, yarıyıl ve yaz tatillerinde "
                     "ayrılış bildirilmez. Aynı öğrencinin işletme değişikliğinde (15 gün içinde yeni kayıt) "
                     "bildirim gerekmez. e-Bildirge'den aldığınız bildirge listesini Veri Aktarımı'ndan yüklerseniz "
                     "kayıtlar otomatik işaretlenir.")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#555")
        lay.addWidget(lbl)
        ust = ortak.AkisDuzeni()
        for metin, fn in [("Yenile", self.yenile), ("Seçilenleri 'Bildirildi' İşaretle", self.isaretle),
                          ("Excel'e Aktar", self.excel),
                          ("SGK XML Üret", lambda *_: self.sgk_dosyasi("xml")),
                          ("SGK Excel Üret", lambda *_: self.sgk_dosyasi("excel"))]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            if metin.startswith("SGK"):
                b.setToolTip("Seçili satırlar (seçim yoksa tümü) için 4A toplu işe giriş / işten ayrılış dosyası")
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        lay.addWidget(self.view, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self):
        rows, self.liste = raporlar.bildirim_satirlari(self.db)
        self.model.ayarla(rows, [(b.yerlestirme_id, b.tur) for b in self.liste],
                          {i: ortak.RENK_KRITIK for i, b in enumerate(self.liste) if b.gecikti})
        ortak.sutunlari_sigdir(self.view)

    def isaretle(self):
        secili = [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)]
        for yid, tur in secili:
            sigorta.bildirildi_isaretle(self.db, yid, tur)
        self.yenile()

    def excel(self):
        yol = ortak.kaydet_yolu(self, "SGK Giriş-Çıkış Bildirim Listesi.xlsx")
        if yol:
            ortak.kaydedildi(self, raporlar.sgk_bildirim_listesi(self.db, yol))

    def sgk_dosyasi(self, bicim: str, klasor: Path | None = None, sessiz: bool = False):
        kimlikler = [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)] or \
                    [(b.yerlestirme_id, b.tur) for b in self.liste]
        if not kimlikler:
            if not sessiz:
                ortak.bilgi(self, "Bekleyen işe giriş / işten ayrılış bildirimi yok.")
            return None
        sonuc = sgk_dosya.DosyaSonucu()
        hatalar = []
        for tur in ("Giriş", "Çıkış"):
            ids = [yid for yid, t in kimlikler if t == tur]
            if not ids:
                continue
            try:
                s = sgk_dosya.bildirge_dosyalari(self.db, ids, tur, klasor or sgk_klasoru(), bicim)
            except sgk_dosya.SgkDosyaHatasi as e:
                hatalar.append(str(e))
                continue
            sonuc.yollar += s.yollar
            sonuc.kisi += s.kisi
            sonuc.uyarilar += [u for u in s.uyarilar if u not in sonuc.uyarilar]
        if not sonuc.yollar:
            if not sessiz:
                ortak.hata(self, "\n".join(hatalar))
            return None
        sonuc.uyarilar[:0] = hatalar
        if not sessiz:
            dosya_sonucu_goster(self, sonuc, "e-Bildirge > 4A Sigortalı İşe Giriş / İşten Ayrılış > 'Toplu' "
                                             "seçeneğinden yükleyin. Onaydan sonra satırları 'Bildirildi' "
                                             "işaretleyin.", "sgk4a" if bicim == "xml" else "")
        return sonuc


class SgkSayfasi(QTabWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.addTab(GirisCikisBildirimleri(db), "İşe Giriş / İşten Ayrılış")
        self.addTab(AylikPrimListesi(db), "Aylık Prim Hizmet Listesi")
        self.addTab(SgkKarsilastirma(db), "Liste Karşılaştırma")
        self.addTab(SgkRiskleri(db), "Risk ve Öneriler")
        self.addTab(TopluGirisTarihi(db), "Toplu Giriş Tarihi")
        self.addTab(TopluCikisTarihi(db), "Toplu Çıkış Tarihi")
        self.addTab(ListeDisiKalanlar(db), "Liste Dışı Kalanlar")
        self.addTab(BilgiKontrolu(db), "Bilgi Kontrolü")


class UcretListesi(QWidget):
    BASLIKLAR = raporlar.UCRET_BASLIKLAR

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        ust = ortak.AkisDuzeni()
        self.ay = ortak.AySecici()
        self.ay.degisti.connect(lambda *_: self.yenile())
        ust.addWidget(self.ay)
        for metin, fn in [("Dönemi Kaydet", self.kaydet), ("Excel'e Aktar", self.excel),
                          ("İşletmelere Ücret Yazısı (Word)", self.yazilar)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        self.bilgi = QLabel()
        self.bilgi.setWordWrap(True)
        lay.addWidget(self.bilgi)
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
        g12 = self.db.ayar("gecici12_aktif")
        renk = "#155724" if g12 else "#856404"
        self.bilgi.setText(
            f"<span style='color:{renk}'>Net asgari ücret: {para(self.db.ayar('asgari_ucret_net'))} TL. "
            f"3308 Geçici 12. madde: {'UYGULANIYOR' if g12 else 'UYGULANMIYOR'} "
            f"(Ayarlar'dan değiştirilebilir). İşletmeler ücreti izleyen ayın {self.db.ayar('dekont_teslim_son_gun')}'una "
            f"kadar öder; devlet katkısı e-Okul/e-Mesem üzerinden ayın {self.db.ayar('dk_sisteme_giris_son_gun')}'ine "
            f"kadar girilir.</span>")
        rows, self.liste = raporlar.ucret_satirlari(self.db, *self.ay.deger())
        self.model.ayarla(rows)
        ortak.sutunlari_sigdir(self.view)
        self.ozet.setText(f"{len(self.liste)} öğrenci — Ödenecek toplam: {para(sum(s.odenecek_ucret for s in self.liste))}"
                          f" TL — Devlet katkısı: {para(sum(s.devlet_katkisi for s in self.liste))} TL")

    def kaydet(self):
        ucret.kaydet(self.db, *self.ay.deger(), self.liste)
        ortak.bilgi(self, "Dönem hesapları kaydedildi. Dekont takibi bu kayıtlar üzerinden yapılır.")

    def excel(self):
        yil, ay = self.ay.deger()
        yol = ortak.kaydet_yolu(self, f"Öğrenci Ücret ve Devlet Katkısı {AYLAR[ay - 1]} {yil}.xlsx")
        if yol:
            ortak.kaydedildi(self, raporlar.ucret_listesi(self.db, yil, ay, yol))

    def yazilar(self):
        yil, ay = self.ay.deger()
        ids = {r["id"] for r in self.db.q("SELECT id, ad FROM isletmeler") if r["ad"] in {s.isletme for s in self.liste}}
        if not ids:
            ortak.bilgi(self, "Bu dönem için hesaplanmış ücret yok.")
            return
        son = None
        for i in ids:
            son = belgeler.uret(self.db, "isletme_ucret_bildirimi", i, yil=yil, ay=ay)
        ortak.kaydedildi(self, son.parent, coklu=True)


class DekontTakibi(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lbl = QLabel("Ücret dönemi kaydedildikten sonra işletmelerden gelen dekontlar burada izlenir. Banka/işletme "
                     "dekont listesini (Excel, PDF, Word) Veri Aktarımı'ndan yüklerseniz ödenen tutarlar işlenir ve "
                     "eksik ödemeler işaretlenir.")
        lbl.setWordWrap(True)
        lbl.setStyleSheet("color:#555")
        lay.addWidget(lbl)
        ust = ortak.AkisDuzeni()
        self.ay = ortak.AySecici()
        self.ay.degisti.connect(lambda *_: self.yenile())
        ust.addWidget(self.ay)
        for metin, fn in [("Dönemi Hesapla ve Kaydet", self.hesapla), ("Seçilenler: Dekont Teslim Alındı", self.teslim),
                          ("Seçilenler: Devlet Katkısı Sisteme Girildi", self.sisteme), ("Excel'e Aktar", self.excel)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        self.model = ortak.TabloModeli(raporlar.DEKONT_BASLIKLAR)
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
        kayit = raporlar.dekont_kayitlari(self.db, *self.ay.deger())
        renk = {"Dekont yok": ortak.RENK_UYARI, "Eksik ödeme": ortak.RENK_KRITIK, "Tamam": ortak.RENK_TAMAM}
        self.model.ayarla([r for _, r in kayit], [i for i, _ in kayit],
                          {n: renk[r[-1]] for n, (_, r) in enumerate(kayit)})
        ortak.sutunlari_sigdir(self.view)
        teslim = sum(1 for _, r in kayit if r[6] == "Teslim")
        eksik = sum(1 for _, r in kayit if r[-1] == "Eksik ödeme")
        self.ozet.setText(f"{len(kayit)} öğrenci — dekont teslim: {teslim}, bekleyen: {len(kayit) - teslim}, "
                          f"eksik ödeme: {eksik}" if kayit else
                          "Bu dönem kaydedilmemiş. 'Dönemi Hesapla ve Kaydet' ile başlayın.")

    def hesapla(self):
        yil, ay = self.ay.deger()
        ucret.kaydet(self.db, yil, ay, ucret.aylik_hesap(self.db, yil, ay))
        self.yenile()

    def _isaretle(self, kolon: str):
        ids = [self.model.kimlik(r) for r in ortak.secili_satirlar(self.view, self.proxy)]
        if not ids:
            ortak.bilgi(self, "Listeden kayıt seçiniz.")
            return
        for i in ids:
            vals = {kolon: 1}
            if kolon == "dekont_teslim":
                vals["dekont_tarihi"] = date.today().isoformat()
            self.db.update("aylik_odemeler", i, vals)
        self.yenile()

    def teslim(self):
        self._isaretle("dekont_teslim")

    def sisteme(self):
        self._isaretle("sisteme_girildi")

    def excel(self):
        yil, ay = self.ay.deger()
        yol = ortak.kaydet_yolu(self, f"Dekont Takip Listesi {AYLAR[ay - 1]} {yil}.xlsx")
        if yol:
            ortak.kaydedildi(self, raporlar.dekont_takip(self.db, yil, ay, yol))


class UcretSayfasi(QTabWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.addTab(UcretListesi(db), "Ücret ve Devlet Katkısı")
        self.addTab(DekontTakibi(db), "Dekont Takibi")
