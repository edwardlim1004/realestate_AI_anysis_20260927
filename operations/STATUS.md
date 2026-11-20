# 통합 운영 현황 · 읽기 전용 점검기록
- 기록일: 2026-11-01 KST
- 검토 기준 main commit: 97c031906243d7124a7bb658848f9672cdf584fd
- 이 문서는 최신 원천 데이터 실물 점검이 아니라 GitHub에 공개된 파일, PR, Actions 기록을 읽어 정리한 스냅샷이다.
- 본 관리 브랜치의 모든 항목: 미병합 / 운영 미반영 / 사용자 최종 승인 대기

## 모듈 상태
| 기능 | 상태 | 근거 / 오해 방지 |
|---|---|---|
| 서울·경기·대전 과거 거래 저장 | 감사 보고서 범위 검증 / 원천 전수 미검증 | 2026-10-28 저장파일 재열람 검증, 원 API는 층화 샘플 |
| 자동 수집/저장 | 실행 상태 추적 중 | status.json 기준 2026-11-01, 전체 35,344 범위 vs 지역합 34,034 |
| 대시보드 ver1.0 및 ver0.0 | 기존 운영본 보존 | 새 브랜치에서 UI 및 데이터 파일 미수정 |
| 전국 거시 역사위험 | 운영 참고지표 (3/4) | 위험 백분위는 서울 하락확률이 아님 |
| 유동성 | SHADOW_VALIDATION | 9게이트 중 6 통과, 예측/빈티지/결재 미충족 |
| GSADF | WAITING_DATA | 워크플로 존재 ≠ 신뢰성 확인 완료 |
| HaR | WAITING_DATA | 연구용 Draft PR #18 메인 미병합 |
| 5년 가격평가 | 빌드 실패 확인 | 2026-10-31 서울 25개 구의 R2 CSV read/validation ValueError |
| 대전 4축 점수 | RESEARCH_ONLY | 2026-09 기준월, 대전 내 상대비교에만 사용 |
| 경공매 | PROTOTYPE | 공식 실시간 원천 및 AI 권리확인 미연결 |

## 우선 조치: 실제 수정은 별도 승인/PR
1. P0 · 5년 가치평가 R2 읽기/검증 실패 원인 분석 (운영 원본 삭제 금지): https://github.com/edwardlim1004/realestate_AI_anysis_20260927/actions/runs/41208352776
2. P0 · 수집상태 범위 계산 규칙 차이 1,310개 조사: status.json 전체 35,344, 서울 11,050 + 경기 20,774 + 대전 2,210 = 34,034. 실제 누락을 뜻하는지 아직 불명확
3. P1 · 유동성 음성 예측 성과·빈티지 부재 해결 전 연구 격리
4. P1 · HaR PR #18과 GSADF 별도 검정, 승인 전에 복합점수에 추가 금지
5. P2 · PR #36 오래된 기준을 최신 메인 기반 관리 브랜치로 포팅; 원 PR은 현 상태로 보존

## 증거 출처
- [수집 실행 상태](../seoul-apartment-collector/status.json) · [서울/경기 감사](../seoul-apartment-collector/coverage_audit.json) · [대전 감사](../seoul-apartment-collector/daejeon_coverage_audit.json)
- [유동성 검증](../risk-data/liquidity/validation.json) · [거시 모델 요약](../risk-data/risk_summary.json)
- [대전 연구용 집계](../dashboard-v1/data/daejeon-regions.json)
- [기존 PR #36](https://github.com/edwardlim1004/realestate_AI_anysis_20260927/pull/36) · [HaR PR #18](https://github.com/edwardlim1004/realestate_AI_anysis_20260927/pull/18)

상태는 증거가 새로 생길 때 갱신하되, 서류상의 완료·진행중 표시를 실제 시스템 실행 성공으로 대체하지 않는다.
