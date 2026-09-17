# Decision Log

This file records research degrees of freedom before the protocol is frozen. `TBD` means no choice has been made and no confirmatory result may be produced from that choice.

| ID | Decision | Current state | Evidence required before freeze |
|---|---|---|---|
| D-001 | Primary bar interval | Proposed: 5 minutes | Synchronization and microstructure audit; 1-minute retained as robustness |
| D-002 | Primary forecast horizon | TBD | Economic mechanism and development-only response study; must be chosen without final P&L |
| D-003 | Coherence definition | Metric TBD; restricted to direction and normalized shape | Compare a small declared family on stability and interpretability; magnitude is excluded |
| D-004 | Joint-event definition | Continuous primary; thresholded events secondary | Confirm exact normalization and trailing volatility estimator |
| D-005 | Primary traded instrument | Proposed: MNQ | Confirm availability of execution-quality data and cost assumptions |
| D-006 | Development sample | Existing data through 2026-05-12 may be exploratory | Register exact file hashes and prior exposure |
| D-007 | Final holdout | TBD and unopened | Boundaries must be committed before data inspection |
| D-008 | Pre-ETP sample start | Proposed: 2022-01-01 | Confirm consistent BTC and futures coverage |
| D-009 | Session definition | Proposed: US cash hours primary | Specify overnight and weekend negative controls |
| D-010 | Multiple-testing procedure | TBD | Match procedure to final estimands and dependence structure |
| D-011 | Magnitude-balance representation | TBD: signed difference or log-ratio of absolute standardized moves | Compare numerical stability and interpretability without selecting on final P&L |

## Recorded decisions

### 2026-09-17 — clean redesign

- The new repository will not copy code, selected parameters, or empirical results from the prior strategy project.
- Contemporaneous agreement is treated as a detected market state, not automatically as a prediction.
- Predictive value must be measured as an increment over a comparable NQ-only information set.
- Trading rules will be considered only after descriptive and predictive stages.

### 2026-09-17 — magnitude without an assumed lead–lag direction

- H2 is `magnitude-conditioned persistence`, not `magnitude catch-up`.
- Coherence measures direction and normalized candle shape; it must exclude joint intensity and magnitude balance.
- Joint intensity measures how strong the common move is.
- Magnitude balance measures relative BTC–NQ move strength without assuming which market leads.
- Catch-up, continuation, reversal, and no balance effect are competing exploratory outcomes.
- Future observations are outcomes for persistence and tradability tests, not evidence that BTC is assumed to lead NQ.
