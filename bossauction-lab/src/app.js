import {lots} from "./data/mock.js";
import {state,routeFromHash,toggleSaved,toggleCompare} from "./core/store.js";
import {renderDashboard} from "./features/dashboard.js";
import {renderSearch} from "./features/search.js";
import {renderSchedule} from "./features/schedule.js";
import {renderWatchlist} from "./features/watchlist.js";
import {renderCompare} from "./features/compare.js";
import {renderCalculator,calculateBid,renderCalculation} from "./features/calculator.js";
import {openDetail} from "./features/detail.js";
const views={dashboard:renderDashboard,search:renderSearch,schedule:renderSchedule,watchlist:renderWatchlist,compare:renderCompare,calculator:renderCalculator};
function render(){
 state.view=routeFromHash();
 document.getElementById("app").innerHTML=views[state.view](state);
 document.querySelectorAll("[data-route]").forEach(a=>{a.classList.toggle("active",a.dataset.route===state.view);if(a.dataset.route===state.view)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");});
 document.title="Auction Lab | "+({dashboard:"대시보드",search:"물건 검색",schedule:"경매 일정",watchlist:"관심 물건",compare:"물건 비교",calculator:"입찰 계산기"}[state.view]);
}
window.addEventListener("hashchange",render);
document.addEventListener("change",event=>{
 const field=event.target.closest("[data-filter]");
 if(field){state.filters[field.dataset.filter]=field.value;render();}
});
document.addEventListener("submit",event=>{
 if(event.target.id==="search-form"){event.preventDefault();state.filters.query=new FormData(event.target).get("query")?.toString()||"";render();}
 if(event.target.id==="calculator-form"){event.preventDefault();const f=new FormData(event.target);const n=(x)=>Number(f.get(x));try{const r=calculateBid({bid:n("bid")*10000,depositRate:n("depositRate"),taxRate:n("taxRate"),otherCost:n("otherCost")*10000,expectedResale:n("expectedResale")*10000});state.calculation=r;document.getElementById("calculation-result").innerHTML=renderCalculation(r);}catch(err){document.getElementById("calculation-result").textContent=err.message;}}
});
document.addEventListener("click",event=>{
 const trigger=event.target.closest("[data-action]");
 if(!trigger)return;
 const action=trigger.dataset.action;
 if(action==="close-dialog"){document.getElementById("lot-dialog").close();return;}
 const id=trigger.dataset.id,lot=lots.find(l=>l.id===id);if(!lot)return;
 if(action==="detail"){openDetail(lot);return;}
 if(action==="save"){toggleSaved(id);render();}
 if(action==="compare"){if(!toggleCompare(id)){alert("비교는 최대 3건까지 선택할 수 있습니다.");return;}render();}
});
render();