-- Matrix Calendar lookup indexes.
-- Apply after inspecting existing indexes; all statements are idempotent.
-- For very large tables, run these outside a transaction with CONCURRENTLY.

CREATE INDEX IF NOT EXISTS ix_instruments_strategy_contract
    ON instruments (underlying_symbol, instrument_type, expiry, strike);

CREATE INDEX IF NOT EXISTS ix_instruments_strategy_expiry
    ON instruments (underlying_symbol, instrument_type, expiry);

CREATE INDEX IF NOT EXISTS ix_candles_strategy_instrument_ts
    ON candles_1min (instrument_id, ts);

CREATE INDEX IF NOT EXISTS ix_nifty_expiry_calendar_strategy
    ON nifty_expiry_calendar (underlying, expiry_type, expiry_date);

CREATE INDEX IF NOT EXISTS ix_nse_holidays_strategy
    ON nse_holidays (segment, holiday_date);
