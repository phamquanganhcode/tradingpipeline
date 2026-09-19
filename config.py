"""
config.py — Cấu hình tập trung cho toàn bộ pipeline
API Keys được đọc từ file .env (bảo mật hơn hardcode)
"""

import os
from pathlib import Path

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
SYMBOL     = "BTCUSD"
TIMEFRAMES = ["D1", "H4", "H1", "M15"]   # khung dùng để tính indicator bổ sung

# ─────────────────────────────────────────────
# RISK MANAGEMENT
# ─────────────────────────────────────────────
RISK_PER_TRADE_PCT  = 2      # % tài khoản rủi ro mỗi lệnh
MINIMUM_RR          = 1.3    # R:R tối thiểu để chấp nhận setup
MAX_SPREAD_PIPS     = 5.0    # spread tối đa cho phép (pips)
NEWS_BLOCK_MINUTES  = 30     # chặn giao dịch ±30 phút quanh tin tức high-impact
MAX_TRADES_PER_DAY  = 3

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
REPORTS_DIR = r"D:\TradingAgentsv2\reports"            # thư mục chứa file report từ TradingAgents
CHARTS_DIR  = "charts"
DB_PATH     = "data/trades.db"

# ─────────────────────────────────────────────
# INDICATOR SETTINGS (phải khớp với Trading_System_Pro.md)
# ─────────────────────────────────────────────
EMA_FAST   = 20
EMA_SLOW   = 50
BB_PERIOD  = 20
BB_STD     = 2.0
ATR_PERIOD = 14
RSI_PERIOD = 14