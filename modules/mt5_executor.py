"""
modules/mt5_executor.py
────────────────────────────────────────────────────────────────
Cầu nối thực thi lệnh trực tiếp lên MetaTrader 5 (Exness, v.v.)
"""
import os
import datetime
import MetaTrader5 as mt5
from dotenv import load_dotenv

load_dotenv()

MT5_LOGIN = int(os.getenv("MT5_LOGIN", 0))
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

class MT5Executor:
    def __init__(self):
        self.is_connected = False
        
    def connect(self) -> bool:
        """Khởi tạo kết nối tới Terminal MT5."""
        if not MT5_LOGIN or not MT5_PASSWORD or not MT5_SERVER:
            print("[MT5] ⚠️ Chưa cấu hình MT5_LOGIN, MT5_PASSWORD, MT5_SERVER trong .env")
            return False
            
        if not mt5.initialize():
            print(f"[MT5] ❌ Không thể khởi tạo MT5. Lỗi: {mt5.last_error()}")
            return False
            
        authorized = mt5.login(MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
        if authorized:
            print(f"[MT5] ✅ Kết nối thành công tài khoản: {MT5_LOGIN} ({MT5_SERVER})")
            self.is_connected = True
            return True
        else:
            print(f"[MT5] ❌ Đăng nhập thất bại. Lỗi: {mt5.last_error()}")
            return False

    def execute_trade(self, symbol: str, decision: str, entry_type: str, entry_price: float, sl: float, tp: float, lot_size: float, clear_pending: bool = True) -> bool:
        """Gửi lệnh giao dịch lên sàn."""
        if not self.is_connected:
            if not self.connect():
                return False

        # Kiểm tra Symbol có tồn tại trên sàn không
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            # Thử các biến thể hoa/thường hoặc đuôi m/c
            alt_candidates = [
                symbol.upper(), symbol.lower(),
                symbol.rstrip("m").rstrip("M"),
                f"{symbol.rstrip('m').rstrip('M')}m",
                f"{symbol.rstrip('m').rstrip('M')}c",
            ]
            for alt in alt_candidates:
                s_info = mt5.symbol_info(alt)
                if s_info:
                    print(f"[MT5] ℹ️  Tự động khớp mã: '{symbol}' -> '{alt}'")
                    symbol = alt
                    symbol_info = s_info
                    break

        if symbol_info is None:
            print(f"[MT5] ❌ Không tìm thấy mã {symbol} trên sàn.")
            return False
            
        if not symbol_info.visible:
            if not mt5.symbol_select(symbol, True):
                print(f"[MT5] ❌ Không thể bật mã {symbol} trong Market Watch.")
                return False

        # Xác định loại lệnh (ORDER_TYPE)
        order_type = None
        action = mt5.TRADE_ACTION_PENDING
        
        # Nếu là BUY
        if decision == "BUY":
            if entry_type.lower() == "market":
                order_type = mt5.ORDER_TYPE_BUY
                action = mt5.TRADE_ACTION_DEAL
                entry_price = mt5.symbol_info_tick(symbol).ask
            elif "limit" in entry_type.lower():
                order_type = mt5.ORDER_TYPE_BUY_LIMIT
            elif "stop" in entry_type.lower():
                order_type = mt5.ORDER_TYPE_BUY_STOP
        
        # Nếu là SELL
        elif decision == "SELL":
            if entry_type.lower() == "market":
                order_type = mt5.ORDER_TYPE_SELL
                action = mt5.TRADE_ACTION_DEAL
                entry_price = mt5.symbol_info_tick(symbol).bid
            elif "limit" in entry_type.lower():
                order_type = mt5.ORDER_TYPE_SELL_LIMIT
            elif "stop" in entry_type.lower():
                order_type = mt5.ORDER_TYPE_SELL_STOP
                
        if order_type is None:
            print(f"[MT5] ⚠️ Không hỗ trợ loại lệnh: {decision} {entry_type}")
            return False

        # XÓA LỆNH CHỜ CŨ CỦA BOT (tránh nhồi lệnh)
        if clear_pending:
            existing_orders = mt5.orders_get(symbol=symbol)
            if existing_orders:
                for order in existing_orders:
                    if order.magic == 999999:  # Chỉ can thiệp lệnh do bot đặt
                        cancel_request = {
                            "action": mt5.TRADE_ACTION_REMOVE,
                            "order": order.ticket,
                        }
                        mt5.order_send(cancel_request)
                        print(f"[MT5] 🗑️ Đã xóa lệnh chờ cũ (Ticket: {order.ticket}) để cập nhật lệnh mới.")

        # Cấu trúc Request gửi lên MT5
        request = {
            "action": action,
            "symbol": symbol,
            "volume": float(lot_size),
            "type": order_type,
            "price": float(entry_price),
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 20,
            "magic": 999999,      # Magic number để nhận diện lệnh do Bot đánh
            "comment": "AI Bot",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Nếu là lệnh Pending (Chờ), cài đặt tự động hủy sau 4 giờ
        if action == mt5.TRADE_ACTION_PENDING:
            expiration_time = int((datetime.datetime.now() + datetime.timedelta(hours=4)).timestamp())
            request["type_time"] = mt5.ORDER_TIME_SPECIFIED
            request["expiration"] = expiration_time
        else:
            request["type_time"] = mt5.ORDER_TIME_GTC

        # Gửi lệnh
        print(f"[MT5] ⏳ Đang gửi lệnh {decision} {lot_size} lot {symbol}...")
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[MT5] ❌ Đặt lệnh THẤT BẠI. Mã lỗi: {result.retcode} - {result.comment}")
            return False
            
        print(f"[MT5] ✅ Đặt lệnh THÀNH CÔNG! Ticket: {result.order}")
        return True
        
    def get_current_status(self, symbol: str) -> str:
        """Lấy thông tin lệnh đang mở (position) hoặc lệnh chờ (pending) của symbol này (chỉ lấy lệnh của bot)."""
        if not self.is_connected:
            if not self.connect():
                return "Không thể kết nối MT5 để đọc lệnh."

        status_text = []

        # Kiểm tra Positions (lệnh đang chạy)
        positions = mt5.positions_get(symbol=symbol)
        if positions:
            for pos in positions:
                if pos.magic == 999999:
                    pos_type = "BUY" if pos.type == mt5.POSITION_TYPE_BUY else "SELL"
                    status_text.append(f"- [POSITION ĐANG CHẠY] {pos_type} {pos.volume} lot | Entry: {pos.price_open} | SL: {pos.sl} | TP: {pos.tp} | Lợi nhuận hiện tại: ${pos.profit:.2f}")

        # Kiểm tra Orders (lệnh chờ)
        orders = mt5.orders_get(symbol=symbol)
        if orders:
            for order in orders:
                if order.magic == 999999:
                    o_type = "PENDING"
                    if order.type == mt5.ORDER_TYPE_BUY_LIMIT: o_type = "BUY LIMIT"
                    elif order.type == mt5.ORDER_TYPE_SELL_LIMIT: o_type = "SELL LIMIT"
                    elif order.type == mt5.ORDER_TYPE_BUY_STOP: o_type = "BUY STOP"
                    elif order.type == mt5.ORDER_TYPE_SELL_STOP: o_type = "SELL STOP"
                    status_text.append(f"- [{o_type} ĐANG CHỜ] {order.volume} lot | Chờ khớp tại: {order.price_open} | SL: {order.sl} | TP: {order.tp}")

        if not status_text:
            return "Hiện tại KHÔNG CÓ lệnh nào (do bot đánh) đang chạy hoặc đang chờ."

        return "\n".join(status_text)

    def shutdown(self):
        mt5.shutdown()
