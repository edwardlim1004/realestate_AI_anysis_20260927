"""Registry tests: no indicator is automatically promoted."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "review_candidates.py"
SPEC = importlib.util.spec_from_file_location("leading_registry", MODULE)
REGISTRY = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = REGISTRY
SPEC.loader.exec_module(REGISTRY)
REGISTRY_FILE = MODULE.with_name("candidates.json")


class CandidateRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))

    def test_missing_evidence_never_promotes(self):
        result = REGISTRY.compute(self.registry, {})
        self.assertFalse(result["compositeEligible"])
        self.assertIsNone(result["publicCompositeScore"])
        self.assertGreaterEqual(result["indicatorCount"], 10)
        self.assertTrue(all(not x["compositeEligible"] for x in result["indicators"]))

    def test_raw_average_and_future_data_are_quarantined(self):
        result = REGISTRY.compute(self.registry, {})
        out = {r["id"]: r for r in result["indicators"]}
        self.assertEqual(out["RAW_FIVE_YEAR_DISTRICT_MEAN"]["decision"], "QUARANTINE_RESEARCH_ONLY")
        self.assertEqual(out["TWO_SIDED_HP_REALTIME"]["decision"], "QUARANTINE_RESEARCH_ONLY")
        self.assertEqual(out["OLD_NSI_MIXED_WITH_NEW"]["decision"], "QUARANTINE_RESEARCH_ONLY")

    def test_synthetic_metrics_are_ignored(self):
        bogus = {"BOK_NEW_NSI": {str(h): {
            "sourceType": "SYNTHETIC", "oosPredictions": 120,
            "downturnEvents": 40, "rmseReductionPct": 50,
            "dmHacPValue": 0.000001, "falsePositiveRateDeltaPp": -40,
            **{s: True for s in self.registry["decisionThresholds"]["requiredEvidence"]},
        } for h in (1, 3, 6)}}
        out = {r["id"]: r for r in REGISTRY.compute(self.registry, bogus)["indicators"]}
        self.assertEqual(out["BOK_NEW_NSI"]["decision"], "INSUFFICIENT_EVIDENCE")

    def test_official_success_is_still_human_review_only(self):
        good = {"sourceType": "ACTUAL_OFFICIAL_DATA", "oosPredictions": 100,
                "downturnEvents": 30, "rmseReductionPct": 4,
                "dmHacPValue": 0.01, "falsePositiveRateDeltaPp": 1,
                **{s: True for s in self.registry["decisionThresholds"]["requiredEvidence"]}}
        out = {r["id"]: r for r in REGISTRY.compute(self.registry, {"BOK_NEW_NSI": {"1": good}})["indicators"]}
        self.assertEqual(out["BOK_NEW_NSI"]["decision"], "REVIEW_ELIGIBLE_NOT_PRODUCTION")
        self.assertFalse(out["BOK_NEW_NSI"]["promotionPermitted"])

    def test_control_not_counted_twice(self):
        good = {"KOSPI": {"1": {"sourceType": "ACTUAL_OFFICIAL_DATA", "rmseReductionPct": 90}}}
        out = {r["id"]: r for r in REGISTRY.compute(self.registry, good)["indicators"]}
        self.assertEqual(out["KOSPI"]["decision"], "RESEARCH_HOLD")

    def test_unknown_indicator_fails_closed(self):
        with self.assertRaises(ValueError):
            REGISTRY.compute(self.registry, {"FAKE_INDICATOR": {}})


if __name__ == "__main__":
    unittest.main()
