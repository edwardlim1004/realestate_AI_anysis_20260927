import test from "node:test";
import assert from "node:assert/strict";
import {MAX_GEOCODE_PER_CLICK,parcelQuery,normalizedAddress,getUnlocatedGroups,classifyGeocodeResponse,applyGeocodedPoint,geocodeWithSdk} from "../advanced/geocode.js";

const make=(id,location,lat=null)=>({id,location,lat,lng:lat===null?null:127.1,coordinateSource:null});
const result=(records)=>({v2:{status:"OK",addresses:records}});
const candidate=(jibunAddress,x="127.1265",y="37.5023")=>({jibunAddress,roadAddress:"",x,y});
test("업로드 DB 주소에서 건물 호실을 제거하고 동·지번까지만 변환",()=>{
 const query=parcelQuery("서울특별시 송파구 오금동 37-2 천광캐슬 제2층 제201호");
 assert.equal(query,"서울특별시 송파구 오금동 37-2");
 assert.equal(parcelQuery("서울특별시 송파구 송파동 85 에스아이팰리스 제9층 제901호"),"서울특별시 송파구 송파동 85");
});
test("지번 없는 모호한 소재지는 추측하지 않음",()=>{
 assert.equal(parcelQuery("서울특별시 송파구 잠실동"),null);
 assert.equal(parcelQuery("서울 아파트"),null);
});
test("공백 정규화",()=>assert.equal(normalizedAddress(" 서울특별시   송파구 가락동 151-4  "),"서울특별시 송파구 가락동 151-4"));
test("같은 지번 물건 2개를 API 1회 그룹으로 묶음",()=>{
 const lots=[make("A","서울특별시 송파구 오금동 37-2 천광캐슬 제201호"),make("B","서울특별시 송파구 오금동 37-2 천광캐슬 제501호"),make("C","서울특별시 송파구 송파동 85")];
 const groups=getUnlocatedGroups(lots);
 assert.equal(groups.length,2);
 assert.deepEqual(groups[0].ids,["A","B"]);
 assert.equal(getUnlocatedGroups(lots,new Set([groups[0].query])).length,1);
});
test("이미 좌표를 확보한 주소는 재조회하지 않음",()=>{
 assert.equal(getUnlocatedGroups([make("A","서울특별시 송파구 송파동 85",37.5)]).length,0);
});
test("한 번에 최대 5곳 조회하도록 UI 한도 고정",()=>assert.equal(MAX_GEOCODE_PER_CLICK,5));
test("네이버 v2 응답에 건물명 포함되어도 동일 지번이면 정확 매칭",()=>{
 const query="서울특별시 송파구 오금동 37-2";
 const r=classifyGeocodeResponse(result([candidate(query+" 천광캐슬")]),query);
 assert.equal(r.status,"exact");assert.equal(r.point.lat,37.5023);
});
test("지번 20 vs 20-1 혼동 방지",()=>{
 const query="서울특별시 송파구 거여동 20";
 assert.equal(classifyGeocodeResponse(result([candidate("서울특별시 송파구 거여동 20-1")]),query).status,"review");
});
test("두 개의 동일 지번 후보도 자동 수락하지 않음",()=>{
 const query="서울특별시 송파구 오금동 37-2";
 assert.equal(classifyGeocodeResponse(result([candidate(query),candidate(query,"127.1264")]),query).status,"review");
});
test("주소 결과 없음 처리",()=>assert.equal(classifyGeocodeResponse(result([]),"서울특별시 송파구 거여동 20").status,"not-found"));
test("유효하지 않은 좌표 거부",()=>assert.equal(classifyGeocodeResponse(result([candidate("서울특별시 송파구 거여동 20","0","0")]),"서울특별시 송파구 거여동 20").status,"not-found"));
test("응답 스키마 오류 식별",()=>assert.throws(()=>classifyGeocodeResponse({v2:{}},"서울특별시 송파구 거여동 20"),/응답/));
test("정확 일치 지번의 모든 물건에 출처와 좌표 표시",()=>{
 const lot1=make("A","서울특별시 송파구 송파동 85 제901호"),lot2=make("B","서울특별시 송파구 송파동 85 제801호"),lot3=make("C","서울특별시 송파구 오금동 37-2");
 const ids=getUnlocatedGroups([lot1,lot2,lot3])[0];
 const changed=applyGeocodedPoint([lot1,lot2,lot3],ids,{lat:37.5,lng:127.1});
 assert.equal(changed,2);assert.equal(lot1.lat,37.5);assert.equal(lot2.lat,37.5);assert.equal(lot3.lat,null);
 assert.match(lot1.coordinateSource,/대표점·미검증/);
});
test("좌표나 지번이 다른 물건의 임의 변경 금지",()=>{
 const a=make("A","서울특별시 송파구 오금동 37-2");
 const changed=applyGeocodedPoint([a],{query:"서울특별시 송파구 거여동 20",ids:["A"]},{lat:37.5,lng:127.1});
 assert.equal(changed,0);assert.equal(a.lat,null);
});
test("지번 수동 확인 적용 출처 기록",()=>{
 const a=make("A","서울특별시 송파구 송파동 85");
 applyGeocodedPoint([a],{query:parcelQuery(a.location),ids:["A"]},{lat:37.52,lng:127.1},"manual");
 assert.match(a.coordinateSource,/사용자 후보 선택/);
});
test("Naver SDK geocode는 query 방식과 v2 응답 사용",async()=>{
 const query="서울특별시 송파구 거여동 20";let input;
 const maps={Service:{Status:{OK:"OK"},geocode:(opts,cb)=>{input=opts;cb("OK",result([candidate(query)]));}}};
 const v=await geocodeWithSdk(maps,query);
 assert.deepEqual(input,{query});assert.equal(v.status,"exact");
});
test("API 인증/쿼터 오류 시 실제 실패로 반환하고 좌표 만들지 않음",async()=>{
 const maps={Service:{Status:{OK:"OK"},geocode:(opts,cb)=>cb("ERROR",{error:"429"})}};
 await assert.rejects(geocodeWithSdk(maps,"서울특별시 송파구 거여동 20"),/요청 실패/);
});
test("Geocoder 모듈 미설치 식별",async()=>{
 await assert.rejects(geocodeWithSdk({},"서울특별시 송파구 거여동 20"),/모듈/);
});
