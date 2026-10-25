import test from "node:test";
import assert from "node:assert/strict";
import {FREE_DYNAMIC_MAP,FREE_GEOCODING,validClientId,readClientId,saveClientId,clearClientId,koreaMonth,validateUsage,buildQuotaSnapshot,quotaOverview,remainingUsage,readQuotaSnapshot,saveQuotaSnapshot,deleteQuotaSnapshot,localGeocodeRequests,recordLocalGeocodeRequest} from "../advanced/maps-account.js";
const store=()=>{
 const x=new Map();
 return {getItem:k=>x.get(k)??null,setItem:(k,v)=>x.set(k,String(v)),removeItem:k=>x.delete(k)};
};
const oct=new Date("2026-10-25T07:00:00.000Z"),nov=new Date("2026-11-01T00:05:00.000Z");
test("공식 Maps 월 무료 한도 표시",()=>{assert.equal(FREE_DYNAMIC_MAP,6_000_000);assert.equal(FREE_GEOCODING,3_000_000);});
test("브라우저 Client ID 저장, 복원, 명시적 삭제",()=>{
 const s=store();assert.equal(readClientId(s),null);
 assert.equal(saveClientId(s,"validPublicId_123"),true);
 assert.equal(readClientId(s),"validPublicId_123");
 assert.equal(clearClientId(s),true);assert.equal(readClientId(s),null);
});
test("Client Secret 비슷한 형식과 URL 등을 저장하지 않음",()=>{
 assert.equal(validClientId(""),false);
 assert.equal(validClientId("abc!@_"),false);
 assert.equal(validClientId("https://example.com?a=1"),false);
 assert.throws(()=>saveClientId(store(),"spaces in public id"),/형식/);
});
test("저장소 차단 시 안전하게 처리",()=>{
 const s={getItem(){throw Error("denied");},setItem(){throw Error("denied");},removeItem(){throw Error("denied");}};
 assert.equal(readClientId(s),null);assert.equal(saveClientId(s,"valid_abc123"),false);assert.equal(clearClientId(s),false);
});
test("월 기준은 한국 시간 경계",()=>{
 assert.equal(koreaMonth(new Date("2026-10-31T14:59:59Z")),"2026-10");
 assert.equal(koreaMonth(new Date("2026-10-31T15:00:00Z")),"2026-11");
});
test("빈 사용량은 0이 아니라 미확인",()=>{
 assert.equal(validateUsage(""),null);assert.equal(validateUsage(null),null);
 assert.throws(()=>buildQuotaSnapshot("","",oct),/하나 이상/);
});
test("실제 콘솔 입력으로 계산하는 남은 무료량",()=>{
 const snap=buildQuotaSnapshot("12000","19",oct);
 const view=quotaOverview(snap,oct);
 assert.equal(view.month,"2026-10");
 assert.equal(view.map.remaining,5_988_000);
 assert.equal(view.geocoding.remaining,2_999_981);
});
test("초과한 사용량은 음수 잔여로 표시하지 않음",()=>{
 assert.equal(remainingUsage(6_000_000,7_000_000),0);
 assert.equal(remainingUsage(3_000_000,3_000_000),0);
});
test("다음 달에는 이전 달 사용량으로 잔여를 주장하지 않음",()=>{
 const snap=buildQuotaSnapshot("12000","19",oct),view=quotaOverview(snap,nov);
 assert.equal(view.stale,true);assert.equal(view.map.remaining,null);assert.equal(view.geocoding.remaining,null);
});
test("한 서비스의 사용량만 입력했다면 다른 것은 미확인",()=>{
 const view=quotaOverview(buildQuotaSnapshot("","17",oct),oct);
 assert.equal(view.map.remaining,null);assert.equal(view.geocoding.remaining,2_999_983);
});
test("음수·소수·지수·불량 사용량 차단",()=>{
 for(const value of ["-1","0.5","1e8","Infinity",{},2.2,Number.MAX_SAFE_INTEGER])assert.throws(()=>validateUsage(value));
});
test("수동 콘솔 사용량 브라우저 저장·삭제",()=>{
 const s=store(),snap=buildQuotaSnapshot("200","3",oct);
 assert.equal(saveQuotaSnapshot(s,snap),true);assert.deepEqual(readQuotaSnapshot(s),snap);
 assert.equal(deleteQuotaSnapshot(s),true);assert.equal(readQuotaSnapshot(s),null);
});
test("주소변환 호출 카운터는 이 브라우저에서만 계산하고 다음달 초기화",()=>{
 const s=store();assert.equal(recordLocalGeocodeRequest(s,oct),1);
 assert.equal(recordLocalGeocodeRequest(s,oct),2);assert.equal(localGeocodeRequests(s,oct),2);
 assert.equal(localGeocodeRequests(s,nov),0);
});
