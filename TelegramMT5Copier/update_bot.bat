@echo off
chcp 65001 >nul
echo ==========================================
echo ĐANG CẬP NHẬT CODE TỪ GITHUB...
echo ==========================================
git pull

echo.
echo ==========================================
echo ĐANG KHỞI ĐỘNG LẠI BOT...
echo ==========================================
:: Tìm và tắt tiến trình bot cũ (chỉ tắt cửa sổ có tiêu đề chứa chữ "TelegramMT5Copier" hoặc tắt main.py)
:: Cách an toàn nhất nếu bạn chạy bằng start_bot.bat:
taskkill /FI "WINDOWTITLE eq Administrator:  start_bot*" /F 2>nul
taskkill /FI "WINDOWTITLE eq start_bot*" /F 2>nul

:: Nếu bạn dùng tên file start_bot.bat, ta gọi nó chạy lại trong một cửa sổ mới
start "Telegram MT5 Bot" cmd /k "start_bot.bat"

echo Hoan thanh! Cua so bot moi da duoc mo.
pause
