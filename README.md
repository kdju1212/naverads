# naverads

SMB 전문 광고대행사용 네이버 광고(파워링크·쇼핑검색 상품형) 통합 관리 SaaS.

- 기준 문서: `Naver_Ads_SaaS_PROJECT_CONTEXT.md`
- 기획/설계: `docs/PRD.md`, `docs/SCREEN_SPEC.md`, `docs/DB_SCHEMA.md`, `docs/IMPLEMENTATION_PLAN.md`
- 진행 상태: `docs/IMPLEMENTATION_STATUS.md`

## 백엔드 실행 (Mock 모드)
```
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload   # http://localhost:8000/docs
python -m pytest -q
```
