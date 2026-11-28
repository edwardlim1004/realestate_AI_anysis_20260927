#!/usr/bin/env python3
"""Convert an approved official REB Seoul-apartment monthly series to model CSV.

Caller supplies a downloaded official CSV and an approval contract describing
EXACT region/type/metric. Never substitutes a transaction arithmetic mean.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

OFFICIAL_ROOTS = ("https://www.reb.or.kr/", "https://www.data.go.kr/")
METRIC = "서울 아파트 매매가격지수"


def normalize_month(raw: str) -> str:
    val = str(raw).strip().replace(".", "-").replace("/", "-")
    if re.fullmatch(r"\d{6}", val):
        val = val[:4] + "-" + val[4:]
    if not re.fullmatch(r"\d{4}-\d{2}", val) or not (1 <= int(val[-2:]) <= 12):
        raise ValueError("Invalid monthly period " + raw)
    return val


def check_manifest(manifest: dict) -> None:
    necessary = ("provider", "sourceURL", "metric", "region", "housingType",
                 "priceType", "unit", "retrievedDate", "reviewedBy")
    if any(not str(manifest.get(x) or "").strip() for x in necessary):
        raise ValueError("Official source approval contract is incomplete")
    if manifest["provider"] != "REB":
        raise ValueError("Only REB approved here; KB needs a separate contract")
    if manifest["region"] != "서울" or manifest["housingType"] != "아파트":
        raise ValueError("Only Seoul apartment index supported")
    if manifest["priceType"] != "매매가격지수" or manifest["metric"] != METRIC:
        raise ValueError("Wrong metric: price index is required, not mean sales price")
    if not str(manifest["sourceURL"]).startswith(OFFICIAL_ROOTS):
        raise ValueError("Official REB or public-data URI required")


def convert(raw: bytes, manifest: dict, month_col: str, price_col: str,
            min_months: int = 180) -> tuple[str, dict]:
    check_manifest(manifest)
    text = None
    for encoding in ("utf-8-sig", "cp949"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeError:
            pass
    if text is None:
        raise ValueError("Unknown official CSV text encoding")
    reader = csv.DictReader(io.StringIO(text))
    if month_col not in (reader.fieldnames or ()) or price_col not in (reader.fieldnames or ()):
        raise ValueError("Selected columns not in official CSV")
    points = {}
    for row in reader:
        month = normalize_month(row[month_col])
        if month in points:
            raise ValueError("Duplicate monthly observation; check region/type filters")
        number = float(str(row[price_col]).strip().replace(",", ""))
        if not math.isfinite(number) or number <= 0:
            raise ValueError("Invalid price index at " + month)
        points[month] = number
    if len(points) < min_months:
        raise ValueError(f"Insufficient official history: {len(points)} < {min_months}")
    ordered = sorted(points)
    for a, b in zip(ordered, ordered[1:]):
        year, mon = map(int, a.split("-"))
        next_expected = f"{year + (mon == 12):04d}-{mon % 12 + 1:02d}"
        if b != next_expected:
            raise ValueError(f"Missing month after {a}: expected {next_expected}, got {b}")
        if abs(math.log(points[b] / points[a])) > 0.12:
            raise ValueError("Suspicious 12%+ monthly index jump: rebasing/series splice? " + b)
    buf = io.StringIO(newline="")
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["month", "price_index"])
    for t in ordered:
        writer.writerow([t, format(points[t], ".12g")])
    exported = buf.getvalue()
    info = {"schemaVersion": "1.0", "provider": "REB",
            "source": manifest, "firstPeriod": ordered[0], "lastPeriod": ordered[-1],
            "observationCount": len(ordered),
            "rawSHA256": hashlib.sha256(raw).hexdigest(),
            "exportSHA256": hashlib.sha256(exported.encode()).hexdigest(),
            "createdUTC": datetime.now(timezone.utc).isoformat(),
            "archiveReleaseDatesVerified": False, "fullPITVerified": False,
            "warning": "Normalised from current official file; original historical release vintages not established"}
    return exported, info


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reb-csv", type=Path, required=True)
    parser.add_argument("--approval-json", type=Path, required=True)
    parser.add_argument("--month-column", required=True)
    parser.add_argument("--price-column", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("research-data/nsi"))
    args = parser.parse_args()
    manifest = json.loads(args.approval_json.read_text(encoding="utf-8"))
    output, provenance = convert(args.reb_csv.read_bytes(), manifest,
                                 args.month_column, args.price_column)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "seoul_price.csv").write_text(output, encoding="utf-8")
    (args.output_dir / "seoul_price.provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Created approved historical-price research input; fullPITVerified=False")


if __name__ == "__main__":
    main()
