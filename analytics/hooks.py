import os, csv
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]  # trading_project2
RAW_DIR = ROOT / "trading-analytics-logger" / "data" / "raw"
MARKET_DIR = RAW_DIR / "market"
SIGNAL_DIR = RAW_DIR / "signals"
TRADE_DIR  = RAW_DIR / "trades"

for d in (MARKET_DIR, SIGNAL_DIR, TRADE_DIR):
    d.mkdir(parents=True, exist_ok=True)

def _iran_now_str():
    tehran = timezone(timedelta(hours=3, minutes=30))
    return datetime.now(tehran).strftime("%Y-%m-%d %H:%M:%S")

def _utc_now_str():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

def _append_csv(fp: Path, headers: list[str], row: dict):
    file_exists = fp.exists()
    with fp.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        if not file_exists:
            w.writeheader()
        w.writerow(row)

def log_market(symbol: str, bid: float, ask: float, last: Optional[float], point: float, digits: int, source="mt5", session="bot"):
    # 1 pip = 0.01 for 2/3 digits, else 0.0001
    pip = 0.01 if digits in (2,3) else 0.0001
    spread_points = (ask - bid) / point if (ask and bid and point) else None
    spread_pips = (ask - bid) / pip if (ask and bid) else None
    row = {
        "dt_utc": _utc_now_str(),
        "dt_iran": _iran_now_str(),
        "symbol": symbol,
        "bid": bid, "ask": ask, "last": last,
        "spread_points": spread_points, "spread_pips": spread_pips,
        "point": point, "digits": digits,
        "source": source, "session": session
    }
    fp = MARKET_DIR / f"{symbol}_ticks_{datetime.utcnow():%Y-%m-%d}.csv"
    _append_csv(fp, [
        "dt_utc","dt_iran","symbol","bid","ask","last",
        "spread_points","spread_pips","point","digits","source","session"
    ], row)

def log_signal(symbol: str, strategy: str, direction: str, rr: float, entry: float, sl: float, tp: float,
               fib: Optional[dict]=None, confidence: Optional[float]=None, features_json: Optional[str]=None, note: Optional[str]=None):
    fib = fib or {}
    row = {
        "dt_utc": _utc_now_str(),
        "dt_iran": _iran_now_str(),
        "symbol": symbol, "strategy": strategy, "direction": direction, "rr": rr,
        "entry": entry, "sl": sl, "tp": tp,
        "fib_0": fib.get("0.0"), "fib_0705": fib.get("0.705"), "fib_09": fib.get("0.9"), "fib_1": fib.get("1.0"),
        "confidence": confidence, "features_json": features_json, "note": note
    }
    fp = SIGNAL_DIR / f"{symbol}_signals_{datetime.utcnow():%Y-%m-%d}.csv"
    _append_csv(fp, [
        "dt_utc","dt_iran","symbol","strategy","direction","rr","entry","sl","tp",
        "fib_0","fib_0705","fib_09","fib_1","confidence","features_json","note"
    ], row)

def log_trade(symbol: str, side: str, request: dict, result, reason: str=""):
    # result می‌تواند آبجکت MT5 یا dict باشد
    retcode = getattr(result, "retcode", None) if result is not None else None
    order = getattr(result, "order", None) if result is not None else None
    deal = getattr(result, "deal", None) if result is not None else None
    price = getattr(result, "price", None) if result is not None else None
    comment = getattr(result, "comment", None) if result is not None else None
    row = {
        "dt_utc": _utc_now_str(),
        "dt_iran": _iran_now_str(),
        "symbol": symbol, "side": side,
        "req_price": request.get("price"), "req_vol": request.get("volume"),
        "req_deviation": request.get("deviation"), "req_filling": request.get("type_filling"),
        "retcode": retcode, "order": order, "deal": deal,
        "result_price": price, "result_comment": comment,
        "sl": request.get("sl"), "tp": request.get("tp"),
        "magic": request.get("magic"), "reason": reason
    }
    fp = TRADE_DIR / f"{symbol}_trades_{datetime.utcnow():%Y-%m-%d}.csv"
    _append_csv(fp, [
        "dt_utc","dt_iran","symbol","side","req_price","req_vol","req_deviation","req_filling",
        "retcode","order","deal","result_price","result_comment","sl","tp","magic","reason"
    ], row)