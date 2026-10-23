import {lots} from "../data/mock.js";
import {won,discount,escapeHTML,dateKR} from "../core/format.js";
export function renderCompare(state){
 const list=lots.filter(x=>state.selected.has(x.id));
 if(!list.length)return '<section class="hero"><div><div class="eyebrow">Side by side</div><h1>물건 비교</h1><p class="muted">검색 화면에서 최대 3건까지 비교할 수 있습니다.</p></div></section><div class="empty">선택된 물건이 없습니다. <a href="#search" data-route="search">검색 화면에서 비교 물건 선택하기 →</a></div>';
 const rows=[["구분",l=>l.channel==="court"?"법원경매":"공매"],["지역",l=>l.region],["물건유형",l=>l.type],["감정가",l=>won(l.appraisal)],["최저가",l=>won(l.minimum)],["감정가 대비",l=>discount(l).toFixed(1)+"% 낮음"],["면적",l=>l.area+"㎡"],["기일 (가상)",l=>dateKR(l.date)]];
 return '<section class="hero"><div><div class="eyebrow">Side by side</div><h1>물건 비교</h1><p class="muted">선택 '+list.length+'/3건 · 전부 원문 검증 전 자료입니다.</p></div><a class="btn" href="#search" data-route="search">추가 선택</a></section><section class="panel"><div class="table-wrap"><table class="table"><thead><tr><th>비교 항목</th>'+list.map(l=>'<th>'+escapeHTML(l.title)+'<div><button class="btn" data-action="compare" data-id="'+l.id+'">선택 해제</button></div></th>').join("")+'</tr></thead><tbody>'+rows.map(([label,fn])=>'<tr><th>'+label+'</th>'+list.map(l=>'<td>'+escapeHTML(fn(l))+'</td>').join("")+'</tr>').join("")+'</tbody></table></div></section>';
}