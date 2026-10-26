/* All-56-region apartment trade drilldown from verified, sanitized static snapshots.
 * Never load private R2 or Google Drive data from the browser. */
let tradeDetailRows = [];
let tradeDetailRegion = null;
let tradeDetailSeq = 0;
let tradeDetailLoadedMonths = [];
const tradeDetailPageSize = 120;

function tradeSafe(value) {
  return String(value ?? '').replace(/[&<>"']/g, c =>
    ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
}
function tradePrice(value) {
  const n = Number(String(value || '').replace(/,/g,''));
  return Number.isFinite(n) && n > 0
    ? (n / 10000).toLocaleString('ko-KR',{maximumFractionDigits:4}) + '억원'
    : '미확인';
}
function tradeEl(id) { return document.getElementById(id); }
function tradeReset(region) {
  tradeDetailRegion = region;
  tradeDetailRows = [];
  tradeDetailLoadedMonths = [];
  tradeEl('tradeDetailPanel').hidden = false;
  tradeEl('tradeDetailSearch').value = '';
  tradeEl('tradeDetailSearch').disabled = true;
  tradeEl('tradeDetailSelected').textContent = '';
  tradeEl('tradeDetailRows').innerHTML = '';
  tradeEl('tradeDetailStatus').textContent = '공식 거래 상세 자료를 확인하는 중…';
}
async function tradeJson(url) {
  const response = await fetch(url, {cache:'no-store'});
  if (!response.ok) throw new Error('HTTP ' + response.status + ' (' + url + ')');
  return response.json();
}
async function showApartmentTrades(name) {
  const region = REGIONS.find(r => r.name === name);
  const id = ++tradeDetailSeq;
  if (!region) return;
  tradeReset(region);
  try {
    const index = await tradeJson('trade-details/index.json');
    if (id !== tradeDetailSeq) return;
    const entry = index.regions && index.regions[name];
    if (!entry || !/^[0-9]{5}\.json$/.test(entry.file)) {
      throw new Error('지역 연결정보 없음');
    }
    const payload = await tradeJson('trade-details/' + entry.file);
    if (id !== tradeDetailSeq) return;
    if (payload.schema !== 1 || payload.region !== name || !Array.isArray(payload.rows)
        || !Array.isArray(payload.months) || !payload.coverage
        || payload.coverage.missing_scopes !== 0) {
      throw new Error('상세자료 검증 실패');
    }
    tradeDetailRows = payload.rows.filter(row =>
      row && typeof row.apt === 'string' && typeof row.date === 'string');
    tradeDetailLoadedMonths = payload.months;
    const activeMonthLabels = (typeof MONTHS !== 'undefined' ? MONTHS.slice(-2) : []).map(x => x.replace('-',''));
    const stale = activeMonthLabels.join(',') !== payload.months.join(',');
    const count = tradeDetailRows.length;
    const expected = Number((region.trades.match(/^[\d,]+/) || ['0'])[0].replace(/,/g,''));
    const actual = payload.months.map(m => m.slice(4) + '월 ' + Number(payload.by_month?.[m] || 0) + '건').join(' / ');
    let message = '원천 확인 ' + count.toLocaleString() + '건 (' + actual + ') · 화면 집계 '
      + expected.toLocaleString() + '건 · 해제·무효 ' + Number(payload.excluded_rows || 0)
      + '건 제외 · 원본 검증 ' + payload.coverage.verified_scopes + '개 파일';
    if (count !== expected) message += ' · 집계 차이(수집 시각·정정·해제 등) 검토 필요';
    if (stale) message += ' · 상세자료 기준월이 화면과 다름: 갱신 대기';
    message += ' · 생성일 ' + String(payload.updated_at_kst || '').slice(0,16);
    tradeEl('tradeDetailStatus').textContent = message;
    tradeEl('tradeDetailSearch').disabled = false;
    renderApartmentTrades();
  } catch (error) {
    if (id !== tradeDetailSeq) return;
    tradeEl('tradeDetailStatus').textContent =
      '상세 원자료를 아직 불러오지 못했습니다. 거래 건수 집계와 개별 상세자료는 별도로 갱신됩니다. '
      + 'trade-details/build-report.json 또는 GitHub Actions의 상세자료 생성 작업을 확인하세요. '
      + '(' + String(error.message || error).slice(0,130) + ')';
    tradeEl('tradeDetailRows').innerHTML = '<tr><td colspan="4">검증된 거래 상세자료를 준비 중입니다. 거래를 임의로 생성하지 않습니다.</td></tr>';
  }
}
function renderApartmentTrades() {
  const query = tradeEl('tradeDetailSearch').value.trim().toLowerCase();
  const found = tradeDetailRows.map((row, index) => ({row, index})).filter(({row}) =>
    !query || [row.apt,row.city,row.dong,row.jibun,row.date].join(' ').toLowerCase().includes(query));
  const visible = found.slice(0,tradeDetailPageSize);
  tradeEl('tradeDetailRows').innerHTML = visible.length
    ? visible.map(({row,index}) =>
      '<tr><td>' + tradeSafe(row.date) + '</td><td><button type="button" onclick="selectApartmentTrade('
      + index + ')">' + tradeSafe(row.apt || '단지 미기재') + '</button><div>'
      + tradeSafe([row.city,row.dong,row.jibun].filter(Boolean).join(' ')) + '</div></td><td>'
      + tradeSafe(row.area) + '㎡ / ' + tradeSafe(row.floor) + '층</td><td>'
      + tradePrice(row.price) + '</td></tr>').join('')
    : '<tr><td colspan="4">해당 기간에 거래가 없거나 검색 결과가 없습니다.</td></tr>';
  const old = tradeEl('tradeDetailPageInfo');
  if (old) old.textContent = '표시: ' + visible.length.toLocaleString() + ' / 검색 ' +
    found.length.toLocaleString() + '건' + (found.length > visible.length ? ' · 아래 검색창에서 단지명·동·지번을 입력하면 나머지도 검색됩니다.' : '');
}
function selectApartmentTrade(index) {
  const row = tradeDetailRows[index];
  if (!row || !tradeDetailRegion) return;
  const near = tradeDetailRows.filter(item =>
    item.apt === row.apt && item.dong === row.dong && item.jibun === row.jibun
    && Math.abs(Number(item.area) - Number(row.area)) <= 3)
    .map(item => Number(item.price)).filter(x => Number.isFinite(x) && x > 0).sort((a,b)=>a-b);
  const n = near.length;
  const middle = n ? (near[Math.floor((n-1)/2)] + near[Math.floor(n/2)])/2 : null;
  const compared = n >= 3
    ? '조회된 2개월 같은 단지·유사면적 ' + n + '건 중위값 ' + tradePrice(middle)
      + ' 대비 ' + ((Number(row.price)/middle-1)*100).toFixed(1) + '% (적정가 아님)'
    : '동일 단지·면적 거래가 3건 미만이므로 단지별 고·저평가 판단 보류';
  const box = tradeEl('tradeDetailSelected');
  box.innerHTML = '<b>' + tradeSafe(row.apt) + '</b>'
    + '<div>주소: ' + tradeSafe([row.city,row.dong,row.jibun].filter(Boolean).join(' ')) + '</div>'
    + '<div>계약일: ' + tradeSafe(row.date) + ' · 전용 ' + tradeSafe(row.area)
    + '㎡ · ' + tradeSafe(row.floor) + '층 · 건축년도 ' + tradeSafe(row.year) + '</div>'
    + '<div>거래금액: ' + tradePrice(row.price) + ' · 거래유형: ' + tradeSafe(row.type || '미기재') + '</div>'
    + '<div>' + tradeSafe(compared) + '</div>'
    + '<div>지역 전체 5년 추세 대비 ' + tradeDetailRegion.gapPct.toFixed(1)
    + '% (이 단지의 고·저평가율이 아님)</div>';
  if (tradeDetailRegion.province === 'seoul') {
    const link = new URL('long-term-value/index.html', location.href);
    const code = tradeDetailLoadedMonths.length ? (row.code || '') : '';
    link.searchParams.set('district', code);
    link.searchParams.set('apt', row.apt);
    link.searchParams.set('dong', row.dong || '');
    link.searchParams.set('jibun', row.jibun || '');
    link.searchParams.set('size', row.area || '');
    link.searchParams.set('price', String(row.price || ''));
    const anchor = document.createElement('a');
    anchor.href = link.href;
    anchor.textContent = '이 아파트의 5년 장기 가격평가 보기 →';
    anchor.style.cssText = 'display:inline-block;margin-top:10px;color:var(--buy);font-weight:700';
    box.appendChild(anchor);
  } else {
    const info = document.createElement('div');
    info.textContent = '경기도 5년 개별 단지 평가 기능은 별도로 확장 예정입니다.';
    box.appendChild(info);
  }
  box.scrollIntoView({behavior:'smooth',block:'nearest'});
}
