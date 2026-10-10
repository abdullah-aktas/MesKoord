# -*- mode: python ; coding: utf-8 -*-
# Klasör (onedir) paketi: dist\MesKoord\MesKoord.exe + _internal\
# Tek dosya (onefile) kullanılmaz: tarayıcı bileşeni her açılışta yüzlerce MB geçici dosya açardı ve
# Qt kütüphanelerinin (LGPL) kullanıcı tarafından değiştirilebilir ayrı dosyalar olarak kalması gerekir.
# Derleme: python araclar\surum_hazirla.py   (doğrudan: pyinstaller --noconfirm MesKoord.spec)
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules
from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct, StringTable,
                                                 VarFileInfo, VarStruct, VSVersionInfo)

KOK = Path(SPECPATH)
_init = (KOK / "koordmes" / "__init__.py").read_text("utf-8")
SURUM = re.search(r'__version__\s*=\s*"([^"]+)"', _init).group(1)
YAYINCI = re.search(r'APP_PUBLISHER\s*=\s*"([^"]+)"', _init).group(1)
_s = tuple(int(x) for x in (SURUM.split(".") + ["0", "0", "0"])[:4])

surum_bilgisi = VSVersionInfo(
    ffi=FixedFileInfo(filevers=_s, prodvers=_s),
    kids=[
        StringFileInfo([StringTable("041F04B0", [
            StringStruct("CompanyName", YAYINCI),
            StringStruct("FileDescription", "MesKoord - Mesleki Eğitim Koordinasyon ve Yönetim Sistemi"),
            StringStruct("FileVersion", SURUM),
            StringStruct("InternalName", "MesKoord"),
            StringStruct("OriginalFilename", "MesKoord.exe"),
            StringStruct("ProductName", "MesKoord"),
            StringStruct("ProductVersion", SURUM),
        ])]),
        VarFileInfo([VarStruct("Translation", [0x041F, 1200])]),
    ],
)

datas = [("koordmes/gorseller/*.png", "koordmes/gorseller"), ("koordmes/veri/*.json", "koordmes/veri"),
         ("koordmes/veri/sgk/*.xsd", "koordmes/veri/sgk"), ("docs/KULLANIM_KILAVUZU.md", "docs")]
binaries = []
hiddenimports = collect_submodules("koordmes")
hiddenimports += ["PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"]
datas += collect_data_files("pdfminer")
for paket in ("pdfplumber", "pypdfium2"):
    d, b, h = collect_all(paket)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["run.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # araclar/ (lisans yöneticisi) hiçbir zaman pakete girmez
    excludes=["pytest", "tkinter", "araclar"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MesKoord",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=str(KOK / "dagitim" / "meskoord.ico"),
    version=surum_bilgisi,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MesKoord",
)
