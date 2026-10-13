"""SQLite veritabanı erişimi ve şema."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from . import config, hesaplar
from .mevzuat import PARAMETRELER, PARAMETRE_SOZLUK

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (anahtar TEXT PRIMARY KEY, deger TEXT);
CREATE TABLE IF NOT EXISTS ayarlar (anahtar TEXT PRIMARY KEY, deger TEXT);

CREATE TABLE IF NOT EXISTS kurum (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    ad TEXT DEFAULT '', tur TEXT DEFAULT 'MTAL', kurum_kodu TEXT DEFAULT '',
    il TEXT DEFAULT '', ilce TEXT DEFAULT '', buyuksehir INTEGER DEFAULT 0,
    mudur TEXT DEFAULT '', koordinator_mudur_yrd TEXT DEFAULT '',
    sgk_isyeri_sicil TEXT DEFAULT '', adres TEXT DEFAULT '', telefon TEXT DEFAULT '',
    eposta TEXT DEFAULT '', egitim_yili TEXT DEFAULT '2026-2027'
);

CREATE TABLE IF NOT EXISTS alanlar (
    id INTEGER PRIMARY KEY, ad TEXT NOT NULL, kod TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS dallar (
    id INTEGER PRIMARY KEY, alan_id INTEGER REFERENCES alanlar(id) ON DELETE CASCADE,
    ad TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS siniflar (
    id INTEGER PRIMARY KEY, ad TEXT NOT NULL, seviye INTEGER DEFAULT 9,
    program TEXT DEFAULT 'MTAL-AMP',
    alan_id INTEGER REFERENCES alanlar(id) ON DELETE SET NULL,
    dal_id INTEGER REFERENCES dallar(id) ON DELETE SET NULL,
    okul_gunleri TEXT DEFAULT '1,2,3,4,5', isletme_gunleri TEXT DEFAULT '',
    rehber_ogretmen_id INTEGER REFERENCES ogretmenler(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS ogretmenler (
    id INTEGER PRIMARY KEY, tc TEXT DEFAULT '', ad TEXT NOT NULL, soyad TEXT NOT NULL,
    brans TEXT DEFAULT '', alan_id INTEGER REFERENCES alanlar(id) ON DELETE SET NULL,
    unvan TEXT DEFAULT 'Öğretmen', telefon TEXT DEFAULT '', eposta TEXT DEFAULT '',
    aylik_karsilik INTEGER, max_ek_ders INTEGER, koordinator INTEGER DEFAULT 1,
    musait_olmayan TEXT DEFAULT '', aktif INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS ogrenciler (
    id INTEGER PRIMARY KEY, tc TEXT DEFAULT '', okul_no TEXT DEFAULT '',
    ad TEXT NOT NULL, soyad TEXT NOT NULL, dogum_tarihi TEXT, cinsiyet TEXT DEFAULT '',
    sinif_id INTEGER REFERENCES siniflar(id) ON DELETE SET NULL,
    statu TEXT DEFAULT 'Öğrenci', bakmakla_yukumlu INTEGER DEFAULT 1,
    veli_ad TEXT DEFAULT '', veli_tel TEXT DEFAULT '', telefon TEXT DEFAULT '',
    iban TEXT DEFAULT '', adres TEXT DEFAULT '', aktif INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS isletmeler (
    id INTEGER PRIMARY KEY, ad TEXT NOT NULL, vergi_no TEXT DEFAULT '', sgk_sicil TEXT DEFAULT '',
    yetkili TEXT DEFAULT '', telefon TEXT DEFAULT '', eposta TEXT DEFAULT '', adres TEXT DEFAULT '',
    ilce TEXT DEFAULT '', guzergah TEXT DEFAULT '', mesafe_km REAL DEFAULT 0,
    personel_sayisi INTEGER DEFAULT 0, kamu_kurumu INTEGER DEFAULT 0,
    usta_ogretici TEXT DEFAULT '', usta_ogretici_tel TEXT DEFAULT '', iban TEXT DEFAULT '',
    alan_id INTEGER REFERENCES alanlar(id) ON DELETE SET NULL,
    kontenjan INTEGER DEFAULT 0, aktif INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS atolyeler (
    id INTEGER PRIMARY KEY, ad TEXT NOT NULL, tur TEXT DEFAULT 'Atölye',
    alan_id INTEGER REFERENCES alanlar(id) ON DELETE SET NULL, kapasite INTEGER DEFAULT 16
);
CREATE TABLE IF NOT EXISTS dersler (
    id INTEGER PRIMARY KEY, ad TEXT NOT NULL, kisa_ad TEXT DEFAULT '',
    alan_id INTEGER REFERENCES alanlar(id) ON DELETE SET NULL,
    tur TEXT DEFAULT 'Meslek', atolye_gerekli INTEGER DEFAULT 0, blok INTEGER DEFAULT 2
);
CREATE TABLE IF NOT EXISTS ders_atamalari (
    id INTEGER PRIMARY KEY,
    sinif_id INTEGER NOT NULL REFERENCES siniflar(id) ON DELETE CASCADE,
    ders_id INTEGER NOT NULL REFERENCES dersler(id) ON DELETE CASCADE,
    ogretmen_id INTEGER REFERENCES ogretmenler(id) ON DELETE SET NULL,
    haftalik_saat INTEGER NOT NULL DEFAULT 2, blok INTEGER,
    atolye_id INTEGER REFERENCES atolyeler(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS program_hucreleri (
    id INTEGER PRIMARY KEY,
    atama_id INTEGER NOT NULL REFERENCES ders_atamalari(id) ON DELETE CASCADE,
    gun INTEGER NOT NULL, saat INTEGER NOT NULL,
    atolye_id INTEGER REFERENCES atolyeler(id) ON DELETE SET NULL,
    kilitli INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS yerlestirmeler (
    id INTEGER PRIMARY KEY,
    ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id) ON DELETE CASCADE,
    isletme_id INTEGER REFERENCES isletmeler(id) ON DELETE SET NULL,
    tur TEXT DEFAULT 'İşletmede Mesleki Eğitim',
    baslangic TEXT, bitis TEXT, sozlesme_no TEXT DEFAULT '', sozlesme_tarihi TEXT,
    ucret REAL DEFAULT 0,
    sigorta_giris_bildirildi INTEGER DEFAULT 0, sigorta_giris_bildirim_tarihi TEXT,
    sigorta_cikis_bildirildi INTEGER DEFAULT 0, sigorta_cikis_bildirim_tarihi TEXT,
    fesih_nedeni TEXT DEFAULT '', durum TEXT DEFAULT 'Aktif'
);
CREATE TABLE IF NOT EXISTS koordinator_gorevleri (
    id INTEGER PRIMARY KEY,
    ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id) ON DELETE CASCADE,
    isletme_id INTEGER NOT NULL REFERENCES isletmeler(id) ON DELETE CASCADE,
    gun INTEGER NOT NULL, haftalik_saat INTEGER NOT NULL DEFAULT 1,
    baslangic TEXT, bitis TEXT
);
CREATE TABLE IF NOT EXISTS ziyaretler (
    id INTEGER PRIMARY KEY,
    ogretmen_id INTEGER REFERENCES ogretmenler(id) ON DELETE SET NULL,
    isletme_id INTEGER REFERENCES isletmeler(id) ON DELETE CASCADE,
    tarih TEXT NOT NULL, durum TEXT DEFAULT 'Planlandı',
    tespitler TEXT DEFAULT '', oneriler TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS devamsizlik (
    id INTEGER PRIMARY KEY,
    ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id) ON DELETE CASCADE,
    tarih TEXT NOT NULL, tur TEXT DEFAULT 'Özürsüz', yer TEXT DEFAULT 'İşletme',
    gun REAL DEFAULT 1, sgk_eksik INTEGER DEFAULT 1, aciklama TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS beceri_notlari (
    id INTEGER PRIMARY KEY,
    ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id) ON DELETE CASCADE,
    donem INTEGER DEFAULT 1, isletme_notu REAL, koordinator_notu REAL,
    tarih TEXT, aciklama TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS ek_ders_kayitlari (
    id INTEGER PRIMARY KEY,
    ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id) ON DELETE CASCADE,
    tarih TEXT NOT NULL, tur TEXT DEFAULT 'Gündüz', saat REAL NOT NULL DEFAULT 1,
    aciklama TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS tatiller (
    id INTEGER PRIMARY KEY, ad TEXT NOT NULL, baslangic TEXT NOT NULL, bitis TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS aylik_odemeler (
    id INTEGER PRIMARY KEY, donem TEXT NOT NULL,
    yerlestirme_id INTEGER REFERENCES yerlestirmeler(id) ON DELETE CASCADE,
    gun INTEGER, en_az_ucret REAL, odenecek_ucret REAL, devlet_katkisi REAL,
    dekont_teslim INTEGER DEFAULT 0, sisteme_girildi INTEGER DEFAULT 0,
    UNIQUE (donem, yerlestirme_id)
);
CREATE TABLE IF NOT EXISTS evrak (
    id INTEGER PRIMARY KEY, tarih TEXT, sayi TEXT DEFAULT '', konu TEXT DEFAULT '',
    tur TEXT DEFAULT 'Giden', dosya TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS isletme_talepleri (
    id INTEGER PRIMARY KEY, tarih TEXT,
    isletme_id INTEGER REFERENCES isletmeler(id) ON DELETE CASCADE,
    alan_id INTEGER REFERENCES alanlar(id) ON DELETE SET NULL, dal TEXT DEFAULT '',
    talep_sayisi INTEGER DEFAULT 1,
    ogretmen_id INTEGER REFERENCES ogretmenler(id) ON DELETE SET NULL, aciklama TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS anketler (
    id INTEGER PRIMARY KEY, tarih TEXT, tur TEXT DEFAULT 'Mezun',
    ogrenci_id INTEGER REFERENCES ogrenciler(id) ON DELETE SET NULL,
    isletme_id INTEGER REFERENCES isletmeler(id) ON DELETE SET NULL,
    ogretmen_id INTEGER REFERENCES ogretmenler(id) ON DELETE SET NULL,
    calisma_durumu TEXT DEFAULT '', memnuniyet INTEGER, e_ortama_aktarildi INTEGER DEFAULT 0,
    gorusler TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS hizmetici_egitimler (
    id INTEGER PRIMARY KEY, tarih TEXT, konu TEXT NOT NULL,
    isletme_id INTEGER REFERENCES isletmeler(id) ON DELETE SET NULL,
    katilimcilar TEXT DEFAULT '', egitici TEXT DEFAULT '', yer TEXT DEFAULT '',
    sure_saat REAL DEFAULT 0, durum TEXT DEFAULT 'Planlandı'
);

CREATE TABLE IF NOT EXISTS kullanicilar (
    id INTEGER PRIMARY KEY, kullanici_adi TEXT NOT NULL UNIQUE COLLATE NOCASE, ad_soyad TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'personel', parola_ozeti TEXT NOT NULL DEFAULT '',
    aktif INTEGER DEFAULT 1, parola_degistirmeli INTEGER DEFAULT 0, son_giris TEXT
);
CREATE TABLE IF NOT EXISTS islem_gunlugu (
    id INTEGER PRIMARY KEY, zaman TEXT NOT NULL, kullanici TEXT DEFAULT '', bilgisayar TEXT DEFAULT '',
    islem TEXT NOT NULL, tablo TEXT NOT NULL, kayit_id INTEGER, kayit TEXT DEFAULT '', ayrinti TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS program_ders_gruplari (
    id INTEGER PRIMARY KEY, ad TEXT NOT NULL, dersler TEXT DEFAULT '', aktif INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS program_surumleri (
    id INTEGER PRIMARY KEY, ad TEXT NOT NULL, tarih TEXT, aciklama TEXT DEFAULT '', veri TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS belge_takibi (
    id INTEGER PRIMARY KEY, tur TEXT NOT NULL, tarih TEXT NOT NULL,
    ogretmen_id INTEGER REFERENCES ogretmenler(id) ON DELETE CASCADE,
    isletme_id INTEGER REFERENCES isletmeler(id) ON DELETE CASCADE,
    teslim_tarihi TEXT, barkod TEXT DEFAULT '', aciklama TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sinav_donemleri (
    id INTEGER PRIMARY KEY, ad TEXT NOT NULL, tur TEXT DEFAULT 'Sorumluluk', baslangic TEXT, bitis TEXT,
    ogrenci_gunluk_azami INTEGER DEFAULT 2, ogretmen_gunluk_azami INTEGER DEFAULT 3,
    komisyon_uye_sayisi INTEGER DEFAULT 2, gozcu_ogrenci_sayisi INTEGER DEFAULT 25, aciklama TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sinav_seanslari (
    id INTEGER PRIMARY KEY, donem_id INTEGER NOT NULL REFERENCES sinav_donemleri(id) ON DELETE CASCADE,
    tarih TEXT NOT NULL, sira INTEGER NOT NULL DEFAULT 1, baslangic TEXT DEFAULT '', bitis TEXT DEFAULT '',
    acik INTEGER DEFAULT 1, UNIQUE (donem_id, tarih, sira)
);
CREATE TABLE IF NOT EXISTS sinav_salonlari (
    id INTEGER PRIMARY KEY, ad TEXT NOT NULL, kapasite INTEGER DEFAULT 30, sira INTEGER DEFAULT 0,
    aktif INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sinavlar (
    id INTEGER PRIMARY KEY, donem_id INTEGER NOT NULL REFERENCES sinav_donemleri(id) ON DELETE CASCADE,
    ders TEXT NOT NULL, seviye INTEGER, grup TEXT DEFAULT '', sekil TEXT DEFAULT 'Yazılı', sure_dk INTEGER DEFAULT 40,
    alan_id INTEGER REFERENCES alanlar(id) ON DELETE SET NULL,
    ders_id INTEGER REFERENCES dersler(id) ON DELETE SET NULL,
    seans_id INTEGER REFERENCES sinav_seanslari(id) ON DELETE SET NULL, cakili INTEGER DEFAULT 0,
    aciklama TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sinav_ogrencileri (
    id INTEGER PRIMARY KEY, sinav_id INTEGER NOT NULL REFERENCES sinavlar(id) ON DELETE CASCADE,
    ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id) ON DELETE CASCADE,
    salon_id INTEGER REFERENCES sinav_salonlari(id) ON DELETE SET NULL, sira_no INTEGER,
    UNIQUE (sinav_id, ogrenci_id)
);
CREATE TABLE IF NOT EXISTS sinav_gorevlileri (
    id INTEGER PRIMARY KEY, sinav_id INTEGER NOT NULL REFERENCES sinavlar(id) ON DELETE CASCADE,
    ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id) ON DELETE CASCADE,
    gorev TEXT DEFAULT 'Komisyon Üyesi', salon_id INTEGER REFERENCES sinav_salonlari(id) ON DELETE SET NULL,
    kilitli INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sinav_ogretmenleri (
    id INTEGER PRIMARY KEY, donem_id INTEGER NOT NULL REFERENCES sinav_donemleri(id) ON DELETE CASCADE,
    ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id) ON DELETE CASCADE,
    gorev_alir INTEGER DEFAULT 1, gunluk_azami INTEGER, kapali_seanslar TEXT DEFAULT '',
    UNIQUE (donem_id, ogretmen_id)
);
CREATE TABLE IF NOT EXISTS sinav_ogrenci_kapali (
    id INTEGER PRIMARY KEY, donem_id INTEGER NOT NULL REFERENCES sinav_donemleri(id) ON DELETE CASCADE,
    ogrenci_id INTEGER NOT NULL REFERENCES ogrenciler(id) ON DELETE CASCADE,
    seans_id INTEGER NOT NULL REFERENCES sinav_seanslari(id) ON DELETE CASCADE,
    UNIQUE (donem_id, ogrenci_id, seans_id)
);
CREATE TABLE IF NOT EXISTS sinav_kurallari (
    id INTEGER PRIMARY KEY, donem_id INTEGER NOT NULL REFERENCES sinav_donemleri(id) ON DELETE CASCADE,
    ders1 TEXT NOT NULL, ders2 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sinav_salon_atamalari (
    id INTEGER PRIMARY KEY, sinav_id INTEGER NOT NULL REFERENCES sinavlar(id) ON DELETE CASCADE,
    salon_id INTEGER NOT NULL REFERENCES sinav_salonlari(id) ON DELETE CASCADE, UNIQUE (sinav_id, salon_id)
);
CREATE TABLE IF NOT EXISTS sinav_gun_kurallari (
    id INTEGER PRIMARY KEY, donem_id INTEGER NOT NULL REFERENCES sinav_donemleri(id) ON DELETE CASCADE,
    ders TEXT, seviye INTEGER, kapsam TEXT DEFAULT 'sinav', tarihler TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sinav_nobetci (
    id INTEGER PRIMARY KEY, donem_id INTEGER NOT NULL REFERENCES sinav_donemleri(id) ON DELETE CASCADE,
    tarih TEXT NOT NULL, ogretmen_id INTEGER NOT NULL REFERENCES ogretmenler(id) ON DELETE CASCADE,
    UNIQUE (donem_id, tarih)
);
-- [EK-TABLO: SINAV]
CREATE TABLE IF NOT EXISTS ders_mekanlari (
    id INTEGER PRIMARY KEY, ders_id INTEGER REFERENCES dersler(id) ON DELETE CASCADE,
    atama_id INTEGER REFERENCES ders_atamalari(id) ON DELETE CASCADE,
    atolye_id INTEGER NOT NULL REFERENCES atolyeler(id) ON DELETE CASCADE
);
-- [EK-TABLO: DERS PROGRAMI]
-- e-Bildirge'ye verilmiş aylık prim ve hizmet belgelerinin (asıl / ek / iptal) satır satır kaydı; verildikten
-- sonra değişen kayıtlar için iptal + ek belge bu kayıtla hesaplanır.
CREATE TABLE IF NOT EXISTS sgk_beyanlari (
    id INTEGER PRIMARY KEY, donem TEXT NOT NULL, mahiyet TEXT NOT NULL DEFAULT 'A', tahakkuk TEXT DEFAULT 'A',
    tarih TEXT NOT NULL, kisi INTEGER DEFAULT 0, aciklama TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sgk_beyan_satirlari (
    id INTEGER PRIMARY KEY, beyan_id INTEGER NOT NULL REFERENCES sgk_beyanlari(id) ON DELETE CASCADE,
    ogrenci_id INTEGER REFERENCES ogrenciler(id) ON DELETE SET NULL,
    tc TEXT NOT NULL, ad TEXT DEFAULT '', soyad TEXT DEFAULT '', belge TEXT NOT NULL, kanun TEXT DEFAULT '00000',
    gun INTEGER DEFAULT 0, pek REAL DEFAULT 0, giris TEXT, cikis TEXT, eksik_gun INTEGER DEFAULT 0,
    eksik_neden TEXT DEFAULT '', cikis_nedeni TEXT DEFAULT '', meslek TEXT DEFAULT '', okul_ici INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_sgk_beyan_donem ON sgk_beyanlari(donem);
CREATE INDEX IF NOT EXISTS ix_sgk_beyan_satir ON sgk_beyan_satirlari(beyan_id);
-- [EK-TABLO: SGK]
-- [EK-TABLO: MES]

CREATE INDEX IF NOT EXISTS ix_gunluk_zaman ON islem_gunlugu(zaman);
CREATE INDEX IF NOT EXISTS ix_ph_atama ON program_hucreleri(atama_id);
CREATE INDEX IF NOT EXISTS ix_yer_ogr ON yerlestirmeler(ogrenci_id);
CREATE INDEX IF NOT EXISTS ix_dev_ogr ON devamsizlik(ogrenci_id, tarih);
CREATE INDEX IF NOT EXISTS ix_ziy_tarih ON ziyaretler(tarih);
CREATE INDEX IF NOT EXISTS ix_belge_tarih ON belge_takibi(tarih);
CREATE INDEX IF NOT EXISTS ix_sinav_ogr ON sinav_ogrencileri(ogrenci_id);
CREATE INDEX IF NOT EXISTS ix_sinav_seans ON sinavlar(donem_id, seans_id);
"""

# Sonradan eklenen kolonlar; eski veritabanlarına açılışta eklenir.
EK_KOLONLAR = [
    ("aylik_odemeler", "odenen_ucret", "REAL"),
    ("aylik_odemeler", "dekont_tarihi", "TEXT"),
    ("kurum", "ders_yili_baslangic", "TEXT"),
    ("kurum", "birinci_donem_sonu", "TEXT"),
    ("kurum", "ders_yili_sonu", "TEXT"),
    ("ogretmenler", "atolye_lab", "INTEGER DEFAULT 0"),
    ("ogrenciler", "basari_ortalamasi", "REAL"),
    ("ogrenciler", "agir_disiplin", "INTEGER DEFAULT 0"),
    ("ogrenciler", "oncelikli", "INTEGER DEFAULT 0"),
    ("isletmeler", "usta_ogretici_sayisi", "INTEGER DEFAULT 1"),
    ("isletmeler", "usta_belgesi", "INTEGER DEFAULT 0"),
    ("isletmeler", "egitim_birimi", "INTEGER DEFAULT 0"),
    ("isletmeler", "il_disi", "INTEGER DEFAULT 0"),
    ("isletmeler", "doner_sermaye", "INTEGER DEFAULT 0"),
    ("isletmeler", "uygunluk_tarihi", "TEXT"),
    ("isletmeler", "plan_onay_tarihi", "TEXT"),
    ("ders_atamalari", "ogretmen2_id", "INTEGER REFERENCES ogretmenler(id) ON DELETE SET NULL"),
    ("ders_atamalari", "atolye2_id", "INTEGER REFERENCES atolyeler(id) ON DELETE SET NULL"),
    ("ders_atamalari", "birlestirme", "TEXT DEFAULT ''"),
    ("program_hucreleri", "atolye2_id", "INTEGER REFERENCES atolyeler(id) ON DELETE SET NULL"),
    ("ogretmenler", "nobet_gun", "INTEGER"),
    ("ogretmenler", "nobet_yeri", "TEXT"),
    ("ogretmenler", "sinif_ogretmenligi", "TEXT"),
    ("siniflar", "kapali_saatler", "TEXT DEFAULT ''"),
    ("ogrenciler", "baba_adi", "TEXT DEFAULT ''"),
    ("ogrenciler", "anne_adi", "TEXT DEFAULT ''"),
    ("ogrenciler", "dogum_yeri", "TEXT DEFAULT ''"),
    ("ogrenciler", "nufus_il", "TEXT DEFAULT ''"),
    ("ogrenciler", "nufus_ilce", "TEXT DEFAULT ''"),
    ("ogrenciler", "baska_sigortali", "INTEGER DEFAULT 0"),
    ("koordinator_gorevleri", "saatler", "TEXT DEFAULT ''"),
    ("sinav_donemleri", "uygulama_saati", "TEXT DEFAULT ''"),
    ("sinav_donemleri", "sozlu_saati", "TEXT DEFAULT ''"),
    ("sinav_donemleri", "oturma_duzeni", "TEXT DEFAULT 'Sınıf ve ada göre'"),
    ("sinav_donemleri", "komisyon_ucret_saat", "REAL DEFAULT 1"),
    ("sinav_donemleri", "gozcu_ucret_saat", "REAL DEFAULT 1"),
    ("sinav_donemleri", "yillik_azami_gorev", "INTEGER"),
    ("sinav_donemleri", "baslik_aciklama", "TEXT DEFAULT ''"),
    ("sinav_donemleri", "duzenleyen", "TEXT DEFAULT ''"),
    ("sinav_donemleri", "duzenleyen_unvan", "TEXT DEFAULT ''"),
    ("sinav_donemleri", "onaylayan", "TEXT DEFAULT ''"),
    ("sinav_donemleri", "onaylayan_unvan", "TEXT DEFAULT ''"),
    ("sinavlar", "komisyon_sayisi", "INTEGER"),
    ("sinavlar", "gozcu_sayisi", "INTEGER"),
    ("sinavlar", "bagli_sinav_id", "INTEGER REFERENCES sinavlar(id) ON DELETE SET NULL"),
    ("sinavlar", "ucretsiz", "INTEGER DEFAULT 0"),
    ("sinav_ogrencileri", "tur", "TEXT DEFAULT ''"),
    ("sinav_ogrencileri", "salon_kilitli", "INTEGER DEFAULT 0"),
    ("sinav_ogrencileri", "katilim", "TEXT DEFAULT ''"),
    ("sinav_gorevlileri", "ucretsiz", "INTEGER DEFAULT 0"),
    ("sinav_gorevlileri", "durum", "TEXT DEFAULT ''"),
    ("sinav_kurallari", "tur", "TEXT DEFAULT 'ortak_ogrenci'"),
    ("sinav_ogretmenleri", "onceki_gorev", "INTEGER DEFAULT 0"),
    ("sinav_donemleri", "ders_yili_icinde", "TEXT DEFAULT 'Otomatik'"),
    # [EK-KOLON: SINAV]
    ("ogretmenler", "kulup", "TEXT DEFAULT ''"),
    ("ogretmenler", "sef", "INTEGER DEFAULT 0"),
    ("dersler", "brans", "TEXT DEFAULT ''"),
    ("dersler", "blok_deseni", "TEXT DEFAULT ''"),
    ("dersler", "ogle_bolunmez", "INTEGER DEFAULT 0"),
    ("ders_atamalari", "blok_deseni", "TEXT DEFAULT ''"),
    ("ders_atamalari", "mekanli_saat", "INTEGER"),
    ("ders_atamalari", "ogle_bolunmez", "INTEGER DEFAULT 0"),
    ("ders_atamalari", "grup", "TEXT DEFAULT ''"),
    ("atolyeler", "eszamanli", "INTEGER DEFAULT 1"),
    ("siniflar", "derslik_id", "INTEGER REFERENCES atolyeler(id) ON DELETE SET NULL"),
    ("siniflar", "tedrisat", "TEXT DEFAULT 'Tam gün'"),
    ("program_ders_gruplari", "siniflar", "TEXT DEFAULT ''"),
    ("program_ders_gruplari", "kesin", "INTEGER DEFAULT 0"),
    ("ogretmenler", "oncelikli_tercih", "TEXT DEFAULT ''"),
    # [EK-KOLON: DERS PROGRAMI]
    # [EK-KOLON: SGK]
    # [EK-KOLON: MES]
]

# Bir dersin öğretmenleri (2. öğretmenli / grup derslerinde iki satır). Öğretmen saat sayımları bu görünümle yapılır.
GORUNUMLER = """
CREATE VIEW IF NOT EXISTS ders_ogretmenleri AS
    SELECT id AS atama_id, ogretmen_id FROM ders_atamalari WHERE ogretmen_id IS NOT NULL
    UNION SELECT id, ogretmen2_id FROM ders_atamalari WHERE ogretmen2_id IS NOT NULL;
"""


BEKLEME_SN = 30  # başka bir bilgisayar/iş yazarken kilidin açılmasını bekleme süresi
OTOMATIK_YEDEK_SAYISI = 100


def baglan(yol: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(str(yol), timeout=BEKLEME_SN, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


class Database:
    uzak = False

    def __init__(self, path: Path | str | None = None, kimlik: hesaplar.Kimlik | None = None):
        self.path = Path(path) if path else config.db_path()
        self.conn = baglan(self.path)
        self._init_schema()
        self.kimlik = kimlik or hesaplar.Kimlik.varsayilan()
        hesaplar.baglantiyi_hazirla(self._ham_baglanti(), self.kimlik)

    @property
    def konum(self) -> str:
        return str(self.path)

    def _ham_baglanti(self) -> sqlite3.Connection:
        return self.conn

    def kimlik_ata(self, kimlik: hesaplar.Kimlik) -> None:
        """Giriş yapan kullanıcının yetkilerini ve işlem günlüğündeki adını bu bağlantıya uygular."""
        self.kimlik = kimlik
        hesaplar.baglantiyi_hazirla(self._ham_baglanti(), kimlik)

    def kopya(self) -> "Database":
        """Arka plan işleri için ayrı bağlantı (iş parçacıkları arasında bağlantı paylaşılmaz)."""
        return Database(self.path, self.kimlik)

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        for tablo, kolon, tanim in EK_KOLONLAR:
            if kolon not in self.columns(tablo):
                self.conn.execute(f"ALTER TABLE {tablo} ADD COLUMN {kolon} {tanim}")
        self.conn.executescript(GORUNUMLER)
        self.conn.execute("INSERT OR IGNORE INTO kurum (id) VALUES (1)")
        self.conn.execute("INSERT OR IGNORE INTO meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        for p in PARAMETRELER:
            self.conn.execute("INSERT OR IGNORE INTO ayarlar VALUES (?, ?)", (p.anahtar, p.varsayilan))
        self.conn.commit()

    # --- genel sorgu yardımcıları ---
    def q(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def q1(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def execute(self, sql: str, params: Iterable[Any] = ()) -> int:
        cur = self.conn.execute(sql, tuple(params))
        self.conn.commit()
        return cur.lastrowid

    def insert(self, table: str, values: dict[str, Any]) -> int:
        cols = ", ".join(values)
        ph = ", ".join("?" for _ in values)
        return self.execute(f"INSERT INTO {table} ({cols}) VALUES ({ph})", values.values())

    def update(self, table: str, row_id: int, values: dict[str, Any]) -> None:
        sets = ", ".join(f"{k} = ?" for k in values)
        self.execute(f"UPDATE {table} SET {sets} WHERE id = ?", [*values.values(), row_id])

    def delete(self, table: str, row_id: int) -> None:
        self.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))

    def columns(self, table: str) -> list[str]:
        return [r["name"] for r in self.q(f"PRAGMA table_info({table})")]

    # --- ayarlar ---
    def ayar(self, anahtar: str) -> Any:
        row = self.q1("SELECT deger FROM ayarlar WHERE anahtar = ?", (anahtar,))
        p = PARAMETRE_SOZLUK.get(anahtar)
        raw = row["deger"] if row else (p.varsayilan if p else None)
        if p is None or raw is None:
            return raw
        try:
            if p.tip == "float":
                return float(str(raw).replace(",", "."))
            if p.tip == "int":
                return int(float(str(raw).replace(",", ".")))
            if p.tip == "bool":
                return str(raw).strip().lower() in ("1", "true", "evet", "e")
        except ValueError:
            return float(p.varsayilan) if p.tip == "float" else int(p.varsayilan) if p.tip == "int" else raw
        return raw

    # Değeri değişmeyen ayar işlem günlüğüne yazılmasın diye REPLACE yerine UPSERT
    AYAR_YAZ = ("INSERT INTO ayarlar VALUES (?, ?) ON CONFLICT (anahtar) DO UPDATE SET deger = excluded.deger "
                "WHERE deger IS NOT excluded.deger")

    def ayar_yaz(self, anahtar: str, deger: Any) -> None:
        self.execute(self.AYAR_YAZ, (anahtar, str(deger)))

    def ayarlari_sifirla(self) -> None:
        for p in PARAMETRELER:
            self.conn.execute(self.AYAR_YAZ, (p.anahtar, p.varsayilan))
        self.conn.commit()

    def kurum(self) -> sqlite3.Row:
        return self.q1("SELECT * FROM kurum WHERE id = 1")

    # --- yedekleme ---
    def yedekle(self, hedef: Path | None = None) -> Path:
        otomatik = hedef is None
        if otomatik:
            hedef = config.backup_dir() / config.yedek_adi(datetime.now())
        self.conn.commit()
        dst = sqlite3.connect(str(hedef))
        with dst:
            self.conn.backup(dst)
        dst.close()
        if otomatik:
            eski_yedekleri_temizle(hedef.parent)
            from . import yedekleme
            yedekleme.yedek_alindi(hedef)
        return hedef

    def geri_yukle(self, kaynak: Path) -> None:
        """Yedeği yerinde geri yükler; açık başka bağlantılar (ağdaki kullanıcılar) bozulmaz."""
        self.conn.commit()
        src = sqlite3.connect(str(kaynak))
        try:
            src.backup(self.conn)
        finally:
            src.close()
        self._init_schema()
        hesaplar.baglantiyi_hazirla(self._ham_baglanti(), self.kimlik)

    def close(self) -> None:
        self.conn.close()


def eski_yedekleri_temizle(klasor: Path, tut: int = OTOMATIK_YEDEK_SAYISI) -> None:
    yedekler = config.yedek_dosyalari(klasor)
    for eski in yedekler[:-tut]:
        try:
            eski.unlink()
        except OSError:
            pass
