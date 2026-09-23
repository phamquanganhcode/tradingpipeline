import os
import re
import json
import time
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv
from telethon import TelegramClient, events
import MetaTrader5 as mt5

# ==========================================
# 0. TẢI CẤU HÌNH TỪ FILE .ENV
# ==========================================
load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", 0))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
PHONE_NUMBER = os.getenv("TELEGRAM_PHONE_NUMBER", "")
CHANNEL_NAME = os.getenv("TELEGRAM_CHANNEL_NAME", "")
if CHANNEL_NAME.lstrip('-').isdigit():
    CHANNEL_NAME = int(CHANNEL_NAME)

# Cấu hình Lot chia đôi
LOT_SIZE_TP1 = float(os.getenv("MT5_LOT_SIZE_TP1", 0.02))
LOT_SIZE_TP2 = float(os.getenv("MT5_LOT_SIZE_TP2", 0.01))
MAGIC_NUMBER = int(os.getenv("MT5_MAGIC_NUMBER", 123456))
SYMBOL_SUFFIX = os.getenv("SYMBOL_SUFFIX", "")

MT5_LOGIN = int(os.getenv("MT5_LOGIN", 0)) if os.getenv("MT5_LOGIN") else 0
MT5_PASSWORD = os.getenv("MT5_PASSWORD", "")
MT5_SERVER = os.getenv("MT5_SERVER", "")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

PENDING_EXPIRATION_MINUTES = int(os.getenv("PENDING_EXPIRATION_MINUTES", 10))
MAX_TRADE_DURATION_MINUTES = int(os.getenv("MAX_TRADE_DURATION_MINUTES", 60))

# ==========================================
# HÀM KẾT NỐI MT5
# ==========================================
def connect_mt5():
    if MT5_LOGIN > 0 and MT5_PASSWORD and MT5_SERVER:
        return mt5.initialize(login=MT5_LOGIN, password=MT5_PASSWORD, server=MT5_SERVER)
    return mt5.initialize()

# ==========================================
# HÀM PHÂN TÍCH TIN NHẮN (BẰNG GEMINI AI)
# ==========================================
def parse_signal(message_text):
    ignore_keywords = ['hit', 'pips', 'profit', 'running', 'closed', 'win', 'loss']
    if any(keyword in message_text.lower() for keyword in ignore_keywords):
        print("-> Đã chặn một tin nhắn báo cáo kết quả.")
        return None
        
    if not GEMINI_API_KEY:
        print("Chưa cấu hình GEMINI_API_KEY!")
        return None

    prompt = f"""
    Bạn là một hệ thống phân tích tín hiệu Forex. Hãy đọc tin nhắn dưới đây và trích xuất thông tin.
    LƯU Ý: Trả về CHỈ một đoạn JSON chuẩn (không markdown).
    Nếu tin nhắn không phải là tín hiệu vào lệnh, trả về JSON rỗng {{}}.
    
    Các trường cần có:
    "symbol": "Tên cặp tiền (ví dụ XAUUSD)",
    "type": "BUY hoặc SELL. (Nếu text ghi Lệnh: WAIT nhưng có chữ Sell Limit/Sell Breakout thì trả về SELL. Nếu SL cao hơn Entry thì là SELL, SL thấp hơn Entry thì là BUY)",
    "entry": Số thập phân cho giá vào lệnh (Nếu có nhiều giá, lấy giá đầu tiên),
    "sl": Số thập phân cho Stop Loss,
    "tp1": Số thập phân cho Take Profit 1 (giá TP đầu tiên),
    "tp2": Số thập phân cho Take Profit 2 (giá TP thứ hai, nếu không có để 0)
    
    Tin nhắn:
    {message_text}
    """
    try:
        model = genai.GenerativeModel('gemini-3.1-flash-lite')
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        if text.startswith('```'):
            text = text.split('\n', 1)[1]
            if text.endswith('```'):
                text = text.rsplit('\n', 1)[0]
                
        data = json.loads(text)
        
        if not data.get('symbol') or not data.get('type') or not data.get('entry'):
            return None
            
        return {
            'symbol': data['symbol'].replace('#', '').strip(),
            'type': str(data['type']).upper().strip(),
            'entry': float(data['entry']),
            'sl': float(data.get('sl') or 0),
            'tp1': float(data.get('tp1') or 0),
            'tp2': float(data.get('tp2') or 0)
        }
    except Exception as e:
        print(f"Lỗi AI phân tích: {e}")
        return None

# ==========================================
# CÁC HÀM XỬ LÝ LỆNH TRÊN MT5
# ==========================================
def execute_trade(signal_data):
    symbol = signal_data['symbol'] + SYMBOL_SUFFIX
    
    if not connect_mt5():
        print(f"Không thể kết nối với MT5. Lỗi: {mt5.last_error()}")
        return
        
    if not mt5.symbol_select(symbol, True):
        print(f"Không tìm thấy cặp {symbol} trong MT5")
        return

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print("Lỗi: Không lấy được giá hiện tại.")
        return

    current_ask = tick.ask
    current_bid = tick.bid
    entry_price = signal_data['entry']
    
    # TÍNH TOÁN LOẠI LỆNH
    if signal_data['type'] == 'BUY':
        if entry_price < current_ask:
            order_type = mt5.ORDER_TYPE_BUY_LIMIT
        elif entry_price > current_ask:
            order_type = mt5.ORDER_TYPE_BUY_STOP
        else:
            order_type = mt5.ORDER_TYPE_BUY
            
    elif signal_data['type'] == 'SELL':
        if entry_price > current_bid:
            order_type = mt5.ORDER_TYPE_SELL_LIMIT
        elif entry_price < current_bid:
            order_type = mt5.ORDER_TYPE_SELL_STOP
        else:
            order_type = mt5.ORDER_TYPE_SELL
    else:
        return

    expiration = int(time.time()) + (PENDING_EXPIRATION_MINUTES * 60)
    is_pending = order_type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP)
    action_type = mt5.TRADE_ACTION_PENDING if is_pending else mt5.TRADE_ACTION_DEAL

    # HÀM PHỤ ĐỂ GỬI TỪNG LỆNH (CHIA LỆNH)
    def send_order(volume, tp_price, label):
        if volume <= 0 or tp_price <= 0:
            return
            
        request = {
            "action": action_type,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": entry_price,
            "sl": signal_data['sl'],
            "tp": tp_price,
            "deviation": 20,
            "magic": MAGIC_NUMBER,
            "comment": f"Bot AI - {label}",
        }
        
        if is_pending:
            request["type_time"] = mt5.ORDER_TIME_SPECIFIED
            request["expiration"] = expiration
        else:
            request["type_time"] = mt5.ORDER_TIME_GTC
            request["type_filling"] = mt5.ORDER_FILLING_IOC
            request["price"] = current_ask if signal_data['type'] == 'BUY' else current_bid

        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Lỗi đặt lệnh {label}: {result.retcode} - {result.comment}")
        else:
            mode_text = "CHO" if is_pending else "MARKET"
            print(f"Da dat lenh {mode_text} {label} ({volume} lot): {signal_data['type']} {symbol} tai {request['price']} - TP: {tp_price}")

    # GỬI LỆNH LẦN LƯỢT CHO TP1 VÀ TP2
    send_order(LOT_SIZE_TP1, signal_data['tp1'], "TP1")
    send_order(LOT_SIZE_TP2, signal_data['tp2'], "TP2")


def close_position(position):
    tick = mt5.symbol_info_tick(position.symbol)
    if not tick:
        return
    
    if position.type == mt5.ORDER_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    elif position.type == mt5.ORDER_TYPE_SELL:
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    else:
        return

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": position.ticket,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": "Auto Close > 60m",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"Lỗi tự động đóng lệnh {position.ticket}: {result.retcode} - {result.comment}")
    else:
        print(f"Đã TỰ ĐỘNG ĐÓNG lệnh {position.ticket} (lãi/lỗ: {position.profit}$) do quá thời gian {MAX_TRADE_DURATION_MINUTES} phút.")

async def trade_manager_loop():
    print(f"Đã kích hoạt hệ thống Quản Lý Lệnh (Tuần tra tự đóng lệnh sau {MAX_TRADE_DURATION_MINUTES} phút).")
    while True:
        try:
            if mt5.terminal_info() is not None:
                positions = mt5.positions_get(magic=MAGIC_NUMBER)
                if positions:
                    current_time = time.time()
                    for pos in positions:
                        duration = current_time - pos.time
                        if duration >= (MAX_TRADE_DURATION_MINUTES * 60):
                            print(f"\nPhát hiện lệnh {pos.ticket} đã mở quá {MAX_TRADE_DURATION_MINUTES} phút. Đang xử lý đóng lệnh...")
                            close_position(pos)
        except Exception as e:
            print(f"Lỗi hệ thống quản lý lệnh: {e}")
            
        await asyncio.sleep(10)

client = TelegramClient('session_name', API_ID, API_HASH)

@client.on(events.NewMessage(chats=CHANNEL_NAME))
async def handler(event):
    message_text = event.message.text
    print("\n--- NHẬN ĐƯỢC TIN NHẮN MỚI ---")
    print(message_text)
    
    signal_data = parse_signal(message_text)
    
    if signal_data:
        print(f"Đã phân tích tín hiệu AI: {signal_data}")
        execute_trade(signal_data)

async def main():
    print("Đang khởi động Bot...")
    if not connect_mt5():
        print(f"Lỗi: Không thể kết nối MT5. Lỗi: {mt5.last_error()}")
        return
    print("Đã kết nối MetaTrader 5.")
    
    if not API_ID or not API_HASH:
        print("Lỗi: Vui lòng cấu hình TELEGRAM_API_ID và TELEGRAM_API_HASH trong file .env")
        return

    asyncio.create_task(trade_manager_loop())

    await client.start(phone=PHONE_NUMBER)
    print(f"Đang lắng nghe tin nhắn từ kênh: {CHANNEL_NAME}...")
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
