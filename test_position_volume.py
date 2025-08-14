# tests/test_position_sizing.py
import types
import pytest

#
# سناریو (EURUSD):
# balance=1000 ، risk=1% => risk_money=10
# BUY: ask=1.10000، SL=1.09700 (30 pip)
# SELL: bid=1.10000، SL=1.10300 (30 pip)
# spread=1 pip => ask-bid=0.00010
# tick_size=0.00001 ، tick_value=1.0 $/tick/lot => 1 pip = 10$
# commission per-side=3.5$ => round-turn=7$
# total_cost_per_lot = 300 (price) + 10 (spread) + 7 (commission) = 317$
# lot_raw = 10 / 317 = 0.03155... -> با step=0.01 => 0.03
#
EXPECTED_VOL = 0.03
RISK_FRAC = 0.01  # 1% به صورت کسر


class DummyResult:
    def __init__(self, retcode, price=None, volume=None, order=123):
        self.retcode = retcode
        self.price = price
        self.volume = volume
        self.order = order
        self.comment = "OK"


@pytest.fixture
def mock_mt5(monkeypatch):
    """یک MetaTrader5 ساختگی می‌سازیم و همه چیز را mock می‌کنیم."""
    mt5 = types.SimpleNamespace()

    # ثابت‌ها
    mt5.TRADE_RETCODE_DONE = 10009
    mt5.TRADE_RETCODE_PLACED = 10008
    mt5.TRADE_ACTION_DEAL = 1
    mt5.ORDER_TYPE_BUY = 0
    mt5.ORDER_TYPE_SELL = 1
    mt5.ORDER_TIME_GTC = 0
    mt5.ORDER_FILLING_IOC = 1
    mt5.ORDER_FILLING_FOK = 2
    mt5.ORDER_FILLING_RETURN = 4

    # اطلاعات حساب/ترمینال
    acc = types.SimpleNamespace(balance=1000.0, equity=1000.0, margin_free=1000.0)
    mt5.account_info = lambda: acc
    term = types.SimpleNamespace(trade_allowed=True)
    mt5.terminal_info = lambda: term

    # اطلاعات نماد
    info = types.SimpleNamespace(
        point=0.00001,
        digits=5,
        tick_size=0.00001,
        tick_value=1.0,          # 1$ per tick per lot
        trade_stops_level=0,
        volume_step=0.01,
        volume_min=0.01,
        volume_max=100.0,
        filling_mode=mt5.ORDER_FILLING_IOC | mt5.ORDER_FILLING_FOK | mt5.ORDER_FILLING_RETURN,
        visible=True,
    )
    mt5.symbol_info = lambda symbol: info
    mt5.symbol_select = lambda symbol, sel: True

    # تیک قیمت (اسپرد = 1 pip)
    class _Tick:
        def __init__(self, bid, ask, t):
            self.bid = bid
            self.ask = ask
            self.time = t

    tick = _Tick(1.09990, 1.10000, 1_700_000_000)
    mt5.symbol_info_tick = lambda symbol: tick

    # تاریخچه (در این تست استفاده نمی‌شود)
    mt5.copy_rates_from_pos = lambda symbol, tf, start_pos, count: []

    # init/shutdown
    mt5.initialize = lambda: True
    mt5.shutdown = lambda: None
    mt5.last_error = lambda: (0, "OK")

    # پوزیشن‌ها (در این تست استفاده نمی‌شود)
    mt5.positions_get = lambda **kw: []

    # محاسبه مارجین (تقریب خطی با حجم)
    mt5.order_calc_margin = lambda order_type, symbol, volume, price: 50.0 * float(volume)

    # order_send: تلاش اول fail، بعدی succeed. ضمن اینکه volume درخواست را در نتیجه کپی می‌کنیم.
    call_state = {"calls": 0}
    def _order_send(request):
        call_state["calls"] += 1
        vol = request.get("volume")
        price = request.get("price")
        if call_state["calls"] == 1:
            return DummyResult(retcode=99999, price=price, volume=vol)
        return DummyResult(retcode=mt5.TRADE_RETCODE_DONE, price=price, volume=vol)
    mt5.order_send = _order_send

    return mt5


@pytest.fixture
def connector(monkeypatch, mock_mt5):
    """ماژول mt5_connector را لود و mt5 و MT5_CONFIG را درونش patch می‌کنیم."""
    import importlib
    m = importlib.import_module("mt5_connector")

    # تزریق mt5 ساختگی
    monkeypatch.setattr(m, "mt5", mock_mt5, raising=True)

    # پچ کانفیگ (مخصوص EURUSD و کمیسیون per-side)
    cfg = dict(getattr(m, "MT5_CONFIG", {}))
    cfg.update({
        "symbol": "EURUSD",
        "lot_size": 0.01,
        "deviation": 20,
        "magic_number": 234000,
        "max_spread": 3.0,  # پیپ
        "min_balance": 100,
        "trading_hours": {"start": "00:00:00", "end": "23:59:59"},
        "commission_per_lot_side": 3.5,  # per-side => round-turn=7$
    })
    monkeypatch.setattr(m, "MT5_CONFIG", cfg, raising=True)

    c = m.MT5Connector()
    assert c.initialize() is True
    return c


def _almost(a, b, tol=1e-9):
    return abs(a - b) <= tol


def test_open_buy_position_risk_sizing(connector):
    mt5 = __import__("mt5_connector").mt5
    tick = mt5.symbol_info_tick(connector.symbol)

    entry = tick.ask
    sl = entry - 0.00300  # 30 pip پایین‌تر
    tp = entry + 0.00600  # کافی است از min_dist عبور کند

    result = connector.open_buy_position(
        tick=tick,
        sl=sl,
        tp=tp,
        comment="TEST BUY",
        volume=None,
        risk_pct=RISK_FRAC,
    )
    assert result is not None
    assert result.retcode == mt5.TRADE_RETCODE_DONE

    # حجم واقعی ارسال‌شده به order_send باید همان EXPECTED_VOL باشد (بعد از نرمال‌سازی step)
    sent_vol = result.volume
    assert _almost(round(sent_vol, 2), EXPECTED_VOL), f"BUY vol expected {EXPECTED_VOL}, got {sent_vol}"


def test_open_sell_position_risk_sizing(connector):
    mt5 = __import__("mt5_connector").mt5
    tick = mt5.symbol_info_tick(connector.symbol)

    entry = tick.bid
    sl = entry + 0.00300  # 30 pip بالاتر
    tp = entry - 0.00600

    result = connector.open_sell_position(
        tick=tick,
        sl=sl,
        tp=tp,
        comment="TEST SELL",
        volume=None,
        risk_pct=RISK_FRAC,
    )
    assert result is not None
    assert result.retcode == mt5.TRADE_RETCODE_DONE

    sent_vol = result.volume
    assert _almost(round(sent_vol, 2), EXPECTED_VOL), f"SELL vol expected {EXPECTED_VOL}, got {sent_vol}"
