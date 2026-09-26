import asyncio
import os
import google.generativeai as genai
from dotenv import load_dotenv
import json
import time

load_dotenv('d:/TradingPineline/TelegramMT5Copier/.env')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)

def parse_signal(message_text, current_price_info=""):
    ignore_keywords = ['hit', 'pips', 'profit', 'running', 'closed', 'win', 'loss']
    action_keywords = ['hạ', 'dời', 'hủy', 'đóng', 'cắt', 'chốt']
    if any(keyword in message_text.lower() for keyword in ignore_keywords) and not any(kw in message_text.lower() for kw in action_keywords):
        return f"BLOCKED: {message_text}"
        
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
    "entry1": Số thập phân cho giá vào lệnh 1 (Ví dụ Entry: 4292 4291 thì entry1 = 4292. Nếu chỉ có 1 giá thì lấy giá đó).
    "entry2": Số thập phân cho giá vào lệnh 2 (Ví dụ Entry: 4292 4291 thì entry2 = 4291. Nếu chỉ có 1 giá thì lấy giống hệt entry1).
    "sl": Số thập phân cho Stop Loss (Nếu có cập nhật SL thì ghi, không thì null).
    "tp1": Số thập phân cho Take Profit 1.
    "tp2": Số thập phân cho Take Profit 2.
    
    Tin nhắn:
    {message_text}
    """
    try:
        model = genai.GenerativeModel('gemini-3.1-flash-lite')
        response = model.generate_content(prompt)
    except Exception as api_e:
        error_msg = str(api_e).lower()
        if '429' in error_msg or 'quota' in error_msg:
            print("Fallback to gemini-3.5-flash-lite...")
            model_fallback = genai.GenerativeModel('gemini-3.5-flash-lite')
            response = model_fallback.generate_content(prompt)
        else:
            raise api_e
            
    text = response.text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        if text.endswith('```'):
            text = text.rsplit('\n', 1)[0]
    return text

messages = [
    "PAIR: #XAUUSD TYPE: BUY LIMIT Entry: 4282 4281 TP1: 4290.5 TP2: 4299.0",
    "PAIR: #XAUUSD TYPE: BUY LIMIT Entry: 4282 4281 ✅ TP1: 4290.5 TP2: 4299.0",
    "PAIR: #XAUUSD TYPE: BUY LIMIT Entry: 4282 4281 ✅ TP1: 4290.5 \n\n #XAUUSD - BUY \n ✅ +60 Pips (Profit Running)",
    "Đẩy lên 81 nhé ae không đón nữa thì dọn hàng nhé",
    "30 pép rồi lên đi cho ae ăn khuya cái rồi còn đi ngủ nào",
    "Khả năng cậu tới đón"
]

for m in messages:
    print(f"--- {m} ---")
    try:
        print(parse_signal(m))
    except Exception as e:
        print("Error:", e)
    print("\n")
    time.sleep(2)
