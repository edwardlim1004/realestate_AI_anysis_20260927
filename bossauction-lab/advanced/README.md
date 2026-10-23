# Auction Lab v11 Pages: 네이버 지도·경매/공매 워크스페이스

복구된 2026-10-18 BossAuction Reference v11.4의 자체 개발 기능을 참고해 다시 작성한 정적 웹용 버전입니다.
로컬 Python/SQLite 전체를 서버처럼 실행하는 배포가 아닙니다. 원본 대장옥션의 공식 서비스·비공개 API·저작물과 무관합니다.

## 온라인에서 가능한 기능
- 경매·공매 통합 필터, 물건 상세, 일정, 관심물건, 최대 3건 비교
- CSV/JSON 수동 가져오기(8MB, 1~10,000건), 브라우저 내 검색·정렬·지도 영역 필터
- 네이버 Web Dynamic Map v3 사용자 명시 실행, 실제 지도 이동·줌, 위성/지적도, 좌표가 있는 마커와 상세정보
- 지도 클릭을 통한 폴리라인 거리 및 다각형 면적 계산. 필지 법적 면적 아님
- 좌표 미제공 물건 지도 미표시, 사용자가 선택한 시험 좌표는 출처를 별도로 기록
- 권리문서 점검표(법률판정 아님), 낙찰 비용 산술 계산
- 기본 데이터 0건. 가상 데이터는 사용자가 예제 버튼을 누를 때만 표시

## 네이버 지도 활성화
1. 네이버 클라우드 새 Maps 상품에서 Web Dynamic Map 신청.
2. 허용 서비스 URL에 https://edwardlim1004.github.io 등록.
3. 지도검색의 연결 설정에서 새 ncpKeyId (Client ID)만 입력. Client Secret 입력 금지.
4. 실제 타일과 인증은 해당 개발자 계정 및 웹 브라우저 환경에서 확인.
5. 2026-06-25 AI NAVER API 지도 상품은 종료됐으므로 기존 Client ID가 동작하지 않을 수 있음.

## 기존 v11.4 DB 연동
기존 DB 파일은 GitHub Pages에 올리지 않고 로컬에서 tools/export_v11_sqlite.py를 실행한 뒤 출력 JSON을 사용자가 브라우저에 불러옵니다.
명령: python tools/export_v11_sqlite.py path/to/auction_v11.sqlite3 v11-export.json
사용권이 없는 원본 저장 화면과 이미지, API 비밀키, 개인정보 DB는 공개 저장소에 업로드하지 마세요.

지원 JSON: 최상위 sourceName, collectedAt 및 lots 배열. CSV: id, channel, title, region, type, location, authority, appraisal, minimum, date, failures, area, lat, lng, coordinateSource, sourceUrl 및 대응하는 대표적인 한글 헤더.
channel 값은 court/public 또는 경매/공매. 금액은 원, 기일은 YYYY-MM-DD.

## 아직 연동되지 않은 것
- 전국 법원·온비드 공식 실시간 API(공식 권한 및 서비스키/별도 서버 필요)
- Python 백엔드/SQLite 실시간 질의, 아파트 실거래 대용량 자동 수집(로컬 v11.4 기능에 남음)
- 실제 물건 위치 자동 지오코딩, 정식 로그인/결제/AI 권리 안전성 판정
- 지도 이동 시 원격 서버 호출 대신 현재 브라우저에 가져온 데이터에 한해 필터링

확인: Node.js에서 npm test 및 GitHub Actions. 실제 Maps 계정 인증·지도 타일 출력은 클라이언트 환경에서 별도 검증해야 합니다.
