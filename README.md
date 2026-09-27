# 🚦 부동산 신호등 PRO — 자체 호스팅 대시보드

원본 사이트(`https://kdmin7.github.io/realestate-traffic-light/index.html`)의 기능을 그대로 옮기고,
① 판단 근거를 정량 점수 모델로 강화하고 ② 과거 추세 대비 고/저평가율을 그래프로 보여주도록 확장한 버전입니다.

## 폴더 구성

```
realestate-dashboard/
├── index.html          # 강화된 대시보드 (이걸 배포하세요)
├── data.js             # 56개 지역 데이터 + 점수 계산 결과 (JS 객체)
├── original/index.html # 원본 사이트 코드 그대로 (요청하신 "원본 그대로" 백업본)
└── README.md
```

`index.html`과 `data.js`만 있으면 동작하는 완전한 정적 웹사이트입니다. 별도 서버(Node/DB) 없이
**정적 파일 호스팅**만으로 바로 배포할 수 있습니다.

## 1. 배포 방법 (택 1)

- **GitHub Pages**: 이 폴더를 새 저장소(`main` 브랜치 root)에 올리고 Settings → Pages에서 활성화
- **Netlify / Vercel**: 폴더를 드래그 앤 드롭하거나 `vercel` / `netlify deploy` 실행
- **자체 서버(Nginx)**:
  ```nginx
  server {
    listen 80;
    server_name yourdomain.com;
    root /var/www/realestate-dashboard;
    index index.html;
  }
  ```
  파일을 `/var/www/realestate-dashboard`에 복사 후 `nginx -s reload`
- **가장 간단한 로컬 테스트**: `python3 -m http.server 8000` 실행 후 `http://localhost:8000`

## 2. 판단 근거를 강화한 부분 (요청 2번)

원본 사이트는 "신호(🟢🟡🔴)"가 어떤 기준으로 산출됐는지 백엔드 에이전트(re-timing-judge)의
내부 규칙에 의존해 프론트엔드에서는 결과값만 보여줬습니다. 이번 버전은 **모든 계산을 브라우저에서
직접 수행**하고 공식을 화면에 공개합니다.

| 지표 | 산출 방법 | 가중치 |
|---|---|---|
| 밸류에이션 갭 | 5년 로그회귀 추세선(최근 12개월 제외) 대비 현재가 괴리율의 56개 지역 내 백분위 | 35% |
| 모멘텀 | 최근 실거래가 변동률의 백분위 | 15% |
| 거래 유동성 | 전월 대비 실거래 건수 증감률의 백분위 | 15% |
| 리스크 | 4대 리스크(고점·환금성·금리·치안) 지표 역산 백분위 | 20% |
| 전세가율 | 전세/매매가 비율 백분위 (갭투자 리스크 대리지표) | 15% |

`data.js`의 `ENHANCED_DATA.weights` 값을 바꾸면 대시보드 전체 점수·신호가 즉시 재계산되도록
`index.html`의 스크립트가 구조화되어 있습니다.

## 3. 과거 대비 고/저평가 시각화 (요청 3번)

- 지역 클릭 시 뜨는 상세 모달에서 **61개월 시세 추이 vs 구조적 적정가(추세선)** 라인 차트 제공
- 대시보드 상단에 **전체 56개 지역 고평가/저평가 TOP 8 랭킹**과
  **종합점수 × 밸류에이션 괴리율 산점도**로 전체 분포를 한눈에 확인 가능
- 괴리율(%) = `(현재가 − 추세선 적정가) / 추세선 적정가 × 100`

## ⚠️ 반드시 확인하세요 — 데이터의 한계

- **현재 스냅샷 값**(전용84 평균가, 전체 평균가, 실거래 건수, 모멘텀·리스크 지표)은 원본 사이트에
  박혀 있던 2026-09-19 기준 정적 데이터를 그대로 사용했습니다. 실시간으로 자동 갱신되지 않습니다.
- **61개월 과거 시계열과 "구조적 적정가" 추세선은 실제 국토부 실거래가 이력이 아니라, 위 스냅샷의
  모멘텀·리스크 수치를 바탕으로 방법론을 보여주기 위해 만든 모델링(시뮬레이션) 데이터**입니다.
  실제 서비스로 쓰시려면 아래처럼 `data.js`의 각 지역 `history` 배열을 국토부 실거래가 공개 API의
  월별 평균가로 교체하시면 됩니다. (`fairSeries`는 `history`로부터 코드가 자동 재계산하도록
  바꿔서 매번 실데이터 기준으로 회귀선을 새로 그리게 할 수 있습니다.)
- 금리·범죄·학군 등 상단 KPI 카드도 스냅샷 값이며, 실시간 연동을 원하시면 한국은행 ECOS API,
  경찰청 공공데이터 API를 별도로 호출해 해당 값을 갱신하는 코드가 필요합니다(원본 저장소의
  `MCP/` 폴더가 이 역할을 하던 백엔드 수집기입니다 — 정적 페이지에는 포함되지 않았습니다).
- 본 대시보드는 투자 판단을 돕는 참고 도구이며, 투자 자문이 아닙니다.

## 4. 실데이터 연동 가이드 (요약)

1. 국토부 실거래가 공개 API(또는 KB부동산 리브온 시계열)에서 지역별 월별 평균가를 수집
2. `data.js`의 해당 지역 객체 `history` 배열(길이 61, 오래된 순 → 최신 순)을 교체
3. `index.html`에 아래처럼 회귀 계산 함수를 추가해 `fairSeries`/`gapPct`를 매번 실데이터 기준으로 재계산
   ```js
   function computeFairValue(history) {
     const xs = history.slice(0, 49).map((_, i) => i);
     const ys = history.slice(0, 49).map(v => Math.log(v));
     const n = xs.length;
     const sx = xs.reduce((a,b)=>a+b,0), sy = ys.reduce((a,b)=>a+b,0);
     const sxx = xs.reduce((a,x)=>a+x*x,0), sxy = xs.reduce((a,x,i)=>a+x*ys[i],0);
     const slope = (n*sxy - sx*sy) / (n*sxx - sx*sx);
     const intercept = (sy - slope*sx) / n;
     const fair = xs2 => xs2.map(m => Math.exp(intercept + slope*m));
     return { fairSeries: fair([...Array(61).keys()]), fairNow: Math.exp(intercept + slope*60) };
   }
   ```
4. 금리·범죄·학군 KPI는 각 공공데이터 API 응답값으로 상단 카드의 텍스트만 교체하면 됩니다.
