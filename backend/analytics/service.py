from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

from .models import AnalyticsSnapshot
from .sources.angelone import configured as angel_configured
from .sources.angelone import fetch_market_data as fetch_angel_data
from .sources.nse_client import fetch_market_data as fetch_nse_data
from .sources.yahoo import fetch_market_data as fetch_yahoo_data


_fallback_lock = threading.Lock()
_fallback_snapshot: AnalyticsSnapshot | None = None
_fallback_at = 0.0


def _public_errors(errors: list[str]) -> list[str]:
    messages = []
    for error in errors:
        if error.startswith("companyName:"):
            symbol = error.split(":", 2)[1]
            messages.append(f"Company details temporarily unavailable for {symbol}.")
        else:
            messages.append("Some market data is temporarily unavailable.")
    return list(dict.fromkeys(messages))


def _empty_snapshot(errors: list[str]) -> AnalyticsSnapshot:
    return AnalyticsSnapshot(
        summary={}, breadth={}, momentumLeaders=[], volatility=[], marketCards={}, indices=[], activeContracts={},
        meta={"asOf": datetime.now(timezone.utc), "source": "Yahoo Finance chart", "freshness": "UNAVAILABLE", "stale": True, "errors": _public_errors(errors)},
    )


def _atr(points: list[dict], period: int = 14) -> float | None:
    ranges = [point["high"] - point["low"] for point in points[-period:] if point.get("high") is not None and point.get("low") is not None]
    return round(sum(ranges) / len(ranges), 2) if ranges else None


def _change(points: list[dict]) -> float | None:
    if len(points) < 2 or not points[-2]["close"]:
        return None
    return round((points[-1]["close"] - points[-2]["close"]) / points[-2]["close"] * 100, 2)


def _snapshot(rows: list[dict], indices: dict[str, list[dict]], errors: list[str], source: str, freshness: str) -> AnalyticsSnapshot:
    advancers = sum(1 for row in rows if row["change_pct"] is not None and row["change_pct"] > 0)
    decliners = sum(1 for row in rows if row["change_pct"] is not None and row["change_pct"] < 0)
    unchanged = max(0, len(rows) - advancers - decliners)
    total = advancers + decliners
    leaders = sorted(rows, key=lambda row: row["change_pct"] if row["change_pct"] is not None else -999, reverse=True)[:5]
    volatility = []
    for name, points in indices.items():
        if name == "INDIA VIX":
            display, value = "India VIX", points[-1]["close"]
        elif name == "BANKNIFTY":
            display, value = "BANKNIFTY ATR", _atr(points)
        else:
            display, value = "NIFTY ATR", _atr(points)
        volatility.append({"name": display, "value": round(value, 2) if value is not None else None, "changePct": _change(points), "unit": ""})
    return AnalyticsSnapshot(
        summary={"advancers": advancers, "decliners": decliners, "advanceDeclineRatio": round(advancers / decliners, 2) if decliners else None, "newHighs": sum(1 for row in rows if row["new_high"]), "newLows": sum(1 for row in rows if row["new_low"])},
        breadth={"advancingPercent": round(advancers / total * 100, 2) if total else None, "decliningPercent": round(decliners / total * 100, 2) if total else None, "unchanged": unchanged},
        momentumLeaders=[{"symbol": row["symbol"], "name": row["name"], "price": row["price"], "changePct": row["change_pct"], "volume": row["volume"], "sparkline": row["sparkline"]} for row in leaders],
        volatility=volatility,
        meta={"asOf": datetime.now(timezone.utc), "source": source, "freshness": freshness, "stale": bool(errors) and not rows, "errors": _public_errors(errors)},
    )


def _nse_row(row: dict) -> dict:
    return {
        "symbol": str(row.get("symbol") or ""),
        "name": row.get("companyName") or row.get("companyname") or str(row.get("symbol") or ""),
        "price": row.get("lastPrice"),
        "changePct": row.get("pchange"),
        "volume": row.get("totalTradedVolume"),
        "value": row.get("totalTradedValue"),
    }


def _nse_52_week_row(row: dict) -> dict:
    return {
        "symbol": str(row.get("symbol") or row.get("securityName") or row.get("meta") or (f"{row['count']} stocks" if row.get("count") is not None else "")),
        "name": row.get("companyName") or row.get("comapnyName") or row.get("companyname") or row.get("securityName") or row.get("symbol"),
        "price": row.get("ltp", row.get("lastPrice", row.get("lastTradedPrice"))),
        "changePct": row.get("pChange", row.get("perChange", row.get("pchange"))),
        "volume": row.get("volume", row.get("totalTradedVolume")),
        "value": row.get("value", row.get("totalTradedValue")),
    }


def _nse_52_week_count(rows: list[dict]) -> int:
    if rows and rows[0].get("count") is not None:
        return int(rows[0]["count"])
    return len(rows)


def _nse_snapshot(data: dict) -> AnalyticsSnapshot:
    stats = data.get("statistics") or {}
    breadth = stats.get("snapshotCapitalMarket") or {}
    movers = data.get("marquee") or data.get("gainers") or []
    rows = [{
        "symbol": row.get("symbol"), "name": row.get("symbol"), "price": row.get("lastTradedPrice"),
        "previous_price": None, "volume": None, "change_pct": row.get("perChange"),
        "sparkline": [], "new_high": False, "new_low": False,
    } for row in movers if row.get("symbol") and row.get("lastTradedPrice") is not None]
    advancers = int(breadth.get("advances") or 0)
    decliners = int(breadth.get("declines") or 0)
    unchanged = int(breadth.get("unchange") or 0)
    total = advancers + decliners + unchanged
    index_rows = [{"name": row.get("indexName"), "value": row.get("last", row.get("indexValue")), "changePct": row.get("percChange", row.get("percentChange"))} for row in data.get("indices", []) if row.get("indexName")]
    vix = next((row for row in index_rows if str(row["name"]).upper().replace("-", " ") in {"INDIA VIX", "INDIA VIX INDEX"}), None)
    nifty = next((row for row in data.get("indices", []) if str(row.get("indexName", "")).upper() == "NIFTY 50"), None)
    if vix is None and nifty and nifty.get("last"):
        intraday_range = ((nifty.get("high", nifty["last"]) - nifty.get("low", nifty["last"])) / nifty["last"]) * 100
        vix = {"name": "NIFTY Range", "value": round(intraday_range, 2), "changePct": nifty.get("percChange", nifty.get("percentChange"))}
    active = {}
    for key in ("mostActiveCall", "mostActivePut", "mostActiveContractbyOI"):
        active[key] = [{"contract": row.get("contract") or row.get("identifier") or "", "symbol": row.get("symbol"), "price": row.get("lastPrice"), "changePct": row.get("perChange")} for row in data.get("activeContracts", {}).get(key, [])]
    return AnalyticsSnapshot(
        summary={"advancers": advancers, "decliners": decliners, "advanceDeclineRatio": round(advancers / decliners, 2) if decliners else None, "newHighs": _nse_52_week_count(data.get("newHighs", [])), "newLows": _nse_52_week_count(data.get("newLows", []))},
        breadth={"advancingPercent": round(advancers / total * 100, 2) if total else None, "decliningPercent": round(decliners / total * 100, 2) if total else None, "unchanged": unchanged},
        momentumLeaders=[{"symbol": row["symbol"], "name": row["name"], "price": row["price"], "changePct": row["change_pct"], "volume": row["volume"], "sparkline": row["sparkline"]} for row in sorted(rows, key=lambda item: item["change_pct"] or -999, reverse=True)[:5]],
        volatility=[{"name": vix["name"] if vix else "India VIX", "value": vix["value"] if vix else None, "changePct": vix["changePct"] if vix else None, "unit": "%"}],
        marketCards={**{key: [_nse_row(row) for row in data.get(key, [])[:5]] for key in ("gainers", "losers", "activeValue", "activeVolume")}, "newHighs": [_nse_52_week_row(row) for row in data.get("newHighs", [])[:5]], "newLows": [_nse_52_week_row(row) for row in data.get("newLows", [])[:5]]},
        indices=index_rows,
        activeContracts=active,
        meta={"asOf": datetime.now(timezone.utc), "source": "NSE India", "freshness": "LIVE", "stale": False, "errors": _public_errors(data.get("errors", []))},
    )


def get_analytics(force_refresh: bool = False) -> AnalyticsSnapshot:
    global _fallback_snapshot, _fallback_at
    try:
        with _fallback_lock:
            if (
                not force_refresh
                and _fallback_snapshot is not None
                and time.monotonic() - _fallback_at < float(os.getenv("ANALYTICS_CACHE_TTL_SECONDS", "60"))
            ):
                return _fallback_snapshot
        nse_data = fetch_nse_data()
        if any(nse_data.get(key) for key in ("gainers", "losers", "statistics", "indices", "marquee")):
            return _nse_snapshot(nse_data)
        source, freshness = "Yahoo Finance chart", "DELAYED"
        if angel_configured():
            rows, indices, errors = fetch_angel_data()
            source, freshness = "Angel One SmartAPI", "LIVE"
            if not rows:
                fallback_rows, fallback_indices, fallback_errors = fetch_yahoo_data()
                rows, indices = fallback_rows, fallback_indices
                errors.extend([f"Angel One unavailable: {error}" for error in fallback_errors])
                source, freshness = "Yahoo Finance chart", "DELAYED"
        else:
            rows, indices, errors = fetch_yahoo_data()
        if not rows:
            return _empty_snapshot(errors or ["No market data returned"])
        snapshot = _snapshot(rows, indices, errors, source, freshness)
        if source == "Yahoo Finance chart":
            with _fallback_lock:
                _fallback_snapshot, _fallback_at = snapshot, time.monotonic()
        return snapshot
    except Exception as error:
        return _empty_snapshot(["Market data is temporarily unavailable."])
