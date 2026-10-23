import {lots,DATA_LABEL} from "../data/mock.js";
import {discount,won} from "../core/format.js";
import {lotCards} from "./search.js";
export function renderDashboard(state){
 const c=lots.filter(x=>x.channel==="court").length,p=lots.filter(x=>x.channel==="public").length;
 const avg=lots.length?lots.reduce((a,l)=>a+discount(l),0)/lots.length:0;
 const picks=[...lots].sort((a,b)=>discount(b)-discount(a)).slice(0,3);
 const imported=state.dataMeta.mode==="import",sourceLabel=imported?"사용자 자료 · 원문 미검증":"가상 데이터";
 return '<section class="hero"><div><div class="eyebrow">Auction intelligence workspace</div><h1>한 화면에서 보는 경·공매 분석</h1><p class="muted">실제 서비스의 공개된 기능 범주를 독립 UI로 재구성한 개발용 샘플입니다.</p></div><a class="btn primary" href="#search" data-route="search">전체 물건 검색 →</a></section>'+
 '<div class="metrics"><div class="metric"><span>전체 물건</span><strong>'+lots.length+'건</strong><small class="muted">'+sourceLabel+'</small></div><div class="metric"><span>법원경매</span><strong>'+c+'건</strong><small class="muted">'+sourceLabel+'</small></div><div class="metric"><span>공매</span><strong>'+p+'건</strong><small class="muted">'+sourceLabel+'</small></div><div class="metric"><span>평균 감정가 대비 하락</span><strong>'+avg.toFixed(1)+'%</strong><small class="muted">단순 산술평균 · 원문 미검증</small></div></div>'+
 '<div class="split"><section class="panel"><h2>기능 둘러보기</h2><div class="statline"><span>🔎 검색·필터링</span><a href="#search" data-route="search">열기 →</a></div><div class="statline"><span>📅 입찰 일정 확인</span><a href="#schedule" data-route="schedule">열기 →</a></div><div class="statline"><span>📊 수익·비용 계산</span><a href="#calculator" data-route="calculator">열기 →</a></div><div class="statline"><span>★ 관심물건 보관함</span><a href="#watchlist" data-route="watchlist">'+state.saved.size+'건 →</a></div></section><section class="panel"><h2>분석 시 유의사항</h2><div class="alert">자료는 원문과 자동 대조되지 않습니다. 실제 입찰 전에 공식 공고와 대조해야 합니다.</div><p class="small muted">원본 서비스와 무관합니다. 정식 로그인·결제·AI 권리판정 및 공식 DB 동기화는 제공하지 않습니다.</p><p class="small muted">자료 범위: '+(imported?state.dataMeta.name+" (사용자 입력·미검증)":DATA_LABEL)+'</p></section></div>'+
 '<div class="toolbar"><h2>감정가 대비 할인율 상위 물건</h2><span class="muted small">매력도·안전성을 뜻하지 않음</span></div>'+lotCards(picks,state);
}