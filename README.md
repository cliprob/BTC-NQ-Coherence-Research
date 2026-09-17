# BTC–NQ Coherence Research

An empirical study of whether synchronized, volatility-adjusted Bitcoin and Nasdaq futures moves define persistent cross-market regimes, and how joint move intensity and cross-market magnitude balance relate to regime duration and returns realized while the regime remains active.

> **Research status: Phase 0 — protocol draft.** No model, backtest, result, or alpha claim exists yet. The protocol must be reviewed and frozen before confirmatory analysis begins.

## Research question

The project separates three questions that are often mixed together:

1. **Co-movement:** when do BTC and NQ produce same-direction candle bodies, and how large are those bodies relative to each market's own recent volatility?
2. **State dynamics:** do joint move intensity and magnitude balance contain information about coherence duration and returns realized during the active regime?
3. **Tradability:** if predictive information exists, does it survive causal execution and MNQ trading costs?

The primary hypotheses under consideration are:

- **H1 — regime persistence:** synchronized BTC–NQ states exhibit measurable duration beyond the detection bar.
- **H2 — magnitude-conditioned persistence:** joint move intensity and cross-market magnitude balance are associated with coherence duration and with returns realized while the regime remains active.
- **H3 — coherence decay:** after entry, a causal decline in coherence identifies when the expected continuation value has disappeared.

The hypotheses do not assume that BTC leads NQ or that the weaker market must catch up. Catch-up, continuation, reversal, or no magnitude-balance effect are competing exploratory outcomes.

ETF adoption motivates a possible change in market integration, but this project will not infer ETF causality from a simple before/after price comparison.

## Agreed coherence representation

For each bar, the BTC and NQ candle-body directions are multiplied to obtain `+1` for agreement, `-1` for disagreement, and `0` for an exact doji. Coherence is the arithmetic mean of this signed agreement over three clock-time scales: **15, 30, and 60 minutes**.

All three continuous measures are used together. No historically best window is selected. Conditional on current body-direction agreement, a discrete-time logistic model produces a next-bar agreement probability from the three scales. A second nested model adds joint body intensity and body-magnitude balance to test whether magnitude improves state-persistence estimates. Model comparison uses Brier score, log loss, and calibration—not trading P&L.

No entry or exit threshold is defined during the state-research stage. Thresholds belong exclusively to a later strategy stage.

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

## Planned research sequence

- [x] Create a clean repository and a machine-readable draft protocol.
- [ ] Review and freeze the research protocol.
- [ ] Build a reproducible data registry and validation layer.
- [ ] Implement the agreed 15/30/60-minute body-direction coherence representation, body-based joint intensity, and body-magnitude balance.
- [ ] Produce descriptive event studies and response curves without strategy optimization.
- [ ] Compare NQ-only and NQ+BTC forecasts with purged walk-forward evaluation.
- [ ] Define entry and exit policies using development data only.
- [ ] Lock the complete specification and open the final holdout once.
- [ ] Publish an academic-style report, including negative or inconclusive results.

See [Research Protocol](docs/RESEARCH_PROTOCOL.md) for the current specification and [Decision Log](docs/DECISIONS.md) for unresolved choices.

## What this project will demonstrate

- causal feature construction and next-bar execution;
- market-calendar, time-zone, session, and futures-roll handling;
- volatility-normalized cross-market candle-body comparison;
- event studies, conditional response surfaces, and uncertainty estimates;
- incremental forecast evaluation: NQ-only versus NQ+BTC;
- walk-forward validation, multiple-testing control, and honest holdout use;
- separation of statistical predictability from economic tradability.

## What this project does not claim

- that contemporaneous BTC–NQ correlation is alpha;
- that spot BTC or ETH ETPs caused any observed relationship;
- that a profitable backtest implies live-trading readiness;
- that a parameter is optimal because it maximized one historical sample.

## Data policy

Raw market data is not committed. The repository will contain schemas, checksums, download instructions for redistributable sources, and synthetic fixtures. Proprietary NQ data must remain local. See [data/README.md](data/README.md).

## Development setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m btc_nq_coherence.protocol configs/research_protocol.yaml
pytest
```

## Repository structure

```text
configs/                  machine-readable research specifications
data/                     schemas and local-data instructions, not raw data
docs/                     protocol, provenance, and decision log
src/btc_nq_coherence/     validated research code
tests/                    unit and integration tests
```

## Provenance

This is a clean research redesign motivated by earlier collaborative coursework with [@AlexSamuseva](https://github.com/AlexSamuseva). Earlier notebooks and their results are not treated as evidence for this study and will not be copied into this repository. See [Provenance](docs/PROVENANCE.md).

No license has been selected yet.
