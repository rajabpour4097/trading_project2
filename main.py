import numpy as np
import pandas as pd
from twelvedata import TDClient
from time import sleep
from colorama import Fore

from fibo_calculate import fibonacci_retracement
from get_data_multiip import get_live_data
from get_legs import get_legs
from swing import get_swing_points



if __name__ == "__main__":
    
    # initial_swing_search()
    
    fib_levels = None
    true_position = False
    last_touched_705_point_up = None
    last_touched_705_point_down = None
    

    cache_data = pd.read_csv("eurusd_prices_filtered.csv", parse_dates=["timestamp"], index_col="timestamp")
    last_data = cache_data.iloc[-1]
    start_index = 0
    
    while True:
        
        try:
            
            cache_data = pd.read_csv("eurusd_prices_filtered.csv", parse_dates=["timestamp"], index_col="timestamp")
            cache_data['status'] = np.where(cache_data['open'] > cache_data['close'], 'bearish', 'bullish')
            
            if cache_data.iloc[-1].name != last_data.name:
                
                legs = get_legs(cache_data[start_index:])
                print(Fore.GREEN+'First len legs: ', len(legs))  
                
                if len(legs) > 2:
                    legs = legs[-3:]
                    swing_type, is_swing = get_swing_points(data=cache_data, legs=legs)
                    
                    if is_swing or fib_levels is not None:
                        print(Fore.BLUE+'1- is_swing or fib_levels is not None')
                        print(Fore.YELLOW+'', 'swing_type: ', swing_type, 
                            cache_data.loc[legs[0]['start']].name, cache_data.loc[legs[0]['end']].name,
                            cache_data.loc[legs[1]['start']].name, cache_data.loc[legs[1]['end']].name, 
                            cache_data.loc[legs[2]['start']].name, cache_data.loc[legs[2]['end']].name
                            )
                        
                        if swing_type == 'bullish':
                            
                            if cache_data.iloc[-1]['close'] >= legs[0]['end_value'] or fib_levels:
                                print(Fore.GREEN+ 'start Long position(Buy) ', cache_data.iloc[-1].name)
                                
                                start_price = legs[1]['end_value']
                                end_price = cache_data.iloc[-1]['high']
                                if fib_levels is None:
                                    fib_levels = fibonacci_retracement(end_price, start_price)
                                    fib0_point = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                                    fib_index = cache_data.iloc[-1].name
                                    last_leg1_value = cache_data.index.tolist().index(legs[1]['end'])
                                
                                elif fib_levels and fib_levels['0.0'] < cache_data.iloc[-1]['high']:
                                    fib_levels = fibonacci_retracement(end_price, start_price)
                                    fib0_point = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                                    fib_index = cache_data.iloc[-1].name
                                
                                if cache_data.iloc[-1]['low'] <= fib_levels['0.705']:
                                    
                                    if last_touched_705_point_up is None:
                                        print(Fore.GREEN+ 'first touch 705 point')
                                        last_touched_705_point_up = cache_data.iloc[-1]
                                    else:
                                        if cache_data.iloc[-1]['status'] != last_touched_705_point_up['status']:
                                            true_position = True
                                        
                                    
                                print(Fore.YELLOW+'', fib_levels)
                                print(Fore.YELLOW+ 'fib_index: ', fib_index)
                                
                        elif swing_type == 'bearish':
                            
                            if cache_data.iloc[-1]['close'] <= legs[0]['end_value'] or fib_levels:
                                print(Fore.RED+ 'start Short position(Sell) ', cache_data.iloc[-1].name)
                                
                                end_price = cache_data.iloc[-1]['low']
                                start_price = legs[1]['end_value']
                            
                                
                                    
                                if fib_levels is None:
                                    fib_levels = fibonacci_retracement(end_price, start_price)
                                    fib0_point = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                                    fib_index = cache_data.iloc[-1].name
                                    last_leg1_value = cache_data.index.tolist().index(legs[1]['end'])
                                    
                                elif fib_levels and fib_levels['0.0'] > cache_data.iloc[-1]['low']:
                                    fib_levels = fibonacci_retracement(end_price, start_price)
                                    fib0_point = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                                    fib_index = cache_data.iloc[-1].name
                                
                                if cache_data.iloc[-1]['high'] >= fib_levels['0.705']:
                                    if last_touched_705_point_down is None:
                                        print(Fore.RED+ 'first touch 705 point')
                                        last_touched_705_point_down = cache_data.iloc[-1]
                                    else:
                                        if cache_data.iloc[-1]['status'] != last_touched_705_point_down['status']:
                                            true_position = True
                                
                                print(Fore.YELLOW+ 'fib_levels: ', fib_levels)
                                print(Fore.YELLOW+ 'fib_index: ', fib_index)
                                
                        # Buy Position
                        if true_position and swing_type == 'bullish':
                            
                            live_data = get_live_data()
                            print(Fore.BLUE+ 'Start long position', cache_data.iloc[-1].name)
                            
                            buy_start_price = cache_data.iloc[-1]['close']
                            
                            
                            while live_data['high'] <= cache_data.iloc[-1]['open'] + 0.0003 and live_data['low'] >= cache_data.iloc[-1]['open'] - 0.0003:
                                live_data = get_live_data()
                                sleep(0.3)
                                
                            fib_levels = None
                            true_position = False
                            last_touched_705_point_up = None
                            last_touched_705_point_down = None
                            legs = []
                            start_index = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                            
                            print(Fore.BLACK+ 'End long position', 'start_index: ', start_index)
                            
                        # Sell Position
                        if true_position and swing_type == 'bearish':
                            
                            live_data = get_live_data()
                            print(Fore.RED+ 'Start short position', cache_data.iloc[-1].name)
                            
                            sell_start_price = cache_data.iloc[-1]['close']
                            
                            while live_data['low'] <= cache_data.iloc[-1]['open'] - 0.0003 and live_data['high'] >= cache_data.iloc[-1]['open'] + 0.0003:
                                live_data = get_live_data()
                                sleep(0.3)
                            
                            fib_levels = None
                            true_position = False
                            last_touched_705_point_up = None
                            last_touched_705_point_down = None
                            legs = []
                            start_index = cache_data.index.tolist().index(cache_data.iloc[-1].name)
                            print(Fore.BLACK+ 'End short position', 'start_index: ', start_index)
                        
                    elif is_swing == False and fib_levels is None:
                        print(Fore.BLUE+'2- is_swing == False and fib_levels is None')
                        fib_levels = None
                        true_position = False
                        last_touched_705_point_up = None
                        last_touched_705_point_down = None
                        legs = legs[-2:]
                        start_index = cache_data.index.tolist().index(legs[0]['start'])
                        
                        print(Fore.GREEN+ 'no swing', legs[0]['start'], legs[0]['end'], legs[1]['start'], legs[1]['end'], legs[2]['start'], legs[2]['end'])
            
                                            
                print(Fore.LIGHTBLUE_EX+'cache_data.iloc[-1].name: ', cache_data.iloc[-1].name)
                print(Fore.LIGHTRED_EX+ 'len(legs): ', len(legs), 'start_index: ', start_index, cache_data.iloc[start_index].name)
                
                if len(legs) < 3:
                    if len(legs) == 2:
                        print(Fore.LIGHTCYAN_EX+'leg0: ', legs[0]['start'], legs[0]['end'], 'leg1: ', legs[1]['start'], legs[1]['end'])
                    if len(legs) == 1:
                        print(Fore.LIGHTCYAN_EX+'leg0: ', legs[0]['start'], legs[0]['end'])
            
            last_data = cache_data.iloc[-1]
            
            sleep(0.5)
        
        except Exception as e:
            print(f"Error: {e}")


        


