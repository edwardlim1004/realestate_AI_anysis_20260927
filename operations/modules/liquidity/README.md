# 03 유동성 연구·검증

기능 ID: `liquidity`

M2 수준·GDP 대비 비율·추세괴리 분리. promotion.enabled=false 확인; 검증과 명시적 결재 전 편입 금지

## 현재 구현 경로

- [risk-monitor/liquidity](../../../risk-monitor/liquidity)
- [risk-data/liquidity](../../../risk-data/liquidity)
- [liquidity-research](../../../liquidity-research)

## 작업 요청

`python tools/ai_task.py liquidity "수행할 목표"`

출력한 작업지시를 AI에게 전달한다. 도구는 지시문만 생성하며 API 호출·수집·배포를 실행하지 않는다. 공통 절차는 [운영 규정](../../README.md)을 따른다.
