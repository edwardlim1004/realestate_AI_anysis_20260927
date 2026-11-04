import test from 'node:test';
import assert from 'node:assert/strict';
import {convertKSkillCourtSearch} from '../tools/k-skill-court-import.mjs';
import {parseImport} from '../advanced/core.js';

const row=()=>({
  courtCode:'B000210',courtName:'서울중앙지방법원',displayCaseNumber:'2026타경12345',
  itemNumber:'1',address:'서울특별시 강남구 역삼동 123-4',
  appraisedPrice:700000000,minimumSalePrice:560000000,
  saleDate:'2026-11-20',flbdCount:1,usageCodes:{large:'20000'},
  coordinatesWgs84:{x:127,y:37},raw:{hjguSido:'서울특별시'}
});
const payload=(items=[row()])=>({page:{pageNo:1,totalCount:1},count:items.length,items});
const opts={now:new Date('2026-11-04T05:00:00.000Z')};
test('정규화된 검색 결과를 기존 Classic/Advanced import 형식으로 변환',()=>{
  const out=convertKSkillCourtSearch(payload(),opts);
  const imported=parseImport(JSON.stringify(out));
  assert.equal(imported.lots[0].id,'court:B000210:2026타경12345:1');
  assert.equal(imported.lots[0].minimum,560000000);
  assert.equal(imported.lots[0].date,'2026-11-20');
  assert.equal(imported.lots[0].region,'서울특별시');
  assert.equal(out.integration.verified,false);
  assert.equal(out.collectedAt,'2026-11-04T05:00:00.000Z');
});
test('원본 WGS84 좌표를 무검증 지도 마커로 사용하지 않음',()=>{
  const l=convertKSkillCourtSearch(payload(),opts).lots[0];
  assert.equal(l.lat,null);assert.equal(l.lng,null);assert.equal(l.coordinateSource,null);
});
test('가격 미제공은 0으로 채우지 않고 null 유지',()=>{
  const r={...row(),appraisedPrice:null,minimumSalePrice:null};
  const l=convertKSkillCourtSearch(payload([r]),opts).lots[0];
  assert.equal(l.appraisal,null);assert.equal(l.minimum,null);
});
test('페이지 응답·공고 목록·원본 응답 혼동을 거부',()=>{
  assert.throws(()=>convertKSkillCourtSearch({items:[row()]},opts),/search 결과/);
  assert.throws(()=>convertKSkillCourtSearch({data:{dlt_srchResult:[]},status:200},opts),/정규화된/);
});
test('중복 사건+물건 및 유찰 정보 누락을 거부',()=>{
  assert.throws(()=>convertKSkillCourtSearch(payload([row(),row()]),opts),/중복/);
  assert.throws(()=>convertKSkillCourtSearch(payload([{...row(),flbdCount:undefined}]),opts),/유찰횟수/);
});
test('비정상 금액·날짜를 거부',()=>{
  assert.throws(()=>convertKSkillCourtSearch(payload([{...row(),minimumSalePrice:-1}]),opts),/정수/);
  assert.throws(()=>convertKSkillCourtSearch(payload([{...row(),saleDate:'2026-02-30'}]),opts),/기일/);
});
