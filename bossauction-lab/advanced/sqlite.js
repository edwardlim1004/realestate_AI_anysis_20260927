/* User-selected SQLite is parsed only in this browser.
   Never upload a DB, key, or copied listing data to the public repository. */
import {parseImport} from "./core.js";

export const SQLITE_MAX_BYTES=25*1024*1024;
export const SQLITE_MAX_ROWS=10000;
const SQLITE_JS="https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.13.0/sql-wasm.min.js";
const SQLITE_WASM="https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.13.0/sql-wasm.wasm";
const DATABASE_NAME="auction-lab-v11-private";
const STORAGE_KEY="user-local-sqlite-items";
let sqlitePromise=null;

export function convertV11Rows(rows,{filename="auction_v11.sqlite3",recordDate=""}={}){
 if(!Array.isArray(rows)||rows.length>SQLITE_MAX_ROWS)throw Error("SQLite 물건은 최대 10,000건까지 읽을 수 있습니다.");
 if(!rows.length)throw Error("DB의 items 테이블에 물건이 없습니다.");
 const lots=rows.map((r,i)=>{
  if(!r||typeof r!=="object")throw Error("DB의 "+(i+1)+"번째 행 오류");
  if(r.kind!=="auction"&&r.kind!=="public")throw Error("지원하지 않는 물건 구분: "+String(r.kind));
  const location=String(r.address||"");
  return {
   id:r.id,channel:r.kind==="auction"?"court":"public",
   title:r.case_no||r.id,region:location.trim().split(/\s+/)[0]||"",
   type:r.subtype||"",location,authority:r.court||"",
   appraisal:r.appraisal,minimum:r.min_price,
   date:r.sale_date||"",failures:r.fail_count??0,
   lat:r.lat,lng:r.lng,coordinateSource:r.location_source,
   sourceUrl:r.source_url||null
  };
 });
 const validDate=/^\d{4}-\d{2}-\d{2}$/.test(String(recordDate))?recordDate:"날짜 미확인";
 const sourceName="로컬 SQLite ("+filename.slice(0,100)+") · 저장본 기준일 "+validDate+" · 미검증";
 const result=parseImport(JSON.stringify({sourceName,collectedAt:validDate==="날짜 미확인"?null:validDate,lots}),filename);
 result.meta.kind="sqlite-local";
 result.meta.asOf=validDate;
 result.meta.name=sourceName;
 return result;
}
export function hasSQLiteHeader(buffer){
 const bytes=buffer instanceof Uint8Array?buffer:new Uint8Array(buffer);
 if(bytes.byteLength<100)return false;
 const signature="SQLite format 3\u0000";
 for(let i=0;i<16;i++)if(bytes[i]!==signature.charCodeAt(i))return false;
 return true;
}
function sqlEngine(){
 if(sqlitePromise)return sqlitePromise;
 sqlitePromise=new Promise((resolve,reject)=>{
  if(typeof window.initSqlJs==="function"){resolve(window.initSqlJs);return;}
  const script=document.createElement("script");
  script.async=true;
  script.src=SQLITE_JS;
  script.crossOrigin="anonymous";
  script.onload=()=>typeof window.initSqlJs==="function"?resolve(window.initSqlJs):reject(Error("SQLite 모듈이 초기화되지 않았습니다."));
  script.onerror=()=>reject(Error("SQLite WASM 라이브러리를 불러오지 못했습니다. 인터넷/CDN 차단 여부를 확인하세요."));
  document.head.appendChild(script);
 }).then(factory=>factory({locateFile:()=>SQLITE_WASM})).catch(error=>{sqlitePromise=null;throw error;});
 return sqlitePromise;
}
export async function readV11Sqlite(file){
 if(!file||typeof file.arrayBuffer!=="function")throw Error("SQLite DB 파일을 선택하세요.");
 if(file.size>SQLITE_MAX_BYTES||file.size<100)throw Error("SQLite 파일은 25MB 이하여야 합니다.");
 const buffer=new Uint8Array(await file.arrayBuffer());
 if(!hasSQLiteHeader(buffer))throw Error("SQLite 데이터베이스 파일이 아닙니다.");
 const SQL=await sqlEngine();
 let db=null;
 try{
  db=new SQL.Database(buffer);
  const cols=db.exec("PRAGMA table_info(items)")[0]?.values.map(row=>String(row[1]))||[];
  const needed=["id","kind","case_no","address","subtype","court","appraisal","min_price","fail_count","sale_date","lat","lng","location_source","source_url","record_date"];
  if(needed.some(col=>!cols.includes(col)))throw Error("v11.4의 items 테이블 구조와 다릅니다. 지원하는 경매 DB인지 확인하세요.");
  const data=db.exec("SELECT id,kind,case_no,address,subtype,court,appraisal,min_price,fail_count,sale_date,lat,lng,location_source,source_url FROM items ORDER BY id LIMIT 10001")[0];
  const rows=data?data.values.map(a=>Object.fromEntries(data.columns.map((col,i)=>[col,a[i]]))):[];
  if(rows.length>SQLITE_MAX_ROWS)throw Error("SQLite 물건이 10,000건을 초과합니다. DB를 나누어 사용하세요.");
  const asOf=db.exec("SELECT MAX(record_date) AS latest FROM items")[0]?.values[0]?.[0]||"";
  return convertV11Rows(rows,{filename:file.name||"auction_v11.sqlite3",recordDate:asOf});
 }catch(e){
  if(/malformed|not a database|file is encrypted/i.test(String(e.message)))throw Error("SQLite 파일을 읽을 수 없습니다. DB가 손상됐거나 지원하지 않는 파일입니다.");
  throw e;
 }finally{if(db)db.close();}
}
function openStorage(){
 if(typeof indexedDB==="undefined")return Promise.reject(Error("이 브라우저는 IndexedDB 저장을 지원하지 않습니다."));
 return new Promise((resolve,reject)=>{
  const req=indexedDB.open(DATABASE_NAME,1);
  req.onupgradeneeded=()=>{if(!req.result.objectStoreNames.contains("snapshots"))req.result.createObjectStore("snapshots");};
  req.onerror=()=>reject(req.error||Error("로컬 저장소를 열 수 없습니다."));
  req.onsuccess=()=>resolve(req.result);
 });
}
async function storageOperation(mode,verb,value){
 const db=await openStorage();
 return new Promise((resolve,reject)=>{
  const tx=db.transaction("snapshots",mode),store=tx.objectStore("snapshots");
  const req=verb==="get"?store.get(STORAGE_KEY):verb==="put"?store.put(value,STORAGE_KEY):store.delete(STORAGE_KEY);
  let retrieved;
  req.onsuccess=()=>{if(verb==="get")retrieved=req.result;};
  tx.oncomplete=()=>{db.close();resolve(retrieved);};
  tx.onerror=()=>{db.close();reject(tx.error||Error("로컬 DB 저장 실패"));};
  tx.onabort=()=>{db.close();reject(tx.error||Error("로컬 DB 저장 중단"));};
 });
}
export async function savePrivateSnapshot(result){
 if(!result?.lots||result.lots.length>SQLITE_MAX_ROWS)throw Error("저장할 자료가 너무 많습니다.");
 return storageOperation("readwrite","put",{version:1,meta:result.meta,lots:result.lots,savedAt:new Date().toISOString()});
}
export async function restorePrivateSnapshot(){
 const obj=await storageOperation("readonly","get");
 if(!obj)return null;
 if(obj.version!==1||!Array.isArray(obj.lots))throw Error("저장된 DB 형식이 오래됐습니다. 삭제 후 다시 선택하세요.");
 const parsed=parseImport(JSON.stringify({sourceName:obj.meta?.name||"브라우저 저장 SQLite",collectedAt:obj.meta?.asOf||null,lots:obj.lots}),"stored-sqlite");
 parsed.meta={...parsed.meta,...obj.meta,kind:"sqlite-local",verified:false};
 return {result:parsed,savedAt:obj.savedAt};
}
export async function forgetPrivateSnapshot(){
 return storageOperation("readwrite","delete");
}
