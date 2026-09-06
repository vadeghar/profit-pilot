"""Debug the V2 NIFTY ATM straddle entry scan for 2026-08-04.

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

Run from backend/ (or with backend on PYTHONPATH):
    python strategies/debug_nifty_atm_entry.py
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
    expiry = repo.get_weekly_expiries(UNDERLYING, "CE", on_or_after=TEST_DATE, limit=1)
    if not expiry:
        print(f"[{TEST_DATE}] No weekly expiry found")
        return
    expiry_date = expiry[0]

    index_id = repo.get_index_instrument_id(UNDERLYING)
    vix_id = repo.get_index_instrument_id(VIX_UNDERLYING)
    if index_id is None or vix_id is None:
        print(f"[{TEST_DATE}] Missing NIFTY/VIX INDEX instrument: index_id={index_id}, vix_id={vix_id}")
        return

    start = datetime.combine(TEST_DATE, MARKET_OPEN)
    end = datetime.combine(TEST_DATE, FORCE_EXIT)
    spot_df = repo.get_candles(index_id, start, end).set_index("ts")
    vix_df = repo.get_candles(vix_id, start, end).set_index("ts")

    print("=" * 180)
    print(f"NIFTY ATM STRADDLE V2 ENTRY DEBUG | DATE={TEST_DATE} | EXPIRY={expiry_date}")
    print(f"Window={start} -> {end} | VIX threshold < {VIX_MAX} | Combined premium <= {INITIAL_MAX_PREMIUM}")
    print("=" * 180)
    print(
        f"{'TIME':19} | {'VIX':7} | {'NIFTY':9} | {'ATM':7} | "
        f"{'CE':9} | {'PE':9} | {'CE+PE':9} | RESULT"
    )
    print("-" * 180)

    for ts in sorted(set(spot_df.index) & set(vix_df.index)):
        if market_time(ts) >= FORCE_EXIT:
            break

        vix = float(vix_df.loc[ts, "close"])
        spot = float(spot_df.loc[ts, "close"])

        if vix >= VIX_MAX:
            print(f"{ts!s:19} | {vix:7.2f} | {spot:9.2f} | {'-':7} | {'-':9} | {'-':9} | {'-':9} | SKIP: VIX >= 15")
            continue

        strike = repo.get_nearest_strike(UNDERLYING, "CE", expiry_date, spot)
        if strike is None:
            print(f"{ts!s:19} | {vix:7.2f} | {spot:9.2f} | {'-':7} | {'-':9} | {'-':9} | {'-':9} | SKIP: no ATM strike")
            continue

        ce = repo.get_instrument(UNDERLYING, "CE", expiry_date, strike)
        pe = repo.get_instrument(UNDERLYING, "PE", expiry_date, strike)
        if ce is None or pe is None:
            print(f"{ts!s:19} | {vix:7.2f} | {spot:9.2f} | {strike:7.0f} | {'-':9} | {'-':9} | {'-':9} | SKIP: missing CE/PE instrument")
            continue

        ce_p = repo.get_price_at_or_before(ce["id"], ts)
        pe_p = repo.get_price_at_or_before(pe["id"], ts)
        if ce_p is None or pe_p is None:
            print(f"{ts!s:19} | {vix:7.2f} | {spot:9.2f} | {strike:7.0f} | {str(ce_p):>9} | {str(pe_p):>9} | {'-':9} | SKIP: missing CE/PE price")
            continue

        combined = ce_p + pe_p
        if combined <= INITIAL_MAX_PREMIUM:
            result = "*** INITIAL ENTRY CONDITION MET ***"
        else:
            result = "SKIP: CE+PE > 50"

        print(
            f"{ts!s:19} | {vix:7.2f} | {spot:9.2f} | {strike:7.0f} | "
            f"{ce_p:9.2f} | {pe_p:9.2f} | {combined:9.2f} | {result}"
        )

        if combined <= INITIAL_MAX_PREMIUM:
            print(f"ENTRY WOULD BE TAKEN HERE: {ts} | ATM={strike} | CE={ce_p:.2f} | PE={pe_p:.2f} | SUM={combined:.2f} | VIX={vix:.2f}")
            break


if __name__ == "__main__":
    main()
