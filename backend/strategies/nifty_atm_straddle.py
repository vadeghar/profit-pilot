"""
Strategy: NIFTY ATM CE + PE Long Straddle Strategy
(strategy_id NK_CAS_NIFTY_ATM_STRADDLE_2PM_V1). See
NIFTY_ATM_STRADDLE.md for the full spec this implements.

Why this doesn't subclass strategies.base.OptionsStrategy:
The generic engine (backtest/engine.py) assumes one fixed entry timestamp
per trade, a static set of legs built once at entry, and a single full
exit. This strategy instead:
  - polls continuously from 2:00 PM for its entry condition (VIX + premium
    thresholds), rather than entering at a fixed clock time;
  - adds legs twice more intraday (2A, 2B averaging);
  - exits partially at each target level, then protects the remainder
    with a cost-based stop;
  - runs on ANY eligible trading day, not a fixed weekday.
So it gets its own self-contained state machine here, and its own
backtest runner in backend/backtest/atm_straddle_engine.py, which adapts
its richer trade record into the generic TradeResult shape so the
existing Strategy screen / BacktestModal UI renders it unchanged.

v1 scope decisions (flag if these need revisiting):
  - Current week's expiry (nearest expiry >= trading_date) is used for
    the CE/PE legs. The spec doesn't pin this down explicitly, but pairs
    naturally with the deploy-mode "expiry day only" restriction -- on an
    expiry day, the nearest expiry >= trading_date IS trading_date.
  - India VIX is read from instruments.underlying_symbol == 'INDIA VIX',
    instrument_type == 'INDEX'. Adjust VIX_UNDERLYING below if your DB
    uses a different symbol/convention for the VIX index row.
  - ATM strike = nearest available strike (from the instruments table,
    not a hard-coded 50-point rounding) to NIFTY spot at the moment the
    time / VIX / premium entry conditions are all first satisfied.
  - Intrabar execution policy (spec Section 14's note that a single 1-min
    candle can cross multiple levels): resolved deterministically by
    evaluating, per candle, in the exact priority order of Section 14 --
    force-exit -> hard SL -> cost exit -> target -> 2A -> 2B -- and using
    the WORST-CASE extreme of the candle for each check's direction:
    hard SL / averaging triggers (premium falling) use the combined
    LOW-proxy (CE.low + PE.low); target checks (premium rising) use the
    combined HIGH-proxy (CE.high + PE.high). This is a conservative
    approximation, since CE and PE highs/lows aren't necessarily
    coincident within the same minute -- a documented v1 choice, same
    spirit as blaze_butterfly.py's own documented v1 decisions. Revisit
    with tick data if the approximation matters for your P&L.
  - This IS the single deterministic state machine described in the
    spec's Section 25: run_strategy_for_day() below is meant to be
    called identically by the backtest runner and by a future live
    deployment runner -- only the `mode` eligibility gate differs.
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
# ASSUMPTION (flag if wrong): India VIX is stored as its own INDEX-type
# instrument row under this underlying_symbol.
VIX_UNDERLYING = "INDIA VIX"

ENTRY_WINDOW_START = time(14, 0)
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
MAX_LOTS_PER_LEG = 6  # reached automatically once 2B has fired; not separately enforced


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
    NO_ENTRY = "NO_ENTRY"  # eligible day, but entry conditions were never met


@dataclass
class StraddleTradeRecord:
    """Matches Section 23's trade record requirements. Fields for stages
    that did not occur are left as None, per the spec."""
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
    charges: Optional[float] = None  # no charges model yet -- left NULL per spec
    net_pnl: Optional[float] = None

    status: str = StrategyState.NO_ENTRY.value

    # Internal bookkeeping (not part of the Section 23 schema) used to
    # compute P&L incrementally and to render a leg-by-leg fill list for
    # the UI adapter in backend/backtest/atm_straddle_engine.py.
    fills: list = field(default_factory=list)

    @property
    def total_premium_outlay(self) -> float:
        """Total premium paid across all BUY fills -- used as the capital
        base for pnl_pct, since this is a long-premium strategy (no
        separate margin requirement to model)."""
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
    """Thin descriptor so this strategy can sit in api/main.py's STRATEGIES
    dict next to the OptionsStrategy-based strategies, without pretending
    to share their fixed-entry/fixed-legs engine (see module docstring).
    """
    name = "NIFTY ATM Straddle"
    underlying = UNDERLYING
    frequency = "Daily \u00b7 2:00 PM entry"
    strategy_id = STRATEGY_ID
    strategy_start_date = STRATEGY_START_DATE

    def run_for_day(self, trading_date: date, mode: Mode = Mode.BACKTEST) -> StraddleTradeRecord:
        return run_strategy_for_day(trading_date, mode=mode)


def _market_time(ts: datetime) -> time:
    if ts.tzinfo is not None:
        ts = ts.astimezone(MARKET_TZ)
    return ts.time().replace(tzinfo=None)


def _current_week_expiry(trading_date: date) -> Optional[date]:
    """Nearest CE expiry on/after trading_date -- on an expiry day itself,
    this IS trading_date."""
    expiries = repo.get_weekly_expiries(UNDERLYING, "CE", on_or_after=trading_date, limit=1)
    return expiries[0] if expiries else None


def _record_fill(record: StraddleTradeRecord, ts: datetime, action: str, option_type: str,
                  lots: int, price: float, tag: str) -> None:
    record.fills.append({
        "ts": ts, "action": action, "option_type": option_type,
        "lots": lots, "price": price, "tag": tag,
    })


def _exit_all(record: StraddleTradeRecord, ts: datetime, ce_close: float, pe_close: float,
              ce_lots: int, pe_lots: int, reason: str) -> None:
    if ce_lots > 0:
        record.ce_lots_sold += ce_lots
        _record_fill(record, ts, "SELL", "CE", ce_lots, ce_close, reason)
    if pe_lots > 0:
        record.pe_lots_sold += pe_lots
        _record_fill(record, ts, "SELL", "PE", pe_lots, pe_close, reason)
    record.final_exit_timestamp = ts
    record.final_exit_reason = reason
    record.realized_pnl = _compute_pnl(record)
    record.net_pnl = record.realized_pnl  # no charges model yet


def _compute_pnl(record: StraddleTradeRecord) -> float:
    """Every fill is against the same locked CE/PE contracts, so summing
    signed cash flows (SELL positive, BUY negative) gives the correct net
    P&L regardless of how many averaging/partial-exit batches occurred."""
    if not record.lot_size:
        return 0.0
    total = 0.0
    for f in record.fills:
        signed_price = f["price"] if f["action"] == "SELL" else -f["price"]
        total += signed_price * f["lots"] * record.lot_size
    return round(total, 2)


def run_strategy_for_day(trading_date: date, mode: Mode = Mode.BACKTEST) -> StraddleTradeRecord:
    """Section 17's pseudocode, implemented against 1-min candles.
    Returns a StraddleTradeRecord regardless of outcome; check `.status`
    (StrategyState values) to see what happened -- CLOSED means a trade
    actually ran; everything else means no trade was taken that day.
    """
    record = StraddleTradeRecord(trading_date=trading_date, mode=mode.value)

    # -- Section 3: applicability --
    if trading_date < STRATEGY_START_DATE:
        record.status = StrategyState.NOT_APPLICABLE.value
        return record

    expiry = _current_week_expiry(trading_date)
    record.expiry_date = expiry
    record.is_expiry_day = (expiry == trading_date) if expiry else None

    # -- Section 5: deploy-mode eligibility gate --
    if mode == Mode.DEPLOY and not record.is_expiry_day:
        record.status = StrategyState.NOT_DEPLOYED_NON_EXPIRY_DAY.value
        return record

    if expiry is None:
        logger.warning("[%s] SKIP: no NIFTY weekly expiry found on/after this date", trading_date)
        record.status = StrategyState.NO_ENTRY.value
        return record

    index_id = repo.get_index_instrument_id(UNDERLYING)
    vix_id = repo.get_index_instrument_id(VIX_UNDERLYING)
    if index_id is None or vix_id is None:
        if index_id is None:
            logger.warning("[%s] SKIP: no INDEX instrument row for underlying=%s", trading_date, UNDERLYING)
        if vix_id is None:
            logger.warning(
                "[%s] SKIP: no INDEX instrument row for underlying=%s -- adjust VIX_UNDERLYING "
                "if your DB uses a different symbol", trading_date, VIX_UNDERLYING,
            )
        record.status = StrategyState.NO_ENTRY.value
        return record

    entry_window_end = datetime.combine(trading_date, FORCE_EXIT_TIME)
    day_start = datetime.combine(trading_date, ENTRY_WINDOW_START)

    spot_df = repo.get_candles(index_id, day_start, entry_window_end)
    vix_df = repo.get_candles(vix_id, day_start, entry_window_end)
    if spot_df.empty or vix_df.empty:
        record.status = StrategyState.NO_ENTRY.value
        return record
    spot_df = spot_df.set_index("ts")
    vix_df = vix_df.set_index("ts")

    # -- Section 7: initial entry search (continuous polling from 14:00) --
    entry_ts = None
    locked_atm_strike = ce_instr = pe_instr = lot_size = None
    ce_price_at_entry = pe_price_at_entry = combined_at_entry = None
    vix_at_entry = spot_at_entry = None

    for ts in sorted(set(spot_df.index) & set(vix_df.index)):
        if _market_time(ts) >= FORCE_EXIT_TIME:
            break
        vix_val = float(vix_df.loc[ts, "close"])
        if vix_val >= VIX_MAX:
            continue
        spot = float(spot_df.loc[ts, "close"])
        strike = repo.get_nearest_strike(UNDERLYING, "CE", expiry, spot)
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
        if combined > INITIAL_ENTRY_MAX_PREMIUM:
            continue

        entry_ts = ts
        locked_atm_strike, ce_instr, pe_instr = strike, ce_candidate, pe_candidate
        lot_size = int(ce_instr["lot_size"])
        ce_price_at_entry, pe_price_at_entry, combined_at_entry = ce_p, pe_p, combined
        vix_at_entry, spot_at_entry = vix_val, spot
        break

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
    _record_fill(record, entry_ts, "BUY", "CE", INITIAL_LOTS, ce_price_at_entry, "INITIAL")
    _record_fill(record, entry_ts, "BUY", "PE", INITIAL_LOTS, pe_price_at_entry, "INITIAL")

    ce_df = repo.get_candles(ce_instr["id"], entry_ts, entry_window_end).set_index("ts")
    pe_df = repo.get_candles(pe_instr["id"], entry_ts, entry_window_end).set_index("ts")

    state = StrategyState.INITIAL
    record.status = state.value
    level_2a_done = level_2b_done = target_done = False
    ce_lots = pe_lots = INITIAL_LOTS
    cost_premium = INITIAL_ENTRY_MAX_PREMIUM

    common_ts = sorted(set(ce_df.index) & set(pe_df.index))

    for ts in common_ts:
        # The entry candle has already been consumed at the initial entry
        # price. Do not let its OHLC range immediately trigger 2A/2B or a
        # target; lifecycle rules begin with the next observation.
        if ts <= entry_ts:
            continue
        # -- Section 13: force exit, checked first every observation --
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

        # -- Section 12: hard stop, independent of stage --
        if combined_low <= HARD_STOP_PREMIUM:
            _exit_all(record, ts, ce_close, pe_close, ce_lots, pe_lots, "HARD_STOP_LOSS")
            record.hard_sl_timestamp = ts
            record.hard_sl_premium = combined_low
            record.status = StrategyState.CLOSED.value
            return record

        # -- Section 11: cost exit, only once a target has already fired --
        if target_done and combined_low <= cost_premium:
            _exit_all(record, ts, ce_close, pe_close, ce_lots, pe_lots, "COST_EXIT")
            record.status = StrategyState.CLOSED.value
            return record

        # -- Section 10: target rules (one per state, each fires once) --
        if state == StrategyState.INITIAL and combined_high >= INITIAL_TARGET:
            ce_lots -= 1
            pe_lots -= 1
            record.ce_lots_sold += 1
            record.pe_lots_sold += 1
            _record_fill(record, ts, "SELL", "CE", 1, ce_close, "TARGET_INITIAL")
            _record_fill(record, ts, "SELL", "PE", 1, pe_close, "TARGET_INITIAL")
            target_done, cost_premium = True, INITIAL_ENTRY_MAX_PREMIUM
            record.target_timestamp, record.target_level = ts, INITIAL_TARGET
            record.target_combined_premium, record.cost_premium = combined_close, cost_premium
            state = StrategyState.TARGETED_INITIAL
            record.status = state.value
            continue

        if state == StrategyState.AFTER_2A and combined_high >= LEVEL_2A_TARGET:
            ce_lots -= 2
            pe_lots -= 2
            record.ce_lots_sold += 2
            record.pe_lots_sold += 2
            _record_fill(record, ts, "SELL", "CE", 2, ce_close, "TARGET_2A")
            _record_fill(record, ts, "SELL", "PE", 2, pe_close, "TARGET_2A")
            target_done, cost_premium = True, LEVEL_2A_MAX_PREMIUM
            record.target_timestamp, record.target_level = ts, LEVEL_2A_TARGET
            record.target_combined_premium, record.cost_premium = combined_close, cost_premium
            state = StrategyState.TARGETED_2A
            record.status = state.value
            continue

        if state == StrategyState.AFTER_2B and combined_high >= LEVEL_2B_TARGET:
            ce_lots -= 3
            pe_lots -= 3
            record.ce_lots_sold += 3
            record.pe_lots_sold += 3
            _record_fill(record, ts, "SELL", "CE", 3, ce_close, "TARGET_2B")
            _record_fill(record, ts, "SELL", "PE", 3, pe_close, "TARGET_2B")
            target_done, cost_premium = True, LEVEL_2B_MAX_PREMIUM
            record.target_timestamp, record.target_level = ts, LEVEL_2B_TARGET
            record.target_combined_premium, record.cost_premium = combined_close, cost_premium
            state = StrategyState.TARGETED_2B
            record.status = state.value
            continue

        # -- Section 8: 2A averaging entry (only once, only from INITIAL) --
        if state == StrategyState.INITIAL and not level_2a_done and combined_low <= LEVEL_2A_MAX_PREMIUM:
            ce_lots += LEVEL_2A_ADD_LOTS
            pe_lots += LEVEL_2A_ADD_LOTS
            record.ce_lots_bought += LEVEL_2A_ADD_LOTS
            record.pe_lots_bought += LEVEL_2A_ADD_LOTS
            _record_fill(record, ts, "BUY", "CE", LEVEL_2A_ADD_LOTS, ce_close, "LEVEL_2A")
            _record_fill(record, ts, "BUY", "PE", LEVEL_2A_ADD_LOTS, pe_close, "LEVEL_2A")
            level_2a_done = True
            record.level_2a_timestamp = ts
            record.level_2a_ce_price, record.level_2a_pe_price = ce_close, pe_close
            record.level_2a_combined_premium = combined_close
            state = StrategyState.AFTER_2A
            record.status = state.value
            continue

        # -- Section 9: 2B averaging entry (only once, only from AFTER_2A) --
        if state == StrategyState.AFTER_2A and not level_2b_done and combined_low <= LEVEL_2B_MAX_PREMIUM:
            ce_lots += LEVEL_2B_ADD_LOTS
            pe_lots += LEVEL_2B_ADD_LOTS
            record.ce_lots_bought += LEVEL_2B_ADD_LOTS
            record.pe_lots_bought += LEVEL_2B_ADD_LOTS
            _record_fill(record, ts, "BUY", "CE", LEVEL_2B_ADD_LOTS, ce_close, "LEVEL_2B")
            _record_fill(record, ts, "BUY", "PE", LEVEL_2B_ADD_LOTS, pe_close, "LEVEL_2B")
            level_2b_done = True
            record.level_2b_timestamp = ts
            record.level_2b_ce_price, record.level_2b_pe_price = ce_close, pe_close
            record.level_2b_combined_premium = combined_close
            state = StrategyState.AFTER_2B
            record.status = state.value
            continue

    # Ran out of candle data before 15:35 (partial/missing day) -- close at
    # the last available mark rather than silently leaving a position open.
    if common_ts:
        last_ts = common_ts[-1]
        ce_close = float(ce_df.loc[last_ts, "close"])
        pe_close = float(pe_df.loc[last_ts, "close"])
        _exit_all(record, last_ts, ce_close, pe_close, ce_lots, pe_lots, "TIME_EXIT")
        record.status = StrategyState.CLOSED.value

    return record
