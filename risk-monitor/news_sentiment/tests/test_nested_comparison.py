"""HAC nested-forecast and multiple-horizon correction tests."""
import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

FILE = Path(__file__).resolve().parents[1] / "model.py"
SPEC = importlib.util.spec_from_file_location("nsi_model_nested", FILE)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class NestedForecastTests(unittest.TestCase):
    def test_holm_monotone_and_conservative(self):
        values = MOD._holm_adjust({"1": 0.01, "3": 0.04, "6": 0.20})
        self.assertEqual(values, {"1": 0.03, "3": 0.08, "6": 0.2})
        self.assertIsNone(MOD._holm_adjust({"1": None})["1"])

    def test_clark_west_p_in_valid_range(self):
        # Deterministic synthetic example only, NOT a housing backtest.
        actual = np.array([0.03, -0.02, 0.01, 0.05] * 30)
        base = np.array([0.0] * 120)
        augmented = actual + np.array([0.003, -0.002, 0.004, -0.001] * 30)
        p = MOD._clark_west_one_sided_pvalue(actual, base, augmented, 3)
        self.assertIsNotNone(p)
        self.assertTrue(0 <= p <= 1)

    def test_cw_disallows_zero_information_test(self):
        actual = np.ones(30)
        same = np.ones(30)
        self.assertIsNone(MOD._clark_west_one_sided_pvalue(actual, same, same, 1))


if __name__ == "__main__":
    unittest.main()
