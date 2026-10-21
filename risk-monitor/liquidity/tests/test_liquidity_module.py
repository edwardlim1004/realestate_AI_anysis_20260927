from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_DIR = Path(__file__).resolve().parents[1]
RISK_MONITOR_DIR = MODULE_DIR.parent
sys.path.insert(0, str(MODULE_DIR))
sys.path.insert(0, str(RISK_MONITOR_DIR))

from adapter import load_for_core  # noqa: E402
from model import build_signal, hp_trend  # noqa: E402


CONFIG = json.loads((MODULE_DIR / "config.json").read_text(encoding="utf-8"))


def add_month(period: str, step: int) -> str:
    index = int(period[:4]) * 12 + int(period[4:6]) - 1 + step
    return f"{index // 12:04d}{index % 12 + 1:02d}"


def synthetic_rows(months: int = 240) -> list[dict]:
    rows = []
    levels = {"M2": 1500.0, "LF": 1900.0, "L": 2400.0, "CPI": 80.0}
    specs = CONFIG["source"]["series"]
    for index in range(months):
        period = add_month("200310", index)
        cycle = 1.0 + 0.012 * math.sin(index / 8.0) + 0.006 * math.sin(index / 29.0)
        for name in ("M2", "LF", "L"):
            growth = {"M2": 1.006, "LF": 1.0057, "L": 1.0054}[name]
            levels[name] *= growth * cycle
        levels["CPI"] *= 1.002
        for name in ("M2", "LF", "L", "CPI"):
            spec = specs[name]
            rows.append({
                "Series": name, "StatisticCode": spec["statCode"], "ItemCode": spec["itemCode"],
                "Frequency": "M", "Period": period, "Value": levels[name], "DataStatus": "Official_API",
            })
        if (index + 1) % 3 == 0:
            quarter = f"{period[:4]}-Q{int(period[4:6]) // 3}"
            spec = specs["NOMINAL_GDP"]
            rows.append({
                "Series": "NOMINAL_GDP", "StatisticCode": spec["statCode"], "ItemCode": spec["itemCode"],
                "Frequency": "Q", "Period": quarter, "Value": 350000 * (1.01 ** (index / 3)),
                "DataStatus": "Official_API",
            })
    return rows


class LiquidityModelTests(unittest.TestCase):
    def test_hp_filter_preserves_a_linear_trend(self):
        values = [3.0 + 1.7 * index for index in range(40)]
        trend = hp_trend(values, 129600)
        self.assertLess(max(abs(left - right) for left, right in zip(values, trend)), 1e-7)

    def test_future_observations_do_not_change_past_score(self):
        rows = synthetic_rows()
        full = build_signal(rows, CONFIG)
        cutoff = full["history"][-6]["period"]
        end_month = f"{cutoff[:4]}{int(cutoff[-1]) * 3:02d}"
        truncated_rows = [
            row for row in rows
            if (row["Frequency"] == "M" and row["Period"] <= end_month)
            or (row["Frequency"] == "Q" and row["Period"] <= cutoff)
        ]
        truncated = build_signal(truncated_rows, CONFIG)
        expected = next(row for row in full["history"] if row["period"] == cutoff)
        self.assertEqual(truncated["current"]["period"], cutoff)
        self.assertAlmostEqual(truncated["current"]["score"], expected["score"], places=9)

    def test_signal_contains_all_three_components(self):
        signal = build_signal(synthetic_rows(), CONFIG)
        self.assertTrue(signal["history"])
        self.assertEqual(
            set(signal["current"]["components"]),
            {"marshallKGap", "realM2Gap", "breadth"},
        )
        self.assertGreaterEqual(signal["current"]["score"], 0)
        self.assertLessEqual(signal["current"]["score"], 100)


class AdapterContractTests(unittest.TestCase):
    def write_summary(self, root: Path, summary: dict) -> None:
        path = root / "risk-data" / "liquidity" / "summary.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(summary), encoding="utf-8")

    def test_shadow_never_enters_core(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_summary(root, {
                "schemaVersion": "1.0", "mode": "SHADOW_VALIDATION", "publicScore": None,
                "shadowScore": 88.0, "validation": {"passed": False, "passedGateCount": 6, "totalGateCount": 9},
                "activation": {"enabled": False, "fingerprintMatched": False},
            })
            result = load_for_core(root)
            self.assertFalse(result["active"])
            self.assertIsNone(result["tile"]["score"])
            self.assertEqual(result["history"], {})

    def test_active_requires_matching_validation_fingerprint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_summary(root, {
                "schemaVersion": "1.0", "mode": "ACTIVE", "publicScore": 72.0,
                "latestPeriod": "2025-Q4", "history": [{"period": "2025-Q4", "score": 72.0}],
                "validation": {"passed": True, "passedGateCount": 9, "totalGateCount": 9, "validationFingerprint": "new"},
                "activation": {"enabled": True, "fingerprintMatched": False, "approvedValidationFingerprint": "old"},
            })
            result = load_for_core(root)
            self.assertFalse(result["active"])
            self.assertIsNone(result["tile"]["score"])

    def test_valid_active_contract_is_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.write_summary(root, {
                "schemaVersion": "1.0", "mode": "ACTIVE", "publicScore": 72.0,
                "latestPeriod": "2025-Q4", "history": [{"period": "2025-Q4", "score": 72.0}],
                "current": {"components": {}},
                "validation": {"passed": True, "passedGateCount": 9, "totalGateCount": 9, "validationFingerprint": "same"},
                "activation": {"enabled": True, "fingerprintMatched": True, "approvedValidationFingerprint": "same"},
            })
            result = load_for_core(root)
            self.assertTrue(result["active"])
            self.assertEqual(result["tile"]["score"], 72.0)
            self.assertEqual(result["history"], {"2025-Q4": 72.0})


if __name__ == "__main__":
    unittest.main()

