"""Offline ECOS parser tests: never connect to live API in CI."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

FILE = Path(__file__).resolve().parents[1] / "ecos_nsi_discovery.py"
SPEC = importlib.util.spec_from_file_location("ecos_nsi_discovery", FILE)
MOD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MOD
SPEC.loader.exec_module(MOD)


class EcosNSISafetyTests(unittest.TestCase):
    def contract(self, **changes):
        out = {"statCode": "523Y001", "itemCode": "A", "frequency": "M",
               "seriesName": "뉴스심리지수", "methodVersion": "BOK_NEW_NSI_2026_09",
               "approver": "research reviewer", "approvalDate": "2026-11-19",
               "bokEvidenceUrl": MOD.RESEARCH_URL, "historicalSeriesIsBackcast": True}
        out.update(changes)
        return out

    def test_requires_verified_methodology(self):
        with self.assertRaises(ValueError):
            MOD.validate_approval(self.contract(methodVersion="OLD_NSI"))
        with self.assertRaises(ValueError):
            MOD.validate_approval(self.contract(historicalSeriesIsBackcast=None))
        with self.assertRaises(ValueError):
            MOD.validate_approval(self.contract(bokEvidenceUrl="https://example.com"))
        with self.assertRaises(ValueError):
            MOD.validate_approval({"statCode": "523Y001"})

    def test_no_unverified_code_or_name_substitution(self):
        contract = self.contract()
        official_items = [{"statCode": "523Y001", "itemCode": "B", "cycle": "M",
                           "itemName": "뉴스심리지수", "unit": "지수"}]
        with patch.object(MOD, "discover_items", return_value=official_items):
            with self.assertRaises(ValueError):
                MOD.export_monthly("fake", contract, "202609", "202610")

    def test_export_stamps_no_pit_verification(self):
        metadata = [{"statCode": "523Y001", "itemCode": "A", "cycle": "M",
                     "itemName": "뉴스심리지수", "unit": "지수"}]
        data = [
            {"STAT_CODE": "523Y001", "ITEM_CODE1": "A", "TIME": "202609", "DATA_VALUE": "101.5"},
            {"STAT_CODE": "523Y001", "ITEM_CODE1": "A", "TIME": "202610", "DATA_VALUE": "99.2"}
        ]
        with patch.object(MOD, "discover_items", return_value=metadata):
            with patch.object(MOD, "ecos_call", return_value=(data, 2)):
                text, manifest = MOD.export_monthly("fake", self.contract(), "202609", "202610")
        self.assertIn("2026-09,101.5", text)
        self.assertEqual(manifest["observationCount"], 2)
        self.assertFalse(manifest["pitVerified"])
        self.assertTrue(manifest["approval"]["historicalSeriesIsBackcast"])

    def test_rejects_duplicate_or_incomplete(self):
        metadata = [{"statCode": "523Y001", "itemCode": "A", "cycle": "M",
                     "itemName": "뉴스심리지수", "unit": "지수"}]
        row = {"STAT_CODE": "523Y001", "ITEM_CODE1": "A",
               "TIME": "202609", "DATA_VALUE": "101"}
        with patch.object(MOD, "discover_items", return_value=metadata):
            with patch.object(MOD, "ecos_call", return_value=([row, row], 2)):
                with self.assertRaises(ValueError):
                    MOD.export_monthly("fake", self.contract(), "202609", "202610")
            with patch.object(MOD, "ecos_call", return_value=([row], 2)):
                with self.assertRaises(ValueError):
                    MOD.export_monthly("fake", self.contract(), "202609", "202610")


if __name__ == "__main__":
    unittest.main()
