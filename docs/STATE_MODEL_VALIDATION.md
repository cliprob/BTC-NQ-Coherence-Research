# Purged Walk-Forward State-Model Validation

**Model version:** 0.1.0  
**Status:** development-only; no final holdout or trading claim

## Question and estimand

This stage asks whether body magnitude contributes incremental information about the next
BTC–NQ directional-agreement state. It does **not** ask whether a trading strategy is
profitable and does not use P&L for model selection.

Conditional on current same-direction bodies, the target is:

\[
P(d_{t+1}=+1 \mid d_t=+1).
\]

The nested models are:

| Model | Predictors |
|---|---|
| Training-rate benchmark | Agreement frequency in the outer training fold |
| \(M_0\) | coherence at 15/30/60 minutes, common direction |
| \(M_1\) | all \(M_0\) predictors plus joint intensity, signed magnitude balance, absolute magnitude balance |

`M0` is a direction/coherence baseline, not yet the pure NQ-only return baseline planned
for the later return-forecast stage. The comparison here isolates the incremental value
of body magnitude within the state-persistence question.

## Registered evaluation design

- observations are ordered by complete XNYS analysis sessions;
- the first 130 feature-ready sessions form the initial training history;
- 12 consecutive validation blocks contain 22 sessions each;
- one complete session immediately before every validation block is purged;
- later folds expand through information available before their purge session;
- both the 5-minute primary and 1-minute robustness specifications use identical session
  boundaries;
- `StandardScaler` and logistic regression are fitted inside each training fold only;
- \(C\in\{0.01,0.1,1,10\}\) is selected separately for each model and outer fold from
  three inner expanding validation blocks by event-weighted OOF Brier score;
- the primary metric is Brier score; log loss is secondary and fixed-width reliability
  bins diagnose calibration;
- uncertainty for paired loss differences resamples complete validation sessions 5,000
  times.

The prespecified incremental-evidence rule requires the 95% session-block interval for
`M1 − M0` Brier loss to lie below zero, directionally consistent log-loss change, and no
expected-calibration-error deterioration larger than 0.01.

## Out-of-fold results

### Five-minute primary

The pooled OOF sample contains 13,724 events from 264 validation sessions spanning
2025-02-24 through 2026-05-11. The observed next-bar agreement rate is 68.25%.

| Model | Brier score | Log loss | Expected calibration error |
|---|---:|---:|---:|
| Training-rate benchmark | 0.217250 | 0.626229 | 0.009849 |
| \(M_0\) | 0.216736 | 0.625038 | 0.010755 |
| \(M_1\) | **0.216037** | **0.623370** | **0.009218** |

The primary paired difference is:

| Loss difference, \(M_1-M_0\) | Estimate | Session-block 95% CI |
|---|---:|---:|
| Brier score | **-0.000699** | **[-0.001120, -0.000297]** |
| Log loss | **-0.001668** | **[-0.002668, -0.000703]** |

`M1` improves Brier score in 10 of 12 outer folds. Its Brier improvement appears on every
weekday, although Wednesday is nearly neutral and Thursday has only 30 validation
sessions. The Brier reduction is about 0.32% relative to `M0`: statistically stable in
this development sample, but economically and practically small.

### One-minute robustness

The robustness sample contains 67,483 events across the same 264 sessions.

| Model | Brier score | Log loss | Expected calibration error |
|---|---:|---:|---:|
| Training-rate benchmark | 0.222683 | 0.637534 | 0.011560 |
| \(M_0\) | 0.221126 | 0.634031 | 0.008314 |
| \(M_1\) | **0.220829** | **0.633357** | 0.008667 |

The `M1 − M0` Brier difference is `-0.000297`, with a 95% interval of
`[-0.000418, -0.000173]`. The log-loss difference is `-0.000674`, with a 95% interval of
`[-0.000941, -0.000408]`. Brier improves in 11 of 12 folds and log loss in all 12. ECE
increases by only 0.000353, within the registered tolerance.

## Coefficient stability

Because every predictor is standardized inside its outer training fold, coefficients can
be compared across folds as conditional log-odds effects. In the five-minute `M1` model,
the principal magnitude coefficients are:

| Predictor | Mean coefficient | Fold range |
|---|---:|---:|
| Joint intensity | +0.10 | [+0.09, +0.11] |
| Magnitude balance | -0.06 | [-0.07, -0.03] |
| Absolute magnitude balance | +0.03 | [+0.02, +0.05] |

Higher joint intensity is therefore associated with greater next-bar agreement
probability in every primary fold. The negative signed-balance coefficient indicates
lower persistence as BTC becomes relatively stronger than NQ, conditional on the other
variables. These are predictive associations, not causal effects. Signed and absolute
balance enter together, so neither coefficient should be interpreted in isolation.

The selected regularization frequently lies at an edge of the registered grid (`0.01` or
`10`). This does not invalidate the OOF comparison—the selection was nested—but it is a
model-stability warning. The grid must not be expanded and the result silently replaced;
any expanded-grid run must become a separately recorded trial.

## Interpretation

The development evidence supports the narrow statement that body magnitude adds a small,
repeatable amount of out-of-fold information about **state persistence** beyond recent
directional coherence and common direction. It does not show that magnitude predicts a
tradable NQ return. Indeed, the separate descriptive primary return estimate remains
approximately zero.

The result is not confirmatory because this history has been inspected previously and no
pristine final holdout exists. The bootstrap conditions on the fitted OOF predictions; it
captures session clustering but not uncertainty from retraining the complete research
process on a different historical sample. A future unseen period is required before
claiming external validity.

## Audit artifacts

- [`state_model_summary.json`](../reports/development/state_model_summary.json) — primary
  machine-readable results and evidence decision;
- [`state_model_fold_metrics.csv`](../reports/development/state_model_fold_metrics.csv) —
  every outer fold, date boundary, selected `C`, and loss;
- [`state_model_calibration.csv`](../reports/development/state_model_calibration.csv) —
  complete fixed-width reliability table, including empty bins;
- [`state_model_coefficients.csv`](../reports/development/state_model_coefficients.csv) —
  standardized outer-fold coefficients;
- [`state_model_weekday_metrics.csv`](../reports/development/state_model_weekday_metrics.csv)
  — mandatory weekday stability diagnostic;
- [`state_model_trial_ledger.csv`](../reports/development/state_model_trial_ledger.csv) —
  all 192 nested regularization attempts;
- [`state_model_manifest.json`](../data/registry/state_model_manifest.json) — input,
  implementation, configuration, local OOF, and committed-artifact hashes.

