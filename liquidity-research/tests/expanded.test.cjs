'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const f=require('../expanded.js');
const base=require('../app.js');
const root=path.resolve(__dirname,'../..');
const rows=base.parseCsv(fs.readFileSync(path.join(root,'risk-data/liquidity/raw.csv'),'utf-8'));
const levels=f.calculateAbsoluteLevels(rows);
assert.ok(levels.length>=80,'long quarterly official record required');
const latest=levels.at(-1);
assert.equal(latest.period,'2026-Q2');
assert.ok(latest.nominalM2>0 && latest.realM2>0);
assert.ok(latest.marshall>0 && latest.marshall<10,'M2 stock / trailing year GDP units must align');
assert.ok(Number.isFinite(latest.realGap)&&Number.isFinite(latest.marshallGap));
assert.ok(latest.realRank>=0&&latest.realRank<=100);
assert.ok(latest.marshallRank>=0&&latest.marshallRank<=100);
assert.ok(latest.m2Rank>=0&&latest.m2Rank<=100);
assert.ok(levels.slice(0,40).every(r=>r.realGap===null),'trend warmup must not peek into future');
assert.equal(f.fitExpectedLog([1,2,3],2),null,'trend does not accept less than 40 earlier observations');
const earlier=levels.slice(0,-1),baseValues=levels.map(r=>r.realGap);
const alteredRows=rows.concat(rows.filter(r=>r.Period==='202606').map(r=>({...r,Period:'202609',Value:'999999'})));
const altered=f.calculateAbsoluteLevels(alteredRows);
assert.equal(altered[altered.length-2].realGap,earlier.at(-1).realGap,
  'future data cannot change already calculated observed trend');
assert.equal(f.quarterlyMean(new Map([['202601',1],['202602',2]]),'2026-Q1'),null,
  'partial 3-month quarter must be excluded');
assert.equal(f.quarterlyMean(new Map([['202601',1],['202602',2],['202603',3]]),'2026-Q1'),2);
const stock=f.quarterlyMarket([
{Series:'KOSPI',Quarter:'2025-Q1',Value:'2500',StatisticCode:'802Y001',ItemCode:'0001000',ObservationCount:'61',SourceURL:'https://ecos.bok.or.kr/api/'},
{Series:'KOSPI',Quarter:'2025-Q2',Value:'2999',StatisticCode:'BAD',ItemCode:'0001000',ObservationCount:'60',SourceURL:'https://ecos.bok.or.kr/api/'},
{Series:'KTB3Y',Quarter:'2025-Q1',Value:'2.53',StatisticCode:'817Y002',ItemCode:'010200000',ObservationCount:'63',SourceURL:'https://ecos.bok.or.kr/api/'}
]);
assert.equal(stock.KOSPI.size,1,'reject forged or mismatched ECOS observations');
assert.equal(stock.KTB3Y.get('2025-Q1'),2.53);
const csv=fs.readFileSync(path.join(root,'risk-data/risk_raw.csv'),'utf8');
const house=f.quarterlyHpi(base.parseCsv(csv));
assert.ok(house.size>=70,'genuine OECD national housing history');
const nationalExample=[...house][0];
assert.ok(nationalExample[0].includes('-Q')&&Number.isFinite(nationalExample[1]));
assert.equal(f.quarterSeoulPrices(null).size,0,'no synthetic Seoul observations');
const html=fs.readFileSync(path.join(root,'liquidity-research/index.html'),'utf8');
for (const required of ['id="liquidity-levels"','id="liquidity-change"','id="transmission"','id="moneyLevelChart"','id="liquidityGapChart"','id="housingChart"','id="kospiChart"','id="bondChart"','한국은행 ECOS','OECD'])
  assert.ok(html.includes(required),required);
const promotion=JSON.parse(fs.readFileSync(path.join(root,'risk-monitor/liquidity/promotion.json'),'utf8'));
assert.equal(promotion.enabled,false,'official 6-pillar score isolated');
console.log('PASS levels: M2/CPI/GDP derived from real ECOS, 40Q lookback no future, 3 asset charts sourced, SHADOW OFF');
