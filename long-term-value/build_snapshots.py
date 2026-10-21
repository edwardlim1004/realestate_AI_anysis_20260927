#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build PUBLIC, aggregate five-year apartment valuation snapshots from PRIVATE R2 archives.

No raw transactions, credentials, or individual household details are written.
Monthly source files are only read server-side in GitHub Actions.
"""
import argparse
import calendar
import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import os
import statistics
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
VERSION = "five-year-v1.1"
DISTRICTS = {
    "11110": "종로구", "11140": "중구", "11170": "용산구", "11200": "성동구",
    "11215": "광진구", "11230": "동대문구", "11260": "중랑구", "11290": "성북구",
    "11305": "강북구", "11320": "도봉구", "11350": "노원구", "11380": "은평구",
    "11410": "서대문구", "11440": "마포구", "11470": "양천구", "11500": "강서구",
    "11530": "구로구", "11545": "금천구", "11560": "영등포구", "11590": "동작구",
    "11620": "관악구", "11650": "서초구", "11680": "강남구", "11710": "송파구",
    "11740": "강동구",
}


def shift_month(ym, offset):
    y, m = divmod(int(ym[:4]) * 12 + int(ym[4:]) - 1 + offset, 12)
    return f"{y:04d}{m+1:02d}"


def median(values):
    return round(statistics.median(values), 2) if values else None


def price_num(value):
    try:
        n = float(str(value or "").replace(",", "").strip())
        return n if math.isfinite(n) and n > 0 else None
    except (ValueError, TypeError):
        return None


def clean(value):
    return " ".join(str(value or "").strip().split())


def month_of(row):
    contract = str(row.get("계약일", "")).strip()
    return contract[:7].replace("-", "") if len(contract) >= 7 else str(row.get("계약년월", "")).strip()[:6]


def parse_rows(payload):
    with gzip.GzipFile(fileobj=io.BytesIO(payload), mode="rb") as raw:
        with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                yield row


def parse_scope(payload, kind, ym, bundles):
    accepted = 0
    for row in parse_rows(payload):
        if clean(row.get("해제사유발생일")) or month_of(row) != ym:
            continue
        name = clean(row.get("단지명"))
        dong = clean(row.get("법정동"))
        jibun = clean(row.get("지번"))
        area = price_num(row.get("전용면적(㎡)"))
        if not (name and dong and area and 10 <= area <= 350):
            continue
        # 5㎡ bins, centered at multiples of five. NEVER mix 59㎡ and 84㎡.
        size = math.floor(area / 5 + 0.5) * 5
        k = (dong, name, jibun, size)
        if kind == "sale":
            amount = price_num(row.get("거래금액(만원)"))
        else:
            # Pure jeonse only. Monthly rents are not equivalent to deposits.
            if price_num(row.get("월세금(만원)")):
                continue
            amount = price_num(row.get("보증금(만원)"))
        if amount is None:
            continue
        bundles[k][kind][ym].append(amount)
        accepted += 1
    return accepted


def make_complex(key, group, months, last):
    dong, name, jibun, size = key
    begin = shift_month(last, -59)
    recent_begin = shift_month(last, -11)
    baseline_end = shift_month(last, -48)
    sales = group["sale"]
    rents = group["rent"]
    sale_months = [[ym, median(vals), len(vals)] for ym, vals in sorted(sales.items()) if vals]
    sale_all = [p for vals in sales.values() for p in vals]
    recent = [p for ym, vals in sales.items() if ym >= recent_begin for p in vals]
    first = [p for ym, vals in sales.items() if ym <= baseline_end for p in vals]
    second = [p for ym, vals in sales.items() if ym >= recent_begin for p in vals]
    jeonse = [p for ym, vals in rents.items() if ym >= recent_begin for p in vals]
    annual = []
    for y in sorted({ym[:4] for ym in months}):
        av = [p for ym, vals in sales.items() if ym.startswith(y) for p in vals]
        if av:
            annual.append([y, median(av), len(av)])
    latest_price = median(recent) if len(recent) >= 5 else None
    first_price = median(first) if len(first) >= 3 else None
    older_months = [ym for ym in sales if ym <= baseline_end]
    observed_cagr = None
    if first_price and latest_price and older_months:
        first_mid = (int(min(older_months)[:4])*12 + int(min(older_months)[4:]))
        second_mid = int(last[:4])*12 + int(last[4:])
        span_yrs = (second_mid - first_mid) / 12
        if span_yrs >= 3.5:
            observed_cagr = round(((latest_price / first_price)**(1/span_yrs)-1)*100, 2)
    recent_rent = median(jeonse) if len(jeonse) >= 3 else None
    rent_rate = round(100 * recent_rent / latest_price, 1) if recent_rent and latest_price else None
    return {
        "dong": dong, "name": name, "jibun": jibun, "size": size,
        "sale_count_5y": len(sale_all), "sale_months": sale_months,
        "annual": annual, "last12_median": latest_price,
        "last12_count": len(recent),
        "first12_median": first_price, "first12_count": len(first),
        "observed_cagr_pct": observed_cagr,
        "jeonse_last12_median": recent_rent,
        "jeonse_last12_count": len(jeonse),
        "jeonse_rate_pct": rent_rate,
        "last_sale_month": max(sales) if sales else None,
        "first_sale_month": min(sales) if sales else None,
    }


def source_digests(manifest, gu, months):
    files = manifest.get("files") or {}
    specs = [(kind, ym, f"{kind}/{ym[:4]}/{gu}/{ym}.csv.gz")
             for kind in ("sale", "rent") for ym in months]
    present = [(k, ym, rel, files[rel]) for k, ym, rel in specs if rel in files and files[rel].get("sha256")]
    missing = [rel for _, _, rel in specs if rel not in files or not files[rel].get("sha256")]
    signature = hashlib.sha256(json.dumps(
        [VERSION, gu, specs[-1][1], [(rel, v["sha256"], v.get("storage", "r2")) for _, _, rel, v in present]],
        ensure_ascii=False, separators=(",", ":")
    ).encode()).hexdigest()
    return present, missing, signature


def build_one(gu, months, last, manifest, storage, force=False):
    present, missing, signature = source_digests(manifest, gu, months)
    target = DATA / (gu + ".json")
    if target.is_file() and not force:
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            if existing.get("source_digest") == signature:
                return ("skip", gu, existing.get("complex_count", 0))
        except (OSError, ValueError):
            pass
    bundles = collections.defaultdict(lambda: {
        "sale": collections.defaultdict(list),
        "rent": collections.defaultdict(list),
    })
    good = 0
    counts = {"sale": 0, "rent": 0}
    # If some scoped files are inaccessible, fail closed without overwriting a valid snapshot.
    for kind, ym, rel, v in present:
        try:
            compressed = storage(rel, v)
            if hashlib.sha256(compressed).hexdigest() != v["sha256"]:
                raise ValueError("sha256 mismatch")
            counts[kind] += parse_scope(compressed, kind, ym, bundles)
            good += 1
        except Exception as ex:
            raise RuntimeError(f"scope read or validation failed: {rel}: {type(ex).__name__}") from ex
    # We require at least 48/60 available sale months AND 48/60 rent months.
    sale_coverage = len({ym for kind, ym, _, _ in present if kind == "sale"})
    rent_coverage = len({ym for kind, ym, _, _ in present if kind == "rent"})
    if min(sale_coverage, rent_coverage) < 48:
        raise RuntimeError(f"{gu}: historical coverage insufficient: sale={sale_coverage}, rent={rent_coverage}")
    complexes = [make_complex(k, v, months, last) for k, v in bundles.items() if v["sale"]]
    complexes.sort(key=lambda v:(v["dong"],v["name"],v["jibun"],v["size"]))
    out = {
        "schema": 1, "method": VERSION, "district_code": gu, "district": DISTRICTS[gu],
        "window_start": months[0], "cutoff_month": last,
        "generated_kst": dt.datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
        "units": "만원", "size_bin_m2": 5,
        "source": "국토교통부 아파트 매매·전월세 API / 내부 R2 보관 원본",
        "source_digest": signature,
        "coverage": {"sale_months": sale_coverage, "rent_months": rent_coverage,
                     "target_months": len(months), "missing_scopes": len(missing),
                     "scopes_verified": good, "sale_rows": counts["sale"],
                     "pure_jeonse_rows": counts["rent"]},
        "complex_count": len(complexes), "complexes": complexes,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(target)
    return ("update", gu, len(complexes))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", choices=list(DISTRICTS)+["all"], default="all")
    parser.add_argument("--cutoff", help="YYYYMM; default last completed calendar month")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--archive-dir", help="Local test fixture containing sale/YYYY/GU/YYYYMM.csv.gz")
    args = parser.parse_args()
    kst = dt.datetime.now(ZoneInfo("Asia/Seoul"))
    last = args.cutoff or shift_month(kst.strftime("%Y%m"), -1)
    dt.date(int(last[:4]), int(last[4:]), 1)  # reject malformed dates
    months = [shift_month(last, i) for i in range(-59, 1)]
    manifest_file = BASE.parent / "seoul-apartment-collector" / "r2_manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if args.archive_dir:
        archive = Path(args.archive_dir)
        def storage(relative, entry):
            return (archive / relative).read_bytes()
    else:
        import boto3
        endpoint = "https://" + os.environ["R2_ACCOUNT_ID"] + ".r2.cloudflarestorage.com"
        client = boto3.client("s3", endpoint_url=endpoint,
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto")
        bucket = os.environ["R2_BUCKET_NAME"]
        prefix = "seoul-apartments/v1/"
        def storage(relative, entry):
            if entry.get("storage", "r2") != "r2":
                raise ValueError("Google Drive fallback requires separate authenticated reader")
            return client.get_object(Bucket=bucket, Key=prefix+relative)["Body"].read()
    names = list(DISTRICTS) if args.district == "all" else [args.district]
    errors = []
    for gu in names:
        try:
            result = build_one(gu, months, last, manifest, storage, args.force)
            print("VALUATION_SNAPSHOT", *result, flush=True)
        except Exception as ex:
            print(f"VALUATION_FAILED {gu}: {ex}", flush=True)
            errors.append(gu)
    if errors:
        raise SystemExit("Failed districts: " + ",".join(errors))


if __name__ == "__main__":
    main()
