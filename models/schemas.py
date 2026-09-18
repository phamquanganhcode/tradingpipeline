"""
models/schemas.py — Pydantic v2 schemas cho toàn bộ pipeline
"""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# INPUT SCHEMAS
# ─────────────────────────────────────────────

class LivePrice(BaseModel):
    """Giá thời gian thực (có thể lấy từ MT5 hoặc yfinance)"""
    symbol:    str
    timestamp: str
    bid:       float
    ask:       float
    spread:    float              # tính bằng pips
    current:   float              # mid price


class IndicatorSnapshot(BaseModel):
    """Giá trị chỉ báo kỹ thuật tại một timeframe"""
    timeframe:    str
    ema20:        Optional[float] = None
    ema50:        Optional[float] = None
    bb_upper:     Optional[float] = None
    bb_middle:    Optional[float] = None
    bb_lower:     Optional[float] = None
    atr14:        Optional[float] = None
    rsi14:        Optional[float] = None
    macd_hist:    Optional[float] = None
    # Thêm mới v2:
    macd_line:    Optional[float] = None   # MACD line
    macd_signal:  Optional[float] = None   # Signal line
    stoch_k:      Optional[float] = None   # Stochastic %K
    stoch_d:      Optional[float] = None   # Stochastic %D


class MarketStructure(BaseModel):
    """Cấu trúc thị trường theo chiến lược Trading_System_Pro"""
    trend:      Literal["bullish", "bearish", "sideways", "neutral"]
    hh_hl:      bool   = False    # Higher Highs & Higher Lows
    lh_ll:      bool   = False    # Lower Highs & Lower Lows
    bos_signal: bool   = False    # Break of Structure
    no_trade_zone: bool = False   # BB phẳng + EMA xoắn


class KeyLevels(BaseModel):
    support:    list[float] = []
    resistance: list[float] = []
    swing_high: Optional[float] = None
    swing_low:  Optional[float] = None


class NewsEvent(BaseModel):
    currency:   str
    event:      str
    time:       str
    importance: Literal["low", "medium", "high"]


class FundamentalContext(BaseModel):
    session:          str
    day_of_week:      str
    economic_events:  list[NewsEvent] = []
    has_high_impact:  bool = False   # flag: có tin quan trọng trong ±30 phút


class TradingAgentReport(BaseModel):
    """
    Tổng hợp dữ liệu đã được parse từ file complete_report_*.md
    Đây là đầu vào chính cho Payload Builder.
    """
    symbol:              str
    report_timestamp:    str
    final_decision:      str          # HOLD / BUY / SELL từ Portfolio Manager
    price_target:        Optional[float] = None
    stop_loss_level:     Optional[float] = None

    market_structure:    MarketStructure
    key_levels:          KeyLevels
    indicators:          list[IndicatorSnapshot] = []
    fundamental:         FundamentalContext

    bull_thesis_summary: str = ""
    bear_thesis_summary: str = ""
    pm_rationale:        str = ""

    raw_text:            str = ""    # full text của report để gửi cho Gemini


# ─────────────────────────────────────────────
# OUTPUT SCHEMAS (Gemini trả về)
# ─────────────────────────────────────────────

class EntryZone(BaseModel):
    type:      Literal["market", "limit", "stop"]
    direction: Literal["buy", "sell"] = "buy"
    zone_low:  Optional[float] = None
    zone_high: Optional[float] = None
    price:     Optional[float] = None   # cho lệnh market


class ThoughtProcess(BaseModel):
    """Chain-of-Thought — đặt lên đầu để Gemini suy luận trước khi quyết định"""
    market_context:    str = ""
    checklist_check:   str = ""   # 5-step checklist verification
    setup_evaluation:  str = ""
    risk_assessment:   str = ""


class TradeProposal(BaseModel):
    """Output chuẩn từ Gemini — bắt buộc có đủ các trường này"""
    thought_process: ThoughtProcess

    decision:   Literal["BUY", "SELL", "WAIT"]
    symbol:     str
    bias:       Literal["bullish", "bearish", "neutral"]
    setup:      str = ""          # mô tả setup (vd: "pullback_to_ema")

    checklist_passed: list[str] = []   # các bước checklist đã pass
    checklist_failed: list[str] = []   # các bước chưa đủ điều kiện

    entry:       Optional[EntryZone] = None
    stop_loss:   Optional[float] = None
    take_profit: list[float] = []

    risk_reward:  Optional[float] = None
    confidence:   float = 0.0          # 0.0 – 1.0

    invalidation: str = ""
    reasons:      list[str] = []
    risks:        list[str] = []


# ─────────────────────────────────────────────
# VALIDATION SCHEMAS
# ─────────────────────────────────────────────

class ValidationResult(BaseModel):
    status:       Literal["ACCEPT", "REJECT"]
    reject_reason: Optional[str] = None

    # Kết quả tính toán của Python (không phải AI)
    sl_distance_pips: Optional[float] = None
    lot_size:         Optional[float] = None
    actual_rr:        Optional[float] = None
    risk_amount_usd:  Optional[float] = None


class TradeRecord(BaseModel):
    """Schema ghi vào SQLite database"""
    id:                Optional[int] = None
    symbol:            str
    timestamp:         str
    report_file:       str

    decision:          str
    bias:              str
    setup:             str
    entry_price:       Optional[float] = None
    stop_loss:         Optional[float] = None
    take_profit_1:     Optional[float] = None
    take_profit_2:     Optional[float] = None

    risk_reward:       Optional[float] = None
    confidence:        Optional[float] = None
    lot_size:          Optional[float] = None

    validation_status: str
    reject_reason:     Optional[str] = None
    reasons:           str = ""    # JSON string
    risks:             str = ""    # JSON string
    pm_final_decision: str = ""
