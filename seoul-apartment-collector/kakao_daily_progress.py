"""Owner-only daily progress with contract-period and observation-date checks."""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import backfill_progress as audit
from collect import START, months, prev
import kakao_self_alert as kakao
from regions import PERIODS, in_month, select

BASE = Path(__file__).resolve().parent
REPORT = BASE/'daily_progress_report.json'
LEGACY_LEDGER_PREFIX = 'internal/kakao-gyeonggi-progress/v1/'
LEDGER_PREFIX = 'internal/kakao-gyeonggi-progress/v2/'
KST = ZoneInfo('Asia/Seoul')


def scope_keys(region, kind, first, last):
    return [f'{kind}/{ym[:4]}/{code}/{ym}.csv.gz'
            for ym in months(first,last) for code in select(region) if in_month(code,ym)]


def valid_keys(files, required):
    # Share the collector audit's checksum/size/backend validation.
    return [key for key in required
            if audit.completeness(files,[key])['completed']]


def observed_day(meta, now):
    try:
        stamp = datetime.fromisoformat(meta['checked_at_utc'].replace('Z','+00:00'))
        if stamp.tzinfo is None or stamp > now + timedelta(minutes=5):
            return None
        return stamp.astimezone(KST).date().isoformat()
    except (KeyError,ValueError,TypeError,AttributeError):
        return None


def build_report(manifest, status, now=None):
    now = (now or datetime.now(KST)).astimezone(KST)
    files = manifest.get('files')
    if not isinstance(files,dict):
        raise ValueError('Missing source manifest')
    cutoff = now.strftime('%Y%m')
    comparison_month = prev(cutoff)  # Current contract month remains provisional.
    coverage = {}; comparison_dates = {}; comparison_complete = True
    comparison_missing_dates = False
    for region in ('seoul','gyeonggi'):
        coverage[region] = {}; comparison_dates[region] = {}
        for kind in ('sale','rent'):
            required = scope_keys(region,kind,START[kind],cutoff)
            good = valid_keys(files,required)
            coverage[region][kind] = {
                'stored':len(good), 'target':len(required),
                'percent':round(len(good)*100/len(required),3),
                'first_contract_month':START[kind], 'last_contract_month':cutoff}
            required_comparison = scope_keys(region,kind,comparison_month,comparison_month)
            good_comparison = valid_keys(files,required_comparison)
            comparison_complete &= len(good_comparison)==len(required_comparison)
            days = [observed_day(files[key],now) for key in good_comparison]
            comparison_missing_dates |= None in days
            comparison_dates[region][kind] = sorted({day for day in days if day})
        stored = sum(value['stored'] for value in coverage[region].values())
        target = sum(value['target'] for value in coverage[region].values())
        coverage[region]['total'] = {'stored':stored,'target':target,'percent':round(stored*100/target,3)}
    all_days = {day for kinds in comparison_dates.values() for days in kinds.values() for day in days}
    aligned = comparison_complete and not comparison_missing_dates and len(all_days)==1
    common_day = next(iter(all_days)) if aligned else None
    reason = ('same_observation_day' if aligned else
              'missing_scopes' if not comparison_complete else
              'observation_date_missing' if comparison_missing_dates else 'observation_days_differ')
    basis={region:{code:PERIODS.get(code,(None,None)) for code in select(region)} for region in ('seoul','gyeonggi')}
    basis_sha=hashlib.sha256(json.dumps([START,basis],sort_keys=True).encode()).hexdigest()
    return {'generated_at_kst':now.isoformat(), 'cutoff':cutoff, 'scope_basis_sha256':basis_sha,
        'periods_equal':True, 'coverage':coverage,
        'comparison':{'contract_month':comparison_month,'coverage_complete':comparison_complete,
            'observation_dates':comparison_dates,'same_observation_day':aligned,
            'common_observation_day_kst':common_day,'fresh_today':common_day==now.date().isoformat(),
            'ready':aligned,'reason':reason,
            'note':'Same observation day is not an immutable official data vintage; later corrections can occur.'},
        'last_collection':{'day_kst':status.get('as_of_kst'),
            'requests':status.get('last_run_requests'), 'failures':status.get('last_run_failures')},
        'manifest_saved_at_utc':manifest.get('updated_at_utc'),
        'source_git_sha':os.getenv('SOURCE_GIT_SHA','unknown'),
        'verification':'Upload-confirmed manifest coverage, not a live reread or transaction semantic audit.'}


def comparable_previous_total(report,previous):
    current=report['coverage']['gyeonggi']['total']
    old=(previous or {}).get('report',{}).get('coverage',{}).get('gyeonggi',{}).get('total',{})
    # A corrected scope definition is not a daily collection delta.
    previous_report=(previous or {}).get('report',{})
    basis=report.get('scope_basis_sha256');old_basis=previous_report.get('scope_basis_sha256')
    comparable=(basis==old_basis) if basis and old_basis else old.get('target')==current['target']
    return old.get('stored') if comparable else None


def render_message(report, previous=None):
    if 'storage' in report:return render_combined_message(report,previous)
    day = datetime.fromisoformat(report['generated_at_kst'])
    data = report['coverage']['gyeonggi']
    def line(label,kind):
        part = data[kind]
        return f"{label} {part['stored']:,}/{part['target']:,} ({part['percent']:.1f}%)"
    previous_total = comparable_previous_total(report,previous)
    delta = (f"전일대비 {data['total']['stored']-previous_total:+,}구간"
             if isinstance(previous_total,int) else '집계기준 변경' if previous else '전일보고 없음')
    cutoff = report['cutoff'][2:4]+'.'+report['cutoff'][4:]
    check = report['comparison']
    check_text = {'same_observation_day':'동일 확인일 '+str(check['common_observation_day_kst'])[5:],
                  'missing_scopes':'일부 미수집','observation_date_missing':'확인일 미기록',
                  'observation_days_differ':'확인일 상이'}[check['reason']]
    failure = report['last_collection']['failures']
    last_day = str(report['last_collection']['day_kst'] or '미확인')[5:]
    text = '\n'.join([f'[경기도 저장현황 {day:%m/%d %H:%M}]',
        line('매매','sale'),line('전월세','rent'),line('합계','total'),delta,
        f'서울과 동일기간: 매매06.01/전월세11.01~{cutoff}',
        f"{check['contract_month'][4:]}월 비교: {check_text}",
        f'최근수집 {last_day} 오류 {failure if failure is not None else "미확인"}건'])
    kakao.payload(text)  # Enforce the existing registered Kakao text-template limit.
    return text


def render_combined_message(report,previous=None):
    from storage_usage import GB
    day=datetime.fromisoformat(report['generated_at_kst'])
    data=report['coverage']['gyeonggi'];storage=report['storage']
    old=comparable_previous_total(report,previous)
    delta=f"·전일{data['total']['stored']-old:+,}" if isinstance(old,int) else '·기준변경' if previous else ''
    github=storage.get('github',{});code=github.get('code',{})
    git=(f"Git코드{code['used_bytes']/1e6:.1f}MB(관리1GB {code['percent']:.1f}%)"
         if code.get('status')=='ok' else 'Git 용량미확인')
    if 'artifacts' in github or 'cache' in github:
        artifacts=github.get('artifacts',{});cache=github.get('cache',{})
        artifact_text=f"{artifacts['used_bytes']/1e6:.1f}M" if artifacts.get('status')=='ok' else '?'
        cache_text=f"{cache['used_bytes']/1e6:.0f}M" if cache.get('status')=='ok' else '?'
        git+=f'·CI{artifact_text}/캐시{cache_text}'
    r2=storage.get('r2',{})
    if r2.get('status')=='ok' and r2.get('scope')=='account':
        r2_line=f"R2 {r2['used_bytes']/GB:.2f}/10GB({r2['percent']:.1f}%)·여유{r2['remaining_bytes']/GB:.2f}GB"
    elif r2.get('status')=='partial':
        r2_line=f"R2 ≥{r2['known_used_bytes']/GB:.2f}GB·계정합계미확인"
    else:r2_line='R2 계정용량미확인'
    google=storage.get('google',{})
    if google.get('status')=='ok' and google.get('limit_bytes'):
        unit,scale=('TB',1e12) if google['limit_bytes']>=1e12 else ('GB',GB)
        google_line=f"Google {google['used_bytes']/scale:.2f}/{google['limit_bytes']/scale:.2f}{unit}({google['percent']:.1f}%)·여유{google['remaining_bytes']/scale:.2f}{unit}"
    elif google.get('status')=='ok':google_line=f"Google {google['used_bytes']/GB:.1f}GB·한도미제공"
    else:google_line='Google 계정용량미확인'
    check=report['comparison']
    checks={'same_observation_day':'확인'+str(check['common_observation_day_kst'])[5:].replace('-','/')+'일치',
            'missing_scopes':'자료누락','observation_date_missing':'확인일미기록',
            'observation_days_differ':'확인일상이'}
    guard=storage.get('guard',{})
    protect='🟢8GB보호' if guard.get('status')=='armed' else '🟡Google전환'
    if guard.get('status')!='armed' and (google.get('status')!='ok' or google.get('remaining_bytes')==0):protect='🔴저장보류'
    failures=report['last_collection']['failures']
    lines=[f'[경기도·저장공간 {day:%m/%d}]',
        f"매매{data['sale']['percent']:.1f}%·전월세{data['rent']['percent']:.1f}%",
        f"합계{data['total']['stored']:,}/{data['total']['target']:,}({data['total']['percent']:.1f}%){delta}",
        git,r2_line,google_line,
        f"{checks[check['reason']]}·오류{failures if failures is not None else '?'}·{protect}"]
    # Keep mandatory coverage, free-space and guard status; shorten labels only.
    text='\n'.join(lines)
    if len(text)>200:
        text=text.replace('·전일','·').replace('Google ','GDrive ').replace('GB·여유','·남음').replace('TB·여유','·남음')
    if len(text)>200:
        text=text.replace('·여유','·잔').replace('관리1GB ','기준1G ').replace('계정용량미확인','용량미확인')
    kakao.payload(text)
    return text


def ledger_key(day):
    return LEDGER_PREFIX+day.isoformat()+'.json'


def read_ledger(storage, key):
    try:
        response = storage.get_object(Bucket=os.environ['R2_BUCKET_NAME'],Key=key)
    except Exception as error:
        code = str(getattr(error,'response',{}).get('Error',{}).get('Code',''))
        if code in ('NoSuchKey','NotFound','404'):
            return None
        raise kakao.NotificationError('Cannot read daily notification receipt') from None
    try:
        body = response['Body']
        try:raw = body.read(131073)
        finally:body.close()
        if len(raw)>131072:
            raise ValueError()
        result = json.loads(raw)
        if not isinstance(result,dict):raise ValueError()
        return result
    except Exception:
        raise kakao.NotificationError('Invalid daily notification receipt') from None


def put_ledger(storage, key, data):
    storage.put_object(Bucket=os.environ['R2_BUCKET_NAME'],Key=key,
        Body=json.dumps(data,ensure_ascii=False).encode(),ContentType='application/json')


def access_token(storage):
    cipher = kakao.token_cipher_secret()
    refresh = kakao.get_refresh_token(storage,cipher)
    if not refresh:raise kakao.NotificationError('Initial Kakao refresh token is missing')
    access,rotated = kakao.renew_access_token(refresh)
    if rotated and rotated!=refresh:
        kakao.save_refresh_token(storage,cipher,rotated)
    return access


def notify(report,now=None,storage=None,send=None,verify_connection=False):
    now = (now or datetime.now(KST)).astimezone(KST)
    if now.date().isoformat()!=report['generated_at_kst'][:10]:
        raise ValueError('Refusing to send a report from a different KST day')
    if now.hour<9:
        if verify_connection:access_token(storage or kakao.r2_client())
        print('KAKAO_DAILY_NOT_DUE: report validated; waits until 09:00 Asia/Seoul')
        return 'not_due'
    storage = storage or kakao.r2_client()
    key = ledger_key(now.date())
    existing = read_ledger(storage,key)
    if existing:
        if existing.get('status')=='sent' and existing.get('api_result_code')==0:
            print('KAKAO_DAILY_ALREADY_SENT',now.date().isoformat())
            return 'already_sent'
        raise kakao.NotificationError('Prior send outcome is uncertain; inspect receipt before retrying')
    previous = read_ledger(storage,ledger_key(now.date()-timedelta(days=1)))
    if previous is None:
        previous=read_ledger(storage,LEGACY_LEDGER_PREFIX+(now.date()-timedelta(days=1)).isoformat()+'.json')
    if previous and previous.get('status')!='sent':previous=None
    message = render_message(report,previous)
    token = access_token(storage)  # Authenticate before reserving the daily send.
    # Every production trigger shares the same GitHub Actions concurrency group.
    # A reservation prevents blindly resending after an ambiguous network failure.
    receipt = {'status':'sending','day_kst':now.date().isoformat(),
               'reserved_at_kst':now.isoformat(),'report':report,'message':message}
    put_ledger(storage,key,receipt)
    (send or kakao.send_to_me)(token,message)
    receipt.update(status='sent',api_result_code=0,sent_at_utc=datetime.now(timezone.utc).isoformat())
    put_ledger(storage,key,receipt)
    print('KAKAO_DAILY_SENT: owner My Chat API accepted; '+json.dumps({
        'day_kst':now.date().isoformat(),'gyeonggi':report['coverage']['gyeonggi'],
        'comparison':report['comparison']},ensure_ascii=False))
    return 'sent'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true')
    parser.add_argument('--verify-connection',action='store_true')
    parser.add_argument('--live-storage',action='store_true')
    args = parser.parse_args()
    try:
        manifest = json.loads((BASE/'r2_manifest.json').read_text(encoding='utf-8'))
        status = json.loads((BASE/'status.json').read_text(encoding='utf-8'))
        report = build_report(manifest,status)
        client=None
        if args.live_storage:
            from storage_usage import collect_storage
            from storage_budget import StorageBudget,StorageBudgetExceeded
            client=kakao.r2_client()
            report['storage']=collect_storage(client,kakao.github_request)
            budget=StorageBudget(client,os.environ['R2_BUCKET_NAME'])
            budget.snapshot=report['storage']['r2']
            try:
                budget.reserve('internal/storage-guard-probe',0)
                report['storage']['guard']={'status':'armed','safe_bytes':8_000_000_000}
            except StorageBudgetExceeded:
                report['storage']['guard']={'status':'r2_data_paused','safe_bytes':8_000_000_000}
            print('STORAGE_MEASUREMENTS '+json.dumps(report['storage'],ensure_ascii=False))
        REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('DAILY_PROGRESS_PREVIEW\n'+render_message(report))
        if not args.dry_run:notify(report,storage=client,verify_connection=args.verify_connection)
        return 0
    except (ValueError,kakao.NotificationError) as error:
        print('KAKAO_DAILY_ERROR:',str(error),file=sys.stderr)
    except Exception as error:
        print('KAKAO_DAILY_ERROR:',type(error).__name__,file=sys.stderr)
    return 1


if __name__=='__main__':raise SystemExit(main())

