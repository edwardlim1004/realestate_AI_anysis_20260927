# 부동산 위험 모니터 v6 — 계산 감사형 GitHub Pages

공개 사이트: https://edwardlim1004.github.io/realestate_AI_anysis_20260927/

이 저장소는 두 성격이 다른 분석을 한 화면에 표시합니다.

1. **대한민국 거시 부동산 위험 모니터**: OECD·BIS 공식 분기자료의 역사 백분위
2. **서울 25구·경기 31개 시군 상대 비교**: 국토교통부 실거래가 API 기반 지역 비교 실험모델

두 점수는 서로 대체할 수 없습니다. 거시 위험점수와 지역 상대점수 모두 폭락확률·수익률 예측·매수추천이 아닙니다.

## 화면에서 가장 먼저 볼 것

- `공식축 3/4`: 가격평가·신용·모멘텀은 반영 중이고 유동성은 독립 SHADOW 검증 중이라는 뜻입니다.
- `WAITING DATA`: 자료 또는 검정요건을 충족하지 않아 점수를 만들지 않았다는 뜻입니다.
- 위험신호 카드 클릭: 현재값, 산식, `Observation_Key`, 논문 위치와 한계를 확인합니다.
- `원자료 CSV`·`수정 이력`·`출처 목록`: 숫자를 외부에서 재계산할 때 사용합니다.

## 개별 아파트 5년 장기 가격평가 (독립 모듈)

- 웹: https://edwardlim1004.github.io/realestate_AI_anysis_20260927/long-term-value/
- 서울 25개 구 동일 단지·지번·유사 전용면적의 공식 5년 실거래 중위값, 거래량 및 전세 보증금 비교
- Theil–Sen 강건 로그추세와 현재 가격의 상대적 괴리, 사용자 가정에 따른 향후 5년 복리 가격 시나리오 분리
- 비공개 R2에서 GitHub Actions가 집계 JSON을 생성하므로 웹과 Git에 인증키를 노출하지 않음
- **최초로 Actions → Build Apartment Five-Year Valuations → Run workflow를 성공시켜야 데이터가 표시됨**. 자세한 내용은 [long-term-value/README.md](long-term-value/README.md).
- 역사적 추세·사용자가 입력한 성장률은 미래 확정 전망이나 구조적 적정가격이 아님.

## 거시 위험 계산

| 축 | 공식 데이터 | 계산 |
|---|---|---|
| 가격평가 | OECD 표준화 PIR·PTR | 각 계열의 expanding 역사 백분위 평균 |
| 신용취약성 | BIS 신용/GDP 갭·가계 DSR | 각 계열의 expanding 역사 백분위 평균 |
| 모멘텀 | OECD 실질주택가격지수 | 전년동기비의 expanding 역사 백분위 |
| 유동성 | ECOS M2·Lf·L·CPI·명목 GDP | 독립 SHADOW 모듈에서 9개 게이트 검증 중, 승인 전 종합점수 제외 |
| GSADF | 실질가격·PIR·PTR | 2,000회 Monte Carlo 등 엄격검정 전 `WAITING DATA` |
| HaR | IMF House Prices at Risk 변수군 | 분위수회귀·표본외 검증 전 `WAITING DATA` |

종합위험 백분위는 유효한 `가격평가·신용·유동성·모멘텀` 축을 동일가중 평균합니다. 최소 세 축이 있어야 표시합니다. `0~100`은 위기확률이 아니라 그 국가의 과거 관측치 대비 위치입니다. GREEN/WATCH/AMBER/RED 구간도 화면 운영용 경계이며 논문이 제시한 붕괴확률 기준이 아닙니다.

### 유동성 모듈의 격리와 승격

유동성은 `risk-monitor/liquidity/`에서 독립적으로 수집·계산·검증합니다. `SHADOW` 상태에서는 그림자 점수가 만들어져도 본체 어댑터가 `score=null`로 차단하므로 기존 종합점수에 영향이 없습니다. 공식계열·표본·연속성·발표시차·계산·no-lookahead 6개 자동 게이트와 예측 백테스트·빈티지 안정성·사람 검토 3개 게이트를 모두 통과해야 `ELIGIBLE`이 됩니다. 이후 승인된 검증 지문이 일치할 때만 `ACTIVE`로 승격되어 4번째 종합축에 편입됩니다. 세부 절차는 [유동성 모듈 README](risk-monitor/liquidity/README.md)를 따릅니다.

## 지역 상대 비교의 제한

- 전용 80~90㎡ 월별 **단순평균**이므로 단지·동·층·연식·거래구성이 달라지면 가격이 크게 움직일 수 있습니다.
- 현재월은 신고가 끝나지 않은 잠정치입니다. 평가가격과 거래유동성은 최신 **완결월**을 사용하도록 수정했습니다.
- 로그회귀 추세선은 구조적 적정가격이 아닙니다.
- 현재 `momentum`과 `risk` 일부는 완전 자동화 전입니다. 화면에서도 `검증 중`으로 표시합니다.
- 전세가율 100% 초과, 전월세전환율 표본 10건 미만, 추세괴리 절대값 50% 초과는 `data-quality-report.json`에 경고로 기록합니다.
- 같은 고정 금리를 모든 지역에서 빼면 순위가 같으므로 임대점수는 내재임대수익률 자체의 상대 백분위를 사용합니다. 4.39%는 과거 시나리오 비교값일 뿐 최신 주담대금리로 표시하지 않습니다.

## 증분 업데이트 구조

### 지역 실거래 — 매일 06:00 KST

`.github/workflows/update-data.yml`

1. 최근 매매 3개월·전월세 2개월만 재조회
2. 기존 캐시와 병합
3. `data.js` 재계산
4. 구조검증과 이상치 보고서 생성
5. 변경이 있을 때만 커밋

### 공식 거시위험 — 매주 월요일 08:15 KST

`.github/workflows/update-risk-monitor.yml`

1. OECD·BIS 공신력 있는 공개 원자료 조회
2. `Observation_Key` 기준 신규·수정치 upsert
3. 값이 수정되면 `risk-data/revision_history.csv`에 이전값과 새값 저장
4. 위험 백분위와 클릭형 계산 감사자료 재생성
5. 공식값 변화가 없으면 파일·커밋을 만들지 않음

BIS bulk 파일은 제공기관 구조상 전체 ZIP을 받지만, 저장소에서는 대상 5개국 계열만 추출해 관측치 단위로 upsert합니다. OECD는 기존 자료가 있으면 최근 약 3년만 중첩 재조회합니다.

### 유동성 SHADOW — 매월 20일 08:35 KST

`.github/workflows/update-liquidity-monitor.yml`

1. 독립 단위테스트와 fail-closed 활성화 계약 검사
2. ECOS M2·Lf·L·CPI·명목 GDP 공식 관측치 upsert
3. one-sided HP·expanding 백분위 계산과 9개 검증 게이트 갱신
4. 변경이 있을 때만 읽기 전용 어댑터로 화면 산출물 재생성
5. `ACTIVE` 전에는 기존 3개 종합축을 그대로 유지

## 주요 파일

```text
index.html                              대시보드 UI와 클릭형 계산 감사
data.js                                56개 지역 실거래·파생지표
risk-data.js                           거시위험 화면용 JS 데이터
risk-data/risk_raw.csv                 OECD·BIS 원자료 누적본
risk-data/revision_history.csv         공식 수정치 이력
risk-data/source_registry.csv          논문·보고서·정확한 사용 위치
risk-monitor/update_risk_data.py       공식 거시자료 증분 갱신·점수 계산
risk-monitor/liquidity/                격리된 ECOS 유동성 계산·검증·승격 모듈
risk-data/liquidity/                   유동성 원자료·수정이력·검증·빈티지 산출물
api-integration/fetch_molit_incremental.py
api-integration/fetch_jeonse_incremental.py
api-integration/merge_into_datajs.py
api-integration/validate_dashboard_data.py
data-quality-report.json               지역자료 구조·이상치 점검 결과
```

## 재현·디버깅

```bash
python risk-monitor/update_risk_data.py
python api-integration/validate_dashboard_data.py
python -m http.server 8000
```

브라우저에서 `http://localhost:8000`을 열고 다음 순서로 확인합니다.

1. 위험신호 카드 → 현재값과 `Observation_Key`
2. `risk-data/risk_raw.csv`에서 같은 키 검색
3. `risk-data/revision_history.csv`에서 수정치 확인
4. `risk-data/source_registry.csv`에서 공식자료·논문 위치 확인
5. `data-quality-report.json`에서 지역자료 이상치 확인

## 방법론의 직접 근거

- OECD Analytical House Prices Indicators
- BIS credit-to-GDP gaps, debt service ratios
- Borio & Lowe (2002), BIS Working Papers No.114
- Himmelberg, Mayer & Sinai (2005), JEP 19(4), pp.74-76
- Phillips, Shi & Yu (2015), GSADF/BSADF
- Mack, Martinez-Garcia & Huber, Dallas Fed WP165, section 3
- IMF Global Financial Stability Report, April 2019, chapter 2

정확한 URL과 사용 위치는 `risk-data/source_registry.csv`가 기준입니다.

## AI 업무 운영과 기능별 작업지시

[운영 규정·역할·플로우](operations/README.md) · [대화 정리표](operations/CHAT_INDEX.md)

`python tools/ai_task.py liquidity "M2 수준과 GDP 대비 과잉을 구분해 검증"`

기존 실행 경로를 유지하는 기능별 관리 입구입니다. 이 명령은 AI 작업지시문만 출력하며 자동 실행·배포를 하지 않습니다.
