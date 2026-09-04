# Market Data Database Model

## 1. Purpose

This database supports the NIFTY market-data ingestion, data-quality auditing, repair, and backtesting workflow.

The model separates:

1. **Instrument master data** — what securities/contracts exist.
2. **Market candles** — 1-minute OHLC/volume/open-interest observations.
3. **Ingestion state** — whether an instrument/day/interval has been successfully processed.
4. **Exchange metadata** — exchange identification.
5. **Trading-calendar metadata** — NSE holidays and NIFTY expiry dates.

The primary backtesting focus is NIFTY options, while the database also supports NIFTY Index, NIFTY 50 equities, and India VIX.

---

## 2. Entity Overview

| Table | Purpose | Main Role |
|---|---|---|
| `exchanges` | Exchange master | Identifies exchange records |
| `instruments` | Instrument/security master | Defines NIFTY, options, equities, VIX, etc. |
| `candles_1min` | 1-minute market data | Stores OHLC, volume and open interest |
| `ingestion_progress` | Ingestion/recovery state | Tracks instrument/day/interval completion |
| `nse_holidays` | NSE trading holiday calendar | Determines non-trading days |
| `nifty_expiry_calendar` | NIFTY expiry calendar | Defines scheduled and actual expiry dates |

---

# 3. `exchanges`

## Purpose

`exchanges` is the exchange master/reference table.

It provides a stable database identifier for the exchange associated with an instrument.

### Columns

| Column | Description |
|---|---|
| `id` | Primary exchange identifier |
| `code` | Exchange code |

### Logical relationship

```text
exchanges
    |
    | 1:N
    v
instruments
```

One exchange can have many instruments.

---

# 4. `instruments`

## Purpose

`instruments` is the **central instrument master**.

It defines every instrument/contract for which market data can be stored.

The database contains instruments representing:

- NIFTY Index
- NIFTY 50 equities
- NIFTY Call Options (`CE`)
- NIFTY Put Options (`PE`)
- India VIX
- Multiple expiries
- Multiple strikes
- Expired and active/future option contracts

### Columns

| Column | Description |
|---|---|
| `id` | Internal unique instrument identifier |
| `exchange_id` | Logical reference to `exchanges.id` |
| `instrument_token` | Provider/exchange token, particularly used by Angel/SmartAPI |
| `trading_symbol` | Exchange/provider trading symbol |
| `name` | Human-readable instrument name |
| `instrument_type` | Instrument category/type |
| `underlying_symbol` | Underlying symbol, e.g. `NIFTY` |
| `expiry` | Derivative contract expiry date |
| `strike` | Option strike price |
| `lot_size` | Contract lot size |
| `tick_size` | Minimum price movement |
| `is_active` | Current instrument-master activity status |
| `created_at` | Instrument creation timestamp |

## NIFTY options

For an option, the important identity fields are:

```text
underlying_symbol = NIFTY
expiry            = contract expiry
strike            = strike price
instrument_type   = CE / PE
trading_symbol    = exchange/provider symbol
```

This lets the audit/backtest layer construct a daily option universe independently of the data provider.

## Expired vs active options

The instrument master contains historical/expired contracts as well as active/future contracts.

The ingestion layer therefore routes:

```text
Active / expiring-today options -> Angel / SmartAPI
Already expired options         -> Breeze
```

The `expiry` field is a key input to that decision.

## Important historical observation

Earlier instrument/data audits found multiple physical NIFTY Index instrument IDs, including exact/partial duplicate representations. Therefore the application/audit layer must not blindly assume that one logical instrument always has exactly one physical master row.

---

# 5. `candles_1min`

## Purpose

`candles_1min` is the **main market-data fact table**.

It stores 1-minute observations for instruments defined in `instruments`.

### Columns

| Column | Description |
|---|---|
| `instrument_id` | Logical reference to `instruments.id` |
| `ts` | Timestamp of the 1-minute candle |
| `open` | Opening price |
| `high` | High price |
| `low` | Low price |
| `close` | Closing price |
| `volume` | Traded volume |
| `open_interest` | Open interest, especially important for options |

### Logical relationship

```text
instruments
    |
    | 1:N
    v
candles_1min
```

One instrument has many candle records.

## Role in the project

This table contains the historical data consumed by audits and, ultimately, the backtesting engine:

- NIFTY Index OHLC
- NIFTY option OHLC
- NIFTY option open interest
- NIFTY 50 equity OHLC/volume
- India VIX

## Session expectations

The audit layer uses exchange-aware session rules.

### NIFTY Index

The established audit policy uses:

```text
09:15 - 15:29
Expected core candles: 375
```

For the post-CAS period, the NIFTY audit became CAS-aware and treats:

```text
09:15 - 15:14
```

as the required core window, with later observations handled separately.

### NIFTY Options

Equity derivatives trade until 15:40:

```text
09:15 - 15:39
Expected candles: 385
```

### NIFTY 50 equities

The current core audit window is:

```text
09:15 - 15:14
Expected core candles: 360
```

The later cash-market CAS/transition observations are treated separately.

### India VIX

The audit uses:

```text
09:15 - 15:29
Expected candles: 375
```

---

# 6. `ingestion_progress`

## Purpose

`ingestion_progress` tracks the **processing/completion state** of ingestion.

A candle row answers:

> Does this market-data record exist?

A progress row answers:

> Does the ingestion process consider this instrument/day/interval successfully processed?

### Columns

| Column | Description |
|---|---|
| `instrument_id` | Instrument being processed |
| `interval` | Processing interval, currently `ONE_MINUTE` or `ONE_MINUTE_OI` |
| `chunk_start` | Logical coverage day/session date |
| `completed_at` | Completion timestamp; `NULL` means pending/incomplete |

## Important semantic rule

`chunk_start` is treated as the **coverage day**, not necessarily the provider API request/chunk boundary.

This keeps progress provider-neutral even though Angel and Breeze may use different API request ranges.

## Completion semantics

```text
completed_at IS NULL
    -> PENDING / NOT COMPLETE

completed_at IS NOT NULL
    -> DONE
```

## Why it is separate from candle data

A provider request may:

- return zero rows
- return incomplete data
- partially populate the day
- succeed for OHLC but fail for OI
- fail after some database rows have already been inserted

Therefore candle existence alone should not determine ingestion completion.

## Role in daily repair

The repair process can:

1. Identify required instrument/day combinations.
2. Validate `candles_1min`.
3. Clear/reset progress for bad days.
4. Fetch missing data.
5. Upsert candles.
6. Validate the completed session.
7. Set `completed_at` only after successful validation.

This makes the pipeline rerunnable and self-healing.

---

# 7. `nse_holidays`

## Purpose

`nse_holidays` stores the NSE holiday calendar used by ingestion, auditing, expiry calculations and backtesting.

### Columns

| Column | Description |
|---|---|
| `holiday_date` | Holiday/non-trading date |
| `segment` | Calendar segment such as `ALL`, `CM`, or `FNO` |
| `holiday_name` | Holiday description |
| `source` | Calendar source |
| `created_at` | Row creation timestamp |

## Why `segment` matters

The implementation distinguishes cash-market (`CM`) and F&O calendars because they are not always identical.

For NIFTY option processing, the relevant calendar is:

```text
segment = FNO
```

For cash equities, the relevant calendar is the CM calendar.

## Usage

The table is used for:

- Trading-day calculation
- Avoiding ingestion on non-trading days
- Expected candle-session calculation
- NIFTY expiry-date shifting
- Backtest calendar logic
- Daily repair scheduling

---

# 8. `nifty_expiry_calendar`

## Purpose

`nifty_expiry_calendar` stores the NIFTY option expiry calendar.

This is particularly important for the options backtesting project because option contracts must be interpreted using the actual NIFTY expiry calendar rather than assuming every Tuesday is an expiry.

### Columns

| Column | Description |
|---|---|
| `expiry_date` | Actual NIFTY expiry/trading date |
| `scheduled_date` | Normally the scheduled Tuesday |
| `expiry_type` | `WEEKLY` or `MONTHLY` |
| `underlying` | Underlying symbol, currently `NIFTY` |
| `exchange` | Exchange/source, currently `NSE` |
| `was_holiday_shift` | Whether the scheduled expiry was shifted |
| `shifted_from_holiday` | Holiday date from which the expiry was shifted |
| `source` | Source of expiry information |
| `created_at` | Row creation timestamp |

## Expiry rule

The historical calendar generation follows:

```text
Normal NIFTY expiry:
Tuesday

If Tuesday is an F&O holiday:
previous trading day
```

The last Tuesday expiry of a month is classified as:

```text
MONTHLY
```

Other Tuesday expiries are:

```text
WEEKLY
```

## Future expiries

Future expiry dates can be obtained directly from NSE's option-chain contract-info API:

```text
https://www.nseindia.com/api/option-chain-contract-info?symbol=NIFTY
```

The response contains an `expiryDates` array.

The setup script supports:

```bash
python setup_nifty_expiry_and_nse_holidays_v3.py --insert-future-expiries
```

Future dates returned by NSE are inserted/upserted into this table.

For future dates, the NSE-published expiry list is treated as the authority instead of blindly calculating an indefinite future calendar.

## Why both dates are stored

For a holiday-shifted expiry:

```text
scheduled_date = Tuesday holiday
expiry_date    = previous trading day
```

Keeping both makes it possible to distinguish the contractual scheduled date from the actual expiry date.

---

# 9. Logical Data Relationships

The core market-data model is:

```text
                         +----------------+
                         |   exchanges    |
                         +----------------+
                                  |
                                  | 1:N
                                  v
                         +----------------+
                         |  instruments   |
                         +----------------+
                           |            |
                         1:N          1:N
                           |            |
                           v            v
                  +---------------+  +----------------------+
                  | candles_1min  |  | ingestion_progress   |
                  +---------------+  +----------------------+
```

Calendar metadata is consumed by the application/audit layer:

```text
+-------------------+       +-------------------------+
|   nse_holidays    | ----> | Trading-day calculation |
+-------------------+       +-------------------------+
                                      |
                                      v
                           +-------------------------+
                           | Ingestion / Audit /     |
                           | Repair / Backtesting    |
                           +-------------------------+
                                      ^
                                      |
+-------------------------+-----------+
| nifty_expiry_calendar   |
+-------------------------+
```

There is also a logical connection:

```text
instruments.expiry
        |
        v
nifty_expiry_calendar.expiry_date
```

This can be used to validate option contract expiry metadata.

These are **logical relationships**. The displayed schema does not establish that every relationship is implemented as a PostgreSQL foreign-key constraint.

---

# 10. How the Tables Work Together

## A. Instrument discovery

`instruments` answers:

> What instruments/contracts exist?

Example:

```text
NIFTY
NIFTY 25SEP2026 25000 CE
NIFTY 25SEP2026 25000 PE
RELIANCE
INDIA VIX
```

## B. Trading calendar

`nse_holidays` answers:

> Is this date a trading day for the relevant segment?

`nifty_expiry_calendar` answers:

> Is this date a NIFTY option expiry, and is it weekly or monthly?

## C. Market data

`candles_1min` answers:

> What happened to this instrument during each minute?

## D. Ingestion state

`ingestion_progress` answers:

> Has the required data for this instrument/day/interval been processed successfully?

## E. Data-quality audit

The audit combines:

```text
instruments
      +
candles_1min
      +
nse_holidays
      +
nifty_expiry_calendar
      +
ingestion_progress
```

to determine completeness.

---

# 11. NIFTY Options Backtesting Data Flow

The intended options backtesting flow is:

```text
                    NIFTY trading calendar
                            |
                            v
                  +-------------------+
                  | Trading Sessions  |
                  +-------------------+
                            |
                            v
NIFTY spot ----------> ATM calculation
                            |
                            v
                 Daily option universe
                            |
               +------------+------------+
               |                         |
               v                         v
        Expiry selection          Strike selection
               |                         |
               +------------+------------+
                            |
                            v
                      instruments
                            |
                            v
                     candles_1min
                            |
                            v
                    Backtest engine
```

The daily option universe is intended to be constructed using:

```text
trading date
+
NIFTY spot/ATM
+
applicable expiry
+
CE/PE
+
required strike range
```

The historical audit logic previously established uses a configurable NIFTY option strike range around ATM, including the specified **ATM ±10 strikes** universe.

---

# 12. Provider Routing

The database model is provider-neutral.

Provider selection is handled by the ingestion layer using instrument metadata and the session date.

Current intended routing:

| Data | Provider |
|---|---|
| NIFTY Index | Angel / SmartAPI |
| NIFTY 50 equities | Angel / SmartAPI |
| Active NIFTY options | Angel / SmartAPI |
| NIFTY options expiring today | Angel / SmartAPI |
| Already expired NIFTY options | Breeze |
| India VIX | Breeze |

The provider itself is not the identity of the market-data record. `instrument_id` remains the database-level identity.

---

# 13. Daily Repair Architecture

The intended daily repair cycle is:

```text
                 Daily repair job
                        |
                        v
              Determine trading days
                        |
                        v
              Determine required
              instrument universe
                        |
                        v
              Check candles_1min
                        |
             +----------+----------+
             |                     |
          Complete               Missing
             |                     |
             v                     v
        Keep state          Reset progress
                                   |
                                   v
                            Fetch provider data
                                   |
                                   v
                           Upsert candles_1min
                                   |
                                   v
                            Validate session
                                   |
                         +---------+---------+
                         |                   |
                       Good                Bad
                         |                   |
                         v                   v
              completed_at = now       Remain pending
```

The daily repair job is designed to include the current trading day when run after market close and to recheck a configurable number of recent sessions so missed/incomplete days can be repaired.

---

# 14. Important Design Principles

## 14.1 Instrument master is the source of contract identity

Option identity should use instrument metadata rather than only a trading-symbol string:

```text
instrument_id
underlying_symbol
expiry
strike
instrument_type
```

## 14.2 Candle existence is not ingestion completion

A partially populated day must not automatically be considered complete.

Use both:

```text
candles_1min
```

and:

```text
ingestion_progress
```

## 14.3 Calendar data drives expected sessions

Do not assume every weekday is a trading day.

Use `nse_holidays`, with the F&O calendar for NIFTY options.

## 14.4 Expiry dates must be exchange-aware

Do not assume:

```text
every Tuesday = expiry
```

A Tuesday holiday can move the actual expiry to the previous trading day.

For future contracts, prefer the NSE-published expiry list when available.

## 14.5 Historical and future options are different ingestion cases

The presence of an option in `instruments` does not mean that candles should exist for every historical date.

An option should only be expected during its applicable contract lifecycle.

This is important because the instrument master contains expired, active, and future/long-dated contracts.

---

# 15. Current Database Scope

The current model supports:

- 1-minute NIFTY Index data
- 1-minute NIFTY options
- Expired NIFTY options
- Active/future NIFTY options
- NIFTY 50 equity data
- India VIX data
- Option open interest
- NSE/F&O trading calendars
- NIFTY weekly/monthly expiry calendar
- Daily ingestion tracking
- Missing-data repair
- Data-quality auditing
- Future options universe construction
- Historical options backtesting

The model is centered on **reliable historical market data and reproducible backtesting**, rather than order management or live trading positions.
