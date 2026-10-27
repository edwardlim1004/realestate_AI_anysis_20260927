"""Excluded periods must be probed even when every planned archive exists."""
import contextlib
from datetime import date
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_region_history as audit
import collect


class FakeAPI:
    calls=0
    limit=128
    def fetch(self,kind,gu,ym):
        self.calls+=1
        return [{'sggCd':gu,'dealYear':ym[:4]}] if kind=='sale' and gu=='41195' and ym=='201608' else []


class HistoryTests(unittest.TestCase):
    def test_probes_cover_reorganization_boundaries(self):
        items=set(audit.probes('202610'))
        for item in [('sale','41195','201608'),('rent','41190','202610')]:
            self.assertIn(item,items)
        self.assertNotIn(('sale','30110','200601'),items)
        self.assertNotIn(('sale','41591','200601'),items)
        self.assertNotIn(('rent','41192','201101'),items)

    def test_unplanned_available_history_prevents_false_completion(self):
        with tempfile.TemporaryDirectory() as tmp,contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(audit,'REPORT',Path(tmp)/'report.json'))
            stack.enter_context(patch.object(collect,'STATE',Path(tmp)/'state.json'))
            stack.enter_context(patch.object(collect,'today',return_value=date(2026,10,27)))
            api=FakeAPI()
            stack.enter_context(patch.object(collect,'Collector',return_value=api))
            stack.enter_context(patch.dict(os.environ,{'MOLIT_SERVICE_KEY':'fake'}))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            self.assertEqual(1,audit.run())
            report=json.loads(audit.REPORT.read_text())
            self.assertFalse(report['passed'])
            self.assertEqual(1,len(report['unplanned_nonempty_scopes']))
            self.assertEqual(api.calls,json.loads(collect.STATE.read_text())['daily_requests'])


if __name__=='__main__':unittest.main(verbosity=2)
