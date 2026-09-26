"""
EA Trading System Pro - Main Orchestrator
─────────────────────────────────────────────────────────────
Điểm khởi chạy tổng của hệ thống Bot giao dịch.
Kết nối 6 Module, đồng bộ thời gian chuẩn xác với nến M15.
(Đã gia cố Try/Except chống Crash và Hệ thống File Logging chuẩn VPS)
"""

import os
import sys
import time
import logging
from datetime import datetime
from dotenv import load_dotenv
import MetaTrader5 as mt5

# ==========================================
# 1. THIẾT LẬP HỆ THỐNG GHI LOG (FILE LOGGING)
# ==========================================
if not os.path.exists("logs"):
    os.makedirs("logs")

# Ghi log theo ngày, vd: trading_bot_2026_09_26.log
log_filename = datetime.now().strftime("logs/trading_bot_%Y_%m_%d.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("EA_Main")

# Nạp các Module
from modules.mt5_data_feed import MT5DataFeed
from modules.market_structure import get_analyzer
from modules.candle_pattern import get_candle_analyzer
from modules.strategy_engine import get_strategy_engine
from modules.equity_protector import EquityProtector
from modules.trade_manager import TradeManager

class EA_TradingSystemPro:
    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.last_scanned_minute = -1
        
        # Khởi tạo các Modules
        self.data_feed = MT5DataFeed()
        self.ms_analyzer = get_analyzer()
        self.candle_analyzer = get_candle_analyzer()
        self.strategy_engine = get_strategy_engine()
        self.equity_protector = EquityProtector(
            max_daily_loss_pct=3.0, 
            max_daily_profit_pct=6.0, 
            risk_per_trade_pct=1.0, 
            max_cons_losses=3
        )
        self.trade_manager = TradeManager(magic_number=888899)
        
    def start(self):
        load_dotenv()
        login = int(os.getenv("MT5_LOGIN", 0))
        password = os.getenv("MT5_PASSWORD", "")
        server = os.getenv("MT5_SERVER", "")
        
        if not self.data_feed.connect(login, password, server):
            logger.error("KHÔNG THỂ KẾT NỐI MT5. DỪNG HỆ THỐNG!")
            return
            
        logger.info("=" * 60)
        logger.info("🚀 HỆ THỐNG EA TRADING PRO ĐÃ KHỞI ĐỘNG (VPS READY)")
        logger.info(f"Theo dõi {len(self.symbols)} mã: {', '.join(self.symbols)}")
        logger.info(f"Nhật ký chạy ngầm lưu tại: {log_filename}")
        logger.info("=" * 60)
        
        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Bot bị dừng thủ công (Ctrl+C).")
        except Exception as e:
            logger.critical(f"FATAL ERROR - Bot Crash: {e}")
        finally:
            self.data_feed.disconnect()

    def _main_loop(self):
        """Vòng lặp trái tim (Heartbeat) của hệ thống"""
        while True:
            # 1. VÒNG LẶP PHÒNG THỦ: Chạy liên tục để Trade Management
            # Bọc Try/Except để đứt cáp mạng không làm bot crash
            try:
                self.trade_manager.manage_open_trades()
            except Exception as e:
                logger.error(f"Lỗi ngoại lệ tại Trade Manager (Có thể do mạng MT5): {e}")
            
            # 2. KIỂM TRA ĐỒNG HỒ ĐỂ TẤN CÔNG (M15 Sync)
            now = datetime.now()
            current_minute = now.minute
            current_second = now.second
            
            # Bóp cò vào phút 00, 15, 30, 45. Trễ 2 giây để Server chốt nến
            is_m15_boundary = (current_minute % 15 == 0)
            
            if is_m15_boundary and current_second >= 2 and current_minute != self.last_scanned_minute:
                logger.info("-" * 40)
                logger.info(f"⏰ KÍCH HOẠT QUÉT TÍN HIỆU ({now.strftime('%H:%M:%S')})")
                
                try:
                    # Check Cầu dao Ngày (Lãi/Lỗ 3%-6%)
                    if self.equity_protector.can_trade():
                        self._scan_market()
                    else:
                        logger.info("💤 Chế độ bảo vệ vốn đang kích hoạt. Bỏ qua lượt quét.")
                except Exception as e:
                    logger.error(f"Lỗi ngoại lệ trong lúc Quét Thị Trường: {e}")
                    
                # Đánh dấu đã quét ở phút này để khóa vòng lặp
                self.last_scanned_minute = current_minute
                
            # Nghỉ ngơi 2 giây giúp giảm tải CPU, không cần tick-by-tick
            time.sleep(2)

    def _scan_market(self):
        """Quét 3 khung thời gian tìm điểm vào lệnh"""
        for sym in self.symbols:
            # Check Max Exposure
            if not self.equity_protector.check_exposure(sym):
                continue
                
            # Tải dữ liệu 3 Khung
            m15_ind = self.data_feed.get_indicators(sym, "M15", bars=300, force=True)
            h1_ind  = self.data_feed.get_indicators(sym, "H1",  bars=300, force=True)
            h4_ind  = self.data_feed.get_indicators(sym, "H4",  bars=300, force=True)
            
            if not all([m15_ind, h1_ind, h4_ind]):
                continue
                
            # Phân tích Cấu trúc Đa khung
            m15_ms, h1_ms, h4_ms = self.ms_analyzer.analyze_3tf(m15_ind, h1_ind, h4_ind)
            
            # Nhận diện Nến M15 (Bóp cò)
            m15_candle = self.candle_analyzer.analyze(m15_ind)
            
            # Chạy qua Bộ não Chiến lược
            proposal = self.strategy_engine.generate_proposal(
                symbol=sym,
                m15_ind=m15_ind, h1_ind=h1_ind, h4_ind=h4_ind,
                m15_ms=m15_ms, h1_ms=h1_ms, h4_ms=h4_ms,
                m15_candle=m15_candle
            )
            
            # Nếu có tín hiệu hỏa lực
            if proposal:
                logger.info(f"🎯 TÍN HIỆU {sym}: {proposal.reason}")
                
                # Tính Lot và Gửi Lệnh
                lot = self.equity_protector.calculate_lot_size(sym, proposal.entry_price, proposal.stop_loss)
                if lot > 0:
                    self.trade_manager.execute_proposal(proposal, lot)
                else:
                    logger.warning(f"⚠️ Bỏ qua lệnh {sym} do Lot tính ra = 0 (Rủi ro quá lớn/Tài khoản bé).")

# ==========================================
# KHỞI CHẠY HỆ THỐNG
# ==========================================
if __name__ == "__main__":
    watchlist = ["XAUUSDm", "EURUSDm", "GBPUSDm", "USDJPYm"]
    
    if os.path.exists("symbol_forex.txt"):
        with open("symbol_forex.txt", "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            if lines: watchlist = lines
            
    bot = EA_TradingSystemPro(symbols=watchlist)
    bot.start()
