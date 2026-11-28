#!/usr/bin/env python3
"""CLI for the isolated NSI research module; fail closed with no live score."""
from __future__ import annotations

import argparse
from pathlib import Path
from model import run, write_result


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Evaluate new NSI vs baseline for Seoul apartments")
    parser.add_argument("--price", type=Path, default=root / "research-data" / "nsi" / "seoul_price.csv")
    parser.add_argument("--nsi", type=Path, default=root / "research-data" / "nsi" / "new_nsi.csv")
    parser.add_argument("--controls", type=Path, default=root / "research-data" / "nsi" / "controls.csv")
    parser.add_argument("--output", type=Path, default=root / "risk-data" / "news-sentiment" / "summary.json")
    args = parser.parse_args()
    result = run(args.price, args.nsi, args.controls)
    write_result(args.output, result)
    print(f"{result['moduleId']}: {result['mode']}; compositeEligible={result['compositeEligible']}")
    for key, score in result.get("horizons", {}).items():
        print(f"  {key}m: {score.get('status')}, OOS count={score.get('forecastCount')}")


if __name__ == "__main__":
    main()
