"""
run_scheduler.py — Chạy pipeline tự động theo lịch
────────────────────────────────────────────────────────────────
Cài đặt: pip install schedule
Chạy:    python run_scheduler.py

Mặc định:
- Pipeline chạy vào phút :01 của mỗi giờ (đầu nến H1 mới)
- Trade monitor chạy mỗi 5 phút để kiểm tra lệnh đang mở
- Có thể Ctrl+C để dừng
"""

from __future__ import annotations

import sys
import os
import time
from datetime import datetime

# Đảm bảo UTF-8 cho console trên Windows (tránh lỗi charmap/UnicodeEncodeError)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import schedule
except ImportError:
    print("❌ Thiếu thư viện 'schedule'. Cài bằng: pip install schedule")
    sys.exit(1)

# Thêm thư mục gốc vào path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SYMBOL, REPORTS_DIR
from modules.report_parser import find_latest_report
from modules.trade_monitor import TradeMonitor


def run_pipeline_job():
    """Chạy toàn bộ pipeline một lần."""
    from main import run_pipeline
    print(f"\n{'='*60}")
    print(f"⏰ SCHEDULER: Bắt đầu pipeline lúc {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*60}")

    # Bỏ chữ 'm' ở cuối (ví dụ BTCUSDm -> BTCUSD) để tìm đúng file report từ TradingAgents
    search_symbol = SYMBOL[:-1] if SYMBOL.endswith('m') else SYMBOL
    report_path = find_latest_report(directory=REPORTS_DIR, symbol=search_symbol)
    if not report_path:
        print(f"[Scheduler] ⚠️  Không tìm thấy report cho {search_symbol}. Bỏ qua lần này.")
        return

    try:
        run_pipeline(report_path=report_path)
    except Exception as e:
        print(f"[Scheduler] ❌ Lỗi pipeline: {e}")


def run_monitor_job():
    """Kiểm tra các lệnh đang mở."""
    from modules.indicator_engine import IndicatorEngine

    def _get_price(symbol: str):
        try:
            engine = IndicatorEngine(symbol=symbol, timeframes=[])
            return engine.get_live_price()
        except Exception:
            return None

    monitor = TradeMonitor()
    monitor.run_check(price_fetcher=_get_price)


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║          AI TRADING PIPELINE — AUTO SCHEDULER                ║
║   Pipeline: mỗi giờ lúc :15 | Monitor: mỗi 5 phút          ║
║   Nhấn Ctrl+C để dừng                                       ║
╚══════════════════════════════════════════════════════════════╝
""")

    run_minute = os.getenv("PIPELINE_RUN_MINUTE", ":15")
    if not run_minute.startswith(":"):
        run_minute = f":{run_minute.zfill(2)}"

    # Lịch chạy
    schedule.every().hour.at(run_minute).do(run_pipeline_job)
    schedule.every(5).minutes.do(run_monitor_job)

    print(f"[Scheduler] ✅ Đã thiết lập lịch:")
    print(f"  - Pipeline: phút {run_minute} của mỗi giờ")
    print(f"  - Monitor : mỗi 5 phút")
    print(f"[Scheduler] Đang chờ... (lần chạy pipeline tiếp theo: phút {run_minute})\n")

    # Chạy monitor ngay lập tức khi khởi động
    run_monitor_job()

    while True:
        schedule.run_pending()
        time.sleep(30)  # check mỗi 30 giây


if __name__ == "__main__":
    main()
