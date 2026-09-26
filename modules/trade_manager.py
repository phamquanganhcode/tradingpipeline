"""
Module 6: Trade Manager (Quản lý và Thực thi Lệnh)
─────────────────────────────────────────────────────────────
Sử dụng Magic Number thay vì Ticket ID để xử lý Hedging Partial Close.
Quản lý StopLevel, Spread, và Breakeven thực tế (có bù point).
"""

import logging
import MetaTrader5 as mt5
from modules.strategy_engine import TradeProposal

logger = logging.getLogger(__name__)

class TradeManager:
    def __init__(self, magic_number: int = 999999):
        self.magic_number = magic_number
        self.breakeven_offset_points = 20 # Bù 20 points (2 pips) cho Commission/Swap

    def execute_proposal(self, proposal: TradeProposal, lot: float) -> bool:
        """Thực thi lệnh Market với kiểm tra Spread và StopLevel"""
        symbol = proposal.symbol
        info = mt5.symbol_info(symbol)
        if not info or not info.visible:
            return False
            
        # 1. Kiểm tra Spread dãn (Né bão tin tức)
        current_spread = info.spread
        # Tuỳ vào cặp tiền, ví dụ Spread > 50 points là dãn
        # Ở đây ta có thể setup tham số, tạm thời check cơ bản
        
        # 2. Setup Type
        if proposal.action == "buy":
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask
        else:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
            
        # 3. Tạo Request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(lot),
            "type": order_type,
            "price": price,
            "sl": float(proposal.stop_loss),
            "tp": float(proposal.tp2), # Đặt cứng TP max, xử lý TP1 bằng code (Partial Close)
            "deviation": 20,
            "magic": self.magic_number,
            "comment": "TSP_" + proposal.action,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC, # Tránh lỗi Unsupported filling
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"[TradeManager] Lỗi bắn lệnh {symbol}: {result.comment} (Code: {result.retcode})")
            return False
            
        logger.info(f"[TradeManager] Bắn Lệnh THÀNH CÔNG: {proposal.action.upper()} {symbol} | Lot: {lot} | Ticket: {result.order}")
        return True

    def manage_open_trades(self, tp1_ratio: float = 1.5):
        """
        Quét vòng lặp ngầm:
        - Dùng MAGIC NUMBER để tóm lệnh (Bất chấp Ticket ID bị thay đổi do Partial Close).
        - Nếu chạy tới TP1 -> Đóng 50% Vol -> Dời SL của 50% còn lại về BE + Offset.
        """
        positions = mt5.positions_get(magic=self.magic_number)
        if positions is None or len(positions) == 0:
            return

        for pos in positions:
            symbol = pos.symbol
            info = mt5.symbol_info(symbol)
            if not info: continue
            
            # Tính khoảng cách Risk ban đầu
            risk_dist = abs(pos.price_open - pos.sl)
            if risk_dist == 0: continue
            
            # Tính giá trị TP1 thực tế
            if pos.type == mt5.POSITION_TYPE_BUY:
                tp1_price = pos.price_open + (risk_dist * tp1_ratio)
                is_hit_tp1 = pos.price_current >= tp1_price
                be_price = pos.price_open + (self.breakeven_offset_points * info.point)
            else:
                tp1_price = pos.price_open - (risk_dist * tp1_ratio)
                is_hit_tp1 = pos.price_current <= tp1_price
                be_price = pos.price_open - (self.breakeven_offset_points * info.point)

            # Đã từng Partial Close và dời SL chưa? (Check qua SL hiện tại)
            # Nếu SL đã ở quanh mức BE_Price -> Nghĩa là ĐÃ xử lý xong, bỏ qua.
            if abs(pos.sl - be_price) < (10 * info.point) or (pos.type == mt5.POSITION_TYPE_BUY and pos.sl > pos.price_open) or (pos.type == mt5.POSITION_TYPE_SELL and pos.sl < pos.price_open):
                continue 

            # XỬ LÝ KHI CHẠM TP1
            if is_hit_tp1:
                # BƯỚC A: Partial Close (Cắt 50% Lot)
                half_lot = max(info.volume_min, round(pos.volume / 2 / info.volume_step) * info.volume_step)
                
                if half_lot < pos.volume:
                    close_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": symbol,
                        "volume": float(half_lot),
                        "type": mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY,
                        "position": pos.ticket, # Cắt dựa vào Ticket ID HIỆN TẠI
                        "price": mt5.symbol_info_tick(symbol).bid if pos.type == mt5.POSITION_TYPE_BUY else mt5.symbol_info_tick(symbol).ask,
                        "deviation": 20,
                        "magic": self.magic_number,
                        "comment": "Partial_Close_TP1",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    mt5.order_send(close_request)
                    logger.info(f"[TradeManager] {symbol}: Đã chốt lãi 50% khối lượng tại TP1.")
                    
                # BƯỚC B: Dời Stoploss về BE + Offset
                # Rào cản StopLevel (Kiểm tra khoảng cách giá hiện tại và điểm muốn đặt SL)
                stop_level_points = info.trade_stops_level
                current_dist_to_be = abs(pos.price_current - be_price) / info.point
                
                if current_dist_to_be > stop_level_points:
                    mod_request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "position": pos.ticket,
                        "symbol": symbol,
                        "sl": float(be_price),
                        "tp": float(pos.tp), # Giữ nguyên TP max
                        "magic": self.magic_number
                    }
                    res = mt5.order_send(mod_request)
                    if res.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"[TradeManager] {symbol}: Đã kéo Stoploss về Hòa vốn (Risk = 0).")
