#!/usr/bin/env python3
"""Live reread of every required archive, with bounded official-source checks.

The result distinguishes physical completeness from original API coverage.
Identical transactions are counted with multiplicity, never deduplicated.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading

import backfill_progress
import collect
from google_drive_backup import authorized_drive, download_verified_source, s3_client
from incremental import canonical, content_hash
from regions import full_name, region_for

BASE=Path(__file__).resolve().parent
REPORT=BASE/'coverage_audit.json'
DETAILS=BASE/'coverage_audit_scopes.jsonl.gz'
MAX_TEXT=100*1024*1024
THREAD=threading.local()


def inspect_scope(key,meta,payload):
    """Verify bytes, gzip/CSV, normalized fields, original rows and rent split."""
    if len(payload)!=meta['bytes']:raise ValueError('byte_size_mismatch')
    if hashlib.sha256(payload).hexdigest()!=meta['sha256']:raise ValueError('sha256_mismatch')
    with gzip.GzipFile(fileobj=io.BytesIO(payload)) as inp:
        data=inp.read(MAX_TEXT+1)
    if len(data)>MAX_TEXT:raise ValueError('uncompressed_size_limit')
    kind,year,gu,name=key.split('/');ym=name[:6]
    csv.field_size_limit(2*1024*1024)
    reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''))
    if reader.fieldnames!=collect.FIELDS:raise ValueError('csv_schema_mismatch')
    raw=[];split=Counter();seen=Counter()
    for record in reader:
        if None in record or any(value is None for value in record.values()):
            raise ValueError('csv_column_mismatch')
        original=json.loads(record['원본항목JSON'])
        if not isinstance(original,dict):raise ValueError('invalid_original_json')
        normalized=collect.row(kind,gu,ym,original)
        if any(record[field]!=normalized[field] for field in collect.FIELDS):
            raise ValueError('normalized_original_mismatch')
        if record['계약년월']!=ym or not record['계약일']:
            raise ValueError('contract_date_mismatch')
        raw_code=collect.field(original,'sggCd','지역코드')
        if raw_code and raw_code!=gu:raise ValueError('district_mismatch')
        if kind=='rent':
            value=record['월세금(만원)'].replace(',','')
            try:monthly=Decimal(value)
            except InvalidOperation:raise ValueError('unclassified_rent') from None
            if not monthly.is_finite() or monthly<0:raise ValueError('invalid_monthly_rent')
            split['jeonse' if monthly==0 else 'monthly']+=1
        else:split['sale']+=1
        raw.append(original);seen[canonical(original)]+=1
    digest=content_hash(raw)
    if 'rows' in meta and meta['rows']!=len(raw):raise ValueError('row_count_mismatch')
    if meta.get('content_sha256') and meta['content_sha256']!=digest:
        raise ValueError('original_content_sha256_mismatch')
    return {'scope':key,'status':'ok','rows':len(raw),'content_sha256':digest,
            'storage':meta.get('storage','r2'),'transactions':dict(split),
            'identical_extra_rows':sum(n-1 for n in seen.values()),
            'had_manifest_row_count':'rows' in meta,
            'had_manifest_content_sha256':bool(meta.get('content_sha256'))}


def read_one(s3,key,meta):
    if meta.get('storage','r2')=='gdrive' and not hasattr(THREAD,'drive'):
        # googleapiclient's HTTP transport is not shared across threads.
        THREAD.drive=authorized_drive(s3)
    entry=(key,meta['sha256'],meta['bytes'])
    if meta.get('storage','r2')=='gdrive':entry=(*entry,meta['drive_file_id'])
    for attempt in range(3):
        try:
            with tempfile.TemporaryDirectory(prefix='apt_audit_') as tmp:
                target=Path(tmp)/'scope.gz'
                download_verified_source(s3,entry,target,drive=getattr(THREAD,'drive',None))
                return inspect_scope(key,meta,target.read_bytes())
        except Exception as exc:
            if attempt==2:
                # Exception text can contain signed URLs/IDs, so omit it.
                return {'scope':key,'status':'error','error_type':type(exc).__name__}


def source_checks(results,max_requests):
    """Requery every empty scope plus one nonempty scope per region/type/year."""
    empty=sorted(item['scope'] for item in results if item['status']=='ok' and item['rows']==0)
    samples={}
    for item in sorted(results,key=lambda v:v['scope']):
        if item['status']!='ok' or not item['rows']:continue
        kind,year,gu,_=item['scope'].split('/')
        samples.setdefault((region_for(gu),kind,year),item['scope'])
    keys=list(dict.fromkeys(empty+list(samples.values())))
    hashes={item['scope']:item.get('content_sha256') for item in results}
    state=collect.read_state();day=collect.today().isoformat()
    used=int(state.get('daily_requests',0)) if state.get('usage_day')==day else 0
    allowed=min(max_requests,max(0,collect.DAILY_MAX_REQUESTS-used))
    key=os.getenv('MOLIT_SERVICE_KEY') or os.getenv('DATA_GO_KR_SERVICE_KEY')
    if not key:return {'requested':len(keys),'checked':0,'pending':len(keys),'status':'missing_api_key'}
    api=collect.Collector(key,allowed,3);checked=[];different=[];errors=[]
    try:
        for relative in keys:
            if api.calls>=api.limit:break
            kind,_,gu,name=relative.split('/')
            try:
                raw=api.fetch(kind,gu,name[:6])
                checked.append(relative)
                if content_hash(raw)!=hashes[relative]:different.append(relative)
            except Exception as exc:
                errors.append({'scope':relative,'error_type':type(exc).__name__})
                break
    finally:
        state.update({'usage_day':day,'daily_requests':used+api.calls})
        collect.save_json(collect.STATE,state)
    return {'status':'ok' if len(checked)==len(keys) and not different and not errors else 'needs_review',
            'requested':len(keys),'checked':len(checked),'pending':len(keys)-len(checked),
            'empty_scopes':len(empty),'historical_samples':len(keys)-len(empty),
            'requests':api.calls,'different_scopes':different,'errors':errors,
            'note':'Empty scopes and stratified samples only; not a requery of every transaction.'}


def run(regions,workers=12,live_source=False,max_requests=1200):
    required=sorted({key for region in regions for key in backfill_progress.expected_keys(region)})
    manifest=json.loads((BASE/'r2_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('bucket')!=os.environ['R2_BUCKET_NAME'] or manifest.get('prefix')!='seoul-apartments/v1/':
        raise ValueError('archive_identity_mismatch')
    files=manifest['files'];s3=s3_client();results=[];tasks=[]
    for key in required:
        meta=files.get(key,{})
        if not backfill_progress.completeness(files,[key])['completed']:
            results.append({'scope':key,'status':'missing_or_invalid_manifest'})
        else:tasks.append((key,meta))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending={pool.submit(read_one,s3,key,meta):key for key,meta in tasks}
        for future in as_completed(pending):
            key=pending[future]
            try:results.append(future.result())
            except Exception as exc:results.append({'scope':key,'status':'error','error_type':type(exc).__name__})
            if len(results)%1000==0:
                print('AUDIT_PROGRESS '+json.dumps({'checked':len(results),'target':len(required),
                     'errors':sum(r['status']!='ok' for r in results)}),flush=True)
    results.sort(key=lambda r:r['scope'])
    source=source_checks(results,max_requests) if live_source else {'status':'not_requested'}
    by_region={}
    for region in regions:
        group=[r for r in results if region_for(r['scope'].split('/')[2])==region]
        good=[r for r in group if r['status']=='ok'];counts=Counter()
        for result in good:counts.update(result['transactions'])
        by_region[region]={'expected_scopes':len(group),'reread_verified_scopes':len(good),
                           'failed_scopes':len(group)-len(good),'transactions':dict(counts),
                           'empty_scopes':sum(r['rows']==0 for r in good)}
    failures=[r for r in results if r['status']!='ok']
    report={'schema':1,'checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'source_git_sha':os.getenv('SOURCE_GIT_SHA',''),'cutoff':backfill_progress.CUTOFF,
            'regions':by_region,'expected_scopes':len(required),
            'reread_verified_scopes':len(required)-len(failures),'failed_scopes':len(failures),
            'failures':failures,'empty_scopes':[r['scope'] for r in results if r.get('rows')==0],
            'identical_extra_rows_preserved':sum(r.get('identical_extra_rows',0) for r in results),
            'source_checks':source,'storage_complete':not failures,
            'passed':not failures and (not live_source or source['status']=='ok'),
            'verification':'Every required stored object reread: SHA256, gzip, CSV, row count, original JSON, dates, district and rent classification; original API rechecked only as specified under source_checks.'}
    collect.save_json(REPORT,report)
    with gzip.open(DETAILS,'wt',encoding='utf-8') as out:
        for result in results:out.write(json.dumps(result,ensure_ascii=False,sort_keys=True)+'\n')
    print('STORAGE_AUDIT_RESULT '+json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--region',choices=['seoul','gyeonggi'],action='append')
    parser.add_argument('--workers',type=int,default=12)
    parser.add_argument('--live-source',action='store_true')
    parser.add_argument('--max-requests',type=int,default=1200)
    args=parser.parse_args()
    if not 1<=args.workers<=24 or not 1<=args.max_requests<=1200:parser.error('workers 1..24; requests 1..1200')
    return run(args.region or ['seoul','gyeonggi'],args.workers,args.live_source,args.max_requests)


if __name__=='__main__':raise SystemExit(main())
