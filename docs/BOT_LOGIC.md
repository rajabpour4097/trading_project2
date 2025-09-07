# Trading Bot Logic Overview

Last updated: 2025-09-07  
Scope: EURUSD swing_fib_v1 strategy on MetaTrader 5

## 1) Files and Roles
- main_metatrader.py
  - Orchestrates the bot loop, builds/updates fib levels, creates trade requests, and manages dynamic risk stages for open positions.
- mt5_connector.py
  - Wraps MetaTrader 5 API (initialize, symbol/tick access, order_send, modify SL/TP, checks).
  - Validates SL/TP distances and broker constraints before sending orders.
- metatrader5_config.py
  - Central configuration for symbol, lot, trading hours, risk management stages, logging.
- analytics.hooks
  - Persists signals, trades, and position stage events to CSV for post-trade analytics.

## 2) Trading Session and Guard Rails
- Trading hours (Iran time) from MT5_CONFIG['trading_hours'] (currently FULL_TIME_IRAN).
- can_trade() checks:
  - Weekend block
  - Within trading hours window
  - Terminal/account trade permissions
  - Minimum balance
  - Optional spread guard in get_live_price() against MT5_CONFIG['max_spread'] (pips)

Note: On BUY we use ask; on SELL we use bid. For floating P/L calculations, current price uses bid for BUY and ask for SELL (correct for mark-to-close).

## 3) Data Pipeline and Swing/Fib Logic
- Pulls historical bars: get_historical_data() with a rolling window.
- Legs are extracted via get_legs(...) -> last 3 legs used.
- get_swing_points(...) detects swing type: bullish/bearish.
- Fibonacci levels are created or updated:
  - For bullish: start = recent high, end = previous leg end; vice versa for bearish.
  - State tracks: fib levels, last swing type, first/second 0.705 touches to confirm a “true_position”.

True position criteria:
- After first touch of 0.705, if the next bar flips status across 0.705, state.true_position becomes True (entry condition is then allowed).

## 4) Entry Construction
- BUY entry price: last_tick.ask
- SELL entry price: last_tick.bid
- SL selection:
  - If price is within 2 pips of fib 0.9, SL = fib 1.0; otherwise SL = fib 0.9.
  - Directional guard: SL must be below entry (BUY) or above entry (SELL).
- Minimum SL distance:
  - main_metatrader.py enforces min_abs_dist = max(2 pips, broker stops_level) before sending.
  - mt5_connector.calculate_valid_stops additionally validates a minimum of 1 pip and correct side; if invalid, it rejects (returns None) and the order is not sent.

TP construction:
- RR = MT5_CONFIG['win_ratio'] (e.g., 1.2)
- TP = entry ± (stop_distance * RR) with the correct sign per side.

Filling mode:
- mt5_connector tries supported modes and falls back to auto/brute-force if needed.

Important:
- Current main uses 2 pips as a local minimum for SL distance. If you require exactly 1 pip minimum, change the local min in main (see Checklist).

## 5) Position Sizing
- Calls open_buy_position/open_sell_position with risk_pct (e.g., 1%).
- The connector resolves final volume:
  - Reads broker min_lot, max_lot, lot_step, and normalizes.
  - If risk-based sizing is enabled, volume ≈ (risk_cash) / (stop_distance * pip_value) then clamped to broker constraints.

Note: Use symbol.trade_contract_size/tick_value or pip_value for accurate cash-to-price conversions.

## 6) Dynamic Risk Management (Stages)
Configured in DYNAMIC_RISK_CONFIG:
- commission_cover (type=commission)
  - Trigger: when floating profit is sufficient to cover estimated commission for the current position volume.
  - Action: move SL to cover-commission price (lock breakeven plus commission), keep TP at base_tp_R (1.2R).
- half_R
  - Trigger: profit_R >= 0.5
  - Action: SL to +0.5R, TP remains 1.2R.
- one_R
  - Trigger: profit_R >= 1.0
  - Action: SL to +1.0R, TP to 1.5R.
- one_half_R
  - Trigger: profit_R >= 1.5
  - Action: SL to +1.5R, TP to 2.0R.

Implementation (main_metatrader.py: manage_open_positions):
- Tracks per-ticket state: entry, initial risk (R), direction, completed stages.
- Computes profit_R from current mark-to-close price vs entry divided by initial risk.
- Commission stage (approximate): triggers when price_profit * volume >= commission_total.
  - Then SL is moved by an offset ≈ commission_total / volume from entry (directional).
- For R-based stages: SL/TP computed from entry ± (R multiples) and applied only if they improve current SL.
- On modification success, logs a position_event row and marks stage as done.

Note: Commission trigger uses a simplified proxy; for accuracy, convert commission to price using contract size/tick_value.

## 7) Logging and Analytics
- Signals: analytics/raw/signals/EURUSD_signals_YYYY-MM-DD.csv
  - Fields include entry, SL suggestion (0.9 vs 1.0), RR, fib levels.
- Trades: analytics/raw/trades_dir/EURUSD_trades_YYYY-MM-DD.csv
  - Includes order request/retcode, result price, SL/TP sent, magic, and risk_abs used.
- Position events: analytics/raw/events/EURUSD_position_events_YYYY-MM-DD.csv
  - open_order/open, stage events (commission_cover, half_R, one_R, ...), current price, profit_R, locked_R, etc.

These provide a full audit trail to verify stages and RR behavior.

## 8) Order Validation and 1-Pip Rule
- mt5_connector.calculate_valid_stops:
  - Ensures SL is on the correct side.
  - Computes pip size: 1 pip = 10 * point for 5- or 3-digit symbols; else 1 * point.
  - Rejects orders if SL distance < 1 pip (no auto-adjustment). Returns None to abort.
- main_metatrader.py currently enforces a local minimum of 2 pips before requesting the trade.

If you require “at least 1 pip” (and allow >1 pip), set main’s min_pip_dist to 1 (see Checklist).

## 9) Error Handling
- All order modifications check retcodes; success when 10009 (TRADE_RETCODE_DONE).
- Filling modes are tried progressively.
- If can_trade() fails, the loop sleeps and retries.
- Exceptions are logged and retried after a short delay.

## 10) Checklist and Known Notes
- Minimum SL distance:
  - Requirement: “reject if < 1 pip; accept if ≥ 1 pip; do not auto-fix.”
  - Current main enforces 2 pips min before send, which is stricter than requested.
  - Action: change min_pip_dist from 2.0 to 1.0 in both BUY/SELL blocks in main_metatrader.py.
- Commission stage accuracy:
  - Current trigger proxy: price_profit * volume >= commission_total.
  - Improvement: use contract_size and tick_value/pip_value for precise conversion of commission USD to price units, then to R.
- Ensure mt5_connector.calculate_valid_stops:
  - Uses the 1-pip check (no automatic SL/TP corrections).
  - Returns None when invalid so open_* functions abort cleanly.
- Spread guard:
  - get_live_price() compares spread in pips to MT5_CONFIG['max_spread'].
  - Confirm pip conversion aligns with the symbol’s digits.
- Risk sizing:
  - Confirm _resolve_volume uses broker min/max/step constraints and stop_distance to target risk_pct.

## 11) How to change main to 1 pip minimum
Search for “min_pip_dist” in main_metatrader.py (BUY/SELL sections) and set to 1.0:
- BUY:
  - min_pip_dist = 1.0
- SELL:
  - min_pip_dist = 1.0

This keeps the broker minimum (stops_level) intact while aligning with your 1-pip minimum policy.

## 12) Validation with Today’s CSVs
- Signals/trades show SLs near 0.9/1.0 with RR=1.2.
- Position events reflect stages; if a stage is missing for a trade, check:
  - profit_R computation (uses mark-to-close price on the correct side),
  - commission stage trigger threshold,
  - whether manage_open_positions() loop was active during the life of the position.

---
Glossary:
- R: Initial risk per trade = |entry - SL| (price distance).
- RR: Reward-to-risk ratio; TP is placed at RR multiples of R.
- Pip: 10 points for 5/3-digit symbols (e.g., EURUSD 5-digit).