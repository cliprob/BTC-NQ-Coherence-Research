# Provenance and prior work

The research question grew out of earlier collaborative BTC–Nasdaq coursework by Robert Mazurczak and [@AlexSamuseva](https://github.com/AlexSamuseva), followed by several exploratory strategy iterations.

This repository is a clean redesign:

- no earlier notebook result is evidence for a hypothesis here;
- no earlier selected threshold is presumed optimal;
- all previously inspected dates are disclosed when defining development and holdout samples;
- reusable ideas are restated as testable hypotheses rather than inherited as strategy rules;
- earlier implementation code is not copied into the new package.

If prior material is later used for comparison, it must be clearly labeled `legacy/exploratory` and cannot influence a locked final evaluation without a documented protocol deviation.

## Data lineage discovered during the local audit

- The prior coursework checkout points to `AlexSamuseva/Cross-Market-Correlation-Strategy-BTC-NASDAQ-Futures` as its original GitHub remote.
- The registered BTCUSDT USDT-M file was recreated from Binance public monthly and daily archives by a local downloader. The archives are retained locally and the combined file hash is registered.
- The registered NQ file is a local stitched derivative. Its extension through 2026-05-12 is documented as an Interactive Brokers front-month export and was joined with overlap checks.
- The original source exports and front-month selection rule for the NQ base file through 2026-03-06 have not been located. Its provenance is therefore only partial.
- File hashes and audit findings document the current local artifacts; they do not repair missing source lineage or make proprietary rows redistributable.
