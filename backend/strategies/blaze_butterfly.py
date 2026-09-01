"""
Strategy 4: NIFTY Blaze Butterfly (weekly, zero-adjustment Put Broken-Wing
Butterfly). See Strategy_04_Blaze_Butterfly.md for the full spec this
implements.

v1 scope decisions (per the doc's own recommendations, revisit later):
  - No event-day filter yet (Section 8, item 2 option (b)).
  - Early-cut rule coded literally: near-buy-leg crossed AND mtm < 0.
  - Holiday handling: if Monday has no data, roll to the next trading day.
  - Put-side only, every week, unconditionally.
"""
import logging
from datetime import date, datetime, time, timedelta
from typing import Optional

from db import repository as repo
from .base import ExitReason, Leg, OptionsStrategy, Position

logger = logging.getLogger(__name__)

ENTRY_TIME = time(15, 15)
INNER_WING = 200
OUTER_WING = 400


def reference_atm(spot: float) -> float:
    """Nearest 50-point strike; if it lands on a '50' strike, shift down
    to the nearest round-hundred (Section 2, Step 0)."""
    nearest_50 = round(spot / 50) * 50
    if nearest_50 % 100 != 0:
        nearest_50 -= 50
    return nearest_50


class BlazeButterflyStrategy(OptionsStrategy):
    name = "NIFTY Blaze Butterfly"
    underlying = "NIFTY"

    def __init__(self, margin_per_unit: float = 85_000, units: int = 1,
                 target_pct: float = 1.0, stop_pct: float = 1.0):
        self.margin_per_unit = margin_per_unit
        self.units = units
        self.target_pct = target_pct
        self.stop_pct = stop_pct

    # ------------------------------------------------------------------
    # Entry scheduling
    # ------------------------------------------------------------------
    def entry_datetimes(self, start: date, end: date) -> list[datetime]:
        out = []
        d = start
        while d <= end:
            if d.weekday() == 0:  # Monday
                out.append(datetime.combine(d, ENTRY_TIME))
            d += timedelta(days=1)
        return out

    def _target_expiry(self, entry_date: date) -> Optional[date]:
        """Skip this week's own Tuesday expiry; use next week's Tuesday (Section 3)."""
        expiries = repo.get_weekly_expiries(self.underlying, "PE", on_or_after=entry_date, limit=4)
        if len(expiries) < 2:
            logger.warning(
                "[%s] no expiry pair found: underlying=%s type=PE on_or_after=%s -> got %s",
                entry_date, self.underlying, entry_date, expiries,
            )
            return None
        return expiries[1]  # [0] is this week's, [1] is next week's

    def _roll_to_trading_day(self, spot_probe_instrument_id: int, d: date, max_roll: int = 3) -> date:
        rolled = d
        tries = 0
        while not repo.has_any_candle_on(spot_probe_instrument_id, rolled) and tries < max_roll:
            rolled += timedelta(days=1)
            tries += 1
        return rolled

    # ------------------------------------------------------------------
    # Position construction
    # ------------------------------------------------------------------
    def build_position(self, entry_time: datetime) -> Optional[Position]:
        entry_date = entry_time.date()

        spot = repo.get_spot_price_at(self.underlying, entry_time)
        if spot is None:
            logger.warning(
                "[%s] SKIP: no spot price found for underlying=%s at/before %s "
                "(check instruments.instrument_type='INDEX' row + candles_1min coverage)",
                entry_date, self.underlying, entry_time,
            )
            return None

        atm = reference_atm(spot)
        expiry = self._target_expiry(entry_date)
        if expiry is None:
            # _target_expiry already logged the specific reason
            return None

        leg_specs = [
            ("BUY", atm - INNER_WING, 1),
            ("SELL", atm - INNER_WING * 2, 2),
            ("BUY", atm - INNER_WING * 2 - OUTER_WING, 1),
        ]

        legs: list[Leg] = []
        for side, strike, qty in leg_specs:
            instr = repo.get_instrument(self.underlying, "PE", expiry, strike)
            if instr is None:
                logger.warning(
                    "[%s] SKIP: no instrument row for underlying=%s type=PE expiry=%s strike=%s "
                    "(spot=%s atm=%s) -- check strike increments / expiry format in `instruments`",
                    entry_date, self.underlying, expiry, strike, spot, atm,
                )
                return None  # missing contract in DB -- skip this week rather than guess
            price = repo.get_price_at_or_before(instr["id"], entry_time)
            if price is None:
                logger.warning(
                    "[%s] SKIP: instrument %s (id=%s) found but no candles_1min row at/before %s",
                    entry_date, instr["trading_symbol"], instr["id"], entry_time,
                )
                return None
            legs.append(
                Leg(
                    instrument_id=instr["id"],
                    trading_symbol=instr["trading_symbol"],
                    strike=strike,
                    option_type="PE",
                    side=side,
                    qty_lots=qty * self.units,
                    lot_size=instr["lot_size"],
                    entry_price=price,
                )
            )

        deployed_margin = self.margin_per_unit * self.units
        logger.info(
            "[%s] Position OPENED: spot=%s atm=%s expiry=%s legs=%s",
            entry_date, spot, atm, expiry, [l.trading_symbol for l in legs],
        )
        return Position(
            entry_time=entry_time,
            expiry=expiry,
            legs=legs,
            deployed_margin=deployed_margin,
            reference_atm=atm,
        )

    # ------------------------------------------------------------------
    # Exit ladder (Section 5)
    # ------------------------------------------------------------------
    def check_exit(self, position: Position, bar_time: datetime, spot: float, mtm: float) -> Optional[ExitReason]:
        atm = position.reference_atm
        sold_strike = atm - INNER_WING * 2       # hard backstop level
        near_buy_strike = atm - INNER_WING       # early-cut trigger level
        pnl_pct = mtm / position.deployed_margin * 100 if position.deployed_margin else 0.0

        if spot <= sold_strike:
            return ExitReason.HARD_BACKSTOP           # unconditional, checked first
        if pnl_pct >= self.target_pct:
            return ExitReason.TARGET
        if pnl_pct <= -self.stop_pct:
            return ExitReason.STOP_LOSS
        if spot <= near_buy_strike and mtm < 0:
            return ExitReason.EARLY_CUT
        return None
