"""Contract checks: HaR never silently publishes into the main risk score."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from build_har import build_frame, design, run


class HaRTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        # Synthetic-only data: never displayed as live forecast.
        for i in range(100):
            p = f"{2000 + i // 4}-Q{i % 4 + 1}"
            for ind, v in [
                ("REAL_HPI", 100 + i * 0.4 + (i % 7) * 0.3),
                ("PIR_LTA", 95 + i * 0.17 + (i % 5)),
                ("PTR_LTA", 99 + i * 0.12 + (i % 3)),
                ("CREDIT_GAP_PP", 2 + (i % 13) * 0.25),
            ]:
                self.rows.append(dict(Country="KOR", Frequency="Q", Indicator=ind, Period=p, Value=str(v)))

    def test_future_target_alignment(self):
        frame = build_frame(self.rows)
        d = design(frame, 4)
        first = frame.index[4]
        self.assertAlmostEqual(float(d.loc[first, "target"]), 100 * (frame.loc[first + 4, "REAL_HPI"] / frame.loc[first, "REAL_HPI"] - 1))

    def test_status_is_never_approved(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / "raw.csv"
            with file.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(self.rows[0]))
                w.writeheader()
                w.writerows(self.rows)
            result = run(path=file)
            self.assertFalse(result["composite_eligible"])
            for v in result["horizons"].values():
                self.assertFalse(v["approved"])
                self.assertFalse(v["validation_gates"]["release_vintage_no_lookahead"])


if __name__ == "__main__":
    unittest.main()
