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
- stitched NQ one-minute bars with contract identifiers, approximately 2024-03-07 through 2026-05-12.

This coverage can support engineering and post-ETP exploration. It cannot identify a pre/post January 2024 change.

The exact known files, identities, schemas, provenance status, and eligibility limits are recorded in [`configs/data_registry.yaml`](../configs/data_registry.yaml). The raw NQ extension was located, but the base portion of the stitched history still has only partial provenance and an incompletely documented front-month roll rule. Calendar-aware auditing also found 83 incomplete XNYS sessions and 16,200 missing cash-session minutes. It is therefore engineering data only, not a valid input to the empirical study.

## Reproduce the structural audit

Pass local paths explicitly; absolute paths are never committed:

```powershell
python -m btc_nq_coherence.data_audit `
  --registry configs/data_registry.yaml `
  --path "btc_binance_um_futures_1m=C:\path\to\BTCUSDT.csv" `
  --path "nq_ibkr_stitched_front_month_1m=C:\path\to\NQ.csv" `
  --output data/registry/local_inventory_audit.json
```

The streaming audit checks file identity, timestamp ordering, duplicates, cadence breaks, finite OHLCV values, OHLC invariants, non-negative volume, NQ tick conformity, contract identifiers, and contract transitions. It then separates legitimate exchange closures from missing primary-session bars using a version-recorded XNYS-compatible market calendar.

## Build the constrained development dataset

```powershell
python -m btc_nq_coherence.canonicalize `
  --registry configs/data_registry.yaml `
  --study configs/available_data_study.yaml `
  --nq-path "C:\path\to\NQ.csv" `
  --btc-path "C:\path\to\BTCUSDT.csv" `
  --output data/interim/synchronized_development_1m.csv `
  --manifest data/registry/available_data_eligibility.json
```

The generated local CSV retains synchronized common minutes and adds explicit eligibility flags. It never fills a missing market price. The committed manifest contains every excluded session and the exact output hash without publishing proprietary rows.

## Build causal feature artifacts

```powershell
python -m btc_nq_coherence.features `
  --canonical data/interim/synchronized_development_1m.csv `
  --eligibility-manifest data/registry/available_data_eligibility.json `
  --config configs/features.yaml `
  --one-minute-output data/interim/features_primary_1m.csv `
  --five-minute-output data/interim/features_primary_5m.csv `
  --manifest data/registry/feature_manifest.json
```

The one- and five-minute output files are local, ignored artifacts. The committed manifest is sufficient to verify their identities and the exact causal definitions used to create them.

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
