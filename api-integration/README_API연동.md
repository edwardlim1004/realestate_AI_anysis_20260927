# 국토부 실거래가·전세가 API 연동 가이드

## 🔐 인증키 보관 원칙 (가장 중요)

이 저장소는 **Public**이므로, 인증키를 코드에 직접 적어서 커밋하면 전 세계에 노출됩니다.
그래서 모든 스크립트는 키를 **코드에 절대 적지 않고**, 아래 두 경로 중 하나에서만 읽습니다.

| 상황 | 키를 넣는 곳 | GitHub에 올라가는가? |
|---|---|---|
| 내 컴퓨터에서 직접 테스트 | `api-integration/.env` 파일 | ❌ 안 올라감 (`.gitignore`에 등록됨) |
| GitHub Actions 자동 실행 | 저장소 Settings → Secrets → `MOLIT_SERVICE_KEY` | ❌ 안 올라감 (Secrets는 암호화 저장, 로그에도 안 보임) |

**`.env` 파일이나 실제 키 값이 담긴 어떤 파일도 GitHub에 업로드하지 마세요.** (`.gitignore`가 자동으로 막아줍니다.)

## 파일 설명

| 파일 | 역할 |
|---|---|
| `regions_lawd.py` | 56개 지역 ↔ 법정동코드(LAWD_CD) 매핑 (매매/전세 공통) |
| `fetch_molit.py` | 아파트 **매매** 실거래 API 호출 → 지역별 월별 평균가(전체/전용84㎡) 수집 |
| `fetch_jeonse.py` | 아파트 **전월세(전세)** 실거래 API 호출 → 지역별 전세가율(%) 계산 |
| `merge_into_datajs.py` | 위 두 결과를 기존 `data.js`에 병합, 점수·신호 재계산 |
| `update-data.yml` | 매달 자동으로 위 세 스크립트를 실행하고 결과를 자동 커밋하는 GitHub Actions |
| `.env.example` | 로컬 테스트용 키 입력 템플릿 (실제 키는 여기 적지 말고 `.env`로 복사해서 사용) |
| `.gitignore` | `.env`(인증키 파일)가 실수로도 커밋되지 않도록 차단 |

## A. 로컬에서 한 번 테스트해보기

```bash
cd api-integration
pip install requests

cp .env.example .env
# .env 파일을 열어서 MOLIT_SERVICE_KEY=발급받은키 로 실제 키 입력

# fetch_molit.py 상단의 REGION_FILTER = ["강남구","서초구"] 로 우선 2개 지역만 테스트
python fetch_molit.py            # -> molit_fetched.json 생성 (매매 데이터)
python fetch_jeonse.py           # -> jeonse_fetched.json 생성 (전세가율)

cp ../data.js .                  # 기존 data.js 복사
python merge_into_datajs.py      # -> data.js 갱신 (전세가율 포함)
cp data.js ../data.js            # 원래 자리로 되돌리기
```

정상 동작하면 `REGION_FILTER = None` 으로 바꿔서 56개 전체 지역을 수집하세요.

## B. 완전 자동화 (GitHub Actions) — 추천

1. **공공데이터포털에서 두 API 모두 활용신청** 되어 있는지 확인
   - 국토교통부_아파트매매 실거래 상세 자료 (`RTMSDataSvcAptTradeDev`)
   - 국토교통부_아파트 전월세 실거래자료 (`RTMSDataSvcAptRent`) ← 전세가율용, 별도 승인 필요
2. 저장소 **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `MOLIT_SERVICE_KEY`
   - Value: 발급받은 서비스키 (두 API 공통으로 같은 키 사용)
3. 아래 파일들을 저장소에 업로드
   - `api-integration/regions_lawd.py`
   - `api-integration/fetch_molit.py`
   - `api-integration/fetch_jeonse.py`
   - `api-integration/merge_into_datajs.py`
   - `api-integration/.gitignore` (이 폴더 안에 별도로 둬도 되고, 저장소 루트 `.gitignore`에 내용만 합쳐도 됨)
   - `.github/workflows/update-data.yml` ← 반드시 이 정확한 경로
   - **`.env`나 `.env.example`은 올릴 필요 없습니다** (Actions에서는 Secrets를 바로 씁니다)
4. 저장소 **Actions** 탭 → "Update Real Estate Data" → **Run workflow** 로 수동 실행해서
   `data.js`가 갱신·자동 커밋되는지 확인
5. 이후 매달 1일 자동 실행되어 매매 시세 + 전세가율이 함께 갱신됩니다.

## C. 전세가율이 어떻게 반영되나요

- `fetch_jeonse.py`가 최근 6개월간 전용 80~90㎡ **순수 전세**(월세 0원) 거래만 모아 평균 보증금을 구하고,
  같은 지역의 매매 평균가(`fetch_molit.py` 결과)와 비교해 `전세가율 = 전세보증금 / 매매가 × 100`을 계산합니다.
- 거래 표본이 부족한 지역(전세 매물이 거의 없는 초고가 단지 등)은 **자동으로 건너뛰고 기존 값을 유지**하므로,
  희소한 데이터로 잘못된 급락/급등 신호가 나오는 것을 방지합니다.
- `merge_into_datajs.py`가 56개 지역 전체를 다시 백분위 점수로 환산해 `scores.jeonse`를 갱신하고,
  이 값이 종합점수(가중치 15%)에 반영되어 신호(🟢🟡🔴)가 자동으로 업데이트됩니다.

## D. 아직 남은 항목

- **모멘텀·리스크 점수**: 현재는 기존 스냅샷 값을 유지합니다. 모멘텀은 매매 API의 최근 3/6개월
  평균가 변화율로 대체 가능하고, 리스크는 치안(경찰청 API)·금리 민감도 등 외부 지표가 추가로 필요합니다.
  필요하시면 이어서 만들어 드릴 수 있습니다.
- **호출량 주의**: 매매 API는 56개 지역 × 61개월 ≈ 3,400회, 전세 API는 56개 지역 × 6개월 ≈ 340회
  호출됩니다. 공공데이터포털 기본 할당량을 넘을 수 있으니 활용신청 시 "트래픽 증가"를 함께 요청하세요.
