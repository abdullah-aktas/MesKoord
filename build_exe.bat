@echo off
rem MesKoord dagitim paketi: testler + dist\MesKoord + cikti\MesKoord_<surum>\ (kurulum exe ve zip)
rem Surum yukseltmek icin:  build_exe.bat --surum 1.1.0
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo Sanal ortam olusturuluyor...
    python -m venv .venv || goto :hata
)

.venv\Scripts\python.exe -m pip install --upgrade pip >nul
.venv\Scripts\python.exe -m pip install -r requirements.txt || goto :hata
.venv\Scripts\python.exe araclar\surum_hazirla.py %* || goto :hata
exit /b 0

:hata
echo.
echo HATA: islem tamamlanamadi.
exit /b 1
