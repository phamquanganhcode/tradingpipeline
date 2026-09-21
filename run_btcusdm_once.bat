@echo off
chcp 65001 > nul
title AI Trading Pipeline - BTCUSDm Run Once
color 0B

:: Chuyen vao thu muc chua file bat nay
cd /d "%~dp0"

echo ================================================================
echo    AI TRADING PIPELINE - BTCUSDm (RUN ONCE CHO TASK SCHEDULER)
echo ================================================================
echo  Thoi gian chay: %DATE% %TIME%
echo ================================================================

set TRADING_SYMBOL=BTCUSDm
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: Chay pipeline 1 lan cho BTCUSDm
python main.py --symbol BTCUSDm --balance 10000

echo.
echo Hoan tat luc %TIME%.
