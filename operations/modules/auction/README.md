# 08 경공매 서비스

기능 ID: `auction`

검색·지도·물건 상세·입찰가 시나리오. API와 실물건 연동 여부를 각각 증거로 확인

## 현재 구현 경로

- [bossauction-lab](../../../bossauction-lab)

## 작업 요청

`python tools/ai_task.py auction "수행할 목표"`

출력한 작업지시를 AI에게 전달한다. 도구는 지시문만 생성하며 API 호출·수집·배포를 실행하지 않는다. 공통 절차는 [운영 규정](../../README.md)을 따른다.
