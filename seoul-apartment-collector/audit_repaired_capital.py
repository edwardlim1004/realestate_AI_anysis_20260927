#!/usr/bin/env python3
"""Audit corrected current-code coverage, reusing immutable prior file evidence.

Previously verified objects are reused only when SHA256, size, storage identity
and semantic metadata still match. Every added/changed object is reread live.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import gzip
import json
import os
from pathlib import Path
import subprocess

import audit_storage as audit
import backfill_progress
import collect
from google_drive_backup import s3_client
from regions import region_for

BASE=Path(__file__).resolve().parent


def reuse_evidence(key,previous,old,current):
    if not previous or previous.get('status')!='ok' or not old or not current:return False
    identity=lambda v:(v.get('sha256'),v.get('bytes'),v.get('storage','r2'),v.get('drive_file_id'))
    return (identity(old)==identity(current)
            and ('rows' not in current or current['rows']==previous['rows'])
            and (not current.get('content_sha256') or current['content_sha256']==previous['content_sha256']))


def run(evidence):
    prior=json.loads((evidence/'coverage_audit.json').read_text(encoding='utf-8'))
    if not prior['storage_complete']:raise ValueError('baseline_storage_audit_not_complete')
    revision=prior['source_git_sha']
    if len(revision)!=40 or any(c not in '0123456789abcdef' for c in revision):raise ValueError('invalid_baseline_revision')
    subprocess.run(['git','fetch','--depth=1','origin',revision],check=True,capture_output=True)
    original=json.loads(subprocess.check_output(['git','show',revision+':seoul-apartment-collector/r2_manifest.json']))['files']
    with gzip.open(evidence/'coverage_audit_scopes.jsonl.gz','rt',encoding='utf-8') as inp:
        previous={r['scope']:r for r in map(json.loads,inp)}
    if len(previous)!=prior['expected_scopes']:raise ValueError('incomplete_baseline_evidence')
    manifest=json.loads((BASE/'r2_manifest.json').read_text(encoding='utf-8'))
    if manifest.get('bucket')!=os.environ['R2_BUCKET_NAME'] or manifest.get('prefix')!='seoul-apartments/v1/':
        raise ValueError('archive_identity_mismatch')
    files=manifest['files'];regions=['seoul','gyeonggi']
    required=sorted({key for region in regions for key in backfill_progress.expected_keys(region)})
    results=[];changed=[];reused=0
    for key in required:
        if not backfill_progress.completeness(files,[key])['completed']:
            results.append({'scope':key,'status':'missing_or_invalid_manifest'})
        elif reuse_evidence(key,previous.get(key),original.get(key),files.get(key)):
            results.append(previous[key]);reused+=1
        else:changed.append(key)
    s3=s3_client()
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures={pool.submit(audit.read_one,s3,key,files[key]):key for key in changed}
        for future in as_completed(futures):
            key=futures[future]
            try:results.append(future.result())
            except Exception as exc:results.append({'scope':key,'status':'error','error_type':type(exc).__name__})
    results.sort(key=lambda r:r['scope'])
    source=audit.source_checks(results,1200)
    groups={}
    for region in regions:
        subset=[r for r in results if region_for(r['scope'].split('/')[2])==region]
        good=[r for r in subset if r['status']=='ok'];counts=Counter()
        for r in good:counts.update(r['transactions'])
        groups[region]={'expected_scopes':len(subset),'reread_verified_scopes':len(good),
                        'failed_scopes':len(subset)-len(good),'transactions':dict(counts),
                        'empty_scopes':sum(r['rows']==0 for r in good)}
    failed=[r for r in results if r['status']!='ok']
    report={'schema':2,'checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'source_git_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
            'cutoff':backfill_progress.CUTOFF,'regions':groups,'expected_scopes':len(required),
            'reread_verified_scopes':len(required)-len(failed),'failed_scopes':len(failed),'failures':failed,
            'storage_complete':not failed,'source_checks':source,'passed':not failed and source['status']=='ok',
            'empty_scopes':[r['scope'] for r in results if r.get('rows')==0],
            'identical_extra_rows_preserved':sum(r.get('identical_extra_rows',0) for r in results),
            'baseline_checked_at_utc':prior['checked_at_utc'],'baseline_source_git_sha':revision,
            'unchanged_verified_objects_reused':reused,'objects_reread_in_this_run':len(changed),
            'verification':'Current codes across full contract history. Original full live-reread evidence reused for unchanged object identities; added/changed objects reread live. SHA256, CSV, rows, original JSON and rent split verified. Empty scopes and region/type/year samples requeried from official API.'}
    collect.save_json(BASE/'coverage_audit.json',report)
    with gzip.open(BASE/'coverage_audit_scopes.jsonl.gz','wt',encoding='utf-8') as out:
        for result in results:out.write(json.dumps(result,ensure_ascii=False,sort_keys=True)+'\n')
    print('CORRECTED_CAPITAL_AUDIT '+json.dumps({k:v for k,v in report.items() if k not in ('failures','empty_scopes')},ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True)
    raise SystemExit(run(parser.parse_args().evidence))
