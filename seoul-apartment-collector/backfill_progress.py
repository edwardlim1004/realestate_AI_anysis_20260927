#!/usr/bin/env python3
# coding: utf-8
"""Report original Seoul apartment API historical collection completeness.
Baseline is fixed at 2026-10 inclusive, the user's requested cutoff.
A scope is one district × contract month × transaction type.
"""
import argparse
import json
import os
import re
from pathlib import Path
from regions import select, in_month

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/"r2_manifest.json"
REPORT=ROOT/"backfill_progress.json"
GU=("11110","11140","11170","11200","11215","11230","11260","11290","11305","11320",
"11350","11380","11410","11440","11470","11500","11530","11545","11560",
"11590","11620","11650","11680","11710","11740")
CUTOFF="202610"
START={"sale":"200601","rent":"201101"}


def all_months(start,end):
    y,m=int(start[:4]),int(start[4:])
    ey,em=int(end[:4]),int(end[4:])
    while (y,m)<=(ey,em):
        yield f"{y:04d}{m:02d}"
        m+=1
        if m>12:y+=1;m=1


def expected_keys(region='seoul'):
    for kind,start in START.items():
        for ym in all_months(start,CUTOFF):
            for gu in (GU if region=='seoul' else select(region)):
                if in_month(gu,ym):
                    yield f"{kind}/{ym[:4]}/{gu}/{ym}.csv.gz"


def completeness(files,required=None):
    required=list(expected_keys() if required is None else required)
    missing=[]
    for key in required:
        entry=files.get(key,{})
        if not isinstance(entry,dict):
            missing.append(key);continue
        sha=entry.get("sha256","")
        backend=entry.get("storage","r2")
        valid=(isinstance(sha,str) and re.fullmatch("[0-9a-f]{64}",sha)
            and isinstance(entry.get("bytes"),int) and entry["bytes"]>0)
        if backend=="gdrive":
            file_id=entry.get("drive_file_id","")
            valid=bool(valid and isinstance(file_id,str)
                       and re.fullmatch("[A-Za-z0-9_-]{10,200}",file_id))
        elif backend!="r2":
            valid=False
        if not valid:
            missing.append(key)
    target=len(required)
    return {"cutoff":CUTOFF,"expected_scopes":target,
            "verified_manifest_scopes":target-len(missing),
            "missing_scopes":len(missing),
            "percent":round((target-len(missing))*100/target,3),
            "completed":len(missing)==0,
            "missing_sample":missing[:60],
            "verification":"R2 or Google Drive upload-verified manifest; not a live reread or transaction semantic audit"}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--region',choices=['seoul','gyeonggi'],default='seoul')
    args=parser.parse_args()
    required=list(expected_keys(args.region))
    if not MANIFEST.exists():
        print("NO_MANIFEST: no R2 transfer confirmed yet")
        report=completeness({},required)
    else:
        m=json.loads(MANIFEST.read_text(encoding="utf-8"))
        if m.get("bucket")!="edward-seoul-apartment-data":
            raise RuntimeError("R2 bucket mismatch; refusing to report completion")
        report=completeness(m.get("files",{}),required)
    report['region']=args.region
    destination=REPORT if args.region=='seoul' else ROOT/'gyeonggi_backfill_progress.json'
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("BACKFILL",json.dumps({k:v for k,v in report.items() if k!="missing_sample"},ensure_ascii=False),flush=True)
    out=os.getenv("GITHUB_OUTPUT")
    if out:
        with open(out,"a",encoding="utf-8") as file:
            file.write("complete="+("true" if report["completed"] else "false")+"\n")
            file.write("percent="+str(report["percent"])+"\n")
    return 0

if __name__=="__main__":raise SystemExit(main())
