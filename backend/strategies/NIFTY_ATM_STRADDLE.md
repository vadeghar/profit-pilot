# NIFTY ATM CE + PE Long Straddle Strategy — V4

**Theme:** 3 PM is my price

## Initial Entry

The strategy is evaluated only on NIFTY expiry days.

### Before 3:01 PM

The first entry occurs when:

- India VIX < 15
- ATM CE + ATM PE combined premium <= 50

ATM is determined from the NIFTY spot observed at that entry time and then locked.

ATM strike selection always uses the nearest 100-point strike. 50-point strikes
are ignored. For example, spot 24,556 selects 24,600 and spot 24,548 selects
24,500.

### 3:01 PM fallback entry

If no initial trade has occurred before 3:01 PM, then **3:01 PM is the price reference**:

1. Take the NIFTY spot available at 3:01 PM.
2. Determine the ATM strike from that spot.
3. Lock that ATM strike for the complete trade.
4. If India VIX < 15, initiate the first trade immediately.
5. The combined CE + PE premium **does not need to be <= 50** for this fallback entry.

The actual CE + PE premium at the 3:01 PM entry is recorded as the initial combined premium.

The strategy does not depend on NIFTY spot after 3:01 PM, because spot data may stop being available after approximately 3:15 PM.

If VIX is >= 15 at 3:01 PM, continue checking until a valid observation before the force-exit boundary has VIX < 15; the first such observation is used for the forced entry and its spot determines ATM. If no such observation exists, there is no entry.

## Position and Remaining Rules

All rules after the initial entry remain unchanged:

| Stage | Combined Premium | Action | Target | Target Exit | Cost Exit |
|---|---:|---|---:|---|---:|
| Initial | <= 50 normally; any value at 3:01 fallback | Buy 2 CE + 2 PE | 100 | Sell 1 CE + 1 PE | 50 |
| 2A | <= 30 | Buy 2 CE + 2 PE | 65 | Sell 2 CE + 2 PE | 30 |
| 2B | <= 20 | Buy 2 CE + 2 PE | 45 | Sell 3 CE + 3 PE | 20 |

Hard stop at combined premium <= 8 exits all remaining positions.

All positions are force-closed at 3:35 PM.

Maximum position is 6 CE lots + 6 PE lots.

The ATM strike is selected once at initial entry and remains locked.

## Example

If at 3:01 PM:

```text
NIFTY spot = 25,183
ATM = 25,200
VIX = 13.7
25,200 CE = 34
25,200 PE = 29
Combined = 63
```

The normal <=50 condition has not been met, but the 3:01 PM fallback applies:

```text
BUY 2 x 25,200 CE
BUY 2 x 25,200 PE
```

Initial combined premium is recorded as 63. Subsequent 2A/2B, target, cost, hard-stop and 3:35 PM rules are unchanged.

## Deployment

Live deployment remains restricted to NIFTY expiry days. Backtest and deployment use the same state-machine strategy logic.
