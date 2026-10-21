# HaR preliminary actual-data backtest — 2026-10-22 KST

**Decision: FAIL / NOT APPROVED / DO NOT MERGE into composite.**

Data source: `risk-data/risk_raw.csv` on default branch, last data retrieval recorded 2026-10-18. Data: KOR quarterly OECD REAL_HPI, PIR_LTA, PTR_LTA 1998-Q1–2026-Q2 (114 observations), BIS CREDIT_GAP_PP 1998-Q1–2026-Q1 (113 observations). DSR also present but excluded from parsimonious specification.

Independent exploratory verification used coordinate-wise exact pinball-loss minimization (0.05 quantile), expanding training window of >=60 rows, and available outcomes at the corresponding origin only. Predictors: 4-quarter real HPI momentum, averaged PIR/PTR gap, BIS credit gap. Target: 4/12-quarter cumulative real HPI percentage change. Historical release vintages **not** accounted for. Quantile solver and baseline should be reproduced with pinned Statsmodels in GitHub Actions before interpreting values as production forecasts.

| horizon | OOS origin count | breaches | breach share | mean pinball loss |
| --- | ---: | ---: | ---: | ---: |
| 4 quarters | 43 | 8 | 18.6% | 1.064 |
| 12 quarters | 27 | 17 | 63.0% | 3.141 |

The 4-quarter and 12-quarter overlapping targets induce serial dependence; do not apply independent Bernoulli coverage inference directly.

Exploratory forecasts using the last jointly available complete predictor origin 2026-Q1: 4-quarter 5th percentile = -3.81% real cumulative return; 12-quarter 5th percentile = +8.93%. **Do not publish these numbers on the production dashboard:** both fail validation. The 12-quarter positive 5th-percentile estimate is especially inconsistent with observed tail exceedances, and requires investigation.

## Mandatory next steps

1. Execute `python -m unittest discover -s har -p 'test_*.py'` and `python har/build_har.py` on actual source files in CI; compare independent solver vs Statsmodels results.
2. Audit data transformations and predictor as-of publication lag; construct observation vintages / point-in-time historical snapshots.
3. Use blocked/rolling temporal cross-validation; compare to unconditional expanding quantile, AR baseline; report both pinball loss and calibration by horizon.
4. Inspect parameter stability, especially during 2008 crisis and 2022–23 housing drawdown. Apply dependence-adjusted uncertainty intervals or block bootstrap.
5. Document Seoul versus nationwide scope; approve scoring transformation and confirm no double-counting with valuation, credit and momentum pillars.
6. Only after gates pass, implement explicit reviewed opt-in promotion from research JSON into risk composite.

**Existing composite stays 43.1 on the last verified published snapshot.**
