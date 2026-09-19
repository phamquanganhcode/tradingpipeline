@echo off
title AI Trading Pipeline - BTCUSDm (24/7 Crypto)
chcp 65001 >nul
color 0B

echo ==============================================================================
echo    AI TRADING PIPELINE - 24/7 CRYPTO MODE
echo ==============================================================================
echo  - Symbol MT5: BTCUSDm
echo  - Tim kiem Report: BTCUSD hoac BTC-USD
echo  - Scheduler: Chay tin hieu moi dau gio, Monitor moi 5 phut
echo  - Bam Ctrl+C de dung
echo ==============================================================================
echo.

set TRADING_SYMBOL=BTCUSDm
python run_scheduler.py

pause
