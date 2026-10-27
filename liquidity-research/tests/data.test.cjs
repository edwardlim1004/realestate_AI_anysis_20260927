/* Offline regression tests: ECOS provenance, quarter alignment, math, immutable composite boundary. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = require('../app.js');
const root = path.resolve(__dirname,'../..');
const rows = app.parseCsv(fs.readFileSync(path.join(root,'risk-data/liquidity/raw.csv'),'utf-8'));
const history = app.quarterlyFromEcos(rows);
const expected = JSON.parse(fs.readFileSync(path.join(root,'risk-data/liquidity/excess_liquidity_comparison.json'),'utf-8'));
assert.ok(history.length>60,'at least 60 quarters of growth data');
const last=history.at(-1);
assert.equal(last.period,expected.latestObservation.period);
for(const [key,output] of [['m2LogYoYGrowthPctPoints','m2'],['nominalGdpLogYoYGrowthPctPoints','gdp'],['excessMoneyGrowthLogPctPoints','excess'],['excessMoneyGrowth4QuarterMeanLogPctPoints','average']]){
  assert.ok(Math.abs(expected.latestObservation[key]-last[output])<0.00001,key+': expected stored comparison to match fresh ECOS CSV');
}
for(const r of history) {
  assert.ok(Number.isFinite(r.m2)&&Number.isFinite(r.gdp)&&Number.isFinite(r.excess));
  assert.ok(Math.abs(r.m2-r.gdp-r.excess)<1e-9);
}
assert.equal(app.quarterShift('2024-Q1',-4),'2023-Q1');
assert.equal(app.quarterShift('2024-Q4',1),'2025-Q1');
const synthetic=[
  ...[1,2,3].map(m=>({Series:'M2',Period:'202301'.slice(0,4)+String(m).padStart(2,'0'),Value:'100'})),
  ...[1,2,3].map(m=>({Series:'M2',Period:'202401'.slice(0,4)+String(m).padStart(2,'0'),Value:'110'})),
  {Series:'NOMINAL_GDP',Period:'2023-Q1',Value:'200'},
  {Series:'NOMINAL_GDP',Period:'2024-Q1',Value:'200'}
];
let result=app.quarterlyFromEcos(synthetic);
assert.equal(result.length,1);
assert.ok(Math.abs(result[0].excess-100*Math.log(1.1))<1e-9);
result=app.quarterlyFromEcos(synthetic.filter(r=>r.Period!=='202403'));
assert.equal(result.length,0,'missing M2 month must not be treated as a valid quarter');
const publicRisk=fs.readFileSync(path.join(root,'risk-data.js'),'utf-8');
assert.ok(publicRisk.length>100,'official risk dataset still present');
const promotion=JSON.parse(fs.readFileSync(path.join(root,'risk-monitor/liquidity/promotion.json'),'utf-8'));
assert.equal(promotion.enabled,false,'SHADOW activation remains disabled');
console.log('PASS: actual official 2003+ ECOS series matches comparison, no fabricated months, composite remains isolated');
