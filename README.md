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

## News feed

The `/news` route reads normalized data from `VITE_NEWS_API_URL` (default: `/api/news`). The included Express server provides that endpoint using NewsAPI when `NEWS_API_KEY` is configured. Keep provider credentials server-side; do not prefix them with `VITE_`.

Set `MARKET_EVENTS_URL` to an endpoint returning either an array of `MarketEvent` objects or `{ "events": [...] }`. The news endpoint caches successful responses for `NEWS_CACHE_TTL_MS` and returns `503` when no provider is configured, allowing the UI to retain its fallback feed.
