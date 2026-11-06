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
 querySelectorAll(sel){if(sel==="path"){
   if(this._pathsHtml!==this.innerHTML){
     this._pathsHtml=this.innerHTML;
     this._pathNodes=[...this.innerHTML.matchAll(/data-district="([^"]+)"/g)].map((m,i)=>new Node("map-path-"+i,{district:m[1]}));
   }
   return this._pathNodes;
 }return [];}
 scrollIntoView(){}
}
for(const m of html.matchAll(/\bid="([^"]+)"/g))dom[m[1]]=new Node(m[1]);
const areaButtons=["seoul","gyeonggi","daejeon"].flatMap(a=>[new Node("top-"+a,{area:a}),new Node("map-"+a,{area:a})]);
dom.riskTabs.querySelectorAll=()=>["history","regional","forecast"].map(a=>new Node("risk-"+a,{tab:a}));
const tradeButtons=["sale","jeonse","monthly"].map(t=>new Node(t,{tradeType:t}));
const document={getElementById(id){assert.ok(dom[id],"missing "+id);return dom[id]},querySelectorAll(s){return s==="[data-area]"?areaButtons:s==="[data-trade-type]"?tradeButtons:[]}};
const MapNavigation=require("../map-navigation.js");
class Chart{constructor(_,data){this.data=data;}destroy(){}}
const reads=[];
async function mockedFetch(url){
 const safe=url.split("?")[0];
 reads.push(safe);
 assert.ok(!safe.includes(".."),"path traversal");
 if(safe==="trade-details/rent/index.json")return {ok:true,json:async()=>({regions:{"송파구":{codes:["11710"],file:"11710.json"}}})};
 if(safe==="trade-details/rent/11710.json")return {ok:true,json:async()=>({months:["202610"],rows:[
 {date:"2026-10-10",apt:"전세테스트",city:"서울특별시 송파구",area:"84",floor:"3",deposit:"50000",monthlyRent:"0",rentalType:"jeonse"},
 {date:"2026-10-11",apt:"월세테스트",city:"서울특별시 송파구",area:"84",floor:"4",deposit:"0",monthlyRent:"150",rentalType:"monthly"}]})};
 const file=path.join(ROOT,safe);
 if(!fs.existsSync(file))return {ok:false,status:404,json:async()=>({})};
 return {ok:true,status:200,json:async()=>JSON.parse(load(safe))};
}
const ctx=vm.createContext({document,MapNavigation,Chart,fetch:mockedFetch,
 ENHANCED_DATA:parse("data.js"),RISK_MONITOR_DATA:parse("risk-data.js"),REGION_BOUNDARIES:parse("dashboard-v1/region-boundaries.js")});
vm.runInContext(load("dashboard-v1/app.js"),ctx,{timeout:8000});
function wait(){return new Promise(resolve=>setTimeout(resolve,100))}
(async()=>{
 await wait();
 tradeButtons.find(b=>b.id==="jeonse").events.click();await wait();
 assert.match(dom.tradeRows.innerHTML,/전세테스트/);assert.ok(!dom.tradeRows.innerHTML.includes("월세테스트"));
 assert.equal(dom.tradePriceHeader.textContent,"전세 보증금");assert.equal(dom.typeSelect.value,"jeonse");
 tradeButtons.find(b=>b.id==="monthly").events.click();await wait();
 assert.match(dom.tradeRows.innerHTML,/월세테스트/);assert.match(dom.tradeRows.innerHTML,/150만원/);assert.match(dom.tradeRows.innerHTML,/보증금 0만원/);assert.ok(!dom.tradeRows.innerHTML.includes("전세테스트"));
 assert.equal(dom.tradePriceHeader.textContent,"보증금 / 월 임대료");
 dom.tradeSearch.value="없는단지";dom.tradeSearch.events.input();assert.match(dom.tradeRows.innerHTML,/표시할 거래가 없습니다/);
 dom.tradeSearch.value="";tradeButtons.find(b=>b.id==="sale").events.click();await wait();
 assert.equal(dom.tradePriceHeader.textContent,"매매가격");assert.ok(!dom.tradeRows.innerHTML.includes("월세테스트"));
 console.log("PASS sale/jeonse/monthly buttons, amounts, search and independent caches");
})().catch(err=>{console.error(err);process.exitCode=1});
