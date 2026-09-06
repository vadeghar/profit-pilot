"""
Backtest runner for the NIFTY ATM Straddle strategy.

The strategy is strictly an NIFTY expiry-day strategy. Expiry dates are
resolved from nifty_expiry_calendar and may be WEEKLY or MONTHLY. Non-expiry
trading dates are ignored before diagnostics or strategy calculations are run.
"""
import logging
from datetime import date, datetime
from typing import Iterator
from zoneinfo import ZoneInfo

from backtest.engine import BacktestSummary, TradeResult
from db import repository as repo
from strategies.nifty_atm_entry_debug_logger import create_run_log_path, run_entry_debug_log
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
MARKET_TZ = ZoneInfo("Asia/Kolkata")


def _legs_summary(record: StraddleTradeRecord) -> list[str]:
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


def _is_expiry_day(trading_date: date) -> bool:
    """Return True only when trading_date is an actual NIFTY expiry date."""
    expiries = repo.get_nifty_expiry_dates(UNDERLYING, on_or_after=trading_date, limit=1)
    return bool(expiries and expiries[0] == trading_date)


def iter_trades(strategy: NiftyATMStraddleStrategy, start: date, end: date) -> Iterator[TradeResult]:
    """Run diagnostics and the strategy state machine only on NIFTY expiry days."""
    trading_days = repo.get_trading_days(UNDERLYING, start, end)
    debug_log_path = create_run_log_path()

    logger.info(
        "[NIFTY ATM V4 DEBUG] Backtest diagnostic logging enabled | "
        "expiry-days-only | range=%s..%s | output=%s",
        start,
        end,
        debug_log_path,
    )

    with debug_log_path.open("w", encoding="utf-8") as handle:
        handle.write(
            "NIFTY ATM STRADDLE V4 BACKTEST ENTRY DIAGNOSTIC\n"
            f"RUN_STARTED_IST={datetime.now(MARKET_TZ).strftime('%Y-%m-%d %H:%M:%S IST')}\n"
            f"REQUESTED_RANGE={start}..{end}\n"
            "SCOPE=NIFTY WEEKLY OR MONTHLY EXPIRY DAYS ONLY\n"
            "Non-expiry trading dates are intentionally ignored and are not logged.\n\n"
        )

    for trading_date in trading_days:
        if trading_date < strategy.strategy_start_date:
            continue

        # HARD SCOPE RULE: no diagnostic scan and no strategy state-machine
        # calculation is performed for a non-expiry trading date.
        if not _is_expiry_day(trading_date):
            continue

        try:
            run_entry_debug_log(trading_date, debug_log_path)
        except Exception:
            logger.exception(
                "[NIFTY ATM V4 DEBUG] Entry diagnostic failed for expiry date %s; continuing backtest",
                trading_date,
            )
            with debug_log_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    f"DATE={trading_date} | RESULT=DIAGNOSTIC_FAILED | see backend logger for traceback\n"
                )

        record = run_strategy_for_day(trading_date, mode=Mode.BACKTEST)
        if record.status not in _TERMINAL_STATUSES:
            continue
        yield _to_trade_result(record)


def run_backtest(strategy: NiftyATMStraddleStrategy, start: date, end: date) -> BacktestSummary:
    trades = list(iter_trades(strategy, start, end))
    return BacktestSummary(strategy_name=strategy.name, trades=trades)
