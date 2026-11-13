# 연구·배포·투자 승인 게이트

## 상태 체계
PLANNED → IMPLEMENTED → TESTED → INDEPENDENTLY_VERIFIED → USER_APPROVED → RELEASED → MONITORED.
FAILED/HOLD는 언제든 별도 기록. 검증 통과, 사용자의 승인, GitHub 병합, Pages 배포 및 실제 운영 확인을 서로 대체하지 않는다.

## 작업/PR 필수 증거
1. 최신 main 기준 SHA와 변경 파일 allowlist, 공유 경로·자동화 영향.
2. 데이터 출처/기준일/hash와 수정·공표시차, 예상/실제 비용.
3. 재현 가능한 테스트 명령과 실행된 결과 (미실행은 NOT_RUN).
4. 독립 검증 검토자와 반례/강건성, 실패 원인, 회귀 위험.
5. 안전한 롤백 명령과 스토리지 키 변경/삭제 여부.
6. 투자 점수·실거래 수집 정책·자동화·실제 자금집행 변경은 명시적 사용자 결재.

## 이번 관리 브랜치 불변 조건
- main 직접 푸시/병합/강제 리베이스/PR auto-merge 없음.
- ver0/, dashboard-v1/, index.html, data.js, risk-data.js, risk-data/, seoul-apartment-collector/, long-term-value/, .github/workflows/, bossauction-lab/ 등의 기존 파일 불변.
- 허용 변경: operations/ 및 tools/ai_task.py, tools/validate_governance.py, tools/test_governance.py.
- 새 관리 파일이 있다고 해서 자동화 또는 보안 정책이 집행되는 것은 아님. 보호 브랜치 설정과 CODEOWNERS·required checks는 별도 검토/구현 대상.
- PR이 Draft로 남아 있는 동안 main 사용자 사이트는 기존대로 운영됨.

## 연구 모형 특별 제한
유동성: existing 9-gate contract 미통과/USER_APPROVED 없는 경우 본체 composite 연결 금지.
HaR/GSADF: 실 데이터 기반 OOS·시점 통제·비교 기준 및 독립 검증이 충족되기 전에는 확률 또는 경보로 표시 금지.
데이터·설정·코드 fingerprint가 바뀌면 검증/승인 효력을 재검토할 것.

## 결재
기술 리뷰는 merge 허가가 아니다. 사용자 명시 결재 전 Draft 유지. 실제 병합은 최신 main 변경여부를 다시 비교한 뒤 승인받아 별도 진행한다.
