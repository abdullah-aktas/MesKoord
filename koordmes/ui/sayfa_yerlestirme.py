"""Öğrenci-işletme yerleştirmeleri ve toplu işlemler."""
from __future__ import annotations

from dataclasses import replace
from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QLineEdit)

from ..mevzuat import FESIH_NEDENLERI, FESIH_SAYILAN, YERLESTIRME_TURLERI
from ..services import belgeler, koruma
from . import ortak
from .crud import CrudSayfasi, fk_combo, combo_deger
from .koruma import rehber_goster
from .varliklar import ISLETME_FK, SINIF_FK, YERLESTIRMELER


def _belge_uret(sayfa: CrudSayfasi, ids: list[int], anahtar: str) -> None:
    if not ids:
        ortak.bilgi(sayfa, "Önce listeden bir veya daha fazla kayıt seçiniz.")
        return
    son = None
    hatalar = []
    for i in ids:
        try:
            son = belgeler.uret(sayfa.db, anahtar, i)
        except Exception as e:
            hatalar.append(str(e))
    if hatalar:
        ortak.hata(sayfa, "\n".join(hatalar[:10]))
    if son:
        ortak.kaydedildi(sayfa, son.parent if len(ids) > 1 else son, coklu=len(ids) > 1)


class TopluYerlestirmeDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sınıfı toplu yerleştir")
        f = QFormLayout(self)
        self.sinif = fk_combo(db, SINIF_FK, True)
        self.tur = QComboBox()
        self.tur.addItems(YERLESTIRME_TURLERI)
        self.isletme = fk_combo(db, ISLETME_FK, False)
        self.bas = QDateEdit(QDate.currentDate())
        self.bas.setCalendarPopup(True)
        self.bas.setDisplayFormat("dd.MM.yyyy")
        self.sozlesme = QLineEdit()
        self.sozlesme.setPlaceholderText("ör. 2026/ (sıra numarası eklenir, boş bırakılabilir)")
        f.addRow("Sınıf", self.sinif)
        f.addRow("Tür", self.tur)
        f.addRow("İşletme (isteğe bağlı)", self.isletme)
        f.addRow("Başlangıç", self.bas)
        f.addRow("Sözleşme no ön eki", self.sozlesme)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)


def _toplu(sayfa: CrudSayfasi, _ids) -> None:
    d = TopluYerlestirmeDialog(sayfa.db, sayfa)
    if not d.exec():
        return
    db = sayfa.db
    sinif_id = combo_deger(d.sinif)
    q = d.bas.date()
    bas = date(q.year(), q.month(), q.day()).isoformat()
    ogrenciler = db.q("""SELECT o.id FROM ogrenciler o WHERE o.sinif_id = ? AND o.aktif = 1 AND NOT EXISTS (
                           SELECT 1 FROM yerlestirmeler y WHERE y.ogrenci_id = o.id AND y.durum = 'Aktif'
                           AND y.tur = ?) ORDER BY o.okul_no""", (sinif_id, d.tur.currentText()))
    on = d.sozlesme.text().strip()
    ids = [db.insert("yerlestirmeler", {"ogrenci_id": o["id"], "isletme_id": combo_deger(d.isletme),
                                        "tur": d.tur.currentText(), "baslangic": bas,
                                        "sozlesme_no": f"{on}{n:03d}" if on else ""})
           for n, o in enumerate(ogrenciler, 1)]
    sayfa.yenile()
    rh = koruma.toplu_rehber(db, ids, "Giriş")
    if rh is None:
        ortak.bilgi(sayfa, f"{len(ogrenciler)} öğrenci için kayıt oluşturuldu.")
        return
    rh.satirlar.insert(0, f"{len(ogrenciler)} öğrenci için kayıt oluşturuldu.")
    rehber_goster(sayfa, db, rh)


def _sona_erdir(sayfa: CrudSayfasi, ids: list[int]) -> None:
    if not ids:
        return
    from PySide6.QtWidgets import QInputDialog
    neden, ok = QInputDialog.getItem(
        sayfa, "Sona erdir", "Neden (sözleşme yalnızca 3308 md.22 hâllerinde, devamsızlık nedeniyle başarısızlıkta\n"
                             "veya sağlık nedeniyle tek taraflı; diğer durumlarda karşılıklı feshedilir - md.143):",
        FESIH_NEDENLERI, 0, True)
    if not ok:
        return
    bugun = date.today().isoformat()
    for i in ids:
        sayfa.db.update("yerlestirmeler", i, {"bitis": bugun,
                                              "durum": "Feshedildi" if neden in FESIH_SAYILAN else "Sona Erdi",
                                              "fesih_nedeni": neden})
    m = "Kayıtlar sona erdirildi. SGK işten ayrılış bildirgesi 'SGK İşlemleri' ekranında listelenir."
    if neden == "İşyeri değişikliği":
        m += (f"\n\nMESEM öğrencileri için yeni işletmeyle {sayfa.db.ayar('isyeri_degisikligi_gun')} gün içinde "
              "sözleşme imzalanmalıdır (md.143); süre Ana Sayfa'da gün gün izlenir.")
    sayfa.yenile()
    rh = koruma.toplu_rehber(sayfa.db, ids, "Çıkış")
    if rh is None:
        ortak.bilgi(sayfa, m)
        return
    rh.satirlar.insert(0, m)
    rehber_goster(sayfa, sayfa.db, rh)


def _secim(sayfa: CrudSayfasi, _ids) -> None:
    w = sayfa.window()
    s = w.git("Komisyon ve İzleme İşleri") if hasattr(w, "git") else None
    if hasattr(s, "secim_sekmesi"):
        s.secim_sekmesi()


def _kaydedildi(sayfa, db, kid: int, _d: dict, onceki: dict | None) -> None:
    rehber_goster(sayfa, db, koruma.yerlestirme_rehberi(db, kid, onceki))


def yerlestirme_sayfasi(db) -> CrudSayfasi:
    v = replace(YERLESTIRMELER, form_sonrasi=_kaydedildi, eylemler=[
        ("Sözleşme Üret (Word)", lambda s, ids: _belge_uret(s, ids, "isletme_sozlesmesi")),
        ("Çıraklık Sözleşmesi (MEM)", lambda s, ids: _belge_uret(s, ids, "ciraklik_sozlesmesi")),
        ("Değerlendirme Formu", lambda s, ids: _belge_uret(s, ids, "beceri_degerlendirme")),
        ("Sınıfı Toplu Yerleştir...", _toplu),
        ("Seçilenleri Sona Erdir...", _sona_erdir),
        ("Öğrenci Seçimi (md.136)...", _secim),
    ])
    return CrudSayfasi(db, v)
