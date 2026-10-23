import {lots} from "../data/mock.js";
import {dateKR,escapeHTML} from "../core/format.js";
export function renderSchedule(state){
 const items=[...lots].sort((a,b)=>a.date.localeCompare(b.date));
 return '<section class="hero"><div><div class="eyebrow">Calendar / unverified</div><h1>경매·공매 일정</h1><p class="muted">현재 자료는 원문과 자동 대조되지 않습니다. 실제 공고를 재확인하세요.</p></div></section>'+
 '<div class="panel"><h2>일정 목록 · '+escapeHTML(state.dataMeta.name)+' (미검증)</h2>'+items.map(l=>'<div class="date-item"><div class="date-chip">'+dateKR(l.date)+'</div><div class="grow"><strong>'+escapeHTML(l.title)+'</strong><div class="muted small">'+(l.channel==="court"?"법원경매":"공매")+' · '+escapeHTML(l.authority)+' · '+l.id+'</div></div><button class="btn" data-action="detail" data-id="'+l.id+'">보기</button></div>').join("")+'</div>';
}