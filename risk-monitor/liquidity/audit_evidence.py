#!/usr/bin/env python3
"""Fail-closed liquidity evidence audit using committed ECOS/OECD snapshots.

Exploratory revised-data pseudo-OOS test: NEVER treats retrospective data as
point-in-time publication vintages. Does not authorize production activation.
Standard library only; no network requests or credentials.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "risk-data" / "liquidity"
VERSION = "exploratory-oos-v1"
HORIZONS = (4, 8)
SCORE_PUBLICATION_LAG_QUARTERS = 2
OUTCOME_PUBLICATION_LAG_QUARTERS = 1
MIN_TRAIN = 12
MIN_TEST = {4: 30, 8: 24}
MIN_MSE_SKILL = 0.05


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def quarter_index(period: str) -> int:
    year, q = period.split("-Q")
    if len(year) != 4 or int(q) not in (1, 2, 3, 4):
        raise ValueError(f"Invalid quarterly period: {period}")
    return int(year) * 4 + int(q) - 1


def quarter_add(period: str, step: int) -> str:
    number = quarter_index(period) + step
    return f"{number // 4:04d}-Q{number % 4 + 1}"


def f(value: object) -> float | None:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def oos(hpi: dict[str, float], scores: dict[str, float], horizon: int) -> dict:
    # A signal for quarter t is first used at t+2. Outcome for t+h enters
    # training at t+h+1, preventing future-label leakage.
    eligible = []
    for period, level in sorted(hpi.items()):
        x = scores.get(quarter_add(period, -SCORE_PUBLICATION_LAG_QUARTERS))
        future = hpi.get(quarter_add(period, horizon))
        if x is not None and future is not None and level > 0 and future > 0:
            eligible.append({
                "origin": period, "origin_index": quarter_index(period),
                "signal_quarter": quarter_add(period, -SCORE_PUBLICATION_LAG_QUARTERS),
                "score": x, "actual_log_pct": 100 * math.log(future / level),
            })
    predictions = []
    for point in eligible:
        training = [
            item for item in eligible
            if item["origin_index"] + horizon + OUTCOME_PUBLICATION_LAG_QUARTERS
            <= point["origin_index"]
        ]
        if len(training) < MIN_TRAIN:
            continue
        mx = sum(item["score"] for item in training) / len(training)
        my = sum(item["actual_log_pct"] for item in training) / len(training)
        xx = sum((item["score"] - mx) ** 2 for item in training)
        xy = sum((item["score"] - mx) * (item["actual_log_pct"] - my) for item in training)
        slope = xy / xx if xx > 1e-12 else 0.0
        predictions.append({
            "horizon_quarters": horizon, "origin_quarter": point["origin"],
            "signal_quarter": point["signal_quarter"],
            "liquidity_score": round(point["score"], 4),
            "actual_log_pct": round(point["actual_log_pct"], 8),
            "linear_prediction": round(my + slope * (point["score"] - mx), 8),
            "mean_baseline": round(my, 8), "mature_training_n": len(training),
        })
    def mse(key: str) -> float | None:
        if not predictions:
            return None
        return sum((item[key] - item["actual_log_pct"]) ** 2 for item in predictions) / len(predictions)

    mse_linear, mse_mean = mse("linear_prediction"), mse("mean_baseline")
    skill = 1 - mse_linear / mse_mean if mse_mean is not None and mse_mean > 0 else None
    return {
        "horizonQuarters": horizon,
        "eligibleOrigins": len(eligible),
        "outOfSampleCount": len(predictions),
        "firstOrigin": predictions[0]["origin_quarter"] if predictions else None,
        "lastOrigin": predictions[-1]["origin_quarter"] if predictions else None,
        "rmseLinearPctPoints": round(math.sqrt(mse_linear), 6) if mse_linear is not None else None,
        "rmseMeanPctPoints": round(math.sqrt(mse_mean), 6) if mse_mean is not None else None,
        "mseSkill": round(skill, 6) if skill is not None else None,
        "requiredN": MIN_TEST[horizon],
        "minimumRequiredMseSkill": MIN_MSE_SKILL,
        "negativeReturns": sum(item["actual_log_pct"] < 0 for item in predictions),
        "predictions": predictions,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true", help="Persist reproducible audit artifacts")
    args = p.parse_args()
    summary_path = DIR / "summary.json"
    risk_path = ROOT / "risk-data" / "risk_raw.csv"
    vintages_path = DIR / "score_vintages.csv"
    revisions_path = DIR / "revision_history.csv"
    report_path = DIR / "backtest.json"
    predictions_path = DIR / "backtest_predictions.csv"
    if not summary_path.exists() or not risk_path.exists():
        raise SystemExit("Missing committed liquidity summary or OECD official data")
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    scores = {item["period"]: f(item.get("score")) for item in summary.get("history", [])}
    scores = {k: v for k, v in scores.items() if v is not None}
    hpi = {}
    official = []
    for item in read_csv(risk_path):
        if (item.get("Provider"), item.get("Indicator"), item.get("Country"),
                item.get("Frequency")) != ("OECD", "REAL_HPI", "KOR", "Q"):
            continue
        value = f(item.get("Value"))
        if value is not None and value > 0:
            hpi[item["Period"]] = value
            official.append((item["Period"], value, item.get("Observation_Key")))
    vintages = read_csv(vintages_path)
    revisions = read_csv(revisions_path)
    tests = [oos(hpi, scores, h) for h in HORIZONS]
    score_hash = summary.get("validation", {}).get("signalFingerprint")
    dependency = {
        "version": VERSION, "signalFingerprint": score_hash,
        "target": sorted(official),
        "vintages": [
            (r.get("GeneratedUTC"), r.get("SignalFingerprint"), r.get("DataThrough"))
            for r in vintages
        ],
        "revisions": [
            (r.get("ChangeID"), r.get("ObservationKey"), r.get("OldValue"), r.get("NewValue"))
            for r in revisions
        ],
    }
    source_hash = hashlib.sha256(json.dumps(dependency, sort_keys=True).encode()).hexdigest()
    previous = {}
    if report_path.exists():
        previous = json.loads(report_path.read_text(encoding="utf-8-sig"))
    unchanged = previous.get("sourceFingerprint") == source_hash
    timestamp = previous.get("updatedAtUTC") if unchanged else datetime.now(timezone.utc).isoformat(timespec="seconds")
    predictive_pass = all(
        t["outOfSampleCount"] >= MIN_TEST[t["horizonQuarters"]]
        and t["mseSkill"] is not None and t["mseSkill"] >= MIN_MSE_SKILL
        for t in tests
    )
    # Vintage is a distinct real provider-published dataset snapshot, not a
    # six-times re-run of today's history. Genuine revisions require timestamped
    # archived original values and matching periods.
    actual_vintage_count = len({(v.get("GeneratedUTC"), v.get("SignalFingerprint")) for v in vintages
                                if v.get("GeneratedUTC") and v.get("SignalFingerprint")})
    revision_count = len(revisions)
    gate_vintage = "INSUFFICIENT_VINTAGES"  # Never auto-pass from a revision-less snapshot log.
    gates = {
        "predictiveBacktest": {
            "status": "PASS" if predictive_pass else "FAIL",
            "detail": "Revised-data pseudo-out-of-sample linear model vs expanding-mean baseline; two-quarter signal lag, matured labels only; NOT a genuine real-time vintage test.",
        },
        "revisionStability": {
            "status": gate_vintage,
            "detail": "At least six independently archived real ECOS publication vintages with per-observation revisions are required; generated score fingerprints alone do not prove stability.",
        },
        "humanReview": {
            "status": "NOT_APPROVED",
            "detail": "Technical audit recommends HOLD: OOS forecast skill, revisions, release-date leakage, seasonality and credit overlap require independent human signoff.",
        },
    }
    report = {
        "schemaVersion": "1.1", "methodVersion": VERSION, "updatedAtUTC": timestamp,
        "sourceFingerprint": source_hash, "signalFingerprint": score_hash,
        "data": {"ecOSScoreQuarters": len(scores), "oeCDRealHpiQuarters": len(hpi),
                 "savedDerivedScoreSnapshots": actual_vintage_count, "verifiedProviderVintages": 0,
                 "observedRevisionEvents": revision_count,
                 "realtimeVintagesVerified": False},
        "protocol": {
            "target": "100*log(real_hpi[t+h]/real_hpi[t])",
            "horizonsQuarters": list(HORIZONS),
            "signalLagQuarters": SCORE_PUBLICATION_LAG_QUARTERS,
            "outcomeLabelLagQuarters": OUTCOME_PUBLICATION_LAG_QUARTERS,
            "minimumMatureTrainingOrigins": MIN_TRAIN,
            "baseline": "expanding historical mean of matured labels",
            "model": "expanding historical univariate OLS of matured future returns on lagged liquidity scores",
            "metric": "MSE skill = 1 - MSE(model)/MSE(baseline)",
            "limitation": "Historical raw inputs are the latest revised values, not original publication vintages. Quarterly outcomes overlap; errors and small samples are not independent evidence of significance.",
        },
        "horizons": [{k: v for k, v in item.items() if k != "predictions"} for item in tests],
        "gates": gates,
        "review": {
            "decision": "HOLD_SHADOW",
            "automaticPromotionAuthorized": False,
            "observations": [
                "The liquidity score has no demonstrated incremental forecasting advantage at both horizons.",
                "Source series may have retrospective revisions not represented in the sole saved score snapshot.",
                "Quarterly GDP, CPI and M2 release calendars need as-of validation; a two-quarter lag reduces but does not eliminate revision bias.",
                "Marshall K ratios using nominal GDP times four warrant seasonality and denominator-unit cross-check.",
                "Liquidity is not synonymous with a house-price crash probability; check overlap with the credit pillar.",
                "An external qualified human must explicitly review before activation.",
            ],
        },
    }
    if args.write:
        if not unchanged or not report_path.exists() or not predictions_path.exists():
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            fields = ["horizon_quarters", "origin_quarter", "signal_quarter", "liquidity_score",
                      "actual_log_pct", "linear_prediction", "mean_baseline", "mature_training_n"]
            with predictions_path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                for result in tests:
                    writer.writerows(result["predictions"])
    print(json.dumps({
        "horizons": report["horizons"], "gates": gates,
        "vintages": actual_vintage_count, "revisions": revision_count,
        "written": args.write, "unchanged": unchanged,
    }, ensure_ascii=False, indent=2))
    assert gates["revisionStability"]["status"] != "PASS"
    assert gates["humanReview"]["status"] != "PASS"
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
