"""Süreç eylemlerini arayüzden çalıştırma (onay, tarih sorma, arka planda çalıştırma)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (QApplication, QDateEdit, QDialog, QDialogButtonBox, QLabel, QMessageBox,
                               QVBoxLayout)

from ..services import surecler
from ..services.surecler import EylemSonucu
from . import ortak


def yil_sonu_tarihi(bugun: date | None = None) -> date:
    bugun = bugun or date.today()
    yil = bugun.year + 1 if bugun.month >= 9 else bugun.year
    d = date(yil, 6, 30)
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return d


def tarih_sor(parent, metin: str, varsayilan: date) -> date | None:
    dlg = QDialog(parent)
    dlg.setWindowTitle("Tarih")
    lay = QVBoxLayout(dlg)
    lay.addWidget(QLabel(metin))
    t = QDateEdit(QDate(varsayilan.year, varsayilan.month, varsayilan.day))
    t.setCalendarPopup(True)
    t.setDisplayFormat("dd.MM.yyyy")
    lay.addWidget(t)
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    lay.addWidget(bb)
    if dlg.exec() != QDialog.Accepted:
        return None
    q = t.date()
    return date(q.year(), q.month(), q.day())


def calistir(parent, db, anahtar: str, bitince: Callable[[EylemSonucu], None], **kw) -> bool:
    """Eylemi çalıştırır; kullanıcı vazgeçerse False döner. Uzun eylemler ayrı iş parçacığında yürür."""
    e = surecler.EYLEMLER[anahtar]
    if e.git and not e.calistir:
        bitince(EylemSonucu("", git=e.git))
        return True
    if e.onay and not ortak.onay(parent, e.onay):
        return False
    if e.tarih_ister and "tarih" not in kw:
        t = tarih_sor(parent, "Bitiş tarihi:", yil_sonu_tarihi())
        if t is None:
            return False
        kw["tarih"] = t

    def hata(m: str) -> None:
        QApplication.restoreOverrideCursor()
        ortak.hata(parent, m.strip().splitlines()[-1] if m.strip() else m)

    if e.uzun:
        def is_():
            d2 = db.kopya()
            try:
                return surecler.calistir(d2, anahtar, **kw)
            finally:
                d2.close()

        def bitti(s):
            QApplication.restoreOverrideCursor()
            bitince(s)

        QApplication.setOverrideCursor(Qt.WaitCursor)
        ortak.arka_planda(is_, bitti, hata)
        return True
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        s = surecler.calistir(db, anahtar, **kw)
    except Exception as ex:
        hata(f"{e.etiket} yapılamadı: {ex}")
        return False
    QApplication.restoreOverrideCursor()
    bitince(s)
    return True


def sonuc_goster(parent, pencere, s: EylemSonucu) -> None:
    """Eylem sonucunu ileti kutusunda gösterir; dosya açma ve ilgili ekrana gitme seçenekleri sunar."""
    if not s.mesaj and s.git:
        if pencere is not None:
            pencere.git(s.git)
        return
    box = QMessageBox(parent)
    box.setWindowTitle("İşlem tamamlandı")
    box.setText(s.mesaj)
    ac = box.addButton("Aç", QMessageBox.AcceptRole) if s.dosyalar else None
    klasor = box.addButton("Klasörü Aç", QMessageBox.ActionRole) if s.dosyalar else None
    git = box.addButton("Ekrana Git", QMessageBox.ActionRole) if s.git and pencere is not None else None
    box.addButton("Kapat", QMessageBox.RejectRole)
    box.exec()
    b = box.clickedButton()
    if ac is not None and b == ac:
        ortak.dosya_ac(s.dosyalar[0])
    elif klasor is not None and b == klasor:
        ortak.klasorde_goster(s.dosyalar[0])
    elif git is not None and b == git:
        pencere.git(s.git)
