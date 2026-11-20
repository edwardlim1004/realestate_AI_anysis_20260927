"""Release-calendar tests: published-after-forecast data must not be used."""
import importlib.util
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FILE = ROOT / "publication_audit.py"
SPEC = importlib.util.spec_from_file_location("publication_audit", FILE)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class PITCalendarTests(unittest.TestCase):
    def fixture(self):
        t = date(2026, 10, 1)
        d = {
            ("SEOUL_APARTMENT_PRICE", date(2026, 9, 1)): date(2026, 10, 15),
            ("SEOUL_APARTMENT_PRICE", date(2026, 8, 1)): date(2026, 9, 15),
            ("SEOUL_APARTMENT_PRICE", date(2026, 7, 1)): date(2026, 8, 15),
            ("BOK_NEW_NSI", date(2026, 9, 1)): date(2026, 10, 3),
            ("BOK_NEW_NSI", date(2026, 8, 1)): date(2026, 9, 3),
            ("REAL_RATE", date(2026, 5, 1)): date(2026, 6, 6),
            ("EXCESS_LIQUIDITY", date(2025, 12, 1)): date(2026, 2, 7),
            ("KOSPI_RETURN", date(2026, 9, 1)): date(2026, 9, 30),
        }
        return t, d

    def test_release_calendar_only_never_full_pit(self):
        t, calendar = self.fixture()
        result = MOD.check_origin(t, calendar)
        self.assertTrue(result["releaseCalendarPass"])
        self.assertFalse(result["verifiedArchiveVintages"])

    def test_housing_index_not_available_before_release(self):
        t, calendar = self.fixture()
        result = MOD.check_origin(t, calendar, day=10)
        self.assertFalse(result["releaseCalendarPass"])
        self.assertEqual(result["failures"][0]["series"], "SEOUL_APARTMENT_PRICE")
        self.assertEqual(result["failures"][0]["reason"], "NOT_YET_PUBLIC_AT_FORECAST")

    def test_retroactive_new_nsi_cannot_backdate_first_release(self):
        t, calendar = self.fixture()
        calendar[("BOK_NEW_NSI", date(2026, 8, 1))] = date(2026, 11, 1)
        result = MOD.check_origin(t, calendar, day=20)
        self.assertFalse(result["releaseCalendarPass"])
        self.assertEqual(result["status"], "RELEASE_NOT_AVAILABLE")

    def test_missing_publication_is_rejected(self):
        t, calendar = self.fixture()
        del calendar[("EXCESS_LIQUIDITY", date(2025, 12, 1))]
        self.assertFalse(MOD.check_origin(t, calendar)["releaseCalendarPass"])

    def test_calendar_csv_rejects_duplicates(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "calendar.csv"
            p.write_text("series,month,first_published_date\n"
                         "BOK_NEW_NSI,2026-09,2026-10-03\n"
                         "BOK_NEW_NSI,2026-09,2026-10-04\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                MOD.load_release_calendar(p)

    def test_audit_never_promotes(self):
        t, cal = self.fixture()
        out = MOD.audit(t, t, cal)
        self.assertEqual(out["releaseCalendarEligible"], 1)
        self.assertFalse(out["fullPITVerified"])
        self.assertFalse(out["readyForProduction"])


if __name__ == "__main__":
    unittest.main()
