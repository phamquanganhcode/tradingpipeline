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

NOTIFICATION_CHANNEL = os.getenv("TELEGRAM_NOTIFICATION_CHANNEL", "")
if NOTIFICATION_CHANNEL.lstrip('-').isdigit():
    NOTIFICATION_CHANNEL = int(NOTIFICATION_CHANNEL)
else:
    NOTIFICATION_CHANNEL = None

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
def parse_signal(message_text, current_price_info=""):
    ignore_keywords = ['hit', 'pips', 'profit', 'running', 'closed', 'win', 'loss']
    # Chỉ chặn nếu là báo cáo kết quả thuần túy (không chứa từ khóa ra lệnh như hạ, dời, hủy, đóng, cắt, chốt)
    action_keywords = ['hạ', 'dời', 'hủy', 'đóng', 'cắt', 'chốt']
    if any(keyword in message_text.lower() for keyword in ignore_keywords) and not any(kw in message_text.lower() for kw in action_keywords):
        print("-> Đã chặn một tin nhắn báo cáo kết quả.")
        return None
        
    if not GEMINI_API_KEY:
        print("Chưa cấu hình GEMINI_API_KEY!")
        return None

    prompt = f"""
    Bạn là một hệ thống phân tích tín hiệu Forex. Hãy đọc tin nhắn dưới đây và trích xuất thông tin.
    {current_price_info}
    LƯU Ý QUAN TRỌNG: Nếu tin nhắn báo dời giá, hạ giá mà chỉ nói 2 chữ số cuối (ví dụ "hạ xuống 35", "dời về 38"), bạn BẮT BUỘC phải ghép nó với đầu số của giá hiện tại để ra giá thực tế (ví dụ giá hiện tại là 4339, báo về 38 thì kết quả phải là 4338.0). Tuyệt đối không trả về số 38.0.
    
    LƯU Ý: Trả về CHỈ một đoạn JSON chuẩn (không markdown).
    Nếu tin nhắn không phải là tín hiệu hoặc lệnh điều khiển, trả về JSON rỗng {{}}.
    
    Các trường cần có:
    "action": "NEW" (kèo mới), "UPDATE" (dời Entry/SL), "CANCEL" (nếu có chữ "hủy", "xóa" -> luôn là CANCEL để xóa lệnh chờ), hoặc "CLOSE" (nếu có chữ "đóng", "cắt", "chốt" -> luôn là CLOSE để đóng lệnh đang chạy).
    "symbol": "Tên cặp tiền (ví dụ XAUUSD). Nếu là UPDATE/CANCEL/CLOSE không nhắc tên, hãy ngầm hiểu là XAUUSD. Nếu hủy toàn bộ mọi cặp thì để null".
    "type": "BUY hoặc SELL. (Ví dụ 'hủy lệnh buy' -> action: CANCEL, type: BUY). Có thể null nếu áp dụng cho cả hai chiều".
    "entry": Số thập phân cho giá vào lệnh (Nếu có nhiều giá, lấy giá đầu tiên. Nếu là tin UPDATE báo dời giá, ghi mức giá mới vào đây).
    "sl": Số thập phân cho Stop Loss (Nếu có cập nhật SL thì ghi, không thì null).
    "tp1": Số thập phân cho Take Profit 1.
    "tp2": Số thập phân cho Take Profit 2.
    
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
        
        if not data.get('action'):
            return None
            
        return {
            'action': data.get('action', 'NEW').upper().strip(),
            'symbol': data.get('symbol').replace('#', '').strip() if data.get('symbol') else None,
            'type': str(data.get('type', '')).upper().strip() if data.get('type') else None,
            'entry': float(data['entry']) if data.get('entry') else None,
            'sl': float(data['sl']) if data.get('sl') else None,
            'tp1': float(data['tp1']) if data.get('tp1') else None,
            'tp2': float(data['tp2']) if data.get('tp2') else None
        }
    except Exception as e:
        print(f"Lỗi AI phân tích: {e}")
        return None

# ==========================================
# CÁC HÀM XỬ LÝ LỆNH TRÊN MT5 (TRẢ VỀ STRING ĐỂ BÁO CÁO)
# ==========================================
def cancel_pending_orders(signal_data):
    if not connect_mt5():
        return "⚠️ Không thể kết nối với MT5."
        
    symbol = signal_data.get('symbol')
    if symbol:
        symbol += SYMBOL_SUFFIX
        orders = mt5.orders_get(symbol=symbol)
    else:
        orders = mt5.orders_get()
        
    if not orders:
        return "⚠️ Không có lệnh CHỜ nào để hủy."
        
    target_type = signal_data.get('type')
    logs = []
    
    for order in orders:
        if order.magic != MAGIC_NUMBER:
            continue
            
        if target_type == 'BUY' and order.type not in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP):
            continue
        if target_type == 'SELL' and order.type not in (mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP):
            continue
            
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": order.ticket,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logs.append(f"❌ Lỗi hủy lệnh {order.ticket}: {result.retcode}")
        else:
            logs.append(f"✅ Đã HỦY lệnh chờ {order.ticket} thành công.")
            
    return "\n".join(logs) if logs else "⚠️ Không có lệnh chờ nào khớp yêu cầu để hủy."

def close_open_positions_by_signal(signal_data):
    if not connect_mt5():
        return "⚠️ Không thể kết nối với MT5."
        
    symbol = signal_data.get('symbol')
    if symbol:
        symbol += SYMBOL_SUFFIX
        positions = mt5.positions_get(symbol=symbol)
    else:
        positions = mt5.positions_get()
        
    if not positions:
        return "⚠️ Không có lệnh ĐANG MỞ nào để đóng."
        
    target_type = signal_data.get('type')
    logs = []
    
    for pos in positions:
        if pos.magic != MAGIC_NUMBER:
            continue
            
        if target_type == 'BUY' and pos.type != mt5.ORDER_TYPE_BUY:
            continue
        if target_type == 'SELL' and pos.type != mt5.ORDER_TYPE_SELL:
            continue
            
        res = close_position(pos, comment="Closed via Telegram")
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            logs.append(f"✅ Đã ĐÓNG TAY lệnh {pos.ticket}.")
        else:
            logs.append(f"❌ Lỗi đóng lệnh {pos.ticket}.")
            
    return "\n".join(logs) if logs else "⚠️ Không có lệnh đang mở nào khớp yêu cầu để đóng."

def update_pending_orders(signal_data):
    if not signal_data.get('symbol'):
        return "⚠️ Không xác định được cặp tiền để cập nhật."
    symbol = signal_data['symbol'] + SYMBOL_SUFFIX
    
    if not connect_mt5():
        return "⚠️ Không thể kết nối với MT5."
        
    orders = mt5.orders_get(symbol=symbol)
    if not orders:
        return f"⚠️ Không tìm thấy lệnh chờ nào cho cặp {symbol} để cập nhật."
        
    logs = []
    for order in orders:
        if order.magic != MAGIC_NUMBER:
            continue
            
        new_price = signal_data.get('entry') or order.price_open
        new_sl = signal_data.get('sl') or order.sl
        new_tp = order.tp
        
        # Cập nhật TP đúng theo từng lệnh chia đôi
        if "TP1" in order.comment and signal_data.get('tp1'):
            new_tp = signal_data['tp1']
        elif "TP2" in order.comment and signal_data.get('tp2'):
            new_tp = signal_data['tp2']
        
        request = {
            "action": mt5.TRADE_ACTION_MODIFY,
            "order": order.ticket,
            "symbol": symbol,
            "price": float(new_price),
            "sl": float(new_sl),
            "tp": float(new_tp),
            "type_time": order.type_time,
            "expiration": order.time_expiration,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logs.append(f"❌ Lỗi cập nhật lệnh {order.ticket}: {result.comment}")
        else:
            logs.append(f"✅ Đã cập nhật lệnh chờ {order.ticket}! Entry: {new_price} | SL: {new_sl} | TP: {new_tp}")
            
    return "\n".join(logs) if logs else "⚠️ Không có lệnh chờ hợp lệ để cập nhật."


def execute_trade(signal_data):
    if not signal_data.get('symbol'):
        return "⚠️ Lỗi: Không xác định được cặp tiền."
    symbol = signal_data['symbol'] + SYMBOL_SUFFIX
    
    if not connect_mt5():
        return "⚠️ Không thể kết nối với MT5."
        
    if not mt5.symbol_select(symbol, True):
        return f"⚠️ Không tìm thấy cặp {symbol} trong MT5"

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return "⚠️ Lỗi: Không lấy được giá hiện tại."

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
        return "⚠️ Không xác định được loại lệnh BUY/SELL."

    expiration = int(time.time()) + (PENDING_EXPIRATION_MINUTES * 60)
    is_pending = order_type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP)
    action_type = mt5.TRADE_ACTION_PENDING if is_pending else mt5.TRADE_ACTION_DEAL

    logs = []

    # HÀM PHỤ ĐỂ GỬI TỪNG LỆNH (CHIA LỆNH)
    def send_order(volume, tp_price, label):
        if volume <= 0 or not tp_price:
            return
            
        request = {
            "action": action_type,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": entry_price,
            "sl": signal_data.get('sl') or 0.0,
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
        mode_text = "CHỜ" if is_pending else "MARKET"
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logs.append(f"❌ Lỗi đặt lệnh {label}: {result.retcode} - {result.comment}")
        else:
            logs.append(f"✅ Đã đặt lệnh {mode_text} {label} ({volume} lot): {signal_data['type']} {symbol} tại {request['price']} - TP: {tp_price}")

    # GỬI LỆNH LẦN LƯỢT CHO TP1 VÀ TP2
    send_order(LOT_SIZE_TP1, signal_data['tp1'], "TP1")
    send_order(LOT_SIZE_TP2, signal_data['tp2'], "TP2")
    
    return "\n".join(logs)


def close_position(position, comment="Auto Close"):
    tick = mt5.symbol_info_tick(position.symbol)
    if not tick:
        return None
    
    if position.type == mt5.ORDER_TYPE_BUY:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    elif position.type == mt5.ORDER_TYPE_SELL:
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    else:
        return None

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "position": position.ticket,
        "symbol": position.symbol,
        "volume": position.volume,
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    return mt5.order_send(request)

async def trade_manager_loop(client):
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
                            result = close_position(pos, comment=f"Close > {MAX_TRADE_DURATION_MINUTES}m")
                            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                                msg = f"⏳ TỰ ĐỘNG ĐÓNG lệnh {pos.ticket} (lãi/lỗ: {pos.profit}$) do quá thời gian."
                                print(msg)
                                if NOTIFICATION_CHANNEL:
                                    await client.send_message(NOTIFICATION_CHANNEL, f"🤖 **BOT REPORT:**\n{msg}")
                            else:
                                print(f"Lỗi đóng lệnh tự động: {result.comment}")
        except Exception as e:
            print(f"Lỗi hệ thống quản lý lệnh: {e}")
            
        await asyncio.sleep(10)

client = TelegramClient('session_name', API_ID, API_HASH)

async def handle_signal_processing(message_text):
    print(message_text)
    current_price_info = ""
    if connect_mt5():
        tick = mt5.symbol_info_tick("XAUUSD" + SYMBOL_SUFFIX)
        if tick:
            current_price_info = f"GỢI Ý: Giá XAUUSD hiện tại trên thị trường đang là {tick.ask}."
            
    signal_data = parse_signal(message_text, current_price_info)
    
    result_msg = ""
    if signal_data:
        print(f"Đã phân tích tín hiệu AI: {signal_data}")
        action = signal_data.get('action')
        
        if action == 'UPDATE':
            result_msg = update_pending_orders(signal_data)
        elif action == 'CANCEL':
            result_msg = cancel_pending_orders(signal_data)
        elif action == 'CLOSE':
            result_msg = close_open_positions_by_signal(signal_data)
        else:
            result_msg = execute_trade(signal_data)
            
        print(result_msg)
        if result_msg and NOTIFICATION_CHANNEL:
            try:
                await client.send_message(NOTIFICATION_CHANNEL, f"🤖 **BOT REPORT:**\n{result_msg}")
            except Exception as e:
                print(f"Không thể gửi tin báo cáo tới Telegram: {e}")

@client.on(events.NewMessage(chats=CHANNEL_NAME))
async def handler(event):
    print("\n--- NHẬN ĐƯỢC TIN NHẮN MỚI ---")
    await handle_signal_processing(event.message.text)

@client.on(events.MessageEdited(chats=CHANNEL_NAME))
async def edit_handler(event):
    print("\n--- PHÁT HIỆN TIN NHẮN BỊ CHỈNH SỬA ---")
    await handle_signal_processing(event.message.text)

async def main():
    print("Đang khởi động Bot...")
    if not connect_mt5():
        print(f"Lỗi: Không thể kết nối MT5. Lỗi: {mt5.last_error()}")
        return
    print("Đã kết nối MetaTrader 5.")
    
    if not API_ID or not API_HASH:
        print("Lỗi: Vui lòng cấu hình TELEGRAM_API_ID và TELEGRAM_API_HASH trong file .env")
        return

    asyncio.create_task(trade_manager_loop(client))

    await client.start(phone=PHONE_NUMBER)
    print(f"Đang lắng nghe tín hiệu từ kênh: {CHANNEL_NAME}")
    if NOTIFICATION_CHANNEL:
        print(f"Sẽ gửi báo cáo tự động tới kênh: {NOTIFICATION_CHANNEL}")
        
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
