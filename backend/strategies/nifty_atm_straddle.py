"""NIFTY ATM CE+PE long straddle state machine.

The evaluator is deliberately independent of market-data and execution adapters.
Adapters provide observations and execute the returned actions; backtest and
deploy therefore share exactly the same trading rules.
"""
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from math import floor
from typing import Optional


class StraddleState(str, Enum):
    WAITING_FOR_ENTRY = "WAITING_FOR_ENTRY"
    INITIAL = "INITIAL"
    AFTER_2A = "AFTER_2A"
    AFTER_2B = "AFTER_2B"
    TARGETED_INITIAL = "TARGETED_INITIAL"
    TARGETED_2A = "TARGETED_2A"
    TARGETED_2B = "TARGETED_2B"
    CLOSED = "CLOSED"


class StraddleExitReason(str, Enum):
    COST_EXIT = "COST_EXIT"
    HARD_STOP_LOSS = "HARD_STOP_LOSS"
    TIME_EXIT = "TIME_EXIT"


@dataclass(frozen=True)
class Observation:
    timestamp: datetime
    spot: float
    india_vix: float
    ce_price: float
    pe_price: float

    @property
    def combined_premium(self) -> float:
        return self.ce_price + self.pe_price


@dataclass(frozen=True)
class Action:
    kind: str
    ce_lots: int = 0
    pe_lots: int = 0
    reason: Optional[str] = None


@dataclass
class StraddleRuntime:
    state: StraddleState = StraddleState.WAITING_FOR_ENTRY
    locked_atm_strike: Optional[float] = None
    ce_lots: int = 0
    pe_lots: int = 0
    cost_premium: Optional[float] = None
    target_done: bool = False
    level_2a_done: bool = False
    level_2b_done: bool = False
    entry_timestamp: Optional[datetime] = None
    target_timestamp: Optional[datetime] = None
    final_exit_timestamp: Optional[datetime] = None
    exit_reason: Optional[StraddleExitReason] = None


class NiftyAtmStraddleStrategy:
    name = "NIFTY ATM CE + PE Long Straddle"
    underlying = "NIFTY 50"
    strategy_id = "NK CAS NIFTY_ATM_STRADDLE_2PM_V1"
    start_date = date(2026, 8, 3)
    monitor_start = time(14, 0)
    force_exit = time(15, 35)

    @staticmethod
    def determine_atm_strike(spot: float) -> float:
        return floor(spot / 50 + 0.5) * 50

    @classmethod
    def eligible(cls, trading_date: date, mode: str, is_expiry_day: bool) -> str:
        if trading_date < cls.start_date:
            return "NOT_APPLICABLE"
        if mode == "DEPLOY" and not is_expiry_day:
            return "NOT_DEPLOYED_NON_EXPIRY_DAY"
        if mode not in {"BACKTEST", "DEPLOY"}:
            raise ValueError("mode must be BACKTEST or DEPLOY")
        return "ELIGIBLE"

    def __init__(self, runtime: Optional[StraddleRuntime] = None):
        self.runtime = runtime or StraddleRuntime()

    def on_observation(self, observation: Observation) -> list[Action]:
        r = self.runtime
        if r.state == StraddleState.CLOSED:
            return []
        if observation.timestamp.time() >= self.force_exit:
            return self._close(observation.timestamp, StraddleExitReason.TIME_EXIT)
        if r.state == StraddleState.WAITING_FOR_ENTRY:
            if observation.timestamp.time() < self.monitor_start:
                return []
            if observation.india_vix >= 15 or observation.combined_premium > 50:
                return []
            r.locked_atm_strike = self.determine_atm_strike(observation.spot)
            r.ce_lots = r.pe_lots = 2
            r.cost_premium = 50
            r.entry_timestamp = observation.timestamp
            r.state = StraddleState.INITIAL
            return [Action("BUY", 2, 2)]

        combined = observation.combined_premium
        if combined <= 8:
            return self._close(observation.timestamp, StraddleExitReason.HARD_STOP_LOSS)
        if r.target_done:
            if combined <= (r.cost_premium or 0):
                return self._close(observation.timestamp, StraddleExitReason.COST_EXIT)
            return []
        if r.state == StraddleState.INITIAL:
            if combined >= 100:
                return self._target(observation.timestamp, 1, StraddleState.TARGETED_INITIAL, 50)
            if combined <= 30:
                r.level_2a_done = True
                r.ce_lots = r.pe_lots = 4
                r.cost_premium = 30
                r.state = StraddleState.AFTER_2A
                return [Action("BUY", 2, 2)]
        elif r.state == StraddleState.AFTER_2A:
            if combined >= 65:
                return self._target(observation.timestamp, 2, StraddleState.TARGETED_2A, 30)
            if combined <= 20:
                r.level_2b_done = True
                r.ce_lots = r.pe_lots = 6
                r.cost_premium = 20
                r.state = StraddleState.AFTER_2B
                return [Action("BUY", 2, 2)]
        elif r.state == StraddleState.AFTER_2B and combined >= 45:
            return self._target(observation.timestamp, 3, StraddleState.TARGETED_2B, 20)
        return []

    def _target(self, timestamp: datetime, lots: int, state: StraddleState, cost: float) -> list[Action]:
        r = self.runtime
        r.ce_lots -= lots
        r.pe_lots -= lots
        r.target_done = True
        r.target_timestamp = timestamp
        r.cost_premium = cost
        r.state = state
        return [Action("SELL", lots, lots, "TARGET")]

    def _close(self, timestamp: datetime, reason: StraddleExitReason) -> list[Action]:
        r = self.runtime
        actions = [Action("SELL", r.ce_lots, r.pe_lots, reason.value)] if r.ce_lots or r.pe_lots else []
        r.ce_lots = r.pe_lots = 0
        r.state = StraddleState.CLOSED
        r.final_exit_timestamp = timestamp
        r.exit_reason = reason
        return actions
