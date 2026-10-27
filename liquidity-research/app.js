/* ECOS-only research visualization. No writes to the official risk composite. */
'use strict';
const REPO_ROOT = '../';
const CSV_URL = REPO_ROOT + 'risk-data/liquidity/raw.csv';
const COMPARE_URL = REPO_ROOT + 'risk-data/liquidity/excess_liquidity_comparison.json';
const VALIDATION_URL = REPO_ROOT + 'risk-data/liquidity/validation.json';
const COLORS = {m2:'#2469df',gdp:'#079865',excess:'#2469df',moving:'#743ad3'};
const CRISES = [
  {start:'2008-Q3',end:'2009-Q4',label:'2008 금융위기'},
  {start:'2020-Q1',end:'2020-Q4',label:'2020 코로나19'},
  {start:'2022-Q1',end:'2023-Q4',label:'2022 금리 인상기'}
];
const app = {series:[],range:'all',charts:[],compare:null,validation:null};

function csvCells(line){
  const cells = []; let value = '',quoted = false;
  for(let i=0;i<line.length;i++){
    const c=line[i];
    if(c==='"'){if(quoted && line[i+1]==='"'){value+='"';i++;}else quoted=!quoted;}
    else if(c===','&&!quoted){cells.push(value);value='';}
    else value+=c;
  }
  cells.push(value);return cells;
}
function parseCsv(csv){
  const lines=csv.replace(/^\uFEFF/,'').replace(/\r/g,'').split('\n').filter(l=>l.trim());
  if(!lines.length) throw new Error('Empty ECOS CSV');
  const keys=csvCells(lines[0]);
  for(const required of ['Series','Period','Value']) if(!keys.includes(required))throw new Error('Missing ECOS field: '+required);
  return lines.slice(1).map(line=>{
    const fields=csvCells(line),row={};
    keys.forEach((k,i)=>row[k]=fields[i]??'');
    return row;
  });
}
function quarterShift(quarter,d){
  const m=/^(\d{4})-Q([1-4])$/.exec(quarter);
  if(!m) throw new Error('Invalid quarter '+quarter);
  const n=Number(m[1])*4+Number(m[2])-1+d;
  return Math.floor(n/4)+'-Q'+((n%4)+1);
}
function quarterlyFromEcos(rows){
  const money=new Map(), nominal=new Map();
  for(const r of rows){
    const v=Number(r.Value);
    if(!Number.isFinite(v)||v<=0)continue;
    if(r.Series==='M2'&&/^\d{6}$/.test(r.Period)){
      const mm=Number(r.Period.slice(4)),yy=r.Period.slice(0,4);
      if(mm<1||mm>12)continue;
      money.set(r.Period,v);
    }
    if(r.Series==='NOMINAL_GDP'&&/^\d{4}-Q[1-4]$/.test(r.Period))nominal.set(r.Period,v);
  }
  const m2q=new Map();
  for(const q of nominal.keys()){
    const y=q.slice(0,4),quarter=Number(q.slice(-1)),months=[1,2,3].map(j=>y+String((quarter-1)*3+j).padStart(2,'0'));
    if(months.every(m=>money.has(m)))m2q.set(q,months.reduce((sum,m)=>sum+money.get(m),0)/3);
  }
  const all=[];
  for(const q of [...nominal.keys()].sort()){
    const previous=quarterShift(q,-4);
    if(!m2q.has(q)||!m2q.has(previous)||!nominal.has(previous))continue;
    const m2=100*Math.log(m2q.get(q)/m2q.get(previous));
    const gdp=100*Math.log(nominal.get(q)/nominal.get(previous));
    all.push({period:q,m2,gdp,excess:m2-gdp,average:null});
  }
  const map=new Map(all.map(d=>[d.period,d]));
  for(const point of all){
    const four=Array.from({length:4},(_,i)=>map.get(quarterShift(point.period,-i)));
    if(four.every(Boolean))point.average=four.reduce((s,r)=>s+r.excess,0)/4;
  }
  return all;
}
function trimHistory(series,years){return years==='all'?series:series.slice(-Number(years)*4);}
function pct(value,unit='%'){return (value>=0?'+':'')+value.toFixed(2)+unit;}
function cssValue(name){return getComputedStyle(document.documentElement).getPropertyValue(name).trim();}
function el(id){return document.getElementById(id);}
function setText(id,value){el(id).textContent=value;}
const EVENT_BANDS={
  id:'excessCrisisBands',
  beforeDatasetsDraw(chart){
    const {ctx,chartArea,scales}=chart;
    if(!chartArea||!scales?.x)return;
    const labels=chart.data.labels;
    ctx.save();
    for(const period of CRISES){
      const s=labels.findIndex(q=>q>=period.start),e=labels.findLastIndex(q=>q<=period.end);
      if(s<0||e<s)continue;
      const x1=Math.max(chartArea.left,scales.x.getPixelForValue(s)-4);
      const x2=Math.min(chartArea.right,scales.x.getPixelForValue(e)+4);
      if(x2<=x1)continue;
      ctx.fillStyle='rgba(126,142,167,.11)';
      ctx.fillRect(x1,chartArea.top,x2-x1,chartArea.bottom-chartArea.top);
      if(x2-x1>55){ctx.fillStyle=cssValue('--muted');ctx.font='10px system-ui';ctx.fillText(period.label,x1+3,chartArea.top+11);}
    }
    ctx.restore();
  }
};
function dataset(label,data,color,extras={}){
  return {label,data,borderColor:color,backgroundColor:'transparent',borderWidth:2.2,pointRadius:0,pointHoverRadius:4,tension:.18,spanGaps:false,...extras};
}
function createChart(canvasId,series,seriesDefinition,showBands){
  const labels=series.map(r=>r.period);
  const styleText=cssValue('--ink'),gray=cssValue('--border');
  return new Chart(el(canvasId),{
    type:'line',plugins:showBands?[EVENT_BANDS]:[],
    data:{labels,datasets:seriesDefinition.map(d=>dataset(d.label,series.map(r=>r[d.key]),d.color,d.extra||{}))},
    options:{
      responsive:true,maintainAspectRatio:false,animation:false,
      interaction:{mode:'index',intersect:false},
      scales:{
        x:{grid:{display:false},ticks:{color:styleText,maxTicksLimit:11,maxRotation:0,autoSkip:true,callback:function(v){const q=this.getLabelForValue(v);return q.slice(0,4)+(q.endsWith('Q4')?'':'');}}},
        y:{grid:{color:gray},ticks:{color:styleText,callback:v=>v+' %p'},title:{display:true,text:'전년동기 대비 로그증가율 · %p',color:styleText,font:{size:10}}}
      },
      plugins:{
        legend:{display:false},
        tooltip:{backgroundColor:'#243149',callbacks:{title:items=>items[0]?.label||'',label:item=>item.dataset.label+': '+(item.parsed.y==null?'N/A':pct(item.parsed.y,'%p'))}}
      }
    }
  });
}
function draw(){
  if(typeof Chart==='undefined'){el('loadError').hidden=false;el('loadError').textContent='그래프 라이브러리를 불러오지 못했습니다. 데이터 출처 링크를 이용해 원자료를 확인하십시오.';return;}
  for(const c of app.charts)c.destroy();
  app.charts=[];
  const data=trimHistory(app.series,app.range);
  app.charts.push(createChart('excessChart',data,[
    {label:'초과통화 증가율',key:'excess',color:COLORS.excess},
    {label:'4분기 이동평균',key:'average',color:COLORS.moving,extra:{borderDash:[6,3],borderWidth:2.5}}
  ],true));
  app.charts.push(createChart('growthChart',data,[
    {label:'M2 로그증가율',key:'m2',color:COLORS.m2},
    {label:'명목 GDP 로그증가율',key:'gdp',color:COLORS.gdp}
  ],true));
  app.charts.push(createChart('combinedChart',data,[
    {label:'초과유동성 4Q 평균',key:'average',color:COLORS.moving},
    {label:'명목 GDP 로그증가율',key:'gdp',color:COLORS.gdp,extra:{borderDash:[5,3]}}
  ],true));
  if (typeof drawExpanded==='function') drawExpanded();
}
function updateCards(){
  const r=app.series.at(-1);
  if(!r)return;
  for(const id of ['periodM2','periodGDP','periodExcess','periodAverage'])setText(id,r.period);
  setText('m2Growth',pct(r.m2));
  setText('gdpGrowth',pct(r.gdp));
  setText('excessGrowth',pct(r.excess,'%p'));
  setText('excessAverage',Number.isFinite(r.average)?pct(r.average,'%p'):'N/A');
  setText('meta','공식자료: 한국은행 ECOS · 계산가능 기간 '+app.series[0].period+' ~ '+r.period+' · '+app.series.length+'개 분기 · 당해 수정본 사용');
}
function renderBacktests(result){
  const tbody=el('backtestRows');
  if(!result||!result.results){tbody.innerHTML='<tr><td colspan="3">공식 비교 보고서 이용 불가 · 수치 미표시</td></tr>';return;}
  const names={currentLiquidityComposite:'기존 유동성 종합',existingMarshallK:'기존 Marshall K',excessMoneyGrowth:'초과통화 증가율',excessMoneyGrowth4QuarterMean:'초과통화 4Q 평균',excessMoneyGrowthExpandingPercentile:'초과통화 백분위'};
  tbody.replaceChildren();
  for(const [key,label] of Object.entries(names)){
    const r=result.results[key];if(!r)continue;
    const tr=document.createElement('tr');
    const name=document.createElement('td');name.textContent=label;tr.append(name);
    for(const k of ['fourQuarters','eightQuarters']){
      const td=document.createElement('td'),v=Number(r[k]?.mseSkill);
      if(!Number.isFinite(v))td.textContent='N/A';
      else{td.textContent=pct(v*100);td.className=v>=0?'good':'bad';}
      tr.append(td);
    }
    tbody.append(tr);
  }
}
function renderValidation(v){
  const gates=Object.values(v?.gates||{}),pass=gates.filter(g=>g.status==='PASS').length;
  setText('gateCount',v?.passedGateCount??pass);
  const line=el('gateStrip');line.replaceChildren();
  for(const g of gates){const piece=document.createElement('span');piece.className=g.status==='PASS'?'pass':g.status==='FAIL'?'fail':'';piece.title=g.status;line.append(piece);}
  if(!gates.length){setText('gateNote','검증 JSON을 읽지 못했습니다. 지표는 연구전용·미반영입니다.');return;}
  setText('gateNote','예측 백테스트 '+(v.gates.predictiveBacktest?.status||'N/A')+' · 수정빈티지 '+(v.gates.revisionStability?.status||'N/A')+' · 전문가 검토 '+(v.gates.humanReview?.status||'N/A')+' (이는 기존 유동성 모듈 검증입니다).');
}
async function loadOptional(url){try{const r=await fetch(url,{cache:'no-store'});if(!r.ok)throw Error(r.status);return await r.json();}catch(e){return null;}}
async function boot(){
  document.querySelectorAll('.range-picker button').forEach(btn=>btn.addEventListener('click',()=>{
    app.range=btn.dataset.range;
    document.querySelectorAll('.range-picker button').forEach(b=>b.classList.toggle('selected',b===btn));
    if(app.series.length)draw();
  }));
  el('themeToggle').addEventListener('click',()=>{
    const next=document.documentElement.dataset.theme==='light'?'dark':'light';
    document.documentElement.dataset.theme=next;
    el('themeToggle').textContent=next==='light'?'☾ 다크':'☀ 라이트';
    if(app.charts.length)draw();
  });
  try{
    const resp=await fetch(CSV_URL,{cache:'no-store'});
    if(!resp.ok)throw new Error('ECOS CSV HTTP '+resp.status);
    const actualRows=parseCsv(await resp.text());
    app.series=quarterlyFromEcos(actualRows);
    if(app.series.length<20)throw new Error('Insufficient real historical series');
    updateCards();draw();
    if(typeof bootExpanded==='function')await bootExpanded(actualRows);
  }catch(error){el('loadError').hidden=false;el('loadError').textContent='공식 ECOS 저장자료를 불러오거나 계산할 수 없습니다: '+error.message+' · 가상값을 대신 표시하지 않습니다.';setText('meta','데이터 로딩 실패 · 계산값 미표시');}
  const [comparison,validation]=await Promise.all([loadOptional(COMPARE_URL),loadOptional(VALIDATION_URL)]);
  renderBacktests(comparison);renderValidation(validation);
}
if(typeof module!=='undefined'&&module.exports){module.exports={parseCsv,quarterShift,quarterlyFromEcos,trimHistory,pct};}
if(typeof document!=='undefined')document.addEventListener('DOMContentLoaded',boot);
