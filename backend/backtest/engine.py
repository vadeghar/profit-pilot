"""
Generic engine: given any OptionsStrategy, walk each scheduled entry
forward minute-by-minute using the legs' own 1-min candles until an
exit condition fires or expiry is reached. Works for Blaze Butterfly
today; Strategies 1-3 (VIX-gated, indicator-based, etc.) plug into the
same loop once their `entry_datetimes` / `build_position` / `check_exit`
are implemented.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

import pandas as pd

from db import repository as repo
from strategies.base import ExitReason, OptionsStrategy, Position

MARKET_CLOSE = time(15, 30)


@dataclass
class TradeResult:
    entry_time: datetime
    exit_time: datetime
    reference_atm: float
    legs: list[str]
    exit_reason: str
    pnl: float
    pnl_pct: float
    deployed_margin: float


@dataclass
class BacktestSummary:
    strategy_name: str
    trades: list[TradeResult]

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t.pnl > 0)
        return wins / len(self.trades) * 100

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)

    @property
    def equity_curve(self) -> list[float]:
        curve, running = [], 0.0
        for t in self.trades:
            running += t.pnl
            curve.append(round(running, 2))
        return curve


def run_backtest(strategy: OptionsStrategy, start: date, end: date) -> BacktestSummary:
    trades: list[TradeResult] = []

    for entry_time in strategy.entry_datetimes(start, end):
        position = strategy.build_position(entry_time)
        if position is None:
            continue  # holiday, missing contract, or no data that week -- skip, don't guess

        result = _walk_to_exit(strategy, position)
        if result is not None:
            trades.append(result)

    return BacktestSummary(strategy_name=strategy.name, trades=trades)


def _walk_to_exit(strategy: OptionsStrategy, position: Position) -> TradeResult | None:
    # Pull each leg's candle series once for the full entry->expiry window.
    window_end = datetime.combine(position.expiry, MARKET_CLOSE)
    leg_frames: dict[int, pd.DataFrame] = {}
    for leg in position.legs:
        df = repo.get_candles(leg.instrument_id, position.entry_time, window_end)
        if df.empty:
            return None
        leg_frames[leg.instrument_id] = df.set_index("ts")

    # Union of timestamps across legs, so we check every minute any leg has data.
    all_ts = sorted(set().union(*[df.index for df in leg_frames.values()]))

    for ts in all_ts:
        prices = {}
        for leg in position.legs:
            df = leg_frames[leg.instrument_id]
            if ts in df.index:
                prices[leg.instrument_id] = float(df.loc[ts, "close"])
        if len(prices) < len(position.legs):
            continue  # wait until all legs have a print at this timestamp

        mtm = position.leg_mtm(prices)
        spot = repo.get_spot_price_at(strategy.underlying, ts)
        if spot is None:
            continue

        reason = strategy.check_exit(position, ts, spot, mtm)
        if reason is not None:
            return _close(position, ts, mtm, reason)

    # Nothing triggered by expiry -- close at last available mark (Section 5 has no
    # explicit "let it expire" rule, so we treat expiry itself as the exit point).
    last_ts = all_ts[-1] if all_ts else position.entry_time
    prices = {leg.instrument_id: float(leg_frames[leg.instrument_id]["close"].iloc[-1]) for leg in position.legs}
    mtm = position.leg_mtm(prices)
    return _close(position, last_ts, mtm, ExitReason.EXPIRY)


def _close(position: Position, exit_time: datetime, mtm: float, reason: ExitReason) -> TradeResult:
    position.exit_time = exit_time
    position.exit_reason = reason
    position.pnl = mtm
    return TradeResult(
        entry_time=position.entry_time,
        exit_time=exit_time,
        reference_atm=position.reference_atm,
        legs=[f"{l.side} {l.qty_lots}x {l.strike} {l.option_type}" for l in position.legs],
        exit_reason=reason.value,
        pnl=round(mtm, 2),
        pnl_pct=round(position.pnl_pct, 2),
        deployed_margin=position.deployed_margin,
    )
