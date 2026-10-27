#!/usr/bin/env python3
"""Resume official-source checks from the immutable full-reread artifact.

The first audit exhausted its per-run 1,200-call budget. Its 30,062 successful
physical rereads are retained; only the unfinished source queries are repeated.
"""
import argparse
from datetime import datetime, timezone
import gzip
import json
import os
from pathlib import Path
import subprocess

import collect
from incremental import content_hash
from regions import region_for

BASE=Path(__file__).resolve().parent


def source_keys(results):
    empty=sorted(r['scope'] for r in results if r['status']=='ok' and r['rows']==0)
    samples={}
    for result in sorted(results,key=lambda r:r['scope']):
        if result['status']!='ok' or not result['rows']:continue
        kind,year,gu,_=result['scope'].split('/')
        samples.setdefault((region_for(gu),kind,year),result['scope'])
    return list(dict.fromkeys(empty+list(samples.values())))


def assert_snapshot(report):
    revision=report['source_git_sha']
    if len(revision)!=40 or any(ch not in '0123456789abcdef' for ch in revision):
        raise ValueError('invalid_audit_revision')
    subprocess.run(['git','fetch','--depth=1','origin',revision],check=True,capture_output=True)
    original=subprocess.check_output(['git','rev-parse',revision+':seoul-apartment-collector/r2_manifest.json'],text=True).strip()
    current=subprocess.check_output(['git','hash-object','seoul-apartment-collector/r2_manifest.json'],text=True).strip()
    if original!=current:raise ValueError('manifest_changed_since_full_live_reread')


def resume(report,results,api):
    keys=source_keys(results);source=report['source_checks']
    if not report['storage_complete'] or len(results)!=report['expected_scopes']:
        raise ValueError('physical_audit_not_complete')
    if any(r['status']!='ok' for r in results) or len({r['scope'] for r in results})!=len(results):
        raise ValueError('invalid_physical_audit_evidence')
    if len(keys)!=source['requested']:raise ValueError('source_query_plan_changed')
    cursor=source['checked']
    if not 0<=cursor<=len(keys) or source.get('errors') or source.get('different_scopes'):
        raise ValueError('audit_needs_repair_before_resume')
    hashes={r['scope']:r['content_sha256'] for r in results}
    previous_calls=source.get('requests',0)
    for key in keys[cursor:]:
        if api.calls>=api.limit:break
        kind,_,gu,name=key.split('/')
        try:
            raw=api.fetch(kind,gu,name[:6])
            cursor+=1
            if content_hash(raw)!=hashes[key]:source.setdefault('different_scopes',[]).append(key)
        except Exception as exc:
            source.setdefault('errors',[]).append({'scope':key,'error_type':type(exc).__name__})
            break
    source.update({'checked':cursor,'pending':len(keys)-cursor,'requests':previous_calls+api.calls,
                   'resumed_at_utc':datetime.now(timezone.utc).isoformat()})
    source['status']='ok' if not source['pending'] and not source['errors'] and not source['different_scopes'] else 'needs_review'
    report['passed']=report['storage_complete'] and source['status']=='ok'
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    path=BASE/'coverage_audit.json';report=json.loads(path.read_text(encoding='utf-8'))
    if report.get('passed'):
        print('SOURCE_AUDIT_ALREADY_COMPLETE');return 0
    original=json.loads((args.evidence/'coverage_audit.json').read_text(encoding='utf-8'))
    if original['source_git_sha']!=report['source_git_sha'] or original['expected_scopes']!=report['expected_scopes']:
        raise ValueError('evidence_does_not_match_live_audit')
    assert_snapshot(report)
    with gzip.open(args.evidence/'coverage_audit_scopes.jsonl.gz','rt',encoding='utf-8') as inp:
        results=[json.loads(line) for line in inp]
    state=collect.read_state();day=collect.today().isoformat()
    used=int(state.get('daily_requests',0)) if state.get('usage_day')==day else 0
    key=os.getenv('MOLIT_SERVICE_KEY') or os.getenv('DATA_GO_KR_SERVICE_KEY')
    if not key:raise RuntimeError('MOLIT_SERVICE_KEY missing')
    api=collect.Collector(key,min(1200,max(0,collect.DAILY_MAX_REQUESTS-used)),3)
    try:report=resume(report,results,api)
    finally:
        state.update({'usage_day':day,'daily_requests':used+api.calls})
        collect.save_json(collect.STATE,state)
    report['source_checks']['resume_workflow_run_id']=os.getenv('GITHUB_RUN_ID')
    collect.save_json(path,report)
    print('SOURCE_AUDIT_RESUMED '+json.dumps(report['source_checks'],ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
