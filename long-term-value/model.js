/* Transparent, deterministic valuation calculations. No API key or hidden ML forecast. */
(function (root, factory) {
  const value = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = value;
  root.FiveYearModel = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  function finitePositive(v) {
    const n = Number(v);
    return Number.isFinite(n) && n > 0 ? n : null;
  }
  function round(v, d) {
    return Math.round((v + Number.EPSILON) * 10 ** d) / 10 ** d;
  }
  function addYears(price, pct, years = 5) {
    const p = finitePositive(price), growth = Number(pct);
    if (p === null || !Number.isFinite(growth) || growth <= -100) return null;
    return round(p * (1 + growth / 100) ** years, 2);
  }
  function monthsApart(start, end) {
    if (!/^[0-9]{6}$/.test(start || "") || !/^[0-9]{6}$/.test(end || "")) return 0;
    return (Number(end.slice(0,4)) - Number(start.slice(0,4))) * 12 +
      Number(end.slice(4)) - Number(start.slice(4));
  }
  function quality(c, doc) {
    const latest = finitePositive(c.last12_median);
    const complete = doc && doc.coverage && doc.coverage.sale_months >= 48;
    const span = monthsApart(c.first_sale_month, c.last_sale_month);
    const months = (c.sale_months || []).length;
    const base = c.first12_count || 0;
    const count = c.last12_count || 0;
    if (!complete) return {rank:"보류", reason:"지역 5년 원천자료의 월별 수집범위가 충분하지 않습니다."};
    if (!latest || count < 5) return {rank:"보류", reason:"최근 12개월 동일 단지·면적구간 매매 5건 미만입니다."};
    if (span < 36 || base < 3 || months < 10) return {rank:"제한적", reason:"장기 관측기간·초기표본이 부족하여 5년 추세 비교 신뢰도가 낮습니다."};
    if (count < 10 || months < 24) return {rank:"보통", reason:"과거 비교는 가능하지만 표본이 적어 불확실성이 큽니다."};
    return {rank:"상대적으로 양호", reason:"관측기간과 표본 최소요건을 충족하지만 층·향·수리상태를 통제한 감정평가는 아닙니다."};
  }
  function assess(c, doc, growths, selectedPrice) {
    if (!c || !doc) return null;
    const base = finitePositive(c.last12_median);
    const q = quality(c, doc);
    const annualPrices = (c.annual || []).map(v => finitePositive(v[1])).filter(v => v !== null);
    const percentile = base && annualPrices.length >= 3
      ? round(100 * annualPrices.filter(v => v <= base).length / annualPrices.length, 0) : null;
    const trade = finitePositive(selectedPrice);
    const delta = base && trade ? round((trade / base - 1) * 100, 1) : null;
    const g = growths || [-2, 2, 5];
    const scenarios = g.map(value => ({
      growth: Number(value), projected: addYears(base, Number(value)),
      change: round(((1 + Number(value) / 100) ** 5 - 1) * 100, 1)
    }));
    return {
      quality:q, current:base, selectedTrade:trade, selectedDeltaPct:delta,
      observedCagrPct:c.observed_cagr_pct,
      annualNominalPositionPct:percentile, scenarios,
      jeonseRatePct:c.jeonse_rate_pct,
      caution:"과거 매매 중위값과 명목 상승률은 구조적 적정가격이 아니며 미래 수익률 예측치가 아닙니다."
    };
  }
  return { assess, quality, addYears, monthsApart };
});