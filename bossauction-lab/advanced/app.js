import {parseImport,filterLots,inViewport,price,pct,escapeHTML,costScenario,safeStoredIDs,MAX_IMPORT_BYTES} from "./core.js";

const $=id=>document.getElementById(id);
const STATE={
 lots:[],source:{name:"자료 미연결",kind:"empty",verified:false},
 filters:{q:"",channel:"all",region:"all",type:"all",sort:"date",favoritesOnly:false,dateFrom:"",dateTo:""},
 favorites:safeStoredIDs(localStorage.getItem("auction-v11-pages-favorites")),
 compare:new Set(),selected:null,activeView:"map",
 map:null,mapMode:"view",markers:[],cadastral:null,mapReady:false,sdkLoading:false,
 coords:[],preview:null,overlays:[],sdkScript:null,manualIds:new Set(),checks:new Set()
};
const KEYS=[["registry","등기사항증명서 발급 및 권리 순위"],["notice","매각물건명세서 인수사항·특별매각조건"],["occupant","현황조사서 점유 및 임대차"],["tenant","대항력·배당요구 및 보증금"],["fees","체납관리비·명도비·세금"],["changes","변경·취소·유찰 및 기일 원문"]];
const SAMPLE=[
{id:"DEMO-001",channel:"court",title:"서울 성동구 가상 아파트",region:"서울",type:"아파트",location:"서울 성동구 (가상 주소)",authority:"가상 법원",appraisal:920000000,minimum:644000000,date:"2026-11-03",failures:1,area:84.9,lat:null,lng:null,coordinateSource:null,sourceUrl:null},
{id:"DEMO-002",channel:"court",title:"경기 수원시 가상 빌라",region:"경기",type:"다세대",location:"경기도 수원시 (가상 주소)",authority:"가상 법원",appraisal:280000000,minimum:196000000,date:"2026-11-05",failures:1,area:59.1,lat:null,lng:null,coordinateSource:null,sourceUrl:null},
{id:"DEMO-003",channel:"public",title:"부산 해운대 가상 상가",region:"부산",type:"상가",location:"부산 해운대구 (가상 주소)",authority:"가상 공매 기관",appraisal:650000000,minimum:520000000,date:"2026-11-09",failures:0,area:112.5,lat:null,lng:null,coordinateSource:null,sourceUrl:null},
{id:"DEMO-004",channel:"court",title:"인천 서구 가상 오피스텔",region:"인천",type:"오피스텔",location:"인천 서구 (가상 주소)",authority:"가상 법원",appraisal:210000000,minimum:147000000,date:"2026-11-12",failures:1,area:39.7,lat:null,lng:null,coordinateSource:null,sourceUrl:null},
{id:"DEMO-005",channel:"public",title:"대전 유성구 가상 토지",region:"대전",type:"토지",location:"대전 유성구 (가상 주소)",authority:"가상 공매 기관",appraisal:410000000,minimum:307500000,date:"2026-11-16",failures:0,area:270,lat:null,lng:null,coordinateSource:null,sourceUrl:null},
{id:"DEMO-006",channel:"court",title:"대구 달서구 가상 아파트",region:"대구",type:"아파트",location:"대구 달서구 (가상 주소)",authority:"가상 법원",appraisal:350000000,minimum:245000000,date:"2026-11-19",failures:1,area:75.2,lat:null,lng:null,coordinateSource:null,sourceUrl:null}
];
function tell(s){$("map-status").textContent=s;}
function diagnostic(s){$("sdk-diagnostics").textContent=s;}
function btnStatus(s){$("sdk-badge").textContent=s;}
function findItem(id){return STATE.lots.find(x=>x.id===id);}
function current(){return filterLots(STATE.lots,{...STATE.filters,saved:STATE.favorites});}
function setView(v){
 const routes=new Set(["map","list","calendar","compare","analyze","data"]);
 if(!routes.has(v))v="map";
 STATE.activeView=v;
 document.querySelectorAll(".view").forEach(x=>x.classList.toggle("active",x.id==="view-"+v));
 document.querySelectorAll("nav [data-view]").forEach(x=>{x.classList.toggle("active",x.dataset.view===v);if(x.dataset.view===v)x.setAttribute("aria-current","page");else x.removeAttribute("aria-current");});
 if(location.hash!=="#"+v)history.replaceState(null,"","#"+v);
 if(v==="map"&&STATE.mapReady){setTimeout(()=>{naver.maps.Event.trigger(STATE.map,"resize");mapIdle();},50);}
}
function statusHTML(){
 $("source-count").textContent=STATE.lots.length+"건";
 $("dataset-name").textContent=STATE.source.name;
 $("dataset-info").textContent=STATE.source.kind==="empty"?"CSV/JSON 파일을 가져오거나 명시적 가상 예제를 여세요.":STATE.source.kind==="demo"?"가상 예제 · 법원·공매 원본 데이터가 아닙니다.":"사용자 반입 "+STATE.lots.length+"건 · 공고 원문 미검증";
 $("unlocated-count").textContent=STATE.lots.filter(l=>l.lat===null).length+"건";
}
function options(id,values){
 const el=$(id),old=el.value;
 el.innerHTML='<option value="all">전체</option>'+[...new Set(values.filter(Boolean))].sort((a,b)=>a.localeCompare(b,"ko")).map(x=>'<option value="'+escapeHTML(x)+'">'+escapeHTML(x)+'</option>').join("");
 if([...el.options].some(x=>x.value===old))el.value=old;else{el.value="all";STATE.filters[id==="region"?"region":"type"]="all";}
}
function getFilters(){
 STATE.filters={q:$("query").value,channel:$("channel").value,region:$("region").value,type:$("ptype").value,sort:$("sort").value,favoritesOnly:$("favorite-filter").checked,dateFrom:$("date-from").value,dateTo:$("date-to").value};
}
function actions(id){
 const p=escapeHTML(id),fav=STATE.favorites.has(id),comp=STATE.compare.has(id);
 return '<button data-act="detail" data-id="'+p+'">상세</button><button data-act="fav" data-id="'+p+'">'+(fav?"★ 저장됨":"☆ 관심")+'</button><button data-act="compare" data-id="'+p+'">'+(comp?"✓ 비교해제":"+ 비교")+'</button>';
}
function lotCard(l){
 return '<article class="card"><span class="tag '+(l.channel==="public"?"public":"")+'">'+(l.channel==="public"?"공매":"법원경매")+'</span><h3>'+escapeHTML(l.title)+'</h3><p>'+escapeHTML(l.id)+' · '+escapeHTML(l.location)+'</p><div class="line"><span>감정가</span><b>'+price(l.appraisal)+'</b></div><div class="line"><span>최저가</span><b>'+price(l.minimum)+'</b></div><div class="line"><span>할인율</span><b>'+pct(l)+'</b></div><div class="line"><span>기일 (미검증)</span><b>'+escapeHTML(l.date||"미제공")+'</b></div><div class="line"><span>좌표</span><b>'+(l.lat===null?"미확보":escapeHTML(l.coordinateSource||"출처 미확인"))+'</b></div><div class="buttons">'+actions(l.id)+'</div></article>';
}
function draw(){
 const items=current();
 statusHTML();
 $("result-count").textContent=items.length+"건";
 $("sidebar-results").innerHTML=items.length?items.slice(0,100).map(l=>'<div class="side-lot"><span class="tag '+(l.channel==="public"?"public":"")+'">'+(l.channel==="court"?"경매":"공매")+'</span> <b>'+escapeHTML(l.title)+'</b><p>'+escapeHTML(l.id)+' · '+escapeHTML(l.location)+'</p><p>최저 '+price(l.minimum)+' · '+escapeHTML(l.date||"일정 미제공")+'</p>'+actions(l.id)+'</div>').join(""):'<div class="empty">조회 물건이 없습니다. 자료를 불러오세요.</div>';
 $("list-results").innerHTML=items.length?items.slice(0,150).map(lotCard).join(""):'<div class="empty">검색 결과가 없습니다. 데이터 연동 화면에서 파일을 가져오세요.</div>';
 if(items.length>150)$("list-results").insertAdjacentHTML("beforeend",'<p class="muted">목록은 150건까지만 렌더링합니다. 검색 조건을 좁혀주세요.</p>');
 $("schedule-results").innerHTML=items.filter(l=>l.date).length?items.filter(l=>l.date).map(l=>'<div class="calendar-item"><div class="date">'+escapeHTML(l.date)+'</div><div style="flex:1"><b>'+escapeHTML(l.title)+'</b><p class="muted">'+(l.channel==="court"?"법원경매":"공매")+' · '+escapeHTML(l.authority)+'</p></div><button data-act="detail" data-id="'+escapeHTML(l.id)+'">보기</button></div>').join(""):'<div class="empty">일정 정보 없음</div>';
 drawCompare();
 $("review-lot").innerHTML='<option value="">대상 선택</option>'+STATE.lots.map(l=>'<option value="'+escapeHTML(l.id)+'">'+escapeHTML(l.title)+'</option>').join("");
 $("review-lot").value=STATE.selected&&findItem(STATE.selected)?STATE.selected:"";
 drawCheckList();
 drawMapPins();
}
function drawCompare(){
 const items=[...STATE.compare].map(findItem).filter(Boolean);
 if(!items.length){$("compare-results").innerHTML='<div class="empty">통합검색에서 비교할 물건을 1~3건 선택하세요.</div>';return;}
 const row=(label,get)=>'<tr><th>'+label+'</th>'+items.map(l=>'<td>'+escapeHTML(get(l))+'</td>').join("")+'</tr>';
 $("compare-results").innerHTML='<table class="compare-table"><thead><tr><th>항목</th>'+items.map(l=>'<th>'+escapeHTML(l.title)+'</th>').join("")+'</tr></thead><tbody>'+
 row("물건번호",l=>l.id)+row("유형",l=>l.channel==="court"?"법원경매":"공매")+row("소재지",l=>l.location)+row("감정가",l=>price(l.appraisal))+row("최저가",l=>price(l.minimum))+row("감정가 대비 할인",pct)+row("일정",l=>l.date||"미확인")+row("좌표 출처",l=>l.coordinateSource||"미확보")+'</tbody></table>';
}
function drawCheckList(){
 $("rights-checks").innerHTML=KEYS.map(([k,title])=>'<label class="check-row"><input type="checkbox" data-check="'+k+'" '+(STATE.checks.has(k)?"checked":"")+'><span>'+title+'</span></label>').join("")+'<p class="muted">'+STATE.checks.size+'/'+KEYS.length+'개 자가 점검 · 권리 안전성 판정 불가</p>';
}
function details(id){
 const l=findItem(id);if(!l)return;
 STATE.selected=id;
 const cells=[["구분",l.channel==="court"?"법원경매":"공매"],["사건/물건 ID",l.id],["주소",l.location],["기관",l.authority],["물건유형",l.type],["감정가",price(l.appraisal)],["최저가",price(l.minimum)],["비율",pct(l)],["매각/입찰기일",l.date||"원문 확인 필요"],["유찰",l.failures+"회"],["위치 좌표",l.lat===null?"미확보":l.lat+", "+l.lng],["좌표 출처",l.coordinateSource||"미제공"]];
 $("detail-panel").innerHTML='<div class="dialog-head"><div><span class="tag '+(l.channel==="public"?"public":"")+'">'+(l.channel==="court"?"경매":"공매")+'</span><h2>'+escapeHTML(l.title)+'</h2></div><button data-act="close">닫기 ×</button></div><div class="detail-grid">'+cells.map(([n,v])=>'<div class="detail-cell"><label>'+n+'</label><strong>'+escapeHTML(v)+'</strong></div>').join("")+'</div>'+
 '<p class="muted">자료 출처: '+escapeHTML(STATE.source.name)+' · 원문 검증 전</p><p>'+(l.sourceUrl?'<a target="_blank" rel="noopener noreferrer" href="'+escapeHTML(l.sourceUrl)+'">사용자 제공 원문 열기 ↗</a>':'<span class="muted">원문 링크 미제공</span>')+'</p>'+
 '<p><button data-act="mark" data-id="'+escapeHTML(l.id)+'">네이버 지도에서 임시 위치 지정</button><button data-act="review" data-id="'+escapeHTML(l.id)+'">권리 점검</button></p><p class="muted">임시 위치 지정은 확인된 부동산 실제 좌표를 의미하지 않습니다.</p>';
 if(!$("detail-dialog").open)$("detail-dialog").showModal();
}
function persistFav(){try{localStorage.setItem("auction-v11-pages-favorites",JSON.stringify([...STATE.favorites]));}catch{}}
function changeData(result){
 STATE.lots=result.lots.map(x=>({...x}));
 STATE.source=result.meta;
 STATE.compare.clear();STATE.manualIds.clear();STATE.selected=null;STATE.checks.clear();
 STATE.filters={q:"",channel:"all",region:"all",type:"all",sort:"date",favoritesOnly:false,dateFrom:"",dateTo:""};
 $("filter-form").reset();
 options("region",STATE.lots.map(l=>l.region));options("ptype",STATE.lots.map(l=>l.type));
 $("import-feedback").textContent="적용 완료: "+STATE.lots.length+"건 (데이터 진위는 미확인)";
 draw();
}
function addDemo(){
 changeData({lots:SAMPLE.map(l=>({...l})),meta:{kind:"demo",name:"가상 예제 6건 (실제 사건 아님)",verified:false}});
 setView("list");
}
function saveAs(name,data,mime="application/json"){
 const blob=new Blob([data],{type:mime}),url=URL.createObjectURL(blob),a=document.createElement("a");
 a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
async function readFile(){
 const file=$("file-input").files?.[0];
 if(!file){$("import-feedback").textContent="CSV 또는 JSON 파일을 선택하세요.";return;}
 if(file.size>MAX_IMPORT_BYTES){$("import-feedback").textContent="8MB 이하 파일을 선택하세요.";return;}
 try{
  const text=await file.text(),result=parseImport(text,file.name);
  changeData(result);setView("list");
 }catch(e){$("import-feedback").textContent="검증 실패: "+String(e.message||e);}
}
function nav(){return window.naver&&window.naver.maps;}
let sdkPromise=null;
window.navermap_authFailure=()=>{diagnostic("인증 실패: 새 Maps 상품 Client ID, Dynamic Map 설정, 허용된 서비스 URL을 확인하세요.");btnStatus("지도 인증 실패");};
function loadSdk(id){
 if(nav())return Promise.resolve();
 if(sdkPromise)return sdkPromise;
 sdkPromise=new Promise((resolve,reject)=>{
  const s=document.createElement("script");let done=false;
  const end=e=>{if(done)return;done=true;clearTimeout(timer);if(e)reject(e);else resolve();};
  s.src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId="+encodeURIComponent(id);
  s.async=true;s.referrerPolicy="strict-origin-when-cross-origin";
  s.onerror=()=>end(new Error("SDK 네트워크/인증 실패"));
  s.onload=()=>nav()?end():end(new Error("네이버 지도 객체가 로드되지 않음"));
  const timer=setTimeout(()=>end(new Error("SDK 응답 시간 초과 (15초)")),15000);
  STATE.sdkScript=s;document.head.appendChild(s);
 }).catch(e=>{sdkPromise=null;throw e;});
 return sdkPromise;
}
async function connectMap(){
 if(STATE.sdkLoading)return;
 const id=$("sdk-id").value.trim();
 if(!/^[A-Za-z0-9_-]{5,120}$/.test(id)){diagnostic("새 Maps 상품 Client ID를 확인하세요. Client Secret은 입력하지 마세요.");return;}
 STATE.sdkLoading=true;btnStatus("지도 SDK 연결 중");
 try{
  await loadSdk(id);
  if(!STATE.mapReady){
   $("naver-map").style.display="block";$("map-placeholder").hidden=true;$("map-placeholder").style.display="none";
   STATE.map=new naver.maps.Map("naver-map",{center:new naver.maps.LatLng(37.5665,126.978),zoom:11,zoomControl:true});
   STATE.mapReady=true;
   naver.maps.Event.addListener(STATE.map,"idle",()=>{clearTimeout(STATE.idleTimer);STATE.idleTimer=setTimeout(mapIdle,260);});
   naver.maps.Event.addListener(STATE.map,"click",evt=>mapClick(evt.coord||evt.latlng));
  }
  btnStatus("네이버 SDK 실행");diagnostic("SDK 객체 생성 완료 · 실제 지도 타일 표시 및 네이버 계정 권한은 브라우저에서 확인하세요.");
  tell("네이버 지도 SDK 연결됨 · 지도 호출은 네이버 Maps 이용정책을 따릅니다.");
  $("sdk-dialog").close();setView("map");drawMapPins();
 }catch(e){btnStatus("지도 연결 오류");diagnostic(e.message+"\n새 Maps Client ID / Web Dynamic Map 활성화 / 허용 URL(https://edwardlim1004.github.io)을 확인하세요.");tell("SDK 연결 실패: "+e.message);}
 finally{STATE.sdkLoading=false;}
}
function stopMap(){
 for(const m of STATE.markers)m.setMap(null);STATE.markers=[];
 if(STATE.cadastral)STATE.cadastral.setMap(null);
 for(const o of STATE.overlays)o.setMap(null);STATE.overlays=[];
 if(STATE.preview)STATE.preview.setMap(null);STATE.preview=null;
 STATE.map=null;STATE.mapReady=false;
 $("naver-map").replaceChildren();$("naver-map").style.display="none";
 $("map-placeholder").hidden=false;$("map-placeholder").style.display="flex";
 btnStatus("SDK 연결 해제");tell("지도 화면 연결 해제 · 재실행 시 Maps SDK가 이미 로드되어 있을 수 있습니다.");
}
function getBounds(){
 if(!STATE.mapReady)return null;
 const b=STATE.map.getBounds(),sw=b.getSW(),ne=b.getNE();
 return {south:sw.lat(),north:ne.lat(),west:sw.lng(),east:ne.lng()};
}
function mapIdle(){
 if(!STATE.mapReady)return;
 const c=STATE.map.getCenter();$("map-coords").textContent="중심 "+c.lat().toFixed(5)+", "+c.lng().toFixed(5)+" / 확대 "+STATE.map.getZoom();
 drawMapPins();
}
function drawMapPins(){
 if(!STATE.mapReady)return;
 for(const x of STATE.markers)x.setMap(null);STATE.markers=[];
 const bounds=getBounds(),eligible=current().filter(l=>inViewport(l,bounds));
 $("viewport-count").textContent=eligible.length+"건";
 // Bounds-limited rendering. Location source appears in tooltip; markers cannot imply legal land boundaries.
 for(const l of eligible.slice(0,600)){
  const m=new naver.maps.Marker({map:STATE.map,position:new naver.maps.LatLng(l.lat,l.lng),title:l.title+" · "+(l.coordinateSource||"출처 미확인")});
  naver.maps.Event.addListener(m,"click",()=>details(l.id));STATE.markers.push(m);
 }
 if(eligible.length>600)tell("현재 지도 내 600건까지 마커 표시 · 필터를 좁혀주세요.");
}
function mapType(type){
 if(!STATE.mapReady){tell("지도 연결 후 사용할 수 있습니다.");return;}
 STATE.map.setMapTypeId(type==="hybrid"?naver.maps.MapTypeId.HYBRID:naver.maps.MapTypeId.NORMAL);
}
function cadastre(){
 if(!STATE.mapReady){tell("지도 연결 후 사용할 수 있습니다.");return;}
 try{if(!STATE.cadastral)STATE.cadastral=new naver.maps.CadastralLayer();STATE.cadastral.setMap(STATE.cadastral.getMap()?null:STATE.map);}
 catch(e){tell("지적도 사용 불가: 계정 설정 또는 SDK 지원 여부를 확인하세요.");}
}
function setMapMode(mode){
 STATE.mapMode=mode;
 if(!STATE.mapReady&&mode!=="view"){tell("네이버 지도 연결 후 측정·위치 지정을 사용할 수 있습니다.");return;}
 if(mode==="view"){STATE.coords=[];erasePreview();}
 const tips={view:"조회 모드",place:"물건 상세에서 위치 지정을 먼저 선택한 후 지도 클릭",distance:"지도에서 2개 이상 점을 찍고 측정 완료",area:"지도에서 3개 이상 점을 찍고 측정 완료"};
 tell(tips[mode]);
}
function erasePreview(){if(STATE.preview){STATE.preview.setMap(null);STATE.preview=null;}}
function mapClick(p){
 if(!p||!STATE.mapReady)return;
 if(STATE.mapMode==="place"){
  const l=findItem(STATE.selected);
  if(!l){tell("물건 상세에서 위치 지정 대상을 선택하세요.");return;}
  if(!STATE.manualIds.has(l.id)){tell("상세 화면에서 임시 위치 지정 버튼을 먼저 선택하세요.");return;}
  l.lat=p.lat();l.lng=p.lng();l.coordinateSource="사용자 수동 지정·검증 전";
  STATE.manualIds.delete(l.id);$("map-mode").value="view";STATE.mapMode="view";tell(l.id+" 임시 좌표 지정됨 · 실제 위치 검증 필요");draw();return;
 }
 if(STATE.mapMode==="distance"||STATE.mapMode==="area"){STATE.coords.push(p);drawMeasure();}
}
function drawMeasure(){
 erasePreview();
 const pts=STATE.coords,n=naver.maps;
 $("measure-value").textContent=pts.length+"개 점 지정";
 if(STATE.mapMode==="distance"&&pts.length>=2){
  STATE.preview=new n.Polyline({map:STATE.map,path:pts,strokeColor:"#126bd2",strokeWeight:4});
  const meters=STATE.preview.getDistance();$("measure-value").textContent=meters>=1000?(meters/1000).toFixed(3)+" km":meters.toFixed(1)+" m";
 }
 if(STATE.mapMode==="area"&&pts.length>=3){
  STATE.preview=new n.Polygon({map:STATE.map,paths:pts,strokeColor:"#0e9463",fillColor:"#21b781",fillOpacity:0.17,strokeWeight:3});
  const m2=STATE.preview.getAreaSize();$("measure-value").textContent=m2.toFixed(2)+" ㎡ / "+(m2/3.305785).toFixed(2)+" 평 (좌표 계산)";
 }
}
function finishMeasure(){
 const min=STATE.mapMode==="area"?3:STATE.mapMode==="distance"?2:999;
 if(STATE.coords.length<min){tell("거리 2개, 면적 3개 이상의 점을 찍으세요.");return;}
 if(STATE.preview){STATE.overlays.push(STATE.preview);STATE.preview=null;}
 STATE.coords=[];tell("측정 완료 · 지도 좌표 계산값이며 법적 필지 면적과 다를 수 있습니다.");
}
function resetMeasures(){STATE.coords=[];erasePreview();for(const o of STATE.overlays)o.setMap(null);STATE.overlays=[];$("measure-value").textContent="측정 초기화";}
function renderCosts(r){
 $("cost-result").innerHTML='<div class="cost-stat"><span>보증금 (입찰대금 포함)</span><strong>'+price(r.deposit)+'</strong></div><div class="cost-stat"><span>보증금 제외 납부잔액</span><strong>'+price(r.balance)+'</strong></div><div class="cost-stat"><span>취득 관련 비용 가정</span><strong>'+price(r.fee)+'</strong></div><div class="cost-stat"><span>총 취득 비용 (보증금 중복 없음)</span><strong>'+price(r.total)+'</strong></div><div class="cost-stat"><span>처분가 대비 단순 차액</span><strong>'+price(r.difference)+'</strong></div>';
}
function bind(){
 document.querySelectorAll("[data-view]").forEach(x=>x.addEventListener("click",()=>setView(x.dataset.view)));
 $("filter-form").addEventListener("submit",e=>{e.preventDefault();getFilters();draw();});
 $("sample-btn").addEventListener("click",addDemo);
 $("import-shortcut").addEventListener("click",()=>setView("data"));
 $("import-file").addEventListener("click",readFile);
 $("export-json").addEventListener("click",()=>{if(!STATE.lots.length){$("import-feedback").textContent="내보낼 데이터가 없습니다.";return;}saveAs("auction-pages-export.json",JSON.stringify({sourceName:STATE.source.name,collectedAt:new Date().toISOString(),lots:STATE.lots},null,2));});
 $("map-connect").addEventListener("click",()=>{if(STATE.mapReady){setView("map");return;}$("sdk-dialog").showModal();});
 $("placeholder-connect").addEventListener("click",()=>$("sdk-dialog").showModal());
 $("map-settings").addEventListener("click",()=>$("sdk-dialog").showModal());
 $("sdk-start").addEventListener("click",connectMap);
 $("sdk-stop").addEventListener("click",stopMap);
 document.querySelectorAll("[data-maptype]").forEach(x=>x.addEventListener("click",()=>mapType(x.dataset.maptype)));
 $("cadastre").addEventListener("click",cadastre);
 $("map-home").addEventListener("click",()=>{if(STATE.mapReady){STATE.map.setCenter(new naver.maps.LatLng(37.5665,126.978));STATE.map.setZoom(11);}else tell("지도 연결 전입니다.");});
 $("map-mode").addEventListener("change",e=>setMapMode(e.target.value));
 $("measure-finish").addEventListener("click",finishMeasure);
 $("measure-undo").addEventListener("click",()=>{STATE.coords.pop();drawMeasure();});
 $("measure-reset").addEventListener("click",resetMeasures);
 $("map-clear-pins").addEventListener("click",()=>{for(const l of STATE.lots){if(l.coordinateSource==="사용자 수동 지정·검증 전"){l.lat=null;l.lng=null;l.coordinateSource=null;}}draw();tell("사용자 임시 지정 좌표만 제거했습니다. 반입 원본 좌표는 보존합니다.");});
 document.addEventListener("click",e=>{
  const b=e.target.closest("[data-act]");if(!b)return;
  const id=b.dataset.id,action=b.dataset.act;
  if(action==="close"){$("detail-dialog").close();return;}
  if(action==="detail"){details(id);return;}
  if(action==="fav"){STATE.favorites.has(id)?STATE.favorites.delete(id):STATE.favorites.add(id);persistFav();draw();return;}
  if(action==="compare"){
   if(STATE.compare.has(id))STATE.compare.delete(id);else if(STATE.compare.size<3)STATE.compare.add(id);else{alert("비교는 최대 3건까지 가능합니다.");return;}
   draw();return;
  }
  if(action==="mark"){
   if(!STATE.mapReady){tell("네이버 지도 연결 후 사용할 수 있습니다.");$("detail-dialog").close();setView("map");return;}
   STATE.selected=id;STATE.manualIds.add(id);$("detail-dialog").close();setView("map");$("map-mode").value="place";setMapMode("place");return;
  }
  if(action==="review"){STATE.selected=id;STATE.checks.clear();$("detail-dialog").close();setView("analyze");drawCheckList();$("review-lot").value=id;}
 });
 $("review-lot").addEventListener("change",e=>{STATE.selected=e.target.value||null;STATE.checks.clear();drawCheckList();});
 document.addEventListener("change",e=>{if(e.target.matches("[data-check]")){e.target.checked?STATE.checks.add(e.target.dataset.check):STATE.checks.delete(e.target.dataset.check);drawCheckList();}});
 $("rights-export").addEventListener("click",()=>saveAs("auction-review-checklist.json",JSON.stringify({lotId:STATE.selected,checked:Object.fromEntries(KEYS.map(([k])=>[k,STATE.checks.has(k)])),rightsSafety:"not-evaluated",note:"사용자 자가 점검. 권리 안전성 판정 아님."},null,2)));
 $("cost-form").addEventListener("submit",e=>{e.preventDefault();const form=new FormData(e.target);const n=k=>Number(form.get(k));try{renderCosts(costScenario({bid:n("bid")*10000,depositPercent:n("depositPercent"),feePercent:n("feePercent"),extra:n("extra")*10000,resale:n("resale")*10000}));}catch(err){$("cost-result").textContent=err.message;}});
 window.addEventListener("hashchange",()=>setView(location.hash.slice(1)));
}
function init(){bind();draw();setView(location.hash.slice(1)||"map");}
init();
