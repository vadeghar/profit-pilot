-- Dedicated Greeks table for options candles, linked to candles_1min via a
-- composite foreign key, instead of altering candles_1min directly.
--
-- Why a separate table:
-- - Greeks only apply to CE/PE rows; keeping them off candles_1min avoids
--   mixing option-only derived data into the shared OHLCV fact table used by
--   every instrument type (INDEX/EQ/FUT/CE/PE).
-- - This is populated by a ONE-TIME backfill job, not a live/incremental
--   process. A separate table means the backfill is pure INSERTs (cheap,
--   append-only) rather than UPDATEs against the large partitioned
--   candles_1min table, which would otherwise generate dead tuples via MVCC.
-- - Recomputing later with a different model_version (better vol model, a
--   fixed IV-solver bug, etc.) is just a fresh batch of INSERTs against this
--   table -- zero impact on candles_1min.
--
-- candles_1min's primary key is the composite (instrument_id, ts), which is
-- also the join key here. Postgres 12+ allows a foreign key to reference a
-- partitioned table's primary key directly, so this FK is valid despite
-- candles_1min being partitioned by month.

CREATE TABLE public.option_greeks_1min (
    instrument_id       bigint NOT NULL,
    ts                  timestamp with time zone NOT NULL,
    underlying_price    numeric(12,4) NOT NULL,   -- NIFTY Index close used for the calc
    time_to_expiry_yrs  numeric(10,8) NOT NULL,
    iv                  numeric(8,4),              -- NULL when unsolved -- see skip_reason
    delta               numeric(8,6),
    gamma               numeric(10,8),
    theta               numeric(10,4),
    vega                numeric(10,4),
    rho                 numeric(10,4),
    model_version       text NOT NULL DEFAULT 'bs_spot_v1',
    skip_reason         text,                      -- e.g. 'no_time_value', 'solver_failed'
    computed_at         timestamp with time zone NOT NULL DEFAULT now(),

    CONSTRAINT option_greeks_1min_pkey PRIMARY KEY (instrument_id, ts),

    CONSTRAINT option_greeks_1min_candle_fkey
        FOREIGN KEY (instrument_id, ts)
        REFERENCES public.candles_1min (instrument_id, ts),

    CONSTRAINT option_greeks_1min_instrument_fkey
        FOREIGN KEY (instrument_id)
        REFERENCES public.instruments (id)
);

-- Main read pattern for backtesting: "give me the Greeks time series for
-- this option contract".
CREATE INDEX idx_option_greeks_1min_instrument_ts
    ON public.option_greeks_1min (instrument_id, ts);
