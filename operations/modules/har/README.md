# 05 HaR 하방위험

기능 ID: `har`

현재 본체는 WAITING_DATA. 전용 실행모듈 완성으로 간주하지 말 것. 분위수 손실·포괄률·표본외 검증 설계부터 수행

## 현재 구현 경로

- [risk-monitor/update_risk_data.py](../../../risk-monitor/update_risk_data.py)

## 작업 요청

`python tools/ai_task.py har "수행할 목표"`

출력한 작업지시를 AI에게 전달한다. 도구는 지시문만 생성하며 API 호출·수집·배포를 실행하지 않는다. 공통 절차는 [운영 규정](../../README.md)을 따른다.
