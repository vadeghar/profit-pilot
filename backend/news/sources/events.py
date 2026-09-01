from __future__ import annotations

import json
import os
from datetime import datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
import re
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo
from urllib.request import Request, urlopen


TOP_COMPANIES = {
    value.strip().upper(): value.strip()
    for value in os.getenv(
        "TOP_COMPANIES",
        "RELIANCE,TCS,HDFCBANK,ICICIBANK,INFY,ITC,SBIN,BHARTIARTL,LT,AXISBANK,KOTAKBANK,HINDUNILVR,"
        "BAJFINANCE,MARUTI,ASIANPAINT",
    ).split(",")
    if value.strip()
}
RESULT_TERMS = re.compile(r"financial results?|quarterly results?|earnings|results for the quarter", re.I)


def _parse_date(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(value)
        return (parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).isoformat()
    except (TypeError, ValueError, OverflowError):
        return datetime.now(timezone.utc).isoformat()


def _strip_html(value: str | None) -> str:
    return re.sub(r"<[^>]+>", " ", unescape(value or "")).strip()


def _rss_events(endpoint: str, provider: str, only_top_companies: bool = False) -> list[dict]:
    request = Request(endpoint, headers={"Accept": "application/rss+xml, application/xml", "User-Agent": "ProfitPilot/1.0"})
    with urlopen(request, timeout=10) as response:
        root = ET.fromstring(response.read())
    events = []
    for item in root.findall(".//item"):
        title = _strip_html(item.findtext("title"))
        description = _strip_html(item.findtext("description"))
        text = f"{title} {description}"
        if not title or (only_top_companies and not any(re.search(rf"\b{re.escape(symbol)}\b", text.upper()) for symbol in TOP_COMPANIES)):
            continue
        is_earnings = bool(RESULT_TERMS.search(text))
        symbol = next((symbol for symbol in TOP_COMPANIES if re.search(rf"\b{re.escape(symbol)}\b", text.upper())), None)
        published = item.findtext("pubDate") or item.findtext("published") or item.findtext("updated")
        link = item.findtext("link") or endpoint
        events.append({
            "id": link,
            "eventAt": _parse_date(published),
            "timezone": "Asia/Kolkata",
            "title": title,
            "country": "IN",
            "category": "EARNINGS" if is_earnings else "MARKET",
            "symbol": symbol,
            "fiscalPeriod": "Quarterly" if is_earnings else None,
            "impact": "HIGH" if is_earnings else "MEDIUM",
            "status": "RELEASED",
            "source": provider,
            "sourceUrl": link,
        })
    return events


def _external_events(endpoint: str, provider: str) -> list[dict]:
    request = Request(endpoint, headers={"Accept": "application/json, application/rss+xml, application/xml", "User-Agent": "ProfitPilot/1.0"})
    with urlopen(request, timeout=10) as response:
        payload = response.read()
    try:
        decoded = json.loads(payload.decode("utf-8"))
        return decoded if isinstance(decoded, list) else decoded.get("events", [])
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _rss_events(endpoint, provider)


def _custom_events() -> list[dict]:
    endpoint = os.getenv("MARKET_EVENTS_URL")
    return _external_events(endpoint, "Configured market events") if endpoint else []


def _macro_ics_events() -> list[dict]:
    endpoint = os.getenv("GLOBAL_MACRO_ICS_URL")
    if not endpoint: return []
    request = Request(endpoint, headers={"Accept": "text/calendar", "User-Agent": "ProfitPilot/1.0"})
    with urlopen(request, timeout=10) as response:
        lines = response.read().decode("utf-8").replace("\r\n ", "").splitlines()
    events, current = [], {}
    for line in lines:
        if line == "BEGIN:VEVENT": current = {}
        elif line == "END:VEVENT":
            start, title = current.get("DTSTART"), current.get("SUMMARY")
            if start and title:
                value = start.split(":", 1)[-1]
                parsed = datetime.strptime(value[:15], "%Y%m%dT%H%M%S").replace(tzinfo=ZoneInfo("America/New_York"))
                events.append({"id": current.get("UID", f"macro-{value}"), "eventAt": parsed.isoformat(), "timezone": "America/New_York", "title": title, "country": "US", "category": "GLOBAL", "impact": "HIGH" if any(word in title.lower() for word in ("employment", "cpi", "inflation", "fed")) else "MEDIUM", "status": "UPCOMING", "source": "Official macro calendar", "sourceUrl": endpoint})
        elif ":" in line:
            key, value = line.split(":", 1)
            current[key.split(";", 1)[0]] = value
    return events


def _nse_events(now: datetime) -> list[dict]:
    if now.weekday() >= 5: return []
    holidays = {value.strip() for value in os.getenv("NSE_HOLIDAYS", "").split(",") if value.strip()}
    if now.date().isoformat() in holidays: return []
    day = now.date().isoformat()
    ist = timezone(timedelta(hours=5, minutes=30))
    source = "https://www.nseindia.com/resources/exchange-communication-holidays/"
    return [
        {"id": f"nse-open-{day}", "eventAt": datetime.combine(now.date(), time(9, 15), ist).isoformat(), "title": "NSE cash market open", "category": "MARKET", "impact": "MEDIUM", "status": "UPCOMING", "source": "NSE India", "sourceUrl": source},
        {"id": f"nse-close-{day}", "eventAt": datetime.combine(now.date(), time(15, 30), ist).isoformat(), "title": "NSE cash market close", "category": "MARKET", "impact": "HIGH", "status": "UPCOMING", "source": "NSE India", "sourceUrl": source},
    ]


def fetch_events() -> tuple[list[dict], list[str], list[str]]:
    ist = timezone(timedelta(hours=5, minutes=30))
    events, providers, errors = _nse_events(datetime.now(timezone.utc).astimezone(ist)), ["nse"], []
    try:
        custom = _custom_events()
        if custom: events.extend(custom); providers.append("custom")
    except Exception as error:
        errors.append(f"custom-events: {error}")
    for env_name, provider, top_only in (
        ("NSE_RSS_URLS", "NSE India", True),
        ("BSE_RSS_URLS", "BSE India", True),
    ):
        for endpoint in (value.strip() for value in os.getenv(env_name, "").split(",") if value.strip()):
            try:
                feed_events = _rss_events(endpoint, provider, only_top_companies=top_only)
                if feed_events:
                    events.extend(feed_events)
                    providers.append(env_name.lower().replace("_urls", ""))
            except Exception as error:
                errors.append(f"{env_name.lower()}: {error}")
    bse_endpoint = os.getenv("BSE_EVENTS_URL")
    if bse_endpoint:
        try:
            bse_events = _external_events(bse_endpoint, "BSE India")
            events.extend(bse_events)
            if bse_events: providers.append("bse")
        except Exception as error:
            errors.append(f"bse-events: {error}")
    try:
        macro = _macro_ics_events()
        if macro: events.extend(macro); providers.append("global-macro")
    except Exception as error:
        errors.append(f"global-macro: {error}")
    unique = {event["id"]: event for event in events if event.get("id") and event.get("eventAt") and event.get("title")}
    return list(unique.values()), providers, errors
