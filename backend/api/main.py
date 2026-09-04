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

Blaze Butterfly and Titan Condor run on the generic OptionsStrategy engine
(backtest/engine.py). NIFTY ATM Straddle has its own dedicated state-machine
engine (backtest/atm_straddle_engine.py) -- see strategies/nifty_atm_straddle.py's
module docstring for why. _iter_trades_for / _run_backtest_for dispatch to
whichever engine a given strategy needs, so the endpoints below don't care.
"""
import json
import logging
import asyncio
import os
import queue
import threading
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backtest import atm_straddle_engine
from backtest.engine import BacktestSummary, iter_trades, run_backtest
from strategies.blaze_butterfly import BlazeButterflyStrategy
from strategies.titan_condor import TitanCondorStrategy
from strategies.nifty_atm_straddle import NiftyATMStraddleStrategy
from news.models import NewsResponse
from news.service import get_news
from analytics.models import AnalyticsSnapshot
from analytics.service import _nse_snapshot, get_analytics
from analytics.sources.nse_client import fetch_market_data as fetch_nse_data
from analytics.sources.nse_client import _market_client as nse_market_client

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
    "titan-condor": TitanCondorStrategy(
        units=int(os.getenv("TITAN_CONDOR_UNITS", "10")),
        margin_per_lot=float(os.getenv("TITAN_CONDOR_MARGIN_PER_LOT", "30000")),
        target_pct=float(os.getenv("TITAN_CONDOR_TARGET_PCT", "1.0")),
        extra_hedge_lots=int(os.getenv("TITAN_CONDOR_EXTRA_HEDGE_LOTS", "1")),
    ),
    "nifty-atm-straddle": NiftyATMStraddleStrategy(),
}

# In-memory cache of the last backtest run per strategy, so the list
# endpoint doesn't re-run a backtest on every page load.
_last_summary: dict[str, dict] = {}


def _iter_trades_for(strat, start: date, end: date):
    if isinstance(strat, NiftyATMStraddleStrategy):
        return atm_straddle_engine.iter_trades(strat, start, end)
    return iter_trades(strat, start, end)


def _run_backtest_for(strat, start: date, end: date) -> BacktestSummary:
    if isinstance(strat, NiftyATMStraddleStrategy):
        return atm_straddle_engine.run_backtest(strat, start, end)
    return run_backtest(strat, start, end)


def _summary_card(strategy_id: str, strategy, summary) -> dict:
    return {
        "id": strategy_id,
        "name": strategy.name,
        "subtitle": f"{strategy.underlying} \u00b7 {getattr(strategy, 'frequency', 'Weekly')}",
        "status": "BACKTEST",
        "win_rate": round(summary.win_rate, 1) if summary else None,
        "pnl": round(summary.total_pnl, 2) if summary else None,
        "trades": summary.total_trades if summary else 0,
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
        "details": t.details,
    }


@app.get("/api/strategies")
def list_strategies():
    cards = []
    for sid, strat in STRATEGIES.items():
        cached = _last_summary.get(sid)
        cards.append(_summary_card(sid, strat, cached["summary"] if cached else None))
    return cards


@app.get("/api/news", response_model=NewsResponse, response_model_by_alias=True)
def news(force_refresh: bool = Query(False)):
    try:
        return get_news(force_refresh=force_refresh)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@app.get("/api/analytics", response_model=AnalyticsSnapshot, response_model_by_alias=True)
def analytics(force_refresh: bool = Query(False)):
    return get_analytics(force_refresh=force_refresh).model_dump(by_alias=True)


@app.get("/api/analytics/card/{card}")
def analytics_card(card: str):
    if card not in {"summary", "breadth", "momentumLeaders", "volatility", "marketCards", "activeContracts"}:
        raise HTTPException(status_code=404, detail="Analytics card not found")
    snapshot = _nse_snapshot(nse_market_client.fetch_card_data(card)).model_dump(by_alias=True)
    return {"card": card, "data": snapshot[card], "meta": snapshot["meta"]}


@app.get("/api/analytics/stream")
async def analytics_stream(request: Request, force_refresh: bool = Query(False)):
    def _stream_nse_data():
        updates: queue.Queue[tuple[str, object]] = queue.Queue()

        def on_result(name, value):
            updates.put((name, value))

        worker = threading.Thread(target=lambda: fetch_nse_data(on_result=on_result), daemon=True)
        worker.start()
        return updates, worker

    def _card_events(snapshot, cards):
        for card in cards:
            payload = {"card": card, "data": snapshot[card], "meta": snapshot["meta"]}
            yield f"event: {card}\ndata: {json.dumps(payload, default=str)}\n\n"

    async def event_stream():
        interval = max(5, float(os.getenv("ANALYTICS_STREAM_INTERVAL_SECONDS", "15")))
        refresh = force_refresh
        try:
            while not await request.is_disconnected():
                yield "event: snapshot_start\ndata: {}\n\n"
                updates, worker = _stream_nse_data()
                partial = {}
                mapping = {
                    "statistics": ("summary", "breadth"),
                    "indices": ("volatility",),
                    "marquee": ("momentumLeaders",),
                    "gainers": ("marketCards",), "losers": ("marketCards",),
                    "activeValue": ("marketCards",), "activeVolume": ("marketCards",),
                    "newHighs": ("summary", "marketCards"), "newLows": ("summary", "marketCards"),
                }
                while worker.is_alive() or not updates.empty():
                    try:
                        name, value = await asyncio.to_thread(updates.get, True, 0.25)
                    except queue.Empty:
                        continue
                    if name == "complete":
                        partial = value
                        continue
                    partial[name] = value
                    cards = mapping.get(name, ())
                    if cards:
                        snapshot = _nse_snapshot(partial).model_dump(by_alias=True)
                        for event in _card_events(snapshot, cards):
                            yield event
                            await asyncio.sleep(0.02)
                if any(partial.get(key) for key in ("gainers", "losers", "statistics", "indices", "marquee")):
                    snapshot = _nse_snapshot(partial).model_dump(by_alias=True)
                else:
                    snapshot = (await asyncio.to_thread(get_analytics, refresh)).model_dump(by_alias=True)
                refresh = False
                for event in _card_events(snapshot, ("summary", "breadth", "momentumLeaders", "volatility", "marketCards")):
                    yield event
                    await asyncio.sleep(0.02)
                yield f"event: snapshot_complete\ndata: {json.dumps(snapshot, default=str)}\n\n"
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.get("/api/strategies/{strategy_id}/backtest")
def backtest_strategy(
    strategy_id: str,
    start: date = Query(..., description="YYYY-MM-DD"),
    end: date = Query(..., description="YYYY-MM-DD"),
):
    strat = STRATEGIES.get(strategy_id)
    if strat is None:
        raise HTTPException(404, f"Unknown strategy '{strategy_id}'")

    summary = _run_backtest_for(strat, start, end)
    _last_summary[strategy_id] = {"summary": summary, "run_at": datetime.utcnow()}

    return {
        "id": strategy_id,
        "name": summary.strategy_name,
        "total_trades": summary.total_trades,
        "win_rate": round(summary.win_rate, 2),
        "total_pnl": round(summary.total_pnl, 2),
        "equity_curve": summary.equity_curve,
        "trades": [_trade_payload(t) for t in summary.trades],
    }


@app.get("/api/strategies/{strategy_id}/backtest/stream")
def backtest_strategy_stream(
    strategy_id: str,
    start: date = Query(..., description="YYYY-MM-DD"),
    end: date = Query(..., description="YYYY-MM-DD"),
):
    strat = STRATEGIES.get(strategy_id)
    if strat is None:
        raise HTTPException(404, f"Unknown strategy '{strategy_id}'")

    def event_stream():
        trades = []
        try:
            for t in _iter_trades_for(strat, start, end):
                trades.append(t)
                wins = sum(1 for x in trades if x.pnl > 0)
                payload = {
                    **_trade_payload(t),
                    "running_trade_count": len(trades),
                    "running_pnl": round(sum(x.pnl for x in trades), 2),
                    "running_win_rate": round(wins / len(trades) * 100, 2),
                }
                yield f"event: trade\ndata: {json.dumps(payload)}\n\n"

            summary = BacktestSummary(strategy_name=strat.name, trades=trades)
            _last_summary[strategy_id] = {"summary": summary, "run_at": datetime.utcnow()}
            done_payload = {
                "total_trades": summary.total_trades,
                "win_rate": round(summary.win_rate, 2),
                "total_pnl": round(summary.total_pnl, 2),
            }
            yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"
        except Exception as error:
            logger.exception("Backtest stream failed for %s: %s", strategy_id, error)
            payload = {"error": str(error), "strategy_id": strategy_id}
            yield f"event: backtest_error\ndata: {json.dumps(payload)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
