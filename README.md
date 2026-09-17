# BTC–NQ Coherence Research

An empirical study of whether synchronized, volatility-adjusted Bitcoin and Nasdaq futures moves define persistent cross-market regimes, and whether relative move magnitude contains incremental information about subsequent NQ returns.

> **Research status: Phase 0 — protocol draft.** No model, backtest, result, or alpha claim exists yet. The protocol must be reviewed and frozen before confirmatory analysis begins.

## Research question

The project separates three questions that are often mixed together:

1. **Co-movement:** when do BTC and NQ produce directionally similar, unusually large candles?
2. **Predictability:** does a detected coherence state, or an imbalance in volatility-adjusted move magnitude, contain information about future NQ returns?
3. **Tradability:** if predictive information exists, does it survive causal execution and MNQ trading costs?

The primary hypotheses under consideration are:

- **H1 — regime persistence:** after a strong synchronized BTC–NQ move, directional coherence persists long enough to affect future NQ returns.
- **H2 — magnitude catch-up:** conditional on common direction and high joint intensity, an unusually stronger BTC move predicts a partial subsequent response in NQ.
- **H3 — coherence decay:** after entry, a causal decline in coherence identifies when the expected continuation value has disappeared.

ETF adoption motivates a possible change in market integration, but this project will not infer ETF causality from a simple before/after price comparison.

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

Contemporaneous correlation is not itself a trading signal. A tradable result requires out-of-sample evidence that the detected state persists or predicts a subsequent response.

## Planned research sequence

- [x] Create a clean repository and a machine-readable draft protocol.
- [ ] Review and freeze the research protocol.
- [ ] Build a reproducible data registry and validation layer.
- [ ] Implement normalized candle, joint-intensity, magnitude-imbalance, and coherence measures.
- [ ] Produce descriptive event studies and response curves without strategy optimization.
- [ ] Compare NQ-only and NQ+BTC forecasts with purged walk-forward evaluation.
- [ ] Define entry and exit policies using development data only.
- [ ] Lock the complete specification and open the final holdout once.
- [ ] Publish an academic-style report, including negative or inconclusive results.

See [Research Protocol](docs/RESEARCH_PROTOCOL.md) for the current specification and [Decision Log](docs/DECISIONS.md) for unresolved choices.

## What this project will demonstrate

- causal feature construction and next-bar execution;
- market-calendar, time-zone, session, and futures-roll handling;
- volatility-normalized cross-market candle comparison;
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
