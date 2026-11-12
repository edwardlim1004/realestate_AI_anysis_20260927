"""Monthly, hash-verified metro history. Raw archives remain private.
Each district is atomic and cached by per-month source hash; missing and empty differ.
"""
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import argparse, csv, gzip, io, json, statistics
from datetime import datetime
from zoneinfo import ZoneInfo
import collect, metro_queue
from regions import METRO_REGIONS, CODE_ALIASES, SEOUL, CURRENT_GYEONGGI, DAEJEON
HISTORY_REGIONS={"seoul":SEOUL,"gyeonggi":CURRENT_GYEONGGI,"daejeon":DAEJEON,**METRO_REGIONS}
from archive_reader import VerifiedArchiveReader
from build_metro_summary import summarize
from build_public_trade_details import public_row

OUT=collect.BASE.parent/'dashboard-v1/data/metro-history'
VERSION=1

def month_record(aliases, ym, kind, files, reader):
    if ym<collect.START[kind]:return {'status':'not_available'}
    keys=[f'{kind}/{ym[:4]}/{code}/{ym}.csv.gz' for code in aliases]
    if any(k not in files for k in keys):return {'status':'missing'}
    digest=metro_queue.fingerprint(files,keys)
    populated=[]
    for key in keys:
        rows=list(csv.DictReader(io.StringIO(gzip.decompress(reader(key,files[key])).decode('utf-8-sig'))))
        if any(r.get('계약년월')!=ym for r in rows):raise ValueError('Contract month mismatch')
        if files[key].get('rows') is not None and len(rows)!=files[key]['rows']:raise ValueError('Row count mismatch')
        if rows:populated.append((key.split('/')[2],rows))
    if len(populated)>1:return {'status':'alias_review_required','digest':digest}
    code,rows=populated[0] if populated else (aliases[0],[])
    metrics={k:summarize(rows,k) for k in (('sale',) if kind=='sale' else ('jeonse','monthly'))}
    # Bounded latest actual contracts for each month/type. These are not the chart's 80–90㎡ sample.
    detail=[]
    for r in rows:
        p=public_row(code,ym,json.loads(r['원본항목JSON']),kind)
        if p:
            p['rentalType']=p.get('rentalType','sale');detail.append(p)
    detail.sort(key=lambda r:r['date'],reverse=True)
    samples={k:[r for r in detail if r['rentalType']==k][:70] for k in metrics}
    return {'status':'ready','digest':digest,'metrics':metrics,'latest':samples,
            'all_area_counts':{k:sum(r['rentalType']==k for r in detail) for k in metrics}}

def build_district(city, code, aliases, files, reader):
    end=collect.today().strftime('%Y%m');path=OUT/f'{city}-{code}.json.gz'
    old=json.loads(gzip.decompress(path.read_bytes())) if path.exists() else {}
    prior=old.get('months',{}) if old.get('schema')==VERSION else {}
    months={}
    for ym in reversed(list(collect.months('200601',end))):
        months[ym]={}
        for kind in ('sale','rent'):
            keys=[f'{kind}/{ym[:4]}/{c}/{ym}.csv.gz' for c in aliases]
            previous=prior.get(ym,{}).get(kind,{})
            if all(k in files for k in keys) and previous.get('digest')==metro_queue.fingerprint(files,keys):
                months[ym][kind]=previous
            else:months[ym][kind]=month_record(aliases,ym,kind,files,reader)
    payload={'schema':VERSION,'city':city,'code':code,'name':HISTORY_REGIONS[city].get(code,HISTORY_REGIONS[city][aliases[0]]),
        'updated_at_kst':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'),
        'start':'200601','end':end,'area_m2':[80,90],'units':'만원','months':dict(sorted(months.items()))}
    OUT.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    tmp.write_bytes(gzip.compress(json.dumps(payload,ensure_ascii=False,separators=(",", ":"),allow_nan=False).encode(),mtime=0))
    tmp.replace(path)
    return {'code':code,'name':payload['name'],'file':path.name,'status':'ready'}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--city",choices=list(HISTORY_REGIONS))
    parser.add_argument("--workers",type=int,default=8)
    args=parser.parse_args()
    selected={args.city:HISTORY_REGIONS[args.city]} if args.city else METRO_REGIONS
    files=metro_queue.manifest();jobs=[]
    for city,codes in selected.items():
        groups=defaultdict(list)
        for code in codes:groups[CODE_ALIASES.get(code,code)].append(code)
        jobs.extend((city,code,aliases) for code,aliases in groups.items())
    def run(args):
        city,code,aliases=args
        try:
            item=build_district(city,code,aliases,files,VerifiedArchiveReader())
            print(city,code,'ready',flush=True)
        except Exception as e:
            item={'code':code,'name':HISTORY_REGIONS[city].get(code,code),'status':'error','error':type(e).__name__}
            print(city,code,type(e).__name__,flush=True)
        return city,item
    output={'schema':VERSION,'generated_kst':collect.today().isoformat(),'cities':{c:[] for c in selected}}
    with ThreadPoolExecutor(max_workers=max(1,min(args.workers,12))) as pool:
        for city,item in pool.map(run,jobs):output['cities'][city].append(item)
    collect.save_json(OUT/(f'index-{args.city}.json' if args.city else 'index.json'),output)
    if any(i['status']=='error' for items in output['cities'].values() for i in items):raise SystemExit('Incomplete history; inspect index.json')

if __name__=='__main__':main()
