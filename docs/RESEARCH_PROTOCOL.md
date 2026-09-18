# Research Protocol

**Protocol version:** 1.0.0

**Status:** COMPLETED DEVELOPMENT RECORD — locked after results; not preregistered

**Created:** 2026-09-17

**Closed:** 2026-09-17

This version freezes what was actually specified, run and reported in the development
study. The freeze is a reproducibility and audit boundary, not a retroactive
preregistration. The inspected data remain ineligible for confirmatory claims.

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

$$
b^i_t = \log\left(\frac{P^{i,close}_t}{P^{i,open}_t}\right).
$$

Wicks and the high-low range are excluded from the primary specification. They may be considered only in a separately labeled robustness analysis after the primary body-based definitions are frozen.

For asset $i$, a causal standardized body is provisionally defined as:

$$
z^i_t = \frac{b^i_t}{\widehat{\sigma}^{i,body}_{t-1}},
$$

where $\widehat{\sigma}^{i,body}_{t-1}$ is the causal, resolution-specific scale defined below. This makes BTC and NQ body magnitudes comparable without using the current body to set its own scale.

Candidate state variables are deliberately separated:

- **directional agreement** $A_t$: whether the BTC and NQ bodies share a sign;
- **coherence** $C_t$: a causal continuous measure of agreement between recent sequences of body directions that excludes body magnitude;
- **joint intensity** $J_t$: the geometric mean of absolute standardized body magnitudes;
- **magnitude balance** $B_t$: the normalized difference between absolute standardized body magnitudes.

Magnitude must not be embedded in $C_t$ and then reused to explain persistence of $C_t$. Keeping state similarity, common intensity, and relative strength separate prevents a partly tautological result.

### 3.1 Directional aggregation and time scales

Per-bar body-direction agreement is:

$$
d_t = \mathrm{sgn}(b^{BTC}_t)\mathrm{sgn}(b^{NQ}_t).
$$

Thus, $d_t=+1$ denotes same-direction bodies, $d_t=-1$ denotes opposite-direction bodies, and an exact doji contributes zero. A missing or invalid body makes the affected rolling window ineligible rather than being treated as disagreement.

For a clock-time scale $K$, directional coherence is the unweighted arithmetic mean:

$$
C_t(K)=\frac{1}{n_K}\sum_{j=0}^{n_K-1}d_{t-j},
$$

where $n_K$ is the number of complete bars spanning $K$. The primary representation uses the three scales $K\in\{15,30,60\}$ minutes together:

$$
\mathbf C_t = [C_t(15), C_t(30), C_t(60)].
$$

Each component remains continuous on $[-1,1]$. No single window is selected by historical performance, and no coherence threshold is imposed at this stage. The windows are defined in clock time so that their meaning is identical in the primary and robustness resolutions.

### 3.2 Causal historical body scale

For asset $i$, resolution $r$, and the DST-aware session slot $s(t)$, define the reference set:

$$
\mathcal H^{i,r}_t =
\left\{
b^{i,r}_{d,s(t)}:
d \in \text{the previous 63 eligible analysis sessions}
\right\}.
$$

The 63 sessions approximate one trading quarter and are fixed by protocol rather than selected by empirical performance. If a slot is missing in a prior session, the search extends backward until 63 valid same-slot observations are available.

Let:

$$
\widetilde b^{i,r}_{t-1}
= \mathrm{median}(\mathcal H^{i,r}_t).
$$

The historical scale is:

$$
\widehat{\sigma}^{i,r}_{t-1}
= 1.4826\,
\mathrm{median}_{x\in\mathcal H^{i,r}_t}
\left|x-\widetilde b^{i,r}_{t-1}\right|.
$$

The current body is divided by this scale without subtracting the historical median, preserving its observed direction. The scale is estimated separately for BTC and NQ and separately for the one- and five-minute resolutions.

Session slots are derived DST-aware in `America/New_York` while stored timestamps remain UTC. BTC uses the same eligible analysis-session dates and slots as NQ rather than its weekend or around-the-clock history.

The current session is excluded from its own scale. During validation or final evaluation, earlier completed sessions from the same evaluation period may update later scales because this information would have been available online; the formula and 63-session lookback remain frozen.

An observation is ineligible if fewer than 63 valid reference bodies exist, the resulting MAD is zero or non-finite, or the body is contaminated by a futures roll, session boundary, or known data gap. No epsilon floor, future-data fallback, or cross-slot substitution is permitted.

### 3.3 Joint intensity and magnitude balance

For each asset, define absolute standardized body magnitude as:

$$
m_t^i = |z_t^i|.
$$

Joint intensity is:

$$
J_t = \sqrt{m_t^{BTC}m_t^{NQ}}.
$$

This symmetric coordinate is zero if either market has no body movement and becomes large only through the combined scale of both moves. It does not designate a leading market.

Magnitude balance is:

$$
B_t = \frac{m_t^{BTC}-m_t^{NQ}}
{m_t^{BTC}+m_t^{NQ}}.
$$

It lies on $[-1,1]$: positive values indicate relatively stronger BTC movement, negative values indicate relatively stronger NQ movement, and zero denotes equal standardized body magnitudes. If both magnitudes are zero, the balance is undefined and the observation is ineligible; no numerical epsilon is introduced.

For an eligible observation with current directional agreement, common direction is retained separately:

$$
S_t = \mathrm{sgn}(b_t^{BTC})
= \mathrm{sgn}(b_t^{NQ}) \in \{-1,+1\}.
$$

The pair $(J_t,B_t)$ separates common event scale from relative strength. The model also receives $|B_t|$, allowing the degree of imbalance to matter independently of which market is relatively stronger.

### 3.4 Baseline and magnitude-conditioned state models

State-model observations require current agreement, $d_t=+1$. The baseline state model is:

$$
M_0: P(d_{t+1}=+1 \mid \mathbf C_t,S_t).
$$

The magnitude-conditioned model is:

$$
M_1: P(d_{t+1}=+1 \mid \mathbf C_t,S_t,J_t,B_t,|B_t|).
$$

Both are discrete-time logistic models fitted only inside the appropriate training fold. Their continuous outputs are next-bar body-direction agreement probabilities conditional on current agreement. $M_1$ tests whether joint intensity and magnitude balance add state-persistence information beyond direction-only coherence and common direction; it does not assume catch-up, reversal, a coefficient sign, or a lead–lag direction.

The primary comparison uses out-of-sample Brier score, log loss, and calibration. Trading P&L is prohibited as a model- or scale-selection criterion. Regularization is selected inside the training/validation process and recorded in the trial ledger.

### 3.5 Bar resolution and construction

The primary specification uses five-minute bars. A one-minute version is a mandatory secondary robustness specification and must be run and reported regardless of whether the primary result is positive, negative, or inconclusive. The one-minute result cannot replace or retroactively redefine the primary result.

Both specifications use the same 15-, 30-, and 60-minute clock-time coherence scales:

| Resolution | 15 minutes | 30 minutes | 60 minutes |
|---|---:|---:|---:|
| Primary: 5-minute bars | 3 bars | 6 bars | 12 bars |
| Robustness: 1-minute bars | 15 bars | 30 bars | 60 bars |

Validated one-minute data is the common source. Five-minute bars are constructed on UTC-aligned boundaries using:

- first valid open;
- maximum high;
- minimum low;
- last valid close;
- summed volume.

A five-minute bin is eligible only when every expected one-minute observation is present and valid under the relevant session calendar. Missing prices are never forward-filled. Session boundaries, futures rolls, and known data gaps cannot be crossed by an aggregated bar.

The five-minute primary reduces timestamp sensitivity and microstructure noise. The one-minute robustness analysis tests whether aggregation conceals a faster relationship; it is secondary even if its point estimate is more favorable.

### 3.6 Session scope and overnight negative control

Primary signal bars, prediction targets, and simulated positions are restricted to the US cash-equity session. The nominal session is `09:30–16:00 America/New_York`, using the official XNYS calendar for holidays and early closes. On an early-close date, the official close replaces 16:00.

Bars use left-closed, right-open intervals. For the five-minute primary, the first cash-session bar is `[09:30,09:35)` and the last full-session bar is `[15:55,16:00)`. A signal may be formed only after a primary-session bar closes. The first possible five-minute execution is therefore 09:35; the one-minute robustness analogue is 09:31.

Every target and simulated position must finish by the official cash-session close. Observations whose target, label, or required exit would cross that close are ineligible rather than truncated. Positions may not be carried overnight.

The causal 15-, 30-, and 60-minute feature lookbacks may include valid bars before 09:30. This preserves information available at the cash open without admitting pre-session signal timestamps or outcomes into the primary sample. Such lookback bars must still pass the same gap, roll, timestamp, and data-quality rules.

The mandatory overnight negative control covers the CME equity-futures session from `18:00` on the prior evening through `09:30 America/New_York`. It excludes the daily CME maintenance interval, weekends, holidays, and unavailable NQ periods. It uses the same feature definitions and is reported regardless of the primary result, but it is evaluated separately and cannot select, alter, or replace primary parameters or conclusions. The post-cash interval from 16:00 until the maintenance break is outside both the primary and overnight specifications.

### 3.7 Primary economic return horizon

Let $\tau_t$ be the boundary at which event bar $t$ has fully closed and its signal becomes observable. Let $O^{NQ}_{\tau_t}$ be the first tradable NQ open at that boundary. The unsigned open-to-open NQ response over $h$ clock minutes is:

$$
R^{NQ}_{t,h}=\log\left(\frac{O^{NQ}_{\tau_t+h}}{O^{NQ}_{\tau_t}}\right).
$$

This timing does not assume a fill at the already observed event-bar close. It represents measurement from the next tradable open after signal formation to the open at the end of the stated horizon.

The primary economic horizon is fixed at $h=5$ minutes for both data resolutions:

| Specification | Event known | Primary measurement | Equivalent bars |
|---|---|---|---:|
| 5-minute primary | after the event bar closes at $\tau_t$ | $O_{\tau_t}$ to $O_{\tau_t+5m}$ | 1 future 5-minute bar |
| 1-minute robustness | after the event bar closes at $\tau_t$ | $O_{\tau_t}$ to $O_{\tau_t+5m}$ | 5 future 1-minute bars |

In the one-minute robustness specification, cumulative responses at +1, +2, +3, +4, and +5 minutes are reported as secondary timing diagnostics. They may describe when a response appears or decays, but they cannot redefine the primary endpoint after inspection.

The 15-, 30-, and 60-minute open-to-open responses form a prespecified secondary response curve. They test persistence, decay, or reversal over longer horizons; no member of that curve may replace the five-minute primary based on observed performance. Every response must end before the applicable official session boundary or the observation is ineligible.

This economic endpoint is distinct from the state-persistence target in Section 3.4. The state model predicts next-bar directional agreement, which spans five minutes in the primary specification and one minute in the robustness specification. By contrast, the primary economic return always spans five clock minutes, preserving the same economic question across resolutions.

For an eligible observation with $d_t=+1$, let $T_t$ denote the number of consecutive future bars for which $d_u=+1$, beginning at $t+1$. This defines agreement-run duration without introducing a coherence threshold. A primary state-dynamics estimand is:

$$
P(T_t \ge k \mid \mathbf C_t, J_t, B_t, d_t=+1).
$$

For economic interpretation, let $S_t$ denote the common detected direction. The signed NQ outcome is:

$$
Y_{t,h} = S_t R^{NQ}_{t,h},
\qquad h\in\{5,15,30,60\}\text{ minutes}.
$$

A positive value denotes continuation in the jointly detected direction and a negative value denotes reversal. Five minutes is the primary horizon; 15, 30, and 60 minutes are secondary. Future observations appear here as outcomes needed to evaluate persistence and tradability; their use does not assert a BTC-to-NQ lead–lag mechanism.

At the later return-prediction stage, the incremental out-of-sample value of the joint state over an NQ-only information set is:

$$
\Delta L_h = L(\widehat r^{NQ\text{-only}}_{t,t+h}) -
L(\widehat r^{NQ+BTC}_{t,t+h}),
$$

evaluated at the primary five-minute horizon and the prespecified secondary horizons. A positive $\Delta L_h$ means the expanded information set reduces forecast loss.

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
3. out-of-sample comparison of the direction-only $M_0$ and magnitude-conditioned $M_1$ state models;
4. event-time response curves across the complete return-horizon set;
5. joint-intensity and magnitude-balance surfaces for regime persistence and within-regime returns;
6. nested out-of-sample return-forecast comparison;
7. separately reported overnight negative control;
8. strategy construction only if predictive evidence warrants it;
9. one final holdout evaluation.

Trading P&L must not be used to select definitions or models during stages 1–7.

## 6. Timing and leakage rules

- A feature timestamped $t$ may use information available through the close of bar $t$, and nothing later.
- The earliest simulated execution based on that feature is the open of bar $t+1$, plus any separately specified latency.
- Volatility estimates, normalizers, quantiles, scalers, models, calibrators, and thresholds are fitted within the appropriate training fold.
- Futures roll transitions, incomplete bars, session boundaries, and material data gaps are explicitly marked and excluded where necessary.
- Fold boundaries are purged by at least the maximum label horizon. Any additional embargo must be specified before the final evaluation.
- Overlapping labels may be used for response estimation only with dependence-aware inference. A trading simulation must enforce its separately declared position policy.
- Primary labels and simulated positions may not cross the official cash-session close; observations are excluded rather than shortened.

## 7. Data requirements

The target dataset should include:

- individual NQ or MNQ futures contracts with one-minute OHLCV and contract identifiers;
- BTC from at least two venues or instrument types for robustness;
- UTC timestamps plus authoritative exchange-calendar metadata;
- sufficient observations before January 2024 for the structural comparison;
- a final period not inspected during protocol or model development.

The existing March 2024–May 2026 data may be used for engineering and exploratory development. It cannot establish a pre/post BTC ETP effect. Because earlier research inspected much of this period, it is not a pristine final holdout for the new study.

### 7.1 Current available-data implementation

The current repository iteration proceeds with the registered local files under an explicit `development-only` constraint. No unavailable row is imputed. A primary or overnight session is eligible only if every expected one-minute BTC and NQ bar is present under its official calendar, and every session containing an NQ contract transition is excluded in full.

After applying those rules, 458 primary XNYS sessions and 551 overnight-control sessions remain before the 63-session feature warm-up. The primary sample is not weekday-balanced: only 31 Thursdays survive, compared with 98–113 sessions for each other weekday. Every empirical result must therefore report weekday-specific stability and may not be generalized as if sessions were missing at random.

The registered range begins after US spot BTC ETP trading started and has already been inspected in previous iterations. Consequently:

- H4 is deferred and cannot be estimated from the current files;
- no result from this range is a pristine final-holdout result;
- walk-forward estimates are development evidence only;
- confirmed-alpha, deployment-readiness, and causal ETF claims are prohibited.

These restrictions are machine-readable in `configs/available_data_study.yaml`. They do not change the mathematical feature definitions or permit selection on future outcomes.

## 8. Models and baselines

The completed study preserved identical sampling and labels for:

1. unconditional next-bar agreement-rate benchmark;
2. $M_0$: discrete-time logistic state model using $C(15),C(30),C(60)$;
3. $M_1$: the same state model expanded with joint intensity and magnitude balance;
4. linear NQ-only autoregressive/Ridge return model;
5. the same return model expanded with BTC/coherence features;
6. an optional constrained nonlinear return model, which was not run after the registered
   linear return comparison failed to show incremental value.

Complexity is justified only by incremental out-of-sample performance, not in-sample fit.

## 9. Evaluation

Reported outputs include:

- event-time response means with complete-session bootstrap intervals;
- out-of-sample $R^2$ and forecast-loss differences;
- Brier score, log loss, and calibration for $M_0$ and $M_1$;
- day- or session-block bootstrap intervals;
- coefficient or response stability across time, direction, session, and venue;
- no gross or net strategy outcomes, because the strategy stage was not opened.

An isolated positive point estimate is not sufficient evidence. Conclusions must account for uncertainty, multiple horizons, model attempts, and the full trial ledger.

## 10. Multiple testing and researcher degrees of freedom

- The five-minute `M1` versus `M0` Brier comparison and five-minute cross-market versus
  NQ-only MSE comparison are primary for their distinct state and return questions.
- Their 95% complete-session bootstrap intervals are unadjusted. No family-wise
  confirmatory error-control claim is made because this is previously inspected
  development data without a pristine holdout.
- One-minute results, 15/30/60-minute horizons, response-surface cells, weekday results,
  coefficients and the overnight analysis are secondary, diagnostic, robustness or
  negative-control outputs. They cannot replace or rescue a primary result.
- All nested model-selection attempts remain in append-preserving trial ledgers, and
  unfavorable primary and control results are reported.
- A future confirmatory study must register its own hypothesis family and error-control
  procedure before opening new data; protocol v1.0.0 does not prescribe that future
  design retroactively.

## 11. Strategy stage

The strategy stage was not opened. The registered linear return comparison supplied no
incremental five-minute cross-market value, and both Ridge models underperformed the fold
training-mean benchmark. Optimizing entry and exit rules on the same inspected sample
would therefore add researcher degrees of freedom without an economic forecasting basis.

The following policies remain ideas for a separately registered future study, not
results or unfinished requirements of this release:

- fixed horizons as transparent benchmarks;
- a coherence-decay exit with separate entry and exit thresholds and confirmation;
- an expected-value exit when predicted incremental return no longer covers estimated costs.

All policies receive identical candidate events and causal execution. Trading MNQ requires an MNQ-specific cost and liquidity model; NQ price behavior cannot silently substitute for MNQ execution quality.

Entry and exit thresholds are intentionally absent. Any future thresholds must be fitted
on development folds, subject to minimum-event constraints, and frozen before a genuinely
new final evaluation.

## 12. Closure and freeze scope

Protocol v1.0.0 is frozen as a **completed development record** because:

1. every decision has a final disposition;
2. the machine-readable YAML agrees with this document;
3. source identities, derived artifacts and trial ledgers are hash-bound;
4. all completed primary, robustness and negative-control analyses are reported;
5. the release tag records an immutable audit boundary.

No final holdout was available or opened, and the study was not preregistered. Therefore
this closure cannot produce confirmatory evidence. Any post-freeze research change
requires a new protocol version and explicit deviation log; any future confirmatory study
requires a separate protocol created before its holdout is inspected.
