#!/usr/bin/env python3
"""CLI to run the lightweight backtester over an OHLC CSV and write trades CSV + summary."""
import argparse
from pathlib import Path
import json
import pandas as pd

from engine import BacktestEngine, BacktestConfig, load_ohlc_csv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="Path to OHLC CSV with columns timestamp,open,high,low,close")
    ap.add_argument("--symbol", default="EURUSD")
    ap.add_argument("--threshold", type=int, default=6, help="leg threshold in points")
    ap.add_argument("--window", type=int, default=100)
    ap.add_argument("--lookahead", type=int, default=20)
    ap.add_argument("--rr", type=float, default=1.2)
    ap.add_argument("--minleg", type=int, default=4, help="minimum leg distance in points")
    ap.add_argument("--scale", type=int, default=100000, help="price scale for points (5-digit FX=100000)")
    ap.add_argument("--outdir", default="backtest/results")
    ap.add_argument("--initial-balance", type=float, default=10000.0, help="starting balance for equity simulation")
    ap.add_argument("--risk-pct", type=float, default=0.01, help="risk per trade as fraction of equity (e.g. 0.01 = 1%)")
    args = ap.parse_args()

    cfg = BacktestConfig(
        symbol=args.symbol,
        threshold_points=args.threshold,
        window_size=args.window,
        lookahead=args.lookahead,
        rr=args.rr,
        min_leg_distance_points=args.minleg,
        price_scale=args.scale,
    initial_balance=args.initial_balance,
    risk_pct=args.risk_pct,
    )

    df = load_ohlc_csv(args.csv)
    engine = BacktestEngine(cfg)
    trades, summary = engine.run(df)
    trades_df = engine.to_dataframe(trades)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.csv).stem
    trades_path = outdir / f"{stem}_trades.csv"
    summary_path = outdir / f"{stem}_summary.json"

    trades_df.to_csv(trades_path, index=False)
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("Backtest summary:")
    for k, v in summary.items():
        print(f"- {k}: {v}")
    print(f"\nSaved trades -> {trades_path}")
    print(f"Saved summary -> {summary_path}")


if __name__ == "__main__":
    main()
