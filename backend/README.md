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
- **Matrix Calendar** (`strategies/matrix_calendar.py`) — implemented, backtest-only.
- Strategies 1–3 — not yet ported; add them as new files in `strategies/`
  implementing the `OptionsStrategy` interface in `strategies/base.py`, then
  register them in `api/main.py`'s `STRATEGIES` dict.

## Matrix Calendar

Strategy 8 is a NIFTY weekly/monthly ratio-calendar setup:

- Monday entry at 15:16.
- Immediate weekly expiry excluded.
- Weekly 23-delta CE/PE shorts, two lots each.
- One 500-point weekly hedge per side.
- One same-strike monthly hedge per side.
- Minimum derived IV of 20%.
- Target 1.5%, stop-loss 2%, and two-day time exit.

See `strategies/MATRIX_CALENDAR.md` for the full rule set and model assumptions.

## Assumptions to verify against your actual schema

- `instruments.instrument_type` values: `'PE'` / `'CE'` for options,
  `'INDEX'` for the underlying spot row also carried in `candles_1min`.
- The expiry calendar uses `underlying = 'NIFTY'` and `expiry_type` values
  `'WEEKLY'` / `'MONTHLY'`.
- Deployed margin and pricing parameters for Matrix Calendar are configurable
  through the `MATRIX_CALENDAR_*` environment variables.
- Historical contract queries intentionally do not require
  `instruments.is_active = true`.
- No event-day filter yet — deliberately deferred for historical research.

## Database performance

`db/sql/002_matrix_calendar_indexes.sql` contains idempotent indexes for:

- Candle lookup by instrument and timestamp.
- Option contract lookup by underlying, type, expiry, and strike.
- Expiry and holiday calendar lookup.

Review existing indexes and run `EXPLAIN ANALYZE` before applying this migration
to a production database. For very large tables, use a non-transactional
`CREATE INDEX CONCURRENTLY` rollout.

## Not yet built

- Forward-testing / live execution via Angel One SmartAPI.
- Persisting backtest runs (currently in-memory cache, resets on restart).
- Auth on the API (fine for local dev; needed before any public deploy).
- Brokerage, taxes, and slippage modeling.
