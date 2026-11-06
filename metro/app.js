'use strict';
const names={busan:'부산',daegu:'대구',gwangju:'광주'};
let progress,summary;
const escapeText=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number=x=>x==null?'—':Number(x).toLocaleString('ko-KR');
function render(){
 const city=document.getElementById('city').value,info=progress?.cities?.[city],data=summary?.cities?.[city];
 const target=document.getElementById('prices');
 if(!info?.verified){target.textContent='수집·검증 중입니다. 검증을 통과하면 가격이 자동 연결됩니다.';return;}
 if(data?.status!=='verified'||!data.archive_fingerprint||data.archive_fingerprint!==info.manifest_fingerprint){target.textContent='원자료 검증 완료 · 가격 집계 생성 또는 갱신 중입니다.';return;}
 const metric=(x,monthly=false)=>`${number(monthly?x.monthly_rent_median_manwon:x.median_manwon)}<small>${number(x.rows)}행 · 동일 반복 ${number(x.identical_extra_rows)}행${monthly?'':' · 고유행 참고 '+number(x.distinct_row_median_manwon)}</small>`;
 target.innerHTML=`<p><strong>${escapeText(summary.window_start)}~${escapeText(summary.cutoff_month)} 공통 집계기간</strong> · 전용 80~90㎡ · 만원</p><div class="scroll"><table><caption>${names[city]} 지역별 매매·전세·월세 중위값</caption><thead><tr><th>지역</th><th>매매가</th><th>전세 보증금</th><th>월세 보증금</th><th>월 임대료</th></tr></thead><tbody>${data.districts.map(d=>d.status==='ready'?`<tr><th>${escapeText(d.name)}</th><td>${metric(d.sale)}</td><td>${metric(d.jeonse)}</td><td>${metric(d.monthly)}</td><td>${metric(d.monthly,true)}</td></tr>`:`<tr><th>${escapeText(d.name)}</th><td colspan="4">구·신 코드 중복 기간 검토 중 · 합산 보류</td></tr>`).join('')}</tbody></table></div>`;
}
async function load(){
 try{
 const response=await fetch('../seoul-apartment-collector/metro_progress.json',{cache:'no-cache'});if(!response.ok)throw Error('현황을 불러오지 못했습니다.');progress=await response.json();
 document.getElementById('status').innerHTML=`<p>현황 기준 ${escapeText(progress.as_of_kst)} · 원자료 수집 목표 ${escapeText(progress.historical_cutoff)}</p><div class="cards">${Object.entries(names).map(([city,name])=>{const c=progress.cities[city];return `<article class="card"><h2>${name}</h2><strong>${c.verified?'검증 완료':c.completed?'원출처 대조 중':'순차 수집 대기·진행'}</strong><p>${number(c.verified_manifest_scopes)} / ${number(c.expected_scopes)} 구역·월·유형<br>${number(c.stored_rows)} 원본 행</p><small>원본 저장 ${number(c.percent)}% · 재읽기 ${c.storage_reread_passed?'통과':'대기'}<br>동일 반복 보존 ${number(c.identical_extra_rows_preserved)}행</small></article>`;}).join('')}</div>`;
 try{const r=await fetch('../dashboard-v1/data/metro-summary.json',{cache:'no-cache'});if(r.ok)summary=await r.json();}catch(e){/* Verified status remains visible; no synthetic prices. */}
 render();
 }catch(e){document.getElementById('status').textContent=e.message;document.getElementById('prices').textContent='자료 연결을 확인한 후 다시 접속해주세요.';}
}
document.getElementById('city').addEventListener('change',render);load();
