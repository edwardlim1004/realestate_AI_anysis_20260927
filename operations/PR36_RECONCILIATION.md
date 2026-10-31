# PR #36 → 최신 main 기반 안전 포팅

- 원본 Draft PR #36: https://github.com/edwardlim1004/realestate_AI_anysis_20260927/pull/36
- 원본 head: 3ea39a4d516daf2da29ef2ec441ce8879be6ee3f
- 최신 base snapshot: 97c031906243d7124a7bb658848f9672cdf584fd
- 관리 브랜치: ops/governance-main-sync-20261101
- PR #36은 2026-11-01 확인시 main과 diverged, 구버전 기준; PR #36 수정/폐쇄/병합하지 않는다.

## 포팅한 범위
기존 operations/ 문서, 8모듈 설정·작업/결재 템플릿, tools/ai_task.py. 
현재 상태에 맞게 보강: macro/governance 별도 분류, 데이터 카탈로그, MODEL_REGISTRY, STATUS, 데이터/가치평가 장애 runbook, 검증·승인 게이트, 메타데이터 정적검증 테스트.

## 의도적으로 제외한 범위
기존 PR #36의 root README.md 변경은 새 브랜치에 포팅하지 않는다. 운영 코드·DB·자동화·웹사이트 파일, R2/Drive 데이터, API/Secrets, 투자 점수 설정도 불변.

## 독립 확인
- git diff --name-status 97c031906243d7124a7bb658848f9672cdf584fd...ops/governance-main-sync-20261101 로 파일 범위 확인
- python tools/validate_governance.py
- python -m unittest discover -s tools -p "test_governance.py" -v
- git diff --name-only 97c031906243d7124a7bb658848f9672cdf584fd...ops/governance-main-sync-20261101 > /tmp/governance-paths.txt && python tools/validate_governance.py --changed-paths /tmp/governance-paths.txt
- 실패/미실행한 검사는 성공으로 표시하지 않는다.
