"""Yerel ağdaki MesKoord sunucularını bulma (UDP yayını). Yalnızca ad/adres/port bilgisi paylaşılır."""
from __future__ import annotations

import ipaddress
import json
import socket
import threading
import time

from .. import __version__
from . import protokol as P


class KesifYanitlayici:
    """Sunucu tarafı: keşif isteklerine sunucunun adı ve portuyla yanıt verir."""

    def __init__(self, ad: str, port: int, kesif_portu: int = P.KESIF_PORTU):
        self.ad, self.port, self.kesif_portu = ad, port, kesif_portu
        self._sok: socket.socket | None = None
        self._dur = threading.Event()

    def baslat(self) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind(("", self.kesif_portu))
            s.settimeout(0.5)
        except OSError:
            return False
        self._sok = s
        threading.Thread(target=self._dongu, name="meskoord-kesif", daemon=True).start()
        return True

    def _dongu(self) -> None:
        yanit = P.json_baytlari({"urun": P.URUN, "ad": self.ad, "port": self.port, "surum": __version__})
        while not self._dur.is_set():
            try:
                veri, adres = self._sok.recvfrom(512)
            except socket.timeout:
                continue
            except OSError:
                break
            if veri in P.KESIF_ISTEKLERI:
                try:
                    self._sok.sendto(yanit, adres)
                except OSError:
                    pass

    def durdur(self) -> None:
        self._dur.set()
        if self._sok is not None:
            self._sok.close()
            self._sok = None


def _yayin_adresleri() -> list[str]:
    adresler = {"255.255.255.255"}
    for a in P.yerel_adresler():
        try:
            adresler.add(str(ipaddress.ip_network(f"{a}/24", strict=False).broadcast_address))
        except ValueError:
            pass
    return sorted(adresler)


def kesfet(sure: float = 1.5, kesif_portu: int = P.KESIF_PORTU, ek_adresler: list[str] | None = None) -> list[dict]:
    """Ağdaki sunucuları döndürür: [{"ad", "adres", "port", "surum"}]."""
    bulunan: dict[tuple[str, int], dict] = {}
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(0.2)
        for hedef in _yayin_adresleri() + list(ek_adresler or []):
            try:
                s.sendto(P.KESIF_ISTEGI, (hedef, kesif_portu))
            except OSError:
                pass
        bitis = time.monotonic() + sure
        while time.monotonic() < bitis:
            try:
                veri, (adres, _) = s.recvfrom(2048)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                d = json.loads(veri)
            except ValueError:
                continue
            if isinstance(d, dict) and d.get("urun") in P.URUN_ADLARI:
                d["adres"] = adres
                bulunan[(adres, int(d.get("port") or P.VARSAYILAN_PORT))] = d
    finally:
        s.close()
    return sorted(bulunan.values(), key=lambda d: (str(d.get("ad")), d["adres"]))
