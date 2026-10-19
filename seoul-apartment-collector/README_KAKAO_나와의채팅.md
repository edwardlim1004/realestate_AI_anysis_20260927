# 카카오톡 '나와의 채팅' 완료 알림 설정 (2026-10)

GitHub: \`edwardlim1004/realestate_AI_anysis_20260927\`

**현재 구현:** 기존 수집 범위 11,000개(서울 아파트 매매 2006-01~2026-10 6,250개, 전월세 2011-01~2026-10 4,750개)의 R2 업로드 완료를 확인한 뒤, 카카오톡 *나와의 채팅*에 메시지 1회 전송. 기존 GitHub 이슈와 함께 전송 기록. 미설정 시 스킵.

공식: <https://developers.kakao.com/docs/ko/kakaotalk-message/rest-api> / <https://developers.kakao.com/docs/ko/kakaologin/rest-api>

## 1. 카카오 개발자 앱 설정 (웹에서)

1. <https://developers.kakao.com/> 로그인 → 내 애플리케이션 → 애플리케이션 추가.
   - 이름: \`Edward Seoul Apartment Alert\` (예시).
2. [앱] > [제품 링크 관리] > [웹 도메인]에 다음 도메인을 등록:
   \`https://edwardlim1004.github.io\`
   - 카카오 기본 텍스트 메시지의 클릭 가능한 URL과 일치해야 합니다.
3. [카카오 로그인] > [사용 설정] → **ON**.
4. [카카오 로그인] > [Redirect URI]에 정확히 다음 URI를 등록:
   \`http://127.0.0.1:8769/callback\`
   - Cloudflare R2 또는 GitHub Pages를 Redirect URI로 사용하지 않습니다.
5. [카카오 로그인] > [동의항목] > [접근권한]의 **카카오톡 메시지 전송(talk_message)**을 사용하도록 설정합니다. 동의 항목을 사용할 수 없으면 카카오 개발자 콘솔에서 요구하는 자격/검수 조건을 따라야 합니다.
6. [앱] > [플랫폼 키] > [REST API 키]를 확인하고 **클라이언트 시크릿**도 확인합니다.
   - 시크릿 사용이 ON인 경우 반드시 인증 요청에 시크릿을 포함해야 합니다. 제공한 도구는 ON을 전제로 합니다.

## 2. 내 PC에서 갱신 토큰 받기

GitHub에서 소스코드를 내려받아 Windows에서 **Python 3**로 아래 파일을 실행:

\`py -3 seoul-apartment-collector\\kakao_oauth_setup_local.py\`

- REST API 키를 입력합니다.
- Client Secret은 화면에 보이지 않게 입력합니다.
- 로컬 브라우저에서 본인 카카오 계정으로 로그인하고 **카카오톡 메시지 전송** 동의합니다.
- 인증 완료 후 터미널에 \`KAKAO_REFRESH_TOKEN\` 값이 한 번 표시됩니다.
- 이 값은 **GitHub Actions Secrets에만** 붙여넣고, 메일/메신저/채팅/공개 저장소로 보내지 않습니다.
- 코드·로그는 REST Client Secret과 발급된 Access Token을 디스크에 기록하지 않습니다.
- 8769 포트가 이미 사용 중이면 다른 프로그램을 종료한 뒤 다시 시도해야 합니다.

## 3. GitHub Actions Secrets 추가

<https://github.com/edwardlim1004/realestate_AI_anysis_20260927/settings/secrets/actions> 에서 다음 3개 추가:

| Secret | 무엇을 넣나 |
|---|---|
| \`KAKAO_REST_API_KEY\` | 카카오 개발자 앱 REST API 키 |
| \`KAKAO_CLIENT_SECRET\` | 카카오 개발자 앱 Client Secret |
| \`KAKAO_REFRESH_TOKEN\` | 로컬 OAuth 프로그램에서 처음 받은 갱신 토큰 |

기존 \`R2_ACCOUNT_ID\`, \`R2_ACCESS_KEY_ID\`, \`R2_SECRET_ACCESS_KEY\`, \`R2_BUCKET_NAME\`은 그대로 사용합니다.

## 4. 시험: 본수집 완료와 무관하게 테스트 메시지 발송

GitHub Actions → \`Kakao My Chat Message Test and Token Refresh\` →
\`Run workflow\` → \`action=test\` → 실행.

**'나와의 채팅'**에서 "[테스트] 서울 아파트 수집 알림 연결 확인" 메시지를 확인합니다. 테스트 실행을 여러 번 누르면 테스트 메시지는 여러 번 옵니다. 이 알림은 서울 전체 데이터 수집 완료를 의미하지 않습니다.

성공 로그: \`KAKAO_TEST: message accepted by Kakao API\`
실패 로그: \`KAKAO_ERROR\` 뒤의 HTTP 코드 확인 (키와 토큰 값은 표시되지 않음).

## 5. 완료 알림과 토큰 유지 방식

- 기존 워크플로는 매번 \`backfill_progress.json\`을 갱신합니다.
- 기준 11,000구간이 모두 업로드되면 GitHub 이슈가 생성되고 \`kakao_self_alert.py --mode complete\`이 한 번 전송을 시도합니다.
- 발송 API 성공 시 완료 GitHub 이슈에 \`edward-kakao-sent:seoul-history-202610\` 표시 코멘트를 추가합니다. 다음 실행에는 보내지 않습니다.
- R2 비공개 버킷의 \`internal/kakao-selfchat-refresh-v1.enc\`에 갱신 토큰을 **Fernet 암호화한 데이터만** 저장합니다. 공개 GitHub에는 비밀 토큰을 넣지 않습니다.
- \`Kakao My Chat Message Test and Token Refresh\` 워크플로는 매주 월요일 오전 7:15(KST)경 토큰 갱신을 시도합니다. 카카오가 갱신 토큰을 새로 발급하면 **새 토큰을 암호화해 R2에 보관**합니다. R2 저장에 실패하면 해당 실행도 실패로 표시됩니다.
- GitHub Secrets \`KAKAO_CLIENT_SECRET\`이나 \`R2_SECRET_ACCESS_KEY\`를 변경하면 암호화된 토큰을 복호화할 수 없을 수 있습니다. 변경 전 토큰 이전 계획을 세워야 합니다.
- R2 버킷에 저장되는 토큰도 결국 애플리케이션 접근정보입니다. R2 계정·GitHub Secrets에 대한 접근을 제한하세요.
- GitHub 이슈 댓글을 통한 중복 방지는 **대부분의 반복 실행**을 차단하지만, 카카오 발송 성공 직후 이슈 댓글 생성 전에 작업이 강제로 중단되면 다음 실행에서 같은 메시지가 중복될 가능성이 있습니다.
- 카카오 OAuth 연결해제·앱 설정 변경·토큰 폐기·권한 철회가 일어나면 다시 사용자 인증을 받아야 합니다.
- 토큰을 암호화하는 기능에 필요한 GitHub 의존성: \`cryptography\`. R2 접속용 \`boto3\`는 기존에 사용 중입니다.
- 실시간 수집의 추가 구간(2026년 11월 이후)은 계속 업데이트하며, 이번 알림은 **과거자료 2026-10 기준 11,000 구간** 완료를 알려줍니다.

## 오류가 나면

- \`KAKAO_SKIP: integration not configured\`: 필요한 GitHub Secret이 없음.
- \`KAKAO_SKIP: no initial refresh token\`: 갱신토큰 입력 누락.
- \`Service HTTP 401\` 카카오 측 응답이면 카카오 앱·토큰 인증 확인.
- \`Service HTTP 403\`이면 카카오 동의항목 \`talk_message\`과 제품 링크 도메인 확인.
- OAuth 실패 시 Client Secret과 Redirect URI가 동일한 앱에 등록돼 있는지 확인.
- 인증 실패 후 GitHub Actions 로그 전체를 그대로 외부에 공개할 필요 없습니다. 토큰 값은 절대 공유하지 마세요.

## 현재 검증 범위

- 사용자 카카오 계정 로그인이나 실제 메시지 발송은 **아직 검증 전**.
- GitHub Actions의 모의 API 테스트는 별도 코드에서 수행합니다.
- 토큰 교체를 GitHub Secrets에 직접 재기록하지 않고 암호화된 R2 객체에 저장하는 구조입니다.
