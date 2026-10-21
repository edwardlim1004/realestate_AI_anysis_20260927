# 3-year HaR bias diagnosis and benchmark rerun (2026-10-22)

## Root cause
The expanding-window 5% linear conditional-quantile model has severe 12-quarter undercoverage (17/27 = 63.0%) in the exploratory earlier test. Long-horizon returns overlap, the Korean sample is short, and the historical housing regime shifted after 2021. Thus **shifting the intercept manually is not a statistically justified fix**. A positive estimated 5th percentile (+8.93%) despite observed negative forward returns is a conspicuous symptom, not a forecast to publish.

## Independent benchmark, real KOR OECD price series
Recomputed the **expanding unconditional empirical 5% quantile** at each origin using only returns fully observed by that origin (60 or more training targets).

| Horizon | Number of out-of-sample origins | Breaches | Breach ratio | Average pinball loss |
|--|--:|--:|--:|--:|
| 4 quarters | 47 | 5 | 10.64% | 0.8101 |
| 12 quarters | 31 | 14 | 45.16% | 3.1988 |

The unconditional benchmark's 12-quarter calibration is also poor. The original and benchmark backtest samples differ because the conditional model additionally requires predictors; **pinball losses must not be compared as if measured on identical origins**. `build_har.py` now evaluates both on identical origin samples when next executed.

Latest full price-series unconditional quantiles, as illustrative, not production-ready: 4-quarter -6.17%, 12-quarter -13.09% (both revised-data historical estimates, not approved conditional forecasts).

## Correct methodological path
1. Define a fully time-aligned information set (availability/release vintage for OECD and BIS predictors).
2. Keep unconditional lower-tail benchmark and conditional quantile candidate side by side on the exact same forecast origins. Record each individual breach and pinball loss.
3. Make proper blocked/rolling evaluation with forecasts whose realized target matured; for a 12-quarter horizon, avoid random shuffles and count dependence in effective sample.
4. Prefer the least complex model demonstrably improving *out-of-sample* calibration and loss; no coefficient/intercept chosen by peeking into held-out periods.
5. If no model meets threshold, display `INSUFFICIENT_VALIDATION`, not a percentage estimate or a composite score. Consider pooling panel data across comparable regions/countries after confirming index and methodology comparability.
6. Preserve existing 43.1 score until a new independently reviewed release.

## Current status
Added equal-origin benchmark and explicit `calibration_pass` diagnostics to research branch. GitHub Actions execution and complete vintage checks remain pending; PR stays draft. No production release.
