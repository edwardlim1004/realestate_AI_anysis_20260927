# Google Drive 5TB: Cloudflare R2 → Google Drive 자동 백업

R2는 원본 보관, Google Drive는 연도별 **CSV 자동 백업**입니다. GitHub Actions 클라우드에서 실행하며 **개인 PC를 켜둘 필요가 없습니다**. 기존 데이터 수집·지도·GitHub Pages·F: 프로그램은 변경하지 않습니다.

## 안전장치

- Google OAuth 권한은 **drive.file**만 요청합니다. 앱이 만든 Drive 파일 및 앱에서 선택한 파일만 접근. Google Drive 전체를 조회·삭제하는 광범위한 \`drive\` 범위는 사용하지 않습니다.
- Google OAuth는 **5TB를 사용하는 Google 계정**으로 로그인해야 합니다. \`drive.google.com/drive/u/1/home\`에서 보던 계정과 OAuth 창에서 선택한 계정이 같아야 합니다.
- 백업 프로그램은 Drive나 R2의 파일을 **절대 삭제하거나 공유하지 않습니다**. R2에서는 다운로드만 하며, 토큰 회전 시 예외적으로 R2의 비공개 내부 토큰만 기록합니다.
- R2에 저장된 파일 크기와 **SHA256**을 확인하고, Google Drive에 파일을 저장한 뒤 **MD5와 길이**를 검증합니다. 손상되면 오류 종료, 다음 실행에서 재시도합니다.
- 원본 \`*.csv.gz\`를 연도별 \`서울아파트_매매_2026.csv\` 및 \`서울아파트_전월세_2026.csv\`로 합칩니다.
- 과거 수집이 덜 된 연도는 **일부 구·월만 포함한 부분 데이터**일 수 있습니다. Drive 파일 설명에 원본 파일 수·거래행 수와 부분 데이터 가능성을 명시합니다.
- Drive의 \`appProperties\`에 원본 목록 지문(SHA256 목록 해시)과 결과 MD5를 적어 **변경 없는 연도는 재업로드하지 않습니다**.
- 매번 최근 연도 우선으로 검사하며 실행당 최대 12개 연도를 백업(수동으로 1~24개 조정). Google Drive API 분당 할당량이나 GitHub Actions 시간 제한 시 단계적으로 재실행합니다.
- Drive 기존 다른 폴더/파일은 수정하지 않습니다. **백업 프로그램이 생성한 전용 폴더**에서만 업로드/업데이트합니다.
- 카카오톡의 기존 수집완료 알림은 유지합니다. Google Drive 백업완료는 별도 이벤트이며 아직 카카오톡 발송조건에 연결하지 않았습니다.
- GitHub Actions Secrets 및 R2 암호화 저장소에만 갱신 토큰을 보관합니다. 일반 Git 파일이나 Actions artifact에는 비밀정보를 저장하지 않습니다.

## 사전 준비: Google Cloud Console

1. **5TB Google Drive 계정으로** <https://console.cloud.google.com/projectcreate> 에 로그인하고 \`Edward Seoul Apt Backup\` 프로젝트 생성.
2. <https://console.cloud.google.com/apis/library/drive.googleapis.com> 에서 **Google Drive API 사용 설정(Enable)**.
3. Google Cloud 콘솔 → **Google Auth Platform → Branding** 에서 OAuth 동의화면(앱 이름 \`Edward Seoul Apt Backup\`, 지원 이메일)을 만듭니다.
4. → **Audience**: 개인 계정이면 \`External\`, 회사 Workspace 내부 사용자만이면 \`Internal\`을 선택. External Testing 사용 시 본인 Google 계정을 Test Users에 추가.
5. → **Data Access**에서 \`https://www.googleapis.com/auth/drive.file\` 권한만 추가합니다. \`drive\` 전체범위는 추가하지 않습니다.
6. **장기 실행 중요**: External + Testing 게시상태는 Google 규정상 refresh token이 **7일 후 만료**됩니다. 본인 전용 장기 자동화 전에 Audience → **Publish App / In production** 전환을 검토하고, 필요한 Google 검증/경고/조직 정책이 있으면 그 조건을 따르세요. 전환 후 최초 OAuth를 다시 실행해 장기 토큰을 받는 것이 안전합니다. 워크스페이스 관리자는 사용을 제한할 수 있습니다.
7. → **Clients → Create client → Application type: Desktop app**. 이름 \`Edward-Seoul-R2-Drive\` → Create → **Download JSON**.
8. Google OAuth Client JSON은 **절대 공개 GitHub, 채팅, 이메일에 업로드하지 마세요.** 사용자 PC에서만 사용합니다. 서비스 계정(Service Account)은 사용자 5TB에 직접 저장하는 대체수단으로 사용하지 않습니다.

## 사용자 PC에서 최초 OAuth 인증 (한 번만)

사용자 PC에서 \`C:\EdwardTools\GoogleDriveBackup\` 폴더를 만들고, 다운로드한 **Desktop OAuth Client JSON**을 \`google_oauth_client.json\`으로 저장합니다.

프로그램 파일은 이 GitHub 저장소의:
\`seoul-apartment-collector/google_drive_oauth_local.py\`

파일을 같은 폴더에 내려받아 놓습니다. Windows PowerShell에서:

\`\`\`powershell
py -3 -m pip install --user google-auth-oauthlib
cd C:\EdwardTools\GoogleDriveBackup
py -3 google_drive_oauth_local.py
\`\`\`

브라우저에서 **5TB Google Drive 계정**으로 로그인·동의하세요. 프로그램은 정확히 \`drive.file\` 권한만 요청합니다. 성공하면 다음 3개 정보를 터미널에서 알려줍니다:

- \`GOOGLE_OAUTH_CLIENT_ID\`
- \`GOOGLE_OAUTH_CLIENT_SECRET\`
- \`GOOGLE_OAUTH_REFRESH_TOKEN\`

값은 **오직 GitHub → Settings → Secrets and variables → Actions → Secrets → New repository secret**으로 등록합니다.
\`MOLIT_SERVICE_KEY\`, 기존 \`R2_...\` Secrets, \`KAKAO_...\` Secrets는 수정하지 않습니다.

OAuth Client JSON은 GitHub에 올리지 말고 안전한 로컬 저장 위치에 보관하거나 보안 삭제합니다. 발급받은 갱신 토큰의 긴 문자열은 메모장이나 공개 소스에 저장하지 마세요.

## 먼저 수동 검증: 실제 백업 자동 실행 전

1. GitHub → Actions → **Cloudflare R2 to Google Drive Backup** → Run workflow
2. Branch \`main\`, mode=\`check\`, max_years=\`2\` 선택 → **Run workflow**.
3. \`GOOGLE_DRIVE_AUTH_OK\` 와 \`R2_SCOPES=...\` 로그가 나오면 OAuth와 Drive 조회 성공. 이 단계는 Google Drive에 파일을 만들지 않습니다.
4. 다시 Run workflow → mode=\`sync\`, max_years=\`2\`. Drive에 자동 생성된 \`Edward_부동산데이터_R2백업/서울아파트매매\` 및 \`서울아파트전월세\` 폴더와 CSV가 실제 존재하는지 확인합니다. 최근 연도부터 2개 연도만 시험합니다.
5. Google Drive CSV의 거래행 수와 앱 설명을 확인하세요. GitHub 로그 \`GDRIVE_BACKUP_OK kind=... year=... rows=...\`도 확인합니다.
6. 성공하면 GitHub → Settings → Secrets and variables → Actions → **Variables** 탭 → New repository variable:
   - Name: \`GDRIVE_BACKUP_ENABLED\`
   - Value: \`true\`
7. 이때부터 **매일 08:20(KST)경** 자동으로 R2에서 변경된 연도별 CSV를 백업합니다(GitHub 일정은 지연 가능). GitHub Actions 실행시간 제한이 있으므로 매번 최대 12개 연도를 처리하고, 다음 날 나머지를 이어받습니다.
8. 중단하려면 변수 \`GDRIVE_BACKUP_ENABLED\`를 \`false\`로 바꿉니다. Google Drive와 R2 파일은 삭제되지 않습니다.

## Google Drive에서 확인할 폴더

\`\`\`
내 드라이브/
  Edward_부동산데이터_R2백업/
    서울아파트매매/
      서울아파트_매매_2026.csv
      서울아파트_매매_2025.csv
      ...
    서울아파트전월세/
      서울아파트_전월세_2026.csv
      서울아파트_전월세_2025.csv
      ...
\`\`\`

Google Drive 파일 이름과 폴더는 Google 로그인 계정 소유로 생성합니다. 기존 개인 파일을 검색하거나 삭제하지 않습니다.

## 인증 토큰의 장기 보관

- Google OAuth refresh token을 GitHub Secrets에 처음 등록합니다.
- GitHub Actions는 실제 API 연결 후 private R2의 \`internal/google-drive-backup-refresh-v1.enc\`에 암호화된 토큰을 보관합니다. 향후 Google이 갱신 토큰을 교체하면 새 암호화 객체를 업데이트합니다.
- 암호화키는 GitHub의 \`GOOGLE_OAUTH_CLIENT_SECRET\`과 \`R2_SECRET_ACCESS_KEY\`에서 파생됩니다. **둘 중 하나를 바꾸면 기존 암호화 토큰을 읽지 못할 수 있으므로** 교체 시 토큰 재발급·이관을 계획해야 합니다.
- Google 앱 권한 철회·계정/조직 정책·7일 테스트 모드 만료가 발생하면 자동 갱신은 실패하고 수동 OAuth 재인증이 필요합니다.
- GitHub 로그에는 OAuth 인증 비밀을 출력하지 않고, 성공 연도·건수·바이트만 출력합니다.

## 제한 및 미검증

- 코드와 테스트는 **모의 Google Drive/R2 환경에서만 검증**했으며, 사용자 Google 5TB OAuth, 실제 파일 업로드, 해당 계정의 실제 잔여 용량은 아직 미검증입니다.
- Google Drive는 복구용 백업입니다. 수집자료가 공식 거래 신고 건수를 완전히 포괄하는지 확인하려면 별도 결측/정정 검증이 필요합니다.
- 위 구조의 백업은 **클라우드가 직접 수행**하므로 사용자 PC의 F: 드라이브에는 자동 기록하지 않습니다. F: 드라이브 동기화는 이전 Windows 모듈과 별도입니다.
