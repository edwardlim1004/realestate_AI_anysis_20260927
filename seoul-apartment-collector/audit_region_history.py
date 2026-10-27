#!/usr/bin/env python3
"""Probe excluded administrative-code periods, rather than assuming API history.

MOLIT can reassign historical records after administrative reorganizations.
An upload-complete manifest alone cannot detect a wrong collection boundary.
"""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone

import collect
from incremental import content_hash
from regions import PERIODS, in_month

BASE=Path(__file__).resolve().parent
REPORT=BASE/'region_history_audit.json'


def next_month(ym):
    year,month=int(ym[:4]),int(ym[4:])
    return f'{year+1:04d}01' if month==12 else f'{year:04d}{month+1:02d}'


def probes(cutoff):
    output=set()
    for gu,(start,end) in PERIODS.items():
        for kind,first in collect.START.items():
            candidates=[]
            if start:candidates.extend([first,collect.prev(start)])
            if end:candidates.extend([next_month(end),cutoff])
            for ym in candidates:
                if first<=ym<=cutoff and not in_month(gu,ym):output.add((kind,gu,ym))
    return sorted(output)


def signature(cutoff):
    return hashlib.sha256(json.dumps([PERIODS,collect.START,cutoff],sort_keys=True).encode()).hexdigest()


def run():
    cutoff=collect.today().strftime('%Y%m');fingerprint=signature(cutoff)
    if REPORT.exists():
        previous=json.loads(REPORT.read_text(encoding='utf-8'))
        if previous.get('passed') and previous.get('configuration_sha256')==fingerprint:
            print('REGION_HISTORY_ALREADY_VERIFIED',flush=True);return 0
    required=probes(cutoff);results=[];unplanned=[];errors=[]
    state=collect.read_state();day=collect.today().isoformat()
    used=int(state.get('daily_requests',0)) if state.get('usage_day')==day else 0
    key=os.getenv('MOLIT_SERVICE_KEY') or os.getenv('DATA_GO_KR_SERVICE_KEY')
    if not key:raise RuntimeError('MOLIT_SERVICE_KEY missing; historical boundaries not verified')
    api=collect.Collector(key,min(128,max(0,collect.DAILY_MAX_REQUESTS-used)),3)
    try:
        for kind,gu,ym in required:
            if api.calls>=api.limit:break
            try:
                raw=api.fetch(kind,gu,ym)
                codes=sorted({collect.field(r,'sggCd','지역코드') for r in raw}- {''})
                item={'kind':kind,'district':gu,'contract_month':ym,'rows':len(raw),
                      'content_sha256':content_hash(raw),'raw_district_codes':codes}
                results.append(item)
                if any(code!=gu for code in codes):
                    errors.append({'scope':collect.R2Storage.relpath(kind,gu,ym),'reason':'source_district_mismatch'})
                elif raw:unplanned.append(item)
            except Exception as exc:
                errors.append({'scope':collect.R2Storage.relpath(kind,gu,ym),'error_type':type(exc).__name__})
                break
    finally:
        state.update({'usage_day':day,'daily_requests':used+api.calls})
        collect.save_json(collect.STATE,state)
    report={'schema':1,'checked_at_utc':datetime.now(timezone.utc).isoformat(),
            'configuration_sha256':fingerprint,'cutoff':cutoff,'requested':len(required),
            'checked':len(results),'pending':len(required)-len(results),'requests':api.calls,
            'unplanned_nonempty_scopes':unplanned,'errors':errors,'probes':results,
            'passed':len(results)==len(required) and not unplanned and not errors,
            'verification':'Representative queries immediately outside configured code periods and at historical/current endpoints; not an exhaustive query of excluded months.'}
    collect.save_json(REPORT,report)
    print('REGION_HISTORY_RESULT '+json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(run())
