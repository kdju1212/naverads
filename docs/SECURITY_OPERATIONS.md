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
| CORS | `allow_origins` = `access.WEB_ORIGINS`(운영 웹, `http://localhost:3000`), `allow_credentials=True`, 허용 헤더 `authorization, content-type, x-naverads-csrf`. Workers 진입점의 마스터 보고서 파일 응답도 같은 출처만 허용한다(`src/main.py`) |
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
- **전환 예외**
  - 0016 이전에 Google로 가입해 `sub` 없이 저장된 계정(비밀번호 없음 `google$`)은 처음 Google 로그인 때 `sub`를 기록한다.
  - 이유: 그 계정은 그때도 같은 Google 인증 이메일로만 만들 수 있었고, 그 밖에 소유를 확인할 수단(비밀번호)이 없다.
  - 한 번 `sub`가 기록되면 같은 이메일의 다른 Google 계정은 붙지 않는다.
  - 남은 위험: 회사 도메인 메일처럼 이메일 주인이 바뀌는 계정이면, 전환 전에 새 주인이 먼저 로그인할 수 있다. 전환 기간을 줄이려면 배포 뒤 기존 Google 사용자에게 한 번 로그인하라고 알린다.
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

**상태**
- 이 저장소의 실제 GitHub 설정은 **확인하지 못했다**. 작업한 PC에 `gh` CLI가 없고, 웹 설정 화면도 열지 않았다.
- 아래는 **적용해야 할 설정**이다. 적용했다고 보지 말 것.

**필수 테스트 워크플로**
- `.github/workflows/test.yml`(이 브랜치에서 추가, GitHub에서 아직 한 번도 돌지 않음)
  - `backend`: `uv run --python 3.13 --group local pytest -q`
  - `frontend`: `npm ci` → `tsc --noEmit` → `lint` → `npm test` → `build`
- 네이버는 Mock만 쓰고 비밀값은 필요 없다.

**설정할 것** (Settings > Rules > Rulesets > New branch ruleset, 또는 Settings > Branches > Branch protection rule)
1. 대상: `main`(Default branch)
2. **Restrict deletions** 켜기, **Block force pushes** 켜기
3. **Require a pull request before merging** 켜기
   - 승인 인원: 혼자 개발이면 0(PR을 거치는 것만 강제). 공동 작업자가 생기면 1 이상
   - "Dismiss stale pull request approvals when new commits are pushed" 켜기
4. **Require status checks to pass** 켜기 → `backend`, `frontend` 선택(워크플로가 한 번 돌아야 목록에 나온다)
   - "Require branches to be up to date before merging" 켜기
5. Bypass list는 비워 둔다(관리자도 우회하지 않게). 급할 때 일시적으로 풀면 다시 켰는지 확인한다.
6. Cloudflare Workers Builds는 main push마다 배포한다. 위 보호로 main에 들어가는 변경은 PR + 테스트 통과만 남는다.
   - Workers Builds의 빌드 명령에도 `pytest`가 이미 들어 있다(작업정리 18번).

**확인하는 방법**
- `gh api repos/kdju1212/naverads/rulesets`, 또는 GitHub 설정 화면
- 테스트 PR에서 실패하는 커밋이 병합 버튼을 막는지

## 5. 운영 체크리스트 (이 브랜치를 배포할 때)

1. `cd backend && npx wrangler d1 migrations apply naverads --remote` → 0016. **push보다 먼저** 한다.
2. 예약 대기 작업 확인(`docs/AD_SAFETY_AND_APPROVALS.md` 6절 2). 캠페인 켜기·예산 증액 예약이 있으면 사용자에게 웹 승인이 필요하다고 알린다.
3. Cloudflare 시크릿 확인: `APP_SECRET`, `CRED_KEY`(필수), `GOOGLE_CLIENT_ID`·`GOOGLE_CLIENT_SECRET`. 새로 넣을 시크릿은 없다.
   - 승인 화면 주소를 바꾸려면 `WEB_URL`. 기본값은 운영 웹이다.
   - `ROAS_AUTOMATION`은 넣지 않는다.
4. 배포 뒤 확인(점검 전용 계정 `.test-account`)
   - 로그인하면 응답 본문에 토큰이 없고, 개발자도구 > Application > Cookies의 API 주소에 `naverads_session`(HttpOnly)이 있다.
   - 새로고침해도 로그인이 유지되고, 로그아웃하면 쿠키가 지워진다.
   - 예전 버전에서 로그인해 둔 브라우저가 다시 로그인하지 않고 넘어간다(전환).
   - Google 로그인과 설정의 "Google 연결".
   - 웹 승인: 꺼진 캠페인 켜기 미리보기 → 실행 → `/approvals`로 이동 → 거절. 실계정에서 실제 켜기는 하지 않는다.
   - Claude: `get_approval`이 보이고, `execute_job`이 승인 요청을 돌려준다.
5. 4절 GitHub 설정을 적용하고 실제로 막히는지 본다.

## 6. 남은 위험

- 토큰에 무작위 값(jti)이 없다(1절 한계, 만료 시각 무작위로 줄임). 기기별 세션 목록이 필요해지면 세션 표로 바꾼다.
- 승인 화면 주소(`WEB_URL`)를 Claude가 채팅에 보여 준다. 승인은 로그인한 웹에서만 되므로 주소가 새도 승인할 수는 없다.
- Workers 무료 플랜: 승인 실행도 요청 1번에 외부 호출·D1 쿼리 50번 한도 안이어야 한다. 큰 작업은 5행씩 나눠 이어서 실행한다.
- 운영 환경에서 쿠키·CORS·CSRF 조합은 아직 실제 브라우저로 확인하지 않았다(로컬 테스트만, 5절 4).
