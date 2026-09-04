"""Database helpers specific to the Titan Condor backtest.

These queries intentionally do not require instruments.is_active so historical
contracts remain available after they expire.
"""
from datetime import date, datetime
from typing import Optional

import pandas as pd
from sqlalchemy import text

from db.config import engine
from db import repository as repo


def get_option_contract(
    underlying: str, option_type: str, expiry: date, strike: float
) -> Optional[dict]:
    query = text(
        """
        SELECT id, trading_symbol, lot_size, tick_size, strike, expiry
        FROM instruments
        WHERE underlying_symbol = :underlying
          AND instrument_type = :option_type
          AND expiry = :expiry
          AND strike = :strike
        ORDER BY is_active DESC, id
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(
            query,
            {
                "underlying": underlying,
                "option_type": option_type,
                "expiry": expiry,
                "strike": strike,
            },
        ).mappings().fetchone()
    return dict(row) if row else None


def get_spot_candles(underlying: str, start: datetime, end: datetime) -> pd.DataFrame:
    instrument_id = repo.get_index_instrument_id(underlying)
    if instrument_id is None:
        return pd.DataFrame()
    return repo.get_candles(instrument_id, start, end)
