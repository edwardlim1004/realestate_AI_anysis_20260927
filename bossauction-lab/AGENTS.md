# BossAuction Lab — coding agent guidelines

Read `README.md`, `docs/DATA_CONTRACT.md` and `docs/K_SKILL_INTEGRATION.md` before adding external auction data. This is a static GitHub Pages app; a client browser must not contain API secrets, login sessions, or paid-source snapshots.

For NomaDamas/k-skill, use read-only and lawful workflows only. Candidate skills: `court-auction-notice-search`, `real-estate-search`, `building-register-search`, `iros-registry-automation`, `korean-law-search`. To inspect a skill's current instructions before use, run `npx -y @nomadamas/k-skill@0 instruct <skill-name>` on an authorized local machine. These skills are NOT installed in ChatGPT Projects by this repository.

`tools/k-skill-court-import.mjs` is a strictly offline adapter for normalized **property search** JSON; no network requests, login, scraping, or payments. Run `node --test tests/k-skill-court-import.test.mjs` to test it.

Preserve source metadata and distinguish missing values from observed zero. Do not invent case numbers, legal statuses, coordinates, property URLs or risk scores. Do not automatically bypass IP blocking, CAPTCHA, identity checks or fee walls. Raw PDFs and personal data must stay outside the public repository. Actual bids and legal interpretations require human verification.
