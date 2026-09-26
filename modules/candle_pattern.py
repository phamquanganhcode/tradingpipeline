"""
Module 3: Candle Pattern Recognition (Nhận diện Mô hình nến)
─────────────────────────────────────────────────────────────
Nhận diện các mô hình nến đảo chiều có tỷ lệ thắng cao:
1. Pinbar (Bullish/Bearish)
2. Engulfing (Bullish/Bearish)
3. RSI Divergence (Phân kỳ RSI cơ bản)
Chỉ xét trên cây nến ĐÃ ĐÓNG CỬA (tránh repainting).
"""

import logging
from dataclasses import dataclass
from typing import Literal, Optional
import pandas as pd

from modules.mt5_data_feed import IndicatorResult

logger = logging.getLogger(__name__)

@dataclass
class CandlePatternResult:
    bullish_pinbar: bool = False
    bearish_pinbar: bool = False
    bullish_engulfing: bool = False
    bearish_engulfing: bool = False
    
    rsi_bullish_div: bool = False
    rsi_bearish_div: bool = False
    
    signal: Literal["buy", "sell", "none"] = "none"
    pattern_name: str = "None"
    
    def summary(self) -> str:
        flags = []
        if self.bullish_pinbar: flags.append("Bullish Pinbar")
        if self.bearish_pinbar: flags.append("Bearish Pinbar")
        if self.bullish_engulfing: flags.append("Bullish Engulfing")
        if self.bearish_engulfing: flags.append("Bearish Engulfing")
        
        div = " + RSI Div" if (self.rsi_bullish_div or self.rsi_bearish_div) else ""
        
        if self.signal != "none":
            return f"[{self.signal.upper()}] {' & '.join(flags)}{div}"
        return "No Pattern"


class CandlePatternAnalyzer:
    def __init__(
        self,
        pinbar_wick_ratio: float = 0.60,      # Râu chính phải chiếm >= 60% nến
        pinbar_body_ratio: float = 0.35,      # Thân phải chiếm <= 35% nến
        max_opposite_wick: float = 0.15,      # Râu đối diện <= 15% (Lọc Spinning Top/High Wave)
        min_range_atr: float = 0.8,           # Biên độ nến (Range) phải > 0.8 ATR (Lọc nhiễu thanh khoản mỏng)
        engulfing_atr_mult: float = 0.5,      # Thân nến nhấn chìm phải > 0.5 ATR (lọc nhiễu)
        rsi_lookback: int = 15,               # Chu kỳ dò phân kỳ RSI
    ):
        self.wick_ratio = pinbar_wick_ratio
        self.body_ratio = pinbar_body_ratio
        self.max_opp_wick = max_opposite_wick
        self.min_range = min_range_atr
        self.engulf_mult = engulfing_atr_mult
        self.rsi_lookback = rsi_lookback

    def analyze(self, indicator: IndicatorResult) -> CandlePatternResult:
        res = CandlePatternResult()
        
        if not indicator or not indicator.is_valid or len(indicator.df) < max(20, self.rsi_lookback + 5):
            return res
            
        df = indicator.df
        
        c0 = df.iloc[-2]  # Nến vừa đóng cửa (Current Closed Candle)
        c1 = df.iloc[-3]  # Nến đóng cửa trước đó (Previous Closed Candle)
        
        atr = indicator.atr14
        
        # ─────────────────────────────────────────────────────────
        # 1. TÍNH TOÁN CÁC THÀNH PHẦN CỦA NẾN HIỆN TẠI (c0)
        # ─────────────────────────────────────────────────────────
        rng = c0['High'] - c0['Low']
        if rng == 0: 
            rng = 0.00001 # Tránh lỗi chia cho 0
            
        body = abs(c0['Open'] - c0['Close'])
        upper_wick = c0['High'] - max(c0['Open'], c0['Close'])
        lower_wick = min(c0['Open'], c0['Close']) - c0['Low']
        mid_point = (c0['High'] + c0['Low']) / 2
        
        # BỘ LỌC ĐỘNG LƯỢNG (Khử nhiễu)
        is_significant_range = rng > (atr * self.min_range)
        
        # ─────────────────────────────────────────────────────────
        # 2. KIỂM TRA PINBAR
        # ─────────────────────────────────────────────────────────
        # Bullish Pinbar (Búa đẩy lên)
        if (is_significant_range and                             # Biên độ đủ lớn
            lower_wick >= rng * self.wick_ratio and              # Râu dưới dài
            upper_wick <= rng * self.max_opp_wick and            # Râu trên ngắn (Lọc nhiễu 2 đầu)
            body <= rng * self.body_ratio and                    # Thân nhỏ
            c0['Close'] >= mid_point):                           # Đóng cửa ở nửa trên
            res.bullish_pinbar = True
            
        # Bearish Pinbar (Búa xả xuống)
        if (is_significant_range and                             # Biên độ đủ lớn
            upper_wick >= rng * self.wick_ratio and              # Râu trên dài
            lower_wick <= rng * self.max_opp_wick and            # Râu dưới ngắn
            body <= rng * self.body_ratio and                    # Thân nhỏ
            c0['Close'] <= mid_point):                           # Đóng cửa ở nửa dưới
            res.bearish_pinbar = True

        # ─────────────────────────────────────────────────────────
        # 3. KIỂM TRA ENGULFING (NHẤN CHÌM)
        # ─────────────────────────────────────────────────────────
        c1_body = abs(c1['Open'] - c1['Close'])
        
        # Bullish Engulfing (Cây xanh nuốt cây đỏ)
        if (c1['Close'] < c1['Open'] and                 # Nến trước là Đỏ (Giảm)
            c0['Close'] > c0['Open'] and                 # Nến nay là Xanh (Tăng)
            c0['Open'] <= c1['Close'] and                # Mở cửa bằng/thấp hơn giá đóng trước
            c0['Close'] >= c1['Open'] and                # Đóng cửa bằng/cao hơn giá mở trước
            body > (atr * self.engulf_mult)):            # Thân nến phải to (không lấy nến lít nhít)
            res.bullish_engulfing = True
            
        # Bearish Engulfing (Cây đỏ nuốt cây xanh)
        if (c1['Close'] > c1['Open'] and                 # Nến trước là Xanh (Tăng)
            c0['Close'] < c0['Open'] and                 # Nến nay là Đỏ (Giảm)
            c0['Open'] >= c1['Close'] and                # Mở cửa bằng/cao hơn giá đóng trước
            c0['Close'] <= c1['Open'] and                # Đóng cửa bằng/thấp hơn giá mở trước
            body > (atr * self.engulf_mult)):            # Thân nến phải to
            res.bearish_engulfing = True

        # ─────────────────────────────────────────────────────────
        # 4. KIỂM TRA PHÂN KỲ RSI (RSI DIVERGENCE) - BỘ LỌC PHỤ
        # ─────────────────────────────────────────────────────────
        # Trích xuất dữ liệu của lookback nến ĐÃ ĐÓNG (từ -2 ngược về trước)
        lookback_df = df.iloc[-(self.rsi_lookback + 2):-2]
        
        if len(lookback_df) > 0 and 'RSI' in df.columns:
            # Lấy RSI của nến vừa đóng
            current_rsi = df['RSI'].iloc[-2]
            
            # Tìm Low và RSI thấp nhất trong đoạn quá khứ
            past_lowest_low = lookback_df['Low'].min()
            past_lowest_rsi = lookback_df['RSI'].min()
            
            # Bullish Divergence: Giá tạo đáy thấp hơn (LL) nhưng RSI tạo đáy cao hơn (HL)
            if c0['Low'] <= past_lowest_low and current_rsi > past_lowest_rsi:
                res.rsi_bullish_div = True
                
            # Tìm High và RSI cao nhất trong đoạn quá khứ
            past_highest_high = lookback_df['High'].max()
            past_highest_rsi = lookback_df['RSI'].max()
            
            # Bearish Divergence: Giá tạo đỉnh cao hơn (HH) nhưng RSI tạo đỉnh thấp hơn (LH)
            if c0['High'] >= past_highest_high and current_rsi < past_highest_rsi:
                res.rsi_bearish_div = True

        # ─────────────────────────────────────────────────────────
        # 5. TỔNG HỢP TÍN HIỆU (SIGNAL GENERATION)
        # ─────────────────────────────────────────────────────────
        is_buy = res.bullish_pinbar or res.bullish_engulfing
        is_sell = res.bearish_pinbar or res.bearish_engulfing
        
        # Nếu xuất hiện cả 2 (rất hiếm, do nến dị dạng) -> None
        if is_buy and not is_sell:
            res.signal = "buy"
            res.pattern_name = "Bullish Pinbar" if res.bullish_pinbar else "Bullish Engulfing"
        elif is_sell and not is_buy:
            res.signal = "sell"
            res.pattern_name = "Bearish Pinbar" if res.bearish_pinbar else "Bearish Engulfing"

        return res

# --- Singleton Instance ---
_analyzer_instance = None
def get_candle_analyzer() -> CandlePatternAnalyzer:
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = CandlePatternAnalyzer()
    return _analyzer_instance


# ──────────────────────────────────────────────────────────────────────
# QUICK TEST SYNTAX
# ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from datetime import datetime, timedelta, timezone
    print("Test nhanh Module Candle Pattern...")
    
    # Tạo DataFrame giả lập
    now = datetime.now(timezone.utc)
    # Nến -3: Tăng
    # Nến -2: Giảm bao trùm (Bearish Engulfing)
    # Nến -1: Đang chạy
    data = {
        'Open':  [100, 102, 105],
        'High':  [103, 106, 106],
        'Low':   [ 99,  98, 100],
        'Close': [102,  99, 101],
        'Volume':[100, 100, 100],
        'RSI':   [ 50,  45,  40]
    }
    # Padding cho đủ 25 nến
    pad_len = 22
    for k in data:
        data[k] = [data[k][0]] * pad_len + data[k]
        
    idx = [now + timedelta(minutes=i) for i in range(len(data['Open']))]
    df = pd.DataFrame(data, index=idx)
    
    ind = IndicatorResult(
        symbol="TEST", timeframe="M15", timestamp=now,
        close=101.0, high=106.0, low=100.0, open_price=105.0, volume=100,
        ema20=100, ema50=100, bb_upper=110, bb_middle=100, bb_lower=90,
        bb_width=20, bb_squeeze=False, atr14=2.0, rsi14=40.0, df=df
    )
    
    analyzer = get_candle_analyzer()
    res = analyzer.analyze(ind)
    
    print("Kết quả:", res.summary())
    assert res.bearish_engulfing == True, "Lỗi: Không nhận diện được Bearish Engulfing"
    assert res.signal == "sell", "Lỗi: Tín hiệu phải là SELL"
    print("Module 3 hoạt động hoàn hảo!")
