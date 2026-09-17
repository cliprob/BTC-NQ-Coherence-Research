# Causal Outcomes and Descriptive Response Surfaces

**Outcome version:** 0.1.0  
**Descriptive version:** 0.1.0  
**Status:** development-only; no confirmatory or trading claim

## Outcome timing

The feature row is indexed by the opening timestamp of event bar `t`. Its final input
becomes available only when that bar closes. The earliest economic entry is therefore
the next bar's open, which is the same instant as the event bar's close:

```text
event bar [t, t + bar interval)
                               feature becomes available
                               = entry at next bar open
                                                     exit at entry + horizon
```

The implementation rejects an artifact if its recorded feature-availability timestamp
does not equal this causal entry time. An economic return is valid only when its entry
and exit opens exist in the same analysis session. No target may cross the XNYS close.

The primary economic label is the NQ open-to-open log return over the next five minutes,
signed by the event bar's common BTC–NQ direction. Thus, positive values mean continuation
and negative values mean reversal. Prespecified secondary endpoints are 15, 30, and 60
minutes. The 1-minute representation additionally records cumulative responses at +1,
+2, +3, +4, and +5 minutes.

## State persistence

For a current agreement event, `next_bar_agreement_label` indicates whether the next
consecutive bar also has same-direction BTC and NQ bodies. `persistence_run_minutes`
counts consecutive future agreement bars until the first observed disagreement or doji.
The run is right-censored at a missing bar or session end; a gap is never interpreted as
an observed state decay.

| Representation | Current-agreement rows | Next-bar labels | Right-censored runs |
|---|---:|---:|---:|
| 5-minute primary | 23,529 | 23,261 | 751 |
| 1-minute robustness | 114,695 | 114,434 | 675 |

These counts include rows before the 63-session feature warm-up. Descriptive analyses
below use only feature-ready events: 20,449 at 5 minutes and 99,846 at 1 minute.

## Descriptive design

The primary 5-minute events are divided into a 5-by-5 surface using empirical quintiles
of `joint_intensity` and `magnitude_balance`. The bin edges are fitted from eligible
contemporaneous features only. Future returns, persistence labels, and cell performance
cannot affect bin assignment. All cells are retained; cells below 30 valid outcomes are
flagged instead of silently removed.

Horizon means use 95% percentile intervals from 2,000 deterministic resamples of whole
analysis sessions. This keeps all overlapping events from a selected session together.
It is a dependence-aware descriptive interval, not a multiple-testing-adjusted
confirmatory test.

## Development results

### Prespecified response curve

| Resolution | Horizon | Events | Mean signed NQ return | Session-block 95% CI |
|---:|---:|---:|---:|---:|
| 5 min | **5 min (primary)** | 19,955 | **0.012 bps** | **[-0.150, 0.181] bps** |
| 5 min | 15 min | 19,441 | 0.076 bps | [-0.177, 0.337] bps |
| 5 min | 30 min | 18,678 | 0.228 bps | [-0.213, 0.699] bps |
| 5 min | 60 min | 17,093 | 0.630 bps | [0.072, 1.281] bps |
| 1 min | 1 min | 99,407 | -0.029 bps | [-0.066, 0.009] bps |
| 1 min | 2 min | 99,165 | -0.014 bps | [-0.059, 0.030] bps |
| 1 min | 3 min | 98,915 | -0.013 bps | [-0.069, 0.048] bps |
| 1 min | 4 min | 98,668 | -0.005 bps | [-0.068, 0.057] bps |
| 1 min | **5 min comparable endpoint** | 98,405 | **-0.034 bps** | **[-0.103, 0.034] bps** |
| 1 min | 15 min | 95,899 | 0.068 bps | [-0.058, 0.192] bps |
| 1 min | 30 min | 92,171 | 0.128 bps | [-0.069, 0.340] bps |
| 1 min | 60 min | 84,670 | 0.331 bps | [0.062, 0.618] bps |

The primary estimate is practically zero and its interval comfortably includes zero.
The comparable 1-minute construction is slightly negative and also inconclusive. The
positive 60-minute secondary estimate is exploratory: it is not the registered primary,
comes from development data, and cannot replace the primary after inspection.

The 25 pooled surface cells contain 304 to 1,315 valid primary outcomes. Their means vary
in sign, from roughly -0.79 to +0.75 bps. This heterogeneity is a reason to model the
conditional response next, not permission to select the historically strongest cell as
a trading rule. The weekday diagnostic is also visibly unbalanced—only 30 eligible
Thursdays—and the Thursday/Friday contrast shows why calendar controls are needed.

## Reproducible artifacts

- [`response_surface_5m.csv`](../reports/development/response_surface_5m.csv) contains
  every feature cell overall and separately for up/down common direction.
- [`horizon_response.csv`](../reports/development/horizon_response.csv) contains the
  prespecified response curves and session-block intervals.
- [`weekday_diagnostics.csv`](../reports/development/weekday_diagnostics.csv) exposes
  the sampling imbalance by weekday.
- [`descriptive_summary.json`](../reports/development/descriptive_summary.json) is a
  compact machine-readable summary.
- [`outcome_manifest.json`](../data/registry/outcome_manifest.json) and
  [`descriptive_manifest.json`](../data/registry/descriptive_manifest.json) bind the
  configurations, implementations, local input identities, and committed aggregates.

## What can and cannot be concluded

The current data do not support a claim that same-direction BTC–NQ bodies are followed by
economically meaningful five-minute NQ continuation on average. They do support moving to
the prespecified conditional-model stage: test whether intensity and balance improve
calibrated persistence or return forecasts over NQ-only information.

No pristine holdout, pre-ETP comparison, execution costs, or trade policy exists in this
iteration. The surface is an exploratory map of development data. Any threshold suggested
by it must be treated as a candidate to be evaluated with purged walk-forward validation
and, ultimately, genuinely new data.

