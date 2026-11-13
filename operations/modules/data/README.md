# 01 데이터 수집·품질

기능 ID: data

서울·경기·대전 매매/전세/월세의 지역×월×유형 coverage, 신고지연, 취소·중복 및 공통 기준일 검증 · 저장 범위와 원천 거래 전수 검증을 구분; status.json 합계 불일치 조사

## 현재 연결 경로
- [seoul-apartment-collector](../../../seoul-apartment-collector)
- [api-integration](../../../api-integration)

## 작업 요청

python tools/ai_task.py data "수행할 목표"

명령은 작업지시만 생성하고 어떤 작업도 자동 실행하지 않는다. [중앙 운영규정](../../README.md), [승인 게이트](../../RELEASE_GATES.md), [현재 상태](../../STATUS.md) 준수. 운영/연구 상태는 MODEL_REGISTRY.json 기준으로 확인하며 미검증을 정상가동으로 표기하지 않는다.
