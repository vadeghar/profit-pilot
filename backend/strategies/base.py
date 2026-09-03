"""
Shared interface every strategy implements, so the backtest engine,
the FastAPI layer, and (later) the live/forward-test runner can all
work with any strategy the same way. Strategy 2, 3, etc. plug in here
the same way Blaze Butterfly does.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Optional


class ExitReason(str, Enum):
    TARGET = "TARGET"
    STOP_LOSS = "STOP_LOSS"
    EARLY_CUT = "EARLY_CUT"
    HARD_BACKSTOP = "HARD_BACKSTOP"
    TIME_EXIT = "TIME_EXIT"
    EXPIRY = "EXPIRY"


@dataclass
class Leg:
    instrument_id: int
    trading_symbol: str
    strike: float
    option_type: str  # "PE" or "CE"
    side: str          # "BUY" or "SELL"
    qty_lots: int
    lot_size: int
    entry_price: float = 0.0


@dataclass
class Position:
    entry_time: datetime
    expiry: date
    legs: list[Leg]
    deployed_margin: float
    reference_atm: float
    exit_time: Optional[datetime] = None
    exit_reason: Optional[ExitReason] = None
    pnl: float = 0.0

    @property
    def pnl_pct(self) -> float:
        if not self.deployed_margin:
            return 0.0
        return self.pnl / self.deployed_margin * 100

    def leg_mtm(self, current_prices: dict[int, float]) -> float:
        """Mark-to-market P&L across all legs given a map of instrument_id -> current price."""
        total = 0.0
        for leg in self.legs:
            price = current_prices.get(leg.instrument_id)
            if price is None:
                continue
            move = price - leg.entry_price
            signed = move if leg.side == "BUY" else -move
            total += signed * leg.qty_lots * leg.lot_size
        return total


class OptionsStrategy(ABC):
    name: str
    underlying: str

    @abstractmethod
    def entry_datetimes(self, start: date, end: date) -> list[datetime]:
        """All scheduled entry timestamps in [start, end]."""

    @abstractmethod
    def build_position(self, entry_time: datetime) -> Optional[Position]:
        """Construct the position for one entry, or None if data was unavailable."""

    @abstractmethod
    def check_exit(self, position: Position, bar_time: datetime, spot: float, mtm: float) -> Optional[ExitReason]:
        """Return an ExitReason if the position should be closed at bar_time, else None."""
