#!/usr/bin/env python3
"""Fetch, calculate and validate the isolated Korean liquidity module."""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import tempfile
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from model import build_signal, canonical_fingerprint, signal_fingerprint, utc_now


MODULE_DIR = Path(__file__).resolve().parent
ROOT = MODULE_DIR.parents[1]
OUT = ROOT / "risk-data" / "liquidity"
CONFIG_PATH = MODULE_DIR / "config.json"
PROMOTION_PATH = MODULE_DIR / "promotion.json"
RAW_PATH = OUT / "raw.csv"
REVISION_PATH = OUT / "revision_history.csv"
BACKTEST_PATH = OUT / "backtest.json"
SUMMARY_PATH = OUT / "summary.json"
VALIDATION_PATH = OUT / "validation.json"
VINTAGE_PATH = OUT / "score_vintages.csv"
MODEL_VERSION = "1.0.0"
PUBLIC_SOURCE_URL = "https://ecos.bok.or.kr/api/"

RAW_FIELDS = [
    "Series", "StatisticCode", "ItemCode", "Frequency", "Period", "Value",
    "Unit", "RetrievedUTC", "SourceURL", "ObservationKey", "DataStatus",
]
REVISION_FIELDS = [
    "ChangeID", "ObservationKey", "ChangedUTC", "OldValue", "NewValue",
    "Series", "Period", "SourceURL",
]
VINTAGE_FIELDS = [
    "GeneratedUTC", "DataThrough", "ShadowScore", "MarshallKScore",
    "RealM2Score", "BreadthScore", "SignalFingerprint",
]


def read_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def csv_text(rows: list[dict], fields: list[str]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def write_if_changed(path: Path, text: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8-sig") if path.exists() else None
    if old == text:
        return False
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def api_json(url: str) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "EdwardHousingLiquidityModule/1.0", "Accept": "application/json"},
    )
    last_error = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.load(response)
        except Exception as error:  # transient official API errors are retried, then fail closed
            last_error = error
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"ECOS request failed: {type(last_error).__name__}: {last_error}")


def normalize_text(value: object) -> str:
    return "".join(str(value or "").split()).lower()


def fetch_series(api_key: str, name: str, spec: dict, config: dict) -> list[dict]:
    now = datetime.now(timezone.utc)
    start = config["source"]["startMonthly"] if spec["frequency"] == "M" else config["source"]["startQuarterly"]
    end = now.strftime("%Y%m") if spec["frequency"] == "M" else f"{now.year}Q{(now.month - 1) // 3 + 1}"
    segments = [
        "StatisticSearch", api_key, "json", "kr", "1", "100000",
        spec["statCode"], spec["frequency"], start, end, spec["itemCode"],
    ]
    url = config["source"]["apiBase"].rstrip("/") + "/" + "/".join(
        urllib.parse.quote(str(segment), safe="") for segment in segments
    ) + "/"
    payload = api_json(url)
    if "RESULT" in payload:
        result = payload["RESULT"]
        raise RuntimeError(f"ECOS {result.get('CODE', '')}: {result.get('MESSAGE', 'unknown error')}")
    block = payload.get("StatisticSearch", {})
    source_rows = block.get("row", [])
    if not source_rows:
        raise RuntimeError(f"ECOS returned no rows for {name}")

    retrieved, rows = utc_now(), []
    expected_name = normalize_text(spec["expectedName"])
    for source in source_rows:
        item_name = source.get("ITEM_NAME1", "")
        unit = source.get("UNIT_NAME", "")
        if source.get("STAT_CODE") != spec["statCode"] or source.get("ITEM_CODE1") != spec["itemCode"]:
            raise RuntimeError(f"ECOS identity mismatch for {name}")
        if expected_name not in normalize_text(item_name):
            raise RuntimeError(f"ECOS item-name mismatch for {name}: {item_name}")
        if normalize_text(spec["expectedUnit"]) not in normalize_text(unit):
            raise RuntimeError(f"ECOS unit mismatch for {name}: {unit}")
        try:
            value = float(str(source["DATA_VALUE"]).replace(",", ""))
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(value) or value <= 0:
            continue
        period = source.get("TIME", "")
        if spec["frequency"] == "Q":
            period = period.replace("-", "").replace("Q", "-Q")
        rows.append({
            "Series": name,
            "StatisticCode": spec["statCode"],
            "ItemCode": spec["itemCode"],
            "Frequency": spec["frequency"],
            "Period": period,
            "Value": str(value),
            "Unit": unit,
            "RetrievedUTC": retrieved,
            "SourceURL": PUBLIC_SOURCE_URL,
            "ObservationKey": f"ECOS|{spec['statCode']}|{spec['itemCode']}|{spec['frequency']}|{period}",
            "DataStatus": "Official_API",
        })
    if not rows:
        raise RuntimeError(f"ECOS returned no numeric rows for {name}")
    return rows


def upsert(old_rows: list[dict], incoming: list[dict]) -> tuple[list[dict], list[dict], int]:
    current = {row.get("ObservationKey", ""): row for row in old_rows if row.get("ObservationKey")}
    revisions, changed, stamp = [], 0, utc_now()
    for raw_row in incoming:
        row = {field: raw_row.get(field, "") for field in RAW_FIELDS}
        before = current.get(row["ObservationKey"])
        if before is None:
            current[row["ObservationKey"]] = row
            changed += 1
            continue
        try:
            same = math.isclose(float(before["Value"]), float(row["Value"]), rel_tol=0, abs_tol=1e-10)
        except (KeyError, TypeError, ValueError):
            same = before.get("Value") == row.get("Value")
        if same and before.get("Unit") == row.get("Unit"):
            continue
        revisions.append({
            "ChangeID": f"{stamp}|{row['ObservationKey']}",
            "ObservationKey": row["ObservationKey"],
            "ChangedUTC": stamp,
            "OldValue": before.get("Value", ""),
            "NewValue": row["Value"],
            "Series": row["Series"],
            "Period": row["Period"],
            "SourceURL": PUBLIC_SOURCE_URL,
        })
        current[row["ObservationKey"]] = row
        changed += 1
    ordered = sorted(current.values(), key=lambda row: (row.get("Series", ""), row.get("Period", "")))
    return ordered, revisions, changed


def add_month(period: str, step: int) -> str:
    index = int(period[:4]) * 12 + int(period[4:6]) - 1 + step
    return f"{index // 12:04d}{index % 12 + 1:02d}"


def add_quarter(period: str, step: int) -> str:
    year, quarter = period.replace("-", "").split("Q")
    index = int(year) * 4 + int(quarter) - 1 + step
    return f"{index // 4:04d}Q{index % 4 + 1}"


def missing_periods(periods: list[str], frequency: str) -> int:
    if len(periods) < 2:
        return 0
    stepper = add_month if frequency == "M" else add_quarter
    missing = 0
    for before, after in zip(periods, periods[1:]):
        expected = stepper(before, 1)
        while expected < after:
            missing += 1
            expected = stepper(expected, 1)
    return missing


def latest_lag_months(period: str) -> int:
    if not period:
        return 9999
    now = datetime.now(timezone.utc)
    return max(0, now.year * 12 + now.month - (int(period[:4]) * 12 + int(period[4:6])))


def gate(status: bool, detail: str, observed=None, required=None) -> dict:
    result = {"status": "PASS" if status else "FAIL", "detail": detail}
    if observed is not None:
        result["observed"] = observed
    if required is not None:
        result["required"] = required
    return result


def no_lookahead_check(rows: list[dict], config: dict, signal: dict) -> bool:
    history = signal.get("history", [])
    if len(history) < 5:
        return False
    checkpoint = history[-5]["period"]
    end_month = f"{checkpoint[:4]}{int(checkpoint[-1]) * 3:02d}"
    truncated = [
        row for row in rows
        if (row.get("Frequency") == "M" and row.get("Period", "") <= end_month)
        or (row.get("Frequency") == "Q" and row.get("Period", "") <= checkpoint)
    ]
    replay = build_signal(truncated, config)
    if not replay.get("current"):
        return False
    expected = next((item for item in history if item["period"] == checkpoint), None)
    return bool(expected and math.isclose(replay["current"]["score"], expected["score"], abs_tol=1e-9))


def validate(rows: list[dict], config: dict, signal: dict, backtest: dict) -> dict:
    by_series = {name: [] for name in config["source"]["series"]}
    identity_ok = True
    for row in rows:
        name = row.get("Series", "")
        if name not in by_series:
            continue
        by_series[name].append(row)
        spec = config["source"]["series"][name]
        identity_ok &= (
            row.get("StatisticCode") == spec["statCode"]
            and row.get("ItemCode") == spec["itemCode"]
            and row.get("Frequency") == spec["frequency"]
            and row.get("DataStatus") == "Official_API"
        )

    rules = config["validation"]
    counts = {name: len(items) for name, items in by_series.items()}
    coverage_ok = all(
        counts[name] >= (rules["minMonthlyObservations"] if spec["frequency"] == "M" else rules["minQuarterlyObservations"])
        for name, spec in config["source"]["series"].items()
    )
    missing = {
        name: missing_periods(sorted({row["Period"] for row in items}), config["source"]["series"][name]["frequency"])
        for name, items in by_series.items()
    }
    continuity_ok = all(by_series.values()) and all(
        missing[name] <= (rules["maxMissingMonthly"] if spec["frequency"] == "M" else rules["maxMissingQuarterly"])
        for name, spec in config["source"]["series"].items()
    )
    monthly_latest = max((row["Period"] for row in by_series["M2"]), default="")
    lag = latest_lag_months(monthly_latest)
    recency_ok = lag <= rules["maxLatestLagMonths"]
    weights = config["calculation"]["weights"]
    calculation_ok = math.isclose(sum(weights.values()), 1.0, abs_tol=1e-12) and bool(signal.get("current"))

    technical = {
        "officialSourceIdentity": gate(identity_ok and all(by_series.values()), "ECOS 코드·항목·주기·공식 API 표식을 설정과 대조", counts),
        "historyCoverage": gate(coverage_ok, "월별·분기별 최소 표본 수 충족", counts, {
            "monthly": rules["minMonthlyObservations"], "quarterly": rules["minQuarterlyObservations"],
        }),
        "continuity": gate(continuity_ok, "계열별 누락 월·분기 수 제한", missing, {
            "monthly": rules["maxMissingMonthly"], "quarterly": rules["maxMissingQuarterly"],
        }),
        "releaseRecency": gate(recency_ok, "M2 최신 관측치 발표시차 제한", lag, rules["maxLatestLagMonths"]),
        "calculationIntegrity": gate(calculation_ok, "가중치 합계·구성요소·최종점수 재현 가능", round(sum(weights.values()), 12), 1.0),
        "noLookAhead": gate(no_lookahead_check(rows, config, signal), "과거 절단표본 재계산 결과가 전체표본의 같은 시점 점수와 일치"),
    }
    evidence = {}
    for name, item in backtest.get("gates", {}).items():
        status = item.get("status", "NOT_RUN")
        evidence[name] = {"status": status, "detail": item.get("detail", "")}
    all_gates = {**technical, **evidence}
    passed = bool(all_gates) and all(item.get("status") == "PASS" for item in all_gates.values())
    return {"passed": passed, "gates": all_gates}


def build_outputs(rows: list[dict], config: dict, promotion: dict, backtest: dict) -> tuple[dict, dict]:
    signal = build_signal(rows, config)
    validation = validate(rows, config, signal, backtest)
    signal_hash = signal_fingerprint(signal)
    fingerprint_payload = {
        "modelVersion": MODEL_VERSION,
        "config": config,
        "signalFingerprint": signal_hash,
        "gates": validation["gates"],
    }
    validation_hash = canonical_fingerprint(fingerprint_payload)
    approved_hash = promotion.get("approvedValidationFingerprint")
    fingerprint_matches = bool(approved_hash and approved_hash == validation_hash)
    enabled = promotion.get("enabled") is True
    current = signal.get("current")
    if validation["passed"] and enabled and fingerprint_matches:
        mode = "ACTIVE"
    elif validation["passed"]:
        mode = "ELIGIBLE"
    elif current:
        mode = "SHADOW_VALIDATION"
    else:
        mode = "SHADOW_WAITING_DATA"
    validation.update({
        "validationFingerprint": validation_hash,
        "signalFingerprint": signal_hash,
        "passedGateCount": sum(item.get("status") == "PASS" for item in validation["gates"].values()),
        "totalGateCount": len(validation["gates"]),
    })
    summary = {
        "schemaVersion": "1.0",
        "moduleId": config["moduleId"],
        "modelVersion": MODEL_VERSION,
        "mode": mode,
        "publicScore": current["score"] if mode == "ACTIVE" and current else None,
        "shadowScore": current["score"] if current else None,
        "latestPeriod": current["period"] if current else None,
        "current": current,
        "history": signal.get("history", []),
        "missingSeries": signal.get("missingSeries", []),
        "validation": {
            "passed": validation["passed"],
            "passedGateCount": validation["passedGateCount"],
            "totalGateCount": validation["totalGateCount"],
            "validationFingerprint": validation_hash,
            "signalFingerprint": signal_hash,
        },
        "activation": {
            "enabled": enabled,
            "approvedValidationFingerprint": approved_hash,
            "fingerprintMatched": fingerprint_matches,
            "approvedAtUTC": promotion.get("approvedAtUTC"),
            "approvedBy": promotion.get("approvedBy"),
        },
        "method": {
            "components": "50% Marshall K gap + 30% real M2 gap + 20% real-liquidity breadth",
            "filter": "one-sided HP filter; monthly lambda 129,600 and quarterly lambda 1,600",
            "normalization": "expanding historical percentile; no future observations",
            "publicPolicy": "Only ACTIVE can expose publicScore or enter the core composite.",
        },
        "downloads": {
            "raw": "risk-data/liquidity/raw.csv",
            "revisions": "risk-data/liquidity/revision_history.csv",
            "validation": "risk-data/liquidity/validation.json",
            "backtest": "risk-data/liquidity/backtest.json",
        },
    }
    return summary, validation


def update_vintages(rows: list[dict], summary: dict, generated: str) -> list[dict]:
    vintages = read_csv(VINTAGE_PATH)
    current = summary.get("current")
    if not current:
        return vintages
    fingerprint = summary["validation"]["signalFingerprint"]
    if any(row.get("SignalFingerprint") == fingerprint for row in vintages):
        return vintages
    components = current["components"]
    vintages.append({
        "GeneratedUTC": generated,
        "DataThrough": current["period"],
        "ShadowScore": current["score"],
        "MarshallKScore": components["marshallKGap"]["score"],
        "RealM2Score": components["realM2Gap"]["score"],
        "BreadthScore": components["breadth"]["score"],
        "SignalFingerprint": fingerprint,
    })
    return vintages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Use the committed ECOS cache only")
    args = parser.parse_args()
    config = read_json(CONFIG_PATH, {})
    promotion = read_json(PROMOTION_PATH, {})
    backtest = read_json(BACKTEST_PATH, {"gates": {}})
    old_rows = read_csv(RAW_PATH)
    incoming, warnings = [], []
    api_key = os.environ.get("ECOS_API_KEY", "").strip()
    if not args.offline and api_key:
        for name, spec in config["source"]["series"].items():
            try:
                fetched = fetch_series(api_key, name, spec, config)
                incoming.extend(fetched)
                print(f"ECOS {name}: OK {len(fetched)}")
            except Exception as error:
                warnings.append(f"{name}: {type(error).__name__}: {str(error)[:180]}")
                print(f"ECOS {name}: REVIEW {type(error).__name__}")
    elif not args.offline:
        warnings.append("ECOS_API_KEY is not configured; retained the committed cache")
        print("ECOS: SHADOW (ECOS_API_KEY missing)")

    rows, revisions, changed_count = upsert(old_rows, incoming)
    all_revisions = read_csv(REVISION_PATH) + revisions
    summary, validation = build_outputs(rows, config, promotion, backtest)
    input_fingerprint = canonical_fingerprint({
        "modelVersion": MODEL_VERSION,
        "config": config,
        "promotion": promotion,
        "backtest": backtest,
        "observations": [
            (row.get("ObservationKey"), row.get("Value"), row.get("Unit")) for row in rows
        ],
    })
    existing = read_json(SUMMARY_PATH, {})
    generated = existing.get("generatedAtUTC") if existing.get("inputFingerprint") == input_fingerprint else utc_now()
    summary["generatedAtUTC"] = generated
    summary["inputFingerprint"] = input_fingerprint
    summary["update"] = {
        "insertedOrRevised": changed_count,
        "warnings": warnings,
        "policy": "Provider failures retain the prior official cache; SHADOW never enters the core score.",
    }
    validation["generatedAtUTC"] = generated
    vintages = update_vintages(rows, summary, generated)

    changed = False
    changed |= write_if_changed(RAW_PATH, csv_text(rows, RAW_FIELDS))
    changed |= write_if_changed(REVISION_PATH, csv_text(all_revisions, REVISION_FIELDS))
    changed |= write_if_changed(VINTAGE_PATH, csv_text(vintages, VINTAGE_FIELDS))
    changed |= write_if_changed(SUMMARY_PATH, json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    changed |= write_if_changed(VALIDATION_PATH, json.dumps(validation, ensure_ascii=False, indent=2) + "\n")
    print(
        f"RESULT: {'CHANGED' if changed else 'NO_CHANGE'}; mode={summary['mode']}; "
        f"gates={validation['passedGateCount']}/{validation['totalGateCount']}; rows={len(rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

