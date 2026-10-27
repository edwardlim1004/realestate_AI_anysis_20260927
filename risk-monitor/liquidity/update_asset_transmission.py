#!/usr/bin/env python3
"""Research-only ECOS KOSPI close and Korean Treasury 3Y quarterly observations.

Does NOT touch the risk composite, promotion contract, or official score.
Observations are obtained through GitHub Actions ECOS_API_KEY only.
"""
from __future__ import annotations
import csv
import datetime as dt
import io
import json
import math
import os
import pathlib
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "risk-data" / "liquidity" / "asset_transmission.csv"
ECOS_BASE = "https://ecos.bok.or.kr/api/StatisticSearch"
SPECS = {
    "KOSPI": {"code": "802Y001", "item": "0001000", "name_terms": ("코스피", "kospi", "종합주가지수"), "unit": "index"},
    "KTB3Y": {"code": "817Y002", "item": "010200000", "name_terms": ("국고채",), "unit": "percent"},
}
FIELDS = ["Series", "Quarter", "Value", "StatisticCode", "ItemCode", "Unit",
          "ObservationCount", "LastObservationDate", "SourceURL"]


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                               "User-Agent": "RealEstateAILiquidityAssetResearch/1.0"})
    with urllib.request.urlopen(req, timeout=55) as response:
        return json.load(response)


def download_series(api_key: str, series: str, start_year: int, today: dt.date) -> list[tuple[str, float]]:
    spec = SPECS[series]
    values: dict[str, float] = {}
    # Two-year windows stay below typical ECOS bulk-response row limits.
    for y in range(start_year, today.year + 1, 2):
        begin = f"{y}0101"
        ending = f"{min(y + 1, today.year)}1231" if today.year > y + 1 else today.strftime("%Y%m%d")
        if ending < begin:
            continue
        segments = ["StatisticSearch", api_key, "json", "kr", "1", "100000",
                    spec["code"], "D", begin, ending, spec["item"]]
        url = "https://ecos.bok.or.kr/api/" + "/".join(urllib.parse.quote(v, safe="") for v in segments) + "/"
        payload = get_json(url)
        block = payload.get("StatisticSearch", {})
        rows = block.get("row") or []
        if not rows:
            # On a provider gap, never manufacture observations or zeros.
            print(f"NO_ROWS: {series} {begin}-{ending}, result={payload.get('RESULT')}")
            continue
        if int(block.get("list_total_count", len(rows))) > len(rows):
            raise RuntimeError(f"Unexpected ECOS partial response for {series}, {begin}-{ending}")
        for row in rows:
            if row.get("STAT_CODE") != spec["code"] or row.get("ITEM_CODE1") != spec["item"]:
                raise RuntimeError(f"ECOS series identity changed for {series}: {row}")
            name = str(row.get("ITEM_NAME1", "")).lower().replace(" ", "")
            if not any(term in name for term in spec["name_terms"]):
                raise RuntimeError(f"ECOS name mismatch for {series}: {row.get('ITEM_NAME1')}")
            if series == "KTB3Y" and "%" not in row.get("UNIT_NAME", ""):
                raise RuntimeError("ECOS bond-yield unit mismatch")
            date = row.get("TIME", "")
            if len(date) != 8 or not date.isdigit():
                continue
            try:
                num = float(str(row.get("DATA_VALUE", "")).replace(",", ""))
            except ValueError:
                continue
            if not math.isfinite(num) or (series == "KOSPI" and num <= 0):
                continue
            values[date] = num
    return sorted(values.items())


def aggregate_quarterly(series: str, data: list[tuple[str, float]]) -> list[dict[str, str]]:
    periods: dict[str, list[tuple[str, float]]] = {}
    for day, val in data:
        if not (len(day) == 8 and day.isdigit() and math.isfinite(val)):
            continue
        month = int(day[4:6])
        if month not in range(1, 13):
            continue
        quarter = f"{day[:4]}-Q{(month - 1) // 3 + 1}"
        periods.setdefault(quarter, []).append((day, val))
    rows = []
    spec = SPECS[series]
    for quarter in sorted(periods):
        obs = sorted(periods[quarter])
        # KOSPI: last trading day's close in the quarter.
        # KTB3Y: trading-day arithmetic mean (annualized percent yield).
        v = obs[-1][1] if series == "KOSPI" else sum(x[1] for x in obs) / len(obs)
        rows.append({"Series": series, "Quarter": quarter, "Value": f"{v:.9f}",
                     "StatisticCode": spec["code"], "ItemCode": spec["item"],
                     "Unit": spec["unit"], "ObservationCount": str(len(obs)),
                     "LastObservationDate": obs[-1][0], "SourceURL": "https://ecos.bok.or.kr/api/"})
    return rows


def read_existing() -> dict[tuple[str, str], dict]:
    if not OUTPUT.exists():
        return {}
    with OUTPUT.open(encoding="utf-8-sig", newline="") as f:
        return {(r["Series"], r["Quarter"]): r for r in csv.DictReader(f)}


def main() -> None:
    key = os.environ.get("ECOS_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ECOS_API_KEY missing; refusing synthetic asset records")
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    existing = read_existing()
    for series in SPECS:
        current = [k[1] for k in existing if k[0] == series]
        start_year = max(2003, int(max(current)[:4]) - 2) if current else 2003
        try:
            daily = download_series(key, series, start_year, today)
            if not daily:
                raise RuntimeError(f"No valid official ECOS rows for {series}")
            current_quarter = f"{today.year}-Q{(today.month - 1) // 3 + 1}"
            for record in aggregate_quarterly(series, daily):
                # A current-quarter observation is not a completed quarter-end close or yield average.
                if record["Quarter"] >= current_quarter:
                    continue
                existing[(series, record["Quarter"])] = record
            print(f"{series}: {len(daily)} daily observations, through {daily[-1][0]}")
        except Exception as error:
            # Preserve old official observations, report missing series visibly.
            print(f"{series}: FAILED: {type(error).__name__}: {error}")
            if not current:
                raise
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for key in sorted(existing):
        writer.writerow(existing[key])
    text = output.getvalue()
    previous = OUTPUT.read_text(encoding="utf-8-sig") if OUTPUT.exists() else None
    if previous != text:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(text, encoding="utf-8")
        print("ASSET_TRANSMISSION_CHANGED")
    else:
        print("ASSET_TRANSMISSION_NO_CHANGE")


if __name__ == "__main__":
    main()
