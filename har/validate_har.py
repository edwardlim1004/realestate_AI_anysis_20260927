#!/usr/bin/env python3
"""Conservative automatic HaR validation. Fails closed."""
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "har" / "validation.json"
RESULT = ROOT / "har" / "results.json"
VINTAGE_PROOF = ROOT / "har" / "point_in_time_validation.json"


def pinball(actual, pred, tau=.05):
    residual = actual - pred
    return max(tau * residual, (tau - 1) * residual)


def assess(result, vintage=None):
    checks = {}
    for horizon, item in result["horizons"].items():
        rows = item["backtest"]
        count = len(rows)
        # Compare with expanding pre-origin historic quantile baseline on
        # identical time-aligned OOS origins; blind use of test data prohibited.
        # The benchmark is a conservative zero-real-change q05 reference until
        # a historical-quantile forecast is added.
        coverage = sum(p["breach"] for p in rows) / count if count else None
        model_loss = mean(pinball(p["actual"], p["predicted"]) for p in rows) if rows else None
        zero_loss = mean(pinball(p["actual"], 0.) for p in rows) if rows else None
        checks[horizon] = {
            "n": count, "breach_rate": coverage,
            "pinball_loss": model_loss, "zero_change_reference_loss": zero_loss,
            "sample_size_ok": count >= 24,
            "calibration_ok": count >= 24 and 0 <= coverage <= .15,
            "score_ok": count >= 24 and model_loss is not None and model_loss < zero_loss,
            "current_forecast": item.get("forecast") is not None,
        }
    # Explicitly require a separate independent audit with verifiable
    # as-of release calendars / archived data snapshots. A boolean supplied by
    # the HaR forecasting code itself can never authorize its own release.
    vintage_ok = bool(
        vintage and vintage.get("approved") is True
        and vintage.get("data_hash") == result.get("input_data_sha256")
        and vintage.get("reviewer")
        and vintage.get("publication_lags_audited") is True
        and vintage.get("revised_series_lookahead_excluded") is True
    )
    passed = all(
        d["sample_size_ok"] and d["calibration_ok"] and d["score_ok"] and d["current_forecast"]
        for d in checks.values()
    ) and vintage_ok
    return {"validated": bool(passed), "vintage_audit_passed": vintage_ok,
            "checks": checks, "note": "Blocked until point-in-time audit and all 4Q/12Q validation gates pass."}


def main():
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    vintage = json.loads(VINTAGE_PROOF.read_text(encoding="utf-8")) if VINTAGE_PROOF.exists() else None
    report = assess(result, vintage)
    OUT = OUTPUT
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
