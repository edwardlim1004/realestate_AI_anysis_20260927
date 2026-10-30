# 07 위험 대시보드·거래상세

기능 ID: `dashboard`

거시 역사백분위와 지역 상대점수 구분, 상세팝업·출처·잠정치·연구상태 표시

## 현재 구현 경로

- [index.html](../../../index.html)
- [apartment-trades.js](../../../apartment-trades.js)
- [trade-details](../../../trade-details)
- [risk-monitor/update_risk_data.py](../../../risk-monitor/update_risk_data.py)

## 작업 요청

`python tools/ai_task.py dashboard "수행할 목표"`

출력한 작업지시를 AI에게 전달한다. 도구는 지시문만 생성하며 API 호출·수집·배포를 실행하지 않는다. 공통 절차는 [운영 규정](../../README.md)을 따른다.
