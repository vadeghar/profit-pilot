"""DEPRECATED / ORPHANED -- do not use.

This script predates NiftyATMEntryFilters and nifty_atm_entry_debug_logger.py
(the diagnostic that's actually wired into the real backtest engine -- see
backend/backtest/atm_straddle_engine.py). It reimplements a V2-only,
hardcoded-single-date entry scan and is not imported or called from
anywhere else in the codebase. It was not deleted as part of the V6 fixes
only because no delete-file tool was available in that session.

Safe to delete this file entirely. If you need a manual one-off entry
scan, use nifty_atm_entry_debug_logger.run_entry_debug_log() instead --
it takes a real NiftyATMEntryFilters object and mirrors the strategy's
actual entry loop exactly.

Original docstring, kept for reference only (the behavior it describes
predates the V3/V4/V5/V6 fixes and should not be trusted):
    Debug the V2 NIFTY ATM straddle entry scan for 2026-08-04.
    This intentionally does not change strategy behavior. It reproduces the V2
    initial-entry scan and prints, for every eligible NIFTY/VIX timestamp:
      - timestamp
      - India VIX
      - NIFTY spot
      - ATM strike selected from the instrument master
      - CE close used by the strategy
      - PE close used by the strategy
      - combined CE + PE premium
      - eligibility / reason for skipping
"""
from datetime import date, datetime, time

from db import repository as repo

UNDERLYING = "NIFTY 50"
VIX_UNDERLYING = "INDIA VIX"
EXPIRY = None  # resolved from the nearest weekly expiry on/after the test date
TEST_DATE = date(2026, 8, 4)
MARKET_OPEN = time(9, 15)
FORCE_EXIT = time(15, 35)
VIX_MAX = 15.0
INITIAL_MAX_PREMIUM = 50.0


def market_time(ts: datetime) -> time:
    return ts.time().replace(tzinfo=None)


def main() -> None:
    raise RuntimeError(
        "debug_nifty_atm_entry.py is deprecated and orphaned -- use "
        "nifty_atm_entry_debug_logger.run_entry_debug_log() with a real "
        "NiftyATMEntryFilters instead. See this file's module docstring."
    )


if __name__ == "__main__":
    main()
