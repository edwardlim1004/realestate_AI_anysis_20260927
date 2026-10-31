#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build verified Daejeon district and five-year apartment snapshots.

Reads existing privately stored collector scopes via R2Storage, including
verified Google Drive failover. Does NOT call MOLIT API or republish raw rows.
Never promotes regional risk or HaR to the official risk model.
"""
from __future__ import annotations
import argparse
import collections
import datetime as dt
import hashlib
import importlib.util
import json
import math
import statistics
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR = ROOT / "seoul-apartment-collector"
VALUATION = ROOT / "long-term-value"
OUTPUT = ROOT / "dashboard-v1" / "data"
sys.path.insert(0, str(COLLECTOR))
from regions import DAEJEON, full_name
from collect import row as normalize_row

spec = importlib.util.spec_from_file_location("five_year_snapshots", VALUATION / "build_snapshots.py")
five = importlib.util.module_from_spec(spec)
spec.loader.exec_module(five)

MODEL = "daejeon-four-axis-research-v1"
MIN_MONTH_SALES = 5

def source_specs(manifest, code, months):
    files = manifest["files"]
    refs = [(kind, ym, f"{kind}/{ym[:4]}/{code}/{ym}.csv.gz")
            for kind in ("sale", "rent") for ym in months]
    invalid = [rel for _, _, rel in refs
               if not files.get(rel, {}).get("sha256")
               or files[rel].get("storage", "r2") not in ("r2", "gdrive")]
    if invalid:
        raise ValueError(f"{code}: missing or unverified scope metadata: {invalid[:3]} (n={len(invalid)})")
    signature = hashlib.sha256(json.dumps(
        [MODEL, code, [(rel, files[rel]["sha256"], files[rel].get("storage", "r2")) for _, _, rel in refs]],
        ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return refs, signature

def valid_price(s):
    return five.price_num(s)

def normalize(kind, code, ym, raw):
    item = normalize_row(kind, code, ym, raw)
    if five.clean(item.get("해제사유발생일")) or five.month_of(item) != ym:
        return None
    apt = five.clean(item.get("단지명"))
    dong = five.clean(item.get("법정동"))
    jibun = five.clean(item.get("지번"))
    area = valid_price(item.get("전용면적(㎡)"))
    if not (apt and dong and area and 10 <= area <= 350):
        return None
    if kind == "sale":
        price = valid_price(item.get("거래금액(만원)"))
    else:
        if valid_price(item.get("월세금(만원)")):
            return None
        price = valid_price(item.get("보증금(만원)"))
    if price is None:
        return None
    return apt, dong, jibun, area, price

def log_gap(monthly, months):
    """Train log-linear trend on first 48 months; last 12 months are holdout."""
    training = [(i, statistics.median(monthly[ym])) for i, ym in enumerate(months[:-12])
                if len(monthly[ym]) >= MIN_MONTH_SALES]
    testing = [(i, statistics.median(monthly[ym])) for i, ym in enumerate(months[-12:], len(months)-12)
               if len(monthly[ym]) >= MIN_MONTH_SALES]
    if len(training) < 30 or len(testing) < 6:
        return None, len(training), len(testing)
    xbar=statistics.mean(i for i, _ in training)
    ys=[math.log(p) for _,p in training]
    ybar=statistics.mean(ys)
    denom=sum((i-xbar)**2 for i,_ in training)
    if not denom: return None, len(training), len(testing)
    slope=sum((i-xbar)*(math.log(p)-ybar) for i,p in training)/denom
    intercept=ybar-slope*xbar
    last_idx=len(months)-1
    # Use the latest complete month, requiring enough actual deals.
    if len(monthly[months[-1]]) < MIN_MONTH_SALES:
        return None, len(training), len(testing)
    observed=statistics.median(monthly[months[-1]])
    trend=math.exp(intercept+slope*last_idx)
    return round((observed/trend-1)*100, 3), len(training), len(testing)

def rank_scores(rows, name, higher=True):
    present=sorted((r for r in rows if isinstance(r.get(name), (int,float))), key=lambda r:r[name])
    n=len(present)
    return {r["code"]: (100 * i/(n-1) if higher else 100 * (n-1-i)/(n-1)) if n>1 else 50
            for i,r in enumerate(present)}

def build_district(code, months, storage):
    if code not in DAEJEON:
        raise ValueError("Non-Daejeon code")
    refs,signature=source_specs({"files":storage.files},code,months)
    bundles=collections.defaultdict(lambda:{"sale":collections.defaultdict(list),"rent":collections.defaultdict(list)})
    monthly_sale=collections.defaultdict(list)
    monthly_jeonse=collections.defaultdict(list)
    monthly_counts=collections.Counter()
    counts={"sale":0,"rent":0}
    for idx,(kind,ym,rel) in enumerate(refs,1):
        raw=storage.read_scope(rel)  # verified SHA256, bytes and original JSON
        expected=storage.files[rel].get("rows")
        if expected is not None and len(raw)!=int(expected):
            raise ValueError(f"Row-count mismatch {rel}: {len(raw)} != {expected}")
        for original in raw:
            parsed=normalize(kind,code,ym,original)
            if parsed is None: continue
            apt,dong,jibun,area,price=parsed
            key=(dong,apt,jibun,math.floor(area/5+0.5)*5)
            bundles[key][kind][ym].append(price)
            counts[kind]+=1
            if 80 <= area <= 90:
                if kind=="sale":
                    monthly_sale[ym].append(price)
                    monthly_counts[ym]+=1
                else:
                    monthly_jeonse[ym].append(price)
    if counts["sale"] == 0 or counts["rent"] == 0:
        raise RuntimeError(f"{code}: no verified sale/rent rows")
    complexes=[five.make_complex(k,v,months,months[-1]) for k,v in bundles.items() if v["sale"]]
    complexes.sort(key=lambda x:(x["dong"],x["name"],x["jibun"],x["size"]))
    valuation={
        "schema":1,"method":"five-year-v1.1","district_code":code,
        "district":DAEJEON[code],"window_start":months[0],"cutoff_month":months[-1],
        "units":"만원","size_bin_m2":5,
        "source":"국토교통부 공식 매매·전월세 수집 원본; 검증된 사설 R2/Google Drive 저장",
        "source_digest":signature,
        "coverage":{"sale_months":len(months),"rent_months":len(months),
                    "target_months":len(months),"missing_scopes":0,
                    "scopes_verified":len(refs),"sale_rows":counts["sale"],
                    "pure_jeonse_rows":counts["rent"]},
        "complex_count":len(complexes),"complexes":complexes,
    }
    gap,ntrain,ntest=log_gap(monthly_sale,months)
    last12=months[-12:]
    sm=[p for ym in last12 for p in monthly_sale[ym]]
    jm=[p for ym in last12 for p in monthly_jeonse[ym]]
    sale_median=statistics.median(sm) if len(sm)>=20 else None
    rent_median=statistics.median(jm) if len(jm)>=20 else None
    ratio=round(100*rent_median/sale_median,3) if sale_median and rent_median else None
    a=months[-1];b=months[-2]
    na=monthly_counts[a];nb=monthly_counts[b]
    volume_change=round((na/nb-1)*100,3) if nb>=5 and na>=5 else None
    period_first=months[-6:-3];period_last=months[-3:]
    first_prices=[p for ym in period_first for p in monthly_sale[ym]]
    last_prices=[p for ym in period_last for p in monthly_sale[ym]]
    momentum=round((statistics.median(last_prices)/statistics.median(first_prices)-1)*100,3) if len(first_prices)>=15 and len(last_prices)>=15 else None
    district={
        "code":code,"name":DAEJEON[code],"province":"daejeon","source_digest":signature,
        "latest_complete_month":months[-1],"latest_sales":na,
        "sale_count_12m_84":len(sm),"rent_count_12m_84":len(jm),
        "avg84":round(sale_median/10000,3) if sale_median else None,
        "jeonseRate":ratio,
        "gapPct":gap,"volumeChangePct":volume_change,"momentum3mPct":momentum,
        "train_months":ntrain,"holdout_months":ntest,
        "history":[[ym,round(statistics.median(monthly_sale[ym])/10000,3) if len(monthly_sale[ym])>=MIN_MONTH_SALES else None, len(monthly_sale[ym])] for ym in months],
        "scope_coverage":"120/120 verified",
    }
    return valuation,district

def regional_reference(rows):
    """4/5-axis within-DAEJEON ONLY. Risk remains unavailable; no five-axis composite."""
    axes=[("gapPct",False,.35,"valuation"),("momentum3mPct",True,.15,"momentum"),
          ("volumeChangePct",True,.15,"liquidity"),("jeonseRate",True,.15,"jeonse")]
    ranks={out:rank_scores(rows,src,higher) for src,higher,_,out in axes}
    for r in rows:
        r["riskVerified"]=False
        subs={out:(round(ranks[out][r["code"]],2) if r["code"] in ranks[out] else None)
              for _,_,_,out in axes}
        r["partial_scores"]=subs
        if all(x is not None for x in subs.values()):
            r["partialScore4of5"]=round(sum(subs[out]*w for _,_,w,out in axes)/.8,2)
        else:
            r["partialScore4of5"]=None
    return rows

def write_json_atomic(path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(obj,ensure_ascii=False,separators=(",",":"),allow_nan=False)+"\n",encoding="utf-8")
    tmp.replace(path)

def main(argv=None, storage=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--cutoff",default=None)
    args=parser.parse_args(argv)
    today=dt.datetime.now(ZoneInfo("Asia/Seoul")).date()
    prior=five.shift_month(today.strftime("%Y%m"),-1)
    deadline=dt.date(int(prior[:4]),int(prior[4:]),1)
    import calendar
    deadline=deadline.replace(day=calendar.monthrange(deadline.year,deadline.month)[1])+dt.timedelta(days=30)
    last=args.cutoff or (prior if today>deadline else five.shift_month(prior,-1))
    months=[five.shift_month(last,i) for i in range(-59,1)]
    if storage is None:
        from r2_bridge import R2Storage
        storage=R2Storage()
    vals=[];rows=[]
    for code in DAEJEON:
        val,reg=build_district(code,months,storage)
        vals.append((code,val))
        rows.append(reg)
        print(f"DAEJEON_VERIFIED {code} scopes={val['coverage']['scopes_verified']} transactions={val['coverage']['sale_rows']}",flush=True)
    regional_reference(rows)
    # Publish only after ALL five regions pass the coverage and checksum gates.
    for code,val in vals:
        target=VALUATION/"data"/(code+".json")
        if target.exists():
            try:
                prev=json.loads(target.read_text(encoding="utf-8"))
                if prev.get("source_digest")==val["source_digest"]:
                    print("DAEJEON_VALUATION_UNCHANGED",code,flush=True)
                    continue
            except (OSError,ValueError):pass
        write_json_atomic(target,val)
    published={"schema":1,"method":MODEL,"status":"RESEARCH_ONLY",
               "cutoff_month":last,"generated_kst":dt.datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
               "source":"국토교통부 매매·전월세 API / R2·Google Drive 원본 SHA256 검증",
               "warning":"대전 내 4축 참고점수는 서울·경기 5축 모델과 직접 비교 불가. 지역 risk와 미래 하락확률 미검증.",
               "regions":rows}
    write_json_atomic(OUTPUT/"daejeon-regions.json",published)
    print("DAEJEON_PUBLISHED",len(rows),"districts",last,flush=True)
    return published

if __name__=="__main__":
    main()
