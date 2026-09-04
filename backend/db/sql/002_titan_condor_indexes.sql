-- Existing deployments already cover candle PKs, holidays, and the
-- three-column instrument/expiry lookups. These two indexes add the strike
-- lookup and calendar filtering used by Titan Condor without duplicating them.
CREATE INDEX IF NOT EXISTS ix_instruments_strategy_contract
    ON instruments (underlying_symbol, instrument_type, expiry, strike);

CREATE INDEX IF NOT EXISTS ix_nifty_expiry_calendar_strategy
    ON nifty_expiry_calendar (underlying, expiry_type, expiry_date);
