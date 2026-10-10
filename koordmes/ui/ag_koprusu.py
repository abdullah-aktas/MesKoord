"""Ağ olaylarını (başka bilgisayardaki değişiklik, bağlanan/ayrılan kullanıcılar) Qt sinyallerine çevirir."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..ag import protokol as P
from ..ag.istemci import OlayDinleyici, UzakDatabase
from ..ag.kesif import KesifYanitlayici
from ..ag.sunucu import YEREL, KoordSunucu


class AgKoprusu(QObject):
    degisti = Signal(dict)
    durum_degisti = Signal()

    def __init__(self, kip: str, sunucu: KoordSunucu | None = None, kesif: KesifYanitlayici | None = None,
                 db: UzakDatabase | None = None):
        super().__init__()
        self.kip, self.sunucu, self.kesif, self.db = kip, sunucu, kesif, db
        self.dinleyici: OlayDinleyici | None = None
        self.hata = ""
        if sunucu is not None:
            sunucu.dinleyici_ekle(self._sunucu_olayi)
        if db is not None:
            self.dinleyici = OlayDinleyici(db.bilgi, self.degisti.emit, self._istemci_durumu)
            self.dinleyici.start()

    @classmethod
    def sunucu_olarak(cls, sunucu: KoordSunucu, kesif: KesifYanitlayici | None) -> "AgKoprusu":
        return cls(P.KIP_SUNUCU, sunucu=sunucu, kesif=kesif)

    @classmethod
    def istemci_olarak(cls, db: UzakDatabase) -> "AgKoprusu":
        return cls(P.KIP_ISTEMCI, db=db)

    def _sunucu_olayi(self, olay: dict) -> None:
        if olay.get("tur") == "kullanicilar":
            self.durum_degisti.emit()
        elif olay.get("istemci") != YEREL:
            self.degisti.emit({"olaylar": [olay], "tam": olay.get("tam", False)})

    def _istemci_durumu(self, bagli: bool, hata: str) -> None:
        self.hata = "" if bagli else hata
        self.durum_degisti.emit()

    # --- ana pencerenin kullandığı yüz ---
    def kullanicilar(self) -> list[dict]:
        if self.sunucu is not None:
            return self.sunucu.kullanicilar()
        return list(self.dinleyici.kullanicilar) if self.dinleyici else []

    def kullanici_listesi(self) -> list[str]:
        return [f"{k['kullanici']} — {k['bilgisayar']}" + (" (sunucu)" if k.get("sunucu") else "")
                for k in self.kullanicilar()]

    def bagli(self) -> bool:
        if self.sunucu is not None:
            return self.sunucu.calisiyor
        return bool(self.dinleyici and self.dinleyici.bagli)

    def durum_metni(self) -> tuple[str, bool]:
        n = len(self.kullanicilar())
        if self.sunucu is not None:
            if not self.sunucu.calisiyor:
                return "Sunucu kapalı", False
            return f"Sunucu açık • {n} kullanıcı çevrim içi", True
        ad = self.db.sunucu_adi if self.db is not None else "?"
        if not self.bagli():
            return f"{ad} sunucusuyla bağlantı yok — yeniden deneniyor", False
        return f"{ad} sunucusuna bağlı • {n} kullanıcı çevrim içi", True

    def cikis_uyarisi(self) -> str:
        if self.sunucu is None:
            return ""
        digerleri = [k for k in self.kullanicilar() if not k.get("sunucu")]
        if not digerleri:
            return ""
        adlar = ", ".join(f"{k['kullanici']} ({k['bilgisayar']})" for k in digerleri[:5])
        return (f"Bu bilgisayar sunucu ve şu anda {len(digerleri)} kullanıcı bağlı: {adlar}. Programı kapatırsanız "
                "onların bağlantısı kesilir; kaydedilmemiş işlemleri kaybolabilir. Önce haber vermeniz önerilir.")

    def kapat(self) -> None:
        if self.dinleyici is not None:
            self.dinleyici.durdur()
            self.dinleyici = None
        if self.kesif is not None:
            self.kesif.durdur()
            self.kesif = None
        if self.sunucu is not None:
            self.sunucu.durdur()
