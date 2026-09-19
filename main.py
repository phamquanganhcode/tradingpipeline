"""
main.py — Orchestrator chính của AI Trading Pipeline
────────────────────────────────────────────────────────────────
Cách dùng:
    python main.py                              # tự động tìm report mới nhất
    python main.py --report complete_report_XAGUSD_20260917_155932.md
    python main.py --report <file> --balance 5000
    python main.py --stats                      # xem thống kê DB
    python main.py --export                     # export CSV
"""

from __future__ import annotations

import argparse
import sys
import os
import time
from datetime import datetime

class DualLogger:
    def __init__(self, log_filepath):
        self.terminal = sys.stdout
        # Mở file với mode "w" để ghi đè (overwrite) thay vì "a" (append)
        self.log_file = open(log_filepath, "w", encoding="utf-8")
        self.log_file.write(f"{'='*80}\n")
        self.log_file.write(f"--- BẮT ĐẦU CHẠY PIPELINE: {datetime.now().isoformat()} ---\n")
        self.log_file.write(f"{'='*80}\n")

    def write(self, message):
        try:
            self.terminal.write(message)
        except UnicodeEncodeError:
            safe_msg = message.encode(self.terminal.encoding or 'utf-8', errors='replace').decode(self.terminal.encoding or 'utf-8')
            self.terminal.write(safe_msg)
        self.log_file.write(message)
        self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

from config import (
    GEMINI_API_KEY, SYMBOL, REPORTS_DIR, TIMEFRAMES
)
from modules.report_parser  import ReportParser, find_latest_report
from modules.indicator_engine import IndicatorEngine
from modules.payload_builder import PayloadBuilder
from modules.gemini_client   import GeminiClient
from modules.risk_validator  import RiskValidator
from modules.trade_logger    import TradeLogger


# ─────────────────────────────────────────────────────────────
# BANNER
# ─────────────────────────────────────────────────────────────

BANNER = """
+-----------------------------------------------------------+
|      AI TRADING PIPELINE -- Price Action + Gemini         |
|      Strategy: EMA 20/50 + Bollinger Bands (10/10)        |
+-----------------------------------------------------------+
"""


# ─────────────────────────────────────────────────────────────
# PIPELINE
# ─────────────────────────────────────────────────────────────

def run_pipeline(report_path: str, account_balance: float = 10_000.0) -> dict:
    """
    Chạy toàn bộ pipeline:
    ReportParser → IndicatorEngine → PayloadBuilder
    → GeminiClient → RiskValidator → TradeLogger
    """
    print(BANNER)
    start = time.time()

    # ── STEP 1: Parse report ──────────────────────────────────
    print("\n[STEP 1/5] 📄 Parsing TradingAgents report...")
    parser = ReportParser(report_path)
    report = parser.parse()

    # ── STEP 2: Tính indicator bổ sung (EMA 20/50) ────────────
    print("\n[STEP 2/5] 📈 Tính toán indicator bổ sung (EMA 20/50)...")
    engine = IndicatorEngine(symbol=report.symbol, timeframes=TIMEFRAMES)
    live_indicators = engine.compute()
    live_price      = engine.get_live_price()
    if live_price:
        print(f"[IndicatorEngine] 💰 Live price: {live_price}")

    # ── STEP 3: Xây dựng payload cho Gemini ──────────────────
    print("\n[STEP 3/5] 🔧 Xây dựng prompt cho Gemini...")
    builder = PayloadBuilder(
        report          = report,
        live_indicators = live_indicators,
        live_price      = live_price,
    )
    prompt        = builder.build_prompt()
    output_schema = builder.get_output_schema()
    print(f"[PayloadBuilder] Prompt length: {len(prompt):,} chars")

    # ── STEP 4: Gọi Gemini API ────────────────────────────────
    print("\n[STEP 4/5] 🤖 Gửi request tới Gemini...")
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
        print("⚠️  GEMINI_API_KEY chưa được cấu hình trong config.py")
        print("    → Chạy trong chế độ DRY RUN (mock response)")
        proposal = _mock_proposal(report.symbol)
    else:
        client   = GeminiClient()
        proposal = client.analyze(prompt, output_schema)

    # ── STEP 5: Validate & Log ────────────────────────────────
    print("\n[STEP 5/5] ✅ Validate rủi ro & lưu kết quả...")
    validator  = RiskValidator(proposal, report, account_balance=account_balance)
    validation = validator.validate()

    logger = TradeLogger()
    trade_id = logger.log(proposal, validation, report, report_path)

    # ── Gửi Telegram (nếu ACCEPT) ─────────────────────────────
    if validation.status == "ACCEPT":
        try:
            from modules.telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier()
            notifier.notify_new_trade(proposal, validation)
        except Exception as e:
            print(f"[Telegram] ⚠️  Không thể gửi thông báo: {e}")
            
        # ── Bắn lệnh sang MT5 ─────────────────────────────
        try:
            from modules.mt5_executor import MT5Executor
            mt5_bot = MT5Executor()
            
            # Lấy thông số lệnh
            ep = proposal.entry.price or proposal.entry.zone_low
            tp = proposal.take_profit[0] if proposal.take_profit else 0.0
            entry_type = proposal.entry.type  # market, limit, stop

            # Khi AI quyết định WAIT nhưng có pending setup được ACCEPT,
            # dùng direction từ entry zone (buy/sell) thay vì "WAIT"
            mt5_decision = proposal.decision
            if mt5_decision == "WAIT" and proposal.entry:
                mt5_decision = proposal.entry.direction.upper()  # "BUY" hoặc "SELL"
                print(f"[MT5] ℹ️  WAIT→Pending: đặt lệnh {entry_type.upper()} {mt5_decision}")
            
            # Thực thi
            mt5_bot.execute_trade(
                symbol=SYMBOL,  # Dùng SYMBOL từ config (ví dụ BTCUSDm) để đúng với mã sàn MT5
                decision=mt5_decision,
                entry_type=entry_type,
                entry_price=ep,
                sl=proposal.stop_loss,
                tp=tp,
                lot_size=validation.lot_size
            )
            mt5_bot.shutdown()
        except Exception as e:
            print(f"[MT5] ⚠️  Lỗi thực thi lệnh: {e}")

    # ── SUMMARY ───────────────────────────────────────────────
    elapsed = round(time.time() - start, 1)
    is_accepted_pending = (proposal.decision == "WAIT" and validation.status == "ACCEPT")
    print(f"\n{'='*60}")
    print(f"  PIPELINE HOÀN TẤT  ({elapsed}s) — Trade ID #{trade_id}")
    print(f"{'='*60}")
    print(f"  Symbol    : {proposal.symbol}")
    if is_accepted_pending:
        print(f"  Decision  : WAIT → ✅ PENDING ORDER ACCEPTED")
    else:
        print(f"  Decision  : {proposal.decision}")
    print(f"  Bias      : {proposal.bias}")
    conf = proposal.confidence
    conf_display = f"{conf:.0%}" if conf <= 1.0 else f"{conf}%"
    print(f"  Confidence: {conf_display}")
    if proposal.decision == "WAIT" and proposal.entry:
        label = "✅ PENDING ORDER ĐÃ ĐẶT" if is_accepted_pending else "PENDING SETUP ĐỀ XUẤT"
        print(f"  [{label}]")
        ep = proposal.entry.price or proposal.entry.zone_low
        dir_str = proposal.entry.direction.upper()
        print(f"  Entry     : {ep} ({dir_str} {proposal.entry.type.upper()})")
    elif proposal.entry:
        ep = proposal.entry.price or proposal.entry.zone_low
        dir_str = proposal.entry.direction.upper()
        print(f"  Entry     : {ep} ({dir_str})")
    
    if proposal.stop_loss:
        print(f"  Stop Loss : {proposal.stop_loss}")
    if proposal.take_profit:
        print(f"  TP Levels : {proposal.take_profit}")
    
    print(f"  Lot Size  : {validation.lot_size if validation.lot_size else 'Chưa tính (cần duyệt lệnh)'}")
    print(f"  R:R       : {validation.actual_rr if validation.actual_rr else proposal.risk_reward}")
    print(f"  Validation: {validation.status}")
    if validation.reject_reason:
        print(f"  Lý do từ chối: {validation.reject_reason}")
    print(f"{'='*60}\n")

    logger.print_stats()

    return {
        "trade_id":   trade_id,
        "proposal":   proposal.model_dump(),
        "validation": validation.model_dump(),
    }


# ─────────────────────────────────────────────────────────────
# MOCK (khi chưa có API key)
# ─────────────────────────────────────────────────────────────

def _mock_proposal(symbol: str):
    """Tạo mock TradeProposal để test pipeline không cần Gemini API."""
    from models.schemas import TradeProposal, ThoughtProcess, EntryZone

    print("[MOCK] Tạo mock proposal cho mục đích test...")
    return TradeProposal(
        thought_process=ThoughtProcess(
            market_context   = "XAGUSD đang trong vùng consolidation giữa SMA 50 và SMA 200.",
            checklist_check  = "SELL checklist: [FAIL] Cấu trúc chưa rõ LH/LL. [FAIL] BB đang nằm ngang.",
            setup_evaluation = "Không có setup rõ ràng — thị trường đang trong No-Trade Zone.",
            risk_assessment  = "High-impact news (FOMC) sắp xảy ra. Tránh giao dịch.",
        ),
        decision = "WAIT",
        symbol   = symbol,
        bias     = "neutral",
        setup    = "no_setup_available",
        checklist_passed = [],
        checklist_failed = ["Cấu trúc LH/LL chưa rõ", "BB đang nằm ngang", "FOMC news risk"],
        entry      = None,
        stop_loss  = None,
        take_profit = [],
        risk_reward = None,
        confidence  = 0.15,
        invalidation = "",
        reasons = ["Thị trường consolidation", "BB phẳng", "Sắp có tin FOMC"],
        risks   = ["Breakout bất ngờ sau FOMC", "Stop-hunt tại SMA 50 (62.79)"],
    )


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

def main():
    # Khởi tạo logger để lưu log ra file
    os.makedirs("data", exist_ok=True)
    log_filename = f"data/pipeline_run_{datetime.now().strftime('%Y%m%d')}.txt"
    sys.stdout = DualLogger(log_filename)
    sys.stderr = sys.stdout

    parser = argparse.ArgumentParser(
        description="AI Trading Pipeline — Price Action + Gemini"
    )
    parser.add_argument(
        "--report", type=str, default=None,
        help="Đường dẫn tới file complete_report_*.md"
    )
    parser.add_argument(
        "--symbol", type=str, default=SYMBOL,
        help=f"Symbol cần tìm report (mặc định: {SYMBOL})"
    )
    parser.add_argument(
        "--balance", type=float, default=10_000.0,
        help="Số dư tài khoản USD (mặc định: 10000)"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Xem thống kê database"
    )
    parser.add_argument(
        "--export", action="store_true",
        help="Export CSV từ database"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Chạy pipeline nhưng KHÔNG lưu vào database (chỉ xem kết quả)"
    )
    parser.add_argument(
        "--monitor", action="store_true",
        help="Kiểm tra tất cả lệnh đang mở (trade_monitor)"
    )
    args = parser.parse_args()

    # Chế độ stats / export
    if args.stats:
        TradeLogger().print_stats()
        return

    if args.export:
        path = TradeLogger().export_csv()
        print(f"Đã export ra: {path}")
        return

    if args.monitor:
        from modules.trade_monitor import TradeMonitor
        from modules.indicator_engine import IndicatorEngine

        def _get_price(symbol: str):
            try:
                eng = IndicatorEngine(symbol=symbol, timeframes=[])
                return eng.get_live_price()
            except Exception:
                return None

        monitor = TradeMonitor()
        monitor.run_check(price_fetcher=_get_price)
        monitor.print_performance_summary()
        return

    # Tìm report
    report_path = args.report
    if not report_path:
        search_sym = args.symbol[:-1] if args.symbol.endswith('m') else args.symbol
        report_path = find_latest_report(REPORTS_DIR, search_sym)
        if not report_path:
            print(f"❌ Không tìm thấy report nào cho {search_sym} trong {REPORTS_DIR}")
            sys.exit(1)
        print(f"[main] Tự động chọn report: {report_path}")

    # Chạy pipeline
    run_pipeline(report_path=report_path, account_balance=args.balance)



if __name__ == "__main__":
    main()
