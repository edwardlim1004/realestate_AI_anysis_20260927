import {lots} from "../data/mock.js";
import {escapeHTML} from "../core/format.js";
export const RIGHTS_ITEMS=[["registry","등기사항증명서의 권리·발급일 확인"],["notice","매각물건명세서의 인수사항·특별조건 확인"],["survey","현황조사서의 점유·임대차 확인"],["tenant","임차인 대항력·우선변제 자료 확인"],["dividend","배당요구종기·보증금 확인"],["expenses","명도·관리비·세금 등 비용 확인"],["latest","공고 원문 기일·변경·취소 확인"]];
export function rightsStatus(state){return {checked:RIGHTS_ITEMS.filter(([key])=>state.rightsChecks.has(key)).length,total:RIGHTS_ITEMS.length,safety:"판정 불가"};}
export function rightsExport(state){return {lotId:state.rightsLotId||null,items:Object.fromEntries(RIGHTS_ITEMS.map(([key])=>[key,state.rightsChecks.has(key)])),rightsSafety:"not-evaluated",note:"사용자 자가 점검표. AI 분석·법률 판단이 아님."};}
export function renderRights(state){
 const s=rightsStatus(state),opts='<option value="">대상 미선택</option>'+lots.map(l=>'<option value="'+escapeHTML(l.id)+'" '+(l.id===state.rightsLotId?"selected":"")+'>'+escapeHTML(l.title)+'</option>').join("");
 return '<section class="hero"><div><div class="eyebrow">Evidence checklist · not AI</div><h1>권리분석 사전 점검표</h1><p class="muted">문서 확인 여부만 체크합니다. 법률적 안전성을 판정하지 않습니다.</p></div></section>'+
 '<div class="split"><section class="panel"><h2>원문 문서 점검</h2><div class="field"><label for="rights-lot">대상 물건</label><select id="rights-lot" data-rights-lot>'+opts+'</select></div>'+RIGHTS_ITEMS.map(([key,label])=>'<label class="check-row"><input type="checkbox" data-rights-check="'+key+'" '+(state.rightsChecks.has(key)?"checked":"")+'><span>'+label+'</span></label>').join("")+'<div class="actions"><button class="btn" data-action="reset-rights">초기화</button><button class="btn primary" data-action="export-rights">점검표 JSON 저장</button></div></section>'+
 '<section class="panel"><h2>점검 상태</h2><div class="metric"><span>사용자가 체크한 항목</span><strong>'+s.checked+' / '+s.total+'</strong></div><p class="alert"><strong>안전성 판정 불가.</strong> 모든 항목을 체크했더라도 실제 등기 순위·인수채무·대항력을 분석하지 않았습니다. 입찰 전 원문과 전문가 검토가 필요합니다.</p></section></div>';
}