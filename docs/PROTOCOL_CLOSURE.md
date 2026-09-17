# Protocol v1.0.0 Closure Record

**Closure date:** 2026-09-17

**Release tag:** `research-v1.0.0`

**Scope:** completed development study

## Meaning of the freeze

Protocol v1.0.0 locks the analysis record that was actually executed on the registered
March 2024–May 2026 data. It prevents later model, endpoint or interpretation changes
from silently replacing the reported results.

The protocol was frozen after the results were produced. It is therefore **not** a
preregistration, does not create a pristine holdout, and does not convert the reported
intervals into confirmatory evidence. All source data through 2026-05-12 remain exposed
development data.

## Closed analysis scope

- five-minute primary and one-minute mandatory robustness representations;
- 15/30/60-minute body-direction coherence with causal 63-session same-slot MAD scaling;
- descriptive five-minute NQ response and secondary response curve;
- nested `M0` coherence-only versus `M1` magnitude-conditioned state models;
- NQ-only versus NQ+BTC/coherence Ridge return models;
- mandatory overnight negative control;
- purged expanding walk-forward evaluation, complete-session bootstrap intervals,
  weekday diagnostics and append-preserving trial ledgers.

## Multiplicity disposition

The five-minute state and return comparisons are primary for their distinct questions.
Their 95% complete-session bootstrap intervals are unadjusted and support only
development-level conclusions. One-minute results, secondary horizons, response-surface
cells, weekdays, coefficients and overnight results are robustness, diagnostic or
control outputs; none may rescue an unfavorable primary result.

No family-wise confirmatory error-control claim is made. This is more accurate than
applying a post-hoc correction and presenting previously inspected data as confirmation.
A future confirmatory study must define its hypothesis family and error-control procedure
before new holdout data are opened.

## Stopping decision

The magnitude-conditioned state model produced a small, repeatable improvement in
next-bar agreement prediction. The registered cross-market return model did not improve
five-minute NQ forecasts over NQ-only, and both Ridge models trailed the fold
training-mean benchmark. The overnight control also failed to establish incremental
return value.

Consequently, the strategy stage was not opened: no entry threshold, exit threshold,
MNQ cost model or trading P&L was optimized. Those are not missing pieces of this release;
they require a separately registered study with new data and execution-quality inputs.

## Future-study boundary

Any future nonlinear model, trading rule, pre/post-ETP comparison or final-holdout test
must use a new protocol version. A confirmatory study additionally requires untouched
data beyond the exposed range, boundaries recorded before inspection, a prespecified
multiplicity procedure and an explicit deviation log.
