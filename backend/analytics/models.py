from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AnalyticsMeta(BaseModel):
    as_of: datetime = Field(alias="asOf")
    source: str
    freshness: Literal["LIVE", "DELAYED", "EOD", "STALE", "UNAVAILABLE"]
    stale: bool = False
    errors: list[str] = Field(default_factory=list)


class AnalyticsSummary(BaseModel):
    advancers: int | None = None
    decliners: int | None = None
    advance_decline_ratio: float | None = Field(default=None, alias="advanceDeclineRatio")
    new_highs: int | None = Field(default=None, alias="newHighs")
    new_lows: int | None = Field(default=None, alias="newLows")


class BreadthData(BaseModel):
    advancing_percent: float | None = Field(default=None, alias="advancingPercent")
    declining_percent: float | None = Field(default=None, alias="decliningPercent")
    unchanged: int | None = None


class MomentumLeader(BaseModel):
    symbol: str
    name: str
    price: float | None = None
    change_pct: float | None = Field(default=None, alias="changePct")
    volume: float | None = None
    sparkline: list[float] = Field(default_factory=list)


class VolatilityMetric(BaseModel):
    name: str
    value: float | None = None
    change_pct: float | None = Field(default=None, alias="changePct")
    unit: str = ""


class MarketMover(BaseModel):
    symbol: str
    name: str | None = None
    price: float | None = None
    change_pct: float | None = Field(default=None, alias="changePct")
    volume: float | None = None
    value: float | None = None


class IndexSnapshot(BaseModel):
    name: str
    value: float | None = None
    change_pct: float | None = Field(default=None, alias="changePct")


class ActiveContract(BaseModel):
    contract: str
    symbol: str | None = None
    price: float | None = None
    change_pct: float | None = Field(default=None, alias="changePct")


class AnalyticsSnapshot(BaseModel):
    summary: AnalyticsSummary
    breadth: BreadthData
    momentum_leaders: list[MomentumLeader] = Field(alias="momentumLeaders")
    volatility: list[VolatilityMetric]
    market_cards: dict[str, list[MarketMover]] = Field(default_factory=dict, alias="marketCards")
    indices: list[IndexSnapshot] = Field(default_factory=list)
    active_contracts: dict[str, list[ActiveContract]] = Field(default_factory=dict, alias="activeContracts")
    meta: AnalyticsMeta
