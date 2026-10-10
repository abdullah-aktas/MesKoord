"""Kişisel kullanıcı hesapları, roller ve işlem günlüğü.

Hesaplar isteğe bağlıdır: ilk yönetici hesabı oluşturulunca açılır ve bundan sonra herkes kendi kullanıcı adı
ve parolasıyla girer. Hesap yokken program eskisi gibi çalışır (herkes tam yetkili).

Yetkiler veritabanı bağlantısının kendisinde, SQLite yetkilendirme geri çağrısıyla uygulanır: ağda sunucudaki
oturum bağlantısında, tek bilgisayarda yerel bağlantıda. Böylece servis ve ekran kodu değişmeden her yazma
denetlenir. İşlem günlüğü her bağlantıya o kullanıcının adıyla kurulan geçici (TEMP) tetikleyicilerle tutulur;
veritabanı dosyasına kalıcı tetikleyici eklenmez, eski sürümler ve başka araçlar dosyayı aynen açar.
"""
from __future__ import annotations

import socket
import sqlite3
from dataclasses import dataclass, field, replace
from pathlib import Path

from .ag.protokol import parola_dogru, parola_ozeti, varsayilan_kullanici

YONETICI, PERSONEL, IZLEYICI = "yonetici", "personel", "izleyici"
ROLLER = {YONETICI: "Yönetici", PERSONEL: "Personel", IZLEYICI: "Salt okunur"}
ROL_ACIKLAMALARI = {
    YONETICI: "Bütün işlemler; kullanıcı hesapları, kurum bilgileri, mevzuat parametreleri, yedekten geri "
              "yükleme ve işlem günlüğü.",
    PERSONEL: "Bütün veri girişleri, aktarım, hesaplar ve belge üretimi. Kullanıcı hesaplarını, kurum bilgilerini "
              "ve mevzuat parametrelerini değiştiremez; yedekten geri yükleyemez.",
    IZLEYICI: "Ekranları görür, listeleri ve belgeleri dosyaya alır; hiçbir kaydı değiştiremez.",
}
EN_KISA_PAROLA = 6
GUNLUK_SAKLAMA_GUN = 730
GUNLUK_ON_EKI = "kg_"
YETKI_YOK = "Bu işlem için yetkiniz yok."

GUNLUGE_GIRMEYEN = {"meta", "islem_gunlugu", "program_hucreleri"}
GIZLI_KOLONLAR = {"tc", "iban", "telefon", "veli_tel", "adres", "eposta", "dogum_tarihi", "vergi_no",
                  "usta_ogretici_tel", "parola_ozeti", "agir_disiplin", "oncelikli"}
YONETICI_TABLOLARI = {"kurum", "ayarlar"}
_OGRENCI = "(SELECT ad || ' ' || soyad FROM ogrenciler WHERE id = {r}.ogrenci_id)"
_OGRETMEN = "(SELECT ad || ' ' || soyad FROM ogretmenler WHERE id = {r}.ogretmen_id)"
_ISLETME = "(SELECT ad FROM isletmeler WHERE id = {r}.isletme_id)"
KAYIT_ADI = {
    "ogrenciler": "{r}.ad || ' ' || {r}.soyad",
    "ogretmenler": "{r}.ad || ' ' || {r}.soyad",
    "kullanicilar": "{r}.ad_soyad || ' (' || {r}.kullanici_adi || ')'",
    "ayarlar": "{r}.anahtar",
    "kurum": "'Kurum bilgileri'",
    "yerlestirmeler": _OGRENCI + " || ' / ' || ifnull(" + _ISLETME + ", '')",
    "devamsizlik": _OGRENCI + " || ' / ' || {r}.tarih",
    "beceri_notlari": _OGRENCI + " || ' / ' || {r}.donem || '. dönem'",
    "ek_ders_kayitlari": _OGRETMEN + " || ' / ' || {r}.tarih",
    "koordinator_gorevleri": _OGRETMEN + " || ' / ' || ifnull(" + _ISLETME + ", '')",
    "ziyaretler": "ifnull(" + _ISLETME + ", '') || ' / ' || {r}.tarih",
    "aylik_odemeler": "{r}.donem || ' / ' || ifnull((SELECT o.ad || ' ' || o.soyad FROM yerlestirmeler y "
                      "JOIN ogrenciler o ON o.id = y.ogrenci_id WHERE y.id = {r}.yerlestirme_id), '')",
    "ders_atamalari": "ifnull((SELECT ad FROM siniflar WHERE id = {r}.sinif_id), '') || ' / ' || "
                      "ifnull((SELECT ad FROM dersler WHERE id = {r}.ders_id), '')",
    "evrak": "{r}.sayi || ' ' || {r}.konu",
    "isletme_talepleri": "ifnull(" + _ISLETME + ", '') || ' / ' || ifnull({r}.tarih, '')",
    "anketler": "{r}.tur || ' / ' || ifnull(" + _OGRENCI + ", ifnull(" + _ISLETME + ", ''))",
    "hizmetici_egitimler": "{r}.konu || ' / ' || ifnull({r}.tarih, '')",
}
ISLEMLER = {"INSERT": ("Ekleme", "NEW"), "UPDATE": ("Değişiklik", "NEW"), "DELETE": ("Silme", "OLD")}


@dataclass(frozen=True)
class Kimlik:
    """Bağlantıyı kullanan kişi. Hesaplar kapalıyken herkes `YONETICI` yetkisindedir."""
    ad: str
    rol: str = YONETICI
    kullanici_adi: str = ""
    id: int | None = None
    bilgisayar: str = field(default_factory=socket.gethostname)
    hesapli: bool = False
    parola_degistirmeli: bool = False

    @classmethod
    def varsayilan(cls, ad: str = "", bilgisayar: str = "") -> "Kimlik":
        return cls(ad or varsayilan_kullanici(), bilgisayar=bilgisayar or socket.gethostname())

    @property
    def yonetici(self) -> bool:
        return self.rol == YONETICI

    @property
    def rol_adi(self) -> str:
        return ROLLER.get(self.rol, self.rol)

    def sozluk(self) -> dict:
        return {"ad": self.ad, "rol": self.rol, "kullanici_adi": self.kullanici_adi, "id": self.id,
                "hesapli": self.hesapli, "parola_degistirmeli": self.parola_degistirmeli}

    @classmethod
    def sozlukten(cls, d: dict | None, bilgisayar: str = "") -> "Kimlik":
        if not d:
            return cls.varsayilan(bilgisayar=bilgisayar)
        return cls(str(d.get("ad") or varsayilan_kullanici()), str(d.get("rol") or YONETICI),
                   str(d.get("kullanici_adi") or ""), d.get("id"), bilgisayar or socket.gethostname(),
                   bool(d.get("hesapli")), bool(d.get("parola_degistirmeli")))


def yetki_hatasi_mi(e: BaseException) -> bool:
    return isinstance(e, sqlite3.DatabaseError) and "not authorized" in str(e)


# ---------------------------------------------------------------- bağlantı hazırlığı

def _metin(s: str) -> str:
    return "'" + str(s).replace("'", "''") + "'"


def _deger(r: str, kolon: str) -> str:
    if kolon in GIZLI_KOLONLAR:
        return f"CASE WHEN ifnull({r}.\"{kolon}\", '') = '' THEN '' ELSE '***' END"
    return f"substr({r}.\"{kolon}\", 1, 80)"


def _tetikleyiciler(conn: sqlite3.Connection, kimlik: Kimlik) -> list[str]:
    tablolar = [r[0] for r in conn.execute(
        "SELECT name FROM main.sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        if r[0] not in GUNLUGE_GIRMEYEN]
    kim, pc = _metin(kimlik.ad), _metin(kimlik.bilgisayar)
    komutlar = []
    for t in tablolar:
        kolonlar = [r[1] for r in conn.execute(f'PRAGMA main.table_info("{t}")')]
        ad = KAYIT_ADI.get(t, "{r}.ad" if "ad" in kolonlar else "''")
        for olay, (islem, r) in ISLEMLER.items():
            kosul, ayrinti = "", "''"
            if olay == "UPDATE":
                degisen = [f'OLD."{k}" IS NOT NEW."{k}"' for k in kolonlar]
                kosul = "WHEN " + " OR ".join(degisen)
                parcalar = [f"SELECT '{k}' k, json_array({_deger('OLD', k)}, {_deger('NEW', k)}) v "
                            f"WHERE {d}" for k, d in zip(kolonlar, degisen)]
                ayrinti = "(SELECT json_group_object(k, json(v)) FROM (" + " UNION ALL ".join(parcalar) + "))"
            komutlar.append(
                f'CREATE TEMP TRIGGER "{GUNLUK_ON_EKI}{t}_{olay[0].lower()}" AFTER {olay} ON main."{t}" {kosul} '
                "BEGIN INSERT INTO islem_gunlugu (zaman, kullanici, bilgisayar, islem, tablo, kayit_id, kayit, "
                f"ayrinti) VALUES (datetime('now', 'localtime'), {kim}, {pc}, '{islem}', '{t}', {r}.rowid, "
                f"ifnull({ad.format(r=r)}, ''), {ayrinti}); END")
    if not kimlik.yonetici:
        kendi = kimlik.id if kimlik.id is not None else -1
        komutlar.append(
            f'CREATE TEMP TRIGGER "{GUNLUK_ON_EKI}kendi_parolasi" BEFORE UPDATE ON main.kullanicilar '
            f"WHEN OLD.id <> {int(kendi)} BEGIN SELECT RAISE(ABORT, 'Yalnızca kendi parolanızı "
            "değiştirebilirsiniz.'); END")
    return komutlar


def baglantiyi_hazirla(conn: sqlite3.Connection, kimlik: Kimlik) -> None:
    """Bağlantıya kimliğin işlem günlüğü tetikleyicilerini kurar ve rolünün yetkilerini uygular."""
    conn.set_authorizer(None)
    if conn.in_transaction:
        conn.commit()
    for (ad,) in conn.execute("SELECT name FROM temp.sqlite_master WHERE type = 'trigger' AND name LIKE ? "
                              "ESCAPE '!'", (GUNLUK_ON_EKI.replace("_", "!_") + "%",)).fetchall():
        conn.execute(f'DROP TRIGGER temp."{ad}"')
    for komut in _tetikleyiciler(conn, kimlik):
        conn.execute(komut)
    conn.set_authorizer(yetkilendirici(kimlik.rol))


_YAZMA = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE}
_SILME_DDL = {sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_DROP_TRIGGER,
              sqlite3.SQLITE_DROP_VIEW, sqlite3.SQLITE_ALTER_TABLE}
_HER_ZAMAN_YASAK = {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
                    sqlite3.SQLITE_DROP_TEMP_TRIGGER}


def yetkilendirici(rol: str):
    yonetici, izleyici = rol == YONETICI, rol == IZLEYICI

    def yetki(eylem, a1, a2, vt, tetikleyici):
        if eylem in _HER_ZAMAN_YASAK:
            return sqlite3.SQLITE_DENY
        if eylem == sqlite3.SQLITE_READ:
            gizli = (a1, a2) == ("kullanicilar", "parola_ozeti") and not (tetikleyici or "").startswith(GUNLUK_ON_EKI)
            return sqlite3.SQLITE_IGNORE if gizli else sqlite3.SQLITE_OK
        if eylem in _YAZMA:
            if vt == "temp" or (a1 or "").startswith("sqlite_"):
                return sqlite3.SQLITE_OK
            if a1 == "islem_gunlugu":
                ok = eylem == sqlite3.SQLITE_INSERT and (tetikleyici or "").startswith(GUNLUK_ON_EKI)
                return sqlite3.SQLITE_OK if ok else sqlite3.SQLITE_DENY
            if yonetici:
                return sqlite3.SQLITE_OK
            if a1 == "kullanicilar":
                ok = eylem == sqlite3.SQLITE_UPDATE and a2 in ("parola_ozeti", "parola_degistirmeli")
                return sqlite3.SQLITE_OK if ok else sqlite3.SQLITE_DENY
            if izleyici or a1 in YONETICI_TABLOLARI:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        if eylem in _SILME_DDL and not yonetici:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    return yetki


def gunlugu_temizle(yol: Path | str, gun: int = GUNLUK_SAKLAMA_GUN) -> None:
    """Saklama süresini aşan işlem günlüğü kayıtlarını siler (yalnızca veritabanının durduğu bilgisayarda)."""
    try:
        c = sqlite3.connect(str(yol), timeout=10)
        try:
            with c:
                c.execute("DELETE FROM islem_gunlugu WHERE zaman < datetime('now', 'localtime', ?)", (f"-{gun} days",))
        finally:
            c.close()
    except sqlite3.Error:
        pass


# ---------------------------------------------------------------- hesaplar

def hesaplar_acik(db) -> bool:
    return db.q1("SELECT 1 FROM kullanicilar WHERE aktif = 1 AND rol = ? LIMIT 1", (YONETICI,)) is not None


def hesaplar_acik_yol(yol: Path | str) -> bool:
    c = sqlite3.connect(str(yol), timeout=10)
    try:
        return c.execute("SELECT 1 FROM kullanicilar WHERE aktif = 1 AND rol = ? LIMIT 1", (YONETICI,)).fetchone() \
            is not None
    except sqlite3.OperationalError:
        return False
    finally:
        c.close()


def dogrula(yol: Path | str, kullanici_adi: str, parola: str, bilgisayar: str = "") -> Kimlik | None:
    """Kullanıcı adı ve parolayı denetler (yetki kısıtı olmayan ayrı bir bağlantıyla)."""
    c = sqlite3.connect(str(yol), timeout=10)
    try:
        r = c.execute("SELECT id, ad_soyad, rol, parola_ozeti, parola_degistirmeli FROM kullanicilar "
                      "WHERE kullanici_adi = ? COLLATE NOCASE AND aktif = 1", (kullanici_adi.strip(),)).fetchone()
        if r is None or not parola or not parola_dogru(parola, r[3] or ""):
            return None
        with c:
            c.execute("UPDATE kullanicilar SET son_giris = datetime('now', 'localtime') WHERE id = ?", (r[0],))
        return Kimlik(r[1], r[2], kullanici_adi.strip(), r[0], bilgisayar or socket.gethostname(), True, bool(r[4]))
    except sqlite3.OperationalError:
        return None
    finally:
        c.close()


def kullanicilar(db) -> list:
    return db.q("SELECT id, kullanici_adi, ad_soyad, rol, aktif, parola_degistirmeli, son_giris FROM kullanicilar "
                "ORDER BY aktif DESC, ad_soyad")


def _denetle(kullanici_adi: str, ad_soyad: str, rol: str, parola: str | None) -> None:
    if not kullanici_adi.strip() or not ad_soyad.strip():
        raise ValueError("Ad soyad ve kullanıcı adı boş olamaz.")
    if any(ch.isspace() for ch in kullanici_adi.strip()):
        raise ValueError("Kullanıcı adında boşluk olamaz (ör. ayse.yilmaz).")
    if rol not in ROLLER:
        raise ValueError(f"Bilinmeyen rol: {rol}")
    if parola is not None and len(parola) < EN_KISA_PAROLA:
        raise ValueError(f"Parola en az {EN_KISA_PAROLA} karakter olmalı.")


def kullanici_ekle(db, ad_soyad: str, kullanici_adi: str, rol: str, parola: str, degistirmeli: bool = True) -> int:
    _denetle(kullanici_adi, ad_soyad, rol, parola)
    if db.q1("SELECT 1 FROM kullanicilar WHERE kullanici_adi = ? COLLATE NOCASE", (kullanici_adi.strip(),)):
        raise ValueError(f"'{kullanici_adi.strip()}' kullanıcı adı zaten var.")
    return db.insert("kullanicilar", {"ad_soyad": ad_soyad.strip(), "kullanici_adi": kullanici_adi.strip(),
                                      "rol": rol, "parola_ozeti": parola_ozeti(parola),
                                      "parola_degistirmeli": int(degistirmeli), "aktif": 1})


def _yonetici_kalir(db, kullanici_id: int, rol: str, aktif: bool) -> bool:
    if rol == YONETICI and aktif:
        return True
    r = db.q1("SELECT COUNT(*) n FROM kullanicilar WHERE aktif = 1 AND rol = ? AND id <> ?", (YONETICI, kullanici_id))
    return r["n"] > 0


def kullanici_guncelle(db, kullanici_id: int, ad_soyad: str, rol: str, aktif: bool) -> None:
    eski = db.q1("SELECT kullanici_adi FROM kullanicilar WHERE id = ?", (kullanici_id,))
    if eski is None:
        raise ValueError("Kullanıcı bulunamadı.")
    _denetle(eski["kullanici_adi"], ad_soyad, rol, None)
    if not _yonetici_kalir(db, kullanici_id, rol, aktif):
        raise ValueError("En az bir etkin yönetici hesabı kalmalı. Önce başka bir kullanıcıyı yönetici yapın "
                         "ya da hesapları tümüyle kapatın.")
    db.update("kullanicilar", kullanici_id, {"ad_soyad": ad_soyad.strip(), "rol": rol, "aktif": int(aktif)})


def parola_ata(db, kullanici_id: int, parola: str, degistirmeli: bool = False) -> None:
    if len(parola) < EN_KISA_PAROLA:
        raise ValueError(f"Parola en az {EN_KISA_PAROLA} karakter olmalı.")
    db.execute("UPDATE kullanicilar SET parola_ozeti = ?, parola_degistirmeli = ? WHERE id = ?",
               (parola_ozeti(parola), int(degistirmeli), kullanici_id))


def hesaplari_ac(db, ad_soyad: str, kullanici_adi: str, parola: str) -> Kimlik:
    """İlk yönetici hesabını oluşturur (aynı kullanıcı adı varsa yönetici yapıp etkinleştirir)."""
    _denetle(kullanici_adi, ad_soyad, YONETICI, parola)
    r = db.q1("SELECT id FROM kullanicilar WHERE kullanici_adi = ? COLLATE NOCASE", (kullanici_adi.strip(),))
    if r is None:
        kid = kullanici_ekle(db, ad_soyad, kullanici_adi, YONETICI, parola, degistirmeli=False)
    else:
        kid = r["id"]
        db.update("kullanicilar", kid, {"ad_soyad": ad_soyad.strip(), "rol": YONETICI, "aktif": 1})
        parola_ata(db, kid, parola)
    return Kimlik(ad_soyad.strip(), YONETICI, kullanici_adi.strip(), kid, db.kimlik.bilgisayar, True)


def hesaplari_kapat(db) -> None:
    db.execute("UPDATE kullanicilar SET aktif = 0")


def kendi_parolasini_degistir(db, eski: str | None, yeni: str) -> Kimlik:
    """Oturumdaki kullanıcının parolası. Eski parola, yerelde ayrı bağlantıyla; ağda yeniden girişle denetlenir."""
    k = db.kimlik
    if k.id is None:
        raise ValueError("Kişisel hesapla giriş yapılmamış.")
    if eski is not None and not _eski_parola_dogru(db, k, eski):
        raise ValueError("Şu anki parolanız yanlış.")
    parola_ata(db, k.id, yeni)
    if db.uzak:
        db.bilgi.parola = yeni  # arka plan bağlantıları ve olay dinleyicisi aynı bilgiyi kullanır
    yeni_kimlik = replace(k, parola_degistirmeli=False)
    db.kimlik = yeni_kimlik
    return yeni_kimlik


def _eski_parola_dogru(db, k: Kimlik, eski: str) -> bool:
    if not db.uzak:
        r = sqlite3.connect(str(db.path), timeout=10)
        try:
            row = r.execute("SELECT parola_ozeti FROM kullanicilar WHERE id = ?", (k.id,)).fetchone()
        finally:
            r.close()
        return bool(row) and parola_dogru(eski, row[0] or "")
    return db.parola_dogrula(eski)
