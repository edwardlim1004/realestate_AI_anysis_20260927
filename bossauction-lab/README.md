# 기존 경매·공매 지도검색 화면 복원 (기본)

**기본 실행:** https://edwardlim1004.github.io/realestate_AI_anysis_20260927/bossauction-lab/

v10~v11.4 개인 개발본의 왼쪽 세로 메뉴, 경매 검색 목록, NAVER Maps SDK 설정·진단, 실제 지도 레이어, 거리·면적 측정, 보유 물건을 이용한 지도 집계를 참고해 기존 사용자 화면을 온라인 정적 페이지용으로 다시 만들었습니다.

- [classic/](classic/) — **복원한 새 기본 UI**. 동일 브라우저 Client ID 및 SQLite 사용자 데이터를 재사용하며, 기능이 활성화돼 있으면 자동 지도 연결.
- [advanced/](advanced/) — 기존 별도 통합검색, CSV·JSON, 물건 비교, 점검표·입찰 비용 분석 화면. 삭제하지 않았습니다.
- [legacy.html](legacy.html) — 최초 독립 데모 보존.
- [docs/RECOVERY_STATUS.md](docs/RECOVERY_STATUS.md) — 복원된 개인 v11.4 ZIP에 관한 검증 기록.
- [classic/README.md](classic/README.md) — 메뉴별 지원 상태, 온라인 한계와 사용법.

주의: 법원·온비드 실시간 전국 물건 API, 공식 AI 권리판단, 원본 사진의 재배포는 연결되지 않았습니다. 복구 ZIP에 포함된 외부 사이트의 HTML·사진·화면 캡처를 공개 GitHub 저장소에 올리지 않았습니다. 지도 지역별 수치는 현재 브라우저에 연결한 데이터에서만 계산합니다.

---

## 최초 별도 데모 기록
# Auction Lab v11 Pages — 개선된 GitHub Pages 웹앱

**현재 웹 시작 주소:** https://edwardlim1004.github.io/realestate_AI_anysis_20260927/bossauction-lab/

- 신규 진입 화면: [advanced/](advanced/) — NAVER Maps Web Dynamic Map 수동 연결, 지도 검색, 거리·면적 측정, 경매·공매 CSV/JSON 검색·비교·상세, 입찰 가정 계산
- [advanced/README.md](advanced/README.md) — 네이버 새 Maps Client ID 설정, 실제 구현·남은 제약, 로컬 v11.4 SQLite JSON 변환법
- [legacy.html](legacy.html) — 2026-10-23에 별도로 만든 이전 정적 데모 (보존)
- [docs/RECOVERY_STATUS.md](docs/RECOVERY_STATUS.md) — 로컬 v11.4 프로그램 복구 기록

**주의:** 새로운 Pages 버전은 2026-10-18 개인 보관 v11.4의 자가 개발 기능을 참고해 웹에서 실행되도록 다시 만든 버전입니다. Python/SQLite의 모든 기능을 정적 Pages에 포팅한 것은 아니며, 대장옥션의 실시간 원천정보나 타사 저장화면을 공개 배포하지 않습니다. 계정 인증 없는 기본 물건은 0건이며, 사용자가 가상 샘플 또는 사용권이 있는 파일을 선택해야 합니다.

---

## 아래는 이전 데모의 이력 문서

# 주의: 기존 v11.4 복원본이 아닙니다

이 `bossauction-lab/` 폴더는 2026-10-23 별도로 작성한 정적 샘플이며, 사용자의 2026-10-17/18 `BossAuction_Reference_v11_4.zip` 원본(네이버 지도 SDK, Python HTTP/SQLite 서버, 전국 DB 수용 구조, 실거래 CSV 수입기)을 복원한 것이 아닙니다. 비교 및 복구 절차는 [docs/RECOVERY_STATUS.md](docs/RECOVERY_STATUS.md)를 참조하십시오. GitHub Pages는 정적 호스팅이므로 Python+SQLite 백엔드를 실행하지 않습니다.

---

# Auction Lab — 경·공매 기능별 독립 프로토타입

대장옥션 공개 기능 범주를 연구하여 별도 구현한 정적 웹 앱입니다. 원본 사이트의 사유 소스코드·디자인 자산·유료 데이터·세션/API를 복제하지 않습니다.

**현재 상태: 데모 전용.** 표시되는 8건의 물건, 감정가, 날짜, 지역, 권리 검토 내용은 실제 경매물건이 아닙니다. 실제 입찰 판단에 사용하지 마세요. 원본 업체와 제휴·공식 관계가 없습니다.

## 바로 열기
- GitHub Pages 배포 시: https://edwardlim1004.github.io/realestate_AI_anysis_20260927/bossauction-lab/
- 로컬 서버: 저장소 루트에서 python3 -m http.server 8000 실행 후 http://localhost:8000/bossauction-lab/
- 또는 이 폴더에서 python3 -m http.server 8000 실행 후 http://localhost:8000/

브라우저 ES 모듈이므로 file:// 방식 직접 열기는 지원하지 않습니다. Node.js 20+ 사용 시 이 폴더에서 npm test로 순수 함수 테스트를 실행할 수 있습니다. npm install은 필요하지 않습니다.

## 구성
| 경로 | 역할 |
| --- | --- |
| index.html / assets/styles.css | 접근성 및 반응형 프레임 |
| src/app.js | 해시 라우팅 및 화면/이벤트 통합 |
| src/data/mock.js | **가상** 물건 8건 |
| src/core/format.js | 금액·날짜 포맷과 출력 이스케이프 |
| src/core/store.js | 로컬 관심물건 및 비교 선택 상태 |
| src/features/dashboard.js | 샘플 집계 및 기본 대시보드 |
| src/features/search.js | 검색·필터·정렬·목록 |
| src/features/schedule.js | 샘플 일정 |
| src/features/detail.js | 상세·권리분석 점검사항 |
| src/features/watchlist.js | 로컬 관심물건 |
| src/features/compare.js | 비교 테이블 |
| src/features/calculator.js | 비용·시나리오 계산 |
| src/adapters/README.md | 합법적인 외부 연동 방식 |
| docs/SITE_AUDIT.md | 공개 기능 확인 및 미확인 범위 |
| docs/DATA_CONTRACT.md | 향후 실제 데이터 계약 |
| tests/features.test.mjs | 함수 단위 테스트 |

## 다음 단계
1. 데이터 제공 권한 및 계약/API 자격 확보.
2. 서버 수집기와 데이터베이스 설계 후 소스·기준일·변경이력 저장.
3. 실제 물건 검색, 원문 문서·현황조사서·권리관계 등 화면에 단계적으로 연결.
4. 인증/알림/지도/관리화면/배포 검증 구현.
5. AI 권리분석은 명확한 근거 문서와 사람 검수 체계를 먼저 구축.

## 원본 기능 조사
docs/SITE_AUDIT.md 참조. 본 앱은 공개로 확인된 메뉴에 기반한 독립적인 기능 구현이며, 원본과 기능 동등성을 주장하지 않습니다.


## 추가 기능 (2026-10-23)

지도 지역 검색 (#map), JSON 자료 가져오기 (#data), 권리 서류 체크리스트 (#rights), 게스트 작업공간 (#workspace)을 구현했습니다. docs/IMPLEMENTATION_STATUS.md에 실제 구현과 미구현 기능을 구분했습니다. 공식 실시간 API, 정식 로그인, 실제 물건 좌표와 AI 권리판정은 아직 연동되지 않았습니다.
