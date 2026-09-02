"""
FastAPI backend for Profit Pilot's Strategy screen.

Run locally:
    uvicorn api.main:app --reload --port 8000

Endpoints:
    GET /api/strategies
        -> list of strategies with cached/last-run backtest summary,
           shaped to match what StrategyView.tsx renders as cards.
    GET /api/strategies/{strategy_id}/backtest?start=YYYY-MM-DD&end=YYYY-MM-DD
        -> run a backtest synchronously and return full trade list + equity curve.
    GET /api/strategies/{strategy_id}/backtest/stream?start=...&end=...
        -> Server-Sent Events: one "trade" event per completed trade (with
           running totals), then a final "done" event. Use this from the UI
           instead of the endpoint above so results appear as they're found
           rather than after the whole backtest finishes.

Backtest results are cached in Redis (see cache.py) keyed on strategy +
date range + strategy params, so re-running the same backtest replays
cached trades instantly instead of recomputing. Fully historical ranges
(end date more than a few days old) are cached indefinitely since the
result can never change; ranges touching recent days get a short TTL
since candle ingestion for those days may still be catching up. Set
CACHE_ENABLED=false (the default) to disable this entirely.

Only Blaze Butterfly is wired up for now -- add entries to STRATEGIES
as Strategies 1-3 get implemented the same way.
"""
import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

import cache
from backtest.engine import BacktestSummary, iter_trades, run_backtest
from strategies.blaze_butterfly import BlazeButterflyStrategy
from news.models import NewsResponse
from news.service import get_news

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Surfaces per-Monday diagnostic warnings from strategies/blaze_butterfly.py
# and backtest/engine.py in the uvicorn console -- look here first if a
# backtest comes back with 0 trades.
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Profit Pilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # vite dev server; add prod origin later
    allow_methods=["*"],
    allow_headers=["*"],
)

STRATEGIES = {
    "blaze-butterfly": BlazeButterflyStrategy(),
}

# In-memory summary of the last backtest run per strategy, so the list
# endpoint doesn't need Redis or a fresh run just to render the cards.
# Shape: {"win_rate": float, "pnl": float, "trades": int}
_last_summary: dict[str, dict] = {}

RECENT_WINDOW_DAYS = 3        # ranges touching the last N days get a short TTL
RECENT_RANGE_TTL_SECONDS = 3600
REPLAY_DELAY_SECONDS = 0.03   # small pacing delay so a cache-hit replay still feels "live"


def _summary_card(strategy_id: str, strategy, totals: dict | None) -> dict:
    return {
        "id": strategy_id,
        "name": strategy.name,
        "subtitle": f"{strategy.underlying} · Weekly",
        "status": "BACKTEST",
        "win_rate": totals["win_rate"] if totals else None,
        "pnl": totals["pnl"] if totals else None,
        "trades": totals["trades"] if totals else 0,
    }


def _trade_payload(t) -> dict:
    return {
        "entry_time": t.entry_time.isoformat(),
        "exit_time": t.exit_time.isoformat(),
        "reference_atm": t.reference_atm,
        "legs": t.legs,
        "exit_reason": t.exit_reason,
        "pnl": t.pnl,
        "pnl_pct": t.pnl_pct,
    }


def _strategy_params(strategy) -> dict:
    """Grab the strategy's simple tunable attributes for cache-key hashing,
    generically -- so new strategies don't need code changes here to be
    cached correctly by their own parameters."""
    return {k: v for k, v in vars(strategy).items() if isinstance(v, (int, float, str, bool))}


def _backtest_cache_key(strategy_id: str, strategy, start: date, end: date) -> str:
    phash = cache.params_hash(**_strategy_params(strategy))
    return f"backtest:v1:{strategy_id}:{start.isoformat()}:{end.isoformat()}:{phash}"


def _backtest_ttl(end: date) -> int | None:
    """None = cache indefinitely (fully historical, can't change).
    A range touching the last few days gets a short TTL since candle
    ingestion for those days may still be backfilling."""
    if end >= date.today() - timedelta(days=RECENT_WINDOW_DAYS):
        return RECENT_RANGE_TTL_SECONDS
    return None


@app.get("/api/strategies")
def list_strategies():
    cards = []
    for sid, strat in STRATEGIES.items():
        cards.append(_summary_card(sid, strat, _last_summary.get(sid)))
    return cards


@app.get("/api/news", response_model=NewsResponse, response_model_by_alias=True)
def news(force_refresh: bool = Query(False)):
    try:
        return get_news(force_refresh=force_refresh)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/strategies/{strategy_id}/backtest")
def backtest_strategy(
    strategy_id: str,
    start: date = Query(..., description="YYYY-MM-DD"),
    end: date = Query(..., description="YYYY-MM-DD"),
):
    strat = STRATEGIES.get(strategy_id)
    if strat is None:
        raise HTTPException(404, f"Unknown strategy '{strategy_id}'")

    cache_key = _backtest_cache_key(strategy_id, strat, start, end)
    cached = cache.get_json(cache_key)
    if cached is not None:
        _last_summary[strategy_id] = {
            "win_rate": cached["win_rate"],
            "pnl": cached["total_pnl"],
            "trades": cached["total_trades"],
        }
        return cached

    summary = run_backtest(strat, start, end)
    result = {
        "id": strategy_id,
        "name": summary.strategy_name,
        "total_trades": summary.total_trades,
        "win_rate": round(summary.win_rate, 2),
        "total_pnl": round(summary.total_pnl, 2),
        "equity_curve": summary.equity_curve,
        "trades": [_trade_payload(t) for t in summary.trades],
    }
    cache.set_json(cache_key, result, ttl_seconds=_backtest_ttl(end))
    _last_summary[strategy_id] = {
        "win_rate": result["win_rate"],
        "pnl": result["total_pnl"],
        "trades": result["total_trades"],
    }
    return result


@app.get("/api/strategies/{strategy_id}/backtest/stream")
def backtest_strategy_stream(
    strategy_id: str,
    start: date = Query(..., description="YYYY-MM-DD"),
    end: date = Query(..., description="YYYY-MM-DD"),
):
    strat = STRATEGIES.get(strategy_id)
    if strat is None:
        raise HTTPException(404, f"Unknown strategy '{strategy_id}'")

    cache_key = _backtest_cache_key(strategy_id, strat, start, end)
    lock_key = f"lock:{cache_key}"

    def _replay(cached: dict):
        """Cache hit -- replay the stored trades as SSE events (with a small
        pacing delay) so the UI keeps its progressive feel instead of the
        grid populating all at once."""
        for trade_payload in cached["trades"]:
            yield f"event: trade\ndata: {json.dumps(trade_payload)}\n\n"
            time.sleep(REPLAY_DELAY_SECONDS)
        done_payload = {
            "total_trades": cached["total_trades"],
            "win_rate": cached["win_rate"],
            "total_pnl": cached["total_pnl"],
        }
        _last_summary[strategy_id] = {
            "win_rate": done_payload["win_rate"],
            "pnl": done_payload["total_pnl"],
            "trades": done_payload["total_trades"],
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    def _compute_and_stream():
        """Cache miss -- run the backtest for real, streaming each trade as
        it's found, then persist the full result before the final event."""
        trades = []
        trade_payloads = []
        for t in iter_trades(strat, start, end):
            trades.append(t)
            wins = sum(1 for x in trades if x.pnl > 0)
            payload = {
                **_trade_payload(t),
                "running_trade_count": len(trades),
                "running_pnl": round(sum(x.pnl for x in trades), 2),
                "running_win_rate": round(wins / len(trades) * 100, 2),
            }
            trade_payloads.append(payload)
            yield f"event: trade\ndata: {json.dumps(payload)}\n\n"

        summary = BacktestSummary(strategy_name=strat.name, trades=trades)
        done_payload = {
            "total_trades": summary.total_trades,
            "win_rate": round(summary.win_rate, 2),
            "total_pnl": round(summary.total_pnl, 2),
        }
        cache.set_json(
            cache_key,
            {"trades": trade_payloads, **done_payload},
            ttl_seconds=_backtest_ttl(end),
        )
        _last_summary[strategy_id] = {
            "win_rate": done_payload["win_rate"],
            "pnl": done_payload["total_pnl"],
            "trades": done_payload["total_trades"],
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    def event_stream():
        cached = cache.get_json(cache_key)
        if cached is not None:
            yield from _replay(cached)
            return

        # Stampede protection: if another request is already computing this
        # exact backtest, wait briefly for its result instead of duplicating
        # the work. If it doesn't finish in time, fall through and compute
        # independently -- never block forever on someone else's request.
        got_lock = cache.acquire_lock(lock_key, ttl_seconds=120)
        if not got_lock:
            for _ in range(20):  # up to ~10s
                time.sleep(0.5)
                cached = cache.get_json(cache_key)
                if cached is not None:
                    yield from _replay(cached)
                    return
            logger.warning("Lock wait timed out for %s -- computing independently", cache_key)

        try:
            yield from _compute_and_stream()
        finally:
            if got_lock:
                cache.release_lock(lock_key)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
