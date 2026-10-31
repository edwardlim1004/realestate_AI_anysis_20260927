# 부산 → 대구 → 광주 아파트 원자료 순차 확보

2026-11-01 요청. 기존 서울·경기·대전 수집과 ver0/ver1 화면은 보존한다.

## 범위 및 순서

| 순서 | 지역 | 지리적 범위 | 원천코드 파티션 |
|---|---|---|---|
| 1 | 부산 | 16개 구·군 | 16 |
| 2 | 대구 | 9개 구·군(군위 포함) | 10(군위 구·신코드 포함) |
| 3 | 광주 | 기존 광주 5개 구(경기도 광주시 및 전남 다른 시군 제외) | 10(구·신코드 포함) |

- 매매: 2006-01부터. 전월세: 2011-01부터. 최초 역사자료 목표는 서울 기준과 같은 2026-10까지.
- 월세금 0이면 전세, 양수면 월세. 보증금·월세금·매매가·면적·주소·계약일·원본 JSON 보존.
- 최초 확보·검증 후 현재월 포함 최근 6개월을 정기 재조회한다. 현재월과 신고 진행 월은 잠정치이며 API에 미신고된 거래까지 완전하다는 뜻이 아니다.
- 15,840개 지역코드×월×거래유형 원천 파티션 목표. 별칭 코드를 포함한 수이며 실제 거래건수/행정구역 수가 아니다.
- 빈 월도 정상 응답을 저장하고, 저장 이후 다시 원 API를 조회해 확인한다. 코드 별칭끼리 거래건수를 합산하거나 가격지표에 바로 편입하지 않는다.

## 실행 / 저장

`.github/workflows/metro-apartment-history.yml`는 main 배포 즉시 및 3시간마다 실행한다.
기존 `seoul-apartment-collector` 동시실행 잠금과 `state.json`의 하루 8,000회 API 예산을 공유한다.
한 배치 200회, 한 실행 최대 4배치. 실제 호출에는 페이지네이션/재시도가 포함된다.
예산 소진 시 다음 실행에서 재개한다. 저장 결과는 매 배치 커밋한다.

원자료는 기존 R2 경로 `seoul-apartments/v1/<sale|rent>/<year>/<code>/<month>.csv.gz`에 저장한다.
R2 8GB 소프트 한도와 계정 전체 예산 검사를 그대로 사용하며 Google Drive 검증 저장으로 전환한다.
원천 CSV는 GitHub에 올리지 않는다. GitHub에는 매니페스트, 진행률, 압축 감사 명세와 코드만 둔다.
새 카카오 발송은 추가하지 않는다.

## 완료 조건

1. 모든 목표 파티션의 업로드 검증 매니페스트가 존재.
2. 원격 파일 전수 재읽기: SHA256/바이트/gzip/CSV/원본 JSON/계약일/지역코드/행 수/전세·월세 분류 확인.
3. 매매·전세·월세가 실제 관측되는지 확인(도시 전체가 잘못된 코드의 빈 응답인 상황 차단).
4. 빈 파티션 전체 + 지역코드·거래유형·연도별 비어 있지 않은 표본을 원 API로 재조회. 검증 영수증으로 이어서 실행.
5. 1~4 통과 후 다음 도시. API 정정 발견 시 해당 월을 갱신하고 재감사.

`metro_progress.json`의 `completed`는 업로드 목록 충족, `storage_reread_passed`는 저장 검증,
`verified`는 표본/빈 월 원 API 재확인까지 통과를 뜻한다. 이 세 상태를 구분한다.
파일이 변경되면 지문이 바뀌어 이전 감사결과를 재사용하지 않는다.

## 행정코드 출처와 주의

- 국토교통부 매매 API: https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev
- 국토교통부 전월세 API: https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent
- 행정표준코드: https://www.code.go.kr/stdcode/regCodeL.do
- 행정안전부 2026-07-01 개편 공지(광주 법정동 폐지/신설): https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000052&nttId=127039
- 광주 코드 전환 공지: https://hreas.gwangju.go.kr/NOTICE/BoardView.aspx?bID=429&bType=1&pID=0
- KOSIS 군위 47720 → 27720 안내: https://kosis.kr/serviceInfo/noticeDetail.do?boardIdx=2398

광주 신코드 12210/12240/12270/12300/12330 및 구코드 29110/29140/29155/29170/29200을 별도 보존한다.
변경일 이전 자료가 신코드에 재배정될 수 있으므로 행정 시행일로 API 수집기간을 잘라 버리지 않는다.
실제 원 API 지역코드와 저장 코드가 맞지 않으면 감사 실패로 남긴다.
신·구코드 동시 보관에 따른 중복 거래 조정은 별도 분석 단계이며, 검증 전 대시보드 점수에 편입하지 않는다.

## 로컬 확인

```sh
python -m unittest discover -s seoul-apartment-collector -p 'test_*.py'
python seoul-apartment-collector/metro_queue.py --report-only
```

원 API 및 R2/Drive 자격증명은 기존 GitHub Secrets에서만 사용한다.
