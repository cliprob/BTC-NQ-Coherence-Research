# BTC–NQ Coherence Research

An empirical study of whether synchronized, volatility-adjusted Bitcoin and Nasdaq futures moves define persistent cross-market regimes, and how joint move intensity and cross-market magnitude balance relate to regime duration and returns realized while the regime remains active.

> **Research status: completed development study (protocol v1.0.0).** The completed
> record is locked after results for reproducibility; it was not preregistered and is not
> confirmatory. Magnitude slightly improves prediction of state persistence in both cash
> and overnight sessions, while cross-market information does not improve the primary
> five-minute NQ return forecast over an NQ-only baseline. No strategy or alpha claim
> exists.

## Verdict

**Cross-market magnitude contains a small amount of information about persistence of the
BTC–NQ same-direction state, but it does not add five-minute NQ return value over an
NQ-only baseline.** The state result repeats overnight, so it is not specific to US cash
hours. This is a model-validation result, not a strategy or alpha claim.

![Primary state and return comparisons](report/figures/primary_results.png)

*Primary five-minute paired loss differences. Points are out-of-fold means and bars are
complete-session bootstrap 95% intervals. Lower values favor the expanded cross-market
model.*

### Results snapshot

| Registered comparison | OOF events | Difference | 95% session-block interval | Conclusion |
|---|---:|---:|---:|---|
| Cash state Brier, `M1 − M0` | 13,724 | `-0.000699` | `[-0.001120, -0.000297]` | Small state improvement |
| Cash return MSE, cross-market − NQ-only | 11,364 | `+0.1924 bps²` | `[+0.0728, +0.3222]` | No incremental return value |
| Overnight state Brier, `M1 − M0` | 36,230 | `-0.000259` | `[-0.000440, -0.000081]` | State effect is not cash-specific |
| Overnight return MSE, cross-market − NQ-only | 35,804 | `+0.0106 bps²` | `[-0.0283, +0.0502]` | Inconclusive; MAE worsens |

Read the [seven-page academic report](output/pdf/btc_nq_coherence_research.pdf), the
[state validation](docs/STATE_MODEL_VALIDATION.md), [return validation](docs/RETURN_MODEL_VALIDATION.md),
and [overnight negative control](docs/OVERNIGHT_NEGATIVE_CONTROL.md).

## Research question

The project separates three questions that are often mixed together:

1. **Co-movement:** when do BTC and NQ produce same-direction candle bodies, and how large are those bodies relative to each market's own recent volatility?
2. **State dynamics:** do joint move intensity and magnitude balance contain information about coherence duration and returns realized during the active regime?
3. **Tradability:** if predictive information exists, does it survive causal execution and MNQ trading costs?

The completed development study considered:

- **H1 — regime persistence:** synchronized BTC–NQ states exhibit measurable duration beyond the detection bar.
- **H2 — magnitude-conditioned persistence:** joint move intensity and cross-market magnitude balance are associated with coherence duration and with returns realized while the regime remains active.
- **H3 — coherence decay:** reserved for a strategy stage that was not opened after the
  registered return comparison failed to show incremental value.

The hypotheses do not assume that BTC leads NQ or that the weaker market must catch up. Catch-up, continuation, reversal, or no magnitude-balance effect are competing exploratory outcomes.

ETF adoption motivates a possible change in market integration, but this project will not infer ETF causality from a simple before/after price comparison.

## Agreed coherence representation

For each bar, the BTC and NQ candle-body directions are multiplied to obtain `+1` for agreement, `-1` for disagreement, and `0` for an exact doji. Coherence is the arithmetic mean of this signed agreement over three clock-time scales: **15, 30, and 60 minutes**.

All three continuous measures are used together. No historically best window is selected. Conditional on current body-direction agreement, a discrete-time logistic model produces a next-bar agreement probability from the three scales. A second nested model adds joint body intensity and body-magnitude balance to test whether magnitude improves state-persistence estimates. Model comparison uses Brier score, log loss, and calibration—not trading P&L.

No entry or exit threshold is defined during the state-research stage. Thresholds belong exclusively to a later strategy stage.

### Magnitude coordinates

For each asset, body magnitude is the absolute body return divided by a causal historical scale. Joint intensity is the geometric mean of the two normalized magnitudes. Magnitude balance is their normalized difference on `[-1, 1]`: positive when BTC is relatively stronger, negative when NQ is relatively stronger, and zero when they are equal.

The baseline state model uses the three coherence scales and the current common direction. The nested magnitude model adds joint intensity, signed magnitude balance, and absolute magnitude imbalance. No coefficient sign is imposed in advance.

Body magnitude is normalized with a causal, resolution-specific MAD computed for the same DST-aware session slot over the previous 63 eligible sessions. The current session is excluded from its own scale. Missing history, zero scale, and roll-contaminated observations are ineligible; no epsilon or forward-looking fallback is used.

## Bar resolution

The primary specification uses **5-minute bars** constructed from validated one-minute source data. A **1-minute robustness specification is mandatory and is run regardless of the 5-minute result**. Both resolutions retain the same 15/30/60-minute clock-time coherence scales, so the economic meaning of each feature is unchanged.

Five-minute bars are aligned in UTC and use first open, maximum high, minimum low, last close, and summed volume. Incomplete bins are ineligible and prices are never forward-filled.

## Economic return horizon

The primary economic outcome is always the **subsequent five-minute NQ return**, measured causally from the first tradable open after the event bar closes to the open five minutes later. In the 5-minute specification this is the next bar's open-to-open return. In the 1-minute robustness specification it is the cumulative return over the next five one-minute bars.

The cumulative 1-minute response path at +1 through +5 minutes is reported only as a timing diagnostic. Open-to-open responses at 15, 30, and 60 minutes form a prespecified secondary response curve; none may replace the 5-minute primary after results are observed. This economic endpoint is separate from the next-bar state-persistence label, whose duration necessarily follows the chosen bar resolution.

## Parameter provenance

| Parameter | Locked value | Research role and status |
|---|---:|---|
| Primary bar representation | 5 minutes | Computationally tractable primary view; not asserted to be optimal |
| Robustness representation | 1 minute | Mandatory timing check with the same five-minute economic endpoint |
| Coherence clocks | 15/30/60 minutes | Prespecified multiscale representation; no best-window selection by outcome |
| Historical body scale | 63 prior sessions | Causal same-slot MAD; the current session is excluded |
| Primary economic horizon | 5 minutes | Next-open to horizon-open; fixed across both bar resolutions |
| Purge | 1 complete session | Deliberately exceeds the target horizon and separates adjacent folds |

These are frozen development-study choices, not estimates of economically optimal
parameters. Any future sensitivity analysis or strategy design requires a new protocol.

## Session scope

Primary events and targets are restricted to the US cash-equity session, `09:30–16:00 America/New_York`, shortened by official early closes. Events are formed only after an eligible bar closes, and targets may not cross the official session close. Causal coherence lookbacks may use valid pre-09:30 bars so that the cash open remains observable.

The NQ overnight session from `18:00` on the prior evening to `09:30 America/New_York` is a mandatory, separately reported negative control. It uses the same feature definitions but cannot select or replace the primary specification. Weekends, the CME maintenance break, holidays, and invalid bars are excluded.

## Design principle

Detection and execution are deliberately separated:

```text
information available through bar t close
                  │
                  ▼
     event and coherence state at t
                  │
                  ▼
       forecast of future NQ return
                  │
                  ▼
 earliest simulated fill: bar t+1 open
```

Contemporaneous correlation is not itself a trading signal. A tradable result requires out-of-sample evidence that the jointly detected state persists and leaves a return available after causal execution. This timing requirement does not imply that one market leads the other.

## Completed development scope

- [x] Create a clean repository and a machine-readable draft protocol.
- [x] Register and structurally audit the existing local BTC and NQ files.
- [x] Define a development-only fallback that excludes incomplete and contract-transition sessions without forward-filling.
- [x] Record complete contract-level history, a pre-ETP sample, and a pristine holdout as unavailable in the current iteration.
- [x] Close and version the development protocol without retroactive preregistration.
- [x] Build deterministic canonicalization and session-eligibility pipelines for the registered data.
- [x] Implement the agreed 15/30/60-minute body-direction coherence representation, body-based joint intensity, and body-magnitude balance at 1m and 5m.
- [x] Produce descriptive event studies and response curves without strategy optimization.
- [x] Run the mandatory 1-minute response-path specification regardless of the primary result.
- [x] Compare direction/coherence-only and magnitude-conditioned state models with nested purged walk-forward validation.
- [x] Run the mandatory overnight negative control without changing primary parameters.
- [x] Compare NQ-only and NQ+BTC forecasts with purged walk-forward evaluation.
- [x] Stop before entry/exit optimization because the registered return comparison did not support incremental value.
- [x] Record that no pristine final holdout was available or opened; require a new protocol for future confirmation.
- [x] Publish a reproducible academic-style report, including negative and inconclusive results.

See [Research Protocol](docs/RESEARCH_PROTOCOL.md) for the closed specification,
[Protocol Closure Record](docs/PROTOCOL_CLOSURE.md) for the meaning and limits of the
post-study freeze,
[Causal Outcomes and Descriptive Results](docs/OUTCOMES_AND_DESCRIPTIVE.md) for the
implemented timing and first results, [State-Model Validation](docs/STATE_MODEL_VALIDATION.md)
for persistence prediction, [Return-Model Validation](docs/RETURN_MODEL_VALIDATION.md) for
the economic forecast test, [Overnight Negative Control](docs/OVERNIGHT_NEGATIVE_CONTROL.md)
for the cash-session-specificity falsification, and [Decision Log](docs/DECISIONS.md) for
the final disposition of every research choice.

## What this project demonstrates

- causal feature construction and next-bar execution;
- market-calendar, time-zone, session, and futures-roll handling;
- volatility-normalized cross-market candle-body comparison;
- event studies, conditional response surfaces, and uncertainty estimates;
- incremental forecast evaluation: NQ-only versus NQ+BTC;
- walk-forward validation, multiplicity-aware primary/secondary separation, complete
  trial ledgers, and honest disclosure that no pristine holdout exists;
- separation of statistical predictability from economic tradability.

## What this project does not claim

- that contemporaneous BTC–NQ correlation is alpha;
- that spot BTC or ETH ETPs caused any observed relationship;
- that a profitable backtest implies live-trading readiness;
- that a parameter is optimal because it maximized one historical sample.

## Data policy

Raw market data is not committed. The repository contains schemas, checksums, download instructions for redistributable sources, and synthetic fixtures. Proprietary NQ data must remain local. See [data/README.md](data/README.md).

## Quickstart

```bash
python -m venv .venv
python -m pip install -e ".[dev,report]"
python -m btc_nq_coherence.protocol configs/research_protocol.yaml
pytest
python report/build_report.py --check
```

## Repository structure

```text
configs/                  machine-readable research specifications
data/                     schemas and local-data instructions, not raw data
docs/                     protocol, provenance, and decision log
report/                   deterministic figure and PDF builders plus manifests
output/pdf/               final seven-page academic report
src/btc_nq_coherence/     validated research code
tests/                    unit and integration tests
```

## Provenance

This is a clean research redesign motivated by earlier collaborative coursework with [@AlexSamuseva](https://github.com/AlexSamuseva). Earlier notebooks and their results are not treated as evidence for this study and will not be copied into this repository. See [Provenance](docs/PROVENANCE.md).

No license has been selected yet.
