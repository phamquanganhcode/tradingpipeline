"""
test_market_structure_visual.py
────────────────────────────────────────────────────────────────
Script kiểm tra trực quan Module 2 (market_structure.py)

Cách dùng:
    python test_market_structure_visual.py

Kết quả:
    1. In ra terminal: Tóm tắt xu hướng + các Swing Points tìm được
    2. Xuất file CSV: data/test_ms_swings_XAUUSD_M15.csv
       → Mở TradingView, vẽ tay đỉnh/đáy rồi so sánh với CSV
    3. Vẽ biểu đồ matplotlib (nếu cài matplotlib)
       → Xem trực tiếp Swing Points trên chart giá

Tiêu chí PASS:
    - Swing Highs/Lows trong CSV khớp với đỉnh/đáy thật trên TradingView (±1-2 nến)
    - Uptrend được nhận diện đúng trong giai đoạn giá tăng rõ ràng
    - No-Trade Zone bật đúng khi giá đi ngang (vd: phiên Châu Á)
"""

import os
import sys
import csv
import logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.WARNING,   # Tắt log INFO để output gọn hơn
    format="%(levelname)-7s | %(message)s",
)

from modules.mt5_data_feed import MT5DataFeed
from modules.market_structure import MarketStructureAnalyzer
import MetaTrader5 as mt5

# ─────────────────────────────────────────────────────────────
# TU DONG PHAT HIEN TEN SYMBOL THUC TE TREN BROKER
# Xu ly broker dung suffix: XAUUSDm (Exness), XAUUSDc, XAUUSD.raw...
# ─────────────────────────────────────────────────────────────
def resolve_symbol(base: str) -> str:
    """
    Tim ten symbol thuc te tren MT5 tu ten chuan.
    VD: 'XAUUSD' -> 'XAUUSDm' (Exness) hoac 'XAUUSDc' hoac 'XAUUSD'
    """
    if mt5.symbol_info(base):
        return base
    for suffix in ["m", "c", ".r", ".raw", "pro", "ECN", "i", "s"]:
        candidate = base + suffix
        if mt5.symbol_info(candidate):
            return candidate
    # Tim kiem trong toan bo danh sach (fallback)
    all_syms = mt5.symbols_get()
    if all_syms:
        for s in all_syms:
            if s.name.upper().startswith(base.upper()):
                return s.name
    return base   # Tra ve ten goc neu khong tim thay

# ─────────────────────────────────────────────────────────────
# CAU HINH TEST (ten chuan - se duoc resolve sang ten thuc khi chay)
# ─────────────────────────────────────────────────────────────
TEST_CONFIGS_BASE = [
    # (symbol_chuan,  timeframe, bars,  fractal_lookback)
    ("XAUUSD",        "M15",     500,   5),
    ("XAUUSD",        "H4",      300,   3),   # H4 cho XAUUSD
    ("EURUSD",        "M15",     500,   5),
    ("GBPUSD",        "H4",      300,   3),   # H4 cho GBPUSD


]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _separator(char="─", width=70):
    print(char * width)


def run_visual_test(
    feed:     MT5DataFeed,
    symbol:   str,
    timeframe: str,
    bars:     int,
    lookback: int,
) -> bool:
    """
    Chạy test trực quan cho 1 symbol/timeframe.
    Returns True nếu có đủ dữ liệu để phân tích.
    """
    _separator()
    print(f"  TEST: {symbol} / {timeframe}  |  bars={bars}  |  lookback={lookback}")
    _separator()

    # Lấy dữ liệu từ MT5
    indicator = feed.get_indicators(symbol, timeframe, bars=bars, force=True)
    if not indicator or not indicator.is_valid:
        print(f"  [SKIP] Không lấy được dữ liệu từ MT5 cho {symbol}/{timeframe}")
        return False

    df = indicator.df
    print(f"  Dữ liệu: {len(df)} nến  |  Từ {df.index[0]}  đến  {df.index[-1]}")
    print(f"  Giá hiện tại: Close={indicator.close:.5f}  |  ATR={indicator.atr14:.5f}")
    print(f"  EMA20={indicator.ema20:.5f}  |  EMA50={indicator.ema50:.5f}")
    print()

    # Phân tích cấu trúc
    analyzer = MarketStructureAnalyzer(
        fractal_lookback=lookback,
        min_swing_count=2,
        atr_noise_filter=0.3,
        squeeze_mult=0.8,
        ema_gap_mult=0.2,
    )
    result = analyzer.analyze(indicator)

    # ── In kết quả tổng quan ──────────────────────────────────
    trend_arrow = {"uptrend": "↑ UPTREND", "downtrend": "↓ DOWNTREND", "sideways": "→ SIDEWAYS"}.get(result.trend, "?")
    print(f"  KẾT QUẢ XU HƯỚNG: {trend_arrow}")
    print(f"  {'is_hh':<12}: {result.is_hh}   (Đỉnh mới > Đỉnh cũ?)")
    print(f"  {'is_hl':<12}: {result.is_hl}   (Đáy mới > Đáy cũ?)")
    print(f"  {'is_lh':<12}: {result.is_lh}   (Đỉnh mới < Đỉnh cũ?)")
    print(f"  {'is_ll':<12}: {result.is_ll}   (Đáy mới < Đáy cũ?)")
    print(f"  {'bos_bullish':<12}: {result.bos_bullish}   (Giá phá đỉnh cũ?)")
    print(f"  {'bos_bearish':<12}: {result.bos_bearish}   (Giá phá đáy cũ?)")
    print(f"  {'choch':<12}: {result.choch}   (Cảnh báo đảo chiều?)")
    print(f"  {'no_trade_zone':<12}: {result.no_trade_zone}   ({result.reason})")
    print(f"  {'allow_buy':<12}: {result.allow_buy}")
    print(f"  {'allow_sell':<12}: {result.allow_sell}")
    print()

    # ── In danh sách Swing Points ─────────────────────────────
    print(f"  Tìm được {len(result.swing_highs)} Swing Highs + {len(result.swing_lows)} Swing Lows")
    print()

    # 5 Swing Highs gần nhất
    print(f"  {'#':<4} {'SWING HIGH':>12}  {'Thời gian':<20}  Ghi chú")
    print(f"  {'─'*55}")
    for i, sh in enumerate(result.swing_highs[-5:], start=1):
        age_bars = len(df) - sh.index - 1
        note = "<-- Gần nhất" if i == len(result.swing_highs[-5:]) else ""
        if i == len(result.swing_highs[-5:]) - 1:
            note = "<-- Thứ 2"
        ts_str = sh.timestamp.strftime("%Y-%m-%d %H:%M")
        print(f"  {i:<4} {sh.price:>12.5f}  {ts_str:<20}  {age_bars} nến trước  {note}")

    print()

    # 5 Swing Lows gần nhất
    print(f"  {'#':<4} {'SWING LOW':>12}  {'Thời gian':<20}  Ghi chú")
    print(f"  {'─'*55}")
    for i, sl in enumerate(result.swing_lows[-5:], start=1):
        age_bars = len(df) - sl.index - 1
        note = "<-- Gần nhất" if i == len(result.swing_lows[-5:]) else ""
        if i == len(result.swing_lows[-5:]) - 1:
            note = "<-- Thứ 2"
        ts_str = sl.timestamp.strftime("%Y-%m-%d %H:%M")
        print(f"  {i:<4} {sl.price:>12.5f}  {ts_str:<20}  {age_bars} nến trước  {note}")

    # ── Xuất CSV để so sánh với TradingView ──────────────────
    csv_path = os.path.join(
        OUTPUT_DIR,
        f"test_ms_swings_{symbol}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    )
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Type", "Price", "Timestamp", "Index", "Bars_Ago"])
        for sh in result.swing_highs:
            age = len(df) - sh.index - 1
            writer.writerow(["SwingHigh", f"{sh.price:.5f}", sh.timestamp.strftime("%Y-%m-%d %H:%M"), sh.index, age])
        for sl in result.swing_lows:
            age = len(df) - sl.index - 1
            writer.writerow(["SwingLow", f"{sl.price:.5f}", sl.timestamp.strftime("%Y-%m-%d %H:%M"), sl.index, age])

    print()
    print(f"  [CSV] Đã xuất: {csv_path}")
    print(f"  [HUONG DAN] Mo TradingView, chon {symbol} khung {timeframe}")
    print(f"             Tim cac moc gia trong CSV va kiem tra xem co khop voi dinh/day that khong.")
    print()

    # ── Vẽ biểu đồ matplotlib (nếu cài được) ────────────────
    _try_plot(df, result, symbol, timeframe, OUTPUT_DIR)

    return True


def _try_plot(df, result, symbol, timeframe, output_dir):
    """Vẽ biểu đồ giá + Swing Points. Bỏ qua nếu matplotlib chưa cài."""
    try:
        import matplotlib
        matplotlib.use("Agg")   # Non-interactive backend (lưu file thay vì popup)
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.patches import Patch

        # Chỉ lấy 150 nến cuối để biểu đồ không quá chật
        plot_df = df.tail(150).copy()
        plot_df.index = plot_df.index.tz_localize(None) if plot_df.index.tz else plot_df.index

        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(18, 10),
            gridspec_kw={"height_ratios": [3, 1]},
            sharex=True,
        )
        fig.patch.set_facecolor("#1a1a2e")
        for ax in [ax1, ax2]:
            ax.set_facecolor("#16213e")
            ax.tick_params(colors="white")
            ax.yaxis.label.set_color("white")
            ax.xaxis.label.set_color("white")
            ax.title.set_color("white")
            for spine in ax.spines.values():
                spine.set_edgecolor("#444")

        times = plot_df.index

        # Vẽ nến (dùng lines thay vì candlestick để đơn giản)
        for i, (ts, row) in enumerate(plot_df.iterrows()):
            color = "#26a69a" if row["Close"] >= row["Open"] else "#ef5350"
            ax1.plot([ts, ts], [row["Low"], row["High"]], color=color, linewidth=0.7, alpha=0.8)
            ax1.bar(ts, row["Close"] - row["Open"], bottom=row["Open"],
                    color=color, width=timedelta(minutes=12), alpha=0.9)

        # Vẽ EMA
        close_s = plot_df["Close"]
        ema20 = close_s.ewm(span=20, adjust=False).mean()
        ema50 = close_s.ewm(span=50, adjust=False).mean()
        ax1.plot(times, ema20, color="#ff9800", linewidth=1.2, label="EMA 20", alpha=0.9)
        ax1.plot(times, ema50, color="#2196f3", linewidth=1.2, label="EMA 50", alpha=0.9)

        # Vẽ Swing Highs (tam giác đỏ ↓ phía trên)
        plot_start_idx = len(df) - len(plot_df)
        for sh in result.swing_highs:
            if sh.index >= plot_start_idx:
                ts = sh.timestamp
                if ts.tzinfo:
                    ts = ts.replace(tzinfo=None)
                ax1.annotate("▼", xy=(ts, sh.price),
                             xytext=(ts, sh.price + (result.last_swing_high - result.last_swing_low) * 0.08),
                             color="#ff4444", fontsize=10, ha="center", va="bottom",
                             fontweight="bold")
                ax1.axhline(y=sh.price, color="#ff4444", linewidth=0.4, linestyle="--", alpha=0.4)

        # Vẽ Swing Lows (tam giác xanh ↑ phía dưới)
        for sl in result.swing_lows:
            if sl.index >= plot_start_idx:
                ts = sl.timestamp
                if ts.tzinfo:
                    ts = ts.replace(tzinfo=None)
                ax1.annotate("▲", xy=(ts, sl.price),
                             xytext=(ts, sl.price - (result.last_swing_high - result.last_swing_low) * 0.08),
                             color="#00e676", fontsize=10, ha="center", va="top",
                             fontweight="bold")
                ax1.axhline(y=sl.price, color="#00e676", linewidth=0.4, linestyle="--", alpha=0.4)

        # Vẽ đường Swing High/Low gần nhất (dày hơn)
        if result.last_swing_high:
            ax1.axhline(y=result.last_swing_high, color="#ff4444", linewidth=1.2,
                        linestyle="-", alpha=0.8, label=f"Last SH: {result.last_swing_high:.3f}")
        if result.last_swing_low:
            ax1.axhline(y=result.last_swing_low, color="#00e676", linewidth=1.2,
                        linestyle="-", alpha=0.8, label=f"Last SL: {result.last_swing_low:.3f}")

        # Tiêu đề và nhãn
        trend_label = f"↑ UPTREND" if result.trend == "uptrend" else ("↓ DOWNTREND" if result.trend == "downtrend" else "→ SIDEWAYS")
        flags = []
        if result.is_hh: flags.append("HH")
        if result.is_hl: flags.append("HL")
        if result.is_lh: flags.append("LH")
        if result.is_ll: flags.append("LL")
        if result.bos_bullish: flags.append("BOS↑")
        if result.bos_bearish: flags.append("BOS↓")
        if result.choch: flags.append("CHoCH!")
        if result.no_trade_zone: flags.append("[NTZ]")

        ax1.set_title(
            f"{symbol} / {timeframe}  |  {trend_label}  |  {' | '.join(flags)}\n"
            f"allow_buy={result.allow_buy}  allow_sell={result.allow_sell}",
            fontsize=12, color="white", pad=10,
        )
        ax1.legend(loc="upper left", facecolor="#1a1a2e", labelcolor="white", fontsize=8)
        ax1.set_ylabel("Price", color="white")

        # Subplot 2: Volume
        colors_vol = ["#26a69a" if r["Close"] >= r["Open"] else "#ef5350"
                      for _, r in plot_df.iterrows()]
        ax2.bar(times, plot_df["Volume"], color=colors_vol, alpha=0.7, width=timedelta(minutes=12))
        ax2.set_ylabel("Volume", color="white")
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
        plt.xticks(rotation=30, ha="right", color="white")

        plt.tight_layout()
        img_path = os.path.join(
            output_dir,
            f"test_ms_chart_{symbol}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M')}.png"
        )
        plt.savefig(img_path, dpi=120, bbox_inches="tight", facecolor="#1a1a2e")
        plt.close()
        print(f"  [CHART] Bieu do da luu: {img_path}")
        print(f"  [CHART] Mo anh nay va so sanh Swing Points (tam giac do/xanh) voi TradingView.")

    except ImportError:
        print("  [SKIP] Chua cai matplotlib. De ve bieu do, chay: pip install matplotlib")
    except Exception as e:
        print(f"  [SKIP] Loi ve bieu do: {e}")


def print_checklist():
    """Hướng dẫn cách đọc kết quả test."""
    print()
    _separator("═")
    print("  HUONG DAN KIEM TRA KET QUA")
    _separator("═")
    print("""
  Buoc 1: Mo TradingView, chon XAUUSD khung M15 (hoac symbol/TF ban muon test)
  Buoc 2: Dat lich su bien do ve khoang thoi gian trong CSV
  Buoc 3: Tu tay xac dinh cac Swing High/Low tren bieu do TradingView
  Buoc 4: So sanh voi danh sach trong CSV / anh bieu do vua xuat

  TIEU CHI PASS:
  [OK] Swing Highs trong CSV nam tai cac dinh ro rang tren bieu do (±1-2 nen)
  [OK] Swing Lows trong CSV nam tai cac day ro rang tren bieu do (±1-2 nen)
  [OK] Khi thi truong tang ro rang → trend = uptrend, is_hh=True, is_hl=True
  [OK] Khi thi truong giam ro rang → trend = downtrend, is_lh=True, is_ll=True
  [OK] Khi gia di ngang (phien Chau A)  → no_trade_zone = True

  TIEU CHI FAIL (Can dieu chinh tham so):
  [FAIL] Swing Points qua nhieu (nhieu qua) → Tang fractal_lookback len (vd: 5 → 7)
  [FAIL] Swing Points qua it (bo qua dinh day ro rang) → Giam fractal_lookback (vd: 5 → 3)
  [FAIL] No-trade zone bat nham khi gia dang co xu huong → Giam squeeze_mult (vd: 0.8 → 0.5)
  [FAIL] Uptrend khong duoc nhan dien → Giam atr_noise_filter (vd: 0.3 → 0.15)
    """)
    _separator("═")


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print()
    _separator("═")
    print("  MODULE 2 - MARKET STRUCTURE - VISUAL TEST")
    print(f"  Thoi gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _separator("═")
    print()

    # Ket noi MT5
    feed = MT5DataFeed()
    login    = int(os.getenv("MT5_LOGIN", 0))
    password = os.getenv("MT5_PASSWORD", "")
    server   = os.getenv("MT5_SERVER", "")

    if not feed.connect(login=login, password=password, server=server):
        print("[ERROR] Khong the ket noi MT5!")
        print("        Kiem tra: MT5 dang mo? MT5_LOGIN/PASSWORD/SERVER trong .env dung chua?")
        sys.exit(1)

    print("  [OK] Ket noi MT5 thanh cong")
    print()

    # Buoc quan trong: Resolve ten symbol thuc te cua broker
    # Exness dung suffix 'm': XAUUSDm, EURUSDm, GBPUSDm...
    print("  [AUTO] Dang xac dinh ten symbol thuc te tren broker...")
    TEST_CONFIGS = []
    seen = set()
    for base_sym, tf, bars, lookback in TEST_CONFIGS_BASE:
        real_sym = resolve_symbol(base_sym)
        key = (real_sym, tf)
        if key not in seen:
            seen.add(key)
            TEST_CONFIGS.append((real_sym, tf, bars, lookback))
            tag = f"-> {real_sym}" if real_sym != base_sym else "-> OK (khong co suffix)"
            print(f"    {base_sym:10s} {tag}  [{tf}]")
    print()

    passed = 0
    for sym, tf, bars, lookback in TEST_CONFIGS:
        ok = run_visual_test(feed, sym, tf, bars, lookback)
        if ok:
            passed += 1
        print()

    feed.disconnect()

    print_checklist()
    print(f"  Tong ket: {passed}/{len(TEST_CONFIGS)} symbol co du lieu de phan tich")
    print()
