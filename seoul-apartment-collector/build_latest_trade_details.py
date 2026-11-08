"""Resumable backwards search for each apartment's latest older sale/jeonse/monthly contract.
Only public display fields are persisted; original archives remain private.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo
from build_public_trade_details import REGION_LAWD, dashboard_periods, public_row
from regions import in_month
from r2_bridge import R2Storage

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'trade-details/latest'

def identity(row):
    return tuple(row.get(k,'') for k in ('code','apt','dong','jibun','rentalType'))

def merge_latest(existing, incoming):
    grouped={}
    for row in existing+incoming:
        key=identity(row);current=grouped.get(key,[])
        if not current or row['date']>current[0]['date']:grouped[key]=[row]
        elif row['date']==current[0]['date']:current.append(row)
    return sorted([r for group in grouped.values() for r in group],key=lambda r:r['date'],reverse=True)

def build_region(name, store, limit=24):
    codes=REGION_LAWD[name];cutoff=dashboard_periods()[0]
    keys=sorted([k for k in store.files if len(k.split('/'))==4
                 and k.split('/')[0] in ('sale','rent') and k.split('/')[2] in codes
                 and k.split('/')[-1][:6]<cutoff and in_month(k.split('/')[2],k.split('/')[-1][:6])],
                key=lambda k:(k.split('/')[-1][:6],k),reverse=True)
    path=OUT/(codes[0]+'.json')
    old=json.loads(path.read_text()) if path.exists() else {}
    scanned=old.get('source_scopes',{});rows=old.get('rows',[])
    # Revisions/cancellations invalidate previous winners; restart safely.
    if any(k not in keys or store.files.get(k,{}).get('sha256')!=sha for k,sha in scanned.items()):
        scanned={};rows=[]
    todo=[k for k in keys if k not in scanned][:limit]
    for key in todo:
        kind,_,code,filename=key.split('/');ym=filename[:6]
        raw=store.read_scope(key)
        if store.files[key].get('rows') is not None and len(raw)!=store.files[key]['rows']:raise ValueError('Row count mismatch')
        incoming=[]
        for source in raw:
            row=public_row(code,ym,source,kind)
            if row:
                if row['date'][:7].replace('-','')!=ym:raise ValueError('Contract month mismatch')
                if kind=='sale':row['rentalType']='sale'
                incoming.append(row)
        rows=merge_latest(rows,incoming)
        scanned[key]=store.files[key]['sha256']
    payload={'schema':1,'region':name,'codes':codes,'rows':rows,
        'updated_at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'),
        'before_month':cutoff,'earliest_scanned_month':min((k.split('/')[-1][:6] for k in scanned),default=None),
        'scanned_scopes':len(scanned),'available_scopes':len(keys),'archive_scan_complete':len(scanned)==len(keys),
        'source_scopes':scanned,
        'meaning':'보관자료에서 확인된 단지·주소·거래유형별 가장 최근 계약일의 기록. 전체 거래목록 아님.'}
    OUT.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n')
    temp.replace(path)
    return {'region':name,'processed':len(todo),'scanned':len(scanned),'available':len(keys)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--max-scopes',type=int,default=24);args=parser.parse_args()
    if not 1<=args.max_scopes<=1000:parser.error('scope limit 1..1000')
    def task(name):
        try:result=build_region(name,R2Storage(),args.max_scopes)
        except Exception as e:result={'region':name,'error':type(e).__name__}
        print(json.dumps(result,ensure_ascii=False),flush=True);return result
    with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(task,REGION_LAWD))
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'build-report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    if all('error' in r for r in results):raise SystemExit('No historical fallback built')
if __name__=='__main__':main()
