-- Matrix Calendar lookup indexes.
-- Existing-schema review:
--   * candles_1min already has (instrument_id, ts) on the parent and partitions.
--   * instruments already has (underlying_symbol, instrument_type, expiry).
--   * nse_holidays already has (segment, holiday_date).
-- The statements below intentionally add only non-duplicate coverage.

CREATE INDEX IF NOT EXISTS ix_instruments_strategy_contract
    ON instruments (underlying_symbol, instrument_type, expiry, strike);

CREATE INDEX IF NOT EXISTS ix_nifty_expiry_calendar_strategy
    ON nifty_expiry_calendar (underlying, expiry_type, expiry_date);
