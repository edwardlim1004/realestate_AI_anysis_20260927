# 서울 아파트 하방위험 선행지표 확장 검증

2026-11-25 연구 검토본. seoul_leading_indicators.html을 브라우저에서 열면 6·12·36개월, 후보 지표, 월과 평가 구간을 선택할 수 있다. PNG는 매매·전세·월세 가격과 1년 하위 5% 예측선 요약이다.

## 자료
- 목표는 한국부동산원 공동주택 실거래가격지수의 서울 아파트 매매 지수를 전국 CPI로 조정한 뒤 구한 미래 누적 수익률. 2006-01~2026-08 동결본. [실거래 통계](https://www.reb.or.kr/r-one/portal/stat/easyStatPage/A_2024_00178.do).
- [서울 아파트 매매 조사 지수](https://www.reb.or.kr/r-one/portal/stat/easyStatPage/A_2024_00045.do) 및 [전세 조사 지수](https://www.reb.or.kr/r-one/portal/stat/easyStatPage/A_2024_00050.do) 2003-11~2026-10. [월세 조사 지수](https://www.reb.or.kr/r-one/portal/stat/easyStatPage/A_2024_00055.do) 및 [월세 통합 지수](https://www.reb.or.kr/r-one/portal/stat/easyStatPage/A_2024_00054.do) 2015-06~2026-10. 순수 월세 분류 지수를 모형 입력으로 사용하고 월세 통합은 추출본에 보존했다. 매매·전세 격차는 같은 조사 계열의 최근 3개월 로그 상승률 차이다.
- 주담대 금리 및 서울 거래량은 R-ONE 보존본. 실질 주담대금리는 명목금리에서 전국 CPI 전년비를 뺀 사후 물가조정 지표다. 실질 M2는 전국 ECOS 보존본을 CPI로 조정한 12개월 로그 성장률. 신용 상환부담은 BIS 한국 가계부문 부채 상환비율(DSR, Q.KR.H)로 개별 주택담보대출 규제 DSR과 정의가 다르다. PIR은 OECD 한국 장기평균 대비 가격/소득 지수다.
- 월별 지연 가정은 REB 실거래 모멘텀·임대 지수 2개월, 거래량·주담대·M2 3개월, 분기 신용갭·DSR·PIR 6개월. 최초 공표 빈티지는 미확보 상태다.

## 검증
- 기존과 같은 L1 분위수 회귀(5%), L2 로지스틱, 60개 월별 학습과 3개월 결과 확인 시차. 직전 화면이 고정했던 2016-01 제한을 제거했다. 후보별로 지표 1개만 추가하며, 각 표본 안에서는 동일한 학습·평가 월을 사용한다.
- 12개월 장기 표본은 2013-08~2025-08 145개월. DSR 추가 하위 5% 오차 1.4977→1.2467, 동시 스트레스 1.2807, 전세 모멘텀 1.3474. 2023년 이후에는 DSR 1.4713 대 기존 0.8907, 전세 모멘텀 0.6871. 이 구간은 실제 하락 사례 0/32.
- 12개월 전월세 공통 표본은 2022-01~2025-08 44개월. 동시 스트레스 5.0073→2.1496, Brier 0.2260→0.2789. 월세 모멘텀 6.3067. 36개월 전월세 공통의 첫 평가 가능 결과월은 2027-01이다.
- 2026-08 기점까지 모형 계산은 가능하며, 결과월이 관측되지 않은 행은 predictions.csv에 actual·평가 점수가 공란이다. 화면에서는 평가 완료 행만 사용한다. 지평이 겹쳐 월별 표본은 독립이 아니다. 순위는 탐색 결과로, 별도로 보존된 새 평가 기간 검증이 필요하다.

## 재현
Python과 numpy/pandas/scikit-learn/matplotlib 사용. 이 폴더에서 `python backtest_leading.py`로 monthly_inputs.csv에서 predictions.csv 및 scores.csv를 재현한다. `python build_dashboard.py`, `python plot_leading.py`로 화면을 재생성한다. `fetch_rents.py`는 새 빈티지를 요청하므로 저장 번들의 값을 그대로 재현하려면 실행하지 않는다. `prepare.py`는 작업 환경에 보존된 기존 금융 입력을 결합하는 스크립트다.

- [영란은행 2026 HaR](https://www.bankofengland.co.uk/working-paper/2026/developing-a-house-price-at-risk-framework-for-the-uk)
- [IMF 2020 HaR](https://www.imf.org/-/media/files/publications/wp/2020/english/wpiea2020011-print-pdf.pdf)
