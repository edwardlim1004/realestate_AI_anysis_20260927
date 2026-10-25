// NAVER Cloud Maps published monthly free allowances (representative account).
// Actual account usage is NOT accessible with the public browser Client ID.
// The user must enter total usage for all Applications from NAVER Cloud Console.
export const FREE_DYNAMIC_MAP=6_000_000;
export const FREE_GEOCODING=3_000_000;
export const CLIENT_ID_STORAGE_KEY="auction-lab-v11-maps-public-id";
export const QUOTA_STORAGE_KEY="auction-lab-v11-maps-console-usage";
export const LOCAL_GEO_CALLS_KEY="auction-lab-v11-geocoder-local-requests";
const CLIENT_PATTERN=/^[A-Za-z0-9_-]{5,120}$/;

export function validClientId(id){return typeof id==="string"&&CLIENT_PATTERN.test(id);}
export function readClientId(storage){
 try{const id=storage?.getItem(CLIENT_ID_STORAGE_KEY);return validClientId(id)?id:null;}catch{return null;}
}
export function saveClientId(storage,id){
 if(!validClientId(id))throw Error("Client ID 형식이 올바르지 않습니다.");
 try{storage.setItem(CLIENT_ID_STORAGE_KEY,id);return true;}catch{return false;}
}
export function clearClientId(storage){
 try{storage?.removeItem(CLIENT_ID_STORAGE_KEY);return true;}catch{return false;}
}
export function koreaMonth(at=new Date()){
 if(!(at instanceof Date)||!Number.isFinite(at.getTime()))throw Error("유효하지 않은 시간");
 const parts=new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Seoul",year:"numeric",month:"2-digit"}).formatToParts(at);
 const y=parts.find(p=>p.type==="year")?.value,m=parts.find(p=>p.type==="month")?.value;
 return y+"-"+m;
}
export function validateUsage(input){
 // Empty means unknown, NOT zero. Billing is aggregated over all applications.
 if(input===null||input===undefined||input==="")return null;
 if(typeof input!=="string"&&typeof input!=="number")throw Error("사용량은 정수로 입력하세요.");
 if(!/^\d+$/.test(String(input)))throw Error("사용량은 0 이상의 정수로 입력하세요.");
 const n=Number(input);
 if(!Number.isSafeInteger(n)||n<0||n>1_000_000_000_000)throw Error("사용량이 허용 범위를 벗어났습니다.");
 return n;
}
export function buildQuotaSnapshot(mapInput,geoInput,date=new Date()){
 const map=validateUsage(mapInput),geocoding=validateUsage(geoInput);
 if(map===null&&geocoding===null)throw Error("지도 또는 주소변환의 당월 사용량을 하나 이상 입력하세요.");
 return {version:1,month:koreaMonth(date),capturedAt:date.toISOString(),used:{map,geocoding},source:"manual-console-account-total"};
}
export function remainingUsage(free,used){
 if(used===null||used===undefined)return null;
 return Math.max(0,free-used);
}
export function quotaOverview(snapshot,date=new Date()){
 const month=koreaMonth(date);
 const valid=snapshot?.version===1&&snapshot?.source==="manual-console-account-total"&&snapshot?.month===month;
 const map=valid?validateUsage(snapshot.used?.map):null;
 const geocoding=valid?validateUsage(snapshot.used?.geocoding):null;
 return {month,valid,stale:!!snapshot&&!valid,updatedAt:valid?snapshot.capturedAt:null,
  map:{free:FREE_DYNAMIC_MAP,used:map,remaining:remainingUsage(FREE_DYNAMIC_MAP,map)},
  geocoding:{free:FREE_GEOCODING,used:geocoding,remaining:remainingUsage(FREE_GEOCODING,geocoding)}};
}
export function readQuotaSnapshot(storage){
 try{
  const obj=JSON.parse(storage?.getItem(QUOTA_STORAGE_KEY)||"null");
  return obj?.version===1&&obj?.source==="manual-console-account-total"?obj:null;
 }catch{return null;}
}
export function saveQuotaSnapshot(storage,snapshot){
 try{storage.setItem(QUOTA_STORAGE_KEY,JSON.stringify(snapshot));return true;}catch{return false;}
}
export function deleteQuotaSnapshot(storage){
 try{storage.removeItem(QUOTA_STORAGE_KEY);return true;}catch{return false;}
}
export function localGeocodeRequests(storage,date=new Date()){
 try{
  const obj=JSON.parse(storage?.getItem(LOCAL_GEO_CALLS_KEY)||"null");
  return obj?.month===koreaMonth(date)&&Number.isSafeInteger(obj.calls)&&obj.calls>=0?obj.calls:0;
 }catch{return 0;}
}
export function recordLocalGeocodeRequest(storage,date=new Date()){
 const count=localGeocodeRequests(storage,date)+1;
 try{storage?.setItem(LOCAL_GEO_CALLS_KEY,JSON.stringify({month:koreaMonth(date),calls:count}));}catch{}
 return count;
}
