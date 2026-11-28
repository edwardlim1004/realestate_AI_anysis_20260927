"""Official REB importer contract tests, all mocked/synthetic data."""
import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "prepare_reb_price.py"
SPEC = importlib.util.spec_from_file_location("reb_price", FILE)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class REBImportSafetyTests(unittest.TestCase):
    def manifest(self):
        return {"provider": "REB", "sourceURL": "https://www.data.go.kr/data/15167008/fileData.do",
                "metric": "서울 아파트 매매가격지수", "region": "서울",
                "housingType": "아파트", "priceType": "매매가격지수",
                "unit": "2021=100", "retrievedDate": "2026-11-19", "reviewedBy": "researcher"}

    def rows(self, count=185, jump=None):
        output = ["MONTH,PRICE"]
        for i in range(count):
            year, m = 2010 + i // 12, i % 12 + 1
            value = 100 + 0.1 * i
            if jump is not None and i == jump:
                value *= 2
            output.append(f"{year:04d}{m:02d},{value}")
        return ("\n".join(output)+"\n").encode()

    def test_normalizes_authorized_series(self):
        output, meta = MOD.convert(self.rows(), self.manifest(), "MONTH", "PRICE")
        self.assertIn("2010-01,100", output)
        self.assertEqual(meta["observationCount"], 185)
        self.assertFalse(meta["fullPITVerified"])

    def test_reject_average_price_metric(self):
        contract = self.manifest()
        contract["metric"] = "서울 아파트 평균매매가격"
        with self.assertRaises(ValueError):
            MOD.convert(self.rows(), contract, "MONTH", "PRICE")

    def test_reject_wrong_region_and_series_splice(self):
        contract = self.manifest()
        contract["region"] = "경기"
        with self.assertRaises(ValueError):
            MOD.convert(self.rows(), contract, "MONTH", "PRICE")
        with self.assertRaises(ValueError):
            MOD.convert(self.rows(jump=80), self.manifest(), "MONTH", "PRICE")

    def test_reject_short_and_bad_column(self):
        with self.assertRaises(ValueError):
            MOD.convert(self.rows(count=60), self.manifest(), "MONTH", "PRICE")
        with self.assertRaises(ValueError):
            MOD.convert(self.rows(), self.manifest(), "period", "PRICE")


if __name__ == "__main__":
    unittest.main()
