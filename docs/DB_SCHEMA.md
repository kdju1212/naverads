# DB 스키마 — MVP v1.0

> 최종 갱신: 2026-10-18. 구현: `backend/src/app/models.py` (SQLAlchemy). 운영 DB: Cloudflare D1(SQLite 호환), 개발/테스트: SQLite. 스키마 SQL: `backend/migrations/`.

## 설계 원칙
- **조직(workspace)과 광고 계정(ad_account)은 다대다 관계 테이블(`workspace_ad_accounts`)로 분리.** 한 광고 계정이 대행사 교체 등으로 다른 조직에 연결될 수 있다.
- **직원별 계정 접근은 `account_access`로 관리.** OWNER/ADMIN은 조직의 연결된 전 계정 접근.
- 광고 데이터(campaigns 등)는 `ad_account_id`로 분리. 모든 조회는 접근 가능한 계정 ID 집합으로 필터링.
- `workspaces.type`: `AGENCY` | `DIRECT_ADVERTISER`. 직접 광고주는 "계정 1~몇 개 + 직원 1명인 조직"으로 동일 엔진 사용.
- 구독·결제 테이블은 광고 관리 테이블과 외래키로 엮지 않는다(조직만 참조).

## 테넌트·권한
| 테이블 | 주요 컬럼 | 설명 |
|---|---|---|
| `users` | id, email(unique), password_hash, name | 로그인 사용자 |
| `workspaces` | id, name, type | 대행사 또는 직접 광고주 조직 |
| `memberships` | id, workspace_id, user_id, role(`OWNER`/`ADMIN`/`MEMBER`) | unique(workspace_id, user_id) |
| `naver_api_credentials` | id, workspace_id, label, api_key, secret_key_enc, is_mock | 네이버 검색광고 API 라이선스. 비밀키 암호화 |
| `ad_accounts` | id, customer_id(unique), name, is_mock | 네이버 광고 계정(광고주) |
| `workspace_ad_accounts` | id, workspace_id, ad_account_id, credential_id, status(`CONNECTED`/`DISCONNECTED`), connected_by, connected_at | 조직-계정 관계 |
| `account_access` | id, membership_id, ad_account_id, level(`VIEW`/`EDIT`) | 직원별 담당 계정 배정 |

## 광고 데이터 (네이버 동기화 사본)
| 테이블 | 주요 컬럼 | 파워링크 | 쇼핑검색 |
|---|---|---|---|
| `campaigns` | ad_account_id, naver_id, name, campaign_tp, status, daily_budget | `WEB_SITE` | `SHOPPING` |
| `adgroups` | ad_account_id, campaign_id, naver_id, name, adgroup_type, status, bid_amt | `WEB_SITE` | `SHOPPING` |
| `keywords` | ad_account_id, adgroup_id, naver_id, keyword, status, bid_amt, use_group_bid | 사용 | **사용 안 함** |
| `ads` | ad_account_id, adgroup_id, naver_id, ad_type, status, inspect_status, bid_amt, use_group_bid, payload(JSON) | `TEXT_45` (bid 없음) | `SHOPPING_PRODUCT_AD` (소재 입찰가) |
| `performance_daily` | ad_account_id, campaign_id, date, impressions, clicks, cost, conversions, revenue | | |

- `status`: `ON` / `OFF` (네이버 `userLock` 의 반대).
- `conversions`, `revenue`는 NULL 허용 — **미제공과 0을 구분**. ROAS는 revenue가 NULL이면 NULL.
- 확장소재(`ad_extensions`), 비즈채널(`business_channels`), 제외 키워드는 공식 API 검증 후 추가 예정.

## 작업·감사
| 테이블 | 주요 컬럼 | 설명 |
|---|---|---|
| `bulk_jobs` | id, workspace_id, created_by, source(`UI`/`EXCEL`/`RETRY`), status, parent_job_id, created_at, executed_at | status: `PREVIEW` → `RUNNING` → `DONE`/`PARTIAL`/`FAILED` |
| `bulk_job_rows` | id, job_id, ad_account_id, entity_type, naver_id, field, before, after, status, error | status: `VALID`/`INVALID`/`SUCCESS`/`FAILED` |
| `audit_logs` | id, workspace_id, user_id, ad_account_id, job_id, entity_type, naver_id, field, before, after, created_at | 사용자별 변경 이력 |
| `sync_runs` | id, ad_account_id, status(`SUCCESS`/`FAILED`), error, started_at, finished_at | 동기화 상태·오류 |

## 구독 (광고 관리와 분리)
| 테이블 | 주요 컬럼 |
|---|---|
| `plans` | code, name, price_per_account(KRW), trial_days |
| `subscriptions` | workspace_id, plan_code, status(`TRIALING`/`ACTIVE`/`CANCELED`), trial_ends_at |

과금 대상 계정 수 = 해당 조직의 `CONNECTED` 계정 수 (조회 시 계산, 저장하지 않음).
