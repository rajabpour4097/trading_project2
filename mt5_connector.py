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
    
    def get_supported_filling_mode(self):
        """تشخیص بهترین filling mode پشتیبانی شده با debug اطلاعات"""
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info is None:
            print(f"❌ Symbol {self.symbol} not found")
            return mt5.ORDER_FILLING_IOC
            
        filling_mode = symbol_info.filling_mode
        
        # نمایش اطلاعات debug
        print(f"🔍 Symbol filling mode: {filling_mode}")
        print(f"🔍 FOK support (bit 1): {bool(filling_mode & 1)}")  # اصلاح شده
        print(f"🔍 IOC support (bit 2): {bool(filling_mode & 2)}")  # اصلاح شده
        print(f"🔍 RETURN support (bit 0): {filling_mode == 0}")     # اضافه شده
        
        # ترتیب اولویت filling modes - اصلاح شده
        if filling_mode & 2:  # IOC = bit 2
            print("✅ Using ORDER_FILLING_IOC")
            return mt5.ORDER_FILLING_IOC
        elif filling_mode & 1:  # FOK = bit 1
            print("✅ Using ORDER_FILLING_FOK")
            return mt5.ORDER_FILLING_FOK
        else:  # RETURN = 0
            print("✅ Using ORDER_FILLING_RETURN")
            return mt5.ORDER_FILLING_RETURN
    
    def test_filling_modes(self):
        """تست تمام filling modes برای تشخیص پشتیبانی"""
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            return None
            
        print(f"📊 Testing filling modes for {self.symbol}:")
        print(f"   Filling mode value: {symbol_info.filling_mode}")
        
        # تست هر filling mode با bit صحیح
        modes = [
            (0, "RETURN", mt5.ORDER_FILLING_RETURN),
            (1, "FOK", mt5.ORDER_FILLING_FOK),
            (2, "IOC", mt5.ORDER_FILLING_IOC)
        ]
        
        for bit_value, mode_name, mt5_constant in modes:
            if bit_value == 0 and symbol_info.filling_mode == 0:
                print(f"   ✅ {mode_name} ({mt5_constant}) - Supported")
            elif bit_value > 0 and (symbol_info.filling_mode & bit_value):
                print(f"   ✅ {mode_name} ({mt5_constant}) - Supported")
            else:
                print(f"   ❌ {mode_name} ({mt5_constant}) - Not supported")
        
        return symbol_info.filling_mode
    
    def try_all_filling_modes(self, request):
        """تست تمام filling modes تا یکی کار کند"""
        # ترتیب اولویت برای تست
        filling_modes = [
            mt5.ORDER_FILLING_IOC,
            mt5.ORDER_FILLING_FOK,
            mt5.ORDER_FILLING_RETURN
        ]
        
        for filling_mode in filling_modes:
            request_copy = request.copy()
            request_copy["type_filling"] = filling_mode
            
            print(f"🔄 Trying filling mode: {filling_mode}")
            result = mt5.order_send(request_copy)
            
            if result and result.retcode == 10009:
                print(f"✅ Success with filling mode: {filling_mode}")
                return result
            elif result:
                print(f"❌ Failed with filling mode {filling_mode}: {result.comment} (code: {result.retcode})")
        
        return None
    
    def open_sell_position(self, price, sl, tp, comment=""):
        """باز کردن پوزیشن فروش با تست تمام filling modes"""
        iran_time = self.get_iran_time()
        comment_with_time = f"{comment} {iran_time.strftime('%H:%M')}"
        
        # دریافت قیمت فعلی برای validation
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return None
        
        # ساخت request اولیه
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_SELL,
            "price": tick.bid,
            "sl": sl,
            "tp": tp,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": comment_with_time,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        
        print(f"📤 Sending SELL order:")
        print(f"   Symbol: {self.symbol}")
        print(f"   Volume: {self.lot}")
        print(f"   Price: {tick.bid}")
        print(f"   SL: {sl}")
        print(f"   TP: {tp}")
        print(f"   Deviation: {self.deviation}")
        
        # تست با تمام filling modes
        result = self.try_all_filling_modes(request)
        
        if result and result.retcode == 10009:
            print(f"✅ SELL order successful: ticket {result.order}")
        else:
            print(f"❌ All filling modes failed")
        
        return result
    
    def open_buy_position(self, price, sl, tp, comment=""):
        """باز کردن پوزیشن خرید با تست تمام filling modes"""
        iran_time = self.get_iran_time()
        comment_with_time = f"{comment} {iran_time.strftime('%H:%M')}"
        
        # دریافت قیمت فعلی برای validation
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return None
        
        # ساخت request اولیه
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "sl": sl,
            "tp": tp,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": comment_with_time,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        
        print(f"📤 Sending BUY order:")
        print(f"   Symbol: {self.symbol}")
        print(f"   Volume: {self.lot}")
        print(f"   Price: {tick.ask}")
        print(f"   SL: {sl}")
        print(f"   TP: {tp}")
        print(f"   Deviation: {self.deviation}")
        
        # تست با تمام filling modes
        result = self.try_all_filling_modes(request)
        
        if result and result.retcode == 10009:
            print(f"✅ BUY order successful: ticket {result.order}")
        else:
            print(f"❌ All filling modes failed")
        
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
    
    def check_trading_conditions(self):
        """بررسی شرایط معاملاتی"""
        # بررسی اتصال
        if not mt5.terminal_info():
            return False, "MT5 terminal not connected"
        
        # بررسی symbol
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            return False, f"Symbol {self.symbol} not found"
        
        if not symbol_info.visible:
            mt5.symbol_select(self.symbol, True)
        
        # بررسی AutoTrading
        terminal = mt5.terminal_info()
        if not terminal.trade_allowed:
            return False, "AutoTrading disabled in terminal"
        
        # بررسی حساب
        account = mt5.account_info()
        if not account:
            return False, "Account info not available"
        
        if not account.trade_allowed:
            return False, "Trading not allowed on account"
        
        return True, "All conditions OK"
    
    def check_symbol_properties(self):
        """بررسی جزئیات symbol برای debugging"""
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            print(f"❌ Symbol {self.symbol} not found")
            return
        
        print(f"📊 Symbol Properties for {self.symbol}:")
        print(f"   Visible: {symbol_info.visible}")
        print(f"   Select: {symbol_info.select}")
        print(f"   Trade Mode: {symbol_info.trade_mode}")
        print(f"   Trade Execution: {symbol_info.trade_exemode}")
        print(f"   Filling Mode: {symbol_info.filling_mode}")
        print(f"   Trade Stops Level: {symbol_info.trade_stops_level}")
        print(f"   Volume Min: {symbol_info.volume_min}")
        print(f"   Volume Max: {symbol_info.volume_max}")
        print(f"   Volume Step: {symbol_info.volume_step}")
        print(f"   Point: {symbol_info.point}")
        print(f"   Digits: {symbol_info.digits}")
        
        # تنظیم symbol اگر visible نیست
        if not symbol_info.visible:
            print("🔧 Making symbol visible...")
            if mt5.symbol_select(self.symbol, True):
                print("✅ Symbol is now visible")
            else:
                print("❌ Failed to make symbol visible")
    
    def calculate_valid_stops(self, entry_price, sl_price, tp_price, order_type):
        """محاسبه stop loss و take profit معتبر با در نظر گیری stops level"""
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            return sl_price, tp_price
        
        # دریافت stops level (حداقل فاصله از قیمت فعلی)
        stops_level = symbol_info.trade_stops_level
        point = symbol_info.point
        
        # محاسبه حداقل فاصله بر حسب point
        min_distance = stops_level * point
        
        print(f"🔍 Stops Level: {stops_level} points ({min_distance:.5f} price)")
        
        # برای BUY orders
        if order_type == mt5.ORDER_TYPE_BUY:
            # SL باید کمتر از entry باشد و حداقل فاصله را رعایت کند
            min_sl = entry_price - min_distance
            if sl_price > min_sl:
                sl_price = min_sl
                print(f"🔧 SL adjusted to: {sl_price:.5f}")
            
            # TP باید بیشتر از entry باشد و حداقل فاصله را رعایت کند
            min_tp = entry_price + min_distance
            if tp_price < min_tp:
                tp_price = min_tp
                print(f"🔧 TP adjusted to: {tp_price:.5f}")
        
        # برای SELL orders
        elif order_type == mt5.ORDER_TYPE_SELL:
            # SL باید بیشتر از entry باشد و حداقل فاصله را رعایت کند
            max_sl = entry_price + min_distance
            if sl_price < max_sl:
                sl_price = max_sl
                print(f"🔧 SL adjusted to: {sl_price:.5f}")
            
            # TP باید کمتر از entry باشد و حداقل فاصله را رعایت کند
            max_tp = entry_price - min_distance
            if tp_price > max_tp:
                tp_price = max_tp
                print(f"🔧 TP adjusted to: {tp_price:.5f}")
        
        return sl_price, tp_price
    
    def get_best_filling_mode(self):
        """تشخیص بهترین filling mode با تست واقعی"""
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            return mt5.ORDER_FILLING_IOC
        
        # ترتیب اولویت برای تست
        modes_to_test = []
        
        # بررسی پشتیبانی bit-wise
        filling_mode = symbol_info.filling_mode
        
        if filling_mode & 1:  # FOK supported
            modes_to_test.append(mt5.ORDER_FILLING_FOK)
        if filling_mode & 2:  # IOC supported  
            modes_to_test.append(mt5.ORDER_FILLING_IOC)
        if filling_mode == 0:  # Return supported
            modes_to_test.append(mt5.ORDER_FILLING_RETURN)
        
        # اگر هیچ mode تشخیص داده نشد، همه را تست کن
        if not modes_to_test:
            modes_to_test = [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN]
        
        print(f"🧪 Testing filling modes: {modes_to_test}")
        return modes_to_test[0] if modes_to_test else mt5.ORDER_FILLING_IOC
    
    def open_sell_position(self, price, sl, tp, comment=""):
        """باز کردن پوزیشن فروش با بررسی دقیق stops"""
        iran_time = self.get_iran_time()
        comment_with_time = f"{comment} {iran_time.strftime('%H:%M')}"
        
        # دریافت قیمت فعلی
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            print("❌ Unable to get current tick")
            return None
        
        # استفاده از bid price برای SELL
        entry_price = tick.bid
        
        # تنظیم stops معتبر
        sl_adjusted, tp_adjusted = self.calculate_valid_stops(
            entry_price, sl, tp, mt5.ORDER_TYPE_SELL
        )
        
        # دریافت بهترین filling mode
        filling_mode = self.get_best_filling_mode()
        
        # ساخت request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_SELL,
            "price": entry_price,
            "sl": sl_adjusted,
            "tp": tp_adjusted,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": comment_with_time,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        print(f"📤 Sending SELL order:")
        print(f"   Entry Price: {entry_price:.5f}")
        print(f"   SL (Original/Adjusted): {sl:.5f} / {sl_adjusted:.5f}")
        print(f"   TP (Original/Adjusted): {tp:.5f} / {tp_adjusted:.5f}")
        print(f"   Filling Mode: {filling_mode}")
        
        # ارسال order
        result = mt5.order_send(request)
        
        if result and result.retcode == 10009:
            print(f"✅ SELL order successful: ticket {result.order}")
            return result
        elif result:
            print(f"❌ SELL order failed: {result.comment} (code: {result.retcode})")
            
            # تست با filling modes دیگر در صورت نیاز
            if result.retcode == 10030:  # Unsupported filling mode
                print("🔄 Trying alternative filling modes...")
                
                alternative_modes = [mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK]
                
                for alt_mode in alternative_modes:
                    if alt_mode != filling_mode:
                        request["type_filling"] = alt_mode
                        print(f"🔄 Trying filling mode: {alt_mode}")
                        
                        result2 = mt5.order_send(request)
                        if result2 and result2.retcode == 10009:
                            print(f"✅ SELL success with mode {alt_mode}: ticket {result2.order}")
                            return result2
                        elif result2:
                            print(f"❌ Failed with mode {alt_mode}: {result2.comment} (code: {result2.retcode})")
        
        return result
    
    def open_buy_position(self, price, sl, tp, comment=""):
        """باز کردن پوزیشن خرید با بررسی دقیق stops"""
        iran_time = self.get_iran_time()
        comment_with_time = f"{comment} {iran_time.strftime('%H:%M')}"
        
        # دریافت قیمت فعلی
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            print("❌ Unable to get current tick")
            return None
        
        # استفاده از ask price برای BUY
        entry_price = tick.ask
        
        # تنظیم stops معتبر
        sl_adjusted, tp_adjusted = self.calculate_valid_stops(
            entry_price, sl, tp, mt5.ORDER_TYPE_BUY
        )
        
        # دریافت بهترین filling mode
        filling_mode = self.get_best_filling_mode()
        
        # ساخت request
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_BUY,
            "price": entry_price,
            "sl": sl_adjusted,
            "tp": tp_adjusted,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": comment_with_time,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_mode,
        }
        
        print(f"📤 Sending BUY order:")
        print(f"   Entry Price: {entry_price:.5f}")
        print(f"   SL (Original/Adjusted): {sl:.5f} / {sl_adjusted:.5f}")
        print(f"   TP (Original/Adjusted): {tp:.5f} / {tp_adjusted:.5f}")
        print(f"   Filling Mode: {filling_mode}")
        
        # ارسال order
        result = mt5.order_send(request)
        
        if result and result.retcode == 10009:
            print(f"✅ BUY order successful: ticket {result.order}")
            return result
        elif result:
            print(f"❌ BUY order failed: {result.comment} (code: {result.retcode})")
            
            # تست با filling modes دیگر در صورت نیاز
            if result.retcode == 10030:  # Unsupported filling mode
                print("🔄 Trying alternative filling modes...")
                
                alternative_modes = [mt5.ORDER_FILLING_RETURN, mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK]
                
                for alt_mode in alternative_modes:
                    if alt_mode != filling_mode:
                        request["type_filling"] = alt_mode
                        print(f"🔄 Trying filling mode: {alt_mode}")
                        
                        result2 = mt5.order_send(request)
                        if result2 and result2.retcode == 10009:
                            print(f"✅ BUY success with mode {alt_mode}: ticket {result2.order}")
                            return result2
                        elif result2:
                            print(f"❌ Failed with mode {alt_mode}: {result2.comment} (code: {result2.retcode})")
        
        return result
    
    def check_trading_limits(self):
        """بررسی محدودیت‌های معاملاتی broker"""
        symbol_info = mt5.symbol_info(self.symbol)
        if not symbol_info:
            return
        
        print(f"📋 Trading Limits for {self.symbol}:")
        print(f"   Min Volume: {symbol_info.volume_min}")
        print(f"   Max Volume: {symbol_info.volume_max}")
        print(f"   Volume Step: {symbol_info.volume_step}")
        print(f"   Stops Level: {symbol_info.trade_stops_level} points")
        print(f"   Freeze Level: {symbol_info.trade_freeze_level} points")
        print(f"   Point Value: {symbol_info.point}")
        print(f"   Digits: {symbol_info.digits}")
        print(f"   Spread: {symbol_info.spread} points")
    
    def get_positions(self):
        """دریافت پوزیشن‌های باز"""
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            return positions
        except Exception as e:
            print(f"❌ Error getting positions: {e}")
            return None