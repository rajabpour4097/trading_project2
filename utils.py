from fibo_calculate import fibonacci_retracement
from get_live_data import get_live_data
from time import sleep



class BotState:
    def __init__(self):
        self.reset()

    def reset(self):
        self.fib_levels = None
        self.true_position = False
        self.last_touched_705_point_up = None
        self.last_touched_705_point_down = None
        

def handle_fib_levels(state, swing_type, legs, cache_data, start_index):
    """Handle fibonacci level calculations and updates"""
    if swing_type == 'bullish':
        start_price = legs[1]['end_value']
        end_price = cache_data.iloc[-1]['high']
        price_check = lambda x: x['low']
        level_check = lambda fib, price: price <= fib
        opposite_level_check = lambda fib, price: price < fib
    else:  # bearish
        end_price = cache_data.iloc[-1]['low']
        start_price = legs[1]['end_value']
        price_check = lambda x: x['high']
        level_check = lambda fib, price: price >= fib
        opposite_level_check = lambda fib, price: price > fib

    if (swing_type == 'bullish' and state.fib_levels['0.0'] < cache_data.iloc[-1]['high']) or \
       (swing_type == 'bearish' and state.fib_levels['0.0'] > cache_data.iloc[-1]['low']):
        state.fib_levels = fibonacci_retracement(end_price, start_price)
        fib0_point = cache_data.index.tolist().index(cache_data.iloc[-1].name)
        fib_index = cache_data.iloc[-1].name
        
    elif level_check(state.fib_levels['0.705'], price_check(cache_data.iloc[-1])):
        touched_point = state.last_touched_705_point_up if swing_type == 'bullish' else state.last_touched_705_point_down
        if touched_point is None:
            if swing_type == 'bullish':
                state.last_touched_705_point_up = cache_data.iloc[-1]
            else:
                state.last_touched_705_point_down = cache_data.iloc[-1]
        elif cache_data.iloc[-1]['status'] != touched_point['status']:
            state.true_position = True
            
    elif opposite_level_check(state.fib_levels['1.0'], price_check(cache_data.iloc[-1])):
        state.reset()
        legs = legs[-2:]
        start_index = cache_data.index.tolist().index(legs[0]['start'])
        
    return state, legs, start_index

def handle_trade(state, swing_type, cache_data, live_data):
    """Handle trade execution and monitoring"""
    current_open_point = cache_data.iloc[-1]['close']
    
    # تعیین جهت و پارامترهای معامله
    if swing_type == 'bullish':
        direction = 1
        position_type = 'long'
        check_reward = lambda h, r: h >= r
        check_stop = lambda l, s: l <= s
    else:
        direction = -1
        position_type = 'short'
        check_reward = lambda l, r: l <= r
        check_stop = lambda h, s: h >= s

    # محاسبه حد ضرر و سود
    if abs(state.fib_levels['0.9'] - current_open_point) * 10000 < 2:
        stop = state.fib_levels['1.0']
    else:
        stop = state.fib_levels['0.9']

    stop_distance = abs(current_open_point - stop)
    reward_end = current_open_point + (stop_distance * 2 * direction)

    # مانیتورینگ قیمت
    high = low = live_data['mid']
    while not (check_reward(high if direction == 1 else low, reward_end) or 
              check_stop(high if direction == -1 else low, stop)):
        live_data = get_live_data()
        mid = live_data['mid']
        high = max(high, mid)
        low = min(low, mid)
        sleep(0.3)

    return cache_data.index.tolist().index(cache_data.iloc[-1].name)