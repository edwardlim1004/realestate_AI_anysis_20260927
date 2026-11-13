# 기존 채팅 → 작업 모듈 분류 (제안)

채팅을 자동 이동하거나 복구하지 않는다. GitHub Issue/PR/작업패킷이 구현 증거의 원본이다. 기존 대화의 완료 표현은 별도 테스트/배포 확인을 대체하지 않는다.

| 번호 | 기존 대화 또는 업무 주제 | 모듈 |
|---|---|---|
| 00 | 프로젝트 점검 확인, 전체 의사결정 | governance |
| 01 | 부동산 데이터 저장, 누락/정정 검증 | data |
| 02 | R2·Drive 백업, 용량, 카카오 알림 | storage |
| 03 | 초과유동성/M2·GDP, 모형 검증 | liquidity |
| 04 | GSADF 버블검정 | gsadf |
| 05 | HaR 미래 하방위험 | har |
| 06 | 아파트 5년 장기 가격평가 | valuation |
| 07 | 서울/경기/대전 지도, ver0/1.0, 거래상세 | dashboard |
| 08 | 경공매 옥션, 지도·권리분석 | auction |
| 09 | OECD·BIS·금리, 글로벌 역사 위험 비교 | macro |
| 10 | AI 에이전트 역할·견제·검증 및 GitHub 작업지시 | governance |

분류와 기능 상태는 [modules.json](modules.json), [STATUS.md](STATUS.md), [MODEL_REGISTRY.json](MODEL_REGISTRY.json) 확인.
채팅 아카이브와 GitHub 코드 보관은 서로 다른 기능이다.
