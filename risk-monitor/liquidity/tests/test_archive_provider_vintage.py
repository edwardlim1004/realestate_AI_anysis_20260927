"""Test R2 source snapshot canonicalization without credentials or a network."""
import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "archive_provider_vintage.py"
SPEC = importlib.util.spec_from_file_location("liquidity_r2_vintage", SCRIPT)
ARCHIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ARCHIVE)


class ArchiveTests(unittest.TestCase):
    def test_source_csv_is_deterministic_and_checks_all_series(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "raw.csv"
            fields = list(ARCHIVE.CSV_FIELDS)
            rows = []
            for series in sorted(ARCHIVE.REQUIRED, reverse=True):
                for n in range(50):
                    key = f"{series}|2024{n:02d}"
                    rows.append({
                        "Series": series, "StatisticCode": "TEST", "ItemCode": "0",
                        "Frequency": "Q" if series == "NOMINAL_GDP" else "M",
                        "Period": f"2024{n:02d}", "Value": str(n+1), "Unit": "1",
                        "ObservationKey": key, "DataStatus": "Official_API",
                    })
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            text1, count, names = ARCHIVE.csv_text(path)
            self.assertEqual(count, 250)
            self.assertEqual(names, ARCHIVE.REQUIRED)
            self.assertEqual(text1, ARCHIVE.csv_text(path)[0])
            self.assertTrue(text1.splitlines()[1].startswith("CPI,"))

    def test_non_official_input_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "raw.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=ARCHIVE.CSV_FIELDS)
                writer.writeheader()
                writer.writerow({"Series": "M2", "ObservationKey": "fake", "DataStatus": "synthetic"})
            with self.assertRaises(ValueError):
                ARCHIVE.csv_text(path)


if __name__ == "__main__":
    unittest.main()
