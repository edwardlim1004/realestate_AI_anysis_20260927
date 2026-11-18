#!/usr/bin/env python3
"""Discover and optionally export BOK ECOS NSI with explicit source approval.

This module never guesses an NSI item code, nor treats historical backfill as a
real-time vintage. The public BOK publication in 2026 changed the methodology.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_BASE = "https://ecos.bok.or.kr/api"
RESEARCH_URL = "https://www.bok.or.kr/portal/bbs/P0002353/view.do?nttId=11064365&menuNo=200433"
NEWS_PATTERN = re.compile(r"뉴스\s*심리|news\s*sentiment", re.IGNORECASE)


def ecos_call(key: str, service: str, *segments: str) -> tuple[list[dict], int]:
    if not key:
        raise ValueError("ECOS_API_KEY is required; credentials never go to Git")
    fields = (service, key, "json", "kr", *segments)
    uri = API_BASE + "/" + "/".join(urllib.parse.quote(str(s), safe="") for s in fields) + "/"
    request = urllib.request.Request(uri, headers={"Accept": "application/json", "User-Agent": "housing-risk-shadow-research/1.1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as stream:
            payload = json.load(stream)
    except Exception as exc:
        raise RuntimeError("ECOS metadata/data request failed (credentials hidden)") from exc
    if "RESULT" in payload:
        error = payload["RESULT"]
        raise RuntimeError(f"ECOS error: {error.get('CODE', 'UNKNOWN')} {error.get('MESSAGE', '')}")
    data = payload.get(service, {})
    if "row" not in data:
        raise ValueError(f"ECOS returned no {service} rows; cannot infer series")
    return data["row"], int(data.get("list_total_count", len(data["row"])))


def discover_catalog(key: str) -> list[dict]:
    matches = []
    offset, batch = 1, 1000
    for _ in range(35):
        rows, total = ecos_call(key, "StatisticTableList", str(offset), str(offset + batch - 1))
        for row in rows:
            if NEWS_PATTERN.search(str(row.get("STAT_NAME") or "")):
                matches.append({
                    "statCode": row.get("STAT_CODE"),
                    "statName": row.get("STAT_NAME"),
                    "cycle": row.get("CYCLE"), "source": "ECOS_StatisticTableList",
                    "status": "CANDIDATE_REQUIRES_ITEM_AND_METHODOLOGY_CONFIRMATION",
                })
        offset += batch
        if offset > total:
            break
    else:
        raise ValueError("ECOS catalog exceeded bounded scan; fail closed")
    return matches


def discover_items(key: str, table: str) -> list[dict]:
    if not re.fullmatch(r"[A-Za-z0-9]+", table):
        raise ValueError("Invalid ECOS table code")
    out, offset, batch = [], 1, 1000
    for _ in range(10):
        rows, total = ecos_call(key, "StatisticItemList", str(offset), str(offset + batch - 1), table)
        out.extend({
            "statCode": row.get("STAT_CODE"), "itemCode": row.get("ITEM_CODE"),
            "itemName": row.get("ITEM_NAME"), "cycle": row.get("CYCLE"),
            "unit": row.get("UNIT_NAME"), "firstPeriod": row.get("START_TIME"),
            "lastPeriod": row.get("END_TIME"), "observations": row.get("DATA_CNT"),
        } for row in rows)
        offset += batch
        if offset > total:
            break
    else:
        raise ValueError("ECOS items exceeded bounded scan; fail closed")
    return out


def validate_approval(contract: dict) -> None:
    required = ("statCode", "itemCode", "frequency", "seriesName", "methodVersion",
                "approver", "approvalDate", "bokEvidenceUrl", "historicalSeriesIsBackcast")
    missing = [k for k in required if k not in contract]
    if missing:
        raise ValueError("Explicit reviewed BOK series contract is incomplete: " + ",".join(missing))
    if contract["frequency"] != "M":
        raise ValueError("This exporter requires an ECOS monthly M series")
    if contract["methodVersion"] != "BOK_NEW_NSI_2026_09":
        raise ValueError("Do not silently mix legacy and new NSI methodologies")
    if contract["historicalSeriesIsBackcast"] not in (True, False):
        raise ValueError("Historical backcast status must be explicitly evaluated")
    if not str(contract["bokEvidenceUrl"]).startswith("https://www.bok.or.kr/"):
        raise ValueError("Only BOK primary methodology evidence accepted")
    if not all(str(contract[s]).strip() for s in ("statCode","itemCode","approver","approvalDate","seriesName")):
        raise ValueError("Blank approval fields")
    if not NEWS_PATTERN.search(contract["seriesName"]):
        raise ValueError("Series name must explicitly denote news sentiment")


def export_monthly(key: str, contract: dict, start: str, end: str) -> tuple[str, dict]:
    validate_approval(contract)
    if not re.fullmatch(r"\d{6}", start) or not re.fullmatch(r"\d{6}", end) or start > end:
        raise ValueError("Start/end must be valid ordered YYYYMM")
    metadata = discover_items(key, contract["statCode"])
    matches = [m for m in metadata
               if m["statCode"] == contract["statCode"] and m["itemCode"] == contract["itemCode"]
               and m["cycle"] == "M"]
    if not matches:
        raise ValueError("ECOS StatisticItemList does not identify approved monthly code")
    if not any(NEWS_PATTERN.search(str(m["itemName"])) or NEWS_PATTERN.search(contract["seriesName"]) for m in matches):
        raise ValueError("ECOS item name fails official series identity check")
    results, total = ecos_call(key, "StatisticSearch", "1", "100000", contract["statCode"],
                               "M", start, end, contract["itemCode"])
    if total > 100000:
        raise ValueError("ECOS truncation; do not use partial series")
    points = {}
    for row in results:
        if row.get("STAT_CODE") != contract["statCode"] or row.get("ITEM_CODE1") != contract["itemCode"]:
            raise ValueError("ECOS response identity mismatch")
        period = str(row.get("TIME") or "")
        if not re.fullmatch(r"\d{6}", period):
            raise ValueError("Unexpected ECOS month")
        value = float(str(row["DATA_VALUE"]).replace(",", ""))
        if not math.isfinite(value) or period in points:
            raise ValueError("Duplicate or nonfinite ECOS point")
        points[period] = value
    if not points:
        raise ValueError("No ECOS observations")
    if len(points) != total:
        raise ValueError("ECOS result count mismatch; avoid truncated data")
    buf = io.StringIO()
    csvout = csv.writer(buf, lineterminator="\n")
    csvout.writerow(("month", "new_nsi"))
    for period, value in sorted(points.items()):
        csvout.writerow((period[:4] + "-" + period[4:], format(value, ".12g")))
    csv_text = buf.getvalue()
    manifest = {
        "schemaVersion": "1.0", "provider": "BANK_OF_KOREA_ECOS",
        "methodVersion": contract["methodVersion"],
        "seriesIdentity": {k: contract[k] for k in ("statCode","itemCode","frequency","seriesName")},
        "approval": {k: contract[k] for k in ("approver","approvalDate","bokEvidenceUrl","historicalSeriesIsBackcast")},
        "retrievedUTC": datetime.now(timezone.utc).isoformat(),
        "observationCount": len(points), "firstPeriod": min(points), "lastPeriod": max(points),
        "csvSHA256": hashlib.sha256(csv_text.encode()).hexdigest(),
        "sourceEndpoint": API_BASE + "/StatisticSearch/",
        "pitVerified": False,
        "warning": "ECOS current query is not an archival per-release vintage; backcast cannot substantiate ex-ante prediction.",
    }
    return csv_text, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("catalog", "items", "export"), required=True)
    parser.add_argument("--table-code", default=None, help="Use only a code identified through ECOS catalog")
    parser.add_argument("--approval-json", type=Path, default=None)
    parser.add_argument("--start", default="200501")
    parser.add_argument("--end", default=datetime.now(timezone.utc).strftime("%Y%m"))
    parser.add_argument("--out-dir", type=Path, default=Path("research-data/nsi"))
    args = parser.parse_args()
    key = os.environ.get("ECOS_API_KEY", "")
    if args.mode == "catalog":
        print(json.dumps({"candidates": discover_catalog(key), "status": "METADATA_ONLY_UNVERIFIED"}, ensure_ascii=False, indent=2))
    elif args.mode == "items":
        if not args.table_code:
            parser.error("--table-code required for items")
        print(json.dumps({"items": discover_items(key, args.table_code), "status": "METADATA_ONLY_UNVERIFIED"}, ensure_ascii=False, indent=2))
    else:
        if not args.approval_json:
            parser.error("--approval-json required for export")
        contract = json.loads(args.approval_json.read_text(encoding="utf-8"))
        csvtext, manifest = export_monthly(key, contract, args.start, args.end)
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / "new_nsi.csv").write_text(csvtext, encoding="utf-8")
        (args.out_dir / "new_nsi.provenance.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Exported {manifest['observationCount']} monthly observations; pitVerified=False")


if __name__ == "__main__":
    main()
