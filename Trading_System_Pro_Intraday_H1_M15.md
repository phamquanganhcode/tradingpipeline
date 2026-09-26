# ⚡ HỆ THỐNG GIAO DỊCH PRO - PHIÊN BẢN INTRADAY (H1 & M15)

Phiên bản tối ưu hóa dành riêng cho Day Trading (Giao dịch trong ngày) dựa trên bộ nguyên tắc cốt lõi của Hệ Thống Pro, kết hợp Đa khung thời gian (H1-M15) để giải quyết triệt để độ trễ của các chỉ báo kỹ thuật.

---

## 1. CẤU HÌNH HỆ THỐNG TỐI ƯU (SETUP)

*   **Tài khoản bắt buộc:** ECN / Raw Spread (Phí chênh lệch mua bán phải cực thấp, tiệm cận 0 để không bị "ăn" mất lợi nhuận và tránh quét SL oan trên khung nhỏ).
*   **Tài sản:** Các cặp Forex chính (thanh khoản cao, spread mỏng như EUR/USD, GBP/USD) hoặc Vàng (XAU/USD).
*   **Chỉ báo Kỹ thuật (Áp dụng cho cả 2 khung H1 và M15):**
    *   **EMA 50:** Bộ lọc xu hướng chính.
    *   **EMA 20:** Động lực ngắn hạn / Vùng giá trị.
    *   **Bollinger Bands (20, 2):** Đo lường biến động và xác định mục tiêu chốt lời (TP1).
    *   **ATR (14):** Tính toán Stop Loss.

---

## 2. BỘ LỌC THỜI GIAN & TIN TỨC (SỐNG CÒN CHO M15)

Khác với Swing Trading, đánh Intraday trên M15 cực kỳ nhạy cảm với thanh khoản và tin tức.

> [!CAUTION]
> **Bộ lọc Thời gian (Phiên giao dịch):**
> *   **KHÔNG GIAO DỊCH** vào Phiên Á (Sáng - 13h00 VN) vì biên độ thấp, nhiễu nhiều.
> *   **CHỈ GIAO DỊCH** từ **14h00 - 17h00 (Phiên Âu)** và **19h30 - 22h30 (Phiên Mỹ)**. Đây là lúc cấu trúc giá rõ ràng nhất.

> [!WARNING]
> **Bộ lọc Tin tức (News Filter):**
> Bắt buộc kiểm tra *ForexFactory* mỗi sáng. Đóng mọi vị thế lướt sóng hoặc dời SL về hòa vốn **trước 30 phút** khi có tin ĐỎ (NFP, CPI, Lãi suất). Đợi 15-30 phút sau tin mới được phân tích lại.

---

## 3. QUY TRÌNH VÀO LỆNH BÀI BẢN (ENTRY CHECKLIST)

### BƯỚC 1: XÁC ĐỊNH XU HƯỚNG CHÍNH TRÊN KHUNG H1
Tuyệt đối không đi ngược với phe đang kiểm soát trên H1.
*   **Phe MUA kiểm soát:** Giá nằm trên EMA 50 của H1, cấu trúc tạo Đỉnh Cao hơn, Đáy Cao hơn (HH, HL).
*   **Phe BÁN kiểm soát:** Giá nằm dưới EMA 50 của H1, cấu trúc tạo Đỉnh Thấp hơn, Đáy Thấp hơn (LH, LL).
*   *Nếu H1 đang đi ngang (Sideway) -> Nghỉ giao dịch.*

### BƯỚC 2: TÌM ĐIỂM VÀO LỆNH (PULLBACK / CHoCH) TRÊN KHUNG M15
Khi H1 đã rõ xu hướng, ta thu nhỏ xuống M15 để tìm điểm vào sớm.

**Trường hợp 1: Pullback thuận xu hướng (Giá trên M15 đang đi cùng hướng H1)**
*   Chờ giá hồi về **Vùng giá trị** (nằm giữa EMA 20 và EMA 50 trên M15).
*   Chờ xuất hiện nến xác nhận (Pinbar/Engulfing) tại vùng giá trị.

**Trường hợp 2: Bắt đảo chiều sớm (Sử dụng CHoCH)**
*   Nếu H1 đang TĂNG, nhưng giá hồi quá sâu làm thủng EMA 50 trên M15 (tạo cấu trúc giảm tạm thời trên M15).
*   Chờ đợi sự phá vỡ cấu trúc (CHoCH): Đợi giá đánh bật lên, **phá vỡ cái Đỉnh (Lower High) cuối cùng** trên M15 để quay lại xu hướng tăng. Khi đó có thể vào lệnh BUY ngay nhịp test lại đỉnh cũ vừa phá.

### BƯỚC 3: XÁC NHẬN BẰNG NẾN ĐÓNG CỬA (CLOSE)
*   **Luật bất thành văn:** Chỉ vào lệnh khi cây nến M15 đã **ĐÓNG CỬA HOÀN TOÀN**. Không đoán trước, không vào lệnh khi nến đang chạy (chỉ là râu nến) để tránh bẫy thanh khoản (Fakeout).

### BƯỚC 4: TÍNH TOÁN STOP LOSS VÀ TAKE PROFIT

*   **Stop Loss (SL) an toàn:** 
    *   Với M15, đặt SL tại **Đỉnh/Đáy cũ gần nhất + 1.5 lần giá trị ATR hiện tại** (để có độ giãn buffer tránh râu nến).
    *   Tuyệt đối không đặt SL quá sát cản.
*   **Quản lý lệnh và Chốt lời (TP) Quyết liệt:**
    *   **Quy tắc Hòa Vốn:** Khi giá chạy được một đoạn bằng với rủi ro ban đầu (Đạt R:R = 1:1), bắt buộc **dời SL về điểm vào lệnh (Breakeven)**.
    *   **TP1 (Chốt lời 50% - 70%):** Tại dải Bollinger Bands đối diện trên M15 hoặc các vùng cản Đỉnh/Đáy cũ.
    *   **TP2 (Trailing Stop):** Thả nổi 30% còn lại, dời SL chặn lãi bám theo phía sau đường EMA 20 của M15 cho đến khi kết thúc ngày giao dịch. Đóng tất cả lệnh trước khi đi ngủ.

---

## 4. BÍ QUYẾT TÂM LÝ CHO INTRADAY TRADER (KỶ LUẬT NGẮT ĐAO)

1.  **Risk Management:** Rủi ro tối đa 1% - 2% tài khoản cho mỗi lệnh. 
2.  **Kỷ luật "Ngắt Đao" (Hard Stop) Sống Còn:** 
    *   **Giới hạn NGÀY:** Thua âm 3% -> NGHỈ. Thắng lãi 5% -> NGHỈ (Tắt máy ngay lập tức).
    *   **Giới hạn TUẦN:** Thua âm 6% -> NGHỈ. Thắng lãi 10% -> NGHỈ (Bảo vệ lợi nhuận, sang tuần giao dịch tiếp).
    *   **Giới hạn THÁNG:** Thua âm 10% -> NGHỈ (Ngừng Trade tiền thật, quay về tài khoản Demo rèn luyện lại). Thắng lãi 20% -> NGHỈ (Đạt lợi nhuận xuất sắc, tự thưởng cho bản thân).
    
    *Lưu ý:* Việc tuân thủ tuyệt đối các giới hạn này là cách duy nhất để tránh hội chứng trả thù thị trường và bảo vệ thành quả của bạn khỏi lòng tham.
