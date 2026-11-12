#!/usr/bin/env python3
# coding: utf-8
"""Create PUBLIC, static sale-transaction drill-down for all 56 dashboard regions.

Official collector archives stay private in R2 / verified Google Drive failover.
Only impersonal public transaction fields appear in compact JSON. No API call.
Snapshots are regenerated only when source SHA256 values change.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUT = ROOT / "trade-details"
sys.path.insert(0, str(ROOT / "api-integration"))
from regions_lawd import REGION_LAWD
from regions import in_month, full_name, DISTRICTS
from collect import row

DISPLAY_FIELDS = ("date", "apt", "city", "dong", "jibun", "area", "floor", "year", "price", "type", "code")
VERSION = 2


def dashboard_periods():
    raw = (ROOT / "data.js").read_text(encoding="utf-8-sig")
    start = raw.index("=") + 1
    end = raw.rfind(";")
    months = json.loads(raw[start:end]).get("months", [])
    if len(months) < 2 or any(len(m) != 7 or m[4] != "-" for m in months[-2:]):
        raise ValueError("Dashboard has no valid trailing 2 months")
    return [m.replace("-", "") for m in months[-2:]]


def entry_key(code: str, ym: str, kind="sale") -> str:
    return f"{kind}/{ym[:4]}/{code}/{ym}.csv.gz"


def public_row(code, ym, source, kind="sale"):
    data = row(kind, code, ym, source)
    if data["해제사유발생일"].strip():
        return None
    if kind == "rent":
        def amount(field):
            value = str(data[field]).replace(",", "").strip()
            try:
                n = float(value)
                if not math.isfinite(n) or n < 0: return None
            except ValueError: return None
            return value
        deposit, monthly = amount("보증금(만원)"), amount("월세금(만원)")
        if deposit is None or monthly is None or not data["계약일"]: return None
        if float(deposit) == 0 and float(monthly) == 0: return None
        return {"date":data["계약일"], "apt":data["단지명"], "city":data["시군구"],
                "dong":data["법정동"], "jibun":data["지번"], "area":data["전용면적(㎡)"],
                "floor":data["층"], "year":data["건축년도"], "code":code,
                "deposit":deposit, "monthlyRent":monthly,
                "rentalType":"jeonse" if float(monthly)==0 else "monthly"}
    price = str(data["거래금액(만원)"]).replace(",", "").strip()
    try:
        if float(price) <= 0:
            return None
    except ValueError:
        return None
    return {
        "date": data["계약일"], "apt": data["단지명"], "city": data["시군구"],
        "dong": data["법정동"], "jibun": data["지번"], "area": data["전용면적(㎡)"],
        "floor": data["층"], "year": data["건축년도"], "price": price,
        "type": data["거래유형"], "code": code
    }


def signature(codes, months, files, kind="sale"):
    sources = []
    missing = []
    for month in months:
        for code in codes:
            if not in_month(code, month):
                continue
            rel = entry_key(code, month, kind)
            meta = files.get(rel, {})
            if not meta.get("sha256") or meta.get("storage", "r2") not in ("r2", "gdrive"):
                missing.append(rel)
            else:
                sources.append((rel, meta["sha256"], meta.get("storage", "r2")))
    digest = hashlib.sha256(json.dumps(
        [VERSION, months, sources, missing], ensure_ascii=False, separators=(",", ":")
    ).encode()).hexdigest()
    return digest, sources, missing


def build_region(name, codes, months, storage, files, *, force=False, kind="sale"):
    digest, sources, missing = signature(codes, months, files, kind)
    target = (OUTPUT / "rent" if kind == "rent" else OUTPUT) / f"{codes[0]}.json"
    if missing:
        return {"region": name, "status": "missing_source", "missing": missing}
    if target.exists() and not force:
        try:
            prior = json.loads(target.read_text(encoding="utf-8"))
            if prior.get("source_digest") == digest:
                return {"region": name, "status": "unchanged", "count": len(prior.get("rows", []))}
        except (ValueError, OSError):
            pass
    rows, removed = [], 0
    by_month = {m: 0 for m in months}
    raw_counts = {m: 0 for m in months}
    for rel, expected_digest, _ in sources:
        code = rel.split("/")[2]
        month = rel.split("/")[3].split(".")[0]
        # read_scope verifies SHA256 on R2 or Google Drive BEFORE parsing rows.
        transactions = storage.read_scope(rel)
        if files[rel].get("rows") is not None and len(transactions) != int(files[rel]["rows"]):
            raise ValueError(f"Row count mismatch at {rel}")
        raw_counts[month] += len(transactions)
        for item in transactions:
            detail = public_row(code, month, item, kind)
            if detail is not None:
                rows.append(detail)
                by_month[month] += 1
            else:
                removed += 1
    unique = {json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")): item for item in rows}
    duplicate_rows = len(rows) - len(unique)
    rows = list(unique.values())
    rows.sort(key=lambda item: (item["date"], item["apt"], item.get("price", item.get("deposit", ""))), reverse=True)
    snapshot = {
        "schema": VERSION, "region": name, "codes": codes, "months": months,
        "source_digest": digest, "updated_at_kst": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        "source": "국토교통부 아파트 " + ("매매" if kind == "sale" else "전월세") + " 실거래 원자료 (비공개 R2/Google Drive 저장본)",
        "by_month": by_month, "raw_by_month": raw_counts, "excluded_rows": removed, "duplicate_rows": duplicate_rows,
        "coverage": {"expected_scopes": len(sources), "verified_scopes": len(sources), "missing_scopes": 0},
        "rows": rows,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(target)
    return {"region": name, "status": "updated", "count": len(rows), "excluded": removed, "duplicate_rows": duplicate_rows}


def build_all(storage, months, names, *, force=False, kind="sale"):
    folder = OUTPUT / "rent" if kind == "rent" else OUTPUT
    folder.mkdir(parents=True, exist_ok=True)
    index = {
        "schema": VERSION, "months": months,
        "regions": {name: {"codes": codes, "file": codes[0] + ".json"} for name, codes in REGION_LAWD.items()}
    }
    (folder / "index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    results = []
    for i, name in enumerate(names, 1):
        try:
            result = build_region(name, REGION_LAWD[name], months, storage, storage.files, force=force, kind=kind)
        except Exception as e:
            result = {"region": name, "status": "error", "reason": type(e).__name__}
        results.append(result)
        print(f"TRADE_DETAIL {i}/{len(names)} {name}: {result['status']} count={result.get('count', '-')}", flush=True)
    by_status = {}
    for result in results:
        by_status[result["status"]] = by_status.get(result["status"], 0) + 1
    report = {
        "schema": VERSION, "months": months, "region_count": len(names),
        "source_region_count": len(REGION_LAWD),
        "summary": by_status, "regions": results,
        "generated_at_kst": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
    }
    (folder / "build-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--region", help="Exact name in regions_lawd; default all 56")
    parser.add_argument("--kind", choices=["sale", "rent"], default="sale")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    months = dashboard_periods()
    names = [args.region] if args.region else list(REGION_LAWD)
    if any(name not in REGION_LAWD for name in names):
        raise SystemExit("Unknown dashboard region")
    from r2_bridge import R2Storage
    storage = R2Storage()
    report = build_all(storage, months, names, force=args.force, kind=args.kind)
    if report["summary"].get("error") or report["summary"].get("missing_source"):
        print("TRADE_DETAIL_PARTIAL: keep valid regions; incomplete sources remain flagged in build-report.json")
    if not (report["summary"].get("updated") or report["summary"].get("unchanged")):
        raise SystemExit("No verified regional trade-detail snapshots available")


if __name__ == "__main__":
    main()
