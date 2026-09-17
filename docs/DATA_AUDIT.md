# Local Data Audit

**Audit date:** 2026-09-17  
**Registry version:** 0.1.0  
**Scope:** existing local files only; no final holdout was opened or created

## Verdict

The local BTC files are structurally complete over their recorded ranges. The stitched NQ file is syntactically valid and preserves contract identifiers, but it is **not research-ready**: 83 of 545 complete XNYS cash sessions contain missing blocks, for a total of 16,200 absent one-minute bars. The pattern is concentrated on 71 Thursdays and 12 Wednesdays, which is consistent with an acquisition or stitching artifact rather than ordinary exchange closures.

No missing price is to be forward-filled. Reacquisition remains preferable, but the repository now defines a constrained fallback for the data actually available: use only sessions for which every expected BTC and NQ minute is present, exclude the entire session containing a contract transition, and label every result development-only.

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

1. Build the development dataset only from complete sessions under `configs/available_data_study.yaml`.
2. Exclude complete roll-session dates as well as sessions with missing bars; never forward-fill.
3. Report the resulting weekday distribution and all excluded dates in the generated manifest.
4. Treat all inference as post-ETP development evidence, not a pre/post comparison or final holdout result.
5. If better data later becomes available, register it as a new immutable source and rerun the same eligibility layer.

The exact machine-readable findings are in [`data/registry/local_inventory_audit.json`](../data/registry/local_inventory_audit.json). Raw market rows remain outside Git.

## Implemented fallback outcome

The deterministic canonicalization pass retained:

| Role | Candidate sessions | Eligible sessions | Eligible minutes | Excluded sessions |
|---|---:|---:|---:|---:|
| XNYS primary | 545 | 458 | 177,540 | 87 |
| CME overnight negative control | 560 | 551 | 512,430 | 9 |

The primary eligible-session weekday counts are Monday 106, Tuesday 113, Wednesday 98, Thursday 31, and Friday 110. This severe Thursday underrepresentation is an explicit limitation of every analysis using the current data. Results must be shown by weekday and treated as development evidence rather than population-level confirmation.

The synchronized local output contains 746,086 common BTC–NQ minutes with explicit primary and overnight eligibility flags. It is ignored by Git; only its hash, source identities, exclusions, counts, and limitations are committed in [`data/registry/available_data_eligibility.json`](../data/registry/available_data_eligibility.json).
