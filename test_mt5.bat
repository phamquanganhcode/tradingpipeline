@echo off
chcp 65001 > nul
title Kiem Tra Ket Noi & Thu Dat Lenh MetaTrader 5
color 0A

:: Chuyen vao thu muc chua file bat nay
cd /d "%~dp0"

echo.
echo ================================================================
echo         CONG CU KIEM TRA KET NOI VA THU DAT LENH MT5
echo ================================================================
echo  Thu muc hien tai: %CD%
echo  Thoi gian: %DATE% %TIME%
echo ================================================================
echo.

:: Kiem tra Python
where python > nul 2>&1
if errorlevel 1 (
    color 0C
    echo [LOI] Khong tim thay Python tren he thong!
    echo Vui long cai dat Python hoac them vao bien moi truong PATH.
    echo.
    pause
    exit /b 1
)

:: Chay script Python test MT5
python test_mt5.py

echo.
echo ================================================================
echo Chuong trinh test MT5 da ket thuc.
echo ================================================================
pause
