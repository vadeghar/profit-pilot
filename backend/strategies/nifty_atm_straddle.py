"""
Strategy: NIFTY ATM CE + PE Long Straddle Strategy
(strategy_id NK_CAS_NIFTY_ATM_STRADDLE_2PM_V1). See
NIFTY_ATM_STRADDLE.md for the full spec this implements.

V3 entry change ("3pm is my price"):
  - Before 3:01 PM, the normal entry rule remains India VIX < 15 and
    combined CE + PE premium <= 50.
  - If no initial entry has occurred by 3:01 PM, the 3:01 PM NIFTY spot
    becomes the entry spot/ATM reference and the first trade is initiated,
    even when the combined CE + PE premium is above 50.
  - The India VIX < 15 condition remains mandatory for the forced 3:01 PM
    entry.
  - Once entered, all averaging, target, cost-exit, hard-stop and 15:35
    force-exit rules remain unchanged.

V4 strike selection change:
  - ATM strikes are rounded to the nearest 100-point strike; 50-point
    strikes are never selected.

V5: entry rules (V1/V2/V3 time gates, V4 strike rounding) were unified
into a single NiftyATMEntryFilters object so the Strategy screen can
expose them as UI filters instead of shipping four near-duplicate branches.

V6 fixes (see PR description for the full review that found these):
  - Non-100s strike selection is back to the DB-backed nearest-listed
    strike instead of a pure rounding formula.
  - Optional max_forced_entry_premium and hard_stop_pct filters let the
    forced-entry risk and the hard stop scale sensibly instead of being
    uncapped / fixed regardless of how rich the entry premium was.
  - Target/stop/cost-exit fills are priced at the threshold actually
    touched, not the bar's raw close.
  - net_pnl now subtracts an estimated transaction-cost model instead of
    always equaling the pre-cost realized_pnl.

V6 entry-window correction (post-review adjustment):
  - No entry -- normal or forced -- may ever occur after 15:01, full
    stop. The scan itself never looks past that boundary. When
    force_at_1501 is on and no normal entry happened by 15:01, exactly
    one forced-entry attempt is made using the last available NIFTY/VIX
    observation at or before 15:01 (whatever the CE+PE premium is at
    that point, VIX permitting) -- there is no further scanning toward
    15:35 hoping for a better VIX reading. This replaces an earlier
    "keep scanning to force-exit" interpretation that turned out not to
    match the intended design: the 15:01 cutoff is a hard ceiling on
    when a trade can be entered, not just a checkpoint.
  - Default filters changed to entry_time=14:00, only_100s=False,
    force_at_1501=True -- i.e. the default preset now matches the V3
    entry-time/strike behavior (2:00 PM start, 50-point strikes, forced
    3:01 PM fallback) rather than a bare market-open scan.

Scope:
  - This strategy is STRICTLY for NIFTY expiry trading days.
  - Expiry eligibility and actual expiry dates come from
    public.nifty_expiry_calendar (underlying='NIFTY', expiry_type='WEEKLY' or 'MONTHLY').
  - scheduled_date is considered so holiday-shifted expiries are handled;
    expiry_date is the actual trading/expiry date used by the strategy.
  - Non-expiry dates are ignored before any market-data or option calculation.

Why this doesn't subclass strategies.base.OptionsStrategy:
The generic engine assumes one fixed entry timestamp per trade, a static set
of legs built once at entry, and a single full exit. This strategy instead:
  - polls continuously from market open for its entry;
  - has a 3:01 PM forced initial-entry fallback;
  - adds legs twice more intraday (2A, 2B averaging);
  - exits partially at each target level, then protects the remainder with
    a cost-based stop;
  - runs its own state machine and backtest adapter.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

from db import repository as repo

logger = logging.getLogger(__name__)

STRATEGY_ID = "NK_CAS_NIFTY_ATM_STRADDLE_2PM_V1"
STRATEGY_START_DATE = date(2026, 8, 3)

UNDERLYING = "NIFTY 50"
VIX_UNDERLYING = "INDIA VIX"

MARKET_OPEN_TIME = time(9, 15)
DEFAULT_ENTRY_TIME = time(14, 0)
FORCED_INITIAL_ENTRY_TIME = time(15, 1)
FORCE_EXIT_TIME = time(15, 35)
MARKET_TZ = ZoneInfo("Asia/Kolkata")

VIX_MAX = 15.0
INITIAL_ENTRY_MAX_PREMIUM = 50.0
LEVEL_2A_MAX_PREMIUM = 30.0
LEVEL_2B_MAX_PREMIUM = 20.0
INITIAL_TARGET = 100.0
LEVEL_2A_TARGET = 65.0
LEVEL_2B_TARGET = 45.0
HARD_STOP_PREMIUM = 8.0
INITIAL_LOTS = 2
LEVEL_2A_ADD_LOTS = 2
LEVEL_2B_ADD_LOTS = 2
MAX_LOTS_PER_LEG = 6

# --- Illustrative NSE F&O options transaction-cost model -------------------
# These are approximate, commonly-cited rates and WILL drift from reality --
# update them to match your actual broker's contract note / the current
# exchange & regulatory schedule before trusting net_pnl for sizing decisions.
BROKERAGE_PER_ORDER = 20.0            # flat Rs per executed leg (typical discount-broker cap)
EXCHANGE_TXN_CHARGE_PCT = 0.03503 / 100  # NSE F&O options, % of premium turnover, both sides
SEBI_CHARGE_PCT = 10 / 1_00_00_000    # Rs 10 per crore of turnover
STT_SELL_PCT = 0.1 / 100              # STT on options SELL-side premium turnover only
STAMP_DUTY_BUY_PCT = 0.003 / 100      # stamp duty on options BUY-side premium turnover only
GST_PCT = 18 / 100                    # GST on (brokerage + exchange txn charge + SEBI charge)


def estimate_charges(fills: list, lot_size: Optional[int]) -> float:
    """Illustrative total transaction cost across every fill in a trade.

    NOT a substitute for your actual contract note -- the constants above
    are approximate and change periodically. This exists so net_pnl isn't
    silently identical to the pre-cost realized_pnl.
    """
    if not lot_size or not fills:
        return 0.0
    total = 0.0
    for f in fills:
        turnover = f["price"] * f["lots"] * lot_size
        brokerage = BROKERAGE_PER_ORDER
        exchange_txn = turnover * EXCHANGE_TXN_CHARGE_PCT
        sebi = turnover * SEBI_CHARGE_PCT
        gst = (brokerage + exchange_txn + sebi) * GST_PCT
        stt = turnover * STT_SELL_PCT if f["action"] == "SELL" else 0.0
        stamp_duty = turnover * STAMP_DUTY_BUY_PCT if f["action"] == "BUY" else 0.0
        total += brokerage + exchange_txn + sebi + gst + stt + stamp_duty
    return round(total, 2)


def preferred_atm_strike(spot: float) -> float:
    """Round NIFTY spot to the nearest 100-point strike, never a 50-point strike.

    This is a deliberate V4 strike-selection *policy* (fewer strike/instrument
    switches during the day), not a stand-in for a DB lookup -- unlike
    nearest_available_strike() below, it intentionally does not consult the
    instruments table.
    """
    import math
    return float(math.floor(spot / 100.0 + 0.5) * 100)


def nearest_available_strike(expiry: date, spot: float) -> Optional[float]:
    """DB-backed nearest *listed* strike -- matches V1-V3 exactly.

    Used when the "only 100s" filter is off. V5 had replaced this with a
    pure floor/round formula that assumed a perfectly uniform 50-point
    strike ladder always exists; this restores the original behavior of
    asking the instrument master for the actual closest listed strike.
    """
    return repo.get_nearest_strike(UNDERLYING, "CE", expiry, spot)


@dataclass(frozen=True)
class NiftyATMEntryFilters:
    entry_time: time = DEFAULT_ENTRY_TIME
    india_vix_below: float = VIX_MAX
    combined_premium: float = INITIAL_ENTRY_MAX_PREMIUM
    only_100s: bool = False
    force_at_1501: bool = True
    max_forced_entry_premium: Optional[float] = None
    hard_stop_pct: Optional[float] = None


class Mode(str, Enum):
    BACKTEST = "BACKTEST"
    DEPLOY = "DEPLOY"


class StrategyState(str, Enum):
    WAITING_FOR_ENTRY = "WAITING_FOR_ENTRY"
    INITIAL = "INITIAL"
    AFTER_2A = "AFTER_2A"
    AFTER_2B = "AFTER_2B"
    TARGETED_INITIAL = "TARGETED_INITIAL"
    TARGETED_2A = "TARGETED_2A"
    TARGETED_2B = "TARGETED_2B"
    CLOSED = "CLOSED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NOT_DEPLOYED_NON_EXPIRY_DAY = "NOT_DEPLOYED_NON_EXPIRY_DAY"
    NO_ENTRY = "NO_ENTRY"


@dataclass
class StraddleTradeRecord:
    strategy_id: str = STRATEGY_ID
    mode: str = Mode.BACKTEST.value
    trading_date: Optional[date] = None
    expiry_date: Optional[date] = None
    is_expiry_day: Optional[bool] = None
    initial_entry_timestamp: Optional[datetime] = None
    initial_entry_spot: Optional[float] = None
    atm_strike: Optional[float] = None
    lot_size: Optional[int] = None
    ce_instrument_id: Optional[int] = None
    pe_instrument_id: Optional[int] = None
    ce_trading_symbol: Optional[str] = None
    pe_trading_symbol: Optional[str] = None
    initial_ce_price: Optional[float] = None
    initial_pe_price: Optional[float] = None
    initial_combined_premium: Optional[float] = None
    vix_at_entry: Optional[float] = None
    level_2a_timestamp: Optional[datetime] = None
    level_2a_ce_price: Optional[float] = None
    level_2a_pe_price: Optional[float] = None
    level_2a_combined_premium: Optional[float] = None
    level_2b_timestamp: Optional[datetime] = None
    level_2b_ce_price: Optional[float] = None
    level_2b_pe_price: Optional[float] = None
    level_2b_combined_premium: Optional[float] = None
    target_timestamp: Optional[datetime] = None
    target_level: Optional[float] = None
    target_combined_premium: Optional[float] = None
    cost_premium: Optional[float] = None
    hard_sl_timestamp: Optional[datetime] = None
    hard_sl_premium: Optional[float] = None
    final_exit_timestamp: Optional[datetime] = None
    final_exit_reason: Optional[str] = None
    ce_lots_bought: int = 0
    pe_lots_bought: int = 0
    ce_lots_sold: int = 0
    pe_lots_sold: int = 0
    realized_pnl: float = 0.0
    charges: Optional[float] = None
    net_pnl: Optional[float] = None
    status: str = StrategyState.NO_ENTRY.value
    fills: list = field(default_factory=list)

    @property
    def total_premium_outlay(self) -> float:
        if not self.lot_size:
            return 0.0
        return sum(f["price"] * f["lots"] * self.lot_size for f in self.fills if f["action"] == "BUY")

    @property
    def pnl_pct(self) -> float:
        outlay = self.total_premium_outlay
        if not outlay:
            return 0.0
        return self.realized_pnl / outlay * 100


class NiftyATMStraddleStrategy:
    name = "NIFTY ATM Straddle"
    underlying = UNDERLYING
    frequency = "NIFTY weekly/monthly expiry days · configurable entry-time/VIX/premium/strike filters, optional 3:01 PM forced entry"
    strategy_id = STRATEGY_ID
    strategy_start_date = STRATEGY_START_DATE

    def run_for_day(self, trading_date: date, mode: Mode = Mode.BACKTEST, filters: Optional[NiftyATMEntryFilters] = None) -> StraddleTradeRecord:
        return run_strategy_for_day(trading_date, mode=mode, filters=filters)


def _market_time(ts: datetime) -> time:
    if ts.tzinfo is not None:
        ts = ts.astimezone(MARKET_TZ)
    return ts.time().replace(tzinfo=None)


def _current_expiry(trading_date: date) -> Optional[date]:
    expiries = repo.get_nifty_expiry_dates(UNDERLYING, on_or_after=trading_date, limit=1)
    return expiries[0] if expiries else None


def _record_fill(record: StraddleTradeRecord, ts: datetime, action: str, option_type: str, lots: int, price: float, tag: str) -> None:
    record.fills.append({"ts": ts, "action": action, "option_type": option_type, "lots": lots, "price": price, "tag": tag})


def _threshold_fill_prices(ce_close: float, pe_close: float, threshold: float) -> tuple[float, float]:
    """Approximate the CE/PE split at the moment the combined premium
    touched `threshold` intrabar, by scaling the bar's close prices so
    they sum to the threshold instead of crediting/charging the trade at
    an arbitrary close price that may be far from what was actually
    touched. Falls back to the raw close prices if the bar's close sum
    is degenerate (<=0).
    """
    combined_close = ce_close + pe_close
    if combined_close <= 0:
        return ce_close, pe_close
    scale = threshold / combined_close
    return round(ce_close * scale, 2), round(pe_close * scale, 2)


def _exit_all(record: StraddleTradeRecord, ts: datetime, ce_fill: float, pe_fill: float, ce_lots: int, pe_lots: int, reason: str) -> None:
    if ce_lots > 0:
        record.ce_lots_sold += ce_lots
        _record_fill(record, ts, "SELL", "CE", ce_lots, ce_fill, reason)
    if pe_lots > 0:
        record.pe_lots_sold += pe_lots
        _record_fill(record, ts, "SELL", "PE", pe_lots, pe_fill, reason)
    record.final_exit_timestamp = ts
    record.final_exit_reason = reason
    record.realized_pnl = _compute_pnl(record)
    record.charges = estimate_charges(record.fills, record.lot_size)
    record.net_pnl = round(record.realized_pnl - record.charges, 2)


def _compute_pnl(record: StraddleTradeRecord) -> float:
    if not record.lot_size:
        return 0.0
    total = 0.0
    for f in record.fills:
        signed_price = f["price"] if f["action"] == "SELL" else -f["price"]
        total += signed_price * f["lots"] * record.lot_size
    return round(total, 2)


def run_strategy_for_day(trading_date: date, mode: Mode = Mode.BACKTEST, filters: Optional[NiftyATMEntryFilters] = None) -> StraddleTradeRecord:
    """Run the state machine only on a NIFTY weekly or monthly expiry day."""
    record = StraddleTradeRecord(trading_date=trading_date, mode=mode.value)
    filters = filters or NiftyATMEntryFilters()

    if trading_date < STRATEGY_START_DATE:
        record.status = StrategyState.NOT_APPLICABLE.value
        return record

    expiry = _current_expiry(trading_date)
    record.expiry_date = expiry
    record.is_expiry_day = (expiry == trading_date) if expiry else False

    # HARD SCOPE RULE: this strategy is expiry-day-only in BOTH backtest and deploy.
    if not record.is_expiry_day:
        record.status = (
            StrategyState.NOT_DEPLOYED_NON_EXPIRY_DAY.value
            if mode == Mode.DEPLOY
            else StrategyState.NOT_APPLICABLE.value
        )
        return record

    if expiry is None:
        logger.warning("[%s] SKIP: no NIFTY weekly/monthly expiry found in nifty_expiry_calendar", trading_date)
        record.status = StrategyState.NO_ENTRY.value
        return record

    index_id = repo.get_index_instrument_id(UNDERLYING, trading_date=trading_date)
    vix_id = repo.get_index_instrument_id(VIX_UNDERLYING, trading_date=trading_date)
    if index_id is None or vix_id is None:
        if index_id is None:
            logger.warning("[%s] SKIP: no INDEX instrument row for underlying=%s", trading_date, UNDERLYING)
        if vix_id is None:
            logger.warning("[%s] SKIP: no INDEX instrument row for underlying=%s", trading_date, VIX_UNDERLYING)
        record.status = StrategyState.NO_ENTRY.value
        return record

    entry_window_end = datetime.combine(trading_date, FORCE_EXIT_TIME, tzinfo=MARKET_TZ)
    day_start = datetime.combine(trading_date, MARKET_OPEN_TIME, tzinfo=MARKET_TZ)

    spot_df = repo.get_candles(index_id, day_start, entry_window_end)
    vix_df = repo.get_candles(vix_id, day_start, entry_window_end)
    if spot_df.empty or vix_df.empty:
        record.status = StrategyState.NO_ENTRY.value
        return record
    spot_df = spot_df.set_index("ts")
    vix_df = vix_df.set_index("ts")

    entry_ts = None
    locked_atm_strike = ce_instr = pe_instr = lot_size = None
    ce_price_at_entry = pe_price_at_entry = combined_at_entry = None
    vix_at_entry = spot_at_entry = None
    forced_entry = False
    last_ts_at_or_before_cutoff = None

    # HARD RULE: no entry -- normal or forced -- may ever occur after
    # FORCED_INITIAL_ENTRY_TIME (15:01). The scan itself never looks past
    # that boundary. If force_at_1501 is on and nothing qualified during
    # the scan, exactly one forced-entry attempt is made afterwards using
    # the last available observation at or before the cutoff -- there is
    # no further scanning toward 15:35 looking for a better VIX reading.
    for ts in sorted(set(spot_df.index) & set(vix_df.index)):
        market_time = _market_time(ts)
        if market_time > FORCED_INITIAL_ENTRY_TIME:
            break
        last_ts_at_or_before_cutoff = ts

        vix_val = float(vix_df.loc[ts, "close"])
        if market_time < filters.entry_time or vix_val >= filters.india_vix_below:
            continue

        spot = float(spot_df.loc[ts, "close"])
        strike = preferred_atm_strike(spot) if filters.only_100s else nearest_available_strike(expiry, spot)
        if strike is None:
            continue
        ce_candidate = repo.get_instrument(UNDERLYING, "CE", expiry, strike)
        pe_candidate = repo.get_instrument(UNDERLYING, "PE", expiry, strike)
        if ce_candidate is None or pe_candidate is None:
            continue
        ce_p = repo.get_price_at_or_before(ce_candidate["id"], ts)
        pe_p = repo.get_price_at_or_before(pe_candidate["id"], ts)
        if ce_p is None or pe_p is None:
            continue

        combined = ce_p + pe_p
        if combined <= filters.combined_premium:
            entry_ts = ts
            locked_atm_strike, ce_instr, pe_instr = strike, ce_candidate, pe_candidate
            lot_size = int(ce_instr["lot_size"])
            ce_price_at_entry, pe_price_at_entry, combined_at_entry = ce_p, pe_p, combined
            vix_at_entry, spot_at_entry = vix_val, spot
            break

    if entry_ts is None and filters.force_at_1501 and last_ts_at_or_before_cutoff is not None:
        # "3pm is my price": take the ATM CE+PE at whatever price they're
        # at by the cutoff, regardless of the normal premium ceiling --
        # but never past the cutoff, and VIX must still be below the
        # threshold.
        ts = last_ts_at_or_before_cutoff
        vix_val = float(vix_df.loc[ts, "close"])
        if vix_val < filters.india_vix_below:
            spot = float(spot_df.loc[ts, "close"])
            strike = preferred_atm_strike(spot) if filters.only_100s else nearest_available_strike(expiry, spot)
            ce_candidate = repo.get_instrument(UNDERLYING, "CE", expiry, strike) if strike is not None else None
            pe_candidate = repo.get_instrument(UNDERLYING, "PE", expiry, strike) if strike is not None else None
            ce_p = repo.get_price_at_or_before(ce_candidate["id"], ts) if ce_candidate is not None else None
            pe_p = repo.get_price_at_or_before(pe_candidate["id"], ts) if pe_candidate is not None else None
            if ce_p is not None and pe_p is not None:
                combined = ce_p + pe_p
                if filters.max_forced_entry_premium is None or combined <= filters.max_forced_entry_premium:
                    entry_ts = ts
                    forced_entry = True
                    locked_atm_strike, ce_instr, pe_instr = strike, ce_candidate, pe_candidate
                    lot_size = int(ce_instr["lot_size"])
                    ce_price_at_entry, pe_price_at_entry, combined_at_entry = ce_p, pe_p, combined
                    vix_at_entry, spot_at_entry = vix_val, spot

    if entry_ts is None:
        record.status = StrategyState.NO_ENTRY.value
        return record

    record.initial_entry_timestamp = entry_ts
    record.initial_entry_spot = spot_at_entry
    record.atm_strike = locked_atm_strike
    record.lot_size = lot_size
    record.ce_instrument_id = ce_instr["id"]
    record.pe_instrument_id = pe_instr["id"]
    record.ce_trading_symbol = ce_instr["trading_symbol"]
    record.pe_trading_symbol = pe_instr["trading_symbol"]
    record.initial_ce_price = ce_price_at_entry
    record.initial_pe_price = pe_price_at_entry
    record.initial_combined_premium = combined_at_entry
    record.vix_at_entry = vix_at_entry
    record.ce_lots_bought = INITIAL_LOTS
    record.pe_lots_bought = INITIAL_LOTS
    entry_tag = "INITIAL_FORCED_1501" if forced_entry else "INITIAL"
    _record_fill(record, entry_ts, "BUY", "CE", INITIAL_LOTS, ce_price_at_entry, entry_tag)
    _record_fill(record, entry_ts, "BUY", "PE", INITIAL_LOTS, pe_price_at_entry, entry_tag)

    # Hard stop scales with the actual entry premium when hard_stop_pct is
    # set; otherwise keep the fixed absolute value for backward compatibility.
    hard_stop_level = (
        round(combined_at_entry * filters.hard_stop_pct, 2)
        if filters.hard_stop_pct is not None
        else HARD_STOP_PREMIUM
    )

    ce_df = repo.get_candles(ce_instr["id"], entry_ts, entry_window_end).set_index("ts")
    pe_df = repo.get_candles(pe_instr["id"], entry_ts, entry_window_end).set_index("ts")

    state = StrategyState.INITIAL
    record.status = state.value
    level_2a_done = level_2b_done = target_done = False
    ce_lots = pe_lots = INITIAL_LOTS
    # A forced entry above the table's assumed ceiling must not set a
    # cost-protection level below what was actually paid.
    cost_premium = max(INITIAL_ENTRY_MAX_PREMIUM, combined_at_entry)
    common_ts = sorted(set(ce_df.index) & set(pe_df.index))

    for ts in common_ts:
        if ts <= entry_ts:
            continue
        if _market_time(ts) >= FORCE_EXIT_TIME:
            ce_close = float(ce_df.loc[ts, "close"])
            pe_close = float(pe_df.loc[ts, "close"])
            _exit_all(record, ts, ce_close, pe_close, ce_lots, pe_lots, "TIME_EXIT")
            record.status = StrategyState.CLOSED.value
            return record

        ce_bar, pe_bar = ce_df.loc[ts], pe_df.loc[ts]
        ce_close, pe_close = float(ce_bar["close"]), float(pe_bar["close"])
        combined_close = ce_close + pe_close
        combined_low = float(ce_bar["low"]) + float(pe_bar["low"])
        combined_high = float(ce_bar["high"]) + float(pe_bar["high"])

        if combined_low <= hard_stop_level:
            ce_fill, pe_fill = _threshold_fill_prices(ce_close, pe_close, hard_stop_level)
            _exit_all(record, ts, ce_fill, pe_fill, ce_lots, pe_lots, "HARD_STOP_LOSS")
            record.hard_sl_timestamp = ts
            record.hard_sl_premium = combined_low
            record.status = StrategyState.CLOSED.value
            return record

        if target_done and combined_low <= cost_premium:
            ce_fill, pe_fill = _threshold_fill_prices(ce_close, pe_close, cost_premium)
            _exit_all(record, ts, ce_fill, pe_fill, ce_lots, pe_lots, "COST_EXIT")
            record.status = StrategyState.CLOSED.value
            return record

        if state == StrategyState.INITIAL and combined_high >= INITIAL_TARGET:
            ce_fill, pe_fill = _threshold_fill_prices(ce_close, pe_close, INITIAL_TARGET)
            ce_lots -= 1; pe_lots -= 1
            record.ce_lots_sold += 1; record.pe_lots_sold += 1
            _record_fill(record, ts, "SELL", "CE", 1, ce_fill, "TARGET_INITIAL")
            _record_fill(record, ts, "SELL", "PE", 1, pe_fill, "TARGET_INITIAL")
            target_done, cost_premium = True, max(INITIAL_ENTRY_MAX_PREMIUM, combined_at_entry)
            record.target_timestamp, record.target_level = ts, INITIAL_TARGET
            record.target_combined_premium, record.cost_premium = ce_fill + pe_fill, cost_premium
            state = StrategyState.TARGETED_INITIAL; record.status = state.value
            continue

        if state == StrategyState.AFTER_2A and combined_high >= LEVEL_2A_TARGET:
            ce_fill, pe_fill = _threshold_fill_prices(ce_close, pe_close, LEVEL_2A_TARGET)
            ce_lots -= 2; pe_lots -= 2
            record.ce_lots_sold += 2; record.pe_lots_sold += 2
            _record_fill(record, ts, "SELL", "CE", 2, ce_fill, "TARGET_2A")
            _record_fill(record, ts, "SELL", "PE", 2, pe_fill, "TARGET_2A")
            target_done, cost_premium = True, LEVEL_2A_MAX_PREMIUM
            record.target_timestamp, record.target_level = ts, LEVEL_2A_TARGET
            record.target_combined_premium, record.cost_premium = ce_fill + pe_fill, cost_premium
            state = StrategyState.TARGETED_2A; record.status = state.value
            continue

        if state == StrategyState.AFTER_2B and combined_high >= LEVEL_2B_TARGET:
            ce_fill, pe_fill = _threshold_fill_prices(ce_close, pe_close, LEVEL_2B_TARGET)
            ce_lots -= 3; pe_lots -= 3
            record.ce_lots_sold += 3; record.pe_lots_sold += 3
            _record_fill(record, ts, "SELL", "CE", 3, ce_fill, "TARGET_2B")
            _record_fill(record, ts, "SELL", "PE", 3, pe_fill, "TARGET_2B")
            target_done, cost_premium = True, LEVEL_2B_MAX_PREMIUM
            record.target_timestamp, record.target_level = ts, LEVEL_2B_TARGET
            record.target_combined_premium, record.cost_premium = ce_fill + pe_fill, cost_premium
            state = StrategyState.TARGETED_2B; record.status = state.value
            continue

        if state == StrategyState.INITIAL and not level_2a_done and combined_low <= LEVEL_2A_MAX_PREMIUM:
            ce_lots += LEVEL_2A_ADD_LOTS; pe_lots += LEVEL_2A_ADD_LOTS
            record.ce_lots_bought += LEVEL_2A_ADD_LOTS; record.pe_lots_bought += LEVEL_2A_ADD_LOTS
            _record_fill(record, ts, "BUY", "CE", LEVEL_2A_ADD_LOTS, ce_close, "LEVEL_2A")
            _record_fill(record, ts, "BUY", "PE", LEVEL_2A_ADD_LOTS, pe_close, "LEVEL_2A")
            level_2a_done = True
            record.level_2a_timestamp = ts
            record.level_2a_ce_price, record.level_2a_pe_price = ce_close, pe_close
            record.level_2a_combined_premium = combined_close
            state = StrategyState.AFTER_2A; record.status = state.value
            continue

        if state == StrategyState.AFTER_2A and not level_2b_done and combined_low <= LEVEL_2B_MAX_PREMIUM:
            ce_lots += LEVEL_2B_ADD_LOTS; pe_lots += LEVEL_2B_ADD_LOTS
            record.ce_lots_bought += LEVEL_2B_ADD_LOTS; record.pe_lots_bought += LEVEL_2B_ADD_LOTS
            _record_fill(record, ts, "BUY", "CE", LEVEL_2B_ADD_LOTS, ce_close, "LEVEL_2B")
            _record_fill(record, ts, "BUY", "PE", LEVEL_2B_ADD_LOTS, pe_close, "LEVEL_2B")
            level_2b_done = True
            record.level_2b_timestamp = ts
            record.level_2b_ce_price, record.level_2b_pe_price = ce_close, pe_close
            record.level_2b_combined_premium = combined_close
            state = StrategyState.AFTER_2B; record.status = state.value
            continue

    if common_ts:
        last_ts = common_ts[-1]
        ce_close = float(ce_df.loc[last_ts, "close"])
        pe_close = float(pe_df.loc[last_ts, "close"])
        _exit_all(record, last_ts, ce_close, pe_close, ce_lots, pe_lots, "TIME_EXIT")
        record.status = StrategyState.CLOSED.value

    return record
