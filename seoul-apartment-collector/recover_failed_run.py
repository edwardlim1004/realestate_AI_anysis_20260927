"""One-time recovery of uploaded results whose final Git commit failed.

The plan is evidence from the completed job log and its sanitized artifact.
No official-data requests, uploads, deletes, or credential output occur here.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path

from collect import save_json
from incremental import content_hash, record_change
from r2_bridge import R2Storage, PREFIX
from r2_gdrive_failover import KEY_RE

BASE = Path(__file__).resolve().parent
PLAN = BASE / 'recoveries/39597380565.json'
STATE = BASE / 'state.json'
MANIFEST = BASE / 'r2_manifest.json'
STATUS = BASE / 'status.json'
UPDATES = BASE / 'updates'
RECEIPT = BASE / 'recoveries/39597380565.receipt.json'


def output_recovered(value):
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as out:
            out.write('recovered='+str(value).lower()+'\n')


def git_blob_sha(blob):
    return hashlib.sha1(b'blob '+str(len(blob)).encode()+b'\0'+blob).hexdigest()


def read_verified_scope(archive, item, plan):
    kind, district, ym, expected_rows = item
    relative = archive.relpath(kind, district, ym)
    if not KEY_RE.fullmatch(relative):
        raise ValueError('Invalid recovery scope')
    response = archive.client.get_object(Bucket=archive.bucket, Key=PREFIX+relative)
    body = response['Body']
    try:
        blob = body.read(50*1024*1024+1)
    finally:
        body.close()
    if not 0 < len(blob) <= 50*1024*1024 or len(blob) != response['ContentLength']:
        raise ValueError('Recovery source byte count mismatch: '+relative)
    modified = response['LastModified']
    start = datetime.fromisoformat(plan['started_at_utc'].replace('Z', '+00:00'))
    end = datetime.fromisoformat(plan['finished_at_utc'].replace('Z', '+00:00'))
    if not start <= modified <= end:
        raise ValueError('Recovery object is outside failed run interval: '+relative)
    records = []
    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as compressed:
        with io.TextIOWrapper(compressed, encoding='utf-8-sig', newline='') as inp:
            reader = csv.DictReader(inp)
            if not {'계약년월','원본항목JSON'} <= set(reader.fieldnames or []):
                raise ValueError('Recovery source header mismatch')
            for row in reader:
                raw = json.loads(row['원본항목JSON'])
                if row['계약년월'] != ym or not isinstance(raw, dict):
                    raise ValueError('Recovery source contract month mismatch')
                records.append(raw)
                if len(records) > 60000:
                    raise ValueError('Recovery source row bound exceeded')
    if len(records) != expected_rows:
        raise ValueError('Recovery source does not match successful job row count: '+relative)
    return relative, {'sha256':hashlib.sha256(blob).hexdigest(), 'bytes':len(blob),
                      'storage':'r2', 'content_sha256':content_hash(records), 'rows':len(records)}


def recover(plan=None, archive=None):
    plan = plan or json.loads(PLAN.read_text(encoding='utf-8'))
    state = json.loads(STATE.read_text(encoding='utf-8'))
    run_id = str(plan['run_id'])
    if run_id in state.get('recovered_runs', []):
        output_recovered(False)
        print('RECOVERY_ALREADY_COMPLETE', run_id, flush=True)
        return
    # Refuse to overwrite newer collection state or a different source manifest.
    if state != plan['base_state'] or git_blob_sha(MANIFEST.read_bytes()) != plan['base_manifest_blob_sha']:
        raise ValueError('Recovery baseline moved; manual reconciliation required')
    archive = archive or R2Storage()
    before = archive.files
    after = copy.deepcopy(before)
    scopes = plan['scopes']
    if len(scopes) != plan['status_after']['last_run_changed_scopes']:
        raise ValueError('Recovery plan changed-scope count mismatch')
    verified = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for relative, meta in pool.map(lambda item:read_verified_scope(archive, item, plan), scopes):
            if relative in verified:
                raise ValueError('Duplicate recovery scope')
            verified[relative] = meta
    after.update(verified)
    expected = plan['status_after']
    r2_bytes = sum(int(v['bytes']) for v in after.values())
    by_region = {region:sum(key.split('/')[2].startswith(prefix) for key in after)
                 for region,prefix in [('seoul','11'), ('gyeonggi','41')]}
    if (any(v.get('storage','r2') != 'r2' for v in after.values()) or
            len(after) != expected['total_completed_scopes'] or
            r2_bytes != expected['r2_compressed_bytes'] or
            by_region != expected['completed_by_region']):
        raise ValueError('Recovered manifest does not match failed-run totals')
    # Nothing is persisted until every downloaded scope and aggregate matches.
    archive.files = after
    archive._r2_bytes = r2_bytes
    archive.save_manifest()
    day = plan['state_after']['usage_day']
    for relative, meta in verified.items():
        is_new = relative not in before
        event_id = hashlib.sha256((run_id+'|'+relative+'|'+meta['sha256']).encode()).hexdigest()
        record_change(UPDATES, {'event_id':event_id, 'scope':relative,
            'kind':'new_scope' if is_new else 'recovered_snapshot',
            'source_run_id':int(run_id), 'observed_day_kst':day,
            'rows':meta['rows'], 'after_content_sha256':meta['content_sha256'],
            'before_content_sha256':before.get(relative,{}).get('content_sha256'),
            'added_rows':meta['rows'] if is_new else None,
            'removed_rows':0 if is_new else None,
            'recovery_note':'Existing scopes have unknown per-scope deltas; run totals are in the recovery receipt.'})
    receipt = {'run_id':int(run_id), 'source_url':plan['source_url'],
        'verified_at_utc':datetime.now(timezone.utc).isoformat(),
        'r2_scopes_reread':len(verified), 'completed_by_region':by_region,
        'r2_compressed_bytes':r2_bytes,
        'requests_today_restored':plan['state_after']['daily_requests'],
        'added_rows_from_job_report':expected['last_run_added_rows'],
        'removed_rows_from_job_report':expected['last_run_removed_rows'],
        'note':'Per-scope original change summaries were not in the failed artifact; recovered snapshots identify this limitation.'}
    save_json(RECEIPT, receipt)
    save_json(STATUS, {**expected, 'recovery':receipt})
    save_json(STATE, {**plan['state_after'], 'recovered_runs':[*state.get('recovered_runs',[]), run_id]})
    output_recovered(True)
    print('RECOVERY_VERIFIED', json.dumps(receipt), flush=True)


if __name__ == '__main__':
    recover()
