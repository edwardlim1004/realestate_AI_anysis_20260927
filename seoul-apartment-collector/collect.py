#!/usr/bin/env python3
# coding: utf-8
"""서울·경기·대전 아파트 매매/전월세: 과거자료 재개 + 변경분만 저장하는 정기 갱신."""
from __future__ import annotations
import argparse, csv, datetime as dt, gzip, io, json, os, random, sys, time
from pathlib import Path
from urllib.parse import urlencode, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo
from r2_bridge import R2Storage
from regions import LABELS, DISTRICTS, full_name, in_month, region_for, select
from incremental import content_hash, change_summary, record_change

BASE=Path(__file__).resolve().parent
DATA=BASE/'data'
STATE=BASE/'state.json'
STATUS=BASE/'status.json'
UPDATES=BASE/'updates'
DAILY_MAX_REQUESTS=8000
R2_DATA_SAFETY_CAP=8_000_000_000  # 8 GB safety limit; not a cloud billing limit
GU=DISTRICTS
START={'sale':'200601','rent':'201101'}
API={
'sale':'https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev',
'rent':'https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent'}
FIELDS=['시군구','법정동','단지명','지번','전용면적(㎡)','계약년월','계약일','층','건축년도',
'거래금액(만원)','보증금(만원)','월세금(만원)','해제사유발생일','거래유형','자료종류','출처','원본항목JSON']

def today(): return dt.datetime.now(ZoneInfo('Asia/Seoul')).date()
def months(first,last):
    year,mon=int(first[:4]),int(first[4:]);ly,lm=int(last[:4]),int(last[4:])
    while (year,mon)<=(ly,lm):
        yield f'{year:04d}{mon:02d}'
        mon+=1
        if mon==13:year+=1;mon=1
def prev(ym):
    y,m=int(ym[:4]),int(ym[4:])
    return f'{y-1:04d}12' if m==1 else f'{y:04d}{m-1:02d}'
def recent(reference,n=6):
    ym=reference.strftime('%Y%m');result=[]
    for _ in range(n):result.append(ym);ym=prev(ym)
    return result
def read_state():
    try:return json.loads(STATE.read_text(encoding='utf-8'))
    except (ValueError,OSError):return {'refresh_cycle':None,'refresh_done':[]}
def save_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)
def field(d,*names):
    for name in names:
        if d.get(name) is not None and str(d[name]).strip():return str(d[name]).strip()
    return ''
def parse_xml(data):
    if len(data)>20000000 or b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('invalid XML payload')
    root=ET.fromstring(data)
    tag=lambda item:item.tag.rsplit('}',1)[-1]
    nodes=list(root.iter())
    def get(k):return next((''.join(e.itertext()).strip() for e in nodes if tag(e)==k),'')
    code=get('resultCode')
    if code not in ('00','000','0','INFO-000'):
        raise ValueError('API_CODE:'+str(code or 'MISSING')+':'+get('resultMsg')[:80])
    rows=[]
    for node in nodes:
        if tag(node)=='item':rows.append({tag(c):''.join(c.itertext()).strip() for c in node})
    count=get('totalCount')
    return rows,int(count) if count.isdecimal() else None
def row(kind,gu,ym,raw):
    year=field(raw,'년','dealYear','contractYear') or ym[:4]
    mon=field(raw,'월','dealMonth','contractMonth') or ym[4:]
    day=field(raw,'일','dealDay','contractDay')
    try:date=dt.date(int(year),int(mon),int(day)).isoformat()
    except (ValueError,TypeError):date=''
    return {'시군구':full_name(gu),'법정동':field(raw,'법정동','umdNm'),
    '단지명':field(raw,'아파트','aptNm'),'지번':field(raw,'지번','jibun'),
    '전용면적(㎡)':field(raw,'전용면적','excluUseAr'),'계약년월':date[:7].replace('-','') if date else ym,
    '계약일':date,'층':field(raw,'층','floor'),'건축년도':field(raw,'건축년도','buildYear'),
    '거래금액(만원)':field(raw,'거래금액','dealAmount','dealAmt') if kind=='sale' else '',
    '보증금(만원)':field(raw,'보증금액','deposit') if kind=='rent' else '',
    '월세금(만원)':field(raw,'월세금액','monthlyRent') if kind=='rent' else '',
    '해제사유발생일':field(raw,'해제사유발생일','cdealDay'),
    '거래유형':field(raw,'거래유형','dealingGbn'),
    '자료종류':'아파트 매매' if kind=='sale' else '아파트 전월세',
    '출처':'국토교통부 공식 실거래가 API',
    '원본항목JSON':json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':'))}
def scope(kind,gu,ym):return DATA/kind/ym[:4]/gu/(ym+'.csv.gz')
def save_scope(kind,gu,ym,records):
    output=scope(kind,gu,ym);output.parent.mkdir(parents=True,exist_ok=True)
    tmp=output.with_suffix('.gz.tmp')
    with tmp.open('wb') as binary:
        with gzip.GzipFile(filename='',mode='wb',fileobj=binary,mtime=0,compresslevel=6) as compressed:
            with io.TextIOWrapper(compressed,encoding='utf-8-sig',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=FIELDS,lineterminator='\n');writer.writeheader()
                for record in sorted(records,key=lambda x:json.dumps(x,ensure_ascii=False,sort_keys=True)):
                    writer.writerow(row(kind,gu,ym,record))
    tmp.replace(output)

class StopSafely(Exception):pass
class Collector:
    def __init__(self,key,limit=180,delay=3,transport=None):
        self.key=unquote(key);self.limit=limit;self.delay=max(3,float(delay));self.transport=transport or self.http
        self.calls=0;self.last=0.0
    @staticmethod
    def http(url):
        req=Request(url,headers={'User-Agent':'SeoulAptOfficialDataCollector/2.0','Accept':'application/xml'})
        with urlopen(req,timeout=45) as response:return response.read(20000001)
    def request(self,kind,gu,ym,page):
        for trial in range(3):
            if self.calls>=self.limit:raise StopSafely('daily request ceiling')
            wait=self.delay-(time.monotonic()-self.last)
            if self.last and wait>0:time.sleep(wait)
            if trial:time.sleep(10*2**(trial-1)+random.uniform(0,1))
            self.last=time.monotonic();self.calls+=1
            params=urlencode({'serviceKey':self.key,'LAWD_CD':gu,'DEAL_YMD':ym,'pageNo':page,'numOfRows':1000})
            # Do not log URLs containing the service key.
            try:return parse_xml(self.transport(API[kind]+'?'+params))
            except (HTTPError,URLError,TimeoutError,ValueError,ET.ParseError) as error:
                if isinstance(error,HTTPError) and error.code in (401,403,429):raise StopSafely('HTTP '+str(error.code))
                if isinstance(error,ValueError) and 'API_CODE:' in str(error):raise StopSafely(str(error)[:100])
                if trial==2:raise RuntimeError('request failed after retries; key suppressed') from None
        raise AssertionError('unreachable')
    def fetch(self,kind,gu,ym):
        result=[];page=1
        while True:
            chunk,total=self.request(kind,gu,ym,page)
            result.extend(chunk)
            if len(result)>60000:raise ValueError('abnormal large scope')
            if total is not None and len(result)>=total:break
            if not chunk or (total is None and len(chunk)<1000):break
            page+=1
            if page>100:raise ValueError('pagination bound reached')
        if total is not None and len(result)!=total:raise ValueError('incomplete response')
        return result

def run(mode,max_requests,delay,until=None,districts=None,collector=None,region='all',refresh_months=6):
    now=today();end=until or now.strftime('%Y%m')
    state=read_state()
    run_day=now.isoformat()
    used_today=int(state.get('daily_requests',0)) if state.get('usage_day')==run_day else 0
    remaining=max(0,DAILY_MAX_REQUESTS-used_today)
    actual_limit=min(max_requests,remaining)
    c=collector or Collector(os.environ['MOLIT_SERVICE_KEY'],actual_limit,delay)
    c.limit=min(c.limit,actual_limit)
    archive=R2Storage()
    archive.migrate_legacy()
    storage_cap=int(os.environ.get('R2_STORAGE_SOFT_CAP_BYTES',str(R2_DATA_SAFETY_CAP)))
    if archive.stats()['r2_compressed_bytes']>=storage_cap and not archive.fallback_enabled():
        print('SAFE_STOP: R2 soft cap reached; Google Drive failover unavailable',flush=True)
        c.limit=0
    if actual_limit==0:
        print('SAFE_STOP: daily collector request budget used',flush=True)
    districts=districts or select(region)
    # A six-month rolling check runs once per day, resumed across 3-hour jobs.
    # State is shared across ALL regions, including the 8,000-call daily budget.
    cycle=now.isoformat()
    if state.get('refresh_cycle')!=cycle:
        state.update({'refresh_cycle':cycle,'refresh_done':[]})
    cycle=state.get('refresh_cycle');done=set(state.get('refresh_done',[]))
    base=dt.date(int(end[:4]),int(end[4:]),1)
    refresh=[]
    if cycle:
        refresh=[(kind,gu,ym) for ym in recent(base,refresh_months) for kind in ('sale','rent') for gu in districts
                 if ym>=START[kind] and ym<=end and in_month(gu,ym)]
        refresh=[x for x in refresh if '/'.join(x) not in done]
    history=[(kind,gu,ym) for ym in reversed(list(months('200601',end))) for kind in ('sale','rent')
             for gu in districts if ym>=START[kind] and in_month(gu,ym)
             and not archive.has_scope(kind,gu,ym)]
    if mode=='test':
        refresh=[]
        month=prev(now.strftime('%Y%m'))
        history=[('sale',districts[0],month),('rent',districts[0],month)]
    if mode=='backfill':refresh=[]
    if mode=='refresh':history=[]
    # Missing recent scopes already appear in refresh; never fetch them twice.
    refresh_set=set(refresh)
    tasks=refresh+[item for item in history if item not in refresh_set]
    print(f'pending refresh {len(refresh)}; history {len(history)}; request cap {c.limit}',flush=True)
    success=0;failures=0;changed=0;unchanged=0;added_rows=0;removed_rows=0
    for kind,gu,ym in tasks:
        if c.calls>=c.limit:break
        try:
            records=c.fetch(kind,gu,ym)
            relative=archive.relpath(kind,gu,ym)
            previous=archive.files.get(relative)
            digest=content_hash(records)
            before=[]
            prior_digest=previous.get('content_sha256') if previous else None
            # Old manifests are bootstrapped from verified stored raw CSV once.
            if previous and prior_digest!=digest:
                before=archive.read_scope(relative)
                prior_digest=content_hash(before)
            if previous and prior_digest==digest:
                previous.update({'content_sha256':digest,'rows':len(records)})
                unchanged+=1
            else:
                event=change_summary(relative,before,records,previous is not None,observed_day=run_day)
                save_scope(kind,gu,ym,records)
                archive.upload(scope(kind,gu,ym))
                archive.files[relative].update({'content_sha256':digest,'rows':len(records)})
                record_change(UPDATES,event)
                changed+=1
                added_rows+=event['added_rows'];removed_rows+=event['removed_rows']
            # A manifest save time does not establish freshness of every scope.
            archive.files[relative]['checked_at_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
            archive.save_manifest()
            success+=1
            if (kind,gu,ym) in refresh_set:done.add('/'.join((kind,gu,ym)))
            print(f'OK {kind} {gu} {ym}: {len(records)} rows; '+
                  ('unchanged' if previous and prior_digest==digest else 'changed'),flush=True)
            if archive.stats()['r2_compressed_bytes']>=storage_cap and not archive.fallback_enabled():
                print('SAFE_STOP: R2 storage soft cap reached; Drive failover unavailable',flush=True)
                break
        except StopSafely as error:
            print('SAFE_STOP',str(error),flush=True);break
        except Exception as error:
            failures+=1
            print(f'ERROR {kind} {gu} {ym} {type(error).__name__}',flush=True)
            # Fail closed: if an archive fails to confirm receipt, avoid
            # wasting more official API requests in the same run.
            if isinstance(error,(RuntimeError,ValueError)) and (
                    'failover' in str(error).lower() or
                    'google drive' in str(error).lower() or
                    'google raw' in str(error).lower()):
                print('SAFE_STOP: secondary archive not verified',flush=True)
                break
            if failures>=3:break
    # Keep today's completed scopes even after the cycle finishes: later jobs
    # must not restart the same daily refresh. A new KST day resets the cursor.
    state['refresh_done']=sorted(done)
    state['usage_day']=run_day
    state['daily_requests']=used_today+c.calls
    save_json(STATE,state)
    count=len(archive.files)
    save_json(STATUS,{'as_of_kst':now.isoformat(),'total_completed_scopes':count,
        'last_run_requests':c.calls,'last_run_success':success,'last_run_failures':failures,
        'refresh_cycle':state.get('refresh_cycle'),'last_run_mode':mode,
        'requests_today':state['daily_requests'],'daily_cap':DAILY_MAX_REQUESTS,
        'r2_storage_safety_cap_bytes':storage_cap,
        'google_drive_fallback_enabled':archive.fallback_enabled(),
        'last_run_changed_scopes':changed,'last_run_unchanged_scopes':unchanged,
        'last_run_added_rows':added_rows,'last_run_removed_rows':removed_rows,
        'completed_by_region':{name:sum(1 for key in archive.files
            if key.split('/')[2] in select(name))
            for name in LABELS},
        **archive.stats()})
    print('RESULT',json.dumps({'requests':c.calls,'success':success,'failures':failures,'completed_scopes':count}))
    return 0 if failures==0 else 1

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['daily','test','backfill','refresh'],default='daily')
    parser.add_argument('--max-requests',type=int,default=1200)
    parser.add_argument('--delay',type=float,default=3)
    parser.add_argument('--until',default=None)
    parser.add_argument('--district',choices=list(GU),action='append')
    parser.add_argument('--region',choices=['all',*LABELS],default='all')
    parser.add_argument('--refresh-months',type=int,default=6)
    args=parser.parse_args()
    if not 1<=args.max_requests<=1200 or args.delay<3:parser.error('1-1200 requests; delay>=3')
    if not 1<=args.refresh_months<=252:parser.error('refresh-months must be 1..252')
    if args.until and (len(args.until)!=6 or not args.until.isdigit() or not 1<=int(args.until[4:])<=12):parser.error('until YYYYMM')
    if args.until and args.until>today().strftime('%Y%m'):parser.error('until must not be in the future')
    key=os.getenv('MOLIT_SERVICE_KEY','') or os.getenv('DATA_GO_KR_SERVICE_KEY','')
    if not key:
        print('SKIPPED: MOLIT_SERVICE_KEY GitHub Actions Secret unavailable')
        return 0
    return run(args.mode,args.max_requests,args.delay,args.until,args.district,Collector(key,args.max_requests,args.delay),args.region,args.refresh_months)
if __name__=='__main__':sys.exit(main())

