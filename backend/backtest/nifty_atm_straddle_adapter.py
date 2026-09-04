"""Event-driven adapter for the NIFTY ATM straddle state machine.

The database layer is responsible for producing chronologically ordered
observations. This adapter handles fills, partial exits, and P&L without using
the fixed-leg engine, which cannot represent averaging correctly.
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from strategies.nifty_atm_straddle import NiftyAtmStraddleStrategy, Observation, StraddleExitReason, StraddleState


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
        return None
    return NiftyStraddleTrade(
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
