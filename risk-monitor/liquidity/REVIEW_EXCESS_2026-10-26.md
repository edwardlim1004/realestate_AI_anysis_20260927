# 초과유동성 지표 vs 기존 유동성 지표 — 2026-10-26 독립 비교

**판정: RESEARCH_ONLY / SHADOW 유지 / 6대 위험 종합점수 미편입.**

## 경제적 정의와 선행문헌
기존 전체 유동성 점수는 Marshall-K one-sided HP 갭(50%), 실질 M2 갭(30%), M2/Lf/L 확산도(20%)의 합성값이다. Marshall-K 갭 자체가 초과유동성의 한 정의다.

- ECB Working Paper 696, *What is global excess liquidity, and does it matter?*: excess money growth = nominal money growth − nominal GDP growth.
- 최남진 (2023), 한국부동산원 부동산분석 9(1), 195–210, DOI 10.30902/jrea.2023.9.1.195: Marshallian-K 갭 및 P* 순환변동치로 전국 아파트 가격의 SVAR 충격반응 연구.
- 우준명·이지은 (2016), 한국은행 경제분석 22(4), *Implied Liquidity Estimation*: M2, Lf, 은행신용을 활용한 균형유동성 연구.
- 한국은행 (2026-01-20), *Misconceptions and Facts about Current Liquidity and Exchange Rate Conditions*: GDP 대비 통화비율을 구조적 금융심화 없이 과잉이라고 단정하는 해석에 주의.

## 재현 대상 및 방법
- 출처: `risk-data/liquidity/raw.csv` (ECOS), `risk-data/risk_raw.csv` (OECD, KOR, REAL_HPI, Q).
- M2 분기치 = 각 분기 3개 월별 M2 평잔의 단순평균. GDP 분기치 = ECOS 명목 GDP 분기 유량.
- **초과통화 증가율(로그 %p)** = 100×[ln(M2_t/M2_(t−4)) − ln(NGDP_t/NGDP_(t−4))]. 이는 '통화수요모형으로 추정한 초과잔액'과는 다른 정의다.
- 비교 후보: 기존 50:30:20 SHADOW 점수, 기존 Marshall-K 단독, 초과통화 증가율 원자료, 초과통화 증가율 후행 4분기 이동평균, 동 증가율 expanding 과거 백분위.
- 미래 예측 4분기/8분기, 시그널 t−2, 결과 발표 1분기 지연, expanding OLS vs matured-label expanding historical mean. 검증의 표본 및 시작·종료 시점은 모든 후보 간 완전히 동일하게 강제했다.
- 표본외 4분기: n=31 (2017Q4–2025Q2). 8분기: n=23 (2018Q4–2024Q2). 원자료는 사후 수정된 최신값으로 **진짜 실시간 빈티지 테스트 아님**.
- 개선율 = 100×(1−MSE_모델/MSE_과거평균). 양수면 단순평균보다 개선, 음수면 악화. 선정 편향 조정을 거치지 않았음.

## 동일 표본 OOS 결과

| 지표 | 4분기 RMSE (%p) | 4분기 MSE 개선율 | 8분기 RMSE (%p) | 8분기 MSE 개선율 |
|---|---:|---:|---:|---:|
| **과거평균 기준** | 5.5255 | 0% | 9.7709 | 0% |
| 기존 전체 유동성 SHADOW | 5.5993 | −2.69% | 10.0630 | −6.07% |
| 기존 마샬K 단독 | 5.6894 | −6.02% | 9.7891 | −0.37% |
| 초과통화 증가율 | 5.6815 | −5.72% | 9.8205 | −1.02% |
| **초과통화 증가율의 4분기 이동평균** | 6.6038 | **−42.84%** | **8.4676** | **+24.90%** |
| 초과통화 증가율의 과거 백분위 | 5.7050 | −6.60% | 9.8966 | −2.59% |

**판단:** 4분기 이동평균 형태가 **2년 후 가격 변화 예측에서만 탐색적으로 더 좋음**. 같은 모형의 1년 전망은 현저히 악화되므로 두 기간 모두에서 성과가 안정적이지 않음. 여러 후보 중 사후 선택된 2년 결과를 통계적으로 유의한 근거 또는 기존 9개 게이트 PASS로 사용할 수 없다.

## 2026-Q2 지표 해석
- M2 명목 전년 로그증가율 5.635197%p.
- 명목 GDP 전년 로그증가율 23.250722%p (일반적인 비로그 전년 증가율은 약 +26.4%).
- 초과통화 증가율 **−17.615525 로그%p**.
- 후행 4분기 이동평균 **−7.480596 로그%p**.

한국은행 2026년 2분기 국민소득 잠정 발표(2026-09-08)에 따르면 명목 GDP YoY +26.4%에는 반도체 수출가격·기업 영업잉여 급증이 크게 작용한다. 즉 GDP 급증으로 분모가 커지면 M2 증가와 관계없이 초과통화 증가율은 크게 음수가 될 수 있다. **이 수치는 시중자금 17.62% 감소도, 아파트가격 하락 확률도 아니다.**

## 채택 이전 반드시 해결할 항목
1. **분모 왜곡 보정:** 내수 GDP 또는 내수 흡수·비반도체 경제활동을 활용한 후보를 재정의한 뒤 종전 후보와 같은 표본에서 비교. ECOS 신규 계열은 출처/통계작성기준 확인 전 수치 미사용.
2. **통화수요형 초과유동성:** 단순 M2–GDP 증가율이 아닌 균형 통화수요 함수를 GDP/금리/물가/유통속도 구조변화에 따라 추정하여 '초과잔액(monetary overhang)' 검토. 관측 가능한 역사빈티지 확보 필요.
3. **목표변수 정렬:** 유동성 확대는 집값 상방압력과 동시에 미래 조정위험을 형성할 수 있음. 수준/장기 상승기와 하방위험(가격하락/큰 낙폭)을 분리해 가설 사전고정.
4. **강건성:** 2008년 위기 포함 가능한 표본 재구축, 2013 이전 warm-up 영향, 신용축 통제·모형 중복성, 이동 창·시차 및 표본 분할, 중첩 수익률 HAC/부트스트랩, 다중 검정 편향 통제.
5. **실시간 원자료 빈티지:** 발표일 캘린더, 여러 독립 ECOS 개정 스냅샷과 실제 당시 값을 R2에 저장하여 as-of 재검증. 기준 모델과 같은 증거 게이트를 만족해야 함.
6. **격리:** `promotion.json`은 계속 `enabled:false`; `validation.json`은 계속 6/9 상태. 합성위험 점수 변화 없음.

## 재현
```bash
python -m unittest discover -s risk-monitor/liquidity/tests -p 'test_*.py' -v
python risk-monitor/liquidity/compare_excess_liquidity.py --check
```

기계검증용 `risk-data/liquidity/excess_liquidity_comparison.json`이 같지 않으면 `--check`에서 실패한다. 연구 산출물은 과거 실거래를 기반으로 평가한 탐색 결과이며 미래 수익률이나 하락확률이 아니다.

공식 링크:
- https://www.bok.or.kr/eng/bbs/B0000548/view.do?menuNo=400523&nttId=10096071
- https://www.bok.or.kr/portal/bbs/B0000501/view.do?menuNo=201264&nttId=11064532
- https://www.bok.or.kr/eng/bbs/E0002726/view.do?menuNo=400218&nttId=224982
- https://www.ejrea.org/archive/view_article?pid=jrea-9-1-195
