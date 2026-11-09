const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),zlib=require('node:zlib');
const elements={};function el(id){return elements[id]??={value:'',textContent:'',innerHTML:'',hidden:false,events:{},addEventListener(k,f){this.events[k]=f;}};}
['metroHistory','metroHistoryStatus','metroDistrict','metroFrom','metroTo','metroType','metroHeading','metroMonthlyRows','metroContractMonth','metroContractSearch','metroContractsStatus','metroContractRows','metroHistoryChart','metroDownload'].forEach(el);el('metroType').value='sale';
const buttons=['busan','daegu','gwangju'].map(c=>({...el(c),dataset:{metro:c},classList:{toggle(){},remove(){}},setAttribute(){}}));
const legacy={dataset:{area:'seoul'},events:{},classList:{toggle(){},remove(){}},setAttribute(){},addEventListener(k,f){this.events[k]=f;}};
const metric={rows:1,median_manwon:2000,monthly_rent_median_manwon:95};
const detail={date:'2026-09-14',apt:'과거단지',city:'부산',dong:'동',jibun:'1',area:'84',floor:'2',price:'20000',deposit:'2000',monthlyRent:'95'};
const data={schema:1,start:'200601',end:'202611',name:'중구',code:'26110',updated_at_kst:'2026-11-10',months:{'202609':{sale:{status:'ready',metrics:{sale:metric},latest:{sale:[detail]}},rent:{status:'ready',metrics:{monthly:metric},latest:{monthly:[detail]}}},'202611':{sale:{status:'missing'},rent:{status:'missing'}}}};
const ctx={document:{getElementById:el,querySelectorAll(q){return q==='[data-area]'?[legacy]:buttons;},body:{classList:{add(){},remove(){}}}},window:{},Chart:function(_,config){ctx.config=config;this.destroy=()=>{};},fetch:async path=>path.endsWith('index.json')?new Response(JSON.stringify({cities:{busan:[{status:'ready',file:'busan-26110.json.gz',name:'중구'}]}})):new Response(zlib.gzipSync(JSON.stringify(data))),Response,Blob,DecompressionStream,console,URL};ctx.window.Chart=ctx.Chart;
vm.runInNewContext(fs.readFileSync('dashboard-v1/metro-history.js','utf8'),ctx);
(async()=>{
 el('metroDistrict').value='busan-26110.json.gz';await buttons[0].events.click();
 assert.match(el('metroMonthlyRows').innerHTML,/미수집/);assert.equal(ctx.config.data.datasets[0].data[1],null);
 el('metroContractMonth').value='202611';el('metroContractMonth').events.change();assert.match(el('metroContractsStatus').textContent,/과거 최근 기록/);assert.match(el('metroContractRows').innerHTML,/2026-09-14/);
 el('metroType').value='monthly';el('metroType').events.change();el('metroContractMonth').value='202611';el('metroContractMonth').events.change();assert.match(el('metroContractRows').innerHTML,/월 95만원/);
 el('metroFrom').value='2026-12';el('metroTo').value='2026-01';el('metroFrom').events.change();assert.match(el('metroHistoryStatus').textContent,/시작월/);
 legacy.events.click();assert.equal(el('metroHistory').hidden,true);
 console.log('PASS metro: missing != zero, past contract fallback, monthly amount, date validation, return to Seoul');
})().catch(e=>{console.error(e);process.exitCode=1});
