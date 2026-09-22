@echo off
chcp 65001 > nul
title AI Trading Bot - Run Once - XAUUSDm
color 0E

:: Chuyen vao thu muc chua file bat nay
cd /d "%~dp0"

echo.
echo  +============================================================+
echo  ^|         AI TRADING BOT (RUN ONCE) - XAUUSDm               ^|
echo  +============================================================+
echo.

set TRADING_SYMBOL=XAUUSDm
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

python main.py

echo.
echo  [HOAN TAT] Da chay xong pipeline cho XAUUSDm.
pause
