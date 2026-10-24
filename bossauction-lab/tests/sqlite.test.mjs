import test from "node:test";
import assert from "node:assert/strict";
import {convertV11Rows,hasSQLiteHeader,readV11Sqlite,SQLITE_MAX_ROWS} from "../advanced/sqlite.js";
import {filterLots,inViewport} from "../advanced/core.js";
const sample=(more={})=>({
 id:"snapshot_20261017:930472",kind:"auction",case_no:"2023타경51257",
 address:"서울특별시 송파구 거여동 20",subtype:"근린시설",court:"서울동부지방법원",
 appraisal:7815515600,min_price:4001544000,fail_count:3,sale_date:"2026-11-09",
 lat:null,lng:null,location_source:null,source_url:"",record_date:"2026-10-17",...more
});
test("v11.4 items 행을 공공 표준 lot 스키마로 변환",()=>{
 const output=convertV11Rows([sample()],{filename:"auction_v11.sqlite3",recordDate:"2026-10-17"});
 assert.equal(output.lots.length,1);
 assert.equal(output.lots[0].channel,"court");
 assert.equal(output.lots[0].title,"2023타경51257");
 assert.equal(output.lots[0].appraisal,7815515600);
 assert.equal(output.lots[0].minimum,4001544000);
 assert.equal(output.lots[0].region,"서울특별시");
 assert.equal(output.meta.asOf,"2026-10-17");
 assert.equal(output.meta.kind,"sqlite-local");
 assert.equal(output.meta.verified,false);
});
test("기존 복구본과 같은 21건 SQLite 스냅샷을 목록·검색에서 조회",()=>{
 const rows=Array.from({length:21},(_,i)=>sample({id:"snap:"+i,case_no:"2023타경"+String(i),lat:null,lng:null}));
 const output=convertV11Rows(rows,{recordDate:"2026-10-17"});
 assert.equal(filterLots(output.lots,{region:"서울특별시",q:"송파구"}).length,21);
 assert.equal(output.lots.filter(x=>inViewport(x,{south:37,north:38,west:126,east:128})).length,0);
});
test("public 종류는 공매로 구분",()=>assert.equal(convertV11Rows([sample({kind:"public"})]).lots[0].channel,"public"));
test("기존 좌표가 있다면 출처를 보존",()=>{
 const r=convertV11Rows([sample({lat:37.5,lng:127.1,location_source:"개발자가 확인한 위치"})]);
 assert.equal(r.lots[0].coordinateSource,"개발자가 확인한 위치");
});
test("허용하지 않는 kind 값을 거부",()=>assert.throws(()=>convertV11Rows([sample({kind:"other"})]),/지원하지 않는/));
test("검증되지 않은 DB의 위험 URL 거부",()=>assert.throws(()=>convertV11Rows([sample({source_url:"javascript:alert(1)"})]),/https/));
test("DB 내 중복 ID 거부",()=>assert.throws(()=>convertV11Rows([sample(),sample()]),/중복/));
test("10,000건 초과 데이터 차단",()=>assert.throws(()=>convertV11Rows(Array(SQLITE_MAX_ROWS+1).fill(sample())),/최대/));
test("비어있는 v11 DB 오류 처리",()=>assert.throws(()=>convertV11Rows([]),/없습니다/));
test("유효하지 않은 날짜 거부",()=>assert.throws(()=>convertV11Rows([sample({sale_date:"2026-02-30"})]),/기일/));
test("SQLite 헤더 검사",()=>{
 const b=new Uint8Array(101);
 b.set(new TextEncoder().encode("SQLite format 3\0"));
 assert.equal(hasSQLiteHeader(b),true);
 b[0]=0;assert.equal(hasSQLiteHeader(b),false);
});
test("가짜 SQLite 파일 헤더 시 브라우저 엔진 실행 전에 차단",async()=>{
 const b=new Uint8Array(120);
 await assert.rejects(readV11Sqlite({name:"wrong.db",size:b.byteLength,arrayBuffer:async()=>b.buffer}),/SQLite 데이터베이스/);
});
test("선택한 파일 25MB 초과 차단",async()=>{
 await assert.rejects(readV11Sqlite({name:"big.db",size:26*1024*1024,arrayBuffer:async()=>new ArrayBuffer(1)}),/25MB/);
});
test("SQLite SQL 읽기, v11 스키마 검증 및 DB close",async()=>{
 const bytes=new Uint8Array(200);bytes.set(new TextEncoder().encode("SQLite format 3\0"));
 const columns=["id","kind","case_no","address","subtype","court","appraisal","min_price","fail_count","sale_date","lat","lng","location_source","source_url","record_date"];
 const keys=columns.slice(0,14);
 const row=sample();
 let closed=false,queryCount=0;
 globalThis.window={initSqlJs:async(_config)=>({Database:class{
  constructor(content){assert.equal(content[0],83);}
  exec(sql){
   queryCount++;
   if(sql.startsWith("PRAGMA"))return [{columns:["cid","name"],values:columns.map((c,i)=>[i,c])}];
   if(sql.startsWith("SELECT MAX"))return [{columns:["latest"],values:[["2026-10-17"]]}];
   if(sql.startsWith("SELECT id,"))return [{columns:keys,values:[keys.map(k=>row[k])]}];
   throw Error("Unexpected query "+sql);
  }
  close(){closed=true;}
 }})};
 const parsed=await readV11Sqlite({name:"auction_v11.sqlite3",size:200,arrayBuffer:async()=>bytes.buffer});
 assert.equal(parsed.lots.length,1);
 assert.equal(parsed.lots[0].id,row.id);
 assert.equal(parsed.meta.asOf,"2026-10-17");
 assert.equal(closed,true);
 assert.equal(queryCount,3);
 delete globalThis.window;
});
