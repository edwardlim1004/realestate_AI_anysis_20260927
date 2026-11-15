"""Safety, target alignment and reproducibility contracts for NSI shadow module."""
import csv
import importlib.util
import math
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "model.py"
SPEC = importlib.util.spec_from_file_location("nsi_model", SCRIPT)
M = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)


class SafetyTests(unittest.TestCase):
    def fake_inputs(self, size=155):
        months = [M.month_add(date(2010, 1, 1), i) for i in range(size)]
        prices, nsi, controls = {}, {}, {}
        p = 100.0
        for i, month in enumerate(months):
            # Deterministic nonconstant synthetic inputs; NOT empirical evidence.
            signal = math.sin(i / 7.0) + 0.4 * math.cos(i / 11.0)
            p *= math.exp(0.003 * math.sin(i / 8.0) + 0.002 * signal)
            prices[month] = {"price_index": p}
            nsi[month] = {"new_nsi": 100 + 10 * signal}
            controls[month] = {
                "real_rate": math.sin(i / 15.0),
                "excess_liquidity": math.cos(i / 17.0),
                "kospi_return": math.sin(i / 4.0),
            }
        return months, prices, nsi, controls

    def test_only_previous_month_news_used(self):
        months, p, n, c = self.fake_inputs()
        records = M.build_observations(p, n, c, 1)
        target = months[30]
        before = next(r for r in records if r.origin == target)
        n[target]["new_nsi"] = -9999
        after = next(r for r in M.build_observations(p, n, c, 1) if r.origin == target)
        self.assertEqual(before.augmented, after.augmented)
        self.assertEqual(before.target, after.target)
        self.assertEqual(before.target_end, target)

    def test_horizon_embargo_training(self):
        months, p, n, c = self.fake_inputs()
        rows = M.build_observations(p, n, c, 6)
        with patch.object(M, "ridge_predict", wraps=M.ridge_predict) as spy:
            result = M.evaluate(rows, 6)
        self.assertGreater(result["forecastCount"], 24)
        self.assertTrue(spy.called)
        # If 60 labels are allowed to train, then 6 complete months of label
        # must have elapsed; train set at first forecast must NOT be 60 adjacent
        # origins ending on the forecast origin.
        first_idx = next(i for i, r in enumerate(rows) if r.origin.strftime("%Y-%m") == result["forecastMonths"][0])
        actual_training = sum(r.target_end < rows[first_idx].origin for r in rows[:first_idx])
        self.assertEqual(actual_training, M.MIN_TRAIN)

    def test_unchanged_real_time_and_composite_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            result = M.run(base / "no-price.csv", base / "no-nsi.csv", base / "no-controls.csv")
            self.assertIsNone(result["publicScore"])
            self.assertFalse(result["compositeEligible"])
            self.assertFalse(result["realTimeForecastVerified"])
            self.assertEqual(result["mode"], "SHADOW_WAITING_DATA")

    def test_synthetic_end_to_end_never_promoted(self):
        months, p, n, c = self.fake_inputs()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = [root / "price.csv", root / "nsi.csv", root / "control.csv"]
            keys = [("price_index",), ("new_nsi",), ("real_rate", "excess_liquidity", "kospi_return")]
            for path, fields, data in zip(paths, keys, (p, n, c)):
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(handle, fieldnames=("month", *fields))
                    writer.writeheader()
                    for m in months:
                        writer.writerow({"month": m.strftime("%Y-%m"), **data[m]})
            result = M.run(*paths)
            self.assertEqual(result["mode"], "SHADOW_VALIDATION")
            self.assertEqual(set(result["horizons"]), {"1", "3", "6"})
            self.assertTrue(all(v["status"] == "RETROSPECTIVE_ONLY" for v in result["horizons"].values()))
            self.assertTrue(all(v["readyForProduction"] is False for v in result["horizons"].values()))
            self.assertIsNone(result["publicScore"])
            self.assertFalse(result["compositeEligible"])
            self.assertEqual(result["withExpectedNSI"]["status"], "NOT_PROVIDED")

    def test_bad_values_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.csv"
            path.write_text("month,new_nsi\\n2026-10,nan\\n".replace("\\n", "\n"), encoding="utf-8")
            with self.assertRaises(ValueError):
                M.read_monthly_csv(path, ("new_nsi",))

    def test_non_overlap_diagnostic(self):
        self.assertIsNone(M._dm_pvalue(np.zeros(30), 3))
        self.assertIsNotNone(M._dm_pvalue(np.array([1.0, -0.2, 1.2, 0.4] * 10), 3))


if __name__ == "__main__":
    unittest.main()
