# 서울·경기도 아파트 과거 수집 및 변경분 정기 갱신

기존 `collect.py`가 서울과 경기도를 함께 처리합니다. 저장소 Secret 추가 없이
기존 국토부 API, R2, Google Drive 연결을 사용합니다.

## 수집 대상

- 서울 25개 구와 경기도 31개 시·군의 현행 47개 시·군·구 코드.
- 매매는 2006-01부터, 전월세는 2011-01부터 현재 계약월까지.
- 부천 구제 폐지·복원, 화성 2026-02 구 신설, 여주 시 승격 이전 코드도
  해당 계약월의 조회 대상으로 포함합니다. 개편 월은 필요한 신·구 코드를 함께 조회합니다.
- 2026-10 기준 서울 목표 11,000구간, 경기도 목표 19,062구간.
  이는 API 조회 구간의 수이며 거래 건수나 거래 내용의 전수 검증을 뜻하지 않습니다.

현행 코드 목록은 국립농산물품질관리원의 [정부 시군구 목록](https://www.naqs.go.kr/f2t/com/searchSgList.do),
화성·부천 개편은 행정안전부의 [화성 변경 공지](https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000052&nttId=122595)와
[부천 변경 공지](https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000052&nttId=105833)를 참고했습니다.
행정구역 개편 전후 원본은 조회한 LAWD_CD별로 보존하며, 지역 간 합산 분석에서는
행정구역 변환과 동일 거래 여부를 별도로 검증해야 합니다.

## 주기와 저장 방식

기존 Actions가 약 3시간 간격으로 실행됩니다. 서울·경기도가 한 작업과
`state.json`의 하루 합계 8,000회 예산을 공유합니다. 실행당 최대 1,200회,
요청 간 최소 3초 간격을 유지하고, 중단된 과거자료는 다음 실행에서 재개합니다.

국토부 API는 지역·계약월로 조회하므로 최근 6개월을 하루 한 차례 재확인합니다.
한 번 확인한 구간은 그날 뒤의 실행에서 다시 확인하지 않습니다. 응답 순서와 gzip
생성 시각에 영향받지 않는 내용 해시로 비교하여, **내용이 같은 원본은 재업로드하지 않습니다.**
같은 특성을 가진 거래가 여러 건이면 그 건수도 그대로 보존합니다.

신규·정정·해제·제외 등 실제 변화가 있으면 월별 원본을 갱신하고,
`updates/YYYY/MM.jsonl`에 추가/제외 건수, 변경 전후 해시, 조회 구간을 누적 기록합니다.
이 파일은 변경 요약이며 개별 거래 원문의 전체 버전 이력은 아닙니다.
처음부터 저장된 기존 서울 원본은 첫 비교 때 저장본의 SHA256을 검증하여
내용 해시를 보충하며, 변경이 없으면 원본을 다시 올리지 않습니다.
Git에 남은 예전 초기 원본이 최신 R2 원본을 덮어쓰지 않도록 보호합니다.

R2의 8GiB 안전선과 검증된 Google Drive 대체 저장을 함께 사용합니다.
R2 키의 기존 `seoul-apartments/v1/` 접두사는 호환을 위해 유지하며,
그 아래의 11xxx/41xxx 지역코드가 원본을 구분합니다.
Google Drive의 연도별 CSV는 **서울/경기도별 폴더와 파일**로 나누고,
기존 서울 파일의 식별자는 유지합니다. 기존 Windows F: 전용 동기화 도구는 서울 대상입니다.

## 실행과 상태 확인

```bash
python seoul-apartment-collector/collect.py --region gyeonggi --mode daily --max-requests 1200 --delay 3
python seoul-apartment-collector/backfill_progress.py --region gyeonggi
```

6개월보다 오래된 계약의 늦은 정정은 기본 갱신 범위 밖입니다. 필요하면 다음처럼
기간을 확장해 재확인할 수 있습니다. 처리한 구간과 요청 예산은 이어집니다.

```bash
python seoul-apartment-collector/collect.py --region gyeonggi --mode refresh --refresh-months 24
python seoul-apartment-collector/collect.py --region gyeonggi --mode refresh --until 202001 --refresh-months 6
```

- `status.json`: 마지막 요청·성공·실패, 실제 변경/변경 없음, 추가·제외 건수, 지역별 저장 구간.
- `backfill_progress.json`: 서울 과거자료 진행률.
- `gyeonggi_backfill_progress.json`: 경기도 과거자료 진행률.
- `updates/`: 변화가 발생한 구간만 기록한 월별 요약.

수집 코드가 main에 반영되면 경기도 수원시 장안구의 직전 계약월 매매·전월세를
최대 8회 요청으로 실전 점검합니다. 두 조회 구간의 저장 확인까지 통과해야
`GYEONGGI_LIVE_SMOKE_VERIFIED`를 출력합니다. 이 변경분 저장 커밋은 재실행을 유발하지 않습니다.

서울 수집 완료 카카오 알림은 완료 Issue 번호를 직접 전달하여 이슈 생성 직후
목록 조회에서 놓치는 문제를 피합니다. 기존 '나와의 채팅' 연결로 전송하며,
기존 성공 표시가 있으면 중복 발송을 건너뜁니다. 알림 실패는 수집 실패와 구분됩니다.
