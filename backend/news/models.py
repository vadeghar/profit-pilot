from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NewsCategory = Literal["MARKET", "POLICY", "GLOBAL", "SECTOR", "F&O"]
Impact = Literal["HIGH", "MEDIUM", "LOW"]
Sentiment = Literal["POSITIVE", "NEGATIVE", "NEUTRAL"]


class NewsItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    published_at: datetime = Field(alias="publishedAt")
    category: NewsCategory
    title: str
    summary: str | None = None
    source: str
    source_url: str = Field(alias="sourceUrl")
    sentiment: Sentiment
    impact: Impact


class MarketEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    event_at: datetime = Field(alias="eventAt")
    timezone: str = "Asia/Kolkata"
    title: str
    country: str | None = None
    category: str = "MARKET"
    symbol: str | None = None
    fiscal_period: str | None = Field(default=None, alias="fiscalPeriod")
    impact: Impact = "MEDIUM"
    status: Literal["UPCOMING", "RELEASED", "CANCELLED"] = "UPCOMING"
    source: str = "Profit Pilot"
    source_url: str | None = Field(default=None, alias="sourceUrl")
    actual: str | None = None
    forecast: str | None = None
    previous: str | None = None


class NewsStats(BaseModel):
    headlines: int
    high_impact: int = Field(alias="highImpact")
    positive: int
    neutral: int


class NewsResponse(BaseModel):
    items: list[NewsItem]
    events: list[MarketEvent]
    stats: NewsStats
    fetched_at: datetime = Field(alias="fetchedAt")
    sources: dict[str, list[str]]
    stale: bool = False
    errors: list[str] = Field(default_factory=list)
