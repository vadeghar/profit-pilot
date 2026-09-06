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
UTC_TZ = ZoneInfo("UTC")
MARKET_OPEN_TIME = time(9, 15)
MARKET_CLOSE_TIME = time(15, 35)
EXPECTED_MARKET_MINUTES = 381


def _market_aware(value: datetime) -> datetime:
    """Interpret naive strategy boundaries as Asia/Kolkata market time."""
    if value.tzinfo is None:
        return value.replace(tzinfo=MARKET_TZ)
    return value.astimezone(MARKET_TZ)


def get_instrument(underlying_symbol: str, instrument_type: str, expiry: date, strike: Optional[float] = None) -> Optional[dict]:
    query = text("""
        SELECT id, trading_symbol, lot_size, tick_size, strike, expiry
        FROM instruments
        WHERE underlying_symbol = :underlying
          AND instrument_type = :itype
          AND expiry = :expiry
          AND (:strike IS NULL OR strike = :strike)
          AND is_active = true
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"underlying": underlying_symbol, "itype": instrument_type, "expiry": expiry, "strike": strike}).mappings().fetchone()
    return dict(row) if row else None


def get_weekly_expiries(underlying_symbol: str, instrument_type: str = "CE", on_or_after: Optional[date] = None, limit: int = 20) -> list[date]:
    """Return NIFTY expiry dates (weekly or monthly) from nifty_expiry_calendar.

    The expiry calendar is the strategy source of truth. For NIFTY, the
    instrument master name 'NIFTY 50' maps to calendar underlying 'NIFTY'.
    Both scheduled_date and expiry_date are considered so holiday-shifted
    expiries are handled correctly. Returned dates are actual expiry/trading
    dates (expiry_date), ordered chronologically.
    """
    calendar_underlying = "NIFTY" if underlying_symbol == "NIFTY 50" else underlying_symbol
    query = text("""
        SELECT expiry_date
        FROM public.nifty_expiry_calendar
        WHERE underlying = :underlying
          AND expiry_type IN ('WEEKLY', 'MONTHLY')
          AND (
                :on_or_after IS NULL
                OR expiry_date >= :on_or_after
                OR scheduled_date >= :on_or_after
              )
        ORDER BY expiry_date ASC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"underlying": calendar_underlying, "on_or_after": on_or_after, "limit": limit}).fetchall()
    return [r[0] for r in rows]


def get_index_instrument_id(underlying_symbol: str, trading_date: Optional[date] = None) -> Optional[int]:
    """Resolve the best active INDEX instrument instead of unordered LIMIT 1."""
    if trading_date is None:
        query = text("""
            SELECT i.id
            FROM instruments i
            LEFT JOIN candles_1min c ON c.instrument_id = i.id
            WHERE i.underlying_symbol = :underlying
              AND i.instrument_type = 'INDEX'
              AND i.is_active = true
            GROUP BY i.id
            ORDER BY COUNT(c.ts) DESC, i.id ASC
            LIMIT 1
        """)
        with engine.connect() as conn:
            row = conn.execute(query, {"underlying": underlying_symbol}).fetchone()
        return int(row[0]) if row else None

    start = datetime.combine(trading_date, MARKET_OPEN_TIME, tzinfo=MARKET_TZ)
    end = datetime.combine(trading_date, MARKET_CLOSE_TIME, tzinfo=MARKET_TZ)
    query = text("""
        SELECT i.id, COUNT(c.ts) AS candle_count, MIN(c.ts) AS first_candle, MAX(c.ts) AS last_candle
        FROM instruments i
        LEFT JOIN candles_1min c ON c.instrument_id = i.id AND c.ts >= :start AND c.ts <= :end
        WHERE i.underlying_symbol = :underlying
          AND i.instrument_type = 'INDEX'
          AND i.is_active = true
        GROUP BY i.id
        ORDER BY CASE WHEN COUNT(c.ts) = :expected_count AND MIN(c.ts) = :start AND MAX(c.ts) = :end THEN 0 ELSE 1 END,
                 COUNT(c.ts) DESC, i.id ASC
        LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"underlying": underlying_symbol, "start": start, "end": end, "expected_count": EXPECTED_MARKET_MINUTES}).fetchone()
    return int(row[0]) if row else None


def _is_index_instrument(instrument_id: int) -> bool:
    query = text("SELECT instrument_type = 'INDEX' FROM instruments WHERE id = :iid LIMIT 1")
    with engine.connect() as conn:
        row = conn.execute(query, {"iid": instrument_id}).fetchone()
    return bool(row[0]) if row else False


def _align_index_candles(raw: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    """Fill missing INDEX minutes from the previous available candle only."""
    if raw.empty:
        return raw
    raw["ts"] = pd.to_datetime(raw["ts"], utc=True)
    raw = raw.drop_duplicates(subset=["ts"], keep="last").set_index("ts").sort_index()
    expected = pd.date_range(start=start.astimezone(UTC_TZ), end=end.astimezone(UTC_TZ), freq="1min")
    aligned = raw.reindex(expected)
    exact_mask = ~aligned["close"].isna()
    aligned["source_ts"] = aligned.index.to_series().where(exact_mask).ffill()
    value_columns = ["open", "high", "low", "close", "volume", "open_interest"]
    aligned[value_columns] = aligned[value_columns].ffill()
    aligned = aligned.dropna(subset=["close"])
    aligned.index.name = "ts"
    return aligned.reset_index()


def get_candles(instrument_id: int, start: datetime, end: datetime, fill_index_gaps: bool = False) -> pd.DataFrame:
    """1-min OHLCV. INDEX candles are previous-candle aligned without look-ahead.

    LIVE DEPLOYMENT NOTE: live deployment will use broker API market data;
    this historical fallback should normally never be exercised there.
    """
    start = _market_aware(start)
    end = _market_aware(end)
    query = text("""
        SELECT ts, open, high, low, close, volume, open_interest
        FROM candles_1min
        WHERE instrument_id = :iid AND ts >= :start AND ts <= :end
        ORDER BY ts ASC
    """)
    with engine.connect() as conn:
        raw = pd.read_sql(query, conn, params={"iid": instrument_id, "start": start, "end": end})
    if raw.empty:
        return raw
    if fill_index_gaps or _is_index_instrument(instrument_id):
        return _align_index_candles(raw, start, end)
    return raw


def get_index_candles(underlying_symbol: str, trading_date: date, start_time: time = MARKET_OPEN_TIME, end_time: time = MARKET_CLOSE_TIME) -> pd.DataFrame:
    instrument_id = get_index_instrument_id(underlying_symbol, trading_date=trading_date)
    if instrument_id is None:
        return pd.DataFrame()
    start = datetime.combine(trading_date, start_time, tzinfo=MARKET_TZ)
    end = datetime.combine(trading_date, end_time, tzinfo=MARKET_TZ)
    return get_candles(instrument_id, start, end, fill_index_gaps=True)


def get_price_at_or_before(instrument_id: int, ts: datetime) -> Optional[float]:
    ts = _market_aware(ts)
    query = text("SELECT close FROM candles_1min WHERE instrument_id = :iid AND ts <= :ts ORDER BY ts DESC LIMIT 1")
    with engine.connect() as conn:
        row = conn.execute(query, {"iid": instrument_id, "ts": ts}).fetchone()
    return float(row[0]) if row else None


def get_spot_price_at(underlying_symbol: str, ts: datetime) -> Optional[float]:
    ts = _market_aware(ts)
    query = text("""
        SELECT c.close FROM candles_1min c
        JOIN instruments i ON i.id = c.instrument_id
        WHERE i.underlying_symbol = :underlying AND i.instrument_type = 'INDEX'
          AND i.is_active = true AND c.ts <= :ts
        ORDER BY c.ts DESC LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"underlying": underlying_symbol, "ts": ts}).fetchone()
    return float(row[0]) if row else None


def has_any_candle_on(instrument_id: int, day: date) -> bool:
    query = text("SELECT 1 FROM candles_1min WHERE instrument_id = :iid AND ts::date = :day LIMIT 1")
    with engine.connect() as conn:
        return conn.execute(query, {"iid": instrument_id, "day": day}).fetchone() is not None


def get_nearest_strike(underlying_symbol: str, instrument_type: str, expiry: date, target_price: float) -> Optional[float]:
    query = text("""
        SELECT strike FROM instruments
        WHERE underlying_symbol = :underlying AND instrument_type = :itype
          AND expiry = :expiry AND is_active = true
        ORDER BY ABS(strike - :target) ASC LIMIT 1
    """)
    with engine.connect() as conn:
        row = conn.execute(query, {"underlying": underlying_symbol, "itype": instrument_type, "expiry": expiry, "target": target_price}).fetchone()
    return float(row[0]) if row else None


def get_trading_days(underlying_symbol: str, start: date, end: date) -> list[date]:
    query = text("""
        SELECT DISTINCT c.ts::date AS d
        FROM candles_1min c
        JOIN instruments i ON i.id = c.instrument_id
        WHERE i.underlying_symbol = :underlying
          AND c.ts::date BETWEEN :start AND :end
        ORDER BY d ASC
    """)
    with engine.connect() as conn:
        rows = conn.execute(query, {"underlying": underlying_symbol, "start": start, "end": end}).fetchall()
    return [r[0] for r in rows]
