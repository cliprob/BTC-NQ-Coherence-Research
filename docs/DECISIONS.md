# Decision Log

This file records research degrees of freedom before the protocol is frozen. `TBD` means no choice has been made and no confirmatory result may be produced from that choice.

| ID | Decision | Current state | Evidence required before freeze |
|---|---|---|---|
| D-001 | Bar resolution | Resolved: 5-minute primary; mandatory 1-minute robustness | Same 15/30/60-minute clock-time scales; robustness runs regardless of the primary result |
| D-002 | Primary economic return horizon | Resolved: 5 minutes at both resolutions, measured next-open to horizon-open | 5-minute bars use one future bar; 1-minute bars use five future bars; 15/30/60 minutes remain secondary |
| D-003 | Coherence definition | Resolved: signed mean of body-direction products at 15/30/60-minute scales, used jointly | No window selection by P&L; body magnitude is excluded |
| D-004 | Joint-event definition | Continuous primary; thresholded events secondary | Confirm exact normalization and trailing volatility estimator |
| D-005 | Primary traded instrument | Proposed: MNQ | Confirm availability of execution-quality data and cost assumptions |
| D-006 | Development sample | Resolved for current iteration: 458 complete primary sessions through 2026-05-12 before warm-up | Entire incomplete and roll sessions excluded; weekday imbalance reported |
| D-007 | Final holdout | Unavailable in current files; confirmatory claims prohibited | A future unseen range must be separately acquired and frozen |
| D-008 | Pre-ETP sample start | Unavailable in current files; H4 deferred | Coverage beginning by 2022 remains a future data requirement |
| D-009 | Session definition | Resolved: XNYS 09:30–16:00 ET primary; mandatory 18:00–09:30 ET overnight negative control | Official holidays/early closes; no target or position crosses primary close |
| D-010 | Multiple-testing procedure | TBD | Match procedure to final estimands and dependence structure |
| D-011 | Magnitude coordinates | Resolved: geometric-mean joint intensity and normalized-difference balance | \(M_1\) includes \(J\), \(B\), and \(|B|\); no sign is imposed |
| D-012 | Coherence state estimator | Resolved: nested discrete-time logistic models \(M_0\) and \(M_1\) | Both include common direction; evaluate with Brier score, log loss, and calibration |
| D-013 | Entry/exit thresholds | Deferred to strategy stage | Must be fitted on development folds and frozen before final evaluation |
| D-014 | Historical body-scale estimator | Resolved: same-slot MAD over previous 63 eligible sessions | Separate by asset and resolution; current session excluded; no epsilon or fallback |

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

### 2026-09-17 — causal historical body scale

- The scale is `1.4826 × MAD` of the same session slot over the previous 63 eligible analysis sessions.
- It is estimated separately for BTC and NQ and for one- and five-minute bars.
- The current body is divided by the scale without median-centering, preserving its direction.
- Session slots are DST-aware in `America/New_York`; stored data remains UTC.
- BTC uses the same eligible analysis-session dates and slots as NQ.
- The current session is excluded; completed prior sessions may update later validation or holdout scales online.
- Missing slots extend the search backward until 63 valid observations exist.
- Fewer than 63 observations, zero/non-finite MAD, roll contamination, or known gaps make the observation ineligible.
- No epsilon floor, cross-slot substitution, or future-data fallback is allowed.

### 2026-09-17 — primary cash session and overnight control

- Primary signal bars, targets, and simulated positions use `09:30–16:00 America/New_York` and the official XNYS holiday/early-close calendar.
- Signals are formed after bar close; the earliest primary executions are 09:35 for five-minute bars and 09:31 for one-minute bars.
- Targets and positions must finish by the official session close and are never truncated or carried overnight.
- Causal feature lookbacks may use valid pre-09:30 bars, preserving the market open without expanding primary signal or outcome timestamps.
- The mandatory overnight negative control covers the CME equity-futures period from 18:00 on the prior evening through 09:30 ET.
- Overnight results are separately reported, use the same feature definitions, and cannot select or replace primary parameters or conclusions.
- Weekends, holidays, the CME maintenance break, and unavailable NQ periods are excluded.
- The post-cash period before the maintenance break belongs to neither specification.

### 2026-09-17 — five-minute primary economic horizon

- The primary economic outcome is the signed NQ return over the five minutes immediately following an eligible event.
- The event is known only after its bar closes. Measurement starts at the next tradable open and ends at the open exactly five minutes later; no event-bar close fill is assumed.
- In the five-minute primary specification this is one future open-to-open bar return.
- In the one-minute robustness specification it is the cumulative open-to-open return across five future one-minute bars.
- The cumulative one-minute path at +1, +2, +3, +4, and +5 minutes is a secondary timing diagnostic. It cannot redefine the primary endpoint.
- Fifteen-, thirty-, and sixty-minute open-to-open responses form a prespecified secondary response curve. The most favorable secondary horizon cannot replace the five-minute primary.
- This economic horizon is distinct from the state-persistence label: the latter remains next-bar agreement and therefore spans five minutes in the primary specification but one minute in the robustness specification.

### 2026-09-17 — constrained available-data study

- Research continues on the existing registered files as development-only work; better source data is not assumed to be available.
- An incomplete primary or overnight session is excluded in full. Missing prices are never forward-filled.
- Every session containing an NQ contract transition is excluded in full.
- The deterministic eligibility pass retains 458 primary sessions and 551 overnight sessions before feature warm-up.
- Only 31 Thursdays survive in the primary sample, versus 98–113 sessions for each other weekday. Weekday-specific reporting is mandatory.
- The current range cannot estimate the pre/post-ETP hypothesis and cannot supply a pristine final holdout.
- Walk-forward results may refine or reject the hypothesis but may not support confirmed-alpha or deployment-readiness language.

### 2026-09-17 — state-model walk-forward specification

- The state-model primary metric is event-level Brier score; log loss is secondary and calibration is diagnostic.
- The first 130 feature-ready sessions initialize training; 12 subsequent 22-session blocks are scored out of fold.
- One complete analysis session is purged before every outer and inner validation block.
- Logistic models use fold-local standardization and L2 regularization selected independently for `M0` and `M1` from `C = 0.01/0.1/1/10`.
- Each outer fold uses three trailing, expanding inner validation blocks of 22 sessions; selection minimizes event-weighted inner OOF Brier score.
- Paired `M1 − M0` loss uncertainty uses 5,000 complete-session bootstrap resamples.
- Incremental evidence requires a negative upper 95% Brier-difference bound, directionally consistent log loss, and ECE deterioration no greater than 0.01.
- The primary result meets this development-only rule, but the effect is small and cannot be described as confirmed or tradable without unseen data.

### 2026-09-17 — return-model incremental-value specification

- The return target is the executable next-five-minute NQ log return in basis points, signed by current NQ direction on current BTC–NQ agreement events.
- The first 60 minutes of every cash session are excluded from scoring so all NQ and BTC momentum predictors use complete within-session 5/15/30/60-minute histories.
- NQ-only Ridge uses current NQ direction/magnitude, aligned NQ momentum, two intraday Fourier harmonics, and weekday controls.
- The cross-market Ridge adds aligned BTC momentum, BTC magnitude, coherence, joint intensity, signed magnitude balance, and absolute balance.
- Targets are not globally normalized, clipped, or winsorized.
- Ridge alpha is selected separately inside each outer fold from `0.01/0.1/1/10/100/1000` using three inner purged folds and event-weighted MSE.
- The state-model outer session boundaries and full-session purge are reused exactly.
- Incremental evidence requires a negative upper 95% session-block bound for cross-market-minus-NQ-only squared-error loss and directionally consistent MAE.
- The primary result rejects incremental return-forecast value for the registered cross-market linear model; post-hoc changes require a separately logged trial and cannot replace this result.
