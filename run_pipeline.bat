@echo off
chcp 65001 > nul
color 0A
title AI Trading Pipeline v2

:: Tu dong chuyen vao thu muc chua file bat nay
cd /d "%~dp0"

cls
echo.
echo  +============================================================+
echo  ^|        AI TRADING PIPELINE v2 -- Price Action + Gemini    ^|
echo  ^|        Strategy: EMA 20/50 + BB + MACD + Stochastic       ^|
echo  +============================================================+
echo.
echo  Thu muc: %CD%
echo  Thoi gian: %DATE% %TIME%
echo.

:: Kiem tra Python
where python > nul 2>&1
if errorlevel 1 (
    color 0C
    echo  [LOI] Khong tim thay Python! Hay cai Python va thu lai.
    pause
    exit /b 1
)

:: Kiem tra file .env
if not exist ".env" (
    color 0E
    echo  [CANH BAO] Khong tim thay file .env
    echo  Hay tao file .env voi noi dung:
    echo    GEMINI_API_KEY=your_key_here
    echo    TWELVEDATA_API_KEY=your_key_here
    echo.
    pause
    exit /b 1
)

:: Menu chon Symbol
echo  Chon symbol muon phan tich:
echo  [1] XAUUSDm - Vang / Gold      (mac dinh)
echo  [2] XAGUSDm - Bac / Silver
echo  [3] EURUSDm - Euro / USD
echo  [4] BTCUSDm - Bitcoin / USD
echo.
set /p choice="  Nhap so lua chon roi nhan Enter (Enter = XAUUSD): "

if "%choice%"=="2" set SYMBOL=XAGUSDm
if "%choice%"=="3" set SYMBOL=EURUSDm
if "%choice%"=="4" set SYMBOL=BTCUSDm
if not defined SYMBOL set SYMBOL=XAUUSDm

echo.
echo  Dang chay pipeline cho: %SYMBOL%
echo  -------------------------------------------------------------
echo.

:: Fix encoding Python
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: Chay pipeline
python main.py --symbol %SYMBOL% --balance 10000

:: Hien thi ket qua
echo.
echo  -------------------------------------------------------------
if errorlevel 1 (
    color 0C
    echo  [LOI] Pipeline gap loi! Xem log ben tren de biet chi tiet.
) else (
    color 0A
    echo  [OK] Pipeline hoan tat thanh cong!
)
echo.
echo  Nhan phim bat ky de dong cua so...
pause > nul
