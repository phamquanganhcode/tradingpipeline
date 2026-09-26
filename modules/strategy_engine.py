"""
Module 4: Strategy Engine (Trái tim của hệ thống)
─────────────────────────────────────────────────────────────
Tổng hợp dữ liệu từ Data (M1), Structure (M2), Candle (M3)
Áp dụng bộ lọc Top-Down Đa Khung Thời Gian (H4 -> H1 -> M15)
Ra quyết định và tính toán chi tiết lệnh (TradeProposal).
"""

import logging
from dataclasses import dataclass
from typing import Optional

from modules.mt5_data_feed import IndicatorResult
from modules.market_structure import MarketStructureResult
from modules.candle_pattern import CandlePatternResult

logger = logging.getLogger(__name__)

@dataclass
class TradeProposal:
    symbol: str
    action: str              # "buy" or "sell"
    entry_price: float
    stop_loss: float
    tp1: float               # 1.5R (Dùng để chốt lời 50% & kéo SL về Hòa vốn)
    tp2: float               # 3.0R (Chốt lời toàn bộ)
    actual_rr_to_level: float # Tỷ lệ R:R thực tế nếu đập vào cản H1
    reason: str              # Dấu vết lưu log tại sao vào lệnh

class StrategyEngine:
    def __init__(self, sl_atr_buffer: float = 0.5, min_rr_clearance: float = 1.0):
        self.sl_buffer = sl_atr_buffer
        self.min_rr = min_rr_clearance # Yêu cầu ít nhất khoảng trống 1.0R cho đến cản H1
        
    def generate_proposal(
        self,
        symbol: str,
        m15_ind: IndicatorResult, h1_ind: IndicatorResult, h4_ind: IndicatorResult,
        m15_ms: MarketStructureResult, h1_ms: MarketStructureResult, h4_ms: MarketStructureResult,
        m15_candle: CandlePatternResult
    ) -> Optional[TradeProposal]:
        
        # 0. Điều kiện tiên quyết: Dữ liệu phải hợp lệ
        if not (m15_ind.is_valid and h1_ind.is_valid and h4_ind.is_valid):
            return None
            
        c0 = m15_ind.df.iloc[-2] # Cây nến M15 vừa đóng cửa (đã fix, không dùng nến đang chạy)
        m15_atr = m15_ind.atr14
        
        # 1. BƯỚC 1: Lọc H4 (La bàn xu hướng)
        if h4_ms.trend == "sideways":
            return None # H4 nhiễu -> Đứng ngoài

        # ─────────────────────────────────────────────────────────────
        # KỊCH BẢN MUA (BUY) - KHI H4 ĐANG TĂNG
        # ─────────────────────────────────────────────────────────────
        if h4_ms.trend == "uptrend":
            # 2. BƯỚC 2: Kiểm tra bối cảnh H1
            # H1 bị CHoCH giảm (Gãy cấu trúc) -> Nhịp hồi đã thành đảo chiều -> HỦY
            if h1_ms.choch:
                return None
                
            # 3. BƯỚC 3: M15 Phát tín hiệu
            if m15_candle.signal != "buy":
                return None
                
            # 4. GIA CỐ CỰC HẠN: Điều kiện Giao cắt (Intersection) & Quét Thanh Khoản
            h1_ema20 = h1_ind.ema20
            h1_swing_low = h1_ms.last_swing_low
            
            if not h1_swing_low:
                return None # Không có đáy H1 để làm điểm tựa
                
            m15_low = c0['Low']
            
            # Lệnh bắt buộc phải chạm vào EMA20 hoặc đâm sâu hơn xuống Swing Low H1
            if m15_low > h1_ema20:
                # Tín hiệu lơ lửng, thiếu độ bám
                return None
                
            # Nhưng tuyệt đối không được thủng chốt chặn cuối cùng (Swing Low H1)
            # Nếu Pinbar M15 mà thủng luôn đáy H1 -> Bắt dao rơi rủi ro cao -> Cắt
            if m15_low < h1_swing_low:
                return None

            # 5. TÍNH TOÁN SL, TP VÀ QUẢN TRỊ RỦI RO
            entry = c0['Close'] # Vào lệnh ngay khi nến đóng cửa
            sl = m15_low - (m15_atr * self.sl_buffer)
            risk = entry - sl
            
            if risk <= 0: return None
            
            tp1 = entry + (risk * 2.0)
            tp2 = entry + (risk * 3.0)
            
            # 6. KIỂM TRA CHƯỚNG NGẠI VẬT (H1 Swing High)
            h1_swing_high = h1_ms.last_swing_high
            actual_rr = 99.0 # Mặc định coi như khoảng trống mênh mông
            
            if h1_swing_high and h1_swing_high > entry:
                room_to_move = h1_swing_high - entry
                actual_rr = room_to_move / risk
                if actual_rr < self.min_rr:
                    # Đỉnh H1 nằm ngay trên đầu, không đủ không gian di chuyển (Chưa tới 1R đã chạm cản)
                    return None
            
            # 7. HOÀN THÀNH - PHÁT LỆNH
            return TradeProposal(
                symbol=symbol, action="buy", entry_price=entry, stop_loss=sl,
                tp1=tp1, tp2=tp2, actual_rr_to_level=actual_rr,
                reason=f"[BUY] H4 Up | H1 Pullback | M15 {m15_candle.pattern_name} chạm EMA H1 | RR cản: {actual_rr:.1f}"
            )

        # ─────────────────────────────────────────────────────────────
        # KỊCH BẢN BÁN (SELL) - KHI H4 ĐANG GIẢM
        # ─────────────────────────────────────────────────────────────
        if h4_ms.trend == "downtrend":
            # H1 bị CHoCH tăng -> HỦY
            if h1_ms.choch:
                return None
                
            # M15 Phát tín hiệu Bán
            if m15_candle.signal != "sell":
                return None
                
            # Giao cắt (Intersection) & Quét Thanh Khoản
            h1_ema20 = h1_ind.ema20
            h1_swing_high = h1_ms.last_swing_high
            
            if not h1_swing_high:
                return None
                
            m15_high = c0['High']
            
            # Râu nến phải chạm lên EMA20 H1 (hoặc đâm lên tận Swing High)
            if m15_high < h1_ema20:
                return None # Lơ lửng
                
            # Nhưng không được xuyên thủng luôn cản trên (Swing High H1)
            if m15_high > h1_swing_high:
                return None # Gãy cấu trúc H1 mất rồi

            # Tính toán SL, TP
            entry = c0['Close']
            sl = m15_high + (m15_atr * self.sl_buffer)
            risk = sl - entry
            
            if risk <= 0: return None
            
            tp1 = entry - (risk * 2.0)
            tp2 = entry - (risk * 3.0)
            
            # Kiểm tra Cản dưới (H1 Swing Low)
            h1_swing_low = h1_ms.last_swing_low
            actual_rr = 99.0
            
            if h1_swing_low and h1_swing_low < entry:
                room_to_move = entry - h1_swing_low
                actual_rr = room_to_move / risk
                if actual_rr < self.min_rr:
                    # Đáy H1 quá gần, biên độ lợi nhuận hẹp
                    return None
            
            # HOÀN THÀNH - PHÁT LỆNH
            return TradeProposal(
                symbol=symbol, action="sell", entry_price=entry, stop_loss=sl,
                tp1=tp1, tp2=tp2, actual_rr_to_level=actual_rr,
                reason=f"[SELL] H4 Down | H1 Pullback | M15 {m15_candle.pattern_name} chạm EMA H1 | RR cản: {actual_rr:.1f}"
            )

        return None


# --- Singleton ---
_engine_instance = None
def get_strategy_engine() -> StrategyEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = StrategyEngine()
    return _engine_instance
