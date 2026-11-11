# 01 데이터 수집·품질

기능 ID: `data`

서울·경기·대전 매매/전세/월세의 지역×월×유형 coverage, 신고지연, 취소·중복 및 공통 기준일 검증

## 현재 구현 경로

- [seoul-apartment-collector](../../../seoul-apartment-collector)
- [api-integration](../../../api-integration)

## 작업 요청

`python tools/ai_task.py data "수행할 목표"`

출력한 작업지시를 AI에게 전달한다. 도구는 지시문만 생성하며 API 호출·수집·배포를 실행하지 않는다. 공통 절차는 [운영 규정](../../README.md)을 따른다.
