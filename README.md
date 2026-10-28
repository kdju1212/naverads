# naverads

SMB 전문 광고대행사용 네이버 광고(파워링크·쇼핑검색 상품형) 통합 관리 SaaS.

- 기준 문서: `Naver_Ads_SaaS_PROJECT_CONTEXT.md`
- 기획/설계: `docs/PRD.md`, `docs/SCREEN_SPEC.md`, `docs/DB_SCHEMA.md`, `docs/IMPLEMENTATION_PLAN.md`
- 진행 상태: `docs/IMPLEMENTATION_STATUS.md`
- **최신 진행 상황·할 일은 `작업정리.txt`가 기준이다.** `docs/`는 10/18 설계 당시 문서라 그 뒤 바뀐 것(마이그레이션 0002~0012, Google 로그인,
  자동입찰·목표 ROAS, 광고 데이터 브라우저 보관 등)이 빠져 있다. DB 구조는 `backend/src/app/models.py`와 `backend/migrations/`를 본다.

## 웹 (Next.js 정적 사이트 on Cloudflare Workers)
주소: https://naverads.djkim0509.workers.dev

```
cd frontend && npm install && npm run dev      # http://localhost:3000 (API는 배포 주소 사용, NEXT_PUBLIC_API_URL로 변경 가능)
npm run build && npx wrangler deploy             # 저장소 루트에서 배포 (wrangler.jsonc, Worker 이름 naverads)
```
GitHub 연결된 Worker(`naverads`)는 루트 `npm run build` → `npx wrangler deploy`로 자동 배포된다.

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
