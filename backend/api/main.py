"""
FastAPI backend for Profit Pilot's Strategy screen.

Run locally:
    uvicorn api.main:app --reload --port 8000

Endpoints:
    GET /api/strategies
        -> list of strategies with cached/last-run backtest summary,
           shaped to match what StrategyView.tsx renders as cards.
    GET /api/strategies/{strategy_id}/backtest?start=YYYY-MM-DD&end=YYYY-MM-DD
        -> run (or re-run) a backtest and return full trade list + equity curve.

Only Blaze Butterfly is wired up for now -- add entries to STRATEGIES
as Strategies 1-3 get implemented the same way.
"""
from datetime import date, datetime

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from backtest.engine import run_backtest
from strategies.blaze_butterfly import BlazeButterflyStrategy

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

# In-memory cache of the last backtest run per strategy, so the list
# endpoint doesn't re-run a backtest on every page load.
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


@app.get("/api/strategies")
def list_strategies():
    cards = []
    for sid, strat in STRATEGIES.items():
        cached = _last_summary.get(sid)
        cards.append(_summary_card(sid, strat, cached["summary"] if cached else None))
    return cards


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
        "trades": [
            {
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat(),
                "reference_atm": t.reference_atm,
                "legs": t.legs,
                "exit_reason": t.exit_reason,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
            }
            for t in summary.trades
        ],
    }
