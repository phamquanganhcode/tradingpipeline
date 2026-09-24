import os
import re
import json
import time
import asyncio
from google import genai
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
if NOTIFICATION_CHANNEL:
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
genai_client = None
if GEMINI_API_KEY:
    genai_client = genai.Client(api_key=GEMINI_API_KEY)

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
    if "tổng hợp" in message_text.lower():
        print("-> Đã chặn một tin nhắn báo cáo tổng hợp.")
        return None

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
    LƯU Ý QUAN TRỌNG: Nếu tin nhắn báo dời giá, hạ giá mà chỉ nói 2 hoặc 3 chữ số cuối (ví dụ "hạ xuống 35", "dời về 295"), bạn BẮT BUỘC phải ghép nó với đầu số của giá hiện tại để ra giá thực tế (ví dụ giá hiện tại là 4279, báo về 295 thì kết quả phải là 4295.0). Tuyệt đối không trả về 4229.5 hay số nhỏ vô lý.
    
    LƯU Ý: Trả về CHỈ một đoạn JSON chuẩn (không markdown).
    Nếu tin nhắn không phải là tín hiệu hoặc lệnh điều khiển, trả về JSON rỗng {{}}.
    
    Các trường cần có:
    "action": "NEW" (kèo mới), "UPDATE" (dời Entry/SL), "CANCEL" (chỉ trả về CANCEL khi tin nhắn là LỆNH YÊU CẦU hủy/xóa. KHÔNG trả về CANCEL nếu chữ "hủy", "xóa" chỉ là trạng thái của một kèo cũ như "Đã hủy"), hoặc "CLOSE" (nếu có chữ "đóng", "cắt", "chốt" -> luôn là CLOSE để đóng lệnh đang chạy).
    "symbol": "Tên cặp tiền (ví dụ XAUUSD). Nếu là UPDATE/CANCEL/CLOSE không nhắc tên, hãy ngầm hiểu là XAUUSD. Nếu hủy toàn bộ mọi cặp thì để null".
    "type": "BUY hoặc SELL. (Ví dụ 'hủy lệnh buy' -> action: CANCEL, type: BUY). Có thể null nếu áp dụng cho cả hai chiều".
    "entry1": Số thập phân cho giá vào lệnh 1 (Ví dụ Entry: 4292 4291 thì entry1 = 4292. Nếu chỉ có 1 giá thì lấy giá đó).
    "entry2": Số thập phân cho giá vào lệnh 2 (Ví dụ Entry: 4292 4291 thì entry2 = 4291. Nếu chỉ có 1 giá thì lấy giống hệt entry1).
    "sl": Số thập phân cho Stop Loss (Nếu có cập nhật SL thì ghi, không thì null).
    "tp1": Số thập phân cho Take Profit 1.
    "tp2": Số thập phân cho Take Profit 2.
    
    Tin nhắn:
    {message_text}
    """
    try:
        try:
            response = genai_client.models.generate_content(
                model='gemini-3.1-flash-lite',
                contents=prompt
            )
        except Exception as api_e:
            error_msg = str(api_e).lower()
            if '429' in error_msg or 'quota' in error_msg:
                print("-> Hết hạn ngạch (Rate Limit) của model 3.1! Tự động chuyển sang model dự phòng: gemini-3.5-flash-lite...")
                response = genai_client.models.generate_content(
                    model='gemini-3.5-flash-lite',
                    contents=prompt
                )
            else:
                raise api_e
                
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
            'entry1': float(data['entry1']) if data.get('entry1') else None,
            'entry2': float(data['entry2']) if data.get('entry2') else None,
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
            
        new_price = order.price_open
        new_sl = signal_data.get('sl') or order.sl
        new_tp = order.tp
        
        # Cập nhật Entry và TP đúng theo từng lệnh chia đôi (TP1 và TP2)
        if "TP1" in order.comment:
            if signal_data.get('entry1'):
                new_price = signal_data['entry1']
            if signal_data.get('tp1'):
                new_tp = signal_data['tp1']
        elif "TP2" in order.comment:
            if signal_data.get('entry2'):
                new_price = signal_data['entry2']
            if signal_data.get('tp2'):
                new_tp = signal_data['tp2']
        
        request = {
            "action": mt5.TRADE_ACTION_MODIFY,
            "order": order.ticket,
            "symbol": symbol,
            "price": float(new_price),
            "sl": float(new_sl),
            "tp": float(new_tp),
            "type_time": mt5.ORDER_TIME_GTC,
            "expiration": 0,
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
    logs = []

    # HÀM PHỤ ĐỂ GỬI TỪNG LỆNH (CHIA LỆNH)
    def send_order(volume, entry_price, tp_price, label):
        if volume <= 0 or not tp_price or not entry_price:
            return
            
        # Xác định loại lệnh cho mức giá này
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
            
        is_pending = order_type in (mt5.ORDER_TYPE_BUY_LIMIT, mt5.ORDER_TYPE_BUY_STOP, mt5.ORDER_TYPE_SELL_LIMIT, mt5.ORDER_TYPE_SELL_STOP)

        # --- KIỂM TRA TRÙNG LẶP ĐỂ TRÁNH ĐẶT LỆNH NHIỀU LẦN KHI TIN NHẮN BỊ EDIT ---
        if is_pending:
            existing_orders = mt5.orders_get(symbol=symbol)
            if existing_orders:
                for ord in existing_orders:
                    if ord.magic == MAGIC_NUMBER and ord.type == order_type and abs(ord.price_open - entry_price) < 0.00001 and label in ord.comment:
                        logs.append(f"⚠️ Bỏ qua lệnh {label}: Đã tồn tại lệnh chờ {signal_data['type']} tại giá {entry_price}")
                        return
        # --------------------------------------------------------------------------

        action_type = mt5.TRADE_ACTION_PENDING if is_pending else mt5.TRADE_ACTION_DEAL

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
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC if not is_pending else 0,
        }

        if not is_pending:
            request["price"] = current_ask if signal_data['type'] == 'BUY' else current_bid

        result = mt5.order_send(request)
        mode_text = "CHỜ" if is_pending else "MARKET"
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logs.append(f"❌ Lỗi đặt lệnh {label}: {result.retcode} - {result.comment}")
        else:
            logs.append(f"✅ Đã đặt lệnh {mode_text} {label} ({volume} lot): {signal_data['type']} {symbol} tại {request['price']} - TP: {tp_price}")

    # GỬI LỆNH LẦN LƯỢT VỚI ENTRY VÀ TP RIÊNG
    send_order(LOT_SIZE_TP1, signal_data.get('entry1'), signal_data.get('tp1'), "TP1")
    send_order(LOT_SIZE_TP2, signal_data.get('entry2'), signal_data.get('tp2'), "TP2")
    
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

message_text_cache = {}

async def process_event(event, event_type):
    msg_id = event.message.id
    msg_text = event.message.text
    
    if not msg_text:
        return
        
    if event_type == "EDIT":
        if message_text_cache.get(msg_id) == msg_text:
            print("-> Bỏ qua vì nội dung text không thay đổi.")
            return
            
    message_text_cache[msg_id] = msg_text
    
    if len(message_text_cache) > 1000:
        keys_to_remove = list(message_text_cache.keys())[:100]
        for k in keys_to_remove:
            del message_text_cache[k]
            
    await handle_signal_processing(msg_text)

@client.on(events.NewMessage(chats=CHANNEL_NAME))
async def handler(event):
    print("\n--- NHẬN ĐƯỢC TIN NHẮN MỚI ---")
    await process_event(event, "NEW")

@client.on(events.MessageEdited(chats=CHANNEL_NAME))
async def edit_handler(event):
    print("\n--- PHÁT HIỆN TIN NHẮN BỊ CHỈNH SỬA ---")
    await process_event(event, "EDIT")

async def main():
    print("Đang khởi động Bot...")
    if not connect_mt5():
        print(f"Lỗi: Không thể kết nối MT5. Lỗi: {mt5.last_error()}")
        return
    print("Đã kết nối MetaTrader 5.")
    
    if not API_ID or not API_HASH:
        print("Lỗi: Vui lòng cấu hình TELEGRAM_API_ID và TELEGRAM_API_HASH trong file .env")
        return

    await client.start(phone=PHONE_NUMBER)
    print(f"Đang lắng nghe tín hiệu từ kênh: {CHANNEL_NAME}")
    if NOTIFICATION_CHANNEL:
        print(f"Sẽ gửi báo cáo tự động tới kênh: {NOTIFICATION_CHANNEL}")
        
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
