"""Çok kullanıcılı çalışma ayarları: bu bilgisayar sunucu mu, istemci mi, yoksa tek başına mı çalışacak."""
from __future__ import annotations

import socket

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QRadioButton,
                               QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..ag import protokol as P
from ..ag.istemci import BaglantiBilgisi, BaglantiHatasi, ParolaHatasi, UzakBaglanti, sunucu_bilgisi
from ..ag.kesif import kesfet
from . import ortak, tepsi

ACIKLAMA = (
    "<b>Birden çok bilgisayarda aynı verilerle çalışmak için:</b> okuldaki bir bilgisayar (örneğin koordinatör "
    "müdür yardımcısının bilgisayarı) <b>sunucu</b> olur; veriler yalnızca onda durur. Diğer bilgisayarlarda "
    "MesKoord kurulur ve <b>sunucuya bağlan</b> seçilir. Herkes aynı anda çalışabilir; birinin kaydettiği "
    "değişiklik diğer ekranlarda anında görünür. Aynı kaydı iki kişi aynı anda değiştirirse program uyarır.<br>"
    "Bağlantı şifrelidir ve sunucu parolası olmadan kimse bağlanamaz. Veriler okulun ağından dışarı çıkmaz. "
    "Sunucu bilgisayarı açık ve MesKoord çalışır durumda olmalıdır.")


def sunucuyu_dogrula(parent, adres: str, port: int) -> str | None:
    """Sunucunun kimliğini (doğrulama kodu) kullanıcıya onaylatır; onaylanan parmak izini döndürür."""
    try:
        iz, bilgi = sunucu_bilgisi(adres, port)
    except Exception as e:  # noqa: BLE001
        ortak.hata(parent, f"{adres}:{port} adresindeki sunucuya ulaşılamadı.\n\n{e}\n\n"
                           "Sunucu bilgisayarında MesKoord'un açık olduğunu ve güvenlik duvarı izninin "
                           "verildiğini denetleyin.")
        return None
    kod = P.dogrulama_kodu(iz)
    cevap = QMessageBox.question(
        parent, "Sunucunun kimliğini doğrulayın",
        f"Bağlanılan sunucu: <b>{bilgi.get('ad')}</b> (MesKoord {bilgi.get('surum')})<br><br>"
        f"Doğrulama kodu:<br><span style='font-size:16pt; font-family:Consolas'><b>{kod}</b></span><br><br>"
        "Sunucu bilgisayarındaki <i>Çok Kullanıcılı Çalışma</i> ekranında görünen kodla aynı mı?<br>"
        "Aynıysa <b>Evet</b>'e basın. Farklıysa bağlanmayın ve okulun bilişim sorumlusuna haber verin.")
    return iz if cevap == QMessageBox.Yes else None


class AgSayfasi(QWidget):
    def __init__(self, db, ana_pencere=None, parent=None):
        super().__init__(parent)
        self.db, self.ana = db, ana_pencere
        self.ayar = P.AgAyarlari.yukle()
        self._iz = self.ayar.parmak_izi
        lay = QVBoxLayout(self)
        aciklama = QLabel(ACIKLAMA)
        aciklama.setWordWrap(True)
        lay.addWidget(aciklama)

        g = QGroupBox("Şu anki durum")
        gl = QVBoxLayout(g)
        self.durum = QLabel()
        self.durum.setWordWrap(True)
        self.durum.setTextInteractionFlags(Qt.TextSelectableByMouse)
        gl.addWidget(self.durum)
        self.kullanicilar = QTableWidget(0, 4)
        self.kullanicilar.setHorizontalHeaderLabels(["Kullanıcı", "Bilgisayar", "Adres", "Bağlanma"])
        self.kullanicilar.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.kullanicilar.setEditTriggers(QTableWidget.NoEditTriggers)
        self.kullanicilar.setMaximumHeight(160)
        gl.addWidget(self.kullanicilar)
        lay.addWidget(g)

        g = QGroupBox("Bu bilgisayar nasıl çalışsın?")
        gl = QVBoxLayout(g)
        self.secim = QButtonGroup(self)
        self.r_tek = QRadioButton("Tek başına (veriler yalnızca bu bilgisayarda, ağ kullanılmaz)")
        self.r_sunucu = QRadioButton("Sunucu olsun (veriler bu bilgisayarda; diğer bilgisayarlar buna bağlanır)")
        self.r_istemci = QRadioButton("Ağdaki sunucuya bağlansın (verileri sunucudan kullanır)")
        for i, r in enumerate([self.r_tek, self.r_sunucu, self.r_istemci]):
            self.secim.addButton(r, i)
            gl.addWidget(r)
        lay.addWidget(g)

        self.g_sunucu = QGroupBox("Sunucu ayarları")
        f = QFormLayout(self.g_sunucu)
        self.s_ad = QLineEdit(self.ayar.sunucu_adi)
        f.addRow("Sunucunun görünen adı", self.s_ad)
        self.s_port = QSpinBox()
        self.s_port.setRange(1024, 65535)
        self.s_port.setValue(self.ayar.port)
        f.addRow("Port", self.s_port)
        self.s_parola = QLineEdit()
        self.s_parola.setEchoMode(QLineEdit.Password)
        self.s_parola2 = QLineEdit()
        self.s_parola2.setEchoMode(QLineEdit.Password)
        if self.ayar.parola_ozeti:
            self.s_parola.setPlaceholderText("Parola belirlenmiş — değiştirmek için yeni parolayı yazın")
        f.addRow("Sunucu parolası", self.s_parola)
        f.addRow("Parola (tekrar)", self.s_parola2)
        self.s_otomatik = QCheckBox("Windows oturumu açılınca MesKoord'u arka planda başlat (sunucu kendiliğinden açılır)")
        self.s_otomatik.setChecked(tepsi.otomatik_baslat_acik())
        f.addRow("", self.s_otomatik)
        self.s_tepsi = QCheckBox("Pencere kapatılınca sistem tepsisinde çalışmayı sürdür (diğer kullanıcıların "
                                 "bağlantısı kesilmez; programı Güvenli Çıkış kapatır)")
        self.s_tepsi.setChecked(self.ayar.tepside_calis)
        f.addRow("", self.s_tepsi)
        self.s_bilgi = QLabel()
        self.s_bilgi.setWordWrap(True)
        self.s_bilgi.setTextInteractionFlags(Qt.TextSelectableByMouse)
        f.addRow(self.s_bilgi)
        lay.addWidget(self.g_sunucu)

        self.g_istemci = QGroupBox("Sunucuya bağlantı")
        v = QVBoxLayout(self.g_istemci)
        ust = QHBoxLayout()
        ara = QPushButton("Ağdaki Sunucuları Bul")
        ara.clicked.connect(self.ara)
        ust.addWidget(ara)
        self.bulunanlar = QListWidget()
        self.bulunanlar.setMaximumHeight(80)
        self.bulunanlar.itemClicked.connect(self._bulunan_sec)
        ust.addWidget(self.bulunanlar, 1)
        v.addLayout(ust)
        f = QFormLayout()
        self.i_adres = QLineEdit(self.ayar.adres)
        self.i_adres.setPlaceholderText("Sunucu bilgisayarın adı ya da IP adresi (ör. 192.168.1.20)")
        self.i_adres.textEdited.connect(self._adres_degisti)
        f.addRow("Sunucu adresi", self.i_adres)
        self.i_port = QSpinBox()
        self.i_port.setRange(1024, 65535)
        self.i_port.setValue(self.ayar.sunucu_portu)
        self.i_port.valueChanged.connect(self._adres_degisti)
        f.addRow("Port", self.i_port)
        self._hesap = self.ayar.hesap
        self.i_kullanici = QLineEdit(self.ayar.kullanici)
        self.i_kullanici_etiket = QLabel()
        f.addRow(self.i_kullanici_etiket, self.i_kullanici)
        self.i_parola = QLineEdit("" if self._hesap else self.ayar.parola)
        self.i_parola.setEchoMode(QLineEdit.Password)
        self.i_parola_etiket = QLabel()
        f.addRow(self.i_parola_etiket, self.i_parola)
        self.i_hatirla = QCheckBox("Parolayı bu Windows hesabında şifreli olarak hatırla")
        self.i_hatirla.setChecked(bool(self.ayar.parola_gizli) or not self.ayar.adres)
        f.addRow("", self.i_hatirla)
        self._hesap_gorunumu()
        self.i_iz = QLabel()
        f.addRow("Sunucu kimliği", self.i_iz)
        v.addLayout(f)
        sina = QPushButton("Bağlantıyı Sına")
        sina.clicked.connect(self.sina)
        v.addWidget(sina, alignment=Qt.AlignLeft)
        lay.addWidget(self.g_istemci)

        alt = QHBoxLayout()
        kaydet = QPushButton("Kaydet ve Programı Yeniden Başlat")
        kaydet.setDefault(True)
        kaydet.clicked.connect(self.kaydet)
        alt.addWidget(kaydet)
        alt.addStretch()
        lay.addLayout(alt)
        lay.addStretch()

        {P.KIP_SUNUCU: self.r_sunucu, P.KIP_ISTEMCI: self.r_istemci}.get(self.ayar.kip, self.r_tek).setChecked(True)
        self.secim.idToggled.connect(lambda *_: self._gorunum())
        ag = getattr(ana_pencere, "ag", None)
        if ag is not None:
            ag.durum_degisti.connect(self.yenile)
        self._gorunum()
        self._iz_goster()
        self.yenile()

    # --- görünüm ---
    def _kip(self) -> str:
        return {1: P.KIP_SUNUCU, 2: P.KIP_ISTEMCI}.get(self.secim.checkedId(), P.KIP_TEK)

    def _gorunum(self) -> None:
        self.g_sunucu.setVisible(self._kip() == P.KIP_SUNUCU)
        self.g_istemci.setVisible(self._kip() == P.KIP_ISTEMCI)

    def _hesap_gorunumu(self) -> None:
        """Sunucuda kişisel hesaplar açıksa kullanıcı adı ve kişisel parola sorulur; parola hatırlanmaz."""
        self.i_kullanici_etiket.setText("Kullanıcı adınız" if self._hesap else "Adınız")
        self.i_kullanici.setPlaceholderText("Okulun size verdiği kullanıcı adı" if self._hesap
                                            else "Diğer kullanıcılara görünecek adınız")
        self.i_parola_etiket.setText("Parolanız" if self._hesap else "Sunucu parolası")
        self.i_hatirla.setVisible(not self._hesap)

    def _iz_goster(self) -> None:
        self.i_iz.setText(f"doğrulandı — kod {P.dogrulama_kodu(self._iz)}" if self._iz
                          else "henüz doğrulanmadı (Bağlantıyı Sına'ya basın)")

    def _adres_degisti(self, *_):
        if (self.i_adres.text().strip(), self.i_port.value()) != (self.ayar.adres, self.ayar.sunucu_portu):
            self._iz = ""
        else:
            self._iz = self.ayar.parmak_izi
        self._iz_goster()

    def yenile(self) -> None:
        ag = getattr(self.ana, "ag", None)
        if ag is None:
            self.durum.setText(f"Bu bilgisayar <b>tek başına</b> çalışıyor. Veritabanı: {self.db.konum}")
            kullanicilar = []
        else:
            metin, iyi = ag.durum_metni()
            renk = "#1b5e20" if iyi else "#b00020"
            ek = ""
            if ag.sunucu is not None:
                adresler = ", ".join(P.yerel_adresler()) or "bulunamadı"
                ek = (f"<br>Diğer bilgisayarlarda sunucu adresi olarak <b>{adresler}</b> (ya da "
                      f"<b>{socket.gethostname()}</b>), port <b>{ag.sunucu.port}</b> yazılır.<br>"
                      f"Doğrulama kodu: <b style='font-family:Consolas'>{P.dogrulama_kodu(ag.sunucu.parmak_izi)}"
                      "</b> (bağlanan bilgisayarlarda aynı kod görünmelidir)")
            elif ag.hata:
                ek = f"<br><span style='color:#b00020'>{ag.hata}</span>"
            self.durum.setText(f"<span style='color:{renk}'><b>{metin}</b></span><br>Veritabanı: {self.db.konum}"
                               + ek)
            kullanicilar = ag.kullanicilar()
        self.kullanicilar.setRowCount(len(kullanicilar))
        for i, k in enumerate(kullanicilar):
            for j, d in enumerate([k["kullanici"], k["bilgisayar"] + (" (sunucu)" if k.get("sunucu") else ""),
                                   k.get("adres", ""), k.get("giris", "")]):
                self.kullanicilar.setItem(i, j, QTableWidgetItem(d))
        self.kullanicilar.setVisible(bool(kullanicilar))
        self._sunucu_bilgisi()

    def _sunucu_bilgisi(self) -> None:
        adresler = ", ".join(P.yerel_adresler()) or "bulunamadı"
        self.s_bilgi.setText(
            f"Bu bilgisayarın ağ adresleri: <b>{adresler}</b> — adı: <b>{socket.gethostname()}</b><br>"
            "Kurulum, Windows güvenlik duvarında MesKoord'a yerel ağ izni verir. Başka bir güvenlik yazılımı "
            "kullanılıyorsa bu porta izin verilmelidir. Sunucu bilgisayarının uyku moduna geçmemesi önerilir.")

    # --- istemci ---
    def ara(self) -> None:
        self.bulunanlar.clear()
        self.setCursor(Qt.WaitCursor)
        try:
            liste = kesfet()
        finally:
            self.unsetCursor()
        if not liste:
            self.bulunanlar.addItem("Sunucu bulunamadı — adresi elle yazabilirsiniz.")
            return
        for d in liste:
            it = QListWidgetItem(f"{d.get('ad')} — {d['adres']}:{d.get('port')} (sürüm {d.get('surum')})")
            it.setData(Qt.UserRole, d)
            self.bulunanlar.addItem(it)

    def _bulunan_sec(self, it: QListWidgetItem) -> None:
        d = it.data(Qt.UserRole)
        if d:
            self.i_adres.setText(d["adres"])
            self.i_port.setValue(int(d.get("port") or P.VARSAYILAN_PORT))
            self._adres_degisti()

    def sina(self) -> bool:
        adres, port = self.i_adres.text().strip(), self.i_port.value()
        if not adres:
            ortak.hata(self, "Sunucu adresini yazın ya da 'Ağdaki Sunucuları Bul' ile seçin.")
            return False
        if not self._iz:
            iz = sunucuyu_dogrula(self, adres, port)
            if not iz:
                return False
            self._iz = iz
            self._iz_goster()
        bilgi = BaglantiBilgisi(adres, port, self.i_parola.text(), self._iz,
                                self.i_kullanici.text().strip() or P.varsayilan_kullanici())
        self.setCursor(Qt.WaitCursor)
        try:
            b = UzakBaglanti(bilgi, ana=False)
            ad = b.sunucu.get("sunucu_adi")
            self._hesap = bool(b.sunucu.get("hesap"))
            b.close()
        except ParolaHatasi as e:
            degisti = e.hesap != self._hesap
            self._hesap = e.hesap
            self._hesap_gorunumu()
            ortak.hata(self, "Bu sunucuda kişisel kullanıcı hesapları açık. Okulun size verdiği kullanıcı adını ve "
                             "kendi parolanızı yazın." if degisti and e.hesap else str(e))
            return False
        except (BaglantiHatasi, OSError) as e:
            ortak.hata(self, f"Bağlanılamadı:\n{e}")
            return False
        finally:
            self.unsetCursor()
        self._hesap_gorunumu()
        ortak.bilgi(self, f"{ad} sunucusuna bağlantı başarılı.")
        return True

    # --- kaydet ---
    def kaydet(self) -> None:
        kip = self._kip()
        a = P.AgAyarlari.yukle()
        if kip == P.KIP_SUNUCU:
            p1, p2 = self.s_parola.text(), self.s_parola2.text()
            if p1 or not a.parola_ozeti:
                if len(p1) < 6:
                    return ortak.hata(self, "Sunucu parolası en az 6 karakter olmalı.")
                if p1 != p2:
                    return ortak.hata(self, "Parolalar birbirini tutmuyor.")
                a.parola_ozeti = P.parola_ozeti(p1)
            a.sunucu_adi = self.s_ad.text().strip() or socket.gethostname()
            a.port = self.s_port.value()
            a.tepside_calis = self.s_tepsi.isChecked()
        elif kip == P.KIP_ISTEMCI:
            if not self.sina():
                return
            if a.kip != P.KIP_ISTEMCI and not ortak.onay(
                    self, "Bu bilgisayar bundan sonra sunucudaki verilerle çalışacak. Bu bilgisayarda şimdiye kadar "
                          "girilmiş veriler silinmez ama kullanılmaz; gerekiyorsa önce Ayarlar > Veri Yönetimi'nden "
                          "yedek alıp sunucuda geri yükleyin. Devam edilsin mi?"):
                return
            a.adres, a.sunucu_portu, a.parmak_izi = self.i_adres.text().strip(), self.i_port.value(), self._iz
            a.kullanici = self.i_kullanici.text().strip() or P.varsayilan_kullanici()
            a.hesap = self._hesap
            a.parola = self.i_parola.text() if self.i_hatirla.isChecked() and not a.hesap else ""
        try:
            tepsi.otomatik_baslat_ayarla(kip == P.KIP_SUNUCU and self.s_otomatik.isChecked())
        except OSError as e:
            ortak.hata(self, f"Windows açılışında başlatma ayarlanamadı:\n{e}")
        a.kip = kip
        a.kaydet()
        self.ayar = a
        if self.ana is None:
            return
        if not ortak.onay(self, "Ayarlar kaydedildi. Yeni çalışma biçimi program yeniden başlatılınca geçerli olur. "
                                "Şimdi yeniden başlatılsın mı?"):
            return
        self.ana.yeniden_baslat = True
        if not self.ana.guvenli_cikis():
            self.ana.yeniden_baslat = False
