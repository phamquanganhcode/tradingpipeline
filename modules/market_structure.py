"""
modules/market_structure.py
────────────────────────────────────────────────────────────────
Module 2 — Nhận diện Cấu trúc Thị trường (Market Structure)

Các khái niệm được implement:
  - Swing Points (Đỉnh/Đáy) bằng phương pháp Fractal N-Bar
  - HH (Higher High) / HL (Higher Low) → Xu hướng TĂNG
  - LH (Lower High)  / LL (Lower Low)  → Xu hướng GIẢM
  - BOS (Break of Structure) → Xác nhận xu hướng tiếp diễn
  - CHoCH (Change of Character) → Cảnh báo đảo chiều sớm
  - No-Trade Zone → Thị trường đi ngang, cấm giao dịch

Phụ thuộc:
  - Module 1: modules/mt5_data_feed.py (IndicatorResult)

Tác giả: TradingPipeline TSP Robot
Phiên bản: 1.0.0
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional

import numpy as np
import pandas as pd

from modules.mt5_data_feed import IndicatorResult

logger = logging.getLogger("MarketStructure")


# ─────────────────────────────────────────────────────────────
# DATA CLASSES
# ─────────────────────────────────────────────────────────────

@dataclass
class SwingPoint:
    """Một điểm Swing High hoặc Swing Low đã được xác nhận."""
    index:     int                      # Vị trí (chỉ số hàng) trong DataFrame
    price:     float                    # Giá tại điểm swing
    timestamp: datetime                 # Thời gian của nến
    kind:      Literal["high", "low"]   # Loại: đỉnh hay đáy

    def __repr__(self) -> str:
        ts = self.timestamp.strftime("%m-%d %H:%M")
        return f"Swing{self.kind.title()}({self.price:.5f} @ {ts})"


@dataclass
class MarketStructureResult:
    """
    Kết quả phân tích cấu trúc thị trường cho 1 symbol/timeframe.
    Đây là đầu vào cho candle_pattern.py và strategy_engine.py.
    """
    symbol:    str
    timeframe: str

    # ── Xu hướng tổng thể ─────────────────────────────────────
    trend: Literal["uptrend", "downtrend", "sideways"] = "sideways"

    # ── Cấu trúc đỉnh/đáy ─────────────────────────────────────
    is_hh: bool = False   # Higher High: đỉnh mới > đỉnh trước
    is_hl: bool = False   # Higher Low:  đáy mới  > đáy trước
    is_lh: bool = False   # Lower High:  đỉnh mới < đỉnh trước
    is_ll: bool = False   # Lower Low:   đáy mới  < đáy trước

    # ── Sự kiện đặc biệt ──────────────────────────────────────
    bos_bullish:  bool = False  # BOS tăng: xác nhận tiếp diễn uptrend
    bos_bearish:  bool = False  # BOS giảm: xác nhận tiếp diễn downtrend
    choch:        bool = False  # CHoCH: cảnh báo đảo chiều sớm
    no_trade_zone: bool = True  # Sideway / nhiễu → cấm giao dịch

    # ── Mức giá Swing Points gần nhất ─────────────────────────
    last_swing_high: float = 0.0   # Đỉnh Swing gần nhất
    last_swing_low:  float = 0.0   # Đáy Swing gần nhất
    prev_swing_high: float = 0.0   # Đỉnh Swing trước đó
    prev_swing_low:  float = 0.0   # Đáy Swing trước đó

    # ── Toàn bộ danh sách Swing Points (để vẽ biểu đồ/debug) ─
    swing_highs: list[SwingPoint] = field(default_factory=list)
    swing_lows:  list[SwingPoint] = field(default_factory=list)

    # ── Thông tin bổ sung ──────────────────────────────────────
    reason: str = ""   # Lý do kết luận (debug)

    # ── PROPERTIES TIỆN LỢI ────────────────────────────────────

    @property
    def is_valid_uptrend(self) -> bool:
        """Uptrend hợp lệ: có HH + HL và không phải No-Trade Zone."""
        return self.is_hh and self.is_hl and not self.no_trade_zone

    @property
    def is_valid_downtrend(self) -> bool:
        """Downtrend hợp lệ: có LH + LL và không phải No-Trade Zone."""
        return self.is_lh and self.is_ll and not self.no_trade_zone

    @property
    def allow_buy(self) -> bool:
        """
        Cho phép tìm lệnh MUA không?
        Cần: uptrend hợp lệ VÀ không có cảnh báo đảo chiều (CHoCH).
        """
        return self.is_valid_uptrend and not self.choch

    @property
    def allow_sell(self) -> bool:
        """
        Cho phép tìm lệnh BÁN không?
        Cần: downtrend hợp lệ VÀ không có cảnh báo đảo chiều (CHoCH).
        """
        return self.is_valid_downtrend and not self.choch

    def summary(self) -> str:
        """Tóm tắt ngắn gọn để log ra terminal."""
        trend_emoji = {"uptrend": "↑", "downtrend": "↓", "sideways": "→"}.get(self.trend, "?")
        flags = []
        if self.is_hh: flags.append("HH")
        if self.is_hl: flags.append("HL")
        if self.is_lh: flags.append("LH")
        if self.is_ll: flags.append("LL")
        if self.bos_bullish:  flags.append("BOS↑")
        if self.bos_bearish:  flags.append("BOS↓")
        if self.choch:        flags.append("CHoCH!")
        if self.no_trade_zone: flags.append("NTZ")
        flags_str = " | ".join(flags) if flags else "none"
        allow = []
        if self.allow_buy:  allow.append("BUY_OK")
        if self.allow_sell: allow.append("SELL_OK")
        allow_str = " ".join(allow) if allow else "WAIT"
        return (
            f"{trend_emoji} {self.trend.upper():10s} | {flags_str:30s} | "
            f"SH={self.last_swing_high:.5f} SL={self.last_swing_low:.5f} | {allow_str}"
        )


# ─────────────────────────────────────────────────────────────
# MAIN CLASS: MarketStructureAnalyzer
# ─────────────────────────────────────────────────────────────

class MarketStructureAnalyzer:
    """
    Phân tích cấu trúc thị trường từ dữ liệu OHLCV.

    Cách dùng:
        from modules.mt5_data_feed import get_feed
        from modules.market_structure import MarketStructureAnalyzer

        feed     = get_feed()
        analyzer = MarketStructureAnalyzer()

        ltf = feed.get_indicators("XAUUSD", "M15")
        htf = feed.get_indicators("XAUUSD", "H1")

        ltf_ms = analyzer.analyze(ltf)
        htf_ms = analyzer.analyze(htf)

        if htf_ms.allow_buy and ltf_ms.allow_buy:
            print("Cấu trúc MTF hợp lệ → Tìm điểm vào lệnh Mua")
    """

    def __init__(
        self,
        fractal_lookback:  int   = 5,    # Số nến mỗi bên để xác nhận Fractal
        min_swing_count:   int   = 2,    # Số cặp đỉnh/đáy tối thiểu
        atr_noise_filter:  float = 0.5,  # [TUNE] Lọc Swing Point quá gần nhau (từ 0.3 -> 0.5)
        squeeze_mult:      float = 0.8,  # BB Width < ATR × này → Squeeze
        ema_gap_mult:      float = 0.8,  # [TUNE] |EMA20-EMA50| < ATR × này → EMA xoắn
        spike_filter_mult: float = 4.0,  # Nến có range > ATR × này → bỏ qua (spike)
    ):
        self.fractal_lookback  = fractal_lookback
        self.min_swing_count   = min_swing_count
        self.atr_noise_filter  = atr_noise_filter
        self.squeeze_mult      = squeeze_mult
        self.ema_gap_mult      = ema_gap_mult
        self.spike_filter_mult = spike_filter_mult

    # ─────────────────────────────────────────────────────────
    # BƯỚC 1: TÌM SWING POINTS (Fractal N-Bar + Lọc ATR)
    # ─────────────────────────────────────────────────────────

    def find_swing_points(
        self,
        df:  pd.DataFrame,
        atr: float,
    ) -> tuple[list[SwingPoint], list[SwingPoint]]:
        """
        Tìm tất cả Swing Highs và Swing Lows bằng phương pháp Fractal.

        Định nghĩa Fractal:
          SwingHigh[i]: High[i] > High[i-n] ... High[i-1] VÀ High[i] > High[i+1] ... High[i+n]
          SwingLow[i]:  Low[i]  < Low[i-n]  ... Low[i-1]  VÀ Low[i]  < Low[i+1]  ... Low[i+n]

        Sau đó lọc nhiễu bằng ATR: bỏ các điểm quá gần điểm trước đó.

        Args:
            df:  DataFrame OHLCV (index = datetime)
            atr: Giá trị ATR hiện tại (dùng để lọc nhiễu)

        Returns:
            (swing_highs, swing_lows): Hai danh sách SwingPoint đã sắp xếp theo thời gian
        """
        n   = self.fractal_lookback
        high_arr = df["High"].values
        low_arr  = df["Low"].values
        times    = df.index

        # Tính ATR nhanh để lọc spike nếu atr=0
        if atr <= 0:
            ranges = high_arr - low_arr
            atr = float(np.mean(ranges[-20:])) if len(ranges) >= 20 else float(np.mean(ranges))

        noise_threshold = atr * self.atr_noise_filter
        spike_threshold = atr * self.spike_filter_mult

        raw_highs: list[SwingPoint] = []
        raw_lows:  list[SwingPoint] = []

        # Quét từng nến (bỏ qua n nến đầu và n nến cuối vì chưa có đủ nến 2 bên)
        for i in range(n, len(df) - n):
            candle_range = high_arr[i] - low_arr[i]

            # Bỏ qua nến spike bất thường (tin tức, lỗi dữ liệu)
            if candle_range > spike_threshold:
                continue

            # Kiểm tra Swing High
            left_highs  = high_arr[i - n: i]
            right_highs = high_arr[i + 1: i + n + 1]
            if high_arr[i] > np.max(left_highs) and high_arr[i] > np.max(right_highs):
                ts = times[i]
                if hasattr(ts, "to_pydatetime"):
                    ts = ts.to_pydatetime()
                raw_highs.append(SwingPoint(
                    index=i,
                    price=round(float(high_arr[i]), 6),
                    timestamp=ts,
                    kind="high",
                ))

            # Kiểm tra Swing Low
            left_lows  = low_arr[i - n: i]
            right_lows = low_arr[i + 1: i + n + 1]
            if low_arr[i] < np.min(left_lows) and low_arr[i] < np.min(right_lows):
                ts = times[i]
                if hasattr(ts, "to_pydatetime"):
                    ts = ts.to_pydatetime()
                raw_lows.append(SwingPoint(
                    index=i,
                    price=round(float(low_arr[i]), 6),
                    timestamp=ts,
                    kind="low",
                ))

        # Lọc nhiễu ATR: gộp các điểm quá gần nhau
        swing_highs = self._filter_noise(raw_highs, noise_threshold, keep="max")
        swing_lows  = self._filter_noise(raw_lows,  noise_threshold, keep="min")

        return swing_highs, swing_lows

    def _filter_noise(
        self,
        points:    list[SwingPoint],
        threshold: float,
        keep:      Literal["max", "min"] = "max",
    ) -> list[SwingPoint]:
        """
        Lọc các SwingPoint quá gần nhau (về giá).
        Nếu 2 điểm liên tiếp chênh nhau < threshold → Giữ lại điểm có giá cao hơn (đối với High)
        hoặc thấp hơn (đối với Low).
        """
        if not points:
            return []

        filtered: list[SwingPoint] = [points[0]]

        for curr in points[1:]:
            prev = filtered[-1]
            diff = abs(curr.price - prev.price)

            if diff < threshold:
                # Hai điểm quá gần → Giữ điểm "cực trị" hơn
                if keep == "max" and curr.price > prev.price:
                    filtered[-1] = curr
                elif keep == "min" and curr.price < prev.price:
                    filtered[-1] = curr
                # Ngược lại: giữ nguyên điểm cũ
            else:
                filtered.append(curr)

        return filtered

    # ─────────────────────────────────────────────────────────
    # BƯỚC 2: PHÂN LOẠI CẤU TRÚC (HH/HL/LH/LL)
    # ─────────────────────────────────────────────────────────

    def classify_structure(
        self,
        swing_highs: list[SwingPoint],
        swing_lows:  list[SwingPoint],
    ) -> tuple[bool, bool, bool, bool, Literal["uptrend", "downtrend", "sideways"]]:
        """
        Phân loại xu hướng dựa trên chuỗi Swing High / Swing Low.

        Returns:
            (is_hh, is_hl, is_lh, is_ll, trend)
        """
        is_hh = is_hl = is_lh = is_ll = False

        # Cần ít nhất 2 Swing Highs và 2 Swing Lows để so sánh
        if len(swing_highs) >= 2:
            last_sh = swing_highs[-1].price
            prev_sh = swing_highs[-2].price
            is_hh = last_sh > prev_sh   # Đỉnh mới cao hơn đỉnh cũ
            is_lh = last_sh < prev_sh   # Đỉnh mới thấp hơn đỉnh cũ

        if len(swing_lows) >= 2:
            last_sl = swing_lows[-1].price
            prev_sl = swing_lows[-2].price
            is_hl = last_sl > prev_sl   # Đáy mới cao hơn đáy cũ
            is_ll = last_sl < prev_sl   # Đáy mới thấp hơn đáy cũ

        # Phân loại xu hướng
        if is_hh and is_hl:
            trend: Literal["uptrend", "downtrend", "sideways"] = "uptrend"
        elif is_lh and is_ll:
            trend = "downtrend"
        else:
            trend = "sideways"

        return is_hh, is_hl, is_lh, is_ll, trend

    # ─────────────────────────────────────────────────────────
    # BƯỚC 3: PHÁT HIỆN BOS VÀ CHoCH
    # ─────────────────────────────────────────────────────────

    def detect_bos_choch(
        self,
        df:          pd.DataFrame,
        swing_highs: list[SwingPoint],
        swing_lows:  list[SwingPoint],
        trend:       Literal["uptrend", "downtrend", "sideways"],
    ) -> tuple[bool, bool, bool]:
        """
        Phát hiện Break of Structure (BOS) và Change of Character (CHoCH).

        BOS Tăng: Trong uptrend, giá đóng cửa TRÊN Swing High gần nhất
                  → Xác nhận xu hướng tăng tiếp diễn mạnh

        BOS Giảm: Trong downtrend, giá đóng cửa DƯỚI Swing Low gần nhất
                  → Xác nhận xu hướng giảm tiếp diễn mạnh

        CHoCH: Giá phá vỡ cấu trúc NGƯỢC chiều với xu hướng hiện tại
               → Cảnh báo đảo chiều sớm (chưa xác nhận đổi trend)

        Args:
            df:          DataFrame OHLCV
            swing_highs: Danh sách Swing Highs
            swing_lows:  Danh sách Swing Lows
            trend:       Xu hướng hiện tại

        Returns:
            (bos_bullish, bos_bearish, choch)
        """
        if trend == "sideways" or df.empty:
            return False, False, False

        # Lấy 3 nến gần nhất để kiểm tra (đủ để loại bỏ nhiễu 1 nến)
        recent_closes = df["Close"].values[-3:]
        if len(recent_closes) == 0:
            return False, False, False

        last_close = float(recent_closes[-1])
        bos_bullish = bos_bearish = choch = False

        if trend == "uptrend" and len(swing_highs) >= 1 and len(swing_lows) >= 1:
            last_sh_price = swing_highs[-1].price
            last_sl_price = swing_lows[-1].price

            # BOS Tăng: Giá đóng cửa TRÊN Swing High gần nhất
            if last_close > last_sh_price:
                bos_bullish = True

            # CHoCH trong uptrend: Giá đóng cửa DƯỚI Swing Low gần nhất
            # → Phe bán đang nắm quyền kiểm soát, cảnh báo đảo chiều
            if last_close < last_sl_price:
                choch = True

        elif trend == "downtrend" and len(swing_lows) >= 1 and len(swing_highs) >= 1:
            last_sl_price = swing_lows[-1].price
            last_sh_price = swing_highs[-1].price

            # BOS Giảm: Giá đóng cửa DƯỚI Swing Low gần nhất
            if last_close < last_sl_price:
                bos_bearish = True

            # CHoCH trong downtrend: Giá đóng cửa TRÊN Swing High gần nhất
            # → Phe mua đang phản công, cảnh báo đảo chiều
            if last_close > last_sh_price:
                choch = True

        return bos_bullish, bos_bearish, choch

    # ─────────────────────────────────────────────────────────
    # BƯỚC 4: PHÁT HIỆN NO-TRADE ZONE (Sideway)
    # ─────────────────────────────────────────────────────────

    def detect_no_trade_zone(
        self,
        atr:       float,
        bb_width:  Optional[float],
        ema20:     Optional[float],
        ema50:     Optional[float],
        trend:     Literal["uptrend", "downtrend", "sideways"],
    ) -> tuple[bool, str]:
        """
        Phát hiện thị trường đang sideway / nhiễu → Cấm giao dịch.

        3 tiêu chí kiểm tra:
          1. BB Width phẳng lì (< ATR × squeeze_mult)
          2. EMA 20 và EMA 50 xoắn vào nhau (gap < ATR × ema_gap_mult)
          3. Cấu trúc giá không rõ ràng (trend = sideways từ bước 2)

        Returns:
            (no_trade_zone: bool, reason: str)
        """
        reasons: list[str] = []

        # Bảo vệ: ATR không hợp lệ
        if not atr or atr <= 0:
            return True, "ATR=0 (dữ liệu không hợp lệ)"

        # Tiêu chí 1: BB phẳng lì
        bb_flat = False
        if bb_width is not None and bb_width > 0:
            bb_flat = bb_width < (atr * self.squeeze_mult)
            if bb_flat:
                reasons.append(f"BB_Width({bb_width:.5f}) < ATR×{self.squeeze_mult}({atr * self.squeeze_mult:.5f})")

        # Tiêu chí 2: EMA xoắn vào nhau
        ema_intertwined = False
        if ema20 is not None and ema50 is not None:
            ema_gap = abs(ema20 - ema50)
            ema_intertwined = ema_gap < (atr * self.ema_gap_mult)
            if ema_intertwined:
                reasons.append(f"EMA_gap({ema_gap:.5f}) < ATR×{self.ema_gap_mult}({atr * self.ema_gap_mult:.5f})")

        # Tiêu chí 3: Cấu trúc giá không rõ ràng
        structure_unclear = trend == "sideways"
        if structure_unclear:
            reasons.append("Không nhận diện được HH/HL hoặc LH/LL")

        # Kết luận: No-Trade Zone nếu ít nhất 2/3 tiêu chí thỏa mãn
        # (Không quá nghiêm ngặt — tránh bỏ lỡ kèo thật khi chỉ 1 tiêu chí kích hoạt)
        ntc_count = sum([bb_flat, ema_intertwined, structure_unclear])
        no_trade  = ntc_count >= 2

        reason_str = " | ".join(reasons) if reasons else "OK"
        return no_trade, reason_str

    # ─────────────────────────────────────────────────────────
    # HÀM CHÍNH: analyze()
    # ─────────────────────────────────────────────────────────

    def analyze(self, indicator: IndicatorResult) -> MarketStructureResult:
        """
        Phân tích đầy đủ cấu trúc thị trường từ IndicatorResult (Module 1).

        Đây là hàm DUY NHẤT mà strategy_engine.py cần gọi.

        Args:
            indicator: IndicatorResult từ MT5DataFeed.get_indicators()

        Returns:
            MarketStructureResult với đầy đủ thông tin xu hướng và tín hiệu
        """
        symbol    = indicator.symbol
        timeframe = indicator.timeframe

        # ── Khởi tạo kết quả mặc định (sideways, no-trade) ────
        default = MarketStructureResult(
            symbol=symbol,
            timeframe=timeframe,
            trend="sideways",
            no_trade_zone=True,
            reason="Khởi tạo mặc định",
        )

        # ── Kiểm tra dữ liệu đầu vào ──────────────────────────
        df  = indicator.df
        atr = indicator.atr14 or 0.0

        if df is None or df.empty:
            default.reason = "DataFrame rỗng"
            logger.warning(f"[MarketStructure] {symbol}/{timeframe}: DataFrame rỗng")
            return default

        min_bars_needed = self.fractal_lookback * 2 + self.min_swing_count * 5 + 10
        if len(df) < min_bars_needed:
            default.reason = f"Không đủ nến: {len(df)}/{min_bars_needed}"
            logger.warning(f"[MarketStructure] {symbol}/{timeframe}: {default.reason}")
            return default

        if atr <= 0:
            default.reason = "ATR không hợp lệ"
            return default

        # ── Bước 1: Tìm Swing Points ───────────────────────────
        swing_highs, swing_lows = self.find_swing_points(df, atr)

        if len(swing_highs) < self.min_swing_count or len(swing_lows) < self.min_swing_count:
            default.reason = (
                f"Không đủ Swing Points: "
                f"SH={len(swing_highs)}/{self.min_swing_count} | "
                f"SL={len(swing_lows)}/{self.min_swing_count}"
            )
            logger.debug(f"[MarketStructure] {symbol}/{timeframe}: {default.reason}")
            return default

        # ── Bước 2: Phân loại cấu trúc ────────────────────────
        is_hh, is_hl, is_lh, is_ll, trend = self.classify_structure(
            swing_highs, swing_lows
        )

        # ── Bước 3: Phát hiện BOS và CHoCH ────────────────────
        bos_bullish, bos_bearish, choch = self.detect_bos_choch(
            df, swing_highs, swing_lows, trend
        )

        # ── Bước 4: Phát hiện No-Trade Zone ───────────────────
        no_trade_zone, ntc_reason = self.detect_no_trade_zone(
            atr      = atr,
            bb_width = indicator.bb_width,
            ema20    = indicator.ema20,
            ema50    = indicator.ema50,
            trend    = trend,
        )

        # ── Lấy mức giá Swing Points gần nhất ─────────────────
        last_sh = swing_highs[-1].price if swing_highs else 0.0
        prev_sh = swing_highs[-2].price if len(swing_highs) >= 2 else 0.0
        last_sl = swing_lows[-1].price  if swing_lows  else 0.0
        prev_sl = swing_lows[-2].price  if len(swing_lows) >= 2  else 0.0

        # ── Tổng hợp kết quả ──────────────────────────────────
        result = MarketStructureResult(
            symbol          = symbol,
            timeframe       = timeframe,
            trend           = trend,
            is_hh           = is_hh,
            is_hl           = is_hl,
            is_lh           = is_lh,
            is_ll           = is_ll,
            bos_bullish     = bos_bullish,
            bos_bearish     = bos_bearish,
            choch           = choch,
            no_trade_zone   = no_trade_zone,
            last_swing_high = last_sh,
            last_swing_low  = last_sl,
            prev_swing_high = prev_sh,
            prev_swing_low  = prev_sl,
            swing_highs     = swing_highs,
            swing_lows      = swing_lows,
            reason          = ntc_reason,
        )

        logger.info(f"[MarketStructure] {symbol}/{timeframe}: {result.summary()}")
        return result

    def analyze_3tf(
        self,
        ltf_indicator: IndicatorResult,
        mtf_indicator: IndicatorResult,
        htf_indicator: IndicatorResult,
    ) -> tuple[MarketStructureResult, MarketStructureResult, MarketStructureResult]:
        """
        Phân tích cấu trúc cho cả 3 khung thời gian cùng lúc.
        Dùng cho mô hình Top-Down: H4 -> H1 -> M15.

        Returns:
            (ltf_ms, mtf_ms, htf_ms)
        """
        ltf_ms = self.analyze(ltf_indicator)
        mtf_ms = self.analyze(mtf_indicator)
        htf_ms = self.analyze(htf_indicator)
        return ltf_ms, mtf_ms, htf_ms


# ─────────────────────────────────────────────────────────────
# SINGLETON INSTANCE
# ─────────────────────────────────────────────────────────────
_analyzer_instance: Optional[MarketStructureAnalyzer] = None


def get_analyzer(
    fractal_lookback: int   = 5,
    min_swing_count:  int   = 2,
    atr_noise_filter: float = 0.5,
    squeeze_mult:     float = 0.8,
    ema_gap_mult:     float = 0.8,
) -> MarketStructureAnalyzer:
    """
    Trả về singleton MarketStructureAnalyzer.
    Dùng chung toàn bộ project để tránh tạo nhiều instance.

    Ví dụ:
        from modules.market_structure import get_analyzer
        analyzer = get_analyzer()
        ms = analyzer.analyze(indicator_result)
    """
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = MarketStructureAnalyzer(
            fractal_lookback=fractal_lookback,
            min_swing_count=min_swing_count,
            atr_noise_filter=atr_noise_filter,
            squeeze_mult=squeeze_mult,
            ema_gap_mult=ema_gap_mult,
        )
    return _analyzer_instance


# ─────────────────────────────────────────────────────────────
# QUICK TEST
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    import sys
    from dotenv import load_dotenv
    from modules.mt5_data_feed import MT5DataFeed

    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    print("=" * 70)
    print("  Module 2: MarketStructureAnalyzer — Quick Test")
    print("=" * 70)

    # Kết nối MT5
    feed = MT5DataFeed()
    login    = int(os.getenv("MT5_LOGIN", 0))
    password = os.getenv("MT5_PASSWORD", "")
    server   = os.getenv("MT5_SERVER", "")

    if not feed.connect(login=login, password=password, server=server):
        print("Khong the ket noi MT5. Kiem tra lai .env")
        sys.exit(1)

    analyzer = MarketStructureAnalyzer(fractal_lookback=5)

    test_symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"]

    for symbol in test_symbols:
        print(f"\n[TEST] {symbol}")
        print("-" * 60)

        m15 = feed.get_indicators(symbol, "M15", bars=300)
        h1  = feed.get_indicators(symbol, "H1",  bars=200)

        if not m15 or not m15.is_valid:
            print(f"  Khong co du lieu M15 cho {symbol}")
            continue
        if not h1 or not h1.is_valid:
            print(f"  Khong co du lieu H1 cho {symbol}")
            continue

        ltf_ms, htf_ms = analyzer.analyze_mtf(m15, h1)

        print(f"  H1  | {htf_ms.summary()}")
        print(f"  M15 | {ltf_ms.summary()}")
        print(f"  SH count: {len(ltf_ms.swing_highs)} | SL count: {len(ltf_ms.swing_lows)}")

        # Kiểm tra điều kiện MTF
        if htf_ms.allow_buy and ltf_ms.allow_buy:
            print(f"  ==> MTF OK: Co the tim lenh MUA tren {symbol}")
        elif htf_ms.allow_sell and ltf_ms.allow_sell:
            print(f"  ==> MTF OK: Co the tim lenh BAN tren {symbol}")
        else:
            reason = htf_ms.reason if htf_ms.no_trade_zone else ltf_ms.reason
            print(f"  ==> Khong co tin hieu. Ly do: {reason}")

    feed.disconnect()
    print("\nModule 2 test hoan thanh!")
    print("=" * 70)
