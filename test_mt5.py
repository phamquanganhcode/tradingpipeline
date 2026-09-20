"""
test_mt5.py — Công cụ kiểm tra kết nối MetaTrader 5 & thử nghiệm đặt lệnh
──────────────────────────────────────────────────────────────────────────
Chức năng:
  1. Kiểm tra kết nối MT5 (Login, Server, Quyền Algo Trading, Số dư tài khoản).
  2. Kiểm tra thông số Symbol (Bid, Ask, Spread, Min Lot, Lot Step).
  3. Thử đặt Lệnh Chờ (Pending Buy Limit) an toàn (giá xa thị trường, không sợ khớp ngay).
  4. Thử đặt Lệnh Trực Tiếp (Market Order) với volume tối thiểu (có xác nhận).
  5. Hủy hoặc đóng các lệnh test vừa tạo (Magic: 999999).
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

# Đảm bảo UTF-8 cho console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load biến môi trường
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path)

try:
    import MetaTrader5 as mt5
except ImportError:
    print("\n[LỖI] Chưa cài đặt thư viện MetaTrader5!")
    print("Vui lòng chạy: pip install MetaTrader5\n")
    sys.exit(1)

from config import SYMBOL as CONFIG_SYMBOL

TEST_MAGIC = 999999
TEST_COMMENT = "Test MT5 Script"


def get_credentials():
    login = os.getenv("MT5_LOGIN", "")
    password = os.getenv("MT5_PASSWORD", "")
    server = os.getenv("MT5_SERVER", "")
    try:
        login = int(login)
    except ValueError:
        login = 0
    return login, password, server


def connect_mt5(verbose=True):
    login, password, server = get_credentials()

    if not login or not password or not server:
        if verbose:
            print("\n[CẢNH BÁO] Chưa cấu hình đầy đủ MT5 trong file .env!")
            print(f"  - MT5_LOGIN    : {'Đã có' if login else 'TRỐNG'}")
            print(f"  - MT5_PASSWORD : {'Đã có' if password else 'TRỐNG'}")
            print(f"  - MT5_SERVER   : {'Đã có' if server else 'TRỐNG'}")
            print("\n  -> Đang thử kết nối tới terminal MT5 đang mở sẵn trên máy...")

    if not mt5.initialize():
        err = mt5.last_error()
        print(f"\n[LỖI] Không thể khởi tạo MT5 Terminal: {err}")
        print("💡 Gợi ý: Hãy mở phần mềm MetaTrader 5 trên máy tính của bạn trước khi chạy script.")
        return False

    if login and password and server:
        authorized = mt5.login(login=login, password=password, server=server)
        if not authorized:
            err = mt5.last_error()
            print(f"\n[LỖI] Đăng nhập MT5 thất bại. Lỗi: {err}")
            print("💡 Kiểm tra lại MT5_LOGIN, MT5_PASSWORD, MT5_SERVER trong file .env")
            return False

    acc_info = mt5.account_info()
    term_info = mt5.terminal_info()

    if acc_info is None:
        print("\n[LỖI] Không đọc được thông tin tài khoản MT5.")
        return False

    if verbose:
        print("\n" + "=" * 60)
        print("          KẾT NỐI METATRADER 5 THÀNH CÔNG! ✅")
        print("=" * 60)
        print(f"  👤 Chủ tài khoản  : {acc_info.name}")
        print(f"  🔢 Số tài khoản   : {acc_info.login}")
        print(f"  🏢 Server         : {acc_info.server} ({acc_info.company})")
        print(f"  💵 Loại tiền tệ   : {acc_info.currency}")
        print(f"  💰 Số dư (Balance): {acc_info.balance:,.2f} {acc_info.currency}")
        print(f"  📈 Vốn (Equity)   : {acc_info.equity:,.2f} {acc_info.currency}")
        print(f"  🛡️  Đòn bẩy       : 1:{acc_info.leverage}")
        demo_str = "Tài khoản DEMO" if acc_info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO else "Tài khoản REAL (THẬT)"
        print(f"  🏷️  Chế độ        : {demo_str}")

        # Kiểm tra quyền giao dịch tự động
        algo_allowed = term_info.trade_allowed if term_info else False
        algo_status = "BẬT (Cho phép giao dịch tự động) ✅" if algo_allowed else "TẮT ❌ (Cần bấm nút 'Algo Trading' trên MT5)"
        print(f"  🤖 Algo Trading   : {algo_status}")
        print("=" * 60)

        if not algo_allowed:
            print("\n⚠️  LƯU Ý QUAN TRỌNG: Nút 'Algo Trading' trên thanh công cụ MT5 đang bị TẮT.")
            print("   Để bot có thể đặt lệnh tự động, hãy mở MT5 và bấm nút 'Algo Trading' thành màu XANH.\n")

    return True


def check_symbol_info(symbol: str):
    if not mt5.symbol_select(symbol, True):
        print(f"\n[LỖI] Không tìm thấy hoặc không thể kích hoạt mã '{symbol}' trong Market Watch.")
        print("💡 Hãy kiểm tra lại mã chính xác trên sàn của bạn (VD: BTCUSDm, XAUUSDm, BTCUSD, EURUSD,...)")
        return None

    info = mt5.symbol_info(symbol)
    tick = mt5.symbol_info_tick(symbol)

    if info is None or tick is None:
        print(f"\n[LỖI] Không thể đọc giá của mã '{symbol}'.")
        return None

    spread = (tick.ask - tick.bid)
    digits = info.digits

    print(f"\n📊 THÔNG TIN MÃ GIAO DỊCH: [{symbol}]")
    print(f"  - Giá Bid         : {tick.bid:.{digits}f}")
    print(f"  - Giá Ask         : {tick.ask:.{digits}f}")
    print(f"  - Chênh lệch giá  : {spread:.{digits}f} (Spread: {info.spread} points)")
    print(f"  - Volume tối thiểu: {info.volume_min} lot")
    print(f"  - Volume tối đa   : {info.volume_max} lot")
    print(f"  - Bước nhảy volume: {info.volume_step} lot")
    return info, tick


def get_safe_filling(symbol_info):
    """Chọn filling mode phù hợp với sàn để tránh lỗi unsupported filling mode."""
    mode = symbol_info.filling_mode
    if mode & 2:
        return mt5.ORDER_FILLING_IOC
    elif mode & 1:
        return mt5.ORDER_FILLING_FOK
    return mt5.ORDER_FILLING_RETURN


def test_pending_order(symbol: str):
    print(f"\n--- ⏳ THỬ ĐẶT LỆNH CHỜ (PENDING BUY LIMIT) AN TOÀN TRÊN [{symbol}] ---")
    print("Mục đích: Kiểm tra khả năng gửi lệnh lên sàn mà KHÔNG sợ khớp ngay.")

    res = check_symbol_info(symbol)
    if not res:
        return
    info, tick = res

    # Đặt giá BUY LIMIT thấp hơn giá thị trường 3% (để không bao giờ khớp ngay)
    digits = info.digits
    current_ask = tick.ask
    limit_price = round(current_ask * 0.97, digits)
    sl_price = round(limit_price * 0.98, digits)
    tp_price = round(limit_price * 1.04, digits)
    lot_size = info.volume_min  # Dùng volume nhỏ nhất

    print(f"\nThông số lệnh test:")
    print(f"  - Loại lệnh : BUY LIMIT (Chờ mua thấp hơn giá hiện tại 3%)")
    print(f"  - Khối lượng: {lot_size} lot")
    print(f"  - Giá đặt   : {limit_price}")
    print(f"  - Stop Loss : {sl_price}")
    print(f"  - TakeProfit: {tp_price}")

    filling = get_safe_filling(info)

    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": float(lot_size),
        "type": mt5.ORDER_TYPE_BUY_LIMIT,
        "price": float(limit_price),
        "sl": float(sl_price),
        "tp": float(tp_price),
        "deviation": 20,
        "magic": TEST_MAGIC,
        "comment": TEST_COMMENT,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }

    print("\n⏳ Đang gửi request tới MetaTrader 5...")
    result = mt5.order_send(request)

    if result is None:
        print(f"❌ order_send trả về None. Lỗi MT5: {mt5.last_error()}")
        return

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ Đặt lệnh thất bại! Mã lỗi: {result.retcode} — {result.comment}")
        if result.retcode == 10027:
            print("💡 Lỗi 10027: Algo Trading bị tắt. Hãy bật nút 'Algo Trading' trên MT5.")
        elif result.retcode == 10014:
            print("💡 Lỗi 10014: Khối lượng (lot size) không hợp lệ.")
        elif result.retcode == 10015:
            print("💡 Lỗi 10015: Giá đặt lệnh không hợp lệ.")
        return

    order_ticket = result.order
    print(f"\n🎉 THÀNH CÔNG! Lệnh chờ đã xuất hiện trên MT5.")
    print(f"  - Ticket ID : #{order_ticket}")
    print(f"  - Trạng thái: RETCODE_DONE ({result.comment})")
    print("👉 Bạn hãy mở phần mềm MT5 và nhìn vào tab 'Trade' / 'Orders' để thấy lệnh này.")

    # Hỏi người dùng có muốn hủy lệnh test ngay không
    ans = input("\nBạn có muốn HỦY ngay lệnh test này không? (y/n) [mặc định y]: ").strip().lower()
    if ans in ("", "y", "yes"):
        cancel_request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": order_ticket,
        }
        del_res = mt5.order_send(cancel_request)
        if del_res and del_res.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"✅ Đã hủy lệnh test #{order_ticket} thành công!")
        else:
            print(f"⚠️ Chưa hủy được lệnh #{order_ticket}. Bạn có thể xóa thủ công trên MT5.")
    else:
        print(f"ℹ️ Lệnh test #{order_ticket} vẫn đang được giữ trên MT5.")


def test_market_order(symbol: str):
    print(f"\n--- ⚡ THỬ ĐẶT LỆNH TRỰC TIẾP (MARKET BUY) TRÊN [{symbol}] ---")
    print("⚠️  CẢNH BÁO: Lệnh này sẽ KHỚP NGAY LẬP TỨC trên tài khoản của bạn!")
    acc_info = mt5.account_info()
    if acc_info and acc_info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        print("🚨 CHÚ Ý: ĐÂY LÀ TÀI KHOẢN THẬT (REAL)!")
    
    confirm = input("Bạn có CHẮC CHẮN muốn đặt 1 lệnh Market Buy với volume tối thiểu không? (gõ 'ok' để tiếp tục): ").strip().lower()
    if confirm != "ok":
        print("❌ Đã hủy thao tác.")
        return

    res = check_symbol_info(symbol)
    if not res:
        return
    info, tick = res

    digits = info.digits
    lot_size = info.volume_min
    price = tick.ask
    # SL cách 1000 points, TP cách 2000 points
    point = info.point
    sl = round(price - 2000 * point, digits)
    tp = round(price + 4000 * point, digits)

    filling = get_safe_filling(info)

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": float(lot_size),
        "type": mt5.ORDER_TYPE_BUY,
        "price": float(price),
        "sl": float(sl),
        "tp": float(tp),
        "deviation": 50,
        "magic": TEST_MAGIC,
        "comment": TEST_COMMENT,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }

    print("\n⏳ Đang bắn lệnh Market...")
    result = mt5.order_send(request)

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        err_msg = result.comment if result else mt5.last_error()
        print(f"❌ Đặt lệnh Market thất bại! Chi tiết: {err_msg}")
        return

    deal_order = result.order
    print(f"\n🎉 THÀNH CÔNG! Lệnh Market Buy đã được khớp.")
    print(f"  - Order Ticket: #{deal_order}")
    print(f"  - Giá khớp    : {result.price}")
    print(f"  - Volume      : {result.volume} lot")

    # Tùy chọn đóng ngay
    ans = input("\nBạn có muốn ĐÓNG (CLOSE) ngay lệnh này không? (y/n) [mặc định y]: ").strip().lower()
    if ans in ("", "y", "yes"):
        time.sleep(1)
        # Tìm position tương ứng
        positions = mt5.positions_get(symbol=symbol)
        target_pos = None
        if positions:
            for pos in positions:
                if pos.magic == TEST_MAGIC or pos.ticket == deal_order:
                    target_pos = pos
                    break
        if target_pos:
            tick_now = mt5.symbol_info_tick(symbol)
            close_req = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": float(target_pos.volume),
                "type": mt5.ORDER_TYPE_SELL,
                "position": target_pos.ticket,
                "price": float(tick_now.bid),
                "deviation": 50,
                "magic": TEST_MAGIC,
                "comment": "Close Test",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling,
            }
            close_res = mt5.order_send(close_req)
            if close_res and close_res.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ Đã đóng vị thế test #{target_pos.ticket} thành công!")
            else:
                print(f"⚠️ Chưa đóng được vị thế tự động. Vui lòng đóng bằng tay trên MT5.")
        else:
            print("ℹ️ Không tìm thấy position test để đóng tự động.")


def cleanup_all_test_orders():
    print("\n--- 🧹 DỌN DẸP TẤT CẢ LỆNH TEST (MAGIC 999999) ---")
    # Hủy pending orders
    orders = mt5.orders_get()
    canceled_count = 0
    if orders:
        for o in orders:
            if o.magic == TEST_MAGIC:
                req = {"action": mt5.TRADE_ACTION_REMOVE, "order": o.ticket}
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    canceled_count += 1
                    print(f"  - Đã hủy lệnh chờ #{o.ticket} ({o.symbol})")
    print(f"Đã hủy {canceled_count} lệnh chờ test.")

    # Đóng positions test
    positions = mt5.positions_get()
    closed_count = 0
    if positions:
        for p in positions:
            if p.magic == TEST_MAGIC:
                symbol_info = mt5.symbol_info(p.symbol)
                tick = mt5.symbol_info_tick(p.symbol)
                order_type = mt5.ORDER_TYPE_SELL if p.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
                price = tick.bid if order_type == mt5.ORDER_TYPE_SELL else tick.ask
                req = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": p.symbol,
                    "volume": float(p.volume),
                    "type": order_type,
                    "position": p.ticket,
                    "price": float(price),
                    "deviation": 50,
                    "magic": TEST_MAGIC,
                    "comment": "Cleanup",
                    "type_filling": get_safe_filling(symbol_info),
                }
                res = mt5.order_send(req)
                if res and res.retcode == mt5.TRADE_RETCODE_DONE:
                    closed_count += 1
                    print(f"  - Đã đóng vị thế #{p.ticket} ({p.symbol})")
    print(f"Đã đóng {closed_count} vị thế test.")


def main():
    print("""
+-------------------------------------------------------------+
|        KIỂM TRA KẾT NỐI VÀ TẠO LỆNH METATRADER 5           |
|        Hệ thống AI Trading Pipeline                         |
+-------------------------------------------------------------+
""")
    if not connect_mt5(verbose=True):
        input("\nNhấn Enter để kết thúc...")
        return

    symbol = CONFIG_SYMBOL
    while True:
        print(f"\n[Mã giao dịch hiện tại: {symbol}]")
        print("1. Kiểm tra lại thông tin kết nối MT5")
        print("2. Xem giá & thông số của mã giao dịch hiện tại")
        print("3. Thử đặt LỆNH CHỜ (Pending Buy Limit) - [Khuyên dùng, an toàn]")
        print("4. Thử đặt LỆNH TRỰC TIẾP (Market Buy) - [Khớp ngay, có hỏi xác nhận]")
        print("5. Dọn dẹp / Hủy tất cả các lệnh test vừa tạo")
        print("6. Đổi mã giao dịch khác (VD: BTCUSDm, XAUUSDm, EURUSD,...)")
        print("0. Thoát")

        choice = input("\n👉 Hãy chọn chức năng (0-6): ").strip()

        if choice == "1":
            connect_mt5(verbose=True)
        elif choice == "2":
            check_symbol_info(symbol)
        elif choice == "3":
            test_pending_order(symbol)
        elif choice == "4":
            test_market_order(symbol)
        elif choice == "5":
            cleanup_all_test_orders()
        elif choice == "6":
            new_sym = input(f"Nhập mã mới (hiện tại: {symbol}): ").strip()
            if new_sym:
                symbol = new_sym
                check_symbol_info(symbol)
        elif choice == "0":
            print("\nĐang ngắt kết nối MT5...")
            mt5.shutdown()
            print("Đã đóng kết nối. Hẹn gặp lại!")
            break
        else:
            print("Lựa chọn không hợp lệ, vui lòng chọn từ 0 đến 6.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã hủy bởi người dùng.")
        mt5.shutdown()
    except Exception as e:
        print(f"\n[LỖI NGOẠI LỆ]: {e}")
        import traceback
        traceback.print_exc()
        mt5.shutdown()
        input("\nNhấn Enter để thoát...")
