"""Kurum bilgileri, mevzuat parametreleri ve veri yönetimi."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
                               QHeaderView, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from .. import config, lisans, marka, yedekleme
from ..db import OTOMATIK_YEDEK_SAYISI
from ..mevzuat import PARAMETRELER
from ..services import ornek_veri
from ..services.kurum_turu import aciklama, tur_tahmin
from ..services.utils import tarih, tr
from . import ortak


class KurumBilgileri(QWidget):
    ALANLAR = [("ad", "Kurum Adı"), ("kurum_kodu", "Kurum Kodu"), ("il", "İl"), ("ilce", "İlçe"),
               ("mudur", "Okul/Kurum Müdürü"), ("koordinator_mudur_yrd", "Koordinatör Müdür Yardımcısı"),
               ("sgk_isyeri_sicil", "SGK İşyeri Sicil No"), ("adres", "Adres"), ("telefon", "Telefon"),
               ("eposta", "E-posta"), ("egitim_yili", "Eğitim-Öğretim Yılı")]
    TARIHLER = [("ders_yili_baslangic", "Ders Yılı Başlangıcı"), ("birinci_donem_sonu", "1. Dönem Sonu"),
                ("ders_yili_sonu", "Ders Yılı Sonu")]
    KILITLI = ("ad", "kurum_kodu")

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        self.yetki_notu = _yetki_notu()
        lay.addWidget(self.yetki_notu)
        f = QFormLayout()
        self.w = {}
        self.tur = QComboBox()
        for kod, ad in [("MTAL", "Mesleki ve Teknik Anadolu Lisesi"),
                        ("MEM", "Mesleki Eğitim Merkezi"),
                        ("ÇPAL", "Çok Programlı Anadolu Lisesi"),
                        ("MTAL+MEM", "MTAL ve MEM birlikte")]:
            self.tur.addItem(ad, kod)
        self._tur_elle = False
        self.tur.activated.connect(self._tur_elle_secildi)
        f.addRow("Kurum Türü", self.tur)
        self.tur_bilgi = QLabel()
        self.tur_bilgi.setWordWrap(True)
        self.tur.currentIndexChanged.connect(lambda _: self._tur_aciklama())
        f.addRow("", self.tur_bilgi)
        self.bs = QCheckBox("Büyükşehir belediyesi sınırları içinde")
        f.addRow("", self.bs)
        for k, e in self.ALANLAR:
            self.w[k] = QLineEdit()
            f.addRow(e, self.w[k])
        for k, e in self.TARIHLER:
            self.w[k] = QLineEdit()
            self.w[k].setPlaceholderText("gg.aa.yyyy")
            self.w[k].setToolTip("Sözleşme süresi (md.143) ve puan çizelgesi teslim (md.89/1-g) hatırlatmaları "
                                 "bu tarihlere göre yapılır.")
            f.addRow(e, self.w[k])
        self.w["ad"].textChanged.connect(self._ad_degisti)
        lay.addLayout(f)
        satir = QHBoxLayout()
        b = QPushButton("Kaydet")
        b.clicked.connect(self.kaydet)
        satir.addWidget(b)
        self.sistem_btn = QPushButton("Sistemlerden verileri getir")
        self.sistem_btn.setToolTip("Kurum türüne göre e-Okul, e-Mesem, SGK işe giriş/çıkış, e-Bildirge ve "
                                   "e-Vizite ekranlarını programın içinde sırayla açar.")
        self.sistem_btn.clicked.connect(lambda: self.sistemlerden_getir())
        satir.addWidget(self.sistem_btn)
        satir.addStretch()
        lay.addLayout(satir)
        self.yonetici_dugmeleri = [b, self.sistem_btn]
        self._tur_aciklama()
        g = QGroupBox("Kurum logosu (üretilen Word belgelerinin ve PDF raporların başında)")
        gl = QHBoxLayout(g)
        self.logo = QLabel()
        self.logo.setFixedSize(96, 96)
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet("border:1px solid #c9d3e0; background:white")
        gl.addWidget(self.logo)
        sag = QVBoxLayout()
        self.logo_bilgi = QLabel()
        self.logo_bilgi.setWordWrap(True)
        sag.addWidget(self.logo_bilgi)
        dugmeler = QHBoxLayout()
        for metin, fn in [("Logo Seç...", self.logo_sec), ("Logoyu Kaldır", self.logo_kaldir)]:
            lb = QPushButton(metin)
            lb.clicked.connect(fn)
            dugmeler.addWidget(lb)
            self.yonetici_dugmeleri.append(lb)
        dugmeler.addStretch()
        sag.addLayout(dugmeler)
        gl.addLayout(sag, 1)
        lay.addWidget(g)
        lay.addStretch()

    def _logo_goster(self) -> None:
        yol = marka.kurum_logosu(self.db)
        if yol:
            self.logo.setPixmap(QPixmap(str(yol)).scaled(90, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.logo.clear()
            self.logo.setText("Logo yok")
        self.logo_bilgi.setText(
            "Yüklenen logo veritabanında saklanır; ağdaki bütün bilgisayarlar aynı logoyu kullanır." if yol else
            "Logo yüklenmedi; belgeler logosuz çıkar. PNG veya JPG biçiminde, tercihen kare ve saydam zeminli bir "
            "logo seçin.")
        ortak.KURUM_LOGOSU = yol

    def logo_sec(self) -> None:
        yol, _ = QFileDialog.getOpenFileName(self, "Kurum logosu", str(Path.home()),
                                             "Resim (*.png *.jpg *.jpeg *.bmp)")
        if not yol:
            return
        try:
            marka.kurum_logosu_yaz(self.db, Path(yol))
        except Exception as e:  # noqa: BLE001
            ortak.hata(self, f"Logo okunamadı:\n{e}")
            return
        self._logo_goster()

    def logo_kaldir(self) -> None:
        marka.kurum_logosu_yaz(self.db, None)
        self._logo_goster()

    def showEvent(self, e):
        super().showEvent(e)
        lis, _ = lisans.bul()
        lisans.kurum_uygula(self.db, lis)
        k = self.db.kurum()
        yon = _yetki_uygula(self.db, self.yetki_notu, self.yonetici_dugmeleri)
        self.w["ad"].blockSignals(True)
        for a, _ in self.ALANLAR:
            self.w[a].setText(k[a] or "")
            self.w[a].setReadOnly(not yon)
        self.w["ad"].blockSignals(False)
        for a, _ in self.TARIHLER:
            self.w[a].setText(tr(k[a]))
            self.w[a].setReadOnly(not yon)
        for a in self.KILITLI:
            self.w[a].setReadOnly(lis is not None or not yon)
            self.w[a].setStyleSheet("background:#eeeeee" if lis else "")
            self.w[a].setToolTip(f"Lisanstan gelir ({lis.lisans_no}); değiştirilemez." if lis else "")
        kod = k["tur"] or "MTAL"
        if self.tur.findData(kod) < 0:
            self.tur.addItem(kod, kod)
        self.tur.setCurrentIndex(self.tur.findData(kod))
        tahmin = tur_tahmin(k["ad"] or "")
        self._tur_elle = bool(tahmin and tahmin != kod)
        self.bs.setChecked(bool(k["buyuksehir"]))
        self.tur.setEnabled(yon)
        self.bs.setEnabled(yon)
        self._tur_aciklama()
        self._logo_goster()

    def _tur_elle_secildi(self) -> None:
        self._tur_elle = True

    def _ad_degisti(self) -> None:
        if self._tur_elle:
            return
        tahmin = tur_tahmin(self.w["ad"].text())
        if not tahmin:
            return
        i = self.tur.findData(tahmin)
        if i >= 0 and i != self.tur.currentIndex():
            self.tur.setCurrentIndex(i)

    def _tur_aciklama(self) -> None:
        self.tur_bilgi.setText(aciklama(self.tur.currentData() or "MTAL"))

    def kaydet(self, sessiz: bool = False) -> bool:
        d = {a: self.w[a].text().strip() for a, _ in self.ALANLAR}
        for a, etiket in self.TARIHLER:
            metin = self.w[a].text().strip()
            t = tarih(metin)
            if metin and not t:
                ortak.hata(self, f"{etiket} tarihi anlaşılamadı; gg.aa.yyyy biçiminde yazınız.")
                return False
            d[a] = t.isoformat() if t else None
        d["tur"] = self.tur.currentData() or "MTAL"
        d["buyuksehir"] = 1 if self.bs.isChecked() else 0
        self.db.update("kurum", 1, d)
        lisans.kurum_uygula(self.db, lisans.bul()[0])
        pencere = self.window()
        if hasattr(pencere, "kurum_guncelle"):
            pencere.kurum_guncelle()
        self._logo_goster()
        if sessiz:
            return True
        ortak.bilgi(self, "Kurum bilgileri kaydedildi.\n\n" + aciklama(d["tur"]))
        if d["ad"] and d["kurum_kodu"] and hasattr(pencere, "git") and ortak.onay(
                self, "Kurum adı ve kodu kaydedildi. Bu tür için e-Okul, e-Mesem ve SGK ekranları "
                      "programın içinde açılsın mı?\n\nVeriler, bu sistemlere giriş yaptıktan sonra "
                      "indirdiğiniz listelerden kendiliğinden gelir. Şifre saklanmaz. "
                      "Kayıtları elle de girebilirsiniz.", "Sistemlere bağlan"):
            self._sistemleri_ac()
        return True

    def sistemlerden_getir(self) -> None:
        if not self.kaydet(sessiz=True):
            return
        self._sistemleri_ac()

    def _sistemleri_ac(self) -> None:
        pencere = self.window()
        if not hasattr(pencere, "git"):
            ortak.bilgi(self, "Sistemler ana penceredeki e-Okul / e-Mesem / SGK Bağlantısı ekranından açılır.")
            return
        sayfa = pencere.git("e-Okul / e-Mesem / SGK Bağlantısı")
        if sayfa is not None and hasattr(sayfa, "turune_gore_ac"):
            sayfa.turune_gore_ac()


class MevzuatParametreleri(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        lbl = QLabel("Mevzuat değiştiğinde (yeni asgari ücret, katsayı, oranlar, Geçici 12. madde uzatması vb.) "
                     "yalnızca 'Değer' sütununu güncelleyiniz. Mantıksal değerler için 1 = evet, 0 = hayır.")
        lbl.setWordWrap(True)
        lay.addWidget(lbl)
        self.yetki_notu = _yetki_notu()
        lay.addWidget(self.yetki_notu)
        self.yonetici_dugmeleri: list[QPushButton] = []
        self.t = QTableWidget(len(PARAMETRELER), 4)
        self.t.setHorizontalHeaderLabels(["Grup", "Parametre", "Değer", "Dayanak / Not"])
        self.t.verticalHeader().setVisible(False)
        h = self.t.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Interactive)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        self.t.setColumnWidth(1, 420)
        self.t.setColumnWidth(2, 110)
        lay.addWidget(self.t, 1)
        alt = QHBoxLayout()
        for metin, fn in [("Kaydet", self.kaydet), ("Varsayılanlara Dön", self.sifirla)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            alt.addWidget(b)
            self.yonetici_dugmeleri.append(b)
        alt.addStretch()
        lay.addLayout(alt)

    def showEvent(self, e):
        super().showEvent(e)
        self.doldur()

    def doldur(self):
        yon = _yetki_uygula(self.db, self.yetki_notu, self.yonetici_dugmeleri)
        for i, p in enumerate(PARAMETRELER):
            for j, v in enumerate([p.grup, p.etiket, str(self.db.q1("SELECT deger FROM ayarlar WHERE anahtar = ?",
                                                                     (p.anahtar,))["deger"]), p.kaynak]):
                it = QTableWidgetItem(v)
                if j != 2 or not yon:
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                self.t.setItem(i, j, it)

    def kaydet(self):
        hatali = []
        for i, p in enumerate(PARAMETRELER):
            v = self.t.item(i, 2).text().strip().replace(",", ".") if p.tip in ("float", "int") else \
                self.t.item(i, 2).text().strip()
            try:
                if p.tip == "float":
                    float(v)
                elif p.tip == "int":
                    int(float(v))
                elif p.tip == "bool" and v not in ("0", "1"):
                    raise ValueError
            except ValueError:
                hatali.append(p.etiket)
                continue
            self.db.ayar_yaz(p.anahtar, v)
        if hatali:
            ortak.hata(self, "Geçersiz değerler kaydedilmedi:\n- " + "\n- ".join(hatali))
        else:
            ortak.bilgi(self, "Parametreler kaydedildi.")
        self.doldur()

    def sifirla(self):
        if ortak.onay(self, "Tüm parametreler varsayılan değerlere döndürülsün mü?"):
            self.db.ayarlari_sifirla()
            self.doldur()


class VeriYonetimi(QWidget):
    def __init__(self, db, ana_pencere, parent=None):
        super().__init__(parent)
        self.db, self.ana = db, ana_pencere
        lay = QVBoxLayout(self)
        g = QGroupBox("Veri klasörü")
        gl = QVBoxLayout(g)
        gl.addWidget(QLabel(f"Veritabanı: {db.konum}"))
        gl.addWidget(QLabel(f"Çıktılar: {config.output_dir()}\nŞablonlar: {config.templates_dir()}\n"
                            f"Yedekler: {config.backup_dir()}"))
        b = QPushButton("Veri Klasörünü Aç")
        b.clicked.connect(lambda: ortak.dosya_ac(config.data_dir()))
        gl.addWidget(b, alignment=Qt.AlignLeft)
        lay.addWidget(g)
        self.yetki_notu = _yetki_notu()
        lay.addWidget(self.yetki_notu)
        g2 = QGroupBox("Yedekleme")
        gl2 = QHBoxLayout(g2)
        self.yonetici_dugmeleri: list[QPushButton] = []
        for metin, fn in [("Şimdi Yedekle", self.yedekle), ("Yedekten Geri Yükle...", self.geri_yukle)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            gl2.addWidget(b)
        self.yonetici_dugmeleri.append(b)
        gl2.addStretch()
        lay.addWidget(g2)
        lay.addWidget(self._otomatik_yedek_grubu())
        g3 = QGroupBox("Deneme")
        gl3 = QHBoxLayout(g3)
        b = QPushButton("Örnek Veri Yükle (mevcut veriler silinir)")
        b.clicked.connect(self.ornek)
        gl3.addWidget(b)
        self.yonetici_dugmeleri.append(b)
        gl3.addStretch()
        lay.addWidget(g3)
        lay.addStretch()

    def _otomatik_yedek_grubu(self) -> QGroupBox:
        g = QGroupBox("Otomatik yedek")
        v = QVBoxLayout(g)
        if self.db.uzak:
            lbl = QLabel("Bu bilgisayar sunucuya bağlı. Otomatik yedeği verilerin durduğu sunucu bilgisayarı alır; "
                         "ayarı sunucudaki MesKoord'da yapın.")
            lbl.setWordWrap(True)
            v.addWidget(lbl)
            return g
        a = yedekleme.YedekAyarlari.yukle()
        satir = QHBoxLayout()
        self.oto = QCheckBox("Program açıkken düzenli yedek al")
        self.oto.setChecked(a.otomatik)
        satir.addWidget(self.oto)
        self.aralik = QComboBox()
        for saat, ad in yedekleme.ARALIKLAR:
            self.aralik.addItem(ad, saat)
        self.aralik.setCurrentIndex(max(0, self.aralik.findData(a.aralik_saat)))
        satir.addWidget(self.aralik)
        satir.addStretch()
        v.addLayout(satir)
        satir = QHBoxLayout()
        satir.addWidget(QLabel("İkinci yedek klasörü:"))
        self.ikinci = QLineEdit(a.ikinci_klasor)
        self.ikinci.setReadOnly(True)
        self.ikinci.setPlaceholderText("Seçilmedi (USB bellek ya da ağ klasörü önerilir)")
        satir.addWidget(self.ikinci, 1)
        for metin, fn in [("Klasör Seç...", self.ikinci_sec), ("Kaldır", lambda: self._ikinci_ayarla(""))]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            satir.addWidget(b)
        v.addLayout(satir)
        self.yedek_durum = QLabel()
        self.yedek_durum.setWordWrap(True)
        v.addWidget(self.yedek_durum)
        self.oto.toggled.connect(lambda *_: self._oto_kaydet())
        self.aralik.currentIndexChanged.connect(lambda *_: self._oto_kaydet())
        self._yedek_durumu()
        return g

    def _oto_kaydet(self) -> None:
        a = yedekleme.YedekAyarlari.yukle()
        a.otomatik, a.aralik_saat = self.oto.isChecked(), int(self.aralik.currentData())
        a.kaydet()
        self._yedek_durumu()

    def ikinci_sec(self) -> None:
        yol = QFileDialog.getExistingDirectory(self, "İkinci yedek klasörü", self.ikinci.text() or str(Path.home()))
        if yol:
            self._ikinci_ayarla(yol)

    def _ikinci_ayarla(self, yol: str) -> None:
        a = yedekleme.YedekAyarlari.yukle()
        a.ikinci_klasor, a.son_hata = yol, ""
        a.kaydet()
        self.ikinci.setText(yol)
        if yol:
            yedek = self.db.yedekle()
            a = yedekleme.YedekAyarlari.yukle()
            if a.son_hata:
                ortak.hata(self, a.son_hata)
            else:
                ortak.bilgi(self, "Yedekler bundan sonra bu klasöre de kopyalanacak. İlk kopya:\n"
                                  f"{Path(yol) / yedekleme.IKINCI_KLASOR_ADI / yedek.name}")
        self._yedek_durumu()

    def _yedek_durumu(self) -> None:
        a = yedekleme.YedekAyarlari.yukle()
        son = a.son_yedek_zamani()
        metin = f"Son yedek: {son:%d.%m.%Y %H:%M}" if son else "Henüz yedek alınmadı."
        metin += f" — yedek klasörü: {config.backup_dir()} (son {OTOMATIK_YEDEK_SAYISI} yedek tutulur)"
        if a.ikinci_klasor:
            metin += f"; ikinci klasörde son {yedekleme.IKINCI_KLASOR_TUT} yedek tutulur."
        if a.son_hata:
            metin += f"<br><span style='color:#b00020'>{a.son_hata}</span>"
        self.yedek_durum.setText(metin)

    def showEvent(self, e):
        super().showEvent(e)
        _yetki_uygula(self.db, self.yetki_notu, self.yonetici_dugmeleri)
        if not self.db.uzak:
            self._yedek_durumu()

    def yedekle(self):
        yol = self.db.yedekle()
        if yol.exists():
            ortak.kaydedildi(self, yol)
        else:
            ortak.bilgi(self, f"Yedek sunucu bilgisayarında alındı ({yol.name}). Yedek dosyasını yalnızca yönetici "
                              "kendi bilgisayarına indirebilir.")
        if not self.db.uzak:
            self._yedek_durumu()

    def geri_yukle(self):
        yol, _ = QFileDialog.getOpenFileName(self, "Yedek seç", str(config.backup_dir()), "Veritabanı (*.db)")
        ag = " Ağdaki bütün kullanıcıların verileri değişir." if self.db.uzak else ""
        if yol and ortak.onay(self, "Mevcut veriler seçilen yedekle değiştirilecek. Önce otomatik yedek alınacak."
                                    f"{ag} Devam edilsin mi?"):
            self.db.yedekle()
            self.db.geri_yukle(Path(yol))
            lisans.kurum_uygula(self.db, lisans.bul()[0])
            ortak.bilgi(self, "Yedek geri yüklendi.")

    def ornek(self):
        if not ortak.onay(self, "TÜM MEVCUT VERİLER SİLİNECEK ve örnek veri yüklenecek (önce yedek alınır). "
                                "Devam edilsin mi?"):
            return
        self.db.yedekle()
        ornek_veri.yukle(self.db)
        lisans.kurum_uygula(self.db, lisans.bul()[0])
        ortak.bilgi(self, "Örnek veri yüklendi; ders programı ve koordinatörlük görevleri otomatik oluşturuldu.")


def _yetki_notu() -> QLabel:
    lbl = QLabel()
    lbl.setWordWrap(True)
    lbl.setStyleSheet("background:#fff4e5; color:#8a4b00; padding:6px; border-radius:4px")
    lbl.hide()
    return lbl


def _yetki_uygula(db, notu: QLabel, dugmeler: list[QPushButton]) -> bool:
    """Yönetici olmayan hesapta bölümü salt okunur yapar; yönetici mi döndürür."""
    yon = db.kimlik.yonetici
    notu.setText(f"Bu bölümü yalnızca yönetici değiştirebilir. Girişteki hesap: <b>{db.kimlik.ad}</b> "
                 f"({db.kimlik.rol_adi}).")
    notu.setVisible(not yon)
    for b in dugmeler:
        b.setEnabled(yon)
    return yon


class AyarlarSayfasi(QTabWidget):
    def __init__(self, db, ana_pencere, parent=None):
        super().__init__(parent)
        from .sayfa_kullanicilar import IslemGunluguSekmesi, KullanicilarSekmesi
        self.addTab(KurumBilgileri(db), "Kurum Bilgileri")
        self.addTab(MevzuatParametreleri(db), "Mevzuat Parametreleri")
        self.addTab(VeriYonetimi(db, ana_pencere), "Veri ve Yedekleme")
        self.addTab(KullanicilarSekmesi(db, ana_pencere), "Kullanıcılar")
        self.addTab(IslemGunluguSekmesi(db), "İşlem Günlüğü")
