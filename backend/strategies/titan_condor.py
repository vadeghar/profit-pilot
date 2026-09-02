"""Strategy 10: NIFTY Titan Condor (weekly low-probability iron condor).

The implementation follows the supplied transcript:
- enter Friday at 15:16;
- skip the nearest weekly expiry and use the following Tuesday expiry;
- sell call/put approximately 400 points from spot on 100-point strikes;
- buy 100-point wings, plus one additional far OTM call;
- take profit at 1%, exit on a short-strike breach, or the following Friday
  at 09:45.
"""
import logging
import math
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

from db import repository as repo
from .base import ExitReason, Leg, OptionsStrategy, Position
from .titan_condor_data import get_option_contract

logger = logging.getLogger(__name__)

ENTRY_TIME = time(15, 16)
TIME_EXIT = time(9, 45)
STRIKE_STEP = 100
SHORT_DISTANCE = 400
WING_DISTANCE = 100
EXTRA_CALL_DISTANCE = 300
DEFAULT_LOT_SIZE_AFTER_2026 = 65
DEFAULT_LOT_SIZE_BEFORE_2026 = 75
MARKET_TIMEZONE = ZoneInfo("Asia/Kolkata")


def _local_bar_time(bar_time: datetime) -> datetime:
    """Compare database bars in the market timezone regardless of DB timezone."""
    value = bar_time.to_pydatetime() if hasattr(bar_time, "to_pydatetime") else bar_time
    if value.tzinfo is None or value.utcoffset() is None:
        return value
    return value.astimezone(MARKET_TIMEZONE).replace(tzinfo=None)


def _nearest_hundred(value: float) -> int:
    return int(math.floor(value / STRIKE_STEP + 0.5) * STRIKE_STEP)


def _lot_size(contract: dict, expiry: date) -> int:
    value = contract.get("lot_size")
    if value:
        return int(value)
    return (
        DEFAULT_LOT_SIZE_AFTER_2026
        if expiry >= date(2026, 1, 1)
        else DEFAULT_LOT_SIZE_BEFORE_2026
    )


class TitanCondorStrategy(OptionsStrategy):
    name = "NIFTY Titan Condor"
    underlying = "NIFTY 50"

    def __init__(
        self,
        margin_per_lot: float = 30_000,
        units: int = 10,
        target_pct: float = 1.0,
        extra_call_lots: int = 1,
    ):
        self.margin_per_lot = margin_per_lot
        self.units = units
        self.target_pct = target_pct
        self.extra_call_lots = extra_call_lots

    def entry_datetimes(self, start: date, end: date) -> list[datetime]:
        out = []
        current = start
        while current <= end:
            if current.weekday() == 4:
                out.append(datetime.combine(current, ENTRY_TIME))
            current += timedelta(days=1)
        return out

    def _target_expiry(self, entry_date: date) -> Optional[date]:
        expiries = repo.get_weekly_expiries(
            self.underlying, "CE", on_or_after=entry_date, limit=4
        )
        if len(expiries) < 2:
            logger.warning(
                "[%s] SKIP: expected two weekly expiries for %s, got %s",
                entry_date, self.underlying, expiries,
            )
            return None
        return expiries[1]

    def build_position(self, entry_time: datetime) -> Optional[Position]:
        spot = repo.get_spot_price_at(self.underlying, entry_time)
        expiry = self._target_expiry(entry_time.date())
        if spot is None or expiry is None:
            return None

        atm = _nearest_hundred(spot)
        short_call = _nearest_hundred(spot + SHORT_DISTANCE)
        short_put = _nearest_hundred(spot - SHORT_DISTANCE)
        specs = [
            ("SELL", "CE", short_call, self.units),
            ("BUY", "CE", short_call + WING_DISTANCE, self.units),
            ("SELL", "PE", short_put, self.units),
            ("BUY", "PE", short_put - WING_DISTANCE, self.units),
        ]
        if self.extra_call_lots:
            specs.append(
                ("BUY", "CE", short_call + EXTRA_CALL_DISTANCE, self.extra_call_lots)
            )

        legs: list[Leg] = []
        for side, option_type, strike, qty_lots in specs:
            contract = get_option_contract(
                self.underlying, option_type, expiry, strike
            )
            if contract is None:
                logger.warning(
                    "[%s] SKIP: missing %s %s contract for expiry=%s strike=%s",
                    entry_time.date(), option_type, side, expiry, strike,
                )
                return None
            entry_price = repo.get_price_at_or_before(contract["id"], entry_time)
            if entry_price is None:
                logger.warning(
                    "[%s] SKIP: no candle for %s at/before %s",
                    entry_time.date(), contract["trading_symbol"], entry_time,
                )
                return None
            legs.append(
                Leg(
                    instrument_id=contract["id"],
                    trading_symbol=contract["trading_symbol"],
                    strike=float(strike),
                    option_type=option_type,
                    side=side,
                    qty_lots=qty_lots,
                    lot_size=_lot_size(contract, expiry),
                    entry_price=entry_price,
                )
            )

        logger.info(
            "[%s] Position OPENED: spot=%s short_call=%s short_put=%s expiry=%s",
            entry_time.date(), spot, short_call, short_put, expiry,
        )
        return Position(
            entry_time=entry_time,
            expiry=expiry,
            legs=legs,
            deployed_margin=self.margin_per_lot * self.units,
            reference_atm=atm,
        )

    def check_exit(
        self, position: Position, bar_time: datetime, spot: float, mtm: float
    ) -> Optional[ExitReason]:
        short_call = next(
            leg.strike for leg in position.legs
            if leg.side == "SELL" and leg.option_type == "CE"
        )
        short_put = next(
            leg.strike for leg in position.legs
            if leg.side == "SELL" and leg.option_type == "PE"
        )
        if spot >= short_call or spot <= short_put:
            return ExitReason.HARD_BACKSTOP

        pnl_pct = (
            mtm / position.deployed_margin * 100
            if position.deployed_margin else 0.0
        )
        if pnl_pct >= self.target_pct:
            return ExitReason.TARGET

        time_exit = datetime.combine(
            position.entry_time.date() + timedelta(days=7), TIME_EXIT
        )
        if _local_bar_time(bar_time) >= time_exit:
            return ExitReason.EARLY_CUT
        return None
