"""
modules/trade_monitor.py
────────────────────────────────────────────────────────────────
Module mới: Theo dõi và quản lý các lệnh đang mở.

Chức năng:
- Đọc danh sách lệnh ACCEPT chưa đóng từ DB
- So sánh giá hiện tại với SL/TP đã ghi
- Đề xuất Break-even, Partial TP, cảnh báo SL sắp bị chạm
- Cập nhật kết quả lệnh (WIN/LOSS/BREAK-EVEN) vào DB
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, date
from typing import Optional

from config import DB_PATH


# ─────────────────────────────────────────────────────────────
# MONITOR
# ─────────────────────────────────────────────────────────────

class TradeMonitor:
    """
    Quản lý vòng đời của các lệnh sau khi vào (Post-Entry Management).
    Không đặt lệnh thực tế — chỉ phân tích và đề xuất hành động.
    """

    SL_WARN_THRESHOLD = 0.25   # cảnh báo khi giá cách SL < 25% khoảng cách ban đầu
    BE_TRIGGER_RR     = 1.0    # dời SL về BE khi lệnh đạt R:R = 1.0

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        # Đảm bảo thư mục chứa database tồn tại
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        # Đảm bảo bảng trades cơ sở đã tồn tại trước khi chạy migrations
        from modules.trade_logger import TradeLogger
        TradeLogger(self.db_path)
        self._ensure_monitor_columns()

    def _ensure_monitor_columns(self):
        """Thêm cột monitor vào DB nếu chưa có (migration an toàn)."""
        with sqlite3.connect(self.db_path) as conn:
            existing = [row[1] for row in conn.execute("PRAGMA table_info(trades)").fetchall()]
            migrations = [
                ("trade_status",  "ALTER TABLE trades ADD COLUMN trade_status TEXT DEFAULT 'OPEN'"),
                ("closed_at",     "ALTER TABLE trades ADD COLUMN closed_at TEXT"),
                ("close_price",   "ALTER TABLE trades ADD COLUMN close_price REAL"),
                ("pnl_pips",      "ALTER TABLE trades ADD COLUMN pnl_pips REAL"),
                ("pnl_usd",       "ALTER TABLE trades ADD COLUMN pnl_usd REAL"),
                ("outcome",       "ALTER TABLE trades ADD COLUMN outcome TEXT"),  # WIN/LOSS/BE/OPEN
                ("be_moved",      "ALTER TABLE trades ADD COLUMN be_moved INTEGER DEFAULT 0"),
            ]
            for col_name, sql in migrations:
                if col_name not in existing:
                    try:
                        conn.execute(sql)
                        print(f"[TradeMonitor] ✅ Thêm cột mới: {col_name}")
                    except Exception as e:
                        print(f"[TradeMonitor] ⚠️  Không thể thêm cột {col_name}: {e}")
            conn.commit()

    def get_open_trades(self) -> list[dict]:
        """Lấy tất cả lệnh ACCEPT đang ở trạng thái OPEN."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM trades
                WHERE validation_status = 'ACCEPT'
                  AND (trade_status IS NULL OR trade_status = 'OPEN')
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def analyze_trade(self, trade: dict, current_price: float) -> dict:
        """
        Phân tích một lệnh đang mở so với giá hiện tại.
        Trả về dict với các đề xuất hành động.
        """
        entry   = trade.get("entry_price")
        sl      = trade.get("stop_loss")
        tp1     = trade.get("take_profit_1")
        decision = trade.get("decision", "")
        be_moved = bool(trade.get("be_moved", 0))

        if not all([entry, sl, tp1]):
            return {"trade_id": trade["id"], "action": "SKIP", "reason": "Thiếu entry/SL/TP"}

        sl_dist  = abs(entry - sl)
        tp_dist  = abs(tp1 - entry)
        progress = 0.0  # % tiến độ về TP

        actions = []
        outcome = "OPEN"

        if decision == "BUY":
            pnl_pips_current = current_price - entry
            if sl_dist > 0:
                progress = pnl_pips_current / tp_dist

            # Kiểm tra chạm SL
            if current_price <= sl:
                outcome = "LOSS"
                actions.append("❌ CHẠM SL — Đóng lệnh LOSS")

            # Kiểm tra chạm TP1
            elif current_price >= tp1:
                outcome = "WIN"
                actions.append("✅ CHẠM TP1 — Đóng lệnh WIN")

            # Đề xuất Break-even
            elif not be_moved and pnl_pips_current >= sl_dist * self.BE_TRIGGER_RR:
                actions.append(f"⚡ ĐỀ XUẤT BREAK-EVEN: Dời SL từ {sl:.5f} → {entry:.5f}")

            # Cảnh báo SL gần
            elif current_price - sl <= sl_dist * self.SL_WARN_THRESHOLD:
                actions.append(f"⚠️  CẢNH BÁO: Giá ({current_price:.5f}) đang sát SL ({sl:.5f})!")

        elif decision == "SELL":
            pnl_pips_current = entry - current_price
            if sl_dist > 0:
                progress = pnl_pips_current / tp_dist

            # Kiểm tra chạm SL
            if current_price >= sl:
                outcome = "LOSS"
                actions.append("❌ CHẠM SL — Đóng lệnh LOSS")

            # Kiểm tra chạm TP1
            elif current_price <= tp1:
                outcome = "WIN"
                actions.append("✅ CHẠM TP1 — Đóng lệnh WIN")

            # Đề xuất Break-even
            elif not be_moved and pnl_pips_current >= sl_dist * self.BE_TRIGGER_RR:
                actions.append(f"⚡ ĐỀ XUẤT BREAK-EVEN: Dời SL từ {sl:.5f} → {entry:.5f}")

            # Cảnh báo SL gần
            elif sl - current_price <= sl_dist * self.SL_WARN_THRESHOLD:
                actions.append(f"⚠️  CẢNH BÁO: Giá ({current_price:.5f}) đang sát SL ({sl:.5f})!")

        return {
            "trade_id":      trade["id"],
            "symbol":        trade.get("symbol"),
            "decision":      decision,
            "entry":         entry,
            "sl":            sl,
            "tp1":           tp1,
            "current_price": current_price,
            "progress_pct":  round(progress * 100, 1),
            "outcome":       outcome,
            "actions":       actions,
        }

    def close_trade(
        self,
        trade_id: int,
        close_price: float,
        outcome: str,
        pnl_pips: float,
        pnl_usd: float,
    ):
        """Cập nhật lệnh đã đóng vào DB."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE trades
                SET trade_status = 'CLOSED',
                    closed_at    = ?,
                    close_price  = ?,
                    outcome      = ?,
                    pnl_pips     = ?,
                    pnl_usd      = ?
                WHERE id = ?
                """,
                (
                    datetime.now().isoformat(),
                    close_price,
                    outcome,
                    pnl_pips,
                    pnl_usd,
                    trade_id,
                ),
            )
            conn.commit()
        print(f"[TradeMonitor] ✅ Đã đóng trade #{trade_id}: {outcome} | PnL={pnl_usd:+.2f} USD")

    def mark_be_moved(self, trade_id: int):
        """Đánh dấu lệnh đã được dời SL về Break-even."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE trades SET be_moved = 1 WHERE id = ?", (trade_id,))
            conn.commit()

    def run_check(self, price_fetcher=None) -> list[dict]:
        """
        Chạy kiểm tra tất cả lệnh đang mở.
        price_fetcher: callable(symbol) -> float | None
        Nếu không có price_fetcher, yêu cầu nhập giá thủ công.
        """
        open_trades = self.get_open_trades()
        if not open_trades:
            print("[TradeMonitor] ℹ️  Không có lệnh nào đang mở.")
            return []

        print(f"\n[TradeMonitor] 🔍 Đang kiểm tra {len(open_trades)} lệnh đang mở...")
        print("=" * 60)

        results = []
        for trade in open_trades:
            symbol = trade.get("symbol", "UNKNOWN")

            # Lấy giá hiện tại
            current_price = None
            if price_fetcher:
                try:
                    current_price = price_fetcher(symbol)
                except Exception:
                    pass

            if current_price is None:
                print(f"[TradeMonitor] Trade #{trade['id']} ({symbol}): Không lấy được giá live.")
                continue

            analysis = self.analyze_trade(trade, current_price)
            results.append(analysis)

            # In kết quả và gửi Telegram
            print(f"\n  Trade #{analysis['trade_id']} | {analysis['symbol']} {analysis['decision']}")
            print(f"  Entry: {analysis['entry']} | SL: {analysis['sl']} | TP: {analysis['tp1']}")
            print(f"  Giá hiện tại: {analysis['current_price']} | Tiến độ: {analysis['progress_pct']}%")
            for action in analysis['actions']:
                print(f"  → {action}")

            if analysis['actions']:
                try:
                    from modules.telegram_notifier import TelegramNotifier
                    notifier = TelegramNotifier()
                    notifier.notify_trade_update(analysis['trade_id'], analysis['symbol'], analysis['actions'])
                except Exception as e:
                    print(f"[Telegram] ⚠️  Không thể gửi cập nhật: {e}")


        print("\n" + "=" * 60)
        return results

    def print_performance_summary(self):
        """In thống kê hiệu suất đầy đủ từ DB."""
        with sqlite3.connect(self.db_path) as conn:
            total_closed = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE trade_status='CLOSED'"
            ).fetchone()[0]

            if total_closed == 0:
                print("[TradeMonitor] Chưa có lệnh nào đóng để thống kê.")
                return

            wins = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE outcome='WIN'"
            ).fetchone()[0]

            losses = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE outcome='LOSS'"
            ).fetchone()[0]

            total_pnl = conn.execute(
                "SELECT COALESCE(SUM(pnl_usd), 0) FROM trades WHERE trade_status='CLOSED'"
            ).fetchone()[0]

            avg_win = conn.execute(
                "SELECT COALESCE(AVG(pnl_usd), 0) FROM trades WHERE outcome='WIN'"
            ).fetchone()[0]

            avg_loss = conn.execute(
                "SELECT COALESCE(AVG(pnl_usd), 0) FROM trades WHERE outcome='LOSS'"
            ).fetchone()[0]

        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        expectancy = (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss)

        print("\n" + "=" * 60)
        print("📊 PERFORMANCE SUMMARY")
        print("=" * 60)
        print(f"  Tổng lệnh đóng : {total_closed}")
        print(f"  Win / Loss     : {wins} / {losses}")
        print(f"  Win Rate       : {win_rate:.1f}%")
        print(f"  Profit Factor  : {profit_factor:.2f}")
        print(f"  Expectancy     : ${expectancy:+.2f} / lệnh")
        print(f"  Tổng PnL       : ${total_pnl:+.2f}")
        print("=" * 60 + "\n")
