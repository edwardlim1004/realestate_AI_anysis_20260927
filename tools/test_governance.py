#!/usr/bin/env python3
"""Offline unit tests for the read-only governance validator."""
import unittest
from validate_governance import MODULE_IDS, validate, validate_changed_paths, valid_relative

class GovernanceTests(unittest.TestCase):
    def test_structural_registry(self):
        self.assertEqual(len(MODULE_IDS), 10)
        self.assertEqual(validate(), [])

    def test_allow_only_governance_paths(self):
        self.assertEqual(validate_changed_paths(["operations/STATUS.md", "tools/ai_task.py"]), [])
        self.assertTrue(validate_changed_paths(["ver0/index.html"]))
        self.assertTrue(validate_changed_paths(["dashboard-v1/app.js"]))
        self.assertTrue(validate_changed_paths([".github/workflows/update-data.yml"]))

    def test_reject_traversal(self):
        self.assertFalse(valid_relative("../data.js"))
        self.assertFalse(valid_relative("/tmp/foo"))
        self.assertFalse(valid_relative("operations/../ver0/index.html"))
        self.assertTrue(validate_changed_paths(["operations/../ver0/index.html"]))

if __name__ == "__main__":
    unittest.main()
