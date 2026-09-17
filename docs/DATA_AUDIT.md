# Local Data Audit

**Audit date:** 2026-09-17  
**Registry version:** 0.1.0  
**Scope:** existing local files only; no final holdout was opened or created

## Verdict

The local BTC files are structurally complete over their recorded ranges. The stitched NQ file is syntactically valid and preserves contract identifiers, but it is **not research-ready**: 83 of 545 complete XNYS cash sessions contain missing blocks, for a total of 16,200 absent one-minute bars. The pattern is concentrated on 71 Thursdays and 12 Wednesdays, which is consistent with an acquisition or stitching artifact rather than ordinary exchange closures.

No missing price is to be forward-filled. The NQ history must be reacquired from a source that preserves individual contract identifiers and complete minute bars, or reconstructed from retained source exports with a documented roll rule and independently verified session coverage.

## Registered inventory

| Dataset | Rows | UTC range | Structural checks | XNYS full-session coverage | Research status |
|---|---:|---|---|---|---|
| Binance BTCUSDT USDT-M perpetual 1m | 1,145,748 | 2024-03-07 23:00 to 2026-05-12 14:47 | pass | 545/545 sessions complete | development BTC candidate |
| Stitched NQ front-month 1m | 746,086 | 2024-03-07 23:00 to 2026-05-12 14:47 | pass | 462/545 sessions complete | engineering only; reacquisition required |
| Legacy Binance BTCUSDT spot 1m | 1,051,201 | 2024-03-07 00:00 to 2026-03-07 00:00 | pass | 501/501 sessions complete | venue-robustness candidate |

Structural checks comprise file identity, timestamp ordering, duplicate timestamps, numeric validity, positive prices, non-negative volume, OHLC invariants, and—where applicable—NQ quarter-tick conformity and non-null contract identifiers. Session coverage is evaluated against the official `NYSE` implementation calendar corresponding to the protocol's `XNYS` cash-session definition, including its holidays and early closes. The generated JSON records the exact calendar-library version.

## NQ findings

- Eight contract transitions are explicitly identifiable: `202406→202409`, `202409→202412`, `202412→202503`, `202503→202506`, `202506→202509`, `202509→202512`, `202512→202603`, and `202603→202606`.
- Several roll transitions contain large unadjusted price gaps. This is acceptable for a raw contract-aware series only if lookbacks, labels, and events crossing the transition are excluded.
- The full-history front-month selection rule is not recorded. The 2026 extension is documented as an IBKR front-month export, while provenance for the earlier base file is incomplete.
- Raw gaps number 568, but that number mixes expected exchange closures with missing data. The calendar comparison isolates 83 incomplete cash sessions and 16,200 genuinely missing primary-session minutes.
- Missing cash-session blocks are systematic rather than isolated. Excluding only affected bars would produce an uneven day-of-week sample, so the current file is not accepted for development inference.

## BTC findings

- The USDT-M futures file matches its retained Binance public archives and downloader provenance.
- Both BTC files have a continuous one-minute timestamp grid over their stored ranges and no structural OHLCV violations.
- The futures file is the stronger primary candidate because its archive-based acquisition is reproducible. The spot file remains a possible venue/instrument robustness check, subject to provenance improvement or reacquisition.
- BTC coverage begins after US spot BTC ETP trading started. It cannot support the protocol's pre/post ETP question.

## Holdout and hypothesis implications

All registered data ends on or before 2026-05-12 and was available during earlier project iterations. None of it is a pristine final holdout. A future final holdout must begin strictly after this exposed period and its boundaries must be committed before inspection.

The existing files also cannot estimate a pre/post January 2024 regime change. That secondary hypothesis requires new BTC and NQ coverage beginning early enough to provide both a pre-ETP sample and the 63-session causal warm-up.

## Required remediation before feature research

1. Reacquire contract-level NQ or MNQ one-minute OHLCV with documented vendor metadata and timestamp semantics.
2. Retain immutable source exports and hashes rather than only a stitched derivative.
3. Register the deterministic front-contract/roll policy; never infer it from future liquidity.
4. Repeat the structural and official-calendar audit and require zero missing primary-session minutes in all retained sessions.
5. Acquire data beginning no later than 2022 if the post-ETP comparison remains in scope.
6. Reserve an unseen period strictly after 2026-05-12; do not inspect it during feature or model development.

The exact machine-readable findings are in [`data/registry/local_inventory_audit.json`](../data/registry/local_inventory_audit.json). Raw market rows remain outside Git.

