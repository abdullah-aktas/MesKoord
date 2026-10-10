"""Koordinatörlük: görev dağılımı, görevlendirme yazıları, ziyaret planı."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QSplitter, QTabWidget, QVBoxLayout, QWidget

from ..mevzuat import AYLAR, GUNLER
from ..services import belgeler, koordinator, raporlar
from ..services.utils import ay_araligi
from . import ortak
from .crud import CrudSayfasi
from .varliklar import KOORDINATOR_GOREVLERI, ZIYARETLER


class GorevDagilimi(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        self.aciklama = QLabel()
        self.aciklama.setWordWrap(True)
        self.aciklama.setStyleSheet("color:#555")
        lay.addWidget(self.aciklama)
        ust = ortak.AkisDuzeni()
        for metin, fn in [("Otomatik Görevlendir", self.otomatik), ("Görevlendirme Yazıları (Word)", self.yazilar),
                          ("İşletmelere Bildirim (Word)", self.bildirimler),
                          ("Komisyon Kararı (Word)", self.komisyon), ("Excel'e Aktar", self.excel)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        lay.addLayout(ust)
        sp = QSplitter()
        self.model = ortak.TabloModeli(["Öğretmen"] + GUNLER + ["Haftalık Toplam", "Sınır"])
        self.view, self.proxy = ortak.tablo_gorunumu(self.model)
        self.view.setWordWrap(True)
        sp.addWidget(self.view)
        sag = QWidget()
        sl = QVBoxLayout(sag)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(QLabel("<b>Görevlendirilemeyen işletmeler</b>"))
        self.atanamayan = QListWidget()
        sl.addWidget(self.atanamayan)
        sl.addWidget(QLabel("<b>İşletme ihtiyaçları</b>"))
        self.ihtiyac = QListWidget()
        sl.addWidget(self.ihtiyac)
        sp.addWidget(sag)
        sp.setSizes([900, 320])
        lay.addWidget(sp, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self):
        self.aciklama.setText("Saat hesabı (komisyon ölçütleri, Ayarlar'dan değiştirilebilir): "
                              + koordinator.saat_hesabi_aciklama(self.db)
                              + " Görevler öğretmenin ders programında boş olan ve öğrencilerin işletmede olduğu "
                                "günlere verilir.")
        _, rows = raporlar.koordinator_satirlari(self.db)
        self.model.ayarla(rows, None, {i: ortak.RENK_KRITIK for i, r in enumerate(rows) if r[-2] > r[-1]})
        self.view.resizeRowsToContents()
        ortak.sutunlari_sigdir(self.view, 260)
        self.ihtiyac.clear()
        for ih in koordinator.isletme_ihtiyaclari(self.db):
            self.ihtiyac.addItem(f"{ih.ad}: {ih.ogrenci_sayisi} öğrenci, {ih.saat} saat, "
                                 f"{ih.guzergah or '-'} ({ih.mesafe_km:g} km)")

    def otomatik(self):
        if self.db.q1("SELECT COUNT(*) c FROM koordinator_gorevleri")["c"] and not ortak.onay(
                self, "Mevcut koordinatörlük görevleri silinip yeniden dağıtılacak. Devam edilsin mi?"):
            return
        s = koordinator.otomatik_gorevlendir(self.db)
        self.atanamayan.clear()
        for ih, neden in s.atanamayan:
            self.atanamayan.addItem(f"{ih.ad}: {neden}")
        for ad, neden in s.kapsam_disi:
            self.atanamayan.addItem(f"{ad}: {neden}")
        self.yenile()
        m = f"{len(s.gorevler)} görev verildi, {len(s.atanamayan)} işletme/grup görevlendirilemedi."
        if s.alan_disi:
            m += ("\n\nAlanı dışında görevlendirilen öğretmenler (md.88/2-e uyarınca işletmelerde mesleki eğitimin "
                  "usul ve esasları hakkında bilgilendirilmelidir):\n" + "\n".join(s.alan_disi[:15]))
        ortak.bilgi(self, m)

    def yazilar(self):
        ids = [r["ogretmen_id"] for r in self.db.q("SELECT DISTINCT ogretmen_id FROM koordinator_gorevleri")]
        if not ids:
            ortak.bilgi(self, "Önce görevlendirme yapınız.")
            return
        son = None
        for t in ids:
            son = belgeler.uret(self.db, "koordinator_gorevlendirme", t)
        ortak.kaydedildi(self, son.parent, coklu=True)

    def bildirimler(self):
        ids = [r["isletme_id"] for r in self.db.q("SELECT DISTINCT isletme_id FROM koordinator_gorevleri")]
        if not ids:
            ortak.bilgi(self, "Önce görevlendirme yapınız.")
            return
        son = None
        for i in ids:
            son = belgeler.uret(self.db, "koordinator_bildirimi", i)
        ortak.kaydedildi(self, son.parent, coklu=True)

    def komisyon(self):
        ortak.kaydedildi(self, belgeler.uret(self.db, "koordinatorluk_komisyon_karari", 1))

    def excel(self):
        yol = ortak.kaydet_yolu(self, "Koordinatörlük Görev Dağılımı.xlsx")
        if yol:
            ortak.kaydedildi(self, raporlar.koordinator_dagilimi(self.db, yol))


class ZiyaretPlani(QWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        ust = QHBoxLayout()
        self.ay = ortak.AySecici()
        self.ay.degisti.connect(lambda *_: self.yenile())
        ust.addWidget(self.ay)
        for metin, fn in [("Aylık Planı Oluştur", self.olustur), ("Plan Çizelgesi (Excel)", self.excel)]:
            b = QPushButton(metin)
            b.clicked.connect(fn)
            ust.addWidget(b)
        ust.addStretch()
        self.istatistik = QLabel()
        ust.addWidget(self.istatistik)
        lay.addLayout(ust)
        v = replace(ZIYARETLER, eylemler=[
            ("Ziyaret Formu Üret (Word)", self._formlar),
            ("Yapıldı Olarak İşaretle", lambda s, ids: self._durum(ids, "Yapıldı")),
            ("Yapılmadı Olarak İşaretle", lambda s, ids: self._durum(ids, "Yapılmadı")),
        ])
        self.crud = CrudSayfasi(db, v)
        lay.addWidget(self.crud, 1)

    def showEvent(self, e):
        super().showEvent(e)
        self.yenile()

    def yenile(self):
        ilk, son = ay_araligi(*self.ay.deger())
        self.crud.ek_kosul = ("tarih BETWEEN ? AND ?", [ilk.isoformat(), son.isoformat()])
        self.crud.yenile()
        ist = koordinator.ziyaret_istatistigi(self.db, *self.ay.deger())
        p = sum(x["planlandi"] or 0 for x in ist)
        y = sum(x["yapildi"] or 0 for x in ist)
        n = sum(x["yapilmadi"] or 0 for x in ist)
        self.istatistik.setText(f"Planlı: {p}   Yapıldı: {y}   Yapılmadı: {n}")

    def olustur(self):
        yil, ay = self.ay.deger()
        n = koordinator.ziyaret_plani_olustur(self.db, yil, ay)
        self.yenile()
        ortak.bilgi(self, f"{AYLAR[ay - 1]} {yil} için {n} ziyaret planlandı (tatil günleri atlandı).")

    def _formlar(self, sayfa, ids):
        if not ids:
            ortak.bilgi(self, "Listeden ziyaret seçiniz.")
            return
        son = None
        for i in ids:
            son = belgeler.uret(self.db, "ziyaret_formu", i)
        ortak.kaydedildi(self, son if len(ids) == 1 else son.parent, coklu=len(ids) > 1)

    def _durum(self, ids, durum):
        for i in ids:
            self.db.update("ziyaretler", i, {"durum": durum})
        self.yenile()

    def excel(self):
        yil, ay = self.ay.deger()
        yol = ortak.kaydet_yolu(self, f"Ziyaret Planı {AYLAR[ay - 1]} {yil}.xlsx")
        if yol:
            ortak.kaydedildi(self, raporlar.ziyaret_plani(self.db, yil, ay, yol))


class KoordinatorSayfasi(QTabWidget):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.addTab(GorevDagilimi(db), "Görev Dağılımı")
        self.addTab(CrudSayfasi(db, KOORDINATOR_GOREVLERI), "Görevleri Düzenle")
        self.addTab(ZiyaretPlani(db), "Ziyaret Planı ve Raporları")
