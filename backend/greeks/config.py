"""
Static risk-free rate and dividend-yield assumptions for the Greeks pipeline.

Both are exposed as get_*(date) functions rather than bare constants so that
upgrading to a real date-varying source later (a risk_free_rates table keyed
off RBI T-bill data, a trailing NIFTY dividend-yield series, etc.) is a
non-breaking change -- nothing in black_scholes.py or pipeline.py needs to
change, only these two function bodies.
"""
from datetime import date

# NIFTY's trailing dividend yield typically runs ~1.1-1.5%. Revisit periodically;
# this does not need to be exact to the day, just in the right neighborhood.
DEFAULT_DIVIDEND_YIELD = 0.013

# Rough short-term INR risk-free rate (91-day T-bill neighborhood). Revisit
# periodically.
DEFAULT_RISK_FREE_RATE = 0.065


def get_risk_free_rate(as_of: date) -> float:  # noqa: ARG001 - as_of reserved for future lookup
    """Annualized risk-free rate to use for a calculation as of `as_of`.

    Currently a static constant. Swap this for a `risk_free_rates(date, rate)`
    table lookup if/when you want it to actually vary by date.
    """
    return DEFAULT_RISK_FREE_RATE


def get_dividend_yield(as_of: date) -> float:  # noqa: ARG001 - as_of reserved for future lookup
    """Annualized continuous dividend yield for NIFTY as of `as_of`.

    Currently a static constant. Swap this for a real trailing-yield series
    if/when you want date-varying precision.
    """
    return DEFAULT_DIVIDEND_YIELD
