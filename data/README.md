# Data contract

Raw data must not be committed to this repository.

## Required sources

| Dataset | Minimum fields | Purpose |
|---|---|---|
| BTC venue A | UTC timestamp, OHLCV, instrument | Primary BTC state features |
| BTC venue B | UTC timestamp, OHLCV, instrument | Venue-robustness check |
| NQ/MNQ contracts | source timestamp, OHLCV, contract ID | Outcome, roll handling, and execution study |
| Exchange calendar | session, holiday, early-close metadata | Eligibility and session controls |

Primary eligibility follows the XNYS `09:30–16:00 America/New_York` cash calendar, including official holidays and early closes. Overnight negative-control eligibility additionally requires the CME equity-futures calendar and maintenance schedule. Calendar versions must be recorded with generated datasets.

Bid/ask or quote data is preferred for the eventual execution study. Bar-only slippage assumptions must be reported as modeled costs rather than observed execution.

## Existing local inventory

The following data is known to exist locally but is not copied here:

- Binance BTCUSDT spot, one minute, approximately 2024-03-07 through 2026-03-07;
- Binance BTCUSDT USDT-M futures, one minute, approximately 2024-03-07 through 2026-05-12;
- stitched NQ one-minute bars with contract identifiers, approximately 2024-03-07 through 2026-03-06;
- a previously used NQ extension through 2026-05-12 that must be located or reacquired.

This coverage can support engineering and post-ETP exploration. It cannot identify a pre/post January 2024 change.

## Planned local layout

```text
data/
  raw/          ignored; immutable source files
  registry/     committed metadata and hashes, no proprietary rows
  interim/      ignored; reproducible transformations
  processed/    ignored unless a synthetic/public artifact is approved
  fixtures/     committed synthetic test data
```

Every registered source must record provider, instrument, venue, timezone, interval, start/end, row count, file size, SHA-256, acquisition timestamp, and redistribution status.

## Warm-up requirement

The research sample requires at least 63 prior eligible analysis sessions at every required session slot. Source files must therefore begin at least one trading quarter before the first reported observation. Warm-up rows are used only for causal feature construction and are not scored as research outcomes.
