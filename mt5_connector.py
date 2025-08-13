import MetaTrader5 as mt5
import pandas as pd
import pytz
from datetime import datetime, time
from metatrader5_config import MT5_CONFIG

RET_OK = 10009  # mt5.TRADE_RETCODE_DONE

class MT5Connector:
    def __init__(self):
        cfg = MT5_CONFIG
        self.symbol = cfg['symbol']
        self.lot = cfg['lot_size']
        self.deviation = cfg['deviation']
        self.magic = cfg['magic_number']
        self.max_spread = cfg['max_spread']
        self.min_balance = cfg['min_balance']
        self.trading_hours = cfg['trading_hours']
        self.iran_tz = pytz.timezone('Asia/Tehran')
        self.utc_tz = pytz.UTC

    # ---------- Time / Session ----------
    def get_iran_time(self):
        return datetime.now(self.utc_tz).astimezone(self.iran_tz)

    def is_trading_time(self):
        start = time.fromisoformat(self.trading_hours['start'])
        end = time.fromisoformat(self.trading_hours['end'])
        now_t = self.get_iran_time().time()
        if start <= end:
            return start <= now_t <= end
        # window passes midnight
        return now_t >= start or now_t <= end

    def check_weekend(self):
        # Forex shuts late Fri (server time). Simplified: block Saturday/Sunday
        wd = self.get_iran_time().weekday()  # Monday=0
        return wd not in (5, 6)  # 5=Saturday,6=Sunday (adjust if broker different)

    def can_trade(self):
        if not self.check_weekend():
            return False, "Weekend - trading disabled"
        if not self.is_trading_time():
            return False, "Outside configured trading hours"
        ti = mt5.terminal_info()
        if not ti:
            return False, "Terminal info unavailable"
        if not ti.trade_allowed:
            return False, "Terminal AutoTrading disabled"
        acc = mt5.account_info()
        if not acc:
            return False, "Account info unavailable"
        if acc.balance < self.min_balance:
            return False, f"Insufficient balance < {self.min_balance}"
        return True, "Trading is allowed"

    # ---------- Initialization ----------
    def initialize(self):
        if not mt5.initialize():
            print("❌ MT5 initialize failed:", mt5.last_error())
            return False
        acc = mt5.account_info()
        if acc and acc.balance < self.min_balance:
            print(f"❌ Balance {acc.balance} < min {self.min_balance}")
            return False
        print("✅ MT5 connection established")
        return True

    def shutdown(self):
        mt5.shutdown()

    # ---------- Data ----------
    def get_live_price(self):
        tick = mt5.symbol_info_tick(self.symbol)
        if not tick:
            return None
        spread = (tick.ask - tick.bid) * 10000
        if spread > self.max_spread:
            print(f"⚠️ Spread {spread:.1f} > max {self.max_spread}")
        utc_time = datetime.fromtimestamp(tick.time, tz=self.utc_tz)
        return {
            'bid': tick.bid,
            'ask': tick.ask,
            'spread': spread,
            'time': utc_time.astimezone(self.iran_tz),
            'utc_time': utc_time
        }

    def get_historical_data(self, timeframe=mt5.TIMEFRAME_M1, count=500):
        rates = mt5.copy_rates_from_pos(self.symbol, timeframe, 0, count)
        if rates is None:
            return None
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True).dt.tz_convert(self.iran_tz)
        df.set_index('time', inplace=True)
        df = df.rename(columns={'tick_volume': 'volume'})
        df['timestamp'] = df.index
        return df

    # ---------- Broker capability helpers ----------
    def test_filling_modes(self):
        info = mt5.symbol_info(self.symbol)
        if not info:
            print("Symbol info not available")
            return None
        print(f"Filling mode raw: {info.filling_mode}")
        return info.filling_mode

    def get_supported_filling_mode(self):
        info = mt5.symbol_info(self.symbol)
        if not info:
            return None
        # Prefer IOC, then FOK, else RETURN
        if info.filling_mode & mt5.ORDER_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        if info.filling_mode & mt5.ORDER_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

    # ---------- Stop validation ----------
    def calculate_valid_stops(self, entry_price, sl_price, tp_price, order_type):
        info = mt5.symbol_info(self.symbol)
        if not info:
            return None, None
        point = info.point
        min_dist = max(info.trade_stops_level * point, 3 * point)
        def norm(p):
            digits = info.digits
            return float(f"{p:.{digits}f}")
        adjusted = False
        if order_type == mt5.ORDER_TYPE_BUY:
            # SL must be below entry, TP above
            if sl_price >= entry_price - min_dist:
                sl_price = entry_price - min_dist
                adjusted = True
            if tp_price <= entry_price + min_dist:
                tp_price = entry_price + min_dist
                adjusted = True
        elif order_type == mt5.ORDER_TYPE_SELL:
            if sl_price <= entry_price + min_dist:
                sl_price = entry_price + min_dist
                adjusted = True
            if tp_price >= entry_price - min_dist:
                tp_price = entry_price - min_dist
                adjusted = True
        sl_price = norm(sl_price)
        tp_price = norm(tp_price)
        return sl_price, tp_price

    # ---------- Order sending core ----------
    def try_all_filling_modes(self, request):
        for mode in (mt5.ORDER_FILLING_IOC,
                     mt5.ORDER_FILLING_FOK,
                     mt5.ORDER_FILLING_RETURN):
            req = dict(request)
            req["type_filling"] = mode
            result = mt5.order_send(req)
            if result and result.retcode in (RET_OK, mt5.TRADE_RETCODE_PLACED):
                return result
        return result  # return last attempt

    # ---------- Trading ----------
    def open_buy_position(self, tick, sl, tp, comment=""):
        if not tick:
            print("No tick data")
            return None
        entry = tick.ask
        sl_adj, tp_adj = self.calculate_valid_stops(entry, sl, tp, mt5.ORDER_TYPE_BUY)
        if sl_adj is None:
            return None
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_BUY,
            "price": entry,
            "sl": sl_adj,
            "tp": tp_adj,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        print(f"📤 BUY {self.symbol} @ {entry} SL={sl_adj} TP={tp_adj}")
        result = self.try_all_filling_modes(request)
        return result

    def open_sell_position(self, tick, sl, tp, comment=""):
        if not tick:
            print("No tick data")
            return None
        entry = tick.bid
        sl_adj, tp_adj = self.calculate_valid_stops(entry, sl, tp, mt5.ORDER_TYPE_SELL)
        if sl_adj is None:
            return None
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": self.symbol,
            "volume": self.lot,
            "type": mt5.ORDER_TYPE_SELL,
            "price": entry,
            "sl": sl_adj,
            "tp": tp_adj,
            "deviation": self.deviation,
            "magic": self.magic,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
        }
        print(f"📤 SELL {self.symbol} @ {entry} SL={sl_adj} TP={tp_adj}")
        result = self.try_all_filling_modes(request)
        return result

    def close_all_positions(self):
        positions = mt5.positions_get(symbol=self.symbol)
        if positions is None:
            return
        for pos in positions:
            tick = mt5.symbol_info_tick(self.symbol)
            if not tick:
                continue
            if pos.type == mt5.ORDER_TYPE_BUY:
                price = tick.bid  # close BUY at bid with SELL
                order_type = mt5.ORDER_TYPE_SELL
            else:
                price = tick.ask  # close SELL at ask with BUY
                order_type = mt5.ORDER_TYPE_BUY
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": pos.volume,
                "type": order_type,
                "position": pos.ticket,
                "price": price,
                "deviation": self.deviation,
                "magic": self.magic,
                "comment": "Close position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            mt5.order_send(request)

    def get_positions(self):
        return mt5.positions_get(symbol=self.symbol)

    # ---------- Diagnostic stubs (used by main/tests) ----------
    def check_trading_limits(self):
        return True

    def check_account_trading_permissions(self):
        return True

    def check_market_state(self):
        return True

    def check_symbol_properties(self):
        info = mt5.symbol_info(self.symbol)
        if not info:
            print("Symbol info not found")
            return
        if not info.visible:
            mt5.symbol_select(self.symbol, True)