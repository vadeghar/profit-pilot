from __future__ import annotations

import os
from datetime import datetime, timezone
from time import monotonic

import cache
from .models import NewsResponse
from .sources.events import fetch_events
from .sources.feeds import fetch_feeds

CACHE_KEY = "news:v1:all"

# In-process fallback -- used only when Redis is disabled/unreachable, or as
# the "serve something stale rather than nothing" path when every upstream
# source fails and Redis has nothing cached either.
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
    ttl = int(float(os.getenv("NEWS_CACHE_TTL_SECONDS", "60")))

    if not force_refresh:
        cached = cache.get_json(CACHE_KEY)
        if cached is not None:
            return cached
        # Redis disabled/unreachable/empty -- fall back to the in-process TTL
        # cache so a single dev server still avoids refetching on every call.
        if _cache and monotonic() - _cache[0] < ttl:
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
    result = data.model_dump(by_alias=True)
    cache.set_json(CACHE_KEY, result, ttl_seconds=ttl)
    _cache = (monotonic(), data)
    return result
