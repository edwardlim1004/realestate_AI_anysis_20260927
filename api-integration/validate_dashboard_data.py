#!/usr/bin/env python3
"""Validate structural integrity and publish non-blocking data-quality flags."""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
DATA_JS = ROOT / "data.js"
REPORT = ROOT / "data-quality-report.json"


def load_data() -> dict:
    text = DATA_JS.read_text(encoding="utf-8")
    start = text.index("=") + 1
    end = text.rindex(";")
    return json.loads(text[start:end])


def write_atomic(path: Path, payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    data = load_data()
    regions = data.get("regions", [])
    months = data.get("months", [])
    errors = []
    warnings = []
    if len(regions) != 56:
        errors.append(f"region count {len(regions)} != 56")
    if len(months) != 61:
        errors.append(f"month count {len(months)} != 61")
    if len({row.get('name') for row in regions}) != len(regions):
        errors.append("duplicate region name")
    for row in regions:
        name = row.get("name", "UNKNOWN")
        if len(row.get("history", [])) != len(months):
            errors.append(f"{name}: history length mismatch")
        if not isinstance(row.get("avg84"), (int, float)) or row.get("avg84", 0) <= 0:
            errors.append(f"{name}: invalid avg84")
        if row.get("jeonseRate", 0) > 100:
            warnings.append({"region": name, "code": "JEONSE_OVER_100", "value": row.get("jeonseRate")})
        if row.get("kSamples", 0) < 10:
            warnings.append({"region": name, "code": "LOW_CONVERSION_SAMPLE", "value": row.get("kSamples", 0)})
        if abs(row.get("gapPct", 0)) > 50:
            warnings.append({"region": name, "code": "EXTREME_TREND_GAP", "value": row.get("gapPct")})
    report_without_time = {
        "status": "FAIL" if errors else ("REVIEW" if warnings else "OK"),
        "structuralErrors": errors,
        "qualityWarnings": warnings,
        "notes": [
            "Warnings do not stop the update; they require source-level review.",
            "The current calendar month is provisional and must not be compared with a completed month.",
            "Simple monthly means are sensitive to apartment and transaction composition.",
        ],
    }
    checked_at = None
    if REPORT.exists():
        try:
            prior = json.loads(REPORT.read_text(encoding="utf-8"))
            prior_without_time = {key: value for key, value in prior.items() if key != "checkedAtKST"}
            if prior_without_time == report_without_time:
                checked_at = prior.get("checkedAtKST")
        except (OSError, json.JSONDecodeError):
            pass
    report = {
        "checkedAtKST": checked_at
        or datetime.now(ZoneInfo("Asia/Seoul")).replace(microsecond=0).isoformat(),
        **report_without_time,
    }
    write_atomic(REPORT, report)
    print(json.dumps({"status": report["status"], "errors": len(errors), "warnings": len(warnings)}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
