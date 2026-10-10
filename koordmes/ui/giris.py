"""Kişisel kullanıcı hesabıyla giriş ve parola değiştirme pencereleri."""
from __future__ import annotations

import time

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                               QVBoxLayout)

from .. import hesaplar, marka
from . import ortak


class GirisPenceresi(QDialog):
    def __init__(self, parent=None, aciklama: str = "", kullanici: str = "", iptal_metni: str = "Çık"):
        super().__init__(parent)
        self.setWindowTitle(f"{marka.URUN} - Giriş")
        self.setWindowIcon(marka.uygulama_simgesi())
        lay = QVBoxLayout(self)
        ust = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(marka.logo_pixmap(64))
        ust.addWidget(logo)
        metin = QLabel(f"<h3 style='color:{marka.ANA}; margin:0'>{marka.URUN}</h3>"
                       + (aciklama or "Kullanıcı adınızı ve parolanızı yazın."))
        metin.setWordWrap(True)
        ust.addWidget(metin, 1)
        lay.addLayout(ust)
        f = QFormLayout()
        self.kullanici = QLineEdit(kullanici)
        self.kullanici.setPlaceholderText("ör. ayse.yilmaz")
        f.addRow("Kullanıcı adı", self.kullanici)
        self.parola = QLineEdit()
        self.parola.setEchoMode(QLineEdit.Password)
        f.addRow("Parola", self.parola)
        lay.addLayout(f)
        self.uyari = QLabel()
        self.uyari.setStyleSheet("color:#b00020")
        self.uyari.setWordWrap(True)
        self.uyari.hide()
        lay.addWidget(self.uyari)
        bb = QDialogButtonBox()
        tamam = bb.addButton("Giriş", QDialogButtonBox.AcceptRole)
        tamam.setDefault(True)
        bb.addButton(iptal_metni, QDialogButtonBox.RejectRole)
        bb.accepted.connect(self._kabul)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        (self.parola if kullanici else self.kullanici).setFocus()
        self.setMinimumWidth(420)

    def _kabul(self) -> None:
        if not self.kullanici.text().strip() or not self.parola.text():
            self.hata_goster("Kullanıcı adı ve parola boş olamaz.")
            return
        self.accept()

    def hata_goster(self, metin: str) -> None:
        self.uyari.setText(metin)
        self.uyari.show()
        self.parola.clear()
        self.parola.setFocus()

    def degerler(self) -> tuple[str, str]:
        return self.kullanici.text().strip(), self.parola.text()


def giris_sor(parent, aciklama: str = "", kullanici: str = "", hata: str = "") -> tuple[str, str] | None:
    dlg = GirisPenceresi(parent, aciklama, kullanici)
    if hata:
        dlg.hata_goster(hata)
    return dlg.degerler() if dlg.exec() == QDialog.Accepted else None


def yerel_giris(parent, db, aciklama: str = "", iptal_metni: str = "Çık") -> hesaplar.Kimlik | None:
    """Veritabanı bu bilgisayardaysa (tek başına ya da sunucu) kullanıcı adı ve parolayı denetler."""
    dlg = GirisPenceresi(parent, aciklama, iptal_metni=iptal_metni)
    hatali = 0
    while dlg.exec() == QDialog.Accepted:
        kimlik = hesaplar.dogrula(db.path, *dlg.degerler())
        if kimlik is not None:
            return kimlik
        hatali += 1
        if hatali >= 5:
            time.sleep(min(10, hatali))
        dlg.hata_goster("Kullanıcı adı ya da parola yanlış. Parolanızı unuttuysanız okuldaki yönetici hesabı "
                        "sahibinden sıfırlamasını isteyin.")
    return None


class ParolaDegistirPenceresi(QDialog):
    def __init__(self, parent=None, eski_sor: bool = True, aciklama: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Parola Değiştir")
        lay = QVBoxLayout(self)
        if aciklama:
            lbl = QLabel(aciklama)
            lbl.setWordWrap(True)
            lay.addWidget(lbl)
        f = QFormLayout()
        self.eski = QLineEdit()
        self.yeni = QLineEdit()
        self.tekrar = QLineEdit()
        for w in (self.eski, self.yeni, self.tekrar):
            w.setEchoMode(QLineEdit.Password)
        if eski_sor:
            f.addRow("Şu anki parola", self.eski)
        f.addRow("Yeni parola", self.yeni)
        f.addRow("Yeni parola (tekrar)", self.tekrar)
        lay.addLayout(f)
        ipucu = QLabel(f"En az {hesaplar.EN_KISA_PAROLA} karakter. Parolanızı kimseyle paylaşmayın.")
        ipucu.setStyleSheet("color:#555")
        lay.addWidget(ipucu)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Kaydet")
        bb.button(QDialogButtonBox.Cancel).setText("Vazgeç")
        bb.accepted.connect(self._kabul)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.eski_sor = eski_sor

    def _kabul(self) -> None:
        if len(self.yeni.text()) < hesaplar.EN_KISA_PAROLA:
            ortak.hata(self, f"Yeni parola en az {hesaplar.EN_KISA_PAROLA} karakter olmalı.")
        elif self.yeni.text() != self.tekrar.text():
            ortak.hata(self, "Yeni parolalar birbirini tutmuyor.")
        elif self.eski_sor and self.yeni.text() == self.eski.text():
            ortak.hata(self, "Yeni parola eskisiyle aynı olamaz.")
        else:
            self.accept()


def parola_degistir(parent, db, zorunlu: bool = False) -> bool:
    aciklama = ("İlk girişiniz ya da parolanız sıfırlandı. Devam etmek için kendinize yeni bir parola belirleyin."
                if zorunlu else "")
    while True:
        dlg = ParolaDegistirPenceresi(parent, eski_sor=not zorunlu, aciklama=aciklama)
        if dlg.exec() != QDialog.Accepted:
            return False
        try:
            hesaplar.kendi_parolasini_degistir(db, None if zorunlu else dlg.eski.text(), dlg.yeni.text())
        except ValueError as e:
            ortak.hata(parent, str(e))
            continue
        if not zorunlu:
            ortak.bilgi(parent, "Parolanız değiştirildi.")
        return True


def kullanici_girisi(db, parent=None) -> bool:
    """Açılışta: hesaplar açıksa giriş ister (ağa bağlı bilgisayarda giriş bağlanırken yapılmıştır)."""
    if not db.uzak and hesaplar.hesaplar_acik(db):
        kimlik = yerel_giris(parent, db)
        if kimlik is None:
            return False
        db.kimlik_ata(kimlik)
    if db.kimlik.parola_degistirmeli and not parola_degistir(parent, db, zorunlu=True):
        return False
    return True


def yetki_uyarisi(parent, db) -> None:
    QMessageBox.warning(parent, "Yetki yok",
                        f"{hesaplar.YETKI_YOK}\n\nGirişteki hesap: {db.kimlik.ad} ({db.kimlik.rol_adi}). "
                        "Bu işlem gerekiyorsa okuldaki yönetici hesabı sahibinden yetki isteyin.",
                        QMessageBox.Ok)

