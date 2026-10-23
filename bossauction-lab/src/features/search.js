import {lots,DATA_LABEL} from "../data/mock.js";
import {discount,won,dateKR,escapeHTML} from "../core/format.js";
export function filterLots(filters,source=lots){
  const q=(filters.query||"").trim().toLocaleLowerCase("ko-KR");
  const found=source.filter(l=>
    (filters.channel==="all"||filters.channel===l.channel)&&
    (filters.region==="all"||filters.region===l.region)&&
    (filters.type==="all"||filters.type===l.type)&&
    (!q||[l.title,l.id,l.location,l.authority].join(" ").toLocaleLowerCase("ko-KR").includes(q))
  );
  if(filters.sort==="minimum")found.sort((a,b)=>a.minimum-b.minimum);
  else if(filters.sort==="discount")found.sort((a,b)=>discount(b)-discount(a));
  else found.sort((a,b)=>a.date.localeCompare(b.date));
  return found;
}
export function lotCards(items,state){
  if(!items.length)return '<div class="empty">조건에 맞는 샘플 물건이 없습니다. 필터를 변경해 보세요.</div>';
  return '<div class="grid">'+items.map(l=>{
    const saved=state.saved.has(l.id),selected=state.selected.has(l.id);
    return '<article class="lot"><div class="lot-head"><span class="tag '+(l.channel==="public"?"public":"")+'">'+(l.channel==="public"?"공매":"법원경매")+'</span><span class="small muted">'+l.id+'</span></div>'+
    '<h3>'+escapeHTML(l.title)+'</h3><div class="small muted">'+escapeHTML(l.location)+'</div>'+
    '<dl><div><dt>감정가 (가상)</dt><dd>'+won(l.appraisal)+'</dd></div><div><dt>최저가 (가상)</dt><dd class="price">'+won(l.minimum)+'</dd></div><div><dt>감정가 대비</dt><dd>'+discount(l).toFixed(1)+'% 낮음</dd></div><div><dt>기일 예시</dt><dd>'+dateKR(l.date)+'</dd></div></dl>'+
    '<div class="actions"><button class="btn primary" data-action="detail" data-id="'+l.id+'">상세 보기</button><button class="btn '+(saved?"saved":"")+'" data-action="save" data-id="'+l.id+'" aria-pressed="'+saved+'">'+(saved?"★ 관심 해제":"☆ 관심 저장")+'</button><button class="btn" data-action="compare" data-id="'+l.id+'" aria-pressed="'+selected+'">'+(selected?"✓ 비교 선택":"＋ 비교")+'</button></div></article>';
  }).join("")+'</div>';
}
export function renderSearch(state){
 const f=state.filters,found=filterLots(f),regions=[...new Set(lots.map(l=>l.region))].sort(),types=[...new Set(lots.map(l=>l.type))].sort();
 const choices=(arr,current)=>arr.map(([value,label])=>'<option value="'+value+'" '+(value===current?"selected":"")+'>'+label+'</option>').join("");
 return '<section class="hero"><div><div class="eyebrow">Auction inventory / demo</div><h1>경매·공매 통합 검색</h1><p class="muted">사건명·소재지·물건유형을 검색하고, 관심물건을 저장해 보세요.</p></div><span class="tag">'+DATA_LABEL+'</span></section>'+
 '<section class="panel"><form id="search-form"><div class="field"><label for="search-query">검색어 · 가상 물건명 / 소재지</label><div style="display:flex;gap:8px"><input id="search-query" name="query" placeholder="예: 성동구, 아파트, DEMO-001" value="'+escapeHTML(f.query)+'"><button class="btn primary" type="submit">검색</button></div></div></form>'+
 '<div class="filter-grid" style="margin-top:14px"><div class="field"><label for="channel">경매 유형</label><select id="channel" data-filter="channel">'+choices([["all","전체"],["court","법원경매"],["public","공매"]],f.channel)+'</select></div>'+
 '<div class="field"><label for="region">지역</label><select id="region" data-filter="region">'+choices([["all","전체"],...regions.map(x=>[x,x])],f.region)+'</select></div>'+
 '<div class="field"><label for="type">물건유형</label><select id="type" data-filter="type">'+choices([["all","전체"],...types.map(x=>[x,x])],f.type)+'</select></div>'+
 '<div class="field"><label for="sort">정렬</label><select id="sort" data-filter="sort">'+choices([["date","예시 일정순"],["minimum","최저가 낮은 순"],["discount","할인율 높은 순"]],f.sort)+'</select></div></div></section>'+
 '<div class="toolbar"><strong>검색 결과 '+found.length+'건</strong><span class="small muted">실제 법원 사건번호 및 공매번호와 무관한 DEMO 물건입니다.</span></div>'+lotCards(found,state);
}