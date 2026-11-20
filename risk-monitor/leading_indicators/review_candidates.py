"""Fail-closed research indicator registry and quarantine decision engine.

Never promotes a signal to the production composite or overwrites raw observations.
All evidence stays on independent research surfaces for audit.
"""
from __future__ import annotations
import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

RESEARCH_BUCKETS = {"CANDIDATE_PRIORITY", "CANDIDATE_SECONDARY", "CONTROL_ONLY", "QUARANTINED", "REJECTED"}
DECISIONS = {"AWAITING_EVIDENCE", "INSUFFICIENT_EVIDENCE", "RESEARCH_HOLD", "QUARANTINE_RESEARCH_ONLY", "REJECTED_BY_VALIDATED_OOS", "REVIEW_ELIGIBLE_NOT_PRODUCTION"}


def finite_number(value: object) -> bool:
    return (isinstance(value, (float, int)) and not isinstance(value, bool)
            and math.isfinite(value))


def gate_horizon(row: dict, policy: dict) -> dict:
    required = policy["requiredEvidence"]
    checks = {
        "sufficientOutOfSample": finite_number(row.get("oosPredictions")) and row["oosPredictions"] >= policy["minOutOfSamplePredictions"],
        "sufficientDownturns": finite_number(row.get("downturnEvents")) and row["downturnEvents"] >= policy["minDownturnEvents"],
        "rmseImproved": finite_number(row.get("rmseReductionPct")) and row["rmseReductionPct"] >= policy["minRmseReductionPct"],
        "dmHacPValid": finite_number(row.get("dmHacPValue")) and 0 <= row["dmHacPValue"] < policy["maxDMHacPValue"],
        "falsePositiveStable": finite_number(row.get("falsePositiveRateDeltaPp")) and row["falsePositiveRateDeltaPp"] <= policy["maxFalsePositiveRateIncreasePp"],
    }
    for flag in required:
        checks[flag] = row.get(flag) is True
    return {"passed": all(checks.values()), "checks": checks}


def classify(indicator: dict, evidence: dict, policy: dict) -> dict:
    identifier = indicator["id"]
    base = {"id": identifier, "name": indicator["name"], "registryBucket": indicator["role"],
            "compositeEligible": False, "promotionPermitted": False}
    if indicator["role"] == "CONTROL_ONLY":
        return {**base, "decision": "RESEARCH_HOLD", "reason": "Existing benchmark, not an additive indicator"}
    if indicator["role"] == "QUARANTINED":
        return {**base, "decision": "QUARANTINE_RESEARCH_ONLY", "reason": indicator["issue"]}
    if indicator["role"] == "REJECTED":
        return {**base, "decision": "REJECTED_BY_VALIDATED_OOS", "reason": indicator["issue"]}
    results = evidence.get(identifier, {})
    if not results:
        return {**base, "decision": "AWAITING_EVIDENCE", "reason": "No validated real OOS results"}
    all_gates, evaluated = {}, []
    for h in (1, 3, 6):
        data = results.get(str(h))
        if not isinstance(data, dict):
            all_gates[str(h)] = {"passed": False, "checks": {}, "reason": "Missing horizon"}
            continue
        if data.get("sourceType") != "ACTUAL_OFFICIAL_DATA":
            all_gates[str(h)] = {"passed": False, "checks": {}, "reason": "Not original verified official data"}
            continue
        outcome = gate_horizon(data, policy)
        all_gates[str(h)] = outcome
        if outcome["passed"]:
            evaluated.append(h)
    # A single horizon may be exploratory evidence but needs additional independent
    # rolling windows, alternate price indices and policy review before any score.
    if evaluated:
        return {**base, "decision": "REVIEW_ELIGIBLE_NOT_PRODUCTION",
                "validatedHorizonCandidates": evaluated, "gates": all_gates,
                "reason": "Some exploratory gates passed; no approval, regime robustness or PIT signoff"}
    all_real = all(str(h) in results and isinstance(results[str(h)], dict)
                   and results[str(h)].get("sourceType") == "ACTUAL_OFFICIAL_DATA" for h in (1, 3, 6))
    if all_real and all(results[str(h)].get("vintagesAvailable") is True for h in (1, 3, 6)):
        return {**base, "decision": "RESEARCH_HOLD", "gates": all_gates,
                "reason": "Validated candidate did not pass additive OOS / false alarm gates"}
    return {**base, "decision": "INSUFFICIENT_EVIDENCE", "gates": all_gates,
            "reason": "Source identity, PIT vintages or validation windows missing"}


def compute(registry: dict, evidence: dict) -> dict:
    policy = registry["decisionThresholds"]
    ids = [row["id"] for row in registry["indicators"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate indicator ID")
    if any(row["role"] not in RESEARCH_BUCKETS for row in registry["indicators"]):
        raise ValueError("Unknown research bucket")
    if not isinstance(evidence, dict):
        raise ValueError("Evidence must be an object")
    if set(evidence) - set(ids):
        raise ValueError("Unregistered evidence IDs: " + ",".join(sorted(set(evidence) - set(ids))))
    rows = [classify(item, evidence, policy) for item in registry["indicators"]]
    return {"schemaVersion": "1.0", "moduleId": "KOR_SEOUL_HOUSING_LEADING_INDICATORS",
            "mode": "RESEARCH_ONLY", "compositeEligible": False,
            "publicCompositeScore": None, "indicatorCount": len(rows),
            "indicators": rows,
            "policy": "A candidate cannot enter the core score via this module. A human must approve an independent contract later."}


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=Path(__file__).with_name("candidates.json"))
    parser.add_argument("--evidence", type=Path, default=root / "research-data" / "leading-indicators" / "performance-evidence.json")
    parser.add_argument("--output", type=Path, default=root / "risk-data" / "leading-indicators" / "review.json")
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    evidence = json.loads(args.evidence.read_text(encoding="utf-8")) if args.evidence.exists() else {}
    result = compute(registry, evidence)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if not args.output.exists() or args.output.read_text(encoding="utf-8") != text:
        args.output.write_text(text, encoding="utf-8")
    buckets = {}
    for row in result["indicators"]:
        buckets[row["decision"]] = buckets.get(row["decision"], 0) + 1
    print(json.dumps({"mode": result["mode"], "decisions": buckets}, ensure_ascii=False))


if __name__ == "__main__":
    main()
