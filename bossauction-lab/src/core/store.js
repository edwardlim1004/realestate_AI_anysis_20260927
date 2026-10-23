const STORAGE_KEY="auction-lab-watchlist-v1";
const ROUTES=new Set(["dashboard","search","schedule","watchlist","compare","calculator","map","data","rights","workspace"]);
export function routeFromHash(){const route=location.hash.replace("#","");return ROUTES.has(route)?route:"dashboard";}
function loadSaved(){try{const parsed=JSON.parse(localStorage.getItem(STORAGE_KEY)||"[]");return new Set(Array.isArray(parsed)?parsed.filter(x=>typeof x==="string"):[]);}catch{return new Set();}}
export const state={view:routeFromHash(),filters:{query:"",channel:"all",region:"all",type:"all",sort:"date"},saved:loadSaved(),selected:new Set(),calculation:null,mapRegion:"all",dataMeta:{mode:"demo",name:"가상 샘플 데이터",loadedAt:null},rightsChecks:new Set(),rightsLotId:null,profile:""};
export function toggleSaved(id){if(state.saved.has(id))state.saved.delete(id);else state.saved.add(id);try{localStorage.setItem(STORAGE_KEY,JSON.stringify([...state.saved]));}catch{/* storage disabled */}}
export function toggleCompare(id){if(state.selected.has(id)){state.selected.delete(id);return true;}if(state.selected.size>=3)return false;state.selected.add(id);return true;}