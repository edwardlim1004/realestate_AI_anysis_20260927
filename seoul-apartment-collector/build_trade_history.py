#!/usr/bin/env python3
"""Build compressed five-year transaction drill-down from verified private archives."""
from __future__ import annotations
import argparse
import gzip
import json
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"trade-details"/"history"
sys.path.insert(0,str(ROOT/"seoul-apartment-collector"))
from build_public_trade_details import REGION_LAWD, entry_key, public_row
from regions import in_month
from r2_bridge import R2Storage


def rolling_months(count):
    now=datetime.now(ZoneInfo("Asia/Seoul"))
    year,month=now.year,now.month
    out=[]
    for _ in range(count):
        out.append(f"{year}{month:02d}")
        month-=1
        if month==0:
            year-=1
            month=12
    return list(reversed(out))


def write_gzip(path,payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(payload,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")
    temp=path.with_suffix(path.suffix+".tmp")
    with temp.open("wb") as handle:
        with gzip.GzipFile(fileobj=handle,mode="wb",mtime=0,compresslevel=9) as zipped:
            zipped.write(raw)
    temp.replace(path)
    return len(raw)


def build(store,months):
    OUT.mkdir(parents=True,exist_ok=True)
    index={"schema":1,"start_month":months[0],"end_month":months[-1],"regions":{}}
    report={"schema":1,"start_month":months[0],"end_month":months[-1],"regions":[]}
    for region,codes in REGION_LAWD.items():
        region_entry={"codes":codes,"files":{}}
        for kind in ("sale","rent"):
            rows=[]
            expected=[]
            missing=[]
            for month in months:
                for code in codes:
                    if not in_month(code,month):
                        continue
                    rel=entry_key(code,month,kind)
                    meta=store.files.get(rel)
                    if not meta or not meta.get("sha256") or meta.get("storage","r2") not in ("r2","gdrive"):
                        missing.append(rel)
                        continue
                    expected.append(rel)
                    raw=store.read_scope(rel)
                    if meta.get("rows") is not None and len(raw)!=int(meta["rows"]):
                        raise ValueError(f"row count mismatch: {rel}")
                    for source in raw:
                        item=public_row(code,month,source,kind)
                        if item:
                            if item["date"][:7].replace("-","")!=month:
                                raise ValueError(f"contract month mismatch: {rel}")
                            if kind=="sale":
                                item["rentalType"]="sale"
                            rows.append(item)
            before=len(rows)
            unique={json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(",",":")):row for row in rows}
            rows=list(unique.values())
            duplicates=before-len(rows)
            rows.sort(key=lambda x:(x["date"],x["apt"],x.get("price",x.get("deposit","")),x.get("floor","")),reverse=True)
            filename=f"{codes[0]}-{kind}.json.gz"
            payload={"schema":1,"region":region,"codes":codes,"kind":kind,
                "start_month":months[0],"end_month":months[-1],"months":months,
                "verified_scopes":len(expected),"missing_months":sorted({x.split("/")[-1][:6] for x in missing}),
                "complete":not missing,"duplicate_rows":duplicates,
                "generated_at_kst":datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds"),
                "source":"국토교통부 아파트 실거래 원자료의 검증된 보관본",
                "rows":rows}
            raw_bytes=write_gzip(OUT/filename,payload)
            region_entry["files"][kind]=filename
            report["regions"].append({"region":region,"kind":kind,"rows":len(rows),
                "verified_scopes":len(expected),"missing_scopes":len(missing),
                "duplicate_rows":duplicates,"uncompressed_bytes":raw_bytes})
        index["regions"][region]=region_entry
    (OUT/"index.json").write_text(json.dumps(index,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    report["generated_at_kst"]=datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    (OUT/"build-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    missing=sum(x["missing_scopes"] for x in report["regions"])
    print(json.dumps({"regions":len(index["regions"]),"files":len(report["regions"]),
        "rows":sum(x["rows"] for x in report["regions"]),
        "missing_scopes":missing,"generated_at_kst":report["generated_at_kst"]},ensure_ascii=False))
    return missing


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--months",type=int,default=60)
    args=parser.parse_args()
    if not 1<=args.months<=120:
        parser.error("--months must be in 1..120")
    missing=build(R2Storage(),rolling_months(args.months))
    if missing:
        print(f"WARNING: {missing} official source scopes are missing; coverage is marked incomplete.")
if __name__=="__main__":
    main()
