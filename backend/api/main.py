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
           running totals), then a final "done" event.
"""
import json
import logging
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backtest.engine import BacktestSummary, iter_trades, run_backtest
from strategies.blaze_butterfly import BlazeButterflyStrategy
from strategies.matrix_calendar import MatrixCalendarStrategy
from news.models import NewsResponse
from news.service import get_news

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Profit Pilot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STRATEGIES = {
    "blaze-butterfly": BlazeButterflyStrategy(),
    "matrix-calendar": MatrixCalendarStrategy(),
}

_last_summary: dict[str, dict] = {}


def _summary_card(strategy_id: str, strategy, summary) -> dict:
    return {
        "id": strategy_id,
        "name": strategy.name,
        "subtitle": f"{strategy.underlying} · Weekly",
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


@app.get("/api/strategies/{strategy_id}/backtest")
def backtest_strategy(
    strategy_id: str,
    start: date = Query(..., description="YYYY-MM-DD"),
    end: date = Query(..., description="YYYY-MM-DD"),
):
    strat = STRATEGIES.get(strategy_id)
    if strat is None:
        raise HTTPException(404, f"Unknown strategy '{strategy_id}'")

    summary = run_backtest(strat, start, end)
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
        for t in iter_trades(strat, start, end):
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

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
