# BossAuction Lab — 기능 개발·변경 이력 (HISTORY)

> **단일 누적 기록**: 옥션프로그램의 기능 추가·수정·삭제 및 주요 개발 지침 변경을 최신 날짜부터 기록합니다.  
> 운영 기준: [docs/PROJECT_GUIDELINES.md](docs/PROJECT_GUIDELINES.md) · 코딩 에이전트 지침: [AGENTS.md](AGENTS.md)  
> 과거 개발분의 상세 복구 기록은 [docs/RECOVERY_STATUS.md](docs/RECOVERY_STATUS.md), [README.md](README.md)에 보존되어 있습니다. 아래 이력은 확인 가능한 변경부터 기록하며, 기록되지 않은 과거 기능을 임의로 발명하지 않습니다.

## 2026-11-04 — 문서·운영: 프로젝트 지침 GitHub 보관 및 변경 이력 제도 도입

- **변경 내용:** 옥션프로그램 프로젝트 운영·보안·데이터 검증·K-Skill 사용 지침을 GitHub 문서로 버전 관리. 앞으로 기능 추가·변경 시 날짜별 HISTORY 기록을 같은 PR에서 작성하도록 개발 지침에 명시.
- **영향 범위:** `docs/PROJECT_GUIDELINES.md`, `HISTORY.md`, `AGENTS.md`, `README.md`, PR 이력 누락 검사 워크플로.
- **검증:** 문서 링크와 GitHub Actions PR 검사 동작을 병합 과정에서 확인. 본 항목은 새로운 실시간 데이터 기능을 제공하지 않습니다.
- **남은 제한:** PR을 거치지 않는 GitHub 직접 푸시는 이력 검사 자동화의 대상이 아닙니다.

## 2026-11-04 — 신규: K-Skill 법원경매 검색 결과의 오프라인 JSON 변환

- **변경 내용:** `court-auction-notice-search`의 정규화된 부동산 **자유검색 결과 JSON**을 기존 Classic/Advanced 화면에서 수동으로 가져올 수 있는 형식으로 변환.
- **영향 범위:** `tools/k-skill-court-import.mjs`, `tests/k-skill-court-import.test.mjs`, `docs/K_SKILL_INTEGRATION.md`, `AGENTS.md`.
- **검증:** 관련 GitHub Actions의 단위테스트 성공. 적용 내역: [PR #38](https://github.com/edwardlim1004/realestate_AI_anysis_20260927/pull/38).
- **남은 제한:** 서버 실시간 수집, 온비드 자동조회, 등기 발급, AI 권리판단은 아직 연결하지 않았습니다. 좌표 미검증 결과는 지도에 표시하지 않습니다.

---

## 향후 기능 변경 시 복사할 기록 형식

새 항목은 이 템플릿 **위쪽에** 삽입하고 기존 항목은 유지합니다. 확정되지 않은 결과는 `미검증`으로 기재합니다.

```markdown
## YYYY-MM-DD — [신규/변경/수정/보안/문서·운영]: 기능명

- **변경 이유:** 기존 문제 또는 사용자 요구
- **변경 내용:** 이전과 달라진 실제 동작
- **영향 범위:** 화면, 주요 파일, 데이터 계약/API
- **검증:** 실행한 테스트 / CI 결과 / 미검증 사항
- **남은 제한:** 구현하지 않은 부분, 사용 시 주의점
- **관련 기록:** PR #번호 / 이슈 / 커밋 (확인된 경우)
```

**주의:** 문서를 새로 작성하는 것만으로 외부 K-Skill이 ChatGPT 프로젝트에 설치되거나 공식 경매 원천자료가 자동 수집되는 것은 아닙니다.
