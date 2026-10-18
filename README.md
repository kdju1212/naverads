# naverads

SMB 전문 광고대행사용 네이버 광고(파워링크·쇼핑검색 상품형) 통합 관리 SaaS.

- 기준 문서: `Naver_Ads_SaaS_PROJECT_CONTEXT.md`
- 기획/설계: `docs/PRD.md`, `docs/SCREEN_SPEC.md`, `docs/DB_SCHEMA.md`, `docs/IMPLEMENTATION_PLAN.md`
- 진행 상태: `docs/IMPLEMENTATION_STATUS.md`

## 백엔드 (FastAPI on Cloudflare Python Workers + D1)
배포 주소: https://naverads-api.djkim0509.workers.dev/docs

```
cd backend
uv run --group local pytest -q                                    # 테스트
cd src && uv run --group local uvicorn app.main:app --reload       # 로컬(SQLite) http://localhost:8000/docs
uv run pywrangler dev                                             # 로컬 Workers + 로컬 D1 (먼저 .dev.vars 에 APP_SECRET=...)
npx wrangler d1 migrations apply naverads --remote                # 스키마 변경 시 (migrations/*.sql)
uv run pywrangler deploy                                          # 배포
```
Secret: `npx wrangler secret put APP_SECRET` (설정 완료).
