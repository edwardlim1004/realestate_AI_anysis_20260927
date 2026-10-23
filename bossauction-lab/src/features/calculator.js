import {won,percent} from "../core/format.js";
export function calculateBid({bid,depositRate,taxRate,otherCost,expectedResale}){
 const values=[bid,depositRate,taxRate,otherCost,expectedResale];
 if(values.some(v=>!Number.isFinite(v))||bid<=0||otherCost<0||expectedResale<0||depositRate<0||depositRate>100||taxRate<0||taxRate>100)throw new Error("모든 값을 유효한 범위로 입력해 주세요.");
 const deposit=bid*depositRate/100,remaining=bid-deposit,tax=bid*taxRate/100,total=bid+tax+otherCost,profit=expectedResale-total;
 return {deposit,remaining,tax,total,profit,roi:total>0?(profit/total*100):0};
}
export function renderCalculator(state){
 const result=state.calculation;
 return '<section class="hero"><div><div class="eyebrow">Bid scenario / manual assumptions</div><h1>입찰 비용 계산기</h1><p class="muted">입찰가와 세율 등 개인 가정을 입력해 비용 구조를 살펴봅니다.</p></div></section>'+
 '<div class="split"><section class="panel"><h2>입찰 가정 입력</h2><form id="calculator-form"><div class="calculator-grid">'+
 '<div class="field"><label for="bid">입찰가 (만원)</label><input id="bid" name="bid" inputmode="decimal" type="number" min="1" step="any" value="40000" required></div>'+
 '<div class="field"><label for="depositRate">입찰보증금 비율 (%)</label><input id="depositRate" name="depositRate" type="number" min="0" max="100" step="any" value="10" required></div>'+
 '<div class="field"><label for="taxRate">취득 관련 비용 가정률 (%)</label><input id="taxRate" name="taxRate" type="number" min="0" max="100" step="any" value="1.1" required></div>'+
 '<div class="field"><label for="otherCost">기타 비용 (만원)</label><input id="otherCost" name="otherCost" type="number" min="0" step="any" value="2000" required></div>'+
 '<div class="field"><label for="expectedResale">예상 처분가 (만원)</label><input id="expectedResale" name="expectedResale" type="number" min="0" step="any" value="50000" required></div></div>'+
 '<button type="submit" class="btn primary" style="margin-top:18px">가정으로 계산</button></form></section>'+
 '<section class="panel"><h2>예상 결과</h2><div id="calculation-result">'+(result?renderCalculation(result):'<div class="empty" style="padding:28px">왼쪽 입력값으로 계산을 실행하세요.</div>')+'</div><p class="alert">단순 산술 도구입니다. 법적 보증금 비율, 실제 취득세·양도세, 명도비용, 이자, 중개비 등은 사건과 조건에 따라 다릅니다. 법률·세무·투자 자문이 아닙니다.</p></section></div>';
}
export function renderCalculation(r){
 return '<div class="calc-result"><div class="statline"><span>입찰보증금 (낙찰대금에 포함)</span><strong>'+won(r.deposit)+'</strong></div><div class="statline"><span>보증금 제외 납부 잔액</span><strong>'+won(r.remaining)+'</strong></div><div class="statline"><span>취득 관련 비용 가정</span><strong>'+won(r.tax)+'</strong></div><div class="statline"><span>총 취득 비용 (보증금 중복 없음)</span><strong>'+won(r.total)+'</strong></div><div class="statline"><span>처분가 가정 대비 차액</span><strong>'+won(r.profit)+'</strong></div><div class="statline"><span>단순 수익률 (차액/총비용)</span><strong>'+percent(r.roi)+'</strong></div></div>';
}