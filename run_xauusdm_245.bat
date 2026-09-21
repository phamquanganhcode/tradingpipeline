@echo off
title AI Trading Pipeline - XAUUSDm (24/5 Gold)
chcp 65001 >nul
color 0E

:: Chuyen vao thu muc chua file bat
cd /d "%~dp0"

echo ==============================================================================
echo    AI TRADING PIPELINE - 24/5 GOLD (XAUUSDm) MODE
echo ==============================================================================
echo  - Symbol MT5: XAUUSDm (Vang / Gold)
echo  - Tim kiem Report: XAUUSD hoac XAU-USD
echo  - Scheduler: Chay tin hieu moi dau gio luc :15, Monitor moi 5 phut
echo  - Bam Ctrl+C de dung
echo ==============================================================================
echo.

set TRADING_SYMBOL=XAUUSDm
set PIPELINE_RUN_MINUTE=:15
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
python run_scheduler.py

pause
