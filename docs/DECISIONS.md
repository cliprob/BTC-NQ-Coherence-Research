# Decision Log

This file records research degrees of freedom before the protocol is frozen. `TBD` means no choice has been made and no confirmatory result may be produced from that choice.

| ID | Decision | Current state | Evidence required before freeze |
|---|---|---|---|
| D-001 | Bar resolution | Resolved: 5-minute primary; mandatory 1-minute robustness | Same 15/30/60-minute clock-time scales; robustness runs regardless of the primary result |
| D-002 | Primary forecast horizon | TBD | Economic mechanism and development-only response study; must be chosen without final P&L |
| D-003 | Coherence definition | Resolved: signed mean of body-direction products at 15/30/60-minute scales, used jointly | No window selection by P&L; body magnitude is excluded |
| D-004 | Joint-event definition | Continuous primary; thresholded events secondary | Confirm exact normalization and trailing volatility estimator |
| D-005 | Primary traded instrument | Proposed: MNQ | Confirm availability of execution-quality data and cost assumptions |
| D-006 | Development sample | Existing data through 2026-05-12 may be exploratory | Register exact file hashes and prior exposure |
| D-007 | Final holdout | TBD and unopened | Boundaries must be committed before data inspection |
| D-008 | Pre-ETP sample start | Proposed: 2022-01-01 | Confirm consistent BTC and futures coverage |
| D-009 | Session definition | Proposed: US cash hours primary | Specify overnight and weekend negative controls |
| D-010 | Multiple-testing procedure | TBD | Match procedure to final estimands and dependence structure |
| D-011 | Magnitude coordinates | Resolved: geometric-mean joint intensity and normalized-difference balance | \(M_1\) includes \(J\), \(B\), and \(|B|\); no sign is imposed |
| D-012 | Coherence state estimator | Resolved: nested discrete-time logistic models \(M_0\) and \(M_1\) | Both include common direction; evaluate with Brier score, log loss, and calibration |
| D-013 | Entry/exit thresholds | Deferred to strategy stage | Must be fitted on development folds and frozen before final evaluation |
| D-014 | Historical body-scale estimator | TBD | Must be causal, resolution-specific, and fitted without final-period information |

## Recorded decisions

### 2026-09-17 — clean redesign

- The new repository will not copy code, selected parameters, or empirical results from the prior strategy project.
- Contemporaneous agreement is treated as a detected market state, not automatically as a prediction.
- Predictive value must be measured as an increment over a comparable NQ-only information set.
- Trading rules will be considered only after descriptive and predictive stages.

### 2026-09-17 — magnitude without an assumed lead–lag direction

- H2 is `magnitude-conditioned persistence`, not `magnitude catch-up`.
- Coherence measures candle-body direction agreement; it must exclude joint intensity and magnitude balance.
- Joint intensity measures how strong the common move is.
- Magnitude balance measures relative BTC–NQ move strength without assuming which market leads.
- Catch-up, continuation, reversal, and no balance effect are competing exploratory outcomes.
- Future observations are outcomes for persistence and tradability tests, not evidence that BTC is assumed to lead NQ.

### 2026-09-17 — candle body is the primary primitive

- "Candle similarity" means agreement of open-to-close body direction, not wick or full-range similarity.
- The signed body is defined as the log open-to-close return.
- Coherence uses sequences of body directions; its exact estimator and lookback remain unresolved.
- Joint intensity uses absolute, causally volatility-normalized body magnitudes.
- Magnitude balance compares the normalized body magnitudes of BTC and NQ.
- Wicks and high-low ranges are excluded from the primary specification and may appear only as labeled robustness features.

### 2026-09-17 — multi-scale directional coherence

- Per-bar agreement is the product of BTC and NQ candle-body signs: `+1`, `-1`, or `0` for an exact doji.
- Coherence is the unweighted arithmetic mean of per-bar agreement.
- The 15-, 30-, and 60-minute continuous coherence measures are used together; no single best window is selected.
- Conditional on current agreement, \(M_0\) predicts next-bar directional agreement from the three coherence scales.
- \(M_1\) adds joint body intensity and body-magnitude balance.
- Model comparison uses Brier score, log loss, and calibration; trading P&L is prohibited for this choice.
- Entry and exit thresholds remain undefined until the strategy stage.

### 2026-09-17 — primary and robustness bar resolutions

- The primary specification uses five-minute bars derived from validated one-minute source data.
- The one-minute specification is a mandatory secondary robustness check and is reported regardless of the primary outcome.
- Both resolutions use identical 15-, 30-, and 60-minute clock-time coherence scales.
- Five-minute OHLCV bars use first open, maximum high, minimum low, last close, and summed volume on UTC-aligned boundaries.
- Incomplete bins are ineligible; prices are not forward-filled and bars cannot cross session, roll, or known-gap boundaries.
- A favorable one-minute result cannot replace a negative or inconclusive five-minute primary result.

### 2026-09-17 — joint intensity and magnitude balance

- Absolute standardized body magnitude is \(m_t^i=|z_t^i|\).
- Joint intensity is the symmetric geometric mean \(J_t=\sqrt{m_t^{BTC}m_t^{NQ}}\).
- Magnitude balance is \(B_t=(m_t^{BTC}-m_t^{NQ})/(m_t^{BTC}+m_t^{NQ})\), bounded on \([-1,1]\).
- A zero denominator is ineligible rather than stabilized with an arbitrary epsilon.
- Common direction \(S_t\) is included in both nested state models.
- \(M_0\) uses the three coherence scales and \(S_t\).
- \(M_1\) adds \(J_t\), \(B_t\), and \(|B_t|\), with no prespecified coefficient signs.
