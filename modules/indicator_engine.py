"""
modules/indicator_engine.py
────────────────────────────────────────────────────────────────
Tính toán bổ sung EMA 20/50, Bollinger Bands, ATR, RSI,
MACD và Stochastic từ Twelve Data API.

Cải thiện v2:
- Cache OHLC data để tránh gọi API thừa
- Tái sử dụng dữ liệu M5/D1 cho live_price (không gọi thêm)
- Thêm MACD và Stochastic Oscillator
"""

from __future__ import annotations

import warnings
from typing import Optional

import requests
import pandas as pd
import ta as ta_lib

from models.schemas import IndicatorSnapshot
from config import EMA_FAST, EMA_SLOW, BB_PERIOD, BB_STD, ATR_PERIOD, RSI_PERIOD, TWELVEDATA_API_KEY

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────────────────────
# SYMBOL MAPPING (TradingAgents → Twelve Data)
# ─────────────────────────────────────────────────────────────
SYMBOL_MAP = {
    "XAGUSD":  "XAG/USD",
    "XAUUSD":  "XAU/USD",
    "XAUUSDm": "XAU/USD",   # Exness micro → same Twelve Data symbol
    "EURUSD":  "EUR/USD",
    "GBPUSD":  "GBP/USD",
    "USDJPY":  "USD/JPY",
    "BTCUSD":  "BTC/USD",
    "BTCUSDm": "BTC/USD",   # Exness micro → same Twelve Data symbol
}

# Twelve Data interval mapping
TF_MAP = {
    "D1":  "1day",
    "H4":  "4h",
    "H1":  "1h",
    "M30": "30min",
    "M15": "15min",
    "M5":  "5min",
}


def _fetch_ohlc(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """Tải dữ liệu OHLC từ Twelve Data API."""
    td_symbol = SYMBOL_MAP.get(symbol, f"{symbol[:3]}/{symbol[3:]}")
    if timeframe not in TF_MAP:
        return None

    interval = TF_MAP[timeframe]
    url = (
        f"https://api.twelvedata.com/time_series"
        f"?symbol={td_symbol}&interval={interval}&outputsize=200"
        f"&apikey={TWELVEDATA_API_KEY}"
    )

    try:
        response = requests.get(url, timeout=15).json()
        if "values" not in response:
            print(f"[IndicatorEngine] ⚠️  Twelve Data API Error cho {symbol}/{timeframe}: {response.get('message', response)}")
            return None

        data = response["values"]
        df = pd.DataFrame(data)
        # Twelve Data trả về nến mới nhất trước (descending), đảo ngược (ascending)
        df = df.iloc[::-1].reset_index(drop=True)

        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)

        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)

        df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}, inplace=True)
        return df

    except Exception as e:
        print(f"[IndicatorEngine] ⚠️  Lỗi tải {symbol}/{timeframe} qua Twelve Data: {e}")
        return None


def _compute_indicators(df: pd.DataFrame, timeframe: str) -> IndicatorSnapshot:
    """Tính EMA, BB, ATR, RSI, MACD, Stochastic từ OHLC DataFrame."""
    close = df["Close"].squeeze()
    high  = df["High"].squeeze()
    low   = df["Low"].squeeze()

    def safe_last(series) -> Optional[float]:
        if series is None:
            return None
        s = pd.Series(series).dropna()
        return round(float(s.iloc[-1]), 5) if not s.empty else None

    # EMA
    ema20 = ta_lib.trend.EMAIndicator(close, window=EMA_FAST).ema_indicator()
    ema50 = ta_lib.trend.EMAIndicator(close, window=EMA_SLOW).ema_indicator()

    # Bollinger Bands
    bb_ind   = ta_lib.volatility.BollingerBands(close, window=BB_PERIOD, window_dev=BB_STD)
    bb_upper = bb_ind.bollinger_hband()
    bb_mid   = bb_ind.bollinger_mavg()
    bb_lower = bb_ind.bollinger_lband()

    # ATR
    atr = ta_lib.volatility.AverageTrueRange(high, low, close, window=ATR_PERIOD).average_true_range()

    # RSI
    rsi = ta_lib.momentum.RSIIndicator(close, window=RSI_PERIOD).rsi()

    # MACD (12, 26, 9) — tiêu chuẩn
    macd_ind    = ta_lib.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    macd_line   = macd_ind.macd()
    macd_signal = macd_ind.macd_signal()
    macd_hist   = macd_ind.macd_diff()

    # Stochastic (14, 3)
    stoch_ind = ta_lib.momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)
    stoch_k   = stoch_ind.stoch()
    stoch_d   = stoch_ind.stoch_signal()

    return IndicatorSnapshot(
        timeframe    = timeframe,
        ema20        = safe_last(ema20),
        ema50        = safe_last(ema50),
        bb_upper     = safe_last(bb_upper),
        bb_middle    = safe_last(bb_mid),
        bb_lower     = safe_last(bb_lower),
        atr14        = safe_last(atr),
        rsi14        = safe_last(rsi),
        macd_line    = safe_last(macd_line),
        macd_signal  = safe_last(macd_signal),
        macd_hist    = safe_last(macd_hist),
        stoch_k      = safe_last(stoch_k),
        stoch_d      = safe_last(stoch_d),
    )


# ─────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────

class IndicatorEngine:
    """
    Tính toán EMA 20/50, BB, ATR, RSI, MACD, Stoch cho các timeframe cần thiết.
    Cache OHLC data để tránh gọi API thừa và tái sử dụng cho live_price.
    """

    def __init__(self, symbol: str, timeframes: list[str] | None = None):
        self.symbol     = symbol
        self.timeframes = timeframes or ["H1", "H4", "D1"]
        self._ohlc_cache: dict[str, pd.DataFrame] = {}   # cache dữ liệu đã tải

    def _get_ohlc(self, timeframe: str) -> Optional[pd.DataFrame]:
        """Lấy OHLC từ cache, hoặc tải mới nếu chưa có."""
        if timeframe not in self._ohlc_cache:
            df = _fetch_ohlc(self.symbol, timeframe)
            if df is not None:
                self._ohlc_cache[timeframe] = df
        return self._ohlc_cache.get(timeframe)

    def compute(self) -> list[IndicatorSnapshot]:
        """Tính toán indicator cho tất cả timeframe."""
        results: list[IndicatorSnapshot] = []

        for tf in self.timeframes:
            print(f"[IndicatorEngine] Tính indicator {self.symbol}/{tf}...")
            df = self._get_ohlc(tf)
            if df is None or len(df) < max(EMA_SLOW, BB_PERIOD) + 5:
                print(f"[IndicatorEngine] ⚠️  Không đủ dữ liệu cho {tf}")
                results.append(IndicatorSnapshot(timeframe=tf))
                continue

            snap = _compute_indicators(df, tf)
            results.append(snap)
            print(
                f"[IndicatorEngine] ✅ {tf}: "
                f"EMA20={snap.ema20} | EMA50={snap.ema50} | "
                f"ATR={snap.atr14} | RSI={snap.rsi14} | "
                f"MACD={snap.macd_hist} | Stoch={snap.stoch_k}"
            )

        return results

    def get_live_price(self) -> Optional[float]:
        """
        Lấy giá hiện tại từ cache (nếu đã tải) hoặc tải M5/D1.
        Ưu tiên dùng lại dữ liệu đã cache để tiết kiệm API quota.
        """
        # Ưu tiên M15 hoặc timeframe nhỏ nhất đã cache
        for tf in ["M15", "M30", "H1", "H4", "D1"]:
            if tf in self._ohlc_cache:
                df = self._ohlc_cache[tf]
                if not df.empty:
                    return round(float(df["Close"].iloc[-1]), 5)

        # Fallback: tải M5 riêng nếu không có gì trong cache
        df = self._get_ohlc("M5")
        if df is not None and not df.empty:
            return round(float(df["Close"].iloc[-1]), 5)

        # Fallback cuối: tải D1
        df = self._get_ohlc("D1")
        if df is not None and not df.empty:
            return round(float(df["Close"].iloc[-1]), 5)

        return None
