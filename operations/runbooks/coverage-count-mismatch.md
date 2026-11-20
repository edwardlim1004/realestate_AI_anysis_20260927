# 장애 기록: 수집 범위 합계 불일치

- 확인 파일: seoul-apartment-collector/status.json (as_of_kst: 2026-11-01)
- total_completed_scopes: 35,344
- total_scopes: 35,344
- completed_by_region: Seoul 11,050 / Gyeonggi 20,774 / Daejeon 2,210
- region sum: 34,034 / difference: 1,310
- R2+Drive scope 합계: 20,781 + 14,563 = 35,344
- 해석: 집계 산식·이동/중복/범위 정의가 다른지 확인 필요. 원본 누락이라고 아직 단정 불가.

## 재검증 기준
1. scope 키 (region / legal district code / kind / YYYYMM) 정규화와 종전 행정구역 코드 매핑을 점검.
2. 현재 region-by-region과 historical/migrated scopes의 포함기준 비교.
3. complete scopes = unique verified object scope와 동일한 기준으로 분리 집계. stored scopes와 logical expected scopes 구별.
4. 1,310 차이를 구성하는 실제 키 집합을 읽기 전용으로 추출하고 중복/미분류/삭제 예정 제외 항목 식별.
5. 신고지연·정정·취소 검증과 저장 범위 완결성, 외부 API 재조회 감사는 서로 다른 PASS 판단으로 보고.

업데이트 결과가 근거와 함께 확인되면 STATUS, DATA_CATALOG 및 알림 문구를 갱신. 원본 삭제/이동 금지.
