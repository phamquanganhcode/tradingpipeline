"""
CỖ MÁY THỜI GIAN (BACKTESTER)
Mô phỏng giao dịch thực tế trên dữ liệu quá khứ.
Vốn: 10,000 USD | Rủi ro: 1%/lệnh.
"""

import os
import sys
import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
sys.path.insert(0, '.')
from dotenv import load_dotenv
from modules.mt5_data_feed import MT5DataFeed, IndicatorResult
from modules.market_structure import get_analyzer
from modules.candle_pattern import get_candle_analyzer
from modules.strategy_engine import get_strategy_engine

def calculate_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Tính toán thủ công bằng hàm pandas cơ bản (không dùng pandas_ta)"""
    if len(df) < 50: return df
    
    # 1. EMA
    df['EMA_20'] = df['Close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    # 2. Bollinger Bands (20, 2)
    df['BB_middle'] = df['Close'].rolling(window=20).mean()
    std = df['Close'].rolling(window=20).std()
    df['BB_upper'] = df['BB_middle'] + 2 * std
    df['BB_lower'] = df['BB_middle'] - 2 * std
    df['BB_width'] = (df['BB_upper'] - df['BB_lower']) / df['BB_middle']
    
    # 3. ATR (14)
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['ATR_14'] = true_range.ewm(alpha=1/14, adjust=False).mean() # RMA/SMMA method like TradingView
    
    # 4. RSI (14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    df['RSI_14'] = 100 - (100 / (1 + rs))
    
    return df

def run_backtest(symbol: str, bars_count: int = 5000, start_date: str = None, end_date: str = None):
    import os
    load_dotenv()
    if not mt5.initialize(
        login=int(os.getenv("MT5_LOGIN", 0)), 
        server=os.getenv("MT5_SERVER", ""), 
        password=os.getenv("MT5_PASSWORD", "")
    ):
        print("Lỗi kết nối MT5!")
        return

    print(f"🔄 Đang tải dữ liệu lịch sử {symbol}...")
    
    # 1. TẢI DỮ LIỆU
    if start_date and end_date:
        d_start = datetime.strptime(start_date, "%Y-%m-%d")
        d_end = datetime.strptime(end_date, "%Y-%m-%d")
        print(f"Khoảng thời gian: {start_date} đến {end_date}")
        m15_rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, d_start - timedelta(days=10), d_end)
        h1_rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, d_start - timedelta(days=30), d_end)
        h4_rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H4, d_start - timedelta(days=60), d_end)
    else:
        m15_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars_count)
        h1_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, bars_count // 4 + 100)
        h4_rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H4, 0, bars_count // 16 + 100)
    
    if m15_rates is None or h1_rates is None or h4_rates is None:
        print("Không tải được dữ liệu.")
        return

    df_m15 = pd.DataFrame(m15_rates)
    df_m15.rename(columns={'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'tick_volume':'Volume'}, inplace=True)
    df_m15 = calculate_all_indicators(df_m15)
    df_h1 = pd.DataFrame(h1_rates)
    df_h1.rename(columns={'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'tick_volume':'Volume'}, inplace=True)
    df_h1 = calculate_all_indicators(df_h1)
    df_h4 = pd.DataFrame(h4_rates)
    df_h4.rename(columns={'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'tick_volume':'Volume'}, inplace=True)
    df_h4 = calculate_all_indicators(df_h4)

    df_m15['time'] = pd.to_datetime(df_m15['time'], unit='s')
    df_h1['time'] = pd.to_datetime(df_h1['time'], unit='s')
    df_h4['time'] = pd.to_datetime(df_h4['time'], unit='s')
    
    df_m15.set_index('time', inplace=True)
    df_h1.set_index('time', inplace=True)
    df_h4.set_index('time', inplace=True)
    
    # Modules
    ms_analyzer = get_analyzer()
    candle_analyzer = get_candle_analyzer()
    engine = get_strategy_engine()
    
    # Variables
    BALANCE = 10000.0
    RISK_PCT = 0.01
    RISK_USD = BALANCE * RISK_PCT
    
    trades_history = []
    active_trade = None

    print(f"🚀 BẮT ĐẦU BACKTEST (Vốn: ${BALANCE:,.2f})")
    
    # 2. VÒNG LẶP THỜI GIAN
    start_idx = 200 # Bỏ qua 200 nến đầu để warmup indicator
    for i in range(start_idx, len(df_m15) - 1): # -1 để chừa nến tương lai cho việc khớp lệnh
        current_time = df_m15.index[i]
        
        # Bỏ qua nếu thời gian nhỏ hơn start_date
        if start_date and end_date:
            if current_time < d_start:
                continue
        
        # --- QUẢN LÝ LỆNH ĐANG CHẠY (Giả lập Module 6) ---
        if active_trade is not None:
            # Lấy giá của nến M15 ngay sau nến tín hiệu (cây nến đang chạy)
            forming_candle = df_m15.iloc[i]
            high = forming_candle['High']
            low = forming_candle['Low']
            
            closed_reason = ""
            pnl_r = 0.0
            
            if active_trade['type'] == 'buy':
                if low <= active_trade['sl']:
                    if active_trade['status'] == 'breakeven':
                        pnl_r = 0.0
                        closed_reason = "Hòa vốn (Breakeven)"
                    else:
                        pnl_r = -1.0
                        closed_reason = "Chạm Cắt lỗ (SL)"
                elif high >= active_trade['tp2'] and active_trade['status'] == 'breakeven':
                    pnl_r = 2.1 # 70% còn lại * 3R
                    closed_reason = "Chạm TP2 (Chốt hết)"
                elif high >= active_trade['tp1'] and active_trade['status'] == 'active':
                    # Partial close
                    active_trade['status'] = 'breakeven'
                    active_trade['sl'] = active_trade['entry']
                    BALANCE += RISK_USD * 0.6 # Đút túi 30% khối lượng * 2.0R = 0.6R
                    print(f"  [{current_time}] 🟢 Chốt lời 30% tại TP1 (2R), dời SL hòa vốn. Lãi: +${RISK_USD*0.6:.2f}")
                    continue
            else: # SELL
                if high >= active_trade['sl']:
                    if active_trade['status'] == 'breakeven':
                        pnl_r = 0.0
                        closed_reason = "Hòa vốn (Breakeven)"
                    else:
                        pnl_r = -1.0
                        closed_reason = "Chạm Cắt lỗ (SL)"
                elif low <= active_trade['tp2'] and active_trade['status'] == 'breakeven':
                    pnl_r = 2.1
                    closed_reason = "Chạm TP2 (Chốt hết)"
                elif low <= active_trade['tp1'] and active_trade['status'] == 'active':
                    active_trade['status'] = 'breakeven'
                    active_trade['sl'] = active_trade['entry']
                    BALANCE += RISK_USD * 0.6
                    print(f"  [{current_time}] 🟢 Chốt lời 30% tại TP1 (2R), dời SL hòa vốn. Lãi: +${RISK_USD*0.6:.2f}")
                    continue
                    
            if closed_reason != "":
                win_amount = RISK_USD * pnl_r
                BALANCE += win_amount
                trades_history.append({
                    'Time': current_time,
                    'Type': active_trade['type'].upper(),
                    'Reason': closed_reason,
                    'PnL': win_amount,
                    'Balance': BALANCE
                })
                icon = "❌" if pnl_r < 0 else "✅" if pnl_r > 0 else "🛡️"
                print(f"  [{current_time}] {icon} Lệnh đóng: {closed_reason} | PnL: ${win_amount:.2f} | Balance: ${BALANCE:,.2f}")
                active_trade = None
                
        # Nếu đang có lệnh thì không mở thêm (Max 1 trade at a time)
        if active_trade is not None:
            continue
            
        # --- TÌM KIẾM LỆNH MỚI (Giả lập Module 1,2,3,4) ---
        # Cắt dữ liệu quá khứ đến đúng thời điểm current_time (Giới hạn 300 nến để phân tích cực nhanh)
        sub_m15 = df_m15.iloc[max(0, i-300):i+1] # Lấy 300 nến M15 gần nhất
        sub_h1 = df_h1[df_h1.index <= current_time].tail(300)
        sub_h4 = df_h4[df_h4.index <= current_time].tail(300)
        
        if len(sub_h1) < 50 or len(sub_h4) < 50:
            continue
            
        # Tạo vỏ bọc IndicatorResult
        def make_ind(df, tf):
            last = df.iloc[-1]
            return IndicatorResult(
                symbol=symbol, timeframe=tf, timestamp=df.index[-1],
                open_price=last['Open'], high=last['High'], low=last['Low'], close=last['Close'], volume=last['Volume'],
                ema20=last['EMA_20'], ema50=last['EMA_50'], bb_upper=last['BB_upper'], bb_middle=last['BB_middle'], bb_lower=last['BB_lower'],
                bb_width=last['BB_width'], bb_squeeze=False, atr14=last['ATR_14'], rsi14=last.get('RSI_14', 50), df=df
            )
            
        ind_m15 = make_ind(sub_m15, "M15")
        ind_h1 = make_ind(sub_h1, "H1")
        ind_h4 = make_ind(sub_h4, "H4")
        
        # Phân tích
        m15_ms, h1_ms, h4_ms = ms_analyzer.analyze_3tf(ind_m15, ind_h1, ind_h4)
        m15_candle = candle_analyzer.analyze(ind_m15)
        
        proposal = engine.generate_proposal(
            symbol=symbol, 
            m15_ind=ind_m15, h1_ind=ind_h1, h4_ind=ind_h4,
            m15_ms=m15_ms, h1_ms=h1_ms, h4_ms=h4_ms,
            m15_candle=m15_candle
        )
        
        if proposal:
            print(f"\n[{current_time}] 🔫 VÀO LỆNH {proposal.action.upper()} | Entry: {proposal.entry_price} | SL: {proposal.stop_loss:.3f} | TP1: {proposal.tp1:.3f}")
            print(f"Lý do: {proposal.reason}")
            active_trade = {
                'type': proposal.action,
                'entry': proposal.entry_price,
                'sl': proposal.stop_loss,
                'tp1': proposal.tp1,
                'tp2': proposal.tp2,
                'status': 'active'
            }

    # Tổng kết
    print("\n" + "="*50)
    print(" KẾT QUẢ BACKTEST")
    print("="*50)
    print(f"Tổng số lệnh: {len(trades_history)}")
    if len(trades_history) > 0:
        wins = sum(1 for t in trades_history if t['PnL'] > 0)
        losses = sum(1 for t in trades_history if t['PnL'] < 0)
        bes = sum(1 for t in trades_history if t['PnL'] == 0)
        print(f"Thắng (TP2/Partial): {wins} lệnh")
        print(f"Thua (Cắn SL): {losses} lệnh")
        print(f"Hòa vốn (Breakeven): {bes} lệnh")
        winrate = (wins / (wins + losses)) * 100 if (wins+losses)>0 else 0
        print(f"Winrate (Ko tính BE): {winrate:.1f}%")
        print(f"Lợi nhuận ròng: ${BALANCE - 10000:,.2f}")
        print(f"Số dư cuối: ${BALANCE:,.2f}")
        
        # XUẤT FILE EXCEL/CSV
        import os
        if not os.path.exists('data'):
            os.makedirs('data')
        
        df_results = pd.DataFrame(trades_history)
        
        # Tạo tên file độc nhất không bị ghi đè
        date_str = f"_{start_date}_to_{end_date}" if start_date and end_date else ""
        run_time = datetime.now().strftime("%H%M%S")
        file_path = f"data/Backtest_Results_{symbol}{date_str}_{run_time}.csv"
        
        df_results.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"\n📁 ĐÃ LƯU BÁO CÁO CHI TIẾT TẠI: D:\\TradingPineline\\{file_path}")
        
    mt5.shutdown()

if __name__ == "__main__":
    run_backtest("XAUUSDm", start_date="2025-01-01", end_date="2025-04-01")
