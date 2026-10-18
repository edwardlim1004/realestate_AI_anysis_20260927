# Cloudflare R2 전환 안내

기존 GitHub Pages 및 실거래 대시보드는 변경하지 않습니다.

## 필수 Repository Secrets
GitHub → Settings → Secrets and variables → Actions:
- `MOLIT_SERVICE_KEY` (기존)
- `R2_ACCOUNT_ID`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`
- `R2_BUCKET_NAME` (값: `edward-seoul-apartment-data`)

**인증값은 코드/채팅/스크린샷에 붙여넣지 마세요.** 버킷은 비공개 유지, R2 API 토큰은 해당 버킷 Object Read & Write로 제한하세요.

## 적용 순서
1. 위 4개 R2 Secret을 모두 만든 뒤에만 PR을 병합합니다.
2. Actions → Seoul Apartment History Collector (Safe) → Run workflow → `mode=test`, 요청 한도 `10`.
3. 첫 실행은 Git에서 이미 수집한 176개 `*.csv.gz`를 R2에 이전합니다. 확인할 로그: `R2_MIGRATION uploaded=... scopes=...`.
4. `R2_MIGRATION`, `OK sale`, `OK rent`, `RESULT`를 확인합니다.
5. R2 대시보드에서 `seoul-apartments/v1/` 경로 아래 파일 수를 확인하세요.
6. 성공할 때까지 기존 GitHub 데이터 삭제 금지. 프로그램도 자동 삭제하지 않습니다.

## 구조와 제한
- 새 API 데이터의 주 저장소는 Cloudflare R2의 `seoul-apartments/v1/sale/...` 또는 `rent/...`
- GitHub에 남는 것은 상태 파일 `state.json`, `status.json`, `r2_manifest.json`.
- Git에 이미 들어있는 기존 원본 파일은 **그대로 유지**하고 별도 확인 뒤 정리합니다.
- GitHub Pages 사이트는 R2의 비공개 파일을 바로 읽을 수 없습니다. 대시보드에는 향후 집계 요약 자료를 별도로 연결해야 합니다.
- GitHub Actions는 Windows F:에 직접 기록하지 못합니다. 현재 Windows 내보내기 도구는 Git에 존재하는 옛 파일만 처리하므로, R2 전환 후 새 데이터의 자동 로컬 동기화는 별도 단계입니다.
- R2 무료 요금은 10GB-month Standard 기준입니다. 비용이 자동으로 0원에 고정되는 것은 아닙니다.
- 소규모 이전 테스트 전 실제 API 및 R2 인증·파일 개수 검증은 아직 완료되지 않았습니다.

## 장애 처리
- 자격정보 부족: 워크플로는 R2 인증 오류로 실패하며 기존 Git 자료는 안전하게 남습니다.
- R2 업로드 오류: 해당 월·구를 완료로 인정하지 않으므로 다음에 재시도합니다.
- R2 성공/Git 커밋 실패: 매니페스트가 반영되지 않아 다음 실행에서 다시 업로드할 수 있습니다. 데이터 손실보다는 중복 업로드를 허용하는 정책입니다.
