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
