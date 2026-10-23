import {won,discount,dateKR,escapeHTML} from "../core/format.js";
export function openDetail(lot,meta){
 const dialog=document.getElementById("lot-dialog");
 document.getElementById("dialog-content").innerHTML=
 '<div class="toolbar"><span class="tag '+(lot.channel==="public"?"public":"")+'">'+(lot.channel==="public"?"공매":"법원경매")+' · '+(meta.mode==='demo'?'가상 예시':'사용자 자료 · 미검증')+'</span><button class="btn" data-action="close-dialog">닫기 ×</button></div>'+
 '<h2>'+escapeHTML(lot.title)+'</h2><p class="muted">'+escapeHTML(lot.id)+' · '+escapeHTML(lot.authority)+'</p>'+
 '<div class="statline"><span>소재지</span><strong>'+escapeHTML(lot.location)+'</strong></div>'+
 '<div class="statline"><span>물건 유형 / 면적</span><strong>'+escapeHTML(lot.type)+' / '+lot.area+'㎡</strong></div>'+
 '<div class="statline"><span>감정가 (가상)</span><strong>'+won(lot.appraisal)+'</strong></div>'+
 '<div class="statline"><span>최저가 (가상)</span><strong>'+won(lot.minimum)+'</strong></div>'+
 '<div class="statline"><span>감정가 대비 하락폭</span><strong>'+discount(lot).toFixed(1)+'%</strong></div>'+
 '<div class="statline"><span>예시 일정</span><strong>'+dateKR(lot.date)+'</strong></div>'+
 '<h3>권리분석 사전 점검표 (자동 판정 아님)</h3><div class="alert">등기사항증명서, 매각물건명세서, 현황조사서, 임대차 현황, 배당요구종기, 대항력·우선변제권, 체납관리비 및 점유 상태를 원문으로 직접 검증해야 합니다. 이 도구는 자료를 조회하거나 안전성을 판정하지 않습니다.</div>'+(lot.sourceUrl?'<p><a href="'+escapeHTML(lot.sourceUrl)+'" target="_blank" rel="noopener noreferrer">사용자 제공 원문 링크 ↗</a></p>':'')+'<p><button class="btn primary" data-action="rights" data-id="'+escapeHTML(lot.id)+'">권리 점검표 열기</button></p>';
 if(!dialog.open)dialog.showModal();
}