"""Publish aggregate 80–90㎡ price evidence only after city archive verification.
Raw multiplicity is preserved; distinct-row medians are sensitivity checks only.
Overlapping old/new code partitions are blocked instead of being double counted.
"""
import calendar
from collections import defaultdict
import csv
from datetime import timedelta
import gzip
import io
import json
import statistics
from pathlib import Path
import collect
import metro_queue
from archive_reader import VerifiedArchiveReader
from regions import METRO_REGIONS, CODE_ALIASES

OUT = Path(__file__).resolve().parent.parent / 'dashboard-v1/data/metro-summary.json'
VERSION = 1

def shift(ym, n):
    y, m = divmod(int(ym[:4])*12 + int(ym[4:])-1+n, 12)
    return f'{y:04d}{m+1:02d}'

def cutoff(today):
    previous = shift(today.strftime('%Y%m'), -1)
    y, m = int(previous[:4]), int(previous[4:])
    deadline = today.replace(year=y, month=m, day=calendar.monthrange(y,m)[1]) + timedelta(days=30)
    safe = previous if today > deadline else shift(previous, -1)
    return min(safe, metro_queue.progress.CUTOFF)

def number(value):
    try:
        value=float(str(value).replace(',',''))
        return value if 0 <= value < float('inf') else None
    except (ValueError, TypeError):
        return None

def summarize(rows, kind):
    # No identity assumption: a repeated source row may describe another contract.
    selected=[]; seen=set(); unique=[]
    for r in rows:
        area=number(r.get('전용면적(㎡)'))
        if area is None or not 80<=area<=90 or r.get('해제사유발생일','').strip(): continue
        monthly=number(r.get('월세금(만원)'))
        if kind=='jeonse' and monthly!=0: continue
        if kind=='monthly' and (monthly is None or monthly<=0): continue
        field='거래금액(만원)' if kind=='sale' else '보증금(만원)'
        price=number(r.get(field))
        if price is None or (kind!='monthly' and price==0): continue
        value=(price,monthly if kind=='monthly' else 0)
        selected.append(value)
        key=json.dumps(r,sort_keys=True,ensure_ascii=False)
        if key not in seen: seen.add(key);unique.append(value)
    def med(values,i): return round(statistics.median(x[i] for x in values),2) if values else None
    return {'rows':len(selected),'identical_extra_rows':len(selected)-len(unique),
            'median_manwon':med(selected,0), 'distinct_row_median_manwon':med(unique,0),
            'monthly_rent_median_manwon':med(selected,1) if kind=='monthly' else None}

def build(report, files, reader, previous=None):
    last=cutoff(collect.today()); months=[shift(last,i) for i in range(-11,1)]
    result={'schema':VERSION,'cutoff_month':last,'window_start':months[0],
        'generated_kst':collect.today().isoformat(), 'units':'만원', 'area_m2':[80,90],
        'policy':'원본 반복행 보존. 고유행 중위가는 민감도 참고값이며 확정 거래수가 아님. 구·신 코드 동시 유효 월은 합산하지 않음.',
        'comparison_warning':'동일 기간·면적의 가격 참고자료. 기존 서울·경기 점수/평균가격과 직접 비교 불가. 신고 지연·정정 가능.',
        'cities':{}}
    for city,codes in METRO_REGIONS.items():
        info=report['cities'][city]
        summary={'status':'verified' if info['verified'] else 'pending','progress':info['percent'],'districts':[]}
        result['cities'][city]=summary
        if not info['verified']:continue
        keys=[f'{k}/{ym[:4]}/{code}/{ym}.csv.gz' for code in codes for k in ('sale','rent') for ym in months]
        if any(key not in files for key in keys):
            summary['status']='missing_scopes';continue
        signature=metro_queue.fingerprint(files,keys)
        old=(previous or {}).get('cities',{}).get(city,{})
        if old.get('source_digest')==signature and (previous or {}).get('cutoff_month')==last and (previous or {}).get('schema')==VERSION:
            result['cities'][city]={**old,'archive_fingerprint':info['manifest_fingerprint']};continue
        summary['source_digest']=signature
        summary['archive_fingerprint']=info['manifest_fingerprint']
        partitions=defaultdict(list)
        for code in codes: partitions[CODE_ALIASES.get(code,code)].append(code)
        for canonical,aliases in partitions.items():
            buckets={'sale':[],'rent':[]};overlaps=[]
            for kind in buckets:
                for ym in months:
                    populated=[]
                    for code in aliases:
                        key=f'{kind}/{ym[:4]}/{code}/{ym}.csv.gz'
                        payload=reader(key,files[key])
                        rows=list(csv.DictReader(io.StringIO(gzip.decompress(payload).decode('utf-8-sig'))))
                        if any(r.get('계약년월')!=ym for r in rows):raise ValueError('Month mismatch')
                        if rows:populated.append(rows)
                    if len(populated)>1: overlaps.append(f'{kind}/{ym}')
                    elif populated:buckets[kind].extend(populated[0])
            district={'code':canonical,'name':codes.get(canonical,codes[aliases[0]]),'alias_overlap_months':overlaps}
            if overlaps:district['status']='alias_review_required'
            else:
                district.update(status='ready',sale=summarize(buckets['sale'],'sale'),
                                jeonse=summarize(buckets['rent'],'jeonse'),monthly=summarize(buckets['rent'],'monthly'))
            summary['districts'].append(district)
    return result

if __name__=='__main__':
    report=metro_queue.snapshot()
    prior=json.loads(OUT.read_text()) if OUT.exists() else {}
    output=build(report,metro_queue.manifest(),VerifiedArchiveReader(),prior)
    collect.save_json(OUT,output)
