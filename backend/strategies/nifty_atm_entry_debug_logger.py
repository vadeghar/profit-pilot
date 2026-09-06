"""Date-scoped diagnostic logger for the V2 NIFTY ATM entry scan."""
from datetime import date, datetime, time
from pathlib import Path
import logging

from db import repository as repo

logger = logging.getLogger(__name__)

UNDERLYING = "NIFTY 50"
VIX_UNDERLYING = "INDIA VIX"
DEBUG_DATE = date(2026, 8, 4)
MARKET_OPEN = time(9, 15)
FORCE_EXIT = time(15, 35)
VIX_MAX = 15.0
INITIAL_MAX_PREMIUM = 50.0
LOG_PATH = Path(__file__).resolve().parents[1] / "logs" / "nifty_atm_entry_debug_20260804.log"


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
        "=" * 180,
        f"NIFTY ATM STRADDLE V2 ENTRY DEBUG | DATE={trading_date}",
        f"Window={MARKET_OPEN} -> {FORCE_EXIT} | VIX < {VIX_MAX} | Combined CE+PE <= {INITIAL_MAX_PREMIUM}",
        "=" * 180,
    ]

    expiries = repo.get_weekly_expiries(UNDERLYING, "CE", on_or_after=trading_date, limit=1)
    if not expiries:
        lines.append("RESULT=NO_ENTRY | reason=NO_WEEKLY_EXPIRY")
        _write(lines)
        return
    expiry = expiries[0]
    lines.append(f"EXPIRY={expiry}")

    index_id = repo.get_index_instrument_id(UNDERLYING)
    vix_id = repo.get_index_instrument_id(VIX_UNDERLYING)
    if index_id is None or vix_id is None:
        lines.append(f"RESULT=NO_ENTRY | reason=MISSING_INDEX_INSTRUMENT | index_id={index_id} | vix_id={vix_id}")
        _write(lines)
        return

    start = datetime.combine(trading_date, MARKET_OPEN)
    end = datetime.combine(trading_date, FORCE_EXIT)
    spot_df = repo.get_candles(index_id, start, end).set_index("ts")
    vix_df = repo.get_candles(vix_id, start, end).set_index("ts")
    if spot_df.empty or vix_df.empty:
        lines.append(f"RESULT=NO_ENTRY | reason=EMPTY_INDEX_DATA | spot_rows={len(spot_df)} | vix_rows={len(vix_df)}")
        _write(lines)
        return

    common_ts = sorted(set(spot_df.index) & set(vix_df.index))
    lines.append(f"COMMON_NIFTY_VIX_TIMESTAMPS={len(common_ts)}")
    lines.append("TIME | VIX | NIFTY | ATM | CE | PE | CE+PE | RESULT")
    lines.append("-" * 180)

    for ts in common_ts:
        if ts.time().replace(tzinfo=None) >= FORCE_EXIT:
            lines.append(f"{ts} | RESULT=SCAN_STOP | reason=FORCE_EXIT_TIME")
            break

        vix = float(vix_df.loc[ts, "close"])
        spot = float(spot_df.loc[ts, "close"])
        if vix >= VIX_MAX:
            lines.append(f"{ts} | VIX={vix:.4f} | NIFTY={spot:.2f} | RESULT=SKIP_VIX")
            continue

        strike = repo.get_nearest_strike(UNDERLYING, "CE", expiry, spot)
        if strike is None:
            lines.append(f"{ts} | VIX={vix:.4f} | NIFTY={spot:.2f} | RESULT=SKIP_NO_ATM_STRIKE")
            continue

        ce = repo.get_instrument(UNDERLYING, "CE", expiry, strike)
        pe = repo.get_instrument(UNDERLYING, "PE", expiry, strike)
        if ce is None or pe is None:
            lines.append(f"{ts} | VIX={vix:.4f} | NIFTY={spot:.2f} | ATM={strike} | RESULT=SKIP_MISSING_OPTION_INSTRUMENT")
            continue

        ce_p = repo.get_price_at_or_before(ce["id"], ts)
        pe_p = repo.get_price_at_or_before(pe["id"], ts)
        if ce_p is None or pe_p is None:
            lines.append(f"{ts} | VIX={vix:.4f} | NIFTY={spot:.2f} | ATM={strike} | CE={ce_p} | PE={pe_p} | RESULT=SKIP_MISSING_OPTION_PRICE")
            continue

        combined = ce_p + pe_p
        result = "INITIAL_ENTRY" if combined <= INITIAL_MAX_PREMIUM else "SKIP_PREMIUM"
        lines.append(
            f"{ts} | VIX={vix:.4f} | NIFTY={spot:.2f} | ATM={strike} | "
            f"CE={ce_p:.2f} | PE={pe_p:.2f} | CE+PE={combined:.2f} | RESULT={result}"
        )
        if combined <= INITIAL_MAX_PREMIUM:
            lines.append(f"ENTRY_WOULD_BE_TAKEN={ts} | ATM={strike} | CE={ce_p:.2f} | PE={pe_p:.2f} | SUM={combined:.2f} | VIX={vix:.4f}")
            logger.info(
                "[NIFTY ATM V2 DEBUG] ENTRY_WOULD_BE_TAKEN=%s | ATM=%s | CE=%.2f | PE=%.2f | SUM=%.2f | VIX=%.4f",
                ts, strike, ce_p, pe_p, combined, vix,
            )
            break

    lines.append("=== V2 INITIAL ENTRY SCAN END ===")
    _write(lines)


def _write(lines: list[str]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    logger.info("[NIFTY ATM V2 DEBUG] Entry diagnostic written: %s", LOG_PATH)
