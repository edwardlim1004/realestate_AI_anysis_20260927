# 서울 아파트 매매·전월세 자동수집기

기존 부동산 GitHub Pages `index.html`, `data.js`, `.github/workflows/update-data.yml`을 변경하지 않는 독립 모듈입니다.

- GitHub Actions: 매일 한국시간 오전 03:30 **무렵** 예약 실행(UTC 18:30, 지연 가능)
- 서울 25개 구, 매매 2006-01~, 전월세 2011-01~; 요청하신 1998년부터의 공백은 원천자료 공개범위 밖입니다.
- 월/구별 `data/sale/YYYY/GU/YYYYMM.csv.gz`, `data/rent/YYYY/GU/YYYYMM.csv.gz` 저장. 종료 후 재시작 시 파일이 있는 월/구는 건너뜁니다.
- 매월 30일, 2월 말일(28/29)에 최근 6개월을 재조회하도록 설계했습니다.
- 기본 최대 180회 API 요청/실행, 최소 3초 간격, 인증·한도 오류 안전중단.
- 기존 API 자동화와 요청 할당량을 **공유할 수 있으므로 합산 이용량 확인 필수**.
- 인증키는 GitHub Repository Secret `MOLIT_SERVICE_KEY`만 사용. 계정에 이미 있다면 재입력할 필요 없습니다.
- **중요:** 공개 저장소로서 수집한 공개 거래자료도 공개됩니다. 원자료 이용조건 및 GitHub 저장소 파일 크기·용량 한도를 확인하세요.

## 사용 방법
1. 이 변경을 PR에서 검토한 후 병합합니다.
2. GitHub → Actions → **Seoul Apartment History Collector (Safe)** → Run workflow → `mode=test`로 송파구 1개월 시험을 진행합니다.
3. 확인 후 `mode=daily`을 실행하거나 자동 예약을 사용합니다. `status.json`으로 수집 범위를 확인합니다.
4. PC에서 `git clone https://github.com/edwardlim1004/realestate_AI_anysis_20260927.git` 실행 후 `seoul-apartment-collector/윈도우_F드라이브_동기화.bat`으로 F 드라이브에 연도별 CSV를 출력합니다.

GitHub Actions는 PC의 F 드라이브에 직접 접근할 수 없습니다. F로의 자동 동기화는 Windows 작업 스케줄러에서 BAT를 별도로 예약해야 합니다. GitHub Pages는 Python 수집기를 실행할 수 없습니다.

**검증:** 오프라인 모의 XML 시험 완료. 실제 계정 API 인증·예약 실행·F 드라이브 저장 성공은 아직 미확인입니다.
