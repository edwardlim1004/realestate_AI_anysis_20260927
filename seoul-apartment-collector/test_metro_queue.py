import contextlib
from datetime import date
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import regions
import collect
import backfill_progress as progress
import metro_queue as queue
import google_drive_backup as backup
import r2_gdrive_failover as failover
from test_incremental import MemoryAPI, MemoryArchive

class MetroTests(unittest.TestCase):
    def test_geography_aliases_and_existing_all_preserved(self):
        self.assertEqual(16,len(regions.select('busan')))
        self.assertEqual(9,len(set(regions.CODE_ALIASES.get(c,c) for c in regions.select('daegu'))))
        self.assertEqual(5,len(set(regions.CODE_ALIASES.get(c,c) for c in regions.select('gwangju'))))
        self.assertEqual(set(regions.SEOUL)|set(regions.CURRENT_GYEONGGI)|set(regions.DAEJEON),set(regions.select('all')))
        self.assertEqual('경기도 광주시',regions.full_name('41610'))
        self.assertEqual('광주광역시 동구',regions.full_name('29110'))
        self.assertEqual('전남광주통합특별시 동구',regions.full_name('12210'))
        self.assertEqual('경상북도 군위군',regions.full_name('47720'))
        for city,n in [('busan',7040),('daegu',4400),('gwangju',4400)]:
            keys=list(progress.expected_keys(city));self.assertEqual(n,len(keys))
            self.assertTrue(all(backup.VALID.fullmatch(k) and failover.KEY_RE.fullmatch(k) for k in keys))

    def test_sequential_gate_requires_verified_not_only_uploaded(self):
        report={'cities':{c:{'verified':False,'completed':True} for c in queue.ORDER}}
        self.assertEqual('busan',queue.next_city(report))
        report['cities']['busan']['verified']=True
        self.assertEqual('daegu',queue.next_city(report))
        report['cities']['daegu']['verified']=True
        self.assertEqual('gwangju',queue.next_city(report))
        report['cities']['gwangju']['verified']=True
        self.assertIsNone(queue.next_city(report))

    def test_real_collector_routes_metro_sale_and_both_rent_types_with_quota(self):
        code='26110';common={'aptNm':'부산검증단지','dealYear':'2026','dealMonth':'10','dealDay':'10'}
        data={('sale',code,'202610'):[{**common,'dealAmount':'30,000'}],
              ('rent',code,'202610'):[{**common,'monthlyRent':'0','deposit':'20,000'},
                                        {**common,'monthlyRent':'70','deposit':'1,000'}]}
        store=MemoryArchive()
        with tempfile.TemporaryDirectory() as tmp,contextlib.ExitStack() as stack:
            root=Path(tmp)
            for name in ('DATA','STATE','STATUS','UPDATES'):
                stack.enter_context(patch.object(collect,name,root/(name.lower()+('.json' if name in ('STATE','STATUS') else ''))))
            stack.enter_context(patch.object(collect,'R2Storage',return_value=store))
            stack.enter_context(patch.object(collect,'today',return_value=date(2026,11,1)))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            api=MemoryAPI(data)
            self.assertEqual(0,collect.run('test',8,3,districts=[code],collector=api,region='busan'))
            self.assertEqual(2,api.calls)
            self.assertEqual(2,json.loads(collect.STATUS.read_text())['completed_by_region']['busan'])
            collect.save_json(collect.STATE,{'usage_day':'2026-11-01','daily_requests':8000})
            api=MemoryAPI(data);collect.run('test',8,3,districts=[code],collector=api,region='busan')
            self.assertEqual(0,api.calls)

    def test_current_month_refresh_not_blocked_by_old_audit(self):
        report={'cities':{c:{'completed':True,'verified':True} for c in queue.ORDER}}
        with patch.object(queue,'snapshot',return_value=report),patch.object(collect,'run',return_value=0) as run:
            self.assertEqual(0,queue.run(200))
        calls=run.call_args_list
        self.assertEqual(list(queue.ORDER),[c.kwargs['region'] for c in calls[:3]])
        self.assertTrue(all(c.kwargs['refresh_months']==1 for c in calls[:3]))

    def test_fingerprint_invalidates_changed_or_missing_scope(self):
        key='sale/2006/26110/200601.csv.gz'
        self.assertNotEqual(queue.fingerprint({key:{'sha256':'a'}},[key]),queue.fingerprint({key:{'sha256':'b'}},[key]))
        self.assertNotEqual(queue.fingerprint({},[key]),queue.fingerprint({key:{'sha256':'a'}},[key]))

if __name__=='__main__':unittest.main()
