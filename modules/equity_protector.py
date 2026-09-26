"""
Module 5: Equity Protector (Quản trị vốn)
─────────────────────────────────────────────────────────────
Xử lý đồng bộ Server Time, lọc lịch sử DEAL_ENTRY_OUT chuẩn xác
Tính Lot size tự động bằng Tick Value.
"""

import logging
from datetime import datetime, timedelta, timezone
import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

class EquityProtector:
    def __init__(
        self, 
        max_daily_loss_pct: float = 3.0, 
        max_daily_profit_pct: float = 6.0, 
        risk_per_trade_pct: float = 1.0, 
        max_cons_losses: int = 3
    ):
        self.max_loss_pct = max_daily_loss_pct
        self.max_profit_pct = max_daily_profit_pct
        self.risk_pct = risk_per_trade_pct
        self.max_cons_losses = max_cons_losses

    def _get_server_midnight(self) -> datetime:
        """Lấy 00:00 theo đúng múi giờ Server MT5 (Né lỗi lệch Local Time)"""
        tick = mt5.symbol_info_tick("EURUSD")
        if not tick:
            # Fallback nếu mất kết nối
            return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        server_time = datetime.fromtimestamp(tick.time)
        return server_time.replace(hour=0, minute=0, second=0, microsecond=0)

    def can_trade(self) -> bool:
        """Quét Lịch sử Deal trong ngày để xét duyệt Cầu dao điện"""
        account = mt5.account_info()
        if not account:
            logger.error("[Equity] Không lấy được Account Info")
            return False
            
        midnight = self._get_server_midnight()
        now_server = midnight + timedelta(days=1)
        
        deals = mt5.history_deals_get(midnight, now_server)
        if deals is None:
            return True # Không có lịch sử -> Cho phép đánh
            
        daily_pnl = 0.0
        cons_losses = 0
        
        # Sắp xếp history theo thời gian đóng lệnh
        sorted_deals = sorted(deals, key=lambda d: d.time)
        
        for deal in sorted_deals:
            # Lọc CHÍNH XÁC: Phải là lệnh Đóng (ENTRY_OUT) và là lệnh Buy/Sell thật sự
            if deal.entry == 1 and (deal.type == mt5.DEAL_TYPE_BUY or deal.type == mt5.DEAL_TYPE_SELL):
                net_profit = deal.profit + deal.commission + deal.swap + deal.fee
                daily_pnl += net_profit
                
                if net_profit < 0:
                    cons_losses += 1
                else:
                    cons_losses = 0 # Reset chuỗi thua
                    
        balance = account.balance
        loss_threshold = -balance * (self.max_loss_pct / 100.0)
        profit_threshold = balance * (self.max_profit_pct / 100.0)
        
        if daily_pnl <= loss_threshold:
            logger.warning(f"[Equity] ⛔ FROZEN: Đã chạm Max Daily Loss ({daily_pnl:.2f}$)")
            return False
            
        if daily_pnl >= profit_threshold:
            logger.warning(f"[Equity] ⛔ FROZEN: Đã đạt Max Daily Profit ({daily_pnl:.2f}$)")
            return False
            
        if cons_losses >= self.max_cons_losses:
            logger.warning(f"[Equity] ⛔ FROZEN: Đã thua {cons_losses} lệnh liên tiếp")
            return False
            
        return True

    def check_exposure(self, symbol: str, max_global_trades: int = 3) -> bool:
        """Kiểm tra tổng số lệnh đang chạy và tránh nhồi chung 1 mã"""
        positions = mt5.positions_get()
        if positions is None:
            return True
            
        if len(positions) >= max_global_trades:
            logger.warning(f"[Equity] Kín Slot ({len(positions)}/{max_global_trades} lệnh)")
            return False
            
        for pos in positions:
            if pos.symbol == symbol:
                logger.warning(f"[Equity] Đã có lệnh {symbol} đang chạy. Cấm nhồi lệnh!")
                return False
                
        return True

    def calculate_lot_size(self, symbol: str, entry_price: float, sl_price: float) -> float:
        """Tính Lot linh hoạt theo Tick Value chuẩn mực của MT5"""
        account = mt5.account_info()
        info = mt5.symbol_info(symbol)
        
        if not account or not info: 
            return 0.01
            
        risk_money = account.balance * (self.risk_pct / 100.0)
        
        # Đổi khoảng cách SL ra Points
        point = info.point
        sl_points = abs(entry_price - sl_price) / point
        if sl_points == 0: 
            return 0.0
            
        # Công thức Loss per Lot = (Points * Point / Tick_Size) * Tick_Value
        tick_size = info.trade_tick_size
        tick_value = info.trade_tick_value
        
        if tick_size == 0 or tick_value == 0:
            return 0.01
            
        loss_per_lot = (sl_points * point / tick_size) * tick_value
        if loss_per_lot == 0: 
            return 0.01
            
        raw_lot = risk_money / loss_per_lot
        
        # Làm tròn theo Step (Quy chuẩn bắt buộc của sàn)
        step = info.volume_step
        lot = round(raw_lot / step) * step
        
        # Ép vào Min/Max Lot
        lot = max(info.volume_min, min(info.volume_max, lot))
        return round(lot, 2)
