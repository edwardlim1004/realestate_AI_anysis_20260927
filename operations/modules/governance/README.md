# 10 AI 업무 운영·검증·결재

기능 ID: governance

작업패킷·기준 SHA·독립검증·승인기록·배포/롤백 관리. 현재는 문서/정적 검사만 구현; 자율 AI와 승인 강제는 미구현

## 현재 연결 경로
- [operations](../../../operations)
- [tools/ai_task.py](../../../tools/ai_task.py)

## 작업 요청

python tools/ai_task.py governance "수행할 목표"

명령은 작업지시만 생성하고 어떤 작업도 자동 실행하지 않는다. [중앙 운영규정](../../README.md), [승인 게이트](../../RELEASE_GATES.md), [현재 상태](../../STATUS.md) 준수. 운영/연구 상태는 MODEL_REGISTRY.json 기준으로 확인하며 미검증을 정상가동으로 표기하지 않는다.
