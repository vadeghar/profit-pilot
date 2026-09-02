"""Strategy 8: NIFTY Matrix Calendar.

The strategy sells a 2-lot weekly strangle and splits each side's protection
between a 500-point weekly wing and a same-strike monthly option. Historical
IV and delta are derived from candle closes using the configured pricing model.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Optional

from db import repository as repo
from .base import ExitReason, Leg, OptionsStrategy, Position
from .matrix_calendar_data import (
    get_expiry_pair,
    get_option_chain_snapshot,
    get_option_contract,
)
from .pricing import implied_volatility, option_delta

logger = logging.getLogger(__name__)

ENTRY_TIME = time(15, 16)
TARGET_PCT = 1.5
STOP_PCT = 2.0
TARGET_DELTA = 0.23
WEEKLY_HEDGE_DISTANCE = 500
ALLOWED_STRIKE_STEP = 100
MAX_CANDLE_STALENESS_MINUTES = 10
TRADING_DAYS_HOLD = 2


class MatrixCalendarStrategy(OptionsStrategy):
    name = "NIFTY Matrix Calendar"
    underlying = "NIFTY 50"

    def __init__(
        self,
        *,
        margin_per_unit: float = 100_000,
        units: int = 1,
        target_pct: float = TARGET_PCT,
        stop_pct: float = STOP_PCT,
        risk_free_rate: float = 0.06,
        dividend_yield: float = 0.012,
    ):
        # The source strategy does not define the capital base for its
        # percentages, so margin_per_unit remains explicit and configurable.
        self.margin_per_unit = margin_per_unit
        self.units = units
        self.target_pct = target_pct
        self.stop_pct = stop_pct
        self.risk_free_rate = risk_free_rate
        self.dividend_yield = dividend_yield

    def entry_datetimes(self, start: date, end: date) -> list[datetime]:
        entries: list[datetime] = []
        current = start
        while current <= end:
            if current.weekday() == 0:
                entries.append(datetime.combine(current, ENTRY_TIME))
            current += timedelta(days=1)
        return entries

    @staticmethod
    def _time_to_expiry(entry_time: datetime, expiry: date) -> float:
        expiry_close = datetime.combine(expiry, time(15, 30))
        return max((expiry_close - entry_time).total_seconds(), 0.0) / (365.0 * 24 * 60 * 60)

    def _candidate(
        self,
        chain: list[dict[str, Any]],
        option_type: str,
        spot: float,
        time_years: float,
        entry_time: datetime,
    ) -> dict[str, Any] | None:
        candidates: list[tuple[float, dict[str, Any]]] = []
        for row in chain:
            if row["instrument_type"] != option_type:
                continue
            strike = float(row["strike"])
            if strike % ALLOWED_STRIKE_STEP != 0:
                continue
            if option_type == "CE" and strike <= spot:
                continue
            if option_type == "PE" and strike >= spot:
                continue
            candle_ts = row["candle_ts"]
            if candle_ts is None or entry_time - candle_ts > timedelta(minutes=MAX_CANDLE_STALENESS_MINUTES):
                continue
            price = float(row["close"])
            iv = implied_volatility(
                price,
                spot,
                strike,
                time_years,
                self.risk_free_rate,
                self.dividend_yield,
                option_type,
            )
            if iv is None:
                continue
            delta = option_delta(
                spot,
                strike,
                time_years,
                self.risk_free_rate,
                self.dividend_yield,
                iv,
                option_type,
            )
            candidates.append((abs(abs(delta) - TARGET_DELTA), {**row, "iv": iv, "delta": delta}))
        return min(candidates, key=lambda item: item[0])[1] if candidates else None

    @staticmethod
    def _append_leg(
        legs: list[Leg],
        contract: dict[str, Any],
        option_type: str,
        side: str,
        qty_lots: int,
    ) -> None:
        legs.append(
            Leg(
                instrument_id=int(contract["id"]),
                trading_symbol=contract["trading_symbol"],
                strike=float(contract["strike"]),
                option_type=option_type,
                side=side,
                qty_lots=qty_lots,
                lot_size=int(contract["lot_size"]),
                entry_price=float(contract["close"]),
            )
        )

    def build_position(self, entry_time: datetime) -> Optional[Position]:
        entry_date = entry_time.date()
        spot = repo.get_spot_price_at(self.underlying, entry_time)
        if spot is None:
            logger.warning("[%s] Matrix Calendar skipped: no NIFTY spot at %s", entry_date, entry_time)
            return None

        expiry_pair = get_expiry_pair(entry_date)
        if expiry_pair is None:
            logger.warning("[%s] Matrix Calendar skipped: no weekly/monthly expiry pair", entry_date)
            return None
        weekly_expiry, monthly_expiry = expiry_pair
        time_years = self._time_to_expiry(entry_time, weekly_expiry)
        chain = get_option_chain_snapshot(self.underlying, weekly_expiry, entry_time)
        call = self._candidate(chain, "CE", spot, time_years, entry_time)
        put = self._candidate(chain, "PE", spot, time_years, entry_time)
        if call is None or put is None:
            logger.warning("[%s] Matrix Calendar skipped: no valid ~23-delta CE/PE pair", entry_date)
            return None

        call_hedge = get_option_contract(
            self.underlying, "CE", weekly_expiry,
            float(call["strike"]) + WEEKLY_HEDGE_DISTANCE, entry_time,
        )
        put_hedge = get_option_contract(
            self.underlying, "PE", weekly_expiry,
            float(put["strike"]) - WEEKLY_HEDGE_DISTANCE, entry_time,
        )
        monthly_call = get_option_contract(
            self.underlying, "CE", monthly_expiry, float(call["strike"]), entry_time,
        )
        monthly_put = get_option_contract(
            self.underlying, "PE", monthly_expiry, float(put["strike"]), entry_time,
        )
        if not all((call_hedge, put_hedge, monthly_call, monthly_put)):
            logger.warning("[%s] Matrix Calendar skipped: one or more hedge contracts are missing", entry_date)
            return None

        qty = self.units
        legs: list[Leg] = []
        self._append_leg(legs, call, "CE", "SELL", 2 * qty)
        self._append_leg(legs, put, "PE", "SELL", 2 * qty)
        self._append_leg(legs, call_hedge, "CE", "BUY", qty)
        self._append_leg(legs, put_hedge, "PE", "BUY", qty)
        self._append_leg(legs, monthly_call, "CE", "BUY", qty)
        self._append_leg(legs, monthly_put, "PE", "BUY", qty)

        return Position(
            entry_time=entry_time,
            expiry=weekly_expiry,
            legs=legs,
            deployed_margin=self.margin_per_unit * self.units,
            reference_atm=float(spot),
        )

    def check_exit(
        self,
        position: Position,
        bar_time: datetime,
        spot: float,
        mtm: float,
    ) -> Optional[ExitReason]:
        pnl_pct = mtm / position.deployed_margin * 100 if position.deployed_margin else 0.0
        if pnl_pct >= self.target_pct:
            return ExitReason.TARGET
        if pnl_pct <= -self.stop_pct:
            return ExitReason.STOP_LOSS

        # The document caps the trade at two days; use a hard timestamp so
        # weekends/holidays cannot accidentally extend the holding period.
        if bar_time >= position.entry_time + timedelta(days=TRADING_DAYS_HOLD):
            return ExitReason.EARLY_CUT
        return None
