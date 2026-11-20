#!/usr/bin/env python3
"""Read-only GitHub Actions + apartment data-quality health report.

The scope/manifest counters are storage progress, NOT proof of semantic completeness
or of an external source-of-truth match. No source data is changed by this script.
"""
import argparse
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, date, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

WATCHED = (
    "Seoul Gyeonggi and Daejeon Apartment Collector (Safe)",
    "Busan Daegu Gwangju Sequential Apartment Archives",
    "Build Seoul + Gyeonggi + Daejeon Transaction Details (61 regions)",
    "Build Five-Year Apartment Transaction History",
    "Build Metro Monthly History",
    "Build Verified Metro Price Summaries",
    "Build Latest Available Apartment Contracts",
)
FAILURES = {"failure", "timed_out", "action_required"}


def read_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def fetch_runs(repo, token):
    if not repo or "/" not in repo:
        raise ValueError("GITHUB_REPOSITORY must be owner/repo")
    url = f"https://api.github.com/repos/{repo}/actions/runs?branch=main&per_page=100"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ops-health-check"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)["workflow_runs"]


def assess(status, quality, runs, today):
    incidents, warnings = [], []
    completed = status.get("total_completed_scopes")
    total = status.get("total_scopes")
    if not isinstance(completed, int) or not isinstance(total, int) or total <= 0:
        incidents.append("Collector scope totals missing/invalid")
    elif completed > total:
        incidents.append("Stored completed scopes exceed expected scope count")
    elif completed < total:
        warnings.append(f"Stored scope progress incomplete: {completed}/{total}")
    # A completed-scope count does not certify source-side record completeness.
    as_of = status.get("as_of_kst", "")
    try:
        age_days = (today - date.fromisoformat(as_of)).days
        if age_days > 2:
            incidents.append(f"Collector status is stale ({age_days} days)")
        if age_days < 0:
            warnings.append(f"Collector status date is in the future: {as_of}")
    except (TypeError, ValueError):
        incidents.append("Collector status date unavailable")
    if status.get("last_run_failures", 0) > 0:
        incidents.append(f"Collector latest recorded failures: {status['last_run_failures']}")
    structural = quality.get("structuralErrors", [])
    if structural:
        incidents.append(f"Dashboard structural data errors: {len(structural)}")
    quality_warnings = quality.get("qualityWarnings", [])
    if quality_warnings:
        warnings.append(f"Dashboard data quality needs source review: {len(quality_warnings)} warnings")
    if quality.get("status") not in ("OK", "PASS", "REVIEW"):
        warnings.append(f"Unknown dashboard data-quality verdict: {quality.get('status')}")
    latest = {}
    for run in sorted(runs, key=lambda item: item.get("created_at", ""), reverse=True):
        name = run.get("name")
        if name in WATCHED and name not in latest:
            latest[name] = {
                "conclusion": run.get("conclusion"),
                "status": run.get("status"),
                "created_at": run.get("created_at"),
                "url": run.get("html_url"),
                "run_id": run.get("id"),
            }
    for name, run in latest.items():
        if run["status"] == "completed" and run["conclusion"] in FAILURES:
            incidents.append(f"Latest run failed: {name} ({run['url']})")
        elif run["status"] != "completed":
            warnings.append(f"Latest run still {run['status']}: {name}")
    if not latest:
        warnings.append("No watched workflow runs found in the last 100 runs; coverage unknown")
    if any(name not in latest for name in WATCHED):
        warnings.append("Some watched workflows are absent from the 100-run sample; do not infer success")
    return {
        "status": "ACTION_REQUIRED" if incidents else ("REVIEW" if warnings else "PASS"),
        "checked_at_kst": datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Seoul")).isoformat(),
        "storage_scope_progress": {"completed": completed, "expected": total,
                                   "meaning": "manifest progress only; original transaction semantics unverified"},
        "quality_verdict": quality.get("status"),
        "watched_latest_runs": latest,
        "incidents": incidents,
        "warnings": warnings,
        "production_mutation": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/ops-health.json")
    args = parser.parse_args()
    try:
        status = read_json("seoul-apartment-collector/status.json")
        quality = read_json("data-quality-report.json")
        runs = fetch_runs(os.environ.get("GITHUB_REPOSITORY", ""),
                          os.environ.get("GITHUB_TOKEN", ""))
        result = assess(status, quality, runs,
                        datetime.now(ZoneInfo("Asia/Seoul")).date())
    except (ValueError, KeyError, OSError, urllib.error.URLError) as exc:
        result = {
            "status": "UNKNOWN", "incidents": ["Health-check evidence unavailable"],
            "warnings": [f"Evidence read failed: {type(exc).__name__}"],
            "production_mutation": False,
        }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        lines = [f"## Apartment Operations: {result['status']}",
                 "Read-only report. Storage scope progress is not source verification.",
                 "### Incidents"]
        lines.extend(f"- {x}" for x in result.get("incidents", []))
        lines.append("### Warnings")
        lines.extend(f"- {x}" for x in result.get("warnings", []))
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    print(f"OPS_HEALTH {result['status']} incidents={len(result.get('incidents', []))} "
          f"warnings={len(result.get('warnings', []))}")


if __name__ == "__main__":
    main()
