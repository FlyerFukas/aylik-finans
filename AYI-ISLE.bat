@echo off
rem Aylik islem: Indirilenler'deki en yeni "Ekstre..." klasorunu isler.
rem Baska bir klasor icin klasoru bu dosyanin ustune surukle-birak.
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if "%~1"=="" (
  py -I -X utf8 arac\ayi_isle.py
) else (
  py -I -X utf8 arac\ayi_isle.py "%~1"
)
echo.
pause
