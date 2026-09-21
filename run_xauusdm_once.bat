@echo off
chcp 65001 > nul
title AI Trading Pipeline - XAUUSDm Run Once
color 0E

:: Chuyen vao thu muc chua file bat
cd /d "%~dp0"

echo ================================================================
echo    AI TRADING PIPELINE - XAUUSDm (RUN ONCE CHO TASK SCHEDULER)
echo ================================================================
echo  Thoi gian chay: %DATE% %TIME%
echo ================================================================

set TRADING_SYMBOL=XAUUSDm
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

:: Chay pipeline 1 lan cho XAUUSDm
python main.py --symbol XAUUSDm --balance 10000

echo.
echo Hoan tat luc %TIME%.
