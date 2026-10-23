import {lots,importLots,resetLots} from "./data/mock.js";
import {parseDataset,MAX_FILE_BYTES} from "./adapters/import.js";
import {state,routeFromHash,toggleSaved,toggleCompare} from "./core/store.js";
import {renderDashboard} from "./features/dashboard.js";
import {renderSearch} from "./features/search.js";
import {renderSchedule} from "./features/schedule.js";
import {renderWatchlist} from "./features/watchlist.js";
import {renderCompare} from "./features/compare.js";
import {renderCalculator,calculateBid,renderCalculation} from "./features/calculator.js";
import {openDetail} from "./features/detail.js";
import {renderMap} from "./features/map.js";
import {renderData} from "./features/data.js";
import {renderRights,rightsExport} from "./features/rights.js";
import {renderWorkspace} from "./features/workspace.js";
const views={dashboard:renderDashboard,search:renderSearch,schedule:renderSchedule,watchlist:renderWatchlist,compare:renderCompare,calculator:renderCalculator,map:renderMap,data:renderData,rights:renderRights,workspace:renderWorkspace};
function render(){
 state.view=routeFromHash();
 document.getElementById("app").innerHTML=views[state.view](state);
 document.querySelectorAll("[data-route]").forEach(a=>{a.classList.toggle("active",a.dataset.route===state.view);if(a.dataset.route===state.view)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");});
 document.title="Auction Lab | "+({dashboard:"대시보드",search:"물건 검색",schedule:"경매 일정",watchlist:"관심 물건",compare:"물건 비교",calculator:"입찰 계산기",map:"지도검색",data:"자료 가져오기",rights:"권리 점검",workspace:"내 작업공간"}[state.view]);
}
window.addEventListener("hashchange",render);
document.addEventListener("change",event=>{
 const field=event.target.closest("[data-filter]");
 if(field){state.filters[field.dataset.filter]=field.value;render();}
 const c=event.target.closest("[data-rights-check]");if(c){c.checked?state.rightsChecks.add(c.dataset.rightsCheck):state.rightsChecks.delete(c.dataset.rightsCheck);render();}
 const d=event.target.closest("[data-rights-lot]");if(d){state.rightsLotId=d.value||null;state.rightsChecks.clear();render();}
});
document.addEventListener("submit",async event=>{
 if(event.target.id==="search-form"){event.preventDefault();state.filters.query=new FormData(event.target).get("query")?.toString()||"";render();}
 if(event.target.id==="profile-form"){event.preventDefault();state.profile=String(new FormData(event.target).get("nickname")||"").trim().slice(0,32);render();}
 if(event.target.id==="import-form"){event.preventDefault();const file=document.getElementById("import-file").files?.[0];const msg=document.getElementById("import-result");if(!file){msg.textContent="파일을 선택하세요.";return;}if(file.size>MAX_FILE_BYTES){msg.textContent="최대 2MB 파일만 가능합니다.";return;}try{const imported=parseDataset(await file.text());importLots(imported.lots);state.dataMeta=imported.meta;state.mapRegion="all";state.selected.clear();state.rightsChecks.clear();state.rightsLotId=null;state.filters={query:"",channel:"all",region:"all",type:"all",sort:"date"};render();}catch(error){msg.textContent="적용 실패: "+error.message;}}
 if(event.target.id==="calculator-form"){event.preventDefault();const f=new FormData(event.target);const n=(x)=>Number(f.get(x));try{const r=calculateBid({bid:n("bid")*10000,depositRate:n("depositRate"),taxRate:n("taxRate"),otherCost:n("otherCost")*10000,expectedResale:n("expectedResale")*10000});state.calculation=r;document.getElementById("calculation-result").innerHTML=renderCalculation(r);}catch(err){document.getElementById("calculation-result").textContent=err.message;}}
});
document.addEventListener("click",event=>{
 const trigger=event.target.closest("[data-action]");
 if(!trigger)return;
 const action=trigger.dataset.action;
 if(action==="close-dialog"){document.getElementById("lot-dialog").close();return;}
 if(action==="map-region"){state.mapRegion=trigger.dataset.region;render();return;}
 if(action==="reset-dataset"){resetLots();state.dataMeta={mode:"demo",name:"가상 샘플 데이터",loadedAt:null};state.mapRegion="all";state.selected.clear();state.rightsChecks.clear();render();return;}
 if(action==="reset-rights"){state.rightsChecks.clear();render();return;}
 if(action==="export-rights"){const blob=new Blob([JSON.stringify(rightsExport(state),null,2)],{type:"application/json"}),url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="auction-rights-checklist.json";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);return;}
 const id=trigger.dataset.id,lot=lots.find(l=>l.id===id);if(!lot)return;
 if(action==="detail"){openDetail(lot,state.dataMeta);return;}
 if(action==="rights"){state.rightsLotId=lot.id;state.rightsChecks.clear();document.getElementById("lot-dialog").close();location.hash="#rights";render();return;}
 if(action==="save"){toggleSaved(id);render();}
 if(action==="compare"){if(!toggleCompare(id)){alert("비교는 최대 3건까지 선택할 수 있습니다.");return;}render();}
});
render();