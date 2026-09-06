"""Date-scoped diagnostic logger for the V2 NIFTY ATM entry scan."""
from datetime import date, datetime, time
from pathlib import Path
import logging
from zoneinfo import ZoneInfo

from db import repository as repo

logger = logging.getLogger(__name__)

UNDERLYING = "NIFTY 50"
VIX_UNDERLYING = "INDIA VIX"
DEBUG_DATE = date(2026, 8, 4)
MARKET_OPEN = time(9, 15)
FORCE_EXIT = time(15, 35)
VIX_MAX = 15.0
INITIAL_MAX_PREMIUM = 50.0
MARKET_TZ = ZoneInfo("Asia/Kolkata")
UTC = ZoneInfo("UTC")
LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "nifty_atm_entry_debug_20260804.log"


def _market_ts(ts: datetime) -> str:
    """Render diagnostic timestamps in the exchange's local timezone."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=MARKET_TZ)
    return ts.astimezone(MARKET_TZ).strftime("%Y-%m-%d %H:%M:%S IST")


def run_entry_debug_log(trading_date: date) -> None:
    """Write the complete V2 entry scan for the diagnostic date only."""
    if trading_date != DEBUG_DATE:
        return

    logger.info(
        "[NIFTY ATM V2 DEBUG] Starting entry scan for %s | output=%s",
        trading_date,
        LOG_PATH,
    )

    lines: list[str] = [
        "=" * 200,
        f"NIFTY ATM STRADDLE V2 ENTRY DEBUG | DATE={trading_date}",
        f"Window={MARKET_OPEN} -> {FORCE_EXIT} IST | VIX < {VIX_MAX} | Combined CE+PE <= {INITIAL_MAX_PREMIUM}",
        "Index data policy=EXACT -> PREVIOUS AVAILABLE CANDLE (NO LOOK-AHEAD)",
        "Live deployment note: live deployment will use broker API market data; historical gap fallback should normally never be exercised.",
        "=" * 200,
    ]

    expiries = repo.get_weekly_expiries(UNDERLYING, "CE", on_or_after=trading_date, limit=1)
    if not expiries:
        lines.append("RESULT=NO_ENTRY | reason=NO_WEEKLY_EXPIRY")
        _write(lines)
        return
    expiry = expiries[0]
    lines.append(f"EXPIRY={expiry}")

    index_id = repo.get_index_instrument_id(UNDERLYING, trading_date=trading_date)
    vix_id = repo.get_index_instrument_id(VIX_UNDERLYING, trading_date=trading_date)
    if index_id is None or vix_id is None:
        lines.append(f"RESULT=NO_ENTRY | reason=MISSING_INDEX_INSTRUMENT | index_id={index_id} | vix_id={vix_id}")
        _write(lines)
        return

    start = datetime.combine(trading_date, MARKET_OPEN, tzinfo=MARKET_TZ)
    end = datetime.combine(trading_date, FORCE_EXIT, tzinfo=MARKET_TZ)
    spot_df = repo.get_candles(index_id, start, end).set_index("ts")
    vix_df = repo.get_candles(vix_id, start, end).set_index("ts")
    if spot_df.empty or vix_df.empty:
        lines.append(f"RESULT=NO_ENTRY | reason=EMPTY_INDEX_DATA | spot_rows={len(spot_df)} | vix_rows={len(vix_df)}")
        _write(lines)
        return

    common_ts = sorted(set(spot_df.index) & set(vix_df.index))
    lines.append(f"SELECTED_INDEX_INSTRUMENT={index_id} | SELECTED_VIX_INSTRUMENT={vix_id}")
    lines.append(f"COMMON_NIFTY_VIX_TIMESTAMPS={len(common_ts)}")
    lines.append("TIME_IST | VIX | VIX_SOURCE_IST | NIFTY | NIFTY_SOURCE_IST | ATM | CE | PE | CE+PE | RESULT")
    lines.append("-" * 200)

    for ts in common_ts:
        if ts.astimezone(MARKET_TZ).time().replace(tzinfo=None) >= FORCE_EXIT:
            lines.append(f"{_market_ts(ts)} | RESULT=SCAN_STOP | reason=FORCE_EXIT_TIME")
            break

        vix = float(vix_df.loc[ts, "close"])
        spot = float(spot_df.loc[ts, "close"])
        vix_source = vix_df.loc[ts, "source_ts"] if "source_ts" in vix_df.columns else ts
        nifty_source = spot_df.loc[ts, "source_ts"] if "source_ts" in spot_df.columns else ts
        vix_source_text = _market_ts(vix_source) if not pd_is_na(vix_source) else "N/A"
        nifty_source_text = _market_ts(nifty_source) if not pd_is_na(nifty_source) else "N/A"
        fallback_flags = []
        if vix_source_text != _market_ts(ts):
            fallback_flags.append("VIX_PREVIOUS")
        if nifty_source_text != _market_ts(ts):
            fallback_flags.append("NIFTY_PREVIOUS")
        fallback_text = ",".join(fallback_flags) if fallback_flags else "EXACT"

        if vix >= VIX_MAX:
            lines.append(f"{_market_ts(ts)} | {vix:.4f} | {vix_source_text} | {spot:.2f} | {nifty_source_text} | RESULT=SKIP_VIX | DATA={fallback_text}")
            continue

        strike = repo.get_nearest_strike(UNDERLYING, "CE", expiry, spot)
        if strike is None:
            lines.append(f"{_market_ts(ts)} | {vix:.4f} | {vix_source_text} | {spot:.2f} | {nifty_source_text} | RESULT=SKIP_NO_ATM_STRIKE | DATA={fallback_text}")
            continue

        ce = repo.get_instrument(UNDERLYING, "CE", expiry, strike)
        pe = repo.get_instrument(UNDERLYING, "PE", expiry, strike)
        if ce is None or pe is None:
            lines.append(f"{_market_ts(ts)} | {vix:.4f} | {vix_source_text} | {spot:.2f} | {nifty_source_text} | ATM={strike} | RESULT=SKIP_MISSING_OPTION_INSTRUMENT | DATA={fallback_text}")
            continue

        ce_p = repo.get_price_at_or_before(ce["id"], ts)
        pe_p = repo.get_price_at_or_before(pe["id"], ts)
        if ce_p is None or pe_p is None:
            lines.append(f"{_market_ts(ts)} | {vix:.4f} | {vix_source_text} | {spot:.2f} | {nifty_source_text} | ATM={strike} | CE={ce_p} | PE={pe_p} | RESULT=SKIP_MISSING_OPTION_PRICE | DATA={fallback_text}")
            continue

        combined = ce_p + pe_p
        result = "INITIAL_ENTRY" if combined <= INITIAL_MAX_PREMIUM else "SKIP_PREMIUM"
        lines.append(
            f"{_market_ts(ts)} | {vix:.4f} | {vix_source_text} | {spot:.2f} | {nifty_source_text} | ATM={strike} | "
            f"CE={ce_p:.2f} | PE={pe_p:.2f} | CE+PE={combined:.2f} | RESULT={result} | DATA={fallback_text}"
        )
        if combined <= INITIAL_MAX_PREMIUM:
            lines.append(f"ENTRY_WOULD_BE_TAKEN={_market_ts(ts)} | ATM={strike} | CE={ce_p:.2f} | PE={pe_p:.2f} | SUM={combined:.2f} | VIX={vix:.4f} | VIX_SOURCE={vix_source_text} | NIFTY_SOURCE={nifty_source_text}")
            logger.info(
                "[NIFTY ATM V2 DEBUG] ENTRY_WOULD_BE_TAKEN=%s | ATM=%s | CE=%.2f | PE=%.2f | SUM=%.2f | VIX=%.4f | DATA=%s",
                _market_ts(ts), strike, ce_p, pe_p, combined, vix, fallback_text,
            )
            break

    lines.append("=== V2 INITIAL ENTRY SCAN END ===")
    _write(lines)


def pd_is_na(value) -> bool:
    """Small dependency-free NA check for pandas Timestamp/NaT values."""
    return value is None or str(value) == "NaT"


def _write(lines: list[str]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("[NIFTY ATM V2 DEBUG] Entry diagnostic written: %s", LOG_PATH)
