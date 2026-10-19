"""Cloudflare Python Workers 진입점. 로컬 실행은 `uvicorn app.main:app` (src 폴더에서)."""
import os

# 앱은 모듈 최상단에서 import해야 시작 스냅샷에 포함된다(요청 안에서 import하면 무료 플랜 CPU 한도 초과)
os.environ.setdefault("APP_ENV", "prod")
os.environ.setdefault("DATABASE_URL", "d1")

from workers import WorkerEntrypoint, asgi  # noqa: E402

from app import db as app_db  # noqa: E402
from app.bulk import run_all_auto_bids  # noqa: E402
from app.main import app  # noqa: E402


class Default(WorkerEntrypoint):
    def _bind(self):
        os.environ.setdefault("APP_SECRET", self.env.APP_SECRET)  # Workers는 os.environ을 채우지 않는다
        app_db.bind_d1(self.env.DB)

    async def fetch(self, request):
        self._bind()
        return await asgi.fetch(app, request, self.env, self.ctx)

    async def scheduled(self, controller, env=None, ctx=None):
        # 자동입찰 (wrangler.jsonc triggers.crons)
        self._bind()
        db = app_db.SessionLocal()
        try:
            run_all_auto_bids(db)
        finally:
            db.close()
