# 신NSI 서울아파트 조기경보: 2026-11-16 선행연구 조사와 사전등록 가설

> 이 문서의 수치는 **외부 선행논문 발표 결과**이며, 본 GitHub 연구모듈의 실제 실증 결과가 아니다. 각각 감성지수의 정의가 달라 교차대입 금지.

| 연구(원문) | 데이터·지수 구분 | 발표 결과 | 한계·모듈 반영 |
|---|---|---|---|
| 한국은행 BOK 이슈노트 제2026-21호 (2026-09-01) | 신NSI, 국내 경제뉴스 NLP 지수 | CCSI 약 1개월·BSI 약 2개월 선행 시 최대 연관성, 기대NSI 더 밀접 | 서울아파트 가격 예측을 직접 검증한 결과 아님. 주택 실증 별도 |
| 배현정·이춘원 (2026), 「뉴스감성지수와 아파트 매매가격의 상관 및 인과관계 분석」, 부동산융복합연구 6(2), 59-82 | 2021~25 부동산 기사 12,734건, 연구자 자체 신문뉴스감성지수 | 서울 아파트가격 변화 약 1개월 선행, 최고 교차상관 0.707, 그랜저 예측력 | 2026 BOK 신NSI와 **다른 지수**. 이 상관수치와 모델이 본 모듈의 성능을 의미하지 않음 |
| 이현석 (2025), 「뉴스 감성지수의 유용성: 소비심리지수 및 주택가격에 대한 영향」, 금융공학연구 24(4), 25-52 | 2000~2025 부동산 뉴스 76,974건으로 FSI(미래)·PSI(과거) 구축 | FSI가 주택소비심리 변화를 선행, 서울 주택가격 단기변동 조기포착 | 서울 HPI 예측 가설을 지지하나 BOK 일반 경제뉴스 NSI의 성능과는 무관 |
| 박순미·이성화 (2025), 「온라인 기반 부동산 심리지수 개발과 아파트 매매가격 반응 분석」, 부동산분석 11(2), 81-104 | 2016~2024 전국 월별, 독자 RSI | 2~3개월 시차 Granger 검정, CSI보다 좋은 예측력 보고 | 전국·전용 부동산감성지수. 신NSI·서울에 전이 불가 |
| 표동진 (2022), 「Sentiment Shock and Housing Prices: Evidence from Korea」, KDI JEP | 주택시장심리지수 HMCI 기반 충격 | 수도권 1개월 후 집값과 긍정적 연관, 표본외 예측 개선 | HMCI 충격 지표. BOK 신NSI 직접 근거 아님 |

## 원문 링크

1. 한국은행: https://www.bok.or.kr/portal/bbs/P0002353/view.do?nttId=11064365&menuNo=200433
2. 배현정·이춘원: https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART003348009
3. 이현석: https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART003286743
4. 박순미·이성화: https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART003230610
5. 표동진 KDI: https://www.kdi.re.kr/research/jepView?art_no=3433

## 사전등록 검증 질문

- Q1: **BOK 신NSI**로 서울 아파트 **1/3/6개월 미래 누적 실질가격 변화율** 예측 시 기존 AR(2)+금리+유동성+KOSPI 기준선 대비 표본외 RMSE가 줄어드는가?
- Q2: 변동 방향은 적중하더라도 하방 진입 경보가 늘어난 것뿐인지(오경보율 증가), 실제 위기 전 신호가 앞당겨졌는가?
- Q3: 2008·2020·2022 스트레스 구간과 평시에서 효과가 달라지는가?
- Q4: Expected NSI·부동산 전용 FSI가 일반 BOK 신NSI 대비 추가 정보를 제공하는가? **BOK 신NSI와 연구자 자체 개발 감성지수는 독립 후보변수로 관리**한다.

## 2026년 10월 최신치 검증 주의

2026-11-03 연합뉴스는 ECOS를 인용해 2026년 10월 월간 뉴스심리지수 **95.34**, 9월 **99.39**라고 보도했다. 일부 비공식 재배포 사이트에 다른 10월 수치가 남아 있으므로 해당 시점의 원래 발표값·현재 최신 수정값·최신 신NSI 계열 식별을 한국은행 ECOS에서 직접 확인하기 전에는 원시 CSV에 임의 삽입하지 않는다.

보도: https://www.yna.co.kr/view/AKR20261102158900002

## 기술 검증 상태

- Official BOK study reviewed: YES
- Independent housing sentiment literature reviewed: YES
- New BOK NSI official historical monthly CSV with verified item code: NO
- Seoul official apartment monthly price index aligned to same vintage: NO
- 1/3/6-month empirical backtest on actual inputs: **NOT RUN**
- GitHub synthetic safety tests: see PR CI
- Composite model: **INELIGIBLE**
