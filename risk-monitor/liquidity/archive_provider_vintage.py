#!/usr/bin/env python3
"""Archive each successfully fetched ECOS release-day snapshot to private R2.

Full point-in-time source values are never committed to Git beyond the
existing current official cache. Only the small R2 manifest is committed.
An archived snapshot is evidence of what the pipeline observed on that
retrieval date, NOT proof of the original first-publication vintage.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "risk-data" / "liquidity"
CATALOG = DIR / "vintage_catalog.csv"
CSV_FIELDS = ("Series", "StatisticCode", "ItemCode", "Frequency", "Period",
              "Value", "Unit", "ObservationKey", "DataStatus")
CATALOG_FIELDS = ("CapturedDateUTC", "CapturedAtUTC", "ObjectKey", "Sha256Uncompressed",
                  "RowCount", "SignalFingerprint", "Storage", "Verified")
PREFIX = "realestate-ai/liquidity/ecos-vintages/v1/"
REQUIRED = {"M2", "LF", "L", "CPI", "NOMINAL_GDP"}


def csv_text(path: Path) -> tuple[str, int, set[str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        original = list(csv.DictReader(stream))
    valid = sorted(original, key=lambda r: (r.get("Series", ""), r.get("Period", "")))
    names = {r.get("Series") for r in valid}
    if not REQUIRED.issubset(names) or len(valid) < 200 or any(
        row.get("DataStatus") != "Official_API" or not row.get("ObservationKey")
        for row in valid
    ):
        raise ValueError("Insufficient or nonofficial ECOS data; abort snapshot")
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows({k: row.get(k, "") for k in CSV_FIELDS} for row in valid)
    return out.getvalue(), len(valid), names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Validate data only; no R2 access")
    args = parser.parse_args()
    raw = DIR / "raw.csv"
    summary = json.loads((DIR / "summary.json").read_text(encoding="utf-8-sig"))
    payload, count, names = csv_text(raw)
    # Never manufacture a fresh release when the live ECOS API was unavailable.
    warnings = summary.get("update", {}).get("warnings", [])
    if warnings:
        print("R2_SNAPSHOT_SKIPPED: ECOS API has warnings; no clean release evidence")
        return 0
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    captured = datetime.now(timezone.utc).replace(microsecond=0)
    day = captured.strftime("%Y-%m-%d")
    object_key = PREFIX + day + "/" + digest[:24] + ".csv.gz"
    if args.dry_run:
        print(json.dumps({"dryRun": True, "rows": count, "series": sorted(names),
                          "day": day, "sha256": digest, "r2Key": object_key}, indent=2))
        return 0
    env = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME")
    if any(not os.environ.get(key) for key in env):
        print("R2_SNAPSHOT_SKIPPED: existing R2 repository secrets are not all configured")
        return 0
    import boto3
    from botocore.exceptions import ClientError
    client = boto3.client(
        "s3", endpoint_url="https://" + os.environ["R2_ACCOUNT_ID"] + ".r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
    bucket = os.environ["R2_BUCKET_NAME"]
    compressed = gzip.compress(payload.encode("utf-8"), compresslevel=9, mtime=0)
    try:
        metadata = client.head_object(Bucket=bucket, Key=object_key)
        if metadata.get("Metadata", {}).get("source-sha256") != digest:
            raise RuntimeError("R2 key collision or checksum mismatch")
        print("R2_SNAPSHOT_ALREADY_PRESENT", object_key)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in ("404", "NoSuchKey", "NotFound"):
            raise
        client.put_object(
            Bucket=bucket, Key=object_key, Body=compressed, ContentType="text/csv",
            ContentEncoding="gzip", Metadata={"source-sha256": digest,
                "captured-utc": captured.isoformat(), "series-count": str(len(names))})
        verified = client.head_object(Bucket=bucket, Key=object_key)
        if verified.get("Metadata", {}).get("source-sha256") != digest:
            raise RuntimeError("R2 checksum metadata missing after upload")
        print("R2_SNAPSHOT_STORED", object_key, len(compressed), "bytes")
    entries = []
    if CATALOG.exists():
        with CATALOG.open(encoding="utf-8-sig", newline="") as stream:
            entries = list(csv.DictReader(stream))
    if not any(row.get("ObjectKey") == object_key for row in entries):
        entries.append({
            "CapturedDateUTC": day, "CapturedAtUTC": captured.isoformat(),
            "ObjectKey": object_key, "Sha256Uncompressed": digest,
            "RowCount": count,
            "SignalFingerprint": summary.get("validation", {}).get("signalFingerprint", ""),
            "Storage": "cloudflare_r2", "Verified": "head_object_metadata",
        })
        entries.sort(key=lambda r: (r["CapturedDateUTC"], r["ObjectKey"]))
        with CATALOG.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CATALOG_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(entries)
    print(f"R2_VINTAGES distinct_utc_days={len({r['CapturedDateUTC'] for r in entries})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
