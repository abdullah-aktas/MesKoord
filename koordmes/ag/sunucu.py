"""MesKoord ağ sunucusu: veritabanını yerel ağdaki diğer MesKoord bilgisayarlarıyla paylaşır.

Her oturum (bağlanan bilgisayardaki program penceresi ya da arka plan işi) sunucuda kendi SQLite
bağlantısına sahiptir; böylece BEGIN/SAVEPOINT/COMMIT davranışı yerel çalışmayla birebir aynıdır ve
SQLite'ın kilitleri eşzamanlı yazmaları sıraya koyar. Kaydedilen her değişiklik bir "olay" olarak
yayınlanır; istemciler uzun bekleme (long-poll) ile olayları anında alır.
"""
from __future__ import annotations

import json
import re
import secrets
import socket
import sqlite3
import ssl
import tempfile
import threading
import time
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from .. import __version__, config, hesaplar, lisans
from ..db import BEKLEME_SN, SCHEMA_VERSION, Database, eski_yedekleri_temizle
from . import protokol as P

YEREL = "sunucu-yerel"
OTURUM_ZAMAN_ASIMI = 15 * 60       # bu kadar sessiz kalan oturum kapatılır
KOPYA_ZAMAN_ASIMI = 5 * 60
ISLEM_ZAMAN_ASIMI = 120            # yarım bırakılan işlem (bağlantısı kopan bilgisayar) geri alınır
CEVRIMICI_SN = 75
AZAMI_HATALI_DENEME = 10
KILIT_SURESI = 5 * 60

_DML = re.compile(r"\b(?:INSERT(?:\s+OR\s+\w+)?\s+INTO|REPLACE\s+INTO|UPDATE(?:\s+OR\s+\w+)?|DELETE\s+FROM)"
                  r"\s+[\"`\[]?(\w+)", re.I)
_GERI_AL = re.compile(r"^\s*ROLLBACK\b(?!.*\bTO\b)", re.I | re.S)
_YASAK = re.compile(r"^\s*(VACUUM|ATTACH|DETACH)\b|\bload_extension\b", re.I)


def degisen_tablolar(sql: str) -> set[str]:
    return {m.lower() for m in _DML.findall(sql or "")}


class _IzlenenBaglanti:
    """Sunucu bilgisayarının kendi bağlantısı: kaydedilen (commit) değişiklikleri sunucuya bildirir."""

    def __init__(self, conn: sqlite3.Connection, bildir: Callable[[set[str]], None]):
        object.__setattr__(self, "_c", conn)
        object.__setattr__(self, "_bildir", bildir)
        object.__setattr__(self, "_tablolar", set())

    def __getattr__(self, ad):
        return getattr(self._c, ad)

    def __setattr__(self, ad, deger):
        setattr(self._c, ad, deger)

    def _isle(self, sql: str) -> None:
        if _GERI_AL.match(sql or ""):
            self._tablolar.clear()
        else:
            self._tablolar.update(degisen_tablolar(sql))
        self._bosalt()

    def _bosalt(self) -> None:
        if not self._c.in_transaction and self._tablolar:
            tablolar = set(self._tablolar)
            self._tablolar.clear()
            self._bildir(tablolar)

    def execute(self, sql, params=()):
        cur = self._c.execute(sql, params)
        self._isle(sql)
        return cur

    def executemany(self, sql, seq):
        cur = self._c.executemany(sql, seq)
        self._isle(sql)
        return cur

    def executescript(self, sql):
        cur = self._c.executescript(sql)
        self._isle(sql)
        return cur

    def commit(self):
        self._c.commit()
        self._bosalt()

    def rollback(self):
        self._c.rollback()
        self._tablolar.clear()

    def __enter__(self):
        self._c.__enter__()
        return self

    def __exit__(self, tur, deger, iz):
        sonuc = self._c.__exit__(tur, deger, iz)
        if tur is None:
            self._bosalt()
        else:
            self._tablolar.clear()
        return sonuc


class SunucuDatabase(Database):
    """Sunucu olan bilgisayarın veritabanı: kendi değişikliklerini ağdaki kullanıcılara duyurur."""

    def __init__(self, path: Path | str | None = None, sunucu: "KoordSunucu | None" = None,
                 kimlik: hesaplar.Kimlik | None = None):
        super().__init__(path, kimlik)
        self.sunucu = sunucu
        self.conn = _IzlenenBaglanti(self.conn, self._bildir)

    def _ham_baglanti(self) -> sqlite3.Connection:
        c = self.conn
        return c._c if isinstance(c, _IzlenenBaglanti) else c

    def kimlik_ata(self, kimlik: hesaplar.Kimlik) -> None:
        super().kimlik_ata(kimlik)
        if self.sunucu is not None:
            self.sunucu.yerel_kullanici = kimlik.ad

    def _bildir(self, tablolar: set[str], tam: bool = False) -> None:
        s = self.sunucu
        if s is not None and s.calisiyor:
            s._veri_olayi(s.yerel_kullanici, s.ad, YEREL, tablolar, tam)

    def kopya(self) -> "SunucuDatabase":
        return SunucuDatabase(self.path, self.sunucu, self.kimlik)

    def geri_yukle(self, kaynak: Path) -> None:
        self.conn.commit()
        src = sqlite3.connect(str(kaynak))
        try:
            src.backup(self.conn._c)
        finally:
            src.close()
        self._init_schema()
        hesaplar.baglantiyi_hazirla(self._ham_baglanti(), self.kimlik)
        self._bildir(set(), tam=True)


class Oturum:
    def __init__(self, sunucu: "KoordSunucu", kimlik: hesaplar.Kimlik, adres: str, istemci: str, ana: bool):
        self.anahtar = secrets.token_urlsafe(32)
        self.kimlik = kimlik
        self.kullanici, self.bilgisayar, self.adres, self.istemci, self.ana = \
            kimlik.ad, kimlik.bilgisayar, adres, istemci, ana
        self.giris = datetime.now()
        self.son_gorulme = self.son_islem = time.monotonic()
        self.kilit = threading.Lock()
        self.tablolar: set[str] = set()
        self.conn = sqlite3.connect(str(sunucu.yol), timeout=BEKLEME_SN, check_same_thread=False)
        self.conn.execute("PRAGMA foreign_keys = ON")
        hesaplar.baglantiyi_hazirla(self.conn, kimlik)

    def kapat(self) -> None:
        with self.kilit:
            try:
                self.conn.rollback()
                self.conn.close()
            except sqlite3.Error:
                pass


class _HttpSunucu(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 64

    def handle_error(self, request, client_address):
        pass


class KoordSunucu:
    def __init__(self, yol: Path | str, parola_ozeti: str, port: int = P.VARSAYILAN_PORT, ad: str = "",
                 host: str = "0.0.0.0", yerel_kullanici: str = "", sertifika_klasoru: Path | None = None):
        if not parola_ozeti:
            raise ValueError("Sunucu parolası belirlenmemiş.")
        self.yol = Path(yol)
        self.parola_ozeti = parola_ozeti
        self.ad = ad or socket.gethostname()
        self.host, self.istenen_port = host, port
        self.yerel_kullanici = yerel_kullanici or P.varsayilan_kullanici()
        self.crt, self.key = P.sertifika_hazirla(sertifika_klasoru)
        self.parmak_izi = P.sertifika_parmak_izi(self.crt)
        self.oturumlar: dict[str, Oturum] = {}
        self._okilit = threading.Lock()
        self._kosul = threading.Condition()
        self._olaylar: deque[dict] = deque(maxlen=1000)
        self.surum = 0
        self.kullanici_surum = 0
        self._son_kullanicilar: list = []
        self._hatalar: dict[str, list[float]] = {}
        self._dinleyiciler: list[Callable[[dict], None]] = []
        self._dur = threading.Event()
        self._httpd: _HttpSunucu | None = None
        self._is_parcaciklari: list[threading.Thread] = []

    # ------------------------------------------------------------ yaşam döngüsü
    @property
    def port(self) -> int:
        return self._httpd.server_address[1] if self._httpd else self.istenen_port

    @property
    def calisiyor(self) -> bool:
        return self._httpd is not None and not self._dur.is_set()

    def baslat(self) -> None:
        with sqlite3.connect(str(self.yol), timeout=BEKLEME_SN) as c:
            c.execute("PRAGMA journal_mode = WAL")
        c.close()
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(str(self.crt), str(self.key))
        httpd = _HttpSunucu((self.host, self.istenen_port), _isleyici_sinifi(self))
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True, do_handshake_on_connect=False)
        self._httpd = httpd
        self._dur.clear()
        for hedef, ad in [(httpd.serve_forever, "koordmes-sunucu"), (self._temizle, "koordmes-temizlik")]:
            t = threading.Thread(target=hedef, name=ad, daemon=True)
            t.start()
            self._is_parcaciklari.append(t)

    def durdur(self) -> None:
        if self._httpd is None:
            return
        self._dur.set()
        with self._kosul:
            self._kosul.notify_all()
        self._httpd.shutdown()
        self._httpd.server_close()
        self._httpd = None
        with self._okilit:
            oturumlar, self.oturumlar = list(self.oturumlar.values()), {}
        for o in oturumlar:
            o.kapat()
        for t in self._is_parcaciklari:
            t.join(timeout=2)
        self._is_parcaciklari.clear()

    # ------------------------------------------------------------ olaylar
    def dinleyici_ekle(self, fn: Callable[[dict], None]) -> None:
        self._dinleyiciler.append(fn)

    def _yayinla(self, olay: dict) -> None:
        with self._kosul:
            if olay["tur"] == "veri":
                self.surum += 1
                olay["no"] = self.surum
                self._olaylar.append(olay)
            else:
                self.kullanici_surum += 1
            self._kosul.notify_all()
        for fn in list(self._dinleyiciler):
            try:
                fn(olay)
            except Exception:  # noqa: BLE001
                pass

    def _veri_olayi(self, kim: str, bilgisayar: str, istemci: str, tablolar, tam: bool = False) -> None:
        self._yayinla({"tur": "veri", "kim": kim, "bilgisayar": bilgisayar, "istemci": istemci,
                       "tablolar": sorted(tablolar), "tam": tam, "zaman": datetime.now().isoformat(" ", "seconds")})

    def kullanicilar(self) -> list[dict]:
        simdi = time.monotonic()
        son: dict[str, Oturum] = {}
        with self._okilit:
            for o in self.oturumlar.values():
                if o.ana and simdi - o.son_gorulme <= CEVRIMICI_SN:
                    if o.istemci not in son or son[o.istemci].son_gorulme < o.son_gorulme:
                        son[o.istemci] = o
        liste = [{"kullanici": self.yerel_kullanici, "bilgisayar": self.ad, "adres": "", "sunucu": True,
                  "giris": ""}]
        liste += sorted(({"kullanici": o.kullanici, "bilgisayar": o.bilgisayar, "adres": o.adres, "sunucu": False,
                          "giris": o.giris.strftime("%H:%M")} for o in son.values()),
                        key=lambda d: (d["kullanici"].lower(), d["bilgisayar"]))
        return liste

    def _kullanicilari_denetle(self) -> None:
        simdiki = [(d["kullanici"], d["bilgisayar"], d["adres"]) for d in self.kullanicilar()]
        if simdiki != self._son_kullanicilar:
            self._son_kullanicilar = simdiki
            self._yayinla({"tur": "kullanicilar"})

    def _temizle(self) -> None:
        while not self._dur.wait(5):
            simdi = time.monotonic()
            with self._okilit:
                adaylar = list(self.oturumlar.items())
            for anahtar, o in adaylar:
                sinir = OTURUM_ZAMAN_ASIMI if o.ana else KOPYA_ZAMAN_ASIMI
                if simdi - o.son_gorulme > sinir:
                    with self._okilit:
                        self.oturumlar.pop(anahtar, None)
                    o.kapat()
                elif simdi - o.son_islem > ISLEM_ZAMAN_ASIMI and o.kilit.acquire(blocking=False):
                    try:
                        if o.conn.in_transaction:
                            o.conn.rollback()
                            o.tablolar.clear()
                    finally:
                        o.kilit.release()
            self._kullanicilari_denetle()

    # ------------------------------------------------------------ istekler
    def _oturum_ac(self, istek: dict, adres: str) -> tuple[int, dict]:
        simdi = time.time()
        denemeler = [t for t in self._hatalar.get(adres, []) if simdi - t < KILIT_SURESI]
        self._hatalar[adres] = denemeler
        if len(denemeler) >= AZAMI_HATALI_DENEME:
            return 429, {"hata": "Çok fazla hatalı parola denemesi. Birkaç dakika sonra yeniden deneyin."}
        kullanici, parola = str(istek.get("kullanici") or "?")[:60], str(istek.get("parola", ""))
        bilgisayar = str(istek.get("bilgisayar") or adres)[:60]
        hesapli = hesaplar.hesaplar_acik_yol(self.yol)
        if hesapli:
            kimlik = hesaplar.dogrula(self.yol, kullanici, parola, bilgisayar)
        else:
            kimlik = hesaplar.Kimlik.varsayilan(kullanici, bilgisayar) \
                if P.parola_dogru(parola, self.parola_ozeti) else None
        if kimlik is None:
            denemeler.append(simdi)
            time.sleep(1)
            return 403, {"hata": "Kullanıcı adı ya da parola yanlış." if hesapli else "Sunucu parolası yanlış.",
                         "hesap": hesapli}
        self._hatalar.pop(adres, None)
        o = Oturum(self, kimlik, adres, str(istek.get("istemci") or secrets.token_hex(8))[:64],
                   bool(istek.get("ana", True)))
        with self._okilit:
            self.oturumlar[o.anahtar] = o
        if o.ana:
            self._kullanicilari_denetle()
        return 200, {"anahtar": o.anahtar, "sunucu_adi": self.ad, "surum": __version__, "sema": SCHEMA_VERSION,
                     "protokol": P.PROTOKOL, "lisanslar": lisans.lisans_metinleri(), "olay_surumu": self.surum,
                     "hesap": hesapli, "kimlik": kimlik.sozluk()}

    def oturum(self, anahtar: str | None) -> Oturum | None:
        with self._okilit:
            o = self.oturumlar.get(anahtar or "")
        if o is not None:
            o.son_gorulme = time.monotonic()
        return o

    def oturumu_kapat(self, anahtar: str) -> None:
        with self._okilit:
            o = self.oturumlar.pop(anahtar, None)
        if o is not None:
            o.kapat()
            self._kullanicilari_denetle()

    def sql(self, o: Oturum, islemler: list[dict]) -> dict:
        sonuclar: list[dict] = []
        cevap: dict = {"sonuclar": sonuclar}
        with o.kilit:
            c = o.conn
            try:
                for i in islemler:
                    t, s = i.get("t"), i.get("s") or ""
                    if t == "c":
                        c.commit()
                        sonuclar.append({})
                        continue
                    if t == "r":
                        c.rollback()
                        o.tablolar.clear()
                        sonuclar.append({})
                        continue
                    if _YASAK.search(s):
                        raise sqlite3.OperationalError("Bu komut ağ üzerinden çalıştırılamaz.")
                    if t == "x":
                        cur = c.execute(s, P.parametre_coz(i.get("p")))
                    elif t == "xm":
                        cur = c.executemany(s, [P.parametre_coz(p) for p in i.get("p") or []])
                    elif t == "xs":
                        cur = c.executescript(s)
                    else:
                        raise sqlite3.ProgrammingError(f"Bilinmeyen işlem: {t}")
                    if _GERI_AL.match(s):
                        o.tablolar.clear()
                    else:
                        o.tablolar |= degisen_tablolar(s)
                    sutunlar = [d[0] for d in cur.description] if cur.description else None
                    satirlar = [[P.deger_kodla(v) for v in r] for r in cur.fetchall()] if sutunlar else []
                    sonuclar.append({"k": sutunlar, "v": satirlar, "l": cur.lastrowid, "n": cur.rowcount})
            except Exception as e:  # noqa: BLE001
                cevap["hata"] = P.hata_kodla(e)
            finally:
                o.son_islem = time.monotonic()
                cevap["it"] = c.in_transaction
                yayinlanacak = None
                if not c.in_transaction and o.tablolar:
                    yayinlanacak, o.tablolar = o.tablolar, set()
        if yayinlanacak:
            self._veri_olayi(o.kullanici, o.bilgisayar, o.istemci, yayinlanacak)
        return cevap

    def bekle(self, o: Oturum, surum: int, kullanici_surum: int) -> dict:
        bitis = time.monotonic() + P.UZUN_BEKLEME_SN
        with self._kosul:
            while (self.surum <= surum and self.kullanici_surum == kullanici_surum and not self._dur.is_set()):
                kalan = bitis - time.monotonic()
                if kalan <= 0:
                    break
                self._kosul.wait(min(kalan, 5))
                o.son_gorulme = time.monotonic()
            olaylar = [e for e in self._olaylar if e["no"] > surum]
            tam = bool(self._olaylar) and surum < self._olaylar[0]["no"] - 1
            cevap = {"surum": self.surum, "kullanici_surum": self.kullanici_surum, "olaylar": olaylar,
                     "tam": tam or surum > self.surum}
        cevap["kullanicilar"] = self.kullanicilar()
        return cevap

    def yedek_al(self, sunucuda_tut: bool) -> tuple[Path, bool]:
        if sunucuda_tut:
            hedef = config.backup_dir() / config.yedek_adi(datetime.now())
        else:
            fd, ad = tempfile.mkstemp(suffix=".db", prefix="meskoord_ag_")
            import os
            os.close(fd)
            hedef = Path(ad)
        src = sqlite3.connect(str(self.yol), timeout=BEKLEME_SN)
        dst = sqlite3.connect(str(hedef))
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
            src.close()
        if sunucuda_tut:
            eski_yedekleri_temizle(hedef.parent)
        return hedef, not sunucuda_tut

    def geri_yukle(self, o: Oturum, veri: bytes) -> None:
        fd, ad = tempfile.mkstemp(suffix=".db", prefix="meskoord_yukle_")
        import os
        with os.fdopen(fd, "wb") as f:
            f.write(veri)
        gecici = Path(ad)
        try:
            try:
                c = sqlite3.connect(str(gecici))
                tamam = c.execute("PRAGMA integrity_check").fetchone()[0] == "ok" and c.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='kurum'").fetchone()
                c.close()
            except sqlite3.Error:
                tamam = False
            if not tamam:
                raise sqlite3.DatabaseError("Gönderilen dosya geçerli bir MesKoord yedeği değil.")
            self.yedek_al(sunucuda_tut=True)
            d = Database(self.yol, o.kimlik)
            try:
                d.geri_yukle(gecici)
            finally:
                d.close()
        finally:
            try:
                gecici.unlink()
            except OSError:
                pass
        self._veri_olayi(o.kullanici, o.bilgisayar, o.istemci, [], tam=True)


def _isleyici_sinifi(sunucu: KoordSunucu):
    class Isleyici(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        timeout = 300
        server_version = P.URUN
        sys_version = ""

        def log_message(self, *a):
            pass

        def _gonder(self, kod: int, veri: dict | bytes, basliklar: dict | None = None) -> None:
            govde = veri if isinstance(veri, bytes) else P.json_baytlari(veri)
            self.send_response(kod)
            self.send_header("Content-Type", "application/octet-stream" if isinstance(veri, bytes)
                             else "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(govde)))
            for k, v in (basliklar or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(govde)

        def _govde(self) -> bytes | None:
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = -1
            if n < 0 or n > P.AZAMI_ISTEK:
                self._gonder(413, {"hata": "İstek çok büyük."})
                self.close_connection = True
                return None
            return self.rfile.read(n) if n else b""

        def do_GET(self):
            self._gonder(404, {"hata": "Bulunamadı"})

        def do_POST(self):
            govde = self._govde()
            if govde is None:
                return
            yol = self.path.split("?", 1)[0]
            adres = self.client_address[0]
            try:
                if yol == "/bilgi":
                    return self._gonder(200, {"urun": P.URUN, "ad": sunucu.ad, "surum": __version__,
                                              "protokol": P.PROTOKOL,
                                              "hesap": hesaplar.hesaplar_acik_yol(sunucu.yol)})
                if yol == "/oturum":
                    kod, cevap = sunucu._oturum_ac(json.loads(govde or b"{}"), adres)
                    return self._gonder(kod, cevap)
                o = sunucu.oturum(self.headers.get("X-Oturum"))
                if o is None:
                    return self._gonder(401, {"hata": "Oturum geçersiz ya da süresi doldu."})
                if yol == "/sql":
                    return self._gonder(200, sunucu.sql(o, json.loads(govde)["islemler"]))
                if yol == "/bekle":
                    istek = json.loads(govde or b"{}")
                    return self._gonder(200, sunucu.bekle(o, int(istek.get("surum", 0)),
                                                          int(istek.get("kullanici_surum", -1))))
                if yol == "/kapat":
                    sunucu.oturumu_kapat(o.anahtar)
                    return self._gonder(200, {})
                if yol == "/yedek":
                    istek = json.loads(govde or b"{}")
                    tut = bool(istek.get("sunucuda_tut"))
                    if not o.kimlik.yonetici:
                        # Yedek dosyası bütün veritabanıdır; yalnızca yönetici indirebilir, diğerleri sunucuda aldırır
                        if not tut:
                            return self._gonder(403, {"hata": "Yedek dosyasını yalnızca yönetici indirebilir."})
                        dosya, _ = sunucu.yedek_al(True)
                        return self._gonder(200, b"", {"X-Yedek-Adi": dosya.name, "X-Yedek-Sunucuda": "1"})
                    dosya, sil = sunucu.yedek_al(tut)
                    try:
                        veri = dosya.read_bytes()
                    finally:
                        if sil:
                            dosya.unlink(missing_ok=True)
                    return self._gonder(200, veri, {"X-Yedek-Adi": dosya.name})
                if yol == "/geri_yukle":
                    if not o.kimlik.yonetici:
                        return self._gonder(403, {"hata": "Yedekten geri yüklemeyi yalnızca yönetici yapabilir."})
                    sunucu.geri_yukle(o, govde)
                    return self._gonder(200, {})
                return self._gonder(404, {"hata": "Bulunamadı"})
            except (ValueError, KeyError, TypeError) as e:
                return self._gonder(400, {"hata": f"Geçersiz istek: {e}"})
            except Exception as e:  # noqa: BLE001
                return self._gonder(500, {"hata": str(e), "sql_hata": P.hata_kodla(e)})

    return Isleyici
