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

## Build causal outcomes

```powershell
python -m btc_nq_coherence.outcomes `
  --one-minute-features data/interim/features_primary_1m.csv `
  --five-minute-features data/interim/features_primary_5m.csv `
  --feature-manifest data/registry/feature_manifest.json `
  --config configs/outcomes.yaml `
  --one-minute-output data/interim/outcomes_primary_1m.csv `
  --five-minute-output data/interim/outcomes_primary_5m.csv `
  --manifest data/registry/outcome_manifest.json
```

Outcome rows remain local and ignored. Open-to-open returns start at the first tradable
open after feature availability and never cross an analysis-session boundary. Missing
bars and session ends right-censor state duration rather than being labeled as decay.

## Build descriptive response surfaces

```powershell
python -m btc_nq_coherence.descriptive `
  --one-minute-outcomes data/interim/outcomes_primary_1m.csv `
  --five-minute-outcomes data/interim/outcomes_primary_5m.csv `
  --outcome-manifest data/registry/outcome_manifest.json `
  --config configs/descriptive.yaml `
  --surface-output reports/development/response_surface_5m.csv `
  --horizon-output reports/development/horizon_response.csv `
  --weekday-output reports/development/weekday_diagnostics.csv `
  --summary-output reports/development/descriptive_summary.json `
  --manifest data/registry/descriptive_manifest.json
```

Only compact aggregate tables are committed. Feature bins are fitted without outcomes,
and uncertainty resamples complete analysis sessions. These development artifacts cannot
be used as confirmatory evidence or as a source of optimized trading thresholds.

## Run the purged state-model comparison

```powershell
python -m btc_nq_coherence.state_models `
  --one-minute-outcomes data/interim/outcomes_primary_1m.csv `
  --five-minute-outcomes data/interim/outcomes_primary_5m.csv `
  --outcome-manifest data/registry/outcome_manifest.json `
  --config configs/state_models.yaml `
  --one-minute-oof-output data/interim/state_model_oof_1m.csv `
  --five-minute-oof-output data/interim/state_model_oof_5m.csv `
  --summary-output reports/development/state_model_summary.json `
  --fold-metrics-output reports/development/state_model_fold_metrics.csv `
  --calibration-output reports/development/state_model_calibration.csv `
  --coefficients-output reports/development/state_model_coefficients.csv `
  --weekday-output reports/development/state_model_weekday_metrics.csv `
  --trial-ledger-output reports/development/state_model_trial_ledger.csv `
  --manifest data/registry/state_model_manifest.json
```

OOF row-level probabilities stay local and ignored. Fold metrics, reliability bins,
standardized coefficients, weekday diagnostics, and the append-preserving trial ledger are
committed as compact aggregates. Scalers and regularization selection are fitted within
past data only; a complete analysis session is purged before each validation block.

## Run the purged return-model comparison

```powershell
python -m btc_nq_coherence.return_models `
  --one-minute-outcomes data/interim/outcomes_primary_1m.csv `
  --five-minute-outcomes data/interim/outcomes_primary_5m.csv `
  --outcome-manifest data/registry/outcome_manifest.json `
  --config configs/return_models.yaml `
  --one-minute-oof-output data/interim/return_model_oof_1m.csv `
  --five-minute-oof-output data/interim/return_model_oof_5m.csv `
  --summary-output reports/development/return_model_summary.json `
  --fold-metrics-output reports/development/return_model_fold_metrics.csv `
  --coefficients-output reports/development/return_model_coefficients.csv `
  --weekday-output reports/development/return_model_weekday_metrics.csv `
  --trial-ledger-output reports/development/return_model_trial_ledger.csv `
  --manifest data/registry/return_model_manifest.json
```

The target is the gross signed NQ return over the same executable five-minute horizon at
both resolutions. The first 60 cash-session minutes are used only to create within-session
momentum history. NQ-only and cross-market Ridge models receive identical observations,
folds, preprocessing, and nested alpha selection. No return target is clipped or
winsorized.

## Run the overnight negative control

Build overnight features from the same canonical one-minute file, then apply the same
causal outcome definitions:

```powershell
python -m btc_nq_coherence.overnight_features `
  --canonical data/interim/synchronized_development_1m.csv `
  --eligibility-manifest data/registry/available_data_eligibility.json `
  --config configs/overnight_features.yaml `
  --one-minute-output data/interim/features_overnight_1m.csv `
  --five-minute-output data/interim/features_overnight_5m.csv `
  --manifest data/registry/overnight_feature_manifest.json

python -m btc_nq_coherence.outcomes `
  --one-minute-features data/interim/features_overnight_1m.csv `
  --five-minute-features data/interim/features_overnight_5m.csv `
  --feature-manifest data/registry/overnight_feature_manifest.json `
  --config configs/outcomes.yaml `
  --one-minute-output data/interim/outcomes_overnight_1m.csv `
  --five-minute-output data/interim/outcomes_overnight_5m.csv `
  --manifest data/registry/overnight_outcome_manifest.json
```

Run the descriptive, state, and return comparisons together. The command reuses the
frozen primary model configurations but applies the mechanically registered overnight
walk-forward boundaries:

```powershell
python -m btc_nq_coherence.overnight_control `
  --one-minute-outcomes data/interim/outcomes_overnight_1m.csv `
  --five-minute-outcomes data/interim/outcomes_overnight_5m.csv `
  --outcome-manifest data/registry/overnight_outcome_manifest.json `
  --control-config configs/overnight_control.yaml `
  --state-config configs/state_models.yaml `
  --return-config configs/return_models.yaml `
  --primary-state-summary reports/development/state_model_summary.json `
  --primary-return-summary reports/development/return_model_summary.json `
  --state-one-minute-oof-output data/interim/overnight_state_oof_1m.csv `
  --state-five-minute-oof-output data/interim/overnight_state_oof_5m.csv `
  --return-one-minute-oof-output data/interim/overnight_return_oof_1m.csv `
  --return-five-minute-oof-output data/interim/overnight_return_oof_5m.csv `
  --summary-output reports/development/overnight_control_summary.json `
  --horizon-output reports/development/overnight_horizon_response.csv `
  --state-fold-output reports/development/overnight_state_fold_metrics.csv `
  --state-calibration-output reports/development/overnight_state_calibration.csv `
  --state-coefficients-output reports/development/overnight_state_coefficients.csv `
  --state-weekday-output reports/development/overnight_state_weekday_metrics.csv `
  --state-trials-output reports/development/overnight_state_trial_ledger.csv `
  --return-fold-output reports/development/overnight_return_fold_metrics.csv `
  --return-coefficients-output reports/development/overnight_return_coefficients.csv `
  --return-weekday-output reports/development/overnight_return_weekday_metrics.csv `
  --return-trials-output reports/development/overnight_return_trial_ledger.csv `
  --manifest data/registry/overnight_control_manifest.json
```

The row-level feature, outcome, and OOF files remain ignored. Compact aggregates and
hash manifests are committed so the reported result can be audited without redistributing
the proprietary NQ source.

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
