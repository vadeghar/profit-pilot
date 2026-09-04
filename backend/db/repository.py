"""
Read-only data access layer over your existing schema:
    exchanges(id, code)
    instruments(id, exchange_id, instrument_token, trading_symbol, name,
                instrument_type, underlying_symbol, expiry, strike,
                lot_size, tick_size, is_active, created_at)
    candles_1min(instrument_id, ts, open, high, low, close, volume, open_interest)
    ingestion_progress(instrument_id, interval, chunk_start, completed_at)

ASSUMPTION (flag if wrong): instrument_type uses 'PE' / 'CE' for option
contracts and 'INDEX' for the underlying spot index row that also has
candles_1min rows. If your actual convention differs (e.g. a separate
option_type column, or 'OPT'/'FUT'/'EQ' style values), only the WHERE
clauses in this file need to change -- nothing above this layer does.
"""
from datetime import date, datetime
from typing import Optional

import pandas as pd
from sqlalchemy import text

from .config import engine


def get_instrument(
    underlying_symbol: str,
    instrument_type: str,
    expiry: date,
    strike: Optional[float] = None,
) -> Optional[dict]:
    """Look up a single instrument row (option leg, index, future, etc)."""
    query = text(
        """
        SELECT id, trading_symbol, lot_size, tick_size, strike, expiry
        FROM instruments
        WHERE underlying_symbol = :underlying
          AND instrument_type = :itype
          AND expiry = :expiry
          AND (:strike IS NULL OR strike = :strike)
          AND is_active = true
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(
            query,
            {
                "underlying": underlying_symbol,
                "itype": instrument_type,
                "expiry": expiry,
                "strike": strike,
            },
        ).mappings().fetchone()
    return dict(row) if row else None


def get_index_instrument_id(underlying_symbol: str) -> Optional[int]:
    """The single INDEX-type instrument row backing spot/underlying candles."""
    query = text(
        """
        SELECT id FROM instruments
        WHERE underlying_symbol = :underlying AND instrument_type = 'INDEX'
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(query, {"underlying": underlying_symbol}).fetchone()
    return int(row[0]) if row else None


def get_weekly_expiries(
    underlying_symbol: str,
    instrument_type: str,
    on_or_after: date,
    limit: int = 10,
) -> list[date]:
    """Distinct expiries for an underlying's option chain, ascending."""
    query = text(
        """
        SELECT DISTINCT expiry
        FROM instruments
        WHERE underlying_symbol = :underlying
          AND instrument_type = :itype
          AND expiry >= :on_or_after
        ORDER BY expiry ASC
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(
            query,
            {"underlying": underlying_symbol, "itype": instrument_type, "on_or_after": on_or_after, "limit": limit},
        ).fetchall()
    return [r[0] for r in rows]


def get_option_instruments(
    underlying_symbol: str,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> pd.DataFrame:
    """All CE/PE instrument rows for an underlying, optionally filtered by
    expiry date range. Used by the Greeks backfill to enumerate what needs
    processing -- includes both expired and active/future contracts."""
    query = text(
        """
        SELECT id AS instrument_id, trading_symbol, instrument_type, expiry, strike
        FROM instruments
        WHERE underlying_symbol = :underlying
          AND instrument_type IN ('CE', 'PE')
          AND (CAST(:start AS date) IS NULL OR expiry >= :start)
          AND (CAST(:end AS date) IS NULL OR expiry <= :end)
        ORDER BY expiry ASC, strike ASC, instrument_type ASC
        """
    )
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"underlying": underlying_symbol, "start": start, "end": end})


def get_candles(instrument_id: int, start: datetime, end: datetime) -> pd.DataFrame:
    """1-min OHLCV for one instrument between start and end, ascending."""
    query = text(
        """
        SELECT ts, open, high, low, close, volume, open_interest
        FROM candles_1min
        WHERE instrument_id = :iid AND ts >= :start AND ts <= :end
        ORDER BY ts ASC
        """
    )
    with engine.connect() as conn:
        return pd.read_sql(query, conn, params={"iid": instrument_id, "start": start, "end": end})


def get_price_at_or_before(instrument_id: int, ts: datetime) -> Optional[float]:
    """Close of the most recent 1-min candle at/just-before ts."""
    query = text(
        """
        SELECT close FROM candles_1min
        WHERE instrument_id = :iid AND ts <= :ts
        ORDER BY ts DESC LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(query, {"iid": instrument_id, "ts": ts}).fetchone()
    return float(row[0]) if row else None


def get_spot_price_at(underlying_symbol: str, ts: datetime) -> Optional[float]:
    """Underlying index close at/just-before ts (instrument_type = 'INDEX').
    Used once per week (position entry) -- for per-minute lookups during a
    trade's lifetime, use get_index_instrument_id() + get_candles() once and
    forward-fill instead; see backtest/engine.py."""
    query = text(
        """
        SELECT c.close
        FROM candles_1min c
        JOIN instruments i ON i.id = c.instrument_id
        WHERE i.underlying_symbol = :underlying
          AND i.instrument_type = 'INDEX'
          AND c.ts <= :ts
        ORDER BY c.ts DESC LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(query, {"underlying": underlying_symbol, "ts": ts}).fetchone()
    return float(row[0]) if row else None


def has_any_candle_on(instrument_id: int, day: date) -> bool:
    """Cheap trading-day check, used for the Monday-holiday roll-forward."""
    query = text(
        """
        SELECT 1 FROM candles_1min
        WHERE instrument_id = :iid AND ts::date = :day
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        return conn.execute(query, {"iid": instrument_id, "day": day}).fetchone() is not None
