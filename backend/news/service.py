from __future__ import annotations

import os
from datetime import datetime, timezone
from time import monotonic

from .models import NewsResponse
from .sources.events import fetch_events
from .sources.feeds import fetch_feeds

_cache: tuple[float, NewsResponse] | None = None


def _response(items: list[dict], events: list[dict], providers: dict[str, list[str]], errors: list[str], stale: bool = False) -> NewsResponse:
    items.sort(key=lambda item: item["publishedAt"], reverse=True)
    events.sort(key=lambda event: event["eventAt"])
    return NewsResponse(
        items=items,
        events=events,
        stats={
            "headlines": len(items),
            "highImpact": sum(item["impact"] == "HIGH" for item in items),
            "positive": sum(item["sentiment"] == "POSITIVE" for item in items),
            "neutral": sum(item["sentiment"] == "NEUTRAL" for item in items),
        },
        fetchedAt=datetime.now(timezone.utc),
        sources=providers,
        errors=errors,
        stale=stale,
    )


def get_news(force_refresh: bool = False) -> dict:
    global _cache
    ttl = float(os.getenv("NEWS_CACHE_TTL_SECONDS", "60"))
    if not force_refresh and _cache and monotonic() - _cache[0] < ttl:
        return _cache[1].model_dump(by_alias=True)

    items, feed_providers, feed_errors = fetch_feeds()
    events, event_providers, event_errors = fetch_events()
    errors = feed_errors + event_errors
    if not items and not events:
        if _cache:
            stale = _cache[1].model_copy(update={"stale": True, "errors": errors})
            return stale.model_dump(by_alias=True)
        raise RuntimeError("No news or event source returned data: " + "; ".join(errors))

    data = _response(items, events, {"news": feed_providers, "events": event_providers}, errors)
    _cache = (monotonic(), data)
    return data.model_dump(by_alias=True)
