"""Batch data access for Matrix Calendar entry selection.

These queries intentionally do not require instruments.is_active because a
historical backtest must be able to resolve contracts after expiry.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import text

from db.config import engine


def get_expiry_pair(entry_date: date) -> tuple[date, date] | None:
    """Return the later weekly expiry and following monthly expiry.

    The first weekly expiry on/after Monday is normally the next-day expiry,
    which Strategy 8 explicitly excludes.
    """
    query = text(
        """
        SELECT expiry_date, expiry_type
        FROM nifty_expiry_calendar
        WHERE underlying = 'NIFTY'
          AND expiry_date >= :entry_date
        ORDER BY expiry_date
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"entry_date": entry_date}).mappings().all()

    weekly_dates = [r["expiry_date"] for r in rows if r["expiry_type"] == "WEEKLY"]
    if len(weekly_dates) < 2:
        return None
    weekly = weekly_dates[1]
    monthly = next(
        (
            r["expiry_date"]
            for r in rows
            if r["expiry_type"] == "MONTHLY" and r["expiry_date"] > weekly
        ),
        None,
    )
    if monthly is None:
        return None
    return weekly, monthly


def get_option_chain_snapshot(
    underlying: str,
    expiry: date,
    timestamp: datetime,
) -> list[dict[str, Any]]:
    """Return the latest candle at/before timestamp for every option in an expiry."""
    query = text(
        """
        SELECT
            i.id,
            i.trading_symbol,
            i.instrument_type,
            i.strike,
            i.lot_size,
            c.ts AS candle_ts,
            c.close,
            c.volume,
            c.open_interest
        FROM instruments i
        JOIN LATERAL (
            SELECT ts, close, volume, open_interest
            FROM candles_1min
            WHERE instrument_id = i.id
              AND ts <= :timestamp
            ORDER BY ts DESC
            LIMIT 1
        ) c ON true
        WHERE i.underlying_symbol = :underlying
          AND i.instrument_type IN ('CE', 'PE')
          AND i.expiry = :expiry
        ORDER BY i.instrument_type, i.strike
        """
    )
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(
            query,
            {"underlying": underlying, "expiry": expiry, "timestamp": timestamp},
        ).mappings().all()]


def get_option_contract(
    underlying: str,
    option_type: str,
    expiry: date,
    strike: float,
    timestamp: datetime,
) -> dict[str, Any] | None:
    """Resolve one contract and its entry mark without active-status filtering."""
    query = text(
        """
        SELECT
            i.id,
            i.trading_symbol,
            i.instrument_type,
            i.strike,
            i.lot_size,
            c.close,
            c.ts AS candle_ts
        FROM instruments i
        JOIN LATERAL (
            SELECT ts, close
            FROM candles_1min
            WHERE instrument_id = i.id
              AND ts <= :timestamp
            ORDER BY ts DESC
            LIMIT 1
        ) c ON true
        WHERE i.underlying_symbol = :underlying
          AND i.instrument_type = :option_type
          AND i.expiry = :expiry
          AND i.strike = :strike
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
                "timestamp": timestamp,
            },
        ).mappings().fetchone()
    return dict(row) if row else None
