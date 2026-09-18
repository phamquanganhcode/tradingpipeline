"""
modules/mt5_executor.py
────────────────────────────────────────────────────────────────
Cầu nối thực thi lệnh trực tiếp lên MetaTrader 5 (Exness, v.v.)
"""
import os
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

    def execute_trade(self, symbol: str, decision: str, entry_type: str, entry_price: float, sl: float, tp: float, lot_size: float) -> bool:
        """Gửi lệnh giao dịch lên sàn."""
        if not self.is_connected:
            if not self.connect():
                return False

        # Kiểm tra Symbol có tồn tại trên sàn không (VD: Exness thường là XAUUSDm hoặc XAUUSD)
        symbol_info = mt5.symbol_info(symbol)
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
            "type_time": mt5.ORDER_TIME_GTC, # Good till cancelled
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        # Gửi lệnh
        print(f"[MT5] ⏳ Đang gửi lệnh {decision} {lot_size} lot {symbol}...")
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"[MT5] ❌ Đặt lệnh THẤT BẠI. Mã lỗi: {result.retcode} - {result.comment}")
            return False
            
        print(f"[MT5] ✅ Đặt lệnh THÀNH CÔNG! Ticket: {result.order}")
        return True
        
    def shutdown(self):
        mt5.shutdown()
