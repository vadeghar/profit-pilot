"""Black-Scholes helpers used to derive historical IV and delta from candles.

The database stores option OHLC, not provider Greeks. These calculations use
the selected candle price as a proxy for an executable option price.
"""

from __future__ import annotations

import math
from typing import Literal

OptionType = Literal["CE", "PE"]


def _validate_option_type(option_type: str) -> None:
    if option_type not in {"CE", "PE"}:
        raise ValueError(f"Unsupported option type: {option_type}")


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def _d1(
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    dividend_yield: float,
    volatility: float,
) -> float:
    return (
        math.log(spot / strike)
        + (rate - dividend_yield + 0.5 * volatility * volatility) * time_years
    ) / (volatility * math.sqrt(time_years))


def black_scholes_price(
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    dividend_yield: float,
    volatility: float,
    option_type: OptionType,
) -> float:
    """Return a European option's theoretical price."""
    _validate_option_type(option_type)
    if min(spot, strike) <= 0:
        raise ValueError("spot and strike must be positive")
    if time_years <= 0:
        intrinsic = max(spot - strike, 0.0) if option_type == "CE" else max(strike - spot, 0.0)
        return intrinsic
    if volatility <= 0:
        raise ValueError("volatility must be positive")

    d1 = _d1(spot, strike, time_years, rate, dividend_yield, volatility)
    d2 = d1 - volatility * math.sqrt(time_years)
    spot_pv = spot * math.exp(-dividend_yield * time_years)
    strike_pv = strike * math.exp(-rate * time_years)

    if option_type == "CE":
        return spot_pv * _normal_cdf(d1) - strike_pv * _normal_cdf(d2)
    return strike_pv * _normal_cdf(-d2) - spot_pv * _normal_cdf(-d1)


def intrinsic_value(spot: float, strike: float, option_type: OptionType) -> float:
    _validate_option_type(option_type)
    return max(spot - strike, 0.0) if option_type == "CE" else max(strike - spot, 0.0)


def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    dividend_yield: float,
    option_type: OptionType,
    *,
    max_volatility: float = 8.0,
    tolerance: float = 1e-7,
    max_iterations: int = 120,
) -> float | None:
    """Solve IV with bisection, returning None for invalid/non-convergent prices."""
    _validate_option_type(option_type)
    if market_price <= 0 or min(spot, strike) <= 0 or time_years <= 0:
        return None

    lower = intrinsic_value(spot, strike, option_type)
    if option_type == "CE":
        upper = spot * math.exp(-dividend_yield * time_years)
    else:
        upper = strike * math.exp(-rate * time_years)

    # A small tolerance accommodates rounded candle prices at the bounds.
    if market_price < lower - tolerance or market_price > upper + tolerance:
        return None

    low, high = 1e-6, max_volatility
    low_price = black_scholes_price(spot, strike, time_years, rate, dividend_yield, low, option_type)
    high_price = black_scholes_price(spot, strike, time_years, rate, dividend_yield, high, option_type)
    if market_price < low_price - tolerance or market_price > high_price + tolerance:
        return None

    for _ in range(max_iterations):
        mid = (low + high) / 2.0
        price = black_scholes_price(spot, strike, time_years, rate, dividend_yield, mid, option_type)
        if abs(price - market_price) <= tolerance:
            return mid
        if price < market_price:
            low = mid
        else:
            high = mid

    result = (low + high) / 2.0
    return result if abs(black_scholes_price(spot, strike, time_years, rate, dividend_yield, result, option_type) - market_price) <= 1e-4 else None


def option_delta(
    spot: float,
    strike: float,
    time_years: float,
    rate: float,
    dividend_yield: float,
    volatility: float,
    option_type: OptionType,
) -> float:
    """Return Black-Scholes delta for a European call or put."""
    _validate_option_type(option_type)
    if min(spot, strike) <= 0 or time_years <= 0 or volatility <= 0:
        raise ValueError("spot, strike, time, and volatility must be positive")

    d1 = _d1(spot, strike, time_years, rate, dividend_yield, volatility)
    discount = math.exp(-dividend_yield * time_years)
    return discount * _normal_cdf(d1) if option_type == "CE" else discount * (_normal_cdf(d1) - 1.0)
