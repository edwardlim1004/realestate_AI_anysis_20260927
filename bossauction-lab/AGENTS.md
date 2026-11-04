# 필수: 프로젝트 지침과 HISTORY 유지

**옥션프로그램을 수정하기 전에 반드시** `docs/PROJECT_GUIDELINES.md` 및 `HISTORY.md`를 읽고, 기능·UI·연동·데이터 계약을 변경하는 동일 PR에서 HISTORY에 날짜, 변경 이유/내용, 영향 범위, 검증 및 한계와 PR을 남긴다. 지침 자체를 바꿀 때도 HISTORY에 기록한다. 관련 README/IMPLEMENTATION_STATUS는 실제 구현과 일치시킨다. 기존 HISTORY 항목은 삭제하지 않는다.

PR의 기능 코드 변경 시 `.github/workflows/bossauction-history-check.yml` 검사가 HISTORY 갱신 누락을 확인한다. 메인 브랜치 직접 푸시는 이 검사를 우회할 수 있으므로 PR 방식을 사용한다.

# BossAuction Lab — coding agent guidelines

Read `README.md`, `docs/DATA_CONTRACT.md` and `docs/K_SKILL_INTEGRATION.md` before adding external auction data. This is a static GitHub Pages app; a client browser must not contain API secrets, login sessions, or paid-source snapshots.

For NomaDamas/k-skill, use read-only and lawful workflows only. Candidate skills: `court-auction-notice-search`, `real-estate-search`, `building-register-search`, `iros-registry-automation`, `korean-law-search`. To inspect a skill's current instructions before use, run `npx -y @nomadamas/k-skill@0 instruct <skill-name>` on an authorized local machine. These skills are NOT installed in ChatGPT Projects by this repository.

`tools/k-skill-court-import.mjs` is a strictly offline adapter for normalized **property search** JSON; no network requests, login, scraping, or payments. Run `node --test tests/k-skill-court-import.test.mjs` to test it.

Preserve source metadata and distinguish missing values from observed zero. Do not invent case numbers, legal statuses, coordinates, property URLs or risk scores. Do not automatically bypass IP blocking, CAPTCHA, identity checks or fee walls. Raw PDFs and personal data must stay outside the public repository. Actual bids and legal interpretations require human verification.
