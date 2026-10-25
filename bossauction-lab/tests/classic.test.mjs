import test from "node:test";
import assert from "node:assert/strict";
import {groupByLocation,summarize,sectionFilter,exportLocalLots} from "../classic/classic-core.js";
const l=(id,location,channel="court",lat=null,lng=null,type="다세대")=>({id,location,channel,lat,lng,type,region:"서울특별시"});
test("지역 집계는 좌표가 확인된 실제 사용자 물건만",()=>{
 const lots=[l("A","서울특별시 송파구 오금동 37-2","court",37.5,127.12),l("B","서울특별시 송파구 오금동 38-1","public",37.51,127.13),l("C","서울특별시 송파구 가락동 151-4")];
 const groups=groupByLocation(lots);
 assert.equal(groups.length,1);assert.equal(groups[0].dong,"오금동");
 assert.equal(groups[0].court,1);assert.equal(groups[0].public,1);assert.equal(groups[0].count,2);
 assert.equal(groups[0].lat,37.504999999999995);
});
test("스냅샷 기준 DB 통계에는 가짜 전국 경매 272건을 포함하지 않음",()=>{
 assert.deepEqual(summarize([l("A","서울특별시 송파구 오금동 37-2")]),{total:1,court:1,public:0,located:0,unlocated:1,regions:0});
});
test("좌표 없는 경우 지역 마커 생성 금지",()=>assert.deepEqual(groupByLocation([l("A","서울특별시 송파구 오금동 37-2")]),[]));
test("종류별 검색",()=>{
 const lots=[l("A","서울특별시 송파구 오금동 37-2"),l("B","서울특별시 송파구 오금동 37-2","public"),l("C","서울특별시 송파구 오금동 37-2","court",null,null,"아파트")];
 assert.equal(sectionFilter(lots,"auction").length,2);
 assert.equal(sectionFilter(lots,"public").length,1);
 assert.equal(sectionFilter(lots,"apt").length,1);
});
test("관심 검색은 ID만 매칭",()=>assert.equal(sectionFilter([l("A","서울특별시 송파구 오금동 37-2"),l("B","서울특별시 송파구 오금동 37-2")],"favorites",new Set(["A"])).length,1));
test("매각 결과 확인 데이터가 없으면 숫자 날조하지 않음",()=>assert.equal(sectionFilter([l("A","서울특별시 송파구 오금동 37-2")],"sale").length,0));
test("기존 21건은 본인 브라우저 내 JSON 내보내기",()=>assert.equal(JSON.parse(exportLocalLots([l("A","서울특별시 송파구 오금동 37-2")],{name:"v11 local"})).lots.length,1));
