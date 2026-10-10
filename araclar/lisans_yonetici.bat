@echo off
rem MesKoord Lisans Yoneticisi - YALNIZCA doner sermaye / lisans veren birim bilgisayarinda.
cd /d "%~dp0.."
if exist .venv\Scripts\pythonw.exe (
    start "" .venv\Scripts\pythonw.exe araclar\lisans_yonetici.py %*
) else (
    start "" pythonw araclar\lisans_yonetici.py %*
)
