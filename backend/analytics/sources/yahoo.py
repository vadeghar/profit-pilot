from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote
from urllib.request import Request, urlopen

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{}"
DEFAULT_SYMBOLS = "RELIANCE,TCS,HDFCBANK,ICICIBANK,INFY,ITC,SBIN,BHARTIARTL,LT,AXISBANK,KOTAKBANK,HINDUNILVR,BAJFINANCE,MARUTI,ASIANPAINT"
INDEX_SYMBOLS = {"NIFTY 50": "^NSEI", "BANKNIFTY": "^NSEBANK", "INDIA VIX": "^INDIAVIX"}


def _symbols() -> list[str]:
    return [value.strip().upper() for value in os.getenv("ANALYTICS_SYMBOLS", DEFAULT_SYMBOLS).split(",") if value.strip()]


def _fetch(symbol: str, range_: str = "1y") -> dict:
    ticker = INDEX_SYMBOLS.get(symbol, f"{symbol}.NS")
    url = f"{YAHOO_CHART_URL.format(quote(ticker))}?range={range_}&interval=1d&includePrePost=false"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "ProfitPilot/1.0"})
    with urlopen(request, timeout=12) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = payload["chart"]["result"][0]
    quote_data = result["indicators"]["quote"][0]
    timestamps = result.get("timestamp", [])
    points = []
    for index, timestamp in enumerate(timestamps):
        close = quote_data.get("close", [])[index]
        if close is not None:
            points.append({"timestamp": timestamp, "close": close, "high": quote_data.get("high", [])[index], "low": quote_data.get("low", [])[index], "volume": quote_data.get("volume", [])[index]})
    if not points:
        raise ValueError(f"no chart data for {symbol}")
    return {"symbol": symbol, "points": points}


def fetch_market_data() -> tuple[list[dict], dict[str, list[dict]], list[str]]:
    symbols = _symbols()
    requested = symbols + list(INDEX_SYMBOLS)
    data, errors = {}, []
    with ThreadPoolExecutor(max_workers=min(8, len(requested) or 1)) as pool:
        futures = {pool.submit(_fetch, symbol): symbol for symbol in requested}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                data[symbol] = future.result()
            except Exception as error:
                errors.append(f"{symbol}: {error}")
    rows = []
    for symbol in symbols:
        series = data.get(symbol, {}).get("points", [])
        if not series:
            continue
        latest, previous = series[-1], series[-2] if len(series) > 1 else None
        rows.append({
            "symbol": symbol, "name": symbol, "price": latest["close"],
            "previous_price": previous["close"] if previous else None, "volume": latest["volume"],
            "change_pct": ((latest["close"] - previous["close"]) / previous["close"] * 100) if previous and previous["close"] else None,
            "sparkline": [point["close"] for point in series[-8:]],
            "new_high": latest["close"] >= max(point["close"] for point in series[:-1]) if len(series) > 1 else False,
            "new_low": latest["close"] <= min(point["close"] for point in series[:-1]) if len(series) > 1 else False,
        })
    return rows, {symbol: data[symbol]["points"] for symbol in INDEX_SYMBOLS if symbol in data}, errors
