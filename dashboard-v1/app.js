
(function(){
"use strict";
const $=id=>document.getElementById(id);
const SOURCE=typeof ENHANCED_DATA!=="undefined"?ENHANCED_DATA:null;
const RISK=typeof RISK_MONITOR_DATA!=="undefined"?RISK_MONITOR_DATA:null;
const GEO=typeof REGION_BOUNDARIES!=="undefined"?REGION_BOUNDARIES:null;
const NAMES={seoul:"서울",gyeonggi:"경기",daejeon:"대전"};
const COUNTS={seoul:25,gyeonggi:31,daejeon:5};
const CODES={"종로구":"11110","중구":"11140","용산구":"11170","성동구":"11200","광진구":"11215","동대문구":"11230","중랑구":"11260","성북구":"11290","강북구":"11305","도봉구":"11320","노원구":"11350","은평구":"11380","서대문구":"11410","마포구":"11440","양천구":"11470","강서구":"11500","구로구":"11530","금천구":"11545","영등포구":"11560","동작구":"11590","관악구":"11620","서초구":"11650","강남구":"11680","송파구":"11710","강동구":"11740"};
const state={area:"seoul",district:"송파구",metric:"composite",riskTab:"history",query:"",aptIndex:-1,tradeQuery:"",pricePeriod:"complete",tradeType:"sale"};
const cache={valuation:{},trades:{},tradeIndex:null};
let historyChart=null,macroChart=null,valueChart=null,asyncSeq=0;
function txt(id,value){const e=$(id);if(e)e.textContent=value==null?"N/A":String(value);}
function esc(v){return String(v==null?"":v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","\"":"&quot;"}[c]));}
function shortName(s){return String(s||"").replace(/\s+\(.*/,"");}
function rowFor(name){return (SOURCE?.regions||[]).find(r=>r.province===state.area&&shortName(r.name)===name);}
function areaRows(){return (SOURCE?.regions||[]).filter(r=>r.province===state.area);}
function number(v){const n=Number(v);return Number.isFinite(n)?n:null;}
function moneyMan(v){const n=number(String(v||"").replace(/,/g,""));return n!=null&&n>0?(n/10000).toLocaleString("ko-KR",{maximumFractionDigits:2})+"억":"N/A";}
function fmtPct(v,d=1){const n=number(v);return n==null?"N/A":(n>0?"+":"")+n.toFixed(d)+"%";}
function scoreColor(v){if(v==null)return "#cbd5e1";if(v<20)return "#dc5b56";if(v<40)return "#f3a47e";if(v<60)return "#f8ce8f";if(v<80)return "#9ec8f5";return "#2784e8";}
function riskColor(v){if(v==null)return "#cbd5e1";if(v<20)return "#2784e8";if(v<40)return "#9ec8f5";if(v<60)return "#f8ce8f";if(v<80)return "#f3a47e";return "#dc5b56";}
function nOrDash(n){return Number.isFinite(Number(n))?Number(n).toFixed(1):"N/A";}
function setArea(area){
 if(!NAMES[area])return;
 state.area=area;state.district="";state.aptIndex=-1;state.query="";state.tradeQuery="";
 txt("aptName","단지를 검색하거나 지역을 선택하세요");
 $("aptSearch").value="";$("tradeSearch").value="";renderAll();
}
function setDistrict(district){state.district=district||"";state.query="";state.aptIndex=-1;$("aptSearch").value="";renderAll();}
function syncControls(){
 document.querySelectorAll("[data-area]").forEach(el=>{const yes=el.dataset.area===state.area;el.classList.toggle("active",yes);el.setAttribute("aria-pressed",yes?"true":"false")});
 const names=(GEO?.regions?.[state.area]||[]).map(g=>g.name).sort((a,b)=>a.localeCompare(b,"ko"));
 $("districtSelect").innerHTML='<option value="">전체 지역</option>'+names.map(n=>'<option value="'+esc(n)+'">'+esc(n)+'</option>').join("");
 $("districtSelect").value=state.district||"";
 txt("globalScopeNote",NAMES[state.area]+" "+COUNTS[state.area]+"개 시군구 · "+(state.district||"전체"));
 txt("regionalTitle","지역 상대매력도 ("+NAMES[state.area]+" "+COUNTS[state.area]+"개 시군구)");
 txt("valueAreaTag",NAMES[state.area]+" 기준");
 txt("regionalTag",state.area==="daejeon"?"지역점수 검증 대기":"연구용 · 상대순위");
 txt("mapTitle","지역별 위험·매력도 지도 ("+NAMES[state.area]+")");
 txt("mapRegionTag","현재 선택: "+NAMES[state.area]);
 txt("transactionRegion",NAMES[state.area]+(state.district?" · "+state.district:""));
 $("mapMetric").value=state.metric;
 $("periodSelect").value=state.pricePeriod;
 $("typeSelect").value=state.tradeType;
}
function renderRanking(){
 const rows=areaRows().slice().sort((a,b)=>(number(b.scores?.composite)||0)-(number(a.scores?.composite)||0));
 const filtered=state.district?rows.filter(r=>shortName(r.name)===state.district):rows;
 if(state.area==="daejeon"){
  $("regionRows").innerHTML='<tr><td colspan="7">대전 5개 구: 행정경계 표시 가능 / 지역별 상대점수는 정규화·검증 전이므로 N/A</td></tr>';
  txt("regionSummary","대전 매매·전월세 원천 수집과 지역 점수 산출은 별도 검증이 필요합니다.");
  return;
 }
 $("regionRows").innerHTML=filtered.map((r,i)=>'<tr tabindex="0" data-district="'+esc(shortName(r.name))+'" class="'+(shortName(r.name)===state.district?"selected":"")+'"><td>'+(rows.indexOf(r)+1)+'</td><td>'+esc(r.name)+'</td><td><b style="color:#1261c4">'+nOrDash(r.scores?.composite)+'</b></td><td>'+fmtPct(r.gapPct)+'</td><td>'+esc(r.trades||"N/A")+'</td><td>'+fmtPct(r.rentalYieldPct,2)+'</td><td><span class="pill '+(r.signal==="buy"?"":"warn")+'">'+(r.signal==="buy"?"상대우위":r.signal==="warning"?"중립":"재검증")+'</span></td></tr>').join("");
 $("regionRows").querySelectorAll("tr[data-district]").forEach(tr=>{
  const fn=()=>setDistrict(tr.dataset.district);
  tr.addEventListener("click",fn);
  tr.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();fn();}});
 });
 txt("regionSummary",rows.length+"개 지역 상대순위 · 전용80~90㎡ 단순평균 · 모멘텀·리스크는 검증 중 (상세 지표는 ver0.0)");
}
function mapMetricValue(r){
 if(!r||state.area==="daejeon")return null;
 const s=r.scores||{};
 switch(state.metric){
  case "composite":return number(s.composite);
  case "gap":return number(r.gapPct)==null?null:Math.max(0,Math.min(100,50+Number(r.gapPct)*1.5));
  case "trades":return number(s.liquidity);
  case "yield":return number(s.jeonse);
  case "risk":return number(s.risk)==null?null:100-number(s.risk);
  default:return null;
 }
}
function metricLabel(r){
 if(!r)return "해당 지역별 검증값 없음";
 if(state.metric==="composite")return "상대매력도 "+nOrDash(r.scores?.composite)+"/100 (연구용)";
 if(state.metric==="gap")return "장기 추세 대비 "+fmtPct(r.gapPct)+" (가격의 적정성 아님)";
 if(state.metric==="trades")return "거래활성 상대점수 "+nOrDash(r.scores?.liquidity)+"/100";
 if(state.metric==="yield")return "내재임대수익률 "+fmtPct(r.rentalYieldPct,2);
 if(state.metric==="risk")return "미검증 리스크 참고값 "+nOrDash(100-Number(r.scores?.risk))+"/100";
 return "지역별 검증자료 미확보 · 수치 미표시";
}
function renderMap(){
 const geo=GEO?.regions?.[state.area]||[];
 const canvas=$("regionMap");
 if(!geo.length){canvas.innerHTML='<text x="20" y="40">경계 데이터 없음</text>';return;}
 const coords=[];geo.forEach(g=>g.polygons.forEach(p=>p.forEach(point=>coords.push(point))));
 let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
 coords.forEach(p=>{minX=Math.min(minX,p[0]);maxX=Math.max(maxX,p[0]);minY=Math.min(minY,p[1]);maxY=Math.max(maxY,p[1]);});
 const sx=568/Math.max(.01,(maxX-minX)*Math.cos(((minY+maxY)/2)*Math.PI/180)),sy=288/Math.max(.01,maxY-minY);
 const scale=Math.min(sx,sy);
 const cx=(maxX+minX)/2,cy=(maxY+minY)/2;
 const x=p=>(300+(p[0]-cx)*Math.cos(cy*Math.PI/180)*scale).toFixed(2);
 const y=p=>(160-(p[1]-cy)*scale).toFixed(2);
 let markup="";
 geo.forEach(g=>{
  const r=rowFor(g.name),v=mapMetricValue(r);
  const c=state.metric==="gap"||state.metric==="risk"?riskColor(v):scoreColor(v);
  const paths=g.polygons.map(poly=>poly.map((p,i)=>(i?"L":"M")+x(p)+","+y(p)).join("")+"Z").join(" ");
  markup+='<path role="button" tabindex="0" aria-label="'+esc(g.name)+' '+esc(metricLabel(r))+'" data-district="'+esc(g.name)+'" class="'+(state.district===g.name?"active":"")+'" fill="'+c+'" d="'+paths+'"><title>'+esc(g.name)+': '+esc(metricLabel(r))+'</title></path>';
 });
 if(state.district){
  const selected=geo.find(g=>g.name===state.district);
  if(selected){const points=selected.polygons.flat();if(points.length){const m=points.reduce((acc,p)=>[acc[0]+p[0],acc[1]+p[1]],[0,0]).map(z=>z/points.length);markup+='<text class="maplabel" x="'+x(m)+'" y="'+y(m)+'" text-anchor="middle">'+esc(state.district)+'</text>';}}
 }
 canvas.innerHTML=markup;
 canvas.querySelectorAll("path").forEach(el=>{
  const choose=()=>setDistrict(el.getAttribute("data-district"));
  el.addEventListener("click",choose);
  el.addEventListener("keydown",e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose();}});
 });
 let details=state.district?state.district+" · "+metricLabel(rowFor(state.district)):"지도에서 시군구를 선택하세요";
 txt("mapInspect",details);
 const legend=$("mapLegend");
 const unavailable=["credit","supply"].includes(state.metric)||state.area==="daejeon";
 legend.innerHTML=unavailable?'<span>◻ 지역별 검증자료 미확보(N/A) · 경계만 표시</span>':
 ["매우 낮음 (0~20)","낮음 (20~40)","보통 (40~60)","높음 (60~80)","매우 높음 (80~100)"].map((label,i)=>{
  const c=(state.metric==="gap"||state.metric==="risk")?riskColor(i*20+10):scoreColor(i*20+10);
  return '<span><i style="background:'+c+'"></i>'+label+'</span>';
 }).join("");
 txt("mapSource","행정경계: 국가공간정보포털 기반 2023년 자료(경계 갱신 확인 필요). "+
 (state.metric==="risk"?"리스크 항목은 아직 독립 검증되지 않은 연구점수의 역순서입니다.":state.metric==="gap"?"가격 추세괴리 분포이며 적정가나 위기확률이 아닙니다.":state.area==="daejeon"?"대전은 검증된 지역별 지표 미확보로 지도만 표시합니다.":"색상은 지역 간 상대지표이며 절대적인 매수·매도 판정이 아닙니다."));
}
function setRiskTab(name){
 state.riskTab=name;
 document.querySelectorAll("#riskTabs [data-tab]").forEach(b=>b.classList.toggle("active",b.dataset.tab===name));
 $("historyPanel").hidden=name!=="history";$("regionalRiskPanel").hidden=name!=="regional";$("forecastPanel").hidden=name!=="forecast";
 if(name==="history")drawRiskHistory();
}
function renderLocalRisk(){
 const r=state.district?rowFor(state.district):null;
 txt("regionalRiskTitle",(state.district||NAMES[state.area])+" 지역 위험 분석");
 if(!r){$("regionalRiskBody").textContent="해당 지역의 검증된 하방위험 추정치가 없습니다. OECD·BIS 시계열은 전국 공통값입니다.";return;}
 $("regionalRiskBody").innerHTML='<strong>리스크 상대점수 '+nOrDash(r.scores?.risk)+'/100 · 지역 실험모형</strong><p>이 점수는 검증되지 않은 보조항목이며 가격하락 확률이나 위기확률로 사용할 수 없습니다.</p><p>현재월 잠정 거래와 과거 완결 거래를 직접 비교하지 않도록 분리했습니다.</p>';
}
function crisisPlugin(labels,events){
 return {id:"crisisBandsV1",beforeDatasetsDraw(chart){
  const ctx=chart.ctx,area=chart.chartArea,scale=chart.scales.x;
  if(!area||!scale)return;
  ctx.save();
  (events||[]).forEach(e=>{const first=labels.findIndex(p=>p>=e.start);let last=-1;labels.forEach((p,i)=>{if(p<=e.end)last=i;});if(first<0||last<first)return;
   const left=scale.getPixelForValue(first),right=scale.getPixelForValue(last);
   ctx.fillStyle="rgba(233,113,73,.11)";ctx.fillRect(left,area.top,Math.max(5,right-left+5),area.bottom-area.top);
   ctx.fillStyle="#a34f31";ctx.font="10px Arial";ctx.fillText(e.label,left+3,area.top+13);
  });ctx.restore();
 }};
}
function drawRiskHistory(){
 const h=RISK?.countries?.KOR?.history||[];if(!h.length)return;
 if(typeof Chart==="undefined"){txt("historyPanel","차트 라이브러리 미로드. ver0.0에서 원자료를 확인하세요.");return;}
 const labels=h.map(v=>v.period),metric=$("historyMetric").value;
 const cols={score:"#ee5955",valuation:"#2d7be6",credit:"#dfa122",momentum:"#139985"};
 const series=metric==="all"?["score","valuation","credit"]: [metric];
 if(historyChart)historyChart.destroy();
 historyChart=new Chart($("historyChart"),{type:"line",
 data:{labels,datasets:series.map(k=>({label:({score:"종합 역사백분위",valuation:"가격평가",credit:"신용",momentum:"모멘텀"})[k],data:h.map(p=>p[k]??null),borderColor:cols[k],backgroundColor:k==="score"?"#e4585424":"transparent",fill:k==="score",borderWidth:k==="score"?2.2:1.6,pointRadius:0,spanGaps:false,tension:.18,borderDash:k==="score"?[]:[4,4]}))},
 plugins:[crisisPlugin(labels,RISK.crisisEvents)],
 options:{maintainAspectRatio:false,responsive:true,interaction:{mode:"index",intersect:false},scales:{x:{ticks:{maxTicksLimit:9},grid:{display:false}},y:{min:0,max:100,title:{display:true,text:"과거 백분위(0~100)"}}},plugins:{legend:{position:"bottom"},tooltip:{callbacks:{afterBody:()=>["과거 상대백분위로, 미래 하락확률이 아닙니다."]}}}}});
}
function renderNational(){
 const c=RISK?.countries?.KOR?.composite;
 const current=RISK?.countries?.KOR?.history?.slice(-1)[0];
 txt("nationalScore",c?.score==null?"N/A":Number(c.score).toFixed(1));
 txt("nationalStatus",(c?.latestPeriod||"기준월 불명")+" · "+(c?.coverage||"")+" · 백분위이며 가격 하락확률이 아닙니다.");
 const keys=[["valuation","가격평가"],["credit","신용위험"],["momentum","모멘텀"]];
 $("nationalFactors").innerHTML=keys.map(([k,name])=>{const n=number(current?.[k]);return '<div class="indicator-row"><b>'+name+'</b><div class="bar"><span style="width:'+(n||0)+'%"></span></div><em>'+(n==null?"N/A":n.toFixed(1))+'</em></div>';}).join("");
}
function drawMacro(){
 const h=RISK?.countries?.KOR?.history||[],key=$("macroMetric").value;
 txt("macroPeriod",h.length?h[0].period+" ~ "+h[h.length-1].period:"원자료 없음");
 if(!h.length||typeof Chart==="undefined")return;
 if(macroChart)macroChart.destroy();
 macroChart=new Chart($("macroChart"),{type:"line",data:{labels:h.map(r=>r.period),datasets:[{label:{credit:"전국 신용 위험백분위",valuation:"전국 가격평가 백분위",momentum:"전국 실질주택가격 모멘텀 백분위"}[key],data:h.map(r=>r[key]??null),borderColor:"#0c71d6",backgroundColor:"#267bea25",fill:true,tension:.17,pointRadius:0,spanGaps:false}]},options:{maintainAspectRatio:false,scales:{x:{ticks:{maxTicksLimit:7}},y:{min:0,max:100}},plugins:{legend:{display:false}}}});
}
async function fetchJSON(path){const res=await fetch(path,{cache:"no-store"});if(!res.ok)throw new Error("HTTP "+res.status);return res.json();}
async function renderValuation(seq){
 const select=$("aptSelect"),name=state.district,code=CODES[name];
 select.innerHTML='<option>조회 준비 중…</option>';
 if(state.area!=="seoul"||!code){
  txt("aptName","이 지역의 5년 단지별 평가자료 검증 대기");
  txt("aptAddress",NAMES[state.area]+(name?" "+name:"")+" · 기존 독립 모형은 서울 25개 구를 우선 지원합니다.");
  txt("aptCoverage","지역별 자료를 임의로 대체하지 않습니다.");
  ["aptPrice","aptCount","aptJeonse"].forEach(k=>txt(k,"N/A"));
  txt("aptDataTag","N/A");
  select.innerHTML='<option value="">단지별 평가 미지원</option>';
  if(valueChart){valueChart.destroy();valueChart=null;}
  txt("valuationMessage","경기·대전은 공식 5년 단지별 평가모형 검증 이후 동일 인터페이스로 제공됩니다.");
  return;
 }
 try{
  if(!cache.valuation[code])cache.valuation[code]=await fetchJSON("long-term-value/data/"+code+".json");
  if(seq!==asyncSeq)return;
  const doc=cache.valuation[code],rows=(doc.complexes||[]).slice().sort((a,b)=>(b.sale_count_5y||0)-(a.sale_count_5y||0));
  const search=$("aptSearch").value.trim().toLowerCase();
  const matches=rows.filter(x=>!search||String(x.name+" "+x.dong).toLowerCase().includes(search));
  const options=matches.slice(0,120);
  if(!options.length){select.innerHTML='<option value="">검색 결과 없음</option>';txt("aptName","일치하는 단지가 없습니다.");return;}
  select.innerHTML=options.map((x,i)=>'<option value="'+i+'">'+esc(x.name+" · "+x.size+"㎡ · "+x.dong)+'</option>').join("");
  const apt=options[Math.max(0,Math.min(state.aptIndex,options.length-1))];state.aptIndex=Number(select.value)||0;
  showApartment(apt,doc);
  select.onchange=()=>{state.aptIndex=Number(select.value);showApartment(options[state.aptIndex],doc);};
 }catch(e){
  if(seq!==asyncSeq)return;
  txt("aptName","5년 단지 자료 조회 실패");txt("aptAddress",String(e));txt("aptDataTag","데이터 미연결");
  select.innerHTML='<option value="">읽기 실패</option>';
  txt("valuationMessage","독립 모형 파일을 확인하거나 ver0.0에서 현재 지역 실거래를 확인하세요.");
 }
}
function showApartment(apt,doc){
 if(!apt)return;
 txt("aptName",apt.name);
 txt("aptAddress",NAMES[state.area]+" "+state.district+" "+apt.dong+(apt.jibun?" "+apt.jibun:"")+" · 전용 "+apt.size+"㎡");
 txt("aptCoverage",(doc.window_start||"")+"~"+(doc.cutoff_month||"")+" · 자료 "+(apt.sale_count_5y||0)+"건");
 txt("aptDataTag","5년 관측중위가격 · 미래 예측 아님");
 txt("aptPrice",apt.last12_median!=null?moneyMan(apt.last12_median):"표본 부족");
 txt("aptCount",apt.sale_count_5y??"N/A");
 txt("aptJeonse",apt.jeonse_rate_pct!=null?Number(apt.jeonse_rate_pct).toFixed(1)+"%":"N/A");
 const src=(apt.annual||[]).filter(x=>Number.isFinite(number(x[1])));
 if(valueChart){valueChart.destroy();valueChart=null;}
 if(src.length&&typeof Chart!=="undefined"){
 valueChart=new Chart($("valueChart"),{type:"line",data:{labels:src.map(x=>x[0]),datasets:[{label:"연도별 거래중위가격(억원)",data:src.map(x=>Number(x[1])/10000),borderColor:"#1766c8",backgroundColor:"#267bea1c",pointRadius:3,fill:true,tension:.12}]},options:{maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{y:{title:{display:true,text:"억원"}},x:{ticks:{maxTicksLimit:5}}}}});
 }
 txt("valuationMessage","이 단지의 최근 5년 실제 거래 중위가격 기반입니다. 장기 적정가격 추정은 별도 모형 상세보기에서 근거·표본 조건을 확인하십시오.");
}
async function getTradeIndex(){if(!cache.tradeIndex)cache.tradeIndex=await fetchJSON("trade-details/index.json");return cache.tradeIndex;}
function tradeIndexMatch(index,district){
 const e=index?.regions||{};
 if(e[district])return {key:district,item:e[district]};
 const k=Object.keys(e).find(key=>shortName(key)===district);
 return k?{key:k,item:e[k]}:null;
}
function renderTransactionRows(){
 const query=$("tradeSearch").value.trim().toLowerCase(),records=cache.trades[state.area+":"+state.district]||[];
 const matched=records.filter(r=>!query||[r.apt,r.city,r.dong,r.jibun].join(" ").toLowerCase().includes(query));
 const shown=matched.slice(0,70);
 $("tradeRows").innerHTML=shown.length?shown.map(r=>'<tr><td>'+esc(r.date)+'</td><td style="text-align:left"><b>'+esc(r.apt)+'</b><div class="small">'+esc([r.city,r.dong,r.jibun].filter(Boolean).join(" "))+'</div></td><td>'+esc(r.area)+'㎡</td><td>'+esc(r.floor)+'</td><td>'+moneyMan(r.price)+'</td></tr>').join(""):'<tr><td colspan="5">표시할 거래가 없습니다.</td></tr>';
}
async function renderTransactions(seq){
 txt("tradeStatus","공식 실거래 원자료 조회 중…");
 txt("tradeLimit","화면에 공개된 검증 자료만 표시합니다.");
 $("tradeRows").innerHTML='<tr><td colspan="5">원자료 조회 중…</td></tr>';
 if(!state.district){txt("tradeStatus","시군구를 선택하면 거래 목록을 불러옵니다.");$("tradeRows").innerHTML='<tr><td colspan="5">상단 시군구 또는 지도에서 지역을 선택하세요.</td></tr>';return;}
 if(state.tradeType==="rent"){txt("tradeStatus","전월세 개별 공개 데이터 연결 대기");$("tradeRows").innerHTML='<tr><td colspan="5">현재 공개 상세목록은 매매 중심입니다. 전월세 데이터를 매매로 오인하지 않도록 비워 둡니다.</td></tr>';return;}
 try{
  const index=await getTradeIndex();if(seq!==asyncSeq)return;
  const match=tradeIndexMatch(index,state.district);
  if(!match){txt("tradeStatus","이 지역의 공개 개별 거래파일이 없습니다.");$("tradeRows").innerHTML='<tr><td colspan="5">집계 데이터와 원본 거래파일은 별개입니다. 현재 공개 상세 거래파일 미확보</td></tr>';return;}
  const file=match.item.file;if(!/^[0-9]{5}\.json$/.test(file))throw new Error("데이터 파일명 불일치");
  const cacheKey=state.area+":"+state.district;
  if(!cache.trades[cacheKey]){const d=await fetchJSON("trade-details/"+file);cache.trades[cacheKey]=d.rows||[];cache.trades[cacheKey+"_meta"]=d;}
  if(seq!==asyncSeq)return;
  const d=cache.trades[cacheKey+"_meta"];
  const rows=cache.trades[cacheKey];
  txt("tradeStatus",rows.length.toLocaleString()+"건 공개 · "+(d.months||[]).join(" / ")+(match.key!==state.district?" · "+match.key+" 일부 권역만":""));
  txt("tradeLimit","2026년 9~10월 공개 매매 계약 기준 · "+(d.updated_at_kst||"")+" 갱신 · 취소·중복 자료는 생성자 검증 방식에 따름. "+(rows.length>70?"최신 70건 표시, 검색으로 상세 확인.":""));
  renderTransactionRows();
 }catch(e){if(seq!==asyncSeq)return;txt("tradeStatus","거래파일 조회 실패");$("tradeRows").innerHTML='<tr><td colspan="5">'+esc(String(e))+'</td></tr>';}
}
function renderAll(){
 ++asyncSeq;const seq=asyncSeq;
 syncControls();renderRanking();renderMap();renderLocalRisk();renderValuation(seq);renderTransactions(seq);
}
function bind(){
 document.querySelectorAll("[data-area]").forEach(el=>el.addEventListener("click",()=>setArea(el.dataset.area)));
 $("districtSelect").addEventListener("change",e=>setDistrict(e.target.value));
 $("applyFilter").addEventListener("click",()=>{state.pricePeriod=$("periodSelect").value;state.tradeType=$("typeSelect").value;renderAll();});
 $("mapMetric").addEventListener("change",e=>{state.metric=e.target.value;renderMap();});
 $("riskTabs").querySelectorAll("[data-tab]").forEach(el=>el.addEventListener("click",()=>setRiskTab(el.dataset.tab)));
 $("historyMetric").addEventListener("change",drawRiskHistory);
 $("macroMetric").addEventListener("change",drawMacro);
 $("tradeSearch").addEventListener("input",renderTransactionRows);
 $("aptSearch").addEventListener("input",()=>{state.aptIndex=0;renderValuation(asyncSeq);});
 $("unifiedSearch").addEventListener("keydown",e=>{if(e.key!=="Enter")return;const q=e.target.value.trim();if(!q)return;const row=(SOURCE?.regions||[]).find(r=>r.name.includes(q)||shortName(r.name)===q);if(row){state.area=row.province;state.district=shortName(row.name);renderAll();document.getElementById("regional").scrollIntoView({behavior:"smooth"});return;}$("aptSearch").value=q;renderValuation(asyncSeq);document.getElementById("valuation").scrollIntoView({behavior:"smooth"});});
}
function start(){
 if(!SOURCE||!GEO){txt("updatedAt","핵심 데이터 로딩 실패 · ver0.0 확인");return;}
 txt("updatedAt","실거래 "+(SOURCE.meta?.evaluationMonth||"기준월 불명")+" 완결 · "+(SOURCE.meta?.latestObservationMonth||"")+" 잠정");
 bind();renderNational();renderAll();setRiskTab("history");drawMacro();
}
start();
})();
