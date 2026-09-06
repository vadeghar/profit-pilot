"""Diagnostic logger for the NIFTY ATM Straddle expiry-day entry scan.

This mirrors strategies.nifty_atm_straddle.run_strategy_for_day()'s entry
loop exactly (same filters object, same conditions) so it can be trusted as
a diagnostic. It previously drifted from the real strategy logic (V1-V4)
and introduced its own regressions on top of that during the V5 filter
unification -- see the V6 PR description for details. Keep this file's
entry-scan logic in lockstep with the real loop in nifty_atm_straddle.py.
"""
from datetime import date, datetime, time
from pathlib import Path
import logging
from zoneinfo import ZoneInfo

from db import repository as repo
from strategies.nifty_atm_straddle import NiftyATMEntryFilters, nearest_available_strike, preferred_atm_strike

logger = logging.getLogger(__name__)
UNDERLYING = "NIFTY 50"
VIX_UNDERLYING = "INDIA VIX"
MARKET_OPEN = time(9, 15)
FORCED_INITIAL_ENTRY = time(15, 1)
FORCE_EXIT = time(15, 35)
VIX_MAX = 15.0
INITIAL_MAX_PREMIUM = 50.0
MARKET_TZ = ZoneInfo("Asia/Kolkata")


def create_run_log_path() -> Path:
    """Create a unique IST timestamped log path for one backtest run."""
    timestamp = datetime.now(MARKET_TZ).strftime("%Y%m%d_%H%M%S_%f")
    return Path(__file__).resolve().parents[1] / "logs" / f"nifty_atm_entry_debug_{timestamp}.log"


def _market_ts(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=MARKET_TZ)
    return ts.astimezone(MARKET_TZ).strftime("%Y-%m-%d %H:%M:%S IST")


def run_entry_debug_log(trading_date: date, log_path: Path, filters: NiftyATMEntryFilters | None = None) -> None:
    """Append the entry scan only for an NIFTY weekly or monthly expiry date."""
    filters = filters or NiftyATMEntryFilters()
    expiries = repo.get_nifty_expiry_dates(UNDERLYING, on_or_after=trading_date, limit=1)
    if not expiries or expiries[0] != trading_date:
        # Strict strategy scope: non-expiry dates are ignored completely.
        return
    expiry = expiries[0]

    logger.info(
        "[NIFTY ATM V6 DEBUG] Running EXPIRY-DAY entry scan for %s | output=%s",
        trading_date, log_path,
    )
    lines: list[str] = [
        "=" * 200,
        f"NIFTY ATM STRADDLE V6 ENTRY DEBUG | EXPIRY DATE={trading_date}",
        f"Window={MARKET_OPEN} -> {FORCE_EXIT} IST | Entry after {filters.entry_time.strftime('%H:%M')} | VIX < {filters.india_vix_below} | Combined CE+PE <= {filters.combined_premium} | Only 100s={filters.only_100s} | 3PM force={filters.force_at_1501} | Max forced premium={filters.max_forced_entry_premium} | Hard stop %={filters.hard_stop_pct}",
        "SCOPE=NIFTY WEEKLY OR MONTHLY EXPIRY DAYS ONLY",
        "Index data policy=EXACT -> PREVIOUS AVAILABLE CANDLE (NO LOOK-AHEAD)",
        "Live deployment note: live deployment will use broker API market data; historical gap fallback should normally never be exercised.",
        "=" * 200,
        f"EXPIRY={expiry}",
    ]

    index_id = repo.get_index_instrument_id(UNDERLYING, trading_date=trading_date)
    vix_id = repo.get_index_instrument_id(VIX_UNDERLYING, trading_date=trading_date)
    if index_id is None or vix_id is None:
        lines.append(f"RESULT=NO_ENTRY | reason=MISSING_INDEX_INSTRUMENT | index_id={index_id} | vix_id={vix_id}")
        _write(lines, log_path)
        return

    start = datetime.combine(trading_date, MARKET_OPEN, tzinfo=MARKET_TZ)
    end = datetime.combine(trading_date, FORCE_EXIT, tzinfo=MARKET_TZ)
    spot_df = repo.get_candles(index_id, start, end).set_index("ts")
    vix_df = repo.get_candles(vix_id, start, end).set_index("ts")
    if spot_df.empty or vix_df.empty:
        lines.append(f"RESULT=NO_ENTRY | reason=EMPTY_INDEX_DATA | spot_rows={len(spot_df)} | vix_rows={len(vix_df)}")
        _write(lines, log_path)
        return

    common_ts = sorted(set(spot_df.index) & set(vix_df.index))
    lines.append(f"SELECTED_INDEX_INSTRUMENT={index_id} | SELECTED_VIX_INSTRUMENT={vix_id}")
    lines.append(f"COMMON_NIFTY_VIX_TIMESTAMPS={len(common_ts)}")
    lines.append("TIME_IST | VIX | VIX_SOURCE_IST | NIFTY | NIFTY_SOURCE_IST | ATM | CE | PE | CE+PE | RESULT")
    lines.append("-" * 200)

    for ts in common_ts:
        market_time = ts.astimezone(MARKET_TZ).time().replace(tzinfo=None)
        if market_time >= FORCE_EXIT:
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

        if market_time < filters.entry_time or vix >= filters.india_vix_below:
            lines.append(f"{_market_ts(ts)} | {vix:.4f} | {vix_source_text} | {spot:.2f} | {nifty_source_text} | RESULT=SKIP_VIX | DATA={fallback_text}")
            continue
        strike = preferred_atm_strike(spot) if filters.only_100s else nearest_available_strike(expiry, spot)
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
        is_forced_candidate = filters.force_at_1501 and market_time >= FORCED_INITIAL_ENTRY
        forced_capped_out = (
            is_forced_candidate
            and filters.max_forced_entry_premium is not None
            and combined > filters.max_forced_entry_premium
        )
        forced_entry = is_forced_candidate and not forced_capped_out
        entry_allowed = (combined <= filters.combined_premium or forced_entry) and not forced_capped_out
        if forced_capped_out:
            result = "SKIP_FORCED_PREMIUM_CAP"
        elif forced_entry and combined > filters.combined_premium:
            result = "INITIAL_FORCED_1501"
        elif entry_allowed:
            result = "INITIAL_ENTRY"
        else:
            result = "SKIP_PREMIUM"
        lines.append(
            f"{_market_ts(ts)} | {vix:.4f} | {vix_source_text} | {spot:.2f} | {nifty_source_text} | ATM={strike} | "
            f"CE={ce_p:.2f} | PE={pe_p:.2f} | CE+PE={combined:.2f} | RESULT={result} | DATA={fallback_text}"
        )
        if entry_allowed:
            entry_reason = "INITIAL_FORCED_1501" if (forced_entry and combined > filters.combined_premium) else "INITIAL"
            lines.append(f"ENTRY_WOULD_BE_TAKEN={_market_ts(ts)} | REASON={entry_reason} | ATM={strike} | CE={ce_p:.2f} | PE={pe_p:.2f} | SUM={combined:.2f} | VIX={vix:.4f} | VIX_SOURCE={vix_source_text} | NIFTY_SOURCE={nifty_source_text}")
            logger.info(
                "[NIFTY ATM V6 DEBUG] ENTRY_WOULD_BE_TAKEN=%s | REASON=%s | ATM=%s | CE=%.2f | PE=%.2f | SUM=%.2f | VIX=%.4f | DATA=%s",
                _market_ts(ts), entry_reason, strike, ce_p, pe_p, combined, vix, fallback_text,
            )
            break
        # NOTE: no early `break` on time here (beyond the FORCE_EXIT check
        # above) -- forced-entry scanning must be allowed to continue past
        # 15:01 all the way to force-exit, per the V3 spec.
    lines.append("=== V6 INITIAL ENTRY SCAN END ===")
    _write(lines, log_path)


def pd_is_na(value) -> bool:
    return value is None or str(value) == "NaT"


def _write(lines: list[str], log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    logger.info("[NIFTY ATM V6 DEBUG] Entry diagnostic appended: %s", log_path)
