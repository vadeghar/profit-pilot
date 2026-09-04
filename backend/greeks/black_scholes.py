"""
Vectorized spot-based Black-Scholes pricing, Greeks, and implied-volatility
solver for NIFTY options.

All functions accept numpy arrays (or scalars broadcastable to arrays) and
return numpy arrays, so a full day's strike chain can be priced in one call
rather than looping row-by-row. `option_type` is an array of 'CE'/'PE'
strings (or a boolean is_call array -- see `_is_call`).

Model: continuous-dividend-yield Black-Scholes.
    d1 = [ln(S/K) + (r - q + sigma^2/2) * T] / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr

MODEL_VERSION = "bs_spot_v1"

# IV solver tuning
_NEWTON_MAX_ITER = 50
_NEWTON_TOL = 1e-6
_IV_INITIAL_GUESS = 0.20
_IV_LOWER_BOUND = 0.005   # 0.5% -- effectively zero vol
_IV_UPPER_BOUND = 5.0     # 500% -- generous ceiling to guard against garbage prices
_MIN_TIME_VALUE = 1e-6    # below this, treat the option as having no solvable time value


def _is_call(option_type: np.ndarray) -> np.ndarray:
    """option_type is an array of 'CE'/'PE' strings -> boolean is_call array."""
    return np.asarray(option_type) == "CE"


def _norm_cdf(x: np.ndarray) -> np.ndarray:
    return ndtr(x)


def _norm_pdf(x: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * x * x) / np.sqrt(2.0 * np.pi)


def _d1_d2(S, K, T, r, q, sigma):
    S, K, T, r, q, sigma = (np.asarray(a, dtype=float) for a in (S, K, T, r, q, sigma))
    sqrt_t = np.sqrt(T)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t
    return d1, d2


def bs_price(S, K, T, r, q, sigma, option_type) -> np.ndarray:
    """Black-Scholes price. All args broadcastable arrays; option_type is 'CE'/'PE'."""
    S, K, T, r, q = (np.asarray(a, dtype=float) for a in (S, K, T, r, q))
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    is_call = _is_call(option_type)

    call_price = S * np.exp(-q * T) * _norm_cdf(d1) - K * np.exp(-r * T) * _norm_cdf(d2)
    put_price = K * np.exp(-r * T) * _norm_cdf(-d2) - S * np.exp(-q * T) * _norm_cdf(-d1)

    return np.where(is_call, call_price, put_price)


def bs_vega(S, K, T, r, q, sigma) -> np.ndarray:
    """Vega, per 1.0 (100%) change in vol -- same formula for calls and puts."""
    S, T, q = (np.asarray(a, dtype=float) for a in (S, T, q))
    d1, _ = _d1_d2(S, K, T, r, q, sigma)
    return S * np.exp(-q * T) * _norm_pdf(d1) * np.sqrt(T)


def intrinsic_value(S, K, option_type) -> np.ndarray:
    S, K = np.asarray(S, dtype=float), np.asarray(K, dtype=float)
    is_call = _is_call(option_type)
    return np.where(is_call, np.maximum(S - K, 0.0), np.maximum(K - S, 0.0))


def implied_volatility(S, K, T, r, q, market_price, option_type):
    """
    Solve for sigma given a market price, vectorized.

    Returns (iv, skip_reason) where iv is NaN and skip_reason is set for any
    row that couldn't be solved:
      - 'no_time_value'  : market_price is at/below intrinsic value -- no
                            time value left to imply a vol from.
      - 'solver_failed'   : neither Newton-Raphson nor the Brent fallback
                            converged within bounds (e.g. stale/bad price).

    Newton-Raphson runs vectorized across all rows at once (fast path).
    Any rows still outside tolerance after _NEWTON_MAX_ITER iterations fall
    back to a per-row scipy.optimize.brentq bisection (slow path, but only
    for the small subset that didn't converge).
    """
    S, K, T, r, q, market_price = (
        np.asarray(a, dtype=float) for a in (S, K, T, r, q, market_price)
    )
    n = S.shape[0]
    skip_reason = np.full(n, None, dtype=object)

    intrinsic = intrinsic_value(S, K, option_type)
    time_value = market_price - intrinsic
    no_time_value = time_value < _MIN_TIME_VALUE
    skip_reason[no_time_value] = "no_time_value"

    sigma = np.full(n, _IV_INITIAL_GUESS, dtype=float)
    active = ~no_time_value  # rows we still need to solve

    for _ in range(_NEWTON_MAX_ITER):
        if not active.any():
            break
        price = bs_price(S, K, T, r, q, sigma, option_type)
        vega = bs_vega(S, K, T, r, q, sigma)
        diff = price - market_price

        converged = np.abs(diff) < _NEWTON_TOL
        active &= ~converged

        # Guard against near-zero vega (deep ITM/OTM) blowing up the step.
        safe_vega = np.where(np.abs(vega) < 1e-8, 1e-8, vega)
        step = diff / safe_vega
        sigma = np.where(active, np.clip(sigma - step, _IV_LOWER_BOUND, _IV_UPPER_BOUND), sigma)

    # Brent fallback for whatever Newton didn't converge on (excluding
    # already-skipped no-time-value rows).
    still_active = active & ~no_time_value
    for i in np.nonzero(still_active)[0]:
        try:
            sigma[i] = brentq(
                lambda vol: bs_price(S[i], K[i], T[i], r[i], q[i], vol, option_type[i:i + 1])[0]
                - market_price[i],
                _IV_LOWER_BOUND,
                _IV_UPPER_BOUND,
                xtol=1e-6,
                maxiter=100,
            )
        except ValueError:
            # No sign change in [_IV_LOWER_BOUND, _IV_UPPER_BOUND] -- price is
            # outside what any vol in range can produce (bad/stale tick).
            sigma[i] = np.nan
            skip_reason[i] = "solver_failed"

    iv = np.where(no_time_value, np.nan, sigma)
    iv = np.where(np.isnan(iv), np.nan, iv)
    return iv, skip_reason


def compute_greeks(S, K, T, r, q, sigma, option_type) -> dict[str, np.ndarray]:
    """Delta, Gamma, Theta, Vega, Rho given an already-known/solved sigma."""
    S, K, T, r, q, sigma = (np.asarray(a, dtype=float) for a in (S, K, T, r, q, sigma))
    d1, d2 = _d1_d2(S, K, T, r, q, sigma)
    is_call = _is_call(option_type)
    sqrt_t = np.sqrt(T)

    disc_q = np.exp(-q * T)
    disc_r = np.exp(-r * T)
    pdf_d1 = _norm_pdf(d1)

    delta = np.where(is_call, disc_q * _norm_cdf(d1), -disc_q * _norm_cdf(-d1))
    gamma = disc_q * pdf_d1 / (S * sigma * sqrt_t)
    vega = S * disc_q * pdf_d1 * sqrt_t  # per 1.0 vol; divide by 100 for "per 1% vol"

    theta_common = -S * disc_q * pdf_d1 * sigma / (2.0 * sqrt_t)
    theta_call = theta_common - r * K * disc_r * _norm_cdf(d2) + q * S * disc_q * _norm_cdf(d1)
    theta_put = theta_common + r * K * disc_r * _norm_cdf(-d2) - q * S * disc_q * _norm_cdf(-d1)
    theta = np.where(is_call, theta_call, theta_put)  # per year; divide by 365 for "per day"

    rho_call = K * T * disc_r * _norm_cdf(d2)
    rho_put = -K * T * disc_r * _norm_cdf(-d2)
    rho = np.where(is_call, rho_call, rho_put)  # per 1.0 (100%) change in r

    return {"delta": delta, "gamma": gamma, "theta": theta, "vega": vega, "rho": rho}
