from datetime import datetime
from fibo_calculate import fibonacci_retracement
import numpy as np
import pandas as pd
from time import sleep
from colorama import init, Fore
from get_legs import get_legs
from metatrader5 import MT5Connector
from swing import get_swing_points
from utils import BotState
from save_file import log
from metatrader5_config import MT5_CONFIG, TRADING_CONFIG

# راه‌اندازی MT5 و colorama
init(autoreset=True)
mt5_conn = MT5Connector()

if not mt5_conn.initialize():
    print("❌ Failed to connect to MT5")
    exit()

# Initial state با تنظیمات
state = BotState()
state.reset()

start_index = 0
win_ratio = MT5_CONFIG['win_ratio']
threshold = TRADING_CONFIG['threshold']
window_size = TRADING_CONFIG['window_size']
min_swing_size = TRADING_CONFIG['min_swing_size']

i = 1
position_open = False

print(f"🚀 MT5 Trading Bot Started...")
print(f"📊 Config: Symbol={MT5_CONFIG['symbol']}, Lot={MT5_CONFIG['lot_size']}, Win Ratio={win_ratio}")
print(f"⏰ Trading Hours (Iran): {MT5_CONFIG['trading_hours']['start']} - {MT5_CONFIG['trading_hours']['end']}")
print(f"🇮🇷 Current Iran Time: {mt5_conn.get_iran_time().strftime('%Y-%m-%d %H:%M:%S')}")

while True:
    try:
        # بررسی ساعات معاملاتی
        can_trade, trade_message = mt5_conn.can_trade()
        
        if not can_trade:
            log(f"⏰ {trade_message}", color='yellow')
            sleep(60)  # چک کردن هر دقیقه در زمان غیرمعاملاتی
            continue
        
        # دریافت داده از MT5
        cache_data = mt5_conn.get_historical_data(count=window_size * 2)
        
        if cache_data is None:
            log("❌ Failed to get data from MT5", color='red')
            sleep(5)
            continue
            
        cache_data['status'] = np.where(cache_data['open'] > cache_data['close'], 'bearish', 'bullish')
        
        log(f'Log number {i}: (Trading time ✅)', color='lightred_ex')
        i += 1
        
        # استفاده از threshold از config
        legs = get_legs(cache_data[start_index:])
        log(f'Legs count: {len(legs)}', color='green')

        if len(legs) >= min_swing_size:
            legs = legs[-3:]
            swing_result = get_swing_points(data=cache_data, legs=legs)
            
            if swing_result and len(swing_result) == 2:
                swing_type, is_swing = swing_result

                if is_swing:
                    # محاسبه fibonacci levels
                    if swing_type == 'bullish':
                        fib_levels = fibonacci_retracement(legs[-2]['end_value'], legs[-1]['end_value'])
                        state.fib_levels = fib_levels
                        log(f'🔵 Bullish swing detected - Fib 0.9: {fib_levels["0.9"]:.5f}', color='blue')
                        
                    elif swing_type == 'bearish':
                        fib_levels = fibonacci_retracement(legs[-2]['end_value'], legs[-1]['end_value'])
                        state.fib_levels = fib_levels
                        log(f'🔴 Bearish swing detected - Fib 0.9: {fib_levels["0.9"]:.5f}', color='red')

                if state.fib_levels:
                    current_price = mt5_conn.get_live_price()
                    
                    if current_price is None:
                        log("⚠️ Unable to get current price or spread too high", color='yellow')
                        sleep(2)
                        continue
                    
                    current_close = current_price['ask'] if swing_type == 'bullish' else current_price['bid']
                    
                    # بررسی شرایط ورود (فقط در ساعات معاملاتی)
                    fib_distance = abs(state.fib_levels['0.9'] - current_close) * 10000
                    
                    if fib_distance < 2 and not position_open:
                        state.true_position = True
                        
                        if swing_type == 'bullish':
                            entry_price = current_price['ask']
                            stop_loss = state.fib_levels['1.0']
                            stop_distance = abs(entry_price - stop_loss)
                            take_profit = entry_price + (stop_distance * win_ratio)
                            
                            result = mt5_conn.open_buy_position(
                                price=entry_price,
                                sl=stop_loss,
                                tp=take_profit,
                                comment=f"SwingBuy-{datetime.now().strftime('%H%M')}"
                            )
                            
                            if result and result.retcode == 10009:
                                log(f'✅ BUY opened - Entry:{entry_price:.5f}, SL:{stop_loss:.5f}, TP:{take_profit:.5f}', color='green')
                                position_open = True
                                state.reset()
                                start_index = len(cache_data) - 1
                            else:
                                log(f'❌ BUY failed: {result.comment if result else "No result"}', color='red')
                        
                        elif swing_type == 'bearish':
                            entry_price = current_price['bid']
                            stop_loss = state.fib_levels['1.0']
                            stop_distance = abs(entry_price - stop_loss)
                            take_profit = entry_price - (stop_distance * win_ratio)
                            
                            result = mt5_conn.open_sell_position(
                                price=entry_price,
                                sl=stop_loss,
                                tp=take_profit,
                                comment=f"SwingSell-{datetime.now().strftime('%H%M')}"
                            )
                            
                            if result and result.retcode == 10009:
                                log(f'✅ SELL opened - Entry:{entry_price:.5f}, SL:{stop_loss:.5f}, TP:{take_profit:.5f}', color='red')
                                position_open = True
                                state.reset()
                                start_index = len(cache_data) - 1
                            else:
                                log(f'❌ SELL failed: {result.comment if result else "No result"}', color='red')
                    
                    else:
                        if fib_distance >= 2:
                            log(f'📏 Distance from Fib 0.9: {fib_distance:.1f} pips (waiting for <2)', color='cyan')

        # بررسی وضعیت پوزیشن‌های باز
        positions = mt5.positions_get(symbol=MT5_CONFIG['symbol'])
        if positions is None or len(positions) == 0:
            if position_open:
                log("🏁 Position closed", color='yellow')
                position_open = False

        sleep(1)

    except KeyboardInterrupt:
        log("🛑 Bot stopped by user", color='yellow')
        mt5_conn.close_all_positions()
        break
    except Exception as e:
        log(f"❌ Error: {e}", color='red')
        sleep(5)

mt5_conn.shutdown()
print("🔌 MT5 connection closed")