# Profit Pilot Backend

FastAPI service that backtests strategies against your Postgres market-data
DB and serves results to the Strategy screen in the frontend.

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in DATABASE_URL
uvicorn api.main:app --reload --port 8000
```

## Status

- **Blaze Butterfly** (`strategies/blaze_butterfly.py`) — implemented, backtest-only.
- **Titan Condor** (`strategies/titan_condor.py`) — implemented, backtest-only; use strategy id `titan-condor`.
- Strategies 1–3 — not yet ported; add them as new files in `strategies/`
  implementing the `OptionsStrategy` interface in `strategies/base.py`, then
  register them in `api/main.py`'s `STRATEGIES` dict.

## Assumptions to verify against your actual schema

- `instruments.instrument_type` values: `'PE'` / `'CE'` for options,
  `'INDEX'` for the underlying spot row also carried in `candles_1min`.
  If your ingestion uses different values, only `db/repository.py` needs
  updating.
- Blaze deployed margin = INR 85,000 per lot-unit, configurable via `BlazeButterflyStrategy(margin_per_unit=..., units=...)`.
- Titan deployed margin defaults to INR 30,000 per primary lot, with 10 primary lots and a 1-lot additional call hedge.
- Titan contract lot size uses the DB value, with fallback 75 before 2026-01-01 and 65 from 2026-01-01 onward.
- No event-day filter yet — deliberately deferred per the strategy doc's own
  recommendation, to see how much it would have mattered historically.

## Not yet built

- Forward-testing / live execution via Angel One SmartAPI.
- Persisting backtest runs (currently in-memory cache, resets on restart).
- Auth on the API (fine for local dev; needed before any public deploy).
