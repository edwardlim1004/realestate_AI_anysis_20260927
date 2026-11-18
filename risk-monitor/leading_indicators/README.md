# 서울 아파트 선행지표 연구 등록부 (RESEARCH_ONLY)

이 폴더는 서울 아파트가격의 1·3·6개월 하방위험을 개선하는지 검정할 **후보지표 17개**를 기존 종합위험 점수와 분리한다. 연구 등록부가 어떤 판정을 해도 `publicCompositeScore=null`, `compositeEligible=false`이고, `risk-monitor/update_risk_data.py`와 기존 대시보드 계산을 변경하지 않는다.

## 운영 상태

- `CANDIDATE_PRIORITY`: 주택가격전망CSI, 국토연구원 주택시장소비심리지수, 한국은행 신NSI/Expected NSI, 서울 아파트 거래회전율. **검증 우선순위**이며 채택 확정이 아니다.
- `CANDIDATE_SECONDARY`: 전세-매매 갭, 준공후 미분양, 착공·인허가·입주공급, 주담대, 신용스프레드. 추가 표본외 검증 대상.
- `CONTROL_ONLY`: KOSPI·실질금리·Marshall K 갭. 기존 기준모형 비교용으로 유지하되 새로운 신호로 이중 점수화하지 않는다.
- `QUARANTINED`: 단순 5년 실거래 평균을 전국 공식가격지수처럼 혼합, 구NSI/신NSI 산식 혼합, 미래 관측치를 쓰는 양방향 HP, 사후 수정값을 당시 실시간 관측값처럼 사용하는 처리. **방법론적 부적격/데이터 누출 위험**으로 자동 격리. 지표 자체가 과학적으로 무용하다는 뜻이 아니다.
- `REJECTED`: 실데이터로 다양한 구간 OOS 악화가 입증되면 추가하는 판정. 현재 확정 기각 지표는 없다.

## 사전등록 판정 게이트

원자료 정체성·기준시점(공표지연)·빈티지·누출방지·표본연속성 확인, OOS 36회 이상 및 하락 이벤트 12개 이상, 기존 대비 RMSE 최소 3% 개선, HAC/DM 근사 p<0.05, 오경보율 증가 5%p 이하를 1/3/6개월 개별 구간에 적용한다. 이는 연구용 **탐색적 기준**이며 다중검정 보정, 지역별 강건성, 위기구간 holdout과 사용자 리뷰 전에는 승격되지 않는다.

예측성능이 없는 경우 어떤 지표도 `REVIEW_ELIGIBLE_NOT_PRODUCTION`으로 판정하지 않는다. 합성데이터·출처 불명 지표·한 번의 사후적 상관관계는 통과할 수 없다. 각 지표별 판정 기록에는 이유와 원본 URL을 유지한다.

### 실행

```bash
python risk-monitor/leading_indicators/review_candidates.py
python -m unittest discover -s risk-monitor/leading_indicators/tests -p 'test_*.py' -v
```

미검증 성능자료 입력은 `research-data/leading-indicators/performance-evidence.json`으로 주고 개인 원자료를 공개 GitHub에 업로드하지 않는다. API 비밀키·개인 데이터를 Git에 커밋하면 안 된다. 산출물은 `risk-data/leading-indicators/review.json`이며 위험 종합점수로의 import 경로가 **없다**.

## 증거와 시간축

- BOK, 「주택가격 기대심리의 특징과 시사점」 (2025-06): https://www.bok.or.kr/portal/bbs/P0002353/view.do?nttId=10091925&menuNo=200433
- BOK, 「언어모형을 활용한 新뉴스심리지수」 (2026-09): https://www.bok.or.kr/portal/bbs/P0002353/view.do?nttId=11064365&menuNo=200433
- 김나영·황영재 (2026), 국내 부동산시장 구조변화와 가격·거래·심리·미분양 지표: https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART003316813
- 서울 아파트 거시/정책/심리 VAR 연구 (2026): https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART003375770
- 국토연구원 2024 연구, 「부동산시장 진단 및 전망지수의 고도화」: https://kremap.krihs.re.kr/
- 한국부동산원 공식 월간 아파트가격 통계: https://www.data.go.kr/data/15167008/fileData.do
- R-ONE 월별 지역 아파트 매매가격지수 데이터: https://www.data.go.kr/data/15069821/fileData.do

**공표 지연 핵심:** REB 월간 전국주택가격동향조사는 일반적으로 **익월 15일** 공표되므로 t월 초에는 (t−1)월 지수를 사용할 수 없다. 주간 가격지수와 실거래가격지수는 각각 별도 통계이며 공표시차와 표본 정의를 혼동하지 않는다. `risk-monitor/news_sentiment/publication_audit.py`는 월 t의 20일 발행 가정으로 release-calendar 사전검사를 수행한다. 실제 발표일/수정치 이력에 대한 완전한 빈티지 자료 없이는 `fullPITVerified=false`.

**유의:** 2026년 새로 발표된 NSI의 2005년 이후 소급 계열이 존재하더라도 해당 2005년 시점에 실제 이용 가능했던 데이터가 아니다. 과거 기간 성능은 ‘소급 후행적 탐색’으로만 분류한다.
