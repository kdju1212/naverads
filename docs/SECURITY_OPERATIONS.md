# 로그인·운영 보안 절차

작성: 2026-11-02 · 브랜치 `feat/web-approval-security` · 마이그레이션 `0016_web_approval_locks.sql`

광고 변경 승인과 광고비 안전장치는 `docs/AD_SAFETY_AND_APPROVALS.md`에 있다.

## 1. 웹 로그인 세션 (HttpOnly 쿠키)

**바뀐 것 (11/02)**
- 예전: 로그인 토큰을 응답 본문으로 받아 브라우저 `localStorage`에 저장했다. 그래서 스크립트가 주입되면 토큰을 훔칠 수 있었다.
- 지금: 서버가 `naverads_session` 쿠키를 심는다. 브라우저 스크립트는 이 토큰을 읽을 수 없다.
  - 쿠키 속성: `HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=43200`(12시간 = `TOKEN_TTL`)

| 항목 | 구현 |
|---|---|
| 로그인 | `POST /auth/login`, Google 콜백 → 쿠키만 심고 본문·주소에 토큰을 싣지 않는다. 가입(`/auth/signup`)은 로컬·테스트 전용이라 토큰도 돌려준다(운영 403) |
| 같은 사이트 | 웹 `naverads.djkim0509.workers.dev`와 API `naverads-api.djkim0509.workers.dev`는 같은 사이트(`workers.dev`가 공개 접미사 목록에 있어 사이트 = `djkim0509.workers.dev`)다. 그래서 `SameSite=Strict` 쿠키가 화면의 `fetch(credentials: "include")`에 실린다. 도메인을 바꾸면 이 조건을 다시 확인해야 한다 |
| CSRF | ① SameSite=Strict ② 쿠키로 인증한 GET 외 요청은 `X-Naverads-CSRF: 1` 헤더가 필수다(다른 사이트의 폼·이미지·링크는 못 붙이고, 스크립트는 CORS 사전 요청에서 막힌다) ③ `Origin`이 있으면 웹 주소여야 한다(`access.check_csrf`) |
| CORS | `allow_origins` = `access.WEB_ORIGINS`(운영 웹, 로컬 `APP_ENV=dev`일 때만 `http://localhost:3000`), `allow_credentials=True`, 허용 헤더 `authorization, content-type, x-naverads-csrf`. Workers 진입점의 마스터 보고서 파일 응답도 같은 출처만 허용한다(`src/main.py`) |
| 로그아웃 | `POST /auth/logout`: 지금 토큰의 해시를 만료 시각까지 `oauth_used`에 저장해 거부하고, 쿠키를 지운다. 모든 기기 로그아웃은 `token_version` 올리기 |
| 세션 만료 | 토큰 안의 만료 시각(12시간)이 지나면 401이다. 화면은 401이면 로그인 화면으로 간다. 갱신 토큰은 없다(하루 업무 단위) |
| Claude(MCP) | 그대로 `Authorization: Bearer`(/mcp 전용, 1시간 + 갱신 토큰)다. Claude 토큰은 쿠키·헤더 어느 쪽으로 와도 일반 API에서 거부한다 |
| Bearer 헤더 | 일반 API도 `Authorization: Bearer 웹 토큰`을 받는다(테스트·API 문서용). 헤더는 브라우저가 자동으로 싣지 않아 CSRF 대상이 아니다 |
| 화면 상태 | 브라우저에는 "로그인했음" 표시(무작위 값, 비밀 아님, `localStorage.session`)만 둔다. 로그인 화면으로 보낼지, 화면 캐시를 사용자별로 나눌지 정하는 데만 쓴다 |

**기존 사용자 전환**
- 배포 뒤 예전 토큰을 가진 브라우저가 화면을 열면 `migrateLegacyToken`이 그 토큰으로 `POST /auth/session`을 한 번 부른다.
- 서버는 예전 토큰을 무효로 하고 새 토큰을 쿠키로 준다. 화면은 예전 토큰을 지운다.
- 실패하면(만료 등) 로그인 화면으로 간다. 예전 토큰은 어차피 12시간 안에 만료된다.
- Claude 연결은 영향이 없다.

**로컬 개발**
- `http://localhost:3000` → `http://localhost:8000`도 같은 사이트(localhost)다.
- 브라우저는 localhost를 안전한 출처로 보고 `Secure` 쿠키를 받는다(최신 Chrome·Firefox 기준).
- Safari 등에서 로그인이 안 되면 https 로컬 서버를 쓴다.

**한계**
- 토큰에 무작위 값(jti)이 없다. 같은 초에 받은 토큰이 같은 값이면 하나를 로그아웃할 때 다른 것도 끊긴다.
  - 그래서 웹 토큰은 만료 시각을 0~10분 무작위로 당긴다(`security.make_token`, 11/02). 같은 초 두 번이면 1/600 확률로 여전히 같다.
- 주입된 스크립트는 토큰을 못 훔쳐도 로그인한 채로 API를 부를 수 있다. 그래서 CSP(`frontend/public/_headers`: 외부 스크립트 금지, 연결은 API만)를 유지해야 한다.

## 2. Google 로그인

- 계정은 이메일이 아니라 **Google 고유 식별자 `sub`**(`users.google_sub`, 고유 색인)로 찾는다. Google 쪽 이메일이 바뀌어도 같은 계정이다.
- 콜백에서 확인하는 것:
  - `state` 서명과 시작한 브라우저의 `g_state` 쿠키(로그인 CSRF)
  - id_token의 `iss`가 `https://accounts.google.com` 또는 `accounts.google.com`
  - `aud`가 우리 클라이언트 ID, `exp`가 지금 이후
  - `sub`가 있음, `email_verified`가 true
- id_token 서명은 검증하지 않는다. Google 토큰 엔드포인트에서 서버가 HTTPS로 직접 받은 토큰이라서다. Google OpenID Connect 문서는 이 경우 서명 검증을 생략할 수 있다고 안내한다(https://developers.google.com/identity/openid-connect/openid-connect#obtainuserinfo). 다른 경로(브라우저가 건넨 토큰)로 받게 되면 반드시 서명 검증을 넣는다.
- **기존 계정 연결(소유 확인)**
  - 같은 이메일의 비밀번호 계정이 있어도 자동으로 붙이지 않는다. 오류: "비밀번호로 로그인한 뒤 설정에서 Google 연결".
  - 연결 방법: 그 계정으로 로그인한 상태에서 설정 > 내 계정 > "Google 연결"을 누른다(`/auth/google/start?link=true`).
    - 시작할 때 로그인 쿠키로 본인을 확인하고, 그 사용자 ID를 서명된 `state`에 넣는다. 콜백은 그 계정에 `sub`를 붙인다.
    - 이미 다른 계정에 붙은 `sub`, 이미 다른 Google이 연결된 계정은 거부한다.
- **전환 예외** (0016 이전에 Google로 가입해 `sub` 없이 저장된 계정, 비밀번호 없음 `google$`)
  - **Google이 그 이메일의 주인일 때만** 처음 Google 로그인 때 `sub`를 기록한다(`main.google_authoritative`).
    - Gmail 주소(`@gmail.com`, `@googlemail.com`): Gmail 주소는 지워져도 다른 사람에게 다시 주지 않는다.
    - Google Workspace 조직 주소: id_token의 `hd`가 이메일 도메인과 같을 때. Google 문서는 조직 판단에 이메일 도메인이 아니라 `hd`를 쓰라고 한다.
  - 그 밖(개인 도메인·다른 회사 메일을 Google 계정에 등록한 경우)은 주소 주인이 바뀌었을 수 있다. 그래서 자동 연결하지 않고 "본인 확인이 필요합니다, 관리자에게 문의" 안내를 보여 준다.
  - **운영자 수동 연결 절차**(이메일 소유가 별도로 확인될 때만)
    1. 그 이메일로 보낸 메일에 답장을 받는 등 다른 경로로 본인을 확인한다.
    2. 예전 계정의 이메일을 비워 새 가입이 되게 한다: `UPDATE users SET email='legacy-<id>@moved.invalid' WHERE id=<예전 id> AND google_sub IS NULL`
    3. 사용자가 Google로 로그인한다 → `sub`가 있는 새 계정이 만들어진다.
    4. 조직 소속을 옮긴다: `UPDATE memberships SET user_id=<새 id> WHERE user_id=<예전 id>`(같은 조직에 새 계정이 이미 있으면 먼저 확인). 실행 전 대상 행을 SELECT로 확인하고, 작업 기록에 남긴다.
  - 한 번 `sub`가 기록되면 같은 이메일의 다른 Google 계정은 붙지 않는다.
  - 남은 위험: Workspace 조직이 주소를 다른 직원에게 다시 주면, 그 직원은 조직이 허락한 그 주소의 주인이 된다. 이 경우 Google 기준으로는 정당한 주인이다. 전환 기간을 줄이려면 배포 뒤 기존 Google 사용자에게 한 번 로그인하라고 알린다.
- Claude 연결 로그인 화면의 "Google로 로그인"도 같은 규칙(`main.google_user`)을 쓴다.

## 3. 네이버 API 비밀키 암호화 (CRED_KEY)

- 새 비밀키는 **CRED_KEY로만** 암호화한다(`security.encrypt`).
  - 운영(`APP_ENV`≠dev)에 CRED_KEY가 없으면 저장을 거부한다(503 "서버 설정이 끝나지 않아 …").
  - 로그인 서명 열쇠(APP_SECRET)로 대신 암호화하지 않는다. 그러면 APP_SECRET 하나만 새도 비밀키가 풀린다.
- 읽기는 CRED_KEY → CRED_KEY_OLD → APP_SECRET 순서로 시도한다. 예전에 APP_SECRET으로 암호화된 값을 읽기 위해서다.
- **기존 데이터 이전**
  1. `/health`의 `cred_key_loaded`가 true인지 본다(값은 내보내지 않음).
  2. 관리자가 설정 > 네이버 API 키 목록을 열거나 크론이 돌면 APP_SECRET·CRED_KEY_OLD로 된 값을 CRED_KEY로 다시 암호화한다(`bulk.rotate_credentials`).
  3. 목록 응답의 `key`가 모두 `CRED_KEY`인지 확인한다.
     - DB로 확인할 수는 없다(암호문만 있음). 화면이나 API 응답으로 본다.
     - `UNREADABLE`이 있으면 열쇠를 잃은 것이다. 그 키는 네이버에서 재발급해 "키 교체"로 다시 넣는다.
- **CRED_KEY 교체**(README와 같음): ① 지금 값을 `CRED_KEY_OLD`로 ② 새 값을 `CRED_KEY`로 ③ 위 2~3단계로 모두 옮겨졌는지 확인 ④ 그 뒤에만 `CRED_KEY_OLD`를 지운다.
  - 순서를 어기면 저장된 비밀키를 못 푼다(10/29 장애, 작업정리 14-9).
- 지금 운영: CRED_KEY는 처음 만든 값이고, 저장된 비밀키 2개는 CRED_KEY로 암호화돼 있다(작업정리 '주의').

## 4. GitHub main 브랜치 보호·필수 테스트

**실제로 확인한 것** (2026-11-02, 공개 GitHub API, 인증 없이 읽기만)
- 저장소 `kdju1212/naverads`는 **공개(public)** 저장소이고, 기본 브랜치는 `main`이다.
- `main`은 **보호되지 않음**(`protected: false`). 그래서 지금은 누구든 쓰기 권한이 있으면 테스트 없이 main에 push할 수 있고, push하면 Cloudflare가 바로 운영에 배포한다.
- GitHub Actions 실행 기록: **없음**.
  - `.github/workflows/test.yml`은 PR과 main push에서만 돈다. 브랜치 push만 했고 PR이 없어 한 번도 돌지 않았다.
- 관리자 우회(bypass) 설정과 rulesets: **확인하지 못함**. 인증이 필요한데 이 PC에 `gh`가 없다.
- 아래 설정은 **아직 적용하지 않았다**.

**필수 테스트 워크플로**
- `.github/workflows/test.yml`
  - `backend`: `uv run --python 3.13 --group local pytest -q`
  - `frontend`: `npm ci` → `tsc --noEmit` → `lint` → `npm test` → `build`
- 네이버는 Mock만 쓰고 비밀값은 필요 없다. PR을 열면 처음 돈다.

**설정할 것** (Settings > Rules > Rulesets > New branch ruleset)
1. 대상: `main`(Default branch)
2. **Restrict deletions** 켜기, **Block force pushes** 켜기
3. **Require a pull request before merging** 켜기
   - 승인 인원: 혼자 개발이면 0(PR을 거치는 것만 강제). 공동 작업자가 생기면 1 이상
   - "Dismiss stale pull request approvals when new commits are pushed" 켜기
4. **Require status checks to pass** 켜기 → `backend`, `frontend` 선택(PR에서 한 번 돌아야 목록에 나온다)
   - "Require branches to be up to date before merging" 켜기
5. **Bypass list는 비워 둔다**(관리자도 우회하지 않게). 급할 때 일시적으로 풀면 다시 켰는지 확인한다.
6. 공개 저장소라 Settings > Actions > General에서 "Fork pull request workflows"의 승인 요구(외부 기여자 첫 실행 승인)를 켜 둔다.
   - 워크플로는 비밀값을 쓰지 않지만, 남의 코드가 Actions에서 도는 것을 줄이기 위해서다.

**확인하는 방법**
- `curl -s https://api.github.com/repos/kdju1212/naverads/branches/main`의 `"protected": true`
- GitHub 설정 화면의 ruleset
- 일부러 실패하는 커밋을 올린 테스트 PR에서 병합 버튼이 막히는지

## 5. 운영 비밀값·외부 설정 확인 (값은 출력하지 않는다)

| 항목 | 확인 방법(값 노출 없음) | 11/02 확인 결과 |
|---|---|---|
| API Worker 시크릿 | `cd backend && npx wrangler secret list --name naverads-api`(이름만 나온다) | `APP_SECRET`, `CRED_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` 있음 |
| 프론트 Worker 시크릿 | `npx wrangler secret list --name naverads` | 없음(필요 없음) |
| CRED_KEY를 읽는지 | `curl -s https://naverads-api.djkim0509.workers.dev/health`의 `cred_key_loaded` | `true`, `roas_automation: false` |
| Google OAuth 콜백 주소 | Google Cloud Console > API 및 서비스 > 사용자 인증 정보 > OAuth 클라이언트의 "승인된 리디렉션 URI"에 `https://naverads-api.djkim0509.workers.dev/auth/google/callback`이 있는지 | **확인 못 함**(Google 콘솔 접근 없음). 코드는 요청 주소로 콜백 주소를 만든다(`main._google_callback_url`) |
| 쿠키 도메인 | 코드: `Domain` 없이 API 주소 전용(host-only), `Secure; HttpOnly; SameSite=Strict` | 배포 전이라 운영 응답으로는 확인 못 함 |
| CORS | 코드: 운영은 `https://naverads.djkim0509.workers.dev`만 | 같음 |
| 크론 | `backend/wrangler.jsonc` `*/10 * * * *`(예약 실행·자동입찰·목표 ROAS(정책상 꺼짐)·비밀키 열쇠 옮기기) | 저장소 설정 확인. 운영 대시보드의 트리거는 확인 못 함 |
| 요청 제한 | `ratelimits` IP당 1분 1500번(`LIMITER`) | 로컬 dry-run에서 바인딩 확인 |

- 비밀값을 문서·로그·채팅에 쓰지 않는다. `wrangler secret put`은 값을 입력 창으로만 넣는다.

## 6. Cloudflare 운영 상태 (2026-11-02 읽기 전용 확인)

**배포 버전** (`wrangler deployments list` / `versions list`)
- API `naverads-api`: 현재 100% `45d01556-7275-40c7-bd6e-c6225a4cd66f`(2026-11-01 14:15 UTC, main의 로그아웃 토큰 폐기 커밋까지).
  - 직전 버전 `754f7a21-…`, `47f53613-…`
- 프론트 `naverads`: 현재 100% `fd314ba9-1cac-4d09-ab44-9edf6143a765`(2026-11-01 14:17 UTC). 직전 `e8bd8973-…`
- 이 브랜치를 push한 뒤 **새 버전·미리보기 버전은 만들어지지 않았다**. 운영은 이 브랜치 코드가 아니다.

**Workers Builds** (GitHub check-runs)
- main 커밋(`6343e25`, `1da19d1`)은 두 Worker 모두 성공했다.
- 이 브랜치 커밋 `2e249fc`, `487de37`은 **두 Worker 모두 실패**했다(시작 1분 안에 끝남).
  - 빌드 로그는 이 PC의 wrangler 토큰 권한으로 읽을 수 없었다(Forbidden).
  - 로컬에서는 같은 코드로 두 Worker 모두 번들링(dry-run)에 성공했다.
  - **원인 미확인**: 비운영 브랜치 빌드 설정(배포 명령·브랜치 제한) 문제일 가능성이 있다. 병합 전에 아래 대시보드에서 실패 로그를 확인한다.
    - API: https://dash.cloudflare.com/7e4c8691da6c83db1b0a2180d768aafe/workers/services/view/naverads-api/production/builds/3223f7fe-28d3-43d4-a713-e16365ed86d6
    - 프론트: https://dash.cloudflare.com/7e4c8691da6c83db1b0a2180d768aafe/workers/services/view/naverads/production/builds/a2d8240c-ba39-4cf6-996b-0785316ac486
- 운영 브랜치·자동 배포·비운영 브랜치 빌드 설정은 대시보드(Workers > 각 Worker > Settings > Builds)에만 있어 **확인하지 못했다**.

**미리보기와 운영의 분리**
- Workers의 미리보기 버전은 **운영과 같은 바인딩**(같은 D1 `naverads`, 같은 시크릿 = 실계정 네이버 키 복호화 가능)을 쓴다.
- 크론은 배포된 운영 버전에서만 돈다.
- 그래서 API Worker는 미리보기 주소를 껐다(`backend/wrangler.jsonc` `"preview_urls": false`, 이 브랜치). 브랜치 빌드가 버전을 올려도 주소로 열 수 없다.
- 그래도 **비운영 브랜치 빌드는 끄기를 권한다**(대시보드 > Builds > "Builds for non-production branches"). 끄지 않을 거면 미리보기에서 운영 쓰기 테스트를 하지 않는다.
- 테스트용 별도 D1·네이버 계정은 없다. 그래서 운영 쓰기 테스트는 하지 않았다.

**운영 D1** (`wrangler d1 migrations list naverads --remote`)
- 적용 대기: `0016_web_approval_locks.sql` **하나**(0015까지 적용됨).
- Time Travel bookmark(11/02 확인): `000006b8-00000000-00005117-7dd1d9e366389bb6003421932605f78b`
  - 마이그레이션 직전에 다시 받아 그 값을 쓴다.
  - 무료 플랜은 7일, 유료는 30일까지 되돌릴 수 있다(공식 문서 https://developers.cloudflare.com/d1/reference/time-travel/).

## 7. 배포 순서·검증·롤백

**배포 전** (승인받은 뒤 진행)
1. PR을 열어 GitHub Actions `backend`·`frontend`가 통과하는지 본다.
2. 6절의 Workers Builds 실패 원인을 대시보드에서 확인한다(main 병합 뒤 운영 빌드가 같은 이유로 실패하면 배포가 안 된다. 그 경우 운영은 예전 버전 그대로).
3. 4절 main 보호를 적용한다.
4. 예약 대기 작업을 확인한다: `npx wrangler d1 execute naverads --remote --command "SELECT id, scheduled_at FROM bulk_jobs WHERE scheduled_at IS NOT NULL AND status='PREVIEW'"`
   - 캠페인 켜기·예산 증액 예약이 있으면 배포 뒤 웹 승인이 필요하다고 알린다.
5. 복구 지점을 기록한다: `npx wrangler d1 time-travel info naverads` → bookmark를 작업 기록에 남긴다.

**배포**
6. `cd backend && npx wrangler d1 migrations apply naverads --remote` → 0016(열·표·색인만 추가). **main 병합보다 먼저** 한다.
   - 새 열·표는 예전 코드가 쓰지 않고, 기본값이 있어 예전 코드의 저장도 그대로 된다. 그래서 0016을 먼저 적용해도 지금 운영은 영향을 받지 않는다.
7. 확인: `npx wrangler d1 execute naverads --remote --command "SELECT name FROM sqlite_master WHERE name IN ('account_locks','ix_users_google_sub')"`가 두 줄이면 된다.
8. PR을 main에 병합한다 → Workers Builds가 두 Worker를 배포한다. 두 빌드가 모두 성공했는지, `wrangler deployments list`에 새 버전이 100%인지 본다.

**배포 뒤 검증** (읽기·거절만. 광고를 켜거나 비용이 생기는 동작은 하지 않는다)
9. `curl -s …/health` → `ok: true`, `cred_key_loaded: true`
10. 점검 전용 계정(`.test-account`)으로 로그인한다.
    - 응답 본문에 토큰이 없고, 개발자도구 > Application > Cookies의 API 주소에 `naverads_session`(HttpOnly, Secure, SameSite=Strict)이 있다.
    - 새로고침해도 로그인이 유지되고, 로그아웃하면 쿠키가 지워진다.
    - 다른 사이트(예: 브라우저 주소창의 about:blank 콘솔)에서 `fetch(API+"/workspaces",{credentials:"include"})`를 부르면 CORS로 응답을 읽지 못한다.
11. 예전 버전에서 로그인해 둔 브라우저(있으면)가 다시 로그인하지 않고 넘어간다(`/auth/session` 전환).
12. Google 로그인과 설정의 "Google 연결"(비밀번호 계정이 있으면). 예전 Google 계정이 Gmail이 아니면 자동 연결되지 않고 안내가 나오는지.
13. 웹 승인 **거절** 시나리오(실계정 sdf 조직, 꺼진 캠페인이 있을 때):
    - 캠페인 화면에서 꺼진 캠페인 하나를 ON으로 미리보기 → 실행 → `/approvals`로 이동한다.
    - 화면에 지금 값(OFF)·바뀐 뒤(ON)·하루예산 합계·과금 안내가 보이는지 확인한다.
    - **거절**을 누른다 → 상태 "거절함". 네이버 광고관리에서 그 캠페인이 계속 꺼져 있는지 본다.
14. Claude에서 `get_approval`이 보이고, 같은 요청이 `execute_job`에서 승인 요청(approval)을 돌려주는지(그 요청도 웹에서 거절).
15. 30분 뒤 대기 요청이 "시간이 지나 무효"가 되는지(선택).

**롤백**
- **코드**(먼저 시도, 데이터 영향 없음): 두 Worker를 함께 되돌린다(새 프론트는 쿠키 로그인, 예전 API는 Bearer라 한쪽만 되돌리면 로그인이 안 된다).
  - `npx wrangler rollback 45d01556-7275-40c7-bd6e-c6225a4cd66f --name naverads-api`
  - `npx wrangler rollback fd314ba9-1cac-4d09-ab44-9edf6143a765 --name naverads`
  - 또는 대시보드 > Deployments > Rollback. 그 뒤 main에서 해당 커밋을 되돌리는 PR을 올려야 다음 push 때 다시 배포되지 않는다.
  - 0016은 그대로 둬도 예전 코드가 동작한다(추가된 열·표 무시).
- **DB**(코드 롤백으로 안 될 때만, 최후 수단): `npx wrangler d1 time-travel restore naverads --bookmark=<5단계에서 기록한 값>`
  - **그 시점 이후 모든 데이터가 사라진다**(회원·작업 이력·승인 기록 포함). 복구 명령이 돌려주는 bookmark로 되돌릴 수는 있다.
  - 실행하기 전에 사용자 승인을 받는다. 이번 작업에서는 실행하지 않았다.
  - 0016만 빼려면 복구 대신 `DROP TABLE account_locks; DROP INDEX ix_users_google_sub; DROP INDEX ix_approval_requests_job_id;` 후 `ALTER TABLE … DROP COLUMN …`(approval_requests: kind·ad_account_id·job_id·web_required·summary, users: google_sub)과 `DELETE FROM d1_migrations WHERE name='0016_web_approval_locks.sql'`. 보통은 필요 없다.

## 8. 남은 위험

- 토큰에 무작위 값(jti)이 없다(1절 한계, 만료 시각 무작위로 줄임). 기기별 세션 목록이 필요해지면 세션 표로 바꾼다.
- 승인 화면 주소(`WEB_URL`)를 Claude가 채팅에 보여 준다. 승인은 로그인한 웹에서만 되므로 주소가 새도 승인할 수는 없다.
- Workers 무료 플랜: 승인 실행도 요청 1번에 외부 호출·D1 쿼리 50번 한도 안이어야 한다. 큰 작업은 5행씩 나눠 이어서 실행한다.
- 운영 환경에서 쿠키·CORS·CSRF 조합은 아직 실제 브라우저로 확인하지 않았다(배포 전, 7절 10).
- 공개 저장소다. 비밀값은 저장소에 없지만(시크릿은 Cloudflare), `.test-account`·`.dev.vars`가 git에서 제외돼 있는지 계속 확인한다.
