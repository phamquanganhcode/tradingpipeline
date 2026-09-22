"""
modules/gemini_client.py
────────────────────────────────────────────────────────────────
Gọi Gemini API với Structured Output và parse kết quả
thành TradeProposal Pydantic object.

Cải thiện v2:
- Retry tối đa 3 lần với exponential backoff (2s, 5s, 15s)
- Fallback về WAIT proposal an toàn nếu tất cả lần thử đều thất bại
- Log rõ ràng từng lần retry
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from config import GEMINI_API_KEY, GEMINI_MODEL
from models.schemas import (
    TradeProposal, ThoughtProcess, EntryZone
)


# ─────────────────────────────────────────────────────────────
# RETRY CONFIG
# ─────────────────────────────────────────────────────────────

MAX_RETRIES   = 3
RETRY_DELAYS  = [2, 5, 15]   # giây chờ giữa các lần retry


# ─────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Bạn là một Senior Trader với 15 năm kinh nghiệm, chuyên về Price Action, 
Market Structure và phân tích kỹ thuật đa khung thời gian.

Nguyên tắc tuyệt đối:
1. LUÔN điền thought_process đầy đủ TRƯỚC khi đưa ra decision.
2. Kiểm tra đủ các bước checklist chiến lược — liệt kê rõ bước nào PASS, bước nào FAIL.
3. Nếu thị trường hiện tại chưa có nến tín hiệu (trigger) hoặc đang sideway, decision có thể là "WAIT".
4. QUAN TRỌNG: Ngay cả khi decision là "WAIT", bạn VẪN BẮT BUỘC phải cung cấp kế hoạch giao dịch CHỜ (Pending Setup) tốt nhất. Hãy phân tích xem nên chờ mua/bán Pullback (Limit) hay Breakout (Stop), và ĐIỀN ĐẦY ĐỦ các trường `entry`, `stop_loss`, `take_profit` cho kịch bản đó.
5. SL và TP phải được tính toán dựa trên cấu trúc, ATR và Bollinger Bands.
6. PHƯƠNG PHÁP SWING TRADING: Chỉ xác định xu hướng chính dựa trên H4 và H1. Phải sử dụng khung M30 để tìm điểm vào lệnh (Entry), Stop Loss (SL) và Take Profit (TP).
7. Trả về JSON hợp lệ, không thêm text thừa ngoài JSON."""


# ─────────────────────────────────────────────────────────────
# FALLBACK PROPOSAL (khi tất cả lần retry đều thất bại)
# ─────────────────────────────────────────────────────────────

def _create_fallback_proposal(symbol: str, error_msg: str) -> TradeProposal:
    """Tạo WAIT proposal an toàn khi Gemini API hoàn toàn không phản hồi."""
    print(f"[GeminiClient] ⚠️  Sử dụng FALLBACK WAIT proposal do lỗi API: {error_msg}")
    return TradeProposal(
        thought_process=ThoughtProcess(
            market_context   = f"Gemini API không phản hồi sau {MAX_RETRIES} lần thử: {error_msg}",
            checklist_check  = "[SKIP] Không thể kiểm tra checklist do lỗi kết nối API.",
            setup_evaluation = "Không thể đánh giá setup.",
            risk_assessment  = "FALLBACK AN TOÀN: Hệ thống tự động chuyển về WAIT để bảo vệ vốn.",
        ),
        decision = "WAIT",
        symbol   = symbol,
        bias     = "neutral",
        setup    = "api_fallback",
        checklist_passed = [],
        checklist_failed = [f"API Error: {error_msg[:100]}"],
        entry       = None,
        stop_loss   = None,
        take_profit = [],
        risk_reward = None,
        confidence  = 0.0,
        invalidation = "Gemini API không khả dụng",
        reasons = ["API không phản hồi — chờ kết nối ổn định"],
        risks   = ["Lỗi kết nối API làm gián đoạn phân tích"],
    )


# ─────────────────────────────────────────────────────────────
# CLIENT
# ─────────────────────────────────────────────────────────────

class GeminiClient:
    """Wrapper cho Gemini API với Structured Output, Retry và Fallback."""

    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = GEMINI_MODEL):
        genai.configure(api_key=api_key)
        self.model_name = model
        self.api_key    = api_key
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=SYSTEM_PROMPT,
        )
        print(f"[GeminiClient] Khởi tạo model: {model}")

    def analyze(self, prompt: str, output_schema: dict[str, Any]) -> TradeProposal:
        """
        Gửi prompt tới Gemini và parse response về TradeProposal.
        Retry tối đa 3 lần với exponential backoff.
        Nếu tất cả lần thử thất bại → trả về WAIT proposal an toàn.
        """
        print(f"[GeminiClient] Đang gửi request tới Gemini ({self.model_name})...")

        generation_config = GenerationConfig(
            response_mime_type="application/json",
            response_schema=output_schema,
            temperature=0.1,       # thấp để giảm hallucination
            max_output_tokens=4096,
        )

        last_error = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self.model.generate_content(
                    contents=prompt,
                    generation_config=generation_config,
                )

                raw_text = response.text
                print(f"[GeminiClient] ✅ Nhận được response ({len(raw_text)} chars)")
                return self._parse_response(raw_text)

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    wait_sec = RETRY_DELAYS[attempt - 1]
                    print(
                        f"[GeminiClient] ⚠️  Lần thử {attempt}/{MAX_RETRIES} thất bại: {e}\n"
                        f"[GeminiClient]    → Chờ {wait_sec}s rồi thử lại..."
                    )
                    time.sleep(wait_sec)
                else:
                    print(f"[GeminiClient] ❌ Tất cả {MAX_RETRIES} lần thử đều thất bại.")

        # Tất cả retry đều thất bại → fallback an toàn
        # Trích xuất symbol từ prompt (fallback thô)
        symbol = "UNKNOWN"
        import re as _re
        m = _re.search(r"PHÂN TÍCH GIAO DỊCH.*?—\s*([A-Z]+)", prompt)
        if m:
            symbol = m.group(1)

        return _create_fallback_proposal(symbol, str(last_error))

    def _parse_response(self, raw_text: str) -> TradeProposal:
        """Parse JSON response thành TradeProposal."""
        # Trích xuất JSON nếu bị bọc trong markdown code block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
        json_str   = json_match.group(1).strip() if json_match else raw_text.strip()

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # Fallback: tìm JSON object đầu tiên
            json_match2 = re.search(r"\{[\s\S]*\}", json_str)
            if json_match2:
                data = json.loads(json_match2.group(0))
            else:
                raise ValueError(f"Không thể parse JSON từ response: {raw_text[:200]}")

        # Build TradeProposal từ dict
        tp_data  = data.get("thought_process", {})
        entry_d  = data.get("entry")
        tps      = data.get("take_profit", [])
        if isinstance(tps, (int, float)):
            tps = [tps]

        entry_zone = None
        if entry_d:
            raw_type = entry_d.get("type", "limit").lower()
            raw_dir  = entry_d.get("direction", "buy").lower()

            # Sanitize nếu AI trả về kiểu "buy_stop" vào trường type
            if "buy" in raw_type:
                raw_dir = "buy"
            elif "sell" in raw_type:
                raw_dir = "sell"

            if "stop" in raw_type:
                raw_type = "stop"
            elif "limit" in raw_type:
                raw_type = "limit"
            elif "market" in raw_type:
                raw_type = "market"
            else:
                raw_type = "limit"

            entry_zone = EntryZone(
                type      = raw_type,
                direction = raw_dir,
                zone_low  = entry_d.get("zone_low"),
                zone_high = entry_d.get("zone_high"),
                price     = entry_d.get("price"),
            )

        # Normalize confidence: Gemini đôi khi trả về 65 thay vì 0.65
        raw_conf = data.get("confidence", 0.0)
        if isinstance(raw_conf, (int, float)) and raw_conf > 1.0:
            raw_conf = raw_conf / 100.0

        alt_entry_d = data.get("alt_entry")
        alt_entry_zone = None
        if alt_entry_d:
            raw_alt_type = alt_entry_d.get("type", "limit").lower()
            if "stop" in raw_alt_type: raw_alt_type = "stop"
            elif "limit" in raw_alt_type: raw_alt_type = "limit"
            alt_entry_zone = EntryZone(
                type      = raw_alt_type,
                direction = alt_entry_d.get("direction", "buy").lower(),
                zone_low  = alt_entry_d.get("zone_low"),
                zone_high = alt_entry_d.get("zone_high"),
                price     = alt_entry_d.get("price"),
            )

        proposal = TradeProposal(
            thought_process=ThoughtProcess(
                market_context   = tp_data.get("market_context", ""),
                checklist_check  = tp_data.get("checklist_check", ""),
                setup_evaluation = tp_data.get("setup_evaluation", ""),
                risk_assessment  = tp_data.get("risk_assessment", ""),
            ),
            decision = data.get("decision", "WAIT"),
            symbol   = data.get("symbol", "UNKNOWN"),
            bias     = data.get("bias", "neutral"),
            setup    = data.get("setup", ""),

            checklist_passed = data.get("checklist_passed", []),
            checklist_failed = data.get("checklist_failed", []),

            entry = entry_zone,
            alt_entry = alt_entry_zone,

            stop_loss    = data.get("stop_loss"),
            take_profit  = tps,
            risk_reward  = data.get("risk_reward"),
            confidence   = raw_conf,
            invalidation = data.get("invalidation", ""),
            reasons      = data.get("reasons", []),
            risks        = data.get("risks", []),
        )

        print(
            f"[GeminiClient] 📊 Decision={proposal.decision} | "
            f"Confidence={proposal.confidence:.0%} | RR={proposal.risk_reward}"
        )
        print(f"[GeminiClient] ✅ Checklist passed: {proposal.checklist_passed}")
        if proposal.checklist_failed:
            print(f"[GeminiClient] ❌ Checklist failed: {proposal.checklist_failed}")

        return proposal