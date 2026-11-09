#!/usr/bin/env python3
"""Serial Busan -> Daegu -> Gwangju archives using the existing shared quota/store."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import collect
import backfill_progress as progress
import audit_storage
from incremental import content_hash
from regions import METRO_REGIONS, CODE_ALIASES

BASE=Path(__file__).resolve().parent
ORDER=('busan','daegu','gwangju')
REPORT=BASE/'metro_progress.json'

def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else ({} if default is None else default)

def manifest(): return read(BASE/'r2_manifest.json').get('files',{})

def fingerprint(files, keys):
    return hashlib.sha256(json.dumps([(k,files.get(k,{}).get('sha256')) for k in keys],sort_keys=True).encode()).hexdigest()

def snapshot():
    files=manifest(); cities={}
    for city in ORDER:
        keys=list(progress.expected_keys(city)); row=progress.completeness(files,keys)
        fp=fingerprint(files,keys)
        audit=read(BASE/(city+'_metro_audit.json'))
        receipt=read(BASE/(city+'_metro_verified.json'))
        row.update(manifest_fingerprint=fp,
                   identical_extra_rows_preserved=audit.get('identical_extra_rows_preserved') if audit.get('manifest_fingerprint')==fp else None,
                   source_code_partitions=len(METRO_REGIONS[city]),
                   stored_rows=sum(files.get(k,{}).get('rows',0) for k in keys),
                   storage_reread_passed=bool(audit.get('passed') and audit.get('manifest_fingerprint')==fp),
                   verified=bool(receipt.get('passed') and receipt.get('manifest_fingerprint')==fp))
        cities[city]=row
    result={'schema':1,'as_of_kst':collect.today().isoformat(),'order':ORDER,
            'historical_cutoff':progress.CUTOFF,'start':progress.START,'cities':cities,
            'raw_only':True,'alias_policy':'Both old/current code histories retained separately; never sum alias rows without reconciliation.',
            'code_aliases':CODE_ALIASES}
    collect.save_json(REPORT,result)
    return result

def next_city(report):
    return next((city for city in ORDER if not report['cities'][city]['verified']),None)

def source_audit(city, limit):
    """Resume rechecking every empty object and district/type/year samples."""
    detail=BASE/(city+'_metro_audit_scopes.jsonl.gz')
    with gzip.open(detail,'rt',encoding='utf-8') as f: rows=[json.loads(line) for line in f]
    selected={}; samples={}
    for r in rows:
        kind,year,code,_=r['scope'].split('/')
        if not r['rows']:selected[r['scope']]=r
        else:samples.setdefault((kind,year,code),r)
    selected.update({r['scope']:r for r in samples.values()})
    path=BASE/(city+'_metro_source.json'); prior=read(path); receipts=prior.get('checked',{})
    state=collect.read_state(); day=collect.today().isoformat()
    used=int(state.get('daily_requests',0)) if state.get('usage_day')==day else 0
    api=collect.Collector(os.environ['MOLIT_SERVICE_KEY'],min(limit,max(0,collect.DAILY_MAX_REQUESTS-used)),3)
    mismatch=[];errors=[]
    try:
        for scope,r in sorted(selected.items()):
            if receipts.get(scope)==r['content_sha256']:continue
            if api.calls>=api.limit:break
            kind,_,code,file=scope.split('/')
            try:
                digest=content_hash(api.fetch(kind,code,file[:6]))
                if digest==r['content_sha256']:receipts[scope]=digest
                else:mismatch.append(scope)
            except Exception as exc:
                errors.append({'scope':scope,'type':type(exc).__name__});break
    finally:
        state.update(usage_day=day,daily_requests=used+api.calls)
        collect.save_json(collect.STATE,state)
        pending=[k for k,r in selected.items() if receipts.get(k)!=r['content_sha256']]
        collect.save_json(path,{'checked':receipts,'pending':len(pending),'different':mismatch,'errors':errors,
                              'sample_policy':'Every empty partition plus one nonempty per source-code/type/year',
                              'all_transactions_requeried':False})
    return not pending and not errors, mismatch

def run(limit):
    report=snapshot()
    # Once every historical partition exists, keep the current month moving
    # even while source revalidation of an older month is still pending.
    if all(info['completed'] for info in report['cities'].values()):
        for name in ORDER:
            rc=collect.run('refresh',max(1,limit//6),3,region=name,refresh_months=1)
            if rc:return rc
        limit=max(1,limit//2)
        report=snapshot()
    city=next_city(report)
    if city is None:
        # After initial validation, maintain recent six months sequentially.
        for name in ORDER:
            rc=collect.run('refresh',max(1,limit//3),3,region=name)
            if rc:return rc
        snapshot();return 0
    info=report['cities'][city]
    print('METRO_ACTIVE',city,info['verified_manifest_scopes'],info['expected_scopes'],flush=True)
    if not info['completed']:
        rc=collect.run('backfill',limit,3,until=progress.CUTOFF,region=city)
        snapshot();return rc
    keys=list(progress.expected_keys(city));fp=fingerprint(manifest(),keys)
    if not info['storage_reread_passed'] or not (BASE/(city+'_metro_audit_scopes.jsonl.gz')).exists():
        audit_storage.REPORT=BASE/(city+'_metro_audit.json')
        audit_storage.DETAILS=BASE/(city+'_metro_audit_scopes.jsonl.gz')
        rc=audit_storage.run([city],workers=6,live_source=False)
        audit=read(audit_storage.REPORT);audit['manifest_fingerprint']=fp
        totals=audit.get('regions',{}).get(city,{}).get('transactions',{})
        if not all(totals.get(kind,0)>0 for kind in ('sale','jeonse','monthly')):
            audit['passed']=False;audit['error']='Missing sale/jeonse/monthly evidence';rc=1
        collect.save_json(audit_storage.REPORT,audit)
        if rc:snapshot();return rc
    passed,changed=source_audit(city,limit)
    if changed:
        # Changed source is legitimate: refresh affected month, retain change log,
        # invalidate the audit by its fingerprint, and reread on the next run.
        kind,_,code,file=changed[0].split('/')
        collect.run('refresh',min(limit,50),3,until=file[:6],districts=[code],region=city,refresh_months=1)
    if passed:
        collect.save_json(BASE/(city+'_metro_verified.json'),{
            'passed':True,'manifest_fingerprint':fp,'verified_at_kst':collect.today().isoformat(),
            'meaning':'All stored scopes reread; empties and stratified source samples rechecked. Not proof of unreported transactions.'})
    snapshot();return 0

def main():
    p=argparse.ArgumentParser();p.add_argument('--max-requests',type=int,default=200);p.add_argument('--report-only',action='store_true');a=p.parse_args()
    if a.report_only:snapshot();return 0
    if not 1<=a.max_requests<=1200:p.error('max-requests must be 1..1200')
    if not os.getenv('MOLIT_SERVICE_KEY'):raise RuntimeError('MOLIT_SERVICE_KEY unavailable; collection not started')
    return run(a.max_requests)

if __name__=='__main__':raise SystemExit(main())
