# 2026-10-23 이전 대장옥션 프로그램 확인 결과

- 이전 개발본: `BossAuction_Reference_v11_4.zip` (개인 Library에 원본 보관).
- 당시 실행: ZIP 전체 압축 해제 → `실행_윈도우.bat` → `http://localhost:8765/map.html`.
- 구성: 자체 HTML/JS 및 Naver Maps SDK 어댑터, `auction_backend.py` Python 서버, `auction_v11.sqlite3`, `molit_prices.py`, `molit_folder_import.py`, 데이터 검색·권리 검토·비용 및 CSV 처리 기능.
- 테스트: v11 Python API/SQLite 테스트, MOLIT API 파서, CSV 폴더 수입, 대용량 CSV 테스트(원 개발 PC 절대경로 테스트 오류를 로컬 준비로 해결), Playwright 모의 SDK 지도 테스트 통과.
- 이전 DB는 2026-10-17 저장본 21건으로, 실좌표 0건. 네이버 지도 타일과 SDK 인증 및 실시간 공식 경·공매 피드는 실제 서비스키로 검증되지 않음.
- 현재 이 폴더는 v11.4 코드를 옮기지 않은 **별도 데모**이다. v11.4 원본을 삭제한 것은 아니다.
- 원본 ZIP에는 대장옥션 저장 화면 및 이미지 등 외부 소유 자료가 포함돼 있어 **공개 저장소에 ZIP 전체를 게시하면 안 됨**. 자체 코드와 공개 가능한 부분을 분리 후 배포할 것.
- GitHub Pages는 Python/SQLite 서버를 운영하지 못함. 정상 운영에는 로컬 Python 서버 또는 별도 서버 호스팅, 네이버 개발자 계정 Dynamic Map 등록, 승인된 법원/온비드 데이터 연동이 필요.
- 본 문서는 사용자가 기존 v11.4 기능을 찾아 복구할 때 이전 데모의 기능 상태를 오해하지 않도록 만든 변경 이력이다.
