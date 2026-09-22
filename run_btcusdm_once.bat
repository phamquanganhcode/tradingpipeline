@echo off
chcp 65001 > nul
title AI Trading Bot - Run Once - BTCUSDm
color 0B

:: Chuyen vao thu muc chua file bat nay
cd /d "%~dp0"

echo.
echo  +============================================================+
echo  ^|         AI TRADING BOT (RUN ONCE) - BTCUSDm               ^|
echo  +============================================================+
echo.

set TRADING_SYMBOL=BTCUSDm
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

python main.py

echo.
echo  [HOAN TAT] Da chay xong pipeline cho BTCUSDm.
pause
