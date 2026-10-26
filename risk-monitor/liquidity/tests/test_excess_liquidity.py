"""Regression tests for exploratory excess-liquidity comparisons."""
import importlib.util
import math
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "compare_excess_liquidity.py"
SPEC = importlib.util.spec_from_file_location("liquidity_excess_comparison", SCRIPT)
import sys
sys.path.insert(0, str(SCRIPT.parent))
COMPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPARE)


class ExcessLiquidityTests(unittest.TestCase):
    def test_yoy_spread_zero_for_equal_nominal_growth(self):
        m2 = {"2024-Q1": 100.0, "2025-Q1": 110.0}
        gdp = {"2024-Q1": 200.0, "2025-Q1": 220.0}
        self.assertAlmostEqual(COMPARE.yoy_spread(m2, gdp)["2025-Q1"], 0.0)

    def test_growth_spread_direction_and_no_future(self):
        m2 = {"2024-Q1": 100.0, "2025-Q1": 120.0, "2026-Q1": 140.0}
        gdp = {"2024-Q1": 200.0, "2025-Q1": 210.0, "2026-Q1": 220.0}
        before = COMPARE.yoy_spread(m2, gdp)
        self.assertGreater(before["2025-Q1"], 0)
        m2["2026-Q1"] = 1e9
        after = COMPARE.yoy_spread(m2, gdp)
        self.assertEqual(before["2025-Q1"], after["2025-Q1"])

    def test_average_requires_three_distinct_months(self):
        rows = [
            {"Series": "M2", "Period": f"2024{m:02d}", "Value": str(100 + m)}
            for m in range(1, 6)
        ]
        values = COMPARE.quarterly_m2(rows)
        self.assertEqual(values["2024-Q1"], 102)
        self.assertNotIn("2024-Q2", values)

    def test_smoothing_is_backward_only(self):
        raw = {f"{2020 + i // 4}-Q{1 + i % 4}": float(i) for i in range(8)}
        original = COMPARE.smooth_spread(raw)
        self.assertEqual(original["2021-Q1"], 2.5)
        changed = dict(raw)
        changed["2021-Q4"] = 1e7
        self.assertEqual(COMPARE.smooth_spread(changed)["2021-Q1"], original["2021-Q1"])

    def test_percentiles_are_expanding(self):
        x = {f"{2010 + i // 4}-Q{1 + i % 4}": float(i) for i in range(24)}
        p = COMPARE.historical_percentile(x, 20)
        self.assertEqual(len(p), 5)
        self.assertEqual(p["2014-Q4"], 100)
        x["2015-Q4"] = -1
        self.assertEqual(COMPARE.historical_percentile(x, 20)["2014-Q4"], 100)


if __name__ == "__main__":
    unittest.main()
