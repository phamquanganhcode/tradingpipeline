"""
modules/telegram_notifier.py
────────────────────────────────────────────────────────────────
Module gửi thông báo qua Telegram khi có tín hiệu giao dịch 
hoặc cập nhật lệnh (chạm SL/TP, dời SL).
"""

from __future__ import annotations

import requests
import urllib.parse
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

class TelegramNotifier:
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.is_enabled = bool(self.bot_token and self.chat_id)

    def send_message(self, message: str) -> bool:
        """Gửi tin nhắn text (hỗ trợ Markdown/HTML tùy chỉnh nếu cần)"""
        if not self.is_enabled:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }

        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                print("[Telegram] ✅ Đã gửi thông báo thành công.")
                return True
            else:
                print(f"[Telegram] ⚠️  Lỗi gửi tin: {response.text}")
                return False
        except Exception as e:
            print(f"[Telegram] ❌ Lỗi kết nối Telegram API: {e}")
            return False

    def notify_new_trade(self, proposal, validation) -> bool:
        """Định dạng và gửi thông báo khi có lệnh ACCEPT mới"""
        if validation.status != "ACCEPT":
            return False

        icon = "🟢" if proposal.decision == "BUY" else "🔴"
        
        entry = proposal.entry.price or proposal.entry.zone_low if proposal.entry else "N/A"
        tp_levels = ", ".join(map(str, proposal.take_profit)) if proposal.take_profit else "N/A"
        
        msg = (
            f"<b>{icon} TÍN HIỆU GIAO DỊCH MỚI</b>\n"
            f"<b>Cặp tiền:</b> #{proposal.symbol}\n"
            f"<b>Lệnh:</b> {proposal.decision}\n"
            f"<b>Entry:</b> {entry}\n"
            f"<b>SL:</b> {proposal.stop_loss}\n"
            f"<b>TP:</b> {tp_levels}\n\n"
            f"<b>Phân tích AI:</b>\n"
            f"<i>{proposal.setup}</i>\n"
            f"<b>R:R:</b> {validation.actual_rr}\n"
            f"<b>Đề xuất Lot (Risk 2%):</b> {validation.lot_size}"
        )
        return self.send_message(msg)

    def notify_trade_update(self, trade_id: int, symbol: str, actions: list[str]) -> bool:
        """Định dạng và gửi thông báo khi Trade Monitor có hành động mới"""
        if not actions:
            return False
            
        action_text = "\n".join([f"• {a}" for a in actions])
        msg = (
            f"<b>🔔 CẬP NHẬT LỆNH ĐANG MỞ</b>\n"
            f"<b>Trade ID:</b> #{trade_id}\n"
            f"<b>Cặp tiền:</b> #{symbol}\n\n"
            f"<b>Hành động:</b>\n"
            f"{action_text}"
        )
        return self.send_message(msg)
