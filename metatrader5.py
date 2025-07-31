import MetaTrader5 as mt5
import pandas as pd
import pytz
from datetime import datetime, time
from metatrader5_config import MT5_CONFIG

class MT5Connector:
    def __init__(self):
        # استفاده از تنظیمات از config file
        self.symbol = MT5_CONFIG['symbol']
        self.lot = MT5_CONFIG['lot_size']
        self.deviation = MT5_CONFIG['deviation']
        self.magic = MT5_CONFIG['magic_number']
        self.max_spread = MT5_CONFIG['max_spread']
        self.min_balance = MT5_CONFIG['min_balance']
        self.trading_hours = MT5_CONFIG['trading_hours']
        
        # تنظیم timezone ایران
        self.iran_tz = pytz.timezone('Asia/Tehran')
        self.utc_tz = pytz.UTC
        
    def get_iran_time(self):
        """دریافت زمان فعلی ایران"""
        utc_now = datetime.now(self.utc_tz)
        iran_now = utc_now.astimezone(self.iran_tz)
        return iran_now
        
    def is_trading_time(self):
        """بررسی اینکه آیا زمان فعلی در ساعات معاملاتی است یا نه (بر اساس ساعت ایران)"""
        iran_now = self.get_iran_time()
        current_time = iran_now.time()
        
        start_time = time.fromisoformat(self.trading_hours['start'])
        end_time = time.fromisoformat(self.trading_hours['end'])
        
        # اگر ساعت پایان از شروع کمتر باشد (مثل 22:00 تا 08:00)
        if start_time > end_time:
            return current_time >= start_time or current_time <= end_time
        else:
            return start_time <= current_time <= end_time
    
    def check_weekend(self):
        """بررسی تعطیلی آخر هفته (بر اساس ساعت ایران)"""
        iran_now = self.get_iran_time()
        
        # در ایران: پنج‌شنبه = 3, جمعه = 4, شنبه = 5
        # فارکس: جمعه شب تا یکشنبه شب بسته است
        
        if iran_now.weekday() == 4:  # جمعه
            # بعد از ساعت 20:30 جمعه تا شب، بازار بسته
            if iran_now.time() >= time(20, 30):
                return False
        elif iran_now.weekday() == 5:  # شنبه
            # تمام روز شنبه بازار بسته
            return False
        elif iran_now.weekday() == 6:  # یکشنبه
            # تا ساعت 20:30 یکشنبه بازار بسته
            if iran_now.time() <= time(20, 30):
                return False
        
        return True
    
    def can_trade(self):
        """بررسی کلی امکان معامله"""
        iran_time = self.get_iran_time()
        
        if not self.check_weekend():
            return False, f"Market closed - Weekend (Iran time: {iran_time.strftime('%Y-%m-%d %H:%M:%S')})"
        
        if not self.is_trading_time():
            return False, f"Outside trading hours ({self.trading_hours['start']}-{self.trading_hours['end']} Iran time: {iran_time.strftime('%H:%M')})"
        
        return True, f"Trading allowed (Iran time: {iran_time.strftime('%H:%M')})"
    
    def initialize(self):
        """اتصال به MT5 با بررسی موجودی"""
        if not mt5.initialize():
            print("initialize() failed, error code =", mt5.last_error())
            return False
        
        # بررسی موجودی حساب
        account_info = mt5.account_info()
        if account_info and account_info.balance < self.min_balance:
            print(f"❌ Balance ({account_info.balance}) is below minimum ({self.min_balance})")
            return False
        
        # نمایش زمان ایران
        iran_time = self.get_iran_time()
        print("✅ MT5 connection established")
        print(f"Terminal: {mt5.terminal_info().name if mt5.terminal_info() else 'Unknown'}")
        print(f"Account: {account_info.login if account_info else 'Unknown'}")
        print(f"Balance: ${account_info.balance if account_info else 0}")
        print(f"🇮🇷 Iran Time: {iran_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        return True
    
    def get_live_price(self):
        """دریافت قیمت زنده با بررسی spread"""
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            print(f"Failed to get tick for {self.symbol}")
            return None
        
        # بررسی spread
        spread = (tick.ask - tick.bid) * 10000  # به pip تبدیل
        if spread > self.max_spread:
            print(f"⚠️ High spread: {spread:.1f} pips (max: {self.max_spread})")
            return None
        
        # تبدیل زمان tick به زمان ایران
        utc_time = datetime.fromtimestamp(tick.time, tz=self.utc_tz)
        iran_time = utc_time.astimezone(self.iran_tz)
        
        return {
            'bid': tick.bid,
            'ask': tick.ask,
            'spread': spread,
            'time': iran_time,
            'utc_time': utc_time
        }
    
    def get_historical_data(self, timeframe=mt5.TIMEFRAME_M1, count=1000):
        """دریافت داده‌های تاریخی"""
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
        if rates is None:
            print("Failed to get historical data")
            return None
            
        df = pd.DataFrame(rates)
        
        # تبدیل زمان به timezone ایران
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df['time'] = df['time'].dt.tz_convert(self.iran_tz)
        df.set_index('time', inplace=True)
        
        # تبدیل نام ستون‌ها
        df = df.rename(columns={'tick_volume': 'volume'})
        df['timestamp'] = df.index
        
        return df
    
    def open_buy_position(self, price, sl, tp, comment=""):
        """باز کردن پوزیشن خرید"""
        iran_time = self.get_iran_time()
        comment_with_time = f"{comment} {iran_time.strftime('%H:%M')}"
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_BUY,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": comment_with_time,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        return result
    
    def open_sell_position(self, price, sl, tp, comment=""):
        """باز کردن پوزیشن فروش"""
        iran_time = self.get_iran_time()
        comment_with_time = f"{comment} {iran_time.strftime('%H:%M')}"
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": comment_with_time,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        return result
    
    def close_all_positions(self):
        """بستن تمام پوزیشن‌ها"""
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return
            
        for position in positions:
            tick = mt5.symbol_info_tick(self.symbol)
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position.volume,
                "type": mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY,
                "position": position.ticket,
                "price": tick.bid if position.type == 0 else tick.ask,
                "deviation": self.deviation,
                "magic": self.magic,
                "comment": "Close position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            mt5.order_send(request)
    
    def shutdown(self):
        """قطع اتصال"""
        mt5.shutdown()