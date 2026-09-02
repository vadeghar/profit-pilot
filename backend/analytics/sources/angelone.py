from __future__ import annotations

import json
import os
import threading
from urllib.request import Request, urlopen

try:
    import pyotp
    from SmartApi import SmartConnect
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
except ImportError:  # Optional until Angel One credentials are configured.
    pyotp = None
    SmartConnect = None
    SmartWebSocketV2 = None


INSTRUMENT_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
DEFAULT_SYMBOLS = "RELIANCE,TCS,HDFCBANK,ICICIBANK,INFY,ITC,SBIN,BHARTIARTL,LT,AXISBANK,KOTAKBANK,HINDUNILVR,BAJFINANCE,MARUTI,ASIANPAINT"
INDEX_ALIASES = {"NIFTY 50": ("NIFTY", "NIFTY 50"), "BANKNIFTY": ("BANKNIFTY", "NIFTY BANK"), "INDIA VIX": ("INDIAVIX", "INDIA VIX")}


def configured() -> bool:
    return all(os.getenv(name) for name in ("ANGEL_ONE_API_KEY", "ANGEL_ONE_CLIENT_ID", "ANGEL_ONE_PASSWORD", "ANGEL_ONE_TOTP_SECRET")) and SmartConnect is not None and SmartWebSocketV2 is not None and pyotp is not None


class AngelOneMarketData:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._started = False
        self._error: str | None = None
        self._token_map: dict[str, str] = {}
        self._ticks: dict[str, dict] = {}
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._started or not configured():
            return
        self._started = True
        self._thread = threading.Thread(target=self._run, name="angelone-market-data", daemon=True)
        self._thread.start()

    def snapshot(self) -> tuple[list[dict], dict[str, list[dict]], list[str]]:
        self.start()
        self._ready.wait(timeout=float(os.getenv("ANALYTICS_INITIAL_WAIT_SECONDS", "5")))
        with self._lock:
            ticks = dict(self._ticks)
            error = self._error
        rows = []
        for symbol in self._symbols():
            tick = ticks.get(symbol)
            if not tick:
                continue
            price = tick.get("last_traded_price")
            previous = tick.get("closed_price")
            if price is None:
                continue
            rows.append({
                "symbol": symbol,
                "name": symbol,
                "price": price,
                "previous_price": previous,
                "volume": tick.get("volume_trade_for_the_day"),
                "change_pct": ((price - previous) / previous * 100) if previous else None,
                "sparkline": [price],
                "new_high": price >= tick.get("52_week_high_price", price),
                "new_low": price <= tick.get("52_week_low_price", price),
            })
        indices = {}
        for display in INDEX_ALIASES:
            tick = ticks.get(display)
            if tick and tick.get("last_traded_price") is not None:
                indices[display] = [{"close": tick["last_traded_price"], "high": tick.get("high_price_of_the_day", tick["last_traded_price"]), "low": tick.get("low_price_of_the_day", tick["last_traded_price"])}]
        return rows, indices, [error] if error else []

    @staticmethod
    def _symbols() -> list[str]:
        return [value.strip().upper() for value in os.getenv("ANALYTICS_SYMBOLS", DEFAULT_SYMBOLS).split(",") if value.strip()]

    def _run(self) -> None:
        try:
            instruments = self._load_instruments()
            subscriptions = self._resolve_tokens(instruments)
            if not subscriptions:
                raise RuntimeError("No configured Analytics symbols matched the Angel One instrument master")
            smart_api = SmartConnect(os.environ["ANGEL_ONE_API_KEY"])
            session = smart_api.generateSession(os.environ["ANGEL_ONE_CLIENT_ID"], os.environ["ANGEL_ONE_PASSWORD"], pyotp.TOTP(os.environ["ANGEL_ONE_TOTP_SECRET"]).now())
            if not session.get("status"):
                raise RuntimeError(session.get("message", "Angel One login failed"))
            data = session["data"]
            socket = SmartWebSocketV2(data["jwtToken"], os.environ["ANGEL_ONE_API_KEY"], os.environ["ANGEL_ONE_CLIENT_ID"], data["feedToken"], max_retry_attempt=5)

            def on_open(wsapp):
                socket.subscribe("profit-pilot-analytics", SmartWebSocketV2.SNAP_QUOTE, [{"exchangeType": 1, "tokens": list(self._token_map.values())}])

            def on_data(wsapp, message):
                if not isinstance(message, dict):
                    return
                token = str(message.get("token", ""))
                symbol = next((key for key, value in self._token_map.items() if value == token), None)
                if not symbol:
                    return
                normalized = dict(message)
                for field in ("last_traded_price", "closed_price", "high_price_of_the_day", "low_price_of_the_day", "52_week_high_price", "52_week_low_price"):
                    if normalized.get(field) is not None:
                        normalized[field] = float(normalized[field]) / 100
                with self._lock:
                    self._ticks[symbol] = normalized
                    self._error = None
                    self._ready.set()

            def on_error(wsapp, error):
                with self._lock:
                    self._error = f"Angel One WebSocket: {error}"
                    self._ready.set()

            socket.on_open, socket.on_data, socket.on_error = on_open, on_data, on_error
            socket.connect()
        except Exception as error:
            with self._lock:
                self._error = str(error)
                self._ready.set()

    def _load_instruments(self) -> list[dict]:
        request = Request(INSTRUMENT_URL, headers={"Accept": "application/json", "User-Agent": "ProfitPilot/1.0"})
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))

    def _resolve_tokens(self, instruments: list[dict]) -> list[str]:
        wanted = self._symbols()
        resolved = []
        for symbol in wanted:
            record = next((item for item in instruments if item.get("exch_seg") == "NSE" and str(item.get("symbol", "")).upper() in {symbol, f"{symbol}-EQ"}), None)
            if record:
                self._token_map[symbol] = str(record["token"])
                resolved.append(str(record["token"]))
        for display, aliases in INDEX_ALIASES.items():
            record = next((item for item in instruments if item.get("exch_seg") == "NSE" and str(item.get("symbol", "")).upper() in aliases), None)
            if record:
                self._token_map[display] = str(record["token"])
                resolved.append(str(record["token"]))
        return resolved


_manager = AngelOneMarketData()


def fetch_market_data() -> tuple[list[dict], dict[str, list[dict]], list[str]]:
    return _manager.snapshot()
