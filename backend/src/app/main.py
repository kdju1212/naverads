from datetime import date, timedelta
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import bulk, naver, seo
from .access import admin_membership, current_user, membership, membership_of, resolve_account_ids, user_from_header
from .db import Base, engine, get_db
from .models import (AccountAccess, AdAccount, AuditLog, AutoBidRule, BulkJob, BulkJobRow, Membership, NaverApiCredential,
                     PerformanceDaily, Plan, Subscription, SyncRun, User, Workspace, WorkspaceAdAccount, now)
from .naver import NaverApiError, client_for
from .security import decrypt, encrypt, hash_password, make_token, verify_password
from .sync import sync_account

app = FastAPI(title="네이버 광고 통합 관리 API")
# 인증은 쿠키가 아닌 Bearer 토큰이라 모든 출처 허용해도 다른 사이트가 토큰을 쓸 수 없다
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
# 로컬(SQLite)은 create_all, Cloudflare D1은 migrations/*.sql 로 스키마 관리
if engine is not None:
    Base.metadata.create_all(engine)

DEFAULT_PLAN = {"code": "PER_ACCOUNT", "name": "계정당 요금제", "price_per_account": 19_900, "trial_days": 14}


def _ids(s: str | None) -> list[int] | None:
    return [int(x) for x in s.split(",") if x] if s else None


def _rows(objs, *cols):
    return [{c: getattr(o, c) for c in cols} for o in objs]


# ---------- 인증 ----------
class SignupIn(BaseModel):
    email: EmailStr
    password: str
    name: str


@app.post("/auth/signup")
async def signup(body: SignupIn, db: Session = Depends(get_db)):
    if len(body.password) < 8:
        raise HTTPException(400, "비밀번호는 8자 이상")
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "이미 가입된 이메일입니다")
    user = User(email=body.email, password_hash=await hash_password(body.password), name=body.name)
    db.add(user)
    db.commit()
    return {"id": user.id, "token": make_token(user.id)}


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@app.post("/auth/login")
async def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not await verify_password(body.password, user.password_hash):
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다")
    return {"id": user.id, "token": make_token(user.id)}


# ---------- 조직·직원·권한 ----------
class WorkspaceIn(BaseModel):
    name: str
    type: Literal["AGENCY", "DIRECT_ADVERTISER"] = "AGENCY"


@app.post("/workspaces")
async def create_workspace(body: WorkspaceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ws = Workspace(name=body.name, type=body.type)
    db.add(ws)
    db.flush()
    db.add(Membership(workspace_id=ws.id, user_id=user.id, role="OWNER"))
    plan = db.get(Plan, DEFAULT_PLAN["code"]) or Plan(**DEFAULT_PLAN)
    db.add(plan)
    db.add(Subscription(workspace_id=ws.id, plan_code=plan.code, status="TRIALING",
                        trial_ends_at=now() + timedelta(days=plan.trial_days)))
    db.commit()
    return {"id": ws.id, "name": ws.name, "type": ws.type}


@app.get("/workspaces")
async def my_workspaces(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Workspace, Membership.role).join(Membership, Membership.workspace_id == Workspace.id).where(Membership.user_id == user.id)
    return [{"id": w.id, "name": w.name, "type": w.type, "role": r} for w, r in db.execute(q)]


class MemberIn(BaseModel):
    email: EmailStr
    role: Literal["ADMIN", "MEMBER"] = "MEMBER"


@app.get("/workspaces/{ws_id}/members")
async def list_members(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    q = select(Membership, User).join(User, User.id == Membership.user_id).where(Membership.workspace_id == m.workspace_id)
    out = []
    for mem, u in db.execute(q):
        access = db.scalars(select(AccountAccess).where(AccountAccess.membership_id == mem.id)).all()
        out.append({"membership_id": mem.id, "user_id": u.id, "email": u.email, "name": u.name, "role": mem.role,
                    "access": [{"ad_account_id": a.ad_account_id, "level": a.level} for a in access]})
    return out


@app.post("/workspaces/{ws_id}/members")
async def add_member(body: MemberIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user:
        raise HTTPException(404, "가입된 사용자가 아닙니다")  # shortcut: 초대 메일 없음, 가입 후 추가. 초대 플로우는 2단계
    if db.scalar(select(Membership).where(Membership.workspace_id == m.workspace_id, Membership.user_id == user.id)):
        raise HTTPException(409, "이미 소속된 직원입니다")
    mem = Membership(workspace_id=m.workspace_id, user_id=user.id, role=body.role)
    db.add(mem)
    db.commit()
    return {"membership_id": mem.id}


class AccessIn(BaseModel):
    ad_account_id: int
    level: Literal["VIEW", "EDIT"] | None  # None = 배정 해제


@app.put("/workspaces/{ws_id}/members/{membership_id}/access")
async def set_access(membership_id: int, body: AccessIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    target = db.get(Membership, membership_id)
    if not target or target.workspace_id != m.workspace_id:
        raise HTTPException(404, "직원을 찾을 수 없습니다")
    if not db.scalar(select(WorkspaceAdAccount).where(WorkspaceAdAccount.workspace_id == m.workspace_id,
                                                      WorkspaceAdAccount.ad_account_id == body.ad_account_id,
                                                      WorkspaceAdAccount.status == "CONNECTED")):
        raise HTTPException(404, "이 조직에 연결된 광고 계정이 아닙니다")
    row = db.scalar(select(AccountAccess).where(AccountAccess.membership_id == membership_id,
                                                AccountAccess.ad_account_id == body.ad_account_id))
    before = row.level if row else None
    if body.level is None:
        if row:
            db.delete(row)
    elif row:
        row.level = body.level
    else:
        db.add(AccountAccess(membership_id=membership_id, ad_account_id=body.ad_account_id, level=body.level))
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=body.ad_account_id, action="ACCESS_SET",
                    field=f"membership:{membership_id}", before=before, after=body.level))
    db.commit()
    return {"ok": True}


# ---------- 네이버 자격증명·광고 계정 ----------
class CredentialIn(BaseModel):
    label: str
    api_key: str
    secret_key: str
    is_mock: bool = True


@app.post("/workspaces/{ws_id}/credentials")
async def add_credential(body: CredentialIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    cred = NaverApiCredential(workspace_id=m.workspace_id, label=body.label, api_key=body.api_key,
                              secret_key_enc=encrypt(body.secret_key), is_mock=body.is_mock)
    db.add(cred)
    db.commit()
    return {"id": cred.id, "label": cred.label, "is_mock": cred.is_mock}  # 비밀키는 반환하지 않는다


@app.get("/workspaces/{ws_id}/credentials")
async def list_credentials(m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    creds = db.scalars(select(NaverApiCredential).where(NaverApiCredential.workspace_id == m.workspace_id))
    return _rows(creds, "id", "label", "is_mock")  # 키는 반환하지 않는다


class ConnectIn(BaseModel):
    credential_id: int
    customer_id: str
    name: str


@app.post("/workspaces/{ws_id}/ad-accounts")
async def connect_account(body: ConnectIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    cred = db.get(NaverApiCredential, body.credential_id)
    if not cred or cred.workspace_id != m.workspace_id:
        raise HTTPException(404, "자격증명을 찾을 수 없습니다")
    try:
        client = client_for(cred, body.customer_id, decrypt)
        client.list_campaigns()  # 이 자격증명으로 해당 계정에 실제 접근 가능한지 검증
    except NaverApiError as e:
        raise HTTPException(400, f"광고 계정 접근 검증 실패: {e}")
    acc = db.scalar(select(AdAccount).where(AdAccount.customer_id == body.customer_id))
    if acc is None:
        acc = AdAccount(customer_id=body.customer_id, name=body.name, is_mock=cred.is_mock)
        db.add(acc)
        db.flush()
    elif acc.is_mock != cred.is_mock:
        raise HTTPException(400, "Mock/실계정 구분이 기존 계정과 다릅니다")
    link = db.scalar(select(WorkspaceAdAccount).where(WorkspaceAdAccount.workspace_id == m.workspace_id,
                                                      WorkspaceAdAccount.ad_account_id == acc.id))
    if link and link.status == "CONNECTED":
        raise HTTPException(409, "이미 연결된 계정입니다")
    if link:
        link.status, link.credential_id, link.connected_by, link.connected_at = "CONNECTED", cred.id, m.user_id, now()
    else:
        db.add(WorkspaceAdAccount(workspace_id=m.workspace_id, ad_account_id=acc.id, credential_id=cred.id, connected_by=m.user_id))
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=acc.id, action="ACCOUNT_CONNECT"))
    db.commit()
    # 성과 통계 동기화는 별도 요청(POST .../sync). 광고 데이터는 화면이 마스터 보고서로 받는다
    return {"id": acc.id, "customer_id": acc.customer_id, "name": acc.name}


@app.delete("/workspaces/{ws_id}/ad-accounts/{account_id}")
async def disconnect_account(account_id: int, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    link = db.scalar(select(WorkspaceAdAccount).where(WorkspaceAdAccount.workspace_id == m.workspace_id,
                                                      WorkspaceAdAccount.ad_account_id == account_id,
                                                      WorkspaceAdAccount.status == "CONNECTED"))
    if not link:
        raise HTTPException(404, "연결된 계정이 아닙니다")
    link.status = "DISCONNECTED"  # 데이터·이력은 보존, 접근만 차단
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=account_id, action="ACCOUNT_DISCONNECT"))
    db.commit()
    return {"ok": True}


@app.get("/workspaces/{ws_id}/ad-accounts")
async def list_accounts(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, None)
    out = []
    for acc in db.scalars(select(AdAccount).where(AdAccount.id.in_(ids))):
        last = db.scalar(select(SyncRun).where(SyncRun.ad_account_id == acc.id).order_by(SyncRun.id.desc()))
        out.append({"id": acc.id, "customer_id": acc.customer_id, "name": acc.name, "is_mock": acc.is_mock,
                    "last_sync": last and {"status": last.status, "error": last.error, "at": last.finished_at}})
    return out


@app.post("/workspaces/{ws_id}/ad-accounts/{account_id}/sync")
async def sync(account_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    resolve_account_ids(db, m, [account_id])
    link = db.scalar(select(WorkspaceAdAccount).where(WorkspaceAdAccount.workspace_id == m.workspace_id,
                                                      WorkspaceAdAccount.ad_account_id == account_id))
    acc = db.get(AdAccount, account_id)
    try:
        client = client_for(db.get(NaverApiCredential, link.credential_id), acc.customer_id, decrypt)
    except NaverApiError as e:
        raise HTTPException(400, str(e))
    run = sync_account(db, acc, client)
    return {"status": run.status, "error": run.error}


@app.get("/workspaces/{ws_id}/keyword-tool")
async def keyword_tool(account_id: int, hint: str, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """연관 키워드. 네이버 키워드 도구는 띄어쓰기 없는 키워드 최대 5개까지 받는다."""
    resolve_account_ids(db, m, [account_id])
    hints = list(dict.fromkeys(h.replace(" ", "") for h in hint.split(",") if h.strip()))[:5]
    if not hints:
        raise HTTPException(400, "키워드를 입력하세요")
    try:
        rows = bulk._client(db, m.workspace_id, account_id).keyword_tool(hints)
    except NaverApiError as e:
        raise HTTPException(400, f"연관 키워드 조회 실패: {e}")
    return sorted(rows, key=lambda r: -(r["pc"] + r["mobile"]))


@app.get("/workspaces/{ws_id}/seo-fetch")
async def seo_fetch(url: str, m: Membership = Depends(membership)):
    """SEO·GEO 점검용으로 광고주 페이지와 robots.txt 등을 가져온다. 판정은 브라우저가 한다."""
    try:
        return seo.fetch(url)
    except seo.SeoError as e:
        raise HTTPException(400, str(e))


# ---------- 네이버 원본 조회 (브라우저 보관용, DB에 저장하지 않음) ----------
MasterItem = Literal["Adgroup", "Keyword", "Ad", "RsaAd", "ShoppingProduct", "AdExtension"]
ROW_OF = {"adgroups": naver.adgroup_row, "ads": naver.ad_row, "ad-extensions": naver.extension_row}


def _naver(db: Session, m: Membership, account_id: int, fn):
    resolve_account_ids(db, m, [account_id])
    try:
        return fn(bulk._client(db, m.workspace_id, account_id))
    except NaverApiError as e:
        raise HTTPException(400, f"네이버 조회 실패: {e}")


@app.post("/workspaces/{ws_id}/ad-accounts/{account_id}/master-reports")
async def create_master_report(account_id: int, item: MasterItem, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _naver(db, m, account_id, lambda c: c.create_master_report(item))


@app.get("/workspaces/{ws_id}/ad-accounts/{account_id}/master-reports/{job_id}")
async def get_master_report(account_id: int, job_id: str, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _naver(db, m, account_id, lambda c: c.get_master_report(job_id))


def master_file_source(db: Session, authorization: str, ws_id: int, account_id: int, job_id: str) -> dict:
    """{"url", "headers"} 또는 {"text"}(Mock). Workers 진입점(src/main.py)이 직접 불러 JS fetch로 본문을 넘긴다."""
    m = membership_of(db, ws_id, user_from_header(db, authorization))
    return _naver(db, m, account_id, lambda c: c.master_file(c.get_master_report(job_id)))


@app.get("/workspaces/{ws_id}/ad-accounts/{account_id}/master-reports/{job_id}/file")
async def master_report_file(ws_id: int, account_id: int, job_id: str, authorization: str = Header(default=""),
                             db: Session = Depends(get_db)):
    """로컬·테스트용. Workers에서는 src/main.py가 이 경로를 먼저 가로챈다(큰 파일을 파이썬이 다루면 CPU 한도 초과)."""
    src = master_file_source(db, authorization, ws_id, account_id, job_id)
    if "text" not in src:
        r = httpx.get(src["url"], headers=src["headers"], timeout=60)
        if r.status_code >= 400:
            raise HTTPException(400, f"보고서 다운로드 실패: {r.status_code}")
        src["text"] = r.text
    return Response(src["text"], media_type="text/tab-separated-values; charset=utf-8")


@app.get("/workspaces/{ws_id}/ad-accounts/{account_id}/naver/{kind}")
async def naver_objects(account_id: int, kind: Literal["campaigns", "adgroups", "ads", "ad-extensions"], ids: str = "",
                        m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """캠페인은 전체, 나머지는 ids(쉼표)로. 마스터 보고서에 없는 값(운영 상태·소재 문구·확장소재 내용)을 채운다."""
    if kind == "campaigns":
        return [naver.campaign_row(account_id, c) for c in _naver(db, m, account_id, lambda c: c.list_campaigns())
                if c["campaignTp"] in ("WEB_SITE", "SHOPPING")]  # MVP 범위 밖 캠페인 유형은 보여 주지 않는다
    id_list = [i for i in ids.split(",") if i]
    if len(id_list) > 500:
        raise HTTPException(400, "한 번에 500개까지")
    return [ROW_OF[kind](account_id, o) for o in _naver(db, m, account_id, lambda c: c.get_many(kind, id_list))]


ProductType = Literal["WEB_SITE", "SHOPPING"] | None


# ---------- 확장소재 ----------
class SubLinkIn(BaseModel):
    name: str
    final: str


class ExtensionIn(BaseModel):
    ad_account_id: int
    adgroup_naver_id: str
    # 실데이터로 내용 구조를 확인한 유형만: DESCRIPTION(홍보문구) {heading: 구분, description}, HEADLINE(추가제목) {headline},
    # DESCRIPTION_EXTRA(추가설명) {description}, SUB_LINKS [{name, final}]
    ext_type: Literal["DESCRIPTION", "HEADLINE", "DESCRIPTION_EXTRA", "SUB_LINKS"]
    heading: str = ""
    description: str = ""
    links: list[SubLinkIn] = []


PROMO_HEADINGS = ("할인", "사은품", "추가선물증정", "이벤트", "신상품")  # 네이버 화면의 홍보문구 구분
TEXT_LIMITS = {"DESCRIPTION": ("홍보문구", 14), "HEADLINE": ("추가제목", 15), "DESCRIPTION_EXTRA": ("추가설명", 45)}


@app.post("/workspaces/{ws_id}/ad-extensions")
async def create_ad_extension(body: ExtensionIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """화면 보관본에 넣을 행을 돌려준다. 쇼핑 광고그룹 등은 화면이 고르지 못하게 하고, 네이버도 거부한다."""
    if body.ext_type in TEXT_LIMITS:
        label, limit = TEXT_LIMITS[body.ext_type]
        text = (body.heading if body.ext_type == "HEADLINE" else body.description).strip()
        if not text or len(text) > limit:
            raise HTTPException(400, f"{label}는 1~{limit}자로 입력하세요")
        if body.ext_type == "DESCRIPTION" and body.heading not in PROMO_HEADINGS:
            raise HTTPException(400, f"홍보문구 구분은 {', '.join(PROMO_HEADINGS)} 중 하나")
        content = {"DESCRIPTION": {"heading": body.heading, "description": text}, "HEADLINE": {"headline": text},
                   "DESCRIPTION_EXTRA": {"description": text}}[body.ext_type]
    else:
        links = [{"name": x.name.strip(), "final": x.final.strip()} for x in body.links]
        if not links or any(not x["name"] or not x["final"].startswith(("http://", "https://")) for x in links):
            raise HTTPException(400, "서브링크는 이름과 http(s):// 로 시작하는 URL을 입력하세요")
        content = links
    return bulk.create_extension(db, m, body.ad_account_id, body.adgroup_naver_id, body.ext_type, content)


@app.delete("/workspaces/{ws_id}/ad-extensions/{naver_id}")
async def delete_ad_extension(naver_id: str, account_id: int, owner_naver_id: str, ext_type: str | None = None,
                              m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return {"ok": True, "already_gone": bulk.delete_extension(db, m, account_id, naver_id, owner_naver_id, ext_type)}


# ---------- 대량 작업 ----------
class ChangeIn(BaseModel):
    """광고 데이터 사본이 서버에 없어 화면(브라우저 보관본)이 대상의 계정·이전 값·유형을 같이 보낸다."""
    entity_type: str
    naver_id: str
    field: str
    value: str
    ad_account_id: int | None = None
    before: str | None = None
    product: Literal["WEB_SITE", "SHOPPING"] | None = None  # 키워드 등록은 광고그룹 유형
    ad_type: str | None = None
    invalid: str | None = None  # 화면이 찾은 오류(없는 ID, 이미 있는 키워드 등) → 그 행은 실행하지 않음


class BulkIn(BaseModel):
    changes: list[ChangeIn]
    source: Literal["UI", "EXCEL"] = "UI"


def _job(db: Session, m: Membership, job_id: int) -> BulkJob:
    job = db.get(BulkJob, job_id)
    if not job or job.workspace_id != m.workspace_id:
        raise HTTPException(404, "작업을 찾을 수 없습니다")
    return job


def _job_out(db: Session, job: BulkJob):
    rows = db.scalars(select(BulkJobRow).where(BulkJobRow.job_id == job.id).order_by(BulkJobRow.id)).all()
    names = dict(db.execute(select(AdAccount.id, AdAccount.name).where(AdAccount.id.in_({r.ad_account_id for r in rows}))).all())
    by_account: dict = {}
    for r in rows:
        by_account.setdefault(r.ad_account_id, {"ad_account_id": r.ad_account_id, "name": names.get(r.ad_account_id), "rows": []})["rows"].append(
            {"id": r.id, "entity_type": r.entity_type, "naver_id": r.naver_id, "field": r.field, "before": r.before,
             "after": r.after, "status": r.status, "error": r.error})
    counts = {s: sum(r.status == s for r in rows) for s in ("VALID", "INVALID", "SUCCESS", "FAILED")}
    return {"id": job.id, "status": job.status, "source": job.source, "parent_job_id": job.parent_job_id,
            "created_by": job.created_by, "created_at": job.created_at, "executed_at": job.executed_at,
            "counts": counts, "accounts": list(by_account.values())}


@app.post("/workspaces/{ws_id}/bulk-jobs")
async def create_bulk_job(body: BulkIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _job_out(db, bulk.create_job(db, m, [c.model_dump() for c in body.changes], body.source))


@app.post("/workspaces/{ws_id}/bulk-jobs/excel/parse")
async def parse_bulk_excel(file: UploadFile, m: Membership = Depends(membership)):
    """엑셀 → 변경 목록. 화면이 보관본으로 계정·이전 값을 채워 POST /bulk-jobs(source=EXCEL)로 미리보기를 만든다."""
    return bulk.parse_excel(await file.read())


@app.get("/bulk-jobs/excel-template")
async def excel_template():
    return Response(bulk.excel_template(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=bulk_template.xlsx"})


@app.get("/workspaces/{ws_id}/bulk-jobs")
async def list_bulk_jobs(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    jobs = db.scalars(select(BulkJob).where(BulkJob.workspace_id == m.workspace_id).order_by(BulkJob.id.desc()).limit(50))
    return _rows(jobs, "id", "status", "source", "parent_job_id", "created_by", "created_at", "executed_at")


@app.get("/workspaces/{ws_id}/bulk-jobs/{job_id}")
async def get_bulk_job(job_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _job_out(db, _job(db, m, job_id))


@app.post("/workspaces/{ws_id}/bulk-jobs/{job_id}/execute")
async def execute_bulk_job(job_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """최대 EXECUTE_CHUNK행씩 실행. 응답 status가 RUNNING이면 화면이 다시 호출한다."""
    return _job_out(db, bulk.execute_job(db, m, _job(db, m, job_id), bulk.EXECUTE_CHUNK))


@app.post("/workspaces/{ws_id}/bulk-jobs/{job_id}/retry-failed")
async def retry_bulk_job(job_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _job_out(db, bulk.retry_failed(db, m, _job(db, m, job_id)))


# ---------- 자동입찰 (목표 순위) ----------
AUTO_BID_LIMIT = 20


class KeywordRef(BaseModel):
    ad_account_id: int
    naver_id: str
    keyword: str = ""


class AutoBidIn(BaseModel):
    keywords: list[KeywordRef]
    device: Literal["PC", "MOBILE"]
    target_rank: int
    max_bid: int
    enabled: bool = True


class AutoBidKeysIn(BaseModel):
    keywords: list[KeywordRef]


def _editable(db: Session, m: Membership, refs: list[KeywordRef]) -> list[KeywordRef]:
    allowed = resolve_account_ids(db, m, None, edit=True)
    if not refs or any(k.ad_account_id not in allowed for k in refs):
        raise HTTPException(403, "키워드가 없거나 수정 권한이 없습니다")
    return refs


def _rule(db: Session, m: Membership, naver_id: str) -> AutoBidRule | None:
    return db.scalar(select(AutoBidRule).where(AutoBidRule.workspace_id == m.workspace_id, AutoBidRule.keyword_naver_id == naver_id))


@app.get("/workspaces/{ws_id}/auto-bids")
async def list_auto_bids(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, None)
    q = select(AutoBidRule).where(AutoBidRule.workspace_id == m.workspace_id, AutoBidRule.ad_account_id.in_(ids)).order_by(AutoBidRule.id)
    return _rows(db.scalars(q), "id", "ad_account_id", "keyword_naver_id", "keyword", "device", "target_rank", "max_bid", "enabled",
                 "last_run_at", "last_result")


@app.put("/workspaces/{ws_id}/auto-bids")
async def set_auto_bids(body: AutoBidIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """선택한 키워드에 같은 규칙을 만들거나 덮어쓴다. 실행은 마지막으로 저장한 사람의 권한으로 한다."""
    hi_rank = 10 if body.device == "PC" else 5
    if not 1 <= body.target_rank <= hi_rank:
        raise HTTPException(400, f"{body.device} 목표 순위는 1~{hi_rank}위")
    lo, hi = bulk.BID_RANGE["WEB_SITE"]
    if not lo <= body.max_bid <= hi or body.max_bid % 10:
        raise HTTPException(400, f"최대 입찰가는 {lo:,}~{hi:,}원, 10원 단위")
    kws = _editable(db, m, body.keywords)
    on = set(db.scalars(select(AutoBidRule.keyword_naver_id).where(AutoBidRule.workspace_id == m.workspace_id,
                                                                   AutoBidRule.enabled.is_(True))))
    # 무료 플랜은 크론 1회당 외부 호출 수 한도가 있어 키워드가 많으면 실행이 끊긴다
    if body.enabled and len(on | {k.naver_id for k in kws}) > AUTO_BID_LIMIT:
        raise HTTPException(400, f"자동입찰은 조직당 {AUTO_BID_LIMIT}개까지입니다 (지금 {len(on)}개 사용 중)")
    for k in kws:
        r = _rule(db, m, k.naver_id)
        if r is None:
            r = AutoBidRule(workspace_id=m.workspace_id, keyword_naver_id=k.naver_id)
            db.add(r)
        r.ad_account_id, r.keyword = k.ad_account_id, k.keyword[:100]
        r.device, r.target_rank, r.max_bid, r.enabled, r.created_by = (body.device, body.target_rank, body.max_bid,
                                                                       body.enabled, m.user_id)
        db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=k.ad_account_id, action="AUTO_BID_SET",
                        entity_type="keyword", naver_id=k.naver_id, field="auto_bid",
                        after=f"{body.device} {body.target_rank}위 최대 {body.max_bid}" + ("" if body.enabled else " 중지")))
    db.commit()
    return {"ok": True}


@app.post("/workspaces/{ws_id}/auto-bids/delete")
async def delete_auto_bids(body: AutoBidKeysIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    for k in _editable(db, m, body.keywords):
        r = _rule(db, m, k.naver_id)
        if r:
            db.delete(r)
            db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=k.ad_account_id,
                            action="AUTO_BID_DELETE", entity_type="keyword", naver_id=k.naver_id, field="auto_bid"))
    db.commit()
    return {"ok": True}


RANK_LIMIT = 10  # 검색 화면을 키워드마다 PC·모바일 2번 읽으므로 무료 플랜 요청당 외부 호출 한도 안에서


@app.post("/workspaces/{ws_id}/ranks")
async def keyword_ranks(body: AutoBidKeysIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """지금 순위 확인. 보기 권한이면 된다."""
    if not 1 <= len(body.keywords) <= RANK_LIMIT:
        raise HTTPException(400, f"순위 확인은 한 번에 1~{RANK_LIMIT}개입니다")
    allowed = resolve_account_ids(db, m, None)
    if any(k.ad_account_id not in allowed for k in body.keywords):
        raise HTTPException(403, "이 광고 계정을 볼 권한이 없습니다")
    return bulk.check_ranks(db, m.workspace_id, body.keywords)


@app.post("/workspaces/{ws_id}/auto-bids/run")
async def run_auto_bids(body: AutoBidKeysIn | None = None, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """지금 실행. keywords를 주면 그 키워드 규칙만."""
    rule_ids = None
    if body and body.keywords:
        nids = [k.naver_id for k in _editable(db, m, body.keywords)]
        rule_ids = list(db.scalars(select(AutoBidRule.id).where(AutoBidRule.workspace_id == m.workspace_id,
                                                                AutoBidRule.keyword_naver_id.in_(nids))))
    jobs = bulk.run_auto_bids(db, m.workspace_id, rule_ids)
    return {"job_ids": [j.id for j in jobs]}


# ---------- 이력·성과·대시보드 ----------
@app.get("/workspaces/{ws_id}/audit-logs")
async def audit_logs(user_id: int | None = None, account_id: int | None = None, m: Membership = Depends(membership),
               db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, [account_id] if account_id else None)
    s = select(AuditLog).where(AuditLog.workspace_id == m.workspace_id, AuditLog.ad_account_id.in_(ids))
    if user_id:
        s = s.where(AuditLog.user_id == user_id)
    return _rows(db.scalars(s.order_by(AuditLog.id.desc()).limit(500)), "id", "user_id", "ad_account_id", "job_id", "action",
                 "entity_type", "naver_id", "field", "before", "after", "created_at")


def _account_performance(db: Session, ids: set[int], since: date, until: date):
    q = (select(PerformanceDaily.ad_account_id, PerformanceDaily.campaign_tp, func.sum(PerformanceDaily.impressions),
                func.sum(PerformanceDaily.clicks), func.sum(PerformanceDaily.cost), func.sum(PerformanceDaily.conversions),
                func.sum(PerformanceDaily.revenue))
         .where(PerformanceDaily.ad_account_id.in_(ids), PerformanceDaily.date.between(since, until))
         .group_by(PerformanceDaily.ad_account_id, PerformanceDaily.campaign_tp))
    names = dict(db.execute(select(AdAccount.id, AdAccount.name).where(AdAccount.id.in_(ids))).all())
    out = {i: {"ad_account_id": i, "name": names[i], "WEB_SITE": None, "SHOPPING": None} for i in ids}
    for acc, tp, imp, clk, cost, conv, rev in db.execute(q):
        out[acc][tp] = {"impressions": imp, "clicks": clk, "cost": cost, "conversions": conv, "revenue": rev,
                        "ctr": round(clk / imp * 100, 2) if imp else None, "cpc": round(cost / clk) if clk else None,
                        # 매출 미제공(NULL)이면 ROAS도 NULL — 0과 구분
                        "roas": round(rev / cost * 100, 1) if rev is not None and cost else None}
    return list(out.values())


@app.get("/workspaces/{ws_id}/performance/accounts")
async def performance_accounts(since: date | None = None, until: date | None = None, account_ids: str | None = None,
                         m: Membership = Depends(membership), db: Session = Depends(get_db)):
    until = until or date.today() - timedelta(days=1)
    since = since or until - timedelta(days=6)
    return _account_performance(db, resolve_account_ids(db, m, _ids(account_ids)), since, until)


@app.get("/workspaces/{ws_id}/performance/daily")
async def performance_daily(since: date, until: date, account_ids: str | None = None, product: ProductType = None,
                            m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """일별 합계. 동기화된 행이 없는 날은 0 (전환·매출은 미제공 NULL 유지)."""
    if since > until or (until - since).days > 92:
        raise HTTPException(400, "기간은 93일 이내")
    ids = resolve_account_ids(db, m, _ids(account_ids))
    q = (select(PerformanceDaily.date, func.sum(PerformanceDaily.impressions), func.sum(PerformanceDaily.clicks),
                func.sum(PerformanceDaily.cost), func.sum(PerformanceDaily.conversions), func.sum(PerformanceDaily.revenue))
         .where(PerformanceDaily.ad_account_id.in_(ids), PerformanceDaily.date.between(since, until))
         .group_by(PerformanceDaily.date))
    if product:
        q = q.where(PerformanceDaily.campaign_tp == product)
    # D1은 날짜를 문자열로 돌려줄 수 있어 문자열 키로 맞춘다
    by_day = {str(d)[:10]: (imp, clk, cost, conv, rev) for d, imp, clk, cost, conv, rev in db.execute(q)}
    out, d = [], since
    while d <= until:
        imp, clk, cost, conv, rev = by_day.get(d.isoformat(), (0, 0, 0, None, None))
        out.append({"date": d.isoformat(), "impressions": imp, "clicks": clk, "cost": cost, "conversions": conv, "revenue": rev})
        d += timedelta(days=1)
    return out


@app.get("/workspaces/{ws_id}/dashboard")
async def dashboard(account_ids: str | None = None, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, None)
    selected = resolve_account_ids(db, m, _ids(account_ids))
    until = date.today() - timedelta(days=1)
    jobs = db.scalars(select(BulkJob).where(BulkJob.workspace_id == m.workspace_id, BulkJob.status != "PREVIEW")
                      .order_by(BulkJob.id.desc()).limit(10)).all()
    failed_syncs = []
    for i in ids:
        last = db.scalar(select(SyncRun).where(SyncRun.ad_account_id == i).order_by(SyncRun.id.desc()))
        if last and last.status == "FAILED":
            failed_syncs.append({"ad_account_id": i, "error": last.error, "at": last.finished_at})
    return {
        "connected_accounts": len(ids),
        "accounts": _account_performance(db, ids, until - timedelta(days=6), until),
        "recent_jobs": [_job_out(db, j) | {"accounts": None} for j in jobs],
        "failed_jobs": [j.id for j in jobs if j.status in ("PARTIAL", "FAILED")],
        "sync_errors": failed_syncs,
        "auto_bids": db.scalar(select(func.count()).select_from(AutoBidRule).where(
            AutoBidRule.workspace_id == m.workspace_id, AutoBidRule.ad_account_id.in_(selected), AutoBidRule.enabled.is_(True))),
    }


# ---------- 구독 (광고 관리와 분리) ----------
@app.get("/workspaces/{ws_id}/subscription")
async def subscription(m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscription).where(Subscription.workspace_id == m.workspace_id))
    plan = db.get(Plan, sub.plan_code)
    billable = db.scalar(select(func.count()).select_from(WorkspaceAdAccount).where(
        WorkspaceAdAccount.workspace_id == m.workspace_id, WorkspaceAdAccount.status == "CONNECTED"))
    return {"plan": plan.name, "status": sub.status, "trial_ends_at": sub.trial_ends_at, "billable_accounts": billable,
            "price_per_account": plan.price_per_account, "monthly_total": billable * plan.price_per_account}
