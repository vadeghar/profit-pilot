"""Free, provider-independent market news ingestion for the FastAPI API."""
from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from time import monotonic
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
QUERY = '(NIFTY OR BANKNIFTY OR NSE OR BSE OR RBI OR SEBI OR "Indian stock market")'
_cache: tuple[float, dict] | None = None


def _get_json(url: str, timeout: float = 15) -> dict | list:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "ProfitPilot/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_text(url: str, timeout: float = 15) -> str:
    request = Request(url, headers={"Accept": "application/rss+xml, application/xml", "User-Agent": "ProfitPilot/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8")


def _category(text: str) -> str:
    text = text.lower()
    if re.search(r"rbi|sebi|policy|rate|inflation|budget|regulation|government", text):
        return "POLICY"
    if re.search(r"f&o|future|option|open interest|strike|expiry|iv rank|pcr|rollover", text):
        return "F&O"
    if re.search(r"asia|china|japan|us market|wall street|europe|global|fed|nasdaq|dow jones", text):
        return "GLOBAL"
    if re.search(r"bank|it stocks|auto|pharma|metal|energy|realty|fmcg|sector", text):
        return "SECTOR"
    return "MARKET"


def _sentiment(text: str) -> str:
    text = text.lower()
    if re.search(r"gain|rise|rally|positive|surge|beat|upgrade|inflow|growth", text):
        return "POSITIVE"
    if re.search(r"fall|drop|loss|negative|sell|downgrade|outflow|cut|crisis", text):
        return "NEGATIVE"
    return "NEUTRAL"


def _impact(text: str) -> str:
    text = text.lower()
    if re.search(r"rbi|sebi|rate decision|inflation|budget|halt|crash|surge|war", text):
        return "HIGH"
    if re.search(r"earnings|results|upgrade|downgrade|acquisition|ipo|open interest", text):
        return "MEDIUM"
    return "LOW"


def _published_at(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return datetime.now(timezone.utc).isoformat()


def _normalize_article(article: dict, index: int) -> dict | None:
    title = (article.get("title") or "").strip()
    url = article.get("url")
    if not title or not url:
        return None
    text = f"{title} {article.get('domain', '')}"
    return {
        "id": url,
        "publishedAt": _published_at(article.get("seendate")),
        "category": _category(text),
        "title": title,
        "source": article.get("domain") or "GDELT News Monitor",
        "sourceUrl": url,
        "sentiment": _sentiment(text),
        "impact": _impact(text),
    }


def _normalize_rss_item(item: ET.Element, index: int) -> dict | None:
    def value(name: str) -> str:
        return (item.findtext(name) or "").strip()

    title, url = value("title"), value("link")
    if not title or not url:
        return None
    text = f"{title} {value('description')}"
    return {
        "id": url,
        "publishedAt": value("pubDate") or datetime.now(timezone.utc).isoformat(),
        "category": _category(text),
        "title": title,
        "source": "RSS News Feed",
        "sourceUrl": url,
        "sentiment": _sentiment(text),
        "impact": _impact(text),
    }


def _events() -> list[dict]:
    endpoint = os.getenv("MARKET_EVENTS_URL")
    if not endpoint:
        return []
    try:
        payload = _get_json(endpoint)
        events = payload if isinstance(payload, list) else payload.get("events", [])
        return [event for event in events if event.get("id") and event.get("eventAt") and event.get("title")]
    except Exception:
        return []


def _build_response(items: list[dict]) -> dict:
    return {
        "items": items,
        "events": _events(),
        "stats": {
            "headlines": len(items),
            "highImpact": sum(item["impact"] == "HIGH" for item in items),
            "positive": sum(item["sentiment"] == "POSITIVE" for item in items),
            "neutral": sum(item["sentiment"] == "NEUTRAL" for item in items),
        },
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
    }


def _load_gdelt() -> dict:
    params = urlencode({"query": QUERY, "mode": "artlist", "format": "json", "maxrecords": 75, "timespan": "24h", "sort": "datedesc"})
    payload = _get_json(f"{GDELT_URL}?{params}")
    articles = payload.get("articles", []) if isinstance(payload, dict) else []
    items = []
    seen: set[str] = set()
    for index, article in enumerate(articles):
        item = _normalize_article(article, index)
        if item and item["id"] not in seen:
            items.append(item)
            seen.add(item["id"])
    return _build_response(items)


def _load_rss() -> dict:
    urls = os.getenv("NEWS_RSS_URLS", "https://news.google.com/rss/search?q=NIFTY+OR+RBI+OR+NSE&hl=en-IN&gl=IN&ceid=IN:en").split(",")
    items = []
    seen: set[str] = set()
    for feed_url in (url.strip() for url in urls if url.strip()):
        root = ET.fromstring(_get_text(feed_url))
        for index, element in enumerate(root.findall(".//item")):
            item = _normalize_rss_item(element, index)
            if item and item["id"] not in seen:
                items.append(item)
                seen.add(item["id"])
    return _build_response(items)


def get_news(force_refresh: bool = False) -> dict:
    global _cache
    ttl = float(os.getenv("NEWS_CACHE_TTL_SECONDS", "60"))
    if not force_refresh and _cache and monotonic() - _cache[0] < ttl:
        return _cache[1]
    try:
        try:
            data = _load_gdelt()
        except Exception as gdelt_error:
            try:
                data = _load_rss()
            except Exception as rss_error:
                raise RuntimeError(f"GDELT failed: {gdelt_error}; RSS failed: {rss_error}") from rss_error
        _cache = (monotonic(), data)
        return data
    except Exception as error:
        if _cache:
            return _cache[1]
        raise RuntimeError(f"News provider unavailable: {error}") from error
