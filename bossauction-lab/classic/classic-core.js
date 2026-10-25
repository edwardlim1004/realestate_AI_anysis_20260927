// Adapt the original v11 map interaction model to validated local-browser data.
// No third-party snapshot images or fictitious live auction counts.
export const typeLabel=l=>l.channel==="public"?"공매":"경매";
export function groupByLocation(lots){
 const groups=new Map();
 for(const lot of lots||[]){
  if(!Number.isFinite(lot.lat)||!Number.isFinite(lot.lng))continue;
  const parts=String(lot.location||"").match(/[가-힣0-9]+(?:동|리|가|읍|면)/g)||[];
  const dong=parts.length?parts[parts.length-1]:(lot.region||"지역 미상");
  const key=lot.region+"|"+dong;
  if(!groups.has(key))groups.set(key,{key,dong,lat:0,lng:0,count:0,court:0,public:0,lots:[]});
  const a=groups.get(key);
  a.lat+=lot.lat;a.lng+=lot.lng;a.count++;a[lot.channel==="public"?"public":"court"]++;a.lots.push(lot);
 }
 return [...groups.values()].map(g=>({...g,lat:g.lat/g.count,lng:g.lng/g.count}));
}
export function summarize(lots){
 const total=lots.length;
 const court=lots.filter(x=>x.channel==="court").length,publicCount=lots.filter(x=>x.channel==="public").length;
 const located=lots.filter(x=>Number.isFinite(x.lat)&&Number.isFinite(x.lng)).length;
 return {total,court,public:publicCount,located,unlocated:total-located,regions:groupByLocation(lots).length};
}
export function sectionFilter(lots,section,favorites=new Set()){
 if(section==="favorites")return lots.filter(l=>favorites.has(l.id));
 if(section==="court"||section==="auction")return lots.filter(l=>l.channel==="court");
 if(section==="public")return lots.filter(l=>l.channel==="public");
 if(section==="apt")return lots.filter(l=>/아파트|오피스텔/i.test(l.type));
 if(section==="land")return lots.filter(l=>/토지|농지|대지|임야|답|전/i.test(l.type));
 if(section==="sale")return []; // no confirmed post-sale status in local source
 return lots;
}
export function exportLocalLots(lots,source){
 return JSON.stringify({sourceName:source?.name||"사용자가 반입한 v11 물건",collectedAt:source?.asOf||null,lots},null,2);
}
