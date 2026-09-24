@echo off
chcp 65001 >nul
title Auto Update Bot
echo ==========================================
echo TOOL TỰ ĐỘNG CẬP NHẬT CODE GITHUB
echo Sẽ tự động kiểm tra code mới mỗi 15 phút.
echo ==========================================

:loop
echo [%time%] Dang kiem tra code moi tu GitHub...
git fetch

:: Kiểm tra xem có code mới không
git status -uno | findstr /I /C:"Your branch is behind" >nul
if %errorlevel% equ 0 (
    echo [%time%] Phat hien code moi! Dang tien hanh cap nhat...
    git pull
    
    echo [%time%] Dang khoi dong lai Bot...
    taskkill /FI "WINDOWTITLE eq Telegram MT5 Bot*" /F /T 2>nul
    start "Telegram MT5 Bot" cmd /k "start_bot.bat"
) else (
    echo [%time%] Code van dang o phien ban moi nhat.
)

:: Đợi 15 phút (900 giây) rồi kiểm tra lại
timeout /t 900 >nul
goto loop
