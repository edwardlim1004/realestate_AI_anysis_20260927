/* Research-only extensions: levels, historical trend deviations, and asset comparisons.
 * Inputs: BOK ECOS raw.csv; OECD risk_raw.csv; independent BOK research asset CSV;
 * optional Ministry of Land Seoul district mean transactions in data.js.
 * Never writes/changes national composite, approvals or risk-data.js.
 */
'use strict';
const ASSET_CSV='../risk-data/liquidity/asset_transmission.csv';
const OECD_CSV='../risk-data/risk_raw.csv';
const EXTRA_COLORS={real:'#079865',m2:'#2469df',marshall:'#743ad3',house:'#2966de',seoul:'#d36d20',stock:'#079865',bond:'#c76b31',liquid:'#c43e52'};
const expanded={levels:[],charts:[],assets:null,yearRange:'all'};
function safeNumeric(s){const v=Number(s);return Number.isFinite(v)?v:null;}
function numericMap(rows,series){return new Map(rows.filter(r=>r.Series===series && Number(r.Value)>0).map(r=>[r.Period,Number(r.Value)]));}
function quarterMonths(q){
  const y=q.slice(0,4),n=Number(q.slice(-1));
  return [1,2,3].map(m=>y+String(3*(n-1)+m).padStart(2,'0'));
}
function sumOrNull(xs){return xs.every(x=>Number.isFinite(x))?xs.reduce((a,b)=>a+b,0):null;}
function quarterlyMean(map,q){
  const values=quarterMonths(q).map(m=>map.get(m));
  return values.every(v=>Number.isFinite(v))?values.reduce((a,b)=>a+b,0)/3:null;
}
function fitExpectedLog(series,index,window=40){
  // At t, estimate local log-linear trend from t-40..t-1 only.
  if(index<window)return null;
  const prev=series.slice(index-window,index);
  if(prev.some(v=>!Number.isFinite(v)||v<=0))return null;
  const meanX=(window-1)/2,avgY=prev.reduce((s,v)=>s+Math.log(v),0)/window;
  const cov=prev.reduce((s,v,i)=>s+(i-meanX)*(Math.log(v)-avgY),0);
  const ss=window*(window*window-1)/12;
  return Math.exp(avgY+(cov/ss)*(window-meanX));
}
function percentileAt(history,current,minN=20){
  const valid=history.filter(Number.isFinite);
  if(!Number.isFinite(current)||valid.length<minN)return null;
  return 100*valid.filter(v=>v<=current).length/valid.length;
}
function calculateAbsoluteLevels(rows){
  const m2=numericMap(rows,'M2'),cpi=numericMap(rows,'CPI'),gdp=numericMap(rows,'NOMINAL_GDP');
  const qs=[...gdp.keys()].filter(q=>/^\d{4}-Q[1-4]$/.test(q)).sort();
  const levels=[];
  for(const q of qs){
    const monthAverageM2=quarterlyMean(m2,q),monthAverageCpi=quarterlyMean(cpi,q);
    const quarters=[0,-1,-2,-3].map(d=>gdp.get(quarterShift(q,d)));
    const fourQuarterNominalGDP=sumOrNull(quarters);
    if(!(monthAverageM2>0&&monthAverageCpi>0&&fourQuarterNominalGDP>0))continue;
    const realM2=monthAverageM2/(monthAverageCpi/100);
    levels.push({period:q,nominalM2:monthAverageM2/1000,realM2:realM2/1000,
      marshall:monthAverageM2/fourQuarterNominalGDP,cpi:monthAverageCpi,
      realGap:null,marshallGap:null,realRank:null,marshallRank:null,m2Rank:null});
  }
  const gapReal=[],gapMarshall=[],growth=[];
  for(let i=0;i<levels.length;i++){
    const record=levels[i];
    const referenceReal=fitExpectedLog(levels.map(v=>v.realM2),i);
    const referenceMarshall=fitExpectedLog(levels.map(v=>v.marshall),i);
    record.realGap=referenceReal?100*(record.realM2/referenceReal-1):null;
    record.marshallGap=referenceMarshall?100*(record.marshall/referenceMarshall-1):null;
    gapReal.push(record.realGap);gapMarshall.push(record.marshallGap);
    const old=i>=4&&levels[i-4].period===quarterShift(record.period,-4)?levels[i-4].nominalM2:null;
    const currentGrowth=old?100*Math.log(record.nominalM2/old):null;
    growth.push(currentGrowth);
    record.realRank=percentileAt(gapReal,record.realGap);
    record.marshallRank=percentileAt(gapMarshall,record.marshallGap);
    record.m2Rank=percentileAt(growth,currentGrowth);
  }
  return levels;
}
function quarterlyHpi(rows){
  const hpi=new Map();
  for(const r of rows){
    if(r.Provider==='OECD'&&r.Indicator==='REAL_HPI'&&r.Country==='KOR'&&r.Frequency==='Q'){
      const n=Number(r.Value);
      if(n>0&&/^\d{4}-Q[1-4]$/.test(r.Period))hpi.set(r.Period,n);
    }
  }
  const yoy=new Map();
  for(const [q,value] of hpi){
    const lag=hpi.get(quarterShift(q,-4));
    if(lag>0)yoy.set(q,100*(value/lag-1));
  }
  return yoy;
}
function quarterlyMarket(rows){
  const market={KOSPI:new Map(),KTB3Y:new Map()};
  for(const r of rows){
    if(!market[r.Series]||!/^\d{4}-Q[1-4]$/.test(r.Quarter))continue;
    const spec=r.Series==='KOSPI'?['802Y001','0001000']:['817Y002','010200000'];
    const n=Number(r.Value);
    if(r.StatisticCode!==spec[0]||r.ItemCode!==spec[1]||!Number.isFinite(n)||n<=0||Number(r.ObservationCount)<1||r.SourceURL!=='https://ecos.bok.or.kr/api/')continue;
    market[r.Series].set(r.Quarter,n);
  }
  return market;
}
function quarterSeoulPrices(dataset){
  if(!dataset||!Array.isArray(dataset.months)||!Array.isArray(dataset.regions))return new Map();
  // Uniform district weights: an illustrative descriptive series, NOT a repeat-sales index.
  const regions=dataset.regions.filter(r=>r.province==='seoul'&&Array.isArray(r.history)&&r.history.length===dataset.months.length);
  if(regions.length!==25)return new Map();
  const monthLevel=new Map();
  for(let i=0;i<dataset.months.length;i++){
    const month=dataset.months[i],v=regions.map(r=>Number(r.history[i]));
    if(/^\d{4}-\d{2}$/.test(month)&&v.every(x=>x>0))monthLevel.set(month,v.reduce((a,b)=>a+b,0)/25);
  }
  const qlevel=new Map();
  for(const date of dataset.months){
    if(!/^\d{4}-\d{2}$/.test(date))continue;
    const mo=Number(date.slice(5));
    const q=date.slice(0,4)+'-Q'+(Math.floor((mo-1)/3)+1);
    const months=quarterMonths(q).map(m=>m.slice(0,4)+'-'+m.slice(4));
    if(months.every(x=>monthLevel.has(x)))qlevel.set(q,months.reduce((s,m)=>s+monthLevel.get(m),0)/3);
  }
  const yoy=new Map();
  for(const [q,v] of qlevel){
    const prior=qlevel.get(quarterShift(q,-4));
    if(prior>0)yoy.set(q,100*(v/prior-1));
  }
  return yoy;
}
function renderLevelCards(levels){
  if(!levels.length)return;
  const r=levels.at(-1),money=v=>new Intl.NumberFormat('ko-KR',{maximumFractionDigits:0}).format(v);
  for(const name of ['periodNominalM2','periodRealM2','periodMarshallK'])setText(name,r.period);
  setText('nominalM2',money(r.nominalM2));
  setText('realM2',money(r.realM2));
  setText('marshallKLevel',r.marshall.toFixed(2)+'배');
  function gap(id,rankId,value,rank){
    setText(id,Number.isFinite(value)?pct(value,'%'):'— (10년 미충족)');
    setText(rankId,Number.isFinite(rank)?'갭 역사 백분위 '+rank.toFixed(0)+'%':'갭 역사 백분위 N/A');
  }
  gap('realM2Gap','realM2Rank',r.realGap,r.realRank);
  gap('marshallKGap','marshallKRank',r.marshallGap,r.marshallRank);
  setText('m2GrowthRank',Number.isFinite(r.m2Rank)?r.m2Rank.toFixed(0)+' 백분위':'N/A');
}
function createDualSeriesChart(canvasId,records,defs,axes){
  const ink=cssValue('--ink'),grid=cssValue('--border');
  return new Chart(el(canvasId),{
    type:'line',plugins:[EVENT_BANDS],data:{labels:records.map(d=>d.period),datasets:defs.map(d=>({
      label:d.label,data:records.map(x=>x[d.key]),yAxisID:d.axis||'y',borderColor:d.color,backgroundColor:'transparent',
      borderWidth:2,pointRadius:0,pointHoverRadius:3,spanGaps:false,tension:.13,borderDash:d.dash||[]
    }))},
    options:{responsive:true,maintainAspectRatio:false,animation:false,
      interaction:{mode:'index',intersect:false},
      scales:{
        x:{grid:{display:false},ticks:{color:ink,maxRotation:0,maxTicksLimit:9,callback:function(v){
          const q=this.getLabelForValue(v);return q.endsWith('Q4')?q.slice(0,4):'';
        }}},
        y:{type:'linear',position:'left',grid:{color:grid},ticks:{color:ink},title:{display:true,text:axes.left,color:ink,font:{size:10}}},
        ...(axes.right?{y1:{type:'linear',position:'right',grid:{drawOnChartArea:false},
          ticks:{color:ink},title:{display:true,text:axes.right,color:ink,font:{size:10}}}}:{})
      },plugins:{legend:{display:true,position:'bottom',labels:{color:ink,font:{size:10},boxWidth:18}},
        tooltip:{callbacks:{label:item=>item.dataset.label+': '+(item.parsed.y==null?'N/A':item.parsed.y.toFixed(2))}}
      }}
    }
  });
}
function assetChart(canvas,liquidity,other,label,color,unit,sourceId){
  const observations=trimHistory(app.series,app.range);
  const joined=observations.map(p=>({period:p.period,liquidity:p.average,market:other.get(p.period)??null}));
  if(!joined.some(p=>Number.isFinite(p.market))){
    setText(sourceId,'공식 시계열 수집·검증 전이므로 수치를 표시하지 않습니다. 가상값을 대입하지 않습니다.');
    el(canvas).hidden=true;
    return null;
  }
  el(canvas).hidden=false;
  return createDualSeriesChart(canvas,joined,[
    {label:'초과통화 4Q 평균 (%p)',key:'liquidity',color:EXTRA_COLORS.liquid},
    {label:label,key:'market',color:color,axis:'y1'}
  ],{left:'유동성 · 로그 %p',right:unit});
}
async function readCsvOptional(url){
  try{const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw Error(response.status);return parseCsv(await response.text());}
  catch(err){console.warn('Optional official source unavailable',url,err.message);return null;}
}
function drawExpanded(){
  for(const c of expanded.charts)c.destroy();
  expanded.charts=[];
  const levels=trimHistory(expanded.levels,app.range);
  if(!levels.length)return;
  const draw=(id,rows,defs,axes)=>{
    const chart=createDualSeriesChart(id,rows,defs,axes);
    expanded.charts.push(chart);return chart;
  };
  draw('moneyLevelChart',levels,[{key:'nominalM2',label:'명목 M2 (조원)',color:EXTRA_COLORS.m2},
    {key:'realM2',label:'실질 M2 (조원, 2020년 가격)',color:EXTRA_COLORS.real}],{left:'M2 조원'});
  draw('liquidityGapChart',levels,[{key:'realGap',label:'실질 M2 10년 추세갭 (%)',color:EXTRA_COLORS.real},
    {key:'marshallGap',label:'M2/GDP 10년 추세갭 (%)',color:EXTRA_COLORS.marshall}],{left:'추세 대비 괴리 (%)'});
  if(!expanded.assets)return;
  let series=app.series.map(r=>({period:r.period,average:r.average}));
  const hpi=expanded.assets.hpi;
  let ch=assetChart('housingChart',series,hpi,'전국 실질 HPI 전년상승률',EXTRA_COLORS.house,'전국 실질 HPI YoY (%)','housingSource');
  if(ch){
    // Seoul 25-district simple means have composition bias; never replace nationwide OECD index.
    const seoul=expanded.assets.seoul;
    if([...seoul.keys()].length){
      ch.data.datasets.push({
        label:'서울 25구 평균 거래가격 YoY (탐색·구성효과)',data:ch.data.labels.map(q=>seoul.get(q)??null),
        yAxisID:'y1',borderColor:EXTRA_COLORS.seoul,backgroundColor:'transparent',
        borderWidth:1.6,pointRadius:0,spanGaps:false,tension:.13,borderDash:[4,3]
      });
      ch.update('none');
      setText('housingSource','OECD 전국 실질 HPI(%) + 국토부 실거래 기반 서울 25구 단순평균 YoY(%) · 서울은 물가미조정·거래구성효과 큼, 투자 신호로 사용 금지.');
    }
    expanded.charts.push(ch);
  }
  const market=expanded.assets.market;
  ch=assetChart('kospiChart',series,market.KOSPI,'KOSPI (분기말 지수)',EXTRA_COLORS.stock,'KOSPI 지수','kospiSource');
  if(ch){expanded.charts.push(ch);setText('kospiSource','한국은행 ECOS 802Y001 / 0001000 · 해당 분기 마지막 거래일 종가. 유동성의 인과효과로 해석하지 마십시오.');}
  const realYield=new Map();
  const levelMap=new Map(expanded.levels.map(p=>[p.period,p]));
  for(const [q,nominalRate] of market.KTB3Y){
    const c=levelMap.get(q),old=levelMap.get(quarterShift(q,-4));
    if(c&&old&&old.cpi>0)realYield.set(q,nominalRate-100*(c.cpi/old.cpi-1));
  }
  ch=assetChart('bondChart',series,realYield,'사후 실질금리 (3년, %)',EXTRA_COLORS.bond,'금리(%)','bondSource');
  if(ch){expanded.charts.push(ch);setText('bondSource','한국은행 ECOS 817Y002 / 010200000 분기 일별평균 금리 − CPI 전년동기 상승률(분기 월평균). 채권가격 및 채권 총수익률과 다릅니다.');}
}
async function bootExpanded(rows){
  expanded.levels=calculateAbsoluteLevels(rows);
  if(expanded.levels.length<50)throw Error('Official M2/CPI/GDP series too short for full liquidity history');
  renderLevelCards(expanded.levels);
  // Government/public national real housing price data are already published in the repository.
  const [oecdRows,assetRows]=await Promise.all([readCsvOptional(OECD_CSV),readCsvOptional(ASSET_CSV)]);
  const d=typeof ENHANCED_DATA!=='undefined'?ENHANCED_DATA:null;
  expanded.assets={hpi:oecdRows?quarterlyHpi(oecdRows):new Map(),
    market:assetRows?quarterlyMarket(assetRows):{KOSPI:new Map(),KTB3Y:new Map()},
    seoul:quarterSeoulPrices(d)};
  drawExpanded();
}
if(typeof module!=='undefined'&&module.exports){
  module.exports={quarterMonths,quarterlyMean,fitExpectedLog,percentileAt,calculateAbsoluteLevels,quarterlyHpi,
    quarterlyMarket,quarterSeoulPrices};
}
