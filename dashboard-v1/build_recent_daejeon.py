#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publish a minimal verified Daejeon dashboard fallback from already-public sale snapshots."""
import json
import statistics
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DETAILS=ROOT/"trade-details"
OUTPUT=ROOT/"dashboard-v1"/"data"/"daejeon-recent.json"
DISTRICTS={"동구":"30110","중구":"30140","서구":"30170","유성구":"30200","대덕구":"30230"}

def build(root=ROOT):
    index=json.loads((root/"trade-details"/"index.json").read_text(encoding="utf-8"))
    raw=(root/"data.js").read_text(encoding="utf-8")
    dashboard=json.loads(raw[raw.index("=")+1:raw.rfind(";")])
    completed=dashboard["meta"]["evaluationMonth"].replace("-","")
    months=index.get("months",[])
    if completed not in months:
        raise ValueError("Verified completed month absent from public trade index")
    provisional=next((m for m in months if m>completed),None)
    rows=[]
    for name,code in DISTRICTS.items():
        key="대전광역시 "+name
        entry=index["regions"].get(key)
        if not entry or entry.get("codes")!=[code] or entry.get("file")!=code+".json":
            raise ValueError("Missing or mismatched Daejeon district: "+name)
        raw=json.loads((root/"trade-details"/entry["file"]).read_text(encoding="utf-8"))
        cov=raw.get("coverage",{})
        if cov.get("missing_scopes")!=0 or cov.get("verified_scopes")!=cov.get("expected_scopes"):
            raise ValueError("Unverified Daejeon scope: "+name)
        if raw.get("region")!=key:
            raise ValueError("Cross-city Daejeon trade mix: "+name)
        if sum(raw["by_month"].values())!=len(raw["rows"]):
            raise ValueError("Contract count mismatch: "+name)
        eligible=[r for r in raw["rows"] if str(r["date"]).startswith(completed[:4]+"-"+completed[4:]) and r.get("code")==code and 80<=float(r["area"])<=90]
        prices=[float(str(r["price"]).replace(",","")) for r in eligible]
        prices=[x for x in prices if x>0]
        med=round(statistics.median(prices),2) if len(prices)>=5 else None
        rows.append({"code":code,"name":name,
                     "complete_month":completed,"complete_month_count":raw["by_month"].get(completed,0),
                     "provisional_month":provisional,"provisional_month_count":raw["by_month"].get(provisional,0) if provisional else 0,
                     "complete_median_84":med,"complete_84_n":len(prices),
                     "coverage":cov,"source_digest":raw["source_digest"]})
    return {"schema":1,"status":"VERIFIED_PUBLIC_RECENT_ONLY",
            "source":"국토교통부 매매 실거래 공개 요약: sha256 검증 R2/Google Drive 소스",
            "warning":"최근 완결월 거래량은 주택 재고 대비 회전율이 아님. 5년 추세·전세수익률·리스크 미포함.",
            "regions":rows}

def main():
    obj=build()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    if OUTPUT.exists() and OUTPUT.read_text(encoding="utf-8")==text:
        print("DAEJEON_RECENT_UNCHANGED",len(obj["regions"]));return
    tmp=OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(text,encoding="utf-8")
    tmp.replace(OUTPUT)
    print("DAEJEON_RECENT_WRITTEN",len(obj["regions"]),obj["regions"][0]["complete_month"])

if __name__=="__main__":main()
