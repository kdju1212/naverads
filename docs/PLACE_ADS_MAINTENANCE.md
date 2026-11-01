# 플레이스광고 유지보수 노트

작성: 2026-11-01 · 브랜치 `feat/place-ads` · 공식 문서 확인일: 2026-11-01

플레이스광고는 네이버 지도·플레이스 검색 결과에 가게를 광고로 보여 주는 상품이다. 이 저장소에서는 파워링크·쇼핑검색과 코드를 분리했다.
파워링크의 키워드 등록 화면·흐름은 쓰지 않는다. 플레이스광고는 키워드를 등록하지 않고 업체(플레이스 비즈채널) 기준으로 노출된다.

## 1. 일반 플레이스광고와 ADVoost 플레이스

| | 일반 플레이스광고 | ADVoost 플레이스 |
|---|---|---|
| 광고그룹 | `adgroupType=LOCAL_AD`, `adgroupAttrJson.useAdvoost=false`(또는 없음) | 같은 `LOCAL_AD` 그룹에 `adgroupAttrJson.useAdvoost=true` |
| 소재 | `LOCAL_AD`. 사람이 등록한다 | `ADVOOST_PLACE_AD`(연동형, type 17). 네이버가 자동 생성하며 `ad`는 `{}` |
| 입찰가 | 광고그룹 `bidAmt` | 변경 불가(3755). 생성할 때도 보내지 않는다 |
| 제외검색어 | 등록·삭제 가능 | 등록 불가(3754, 4422) |
| 소재 추가 | 가능 | 불가(3839). 연동형 직접 등록 불가(3840) |
| 연동형 소재 ON/OFF·삭제 | 해당 없음 | 불가(3838, 3837). 그룹의 `useAdvoost`로만 바뀐다 |
| 끄면 | - | `useAdvoost=false`로 바꾸면 연동형 소재는 지워지지 않고 OFF가 된다 |
| 조건 | 플레이스 비즈채널 | 스마트플레이스 업체 이미지 1개 이상(없으면 3752), 병의원 업종 불가(3756) |

계층 구조: 캠페인 `campaignTp=PLACE` → 광고그룹 `LOCAL_AD`(플레이스 검색 그룹) → 소재.
같은 PLACE 캠페인 아래 있는 `adgroupType=PLACE`(지역소상공인 그룹)는 다루지 않는다.

## 2. 지원 작업과 위치

서버: `backend/src/app/place.py`
- 웹 API: `GET /workspaces/{ws}/place?ad_account_id=`, `POST .../place/plan`, `POST .../place/apply`
- 네이버 호출: `backend/src/app/naver.py`의 `RealNaverClient.create_place_adgroup·set_advoost·create_place_ad`. 나머지는 기존 `update`·`create_campaign`·제외검색어 함수를 쓴다.
- Mock(`MockNaverClient`)은 위 ADVoost 규칙과 오류 코드를 그대로 흉내 낸다.

화면: `frontend/app/place/page.tsx`(메뉴 "광고 관리 > 플레이스광고")
- 용어 설명
- 새로 만들기: 업체 선택 → 예산 → 광고 내용 확인 → 최종 승인
- 지금 상태와 변경 버튼
- 승인 패널

MCP 도구(Claude): `place_ads_status`, `place_ads_plan`, `place_ads_apply`. 정의는 `place.TOOLS`, 연결은 `mcp.py _call`.

| 작업(action) | 네이버 API | 일반 | ADVoost | 실계정 확인 |
|---|---|---|---|---|
| 상태 조회 | `GET /ncc/channels`, `/ncc/campaigns`, `/ncc/adgroups?nccCampaignId=`, `/ncc/ads?nccAdgroupId=`, `/ncc/adgroups/{id}/restricted-keywords`, `/stats` | ✔ | ✔ | 기존 함수는 확인, 플레이스 데이터는 미확인 |
| `create` | `POST /ncc/campaigns`(campaignTp=PLACE, OFF) → `POST /ncc/adgroups`(LOCAL_AD, OFF) → (일반만) `POST /ncc/ads`(LOCAL_AD) | 소재 단계는 실계정에서 막음 | ✔ | 미확인 |
| `set_budget` | `PUT /ncc/campaigns/{id}?fields=budget` | ✔ | ✔ | 파워링크로 확인한 방식 |
| `set_bid` | `PUT /ncc/adgroups/{id}?fields=bidAmt` | ✔ | 차단(3755) | 파워링크로 확인한 방식 |
| `turn_on`/`turn_off` | `PUT ...?fields=userLock`(캠페인·그룹·소재) | ✔ | 연동형 소재는 차단(3838) | 파워링크로 확인한 방식 |
| `set_advoost` | `PUT /ncc/adgroups/{id}?fields=useAdvoost` | 켜기 | 끄기 | 미확인(릴리스 노트 예시 그대로) |
| `add_negative_keyword`/`remove_negative_keyword` | `/ncc/adgroups/{id}/restricted-keywords` | ✔ | 등록 차단(3754) | 파워링크로 확인 |

하루예산은 광고그룹이 아니라 캠페인 하루예산으로 건다. 광고그룹은 `useDailyBudget=false`로 만든다.
캠페인 예산 변경은 실계정에서 확인한 쓰기여서 그쪽으로 모았다.

## 3. 비즈채널·계정 조건

- 광고 계정에 `channelTp=PLACE` 비즈채널(스마트플레이스 업체)이 연결돼 있어야 한다. 없으면 화면이 연결 방법을 안내한다.
- 비즈채널 검토(`inspectStatus`)가 끝나지 않았으면 계획 요약의 주의에 표시한다. 막지는 않는다.
- ADVoost: 업체 이미지 1개 이상이어야 한다. 병의원 업종은 쓸 수 없다. 이 조건은 네이버만 알기 때문에 실행 때 거부되면 쉬운 설명으로 바꿔 보여 준다.
- 광고 계정은 이 서비스에 연결(CONNECTED)돼 있어야 하고, 사용자는 그 계정의 수정(EDIT) 권한이 있어야 한다. 조회는 VIEW 권한이면 된다.

## 4. 예산·입찰가·승인·권한 규칙(서버에서 강제)

- 하루예산: 1,000원~`PLACE_DAILY_BUDGET_MAX`(기본 100,000원), 10원 단위.
- 입찰가: 50원~`PLACE_BID_MAX`(기본 5,000원), 10원 단위. 50원은 공식 문서에서 확인하지 못했다.
- 돈이 나갈 수 있는 작업(켜기, 입찰가 변경, ADVoost 켜기)은 캠페인 하루예산이 있고 상한 이하여야 한다. 네이버 화면 등 다른 곳에서 예산을 크게 바꾼 경우에도 여기서 막힌다.
- 승인 절차(`approval_requests` 표, 0013에 이미 있음, 마이그레이션 추가 없음):
  1. plan: 권한·상한·ADVoost 규칙을 검사하고 네이버의 지금 값을 읽어 요약을 만든다. 요약에는 대상, 지금 값, 바뀔 값, 하루·31일 최대 지출이 들어간다. `ad_account_id·action·params`를 정규화한 JSON과 그 SHA-256을 저장하고, `PENDING`과 15분 만료를 건다.
  2. apply: 같은 조직이고 계획을 만든 사람인지 확인한다. 아니면 404.
  3. 다시 정규화한 요청의 해시가 다르면 409, 만료됐으면 410.
  4. `PENDING→RUNNING`을 UPDATE 한 문장으로 바꾼다. 재사용하거나 동시에 두 번 누르면 409.
  5. 실행 직전에 권한·상한·규칙을 다시 검사한다. 승인 뒤 권한이 없어졌으면 FAILED.
- 정규화: 액션별로 허용한 값만 정해진 타입으로 남긴다. 모르는 값을 끼워 넣어도 실행 내용은 바뀌지 않는다.
- 결과: `SUCCESS`(모든 단계 성공)·`PARTIAL`(일부, 예: 캠페인만 생성)·`FAILED`. 표에는 DONE/PARTIAL/FAILED로 남긴다.
- 변경 이력: 성공한 단계마다 `audit_logs`에 남긴다. `entity_type=place`, field는 campaign/adgroup/ad/daily_budget/bid_amt/status/advoost/negative_kw.
- 새 캠페인·광고그룹은 꺼진 상태(userLock)로 만든다. 성공 응답의 `notice`는 검토 후 노출되고 반영이 늦다고 안내한다. 즉시 노출된다고 말하지 않는다.
- 2026-11-01 사용자 결정: 승인은 지금 방식 유지(A). 계획을 만든 본인이 승인한다. 웹 승인 화면(B)과 관리자 결재(C)는 만들지 않는다.
  한계: 다른 사람의 결재가 아니라 '실행 전 내용 확인'이다. Claude에서 '항상 허용'이면 묻지 않고 적용된다.
- 2026-10-30 결정(14-11: Claude 변경 도구는 허용 버튼 = 승인)과의 관계: 웹에 따로 승인 화면을 만들지 않았다. 대신 plan→apply 두 단계와 해시 검사를 둔다. Claude에서는 plan 결과 표를 보여 준 뒤 apply를 부르고, 허용 버튼이 승인이다.

## 5. 네이버 API 주요 제한과 오류 코드

출처: 2026-09-16 릴리스 노트. 사장님용 문구는 `place.FRIENDLY`에 있다.

| 코드 | 의미 |
|---|---|
| 3752 | 스마트플레이스 업체 이미지가 없어 그룹 저장 불가(ADVoost) |
| 3753 | 업체 정보 로드 실패 |
| 3754, 4422 | ADVoost 그룹 제외검색어 등록 불가 |
| 3755 | ADVoost 그룹 입찰가 등 고급옵션 변경 불가 |
| 3756 | 병의원 업종 ADVoost 불가 |
| 3837 | ADVoost ON 동안 연동형 소재 삭제 불가 |
| 3838 | 연동형 소재 userLock은 그룹 useAdvoost로만 |
| 3839 | ADVoost 그룹에 소재 추가 불가 |
| 3840 | 연동형 소재 직접 등록 불가 |
| 4029 | ADVoost 그룹 확장소재 추가 불가 |
| 4420 | ADVoost 그룹 매체 타겟팅 변경 불가 |
| 5117 | ADVoost 그룹 지역·연령·성별·상세위치 타겟팅 변경 불가 |

- `adgroupAttrJson`은 요청에서는 객체, 응답에서는 JSON 문자열이다. `naver.advoost_on`이 둘 다 처리한다.
- 무료 플랜 한도는 요청 1번에 외부 호출 50번이다. 상태 조회는 광고그룹 15개까지만 소재·제외검색어를 읽는다(`DETAIL_GROUPS`). 넘으면 `partial`을 표시한다.

## 6. 테스트·운영 점검·장애 대응

- 로컬 테스트: `cd backend && uv run --group local pytest -q tests/test_place.py`. 네이버는 Mock이고 실계정은 호출하지 않는다.
  - 다루는 내용: 일반·ADVoost 허용·금지, 업체 조건(사진 없음·병의원), 상한, 승인 변조·재사용·만료·남의 승인, 계정·조직 간 차단, 승인 뒤 권한 상실, 파워링크 대상 거부, 네이버 실패, MCP 도구.
- 화면: `cd frontend && npm run build`. 로컬 확인은 백엔드를 `uvicorn`(dev, Mock 자격증명)으로 띄우고 `NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`로 연다. Mock 계정에는 플레이스 업체 3개(행복 분식·사진 없는 가게·튼튼 의원)가 있다.
- 운영 로그: `npx wrangler tail naverads-api --format json`. `/place/plan`·`/place/apply` 400 응답의 `detail`에 네이버 오류 코드가 들어 있다(예: "(네이버 오류 3752)").
- DB 확인:
  - 승인 상태: `SELECT id, tool, status, result, created_at FROM approval_requests WHERE tool LIKE 'place:%' ORDER BY id DESC LIMIT 20`
  - 이력: `SELECT * FROM audit_logs WHERE entity_type='place' ORDER BY id DESC LIMIT 20`
- 장애 대응:
  - `RUNNING`에 멈춘 요청은 실행 중 Worker가 끊긴 것이다. 네이버 광고관리에서 실제로 반영됐는지 확인한 뒤 새 계획을 만든다. 자동 재시도는 하지 않는다(중복 생성 방지).
  - `PARTIAL` 생성은 꺼진 캠페인이 남아 있다는 뜻이다. 네이버 광고관리에서 지우거나 이유(예: 3752 사진 없음)를 해결한 뒤 다시 만든다.
  - 상한을 바꾸려면 Cloudflare 환경변수 `PLACE_DAILY_BUDGET_MAX`·`PLACE_BID_MAX`를 설정한다.

## 7. 공식 문서(2026-11-01 확인)

- 릴리스 노트 2026-09-16(ADVoost 플레이스): https://naver.github.io/searchad-apidoc/release/2026/09/16/release-note/
- API 문서: https://naver.github.io/searchad-apidoc/
- FAQ(캠페인 PLACE, 그룹 LOCAL_AD·PLACE, 소재 LOCAL_AD 응답 예시): https://github.com/naver/searchad-apidoc/wiki/FAQ
- 명세 JSON(엔드포인트·enum): searchad-apidoc gh-pages `assets/json/ncc-heroes-ncc.json`
  - campaignTp에 PLACE
  - adgroupType에 LOCAL_AD·PLACE
  - 소재 type에 LOCAL_AD·ADVOOST_PLACE_AD

## 8. 아직 구현하지 못했거나 실계정 확인이 필요한 것

1. 실계정 미검증 항목. 플레이스 업체와 검수 통과 계정이 없어 아래 모두 확인 전이다.
   - PLACE 캠페인 생성
   - LOCAL_AD 그룹 생성: `userLock=true`, `useDailyBudget=false` 조합이 받아들여지는지, ADVoost OFF일 때 `bidAmt` 필수 여부
   - `useAdvoost` 변경
   - 상태 조회 응답의 실제 모양
2. 일반 플레이스 소재(`LOCAL_AD`) 등록 요청 본문은 공식 문서에 없다(응답 예시만 있음).
   - 지금은 실계정에서 막혀 있다: `NAVER_ALLOW_REAL_WRITE=1`일 때만 `ad.description` + `referenceKey=비즈채널 channelKey`로 보낸다.
   - 일반 방식 생성은 계획 단계에서 거절하고 ADVoost나 네이버 광고관리를 안내한다.
3. 플레이스 최소·최대 입찰가와 하루예산 최소값은 공식 문서에서 확인하지 못했다(서버 상한은 우리 정책).
4. 다루지 않는 것:
   - 지역소상공인 그룹(`adgroupType=PLACE`)
   - 플레이스 확장소재
   - 매체·지역 타겟팅
   - 광고그룹 단위 하루예산
   - 일반 소재 문구 수정
   - 이미지 소재
5. 마스터 보고서(브라우저 보관 데이터)는 플레이스 소재를 파싱하지 않는다. 플레이스 화면은 네이버에서 바로 읽는다. 성과 동기화에는 PLACE 캠페인을 포함하도록 바꿨다(`sync.py`).
6. `approval_requests`는 오래된 행을 지우지 않는다. 쌓이면 정리 작업이 필요하다.
7. 화면은 빌드와 lint만 확인했다. 브라우저로 직접 눌러 보지는 않았다.
