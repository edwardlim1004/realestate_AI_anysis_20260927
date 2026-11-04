# 옥션프로그램 — 프로젝트 운영·개발 지침 (GitHub 원본)

> 적용 범위: `bossauction-lab/` · 최초 GitHub 보관: **2026-11-04**  
> 중요: 이 문서는 **프로그램 프로젝트의 기준 지침**입니다. GitHub 변경 이력은 [../HISTORY.md](../HISTORY.md)에 누적합니다. ChatGPT의 프로젝트 설정을 자동으로 변경하거나, 외부 CLI 스킬을 ChatGPT에 설치하는 파일은 아닙니다.

## 1. 프로젝트 목적과 실제 상태

BossAuction Lab은 국내 부동산 경매·공매 물건의 **검색, 데이터 확인, 지도, 비교, 입찰비용 계산을 보조**하는 독립 연구용 웹 프로그램입니다.

- GitHub 소스: https://github.com/edwardlim1004/realestate_AI_anysis_20260927/tree/main/bossauction-lab
- 프로그램: https://edwardlim1004.github.io/realestate_AI_anysis_20260927/bossauction-lab/
- 기본 화면: `classic/`; 추가 검색·비교·계산 화면: `advanced/`
- 배포 환경: 정적 GitHub Pages. 서버 없는 브라우저 앱에서 비밀 API 키를 저장하거나 Python/SQLite 백엔드를 상시 실행하지 않습니다.
- 사용자 제공 CSV/JSON/SQLite 파일은 현재 가능한 범위에서 브라우저 로컬로 불러옵니다.
- **법원 전국 실시간 자동조회·온비드 자동수집·등기소 자동발급·공식 AI 권리판정은 미구현**입니다. 실제 입찰 판단에 사용하기 전 원문 재확인이 필요합니다.

구현/미구현 표시는 `README.md`, `classic/README.md`, `advanced/README.md`, `docs/IMPLEMENTATION_STATUS.md`의 실제 코드·테스트와 대조하여 갱신합니다.

## 2. K-Skill 적용 범위

참조 저장소: https://github.com/NomaDamas/k-skill

| 스킬 | 목적 | 현재 연결 상태 |
| --- | --- | --- |
| `court-auction-notice-search` | 법원 경매 공고/사건/물건 조건조회 | **로컬 오프라인 JSON 변환기 구현**. 실시간 웹 자동조회는 아님 |
| `real-estate-search` | 실거래가 비교 | **연동 예정** |
| `building-register-search` | 건축물대장 표제부 사실조회 | **연동 예정** |
| `iros-registry-automation` | 인터넷등기소 사용자 발급 보조 | **PC 설치 이후 검토**. 로그인·인증·결제는 사용자 직접 |
| `korean-law-search` | 법령/판례 출처 확인 | **연동 예정** |

현재 사용할 수 있는 변환기: `tools/k-skill-court-import.mjs`  
사용법 및 데이터 계약: [K_SKILL_INTEGRATION.md](K_SKILL_INTEGRATION.md), [DATA_CONTRACT.md](DATA_CONTRACT.md)

외부 스킬의 GitHub 소스/지침을 참조한다고 해서 이 ChatGPT 프로젝트나 배포 서버에 해당 도구가 자동 설치되거나 실행 가능해지는 것은 아닙니다.

## 3. 데이터 품질과 출처 원칙

1. 법원/기관 원문 주소, 사건번호, 물건번호, 법원 코드, 원문 링크(실제 확인된 경우에만), 조회·발표 기준시각, 취소·변경·유찰 상태를 **출처와 함께** 보존합니다.
2. **조회/변환 시각 ≠ 법원 공고 발표일**입니다. 수집 시각만으로 최신 여부를 보증하지 않습니다.
3. 결측/미확인 값은 `null` 또는 `미확인`으로 둡니다. 임의의 0원, 사건번호, 좌표, 낙찰가, 안전점수, 법원 딥링크를 생성하지 않습니다.
4. 감정가/최저가와 기일은 정정·취하·연기될 수 있습니다. 실제 입찰 전에는 **법원 공식 원문과 매각물건명세서** 등 필수 자료를 직접 확인합니다.
5. 검증하지 않은 주소 기반 좌표는 지도에 표시하지 않습니다. 지도 위치, 면적 및 사용자 입력 계산값의 한계를 명시합니다.
6. 과거 데모 데이터와 사용자 반입 데이터, 검증된 공식 원자료를 UI에서 혼동하지 않습니다.
7. 원문 서류 확인, 임대차/대항력/배당 등 법률 검토 없이 확정적 권리분석이나 낙찰 추천을 하지 않습니다.

## 4. 보안·법적 운영 기준

- 공개 GitHub에 비밀번호, 인증정보, API Secret, 카드/계좌정보, 주민등록번호, 비공개 등기 PDF, 민감 개인자료를 커밋하지 않습니다.
- 인증·CAPTCHA·결제벽·접근차단·IP 제한을 우회하지 않습니다. 각 서비스의 이용약관과 호출 제한을 지킵니다.
- 사용자가 직접 로그인·본인인증·결제·입찰을 수행합니다. 외부 자동화는 허용된 조회·서류 정리의 보조 범위에 한정합니다.
- 공식 API 접근 권한/이용조건을 확인하기 전, 실시간 전국자료가 제공되는 것처럼 UI에 표시하지 않습니다.
- 새 외부 라이브러리·스킬은 의존성, 라이선스, 권한, 변경 범위를 먼저 검토합니다.

## 5. **기능 변경 시 필수 변경 이력 규칙**

**이 프로젝트의 기능을 추가·수정·삭제하거나 데이터 구조/화면/외부 연동을 바꾸는 작업에는 반드시 같은 PR 또는 같은 작업 커밋에서 `bossauction-lab/HISTORY.md`를 함께 수정합니다.**

작업 순서:

1. 코드 수정 전 `AGENTS.md`, 이 문서, [HISTORY.md](../HISTORY.md), 관련 설계/상태 문서를 읽고 기존 기능을 파악합니다.
2. 변경 요구를 **신규 / 변경 / 수정 / 보안 / 문서·운영** 중 하나로 분류하고 기능 영향 범위를 확인합니다.
3. 구현 후 관련 테스트를 추가·실행하고 실제 검증 여부를 구분합니다. 미구현·제약사항을 삭제하거나 감추지 않습니다.
4. `HISTORY.md` 맨 위(최신 먼저)에 **날짜, 종류, 기능명, 변경 내용, 영향을 받는 파일/화면, 테스트 결과, 미완료 사항, 연관 PR**을 기록합니다. 검증하지 않은 결과는 `미검증`으로 적습니다.
5. 동작·구현 상태를 바꾼 경우 관련 README와 구현 상태 표도 함께 갱신합니다.
6. **프로젝트 지침 자체를 변경할 때도** 변경 이유와 지침 변경을 이력에 남깁니다.
7. 가능하면 브랜치 → PR → CI 통과 → 병합 순으로 진행합니다. 기능 코드 변경 PR의 이력 누락 여부를 GitHub Actions가 검사합니다.
8. 원칙은 **기존 내용 보존 + 새 기록 추가**입니다. 과거 이력을 조용히 덮어쓰거나 기능이 존재했던 사실을 지우지 않습니다. 정정 시 정정 날짜/이유를 남깁니다.

GitHub PR 검증은 PR을 거치는 변경에 적용됩니다. **직접 `main`에 푸시하는 경우 체크를 우회할 수 있으므로** 개발 시 PR 방식이 권장됩니다.

## 6. 데스크톱에 설치할 때

데스크톱에서는 Node.js 20+ 환경에서 **필요한 스킬만 선별**하여 설치하고 개별 스킬의 최신 지침을 확인합니다.

```bash
npx --yes skills add NomaDamas/k-skill --skill court-auction-notice-search -g
npx --yes skills add NomaDamas/k-skill --skill real-estate-search -g
npx --yes skills add NomaDamas/k-skill --skill building-register-search -g
npx --yes skills add NomaDamas/k-skill --skill iros-registry-automation -g
npx --yes skills add NomaDamas/k-skill --skill korean-law-search -g
npx -y @nomadamas/k-skill@0 instruct court-auction-notice-search
```

데스크톱 설치/인증/조회가 성공했다고 기록하기 전 실제로 실행·검증합니다. 브라우저의 인증수단이나 개인자료는 GitHub 공개 문서/로그에 저장하지 않습니다.

## 7. 주요 참고 문서

- [개발 변경 이력](../HISTORY.md): 기능 추가·변경 내역의 단일 누적 기록
- [K-Skill 연동 가이드](K_SKILL_INTEGRATION.md): 실제 변환기 사용법 및 제약
- [기능 구현 상태](IMPLEMENTATION_STATUS.md): 제공·미제공 기능 구분
- [데이터 계약](DATA_CONTRACT.md): 물건·이벤트·출처·검증 규칙
- [복구 이력](RECOVERY_STATUS.md): 로컬 v11 계열 복구 및 검증 기록
