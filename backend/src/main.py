"""Cloudflare Python Workers 진입점. 로컬 실행은 `uvicorn app.main:app` (src 폴더에서)."""
import os

# 앱은 모듈 최상단에서 import해야 시작 스냅샷에 포함된다(요청 안에서 import하면 무료 플랜 CPU 한도 초과)
os.environ.setdefault("APP_ENV", "prod")
os.environ.setdefault("DATABASE_URL", "d1")

import json  # noqa: E402
import re  # noqa: E402

import js  # noqa: E402
from fastapi import HTTPException  # noqa: E402
from pyodide.ffi import to_js  # noqa: E402
from workers import WorkerEntrypoint, asgi  # noqa: E402

from app import db as app_db  # noqa: E402
from app.bulk import run_all_auto_bids, run_all_goals  # noqa: E402
from app.main import app, master_file_source  # noqa: E402

# 마스터 보고서 파일은 FastAPI를 거치지 않고 JS fetch로 받아 그대로 넘긴다(파이썬이 본문을 다루면 CPU 한도 초과)
MASTER_FILE = re.compile(r"/workspaces/(\d+)/ad-accounts/(\d+)/master-reports/([^/]+)/file$")
CORS = {"Access-Control-Allow-Origin": "*"}  # Bearer 토큰 인증이라 모든 출처 허용(app.main과 같음)


def _response(body, status=200, content_type="application/json"):
    init = {"status": status, "headers": {**CORS, "Content-Type": content_type}}
    return js.Response.new(body, to_js(init, dict_converter=js.Object.fromEntries))


async def _master_file(request, ws_id, account_id, job_id):
    db = app_db.SessionLocal()
    try:
        src = master_file_source(db, request.headers.get("Authorization") or "", int(ws_id), int(account_id), job_id)
    except HTTPException as e:
        return _response(json.dumps({"detail": e.detail}, ensure_ascii=False), e.status_code)
    finally:
        db.close()
    tsv = "text/tab-separated-values; charset=utf-8"
    if "text" in src:  # Mock
        return _response(src["text"], content_type=tsv)
    r = await js.fetch(src["url"], to_js({"headers": src["headers"]}, dict_converter=js.Object.fromEntries))
    if not r.ok:
        return _response(json.dumps({"detail": f"보고서 다운로드 실패: {r.status}"}, ensure_ascii=False), 400)
    return _response(await r.arrayBuffer(), content_type=tsv)


class Default(WorkerEntrypoint):
    def _bind(self):
        os.environ.setdefault("APP_SECRET", self.env.APP_SECRET)  # Workers는 os.environ을 채우지 않는다
        app_db.bind_d1(self.env.DB)

    async def fetch(self, request):
        self._bind()
        m = MASTER_FILE.search(request.url.split("?")[0])
        if m and request.method == "GET":  # OPTIONS(사전 요청)는 FastAPI CORS가 처리
            return await _master_file(request, *m.groups())
        return await asgi.fetch(app, request, self.env, self.ctx)

    async def scheduled(self, controller, env=None, ctx=None):
        # 자동입찰·계정 목표 ROAS (wrangler.jsonc triggers.crons)
        self._bind()
        db = app_db.SessionLocal()
        try:
            run_all_auto_bids(db)
            run_all_goals(db)
        finally:
            db.close()
