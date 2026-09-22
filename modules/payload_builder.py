"""
modules/payload_builder.py
────────────────────────────────────────────────────────────────
Module 6: Gom 6 nhóm dữ liệu thành multimodal prompt cho Gemini.

Áp dụng kỹ thuật "Interleaving" — xen kẽ context text và
system prompt để Gemini hiểu đúng ngữ cảnh chiến lược.
"""

from __future__ import annotations

import json
from typing import Any

from models.schemas import TradingAgentReport, IndicatorSnapshot


# ─────────────────────────────────────────────────────────────
# STRATEGY SPEC (từ Trading_System_Pro.md)
# ─────────────────────────────────────────────────────────────

STRATEGY_SPEC = """
## CHIẾN LƯỢC: Price Action + EMA 20/50 + Bollinger Bands (Phiên bản 10/10)

### CHECKLIST MUA (BUY) PULLBACK — cần đủ 5 bước:
1. [CẤU TRÚC] Giá đang tạo Higher Highs (HH) & Higher Lows (HL)
2. [XU HƯỚNG] Giá > EMA 50; EMA 20 > EMA 50; dải BB đang mở rộng dốc lên
3. [PULLBACK] Giá đã điều chỉnh về Vùng giá trị (giữa EMA 20 và EMA 50)
4. [TRIGGER] Có nến Bullish Pin Bar hoặc Bullish Engulfing tại vùng giá trị
5. [SL/TP] SL = dưới râu nến + 1×ATR | TP1 = BB Upper | TP2 = Trailing bám EMA 20

### CHECKLIST BÁN (SELL) PULLBACK — cần đủ 5 bước:
1. [CẤU TRÚC] Giá đang tạo Lower Highs (LH) & Lower Lows (LL)
2. [XU HƯỚNG] Giá < EMA 50; EMA 20 < EMA 50; dải BB đang mở rộng dốc xuống
3. [PULLBACK] Giá đã hồi về Vùng giá trị (giữa EMA 20 và EMA 50)
4. [TRIGGER] Có nến Bearish Pin Bar hoặc Bearish Engulfing tại vùng giá trị
5. [SL/TP] SL = trên râu nến + 1×ATR | TP1 = BB Lower | TP2 = Trailing bám EMA 20

### CHIẾN LƯỢC ĐỘT PHÁ (BREAKOUT) KHI SIDEWAY:
1. [CẤU TRÚC] Giá đi ngang, Bollinger Bands bó hẹp (Squeeze).
2. [ENTRY CHỜ] Mua (Buy Stop) khi giá break khỏi Resistance/BB Upper. Bán (Sell Stop) khi giá break khỏi Support/BB Lower.
3. [SL/TP] SL = 1xATR dưới/trên vùng sideway. TP = Bằng chiều cao hộp sideway.

### NGUYÊN TẮC BẮT BUỘC (SWING TRADING ĐA KHUNG THỜI GIAN):
- XÁC ĐỊNH XU HƯỚNG CHÍNH: Chỉ dựa trên khung H4 và H1. Xu hướng ở H4 và H1 phải đồng thuận (cùng Uptrend hoặc cùng Downtrend).
- TÌM ĐIỂM VÀO LỆNH (ENTRY, SL, TP): Bắt buộc sử dụng khung M30 để canh điểm vào lệnh, cắt lỗ và chốt lời.
- Dù EMA 50 dốc lên nhưng cấu trúc giá gãy (BOS) → TUYỆT ĐỐI không BUY.
- Luôn ưu tiên cấu trúc giá (Market Structure) hơn chỉ báo (Indicator).
"""

OUTPUT_SCHEMA = {
    "type": "object",
    "required": [
        "thought_process", "decision", "symbol", "bias",
        "checklist_passed", "checklist_failed", "confidence", "reasons", "risks"
    ],
    "properties": {
        "thought_process": {
            "type": "object",
            "properties": {
                "market_context":   {"type": "string"},
                "checklist_check":  {"type": "string"},
                "setup_evaluation": {"type": "string"},
                "risk_assessment":  {"type": "string"},
            },
            "required": ["market_context", "checklist_check", "setup_evaluation", "risk_assessment"],
        },

        "decision":   {"type": "string", "enum": ["BUY", "SELL", "WAIT"]},
        "symbol":     {"type": "string"},
        "bias":       {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
        "setup":      {"type": "string"},
        "checklist_passed": {"type": "array", "items": {"type": "string"}},
        "checklist_failed": {"type": "array", "items": {"type": "string"}},
        "entry": {
            "type": "object",
            "properties": {
                "type":      {"type": "string"},
                "direction": {"type": "string", "enum": ["buy", "sell"]},
                "zone_low":  {"type": "number"},
                "zone_high": {"type": "number"},
                "price":     {"type": "number"},
            },
        },
        "alt_entry": {
            "type": "object",
            "properties": {
                "type":      {"type": "string"},
                "direction": {"type": "string", "enum": ["buy", "sell"]},
                "zone_low":  {"type": "number"},
                "zone_high": {"type": "number"},
                "price":     {"type": "number"},
            },
        },
        "stop_loss":   {"type": "number"},
        "take_profit": {"type": "array", "items": {"type": "number"}},
        "risk_reward": {"type": "number"},
        "confidence":  {"type": "number"},
        "invalidation": {"type": "string"},
        "reasons":  {"type": "array", "items": {"type": "string"}},
        "risks":    {"type": "array", "items": {"type": "string"}},
    },
}


# ─────────────────────────────────────────────────────────────
# PAYLOAD BUILDER
# ─────────────────────────────────────────────────────────────

class PayloadBuilder:
    """
    Xây dựng prompt multimodal cho Gemini từ:
    - TradingAgentReport (đã parse từ complete_report_*.md)
    - Live indicators (từ IndicatorEngine)
    - Live price (nếu có)
    """

    def __init__(
        self,
        report: TradingAgentReport,
        live_indicators: list[IndicatorSnapshot] | None = None,
        live_price: float | None = None,
        mt5_status: str | None = None,
    ):
        self.report          = report
        self.live_indicators = live_indicators or []
        self.live_price      = live_price
        self.mt5_status      = mt5_status

    # ── Phần text context ─────────────────────────────────────

    def _section_market_context(self) -> str:
        r   = self.report
        ms  = r.market_structure
        kl  = r.key_levels
        ind = r.indicators[0] if r.indicators else IndicatorSnapshot(timeframe="N/A")

        price_line = (
            f"Giá hiện tại (live): **{self.live_price}**"
            if self.live_price
            else f"Giá tại thời điểm report: **{r.report_timestamp}**"
        )

        return f"""
### 1. THÔNG TIN THỊ TRƯỜNG — {r.symbol}
- {price_line}
- Thời gian report: {r.report_timestamp}
- Xu hướng tổng thể: **{ms.trend.upper()}**
- Break of Structure (BOS): {'CÓ ⚠️' if ms.bos_signal else 'KHÔNG'}
- No-Trade Zone: {'CÓ — ĐỨNG NGOÀI 🚫' if ms.no_trade_zone else 'KHÔNG'}

#### Key Levels (từ TradingAgents report):
- Support: {kl.support}
- Resistance: {kl.resistance}
- Swing Low: {kl.swing_low} | Swing High: {kl.swing_high}

#### Indicators (từ report — MIXED timeframe):
- RSI(14):    {ind.rsi14}
- ATR(14):    {ind.atr14}
- MACD Hist:  {ind.macd_hist}
- BB Upper:   {ind.bb_upper} | BB Middle: {ind.bb_middle} | BB Lower: {ind.bb_lower}
- SMA 50:     {ind.ema50}
"""

    def _section_live_indicators(self) -> str:
        if not self.live_indicators:
            return ""
        lines = ["### 2. INDICATORS THỜI GIAN THỰC (EMA 20/50 theo chiến lược)\n"]
        for snap in self.live_indicators:
            # Phần MACD
            macd_str = ""
            if snap.macd_line is not None and snap.macd_signal is not None:
                macd_cross = ""
                if snap.macd_line > snap.macd_signal:
                    macd_cross = " (✅ MACD > Signal — Bullish momentum)"
                elif snap.macd_line < snap.macd_signal:
                    macd_cross = " (⚠️ MACD < Signal — Bearish momentum)"
                macd_str = (
                    f" | MACD={snap.macd_line:.4f}/Signal={snap.macd_signal:.4f}"
                    f"{macd_cross}"
                )
            elif snap.macd_hist is not None:
                macd_str = f" | MACD Hist={snap.macd_hist:.4f}"

            # Phần Stochastic
            stoch_str = ""
            if snap.stoch_k is not None:
                stoch_zone = ""
                if snap.stoch_k >= 80:
                    stoch_zone = " (Overbought ⚠️)"
                elif snap.stoch_k <= 20:
                    stoch_zone = " (Oversold ✅)"
                stoch_str = f" | Stoch%K={snap.stoch_k:.1f}{stoch_zone}"

            lines.append(
                f"**{snap.timeframe}**: EMA20={snap.ema20} | EMA50={snap.ema50} "
                f"| BB({snap.bb_lower}–{snap.bb_upper}) | ATR={snap.atr14}"
                f" | RSI={snap.rsi14}{macd_str}{stoch_str}"
            )
        return "\n".join(lines)


    def _section_fundamental(self) -> str:
        f   = self.report.fundamental
        evs = "\n".join(
            f"  - [{e.importance.upper()}] {e.currency} — {e.event} lúc {e.time}"
            for e in f.economic_events
        ) or "  (Không có tin tức đặc biệt)"
        return f"""
### 3. BỐI CẢNH VĨ MÔ & PHIÊN GIAO DỊCH
- Phiên: **{f.session}** | Thứ: {f.day_of_week}
- Tin tức high-impact trong ±30 phút: {'CÓ ⚠️' if f.has_high_impact else 'KHÔNG'}
- Danh sách sự kiện:
{evs}
"""

    def _section_research_summary(self) -> str:
        r = self.report
        return f"""
### 4. TÓM TẮT PHÂN TÍCH TỪ TRADINGAGENTS
- **Portfolio Manager quyết định**: {r.final_decision}
- **Price Target**: {r.price_target} | **Stop Level**: {r.stop_loss_level}

#### Bull thesis (tóm tắt):
{r.bull_thesis_summary[:400]}

#### Bear thesis (tóm tắt):
{r.bear_thesis_summary[:400]}

#### PM Rationale:
{r.pm_rationale[:600]}
"""

    def _section_strategy(self) -> str:
        return STRATEGY_SPEC

    def _section_task(self) -> str:
        return f"""
### 5. NHIỆM VỤ CỦA BẠN
Bạn là một Senior Trader chuyên nghiệp. Dựa trên toàn bộ thông tin trên, hãy:
1. Xác định xem hiện tại có setup vào lệnh ngay (Market Order) không theo checklist.
2. NẾU KHÔNG CÓ SETUP NGAY (decision = WAIT), bạn VẪN PHẢI đề xuất một lệnh CHỜ (Pending Order) cho kịch bản sắp tới có xác suất cao nhất:
   - CHIẾN THUẬT CHẶN 2 ĐẦU: Nếu có thể, hãy rải cả 2 lệnh chờ cùng lúc. Ví dụ Uptrend: Đặt lệnh Buy Limit ở vùng Pullback (vào trường `entry`), VÀ Đặt thêm lệnh Buy Stop ở kháng cự để đánh Breakout (vào trường `alt_entry`).
   - Nếu xu hướng giảm (Downtrend): Dùng Sell Limit (vào `entry`) và Sell Stop (vào `alt_entry`).
3. BẮT BUỘC cung cấp đầy đủ thông số cho kịch bản giao dịch đó:
   - Entry zone: Vùng giá chờ mua/bán (dùng type="limit" hoặc type="stop" VÀ điền hướng direction="buy" hoặc "sell"). Điền vào `entry` và `alt_entry`.
   - Stop Loss: (dùng ATR={self.report.indicators[0].atr14 if self.report.indicators else 'N/A'} × 1). Áp dụng chung cho cả 2 lệnh.
   - Take Profit: Bạn PHẢI tự tính toán mức giá TP1 sao cho Tỷ lệ R:R (Khoảng cách từ Entry tới TP1 / Khoảng cách từ Entry tới SL) TỐI THIỂU đạt 1.5x. Tuyệt đối không đặt TP1 quá ngắn chỉ vì cản gần đó! Hãy dời TP1 xa hơn để đảm bảo R:R toán học >= 1.5x. (Lưu ý: Hệ thống validator bằng Python sẽ lấy TP đầu tiên trong mảng để chấm điểm).

**QUAN TRỌNG**: 
- Hãy phân tích `thought_process` thật chi tiết trước khi đưa ra `decision`.
- Dù `decision` là "WAIT", các trường `entry`, `alt_entry`, `stop_loss`, `take_profit` VẪN PHẢI CHỨA SỐ LIỆU của lệnh chờ (Pending order setup).
"""

    def _section_mt5_status(self) -> str:
        if not self.mt5_status:
            return ""
        return f"""
### 5. TRẠNG THÁI LỆNH HIỆN TẠI TRÊN MT5 (CỦA BOT)
{self.mt5_status}
Hãy cân nhắc thông tin này. Nếu bot đang giữ lệnh (POSITION) hoặc lệnh chờ (PENDING) đã hợp lý, bạn có thể quyết định WAIT hoặc dời SL/TP thay vì nhồi thêm lệnh ngược chiều.
"""

    # ── Public API ────────────────────────────────────────────

    def build_prompt(self) -> str:
        """Tạo prompt đầy đủ gửi cho Gemini."""
        sections = [
            "# PHÂN TÍCH GIAO DỊCH — AI TRADING PIPELINE\n",
            self._section_market_context(),
            self._section_live_indicators(),
            self._section_fundamental(),
            self._section_research_summary(),
            self._section_strategy(),
            self._section_mt5_status(),
            self._section_task(),
        ]
        return "\n".join(s for s in sections if s.strip())

    def get_output_schema(self) -> dict[str, Any]:
        """Trả về JSON Schema cho Gemini Structured Output."""
        return OUTPUT_SCHEMA
