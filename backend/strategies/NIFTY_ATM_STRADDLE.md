# NIFTY ATM CE + PE Long Straddle

Strategy ID: `NK CAS NIFTY_ATM_STRADDLE_2PM_V1`

The executable rule engine is in `nifty_atm_straddle.py`. It accepts timestamped observations and returns adapter-neutral `BUY`/`SELL` actions. The engine locks ATM only when entry is valid and uses the locked strike thereafter.

Eligibility is separate from the state machine: backtest accepts dates from 03-Aug-2026 onward; deploy additionally requires an actual expiry-calendar result. Lot size, option contract lookup, India VIX, and execution are intentionally adapter responsibilities.

Because 1-minute OHLC data cannot establish whether opposing levels were crossed first, a backtest adapter must define and document an intrabar policy (or use tick data).
