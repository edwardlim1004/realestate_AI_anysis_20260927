// Independent static Pages data utilities. No BossAuction proprietary data/API.
export const EMPTY_SOURCE="사용자 자료 미연결";
export const FORMAT_VERSION=1;
export const COLUMNS=["id","channel","title","region","type","location","authority","appraisal","minimum","date","failures","area","lat","lng","coordinateSource","sourceUrl"];
const MAX_BYTES=8*1024*1024, MAX_ROWS=10000;
const text=(v,n=240)=>String(v??"").trim().slice(0,n);
const numeric=(v)=>v==null||v===""?null:Number(String(v).replace(/,/g,""));
export const escapeHTML=(s)=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
export const price=(n)=>Number.isFinite(n)?(n>=100000000?(n/100000000).toLocaleString("ko-KR",{maximumFractionDigits:2})+"억":(n/10000).toLocaleString("ko-KR",{maximumFractionDigits:0})+"만")+"원":"미제공";
export const pct=(l)=>Number.isFinite(l.appraisal)&&l.appraisal>0&&Number.isFinite(l.minimum)?(100*(1-l.minimum/l.appraisal)).toFixed(1)+"%":"—";
export const dateOK=(d)=>/^\d{4}-\d{2}-\d{2}$/.test(d)&&new Date(d+"T00:00:00Z").toISOString().slice(0,10)===d;
export function csvRows(input){
 const out=[];let row=[],cell="",inQuote=false;
 for(let i=0;i<input.length;i++){const c=input[i];
  if(c==='"'){if(inQuote&&input[i+1]==='"'){cell+='"';i++;}else inQuote=!inQuote;}
  else if(c===','&&!inQuote){row.push(cell);cell="";}
  else if((c==='\n'||c==='\r')&&!inQuote){if(c==='\r'&&input[i+1]==='\n')i++;row.push(cell);if(row.some(s=>s.trim()))out.push(row);row=[];cell="";}
  else cell+=c;
 }
 if(inQuote)throw Error("CSV 따옴표가 닫히지 않았습니다.");
 row.push(cell);if(row.some(s=>s.trim()))out.push(row);
 return out;
}
const MAP={
 id:["id","물건ID","물건아이디","사건번호","사건ID","source_id"],
 channel:["channel","kind","auctionType","구분","경공매","유형구분"],
 title:["title","물건명","사건명","명칭"],
 region:["region","지역","시도","시도명"],
 type:["type","물건유형","용도","물건용도"],
 location:["location","소재지","주소","address"],
 authority:["authority","법원","기관","집행기관"],
 appraisal:["appraisal","감정가","감정가_원","감정평가액"],
 minimum:["minimum","최저가","최저가_원","최저입찰가","최저매각가격"],
 date:["date","기일","매각기일","입찰일","sale_date"],
 failures:["failures","유찰","유찰횟수","유찰_회"],
 area:["area","면적","전용면적","건물면적"],
 lat:["lat","latitude","위도"],lng:["lng","longitude","경도"],
 coordinateSource:["coordinateSource","좌표출처","location_source"],
 sourceUrl:["sourceUrl","원문링크","원문URL","source_url"]
};
function normalizeRecord(raw,i){
 if(!raw||typeof raw!=="object"||Array.isArray(raw))throw Error(i+"번째 행이 객체가 아닙니다.");
 const get=(k)=>MAP[k].map(n=>raw[n]).find(v=>v!==undefined&&v!==null&&String(v).trim()!=="");
 const id=text(get("id"),100);
 if(!id||!(/^[\p{L}\p{N}_.:() -]{1,100}$/u.test(id)))throw Error(i+"번째 물건 ID 오류");
 const ch=text(get("channel"),32).toLowerCase();
 const channel=/^(public|공매|onbid|sale)$/.test(ch)?"public":/^(court|auction|경매|법원경매)$/.test(ch)?"court":null;
 if(!channel)throw Error(id+": 경공매 구분은 court/public 또는 경매/공매이어야 합니다.");
 const date=text(get("date"),20).replaceAll(".","-").replace(/-$/,"");
 if(date&&!dateOK(date))throw Error(id+": 기일은 YYYY-MM-DD 형식입니다.");
 const appraisal=numeric(get("appraisal")),minimum=numeric(get("minimum"));
 if((appraisal!==null&&(!Number.isFinite(appraisal)||appraisal<0))||(minimum!==null&&(!Number.isFinite(minimum)||minimum<0)))throw Error(id+": 가격이 올바르지 않습니다.");
 const lat=numeric(get("lat")),lng=numeric(get("lng"));
 if((lat===null)!==(lng===null))throw Error(id+": 위도·경도는 모두 입력해야 합니다.");
 if(lat!==null&&(!Number.isFinite(lat)||!Number.isFinite(lng)||lat<32||lat>39||lng<124||lng>132))throw Error(id+": 대한민국 범위의 좌표가 아닙니다.");
 let sourceUrl=null;const inputUrl=get("sourceUrl");
 if(inputUrl){const u=new URL(String(inputUrl));if(u.protocol!=="https:"||u.username||u.password)throw Error(id+": 원문 링크는 https만 허용합니다.");sourceUrl=u.href;}
 const failures=numeric(get("failures"))??0,area=numeric(get("area"))??null;
 if(!Number.isInteger(failures)||failures<0||failures>100||(area!==null&&(!Number.isFinite(area)||area<0)))throw Error(id+": 유찰 횟수/면적 오류");
 return {id,channel,title:text(get("title"))||id,region:text(get("region"),60),type:text(get("type"),70),location:text(get("location")),authority:text(get("authority"),80),appraisal,minimum,date,failures,area,lat,lng,coordinateSource:lat===null?null:(text(get("coordinateSource"),90)||"출처 미확인"),sourceUrl};
}
export function parseImport(source,filename="import"){
 if(typeof source!=="string"||new TextEncoder().encode(source).length>MAX_BYTES)throw Error("8MB 이하 파일을 사용하세요.");
 let input,raw,sourceName=filename,asOf=null;
 if(/^\s*[\[{]/.test(source)){
  try{input=JSON.parse(source);}catch{throw Error("JSON을 파싱할 수 없습니다.");}
  if(Array.isArray(input))raw=input;
  else if(input&&Array.isArray(input.lots)){raw=input.lots;sourceName=text(input.sourceName||filename,150);asOf=input.collectedAt||null;}
  else throw Error("JSON은 lots 배열을 포함해야 합니다.");
 }else{
  const [head,...rows]=csvRows(source.replace(/^\uFEFF/,""));
  if(!head||!head.length)throw Error("CSV 헤더가 없습니다.");
  raw=rows.map(row=>Object.fromEntries(head.map((key,j)=>[key.trim(),row[j]??""])));
 }
 if(!raw.length||raw.length>MAX_ROWS)throw Error("1~10,000건의 자료만 가져올 수 있습니다.");
 const seen=new Set();
 const lots=raw.map((x,i)=>{const item=normalizeRecord(x,i+1);if(seen.has(item.id))throw Error("중복 ID "+item.id);seen.add(item.id);return item;});
 return {lots,meta:{name:sourceName,asOf,importedAt:new Date().toISOString(),count:lots.length,kind:"user-supplied",verified:false}};
}
export function filterLots(lots,f={}){
 const keyword=String(f.q||"").trim().toLocaleLowerCase("ko-KR");
 return lots.filter(l=>(!keyword||[l.id,l.title,l.location,l.region,l.authority].join(" ").toLocaleLowerCase("ko-KR").includes(keyword))
 &&(!f.channel||f.channel==="all"||l.channel===f.channel)
 &&(!f.region||f.region==="all"||l.region===f.region)
 &&(!f.type||f.type==="all"||l.type===f.type)
 &&(!f.favoritesOnly||f.saved?.has(l.id))
 &&(!f.dateFrom||!l.date||l.date>=f.dateFrom)
 &&(!f.dateTo||!l.date||l.date<=f.dateTo)
 ).sort((a,b)=>f.sort==="price"?(a.minimum??Infinity)-(b.minimum??Infinity):f.sort==="discount"?((Number(b.appraisal)>0&&b.minimum!==null?(1-b.minimum/b.appraisal):-1)-(Number(a.appraisal)>0&&a.minimum!==null?(1-a.minimum/a.appraisal):-1)):(a.date||"9999").localeCompare(b.date||"9999"));
}
export function inViewport(lot,bounds){
 if(!bounds||lot.lat===null||lot.lng===null)return false;
 return lot.lat>=bounds.south&&lot.lat<=bounds.north&&lot.lng>=bounds.west&&lot.lng<=bounds.east;
}
export function costScenario({bid,feePercent=1.1,extra=0,resale=0,depositPercent=10}){
 const vals=[bid,feePercent,extra,resale,depositPercent].map(Number);
 if(vals.some(x=>!Number.isFinite(x)||x<0)||bid<=0||feePercent>100||depositPercent>100)throw Error("입찰 가정값을 확인하세요.");
 return {deposit:bid*depositPercent/100,balance:bid*(1-depositPercent/100),fee:bid*feePercent/100,total:bid*(1+feePercent/100)+extra,difference:resale-(bid*(1+feePercent/100)+extra)};
}
export function safeStoredIDs(raw){try{const ids=JSON.parse(raw);return new Set(Array.isArray(ids)?ids.filter(x=>typeof x==="string"&&x.length<110):[]);}catch{return new Set();}}
export const MAX_IMPORT_BYTES=MAX_BYTES;
