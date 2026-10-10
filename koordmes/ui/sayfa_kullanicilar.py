"""Ayarlar > Kullanıcılar ve Ayarlar > İşlem Günlüğü sekmeleri."""
from __future__ import annotations

import json
from datetime import date, timedelta

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)

from .. import hesaplar as H
from ..mevzuat import PARAMETRE_SOZLUK
from ..services import excel_io
from ..services.aktarim import tr_kucuk
from . import ortak
from .crud import Varlik
from .giris import ParolaDegistirPenceresi, parola_degistir

ACIKLAMA_KAPALI = (
    "<b>Kişisel kullanıcı hesapları kapalı.</b> Şu anda bu bilgisayarı ya da sunucuyu kullanan herkes bütün "
    "işlemleri yapabilir; işlem günlüğünde Windows kullanıcı adı ya da bağlanırken yazılan ad görünür.<br><br>"
    "Hesaplar açılınca okul personelinin her biri kendi kullanıcı adı ve parolasıyla girer; her kişinin rolüne "
    "göre yetkisi olur ve işlem günlüğünde kimin hangi kaydı değiştirdiği adıyla görünür. Ağdaki bilgisayarlar "
    "bundan sonra sunucu parolası yerine kişisel kullanıcı adı ve parola sorar.<br><br>"
    "Başlamak için kendi yönetici hesabınızı oluşturun, sonra diğer personeli ekleyin.")
ACIKLAMA_ACIK = ("Her personel kendi kullanıcı adı ve parolasıyla girer. Yeni eklenen ya da parolası sıfırlanan "
                 "kullanıcı ilk girişte kendi parolasını belirler. Ayrılan personelin hesabını silmek yerine "
                 "pasifleştirin; geçmiş işlemleri işlem günlüğünde adıyla kalır.")


def _rol_metni() -> str:
    return "<br>".join(f"<b>{ad}:</b> {H.ROL_ACIKLAMALARI[k]}" for k, ad in H.ROLLER.items())


class KullaniciPenceresi(QDialog):
    def __init__(self, parent=None, satir=None, ilk: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Yönetici Hesabını Oluştur" if ilk else "Kullanıcıyı Düzenle" if satir else "Yeni Kullanıcı")
        lay = QVBoxLayout(self)
        f = QFormLayout()
        self.ad = QLineEdit(satir["ad_soyad"] if satir else "")
        f.addRow("Ad Soyad", self.ad)
        self.kullanici = QLineEdit(satir["kullanici_adi"] if satir else "")
        self.kullanici.setPlaceholderText("ör. ayse.yilmaz (boşluksuz)")
        self.kullanici.setReadOnly(satir is not None)
        f.addRow("Kullanıcı adı", self.kullanici)
        self.rol = QComboBox()
        for k, ad in H.ROLLER.items():
            self.rol.addItem(ad, k)
        self.rol.setCurrentIndex(max(0, self.rol.findData(satir["rol"] if satir else H.PERSONEL)))
        self.rol.setToolTip(_rol_metni())
        if not ilk:
            f.addRow("Rol", self.rol)
        self.aktif = QCheckBox("Hesap etkin (pasif hesapla giriş yapılamaz)")
        self.aktif.setChecked(bool(satir["aktif"]) if satir else True)
        if satir:
            f.addRow("", self.aktif)
        self.parola, self.tekrar = QLineEdit(), QLineEdit()
        for w in (self.parola, self.tekrar):
            w.setEchoMode(QLineEdit.Password)
        self.degistirsin = QCheckBox("İlk girişte kendi parolasını belirlesin")
        self.degistirsin.setChecked(True)
        if satir is None:
            f.addRow("Parola", self.parola)
            f.addRow("Parola (tekrar)", self.tekrar)
            if not ilk:
                f.addRow("", self.degistirsin)
        lay.addLayout(f)
        roller = QLabel(_rol_metni())
        roller.setWordWrap(True)
        roller.setStyleSheet("color:#555")
        if not ilk:
            lay.addWidget(roller)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Kaydet")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(self._kabul)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.satir = satir
        self.setMinimumWidth(460)

    def _kabul(self) -> None:
        if self.satir is None and self.parola.text() != self.tekrar.text():
            ortak.hata(self, "Parolalar birbirini tutmuyor.")
            return
        self.accept()


class KullanicilarSekmesi(QWidget):
    def __init__(self, db, ana_pencere=None, parent=None):
        super().__init__(parent)
        self.db, self.ana = db, ana_pencere
        lay = QVBoxLayout(self)
        self.aciklama = QLabel()
        self.aciklama.setWordWrap(True)
        lay.addWidget(self.aciklama)
        self.model = ortak.TabloModeli(["Ad Soyad", "Kullanıcı adı", "Rol", "Durum", "Son giriş"])
        self.view, self.proxy = ortak.tablo_gorunumu(self.model, filtrelenebilir=False)
        self.view.doubleClicked.connect(lambda *_: self.duzenle())
        lay.addWidget(self.view, 1)
        self.roller = QLabel(_rol_metni())
        self.roller.setWordWrap(True)
        self.roller.setStyleSheet("color:#555")
        lay.addWidget(self.roller)
        alt = QHBoxLayout()
        self.dugmeler: dict[str, QPushButton] = {}
        for ad, metin, fn in [("ac", "Kullanıcı Hesaplarını Aç...", self.hesaplari_ac),
                              ("yeni", "Yeni Kullanıcı...", self.yeni),
                              ("duzenle", "Düzenle...", self.duzenle),
                              ("sifirla", "Parolasını Sıfırla...", self.sifirla),
                              ("parolam", "Parolamı Değiştir...", self.parolam),
                              ("kapat", "Hesapları Kapat...", self.hesaplari_kapat)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            alt.addWidget(b)
            self.dugmeler[ad] = b
        alt.addStretch()
        lay.addLayout(alt)
        self.yenile()

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self) -> None:
        acik, yon = H.hesaplar_acik(self.db), self.db.kimlik.yonetici
        yonetim = acik and yon
        if not acik:
            self.aciklama.setText(ACIKLAMA_KAPALI)
        elif yon:
            self.aciklama.setText(ACIKLAMA_ACIK)
        else:
            self.aciklama.setText(f"Girişteki hesap: <b>{self.db.kimlik.ad}</b> ({self.db.kimlik.rol_adi}). "
                                  "Kullanıcı hesaplarını yalnızca yönetici yönetebilir; burada kendi parolanızı "
                                  "değiştirebilirsiniz.")
        self.view.setVisible(yonetim)
        self.roller.setVisible(not acik or yonetim)
        gorunur = {"ac": not acik and yon, "yeni": yonetim, "duzenle": yonetim, "sifirla": yonetim,
                   "kapat": yonetim, "parolam": self.db.kimlik.hesapli}
        for ad, b in self.dugmeler.items():
            b.setVisible(gorunur[ad])
        if yonetim:
            satirlar = H.kullanicilar(self.db)
            self.model.ayarla([[r["ad_soyad"], r["kullanici_adi"], H.ROLLER.get(r["rol"], r["rol"]),
                                ("Etkin" if r["aktif"] else "Pasif")
                                + (" (parola belirleyecek)" if r["aktif"] and r["parola_degistirmeli"] else ""),
                                r["son_giris"] or ""] for r in satirlar],
                              [r["id"] for r in satirlar],
                              {i: ortak.RENK_UYARI for i, r in enumerate(satirlar) if not r["aktif"]})
            ortak.sutunlari_sigdir(self.view)

    def _secili(self):
        satirlar = ortak.secili_satirlar(self.view, self.proxy)
        if not satirlar:
            ortak.bilgi(self, "Listeden bir kullanıcı seçin.")
            return None
        return self.db.q1("SELECT * FROM kullanicilar WHERE id = ?", (self.model.kimlik(satirlar[0]),))

    def _ana_guncelle(self) -> None:
        fn = getattr(self.ana, "kullanici_guncelle", None)
        if callable(fn):
            fn()

    def hesaplari_ac(self) -> None:
        dlg = KullaniciPenceresi(self, ilk=True)
        dlg.ad.setText(self.db.kimlik.ad)
        while dlg.exec() == QDialog.Accepted:
            try:
                kimlik = H.hesaplari_ac(self.db, dlg.ad.text(), dlg.kullanici.text(), dlg.parola.text())
            except ValueError as e:
                ortak.hata(self, str(e))
                continue
            if not self.db.uzak:
                self.db.kimlik_ata(kimlik)
            self._ana_guncelle()
            self.yenile()
            ortak.bilgi(self, "Kullanıcı hesapları açıldı ve yönetici hesabınız oluşturuldu. Şimdi diğer personeli "
                              "'Yeni Kullanıcı' ile ekleyin.\n\nProgram bundan sonra açılışta kullanıcı adı ve parola "
                              "sorar; ağdaki bilgisayarlar da bir sonraki bağlanışta kişisel giriş ister."
                        + ("\n\nBu bilgisayar sunucuya bağlı: yeni hesabınızla çalışmak için programı yeniden "
                           "başlatın." if self.db.uzak else ""))
            return

    def yeni(self) -> None:
        dlg = KullaniciPenceresi(self)
        while dlg.exec() == QDialog.Accepted:
            try:
                H.kullanici_ekle(self.db, dlg.ad.text(), dlg.kullanici.text(), dlg.rol.currentData(),
                                 dlg.parola.text(), dlg.degistirsin.isChecked())
            except ValueError as e:
                ortak.hata(self, str(e))
                continue
            self.yenile()
            return

    def duzenle(self) -> None:
        r = self._secili()
        if r is None:
            return
        dlg = KullaniciPenceresi(self, r)
        while dlg.exec() == QDialog.Accepted:
            try:
                H.kullanici_guncelle(self.db, r["id"], dlg.ad.text(), dlg.rol.currentData(), dlg.aktif.isChecked())
            except ValueError as e:
                ortak.hata(self, str(e))
                continue
            self.yenile()
            return

    def sifirla(self) -> None:
        r = self._secili()
        if r is None:
            return
        dlg = ParolaDegistirPenceresi(self, eski_sor=False,
                                      aciklama=f"<b>{r['ad_soyad']}</b> için geçici parola yazın. Kullanıcı ilk "
                                               "girişte kendi parolasını belirleyecek.")
        if dlg.exec() == QDialog.Accepted:
            try:
                H.parola_ata(self.db, r["id"], dlg.yeni.text(), degistirmeli=True)
            except ValueError as e:
                ortak.hata(self, str(e))
                return
            self.yenile()
            ortak.bilgi(self, "Parola sıfırlandı.")

    def parolam(self) -> None:
        parola_degistir(self, self.db)
        self.yenile()

    def hesaplari_kapat(self) -> None:
        if not ortak.onay(self, "Bütün kullanıcı hesapları pasifleştirilecek ve program eskisi gibi hesapsız "
                                "çalışacak: herkes bütün işlemleri yapabilir, ağdaki bilgisayarlar sunucu parolasıyla "
                                "bağlanır. Hesaplar silinmez; yeniden açınca etkinleştirebilirsiniz.\n\nDevam edilsin mi?"):
            return
        H.hesaplari_kapat(self.db)
        if not self.db.uzak:
            self.db.kimlik_ata(H.Kimlik.varsayilan(bilgisayar=self.db.kimlik.bilgisayar))
        self._ana_guncelle()
        self.yenile()


# ---------------------------------------------------------------- işlem günlüğü

def _etiketler() -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    from . import varliklar as V
    from .sayfa_ayarlar import KurumBilgileri
    tablolar = {"kurum": "Kurum Bilgileri", "ayarlar": "Ayarlar / Mevzuat", "aylik_odemeler": "Ücret ve Dekont",
                "kullanicilar": "Kullanıcı Hesapları"}
    kolonlar = {("kurum", a): e for a, e in KurumBilgileri.ALANLAR}
    kolonlar |= {("kurum", "tur"): "Kurum Türü", ("kurum", "buyuksehir"): "Büyükşehir", ("ayarlar", "deger"): "Değer",
                 ("kullanicilar", "ad_soyad"): "Ad Soyad", ("kullanicilar", "rol"): "Rol",
                 ("kullanicilar", "aktif"): "Etkin", ("kullanicilar", "parola_ozeti"): "Parola",
                 ("kullanicilar", "parola_degistirmeli"): "Parola belirleyecek",
                 ("aylik_odemeler", "gun"): "Gün", ("aylik_odemeler", "en_az_ucret"): "En az ücret",
                 ("aylik_odemeler", "odenecek_ucret"): "Ödenecek ücret",
                 ("aylik_odemeler", "devlet_katkisi"): "Devlet katkısı",
                 ("aylik_odemeler", "dekont_teslim"): "Dekont teslim",
                 ("aylik_odemeler", "sisteme_girildi"): "Sisteme girildi",
                 ("aylik_odemeler", "odenen_ucret"): "Ödenen ücret",
                 ("aylik_odemeler", "dekont_tarihi"): "Dekont tarihi"}
    for v in vars(V).values():
        if isinstance(v, Varlik):
            tablolar.setdefault(v.tablo, v.baslik)
            for a in v.alanlar:
                kolonlar.setdefault((v.tablo, a.ad), a.etiket)
    return tablolar, kolonlar


def ayrinti_metni(tablo: str, ayrinti: str, kolonlar: dict[tuple[str, str], str]) -> str:
    try:
        d = json.loads(ayrinti) if ayrinti else {}
    except ValueError:
        return ayrinti
    parcalar = []
    for k, (eski, yeni) in d.items():
        ad = kolonlar.get((tablo, k)) or k.replace("_", " ")
        parcalar.append(f"{ad}: {'' if eski is None else eski} → {'' if yeni is None else yeni}")
    return "; ".join(parcalar)


class IslemGunluguSekmesi(QWidget):
    BASLIKLAR = ["Zaman", "Kullanıcı", "Bilgisayar", "İşlem", "Kayıt türü", "Kayıt", "Değişiklikler"]
    AZAMI = 5000

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self._etiket: tuple | None = None
        lay = QVBoxLayout(self)
        self.not_ = QLabel(f"Kim, ne zaman, hangi kaydı ekledi, değiştirdi ya da sildi. Son {H.GUNLUK_SAKLAMA_GUN // 365} "
                           "yılın kayıtları saklanır; günlük kayıtları program içinden değiştirilemez ve silinemez. "
                           "T.C. kimlik no, IBAN, telefon ve adres gibi kişisel veriler günlüğe *** olarak yazılır.")
        self.not_.setWordWrap(True)
        self.not_.setStyleSheet("color:#555")
        lay.addWidget(self.not_)
        ust = QHBoxLayout()
        self.bas, self.bit = QDateEdit(), QDateEdit()
        for w, g in ((self.bas, date.today() - timedelta(days=7)), (self.bit, date.today())):
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd.MM.yyyy")
            w.setDate(QDate(g.year, g.month, g.day))
        ust.addWidget(QLabel("Tarih"))
        ust.addWidget(self.bas)
        ust.addWidget(QLabel("–"))
        ust.addWidget(self.bit)
        self.kisi = QComboBox()
        self.kisi.setMinimumWidth(160)
        ust.addWidget(QLabel("Kullanıcı"))
        ust.addWidget(self.kisi)
        self.ara = QLineEdit()
        self.ara.setPlaceholderText("Ara: öğrenci adı, işletme, kayıt türü...")
        self.ara.returnPressed.connect(self.yenile)
        ust.addWidget(self.ara, 1)
        for metin, fn in [("Listele", self.yenile), ("Excel'e Aktar", self.excel)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        lay.addLayout(ust)
        self.model = ortak.TabloModeli(self.BASLIKLAR)
        self.view, self.proxy = ortak.tablo_gorunumu(self.model, filtrelenebilir=False)
        lay.addWidget(self.view, 1)
        self.ozet = QLabel()
        lay.addWidget(self.ozet)
        self.yetkisiz = QLabel("İşlem günlüğünü yalnızca yönetici görebilir.")
        self.yetkisiz.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.yetkisiz)
        self._satirlar: list[list] = []

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def _yetkili(self) -> bool:
        return self.db.kimlik.yonetici or not H.hesaplar_acik(self.db)

    def satirlar(self) -> list[list]:
        if self._etiket is None:
            self._etiket = _etiketler()
        tablolar, kolonlar = self._etiket
        bas = self.bas.date().toString("yyyy-MM-dd")
        bit = self.bit.date().toString("yyyy-MM-dd")
        kosul, p = "zaman >= ? AND zaman < date(?, '+1 day')", [bas, bit]
        if self.kisi.currentIndex() > 0:
            kosul += " AND kullanici = ?"
            p.append(self.kisi.currentText())
        aranan = tr_kucuk(self.ara.text().strip())
        sonuc = []
        for r in self.db.q(f"SELECT * FROM islem_gunlugu WHERE {kosul} ORDER BY id DESC LIMIT 20000", p):
            kayit = r["kayit"] or ""
            if r["tablo"] == "ayarlar" and kayit in PARAMETRE_SOZLUK:
                kayit = PARAMETRE_SOZLUK[kayit].etiket
            satir = [r["zaman"], r["kullanici"], r["bilgisayar"], r["islem"], tablolar.get(r["tablo"], r["tablo"]),
                     kayit, ayrinti_metni(r["tablo"], r["ayrinti"], kolonlar)]
            if aranan and aranan not in tr_kucuk(" ".join(str(v) for v in satir)):
                continue
            sonuc.append(satir)
            if len(sonuc) >= self.AZAMI:
                break
        return sonuc

    def yenile(self) -> None:
        yetkili = self._yetkili()
        for w in (self.view, self.ozet, self.not_):
            w.setVisible(yetkili)
        self.yetkisiz.setVisible(not yetkili)
        if not yetkili:
            return
        secili = self.kisi.currentText()
        kisiler = [r["kullanici"] for r in self.db.q("SELECT DISTINCT kullanici FROM islem_gunlugu ORDER BY 1")]
        self.kisi.blockSignals(True)
        self.kisi.clear()
        self.kisi.addItems(["Tümü", *kisiler])
        self.kisi.setCurrentIndex(max(0, self.kisi.findText(secili)))
        self.kisi.blockSignals(False)
        self._satirlar = self.satirlar()
        self.model.ayarla(self._satirlar)
        ortak.sutunlari_sigdir(self.view, azami=420)
        self.ozet.setText(f"{len(self._satirlar)} kayıt" + (f" (en yeni {self.AZAMI} kayıt gösteriliyor; tarih "
                                                            "aralığını daraltın)" if len(self._satirlar) >= self.AZAMI
                                                            else ""))

    def excel(self) -> None:
        if not self._yetkili():
            return
        yol = ortak.kaydet_yolu(self, f"İşlem Günlüğü {self.bas.date().toString('dd.MM.yyyy')}-"
                                      f"{self.bit.date().toString('dd.MM.yyyy')}.xlsx")
        if yol:
            ortak.kaydedildi(self, excel_io.tablo_yaz(yol, self.BASLIKLAR, self.satirlar(), "İşlem Günlüğü"))
