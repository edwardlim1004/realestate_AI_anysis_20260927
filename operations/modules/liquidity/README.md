# 03 유동성 연구·검증

기능 ID: liquidity

M2 수준·GDP 대비 비율·추세괴리 분리. promotion.enabled=false 확인; 검증과 명시적 결재 전 편입 금지

## 현재 연결 경로
- [risk-monitor/liquidity](../../../risk-monitor/liquidity)
- [risk-data/liquidity](../../../risk-data/liquidity)
- [liquidity-research](../../../liquidity-research)

## 작업 요청

python tools/ai_task.py liquidity "수행할 목표"

명령은 작업지시만 생성하고 어떤 작업도 자동 실행하지 않는다. [중앙 운영규정](../../README.md), [승인 게이트](../../RELEASE_GATES.md), [현재 상태](../../STATUS.md) 준수. 운영/연구 상태는 MODEL_REGISTRY.json 기준으로 확인하며 미검증을 정상가동으로 표기하지 않는다.
