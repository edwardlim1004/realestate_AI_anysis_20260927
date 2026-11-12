const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),zlib=require('node:zlib');
const elements={};function el(id){return elements[id]??={value:'',textContent:'',innerHTML:'',hidden:false,events:{},addEventListener(k,f){this.events[k]=f;}};}
['metroCity','metroClose','historyOpen','metroHistory','metroHistoryStatus','metroDistrict','metroFrom','metroTo','metroType','metroHeading','metroMonthlyRows','metroContractMonth','metroContractSearch','metroContractsStatus','metroContractRows','metroHistoryChart','metroDownload'].forEach(el);el('metroType').value='sale';
const buttons=['busan','daegu','gwangju'].map(c=>({...el(c),dataset:{metro:c},classList:{toggle(){},remove(){}},setAttribute(){}}));
const legacy={dataset:{area:'seoul'},events:{},classList:{toggle(){},remove(){}},setAttribute(){},addEventListener(k,f){this.events[k]=f;}};
const metric={rows:1,median_manwon:2000,monthly_rent_median_manwon:95};
const detail={date:'2026-09-14',apt:'과거단지',city:'부산',dong:'동',jibun:'1',area:'84',floor:'2',price:'20000',deposit:'2000',monthlyRent:'95'};
const data={schema:1,start:'200601',end:'202611',name:'중구',code:'26110',updated_at_kst:'2026-11-10',months:{'202609':{sale:{status:'ready',metrics:{sale:metric},latest:{sale:[detail]}},rent:{status:'ready',metrics:{monthly:metric},latest:{monthly:[detail]}}},'202611':{sale:{status:'missing'},rent:{status:'missing'}}}};
let mode=false;const requested=[];
const ctx={document:{getElementById:el,querySelector(){return {click(){legacy.events.click();}};},querySelectorAll(q){return q==='[data-area]'?[legacy]:q==='[data-open-history]'?[el('historyOpen')]:buttons;},body:{classList:{add(){mode=true;},remove(){mode=false;},contains(){return mode;}}}},window:{},Chart:function(_,config){ctx.config=config;this.destroy=()=>{};},fetch:async path=>{requested.push(path);return /index.*\.json$/.test(path)?new Response(JSON.stringify({cities:{busan:[{status:'ready',file:'busan-26110.json.gz',name:'중구'}],seoul:[{status:'ready',file:'seoul-11710.json.gz',name:'송파구'}],gyeonggi:[{status:'ready',file:'gyeonggi-41135.json.gz',name:'성남시 분당구'}]}})):new Response(zlib.gzipSync(JSON.stringify(data)));},Response,Blob,DecompressionStream,console,URL};ctx.window.Chart=ctx.Chart;
vm.runInNewContext(fs.readFileSync('dashboard-v1/metro-history.js','utf8'),ctx);
(async()=>{
 el('metroDistrict').value='busan-26110.json.gz';await buttons[0].events.click();
 assert.match(el('metroMonthlyRows').innerHTML,/미수집/);assert.equal(ctx.config.data.datasets[0].data[1],null);
 el('metroContractMonth').value='202611';el('metroContractMonth').events.change();assert.match(el('metroContractsStatus').textContent,/과거 공개 표본 중 최근 기록/);assert.match(el('metroContractRows').innerHTML,/2026-09-14/);
 el('metroType').value='monthly';el('metroType').events.change();el('metroContractMonth').value='202611';el('metroContractMonth').events.change();assert.match(el('metroContractRows').innerHTML,/월 95만원/);
 el('metroFrom').value='2026-12';el('metroTo').value='2026-01';el('metroFrom').events.change();assert.match(el('metroHistoryStatus').textContent,/시작월/);
 el('metroDistrict').value='seoul-11710.json.gz';await el('historyOpen').events.click();assert.ok(requested.some(p=>p.endsWith('index-seoul.json')));
 el('metroCity').value='gyeonggi';el('metroDistrict').value='gyeonggi-41135.json.gz';await el('metroCity').events.change();assert.ok(requested.some(p=>p.endsWith('index-gyeonggi.json')));
 el('metroClose').events.click();assert.equal(el('metroHistory').hidden,true);
 console.log('PASS metro: missing != zero, past contract fallback, monthly amount, date validation, return to Seoul');
})().catch(e=>{console.error(e);process.exitCode=1});
