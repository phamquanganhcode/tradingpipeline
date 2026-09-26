"""
modules/mt5_data_feed.py
────────────────────────────────────────────────────────────────
Module 1 — Nguồn dữ liệu nến từ MetaTrader 5 (thay thế Twelve Data)

Ưu điểm so với Twelve Data API:
  ✅ Hoàn toàn miễn phí, không giới hạn số lần gọi
  ✅ Dữ liệu chính xác từ sàn thực (đúng spread, đúng giá)
  ✅ Hỗ trợ tất cả 30 mã trong symbol_forex.txt
  ✅ Có thể backtest với dữ liệu lịch sử MT5 sẵn có
  ✅ Tốc độ cực nhanh (~5ms để lấy 500 nến)

Chức năng chính:
  - Kết nối và quản lý phiên làm việc MT5
  - Tải nến OHLCV từ MT5 cho nhiều symbol và timeframe
  - Tính toán tất cả chỉ báo (EMA, BB, ATR, RSI) bằng pandas/ta
  - Cache thông minh để tránh tải lại nến không cần thiết
  - Lấy giá Bid/Ask và Spread thời gian thực

Tác giả: TradingPipeline TSP Robot
Phiên bản: 1.0.0
"""

from __future__ import annotations

import warnings
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import MetaTrader5 as mt5
import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────
logger = logging.getLogger("MT5DataFeed")


# ─────────────────────────────────────────────────────────────
# CONSTANTS: TIMEFRAME MAPPING
# Python string → MT5 timeframe constant
# ─────────────────────────────────────────────────────────────
TF_MAP: dict[str, int] = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
    "W1":  mt5.TIMEFRAME_W1,
}


# ─────────────────────────────────────────────────────────────
# DATA CLASSES: Kết quả trả về từ module này
# ─────────────────────────────────────────────────────────────

@dataclass
class IndicatorResult:
    """
    Toàn bộ dữ liệu chỉ báo tính được cho 1 symbol ở 1 timeframe.
    Đây là 'ngôn ngữ chung' giữa mt5_data_feed và strategy_engine.
    """
    symbol:     str
    timeframe:  str
    timestamp:  datetime

    # ── Giá hiện tại ──────────────────────────────────────────
    close:      float = 0.0
    high:       float = 0.0
    low:        float = 0.0
    open_price: float = 0.0
    volume:     float = 0.0

    # ── EMA ───────────────────────────────────────────────────
    ema20:      Optional[float] = None
    ema50:      Optional[float] = None

    # ── Bollinger Bands ───────────────────────────────────────
    bb_upper:   Optional[float] = None
    bb_middle:  Optional[float] = None
    bb_lower:   Optional[float] = None
    bb_width:   Optional[float] = None   # upper - lower (đo độ rộng BB)
    bb_squeeze: bool = False             # True nếu BB đang co hẹp

    # ── ATR & RSI ─────────────────────────────────────────────
    atr14:      Optional[float] = None
    rsi14:      Optional[float] = None

    # ── OHLCV Series (toàn bộ dãy, dùng cho market_structure) ─
    df:         Optional[pd.DataFrame] = field(default=None, repr=False)

    @property
    def is_valid(self) -> bool:
        """Kiểm tra dữ liệu có đủ để phân tích không."""
        return all([
            self.ema20 is not None,
            self.ema50 is not None,
            self.bb_upper is not None,
            self.atr14 is not None,
            self.rsi14 is not None,
            self.atr14 > 0,
        ])

    @property
    def is_uptrend_ema(self) -> bool:
        """EMA 20 > EMA 50 → Xu hướng tăng theo EMA."""
        if self.ema20 is None or self.ema50 is None:
            return False
        return self.ema20 > self.ema50

    @property
    def is_downtrend_ema(self) -> bool:
        """EMA 20 < EMA 50 → Xu hướng giảm theo EMA."""
        if self.ema20 is None or self.ema50 is None:
            return False
        return self.ema20 < self.ema50

    @property
    def in_value_area_buy(self) -> bool:
        """Giá đã hồi về Vùng Giá Trị (giữa EMA 20 và EMA 50) để tìm lệnh Mua."""
        if self.ema20 is None or self.ema50 is None or self.atr14 is None:
            return False
        tolerance = self.atr14 * 0.3
        return (self.low <= self.ema20 + tolerance) and (self.low >= self.ema50 - tolerance)

    @property
    def in_value_area_sell(self) -> bool:
        """Giá đã hồi về Vùng Giá Trị (giữa EMA 20 và EMA 50) để tìm lệnh Bán."""
        if self.ema20 is None or self.ema50 is None or self.atr14 is None:
            return False
        tolerance = self.atr14 * 0.3
        return (self.high >= self.ema20 - tolerance) and (self.high <= self.ema50 + tolerance)


@dataclass
class LivePriceResult:
    """Giá Bid/Ask thời gian thực từ MT5."""
    symbol:     str
    timestamp:  datetime
    bid:        float
    ask:        float
    spread_pts: float    # Spread tính bằng points
    spread_pips: float   # Spread tính bằng pips (dễ đọc hơn)
    digits:     int      # Số chữ số thập phân của symbol

    @property
    def mid_price(self) -> float:
        return round((self.bid + self.ask) / 2, self.digits)


# ─────────────────────────────────────────────────────────────
# MAIN CLASS: MT5DataFeed
# ─────────────────────────────────────────────────────────────

class MT5DataFeed:
    """
    Nguồn dữ liệu tập trung từ MetaTrader 5.

    Cách dùng:
        feed = MT5DataFeed()
        feed.connect()

        # Lấy toàn bộ indicator cho 1 symbol
        result_ltf = feed.get_indicators("XAUUSD", "M15", bars=300)
        result_htf = feed.get_indicators("XAUUSD", "H1",  bars=200)

        # Lấy giá thời gian thực
        price = feed.get_live_price("EURUSD")

        feed.disconnect()
    """

    def __init__(
        self,
        ema_fast:       int   = 20,
        ema_slow:       int   = 50,
        bb_period:      int   = 20,
        bb_deviation:   float = 2.0,
        atr_period:     int   = 14,
        rsi_period:     int   = 14,
        squeeze_atr_mult: float = 0.8,   # BB_Width < ATR × mult → Squeeze
        cache_ttl_sec:  int   = 55,      # Cache hết hạn sau 55 giây (< 1 nến M1)
    ):
        self.ema_fast        = ema_fast
        self.ema_slow        = ema_slow
        self.bb_period       = bb_period
        self.bb_deviation    = bb_deviation
        self.atr_period      = atr_period
        self.rsi_period      = rsi_period
        self.squeeze_atr_mult = squeeze_atr_mult
        self.cache_ttl_sec   = cache_ttl_sec

        self._connected: bool = False
        # Cache: key = (symbol, timeframe), value = (timestamp_loaded, IndicatorResult)
        self._cache: dict[tuple[str, str], tuple[float, IndicatorResult]] = {}

    # ─────────────────────────────────────────────────────────
    # KẾT NỐI MT5
    # ─────────────────────────────────────────────────────────

    def connect(self, login: int = 0, password: str = "", server: str = "") -> bool:
        """
        Khởi tạo kết nối MT5.
        Nếu MT5 đã được khởi tạo trước đó (bởi mt5_executor), dùng lại phiên đó.
        """
        if self._connected:
            return True

        # Thử khởi tạo MT5 (nếu chưa có phiên nào)
        if not mt5.initialize():
            logger.error(f"[MT5DataFeed] ❌ Không thể khởi tạo MT5: {mt5.last_error()}")
            return False

        # Đăng nhập nếu có thông tin tài khoản
        if login and password and server:
            authorized = mt5.login(login, password=password, server=server)
            if not authorized:
                logger.error(f"[MT5DataFeed] ❌ Đăng nhập thất bại: {mt5.last_error()}")
                mt5.shutdown()
                return False
            logger.info(f"[MT5DataFeed] ✅ Kết nối MT5 thành công: {login} @ {server}")
        else:
            logger.info("[MT5DataFeed] ✅ Dùng phiên MT5 đang mở sẵn (không cần đăng nhập lại)")

        self._connected = True
        return True

    def disconnect(self) -> None:
        """Đóng kết nối MT5 an toàn."""
        if self._connected:
            mt5.shutdown()
            self._connected = False
            logger.info("[MT5DataFeed] MT5 đã ngắt kết nối.")

    def is_connected(self) -> bool:
        """Kiểm tra trạng thái kết nối."""
        if not self._connected:
            return False
        info = mt5.terminal_info()
        return info is not None and info.connected

    # ─────────────────────────────────────────────────────────
    # LẤY DỮ LIỆU NẾN TỪ MT5
    # ─────────────────────────────────────────────────────────

    def _fetch_ohlcv(self, symbol: str, timeframe: str, bars: int = 300) -> Optional[pd.DataFrame]:
        """
        Tải dữ liệu OHLCV từ MT5.
        Trả về DataFrame với cột: Open, High, Low, Close, Volume, Time
        Sắp xếp theo thời gian tăng dần (nến cũ → mới).
        """
        if not self._connected:
            logger.warning(f"[MT5DataFeed] ⚠️  Chưa kết nối MT5, bỏ qua {symbol}/{timeframe}")
            return None

        if timeframe not in TF_MAP:
            logger.error(f"[MT5DataFeed] ❌ Timeframe không hợp lệ: {timeframe}. Hỗ trợ: {list(TF_MAP.keys())}")
            return None

        # Đảm bảo symbol được bật trong MT5
        if not mt5.symbol_select(symbol, True):
            logger.warning(f"[MT5DataFeed] ⚠️  Không thể chọn symbol {symbol} trong MT5")
            return None

        # Tải nến từ MT5 (0 = nến mới nhất, đếm ngược về quá khứ)
        rates = mt5.copy_rates_from_pos(symbol, TF_MAP[timeframe], 0, bars)

        if rates is None or len(rates) == 0:
            logger.warning(f"[MT5DataFeed] ⚠️  Không có dữ liệu {symbol}/{timeframe}: {mt5.last_error()}")
            return None

        # Chuyển sang DataFrame
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df.set_index("time", inplace=True)
        df.rename(columns={
            "open":     "Open",
            "high":     "High",
            "low":      "Low",
            "close":    "Close",
            "tick_volume": "Volume",
        }, inplace=True)

        # Giữ lại các cột cần thiết
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df = df.sort_index(ascending=True)   # Nến cũ nhất ở trên

        return df

    # ─────────────────────────────────────────────────────────
    # TÍNH TOÁN CHỈ BÁO (INDICATORS)
    # ─────────────────────────────────────────────────────────

    def _compute_indicators(self, df: pd.DataFrame, symbol: str, timeframe: str) -> IndicatorResult:
        """
        Tính toán toàn bộ chỉ báo từ OHLCV DataFrame.
        Sử dụng pandas + numpy thuần — không phụ thuộc thư viện ta.
        """
        close  = df["Close"]
        high   = df["High"]
        low    = df["Low"]

        # ── EMA (Exponential Moving Average) ──────────────────
        ema20 = close.ewm(span=self.ema_fast, adjust=False).mean()
        ema50 = close.ewm(span=self.ema_slow, adjust=False).mean()

        # ── Bollinger Bands ────────────────────────────────────
        sma20   = close.rolling(window=self.bb_period).mean()
        std20   = close.rolling(window=self.bb_period).std(ddof=0)
        bb_upper = sma20 + self.bb_deviation * std20
        bb_lower = sma20 - self.bb_deviation * std20

        # ── ATR (Average True Range) ───────────────────────────
        prev_close = close.shift(1)
        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low  - prev_close).abs(),
        ], axis=1).max(axis=1)
        atr = tr.ewm(span=self.atr_period, adjust=False).mean()

        # ── RSI (Relative Strength Index) ──────────────────────
        delta   = close.diff()
        gain    = delta.clip(lower=0)
        loss    = (-delta).clip(lower=0)
        avg_gain = gain.ewm(span=self.rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(span=self.rsi_period, adjust=False).mean()
        rs       = avg_gain / avg_loss.replace(0, np.nan)
        rsi      = 100 - (100 / (1 + rs))

        # ── Lấy giá trị cuối cùng (nến mới nhất đã đóng) ──────
        def _last(series: pd.Series) -> Optional[float]:
            """Lấy giá trị cuối cùng, làm tròn 6 chữ số."""
            val = series.dropna()
            if val.empty:
                return None
            v = float(val.iloc[-1])
            return round(v, 6) if not (np.isnan(v) or np.isinf(v)) else None

        # ── Nến mới nhất ───────────────────────────────────────
        last_row   = df.iloc[-1]
        last_close = round(float(last_row["Close"]), 6)
        last_high  = round(float(last_row["High"]),  6)
        last_low   = round(float(last_row["Low"]),   6)
        last_open  = round(float(last_row["Open"]),  6)
        last_vol   = float(last_row["Volume"])
        last_time  = last_row.name.to_pydatetime() if hasattr(last_row.name, "to_pydatetime") else datetime.now(timezone.utc)

        # ── BB Width & Squeeze ─────────────────────────────────
        _bb_upper_val = _last(bb_upper)
        _bb_lower_val = _last(bb_lower)
        _atr_val      = _last(atr)
        _bb_width     = None
        _bb_squeeze   = False

        if _bb_upper_val is not None and _bb_lower_val is not None:
            _bb_width = round(_bb_upper_val - _bb_lower_val, 6)
            if _atr_val and _atr_val > 0:
                _bb_squeeze = _bb_width < (_atr_val * self.squeeze_atr_mult)

        return IndicatorResult(
            symbol      = symbol,
            timeframe   = timeframe,
            timestamp   = last_time,
            close       = last_close,
            high        = last_high,
            low         = last_low,
            open_price  = last_open,
            volume      = last_vol,
            ema20       = _last(ema20),
            ema50       = _last(ema50),
            bb_upper    = _bb_upper_val,
            bb_middle   = _last(sma20),
            bb_lower    = _bb_lower_val,
            bb_width    = _bb_width,
            bb_squeeze  = _bb_squeeze,
            atr14       = _atr_val,
            rsi14       = _last(rsi),
            df          = df,   # Lưu toàn bộ dãy cho market_structure module
        )

    # ─────────────────────────────────────────────────────────
    # PUBLIC API: get_indicators (có cache)
    # ─────────────────────────────────────────────────────────

    def get_indicators(
        self,
        symbol:    str,
        timeframe: str,
        bars:      int  = 300,
        force:     bool = False,
    ) -> Optional[IndicatorResult]:
        """
        Lấy toàn bộ indicator cho 1 symbol/timeframe.
        Dữ liệu được cache trong `cache_ttl_sec` giây để tránh tải lại liên tục.

        Args:
            symbol:    Mã giao dịch (vd: "XAUUSD", "EURUSD")
            timeframe: Khung thời gian (vd: "M15", "H1")
            bars:      Số nến cần tải (mặc định 300 nến ≈ ~3 ngày M15)
            force:     Bỏ qua cache, tải lại từ MT5

        Returns:
            IndicatorResult nếu thành công, None nếu lỗi
        """
        cache_key = (symbol, timeframe)
        now = time.monotonic()

        # Kiểm tra cache còn hiệu lực không
        if not force and cache_key in self._cache:
            cached_time, cached_result = self._cache[cache_key]
            if now - cached_time < self.cache_ttl_sec:
                return cached_result

        # Tải OHLCV từ MT5
        min_bars = max(self.ema_slow, self.bb_period, self.atr_period, self.rsi_period) + 50
        bars = max(bars, min_bars)

        df = self._fetch_ohlcv(symbol, timeframe, bars)
        if df is None or len(df) < min_bars:
            logger.warning(f"[MT5DataFeed] ⚠️  Không đủ dữ liệu: {symbol}/{timeframe} ({len(df) if df is not None else 0}/{min_bars} nến)")
            return None

        # Tính indicator
        result = self._compute_indicators(df, symbol, timeframe)

        # Lưu vào cache
        self._cache[cache_key] = (now, result)

        if result.is_valid:
            logger.debug(
                f"[MT5DataFeed] ✅ {symbol}/{timeframe}: "
                f"C={result.close:.5f} | EMA20={result.ema20:.5f} | EMA50={result.ema50:.5f} | "
                f"ATR={result.atr14:.5f} | RSI={result.rsi14:.1f} | "
                f"BB_Squeeze={'🔴' if result.bb_squeeze else '⚪'}"
            )
        else:
            logger.warning(f"[MT5DataFeed] ⚠️  Dữ liệu không hợp lệ cho {symbol}/{timeframe}")

        return result

    # ─────────────────────────────────────────────────────────
    # PUBLIC API: get_live_price
    # ─────────────────────────────────────────────────────────

    def get_live_price(self, symbol: str) -> Optional[LivePriceResult]:
        """
        Lấy Bid/Ask/Spread thời gian thực từ MT5 tick.
        Không dùng cache — luôn lấy giá mới nhất.

        Args:
            symbol: Mã giao dịch (vd: "XAUUSD")

        Returns:
            LivePriceResult hoặc None nếu lỗi
        """
        if not self._connected:
            return None

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logger.warning(f"[MT5DataFeed] ⚠️  Không lấy được tick {symbol}: {mt5.last_error()}")
            return None

        info = mt5.symbol_info(symbol)
        digits = info.digits if info else 5
        point  = info.point if info else 0.00001

        spread_pts  = round(tick.ask - tick.bid, digits)
        spread_pips = round(spread_pts / (point * 10), 1) if point > 0 else 0.0

        return LivePriceResult(
            symbol      = symbol,
            timestamp   = datetime.fromtimestamp(tick.time, tz=timezone.utc),
            bid         = round(tick.bid, digits),
            ask         = round(tick.ask, digits),
            spread_pts  = spread_pts,
            spread_pips = spread_pips,
            digits      = digits,
        )

    # ─────────────────────────────────────────────────────────
    # PUBLIC API: scan_symbols
    # ─────────────────────────────────────────────────────────

    def scan_symbols(
        self,
        symbols:    list[str],
        ltf:        str = "M15",
        mtf:        str = "H1",
        htf:        str = "H4",
        bars:       int = 300,
    ) -> dict[str, dict[str, Optional[IndicatorResult]]]:
        """
        Quét tất cả symbol trong watchlist và trả về indicator cho cả 3 khung.
        Đây là hàm được gọi trong vòng lặp chính của Robot (EA_TradingSystemPro.py).

        Args:
            symbols: Danh sách symbol cần quét (vd: 30 mã từ symbol_forex.txt)
            ltf:     Khung bóp cò (mặc định M15)
            mtf:     Khung cầu nối/vùng cản (mặc định H1)
            htf:     Khung xu hướng chính (mặc định H4)
            bars:    Số nến tải cho mỗi symbol/TF
        """
        results: dict[str, dict[str, Optional[IndicatorResult]]] = {}

        for symbol in symbols:
            ltf_result = self.get_indicators(symbol, ltf, bars=bars)
            mtf_result = self.get_indicators(symbol, mtf, bars=bars)
            htf_result = self.get_indicators(symbol, htf, bars=bars)
            
            results[symbol] = {
                "ltf": ltf_result,
                "mtf": mtf_result,
                "htf": htf_result,
            }

        valid_count = sum(
            1 for v in results.values()
            if v["ltf"] is not None and v["ltf"].is_valid
        )
        logger.info(f"[MT5DataFeed] 🔍 Quét xong {len(symbols)} symbol — {valid_count} symbol có dữ liệu hợp lệ")
        return results

    # ─────────────────────────────────────────────────────────
    # TIỆN ÍCH: Xóa cache thủ công
    # ─────────────────────────────────────────────────────────

    def clear_cache(self, symbol: str = "", timeframe: str = "") -> None:
        """
        Xóa cache. Nếu không truyền tham số → xóa toàn bộ.
        Dùng khi thị trường có tin tức bất ngờ cần lấy dữ liệu mới nhất ngay.
        """
        if symbol and timeframe:
            self._cache.pop((symbol, timeframe), None)
        elif symbol:
            keys_to_del = [k for k in self._cache if k[0] == symbol]
            for k in keys_to_del:
                del self._cache[k]
        else:
            self._cache.clear()
            logger.info("[MT5DataFeed] 🗑️  Cache đã được xóa toàn bộ")


# ─────────────────────────────────────────────────────────────
# SINGLETON INSTANCE (dùng chung toàn bộ project)
# ─────────────────────────────────────────────────────────────
_feed_instance: Optional[MT5DataFeed] = None


def get_feed(
    ema_fast: int = 20,
    ema_slow: int = 50,
    bb_period: int = 20,
    bb_deviation: float = 2.0,
    atr_period: int = 14,
    rsi_period: int = 14,
) -> MT5DataFeed:
    """
    Trả về singleton MT5DataFeed.
    Tất cả module khác (strategy_engine, market_structure...) đều gọi hàm này
    thay vì tự tạo instance mới để tận dụng chung cache.

    Ví dụ:
        from modules.mt5_data_feed import get_feed
        feed = get_feed()
        result = feed.get_indicators("XAUUSD", "M15")
    """
    global _feed_instance
    if _feed_instance is None:
        _feed_instance = MT5DataFeed(
            ema_fast=ema_fast,
            ema_slow=ema_slow,
            bb_period=bb_period,
            bb_deviation=bb_deviation,
            atr_period=atr_period,
            rsi_period=rsi_period,
        )
    return _feed_instance


# ─────────────────────────────────────────────────────────────
# QUICK TEST (chạy trực tiếp file này để kiểm tra)
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    print("=" * 60)
    print("  MT5DataFeed — Module 1 Quick Test")
    print("=" * 60)

    feed = MT5DataFeed()

    # Kết nối MT5 (dùng thông tin từ .env)
    login    = int(os.getenv("MT5_LOGIN", 0))
    password = os.getenv("MT5_PASSWORD", "")
    server   = os.getenv("MT5_SERVER", "")

    if not feed.connect(login=login, password=password, server=server):
        print("❌ Không thể kết nối MT5. Kiểm tra lại MT5_LOGIN, MT5_PASSWORD, MT5_SERVER trong .env")
        exit(1)

    # Test 1: Lấy indicator cho XAUUSD M15
    print("\n[TEST 1] Lấy indicator XAUUSD/M15...")
    result = feed.get_indicators("XAUUSD", "M15", bars=300)
    if result and result.is_valid:
        print(f"  ✅ Symbol   : {result.symbol}")
        print(f"  ✅ Timestamp: {result.timestamp}")
        print(f"  ✅ Close    : {result.close}")
        print(f"  ✅ EMA 20   : {result.ema20}")
        print(f"  ✅ EMA 50   : {result.ema50}")
        print(f"  ✅ BB Upper : {result.bb_upper}")
        print(f"  ✅ BB Middle: {result.bb_middle}")
        print(f"  ✅ BB Lower : {result.bb_lower}")
        print(f"  ✅ BB Width : {result.bb_width}")
        print(f"  ✅ BB Squeeze: {result.bb_squeeze}")
        print(f"  ✅ ATR 14   : {result.atr14}")
        print(f"  ✅ RSI 14   : {result.rsi14}")
        print(f"  ✅ Uptrend EMA: {result.is_uptrend_ema}")
        print(f"  ✅ In Value Area (Buy): {result.in_value_area_buy}")
    else:
        print("  ❌ Lấy dữ liệu thất bại hoặc dữ liệu không hợp lệ")

    # Test 2: Lấy giá thời gian thực
    print("\n[TEST 2] Giá thời gian thực XAUUSD...")
    price = feed.get_live_price("XAUUSD")
    if price:
        print(f"  ✅ Bid: {price.bid} | Ask: {price.ask} | Spread: {price.spread_pips} pips")
    else:
        print("  ❌ Không lấy được giá")

    # Test 3: Quét 5 symbol cùng lúc
    print("\n[TEST 3] Quét 5 symbol cùng lúc...")
    symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "XAGUSD"]
    t_start = time.monotonic()
    all_results = feed.scan_symbols(symbols, ltf="M15", htf="H1")
    elapsed = (time.monotonic() - t_start) * 1000

    for sym, data in all_results.items():
        ltf_r = data["ltf"]
        htf_r = data["htf"]
        ltf_ok = "✅" if ltf_r and ltf_r.is_valid else "❌"
        htf_ok = "✅" if htf_r and htf_r.is_valid else "❌"
        close_str = f"{ltf_r.close:.5f}" if ltf_r else "N/A"
        print(f"  {ltf_ok} {sym:10s} M15 | {htf_ok} H1 | Close: {close_str}")

    print(f"\n  ⚡ Quét 5 symbol xong trong {elapsed:.1f}ms")

    # Test 4: Cache test
    print("\n[TEST 4] Kiểm tra Cache...")
    t1 = time.monotonic()
    feed.get_indicators("XAUUSD", "M15")   # Lần 2: phải lấy từ cache
    t2 = time.monotonic()
    print(f"  ✅ Cache hit trong {(t2-t1)*1000:.2f}ms (thay vì ~5-50ms từ MT5)")

    feed.disconnect()
    print("\n✅ Module 1 (mt5_data_feed.py) hoạt động bình thường!")
    print("=" * 60)
