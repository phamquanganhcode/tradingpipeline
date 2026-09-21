"""
config.py — Cấu hình tập trung cho toàn bộ pipeline
API Keys được đọc từ file .env (bảo mật hơn hardcode)
"""

import os
import sys
from pathlib import Path

# Đảm bảo UTF-8 cho console trên Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Tự động load file .env nếu có thư viện python-dotenv
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=_env_path)
except ImportError:
    pass  # Nếu chưa cài dotenv, vẫn hoạt động qua biến môi trường thông thường

# ─────────────────────────────────────────────
# API KEYS (đọc từ .env hoặc biến môi trường)
# ─────────────────────────────────────────────
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL        = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
TWELVEDATA_API_KEY  = os.getenv("TWELVEDATA_API_KEY", "")
TELEGRAM_BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID    = os.getenv("TELEGRAM_CHAT_ID", "")


# ─────────────────────────────────────────────
# SYMBOL & TIMEFRAME
# ─────────────────────────────────────────────
SYMBOL     = os.getenv("TRADING_SYMBOL", "BTCUSD")
TIMEFRAMES = ["D1", "H4", "H1", "M15"]   # khung dùng để tính indicator bổ sung

# ─────────────────────────────────────────────
# RISK MANAGEMENT
# ─────────────────────────────────────────────
RISK_PER_TRADE_PCT  = float(os.getenv("RISK_PER_TRADE_PCT", "1.5"))  # % tài khoản rủi ro mỗi lệnh
MINIMUM_RR          = 1.3    # R:R tối thiểu để chấp nhận setup
MAX_SPREAD_PIPS     = 5.0    # spread tối đa cho phép (pips)
NEWS_BLOCK_MINUTES  = 30     # chặn giao dịch ±30 phút quanh tin tức high-impact
MAX_TRADES_PER_DAY  = int(os.getenv("MAX_TRADES_PER_DAY", "10"))      # số lệnh tối đa mỗi ngày

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
_default_reports = Path(__file__).resolve().parent.parent / "TradingAgentsv2" / "reports"
if not _default_reports.exists():
    # Fallback to local D: path if running standalone
    _default_reports = Path(r"D:\TradingAgentsv2\reports")
REPORTS_DIR = os.getenv("REPORTS_DIR", str(_default_reports))
BASE_DIR    = Path(__file__).resolve().parent
CHARTS_DIR  = str(BASE_DIR / "charts")
DB_PATH     = str(BASE_DIR / "data" / "trades.db")

# ─────────────────────────────────────────────
# INDICATOR SETTINGS (phải khớp với Trading_System_Pro.md)
# ─────────────────────────────────────────────
EMA_FAST   = 20
EMA_SLOW   = 50
BB_PERIOD  = 20
BB_STD     = 2.0
ATR_PERIOD = 14
RSI_PERIOD = 14