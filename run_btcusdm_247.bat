@echo off
chcp 65001 > nul
title AI Trading Bot 24/7 - BTCUSDm (Bitcoin)
color 0B

:: Chuyen vao thu muc chua file bat nay
cd /d "%~dp0"

:RESTART_LOOP
cls
echo.
echo  +============================================================+
echo  ^|         AI TRADING BOT 24/7 - BTCUSDm (BITCOIN)            ^|
echo  ^|     Chay tu dong: 24/7 ca Thu 7 va Chu Nhat               ^|
echo  ^|     Tin hieu: Phut :15 moi gio ^| Monitor: Moi 5 phut      ^|
echo  +============================================================+
echo.
echo  Thu muc: %CD%
echo  Thoi gian bat dau: %DATE% %TIME%
echo  -------------------------------------------------------------
echo.

:: Kiem tra Python
where python > nul 2>&1
if errorlevel 1 (
    color 0C
    echo  [LOI] Khong tim thay Python! Hay cai Python va thu lai.
    pause
    exit /b 1
)

:: Thiet lap moi truong
set TRADING_SYMBOL=BTCUSDm
set PIPELINE_RUN_MINUTE=:15
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: Chay Auto Scheduler
python run_scheduler.py

:: Neu chuong trinh bi ngat dot ngot, tu dong khoi dong lai
color 0C
echo.
echo  -------------------------------------------------------------
echo  [CANH BAO] Bot vua bi ngung hoac xay ra loi!
echo  Tu dong khoi dong lai sau 5 giay... (Nhan Ctrl+C de huy)
timeout /t 5 /nobreak > nul

goto RESTART_LOOP
