import test from "node:test";
import assert from "node:assert/strict";
import {csvRows,parseImport,filterLots,inViewport,costScenario,escapeHTML,dateOK} from "../advanced/core.js";
const lot={id:"TEST-1",channel:"court",title:"가상",region:"서울",type:"아파트",location:"서울",authority:"가상 법원",appraisal:100000000,minimum:70000000,date:"2026-11-05",lat:37.57,lng:126.98,coordinateSource:"사용자",sourceUrl:"https://example.org/lot"};
const data=()=>JSON.stringify({sourceName:"테스트",lots:[lot]});
test("JSON lot 파싱",()=>assert.equal(parseImport(data()).lots[0].id,lot.id));
test("CSV 이스케이프 처리",()=>assert.deepEqual(csvRows('a,b\n"1,2",3\r\n4,5'),[["a","b"],["1,2","3"],["4","5"]]));
test("한글 CSV 컬럼 대응",()=>assert.equal(parseImport("물건ID,구분,물건명,소재지,지역,감정가_원,최저가_원,매각기일\nC-1,경매,테스트,서울 송파구,서울,100000000,70000000,2026-11-03","test.csv").lots[0].minimum,70000000));
test("중복 ID 차단",()=>assert.throws(()=>parseImport(JSON.stringify({lots:[lot,lot]})),/중복/));
test("음수 가격 차단",()=>assert.throws(()=>parseImport(JSON.stringify({lots:[{...lot,minimum:-1}]})),/가격/));
test("범위 밖 좌표 차단",()=>assert.throws(()=>parseImport(JSON.stringify({lots:[{...lot,lat:1}]})),/범위/));
test("악성 URL 차단",()=>assert.throws(()=>parseImport(JSON.stringify({lots:[{...lot,sourceUrl:"javascript:alert(1)"}]})),/https/));
test("뷰포트 경계 필터",()=>{const {lots}=parseImport(data());assert.equal(inViewport(lots[0],{south:37,north:38,west:126,east:128}),true);assert.equal(inViewport(lots[0],{south:35,north:36,west:126,east:128}),false);});
test("텍스트·채널 필터",()=>assert.equal(filterLots([lot],{q:"서울",region:"서울",channel:"court"}).length,1));
test("보증금 중복 없는 비용 계산",()=>{const r=costScenario({bid:400000000,depositPercent:10,feePercent:1,extra:20000000,resale:500000000});assert.equal(r.deposit,40000000);assert.equal(r.balance,360000000);assert.equal(r.total,424000000);});
test("HTML escape",()=>assert.equal(escapeHTML('<img onerror="x">'),'&lt;img onerror=&quot;x&quot;&gt;'));
test("날짜 유효성",()=>{assert.equal(dateOK("2026-02-30"),false);assert.equal(dateOK("2026-11-03"),true);});

test("형식상 날짜지만 달/일이 불가능하면 예외 없이 거부",()=>{
 assert.equal(dateOK("2026-13-99"),false);
 assert.throws(()=>parseImport(JSON.stringify({lots:[{...lot,date:"2026-13-99"}]})),/기일/);
});
test("좌표 없는 물건에 지도 마커를 만들지 않는 필터",()=>{
 const {lots}=parseImport(JSON.stringify({lots:[{...lot,lat:null,lng:null}]}));
 assert.equal(inViewport(lots[0],{south:32,north:39,west:124,east:132}),false);
});
