import {escapeHTML,price,pct,filterLots,safeStoredIDs,parseImport} from "../advanced/core.js";
import {readV11Sqlite,restorePrivateSnapshot,savePrivateSnapshot,forgetPrivateSnapshot} from "../advanced/sqlite.js";
import {readClientId,saveClientId,clearClientId,quotaOverview,buildQuotaSnapshot,readQuotaSnapshot,saveQuotaSnapshot,deleteQuotaSnapshot,localGeocodeRequests,recordLocalGeocodeRequest} from "../advanced/maps-account.js";
import {getUnlocatedGroups,planGeocodeRequests,geocodeWithSdk,applyGeocodedPoint} from "../advanced/geocode.js";
import {summarize,groupByLocation,sectionFilter,exportLocalLots} from "./classic-core.js";

const $=id=>document.getElementById(id);
const storage=()=>{try{return window.localStorage}catch{return null}};
const n=k=>Number(k).toLocaleString("ko-KR");
const favKey="auction-v11-pages-favorites";
const state={lots:[],source:{name:"자료 없음",kind:"empty"},sdk:null,map:null,
 sdkBusy:false,mapReady:false,cadastral:null,mapMode:"all",section:"map",
 measure:null,measurePoints:[],measurePreview:null,measureDone:[],markers:[],
 modePlace:null,geoRunning:false,geoStop:false,geoAttempted:new Set(),geoReview:[],
 favorites:safeStoredIDs(storage()?.getItem(favKey)),favoriteOnly:false,rememberDB:false,
 latestLoaded:0,logs:[],lastSDKError:null};
const countryCenter={lat:37.5067,lng:127.1355};
function notice(msg){$("map-status").textContent=msg}
function log(code,text){
 const safe=String(text||"").replace(/(ncpKeyId|Client ID|secret|key)\s*[:=]\s*\S+/ig,"$1=[REDACTED]").slice(0,280);
 state.logs.push({time:new Date().toISOString(),code,message:safe});
 if(state.logs.length>120)state.logs.shift();
 $("debug-logs").textContent=state.logs.slice(-22).map(x=>x.time.slice(11,19)+" "+x.code+" · "+x.message).join("\n");
}
function setSDK(s){$("sdk-state").textContent=s;$("sdk-feedback").textContent=s;}
function showPanel(name){
 for(const key of ["sdk","usage","data-map"]){$(key+"-panel").hidden=key!==name;}
}
function hidePanels(){["sdk","usage","data-map"].forEach(k=>$(k+"-panel").hidden=true);}
function changeSection(section){
 state.section=section;
 document.querySelectorAll("[data-section]").forEach(b=>b.classList.toggle("current",b.dataset.section===section));
 if(section==="analysis"){location.href="../advanced/#analyze";return;}
 if(section==="trade"){location.href="../advanced/#data";return;}
 const headings={map:"지도검색 · 보유 물건",search:"경매·공매 종합검색",schedule:"경매 일정",auction:"법원 경매",public:"공매 검색",sale:"매각 결과 · 검증 전",apt:"아파트",land:"토지",favorites:"관심물건"};
 $("section-heading").textContent=headings[section]||"보유 물건 검색";
 renderResults();
 if(section==="schedule")$("results").scrollTop=0;
}
function setLots(result,{remember=false}={}){
 state.latestLoaded++;
 state.lots=result.lots.map(l=>({...l}));
 state.source={...(result.meta||{}),name:result.meta?.name||"사용자 입력 자료"};
 state.geoAttempted.clear();state.geoReview=[];
 state.rememberDB=remember;
 $("db-remember").checked=remember;
 renderAll();
 log("DATA","사용자 입력 DB "+state.lots.length+"건 연결. 실시간 API 아님");
}
function renderStats(){
 const counts=summarize(state.lots);
 $("total-court").textContent=counts.court+"건";
 $("total-public").textContent=counts.public+"건";
 $("total-located").textContent=counts.located+"건";
 $("total-unlocated").textContent=counts.unlocated+"건";
 $("dataset-summary").textContent=state.source.name+" · "+counts.total+"건";
 $("source-hint").textContent="자료 출처: "+state.source.name+" · 저장된 날짜·경매 진행상태는 원문 재확인이 필요합니다.";
 $("db-total").textContent=n(counts.total);
 $("db-located").textContent=n(counts.located);
 $("db-missing").textContent=n(counts.unlocated);
 $("map-summary").textContent="실좌표 "+counts.located+"건 · 마커 "+state.markers.length+"개";
 $("place-case").innerHTML=state.lots.length?state.lots.slice(0,200).map(l=>'<option value="'+escapeHTML(l.id)+'">'+escapeHTML(l.title)+" · "+escapeHTML(l.location)+'</option>').join(""):'<option value="">물건 없음</option>';
}
function makeItem(l){
 const marked=state.favorites.has(l.id);
 return '<article class="record"><span class="record-kind '+(l.channel==="public"?"public":"")+'">'+(l.channel==="public"?"공매":"법원 경매")+'</span><h3>'+escapeHTML(l.title)+'</h3>'+
  '<p>'+escapeHTML(l.id)+' · '+escapeHTML(l.location)+'</p><div class="prices"><span>감정가 '+price(l.appraisal)+'</span><strong>최저 '+price(l.minimum)+'</strong></div>'+
  '<p>기일 '+escapeHTML(l.date||"미확인")+' · 유찰 '+escapeHTML(l.failures)+'회 · '+(l.lat===null?"좌표 미확보":escapeHTML(l.coordinateSource||"좌표 출처 미확인"))+'</p>'+
  '<footer><button data-action="detail" data-id="'+escapeHTML(l.id)+'">물건 상세</button><button data-action="fav" data-id="'+escapeHTML(l.id)+'">'+(marked?"★ 저장됨":"☆ 관심")+'</button>'+
  '<button data-action="on-map" data-id="'+escapeHTML(l.id)+'">지도에서 보기</button></footer></article>';
}
function renderResults(){
 const query=$("search-input").value;
 let rows=sectionFilter(state.lots,state.section,state.favorites);
 if(state.favoriteOnly)rows=rows.filter(l=>state.favorites.has(l.id));
 rows=filterLots(rows,{q:query,channel:$("kind-filter").value,sort:$("sort-filter").value});
 if(state.section==="schedule")rows=rows.filter(l=>!!l.date);
 const results=$("results");
 $("result-label").textContent=n(rows.length)+"건";
 results.innerHTML=rows.length?rows.slice(0,200).map(makeItem).join(""):'<div class="empty">해당 조건에 맞는 저장 물건이 없습니다.<p class="small-note">기존 DB를 연결하거나 검색 조건을 변경해 주세요. 실시간 전체 물건 0건이라는 의미는 아닙니다.</p></div>';
 if(rows.length>200)results.insertAdjacentHTML("beforeend",'<p class="small-note">처음 200건만 표시합니다. 조건을 좁혀주세요.</p>');
}
function renderQuota(){
 const view=quotaOverview(readQuotaSnapshot(storage()));
 $("quota-map").textContent=view.map.remaining===null?"실제 잔여량 미확인":n(view.map.remaining)+"회 남음 (입력시점)";
 $("quota-geocode").textContent=view.geocoding.remaining===null?"실제 잔여량 미확인":n(view.geocoding.remaining)+"회 남음 (입력시점)";
 $("used-map").value=view.valid&&view.map.used!==null?view.map.used:"";
 $("used-geo").value=view.valid&&view.geocoding.used!==null?view.geocoding.used:"";
 $("local-geo-calls").textContent=n(localGeocodeRequests(storage()))+"회";
 $("quota-feedback").textContent=view.stale?"지난달 입력은 재사용하지 않습니다. 네이버 콘솔에서 이번달 사용량을 다시 확인하세요.":"대표 계정 전체 Application 합계의 콘솔 사용량 기준이며 실시간 조회가 아닙니다.";
}
function renderAll(){renderStats();renderResults();drawMarkers();renderGeoCandidates()}
function openDetail(id){
 const l=state.lots.find(x=>x.id===id);if(!l)return;
 const fields=[["구분",l.channel==="public"?"공매":"법원 경매"],["물건 ID",l.id],["주소",l.location],["기관",l.authority||"미제공"],["감정가",price(l.appraisal)],["최저가",price(l.minimum)],["유찰",l.failures+"회"],["매각기일",l.date||"미확인"],["좌표",l.lat===null?"미확보":l.lat+", "+l.lng],["위치 출처",l.coordinateSource||"미제공"]];
 $("detail-content").innerHTML='<h2>'+escapeHTML(l.title)+'</h2><p class="small-note">'+escapeHTML(state.source.name)+' · 경매 진행 상태 및 권리 관계 미검증</p><div class="details-grid">'+fields.map(([k,v])=>'<div><span>'+escapeHTML(k)+'</span><b>'+escapeHTML(v)+'</b></div>').join("")+'</div>'+
 (l.sourceUrl?'<p><a href="'+escapeHTML(l.sourceUrl)+'" rel="noopener noreferrer" target="_blank">사용자가 제공한 원문 보기</a></p>':'<p class="small-note">공식 사건 원문 링크 미제공</p>')+
 '<p><a href="../advanced/#analyze">입찰 비용 · 권리 점검 도구</a></p><p class="small-note">이 화면은 법률 권리분석·대항력 판단이나 입찰 결정을 대행하지 않습니다.</p>';
 $("detail-dialog").showModal();
}
function updateFavorites(id){
 if(state.favorites.has(id))state.favorites.delete(id);else state.favorites.add(id);
 try{storage()?.setItem(favKey,JSON.stringify([...state.favorites]))}catch{}
 renderResults();
}
function focusLot(l){
 if(!l){notice("물건을 찾을 수 없습니다.");return;}
 if(l.lat===null||!state.mapReady){notice("물건 좌표가 없습니다. 데이터 DB에서 주소변환을 하거나 지도 설정에서 시험 좌표를 지정하세요.");showPanel("data-map");return;}
 state.map.setCenter(new naver.maps.LatLng(l.lat,l.lng));
 state.map.setZoom(17);drawMarkers();
}
function setMapMode(mode){
 state.mapMode=mode;
 document.querySelectorAll("[data-mode]").forEach(b=>b.classList.toggle("selected",b.dataset.mode===mode));
 drawMarkers();
}
function clearMarkers(){
 for(const m of state.markers){try{m.setMap(null)}catch{}}
 state.markers=[];
}
function drawMarkers(){
 clearMarkers();
 if(!state.mapReady)return;
 const nav=window.naver.maps,map=state.map;
 let eligible=state.lots.filter(l=>Number.isFinite(l.lat)&&Number.isFinite(l.lng));
 if(state.mapMode==="court"||state.mapMode==="public")eligible=eligible.filter(l=>l.channel===state.mapMode);
 const b=map.getBounds();
 if(b)eligible=eligible.filter(l=>b.hasLatLng(new nav.LatLng(l.lat,l.lng)));
 const zoom=map.getZoom();
 if(zoom<15){
  const groups=groupByLocation(eligible).slice(0,250);
  for(const g of groups){
   const html='<div class="cluster-label">'+escapeHTML(g.dong)+'<div>경매 '+g.court+'건'+(g.public?' <em>공매 '+g.public+'건</em>':'')+'</div></div>';
   const m=new nav.Marker({map,position:new nav.LatLng(g.lat,g.lng),title:g.dong+" · 현재 연결된 물건 "+g.count+"건",icon:{content:html,anchor:new nav.Point(45,22)}});
   nav.Event.addListener(m,"click",()=>{map.setCenter(new nav.LatLng(g.lat,g.lng));map.setZoom(16);});state.markers.push(m);
  }
 }else{
  for(const l of eligible.slice(0,300)){
   const html='<div class="lot-pin '+(l.channel==="public"?"public":"")+'">'+(l.channel==="public"?"공매 ":"경매 ")+escapeHTML(price(l.minimum))+'</div>';
   const m=new nav.Marker({map,position:new nav.LatLng(l.lat,l.lng),title:l.title+" · "+(l.coordinateSource||"출처 미확인"),icon:{content:html,anchor:new nav.Point(15,33)}});
   nav.Event.addListener(m,"click",()=>openDetail(l.id));state.markers.push(m);
  }
 }
 $("map-summary").textContent="현재 지도 마커 "+state.markers.length+"개 · 좌표 확보 "+summarize(state.lots).located+"건";
}
function redrawMeasure(){
 if(state.measurePreview){state.measurePreview.setMap(null);state.measurePreview=null;}
 if(!state.mapReady||!state.measure)return;
 const nav=window.naver.maps,pts=state.measurePoints;
 if(state.measure==="distance"&&pts.length>=2){
  state.measurePreview=new nav.Polyline({map:state.map,path:pts,strokeColor:"#196ac9",strokeWeight:4});
  const d=state.measurePreview.getDistance();
  $("measure-result").textContent=d>=1000?(d/1000).toFixed(3)+" km":d.toFixed(1)+" m";
 }else if(state.measure==="area"&&pts.length>=3){
  state.measurePreview=new nav.Polygon({map:state.map,paths:pts,strokeColor:"#11915b",fillColor:"#3fcb91",fillOpacity:.19,strokeWeight:3});
  const a=state.measurePreview.getAreaSize();
  $("measure-result").textContent=a.toFixed(1)+" ㎡ / "+(a/3.305785).toFixed(1)+" 평";
 }else $("measure-result").textContent=pts.length+"개 점 선택";
}
function startMeasure(mode){
 if(!state.mapReady){notice("네이버 지도 연결 후 측정할 수 있습니다.");return;}
 state.measure=mode;state.modePlace=null;state.measurePoints=[];redrawMeasure();
 notice(mode==="distance"?"거리는 지도에 2개 이상 점을 클릭하세요.":"면적은 지도에 3개 이상 점을 클릭하세요. 법적 필지 면적이 아닙니다.");
}
function finishMeasure(){
 if(!state.measurePreview){notice("거리 2개, 면적 3개 이상의 점이 필요합니다.");return;}
 state.measureDone.push(state.measurePreview);state.measurePreview=null;
 state.measurePoints=[];state.measure=null;notice("지도 측정 완료. 법적 필지 경계나 공식 측량 결과는 아닙니다.");
}
function clearMeasure(){
 if(state.measurePreview)state.measurePreview.setMap(null);
 for(const m of state.measureDone)m.setMap(null);
 state.measurePreview=null;state.measureDone=[];state.measurePoints=[];state.measure=null;
 $("measure-result").textContent="측정 대기";
}
function clickMap(p){
 if(state.modePlace){
  const l=state.lots.find(x=>x.id===state.modePlace);
  state.modePlace=null;
  if(l&&p){l.lat=p.lat();l.lng=p.lng();l.coordinateSource="사용자 임시 좌표·공식 위치 미검증";renderAll();void saveIfOpted();notice(l.title+"의 시험 좌표가 지정됐습니다. 실제 소재지 여부를 검증해야 합니다.");}
  return;
 }
 if(state.measure&&p){state.measurePoints.push(p);redrawMeasure();}
}
function sdkAuthFailure(){
 state.lastSDKError="네이버 지도 인증 실패: Dynamic Map 활성화와 Web 서비스 URL을 확인하세요.";
 log("AUTH_FAIL",state.lastSDKError);setSDK(state.lastSDKError);
}
window.navermap_authFailure=sdkAuthFailure;
let sdkLoader=null;
function loadSDK(id){
 if(window.naver?.maps)return Promise.resolve();
 if(sdkLoader)return sdkLoader;
 sdkLoader=new Promise((resolve,reject)=>{
  const script=document.createElement("script");let done=false;
  const finish=err=>{if(done)return;done=true;clearTimeout(timer);if(err)reject(err);else resolve();};
  const timer=setTimeout(()=>finish(Error("SDK 응답 15초 초과")),15000);
  script.src="https://oapi.map.naver.com/openapi/v3/maps.js?ncpKeyId="+encodeURIComponent(id)+"&submodules=geocoder";
  script.referrerPolicy="strict-origin-when-cross-origin";script.async=true;
  script.onload=()=>window.naver?.maps?finish():finish(Error("네이버 SDK 객체가 생성되지 않았습니다."));
  script.onerror=()=>finish(Error("네이버 SDK 네트워크/인증 오류"));
  document.head.appendChild(script);
 }).catch(e=>{sdkLoader=null;throw e;});
 return sdkLoader;
}
async function connectSDK({automatic=false}={}){
 if(state.sdkBusy||state.mapReady)return;
 const id=$("sdk-client-id").value.trim();
 if(!/^[A-Za-z0-9_-]{5,120}$/.test(id)){setSDK("Client ID 형식을 확인하세요. Secret은 입력하지 마세요.");return;}
 state.sdkBusy=true;setSDK(automatic?"저장된 ID로 자동 네이버 지도 연결 중":"네이버 지도 연결 중");log("SDK_START",automatic?"저장된 Client ID 자동 실행":"사용자 명시적 SDK 시작");
 try{
  await loadSDK(id);
  if(state.lastSDKError)throw Error(state.lastSDKError);
  const nav=window.naver.maps;
  $("naver-map").style.display="block";$("map-empty").style.display="none";
  state.map=new nav.Map("naver-map",{center:new nav.LatLng(countryCenter.lat,countryCenter.lng),zoom:12,minZoom:7,maxZoom:21,zoomControl:true,mapDataControl:false});
  state.mapReady=true;
  nav.Event.addListener(state.map,"idle",()=>{drawMarkers();const center=state.map.getCenter();log("MAP_IDLE","Zoom "+state.map.getZoom()+" / 지도 중심 이동");});
  nav.Event.addListener(state.map,"click",evt=>clickMap(evt.coord||evt.latlng));
  setSDK("NAVER SDK 지도 객체 실행됨 · 타일 상태는 화면에서 확인");notice("네이버 지도 연결 · 실제 경매물건 위치는 저장된 좌표가 있는 경우에만 표시됩니다.");
  log("SDK_READY","Map 객체 초기화 및 확대/이동/측정 이벤트 연결");
  if($("sdk-remember").checked){if(!saveClientId(storage(),id))log("STORAGE","브라우저 로컬 ID 저장이 차단됨");}
  else clearClientId(storage());
  if(!automatic)hidePanels();
  renderAll();
 }catch(e){setSDK("지도 연결 실패 · "+String(e.message||e));notice("SDK 연결 오류. 지도 설정/진단에서 원인을 확인하세요.");log("SDK_ERROR",e.message||String(e));$("naver-map").style.display="none";$("map-empty").style.display="flex";}
 finally{state.sdkBusy=false;}
}
function disconnectSDK(){
 clearMarkers();clearMeasure();
 if(state.cadastral)state.cadastral.setMap(null);
 if(state.map){$("naver-map").replaceChildren();state.map=null;}
 state.mapReady=false;$("naver-map").style.display="none";$("map-empty").style.display="flex";
 setSDK("지도 연결 해제됨 · 저장된 Client ID는 유지됩니다.");log("SDK_STOP","현재 지도 객체 종료");
}
function updateMapType(type){
 if(!state.mapReady){notice("지도를 먼저 연결하세요.");return;}
 state.map.setMapTypeId(type==="hybrid"?naver.maps.MapTypeId.HYBRID:naver.maps.MapTypeId.NORMAL);
 $("map-type-normal").classList.toggle("on",type==="normal");$("map-type-satellite").classList.toggle("on",type==="hybrid");
 log("MAPTYPE",type);
}
function toggleCadastral(){
 if(!state.mapReady){notice("지도를 먼저 연결하세요.");return;}
 try{
  if(!state.cadastral)state.cadastral=new naver.maps.CadastralLayer();
  const current=state.cadastral.getMap?.()||null;
  state.cadastral.setMap(current?null:state.map);
  $("map-cadastral").classList.toggle("on",!current);log("CADASTRAL",current?"off":"on");
 }catch(e){notice("지적도 레이어 사용을 확인할 수 없습니다.");log("CADASTRAL_ERR",e.message);}
}
async function loadDb(){
 const file=$("db-file").files?.[0];
 if(!file){$("db-feedback").textContent="이전 v11.4 SQLite 파일을 선택해 주세요.";return;}
 $("db-load").disabled=true;$("db-feedback").textContent="SQLite 파일을 이 브라우저 안에서 읽는 중입니다.";
 try{
  const result=await readV11Sqlite(file),remember=$("db-remember").checked;
  if(remember){await savePrivateSnapshot(result);}else await forgetPrivateSnapshot();
  setLots(result,{remember});$("db-feedback").textContent="SQLite "+result.lots.length+"건 연결. 지도 좌표 "+summarize(result.lots).located+"건";
  changeSection("search");$("data-panel").hidden=true;
 }catch(e){$("db-feedback").textContent="SQLite 오류: "+String(e.message||e);log("SQLITE_FAIL",e.message||String(e));}
 finally{$("db-load").disabled=false;}
}
async function forgetDb(){
 await forgetPrivateSnapshot();
 setLots({lots:[],meta:{name:"자료 미연결",kind:"empty"}},{remember:false});
 $("db-file").value="";$("db-feedback").textContent="이 브라우저의 물건 저장 목록을 삭제했습니다.";
}
async function restoreDb(){
 try{
  const result=await restorePrivateSnapshot();
  if(result?.result){setLots(result.result,{remember:true});$("db-feedback").textContent="저장된 SQLite "+result.result.lots.length+"건 복원 · 사건 원문 재확인 필요";}
 }catch(e){$("db-feedback").textContent="저장된 물건을 복원할 수 없습니다: "+e.message;}
}
async function saveIfOpted(){
 if(!state.rememberDB)return;
 try{await savePrivateSnapshot({lots:state.lots,meta:state.source});}catch(e){log("SAVE_ERR",e.message);}
}
function renderGeoCandidates(){
 $("geocode-review").innerHTML=state.geoReview.length?state.geoReview.map((r,i)=>
 '<div class="geo-review"><b>'+escapeHTML(r.group.query)+'</b><p class="small-note">정확 일치하지 않아 자동 좌표 지정하지 않았습니다.</p>'+
 r.candidates.map((c,j)=>'<p>'+escapeHTML(c.address)+' <button data-geo-group="'+i+'" data-geo-candidate="'+j+'">주소 확인 후 적용</button></p>').join("")+'</div>').join("")
 :'<p class="small-note">주소 불일치 후보 없음</p>';
}
async function geocodeBatch(all=false){
 if(state.geoRunning)return;
 if(!state.mapReady){$("geocode-progress").textContent="먼저 네이버 지도 SDK를 연결하세요.";showPanel("sdk");return;}
 if(!window.naver?.maps?.Service?.geocode){$("geocode-progress").textContent="Geocoder 서브모듈이 없습니다. 신규 Maps Geocoding 상품 활성화와 SDK 로딩을 확인하세요.";return;}
 const groups=planGeocodeRequests(state.lots,state.geoAttempted,all);
 if(!groups.length){$("geocode-progress").textContent="조회할 새로운 지번이 없습니다.";return;}
 if(!confirm("네이버 Geocoding API에 고유 지번 "+groups.length+"개를 순차 조회합니다. 요청량·요금이 발생할 수 있습니다. 진행할까요?"))return;
 const gen=state.latestLoaded;state.geoRunning=true;state.geoStop=false;
 let sent=0,located=0,review=0,errors=0,stopReason="";
 try{
  for(const group of groups){
   if(state.geoStop||state.latestLoaded!==gen){stopReason="중단 요청 또는 데이터 변경";break;}
   state.geoAttempted.add(group.query);
   recordLocalGeocodeRequest(storage());renderQuota();sent++;
   $("geocode-progress").textContent="주소변환 "+sent+"/"+groups.length+" · "+group.query;
   try{
    const answer=await geocodeWithSdk(naver.maps,group.query);
    if(state.latestLoaded!==gen){stopReason="데이터가 변경되어 결과 미적용";break;}
    if(answer.status==="exact")located+=applyGeocodedPoint(state.lots,group,answer.point);
    else if(answer.status==="review"){state.geoReview.push({group,candidates:answer.candidates});review++;}
    else errors++;
   }catch(e){stopReason=e.message||String(e);errors++;break;}
   if(sent<groups.length)await new Promise(r=>setTimeout(r,350));
  }
 }finally{
  state.geoRunning=false;renderAll();await saveIfOpted();
  $("geocode-progress").textContent="API 요청 "+sent+"회 · 물건 좌표 "+located+"건 적용 · 후보 확인 "+review+"곳 · 결과없음/오류 "+errors+"건"+(stopReason?" · "+stopReason:"")+" · 지번 대표점(공식 위치 미검증)";
 }
}
async function applyCandidate(i,j){
 const r=state.geoReview[i],candidate=r?.candidates[j];if(!r||!candidate)return;
 if(!confirm("이 후보 주소가 실제 해당 경매 물건의 지번과 일치하는지 확인했습니까? 지도 대표점이며 공식 지적 좌표가 아닙니다."))return;
 const count=applyGeocodedPoint(state.lots,r.group,candidate,"manual");
 state.geoReview.splice(i,1);renderAll();await saveIfOpted();
 $("geocode-progress").textContent="사용자 확인 좌표 "+count+"건 적용 · 사건 주소 및 필지 정확도 별도 검증 필요";
}
function exportData(){
 if(!state.lots.length){$("geocode-progress").textContent="내보낼 목록이 없습니다.";return;}
 const blob=new Blob([exportLocalLots(state.lots,state.source)],{type:"application/json"});
 const u=URL.createObjectURL(blob),a=document.createElement("a");
 a.href=u;a.download="auction-v11-local-lots.json";a.click();setTimeout(()=>URL.revokeObjectURL(u),2000);
}
function saveDiagnostic(){
 const diag={generatedAt:new Date().toISOString(),project:"auction-v11-classic",originKind:location.hostname==="localhost"?"local":"published",sdkLoaded:!!window.naver?.maps,mapReady:state.mapReady,lotCount:state.lots.length,located:summarize(state.lots).located,events:state.logs.slice(-100)};
 const blob=new Blob([JSON.stringify(diag,null,2)],{type:"application/json"}),u=URL.createObjectURL(blob),a=document.createElement("a");
 a.href=u;a.download="auction_map_debug_"+new Date().toISOString().slice(0,10)+".json";a.click();setTimeout(()=>URL.revokeObjectURL(u),2000);
}
function wire(){
 document.querySelectorAll("[data-section]").forEach(el=>el.addEventListener("click",()=>changeSection(el.dataset.section)));
 document.querySelectorAll("[data-mode]").forEach(el=>el.addEventListener("click",()=>setMapMode(el.dataset.mode)));
 $("panel-fold").onclick=()=>{document.querySelector(".app").classList.toggle("collapsed");$("panel-fold").textContent=document.querySelector(".app").classList.contains("collapsed")?"›":"‹";};
 $("toggle-search").onclick=()=>{changeSection("search");$("search-input").focus();};
 $("search-submit").onclick=()=>changeSection("search");
 $("search-input").addEventListener("input",renderResults);
 $("kind-filter").onchange=renderResults;$("sort-filter").onchange=renderResults;
 $("filter-reset").onclick=()=>{$("search-input").value="";$("kind-filter").value="all";$("sort-filter").value="date";state.favoriteOnly=false;renderResults();};
 $("show-only-fav").onclick=()=>{state.favoriteOnly=!state.favoriteOnly;$("show-only-fav").textContent=state.favoriteOnly?"★ 관심만 보는 중":"☆ 관심만 보기";renderResults();};
 $("data-toggle").onclick=()=>$("data-panel").hidden=!$("data-panel").hidden;
 $("data-open").onclick=()=>$("data-panel").hidden=false;
 $("results").addEventListener("click",e=>{
  const b=e.target.closest("[data-action]");if(!b)return;
  const id=b.dataset.id,action=b.dataset.action,l=state.lots.find(x=>x.id===id);
  if(action==="detail")openDetail(id);else if(action==="fav")updateFavorites(id);else if(action==="on-map")focusLot(l);
 });
 $("db-load").onclick=loadDb;$("db-disconnect").onclick=()=>void forgetDb();
 $("sdk-settings").onclick=()=>{showPanel("sdk");$("sdk-client-id").focus();};
 $("map-setup").onclick=()=>{showPanel("sdk");$("sdk-client-id").focus();};
 $("sdk-close").onclick=hidePanels;
 $("sdk-connect").onclick=()=>void connectSDK();
 $("sdk-disconnect").onclick=disconnectSDK;
 $("sdk-forget").onclick=()=>{clearClientId(storage());$("sdk-client-id").value="";$("sdk-remember").checked=false;setSDK("저장된 ID 삭제 · 다음 방문 자동 연결 해제. 현재 지도는 별도로 중단할 수 있습니다.");};
 $("diagnose").onclick=()=>{const m=state.mapReady?state.map.getCenter():null;log("CHECK","SDK 객체 "+!!window.naver?.maps+" / map="+state.mapReady+" / center="+(m?"present":"none")+" / 물건 DB="+state.lots.length);setSDK("자체 점검 기록 완료 · 아래 로그 확인");};
 $("download-diagnostics").onclick=saveDiagnostic;
 $("logs-clear").onclick=()=>{state.logs=[];$("debug-logs").textContent="진단 로그 삭제";};
 $("place-mode").onclick=()=>{if(!state.mapReady){setSDK("먼저 네이버 지도 연결 필요");return;}const id=$("place-case").value;if(!id)return;state.measure=null;state.modePlace=id;hidePanels();notice("실제 지도에서 임시 물건 위치를 클릭하세요. 법적 위치 검증 전입니다.");};
 $("map-home").onclick=()=>{if(state.mapReady){state.map.setCenter(new naver.maps.LatLng(countryCenter.lat,countryCenter.lng));state.map.setZoom(12);}};
 $("map-type-normal").onclick=()=>updateMapType("normal");
 $("map-type-satellite").onclick=()=>updateMapType("hybrid");
 $("map-cadastral").onclick=toggleCadastral;
 $("zoom-plus").onclick=()=>{if(state.mapReady)state.map.setZoom(Math.min(21,state.map.getZoom()+1));};
 $("zoom-minus").onclick=()=>{if(state.mapReady)state.map.setZoom(Math.max(7,state.map.getZoom()-1));};
 $("distance-mode").onclick=()=>startMeasure("distance");
 $("area-mode").onclick=()=>startMeasure("area");
 $("measure-done").onclick=finishMeasure;
 $("measure-clear").onclick=clearMeasure;
 $("usage-settings").onclick=()=>{renderQuota();showPanel("usage");};
 $("usage-close").onclick=hidePanels;
 $("quota-form").onsubmit=e=>{e.preventDefault();try{
  const r=buildQuotaSnapshot($("used-map").value,$("used-geo").value);
  if(!saveQuotaSnapshot(storage(),r))throw Error("브라우저 저장소 접근 불가");
  renderQuota();$("quota-feedback").textContent="네이버 콘솔 수동 입력 시점의 잔여량으로 계산했습니다. 실시간 수치가 아닙니다.";
 }catch(x){$("quota-feedback").textContent="입력 오류: "+x.message;}};
 $("quota-forget").onclick=()=>{deleteQuotaSnapshot(storage());renderQuota();};
 $("show-db-panel").onclick=()=>showPanel("data-map");$("db-map-close").onclick=hidePanels;
 $("geocode-batch").onclick=()=>void geocodeBatch(false);
 $("geocode-all").onclick=()=>void geocodeBatch(true);
 $("geocode-stop").onclick=()=>{state.geoStop=true;$("geocode-progress").textContent="중단 요청됨 · 전송된 현재 요청이 완료되면 종료합니다.";};
 $("geocode-review").onclick=e=>{const b=e.target.closest("[data-geo-group]");if(b)void applyCandidate(Number(b.dataset.geoGroup),Number(b.dataset.geoCandidate));};
 $("export-data").onclick=exportData;
 $("detail-close").onclick=()=>$("detail-dialog").close();
 window.addEventListener("resize",()=>{if(state.mapReady)naver.maps.Event.trigger(state.map,"resize");});
 window.addEventListener("storage",e=>{
  if(e.key==="auction-lab-v11-maps-public-id"&&!state.mapReady){
   const key=readClientId(storage());if(key)$("sdk-client-id").value=key;
  }
 });
}
async function init(){
 wire();renderAll();renderQuota();$("sdk-remember").checked=true;
 changeSection("map");await restoreDb();
 const id=readClientId(storage());
 if(id){$("sdk-client-id").value=id;$("sdk-remember").checked=true;void connectSDK({automatic:true});}
 else log("INIT","저장된 Client ID 없음. 지도 설정에서 입력 가능");
}
void init();
