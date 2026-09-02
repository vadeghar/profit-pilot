# NIFTY Titan Condor

Titan Condor is a weekly NIFTY options strategy.

## Entry

- Schedule every Friday at 15:16.
- Read the NIFTY spot close at or before the entry timestamp.
- Skip the nearest weekly expiry and select the following weekly expiry.
- Normalize strikes to 100-point increments.
- Sell the call and put about 400 points above and below spot.
- Buy 100-point protection wings.
- Buy one additional far OTM call 300 points beyond the short call to model the transcript's skew adjustment.
- Default size is 10 lots on each primary leg and 1 lot on the additional call.

## Exit

- Exit immediately if spot reaches either short strike.
- Exit at +1% of configured deployed margin.
- Otherwise exit on the following Friday at 09:45.
- If no exit condition is observed, the generic engine closes at the selected expiry.

## Lot size

The contract's lot_size is used when present. If it is missing, the fallback is 75 before 2026-01-01 and 65 from 2026-01-01 onward.

The default deployed-margin assumption is INR 30,000 per primary lot, configurable in the strategy constructor.
