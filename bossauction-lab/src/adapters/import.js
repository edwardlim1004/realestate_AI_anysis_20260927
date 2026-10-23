const MAX_BYTES=2*1024*1024;
export const MAX_FILE_BYTES=MAX_BYTES;
function str(v,key,max=220){if(typeof v!=="string"||!v.trim()||v.length>max)throw Error(key+" 문자열 형식 오류");return v.trim();}
function num(v,key,min=0,max=1e15){if(typeof v!=="number"||!Number.isFinite(v)||v<min||v>max)throw Error(key+" 숫자 범위 오류");return v;}
function dateOK(d){return typeof d==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(d)&&!Number.isNaN(new Date(d+"T00:00:00Z").valueOf())&&new Date(d+"T00:00:00Z").toISOString().slice(0,10)===d;}
function secureLink(s){if(s==null||s==="")return null;let u;try{u=new URL(str(s,"sourceUrl",1000));}catch{throw Error("원문 링크 URL 오류");}if(u.protocol!=="https:"||u.username||u.password)throw Error("원문 링크는 https만 허용");return u.href;}
export function parseDataset(text){
 if(typeof text!=="string"||new TextEncoder().encode(text).length>MAX_BYTES)throw Error("JSON 파일은 2MB 이하만 허용");
 let obj;try{obj=JSON.parse(text);}catch{throw Error("JSON 파싱 실패");}
 if(!obj||typeof obj!=="object"||!Array.isArray(obj.lots)||obj.lots.length<1||obj.lots.length>1000)throw Error("lots는 1~1000건 배열이어야 함");
 const name=str(obj.sourceName,"sourceName",100),loadedAt=str(obj.collectedAt,"collectedAt",50);
 if(!Number.isFinite(Date.parse(loadedAt)))throw Error("취득 시각의 ISO 형식 오류");
 const seen=new Set(),lots=obj.lots.map((x,i)=>{
   const key="lots["+(i+1)+"]";if(!x||typeof x!=="object"||Array.isArray(x))throw Error(key+" 형식 오류");
   const id=str(x.id,key+".id",90);
   if(!/^[\p{L}\p{N}._:-]+$/u.test(id))throw Error(key+" ID 허용 문자 오류");
   if(seen.has(id))throw Error("중복 ID: "+id);seen.add(id);
   const channel=str(x.channel,key+".channel",10);
   if(!["court","public"].includes(channel))throw Error(key+" channel은 court/public");
   const date=str(x.date,key+".date",10);if(!dateOK(date))throw Error(key+" 날짜 오류");
   const appraisal=num(x.appraisal,key+".appraisal",1),minimum=num(x.minimum,key+".minimum");
   if(minimum>appraisal)throw Error(key+" 최저가가 감정가보다 큼");
   return {id,channel,date,appraisal,minimum,title:str(x.title,key+".title"),region:str(x.region,key+".region",60),type:str(x.type,key+".type",60),location:str(x.location,key+".location"),authority:str(x.authority,key+".authority"),status:str(x.status??"미확인",key+".status",70),failures:num(x.failures??0,key+".failures",0,100),area:num(x.area??0,key+".area",0,1e9),sourceUrl:secureLink(x.sourceUrl)};
 });
 return {lots,meta:{mode:"import",name,loadedAt}};
}