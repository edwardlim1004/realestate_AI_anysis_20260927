#!/usr/bin/env python3
"""Promote HaR to dashboard ONLY when independent audit + OOS checks pass.

Runs after the official risk-summary builder; safely repeats on every refresh.
"""
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
VALIDATION = ROOT / "har" / "validation.json"
RESULTS = ROOT / "har" / "results.json"
SUMMARY = ROOT / "risk-data" / "risk_summary.json"
WRAPPER = ROOT / "risk-data.js"


def percentile(values, at):
    if len(values) < 20:
        return None
    return round(100 * sum(x <= at for x in values) / len(values), 1)


def band(score):
    if score >= 80:
        return "RED"
    if score >= 65:
        return "AMBER"
    if score >= 50:
        return "WATCH"
    return "GREEN"


def promote():
    if not VALIDATION.exists() or not RESULTS.exists():
        print("HaR withheld: validation/results missing")
        return False
    validation = json.loads(VALIDATION.read_text(encoding="utf-8"))
    result = json.loads(RESULTS.read_text(encoding="utf-8"))
    if not validation.get("validated"):
        print("HaR withheld: backtest and/or vintage validation incomplete")
        return False
    if result.get("publication") != "RESEARCH_ONLY" or result.get("country") != "KOR":
        raise ValueError("Unexpected HaR research schema/country")
    horizons = result.get("horizons", {})
    if set(horizons) != {"4", "12"}:
        raise ValueError("Both 1-year and 3-year forecasts required")
    scores = []
    projections = {}
    for h in ("4", "12"):
        history = horizons[h]["backtest"]
        latest = horizons[h]["forecast"]
        if not history or not latest:
            raise ValueError("Validated report lacking horizon history/forecast")
        # Lower 5% forecast means larger downside tail risk.
        ordered = [-r["predicted"] for r in history]
        score = percentile(ordered, -latest["real_price_change_pct"])
        if score is None:
            raise ValueError("At least 20 historical out-of-sample forecasts required")
        scores.append(score)
        projections[{"4": "1Y", "12": "3Y"}[h]] = {
            "value": latest["real_price_change_pct"],
            "period": latest["origin"],
            "percentile_risk": score,
            "backtest_n": len(history),
        }
    har_score = round(mean(scores), 1)
    payload = json.loads(SUMMARY.read_text(encoding="utf-8"))
    target = payload["countries"]["KOR"]
    tile = target["tiles"]["har"]
    tile.update({
        "score": har_score, "status": "OK", "value": projections,
        "calculation": "IMF-inspired 5% quantile forecasts (4/12 quarters): equal-weight expanding OOS empirical percentiles of inverted downside forecasts.",
        "limitations": "Empirical historical tail risk rank, NOT the probability of price decline. National-level; release-vintage audit recorded.",
        "validation": validation,
    })
    comp = target["composite"]
    # Recompute from available pillar scores, not just append a number.
    pillars = [t["score"] for t in target["tiles"].values()
               if t.get("status") == "OK" and isinstance(t.get("score"), (float, int))]
    if len(pillars) < 4:
        raise ValueError("Not enough validated risk pillars")
    comp.update({
        "score": round(mean(pillars), 1),
        "state": band(mean(pillars)),
        "coverage": f"{len(pillars)}/6",
        "meaning": "검증된 가격평가·신용·모멘텀·HaR 역사위험백분위 동일가중",
    })
    # Historic aggregate backfill is not performed without vintaged point-in-time
    # projections; clear old composite history to prevent conflicting chart values.
    target["history"] = []
    payload["method"]["composite"] = "Equal mean of validated and available pillars; HaR included only after audit"
    payload["method"]["note"] += " HaR history withheld pending vintage-by-vintage reconstitution."
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    SUMMARY.write_text(text, encoding="utf-8")
    WRAPPER.write_text("const RISK_MONITOR_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print("HaR promoted after approval:", har_score, comp["score"])
    return True


if __name__ == "__main__":
    promote()
