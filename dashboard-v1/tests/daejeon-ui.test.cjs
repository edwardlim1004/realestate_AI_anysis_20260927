"use strict";
const fs=require("node:fs"),path=require("node:path"),vm=require("node:vm"),assert=require("node:assert/strict");
const ROOT=path.resolve(__dirname,"../.."),load=p=>fs.readFileSync(path.join(ROOT,p),"utf8");
const parse=p=>{const s=load(p);return JSON.parse(s.slice(s.indexOf("=")+1,s.lastIndexOf(";")))};
const html=load("index.html"),dom={};
class Node{
 constructor(id,dataset={}){this.id=id;this.dataset=dataset;this.innerHTML="";this.textContent="";this.value=({historyMetric:"all",macroMetric:"credit",mapMetric:"composite",periodSelect:"complete",typeSelect:"sale"})[id]||"";this.options=Array.from({length:8},()=>({textContent:""}));this.hidden=false;this.disabled=false;this.events={};this.classList={toggle(){}};this.attrs={};}
 addEventListener(evt,fn){this.events[evt]=fn;}
 setAttribute(k,v){this.attrs[k]=v;}
 getAttribute(k){return k==="data-district"?this.dataset.district:this.attrs[k];}
 getBoundingClientRect(){return {width:700,height:320,left:0,top:0};}
 querySelectorAll(sel){if(sel==="path")return [...this.innerHTML.matchAll(/data-district="([^"]+)"/g)].map((m,i)=>new Node("map-path-"+i,{district:m[1]}));return [];}
 scrollIntoView(){}
}
for(const m of html.matchAll(/\bid="([^"]+)"/g))dom[m[1]]=new Node(m[1]);
const areaButtons=["seoul","gyeonggi","daejeon"].flatMap(a=>[new Node("top-"+a,{area:a}),new Node("map-"+a,{area:a})]);
dom.riskTabs.querySelectorAll=()=>["history","regional","forecast"].map(a=>new Node("risk-"+a,{tab:a}));
const document={getElementById(id){assert.ok(dom[id],"missing "+id);return dom[id]},querySelectorAll(s){return s==="[data-area]"?areaButtons:[]}};
const MapNavigation=require("../map-navigation.js");
class Chart{constructor(_,data){this.data=data;}destroy(){}}
const reads=[];
async function mockedFetch(url){
 const safe=url.split("?")[0];
 reads.push(safe);
 assert.ok(!safe.includes(".."),"path traversal");
 const file=path.join(ROOT,safe);
 if(!fs.existsSync(file))return {ok:false,status:404,json:async()=>({})};
 return {ok:true,status:200,json:async()=>JSON.parse(load(safe))};
}
const ctx=vm.createContext({document,MapNavigation,Chart,fetch:mockedFetch,
 ENHANCED_DATA:parse("data.js"),RISK_MONITOR_DATA:parse("risk-data.js"),REGION_BOUNDARIES:parse("dashboard-v1/region-boundaries.js")});
vm.runInContext(load("dashboard-v1/app.js"),ctx,{timeout:8000});
function wait(){return new Promise(resolve=>setTimeout(resolve,100))}
(async()=>{
 areaButtons.find(b=>b.id==="top-daejeon").events.click();
 await wait();
 assert.match(dom.regionRows.innerHTML,/동구/);
 assert.match(dom.regionRows.innerHTML,/4축 잠정/);
 assert.ok(dom.regionRows.innerHTML.includes("62.5"),"real verified Daejeon reference score rendered");
 assert.equal((dom.regionMap.innerHTML.match(/<path/g)||[]).length,5);
 assert.match(dom.mapMetric.options[0].textContent,/4축/);
 assert.ok(dom.regionMap.innerHTML.includes("data-district"));
 const pathMiddle=dom.regionMap.querySelectorAll("path").find(e=>e.dataset.district==="중구");
 assert.ok(pathMiddle);
 pathMiddle.events.click();
 await wait();
 assert.match(dom.tradeRows.innerHTML,/대전광역시 중구/,"Daejeon Jung-gu trade list");
 assert.ok(!dom.tradeRows.innerHTML.includes("서울특별시 중구"),"must not cross-match Seoul Jung-gu");
 assert.match(dom.aptName.textContent,/./,"Daejeon apartments rendered");
 assert.ok(dom.aptSelect.innerHTML.includes("option"),"Daejeon 5-year valuation option list");
 assert.match(dom.valuationFullLink.href,/30140/,"deep link to Daejeon five-year independent viewer");
 assert.ok(reads.includes("trade-details/30140.json"));
 assert.ok(reads.includes("long-term-value/data/30140.json"));
 console.log("PASS verified Daejeon full dashboard: 5 zones, real four-axis score, five-year apartment and scoped transactions");
})().catch(err=>{console.error(err);process.exitCode=1});
