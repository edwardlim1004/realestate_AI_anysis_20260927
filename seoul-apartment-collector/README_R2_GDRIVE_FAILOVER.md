# Cloudflare R2 임계치 → Google Drive 원본 자동 전환

## 설계와 실제 한계

Cloudflare R2 Standard의 무료 사용량은 **월 10 GB-month**이고, 버킷 자체에는 별도 총저장량 상한이 없습니다. 기존 프로젝트에서 설정한 **8GiB**는 사용자가 정한 비용·안전 목적의 **소프트 임계치**이며 물리적인 용량 한계가 아닙니다.

현재 R2는 국토부 공식 API 구·월별 매매 및 전월세 원본 CSV.gz의 우선 저장소입니다. 사용자의 Google Drive에는 이미 별도의 연도별 CSV 백업이 작동합니다.

**R2에 새 파일을 저장하면 8GiB 소프트 임계치를 넘게 되는 경우** 새 파일을 Google Drive의 개인 전용 원본 압축 저장 폴더로 보내도록 구현했습니다. 업로드 후 Drive가 보고하는 MD5·바이트 크기가 일치해야만 GitHub 매니페스트에 해당 구간이 완료로 기록됩니다.

R2에 있던 원본은 **절대로 자동 삭제하지 않습니다.** Drive 검증에 실패하면 수집 실행은 실패로 종료해 다음 실행에서 재시도합니다. R2의 로그인·통신 장애를 용량 초과라고 단정해 무리하게 우회하지 않습니다.

이 기능을 사용하는 원본 데이터는 저장 위치가 R2 또는 Google Drive 중 어디인지 매니페스트에 표시됩니다. 11,000구간 완료 판정과 매매/전월세 연도별 Drive CSV 백업 작업 모두 두 위치를 참조하도록 조정했습니다.

## 자동 설정

Collector GitHub Actions의 다음 환경변수로 활성화합니다.

- R2_GDRIVE_FALLBACK_ENABLED = true
- R2_STORAGE_SOFT_CAP_BYTES = 8589934592 (8GiB)
- 기존 GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_OAUTH_REFRESH_TOKEN GitHub Secrets 재사용

Google Drive 대상 폴더:

내 드라이브 / Edward_부동산데이터_R2백업 / 원본월별압축_자동전환

이 폴더는 실제 전환 또는 수동 경로 검증 전에 보이지 않을 수 있습니다.

## 실제 전환 경로 수동 시험

GitHub Actions의 **Test Cloudflare R2 to Google Raw Archive Failover** → Run workflow (main)를 실행합니다. 이 작업은 기존 R2에 존재하는 공식 원본 중 검증된 작은 파일 하나를 개인 Google Drive에 복사하고 응답의 MD5와 크기를 확인합니다.

성공하면 로그에 R2_GDRIVE_RAW_PROBE_SUCCESS를 출력합니다. 기존 R2의 파일, GitHub 데이터 매니페스트, 수집 진행률을 변경하지 않습니다. 같은 파일을 다시 시험하면 재사용합니다.

이 시험은 실제 Drive OAuth와 업로드의 연결 확인용이며, R2 8GiB 실제 초과 상황을 시험하는 것은 아닙니다.

## 장애·복구와 알려진 제한

- OAuth 토큰이 만료되거나 Google Drive 업로드/검증이 실패하면 **미완료**로 남습니다.
- R2 자체가 전면적으로 사용할 수 없는 상황에서는 Google OAuth 갱신 토큰을 R2에서 읽지 못할 수 있습니다. 이 기능은 **저장량 초과 대비**이고 완전 독립적인 R2 장애재해복구는 아닙니다.
- Google Drive 계정의 남은 실제 용량은 별도 확인이 필요합니다.
- 기존 Windows F: 원본 동기화는 R2 파일만 가져옵니다. **Google Drive에만 저장된 원본은 해당 도구에서 아직 내려받지 않습니다.** 연도별 Google Drive CSV 백업에는 포함됩니다.
- 새 파일들은 연도별 CSV와 별도의 .csv.gz 형태로 저장됩니다.
- 데이터/원본 삭제·자동 R2→Google 이관은 수행하지 않습니다. 안전한 비용 절감을 위한 이전과 삭제는 별도 승인·검증 후 진행해야 합니다.
