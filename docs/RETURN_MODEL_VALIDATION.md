# Purged Walk-Forward Return-Model Validation

**Model version:** 0.1.0  
**Status:** development-only; hypothesis not supported in the primary specification

## Question

The state-model stage found that magnitude adds a small amount of information about
whether BTC and NQ candle-body directions remain aligned. This stage tests the necessary
economic follow-up:

> Does BTC/coherence/magnitude information improve the forecast of the next executable
> five-minute NQ return over a fair NQ-only baseline?

The target is the next-open-to-horizon-open NQ log return in basis points, signed by the
current NQ direction. Positive values mean continuation in the current jointly detected
direction; negative values mean reversal. This is a gross response, not strategy P&L.

## Models and information sets

Both Ridge models receive identical fold-local scaling, target rows, folds, and alpha
selection. The first 60 cash-session minutes are excluded so all 60-minute causal momentum
features exist without crossing a session boundary.

The `NQ-only` baseline contains:

- current NQ direction and volatility-normalized body magnitude;
- NQ close-to-close momentum over 5/15/30/60 minutes, aligned with current NQ direction;
- two Fourier harmonics for intraday time and four weekday controls.

The `cross-market` model adds:

- BTC aligned momentum over 5/15/30/60 minutes and current BTC magnitude;
- BTC–NQ coherence over 15/30/60 minutes;
- joint intensity, signed magnitude balance, and absolute magnitude balance.

No target clipping or winsorization is performed. Ridge
\(\alpha\in\{0.01,0.1,1,10,100,1000\}\) is selected separately for each model and outer
fold from three inner expanding validation blocks. Selection minimizes event-weighted
inner OOF mean squared error.

The outer design is unchanged from state validation: 130 initial training sessions, one
complete purged session, and 12 consecutive 22-session validation blocks. The primary
comparison is `cross-market minus NQ-only` squared-error loss. Uncertainty uses 5,000
paired complete-session bootstrap resamples.

## Five-minute primary result

The OOF sample contains 11,364 events from 264 sessions spanning 2025-02-24 through
2026-05-11. The target standard deviation is 11.61 bps.

| Model | MSE (bps²) | RMSE (bps) | MAE (bps) | OOS \(R^2\) vs fold mean |
|---|---:|---:|---:|---:|
| Fold training-mean benchmark | **134.831** | **11.612** | **7.080** | 0.0000 |
| NQ-only Ridge | 135.101 | 11.623 | 7.092 | -0.0020 |
| Cross-market Ridge | 135.294 | 11.632 | 7.099 | -0.0034 |

| Cross-market minus NQ-only | Estimate | Session-block 95% CI |
|---|---:|---:|
| Squared-error loss | **+0.1924 bps²** | **[+0.0728, +0.3222]** |
| Absolute-error loss | **+0.0073 bps** | **[+0.0010, +0.0135]** |

Lower loss is better, so both differences favor the NQ-only model. The cross-market model
improves MSE in only 5 of 12 folds and MAE in 2 of 12. It is worse on every weekday in the
primary specification. The registered incremental-evidence criterion is not met; the
primary result instead provides development evidence against incremental five-minute
return value for this linear feature set.

Strong shrinkage is itself informative: the largest registered alpha (`1000`) is selected
in 9 of 12 NQ-only folds and 8 of 12 cross-market folds. The nested procedure generally
prefers forecasts close to the training mean rather than large feature-driven variation.

## One-minute robustness

The one-minute representation contains 55,905 events over the same 264 sessions.

| Model | MSE (bps²) | RMSE (bps) | MAE (bps) | OOS \(R^2\) vs fold mean |
|---|---:|---:|---:|---:|
| Fold training-mean benchmark | **141.002** | **11.874** | **7.141** | 0.0000 |
| NQ-only Ridge | 141.030 | 11.876 | 7.157 | -0.0002 |
| Cross-market Ridge | 141.033 | 11.876 | 7.160 | -0.0002 |

The cross-market-minus-NQ-only MSE difference is `+0.0031 bps²`, with a wide interval of
`[-0.1065, +0.0962]`. Its MAE difference is `+0.0027 bps`, with interval
`[-0.0004, +0.0059]`. This robustness result is inconclusive but does not rescue the
negative five-minute primary result.

## Interpretation

The combined evidence separates state predictability from economic predictability:

1. joint intensity and magnitude balance slightly improve prediction of next-bar
   BTC–NQ directional agreement;
2. neither Ridge model beats the simple historical-mean return benchmark;
3. adding cross-market information makes the primary NQ return forecast slightly but
   consistently worse.

Therefore the current evidence does not justify constructing an entry rule or claiming
tradable alpha. Costs would only weaken a return effect that is already absent before
costs. The academically correct conclusion is hypothesis rejection for the registered
linear five-minute return model, not selection of a more favorable fold, weekday,
secondary resolution, or alternative target after inspection.

This does not prove that every nonlinear or regime-specific relationship is absent. Any
new nonlinear model, target transformation, window, or event filter would be a new
development trial requiring explicit registration and genuinely new evaluation data. The
current history is not a pristine final holdout.

## Audit artifacts

- [`return_model_summary.json`](../reports/development/return_model_summary.json) — primary
  metrics, paired intervals, and evidence decision;
- [`return_model_fold_metrics.csv`](../reports/development/return_model_fold_metrics.csv) —
  chronological fold boundaries, losses, and selected alphas;
- [`return_model_coefficients.csv`](../reports/development/return_model_coefficients.csv) —
  standardized Ridge coefficients by fold;
- [`return_model_weekday_metrics.csv`](../reports/development/return_model_weekday_metrics.csv)
  — weekday stability diagnostic;
- [`return_model_trial_ledger.csv`](../reports/development/return_model_trial_ledger.csv) —
  all 288 nested alpha attempts;
- [`return_model_manifest.json`](../data/registry/return_model_manifest.json) — hashes for
  the exact inputs, implementation, configuration, local OOF rows, and committed outputs.
