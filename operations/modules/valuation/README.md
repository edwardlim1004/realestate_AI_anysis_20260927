# 06 장기 가격·전세가치

기능 ID: `valuation`

과거 추세와 미래 시나리오 분리, 거래구성·표본수·전세갭·금리 민감도 검증

## 현재 구현 경로

- [long-term-value](../../../long-term-value)

## 작업 요청

`python tools/ai_task.py valuation "수행할 목표"`

출력한 작업지시를 AI에게 전달한다. 도구는 지시문만 생성하며 API 호출·수집·배포를 실행하지 않는다. 공통 절차는 [운영 규정](../../README.md)을 따른다.
