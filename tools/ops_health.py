#!/usr/bin/env python3
"""Read-only GitHub Actions + apartment data-quality health report.

Production JSON inputs are fetched from one immutable main commit so a PR cannot
report its own edited fixtures as live production state. Scope counters are storage
progress only; they do not prove semantic completeness or source agreement.
"""
import argparse
import base64
import json
import os
import urllib.error
import urllib.parse
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
API = "https://api.github.com"


def github_json(url, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ops-health-check",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def fetch_main_ref(repo, token):
    if not repo or repo.count("/") != 1:
        raise ValueError("GITHUB_REPOSITORY must be owner/repo")
    payload = github_json(f"{API}/repos/{repo}/commits/main", token)
    sha = payload.get("sha") if isinstance(payload, dict) else None
    if not isinstance(sha, str) or len(sha) != 40:
        raise ValueError("Could not resolve an immutable main commit")
    return sha


def fetch_main_json(repo, path, ref, token):
    encoded_path = urllib.parse.quote(path, safe="/")
    payload = github_json(
        f"{API}/repos/{repo}/contents/{encoded_path}?ref={ref}", token
    )
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        raise ValueError(f"Unexpected GitHub contents response for {path}")
    content = payload.get("content")
    if not isinstance(content, str):
        raise ValueError(f"Missing GitHub contents for {path}")
    decoded = base64.b64decode(content, validate=False).decode("utf-8")
    result = json.loads(decoded)
    if not isinstance(result, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return result


def fetch_runs(repo, token):
    if not repo or repo.count("/") != 1:
        raise ValueError("GITHUB_REPOSITORY must be owner/repo")
    payload = github_json(
        f"{API}/repos/{repo}/actions/runs?branch=main&per_page=100", token
    )
    runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
    if not isinstance(runs, list) or any(not isinstance(run, dict) for run in runs):
        raise ValueError("Unexpected GitHub Actions runs response")
    return runs


def assess(status, quality, runs, today, source_commit=None):
    if not isinstance(status, dict) or not isinstance(quality, dict):
        raise ValueError("Status and quality evidence must be JSON objects")
    if not isinstance(runs, list) or any(not isinstance(run, dict) for run in runs):
        raise ValueError("Workflow runs evidence must be a list of objects")

    incidents, warnings = [], []
    completed = status.get("total_completed_scopes")
    total = status.get("total_scopes")
    if type(completed) is not int or type(total) is not int or total <= 0 or completed < 0:
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

    failures = status.get("last_run_failures", 0)
    if type(failures) is not int or failures < 0:
        incidents.append("Collector latest failure count missing/invalid")
    elif failures > 0:
        incidents.append(f"Collector latest recorded failures: {failures}")

    structural = quality.get("structuralErrors", [])
    if not isinstance(structural, list):
        incidents.append("Dashboard structural error evidence is invalid")
    elif structural:
        incidents.append(f"Dashboard structural data errors: {len(structural)}")

    quality_warnings = quality.get("qualityWarnings", [])
    if not isinstance(quality_warnings, list):
        incidents.append("Dashboard quality warning evidence is invalid")
    elif quality_warnings:
        warnings.append(
            f"Dashboard data quality needs source review: {len(quality_warnings)} warnings"
        )

    verdict = quality.get("status")
    if verdict not in ("OK", "PASS", "REVIEW"):
        warnings.append(f"Unknown dashboard data-quality verdict: {verdict}")

    for run in runs:
        created_at = run.get("created_at", "")
        if not isinstance(created_at, str):
            raise ValueError("Workflow run has invalid created_at")

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

    result = {
        "status": "ACTION_REQUIRED" if incidents else ("REVIEW" if warnings else "PASS"),
        "checked_at_kst": datetime.now(timezone.utc).astimezone(
            ZoneInfo("Asia/Seoul")
        ).isoformat(),
        "evidence_source": {"branch": "main", "commit": source_commit},
        "storage_scope_progress": {
            "completed": completed,
            "expected": total,
            "meaning": "manifest progress only; original transaction semantics unverified",
        },
        "quality_verdict": verdict,
        "watched_latest_runs": latest,
        "incidents": incidents,
        "warnings": warnings,
        "production_mutation": False,
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/ops-health.json")
    args = parser.parse_args()
    try:
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        token = os.environ.get("GITHUB_TOKEN", "")
        source_commit = fetch_main_ref(repo, token)
        status = fetch_main_json(
            repo, "seoul-apartment-collector/status.json", source_commit, token
        )
        quality = fetch_main_json(
            repo, "data-quality-report.json", source_commit, token
        )
        runs = fetch_runs(repo, token)
        result = assess(
            status, quality, runs, datetime.now(ZoneInfo("Asia/Seoul")).date(),
            source_commit=source_commit,
        )
    except (ValueError, TypeError, KeyError, OSError, UnicodeError,
            urllib.error.URLError) as exc:
        result = {
            "status": "UNKNOWN",
            "incidents": ["Health-check evidence unavailable"],
            "warnings": [f"Evidence read failed: {type(exc).__name__}"],
            "production_mutation": False,
        }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        lines = [
            f"## Apartment Operations: {result['status']}",
            "Production JSON is pinned to one main commit.",
            "Storage scope progress is not source verification.",
            "### Incidents",
        ]
        lines.extend(f"- {item}" for item in result.get("incidents", []))
        lines.append("### Warnings")
        lines.extend(f"- {item}" for item in result.get("warnings", []))
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    print(f"OPS_HEALTH {result['status']} "
          f"incidents={len(result.get('incidents', []))} "
          f"warnings={len(result.get('warnings', []))}")


if __name__ == "__main__":
    main()
