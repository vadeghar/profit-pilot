-- Adds option Greeks + IV columns directly to candles_1min.
--
-- candles_1min is declaratively partitioned by month (PARTITION BY RANGE (ts)).
-- ALTER TABLE on the parent propagates to every existing partition automatically,
-- and any partition created later (CREATE TABLE ... PARTITION OF candles_1min ...)
-- inherits these columns with no further DDL needed.
--
-- ADD COLUMN without a DEFAULT is metadata-only in Postgres 11+ (no table rewrite,
-- no long-held lock), so this is safe to run against the live table.
--
-- All new columns are NULL for INDEX/EQ/FUT rows and for CE/PE rows not yet
-- processed by the Greeks pipeline. NULL storage cost is negligible (a bit in
-- the row's null bitmap), so there is no meaningful space penalty for the
-- non-option rows that will never populate these columns.

ALTER TABLE public.candles_1min
    ADD COLUMN underlying_price     numeric(12,4),   -- spot/index close used for the calc
    ADD COLUMN time_to_expiry_yrs   numeric(10,8),    -- T used, stored for audit/debugging
    ADD COLUMN iv                   numeric(8,4),     -- solved implied volatility (e.g. 0.1850 = 18.50%)
    ADD COLUMN delta                numeric(8,6),
    ADD COLUMN gamma                numeric(10,8),
    ADD COLUMN theta                numeric(10,4),
    ADD COLUMN vega                 numeric(10,4),
    ADD COLUMN rho                  numeric(10,4),
    ADD COLUMN greeks_model_version text,             -- e.g. 'bs_spot_v1', lets you re-run with a new model without ambiguity
    ADD COLUMN greeks_skip_reason   text,             -- e.g. 'no_time_value', 'solver_failed' -- NULL means either not-yet-processed or successfully computed
    ADD COLUMN greeks_computed_at   timestamp with time zone;

-- Partial index to quickly find CE/PE rows still needing a Greeks pass
-- (backfill progress tracking + the incremental hook's "catch up on gaps" query).
CREATE INDEX IF NOT EXISTS idx_candles_1min_greeks_pending
    ON public.candles_1min (instrument_id, ts)
    WHERE greeks_computed_at IS NULL;
