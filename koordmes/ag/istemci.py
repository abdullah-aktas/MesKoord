"""MesKoord ağ istemcisi: sunucudaki ortak veritabanını yerel veritabanı gibi kullandırır.

`UzakBaglanti`, programın kullandığı sqlite3.Connection yüzünü (execute, executemany, executescript,
commit, rollback, `with conn:`) taklit eder; her komut şifreli bağlantıyla sunucuya gider ve sunucudaki
bu oturuma ait SQLite bağlantısında çalışır. Böylece servis ve arayüz kodu değişmeden ağda çalışır.
"""
from __future__ import annotations

import http.client
import json
import socket
import sqlite3
import ssl
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Iterable

from .. import __version__, config, hesaplar, lisans
from ..db import SCHEMA_VERSION, Database, eski_yedekleri_temizle
from . import protokol as P

BOSTA_YENILE_SN = 100  # bu kadar boşta kalan bağlantı yeniden açılır (sunucu boştaki bağlantıyı kapatabilir)
ISTEMCI_NO = uuid.uuid4().hex  # bu programın kimliği (kendi değişikliklerimizi bildirimlerde ayırmak için)


class BaglantiHatasi(Exception):
    pass


class ParmakIziHatasi(BaglantiHatasi):
    def __init__(self, yeni_iz: str, ilk: bool):
        self.yeni_iz, self.ilk = yeni_iz, ilk
        super().__init__(
            "Sunucu ilk kez doğrulanacak." if ilk else
            "Sunucunun kimlik sertifikası değişmiş! Sunucu yeniden kurulmadıysa bu bağlantı güvenli olmayabilir. "
            f"Yeni doğrulama kodu: {P.dogrulama_kodu(yeni_iz)}")


class ParolaHatasi(BaglantiHatasi):
    def __init__(self, mesaj: str, hesap: bool = False):
        super().__init__(mesaj)
        self.hesap = hesap  # sunucuda kişisel kullanıcı hesapları açık


@dataclass
class BaglantiBilgisi:
    adres: str
    port: int = P.VARSAYILAN_PORT
    parola: str = ""
    parmak_izi: str = ""
    kullanici: str = field(default_factory=P.varsayilan_kullanici)
    bilgisayar: str = field(default_factory=socket.gethostname)
    istemci: str = ISTEMCI_NO
    zaman_asimi: float = 60

    @classmethod
    def ayarlardan(cls, a: P.AgAyarlari) -> "BaglantiBilgisi":
        return cls(a.adres, a.sunucu_portu, "" if a.hesap else a.parola, a.parmak_izi,
                   a.kullanici or P.varsayilan_kullanici())


class _Kanal:
    """Sertifika parmak izi sabitlenmiş, kalıcı (keep-alive) HTTPS bağlantısı."""

    def __init__(self, bilgi: BaglantiBilgisi, zaman_asimi: float | None = None):
        self.bilgi = bilgi
        self.zaman_asimi = zaman_asimi or bilgi.zaman_asimi
        self._conn: http.client.HTTPSConnection | None = None
        self._son = 0.0
        self._ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE  # güven, aşağıdaki parmak izi sabitlemesiyle sağlanır

    def _ac(self) -> http.client.HTTPSConnection:
        c = http.client.HTTPSConnection(self.bilgi.adres, self.bilgi.port, timeout=self.zaman_asimi,
                                        context=self._ctx)
        c.connect()
        iz = P.parmak_izi(c.sock.getpeercert(binary_form=True))
        if iz != self.bilgi.parmak_izi:
            c.close()
            raise ParmakIziHatasi(iz, not self.bilgi.parmak_izi)
        return c

    def kapat(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except OSError:
                pass
            self._conn = None

    def istek(self, yol: str, govde: bytes, basliklar: dict | None = None,
              yinelenebilir: bool = False) -> tuple[int, http.client.HTTPMessage, bytes]:
        for deneme in range(2):
            if self._conn is not None and time.monotonic() - self._son > BOSTA_YENILE_SN:
                self.kapat()
            yeni = self._conn is None
            try:
                if yeni:
                    self._conn = self._ac()
            except ParmakIziHatasi:
                raise
            except (OSError, http.client.HTTPException) as e:
                self.kapat()
                raise BaglantiHatasi(f"Sunucuya ulaşılamadı ({self.bilgi.adres}:{self.bilgi.port}): {e}") from e
            try:
                self._conn.request("POST", yol, body=govde,
                                   headers={"Content-Type": "application/json", **(basliklar or {})})
                r = self._conn.getresponse()
                veri = r.read()
                self._son = time.monotonic()
                if r.getheader("Connection", "").lower() == "close":
                    self.kapat()
                return r.status, r.headers, veri
            except (OSError, http.client.HTTPException) as e:
                self.kapat()
                if deneme == 0 and not yeni and yinelenebilir:
                    continue
                raise BaglantiHatasi(f"Sunucu bağlantısı kesildi ({self.bilgi.adres}): {e}") from e
        raise BaglantiHatasi("Sunucuya ulaşılamadı.")


def _hata_metni(veri: bytes) -> str:
    try:
        return json.loads(veri).get("hata") or ""
    except (ValueError, AttributeError):
        return ""


def oturum_ac(kanal: _Kanal, bilgi: BaglantiBilgisi, ana: bool) -> dict:
    kod, _, veri = kanal.istek("/oturum", P.json_baytlari(
        {"parola": bilgi.parola, "kullanici": bilgi.kullanici, "bilgisayar": bilgi.bilgisayar,
         "istemci": bilgi.istemci, "ana": ana, "protokol": P.PROTOKOL, "surum": __version__}), yinelenebilir=True)
    if kod == 403:
        try:
            hesap = bool(json.loads(veri).get("hesap"))
        except (ValueError, AttributeError):
            hesap = False
        raise ParolaHatasi(_hata_metni(veri) or "Sunucu parolası yanlış.", hesap)
    if kod != 200:
        raise BaglantiHatasi(_hata_metni(veri) or f"Sunucu yanıtı: {kod}")
    cevap = json.loads(veri)
    if cevap.get("sema") != SCHEMA_VERSION or str(cevap.get("surum", "")).split(".")[:2] != __version__.split(".")[:2]:
        raise BaglantiHatasi(
            f"Sunucudaki MesKoord sürümü {cevap.get('surum')}, bu bilgisayardaki {__version__}. "
            "Ağdaki bütün bilgisayarlara aynı sürümü kurun.")
    return cevap


def sunucu_bilgisi(adres: str, port: int = P.VARSAYILAN_PORT, zaman_asimi: float = 5) -> tuple[str, dict]:
    """Sunucunun sertifika parmak izi ve tanıtım bilgisi (ilk bağlantıda doğrulama kodunu göstermek için)."""
    kanal = _Kanal(BaglantiBilgisi(adres, port, parmak_izi="?"), zaman_asimi)
    try:
        kanal.istek("/bilgi", b"{}")
    except ParmakIziHatasi as e:
        iz = e.yeni_iz
    finally:
        kanal.kapat()
    kanal.bilgi.parmak_izi = iz
    try:
        kod, _, veri = kanal.istek("/bilgi", b"{}")
        bilgi = json.loads(veri) if kod == 200 else {}
    finally:
        kanal.kapat()
    if bilgi.get("urun") not in P.URUN_ADLARI:
        raise BaglantiHatasi("Bu adreste bir MesKoord sunucusu yok.")
    return iz, bilgi


class UzakImlec:
    arraysize = 1

    def __init__(self, sonuc: dict):
        self._satirlar = P.satirlar(sonuc.get("k"), sonuc.get("v") or [])
        self._i = 0
        k = sonuc.get("k")
        self.description = tuple((ad, None, None, None, None, None, None) for ad in k) if k else None
        self.lastrowid = sonuc.get("l")
        self.rowcount = sonuc.get("n", -1)

    def fetchall(self) -> list[P.Satir]:
        kalan, self._i = self._satirlar[self._i:], len(self._satirlar)
        return kalan

    def fetchone(self) -> P.Satir | None:
        if self._i >= len(self._satirlar):
            return None
        self._i += 1
        return self._satirlar[self._i - 1]

    def fetchmany(self, n: int | None = None) -> list[P.Satir]:
        n = n or self.arraysize
        parca = self._satirlar[self._i:self._i + n]
        self._i += len(parca)
        return parca

    def __iter__(self):
        while (r := self.fetchone()) is not None:
            yield r

    def close(self) -> None:
        self._satirlar = []


class UzakBaglanti:
    """sqlite3.Connection yerine geçen, komutları sunucudaki oturumda çalıştıran bağlantı."""

    def __init__(self, bilgi: BaglantiBilgisi, ana: bool = True):
        self.bilgi, self.ana = bilgi, ana
        self.row_factory = None
        self._kanal = _Kanal(bilgi)
        self._kilit = threading.RLock()
        self._anahtar = ""
        self._it = False
        self._geri_al = False
        self.sunucu: dict = {}
        self.giris()

    def giris(self) -> None:
        with self._kilit:
            self.sunucu = oturum_ac(self._kanal, self.bilgi, self.ana)
            self._anahtar = self.sunucu["anahtar"]
            self._it = self._geri_al = False

    @property
    def in_transaction(self) -> bool:
        return self._it

    def _istek(self, yol: str, govde: bytes, yinelenebilir: bool = False) -> tuple[int, Any, bytes]:
        try:
            return self._kanal.istek(yol, govde, {"X-Oturum": self._anahtar}, yinelenebilir)
        except BaglantiHatasi as e:
            if self._it:
                self._it, self._geri_al = False, True
            raise sqlite3.OperationalError(str(e)) from e

    def _toplu(self, islemler: list[dict]) -> list[dict]:
        with self._kilit:
            if self._geri_al:
                islemler = [{"t": "r"}] + islemler
            for deneme in range(2):
                kod, _, veri = self._istek("/sql", P.json_baytlari({"islemler": islemler}))
                if kod == 401:
                    yarim = self._it or self._geri_al
                    try:
                        self.giris()
                    except BaglantiHatasi as e:
                        raise sqlite3.OperationalError(str(e)) from e
                    if yarim:
                        raise sqlite3.OperationalError(
                            "Sunucuyla oturum zaman aşımına uğradı; yarım kalan işlem geri alındı. Yeniden deneyin.")
                    if deneme == 0:
                        if islemler and islemler[0] == {"t": "r"}:
                            islemler = islemler[1:]
                        continue
                if kod != 200:
                    raise sqlite3.OperationalError(_hata_metni(veri) or f"Sunucu hatası ({kod})")
                break
            cevap = json.loads(veri)
            self._it = bool(cevap.get("it"))
            sonuclar = cevap.get("sonuclar") or []
            if self._geri_al:
                self._geri_al = False
                sonuclar = sonuclar[1:]
            if "hata" in cevap:
                raise P.hata_coz(cevap["hata"])
            return sonuclar

    # --- sqlite3.Connection yüzü ---
    def execute(self, sql: str, params: Any = ()) -> UzakImlec:
        return UzakImlec(self._toplu([{"t": "x", "s": sql, "p": P.parametre_kodla(params)}])[0])

    def executemany(self, sql: str, seq: Iterable[Any]) -> UzakImlec:
        return UzakImlec(self._toplu([{"t": "xm", "s": sql, "p": [P.parametre_kodla(p) for p in seq]}])[0])

    def executescript(self, sql: str) -> UzakImlec:
        return UzakImlec(self._toplu([{"t": "xs", "s": sql}])[0])

    def calistir_ve_kaydet(self, sql: str, params: Any = ()) -> UzakImlec:
        """execute + commit tek gidiş-dönüşte."""
        return UzakImlec(self._toplu([{"t": "x", "s": sql, "p": P.parametre_kodla(params)}, {"t": "c"}])[0])

    def commit(self) -> None:
        if self._it:
            self._toplu([{"t": "c"}])

    def rollback(self) -> None:
        if self._it or self._geri_al:
            self._toplu([{"t": "r"}])

    def __enter__(self):
        return self

    def __exit__(self, tur, deger, iz):
        if tur is None:
            self.commit()
        else:
            try:
                self.rollback()
            except sqlite3.Error:
                pass
        return False

    def cursor(self):
        return _Imlecci(self)

    # --- ek işlemler ---
    def yedek_al(self, sunucuda_tut: bool) -> tuple[bytes | None, str]:
        """(dosya içeriği, ad); yönetici olmayanlarda yedek yalnızca sunucuda kalır ve içerik None döner."""
        with self._kilit:
            kod, basliklar, veri = self._istek("/yedek", P.json_baytlari({"sunucuda_tut": sunucuda_tut}))
            if kod == 401:
                self.giris()
                kod, basliklar, veri = self._istek("/yedek", P.json_baytlari({"sunucuda_tut": sunucuda_tut}))
            if kod != 200:
                raise sqlite3.OperationalError(_hata_metni(veri) or f"Yedek alınamadı ({kod})")
            ad = basliklar.get("X-Yedek-Adi") or "meskoord_sunucu.db"
            return (None if basliklar.get("X-Yedek-Sunucuda") else veri), ad

    def geri_yukle(self, veri: bytes) -> None:
        with self._kilit:
            kod, _, cevap = self._istek("/geri_yukle", veri)
            if kod != 200:
                raise sqlite3.OperationalError(_hata_metni(cevap) or f"Geri yükleme başarısız ({kod})")

    def close(self) -> None:
        with self._kilit:
            if self._anahtar:
                try:
                    self._kanal.istek("/kapat", b"{}", {"X-Oturum": self._anahtar})
                except BaglantiHatasi:
                    pass
                self._anahtar = ""
            self._kanal.kapat()


class _Imlecci:
    """conn.cursor() ile alınan imleç; execute sonrası sonuçları taşır."""

    def __init__(self, conn: UzakBaglanti):
        self._conn = conn
        self._son: UzakImlec | None = None

    def execute(self, sql, params=()):
        self._son = self._conn.execute(sql, params)
        return self

    def executemany(self, sql, seq):
        self._son = self._conn.executemany(sql, seq)
        return self

    def __getattr__(self, ad):
        return getattr(self._son, ad)


class SunucudakiYedek(type(Path())):
    """Yalnızca sunucu bilgisayarındaki yedek klasöründe duran yedeğin adı; bu bilgisayarda dosyası yoktur."""

    def exists(self, *a, **k) -> bool:
        return False


class UzakDatabase(Database):
    """Sunucudaki ortak veritabanı. Database'in bütün yardımcıları aynen çalışır."""
    uzak = True

    def __init__(self, bilgi: BaglantiBilgisi, ana: bool = True):
        self.bilgi = bilgi
        self.path = Path(f"//{bilgi.adres}/{P.URUN}")
        self.conn = UzakBaglanti(bilgi, ana)
        self.kimlik = hesaplar.Kimlik.sozlukten(self.conn.sunucu.get("kimlik"), bilgi.bilgisayar)
        if ana:
            lisans.SUNUCU_LISANSLARI[:] = self.conn.sunucu.get("lisanslar") or []

    def kimlik_ata(self, kimlik: hesaplar.Kimlik) -> None:
        raise NotImplementedError("Ağa bağlı bilgisayarda kullanıcı, sunucuya yeniden bağlanarak değişir.")

    def parola_dogrula(self, parola: str) -> bool:
        try:
            UzakBaglanti(replace(self.bilgi, parola=parola), ana=False).close()
            return True
        except ParolaHatasi:
            return False

    @property
    def sunucu_adi(self) -> str:
        return self.conn.sunucu.get("sunucu_adi") or self.bilgi.adres

    @property
    def konum(self) -> str:
        return f"{self.sunucu_adi} sunucusundaki ortak veritabanı ({self.bilgi.adres}:{self.bilgi.port})"

    def kopya(self) -> "UzakDatabase":
        return UzakDatabase(self.bilgi, ana=False)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        if self.conn.in_transaction:
            cur = self.conn.execute(sql, tuple(params))
            self.conn.commit()
            return cur.lastrowid
        return self.conn.calistir_ve_kaydet(sql, tuple(params)).lastrowid

    def yedekle(self, hedef: Path | None = None) -> Path:
        """Hedef verilmezse sunucuda otomatik yedek alınır, bir kopyası bu bilgisayarın yedek klasörüne iner."""
        self.conn.commit()
        veri, ad = self.conn.yedek_al(sunucuda_tut=hedef is None)
        otomatik = hedef is None
        if veri is None:
            return SunucudakiYedek(ad)
        if otomatik:
            hedef = config.backup_dir() / ad
        Path(hedef).write_bytes(veri)
        if otomatik:
            eski_yedekleri_temizle(Path(hedef).parent)
        return Path(hedef)

    def geri_yukle(self, kaynak: Path) -> None:
        self.conn.commit()
        self.conn.geri_yukle(Path(kaynak).read_bytes())

    def close(self) -> None:
        self.conn.close()


class OlayDinleyici(threading.Thread):
    """Sunucudaki değişiklikleri uzun bekleme (long-poll) ile anında alır; bağlantı koparsa yeniden dener."""

    def __init__(self, bilgi: BaglantiBilgisi, olay: Callable[[dict], None], durum: Callable[[bool, str], None]):
        super().__init__(name="koordmes-dinleyici", daemon=True)
        self.bilgi, self._olay, self._durum = bilgi, olay, durum
        self._dur = threading.Event()
        self._kanal = _Kanal(bilgi, P.UZUN_BEKLEME_SN + 20)
        self.bagli = False
        self.kullanicilar: list[dict] = []

    def durdur(self) -> None:
        self._dur.set()
        self._kanal.kapat()

    def run(self) -> None:
        anahtar, surum, ksurum, bekleme = "", 0, -1, 1.0
        while not self._dur.is_set():
            try:
                if not anahtar:
                    cevap = oturum_ac(self._kanal, self.bilgi, ana=True)
                    anahtar = cevap["anahtar"]
                    if self.bagli is False and surum:
                        self._olay({"olaylar": [], "tam": True})
                    surum = surum or cevap.get("olay_surumu", 0)
                kod, _, veri = self._kanal.istek("/bekle", P.json_baytlari(
                    {"surum": surum, "kullanici_surum": ksurum}), {"X-Oturum": anahtar}, yinelenebilir=True)
                if kod == 401:
                    anahtar = ""
                    continue
                if kod != 200:
                    raise BaglantiHatasi(_hata_metni(veri) or f"Sunucu yanıtı: {kod}")
                cevap = json.loads(veri)
                if not self.bagli:
                    self.bagli = True
                    self._durum(True, "")
                bekleme = 1.0
                yeni_k = cevap.get("kullanicilar") or []
                if cevap.get("kullanici_surum") != ksurum or yeni_k != self.kullanicilar:
                    self.kullanicilar = yeni_k
                    ksurum = cevap.get("kullanici_surum", ksurum)
                    self._durum(True, "")
                olaylar = [o for o in cevap.get("olaylar") or [] if o.get("istemci") != self.bilgi.istemci]
                if cevap.get("tam") and cevap.get("surum", 0) < surum:
                    olaylar.append({"tam": True})
                surum = cevap.get("surum", surum)
                if olaylar or cevap.get("tam"):
                    self._olay({"olaylar": olaylar, "tam": bool(cevap.get("tam"))})
            except Exception as e:  # noqa: BLE001
                if self._dur.is_set():
                    break
                anahtar = ""
                if self.bagli or bekleme == 1.0:
                    self.bagli = False
                    self._durum(False, str(e))
                self._dur.wait(bekleme)
                bekleme = min(bekleme * 2, 15)
        if anahtar:
            try:
                self._kanal.istek("/kapat", b"{}", {"X-Oturum": anahtar})
            except Exception:  # noqa: BLE001
                pass
        self._kanal.kapat()
