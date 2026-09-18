"""
modules/trade_logger.py
────────────────────────────────────────────────────────────────
Module 9: Lưu kết quả giao dịch vào SQLite database.
Hỗ trợ export CSV để backtest.
"""

from __future__ import annotations

import json
import sqlite3
import csv
import os
from datetime import datetime
from typing import Optional

from models.schemas import (
    TradeProposal, ValidationResult, TradingAgentReport, TradeRecord
)
from config import DB_PATH


# ─────────────────────────────────────────────────────────────
# SCHEMA SQL
# ─────────────────────────────────────────────────────────────

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol            TEXT    NOT NULL,
    timestamp         TEXT    NOT NULL,
    report_file       TEXT,
    decision          TEXT    NOT NULL,
    bias              TEXT,
    setup             TEXT,
    entry_price       REAL,
    stop_loss         REAL,
    take_profit_1     REAL,
    take_profit_2     REAL,
    risk_reward       REAL,
    confidence        REAL,
    lot_size          REAL,
    sl_distance_pips  REAL,
    risk_amount_usd   REAL,
    validation_status TEXT    NOT NULL,
    reject_reason     TEXT,
    checklist_passed  TEXT,
    checklist_failed  TEXT,
    reasons           TEXT,
    risks             TEXT,
    pm_final_decision TEXT,
    invalidation      TEXT,
    created_at        TEXT    DEFAULT (datetime('now'))
)
"""


# ─────────────────────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────────────────────

class TradeLogger:
    """Lưu trade records vào SQLite và export CSV."""

    def __init__(self, db_path: str = DB_PATH):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.commit()
        print(f"[TradeLogger] DB sẵn sàng: {self.db_path}")

    # ── Save ──────────────────────────────────────────────────

    def log(
        self,
        proposal:   TradeProposal,
        validation: ValidationResult,
        report:     TradingAgentReport,
        report_file: str = "",
    ) -> int:
        """Ghi một trade record vào DB và trả về row ID."""
        entry_price = None
        tp1 = tp2 = None

        if proposal.entry:
            entry_price = proposal.entry.price or proposal.entry.zone_low

        if proposal.take_profit:
            tp1 = proposal.take_profit[0] if len(proposal.take_profit) > 0 else None
            tp2 = proposal.take_profit[1] if len(proposal.take_profit) > 1 else None

        sql = """
        INSERT INTO trades (
            symbol, timestamp, report_file, decision, bias, setup,
            entry_price, stop_loss, take_profit_1, take_profit_2,
            risk_reward, confidence, lot_size, sl_distance_pips, risk_amount_usd,
            validation_status, reject_reason,
            checklist_passed, checklist_failed,
            reasons, risks, pm_final_decision, invalidation
        ) VALUES (
            ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?,
            ?, ?,
            ?, ?, ?, ?
        )
        """

        params = (
            proposal.symbol,
            datetime.now().isoformat(),
            report_file,
            proposal.decision,
            proposal.bias,
            proposal.setup,
            entry_price,
            proposal.stop_loss,
            tp1, tp2,
            validation.actual_rr or proposal.risk_reward,
            proposal.confidence,
            validation.lot_size,
            validation.sl_distance_pips,
            validation.risk_amount_usd,
            validation.status,
            validation.reject_reason,
            json.dumps(proposal.checklist_passed, ensure_ascii=False),
            json.dumps(proposal.checklist_failed, ensure_ascii=False),
            json.dumps(proposal.reasons, ensure_ascii=False),
            json.dumps(proposal.risks,   ensure_ascii=False),
            report.final_decision,
            proposal.invalidation,
        )

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            row_id = cursor.lastrowid

        print(f"[TradeLogger] ✅ Đã lưu trade #{row_id}: {proposal.decision} | {validation.status}")
        return row_id

    # ── Query ─────────────────────────────────────────────────

    def get_recent(self, limit: int = 20) -> list[dict]:
        """Lấy các trade gần nhất."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Thống kê cơ bản về các lệnh đã ghi."""
        with sqlite3.connect(self.db_path) as conn:
            total  = conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0]
            accept = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE validation_status='ACCEPT'"
            ).fetchone()[0]
            by_decision = conn.execute(
                "SELECT decision, COUNT(*) FROM trades GROUP BY decision"
            ).fetchall()

        stats = {
            "total_records":  total,
            "accepted_trades": accept,
            "rejected_trades": total - accept,
            "by_decision":    dict(by_decision),
        }
        return stats

    def get_today_accepted_count(self) -> int:
        """Đếm số lệnh ACCEPT hôm nay (theo ngày local)."""
        from datetime import date
        today = date.today().isoformat()  # "2026-09-18"
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE validation_status='ACCEPT' AND DATE(created_at)=?",
                (today,)
            ).fetchone()[0]
        return count

    # ── Export CSV ────────────────────────────────────────────

    def export_csv(self, output_path: str = "data/trades_export.csv") -> str:
        """Export tất cả trades ra CSV để backtest."""
        rows = self.get_recent(limit=10_000)
        if not rows:
            print("[TradeLogger] Không có dữ liệu để export")
            return output_path

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        print(f"[TradeLogger] ✅ Đã export {len(rows)} records → {output_path}")
        return output_path

    # ── Print summary ─────────────────────────────────────────

    def print_stats(self):
        stats = self.get_stats()
        print("\n" + "="*50)
        print("📊 TRADE DATABASE STATS")
        print("="*50)
        print(f"  Tổng records  : {stats['total_records']}")
        print(f"  ACCEPT        : {stats['accepted_trades']}")
        print(f"  REJECT        : {stats['rejected_trades']}")
        print(f"  Theo decision : {stats['by_decision']}")
        print("="*50 + "\n")
