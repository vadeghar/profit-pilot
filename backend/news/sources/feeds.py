from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_QUERY = '(NIFTY OR BANKNIFTY OR NSE OR BSE OR RBI OR SEBI OR "Indian stock market")'
DEFAULT_RSS = "https://news.google.com/rss/search?q=NIFTY+OR+RBI+OR+NSE&hl=en-IN&gl=IN&ceid=IN:en"


def _request(url: str, accept: str, timeout: float = 15) -> bytes:
    request = Request(url, headers={"Accept": accept, "User-Agent": "ProfitPilot/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _classify(text: str) -> str:
    text = text.lower()
    if re.search(r"rbi|sebi|policy|rate|inflation|budget|regulation|government", text): return "POLICY"
    if re.search(r"f&o|future|option|open interest|strike|expiry|iv rank|pcr|rollover", text): return "F&O"
    if re.search(r"asia|china|japan|us market|wall street|europe|global|fed|nasdaq|dow jones", text): return "GLOBAL"
    if re.search(r"bank|it stocks|auto|pharma|metal|energy|realty|fmcg|sector", text): return "SECTOR"
    return "MARKET"


def _sentiment(text: str) -> str:
    text = text.lower()
    if re.search(r"gain|rise|rally|positive|surge|beat|upgrade|inflow|growth", text): return "POSITIVE"
    if re.search(r"fall|drop|loss|negative|sell|downgrade|outflow|cut|crisis", text): return "NEGATIVE"
    return "NEUTRAL"


def _impact(text: str) -> str:
    text = text.lower()
    if re.search(r"rbi|sebi|rate decision|inflation|budget|halt|crash|surge|war", text): return "HIGH"
    if re.search(r"earnings|results|upgrade|downgrade|acquisition|ipo|open interest", text): return "MEDIUM"
    return "LOW"


def _date(value: str | None) -> str:
    if not value: return datetime.now(timezone.utc).isoformat()
    try: return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).isoformat()
    except ValueError: pass
    try:
        parsed = parsedate_to_datetime(value)
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError): return datetime.now(timezone.utc).isoformat()


def _normalize(article: dict, source: str) -> dict | None:
    title, url = (article.get("title") or "").strip(), article.get("url")
    if not title or not url: return None
    text = f"{title} {article.get('description', '')} {article.get('domain', '')}"
    return {"id": url, "publishedAt": _date(article.get("seendate") or article.get("publishedAt")), "category": _classify(text), "title": title, "summary": article.get("description"), "source": source, "sourceUrl": url, "sentiment": _sentiment(text), "impact": _impact(text)}


def _gdelt() -> list[dict]:
    query = urlencode({"query": GDELT_QUERY, "mode": "artlist", "format": "json", "maxrecords": 75, "timespan": "24h", "sort": "datedesc"})
    payload = json.loads(_request(f"{GDELT_URL}?{query}", "application/json"))
    return [item for article in payload.get("articles", []) if (item := _normalize(article, article.get("domain") or "GDELT News Monitor"))]


def _rss() -> list[dict]:
    items = []
    for url in (value.strip() for value in os.getenv("NEWS_RSS_URLS", DEFAULT_RSS).split(",") if value.strip()):
        root = ET.fromstring(_request(url, "application/rss+xml, application/xml"))
        for element in root.findall(".//item"):
            article = {"title": element.findtext("title"), "url": element.findtext("link"), "description": element.findtext("description"), "publishedAt": element.findtext("pubDate")}
            if item := _normalize(article, "RSS News Feed"): items.append(item)
    return items


def fetch_feeds() -> tuple[list[dict], list[str], list[str]]:
    errors, providers = [], []
    try:
        items = _gdelt(); providers.append("gdelt")
    except Exception as error:
        errors.append(f"gdelt: {error}")
        try:
            items = _rss(); providers.append("rss")
        except Exception as rss_error:
            errors.append(f"rss: {rss_error}")
            return [], providers, errors
    return list({item["id"]: item for item in items}.values()), providers, errors
