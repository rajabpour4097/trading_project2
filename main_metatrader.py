import MetaTrader5 as mt5
from datetime import datetime
from fibo_calculate import fibonacci_retracement
import numpy as np
import pandas as pd
from time import sleep
from colorama import init, Fore
from get_legs import get_legs
from mt5_connector import MT5Connector
from swing import get_swing_points
from utils import BotState
from save_file import log
from metatrader5_config import MT5_CONFIG, TRADING_CONFIG

def main():
    # راه‌اندازی MT5 و colorama
    init(autoreset=True)
    mt5_conn = MT5Connector()

    if not mt5_conn.initialize():
        print("❌ Failed to connect to MT5")
        return

    # Initial state با تنظیمات - مطابق main_saver_copy2.py
    state = BotState()
    state.reset()

    start_index = 0
    win_ratio = MT5_CONFIG['win_ratio']
    threshold = TRADING_CONFIG['threshold']
    window_size = TRADING_CONFIG['window_size']
    min_swing_size = TRADING_CONFIG['min_swing_size']

    i = 1
    f = 1
    position_open = False
    last_swing_type = None
    fib_index = None
    fib0_point = None
    last_leg1_value = None
    end_price = None
    start_price = None

    print(f"🚀 MT5 Trading Bot Started...")
    print(f"📊 Config: Symbol={MT5_CONFIG['symbol']}, Lot={MT5_CONFIG['lot_size']}, Win Ratio={win_ratio}")
    print(f"⏰ Trading Hours (Iran): {MT5_CONFIG['trading_hours']['start']} - {MT5_CONFIG['trading_hours']['end']}")
    print(f"🇮🇷 Current Iran Time: {mt5_conn.get_iran_time().strftime('%Y-%m-%d %H:%M:%S')}")

    # در ابتدای main loop بعد از initialize
    print("🔍 Checking symbol properties...")
    mt5_conn.check_symbol_properties()
    print("🔍 Testing broker filling modes...")
    mt5_conn.test_filling_modes()
    mt5_conn.check_trading_limits()
    print("-" * 50)

    # اضافه کردن متغیر برای ذخیره آخرین داده
    last_data_time = None
    wait_count = 0
    max_wait_cycles = 120  # پس از 60 ثانیه (120 * 0.5) اجبار به پردازش

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
            
            # بررسی تغییر داده - مشابه main_saver_copy2.py
            current_time = cache_data.index[-1]
            if last_data_time is None:
                log(f"🔄 First run - processing data from {current_time}", color='cyan')
                last_data_time = current_time
                process_data = True
                wait_count = 0
            elif current_time != last_data_time:
                log(f"📊 New data received: {current_time} (previous: {last_data_time})", color='cyan')
                last_data_time = current_time
                process_data = True
                wait_count = 0
            else:
                wait_count += 1
                if wait_count % 20 == 0:  # هر 10 ثانیه یک بار لاگ
                    log(f"⏳ Waiting for new data... Current: {current_time} (wait cycles: {wait_count})", color='yellow')
                
                # اگر خیلی زیاد انتظار کشیدیم، اجبار به پردازش (در صورت تست)
                if wait_count >= max_wait_cycles:
                    log(f"⚠️ Force processing after {wait_count} cycles without new data", color='magenta')
                    process_data = True
                    wait_count = 0
                else:
                    process_data = False
            
            if process_data:
                log((' ' * 80 + '\n') * 3)
                log(f'Log number {i}:', color='lightred_ex')
                log(f' ' * 80)
                i += 1
                
                legs = get_legs(cache_data.iloc[start_index:])
                log(f'First len legs: {len(legs)}', color='green')
                log(f' ' * 80)

                if len(legs) > 2:
                    legs = legs[-3:]
                    swing_type, is_swing = get_swing_points(data=cache_data, legs=legs)

                    if is_swing or state.fib_levels:
                        log(f'1- is_swing or fib_levels is not None code:411112', color='blue')
                        log(f"{swing_type} | {cache_data.loc[legs[0]['start']].name} {cache_data.loc[legs[0]['end']].name} "
                            f"{cache_data.loc[legs[1]['start']].name} {cache_data.loc[legs[1]['end']].name} "
                            f"{cache_data.loc[legs[2]['start']].name} {cache_data.loc[legs[2]['end']].name}", color='yellow')

                        log(f' ' * 80)
                        
                        # فاز 1: تشخیص اولیه swing
                        if is_swing and state.fib_levels is None:
                            log(f'is_swing and fib_levels is None code:4113312', color='yellow')
                            
                            if swing_type == 'bullish':
                                if cache_data.iloc[-1]['close'] >= legs[0]['end_value']:
                                    start_price = cache_data.iloc[-1]['high']  #fib0
                                    end_price = legs[1]['end_value']  #fib1
                                    
                                    if cache_data.iloc[-1]['high'] >= legs[1]['end_value']:
                                        log(f'The {f} of fib_levels value code:4116455 {cache_data.iloc[-1].name}', color='green')
                                        state.fib_levels = fibonacci_retracement(end_price=end_price, start_price=start_price)
                                        fib0_point = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                                        fib_index = cache_data.iloc[-1].name
                                        last_leg1_value = cache_data.index.tolist().index(legs[1]['end'])
                                        legs = legs[-2:]
                                        f += 1
                                    
                                    elif state.fib_levels and cache_data.iloc[-1]['low'] < state.fib_levels['1.0']:
                                        state.reset()
                                        legs = legs[-2:]
                                        start_index = cache_data.index.tolist().index(legs[0]['start'])

                                    if state.fib_levels:
                                        log(f'fib_levels: {state.fib_levels}', color='yellow')
                                        log(f'fib_index: {fib_index}', color='yellow')

                            elif swing_type == 'bearish':
                                if cache_data.iloc[-1]['close'] <= legs[0]['end_value']:
                                    start_price = cache_data.iloc[-1]['low']  #fib0
                                    end_price = legs[1]['end_value']  #fib1
                                    
                                    if cache_data.iloc[-1]['low'] <= legs[1]['end_value']:
                                        log(f'The {f} of fib_levels value code:4126455 {cache_data.iloc[-1].name}', color='green')
                                        state.fib_levels = fibonacci_retracement(start_price=start_price, end_price=end_price)
                                        fib0_point = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                                        fib_index = cache_data.iloc[-1].name
                                        last_leg1_value = cache_data.index.tolist().index(legs[1]['end'])
                                        legs = legs[-2:]
                                        f += 1
                                    
                                    elif state.fib_levels and cache_data.iloc[-1]['high'] > state.fib_levels['1.0']:
                                        state.reset()
                                        legs = legs[-2:]
                                        start_index = cache_data.index.tolist().index(legs[0]['start'])
                                    
                                    if state.fib_levels:
                                        log(f'fib_levels: {state.fib_levels}', color='yellow')
                                        log(f'fib_index: {fib_index}', color='yellow')
                        
                        # فاز 2: به‌روزرسانی در swing مشابه - تنها در صورت یکسان بودن جهت
                        elif is_swing and state.fib_levels and last_swing_type == swing_type: 
                            log(f'is_swing and state.fib_levels and last_swing_type == swing_type code:4213312', color='yellow')
                            if swing_type == 'bullish' and cache_data.iloc[-1]['high'] >= legs[1]['end_value']:
                                log(f'The {f} of fib_levels value update code:9916455 {cache_data.iloc[-1].name}', color='green')
                                start_price = cache_data.iloc[-1]['high']  #fib0
                                end_price = legs[1]['end_value']  #fib1
                                state.fib_levels = fibonacci_retracement(start_price=start_price, end_price=end_price)
                                fib0_point = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                                fib_index = cache_data.iloc[-1].name
                                last_leg1_value = cache_data.index.tolist().index(legs[1]['end'])
                                legs = legs[-2:]
                                f += 1
                            elif swing_type == 'bearish' and cache_data.iloc[-1]['low'] <= legs[1]['end_value']:
                                log(f'The {f} of fib_levels value update code:9916455 {cache_data.iloc[-1].name}', color='green')
                                start_price = cache_data.iloc[-1]['low']  #fib0
                                end_price = legs[1]['end_value']  #fib1
                                state.fib_levels = fibonacci_retracement(start_price=start_price, end_price=end_price)
                                fib0_point = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                                fib_index = cache_data.iloc[-1].name
                                last_leg1_value = cache_data.index.tolist().index(legs[1]['end'])
                                legs = legs[-2:]
                                f += 1

                        # فاز جدید: مدیریت swing معکوس بدون عبور از fib 1.0
                        elif is_swing and state.fib_levels and last_swing_type != swing_type:
                            log(f'is_swing with opposite direction - checking fib 1.0 violation', color='orange')
                            
                            # اگر swing معکوس است، فقط در صورت عبور از fib 1.0 ریست کنیم
                            if last_swing_type == 'bullish' and swing_type == 'bearish':
                                if cache_data.iloc[-1]['high'] > state.fib_levels['1.0']:
                                    log(f'Bearish swing violated fib 1.0 - resetting', color='red')
                                    state.reset()
                                    legs = legs[-2:]
                                    start_index = cache_data.index.tolist().index(legs[0]['start'])
                                else:
                                    log(f'Bearish swing within fib range - ignoring', color='yellow')
                                    # نادیده گرفتن این swing و ادامه با fib قبلی
                                    
                            elif last_swing_type == 'bearish' and swing_type == 'bullish':
                                if cache_data.iloc[-1]['low'] < state.fib_levels['1.0']:
                                    log(f'Bullish swing violated fib 1.0 - resetting', color='red')
                                    state.reset()
                                    legs = legs[-2:]
                                    start_index = cache_data.index.tolist().index(legs[0]['start'])
                                else:
                                    log(f'Bullish swing within fib range - ignoring', color='yellow')
                                    # نادیده گرفتن این swing و ادامه با fib قبلی

                # len legs <= 2
                elif len(legs) < 3:
                    if len(legs) == 2:
                        if state.fib_levels:
                            if last_swing_type == 'bullish':
                                if state.fib_levels['0.0'] < cache_data.iloc[-1]['high']:
                                    log(f'update fib_levels value code:5117455 {cache_data.iloc[-1].name}', color='green')
                                    start_price = cache_data.iloc[-1]['high']
                                    state.fib_levels = fibonacci_retracement(end_price=end_price, start_price=start_price)
                                    fib0_point = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                                    fib_index = cache_data.iloc[-1].name
                                
                                elif cache_data.iloc[-1]['low'] <= state.fib_levels['0.705']:
                                    if state.last_touched_705_point_up is None:
                                        log(f'first touch 705 point', color='green')
                                        state.last_touched_705_point_up = cache_data.iloc[-1]
                                    elif cache_data.iloc[-1]['status'] != state.last_touched_705_point_up['status']:
                                        log(f'Second touch 705 point code:4118455 {cache_data.iloc[-1].name}', color='green')
                                        state.true_position = True                               

                            if last_swing_type == 'bearish':
                                if state.fib_levels['0.0'] > cache_data.iloc[-1]['low']:
                                    log(f'update fib_levels value code:5127455 {cache_data.iloc[-1].name}', color='green')
                                    start_price = cache_data.iloc[-1]['low']
                                    state.fib_levels = fibonacci_retracement(start_price=start_price, end_price=end_price)
                                    fib0_point = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                                    fib_index = cache_data.iloc[-1].name
                                
                                elif cache_data.iloc[-1]['high'] >= state.fib_levels['0.705']:
                                    if state.last_touched_705_point_down is None:
                                        log(f'first touch 705 point', color='red')
                                        state.last_touched_705_point_down = cache_data.iloc[-1]
                                    elif cache_data.iloc[-1]['status'] != state.last_touched_705_point_down['status']:
                                        log(f'Second touch 705 point code:5128455 {cache_data.iloc[-1].name}', color='green')
                                        state.true_position = True
                                
                        log(f'leg0: {legs[0]["start"]}, {legs[0]["end"]}, leg1: {legs[1]["start"]}, {legs[1]["end"]}', color='lightcyan_ex')
                    if len(legs) == 1:
                        log(f'leg0: {legs[0]["start"]}, {legs[0]["end"]}', color='lightcyan_ex')
                
                # بخش معاملات - sell and buy statement
                if state.true_position and last_swing_type == 'bullish':
                    current_open_point = cache_data.iloc[-1]['close']
                    
                    log(f'Start long position income {cache_data.iloc[-1].name}', color='blue')
                    log(f'current_open_point: {current_open_point}', color='blue')
                    
                    # تعیین stop loss
                    if abs(state.fib_levels['0.9'] - current_open_point) * 10000 < 2:
                        stop = state.fib_levels['1.0']
                        log(f'stop = fib_levels[1.0] {stop}', color='red')
                    else:
                        stop = state.fib_levels['0.9']
                        log(f'stop = fib_levels[0.9] {stop}', color='red')
                    
                    stop_distance = abs(current_open_point - stop)
                    reward_end = current_open_point + (stop_distance * win_ratio)
                    
                    log(f'stop = {stop}', color='green')
                    log(f'reward_end = {reward_end}', color='green')
                    
                    # اجرای معامله در MT5
                    result = mt5_conn.open_buy_position(
                        price=current_open_point,
                        sl=stop,
                        tp=reward_end,
                        comment=f"Bullish Swing {swing_type}"
                    )
                    
                    if result:
                        log(f'✅ BUY order executed successfully', color='green')
                        position_open = True
                    else:
                        log(f'❌ BUY order failed', color='red')

                    # ریست کردن state بعد از معامله
                    state.reset()
                    legs = []
                    start_index = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                    log(f'End long position, start_index: {start_index}', color='black')

                if state.true_position and last_swing_type == 'bearish':
                    current_open_point = cache_data.iloc[-1]['close']
                    
                    log(f'Start short position income {cache_data.iloc[-1].name}', color='red')
                    log(f'current_open_point: {current_open_point}', color='red')
                    
                    # تعیین stop loss
                    if abs(state.fib_levels['0.9'] - current_open_point) * 10000 < 2:
                        stop = state.fib_levels['1.0'] 
                        log(f'stop = fib_levels[1.0] {stop}', color='red')
                    else:
                        stop = state.fib_levels['0.9']
                        log(f'stop = fib_levels[0.9] {stop}', color='red')
                        
                    stop_distance = abs(current_open_point - stop)
                    reward_end = current_open_point - (stop_distance * win_ratio)
                    
                    log(f'stop = {stop}', color='red')
                    log(f'reward_end = {reward_end}', color='red')
                    
                    # اجرای معامله در MT5
                    result = mt5_conn.open_sell_position(
                        price=current_open_point,
                        sl=stop,
                        tp=reward_end,
                        comment=f"Bearish Swing {swing_type}"
                    )
                    
                    if result:
                        log(f'✅ SELL order executed successfully', color='green')
                        position_open = True
                    else:
                        log(f'❌ SELL order failed', color='red')

                    # ریست کردن state بعد از معامله
                    state.reset()
                    legs = []
                    start_index = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                    log(f'End short position, start_index: {start_index}', color='black')
                
                log(f'cache_data.iloc[-1].name: {cache_data.iloc[-1].name}', color='lightblue_ex')
                log(f'len(legs): {len(legs)} | start_index: {start_index} | {cache_data.iloc[start_index].name}', color='lightred_ex')
                log(f' ' * 80)
                log(f'-'* 80)
                log(f' ' * 80)

                # ذخیره آخرین زمان داده
                # last_data_time = cache_data.index[-1]  # این خط حذف شد چون بالا انجام شد

            # بررسی وضعیت پوزیشن‌های باز
            positions = mt5_conn.get_positions()
            if positions is None or len(positions) == 0:
                if position_open:
                    log("🏁 Position closed", color='yellow')
                    position_open = False

            sleep(0.5)  # مطابق main_saver_copy2.py

        except KeyboardInterrupt:
            log("🛑 Bot stopped by user", color='yellow')
            mt5_conn.close_all_positions()
            break
        except Exception as e:
            log(f' ' * 80)
            log(f"❌ Error: {e}", color='red')
            sleep(5)

    mt5_conn.shutdown()
    print("🔌 MT5 connection closed")

if __name__ == "__main__":
    main()