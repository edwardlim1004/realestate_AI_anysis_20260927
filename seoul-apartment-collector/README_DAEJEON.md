# 대전광역시 아파트 원본 수집

대전 동구(30110), 중구(30140), 서구(30170), 유성구(30200), 대덕구(30230)를
기존 서울·경기 수집기에 추가합니다. 기존 API/저장소 연결을 그대로 사용합니다.
시군구 코드는 [행정표준코드관리시스템](https://www.code.go.kr/stdcode/regCodeL.do) 기준입니다.

- 매매: 2006-01~현재 계약월. 2026-10 기준 1,250구간.
- 전세·월세: 2011-01~현재 계약월. 2026-10 기준 950구간.
- 합계 2,200구간. 구간은 구×계약월×매매/전월세 조회 단위이며 거래 건수가 아닙니다.
- 전세와 월세는 국토부 전월세 API 원본에 함께 포함됩니다. 월세금 0은 전세,
  양수는 월세로 집계하고 원본 JSON과 보증금·월세금 모두 보존합니다.

서울·경기의 `coverage_audit.json` 전수 저장 검증을 통과한 뒤 수집을 시작합니다.
배포 시 직전월 매매·전월세 두 구간을 실제 저장 후 다시 읽고, 과거자료는
200회 요청 단위로 진행 상태를 커밋하며 자동으로 이어갑니다. 일일 공동 한도에
도달하면 중단하고 다음 정기 실행에서 재개합니다.

대전 역시 기존 3시간 간격 작업에 포함됩니다. 최근 6개월은 하루 한 번 확인하며,
원본 내용이 달라진 구간만 저장하고 `updates/YYYY/MM.jsonl`에 변화 요약을 기록합니다.
서울·경기·대전 합산 일일 8,000회, 개별 실행 최대 1,200회, 요청 간 최소 3초를 유지합니다.
6개월보다 오래된 계약의 늦은 정정은 기간을 확장한 별도 갱신이 필요합니다.

R2는 계정 전체 측정과 공동 8GB 안전선을 통과할 때만 원본을 추가하며,
측정 불가·안전선 초과 시 Google Drive로 검증 후 대체 저장합니다.
기존 `seoul-apartments/v1/` 접두사는 유지하고 `30xxx` 지역코드로 분리합니다.
Google 연도별 CSV는 대전 폴더와 `daejeon-*` 파일 식별자를 사용합니다.

`daejeon_backfill_progress.json`으로 대전 누락 구간을 확인합니다. 전체 저장 완료 후
`verify_daejeon_storage.py`가 모든 파일을 다시 읽고 SHA256·행 수·지역·계약월·원본 필드를 검증합니다.
0건 구간 전부와 연도·유형별 표본은 API로 재조회하며 결과는 `daejeon_coverage_audit.json`에 저장합니다.
기존 `coverage_audit.json`의 서울·경기 검증 결과는 별도로 유지합니다.

```bash
python seoul-apartment-collector/collect.py --region daejeon --mode daily --max-requests 1200 --delay 3
python seoul-apartment-collector/backfill_progress.py --region daejeon
python seoul-apartment-collector/verify_daejeon_storage.py
```
