"""Publication-calendar audit for monthly Seoul apartment forecasting.

A complete release calendar is NECESSARY, not SUFFICIENT, for a real-time
point-in-time (PIT) backtest. Archival values/revisions remain required.
"""
from __future__ import annotations
import csv
import json
from datetime import date
from pathlib import Path

from model import month_add, parse_month

REQUIRED = ("SEOUL_APARTMENT_PRICE", "BOK_NEW_NSI", "REAL_RATE", "EXCESS_LIQUIDITY", "KOSPI_RETURN")


def parse_day(raw: str) -> date:
    return date.fromisoformat(str(raw))


def load_release_calendar(path: Path) -> dict[tuple[str, date], date]:
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not {"series", "month", "first_published_date"}.issubset(set(reader.fieldnames or [])):
            raise ValueError("Release calendar missing required columns")
        out = {}
        for row in reader:
            key = (row["series"].strip(), parse_month(row["month"]))
            if key[0] not in REQUIRED:
                raise ValueError("Unrecognized series: " + key[0])
            released = parse_day(row["first_published_date"].strip())
            if key in out:
                raise ValueError("Duplicate release entry")
            if released < key[1]:
                raise ValueError("Publication precedes observation month")
            out[key] = released
    return out


def check_origin(month: date, released: dict, day: int = 20, horizon: int = 1) -> dict:
    """t is the forecast start month, executed at month t day 20 KST."""
    if not 1 <= day <= 28:
        raise ValueError("Unsafe issue day")
    if horizon not in (1, 3, 6):
        raise ValueError("Horizon out of scope")
    issue = month.replace(day=day)
    # The t-1 price index is generally released in t, not on t day 1.
    requirements = [
        ("SEOUL_APARTMENT_PRICE", -1), ("SEOUL_APARTMENT_PRICE", -2),
        ("SEOUL_APARTMENT_PRICE", -3), ("BOK_NEW_NSI", -1),
        ("BOK_NEW_NSI", -2), ("REAL_RATE", -5),
        ("EXCESS_LIQUIDITY", -10), ("KOSPI_RETURN", -1),
    ]
    failures = []
    for series, lag in requirements:
        ref_month = month_add(month, lag)
        published = released.get((series, ref_month))
        if published is None:
            failures.append({"series": series, "month": ref_month.isoformat(), "reason": "MISSING_RELEASE_EVIDENCE"})
        elif published > issue:
            failures.append({"series": series, "month": ref_month.isoformat(),
                             "firstPublished": published.isoformat(), "reason": "NOT_YET_PUBLIC_AT_FORECAST"})
    return {"originMonth": month.strftime("%Y-%m"), "issueDate": issue.isoformat(),
            "horizon": horizon, "releaseCalendarPass": not failures, "failures": failures,
            "verifiedArchiveVintages": False,
            "status": "PUBLICATION_TIMING_ONLY_REQUIRES_ARCHIVED_VALUES" if not failures else "RELEASE_NOT_AVAILABLE"}


def audit(start: date, end: date, released: dict, day: int = 20) -> dict:
    if start > end:
        raise ValueError("Inverted date range")
    periods = []
    t = start
    while t <= end:
        periods.append(check_origin(t, released, day))
        t = month_add(t, 1)
    success = [r for r in periods if r["releaseCalendarPass"]]
    return {"mode": "RESEARCH_ONLY", "issueDay": day,
            "testedOrigins": len(periods), "releaseCalendarEligible": len(success),
            "releaseCalendarRejected": len(periods)-len(success),
            "fullPITVerified": False, "readyForProduction": False,
            "results": periods}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-calendar", type=Path, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--issue-day", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = load_release_calendar(args.release_calendar)
    out = audit(parse_month(args.start), parse_month(args.end), records, args.issue_day)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"PIT CALENDAR ONLY: {out['releaseCalendarEligible']}/{out['testedOrigins']}, fullPITVerified=False")


if __name__ == "__main__":
    main()
