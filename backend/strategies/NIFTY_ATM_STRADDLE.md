# NIFTY ATM CE + PE Long Straddle Strategy

**Strategy ID:** `NK_CAS_NIFTY_ATM_STRADDLE_2PM_V1`  
**Strategy Type:** Long ATM Straddle with controlled averaging  
**Underlying:** NIFTY 50  
**Applicable From:** 03-Aug-2026  
**Modes:** Backtest and Deploy in live market
**Deployment Restriction:** Live deployment is permitted **only on NIFTY expiry day**.

---

## 1. Strategy Objective

The strategy buys an ATM NIFTY Call Option (CE) and an ATM NIFTY Put Option (PE) after 2:00 PM when the combined premium is sufficiently low and India VIX is below 15.

If the combined premium falls further, the strategy averages once at 30 and once at 20.

When the combined premium subsequently recovers to the applicable target, 50% of the current position is exited.

The remaining 50% is protected using a **combined-premium cost level**.

A hard stop is always maintained at a combined CE + PE premium of 8.

All open positions are force-closed at 3:35 PM.

---

# 2. Important Definitions

## 2.1 Combined Premium

All strategy decisions are based on:

```text
Combined Premium = ATM CE Price + ATM PE Price
```

Example:

```text
CE = 28
PE = 21

Combined Premium = 28 + 21 = 49
```

The strategy does **not** make entry/target/cost decisions independently on CE and PE.

---

## 2.2 ATM Strike

ATM is determined **only at the initial entry** using the NIFTY spot/index price.

Once the ATM strike is selected, it is locked for the entire trade.

Example:

```text
NIFTY Spot at initial entry = 25,018

ATM Strike = 25,000

Trade:
    Buy 25,000 CE
    Buy 25,000 PE
```

If NIFTY subsequently moves to 25,150 or 24,900, the strategy continues using:

```text
25,000 CE
25,000 PE
```

It must **not** shift to a new ATM strike.

---

## 2.3 Lot Size

The lot size must be obtained from the applicable NIFTY option instrument/master data for the trading date.

Do not hard-code the lot size.

The strategy quantities are expressed in **lots**.

---

# 3. Applicability

The strategy must not be run before 03-Aug-2026.

```pseudo
if trading_date < 2026-08-03:
    strategy_status = NOT_APPLICABLE
```

For dates on or after 03-Aug-2026, the strategy may be evaluated for backtesting.

---

# 4. Backtest Mode

## 4.1 Purpose

Backtest mode is used to evaluate the strategy against historical NIFTY spot, India VIX, and option data.

Backtest mode may evaluate **all eligible trading days from 03-Aug-2026 onward**.

It is **not restricted to expiry days**.

Example:

```text
Trading Date: 10-Aug-2026
NIFTY expiry day: No

Backtest:
    ALLOWED
```

The backtest should determine what the strategy would have done on that historical day.

---

# 5. Deploy Mode

Live deployment has an additional restriction.

```pseudo
if mode == DEPLOY:
    if trading_date is NOT NIFTY expiry day:
        DO NOT START STRATEGY
```

Therefore:

```text
BACKTEST:
    Any eligible trading day >= 03-Aug-2026

DEPLOY:
    NIFTY expiry day only
```

The application should obtain expiry information from the option instrument/master data or exchange calendar.

Do not infer expiry day from a hard-coded weekday.

---

# 6. Fixed Strategy Parameters

| Parameter | Value |
|---|---:|
| Strategy start date | 03-Aug-2026 |
| Initial entry time | 2:00 PM |
| Force exit | 3:35 PM |
| India VIX condition | `< 15` |
| Initial combined premium | `<= 50` |
| 2A combined premium | `<= 30` |
| 2B combined premium | `<= 20` |
| Initial target | `>= 100` |
| 2A target | `>= 65` |
| 2B target | `>= 45` |
| Hard SL | `<= 8` |
| Initial CE lots | 2 |
| Initial PE lots | 2 |
| 2A additional CE lots | 2 |
| 2A additional PE lots | 2 |
| 2B additional CE lots | 2 |
| 2B additional PE lots | 2 |
| Maximum CE position | 6 lots |
| Maximum PE position | 6 lots |
| Maximum total lots | 12 |

---

# 7. Initial Entry

Initial entry can occur only when all conditions are satisfied.

```pseudo
current_time >= 14:00
AND India_VIX < 15
AND no_position_exists
AND combined_premium <= 50
```

At the first valid entry:

1. Determine ATM strike using NIFTY spot.
2. Lock the ATM strike.
3. Buy 2 CE lots.
4. Buy 2 PE lots.
5. Set strategy state to `INITIAL`.

```pseudo
BUY 2 CE lots
BUY 2 PE lots

state = INITIAL
level_2a_done = false
level_2b_done = false
target_done = false
cost_premium = 50
```

---

# 8. 2A Averaging Entry

2A is executed only once.

Condition:

```text
Combined Premium <= 30
```

and:

```text
2A has not already been executed
```

Action:

```text
Buy 2 additional CE lots
Buy 2 additional PE lots
```

Position becomes:

```text
CE = 4 lots
PE = 4 lots
```

Set:

```pseudo
level_2a_done = true
state = AFTER_2A
```

The locked ATM strike remains unchanged.

---

# 9. 2B Averaging Entry

2B is executed only once.

Condition:

```text
Combined Premium <= 20
```

and:

```text
2A has already occurred
2B has not already occurred
```

Action:

```text
Buy 2 additional CE lots
Buy 2 additional PE lots
```

Position becomes:

```text
CE = 6 lots
PE = 6 lots
```

Set:

```pseudo
level_2b_done = true
state = AFTER_2B
```

---

# 10. Target Rules

## 10.1 Initial Position — Target 100

If 2A has not occurred:

```text
Position = 2 CE + 2 PE
```

Target:

```text
Combined Premium >= 100
```

Action:

```text
Sell 1 CE lot
Sell 1 PE lot
```

Remaining:

```text
1 CE + 1 PE
```

The remaining position is now protected at:

```text
Cost Premium = 50
```

---

## 10.2 After 2A — Target 65

If 2A occurred and 2B did not occur:

```text
Position = 4 CE + 4 PE
```

Target:

```text
Combined Premium >= 65
```

Action:

```text
Sell 2 CE lots
Sell 2 PE lots
```

Remaining:

```text
2 CE + 2 PE
```

The remaining position is protected at:

```text
Cost Premium = 30
```

---

## 10.3 After 2B — Target 45

If 2B occurred:

```text
Position = 6 CE + 6 PE
```

Target:

```text
Combined Premium >= 45
```

Action:

```text
Sell 3 CE lots
Sell 3 PE lots
```

Remaining:

```text
3 CE + 3 PE
```

The remaining position is protected at:

```text
Cost Premium = 20
```

---

# 11. Cost Exit

## Critical Rule

The cost exit is based on the **combined CE + PE premium**.

It is **not** based on:

- individual CE average price
- individual PE average price
- weighted average CE/PE price
- combined weighted average execution price

The relevant cost is the **combined premium of the latest averaging/entry level**.

---

## 11.1 Initial Entry Example

Initial entry:

```text
CE + PE = 50
```

Position:

```text
2 CE + 2 PE
```

Target:

```text
CE + PE >= 100
```

At 100:

```text
Exit 1 CE + 1 PE
```

Remaining:

```text
1 CE + 1 PE
```

Cost level:

```text
50
```

If later:

```text
CE + PE <= 50
```

then:

```text
Exit remaining 1 CE + 1 PE
```

Trade is closed.

---

## 11.2 2A Example

Initial entry:

```text
CE + PE = 50
Buy 2 CE + 2 PE
```

Premium falls to:

```text
CE + PE = 30
```

2A:

```text
Buy 2 additional CE + 2 additional PE
```

Position:

```text
4 CE + 4 PE
```

Premium recovers to:

```text
CE + PE = 65
```

Target:

```text
Exit 2 CE + 2 PE
```

Remaining:

```text
2 CE + 2 PE
```

Cost level becomes:

```text
30
```

If premium later falls back to:

```text
CE + PE <= 30
```

then:

```text
Exit remaining 2 CE + 2 PE
```

Trade is closed.

---

## 11.3 2B Example

Initial entry:

```text
CE + PE = 50
Buy 2 CE + 2 PE
```

2A:

```text
CE + PE = 30
Buy 2 CE + 2 PE
```

2B:

```text
CE + PE = 20
Buy 2 CE + 2 PE
```

Position:

```text
6 CE + 6 PE
```

Premium recovers to:

```text
CE + PE = 45
```

Target:

```text
Exit 3 CE + 3 PE
```

Remaining:

```text
3 CE + 3 PE
```

Cost level:

```text
20
```

If premium later falls back to:

```text
CE + PE <= 20
```

then:

```text
Exit remaining 3 CE + 3 PE
```

Trade is closed.

---

# 12. Hard Stop Loss

The hard stop applies at every stage of the trade.

```text
Combined Premium <= 8
```

Action:

```text
Exit ALL remaining CE
Exit ALL remaining PE
Close trade
```

The hard stop is independent of the current entry stage and target status.

```pseudo
if combined_premium <= 8:
    sell_all_remaining_ce()
    sell_all_remaining_pe()
    close_trade(HARD_STOP_LOSS)
```

---

# 13. Force Exit

No position may remain open after 3:35 PM.

```pseudo
if current_time >= 15:35:
    sell_all_remaining_ce()
    sell_all_remaining_pe()
    close_trade(TIME_EXIT)
```

This applies whether the position is:

```text
2 + 2
4 + 4
6 + 6
1 + 1
2 + 2 after target
3 + 3 after target
```

---

# 14. Rule Priority

For every market observation:

```text
1. Check trading date
2. Check deployment eligibility
3. Check whether trade is already closed
4. Check 3:35 PM force exit
5. Calculate current CE + PE combined premium
6. Check hard SL <= 8
7. Check cost exit, if target was already achieved
8. Check applicable target
9. Check 2A entry
10. Check 2B entry
```

### Note

For 1-minute OHLC backtesting, a single candle can cross multiple strategy levels.

Example:

```text
Previous combined premium = 66

Current 1-minute candle:
    High = 101
    Low  = 29
```

This candle has crossed:

```text
Target 100
2A level 30
```

OHLC data alone does not tell us which occurred first.

Therefore the backtester must have a clearly defined **intrabar execution policy**. The strategy should not silently assume an execution order.

---

# 15. State Model

Recommended states:

```text
WAITING_FOR_ENTRY
INITIAL
AFTER_2A
AFTER_2B
TARGETED_INITIAL
TARGETED_2A
TARGETED_2B
CLOSED
```

Recommended runtime variables:

```text
strategy_state
locked_atm_strike

level_2a_done
level_2b_done
target_done

ce_lots
pe_lots

cost_premium

entry_timestamp
target_timestamp
exit_timestamp

exit_reason
```

---

# 16. Strategy State Table

| State | Position | Target | Target Exit | Cost After Target |
|---|---:|---:|---:|---:|
| Initial | 2 CE + 2 PE | 100 | 1 CE + 1 PE | 50 |
| After 2A | 4 CE + 4 PE | 65 | 2 CE + 2 PE | 30 |
| After 2B | 6 CE + 6 PE | 45 | 3 CE + 3 PE | 20 |

At any state:

```text
Combined Premium <= 8
    -> Exit everything
```

At or after:

```text
15:35
    -> Exit everything
```

---

# 17. Complete Strategy Pseudocode

```pseudo
function run_strategy(trading_date, mode):

    if trading_date < 2026-08-03:
        return NOT_APPLICABLE


    # Deployment restriction
    if mode == DEPLOY:

        if not is_nifty_expiry_day(trading_date):
            return NOT_DEPLOYED_NON_EXPIRY_DAY


    state = WAITING_FOR_ENTRY

    level_2a_done = false
    level_2b_done = false
    target_done = false

    locked_atm_strike = null

    ce_lots = 0
    pe_lots = 0

    cost_premium = null


    for each market observation in chronological order:

        # -----------------------------------------
        # FORCE EXIT
        # -----------------------------------------

        if current_time >= 15:35:

            exit_all_positions()

            return TIME_EXIT


        # -----------------------------------------
        # INITIAL ENTRY
        # -----------------------------------------

        if state == WAITING_FOR_ENTRY:

            if current_time < 14:00:
                continue

            vix = get_india_vix()

            if vix >= 15:
                continue

            nifty_spot = get_nifty_spot()

            locked_atm_strike =
                determine_atm_strike(nifty_spot)

            ce_price =
                get_option_price(locked_atm_strike, CE)

            pe_price =
                get_option_price(locked_atm_strike, PE)

            combined =
                ce_price + pe_price

            if combined <= 50:

                buy_ce(2)
                buy_pe(2)

                ce_lots = 2
                pe_lots = 2

                cost_premium = 50

                state = INITIAL

                continue


        # -----------------------------------------
        # CURRENT COMBINED PREMIUM
        # -----------------------------------------

        ce_price =
            get_option_price(locked_atm_strike, CE)

        pe_price =
            get_option_price(locked_atm_strike, PE)

        combined =
            ce_price + pe_price


        # -----------------------------------------
        # HARD STOP
        # -----------------------------------------

        if combined <= 8:

            exit_all_positions()

            return HARD_STOP_LOSS


        # -----------------------------------------
        # COST EXIT
        # -----------------------------------------

        if target_done:

            if combined <= cost_premium:

                exit_all_positions()

                return COST_EXIT


        # -----------------------------------------
        # INITIAL TARGET
        # -----------------------------------------

        if state == INITIAL:

            if combined >= 100:

                sell_ce(1)
                sell_pe(1)

                ce_lots = 1
                pe_lots = 1

                target_done = true
                cost_premium = 50

                state = TARGETED_INITIAL

                continue


        # -----------------------------------------
        # 2A ENTRY
        # -----------------------------------------

        if state == INITIAL:

            if not level_2a_done:

                if combined <= 30:

                    buy_ce(2)
                    buy_pe(2)

                    ce_lots = 4
                    pe_lots = 4

                    level_2a_done = true

                    state = AFTER_2A
                    cost_premium = 30

                    continue


        # -----------------------------------------
        # 2A TARGET
        # -----------------------------------------

        if state == AFTER_2A:

            if combined >= 65:

                sell_ce(2)
                sell_pe(2)

                ce_lots = 2
                pe_lots = 2

                target_done = true
                cost_premium = 30

                state = TARGETED_2A

                continue


        # -----------------------------------------
        # 2B ENTRY
        # -----------------------------------------

        if state == AFTER_2A:

            if not level_2b_done:

                if combined <= 20:

                    buy_ce(2)
                    buy_pe(2)

                    ce_lots = 6
                    pe_lots = 6

                    level_2b_done = true

                    state = AFTER_2B
                    cost_premium = 20

                    continue


        # -----------------------------------------
        # 2B TARGET
        # -----------------------------------------

        if state == AFTER_2B:

            if combined >= 45:

                sell_ce(3)
                sell_pe(3)

                ce_lots = 3
                pe_lots = 3

                target_done = true
                cost_premium = 20

                state = TARGETED_2B

                continue


    return END_OF_DATA
```

---

# 18. Example 1 — Initial Entry and Target

Assume:

```text
Date       = 10-Aug-2026
Time       = 14:05
VIX        = 13.8
NIFTY      = 25,018
ATM        = 25,000
```

Premiums:

```text
25,000 CE = 28
25,000 PE = 21

Combined = 49
```

Condition:

```text
VIX < 15
Combined <= 50
```

Entry:

```text
BUY 2 CE
BUY 2 PE
```

Later:

```text
CE + PE = 101
```

Target reached.

Exit:

```text
SELL 1 CE
SELL 1 PE
```

Remaining:

```text
1 CE + 1 PE
```

Cost protection:

```text
Combined <= 50 -> EXIT
```

If the combined premium instead continues rising, the remaining position stays open until:

```text
3:35 PM
```

---

# 19. Example 2 — 2A Averaging

Initial:

```text
CE + PE = 49

BUY 2 CE + 2 PE
```

Premium falls:

```text
CE + PE = 30
```

2A:

```text
BUY 2 CE + 2 PE
```

Total:

```text
4 CE + 4 PE
```

Premium recovers:

```text
CE + PE = 66
```

Target:

```text
>= 65
```

Exit:

```text
SELL 2 CE + 2 PE
```

Remaining:

```text
2 CE + 2 PE
```

Cost:

```text
30
```

If:

```text
CE + PE <= 30
```

exit remaining position.

---

# 20. Example 3 — Full Averaging / 2B

Initial:

```text
CE + PE = 50

BUY 2 CE + 2 PE
```

2A:

```text
CE + PE = 30

BUY 2 CE + 2 PE
```

2B:

```text
CE + PE = 20

BUY 2 CE + 2 PE
```

Maximum position:

```text
6 CE + 6 PE
```

Recovery:

```text
CE + PE = 45
```

Target reached.

Exit:

```text
SELL 3 CE + 3 PE
```

Remaining:

```text
3 CE + 3 PE
```

Cost:

```text
20
```

If:

```text
CE + PE <= 20
```

exit remaining 3 + 3 lots.

---

# 21. Example 4 — Hard Stop

Suppose:

```text
Initial:
CE + PE = 49

BUY 2 + 2
```

Premium falls:

```text
30
```

2A:

```text
BUY 2 + 2
```

Premium falls:

```text
20
```

2B:

```text
BUY 2 + 2
```

Now:

```text
6 CE + 6 PE
```

If premium continues falling:

```text
CE + PE = 8
```

Hard stop is triggered.

Action:

```text
EXIT ALL 6 CE + 6 PE
```

No target/cost logic is applied after the hard stop.

---

# 22. Example 5 — Deployment Restriction

### Non-expiry day

```text
Mode = DEPLOY
Date = eligible trading date
NIFTY expiry day = NO
```

Result:

```text
DO NOT DEPLOY
DO NOT ENTER
```

### Expiry day

```text
Mode = DEPLOY
Date = eligible trading date
NIFTY expiry day = YES
```

Result:

```text
Strategy may run
```

Normal entry conditions still apply:

```text
Time >= 2:00 PM
VIX < 15
CE + PE <= 50
```

Being an expiry day **does not bypass any strategy condition**.

---

# 23. Trade Record Requirements

Every backtest/live trade should record at minimum:

```text
strategy_id
mode
trading_date

expiry_date
is_expiry_day

initial_entry_timestamp
initial_entry_spot
atm_strike

initial_ce_price
initial_pe_price
initial_combined_premium

vix_at_entry

level_2a_timestamp
level_2a_ce_price
level_2a_pe_price
level_2a_combined_premium

level_2b_timestamp
level_2b_ce_price
level_2b_pe_price
level_2b_combined_premium

target_timestamp
target_level
target_combined_premium

cost_premium

hard_sl_timestamp
hard_sl_premium

final_exit_timestamp
final_exit_reason

ce_lots_bought
pe_lots_bought

ce_lots_sold
pe_lots_sold

realized_pnl
charges
net_pnl
```

Fields for stages that did not occur should be `NULL`.

---

# 24. Final Strategy Summary

```text
START DATE:
    03-Aug-2026

BACKTEST:
    All eligible trading days from start date

DEPLOY:
    NIFTY expiry day ONLY

ENTRY:
    >= 2:00 PM
    India VIX < 15
    ATM CE + ATM PE <= 50

INITIAL:
    Buy 2 CE + 2 PE

2A:
    If CE + PE <= 30
    Buy additional 2 CE + 2 PE
    Execute only once

2B:
    If CE + PE <= 20
    Buy additional 2 CE + 2 PE
    Execute only once

TARGET:
    Initial position -> 100
    After 2A        -> 65
    After 2B        -> 45

TARGET EXIT:
    Initial -> 1 CE + 1 PE
    2A      -> 2 CE + 2 PE
    2B      -> 3 CE + 3 PE

COST EXIT:
    Initial -> combined premium <= 50
    2A      -> combined premium <= 30
    2B      -> combined premium <= 20

HARD SL:
    combined premium <= 8
    Exit everything

FORCE EXIT:
    3:35 PM
    Exit everything

ATM:
    Determine once at initial entry
    Lock for entire trade

MAX POSITION:
    6 CE + 6 PE

ALL DECISIONS:
    Based on combined CE + PE premium
```

---

## 25. Implementation Principle

The strategy should be implemented as a **single deterministic state machine** so that the exact same strategy logic is used by:

```text
Historical Backtester
        |
        +----> Strategy Engine
        |
        +----> Live Deployment Engine
```

The only major difference is the eligibility gate:

```text
BACKTEST
    -> Evaluate eligible historical trading days

DEPLOY
    -> First verify NIFTY expiry day
    -> Then run exactly the same strategy engine
```

This avoids having separate strategy logic for backtesting and live trading, reducing the risk of **backtest/live behavior mismatch**.
