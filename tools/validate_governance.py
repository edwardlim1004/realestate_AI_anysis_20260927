#!/usr/bin/env python3
"""Read-only structural checks for project governance metadata. No network or writes."""
import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MODULE_IDS = {"data", "storage", "liquidity", "gsadf", "har", "valuation", "dashboard", "auction", "macro", "governance"}
RESEARCH_MODELS = {"liquidity", "gsadf", "har"}
ALLOWED_FILES = {"tools/ai_task.py", "tools/validate_governance.py", "tools/test_governance.py"}

def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def valid_relative(value):
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    p = PurePosixPath(value)
    return not p.is_absolute() and all(part not in (".", "..") for part in value.split("/"))

def validate_changed_paths(paths):
    errors = []
    for path in paths:
        if not valid_relative(path) or not (path.startswith("operations/") or path in ALLOWED_FILES):
            errors.append("Unapproved changed path: " + str(path))
    return errors

def validate():
    errors = []
    modules = read_json("operations/modules.json")
    registry = read_json("operations/MODEL_REGISTRY.json")
    baseline = read_json("operations/BASELINE.json")
    if set(modules) != MODULE_IDS:
        errors.append("Module ID mismatch: " + repr(sorted(set(modules) ^ MODULE_IDS)))
    for ident, spec in modules.items():
        paths = spec.get("paths", [])
        if not isinstance(spec.get("name"), str) or not spec["name"].strip():
            errors.append("Module name missing: " + ident)
        if not isinstance(spec.get("scope"), str) or not spec["scope"].strip():
            errors.append("Module scope missing: " + ident)
        if not isinstance(paths, list) or not paths:
            errors.append("Module paths missing: " + ident)
            continue
        for path in paths:
            if not valid_relative(path) or not (ROOT / path).exists():
                errors.append("Module path missing/unsafe: " + str(path))
        if not (ROOT / "operations" / "modules" / ident / "README.md").is_file():
            errors.append("Module README missing: " + ident)
    if registry.get("source_commit") != baseline.get("main_commit"):
        errors.append("Model registry and baseline commit mismatch")
    if not re.fullmatch(r"[0-9a-f]{40}", str(baseline.get("main_commit", ""))):
        errors.append("Invalid baseline commit SHA")
    if baseline.get("main_branch") != "main" or baseline.get("merge_authorized") is not False:
        errors.append("Missing main protection/approval hold snapshot")
    models = registry.get("models", {})
    if not isinstance(models, dict) or not models:
        errors.append("Model registry empty")
        models = {}
    for name, model in models.items():
        for required in ("mode", "operational_integration", "approved_for_new_promotion", "data_as_of", "evidence_paths", "note"):
            if required not in model:
                errors.append("Model field missing: " + name + "." + required)
        if name in RESEARCH_MODELS and (model.get("operational_integration") is not False or model.get("approved_for_new_promotion") is not False):
            errors.append("Research model incorrectly marked operating/approved: " + name)
        for evidence in model.get("evidence_paths", []):
            if not valid_relative(evidence) or not (ROOT / evidence).is_file():
                errors.append("Evidence file missing/unsafe: " + str(evidence))
    for needed in ("STATUS.md", "DATA_CATALOG.md", "RELEASE_GATES.md", "PR36_RECONCILIATION.md", "CHAT_INDEX.md", "README.md"):
        if not (ROOT / "operations" / needed).is_file():
            errors.append("Governance document missing: " + needed)
    return errors

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed-paths", type=Path, help="Plain text file of changed paths from git diff --name-only")
    args = parser.parse_args()
    errors = validate()
    if args.changed_paths is not None:
        errors.extend(validate_changed_paths(args.changed_paths.read_text(encoding="utf-8").splitlines()))
    if errors:
        print("GOVERNANCE FAIL")
        for msg in errors:
            print("- " + msg)
        return 1
    print("GOVERNANCE PASS: schema, evidence paths, research isolation and optional change scope")
    return 0

if __name__ == "__main__":
    sys.exit(main())
