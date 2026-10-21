"""Validate failed-run reconciliation without API credentials or network calls."""
import contextlib
import copy
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import recover_failed_run as recovery
from r2_bridge import R2Storage, PREFIX


def payload(ym, records):
    text = io.StringIO(newline='')
    writer = csv.DictWriter(text, fieldnames=['계약년월','원본항목JSON'])
    writer.writeheader()
    for record in records:
        writer.writerow({'계약년월':ym, '원본항목JSON':json.dumps(record)})
    return gzip.compress(text.getvalue().encode('utf-8-sig'), mtime=0)


class Archive:
    relpath = staticmethod(R2Storage.relpath)
    def __init__(self, files, objects, manifest):
        self.files = files
        self.bucket = 'dummy'
        self.client = self
        self.objects = objects
        self.manifest = manifest
        self.calls = 0
    def get_object(self, Bucket, Key):
        self.calls += 1
        blob = self.objects[Key]
        return {'Body':io.BytesIO(blob), 'ContentLength':len(blob),
                'LastModified':datetime(2026,10,21,12,30,tzinfo=timezone.utc)}
    def save_manifest(self):
        self.manifest.write_text(json.dumps({'files':self.files}))


class RecoveryTests(unittest.TestCase):
    def fixture(self, root):
        old = 'sale/2026/11110/202610.csv.gz'
        new = 'rent/2026/41111/202610.csv.gz'
        objects = {PREFIX+old:payload('202610', [{'id':'corrected'}]),
                   PREFIX+new:payload('202610', [{'id':'new'},{'id':'new'}])}
        files = {old:{'sha256':'a'*64,'bytes':10}}
        manifest = root/'manifest.json'
        manifest.write_text(json.dumps({'files':files}))
        base = {'usage_day':'2026-10-21','daily_requests':3457}
        recovery.STATE.write_text(json.dumps(base))
        recovery.STATUS.write_text('{}')
        plan = {'run_id':123, 'source_url':'https://github.com/example/repo/actions/runs/123',
            'base_state':base, 'base_manifest_blob_sha':recovery.git_blob_sha(manifest.read_bytes()),
            'started_at_utc':'2026-10-21T12:00:00Z', 'finished_at_utc':'2026-10-21T13:00:00Z',
            'state_after':{'usage_day':'2026-10-21','daily_requests':4657,'refresh_done':['sale/11110/202610']},
            'status_after':{'last_run_changed_scopes':2,'total_completed_scopes':2,
                'r2_compressed_bytes':sum(map(len,objects.values())),
                'completed_by_region':{'seoul':1,'gyeonggi':1},
                'last_run_added_rows':3,'last_run_removed_rows':1},
            'scopes':[['sale','11110','202610',1],['rent','41111','202610',2]]}
        return plan, Archive(copy.deepcopy(files),objects,manifest)

    @contextlib.contextmanager
    def location(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            root = Path(tmp)
            for key,name in [('STATE','state.json'),('MANIFEST','manifest.json'),('STATUS','status.json'),
                             ('UPDATES','updates'),('RECEIPT','receipt.json')]:
                stack.enter_context(patch.object(recovery,key,root/name))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            yield root

    def test_reread_hashes_quota_and_idempotent_recovery(self):
        with self.location() as root:
            plan, archive = self.fixture(root)
            recovery.recover(plan,archive)
            self.assertEqual(2,archive.calls)
            result = json.loads(recovery.MANIFEST.read_text())['files']
            self.assertEqual(2,len(result))
            for relative,meta in result.items():
                self.assertEqual(hashlib.sha256(archive.objects[PREFIX+relative]).hexdigest(),meta['sha256'])
            state = json.loads(recovery.STATE.read_text())
            self.assertEqual(4657,state['daily_requests'])
            self.assertEqual(['123'],state['recovered_runs'])
            events = [json.loads(line) for path in recovery.UPDATES.rglob('*.jsonl') for line in path.read_text().splitlines()]
            self.assertEqual(2,len(events))
            previous = next(event for event in events if event['kind']=='recovered_snapshot')
            self.assertIsNone(previous['added_rows'])
            recovery.recover(plan,archive)
            self.assertEqual(2,archive.calls)

    def test_wrong_rows_or_corrupt_gzip_cannot_update_any_state(self):
        for damage in ('rows','gzip','baseline','time'):
            with self.subTest(damage=damage), self.location() as root:
                plan,archive = self.fixture(root)
                before = {path:path.read_bytes() for path in (recovery.STATE,recovery.MANIFEST,recovery.STATUS)}
                if damage=='rows':plan['scopes'][1][-1] = 3
                if damage=='gzip':archive.objects[PREFIX+'sale/2026/11110/202610.csv.gz'] = b'not a gzip'
                if damage=='baseline':plan['base_state']['daily_requests'] = 1
                if damage=='time':plan['started_at_utc'] = '2026-10-21T12:45:00Z'
                with self.assertRaises((ValueError,OSError,EOFError)):
                    recovery.recover(plan,archive)
                self.assertEqual(before,{path:path.read_bytes() for path in before})
                self.assertFalse(recovery.RECEIPT.exists())
                self.assertFalse(recovery.UPDATES.exists())


if __name__=='__main__':unittest.main(verbosity=2)
