# Overnight Negative Control

## Purpose

The overnight analysis is a prespecified negative control for the claim that the
BTC–NQ relationship is specific to the US cash-equity session. It repeats the registered
feature definitions and model comparisons during the CME equity-futures session from
18:00 on the previous evening to 09:30 `America/New_York`. It cannot select parameters,
replace the cash-session primary result, or be promoted because it is favorable.

This is a development-only comparison. The available NQ file is a stitched series with
incomplete contract-level provenance, the history has been inspected before, and no
pristine final holdout exists.

## Data and walk-forward design

After excluding incomplete and contract-transition sessions, 551 overnight sessions
contain all 930 expected one-minute observations. The causal same-slot MAD requires 63
prior eligible sessions, leaving 488 feature-ready sessions.

The control uses 135 initial training sessions, one fully purged session, and 16
consecutive validation blocks of 22 sessions. Every outer fold contains three trailing,
expanding inner validation blocks of 22 sessions with the same one-session purge. The
choice is mechanical: `488 = 135 + 1 + 16 × 22`. Predictor sets, transformations,
regularization grids, primary metrics, and evidence rules are unchanged from the cash
analysis.

## Descriptive return response

| Representation | Events | Mean signed five-minute NQ return | Session-block 95% CI |
|---|---:|---:|---:|
| 5-minute primary | 49,197 | +0.043 bps | [-0.005, +0.090] bps |
| 1-minute robustness, five-minute endpoint | 234,598 | +0.014 bps | [-0.007, +0.035] bps |

Both intervals include zero. Contemporaneous agreement therefore does not produce a
clear unconditional five-minute overnight return response.

## State-persistence control

### Five-minute primary

The OOF sample contains 36,230 events from 352 validation sessions. Adding joint
intensity and magnitude balance to the direction/coherence baseline changes Brier score
by `-0.000259` and log loss by `-0.000510`.

| Loss difference, M1 − M0 | Estimate | Session-block 95% CI |
|---|---:|---:|
| Brier score | **-0.000259** | **[-0.000440, -0.000081]** |
| Log loss | **-0.000510** | **[-0.000901, -0.000118]** |

The Brier difference is negative in 11 of 16 folds and for every weekday. The registered
incremental-evidence rule is met. At one-minute resolution the Brier difference is also
negative (`-0.000191`, 95% CI `[-0.000289, -0.000106]`).

This result **falsifies cash-session specificity**, not the existence of state
dependence. Magnitude contains a small amount of incremental information about next-bar
directional agreement in both cash and overnight samples. The overnight result is
smaller than the cash-session estimate, but this study did not register a formal test of
the difference between those two effects.

## Return-forecast control

### Five-minute primary

The OOF sample contains 35,804 events from 352 validation sessions.

| Model | MSE (bps²) | MAE (bps) | OOS R² vs fold mean |
|---|---:|---:|---:|
| Fold training-mean benchmark | **38.145** | **3.527** | 0.0000 |
| NQ-only Ridge | 38.209 | 3.530 | -0.0017 |
| Cross-market Ridge | 38.220 | 3.533 | -0.0020 |

The cross-market-minus-NQ-only MSE difference is `+0.0106 bps²`, with a 95% interval of
`[-0.0283, +0.0502]`. Its MAE difference is `+0.0030 bps`, with interval
`[+0.0009, +0.0051]`. The registered incremental-return criterion is not met, and both
models are worse than the fold training-mean benchmark.

At one-minute resolution, the cross-market model improves MSE but worsens MAE. Because
the registered rule requires directionally consistent MAE, this mixed result also fails
the evidence criterion and cannot rescue the five-minute primary.

## Conclusion

The negative control changes the interpretation of the state result: the measured
persistence association is a broader cross-session relationship, not evidence of a
cash-hours-only integration mechanism. It does not change the economic conclusion.
Neither the cash nor overnight analysis supports incremental five-minute NQ return
forecast value for the registered linear cross-market model, and neither establishes a
tradable strategy or alpha.

## Audit artifacts

- [`overnight_control_summary.json`](../reports/development/overnight_control_summary.json)
  contains the machine-readable conclusions and specificity decisions.
- [`overnight_state_fold_metrics.csv`](../reports/development/overnight_state_fold_metrics.csv)
  and [`overnight_return_fold_metrics.csv`](../reports/development/overnight_return_fold_metrics.csv)
  contain every outer-fold result.
- [`overnight_state_trial_ledger.csv`](../reports/development/overnight_state_trial_ledger.csv)
  and [`overnight_return_trial_ledger.csv`](../reports/development/overnight_return_trial_ledger.csv)
  preserve all nested model-selection attempts.
- [`overnight_control_manifest.json`](../data/registry/overnight_control_manifest.json)
  binds the exact configurations, implementation, inputs, local OOF files, and committed
  outputs by SHA-256.
