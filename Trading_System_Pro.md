# 🏛️ HỆ THỐNG GIAO DỊCH PRO: PRICE ACTION + EMA 20/50 + BOLLINGER BANDS (BẢN 10/10)

Hệ thống giao dịch thuận xu hướng dựa trên sự kết hợp giữa Cấu trúc thị trường, Động lượng (EMA), Biến động (Bollinger Bands) và Hành vi giá (Price Action).

---

## 1. CẤU HÌNH BIỂU ĐỒ (CHART SETUP)

*   **Khung thời gian (Timeframe):** Tối ưu nhất trên **H1** hoặc **H4** để lọc bỏ nhiễu và các tín hiệu phá vỡ giả (Fakeout).
*   **Cặp tài sản áp dụng:** Các cặp Forex chính (EUR/USD, GBP/USD, USD/JPY...) hoặc Vàng (XAU/USD).
*   **Chỉ báo kỹ thuật:**
    *   **EMA 50:** Bộ lọc xu hướng trung hạn.
    *   **EMA 20:** Động lực ngắn hạn & xác định Vùng giá trị (Value Area).
    *   **Bollinger Bands (20, 2):** Dải biến động (Upper Band, Lower Band, Middle Band/SMA 20).
    *   **ATR (Average True Range) kỳ 14:** Dùng để đo lường biến động và tính toán Stop Loss linh hoạt.

---

## 2. BỘ 3 NGUYÊN TẮC CỐT LÕI (NGUYÊN TẮC SỐNG CÒN)

> [!IMPORTANT]
> **Ưu tiên Cấu trúc Thị trường (Market Structure) lên trên Chỉ báo.**
> Cấu trúc giá làm chủ, chỉ báo chỉ đóng vai trò phụ trợ. Ngay cả khi EMA 50 dốc lên nhưng cấu trúc giá gãy (Break of Structure - BOS), tuyệt đối không vào lệnh BUY.

*   **Uptrend (Lệnh Buy):** Chỉ giao dịch khi cấu trúc giá liên tục tạo các Đỉnh cao hơn - Đáy cao hơn (Higher Highs - Higher Lows).
*   **Downtrend (Lệnh Sell):** Chỉ giao dịch khi cấu trúc giá tạo các Đỉnh thấp hơn - Đáy thấp hơn (Lower Highs - Lower Lows).

> [!CAUTION]
> **Bộ lọc Thị trường Đi ngang (No-Trade Zone)**
> Đứng ngoài tuyệt đối khi dải Bollinger Bands nằm ngang phẳng lì, EMA 20 và EMA 50 xoắn lấy nhau và giá cắt qua cắt lại các đường MA liên tục. Đây là vùng Whipsaw (nhiễu), rất dễ cháy tài khoản.

*   **Tối ưu Stop Loss linh hoạt:** Bỏ quy tắc đếm pips cố định. Sử dụng **ATR** hoặc **Swing Points** (Đỉnh/Đáy gần nhất) để tránh bị Market Maker quét thanh khoản (Stop-hunt).

---

## 3. CHECKLIST THỰC CHIẾN (QUY TRÌNH VÀO LỆNH)

### 📈 STRATEGY 1: Lệnh MUA (BUY / Long Setup - Pullback thuận xu hướng)

Chỉ vào lệnh khi thỏa mãn ĐỦ 5 bước sau:

- [ ] **1. Kiểm tra Cấu trúc:** Giá đang tạo cấu trúc Higher Highs (HH) & Higher Lows (HL).
- [ ] **2. Xác nhận Xu hướng:** Giá nằm trên EMA 50; EMA 20 nằm trên EMA 50 và dải BB đang mở rộng dốc lên.
- [ ] **3. Chờ Pullback (Điều chỉnh):** Kiên nhẫn chờ giá điều chỉnh giảm về Vùng giá trị (nằm giữa EMA 20, Middle Band và EMA 50).
- [ ] **4. Kích hoạt (Trigger):** Xuất hiện nến Price Action đẹp tại vùng giá trị (Bullish Pin Bar đuôi dưới dài hoặc Bullish Engulfing). Vào lệnh ngay khi nến đóng cửa.
- [ ] **5. Tính toán SL/TP:**
    *   **Stop Loss (SL):** Đặt dưới râu nến tín hiệu + 1x giá trị ATR hiện tại, *hoặc* đặt dưới Swing Low (đáy) gần nhất.
    *   **Take Profit 1 (TP1):** Chốt lời 1/2 vị thế tại dải trên của Bollinger Bands (Upper Band) hoặc Đỉnh cũ gần nhất.
    *   **Take Profit 2 (TP2):** Dời SL về hòa vốn (Breakeven). Dùng Trailing Stop bám theo dưới đường EMA 20 cho đến khi cấu trúc tăng bị gãy.

---

### 📉 STRATEGY 2: Lệnh BÁN (SELL / Short Setup - Pullback thuận xu hướng)

Chỉ vào lệnh khi thỏa mãn ĐỦ 5 bước sau:

- [ ] **1. Kiểm tra Cấu trúc:** Giá đang tạo cấu trúc Lower Highs (LH) & Lower Lows (LL).
- [ ] **2. Xác nhận Xu hướng:** Giá nằm dưới EMA 50; EMA 20 nằm dưới EMA 50 và dải BB đang mở rộng dốc xuống.
- [ ] **3. Chờ Pullback (Điều chỉnh):** Kiên nhẫn chờ giá điều chỉnh tăng về Vùng giá trị (nằm giữa EMA 20, Middle Band và EMA 50).
- [ ] **4. Kích hoạt (Trigger):** Xuất hiện nến Price Action đẹp tại vùng giá trị (Bearish Pin Bar đuôi trên dài hoặc Bearish Engulfing). Vào lệnh ngay khi nến đóng cửa.
- [ ] **5. Tính toán SL/TP:**
    *   **Stop Loss (SL):** Đặt trên râu nến tín hiệu + 1x giá trị ATR hiện tại, *hoặc* đặt trên Swing High (đỉnh) gần nhất.
    *   **Take Profit 1 (TP1):** Chốt lời 1/2 vị thế tại dải dưới của Bollinger Bands (Lower Band) hoặc Đáy cũ gần nhất.
    *   **Take Profit 2 (TP2):** Dời SL về hòa vốn (Breakeven). Dùng Trailing Stop bám theo trên đường EMA 20 cho đến khi cấu trúc giảm bị gãy.

---

### ⚡ STRATEGY 3: Đột phá dải co thắt (Bollinger Squeeze Breakout)

*   **Bối cảnh:** Hai dải Bollinger co thắt rất hẹp (Squeeze), EMA 20 và 50 đi ngang. Thị trường đang tích lũy nén.
*   **Điểm vào lệnh (ENTRY):** Vào lệnh khi có một cây nến xung lực thân rất lớn (Marubozu) phá vỡ bùng nổ và **đóng cửa hoàn toàn bên ngoài** dải BB, đồng thời kéo EMA dốc theo hướng phá vỡ.
*   **Stop Loss (SL):** Đặt tại đường trục giữa (Middle Band/SMA 20) hoặc phía bên kia của vùng tích lũy.
*   **Take Profit (TP):** Dùng Trailing Stop bám theo EMA 20 cho đến khi sóng bùng nổ kết thúc và có dấu hiệu đảo chiều.

---

## 4. QUẢN LÝ RỦI RO & TÂM LÝ (RISK MANAGEMENT)

> [!TIP]
> Hệ thống 10/10 chỉ hoạt động nếu Trader tuân thủ kỷ luật 10/10.

1.  **Quản lý Vốn:** Rủi ro tối đa **1% – 2%** tổng tài khoản cho mỗi vị thế. Không bao giờ phá lệ.
2.  **Tỷ lệ Risk:Reward (R:R):** Đảm bảo lợi nhuận kỳ vọng tối thiểu đạt mức **1:1.5** hoặc **1:2** trước khi quyết định bóp cò. Nếu SL quá xa khiến TP1 không đạt được tỷ lệ này, hãy bỏ qua setup đó.
3.  **Tin tức vĩ mô:** Đóng các lệnh lướt sóng hoặc ngưng vào lệnh mới trong khoảng 30 phút trước và sau khi công bố các tin tức kinh tế quan trọng (NFP, CPI, Lãi suất FED...).
4.  **Kiểm chứng (Backtest):** Luôn backtest tối thiểu 100 lệnh trên quá khứ trước khi giao dịch bằng tiền thật để rèn luyện sự nhạy bén và xác lập niềm tin vào hệ thống.

---

## 5. CÁCH ĐIỀU CHỈNH HỆ THỐNG PRO CHO GIAO DỊCH INTRADAY (TRONG NGÀY)

Thay vì dùng khung H4/D1 làm chủ đạo (vốn mất 1–3 ngày để cán TP), khi giao dịch lướt sóng bạn thu nhỏ khung biểu đồ xuống:

*   **Khung nhìn Xu hướng chính (Trend Filter):** Dùng **H1** hoặc **M30**. Kiểm tra giá nằm trên hay dưới EMA 50 khung H1/M30 để xác định phe Mua hay phe Bán đang làm chủ cuộc chơi.
*   **Khung tìm Điểm vào lệnh (Entry & Trigger):** Dùng **M5** hoặc **M15**.
    *   **Áp dụng Strategy 1 & 2 (Pullback):** Chờ giá điều chỉnh về Vùng giá trị (Value Area) giữa EMA 20 và EMA 50 trên M15, xuất hiện nến xác nhận (Pinbar/Engulfing) thì vào lệnh.
    *   **Hoặc Strategy 3 (BB Squeeze):** Chờ nến M15/M30 đóng cản bùng nổ khỏi dải nén Bollinger Bands.
*   **Biên độ Cắt lỗ (SL) & Chốt lời (TP) ngắn hơn:**
    *   **Với Bạc (XAGUSD):** Khung M15 có ATR chỉ khoảng 0.20 – 0.40 USD. Điểm SL chỉ cần lùi 0.30 – 0.40 USD (tương đương 30–40 pips), và mục tiêu TP1/TP2 nằm ở mức +0.50 đến +1.00 USD (+50 đến +100 pips). Mức này giá hoàn toàn có thể chạy chạm TP trong 2 – 6 tiếng.
    *   **Với Vàng (XAUUSD):** Khung M15 có ATR khoảng 5 – 12 USD. SL khoảng 8 – 10 USD (~80–100 pips), TP khoảng 15 – 25 USD (~150–250 pips).

---

## 6. ĐÁNH ĐỔI GIỮA SWING TRADING (H4) VÀ DAY TRADING (M15)

| Tiêu chí | Giao dịch Sóng (Swing H4/D1) | Giao dịch Trong ngày (Day Trading M15/M5) |
| :--- | :--- | :--- |
| **Thời gian giữ lệnh** | 1 – 4 ngày (Cần kiên nhẫn chờ) | Vài chục phút đến vài tiếng (Đóng trong ngày) |
| **Thời gian canh màn hình** | 10–15 phút/ngày (Rất nhàn) | Phải ngồi soi biểu đồ sát sao trong phiên |
| **Nhiễu giá & Bẫy quét SL** | Ít nhiễu, sóng chạy chuẩn mốc | Nhiều nhiễu, dễ dính quét râu nến (Stop-hunt) |
| **Tỷ lệ Lợi nhuận/Rủi ro** | R:R cao (2.0x – 4.0x) | R:R vừa phải (1.5x – 2.0x) |
| **Tác động tâm lý** | Thoải mái, không bị cuốn cảm xúc | Dễ bị cuốn vào giao dịch trả thù (Revenge trade) |

---

## 7. LỜI KHUYÊN THỰC CHIẾN DÀNH CHO GIAO DỊCH INTRADAY

*   **Khung giờ vàng lướt sóng (Trading Hours):**
    *   Không nên vào lệnh buổi sáng (Phiên Á - giá thường đi ngang sideway).
    *   **Tập trung 100% năng lượng vào Phiên Mỹ (19h30 – 22h30 giờ VN):** Đây là lúc thị trường Bạc/Vàng có thanh khoản khổng lồ và lực sóng biến động mạnh nhất, giúp lệnh chạm TP1/TP2 nhanh nhất.
*   **Khối lượng đi lệnh gọn nhẹ:**
    *   Khi đánh trong ngày trên tài khoản Cent (~39,000 USC), nên giữ khối lượng 0.05 – 0.10 lot Cent cho Bạc hoặc 0.01 – 0.02 lot Cent cho Vàng để khi dính SL ngắn, tài khoản chỉ lỗ nhẹ từ 0.5% – 1%.
*   **Kỷ luật ngắt đao (Hard Stop):**
    *   Đặt quy tắc: Nếu trong ngày đã đạt mục tiêu lợi nhuận (ví dụ +1,000 đến +1,500 USC) hoặc chạm tối đa 2 lệnh SL liên tiếp, đóng máy nghỉ trading để bảo toàn vốn và tâm lý.
