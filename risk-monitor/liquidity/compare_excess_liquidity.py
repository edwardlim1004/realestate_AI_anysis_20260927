#!/usr/bin/env python3
"""Compare actual excess-money proxies on identical historical OOS origins.

Research-only. Data are latest-revised official cache, NOT publication vintages.
Never changes risk-data/liquidity/validation.json or promotion.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import audit_evidence as audit

ROOT = Path(__file__).resolve().parents[2]
LIQ_DIR = ROOT / "risk-data" / "liquidity"
MIN_PERCENTILE_HISTORY = 20


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def month_key(quarter: str, ordinal: int) -> str:
    year, q = quarter.split("-Q")
    return f"{year}{(int(q) - 1) * 3 + ordinal:02d}"


def quarterly_m2(rows: list[dict]) -> dict[str, float]:
    monthly = {row["Period"]: float(row["Value"]) for row in rows
               if row.get("Series") == "M2" and float(row["Value"]) > 0}
    result = {}
    for period in sorted({audit.quarter_add(f"{m[:4]}-Q{(int(m[4:]) - 1)//3+1}", 0)
                          for m in monthly}):
        months = [month_key(period, j) for j in (1, 2, 3)]
        if all(m in monthly for m in months):
            result[period] = sum(monthly[m] for m in months) / 3.0
    return result


def yoy_spread(m2: dict[str, float], gdp: dict[str, float]) -> dict[str, float]:
    """Excess monetary growth in log pp: 100*(delta4 log M2 - delta4 log NGDP).

    Year-over-year nominal GDP growth avoids comparing unadjusted adjacent quarters.
    Quarterly M2 is a 3-month average and GDP is a quarterly nominal flow.
    """
    spread = {}
    for q in sorted(m2):
        q_4 = audit.quarter_add(q, -4)
        if all(v is not None and math.isfinite(v) and v > 0
               for v in (m2.get(q), m2.get(q_4), gdp.get(q), gdp.get(q_4))):
            spread[q] = 100.0 * (math.log(m2[q] / m2[q_4])
                                  - math.log(gdp[q] / gdp[q_4]))
    return spread


def smooth_spread(spread: dict[str, float], window: int = 4) -> dict[str, float]:
    smoothed = {}
    for q in sorted(spread):
        terms = [spread.get(audit.quarter_add(q, -i)) for i in range(window)]
        if all(item is not None for item in terms):
            smoothed[q] = sum(terms) / window
    return smoothed


def historical_percentile(spread: dict[str, float], min_n: int = 20) -> dict[str, float]:
    history, ranked = [], {}
    for q in sorted(spread):
        x = spread[q]
        history.append(x)
        if len(history) >= min_n:
            ranked[q] = 100.0 * sum(v <= x for v in history) / len(history)
    return ranked


def evaluate(hpi: dict[str, float], scores: dict[str, float], horizon: int) -> dict:
    raw = audit.oos(hpi, scores, horizon)
    return {key: raw[key] for key in (
        "horizonQuarters", "outOfSampleCount", "firstOrigin", "lastOrigin",
        "rmseLinearPctPoints", "rmseMeanPctPoints", "mseSkill"
    )}


def build_report(raw_rows: list[dict], risk_rows: list[dict], dashboard: dict) -> dict:
    m2 = quarterly_m2(raw_rows)
    gdp = {row["Period"]: float(row["Value"]) for row in raw_rows
           if row.get("Series") == "NOMINAL_GDP" and float(row["Value"]) > 0}
    spread = yoy_spread(m2, gdp)
    smooth = smooth_spread(spread)
    ranks = historical_percentile(spread, MIN_PERCENTILE_HISTORY)

    old = {item["period"]: float(item["score"]) for item in dashboard["history"]}
    marshall = {item["period"]: float(item["components"]["marshallKGap"]["score"])
                for item in dashboard["history"]}
    cutoff = set(old)
    proxies = {
        "currentLiquidityComposite": old,
        "existingMarshallK": marshall,
        "excessMoneyGrowth": {q: v for q, v in spread.items() if q in cutoff},
        "excessMoneyGrowth4QuarterMean": {q: v for q, v in smooth.items() if q in cutoff},
        "excessMoneyGrowthExpandingPercentile": {q: v for q, v in ranks.items() if q in cutoff},
    }
    for name, scores in proxies.items():
        if set(scores) != cutoff:
            raise ValueError(f"Comparison samples differ for {name}, missing {sorted(cutoff-set(scores))}")

    hpi = {row["Period"]: float(row["Value"]) for row in risk_rows
           if all(row.get(k) == v for k, v in
                  (("Provider", "OECD"), ("Indicator", "REAL_HPI"),
                   ("Country", "KOR"), ("Frequency", "Q")))
           and float(row["Value"]) > 0}
    results = {}
    for name, score in proxies.items():
        results[name] = {"fourQuarters": evaluate(hpi, score, 4),
                         "eightQuarters": evaluate(hpi, score, 8)}
    for horizon_key in ("fourQuarters", "eightQuarters"):
        reference = results["currentLiquidityComposite"][horizon_key]
        for name, output in results.items():
            test = output[horizon_key]
            if (test["outOfSampleCount"], test["firstOrigin"], test["lastOrigin"]) != (
                reference["outOfSampleCount"], reference["firstOrigin"], reference["lastOrigin"]
            ):
                raise ValueError(f"Misaligned OOS origin for {name}/{horizon_key}")
            if not math.isclose(test["rmseMeanPctPoints"], reference["rmseMeanPctPoints"], abs_tol=1e-6):
                raise ValueError(f"Inconsistent baseline for {name}/{horizon_key}")

    latest = max(spread)
    reference = audit.quarter_add(latest, -4)
    return {
        "method": "Revised-data pseudo-OOS; fixed lag=2 quarters; expanding OLS vs matured-label expanding mean; fixed common score quarters",
        "status": "RESEARCH_ONLY_NOT_ELIGIBLE_FOR_PROMOTION",
        "proxies": {
            "currentLiquidityComposite": "Existing 50/30/20 liquidity SHADOW score",
            "existingMarshallK": "Original one-sided-HP/expanding-percentile Marshall-K component",
            "excessMoneyGrowth": "100*[ln(M2q/M2q-4)-ln(GDPq/GDPq-4)]; raw annual excess monetary growth, log percent points",
            "excessMoneyGrowth4QuarterMean": "Trailing 4-quarter average of excessMoneyGrowth",
            "excessMoneyGrowthExpandingPercentile": "Expanding historical percentile of excessMoneyGrowth with >=20 observations",
        },
        "sourceCoverage": {
            "threeMonthAverageM2QuarterCount": len(m2),
            "nominalGDPQuarterCount": len(gdp),
            "excessMoneyGrowthQuarterCount": len(spread),
            "commonScoreQuarterCount": len(old),
            "realtimePublicationVintagesVerified": False,
        },
        "latestObservation": {
            "period": latest,
            "m2LogYoYGrowthPctPoints": round(100 * math.log(m2[latest] / m2[reference]), 6),
            "nominalGdpLogYoYGrowthPctPoints": round(100 * math.log(gdp[latest] / gdp[reference]), 6),
            "excessMoneyGrowthLogPctPoints": round(spread[latest], 6),
            "excessMoneyGrowth4QuarterMeanLogPctPoints": round(smooth[latest], 6),
        },
        "results": results,
        "interpretationLimits": [
            "Comparison is retrospective, using latest-revised money/GDP/HPI data rather than each forecast date's release vintage.",
            "M2-to-GDP growth is not an excess money-demand residual; structural money demand and velocity are unmodeled.",
            "Nominal GDP is sensitive to export prices and profit shocks; its rapid growth may lower the ratio without a cash contraction.",
            "Four-quarter and eight-quarter returns overlap; OOS counts are small and no confidence intervals are claimed.",
            "An 8-quarter-only advantage found after testing multiple variants is exploratory and does not authorize score promotion.",
            "Higher excess money can lead to house-price appreciation, not automatically higher crash risk.",
        ]
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="Assert committed comparison report matches current source data")
    args = parser.parse_args()
    data = build_report(read_csv(LIQ_DIR / "raw.csv"),
                        read_csv(ROOT / "risk-data" / "risk_raw.csv"),
                        json.loads((LIQ_DIR / "summary.json").read_text(encoding="utf-8-sig")))
    if args.check:
        saved = json.loads((LIQ_DIR / "excess_liquidity_comparison.json").read_text(encoding="utf-8"))
        if data != saved:
            raise AssertionError("Committed excess-money comparison differs from ECOS/OECD source snapshot")
        print("EXCESS_LIQUIDITY_COMPARISON_REPRODUCED")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    assert data["status"] == "RESEARCH_ONLY_NOT_ELIGIBLE_FOR_PROMOTION"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
