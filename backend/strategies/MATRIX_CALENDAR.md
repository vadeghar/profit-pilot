# Matrix Calendar

Strategy 8 is implemented as a backtest-only NIFTY strategy.

## Entry

- Monday at 15:16.
- The immediate weekly expiry is excluded; the following weekly expiry is selected.
- The next monthly expiry after that weekly expiry is selected.
- The weekly option chain must have valid candle data no older than 10 minutes.
- Only 100-point strikes are considered.
- CE and PE shorts are selected independently by the closest absolute delta to 0.23.
- Each selected option must have derived IV at or above 20%.

## Legs

For the selected weekly expiry:

- Sell 2 CE.
- Sell 2 PE.
- Buy 1 CE 500 points above the short call.
- Buy 1 PE 500 points below the short put.

For the selected monthly expiry:

- Buy 1 CE at the weekly short-call strike.
- Buy 1 PE at the weekly short-put strike.

## Exits

- Target: +1.5% of configured deployed margin.
- Stop-loss: -2% of configured deployed margin.
- Time exit: two calendar days after entry.
- If target and stop-loss are not reached, the time exit closes the position before the engine's expiry fallback.

## Derived Greeks

The database does not store historical IV or delta. At entry:

1. Use the latest option candle close at or before 15:16.
2. Use the NIFTY index close at or before 15:16.
3. Solve implied volatility with Black-Scholes-Merton.
4. Calculate delta from the solved IV.

Current defaults:

- Risk-free rate: 6%.
- Dividend yield: 1.2%.
- Capital base: ₹100,000 per configured unit.

These defaults are model assumptions, not values supplied by the original strategy document. They should be overridden for production-quality research.

## Known limitations

- Candle closes are used instead of bid/ask mid-prices.
- Brokerage, taxes, and slippage are not yet modeled.
- Event filtering is not yet implemented.
- The monthly hedge is marked only until the weekly expiry because the strategy exits within two days.
- The SQL migration must be reviewed against the live database before application.
