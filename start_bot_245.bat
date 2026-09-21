@echo off
chcp 65001 > nul
title AI Trading Bot 24/5 - Auto Scheduler
color 0B

:: Tu dong chuyen vao thu muc chua file bat nay
cd /d "%~dp0"

:RESTART_LOOP
cls
echo.
echo  +============================================================+
echo  ^|         AI TRADING BOT 24/5 - AUTO SCHEDULER               ^|
echo  ^|     He thong dang chay ngam va san sang ban Telegram       ^|
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

set TRADING_SYMBOL=XAUUSDm
set PIPELINE_RUN_MINUTE=:15
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: Chay Auto Scheduler
python run_scheduler.py

:: Neu code bi crash hoac tat, no se chay xuong day
color 0E
echo.
echo  -------------------------------------------------------------
echo  [CANH BAO] Bot vua bi ngung hoac xay ra loi!
echo  Tu dong khoi dong lai sau 5 giay...
timeout /t 5 /nobreak > nul

goto RESTART_LOOP
