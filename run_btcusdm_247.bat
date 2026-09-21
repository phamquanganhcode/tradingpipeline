@echo off
title AI Trading Pipeline - BTCUSDm (24/7 Crypto)
chcp 65001 >nul
color 0B

:: Chuyen vao thu muc chua file bat
cd /d "%~dp0"

echo ==============================================================================
echo    AI TRADING PIPELINE - 24/7 CRYPTO MODE
echo ==============================================================================
echo  - Symbol MT5: BTCUSDm
echo  - Tim kiem Report: BTCUSD hoac BTC-USD
echo  - Scheduler: Chay tin hieu moi dau gio luc :15, Monitor moi 5 phut
echo  - Bam Ctrl+C de dung
echo ==============================================================================
echo.

set TRADING_SYMBOL=BTCUSDm
set PIPELINE_RUN_MINUTE=:15
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
python run_scheduler.py

pause
