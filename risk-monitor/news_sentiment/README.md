# 한국은행 신뉴스심리지수 → 서울 아파트 하방위험: 독립 SHADOW 연구

**상태: SHADOW_WAITING_DATA / RESEARCH_ONLY.** 이 연구는 기존 ver0·ver1.0, 대시보드 점수, 유동성·GSADF·HaR 모형을 변경하지 않는다. 모델의 `publicScore`는 무조건 `null`이고 `compositeEligible=false`이다. 검증을 통과하더라도 자동으로 편입하지 않는다.

## 근거와 현재까지의 실제 결과 (2026-11-16)

- 한국은행, 「언어모형을 활용한 新뉴스심리지수」, BOK 이슈노트 2026-21, 2026-09-01: 신NSI는 소비자심리지수에 약 **1개월**, 기업심리지수에 약 **2개월** 선행할 때 상관계수가 가장 컸고, 기대뉴스심리지수(Expected NSI)가 일부 공식 심리지표와 더 강한 관련을 나타냈다. **이 결과는 주택가격에 대한 선행성 검증이 아니다.**
  https://www.bok.or.kr/portal/bbs/P0002353/view.do?nttId=11064365&menuNo=200433
- 한국은행, 「新뉴스심리지수 공표」, 2026-09-01: 9월부터 ECOS에 매주 자료 갱신. 공식 계열의 항목코드·원자료·공표 빈티지를 별도 확인해야 한다.
  https://www.bok.or.kr/portal/bbs/B0000502/view.do?nttId=11064326&menuNo=201265
- 한국은행 ECOS: https://ecos.bok.or.kr/
- 서울 아파트가격 선행성: **본 모듈에서 아직 실데이터 표본외 추정 결과 없음**. 검증 대기. 임의의 RMSE·상관계수·예측확률을 표시하지 않는다.

직접 관련된 서울 아파트 뉴스심리 선행연구 4편 및 BOK 신NSI와의 차이는 [LITERATURE.md](LITERATURE.md)에 기록했다.

## 가설과 비교

- H0: 신NSI는 기존 모형의 out-of-sample 서울 아파트 수익률 예측오차를 개선하지 않는다.
- H1: 신NSI 수준, 전월 변화, (추가로 확보 시) Expected NSI가 모형에 **증분적인 예측정보**를 제공한다.
- 기준모형: 가격변화율 AR(1·2) + 실질금리(t−5) + 초과유동성(t−10) + KOSPI 월수익률(t−1) (논문의 시차 구조를 참고한 Ridge 비교군이며 **논문 ARIMAX(2,0,0) 자체를 재현한 것은 아님**)
- 증강모형: 동일 5개 변수 + 신NSI 수준 + 신NSI 변화량. Expected NSI는 공식 계열이 확보된 때 **별도 실험**한다.
- 목적변수: 서울 아파트 공식 가격지수의 향후 1·3·6개월 **누적 로그수익률**; 부가 검정은 수익률 음수 여부.
- 월별 `t` 예측 시 `t-1` 이전 설명변수만 사용하고, `t-1`의 가격지수부터 `t+h-1`까지의 미래 변화를 목표로 한다.
- 매월 확대하는 expanding-window Ridge 회귀. 고정 규제강도 10. 학습셋은 결과 관측 종료월 < 예측월인 표본만 허용하여 **수평선 누출(embargo)** 방지. 표준화 통계도 학습셋에서만 산출한다.
- 지표: 기준/증강 RMSE, MAE, 하락 재현율, 오경보율, 방향 정확도, 겹치는 수익률의 HAC(대역폭 h-1) Diebold-Mariano 근사 검정(설명용)과 **중첩 예측모형용 Clark–West 단측 HAC 근사 검정**. 1·3·6개월 탐색의 family-wise 다중검정은 Holm 보정.
- 연구상 사전 판정 기준: 1) OOS 24개월 이상, 2) 하락월 12건 이상, 3) RMSE 3% 이상 감소, 4) Clark–West 단측 HAC p<0.05 및 1·3·6개월 Holm 보정 p<0.05, 5) 오경보율 5%p 초과 악화 없음. 이 **탐색적 기준**을 만족해도 자동 종합점수 승격 금지.

## 입력 계약 (3개 공식 출처 검증 CSV)

민감한 API 키와 원본 R2 자료를 Git에 업로드하지 않는다. **동일 월·동일 관측 정의·원자료 빈티지**를 확인하여 개인 저장소나 실행 환경에 다음 CSV를 배치한다.

```text
research-data/nsi/seoul_price.csv
month,price_index
2005-01,100.0

research-data/nsi/new_nsi.csv
month,new_nsi,expected_nsi
2005-01,99.3,             # expected_nsi가 없으면 열 전체 생략 가능

research-data/nsi/controls.csv
month,real_rate,excess_liquidity,kospi_return
2005-01,2.10,0.01,0.025
```

위 숫자는 **컬럼 형식만 보여주는 예시이며 실제 관측값이 아니다.** 파일은 배포하지 않는다. 공식 신NSI 시계열과 기존 NSI는 혼합하지 않으며 `new_nsi`로 받기 전에 표본 시작·산식 버전·시리즈코드·단위를 확인한다. Expected NSI가 없는 경우 결과에 `NOT_PROVIDED`를 남긴다.

서울 아파트가격은 KB 또는 한국부동산원 전국주택가격동향조사 중 하나의 공식 **서울 아파트 월별 동일 계열**을 일관되게 사용하고, 주택가격 조사 방식 변경이나 개편에 따른 단절을 표시한다. 기존 `data.js`의 구별 **5년 실거래 단순평균**은 거래구성 변화와 표본 기간 문제로 장기 모형에 직접 사용하지 않는다. 수집 지표를 점검할 때 이름·단위·원자료 관측치·대상기간이 일치하지 않으면 실험을 중단한다.

단위에 주의: `real_rate`는 일관되게 %p, `excess_liquidity`는 원래 정의된 Marshall K의 로그갭 등 단일 단위, `kospi_return`은 월 로그수익률(소수). 혼합 시 결과는 무효다. 결과 JSON은 데이터 출처와 입력 파일 해시가 자동 첨부되지 않으므로 운영 승인에서 **별도 provenance/vintage 패킷이 필수**다.

## 실행 및 출력

```bash
python -m pip install numpy
python risk-monitor/news_sentiment/run_research.py
python -m unittest discover -s risk-monitor/news_sentiment/tests -p 'test_*.py' -v
```

원본이 없으면 `risk-data/news-sentiment/summary.json`이 `SHADOW_WAITING_DATA`로 남는다. 유효한 3종 자료가 있어도 `SHADOW_VALIDATION`/후행적 검증만 기록한다. 아래 생산 검증 전에는 **실시간 경보, 가격전망, 위험 점수 편입을 사용하지 않는다.**

1. 한국은행 2005~2026년 신NSI가 **2026년 개발된 산식을 과거 뉴스에 다시 적용해 만든 소급계열인지** 공식 확인. 소급계열이면 2008·2020년 결과는 역사적 재현이며 그 당시 실시간으로 예측 가능했다는 뜻이 아님.
2. 원시 데이터 발표일, 오리지널 빈티지, revisions, 국토부 신고지연·가격지수 발표시차를 저장한 시점일치(PIT) 백테스트 재수행.
3. 시차 1/2/3/6개월·금리상승기/하락기·2008/2020/2022 위기 구간별 split, horizon 선택 다중검정 통제 및 계열상관·구조변화 검정.
4. 뉴스·KOSPI·가격의 내생성/공선성 점검, 가격 수준과 MoM(3MA) 차별 검정, 서울 vs 경기 강건성, NSI 제외 ablation 및 기대NSI/부정심리 추가 ablation.
5. 사용자 승인 + 증거 패킷 해시로만 향후 composite gate 승격 검토. 이 구현에는 의도적으로 승격 코드가 존재하지 않는다.

## 모듈 파일

- `model.py`: 정렬·수평선 누출 방지·상호 동일 OOS 표본 회귀와 평가.
- `run_research.py`: 독립 CLI; 입력 미존재/불량에 대한 fail-closed.
- `tests/test_model.py`: 피처 시점·embargo·누락·사전 격리·연속성 회귀 테스트.
- `risk-data/news-sentiment/summary.json`: 초기 데이터 부재 상태. 메인 점수와 분리.
- `.github/workflows/test-new-nsi.yml`: PR 연구모듈 CI. 배포/데이터 수집/메인 수정 없음.

## 2026-11-19 데이터 수집·입력 준비 추가 (PR #41)

- **BOK 원자료 자동 발견:** `ecos_nsi_discovery.py --mode catalog`가 ECOS `StatisticTableList`를 확인하고 '뉴스심리지수' 통계표 후보를 찾는다. `--mode items --table-code <검증된코드>`로 `StatisticItemList`의 월간 항목코드·공표기간·단위를 조사한다. 구NSI와 신NSI가 동일 코드 내 갱신된 경우 연구자가 2026년 9월 방법 변경과 소급기간을 확인하기 전에는 그대로 합치지 않는다. **아직 한국은행 계열코드 및 항목코드를 공식 확인하지 못했다.**
- **명시적 승인 후 수집:** `ecos_nsi_discovery.py --mode export --approval-json path/to/approved.json`으로만 월별 CSV를 추출한다. 검토자·승인날짜·한국은행 원문 링크·신NSI 산식버전·소급산출 여부가 없는 승인 계약은 실패한다. 전체 수집건수 불일치나 통계표코드·항목코드 불일치도 즉시 중단한다. `new_nsi.provenance.json`에 원본지문을 남기고 `pitVerified=false`로 기록한다.
- **서울 아파트 가격지수:** 한국부동산원 정식 월간 시계열의 서울/아파트/매매 **지수** 원본을 내려받고, `prepare_reb_price.py --reb-csv ORIGINAL.csv --approval-json approved-reb.json --month-column ... --price-column ...`로 변환한다. 180개월 미만·월결측·중복·기준연도 변경과 혼동되는 급격한 단절·평균매매가격 혼합은 차단한다.
- **공표시차 사전검증:** `publication_audit.py --release-calendar release_dates.csv --start 2015-01 --end 2026-10 --output research-data/nsi/pit-calendar.json`을 실행한다. `release_dates.csv`는 `series,month,first_published_date` 컬럼을 갖는다. 월 t의 **20일 KST**에 발행하는 예측을 가정하고 (t−1)월 서울지수와 신NSI가 실제 공표되었는지 점검한다. **공표 달력 검증만 통과해도 원시 발표 당시의 '값'을 담은 빈티지 기록 없이는 fullPITVerified=false이다.**
- **민감 자료 보호:** `.gitignore`가 `research-data/nsi/*.csv|*.json` 및 연구 성능증거 원본을 공개 Git에 올리지 않도록 막는다. API키는 `ECOS_API_KEY` 환경변수/Actions Secret에서만 읽는다.
- **지표 분리:** `risk-monitor/leading_indicators/`에 17개 후보를 `CANDIDATE_PRIORITY / CANDIDATE_SECONDARY / CONTROL_ONLY / QUARANTINED`로 나누고, 표본외·PIT·오경보 기준을 충족한 결과만 '사용자 검토 후보'로 남긴다. 통합위험 계산 경로는 변경되지 않는다.

### 바로 실행 가능한 단계

```bash
python -m unittest discover -s risk-monitor/news_sentiment/tests -p 'test_*.py' -v
python -m unittest discover -s risk-monitor/leading_indicators/tests -p 'test_*.py' -v
export ECOS_API_KEY="<발급받은API키>" # 터미널/서버 secret에서만, 저장소 commit 금지
python risk-monitor/news_sentiment/ecos_nsi_discovery.py --mode catalog
# 후보 STAT_CODE를 확인한 뒤:
# python risk-monitor/news_sentiment/ecos_nsi_discovery.py --mode items --table-code VERIFIED_STAT_CODE
# 공식 원본을 검토하고 승인 계약을 작성한 경우에만 export 실행
python risk-monitor/leading_indicators/review_candidates.py
```

### 실증 검증이 남는 이유

2026년 9월에 새로운 방법론으로 처음 공식 발표된 신NSI는 2026년 11월 현재 실시간 운영기간이 수개월에 불과하다. **2026년 이전 소급 NSI로 검증한 2008·2020·2022 구간은 사후 재현이며, 당시 공개되어 있던 지표를 사용한 실시간 OOS 검증으로 주장할 수 없다.** 공식 원자료의 버전과 재수정 빈티지 확보 이전에 1·3·6개월 실전 예측의 통계적 유의성을 확정할 수 없다. 향후 새로운 전망 기원을 고정해 1/3/6개월 평가를 누적하고, 기존 ARIMAX 모형과 각 후보의 증분 예측력·오경보를 재검증해야 한다.
