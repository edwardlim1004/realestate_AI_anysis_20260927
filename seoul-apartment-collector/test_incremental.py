"""No-network end-to-end checks for both regions and semantic incremental writes."""
import contextlib
import copy
import csv
from datetime import date
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import backfill_progress as audit
import collect
import google_drive_backup as backup
import incremental
import r2_bridge
import r2_gdrive_failover
import regions


class MemoryArchive:
    relpath=staticmethod(r2_bridge.R2Storage.relpath)

    def __init__(self):
        self.files={};self.raw={};self.uploads=0;self.reads=0;self.fail=False

    def has_scope(self,kind,gu,ym):return self.relpath(kind,gu,ym) in self.files
    def fallback_enabled(self):return True
    def migrate_legacy(self):pass
    def save_manifest(self):pass
    def stats(self):return {'r2_compressed_bytes':0,'r2_scopes':len(self.files),'r2_objects_uploaded':self.uploads}

    def read_scope(self,relative):
        self.reads+=1
        return copy.deepcopy(self.raw[relative])

    def upload(self,path):
        if self.fail:raise RuntimeError('Google Drive failover not verified')
        relative=path.relative_to(collect.DATA).as_posix()
        blob=path.read_bytes()
        with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as inp:
            self.raw[relative]=[json.loads(row['원본항목JSON']) for row in csv.DictReader(inp)]
        self.files[relative]={'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob),'storage':'r2'}
        self.uploads+=1
        return True

    def seed(self,codes):
        for kind,start in collect.START.items():
            for ym in collect.months(start,'202610'):
                for code in codes:
                    if regions.in_month(code,ym):
                        relative=self.relpath(kind,code,ym)
                        self.files[relative]={'sha256':'a'*64,'bytes':100,'content_sha256':incremental.content_hash([]),'rows':0}
                        self.raw[relative]=[]


class MemoryAPI:
    def __init__(self,data):self.data=data;self.calls=0;self.limit=1200;self.scopes=[]
    def fetch(self,kind,gu,ym):
        self.calls+=1;self.scopes.append((kind,gu,ym))
        return copy.deepcopy(self.data.get((kind,gu,ym),[]))


class IncrementalTests(unittest.TestCase):
    def test_region_coverage_and_boundaries(self):
        current=[c for c in regions.GYEONGGI if regions.in_month(c,'202610')]
        self.assertEqual(47,len(current))
        self.assertEqual(31,len({regions.GYEONGGI[c].split()[0] for c in current}))
        self.assertEqual(11000,len(list(audit.expected_keys())))
        self.assertEqual(19062,len(list(audit.expected_keys('gyeonggi'))))
        self.assertTrue(regions.in_month('41590','202601'))
        self.assertFalse(regions.in_month('41590','202602'))
        self.assertTrue(regions.in_month('41591','202602'))
        self.assertFalse(regions.in_month('41591','202601'))
        self.assertTrue(regions.in_month('41190','202312'))
        self.assertFalse(regions.in_month('41190','202401'))
        self.assertTrue(regions.in_month('41192','202401'))
        self.assertFalse(regions.in_month('41192','202312'))
        self.assertTrue(regions.in_month('41195','201607'))
        self.assertTrue(regions.in_month('41730','201309'))
        self.assertNotEqual(regions.full_name('11110'),regions.full_name('41111'))
        self.assertTrue(r2_gdrive_failover.KEY_RE.fullmatch('rent/2026/41597/202610.csv.gz'))

    def test_deterministic_gzip_and_duplicate_multiplicity(self):
        a={'aptNm':'A','dealYear':'2026','dealMonth':'10','dealDay':'20'}
        b={**a,'aptNm':'B'}
        with tempfile.TemporaryDirectory() as tmp,patch.object(collect,'DATA',Path(tmp)):
            collect.save_scope('sale','41111','202610',[a,a,b])
            path=collect.scope('sale','41111','202610');first=path.read_bytes()
            collect.save_scope('sale','41111','202610',[b,a,a])
            self.assertEqual(first,path.read_bytes())
            with gzip.open(path,'rt',encoding='utf-8-sig',newline='') as inp:
                rows=list(csv.DictReader(inp))
            self.assertEqual(3,len(rows))
            self.assertTrue(all(r['시군구']=='경기도 수원시 장안구' for r in rows))
        self.assertEqual(incremental.content_hash([a,b,a]),incremental.content_hash([b,a,a]))
        self.assertNotEqual(incremental.content_hash([a,a]),incremental.content_hash([a]))

    def test_daily_resume_unchanged_corrections_failures_and_shared_budget(self):
        codes=['11110','41111'];store=MemoryArchive();store.seed(codes)
        a={'aptNm':'GG A','dealYear':'2026','dealMonth':'10','dealDay':'20','dealAmount':'10,000'}
        data={('sale','41111','202610'):[a,a]}
        # Simulate a legacy entry without the new semantic checksum.
        del store.files[store.relpath('rent','41111','202610')]['content_sha256']
        with tempfile.TemporaryDirectory() as tmp,contextlib.ExitStack() as stack:
            root=Path(tmp)
            for name,value in {'DATA':root/'data','STATE':root/'state.json','STATUS':root/'status.json','UPDATES':root/'updates'}.items():
                stack.enter_context(patch.object(collect,name,value))
            stack.enter_context(patch.object(collect,'R2Storage',return_value=store))
            day=[date(2026,10,21)]
            stack.enter_context(patch.object(collect,'today',side_effect=lambda:day[0]))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            def execute(mode='daily',districts=codes):
                api=MemoryAPI(data)
                result=collect.run(mode,1200,3,districts=districts,collector=api)
                return result,api,json.loads(collect.STATUS.read_text())
            result,api,status=execute()
            self.assertEqual(0,result);self.assertEqual(24,api.calls)
            self.assertEqual(1,store.uploads);self.assertEqual(1,status['last_run_changed_scopes'])
            self.assertEqual(23,status['last_run_unchanged_scopes'])
            logs=list((root/'updates').rglob('*.jsonl'))
            self.assertEqual(1,len(logs));self.assertEqual(1,len(logs[0].read_text().splitlines()))
            result,api,_=execute()
            self.assertEqual(0,api.calls);self.assertEqual(1,store.uploads)
            reads=store.reads
            day[0]=date(2026,10,22)
            data[('sale','41111','202610')]=list(reversed(data[('sale','41111','202610')]))
            result,api,status=execute()
            self.assertEqual(24,api.calls);self.assertEqual(0,status['last_run_changed_scopes'])
            self.assertEqual(reads,store.reads);self.assertEqual(1,store.uploads)
            day[0]=date(2026,10,23)
            data[('sale','41111','202610')]=[a,{**a,'cdealDay':'20261023'},{**a,'aptNm':'GG B'}]
            result,_,status=execute()
            self.assertEqual(2,status['last_run_added_rows']);self.assertEqual(1,status['last_run_removed_rows'])
            self.assertEqual(2,store.uploads)
            events=[json.loads(line) for line in logs[0].read_text().splitlines()]
            self.assertEqual(2,len(events));self.assertEqual('updated',events[-1]['kind'])
            day[0]=date(2026,10,24)
            data[('sale','11110','202610')]=[{**a,'aptNm':'Seoul A'}]
            previous=copy.deepcopy(store.files);store.fail=True
            result,api,_=execute()
            self.assertEqual(1,result);self.assertEqual(1,api.calls)
            self.assertEqual(previous,store.files)
            self.assertEqual(2,len(logs[0].read_text().splitlines()))
            store.fail=False
            result,_,_=execute()
            self.assertEqual(0,result);self.assertEqual(3,store.uploads)
            # Region-specific runs share the same persisted quota ledger.
            collect.save_json(collect.STATE,{'usage_day':day[0].isoformat(),'daily_requests':7999})
            _,api,status=execute(districts=['41111'])
            self.assertEqual(1,api.calls);self.assertEqual(8000,status['requests_today'])
            _,api,status=execute(districts=['11110'])
            self.assertEqual(0,api.calls);self.assertEqual(8000,status['requests_today'])

    def test_bootstrap_cannot_overwrite_incremental_archive(self):
        from test_storage_failover import fake_archive
        store=fake_archive()
        relative='sale/2026/11710/202610.csv.gz'
        verified={'sha256':'b'*64,'bytes':100,'content_sha256':'c'*64}
        store.files[relative]=verified.copy()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'data'/relative
            source.parent.mkdir(parents=True);source.write_bytes(b'obsolete bootstrap archive')
            with patch.object(r2_bridge,'DATA',root/'data'),patch.object(r2_bridge,'MANIFEST',root/'manifest.json'):
                store.migrate_legacy()
            self.assertEqual(verified,store.files[relative]);self.assertEqual([],store.client.sent)

    def test_backups_keep_seoul_and_gyeonggi_separate(self):
        entries={}
        for code in ('11710','41111'):
            relative=f'sale/2026/{code}/202610.csv.gz'
            entries[relative]={'sha256':'a'*64,'bytes':100}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'manifest.json'
            path.write_text(json.dumps({'bucket':'edward-seoul-apartment-data','prefix':backup.PREFIX,'files':entries}))
            with patch.object(backup,'MANIFEST',path):
                seoul=backup.load_source_manifest()
                combined=backup.load_source_manifest(region='all')
            self.assertEqual(1,len(seoul[('sale','2026')]))
            self.assertEqual({('seoul','sale','2026'),('gyeonggi','sale','2026')},set(combined))
            self.assertEqual('sale-2026',backup.annual_key('seoul','sale','2026'))
            self.assertNotEqual(backup.annual_key('seoul','sale','2026'),backup.annual_key('gyeonggi','sale','2026'))
            self.assertNotEqual(backup.kind_folders('seoul')['sale'],backup.kind_folders('gyeonggi')['sale'])


if __name__=='__main__':unittest.main(verbosity=2)
