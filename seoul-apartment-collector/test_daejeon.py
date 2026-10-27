"""Daejeon historical coverage, source classification and incremental resume."""
import contextlib
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import backfill_progress
import collect
import google_drive_backup as backup
import r2_gdrive_failover
import regions
from test_incremental import MemoryAPI, MemoryArchive


class DaejeonTests(unittest.TestCase):
    def test_five_districts_same_periods_and_separate_backup(self):
        keys=list(backfill_progress.expected_keys('daejeon'))
        self.assertEqual(2200,len(keys))
        self.assertEqual(1250,sum(key.startswith('sale/') for key in keys))
        self.assertEqual(950,sum(key.startswith('rent/') for key in keys))
        self.assertIn('sale/2006/30110/200601.csv.gz',keys)
        self.assertIn('rent/2011/30230/201101.csv.gz',keys)
        self.assertEqual({'30110','30140','30170','30200','30230'},set(regions.select('daejeon')))
        self.assertEqual('대전광역시 유성구',regions.full_name('30200'))
        self.assertTrue(backup.VALID.fullmatch('rent/2026/30200/202610.csv.gz'))
        self.assertTrue(r2_gdrive_failover.KEY_RE.fullmatch('rent/2026/30200/202610.csv.gz'))
        self.assertEqual(3,len({backup.kind_folders(region)['rent'][0] for region in regions.LABELS}))
        entries={f'rent/2026/{code}/202610.csv.gz':{'sha256':'a'*64,'bytes':100}
                 for code in ('11110','41111','30200')}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'manifest.json'
            path.write_text(json.dumps({'bucket':'edward-seoul-apartment-data','prefix':backup.PREFIX,'files':entries}))
            with patch.object(backup,'MANIFEST',path):
                self.assertEqual({('seoul','rent','2026'),('gyeonggi','rent','2026'),('daejeon','rent','2026')},
                                 set(backup.load_source_manifest('all')))

    def test_new_rent_and_sale_then_unchanged_and_shared_daily_budget(self):
        codes=['11110','41111','30110'];store=MemoryArchive();store.seed(codes)
        common={'aptNm':'대전단지','dealYear':'2026','dealMonth':'10','dealDay':'27'}
        data={('sale','30110','202610'):[{**common,'dealAmount':'20,000'}],
              ('rent','30110','202610'):[{**common,'monthlyRent':'0','deposit':'10,000'},
                                       {**common,'monthlyRent':'50','deposit':'1,000'}]}
        with tempfile.TemporaryDirectory() as tmp,contextlib.ExitStack() as stack:
            root=Path(tmp)
            for name,value in {'DATA':root/'data','STATE':root/'state.json','STATUS':root/'status.json','UPDATES':root/'updates'}.items():
                stack.enter_context(patch.object(collect,name,value))
            stack.enter_context(patch.object(collect,'R2Storage',return_value=store))
            day=[date(2026,10,27)]
            stack.enter_context(patch.object(collect,'today',side_effect=lambda:day[0]))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            def execute():
                api=MemoryAPI(data)
                self.assertEqual(0,collect.run('daily',1200,3,districts=codes,collector=api))
                return api,json.loads(collect.STATUS.read_text())
            api,status=execute()
            self.assertEqual(36,api.calls);self.assertEqual(2,store.uploads)
            self.assertEqual({'seoul':440,'gyeonggi':440,'daejeon':440},status['completed_by_region'])
            self.assertEqual(0,execute()[0].calls)
            day[0]=date(2026,10,28)
            api,status=execute()
            self.assertEqual(36,api.calls);self.assertEqual(0,status['last_run_changed_scopes'])
            self.assertEqual(2,store.uploads)
            day[0]=date(2026,10,29)
            collect.save_json(collect.STATE,{'usage_day':day[0].isoformat(),'daily_requests':7999})
            self.assertEqual(1,execute()[0].calls)
            self.assertEqual(0,execute()[0].calls)


if __name__=='__main__':unittest.main(verbosity=2)
