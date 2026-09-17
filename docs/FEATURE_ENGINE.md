# Causal Feature Engine

**Feature version:** 0.1.0  
**Status:** development-only implementation of protocol v0.10.0

## Implemented representations

The engine builds two representations from the same synchronized one-minute source:

| Representation | Bar interval | Coherence windows | Role |
|---|---:|---|---|
| Primary | 5 minutes | 3/6/12 bars = 15/30/60 minutes | main development analysis |
| Robustness | 1 minute | 15/30/60 bars = 15/30/60 minutes | mandatory resolution check |

Five-minute OHLCV uses first open, maximum high, minimum low, last close, and summed volume. A five-minute bar is ineligible unless all five source minutes are present, valid, and belong to one NQ contract. Prices are never forward-filled.

## Causal timing

The output index is the bar-open timestamp. The separate `feature_available_timestamp_utc` is the bar close:

```text
5m bar indexed 10:00  = observations over [10:00, 10:05)
feature available     = 10:05
earliest later trade  = open at 10:05
```

Features for the first cash-session bars may use up to 60 valid pre-open minutes. Rolling windows are reset between analysis sessions and cannot cross a gap, roll, or session boundary.

## Feature definitions

For asset \(i\), the signed candle body is:

\[
b_t^i=\log(C_t^i/O_t^i).
\]

Per-bar directional agreement is the product of the BTC and NQ body signs. Coherence is its unweighted rolling mean over 15, 30, and 60 clock minutes. Magnitude is not included in coherence.

For each asset, resolution, and DST-aware New York session slot, the scale is `1.4826 × MAD` over the previous 63 valid eligible sessions. The current observation is appended only after its scale has been computed. A zero or non-finite MAD leaves the observation ineligible; no epsilon is introduced.

Normalized magnitudes are \(m_t^i=|b_t^i/\widehat\sigma_{t-1}^i|\). The derived coordinates are:

\[
J_t=\sqrt{m_t^{BTC}m_t^{NQ}},
\qquad
B_t=\frac{m_t^{BTC}-m_t^{NQ}}{m_t^{BTC}+m_t^{NQ}}.
\]

The denominator-zero case is ineligible. `common_direction` is populated only when the current bodies agree and are non-doji.

## Generated development artifacts

| Resolution | Signal-bar rows | Feature-ready rows | Current-agreement state rows | First feature-ready timestamp |
|---|---:|---:|---:|---|
| 1 minute | 177,540 | 152,964 | 99,846 | 2024-07-01 13:30 UTC |
| 5 minutes | 35,508 | 30,594 | 20,449 | 2024-07-01 13:30 UTC |

The first feature-ready date emerges from the prespecified 63-session warm-up; it was not selected from outcomes. Generated CSV files remain ignored by Git. Their hashes, row counts, source identity, feature configuration, and limitations are recorded in [`data/registry/feature_manifest.json`](../data/registry/feature_manifest.json).

## Guardrails and tests

Automated tests cover:

- complete and incomplete five-minute aggregation;
- exact body-direction coherence independent of magnitude;
- same-slot MAD based only on prior observations;
- invariance of earlier features to changes in future sessions;
- explicit bar-open versus feature-availability timestamps;
- zero/non-finite scale ineligibility through missing feature values.

These artifacts remain development evidence. The feature engine does not create a pre-ETP sample, a pristine holdout, or an alpha claim.

