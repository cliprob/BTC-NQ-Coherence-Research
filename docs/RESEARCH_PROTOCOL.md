# Research Protocol

**Protocol version:** 0.3.0

**Status:** DRAFT — not preregistered or frozen

**Created:** 2026-09-17

## 1. Motivation

BTC and Nasdaq futures sometimes exhibit candle bodies with the same direction while their volatility-adjusted body magnitudes differ. In this protocol, "candle similarity" refers to the direction of the open-to-close body, not to wick geometry or the full high-low range. The economic motivation is that greater institutional access to crypto may have increased integration with the US risk-asset complex. This motivation does not, by itself, establish a causal ETF effect.

The study asks whether these episodes form persistent conditional co-movement regimes and how joint move intensity and cross-market magnitude balance relate to regime duration and returns realized while a regime remains active. It does not initially assume that BTC leads NQ, that NQ leads BTC, or that the weaker market catches up.

## 2. Research questions

### Primary

Do synchronized, volatility-adjusted BTC and NQ moves form persistent coherence regimes, and how do joint move intensity and cross-market magnitude balance relate to regime duration and returns realized while the regime remains active?

### Secondary

1. Do directionally and structurally coherent BTC–NQ states persist beyond the bar on which they are detected?
2. How are regime duration and within-regime returns related to the strength of the joint move?
3. Does cross-market magnitude balance add information beyond joint intensity, without imposing a catch-up or lead–lag direction?
4. Does a causal decline in coherence identify the end of any continuation effect?
5. Did the frequency, duration, or strength of coherence regimes change after US spot BTC ETP trading began? This is a structural-association question, not initially a causal claim.

## 3. Units and candidate estimands

The primary candle primitive is the signed open-to-close body return, never the raw price difference:

\[
b^i_t = \log\left(\frac{P^{i,close}_t}{P^{i,open}_t}\right).
\]

Wicks and the high-low range are excluded from the primary specification. They may be considered only in a separately labeled robustness analysis after the primary body-based definitions are frozen.

For asset \(i\), a causal standardized body is provisionally defined as:

\[
z^i_t = \frac{b^i_t}{\widehat{\sigma}^{i,body}_{t-1}},
\]

where \(\widehat{\sigma}^{i,body}_{t-1}\) is estimated only from completed bodies preceding bar \(t\). This makes BTC and NQ body magnitudes comparable without using the current body to set its own scale.

Candidate state variables are deliberately separated:

- **directional agreement** \(A_t\): whether the BTC and NQ bodies share a sign;
- **coherence** \(C_t\): a causal continuous measure of agreement between recent sequences of body directions that excludes body magnitude;
- **joint intensity** \(J_t\): a symmetric function such as \(\sqrt{|z^{BTC}_t z^{NQ}_t|}\);
- **magnitude balance** \(B_t\): a signed difference or log-ratio between the absolute standardized body magnitudes.

Magnitude must not be embedded in \(C_t\) and then reused to explain persistence of \(C_t\). Keeping state similarity, common intensity, and relative strength separate prevents a partly tautological result.

Let \(T_t\) denote the remaining duration of a coherence episode detected at \(t\). A primary state-dynamics estimand is a survival probability such as:

\[
P(T_t > k \mid C_t, J_t, B_t).
\]

For economic interpretation, let \(S_t\) denote the common detected direction. A candidate signed NQ outcome is:

\[
Y_{t,h} = S_t \sum_{u=t+1}^{t+h} r^{NQ}_u.
\]

A positive value denotes continuation in the jointly detected direction and a negative value denotes reversal. Future observations appear here as outcomes needed to evaluate persistence and tradability; their use does not assert a BTC-to-NQ lead–lag mechanism.

At the later predictive-model stage, the incremental out-of-sample value of the joint state over an NQ-only information set is:

\[
\Delta L_h = L(\widehat r^{NQ\text{-only}}_{t,t+h})
- L(\widehat r^{NQ+BTC}_{t,t+h}),
\]

evaluated at preregistered horizons \(h\). A positive \(\Delta L_h\) means the expanded information set reduces forecast loss.

## 4. Hypotheses

### H1 — coherence-regime persistence

BTC–NQ states defined by agreement between recent candle-body directions exhibit measurable duration beyond the detection bar. The primary outcome is state survival or remaining duration; signed NQ continuation is a related economic outcome.

### H2 — magnitude-conditioned persistence

Conditional on coherence, joint move intensity and cross-market magnitude balance are associated with the duration of the regime and the distribution of returns realized while it remains active. No sign is prespecified for the magnitude-balance relationship, and causal language is not used.

### H3 — coherence decay

Conditional expected continuation value declines when a causally measured coherence state declines. This hypothesis will be evaluated before using coherence decay as an exit policy.

### H4 — post-ETP regime change

The distribution, duration, or predictive content of coherence episodes differs between appropriately defined pre- and post-ETP samples. Without a defensible identification design, conclusions will use association language only.

### Exploratory outcome — catch-up, continuation, or reversal

Only after estimating the complete magnitude-balance response surface will the study describe whether the data are more consistent with weaker-market catch-up, joint continuation, reversal, or no economically relevant balance effect. This outcome is not a directional confirmatory hypothesis and may not be promoted based on final-period performance.

## 5. Analysis order

The order is binding once the protocol is frozen:

1. data-quality and synchronization audit;
2. descriptive contemporaneous co-movement;
3. event-time response curves across the complete horizon set;
4. joint-intensity and magnitude-balance surfaces for regime survival and within-regime returns;
5. nested out-of-sample forecast comparison;
6. strategy construction only if predictive evidence warrants it;
7. one final holdout evaluation.

Trading P&L must not be used to select definitions during stages 1–4.

## 6. Timing and leakage rules

- A feature timestamped \(t\) may use information available through the close of bar \(t\), and nothing later.
- The earliest simulated execution based on that feature is the open of bar \(t+1\), plus any separately specified latency.
- Volatility estimates, normalizers, quantiles, scalers, models, calibrators, and thresholds are fitted within the appropriate training fold.
- Futures roll transitions, incomplete bars, session boundaries, and material data gaps are explicitly marked and excluded where necessary.
- Fold boundaries are purged by at least the maximum label horizon. Any additional embargo must be specified before the final evaluation.
- Overlapping labels may be used for response estimation only with dependence-aware inference. A trading simulation must enforce its separately declared position policy.

## 7. Data requirements

The target dataset should include:

- individual NQ or MNQ futures contracts with one-minute OHLCV and contract identifiers;
- BTC from at least two venues or instrument types for robustness;
- UTC timestamps plus authoritative exchange-calendar metadata;
- sufficient observations before January 2024 for the structural comparison;
- a final period not inspected during protocol or model development.

The existing March 2024–May 2026 data may be used for engineering and exploratory development. It cannot establish a pre/post BTC ETP effect. Because earlier research inspected much of this period, it is not a pristine final holdout for the new study.

## 8. Models and baselines

The minimum comparison will preserve identical sampling and labels:

1. unconditional or zero-return benchmark;
2. linear NQ-only autoregressive/Ridge model;
3. the same model expanded with BTC/coherence features;
4. a direction-classification analogue if classification is retained;
5. at most one constrained nonlinear model as a robustness test.

Complexity is justified only by incremental out-of-sample performance, not in-sample fit.

## 9. Evaluation

Candidate outputs include:

- event-time mean and median response with simultaneous uncertainty bands;
- out-of-sample \(R^2\) and forecast-loss differences;
- Brier score and calibration if direction probabilities are modeled;
- a nested-model predictive-accuracy test where its assumptions are appropriate;
- day- or session-block bootstrap intervals;
- coefficient or response stability across time, direction, session, and venue;
- gross and net economic outcomes only in the strategy stage.

An isolated positive point estimate is not sufficient evidence. Conclusions must account for uncertainty, multiple horizons, model attempts, and the full trial ledger.

## 10. Multiple testing and researcher degrees of freedom

- One primary outcome, bar interval, horizon, direction, and model comparison must be chosen before freezing.
- Secondary horizons and robustness checks must be labeled as such.
- All attempted specifications must enter an append-only trial ledger.
- Full response surfaces will be reported; only the most favorable cell may not be selected for presentation.
- The final holdout may be opened once, after the code, configuration, and input hashes are frozen.

## 11. Strategy stage

If predictive evidence is sufficient, candidate policies may compare:

- fixed horizons as transparent benchmarks;
- a coherence-decay exit with separate entry and exit thresholds and confirmation;
- an expected-value exit when predicted incremental return no longer covers estimated costs.

All policies receive identical candidate events and causal execution. Trading MNQ requires an MNQ-specific cost and liquidity model; NQ price behavior cannot silently substitute for MNQ execution quality.

## 12. Freeze procedure

The protocol becomes `FROZEN` only when:

1. all entries marked `TBD` in the decision log are resolved;
2. the machine-readable YAML agrees with this document;
3. a git tag records the frozen specification;
4. raw-input identities and hashes are registered;
5. the final-period boundaries are recorded before final-period inspection.

Any post-freeze change requires a new protocol version and an explicit deviation log.
