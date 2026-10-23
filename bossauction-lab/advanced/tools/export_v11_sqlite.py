#!/usr/bin/env python3
"""Local read-only conversion of a user's own v11.4 SQLite DB to Pages JSON.
Never publish DBs or third-party copyrighted snapshots or private credentials.
"""
import datetime
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

def export(db_file, output):
    db=Path(db_file).resolve()
    path=Path(output).resolve()
    if not db.is_file(): raise FileNotFoundError(db)
    if db==path: raise ValueError("원본 DB와 출력 경로가 같습니다.")
    conn=sqlite3.connect(db.as_uri()+"?mode=ro",uri=True)
    conn.row_factory=sqlite3.Row
    try:
        required={"id","kind","case_no","address","subtype","court","appraisal",
                  "min_price","fail_count","sale_date","lat","lng","location_source","source","source_url"}
        found={r[1] for r in conn.execute("PRAGMA table_info(items)")}
        if not required.issubset(found): raise ValueError("v11.4 items 테이블 구조가 아닙니다.")
        rows=conn.execute("""SELECT id,kind,case_no,address,subtype,court,appraisal,
            min_price,fail_count,sale_date,lat,lng,location_source,source,source_url
            FROM items ORDER BY id LIMIT 10001""").fetchall()
        if len(rows)>10000: raise ValueError("최대 10000건씩 내보내세요.")
        lots=[]
        for row in rows:
            x=dict(row)
            if x["kind"] not in ("auction","public"): continue
            url=x["source_url"]
            if url:
                parsed=urlparse(url)
                if parsed.scheme!="https" or parsed.username or parsed.password:url=None
            address=x["address"] or ""
            lots.append({
                "id":x["id"],"channel":"court" if x["kind"]=="auction" else "public",
                "title":x["case_no"] or x["id"],"region":address.split()[0] if address else "",
                "type":x["subtype"],"location":address,"authority":x["court"],
                "appraisal":x["appraisal"],"minimum":x["min_price"],"date":x["sale_date"] or "",
                "failures":x["fail_count"] or 0,"lat":x["lat"],"lng":x["lng"],
                "coordinateSource":x["location_source"],"sourceUrl":url
            })
        payload={"sourceName":"사용자 로컬 v11.4 DB 수동 내보내기 · 실시간 미검증",
                 "collectedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),"lots":lots}
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        print("내보내기 완료:",len(lots),"건 ->",path)
        print("공식 데이터 이용권한, 기준일, 원문 확인 후에만 사용하세요.")
    finally: conn.close()

if __name__=="__main__":
    if len(sys.argv)!=3: raise SystemExit("Usage: python export_v11_sqlite.py input.sqlite3 output.json")
    export(sys.argv[1],sys.argv[2])
