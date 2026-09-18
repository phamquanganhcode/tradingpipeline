"""
modules/risk_validator.py
────────────────────────────────────────────────────────────────
Module 8: Validation thuần Python — KHÔNG dùng AI.
Kiểm tra tính hợp lệ của TradeProposal theo luật rủi ro.

Nguyên tắc: AI suy luận, Python tính toán chính xác.
"""

from __future__ import annotations

from models.schemas import (
    TradeProposal, TradingAgentReport,
    ValidationResult
)
from config import (
    MINIMUM_RR, MAX_SPREAD_PIPS, NEWS_BLOCK_MINUTES,
    RISK_PER_TRADE_PCT, MAX_TRADES_PER_DAY
)


# ─────────────────────────────────────────────────────────────
# PIP VALUE TABLE (USD per 1 lot per pip, xấp xỉ)
# ─────────────────────────────────────────────────────────────
PIP_VALUE_PER_LOT = {
    "XAGUSD": 50.0,    # Silver: $50 / lot / pip (contract 5000 oz)
    "XAUUSD": 10.0,    # Gold:   $10 / lot / pip (contract 100 oz)
    "EURUSD": 10.0,    # $10 / lot / pip
    "GBPUSD": 10.0,
    "USDJPY": 9.1,
    "DEFAULT": 10.0,
}

PIP_SIZE = {
    "XAGUSD": 0.001,   # Silver tính theo 0.001
    "XAUUSD": 0.10,
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "DEFAULT": 0.0001,
}


def _pip_value(symbol: str) -> float:
    return PIP_VALUE_PER_LOT.get(symbol, PIP_VALUE_PER_LOT["DEFAULT"])

def _pip_size(symbol: str) -> float:
    return PIP_SIZE.get(symbol, PIP_SIZE["DEFAULT"])

def _price_to_pips(price_diff: float, symbol: str) -> float:
    return abs(price_diff) / _pip_size(symbol)


# ─────────────────────────────────────────────────────────────
# VALIDATOR
# ─────────────────────────────────────────────────────────────

class RiskValidator:
    """
    Validate TradeProposal và tính toán lot size, actual R:R.
    Trả về ValidationResult: ACCEPT hoặc REJECT kèm lý do.
    """

    def __init__(
        self,
        proposal:       TradeProposal,
        report:         TradingAgentReport,
        account_balance: float = 10_000.0,
    ):
        self.proposal        = proposal
        self.report          = report
        self.account_balance = account_balance

    # ── Check functions ───────────────────────────────────────

    def _check_decision(self) -> str | None:
        """Nếu AI đã WAIT, không cần validate thêm."""
        if self.proposal.decision == "WAIT":
            return "AI đã quyết định WAIT — không có setup khả dụng"
        return None

    def _check_news(self) -> str | None:
        """Chặn giao dịch khi có tin tức high-impact."""
        if self.report.fundamental.has_high_impact:
            return (
                f"Có tin tức high-impact trong cửa sổ ±{NEWS_BLOCK_MINUTES} phút "
                f"({', '.join(e.event for e in self.report.fundamental.economic_events if e.importance == 'high')})"
            )
        return None

    def _check_entry_sl(self) -> str | None:
        """Kiểm tra entry và SL có hợp lệ không."""
        p = self.proposal
        if p.entry is None:
            return "Thiếu Entry zone"
        if p.stop_loss is None:
            return "Thiếu Stop Loss"
        if not p.take_profit:
            return "Thiếu Take Profit"

        entry_price = p.entry.price or p.entry.zone_low
        if entry_price is None:
            return "Entry price không xác định"

        # SL phải đúng chiều với lệnh
        if p.decision == "BUY"  and p.stop_loss >= entry_price:
            return f"SL ({p.stop_loss}) phải NHỎ HƠN entry ({entry_price}) cho lệnh BUY"
        if p.decision == "SELL" and p.stop_loss <= entry_price:
            return f"SL ({p.stop_loss}) phải LỚN HƠN entry ({entry_price}) cho lệnh SELL"

        return None

    def _check_spread(self) -> str | None:
        """Kiểm tra spread (hiện tại bỏ qua vì không có live feed MT5)."""
        # TODO: kết nối MT5 để lấy spread thực
        return None

    def _check_daily_limit(self) -> str | None:
        """Kiểm tra số lệnh ACCEPT trong ngày có vượt giới hạn MAX_TRADES_PER_DAY không."""
        try:
            from modules.trade_logger import TradeLogger
            logger = TradeLogger()
            today_count = logger.get_today_accepted_count()
            if today_count >= MAX_TRADES_PER_DAY:
                return (
                    f"Đã đạt giới hạn {MAX_TRADES_PER_DAY} lệnh/ngày "
                    f"(hôm nay đã có {today_count} lệnh ACCEPT)"
                )
        except Exception as e:
            print(f"[RiskValidator] ⚠️  Không thể kiểm tra daily limit: {e}")
        return None

    def _check_no_trade_zone(self) -> str | None:
        """Kiểm tra thị trường có đang trong No-Trade Zone không."""
        if self.report.market_structure.no_trade_zone and self.proposal.decision != "WAIT":
            return "Thị trường đang trong No-Trade Zone (BB phẳng / EMA xoắn)"
        return None

    def _check_bos(self) -> str | None:
        """Nếu có BOS và lệnh ngược xu hướng cũ → cảnh báo."""
        ms = self.report.market_structure
        p  = self.proposal
        if ms.bos_signal and p.decision == "BUY" and ms.trend == "bearish":
            return "Break of Structure xuất hiện trong downtrend — không BUY theo nguyên tắc"
        if ms.bos_signal and p.decision == "SELL" and ms.trend == "bullish":
            return "Break of Structure xuất hiện trong uptrend — không SELL theo nguyên tắc"
        return None

    # ── Calculations ──────────────────────────────────────────

    def _calculate_rr(self) -> float | None:
        """Tính R:R thực tế."""
        p = self.proposal
        if p.entry is None or p.stop_loss is None or not p.take_profit:
            return None

        entry = p.entry.price or p.entry.zone_low
        if entry is None:
            return None

        sl_dist = abs(entry - p.stop_loss)
        tp_dist = abs(p.take_profit[0] - entry)

        if sl_dist == 0:
            return None

        return round(tp_dist / sl_dist, 2)

    def _calculate_sl_pips(self) -> float | None:
        """Tính khoảng cách SL theo pips."""
        p = self.proposal
        if p.entry is None or p.stop_loss is None:
            return None
        entry = p.entry.price or p.entry.zone_low
        if entry is None:
            return None
        return round(_price_to_pips(entry - p.stop_loss, self.proposal.symbol), 1)

    def _calculate_lot_size(self, sl_pips: float) -> float | None:
        """
        Tính lot size theo công thức:
        lot = (account_balance × risk_pct / 100) / (sl_pips × pip_value_per_lot)
        """
        if sl_pips <= 0:
            return None

        risk_amount   = self.account_balance * (RISK_PER_TRADE_PCT / 100)
        pip_val       = _pip_value(self.proposal.symbol)
        lot           = risk_amount / (sl_pips * pip_val)
        return round(max(0.01, lot), 2)

    def _check_rr(self, actual_rr: float | None) -> str | None:
        """Kiểm tra R:R có đạt tối thiểu không."""
        if actual_rr is None:
            return "Không tính được R:R"
        if actual_rr < MINIMUM_RR:
            return f"R:R thực tế ({actual_rr}) < yêu cầu tối thiểu ({MINIMUM_RR})"
        return None

    # ── Public API ────────────────────────────────────────────

    def validate(self) -> ValidationResult:
        """Chạy toàn bộ validation và trả về ValidationResult."""
        print(f"[RiskValidator] Đang validate proposal: {self.proposal.decision}")

        # --- Chạy các checks theo thứ tự ưu tiên ---
        checks = [
            ("AI Decision",    self._check_decision),
            # ("Daily limit",    self._check_daily_limit), # Bỏ giới hạn theo yêu cầu của User
            ("News filter",    self._check_news),
            ("No-Trade Zone",  self._check_no_trade_zone),
            ("BOS rule",       self._check_bos),
            ("Entry/SL valid", self._check_entry_sl),
            ("Spread check",   self._check_spread),
        ]

        reject_reason = None
        for check_name, check_fn in checks:
            reason = check_fn()
            if reason:
                reject_reason = reason
                print(f"[RiskValidator] ❌ REJECT — [{check_name}] {reason}")
                break

        # --- Tính toán Lot Size & R:R (Kể cả khi REJECT để tham khảo cho Pending Order) ---
        actual_rr = self._calculate_rr()
        sl_pips   = self._calculate_sl_pips()
        lot_size  = self._calculate_lot_size(sl_pips) if sl_pips else None
        risk_usd  = (lot_size or 0) * (sl_pips or 0) * _pip_value(self.proposal.symbol)

        rr_reason = self._check_rr(actual_rr)
        if rr_reason and not reject_reason:
            reject_reason = rr_reason
            print(f"[RiskValidator] ❌ REJECT — [R:R] {rr_reason}")

        if reject_reason:
            return ValidationResult(
                status="REJECT",
                reject_reason=reject_reason,
                sl_distance_pips=sl_pips,
                actual_rr=actual_rr,
                lot_size=lot_size,
                risk_amount_usd=round(risk_usd, 2) if risk_usd else None,
            )

        # --- ACCEPT ---
        print(
            f"[RiskValidator] ✅ ACCEPT — "
            f"SL={sl_pips} pips | Lot={lot_size} | R:R={actual_rr} | Risk=~${risk_usd:.2f}"
        )
        return ValidationResult(
            status            = "ACCEPT",
            sl_distance_pips  = sl_pips,
            lot_size          = lot_size,
            actual_rr         = actual_rr,
            risk_amount_usd   = round(risk_usd, 2),
        )
