"use strict";
const fs=require("node:fs"),path=require("node:path"),vm=require("node:vm"),assert=require("node:assert/strict");
const root=path.resolve(__dirname,"../..");
const read=p=>fs.readFileSync(path.join(root,p),"utf8");
const html=read("index.html"),legacy=read("ver0/index.html"),app=read("dashboard-v1/app.js"),boundaries=read("dashboard-v1/region-boundaries.js");
const parsed=s=>JSON.parse(s.slice(s.indexOf("=")+1,s.lastIndexOf(";")));
const data=parsed(read("data.js")),risk=parsed(read("risk-data.js")),geo=parsed(boundaries);
assert.match(html,/ver0\//);assert.match(html,/dashboard-v1\/app.js/);
assert.match(legacy,/ver0\.0/);assert.match(legacy,/<base href="\.\.\/">/);
new vm.Script(app,{filename:"dashboard-v1/app.js"});
assert.equal(data.regions.filter(x=>x.province==="seoul").length,25);
assert.equal(data.regions.filter(x=>x.province==="gyeonggi").length,31);
for(const [key,count] of Object.entries({seoul:25,gyeonggi:31,daejeon:5}))assert.equal(geo.regions[key].length,count,key+" polygons");
assert.ok(risk.countries.KOR.history.length>50);
assert.ok(risk.crisisEvents.some(x=>/글로벌 금융위기/.test(x.label)));
assert.ok(risk.crisisEvents.some(x=>/COVID-19/.test(x.label)));
assert.ok(!data.regions.some(x=>x.province==="daejeon"),"do not silently fake Daejeon scores");
for(const id of ["regionMap","regionRows","tradeRows","historyChart","districtSelect","mapRegionTabs","valueChart"]){
 assert.ok(html.includes('id="'+id+'"'),"missing UI element "+id);
}
const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]),dom={};
class MockElement{
 constructor(id,dataset={}){this.id=id;this.dataset=dataset;this.innerHTML="";this.textContent="";this.hidden=false;this.value=({historyMetric:"all",macroMetric:"credit",mapMetric:"composite",periodSelect:"complete",typeSelect:"sale"})[id]||"";this.events={};this.classList={toggle(){}};}
 setAttribute(){}addEventListener(t,f){this.events[t]=f;}
 querySelectorAll(selector){if(selector==="path")return [...this.innerHTML.matchAll(/data-district="([^"]+)"/g)].map((m,i)=>new MockElement("path-"+i,{district:m[1]}));return [];}
 scrollIntoView(){}getAttribute(s){return s==="data-district"?this.dataset.district:null;}
}
for(const id of ids)dom[id]=new MockElement(id);
const areaButtons=["seoul","gyeonggi","daejeon"].flatMap(a=>[new MockElement("top-"+a,{area:a}),new MockElement("map-"+a,{area:a})]);
const riskButtons=["history","regional","forecast"].map(a=>new MockElement("risk-"+a,{tab:a}));
dom.riskTabs.querySelectorAll=()=>riskButtons;
const doc={getElementById(id){assert.ok(dom[id],"missing "+id);return dom[id];},querySelectorAll(s){return s==="[data-area]"?areaButtons:[];}};
class MockChart{constructor(el,config){assert.ok(el);this.config=config;}destroy(){}}
const ctx=vm.createContext({document:doc,Chart:MockChart,fetch:async()=>({ok:false,status:404,json:async()=>({})}),ENHANCED_DATA:data,RISK_MONITOR_DATA:risk,REGION_BOUNDARIES:geo});
vm.runInContext(app,ctx,{timeout:5000});
const paths=()=>(dom.regionMap.innerHTML.match(/<path/g)||[]).length;
assert.equal(paths(),25);assert.equal((dom.regionRows.innerHTML.match(/<tr/g)||[]).length,25);
areaButtons.find(x=>x.id==="top-gyeonggi").events.click();
assert.equal(paths(),31);assert.match(dom.mapTitle.textContent,/경기/);
areaButtons.find(x=>x.id==="map-daejeon").events.click();
assert.equal(paths(),5);assert.match(dom.mapTitle.textContent,/대전/);
assert.match(dom.regionRows.innerHTML,/N\/A/);
assert.equal((dom.regionRows.innerHTML.match(/<tr/g)||[]).length,5);
console.log("PASS ver1 smoke: version preservation, map 25/31/5, regional filter synchronization, chart data and safety gates");
