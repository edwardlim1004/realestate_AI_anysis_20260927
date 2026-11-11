# 02 저장·백업·알림

기능 ID: `storage`

R2/Drive 보관·복구·용량, 카카오 알림. 수집과 공유 경로이므로 파일 단위로 변경 범위를 제한

## 현재 구현 경로

- [seoul-apartment-collector](../../../seoul-apartment-collector)
- [.github/workflows](../../../.github/workflows)

## 작업 요청

`python tools/ai_task.py storage "수행할 목표"`

출력한 작업지시를 AI에게 전달한다. 도구는 지시문만 생성하며 API 호출·수집·배포를 실행하지 않는다. 공통 절차는 [운영 규정](../../README.md)을 따른다.
