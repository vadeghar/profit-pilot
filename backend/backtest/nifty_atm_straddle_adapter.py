"""Event-driven adapter for the NIFTY ATM straddle state machine.

The database layer is responsible for producing chronologically ordered
observations. This adapter handles fills, partial exits, and P&L without using
the fixed-leg engine, which cannot represent averaging correctly.
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable
import logging

from strategies.nifty_atm_straddle import NiftyAtmStraddleStrategy, Observation, StraddleExitReason, StraddleState

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NiftyStraddleTrade:
    trading_date: date
    entry_time: datetime
    exit_time: datetime
    atm_strike: float
    exit_reason: str
    ce_lots_bought: int
    pe_lots_bought: int
    ce_lots_sold: int
    pe_lots_sold: int
    pnl: float


def run_day(observations: Iterable[Observation], lot_size: int = 65) -> NiftyStraddleTrade | None:
    """Run one day. Observations must be chronological and contain paired prices."""
    items = list(observations)
    if not items:
        logger.info("NIFTY straddle: no observations for day")
        return None
    strategy = NiftyAtmStraddleStrategy()
    cash = 0.0
    bought_ce = bought_pe = sold_ce = sold_pe = 0
    entry_time = exit_time = None
    last = items[-1]
    for observation in items:
        actions = strategy.on_observation(observation)
        for action in actions:
            cash += (action.ce_lots * observation.ce_price + action.pe_lots * observation.pe_price) * lot_size * (1 if action.kind == "SELL" else -1)
            if action.kind == "BUY":
                bought_ce += action.ce_lots
                bought_pe += action.pe_lots
                entry_time = entry_time or observation.timestamp
            else:
                sold_ce += action.ce_lots
                sold_pe += action.pe_lots
                exit_time = observation.timestamp
    if strategy.runtime.state.value != "CLOSED":
        # No 15:35 print: use the last paired candle as the mandated fallback.
        remaining_ce = strategy.runtime.ce_lots
        remaining_pe = strategy.runtime.pe_lots
        if remaining_ce or remaining_pe:
            cash += (remaining_ce * last.ce_price + remaining_pe * last.pe_price) * lot_size
            sold_ce += remaining_ce
            sold_pe += remaining_pe
        strategy.runtime.state = StraddleState.CLOSED
        strategy.runtime.exit_reason = strategy.runtime.exit_reason or StraddleExitReason.TIME_EXIT
        exit_time = last.timestamp
    if entry_time is None:
        logger.info("NIFTY straddle: no entry; observations=%d first=%s last=%s vix_min=%.2f vix_max=%.2f combined_min=%.2f combined_max=%.2f", len(items), items[0].timestamp, last.timestamp, min(x.india_vix for x in items), max(x.india_vix for x in items), min(x.combined_premium for x in items), max(x.combined_premium for x in items))
        return None
    trade = NiftyStraddleTrade(
        trading_date=items[0].timestamp.date(),
        entry_time=entry_time,
        exit_time=exit_time or last.timestamp,
        atm_strike=strategy.runtime.locked_atm_strike or 0,
        exit_reason=(strategy.runtime.exit_reason.value if strategy.runtime.exit_reason else "TIME_EXIT"),
        ce_lots_bought=bought_ce,
        pe_lots_bought=bought_pe,
        ce_lots_sold=sold_ce,
        pe_lots_sold=sold_pe,
        pnl=round(cash, 2),
    )
    logger.info("NIFTY straddle: TRADE completed day=%s entry=%s exit=%s atm=%s reason=%s bought=%d/%d sold=%d/%d pnl=%.2f", trade.trading_date, trade.entry_time, trade.exit_time, trade.atm_strike, trade.exit_reason, trade.ce_lots_bought, trade.pe_lots_bought, trade.ce_lots_sold, trade.pe_lots_sold, trade.pnl)
    return trade


def load_day_observations(trading_day: date) -> list[Observation]:
    """Load a day from DB, selecting the nearest expiry on/after that day.
    ATM is selected from spot until entry, then remains locked by the state machine."""
    from db import repository as repo
    expiries = repo.get_weekly_expiries("NIFTY 50", "CE", trading_day, limit=1)
    if not expiries:
        logger.warning("NIFTY straddle: no expiry found for trading_day=%s", trading_day)
        return []
    logger.info("NIFTY straddle: day=%s selected_expiry=%s", trading_day, expiries[0])
    frame = repo.get_straddle_observations(expiries[0], trading_day)
    if frame.empty:
        logger.warning("NIFTY straddle: zero joined option/spot/VIX rows day=%s expiry=%s", trading_day, expiries[0])
        return []
    observations = []
    for ts, group in frame.groupby("ts", sort=True):
        spot = float(group["spot"].iloc[0])
        atm = NiftyAtmStraddleStrategy.determine_atm_strike(spot)
        pair = group[group["strike"] == atm].set_index("instrument_type")
        if "CE" in pair.index and "PE" in pair.index:
            observations.append(Observation(
                timestamp=ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                spot=spot,
                india_vix=float(group["india_vix"].iloc[0]),
                ce_price=float(pair.loc["CE", "close"]),
                pe_price=float(pair.loc["PE", "close"]),
            ))
    logger.info("NIFTY straddle: day=%s raw_rows=%d paired_observations=%d", trading_day, len(frame), len(observations))
    return observations
