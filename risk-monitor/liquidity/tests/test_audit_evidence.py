"""Regression tests for fail-closed independent OOS audit."""
import importlib.util
import math
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "audit_evidence.py"
SPEC = importlib.util.spec_from_file_location("liquidity_evidence_audit", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class EvidenceAuditTests(unittest.TestCase):
    def test_quarter_arithmetic(self):
        self.assertEqual(AUDIT.quarter_add("2020-Q1", -2), "2019-Q3")
        self.assertEqual(AUDIT.quarter_add("2020-Q4", 1), "2021-Q1")

    def test_train_labels_must_be_matured(self):
        hpi = {}
        scores = {}
        for k in range(90):
            period = f"{2010 + k // 4}-Q{1 + k % 4}"
            hpi[period] = math.exp(k * 0.002 + 0.025 * math.sin(k / 3.0))
            scores[period] = 45 + 20 * math.sin(k / 4.0)
        result = AUDIT.oos(hpi, scores, 4)
        self.assertGreater(result["outOfSampleCount"], 0)
        for point in result["predictions"]:
            self.assertEqual(
                AUDIT.quarter_index(point["origin_quarter"]) -
                AUDIT.quarter_index(point["signal_quarter"]), 2
            )
            earliest = AUDIT.quarter_add(point["origin_quarter"], -5)
            eligible_origins = [
                p for p in hpi
                if AUDIT.quarter_index(p) <= AUDIT.quarter_index(earliest)
                and AUDIT.quarter_add(p, -2) in scores
                and AUDIT.quarter_add(p, 4) in hpi
            ]
            self.assertEqual(point["mature_training_n"], len(eligible_origins))

    def test_lag_sensitivity_preserves_pre_registered_gate(self):
        hpi, scores = {}, {}
        for k in range(90):
            period = f"{2010 + k // 4}-Q{1 + k % 4}"
            hpi[period] = math.exp(k * 0.002 + 0.025 * math.sin(k / 3.0))
            scores[period] = 45 + 20 * math.sin(k / 4.0)
        default = AUDIT.oos(hpi, scores, 4)
        explicit = AUDIT.oos(hpi, scores, 4, signal_lag_quarters=2)
        self.assertEqual(default, explicit)
        for lag in (0, 1, 2, 4):
            alternate = AUDIT.oos(hpi, scores, 4, signal_lag_quarters=lag)
            self.assertGreater(alternate["outOfSampleCount"], 0)
            for point in alternate["predictions"]:
                self.assertEqual(
                    AUDIT.quarter_index(point["origin_quarter"]) -
                    AUDIT.quarter_index(point["signal_quarter"]), lag
                )

    def test_future_hpi_not_used_as_feature(self):
        hpi = {}
        scores = {}
        for k in range(90):
            period = f"{2010 + k // 4}-Q{1 + k % 4}"
            hpi[period] = math.exp(k * 0.001 + 0.013 * math.sin(k / 6))
            scores[period] = 40 + k / 3
        a = AUDIT.oos(hpi, scores, 8)
        # Adding post-cutoff observations cannot change pre-cutoff predictions.
        hpi2 = dict(hpi)
        for k in range(90, 95):
            hpi2[f"{2010 + k // 4}-Q{1 + k % 4}"] = 1e6
        b = AUDIT.oos(hpi2, scores, 8)
        first = {p["origin_quarter"]: p for p in a["predictions"]}
        for p in b["predictions"]:
            if p["origin_quarter"] in first:
                self.assertEqual(first[p["origin_quarter"]], p)


if __name__ == "__main__":
    unittest.main()
