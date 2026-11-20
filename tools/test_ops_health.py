import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ops_health import assess


class OpsHealthTests(unittest.TestCase):
    def setUp(self):
        self.status = {
            "as_of_kst": "2026-11-20",
            "total_completed_scopes": 51256,
            "total_scopes": 51256,
            "last_run_failures": 0,
        }
        self.quality = {"status": "REVIEW", "structuralErrors": [], "qualityWarnings": []}
        self.today = date(2026, 11, 20)

    def test_storage_scope_count_not_semantic_validation(self):
        report = assess(self.status, self.quality, [], self.today)
        self.assertIn("manifest progress only", report["storage_scope_progress"]["meaning"])
        self.assertEqual(report["status"], "REVIEW")

    def test_latest_workflow_failure_requires_action(self):
        runs = [{"name": "Seoul Gyeonggi and Daejeon Apartment Collector (Safe)",
                 "status": "completed", "conclusion": "failure", "id": 12,
                 "created_at": "2026-11-19T22:00:00Z",
                 "html_url": "https://github.com/example/repo/actions/runs/12"}]
        report = assess(self.status, self.quality, runs, self.today)
        self.assertEqual(report["status"], "ACTION_REQUIRED")
        self.assertTrue(any("Latest run failed" in issue for issue in report["incidents"]))

    def test_stale_status_is_not_pass(self):
        self.status["as_of_kst"] = "2026-11-16"
        report = assess(self.status, self.quality, [], self.today)
        self.assertEqual(report["status"], "ACTION_REQUIRED")

    def test_structural_errors_block(self):
        self.quality["structuralErrors"] = ["unexpected null region"]
        report = assess(self.status, self.quality, [], self.today)
        self.assertEqual(report["status"], "ACTION_REQUIRED")

    def test_no_failure_when_latest_recovered(self):
        runs = [
            {"name": "Build Metro Monthly History", "status": "completed",
             "conclusion": "failure", "created_at": "2026-11-19T20:00:00Z"},
            {"name": "Build Metro Monthly History", "status": "completed",
             "conclusion": "success", "created_at": "2026-11-19T22:00:00Z"},
        ]
        report = assess(self.status, self.quality, runs, self.today)
        self.assertFalse(any("Latest run failed" in issue for issue in report["incidents"]))


if __name__ == "__main__":
    unittest.main()
