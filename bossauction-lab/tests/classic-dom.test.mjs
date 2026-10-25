import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
const h=readFileSync(new URL("../classic/index.html",import.meta.url),"utf8");
const js=readFileSync(new URL("../classic/classic.js",import.meta.url),"utf8");
test("복원된 v11 세로 메뉴 기능을 표시",()=>{
 for(const page of ["map","schedule","search","auction","public","sale","apt","land","trade","favorites","analysis"])
  assert.ok(h.includes('data-section="'+page+'"'),page+" navigation missing");
});
test("SDK 진단, 위치 지정, 실측 및 지도 레이어 UI 복원",()=>{
 for(const id of ["sdk-settings","sdk-connect","sdk-forget","debug-logs","download-diagnostics","place-mode","distance-mode","area-mode","map-cadastral","map-type-satellite","map-summary"])
  assert.ok(h.includes('id="'+id+'"'),id+" missing");
});
test("CSV가 아닌 v11 sqlite, 물건 검색, 상세 모달, 지도 클러스터 표시 기능",()=>{
 for(const id of ["db-file","db-load","db-remember","results","detail-dialog","total-court","total-public","total-located"])
  assert.ok(h.includes('id="'+id+'"'),id+" missing");
 for(const bit of ["readV11Sqlite","restorePrivateSnapshot","groupByLocation","new nav.Marker","new nav.Polygon","new nav.Polyline"])
  assert.ok(js.includes(bit),bit+" not wired");
});
test("기존 저장 네이버 ID를 재사용하되 클라이언트 시크릿은 없음",()=>{
 assert.ok(js.includes("readClientId(storage())"));
 assert.ok(js.includes("void connectSDK({automatic:true})"));
 assert.equal(/clientSecret\s*[:=]/i.test(js),false);
});
test("모든 ID 의존성은 DOM에 존재",()=>{
 const ids=new Set([...h.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]));
 const required=[...js.matchAll(/\$\("([a-zA-Z0-9_-]+)"\)/g)].map(x=>x[1]);
 const missing=[...new Set(required)].filter(x=>!ids.has(x));
 assert.deepEqual(missing,[]);
});
test("원본 저장 숫자를 실시간으로 표시하지 않음",()=>{
 assert.equal(h.includes("272건"),false);
 assert.equal(h.includes("187,992"),false);
 assert.ok(js.includes("summarize(state.lots)"));
});
test("기존 화면이 제3자 저장 사진이나 HTML 화면을 직접 올리지 않음",()=>{
 assert.equal(h.includes("snapshot_detail"),false);
 assert.equal(h.includes("map_snapshot.jpg"),false);
 assert.equal(h.includes("saved_map_images"),false);
});
