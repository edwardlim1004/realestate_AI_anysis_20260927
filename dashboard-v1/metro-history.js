/* Public monthly histories; raw storage credentials never reach the browser. */
(function(){
'use strict';
const $=id=>document.getElementById(id),names={busan:'부산',daegu:'대구',gwangju:'광주'},types={sale:'매매',jeonse:'전세',monthly:'월세'};
const base='dashboard-v1/data/metro-history/';let city='busan',index,series,chart,request=0;
const cache={};const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const num=x=>x==null?'—':Number(x).toLocaleString('ko-KR',{maximumFractionDigits:2});
const date=x=>x.slice(0,4)+'-'+x.slice(4);
function status(r){return ({missing:'미수집',not_available:'제공기간 이전',alias_review_required:'행정코드 중복 검토',error:'자료 확인 필요'})[r?.status]||'거래 없음';}
async function json(path,compressed=false){const r=await fetch(base+path,{cache:'no-cache'});if(!r.ok)throw Error('자료 생성 또는 갱신 중입니다. 잠시 후 다시 조회해 주세요.');if(!compressed)return r.json();const bytes=await r.arrayBuffer();return new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).json();}
function metrics(ym,type){const r=series.months[ym]?.[type==='sale'?'sale':'rent'];return {record:r,value:r?.metrics?.[type]};}
function render(){
 if(!series)return;
 const type=$('metroType').value,first=$('metroFrom').value.replace('-',''),last=$('metroTo').value.replace('-','');
 if(first>last){$('metroHistoryStatus').textContent='시작월은 종료월보다 늦을 수 없습니다.';return;}
 const months=Object.keys(series.months).filter(m=>m>=first&&m<=last).sort();
 const points=months.map(m=>metrics(m,type));
 $('metroHistoryStatus').textContent=`${names[city]} · ${series.name} · ${date(first)} ~ ${date(last)} · 갱신 ${series.updated_at_kst} · 당월/최근월 잠정, 신고·취소에 따라 변경`;
 $('metroMonthlyRows').innerHTML=months.slice().reverse().map(m=>{const {record:r,value:v}=metrics(m,type);return `<tr><td>${date(m)}</td><td>${v?num(v.median_manwon):'—'}</td><td>${type==='monthly'&&v?num(v.monthly_rent_median_manwon):'—'}</td><td>${v?num(v.rows):'—'}</td><td>${r?.status==='ready'?(v?.rows?'확인된 기록':'거래 없음'):status(r)}</td></tr>`;}).join('');
 if(chart)chart.destroy();
 if(window.Chart)chart=new Chart($('metroHistoryChart'),{type:'line',data:{labels:months.map(date),datasets:[{label:type==='monthly'?'월세 보증금 중위값 (만원)':types[type]+' 중위가격 (만원)',data:points.map(p=>p.value?.median_manwon??null),borderColor:'#087eb8',pointRadius:0,spanGaps:false},...(type==='monthly'?[{label:'월 임대료 중위값 (만원)',data:points.map(p=>p.value?.monthly_rent_median_manwon??null),borderColor:'#00998b',pointRadius:0,yAxisID:'rent',spanGaps:false}]:[])]},options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'index',intersect:false},scales:{y:{title:{display:true,text:'만원'}},...(type==='monthly'?{rent:{position:'right',grid:{drawOnChartArea:false},title:{display:true,text:'월 임대료 (만원)'}}}:{})}}});
 const options=months.slice().reverse();const previous=$('metroContractMonth').value;
 $('metroContractMonth').innerHTML=options.map(m=>`<option value="${m}">${date(m)}</option>`).join('');
 $('metroContractMonth').value=options.includes(previous)?previous:(options[0]||'');renderContracts();
}
function renderContracts(){
 if(!series)return;
 const type=$('metroType').value,selected=$('metroContractMonth').value,query=$('metroContractSearch').value.trim().toLowerCase();
 let chosen=selected,rows=[],record;
 const months=Object.keys(series.months).filter(m=>m<=selected&&m>=$('metroFrom').value.replace('-','')).sort().reverse();
 for(const ym of months){const item=metrics(ym,type);const matching=(item.record?.latest?.[type]||[]).filter(r=>[r.apt,r.dong,r.jibun].join(' ').toLowerCase().includes(query));if(matching.length){chosen=ym;rows=matching;record=item.record;break;}}
 $('metroContractsStatus').textContent=rows.length?`${chosen===selected?'선택월 기록':'과거 최근 기록'} · ${date(chosen)} · ${rows.length}행 표시 · 월별 거래유형 최신 70행 내 검색 (전 면적)`:`조회기간의 공개 표본에서 일치하는 기록이 없습니다. 월별 최신 70행만 공개하므로 전체 거래 부재를 뜻하지 않습니다.`;
 $('metroContractRows').innerHTML=rows.map(r=>`<tr><td>${esc(r.date)}</td><td><b>${esc(r.apt)}</b><br>${esc(r.city+' '+r.dong+' '+r.jibun)}</td><td>${esc(r.area)}㎡</td><td>${esc(r.floor)}</td><td>${type==='sale'?num(r.price):num(r.deposit)}만원${type==='monthly'?'<br>월 '+num(r.monthlyRent)+'만원':''}</td></tr>`).join('')||'<tr><td colspan="5">표시할 공개 표본이 없습니다.</td></tr>';
}
async function loadDistrict(){const seq=++request;series=null;$('metroHistoryStatus').textContent='월별 기록을 불러오는 중…';$('metroMonthlyRows').innerHTML='';$('metroContractRows').innerHTML='';if(chart){chart.destroy();chart=null;}
 try{const file=$('metroDistrict').value;if(!file)throw Error('조회 가능한 지역 자료를 생성 중입니다.');const data=cache[file]||(cache[file]=await json(file,true));if(seq!==request)return;series=data;$('metroFrom').value=date(data.start);$('metroTo').value=date(data.end);render();}catch(e){if(seq===request)$('metroHistoryStatus').textContent=e.message;}}
async function open(value){city=value;document.body.classList.add('metro-mode');$('metroHistory').hidden=false;$('metroHeading').textContent=names[city]+' 아파트 · 과거부터 현재까지';
 document.querySelectorAll('#topRegionTabs button').forEach(b=>{const yes=b.dataset.metro===city;b.classList.toggle('active',yes);b.setAttribute('aria-pressed',String(yes));});
 $('metroHistoryStatus').textContent='월별 자료 목록 확인 중…';const seq=++request;
 try{index=index||await json('index.json');if(seq!==request)return;$('metroDistrict').innerHTML=index.cities[city].filter(d=>d.status==='ready').map(d=>`<option value="${esc(d.file)}">${esc(d.name)}</option>`).join('');await loadDistrict();}catch(e){if(seq===request)$('metroHistoryStatus').textContent=e.message;}}
 document.querySelectorAll('[data-metro]').forEach(b=>b.addEventListener('click',()=>open(b.dataset.metro)));
 document.querySelectorAll('[data-area]').forEach(b=>b.addEventListener('click',()=>{++request;document.body.classList.remove('metro-mode');$('metroHistory').hidden=true;document.querySelectorAll('[data-metro]').forEach(x=>{x.classList.remove('active');x.setAttribute('aria-pressed','false');});}));
 $('metroDistrict').addEventListener('change',loadDistrict);['metroType','metroFrom','metroTo'].forEach(id=>$(id).addEventListener('change',render));$('metroContractMonth').addEventListener('change',renderContracts);$('metroContractSearch').addEventListener('input',renderContracts);
 $('metroDownload').addEventListener('click',()=>{if(!series)return;const type=$('metroType').value;const lines=['계약월,가격또는보증금_만원,월임대료_만원,원본행수,상태'];for(const m of Object.keys(series.months)){if(m<$('metroFrom').value.replace('-','')||m>$('metroTo').value.replace('-',''))continue;const {record:r,value:v}=metrics(m,type);lines.push([m,v?.median_manwon??'',v?.monthly_rent_median_manwon??'',v?.rows??'',r?.status??'missing'].join(','));}const url=URL.createObjectURL(new Blob(['\ufeff'+lines.join('\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`${city}-${series.code}-${type}-monthly.csv`;a.click();URL.revokeObjectURL(url);});
})();
