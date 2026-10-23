import {lots} from "../data/mock.js";
import {lotCards} from "./search.js";
export function renderWatchlist(state){
 const saved=lots.filter(x=>state.saved.has(x.id));
 return '<section class="hero"><div><div class="eyebrow">Saved / local browser only</div><h1>관심 물건</h1><p class="muted">이 브라우저에만 저장됩니다. 서버 계정과 동기화하지 않습니다.</p></div></section>'+
 '<div class="toolbar"><strong>저장한 물건 '+saved.length+'건</strong><a class="btn" href="#search" data-route="search">물건 찾기</a></div>'+lotCards(saved,state);
}