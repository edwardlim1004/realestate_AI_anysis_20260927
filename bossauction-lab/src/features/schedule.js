import {lots} from "../data/mock.js";
import {dateKR,escapeHTML} from "../core/format.js";
export function renderSchedule(){
 const items=[...lots].sort((a,b)=>a.date.localeCompare(b.date));
 return '<section class="hero"><div><div class="eyebrow">Calendar / demo</div><h1>경매·공매 일정</h1><p class="muted">실제 일정이 아니라 화면 동작을 검증하기 위한 예시 일정입니다.</p></div></section>'+
 '<div class="panel"><h2>2026년 11월 · 가상 일정</h2>'+items.map(l=>'<div class="date-item"><div class="date-chip">'+dateKR(l.date)+'</div><div class="grow"><strong>'+escapeHTML(l.title)+'</strong><div class="muted small">'+(l.channel==="court"?"법원경매":"공매")+' · '+escapeHTML(l.authority)+' · '+l.id+'</div></div><button class="btn" data-action="detail" data-id="'+l.id+'">보기</button></div>').join("")+'</div>';
}