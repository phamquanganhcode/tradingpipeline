"""
modules/report_parser.py
────────────────────────────────────────────────────────────────
Thay thế Module 1 (Data Collector) + Module 3 (Market Structure)
+ Module 4 (Chart Generator) + Module 5 (News Filter).

Parse file complete_report_*.md từ TradingAgents thành
TradingAgentReport — object chuẩn cho Payload Builder.
"""

from __future__ import annotations

import re
import os
import glob
from datetime import datetime
from typing import Optional

from models.schemas import (
    TradingAgentReport, MarketStructure, KeyLevels,
    IndicatorSnapshot, FundamentalContext, NewsEvent, LivePrice
)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _extract_float(pattern: str, text: str) -> Optional[float]:
    """Trích xuất số thực đầu tiên khớp với regex pattern."""
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _extract_text_block(start_marker: str, end_marker: str, text: str) -> str:
    """Trích một đoạn văn bản giữa hai marker."""
    pattern = re.escape(start_marker) + r"(.*?)" + re.escape(end_marker)
    m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


# ─────────────────────────────────────────────────────────────
# MAIN PARSER
# ─────────────────────────────────────────────────────────────

class ReportParser:
    """
    Parse file complete_report_SYMBOL_YYYYMMDD_HHMMSS.md
    thành TradingAgentReport.
    """

    def __init__(self, report_path: str):
        if not os.path.exists(report_path):
            raise FileNotFoundError(f"Report không tìm thấy: {report_path}")
        with open(report_path, "r", encoding="utf-8") as f:
            self.raw_text = f.read()
        self.report_path = report_path
        self.filename = os.path.basename(report_path)

    # ── Metadata ──────────────────────────────────────────────

    def _parse_symbol(self) -> str:
        # Từ tên file: complete_report_XAGUSD_20260917_155932.md
        m = re.search(r"complete_report_([A-Z]+)_", self.filename)
        if m:
            return m.group(1)
        # fallback từ nội dung
        m2 = re.search(r"Trading Analysis Report:\s*([A-Z]+)", self.raw_text)
        return m2.group(1) if m2 else "UNKNOWN"

    def _parse_timestamp(self) -> str:
        m = re.search(r"Generated:\s*([\d\- :]+)", self.raw_text)
        return m.group(1).strip() if m else datetime.now().isoformat()

    # ── Indicators ────────────────────────────────────────────

    def _parse_indicators(self) -> list[IndicatorSnapshot]:
        text = self.raw_text
        snap = IndicatorSnapshot(
            timeframe="MIXED",   # report tổng hợp nhiều TF
            rsi14     = _extract_float(r"RSI(?:\s+\(14\))?\s+(?:is\s+)?(?:at\s+)?([\d.]+)", text),
            atr14     = _extract_float(r"ATR(?:\s+of)?\s+([\d.]+)", text),
            macd_hist = _extract_float(r"MACD\s+histogram\s+is\s+(?:negative\s+at\s+)?\(?([-\d.]+)\)?", text),
            bb_upper  = _extract_float(r"(?:Bollinger\s+Band\s+Upper|upper\s+band)[^\d]*([\d.]+)", text),
            bb_lower  = _extract_float(r"(?:Bollinger\s+(?:lower|Lower)\s+[Bb]and|lower\s+band)[^\d]*([\d.]+)", text),
            bb_middle = _extract_float(r"(?:middle\s+band|Bollinger\s+middle)[^\d]*([\d.]+)", text),
        )
        # EMA / SMA levels
        snap.ema50 = _extract_float(r"50.day\s+SMA\s+(?:of\s+|at\s+)?([\d.]+)", text)

        return [snap]

    # ── Market Structure ──────────────────────────────────────

    def _parse_market_structure(self) -> MarketStructure:
        text = self.raw_text.lower()

        # Xác định xu hướng tổng thể
        bearish_score = text.count("bearish") + text.count("downtrend") + text.count("lower lows")
        bullish_score = text.count("bullish") + text.count("uptrend") + text.count("higher highs")
        sideway_score = text.count("consolidat") + text.count("range-bound") + text.count("neutral") + text.count("deadlock")

        if sideway_score > max(bearish_score, bullish_score):
            trend = "sideways"
        elif bearish_score > bullish_score:
            trend = "bearish"
        elif bullish_score > bearish_score:
            trend = "bullish"
        else:
            trend = "neutral"

        bos = bool(re.search(r"break\s+of\s+structure|bos", text))
        no_trade = "sideways" == trend or "consolidat" in text[:500]

        return MarketStructure(
            trend=trend,
            hh_hl=(trend == "bullish"),
            lh_ll=(trend == "bearish"),
            bos_signal=bos,
            no_trade_zone=no_trade,
        )

    # ── Key Levels ────────────────────────────────────────────

    def _parse_key_levels(self) -> KeyLevels:
        text = self.raw_text

        # Support levels
        support_vals: list[float] = []
        for pat in [
            r"50.day\s+SMA\s+(?:of\s+|at\s+)?([\d.]+)",
            r"Bollinger\s+(?:lower|Lower)\s+[Bb]and\s+(?:at\s+)?\(?(\d+\.\d+)\)?",
        ]:
            v = _extract_float(pat, text)
            if v:
                support_vals.append(v)

        # Resistance levels
        resist_vals: list[float] = []
        for pat in [
            r"200.day\s+SMA\s+(?:of\s+|at\s+)?([\d.]+)",
            r"Bollinger\s+(?:upper|Upper)\s+[Bb]and\s+(?:at\s+)?\(?(\d+\.\d+)\)?",
            r"10.day\s+EMA\s+(?:at\s+)?([\d.]+)",
        ]:
            v = _extract_float(pat, text)
            if v:
                resist_vals.append(v)

        swing_low  = min(support_vals) if support_vals else None
        swing_high = max(resist_vals)  if resist_vals  else None

        return KeyLevels(
            support=support_vals,
            resistance=resist_vals,
            swing_low=swing_low,
            swing_high=swing_high,
        )

    # ── Final Decision ────────────────────────────────────────

    def _parse_final_decision(self) -> str:
        # Portfolio Manager decision là quyết định cuối cùng
        m = re.search(
            r"Portfolio Manager.*?(?:Rating|Action)[:\s]+\*?\*?(\w+)\*?\*?",
            self.raw_text, re.DOTALL | re.IGNORECASE
        )
        if m:
            return m.group(1).upper()
        # fallback: tìm FINAL TRANSACTION PROPOSAL cuối cùng
        proposals = re.findall(
            r"FINAL TRANSACTION PROPOSAL:\s*\*?\*?(\w+)\*?\*?",
            self.raw_text, re.IGNORECASE
        )
        return proposals[-1].upper() if proposals else "HOLD"

    def _parse_price_target(self) -> Optional[float]:
        return _extract_float(r"Price\s+Target[:\s]+([\d.]+)", self.raw_text)

    def _parse_stop_loss_level(self) -> Optional[float]:
        return _extract_float(r"Stop\s+Loss[:\s]+([\d.]+)", self.raw_text)

    # ── Bull / Bear thesis summaries ──────────────────────────

    def _parse_bull_summary(self) -> str:
        block = _extract_text_block("### Bull Researcher", "### Bear Researcher", self.raw_text)
        return block[:600] if block else ""

    def _parse_bear_summary(self) -> str:
        block = _extract_text_block("### Bear Researcher", "### Research Manager", self.raw_text)
        return block[:600] if block else ""

    def _parse_pm_rationale(self) -> str:
        block = _extract_text_block(
            "### Portfolio Manager",
            "## V." if "## V." not in self.raw_text[:self.raw_text.find("### Portfolio Manager")]
            else "---",
            self.raw_text,
        )
        return block[:800] if block else ""

    # ── Fundamental context ───────────────────────────────────

    # ─────────────────────────────────────────────────────────
    # NEWS EVENT TABLE — mở rộng v2
    # ─────────────────────────────────────────────────────────

    _HIGH_IMPACT_EVENTS = [
        (r"FOMC|Federal\s+Reserve|Fed\s+(?:rate|decision|meeting)",
            "USD", "FOMC / Fed Rate Decision"),
        (r"non.farm\s+payroll|NFP",
            "USD", "Non-Farm Payrolls (NFP)"),
        (r"CPI|consumer\s+price\s+index",
            "USD", "CPI Release"),
        (r"GDP|gross\s+domestic\s+product",
            "USD", "GDP Release"),
        (r"interest\s+rate\s+decision|rate\s+hike|rate\s+cut",
            "USD", "Interest Rate Decision"),
        (r"unemployment\s+(?:rate|claims|data)|jobless\s+claims",
            "USD", "Unemployment / Jobless Claims"),
        (r"PPI|producer\s+price\s+index",
            "USD", "PPI Release"),
        (r"ISM\s+(?:manufacturing|services)|PMI",
            "USD", "ISM / PMI Data"),
        (r"10.year\s+Treasury|bond\s+yield",
            "USD", "10-Year Treasury Yield Movement"),
        (r"Jackson\s+Hole|symposium",
            "USD", "Jackson Hole Symposium"),
    ]

    _MEDIUM_IMPACT_EVENTS = [
        (r"retail\s+sales",      "USD", "Retail Sales"),
        (r"housing\s+(?:starts|data|market)", "USD", "Housing Data"),
        (r"trade\s+balance|trade\s+deficit", "USD", "Trade Balance"),
        (r"ADP\s+(?:employment|payroll)",    "USD", "ADP Employment"),
    ]

    def _parse_fundamental(self) -> FundamentalContext:
        text = self.raw_text
        events: list[NewsEvent] = []

        # High-impact events
        for pattern, currency, event_name in self._HIGH_IMPACT_EVENTS:
            if re.search(pattern, text, re.IGNORECASE):
                events.append(NewsEvent(
                    currency=currency, event=event_name,
                    time="TBD", importance="high"
                ))

        # Medium-impact events
        for pattern, currency, event_name in self._MEDIUM_IMPACT_EVENTS:
            if re.search(pattern, text, re.IGNORECASE):
                events.append(NewsEvent(
                    currency=currency, event=event_name,
                    time="TBD", importance="medium"
                ))

        has_high = any(e.importance == "high" for e in events)
        ts = self._parse_timestamp()
        try:
            dt = datetime.fromisoformat(ts.strip())
            day_name = dt.strftime("%A")
            # Session đơn giản theo giờ UTC
            hour = dt.hour
            if 7 <= hour < 16:
                session = "London"
            elif 13 <= hour < 22:
                session = "New York"
            else:
                session = "Asia"
        except Exception:
            day_name = "Unknown"
            session  = "Unknown"

        return FundamentalContext(
            session=session,
            day_of_week=day_name,
            economic_events=events,
            has_high_impact=has_high,
        )

    # ── Public API ────────────────────────────────────────────

    def parse(self) -> TradingAgentReport:
        """Parse toàn bộ report → TradingAgentReport."""
        print(f"[ReportParser] Đang parse: {self.filename}")

        report = TradingAgentReport(
            symbol           = self._parse_symbol(),
            report_timestamp = self._parse_timestamp(),
            final_decision   = self._parse_final_decision(),
            price_target     = self._parse_price_target(),
            stop_loss_level  = self._parse_stop_loss_level(),
            market_structure = self._parse_market_structure(),
            key_levels       = self._parse_key_levels(),
            indicators       = self._parse_indicators(),
            fundamental      = self._parse_fundamental(),
            bull_thesis_summary = self._parse_bull_summary(),
            bear_thesis_summary = self._parse_bear_summary(),
            pm_rationale        = self._parse_pm_rationale(),
            raw_text            = self.raw_text,
        )
        print(f"[ReportParser] ✅ Symbol={report.symbol} | Decision={report.final_decision} | Trend={report.market_structure.trend}")
        return report


# ─────────────────────────────────────────────────────────────
# UTILITY: tìm report mới nhất trong thư mục
# ─────────────────────────────────────────────────────────────

def find_latest_report(directory: str = ".", symbol: Optional[str] = None) -> Optional[str]:
    """Tìm file complete_report_*.md mới nhất trong thư mục (kể cả thư mục con)."""
    pattern = os.path.join(directory, "**", f"complete_report_{symbol or '*'}*.md")
    files = glob.glob(pattern, recursive=True)
    if not files:
        return None
    return max(files, key=os.path.getmtime)
