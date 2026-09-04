"""
One-time backfill: computes Greeks/IV for every CE/PE 1-min candle and
inserts them into option_greeks_1min.

Usage:
    python -m backend.greeks.backfill --underlying NIFTY
    python -m backend.greeks.backfill --underlying NIFTY --from-expiry 2026-01-01 --to-expiry 2026-06-30

Safe to re-run: inserts use ON CONFLICT (instrument_id, ts) DO UPDATE, so
re-running (e.g. after fixing a bug, or with a bumped model_version) simply
overwrites the affected rows rather than erroring or duplicating.

Design notes:
  - Processes one option instrument (one strike/expiry/CE-or-PE contract) at
    a time, so memory use stays bounded regardless of total history size.
  - The NIFTY Index candle history needed to cover the whole run is loaded
    ONCE up front and reused across every option instrument via merge_asof
    (backward fill: the most recent Index close at/before each option tick).
  - Rows with no time value left (price <= intrinsic) or where the IV solver
    fails are still inserted, with iv/greeks NULL and skip_reason set --
    this keeps the table a complete record of "we tried, here's what
    happened" rather than silently dropping data.
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import Table, MetaData

from backend.db.config import engine
from backend.db import repository
from backend.greeks import black_scholes as bs
from backend.greeks.config import get_dividend_yield, get_risk_free_rate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
EXPIRY_CLOSE_TIME = time(15, 30)  # NSE F&O session close
SECONDS_PER_YEAR = 365.0 * 24 * 3600
MIN_T_YEARS = 1e-6  # floor to avoid div-by-zero right at/after expiry close

_greeks_table = Table("option_greeks_1min", MetaData(), autoload_with=engine)


def _expiry_close_ts(expiry_date: date) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(expiry_date, EXPIRY_CLOSE_TIME), tz=IST)


def _load_index_candles(underlying_symbol: str, start: datetime, end: datetime) -> pd.DataFrame:
    """Load the underlying Index's 1-min candles once for the whole run."""
    index_id = repository.get_index_instrument_id(underlying_symbol)
    if index_id is None:
        raise RuntimeError(f"No INDEX instrument found for underlying_symbol={underlying_symbol!r}")
    df = repository.get_candles(index_id, start, end)
    if df.empty:
        raise RuntimeError(f"No Index candles found for {underlying_symbol} between {start} and {end}")
    df = df.rename(columns={"close": "underlying_price"})[["ts", "underlying_price"]]
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df.sort_values("ts")


def _process_instrument(
    instrument_row: pd.Series,
    index_df: pd.DataFrame,
) -> pd.DataFrame | None:
    """Compute Greeks for one option instrument's full candle history.
    Returns a DataFrame ready to insert, or None if it has no candles."""
    instrument_id = int(instrument_row["instrument_id"])
    strike = float(instrument_row["strike"])
    expiry = instrument_row["expiry"]
    option_type = instrument_row["instrument_type"]

    expiry_close = _expiry_close_ts(expiry)
    candles = repository.get_candles(
        instrument_id,
        start=datetime.combine(expiry - pd.Timedelta(days=45), time(0, 0)),
        end=datetime.combine(expiry, EXPIRY_CLOSE_TIME),
    )
    if candles.empty:
        return None

    candles["ts"] = pd.to_datetime(candles["ts"], utc=True)
    candles = candles.sort_values("ts")

    merged = pd.merge_asof(candles, index_df, on="ts", direction="backward")
    merged = merged.dropna(subset=["underlying_price"])
    if merged.empty:
        return None

    T = (expiry_close - merged["ts"]).dt.total_seconds() / SECONDS_PER_YEAR
    valid = T > MIN_T_YEARS
    if not valid.any():
        return None
    merged = merged.loc[valid].copy()
    T = T.loc[valid].clip(lower=MIN_T_YEARS).to_numpy()

    as_of_dates = merged["ts"].dt.tz_convert(IST).dt.date
    r = as_of_dates.map(get_risk_free_rate).to_numpy(dtype=float)
    q = as_of_dates.map(get_dividend_yield).to_numpy(dtype=float)

    S = merged["underlying_price"].to_numpy(dtype=float)
    K = np.full(len(merged), strike, dtype=float)
    market_price = merged["close"].to_numpy(dtype=float)
    option_type_arr = np.full(len(merged), option_type, dtype=object)

    iv, skip_reason = bs.implied_volatility(S, K, T, r, q, market_price, option_type_arr)

    has_iv = ~np.isnan(iv)
    greeks = {k: np.full(len(merged), np.nan) for k in ("delta", "gamma", "theta", "vega", "rho")}
    if has_iv.any():
        computed = bs.compute_greeks(
            S[has_iv], K[has_iv], T[has_iv], r[has_iv], q[has_iv], iv[has_iv], option_type_arr[has_iv]
        )
        for key, values in computed.items():
            greeks[key][has_iv] = values

    result = pd.DataFrame(
        {
            "instrument_id": instrument_id,
            "ts": merged["ts"],
            "underlying_price": S,
            "time_to_expiry_yrs": T,
            "iv": iv,
            "delta": greeks["delta"],
            "gamma": greeks["gamma"],
            "theta": greeks["theta"],
            "vega": greeks["vega"],
            "rho": greeks["rho"],
            "model_version": bs.MODEL_VERSION,
            "skip_reason": skip_reason,
            "computed_at": datetime.now(tz=IST),
        }
    )
    # NaN -> None so psycopg2 writes SQL NULL instead of 'NaN'
    return result.where(pd.notnull(result), None)


def _upsert(rows: pd.DataFrame) -> None:
    if rows.empty:
        return
    records = rows.to_dict(orient="records")
    stmt = pg_insert(_greeks_table).values(records)
    update_cols = {
        c.name: stmt.excluded[c.name]
        for c in _greeks_table.columns
        if c.name not in ("instrument_id", "ts")
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=["instrument_id", "ts"],
        set_=update_cols,
    )
    with engine.begin() as conn:
        conn.execute(stmt)


def run_backfill(underlying_symbol: str, from_expiry: date | None, to_expiry: date | None) -> None:
    instruments = repository.get_option_instruments(underlying_symbol, start=from_expiry, end=to_expiry)
    if instruments.empty:
        logger.warning("No option instruments found for %s in the given range.", underlying_symbol)
        return

    overall_start = datetime.combine(instruments["expiry"].min() - pd.Timedelta(days=45), time(0, 0))
    overall_end = datetime.combine(instruments["expiry"].max(), EXPIRY_CLOSE_TIME)
    logger.info(
        "Loading %s Index candles from %s to %s ...", underlying_symbol, overall_start, overall_end
    )
    index_df = _load_index_candles(underlying_symbol, overall_start, overall_end)

    total = len(instruments)
    total_rows_written = 0
    for i, (_, instrument_row) in enumerate(instruments.iterrows(), start=1):
        result = _process_instrument(instrument_row, index_df)
        if result is None:
            logger.info(
                "[%d/%d] %s: no candles / no valid time-to-expiry, skipped.",
                i, total, instrument_row["trading_symbol"],
            )
            continue
        _upsert(result)
        total_rows_written += len(result)
        logger.info(
            "[%d/%d] %s: wrote %d rows (%d with solved IV).",
            i, total, instrument_row["trading_symbol"], len(result), int(result["iv"].notna().sum()),
        )

    logger.info("Done. %d instruments processed, %d rows written total.", total, total_rows_written)


def main() -> None:
    parser = argparse.ArgumentParser(description="One-time Greeks backfill for candles_1min options.")
    parser.add_argument("--underlying", default="NIFTY", help="underlying_symbol, e.g. NIFTY")
    parser.add_argument("--from-expiry", type=date.fromisoformat, default=None, help="YYYY-MM-DD")
    parser.add_argument("--to-expiry", type=date.fromisoformat, default=None, help="YYYY-MM-DD")
    args = parser.parse_args()
    run_backfill(args.underlying, args.from_expiry, args.to_expiry)


if __name__ == "__main__":
    main()
