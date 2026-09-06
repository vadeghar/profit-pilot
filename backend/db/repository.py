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
from datetime import date, datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import text

from .config import engine

MARKET_TZ = ZoneInfo("Asia/Kolkata")
MARKET_OPEN_TIME = time(9, 15)
MARKET_CLOSE_TIME = time(15, 35)


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


def get_index_instrument_id(
    underlying_symbol: str,
    trading_date: Optional[date] = None,
) -> Optional[int]:
    """Resolve the INDEX instrument used for a trading day.

    The instrument master can contain duplicate/partial historical INDEX
    rows for the same underlying.  A plain ``LIMIT 1`` is therefore unsafe.
    When a trading date is supplied, choose the active candidate with the
    strongest candle coverage for the complete Indian market session,
    preferring a complete 09:15-15:35 series and then the highest count.
    Without a date, retain a deterministic active-row fallback for legacy
    callers.
    """
    if trading_date is None:
        query = text(
            """
            SELECT id
            FROM instruments
            WHERE underlying_symbol = :underlying
              AND instrument_type = 'INDEX'
              AND is_active = true
            ORDER BY id ASC
            LIMIT 1
            """
        )
        with engine.connect() as conn:
            row = conn.execute(query, {"underlying": underlying_symbol}).fetchone()
        return int(row[0]) if row else None

    start = datetime.combine(trading_date, MARKET_OPEN_TIME, tzinfo=MARKET_TZ)
    end = datetime.combine(trading_date, MARKET_CLOSE_TIME, tzinfo=MARKET_TZ)
    query = text(
        """
        SELECT
            i.id,
            COUNT(c.ts) AS candle_count,
            MIN(c.ts) AS first_candle,
            MAX(c.ts) AS last_candle
        FROM instruments i
        LEFT JOIN candles_1min c
               ON c.instrument_id = i.id
              AND c.ts >= :start
              AND c.ts <= :end
        WHERE i.underlying_symbol = :underlying
          AND i.instrument_type = 'INDEX'
          AND i.is_active = true
        GROUP BY i.id
        ORDER BY
            CASE
                WHEN COUNT(c.ts) >= 381
                 AND MIN(c.ts) = :start
                 AND MAX(c.ts) = :end
                THEN 0 ELSE 1
            END,
            COUNT(c.ts) DESC,
            i.id ASC
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(
            query,
            {"underlying": underlying_symbol, "start": start, "end": end},
        ).fetchone()
    return int(row[0]) if row else None


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


def get_aligned_index_candles(
    underlying_symbol: str,
    trading_date: date,
    start_time: time = MARKET_OPEN_TIME,
    end_time: time = MARKET_CLOSE_TIME,
) -> pd.DataFrame:
    """Return an index series on every expected market minute.

    Exact candle is always preferred. If an expected minute is missing,
    carry forward the previous available candle. This is intentionally a
    *previous-only* fallback: it never uses a future candle and therefore
    introduces no look-ahead bias in the backtest.

    ``source_ts`` records the actual candle timestamp used for each resolved
    minute, allowing diagnostics to distinguish exact data from a fallback.

    LIVE DEPLOYMENT NOTE: the deployed strategy will consume live broker API
    ticks/candles, so this historical-data gap fallback should normally never
    be exercised. Keep this fallback for backtesting/replay robustness only.
    """
    start = datetime.combine(trading_date, start_time, tzinfo=MARKET_TZ)
    end = datetime.combine(trading_date, end_time, tzinfo=MARKET_TZ)
    instrument_id = get_index_instrument_id(underlying_symbol, trading_date=trading_date)
    if instrument_id is None:
        return pd.DataFrame()

    raw = get_candles(instrument_id, start, end)
    if raw.empty:
        return raw

    raw["ts"] = pd.to_datetime(raw["ts"], utc=True)
    raw = raw.drop_duplicates(subset=["ts"], keep="last").set_index("ts").sort_index()
    expected = pd.date_range(start=start, end=end, freq="1min", tz="UTC")
    aligned = raw.reindex(expected)
    aligned["source_ts"] = aligned.index.to_series().where(~aligned["close"].isna())
    aligned["source_ts"] = aligned["source_ts"].ffill()
    value_columns = ["open", "high", "low", "close", "volume", "open_interest"]
    aligned[value_columns] = aligned[value_columns].ffill()
    aligned = aligned.dropna(subset=["close"])
    aligned.index.name = "ts"
    return aligned.reset_index()


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
          AND i.is_active = true
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


def get_nearest_strike(
    underlying_symbol: str,
    instrument_type: str,
    expiry: date,
    target_price: float,
) -> Optional[float]:
    """Nearest available strike in the option chain to target_price."""
    query = text(
        """
        SELECT strike
        FROM instruments
        WHERE underlying_symbol = :underlying
          AND instrument_type = :itype
          AND expiry = :expiry
          AND is_active = true
        ORDER BY ABS(strike - :target) ASC
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
                "target": target_price,
            },
        ).fetchone()
    return float(row[0]) if row else None


def get_trading_days(underlying_symbol: str, start: date, end: date) -> list[date]:
    """Distinct calendar dates with underlying INDEX candle data in [start, end]."""
    query = text(
        """
        SELECT DISTINCT c.ts::date AS d
        FROM candles_1min c
        JOIN instruments i ON i.id = c.instrument_id
        WHERE i.underlying_symbol = :underlying
          AND i.instrument_type = 'INDEX'
          AND c.ts::date BETWEEN :start AND :end
        ORDER BY d ASC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(
            query, {"underlying": underlying_symbol, "start": start, "end": end}
        ).fetchall()
    return [r[0] for r in rows]
