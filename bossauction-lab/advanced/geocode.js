// Client-side, explicitly requested NAVER Maps Geocoder queries.
// SDK: maps.js?ncpKeyId=...&submodules=geocoder (never use Client Secret).
// A result point is an address reference point, not a surveyed parcel boundary.
const MAX_CANDIDATES=5;
export const MAX_GEOCODE_PER_CLICK=5;
export const MAX_GEOCODE_ALL=25;
export function normalizedAddress(v){
 return String(v??"").replace(/\s+/g," ").trim().replace(/\s*[,，]\s*$/,"");
}
export function parcelQuery(address){
 const s=normalizedAddress(address);
 // Keep legal dong/ri + exact lot number. Discard building/floor/unit descriptions.
 // This deliberately declines broader address guesses when no parcel address exists.
 const hit=s.match(/^(.*?(?:동|리|가)\s+(?:산\s*)?\d{1,6}(?:-\d{1,6})?)(?:\s|$)/u);
 if(!hit)return null;
 const q=normalizedAddress(hit[1]);
 if(q.length<12||q.length>180||!q.includes(" "))return null;
 return q;
}
export function getUnlocatedGroups(lots,attempted=new Set()){
 const groups=new Map();
 for(const lot of lots||[]){
  if(lot.lat!==null&&lot.lat!==undefined)continue;
  const query=parcelQuery(lot.location);
  if(!query||attempted.has(query))continue;
  if(!groups.has(query))groups.set(query,{query,ids:[]});
  groups.get(query).ids.push(lot.id);
 }
 return [...groups.values()];
}
export function planGeocodeRequests(lots,attempted,all=false){
 return getUnlocatedGroups(lots,attempted).slice(0,all?MAX_GEOCODE_ALL:MAX_GEOCODE_PER_CLICK);
}
function validPoint(x,y){
 const lng=Number(x),lat=Number(y);
 return Number.isFinite(lat)&&Number.isFinite(lng)&&lat>=32&&lat<=39&&lng>=124&&lng<=132;
}
export function classifyGeocodeResponse(response,query){
 const items=response?.v2?.addresses;
 if(!Array.isArray(items))throw Error("네이버 Geocoding 응답 구조를 확인할 수 없습니다.");
 const q=normalizedAddress(query);
 const candidates=items.slice(0,MAX_CANDIDATES).filter(x=>validPoint(x?.x,x?.y)).map(x=>({
  address:normalizedAddress(x.jibunAddress||x.roadAddress),
  jibunAddress:normalizedAddress(x.jibunAddress),
  roadAddress:normalizedAddress(x.roadAddress),
  lat:Number(x.y),lng:Number(x.x)
 }));
 if(!candidates.length)return {status:"not-found",candidates:[]};
 const exact=candidates.filter(c=>c.jibunAddress===q||c.roadAddress===q||parcelQuery(c.jibunAddress)===q);
 if(exact.length===1)return {status:"exact",point:exact[0],candidates};
 return {status:"review",candidates}; // Never auto-select ambiguous results.
}
export function applyGeocodedPoint(lots,group,point,method="exact"){
 if(!group||!Array.isArray(group.ids)||!group.query||!validPoint(point?.lng,point?.lat))throw Error("좌표 적용 대상이 올바르지 않습니다.");
 const source=method==="exact"
  ?"NAVER Geocoding·지번 정확 일치(대표점·미검증)"
  :"NAVER Geocoding·사용자 후보 선택(대표점·미검증)";
 const allowed=new Set(group.ids);
 let changed=0;
 for(const lot of lots){
  if(!allowed.has(lot.id)||parcelQuery(lot.location)!==group.query)continue;
  if(lot.lat!==null&&lot.lat!==undefined)continue;
  lot.lat=Number(point.lat);lot.lng=Number(point.lng);
  lot.coordinateSource=source;
  changed++;
 }
 return changed;
}
export function geocodeWithSdk(maps,query){
 if(!maps?.Service?.geocode||!maps.Service.Status)throw Error("네이버 Geocoder 모듈이 없습니다. 지도 연결 후 새로고침하여 다시 실행하세요.");
 return new Promise((resolve,reject)=>{
  let settled=false;
  const timeout=setTimeout(()=>{if(!settled){settled=true;reject(Error("Geocoding 응답 시간 초과"));}},12000);
  try{
   maps.Service.geocode({query},(status,response)=>{
    if(settled)return;
    settled=true;clearTimeout(timeout);
    if(status!==maps.Service.Status.OK){
     reject(Error("네이버 Geocoding 요청 실패(인증·할당량·API 상품 확인 필요)"));
     return;
    }
    try{resolve(classifyGeocodeResponse(response,query));}catch(e){reject(e);}
   });
  }catch(e){if(!settled){settled=true;clearTimeout(timeout);reject(e);}}
 });
}
