# 데이터 카탈로그 / 기준일 / 감사경계
읽기 전용 기록. 출처·관측시점·공표시점·실제 수집시점·수정 이력을 분리해 기록할 것.

| 데이터군 | 담당 시스템/주 출처 | 파일/검증 근거 | 확인상태 및 한계 |
|---|---|---|---|
| 서울·경기 매매/전세/월세 | 국토교통부 실거래 | seoul-apartment-collector/coverage_audit.json | 2026-10-28 보관 범위 재열람; 원 API 88개 표본 체크, 거래 전수 대조 아님 |
| 대전 매매/전세/월세 | 국토교통부 실거래 | seoul-apartment-collector/daejeon_coverage_audit.json | 2026-10-28 보관 범위 2,200 재열람; 원 API 37개 표본 체크 |
| 자동수집 작업량·저장분포 | R2 / Google Drive | seoul-apartment-collector/status.json | 2026-11-01 지역합과 총계 1,310차이, 구분·산식 확인 필요 |
| 과거 지역 거래 공개 상세 | 국토교통부 집계 | trade-details/index.json | 서울 25 + 경기 31 + 대전 5 시군구, 매매; 원본 및 전월세 상세와 구분 |
| 전국/국제 거시 위험 | OECD, BIS | risk-data/risk_raw.csv, risk-data/source_registry.csv | 데이터별 분기·발표시차 상이. history percentile은 미래 하락확률 아님 |
| 유동성 | 한국은행 ECOS, OECD 결과 비교 | risk-data/liquidity/validation.json | SHADOW; 실제 과거 발표빈티지 확보 미충족 |
| 5년 아파트 평가 | 국토교통부 원천 CSV / R2 | long-term-value/build_snapshots.py | 2026-10-31 빌드 실패, 정상 갱신으로 판정 불가 |
| 대전 지역 4축 | R2/Drive 검증 자료 요약 | dashboard-v1/data/daejeon-regions.json | cutoff 2026-09; RESEARCH_ONLY, 타 도시와 점수 직접 비교 금지 |

## 공통 데이터 계약 (새 모듈 개발시 필수)
- Source ID / API endpoint / 법적 이용조건 / 원 관측키(지역×계약월×유형, 경제계열×주기×시점)
- observation_date, publication_date, retrieved_at_utc, as_of_cutoff, is_provisional, revision_id
- unit, seasonality, geography, duplicate/cancellation handling, source_sha256, derived_sha256
- 원래 공개되지 않는 기간은 SOURCE_UNAVAILABLE로 기록; 결측을 0 또는 실제 거래 0건으로 치환 금지
- 공개 GitHub에는 비밀키 및 권한 없는 원본·민감 데이터 게시 금지
- R2+Drive 데이터 이중보관은 별개 hash로 검증하고 원본 접근 실패 시 기존 검증본 유지

## 조회·보관 분리
GitHub 저장소: 코드, 방법론, 작은 감사 보고서 및 공개 가능한 집계.
R2/Drive: 크기가 큰 원시 및 과거 데이터. 실제 저장된 객체 존재, 내용, 버전은 이번 문서 정리로 재검증되지 않았다.
