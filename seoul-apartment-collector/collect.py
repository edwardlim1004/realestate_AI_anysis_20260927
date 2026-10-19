#!/usr/bin/env python3
# coding: utf-8
"""서울 아파트 매매/전월세 API 수집기: 월·구별 CSV.gz, 표준 라이브러리만 사용."""
from __future__ import annotations
import argparse, calendar, csv, datetime as dt, gzip, json, os, random, sys, time
from pathlib import Path
from urllib.parse import urlencode, unquote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo
from r2_bridge import R2Storage

BASE=Path(__file__).resolve().parent
DATA=BASE/'data'
STATE=BASE/'state.json'
STATUS=BASE/'status.json'
DAILY_MAX_REQUESTS=8000
R2_DATA_SAFETY_CAP=8*1024*1024*1024  # 8 GiB project safety limit; not a cloud billing limit
GU={'11110':'종로구','11140':'중구','11170':'용산구','11200':'성동구','11215':'광진구',
'11230':'동대문구','11260':'중랑구','11290':'성북구','11305':'강북구','11320':'도봉구',
'11350':'노원구','11380':'은평구','11410':'서대문구','11440':'마포구','11470':'양천구',
'11500':'강서구','11530':'구로구','11545':'금천구','11560':'영등포구','11590':'동작구',
'11620':'관악구','11650':'서초구','11680':'강남구','11710':'송파구','11740':'강동구'}
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
    return {'시군구':'서울특별시 '+GU[gu],'법정동':field(raw,'법정동','umdNm'),
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
    with gzip.open(tmp,'wt',encoding='utf-8-sig',newline='',compresslevel=6) as f:
        writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
        for record in records:writer.writerow(row(kind,gu,ym,record))
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

def run(mode,max_requests,delay,until=None,districts=None,collector=None):
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
    if archive.stats()['r2_compressed_bytes']>=R2_DATA_SAFETY_CAP:
        print('SAFE_STOP: R2 storage safety threshold exceeded',flush=True)
        c.limit=0
    if actual_limit==0:
        print('SAFE_STOP: daily collector request budget used',flush=True)
    districts=districts or list(GU)
    last_day=calendar.monthrange(now.year,now.month)[1]
    cycle=now.strftime('%Y%m') if now.day>=min(30,last_day) else None
    if cycle and state.get('refresh_cycle')!=cycle:
        state.update({'refresh_cycle':cycle,'refresh_done':[]})
    cycle=state.get('refresh_cycle');done=set(state.get('refresh_done',[]))
    base=dt.date(int(cycle[:4]),int(cycle[4:]),1) if cycle else now
    refresh=[]
    if cycle:
        refresh=[(kind,gu,ym) for ym in recent(base) for kind in ('sale','rent') for gu in districts if ym>=START[kind]]
        refresh=[x for x in refresh if '/'.join(x) not in done]
    history=[(kind,gu,ym) for ym in reversed(list(months('200601',end))) for kind in ('sale','rent')
             for gu in districts if ym>=START[kind] and not archive.has_scope(kind,gu,ym)]
    if mode=='test':
        refresh=[]
        month=prev(now.strftime('%Y%m'))
        history=[('sale',districts[0],month),('rent',districts[0],month)]
    if mode=='backfill':refresh=[]
    if mode=='refresh':history=[]
    tasks=refresh+history
    print(f'pending refresh {len(refresh)}; history {len(history)}; request cap {c.limit}',flush=True)
    success=0;failures=0
    for kind,gu,ym in tasks:
        if c.calls>=c.limit:break
        try:
            records=c.fetch(kind,gu,ym)
            save_scope(kind,gu,ym,records)
            archive.upload(scope(kind,gu,ym))
            archive.save_manifest()
            success+=1
            if (kind,gu,ym) in refresh:done.add('/'.join((kind,gu,ym)))
            print(f'OK {kind} {gu} {ym}: {len(records)} rows',flush=True)
            if archive.stats()['r2_compressed_bytes']>=R2_DATA_SAFETY_CAP:
                print('SAFE_STOP: R2 storage safety threshold reached',flush=True)
                break
        except StopSafely as error:
            print('SAFE_STOP',str(error),flush=True);break
        except Exception as error:
            failures+=1
            print(f'ERROR {kind} {gu} {ym} {type(error).__name__}',flush=True)
            if failures>=3:break
    if cycle and all('/'.join(x) in done for x in refresh):
        state.update({'refresh_cycle':None,'refresh_done':[]})
    else:state['refresh_done']=sorted(done)
    state['usage_day']=run_day
    state['daily_requests']=used_today+c.calls
    save_json(STATE,state)
    count=len(archive.files)
    save_json(STATUS,{'as_of_kst':now.isoformat(),'total_completed_scopes':count,
        'last_run_requests':c.calls,'last_run_success':success,'last_run_failures':failures,
        'refresh_cycle':state.get('refresh_cycle'),'last_run_mode':mode,
        'requests_today':state['daily_requests'],'daily_cap':DAILY_MAX_REQUESTS,
        'r2_storage_safety_cap_bytes':R2_DATA_SAFETY_CAP,**archive.stats()})
    print('RESULT',json.dumps({'requests':c.calls,'success':success,'failures':failures,'completed_scopes':count}))
    return 0 if failures==0 else 1

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['daily','test','backfill','refresh'],default='daily')
    parser.add_argument('--max-requests',type=int,default=1200)
    parser.add_argument('--delay',type=float,default=3)
    parser.add_argument('--until',default=None)
    parser.add_argument('--district',choices=list(GU),action='append')
    args=parser.parse_args()
    if not 1<=args.max_requests<=1200 or args.delay<3:parser.error('1-1200 requests; delay>=3')
    if args.until and (len(args.until)!=6 or not args.until.isdigit()):parser.error('until YYYYMM')
    key=os.getenv('MOLIT_SERVICE_KEY','') or os.getenv('DATA_GO_KR_SERVICE_KEY','')
    if not key:
        print('SKIPPED: MOLIT_SERVICE_KEY GitHub Actions Secret unavailable')
        return 0
    return run(args.mode,args.max_requests,args.delay,args.until,args.district,Collector(key,args.max_requests,args.delay))
if __name__=='__main__':sys.exit(main())
