"""
Backtest runner for the NIFTY ATM Straddle strategy (the "Historical
Backtester" box in the spec's Section 25 diagram). Iterates every
eligible trading day and calls strategies.nifty_atm_straddle's
run_strategy_for_day() for each one -- the exact same state machine a
future live-deployment runner would call, per the spec's own
single-engine principle. Only the day-iteration and `mode` differ here.

Adapts the rich StraddleTradeRecord (Section 23's trade record) into
backtest.engine's generic TradeResult shape so the existing Strategy
screen / BacktestModal UI can render this strategy without any frontend
changes.
"""
import logging
from datetime import date
from typing import Iterator

from backtest.engine import BacktestSummary, TradeResult
from db import repository as repo
from strategies.nifty_atm_straddle import (
    Mode,
    NiftyATMStraddleStrategy,
    StraddleTradeRecord,
    StrategyState,
    UNDERLYING,
    run_strategy_for_day,
)

logger = logging.getLogger(__name__)

_TERMINAL_STATUSES = {StrategyState.CLOSED.value}


def _legs_summary(record: StraddleTradeRecord) -> list[str]:
    """One line per fill, e.g. 'BUY 2x 25000 CE @ 28.0 [INITIAL]' -- shown
    verbatim in the BacktestModal trade grid's legs column."""
    return [
        f"{f['action']} {f['lots']}x {record.atm_strike} {f['option_type']} @ {f['price']} [{f['tag']}]"
        for f in record.fills
    ]


def _to_trade_result(record: StraddleTradeRecord) -> TradeResult:
    return TradeResult(
        entry_time=record.initial_entry_timestamp,
        exit_time=record.final_exit_timestamp,
        reference_atm=record.atm_strike,
        legs=_legs_summary(record),
        exit_reason=record.final_exit_reason,
        pnl=round(record.realized_pnl, 2),
        pnl_pct=round(record.pnl_pct, 2),
        deployed_margin=round(record.total_premium_outlay, 2),
        details={
            "trading_date": record.trading_date,
            "expiry_date": record.expiry_date,
            "spot": record.initial_entry_spot,
            "lot_size": record.lot_size,
            "fills": record.fills,
        },
    )


def iter_trades(strategy: NiftyATMStraddleStrategy, start: date, end: date) -> Iterator[TradeResult]:
    """Duck-type compatible with backtest.engine.iter_trades's call shape,
    so api/main.py can dispatch to either engine the same way."""
    trading_days = repo.get_trading_days(UNDERLYING, start, end)
    for trading_date in trading_days:
        if trading_date < strategy.strategy_start_date:
            continue  # Section 3: not applicable before the strategy start date
        record = run_strategy_for_day(trading_date, mode=Mode.BACKTEST)
        if record.status not in _TERMINAL_STATUSES:
            continue  # NO_ENTRY / NOT_APPLICABLE -- no trade fired that day
        yield _to_trade_result(record)


def run_backtest(strategy: NiftyATMStraddleStrategy, start: date, end: date) -> BacktestSummary:
    trades = list(iter_trades(strategy, start, end))
    return BacktestSummary(strategy_name=strategy.name, trades=trades)
