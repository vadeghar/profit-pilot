# Profit Pilot

High-density trading terminal UI built with React, TypeScript, Tailwind CSS and Lucide React. The UI is designed to become the frontend of a Python/FastAPI trading application.

## Current mock-data UI
- Persistent TerminalLayout with header, collapsible sidebar and footer ticker.
- Dashboard/watchlist with live mock tick simulation.
- 300ms green/red tick flashes.
- NIFTY 50 candlestick visualization.
- Positions, market news and breadth panels.
- Order-ticket route reserved for execution workflow.
- WebSocket context ready for a Python backend.

## Run
```bash
npm install
npm run dev
```

Set `VITE_WS_URL=ws://localhost:8000/ws` when connecting the UI to the Python backend.

Run the FastAPI backend and UI in separate terminals during development:

```bash
cd backend
uvicorn api.main:app --reload --port 8000

# second terminal, from the repository root
npm run dev
```

Vite proxies `/api/*` from port `5173` to FastAPI on port `8000`, so the UI can use `http://localhost:5173/api/news`.

## News feed

The `/news` route reads normalized data from `VITE_NEWS_API_URL` (default: `/api/news`). FastAPI provides that endpoint using the free GDELT DOC 2.0 API and falls back to configurable RSS feeds (`NEWS_RSS_URLS`) if GDELT is unavailable. Neither source requires an API key. Keep any future provider credentials server-side; do not prefix them with `VITE_`.

Set `MARKET_EVENTS_URL` in `backend/.env` to an endpoint returning either an array of `MarketEvent` objects or `{ "events": [...] }`. `GLOBAL_MACRO_ICS_URL` can point to an official iCalendar release schedule such as the BLS calendar. The news endpoint caches successful responses for `NEWS_CACHE_TTL_SECONDS` and returns `503` only when no news or event source returns data.

Market events also support free public feeds without API keys. Set `NSE_RSS_URLS` to the Financial Results and/or Board Meetings RSS URLs published on the [NSE RSS page](https://www.nseindia.com/static/rss-feed); results are limited to `TOP_COMPANIES` and normalized as `EARNINGS` events. `BSE_RSS_URLS` and `BSE_EVENTS_URL` are optional adapters for a permitted public BSE RSS/JSON mirror because BSE does not expose a stable documented RSS endpoint. `MARKET_EVENTS_URL` accepts either JSON or RSS, so it can be used for a small self-hosted normalized calendar as well.
