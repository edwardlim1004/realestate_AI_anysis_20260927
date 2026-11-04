# BossAuction Lab: k-skill 연동

이 연동은 외부 스킬을 ChatGPT 프로젝트에 설치하는 작업이 아니라, 실제 경매 웹앱의 기존 JSON 가져오기 기능에 연결할 수 있는 **오프라인 변환기**를 추가합니다.

## 이번에 구현한 범위

- `court-auction-notice-search search` 명령의 **정규화된 JSON**(`items[]`, `page`)을 `sourceName`, `collectedAt`, `lots[]` 형태로 변환합니다.
- `bossauction-lab/advanced/` 및 `bossauction-lab/classic/`의 기존 파일 반입 기능을 그대로 사용합니다. 웹앱에서 실시간 수집하거나 스킬을 서버에서 실행하지는 않습니다.
- 인터넷 접속·인증·결제·실시간 조회 없이 로컬 데이터만 변환합니다. 공식 원문 대조 전에는 미검증 데이터입니다.

## PC에서 사용하기 (Node.js 20 이상 권장)

먼저 코딩 에이전트에 스킬을 설치하고 지침을 확인합니다.

```bash
npx --yes skills add NomaDamas/k-skill --skill court-auction-notice-search -g
npx -y @nomadamas/k-skill@0 instruct court-auction-notice-search
```

CLI는 스킬 설치만으로 바로 실행 가능해지는 것이 아니므로, 별도 작업 폴더에서 공식 조회 패키지를 준비하고 사용자 지정 범위에 한정하여 검색합니다.

```bash
npm install --no-save court-auction-notice-search
npx court-auction-notice-search search --sido 서울특별시 --price-max 500000000 --page-size 20 > court-search.json
# 다음 줄은 프로그램 저장소 루트에서 실행
node bossauction-lab/tools/k-skill-court-import.mjs court-search.json court-import.json
```

`court-search.json`과 `court-import.json`은 저장소 외부 개인 작업 폴더에 보관하고 공개 GitHub에 올리지 마세요. 기존 출력 파일은 덮어쓰지 않습니다. 브라우저에서 경매 프로그램 **데이터 연동 → JSON/CSV 가져오기** 메뉴를 열어 `court-import.json`을 선택합니다.

변환 도구는 검색 결과의 **한 페이지**만 처리합니다. 결과가 없거나 입력이 원본 WebSquare 응답/사건 상세/매각공고 목록인 경우 오류를 반환합니다. 동일 사건+물건, 누락 식별자, 잘못된 금액/일자/유찰 횟수도 거부합니다.

## 데이터 의미

| 원천 필드 | 프로그램 필드 | 주의 |
| --- | --- | --- |
| courtCode + displayCaseNumber + itemNumber | id | 중복 차단 |
| address | location | 법원 표시 소재지 |
| appraisedPrice / minimumSalePrice | appraisal / minimum | 원 단위, 결측은 null |
| saleDate / flbdCount | date / failures | 날짜·횟수 검증 |
| usageCodes.large | type | 건물/토지만 분류, 나머지 미확인 |
| raw.hjguSido / 주소 | region | 확인 가능한 시도만 표시 |
| coordinatesWgs84 | lat/lng | 사용하지 않음 — 정밀 검증 없는 지도 마커 금지 |
| 법원 홈페이지 | sourceUrl | 물건별 딥링크를 임의 생성하지 않으므로 null |

`collectedAt`은 **변환 시각**이며 공식 법원 발표 시점이나 데이터 최신성을 증명하지 않습니다. 매각기일·가격은 정정·취하·연기로 바뀔 수 있으므로 **실제 입찰 전 법원 공식 원문을 재확인**해야 합니다: https://www.courtauction.go.kr

조회는 원 저장소의 제한(최소 2초 간격 및 세션 호출 예산)을 지키고, 차단을 우회하거나 대량 자동수집하지 않습니다. 파일·출력에 인증정보, 주민등록번호 등 개인정보를 넣지 않습니다.

## 다음 단계 — 아직 연동 전

- `real-estate-search`: 실거래가 비교
- `building-register-search`: 건축물대장 표제부 사실조회
- `iros-registry-automation`: 로컬 PC에서만 사용자 직접 로그인·결제로 등기발급 보조
- `korean-law-search`: 법령·판례 출처조회

등기/대장 사실조회가 권리 판단 또는 낙찰 추천을 자동으로 확정하지는 않습니다.

출처: https://github.com/NomaDamas/k-skill / https://github.com/NomaDamas/k-skill/tree/main/court-auction-notice-search — 기본 MIT, 일부 하위 프로젝트 별도 라이선스.
