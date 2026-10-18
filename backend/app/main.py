from datetime import date, timedelta
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import bulk
from .access import admin_membership, current_user, membership, resolve_account_ids
from .db import Base, engine, get_db
from .models import (AccountAccess, Ad, AdAccount, AdGroup, AuditLog, BulkJob, BulkJobRow, Campaign, Keyword, Membership,
                     NaverApiCredential, PerformanceDaily, Plan, Subscription, SyncRun, User, Workspace, WorkspaceAdAccount,
                     now)
from .naver import NaverApiError, client_for
from .security import decrypt, encrypt, hash_password, make_token, verify_password
from .sync import sync_account

app = FastAPI(title="네이버 광고 통합 관리 API")
# shortcut: create_all로 스키마 생성, 스키마 안정화 후 Alembic 마이그레이션으로 교체
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
def signup(body: SignupIn, db: Session = Depends(get_db)):
    if len(body.password) < 8:
        raise HTTPException(400, "비밀번호는 8자 이상")
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "이미 가입된 이메일입니다")
    user = User(email=body.email, password_hash=hash_password(body.password), name=body.name)
    db.add(user)
    db.commit()
    return {"id": user.id, "token": make_token(user.id)}


class LoginIn(BaseModel):
    email: EmailStr
    password: str


@app.post("/auth/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다")
    return {"id": user.id, "token": make_token(user.id)}


# ---------- 조직·직원·권한 ----------
class WorkspaceIn(BaseModel):
    name: str
    type: Literal["AGENCY", "DIRECT_ADVERTISER"] = "AGENCY"


@app.post("/workspaces")
def create_workspace(body: WorkspaceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
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
def my_workspaces(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Workspace, Membership.role).join(Membership, Membership.workspace_id == Workspace.id).where(Membership.user_id == user.id)
    return [{"id": w.id, "name": w.name, "type": w.type, "role": r} for w, r in db.execute(q)]


class MemberIn(BaseModel):
    email: EmailStr
    role: Literal["ADMIN", "MEMBER"] = "MEMBER"


@app.get("/workspaces/{ws_id}/members")
def list_members(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    q = select(Membership, User).join(User, User.id == Membership.user_id).where(Membership.workspace_id == m.workspace_id)
    out = []
    for mem, u in db.execute(q):
        access = db.scalars(select(AccountAccess).where(AccountAccess.membership_id == mem.id)).all()
        out.append({"membership_id": mem.id, "user_id": u.id, "email": u.email, "name": u.name, "role": mem.role,
                    "access": [{"ad_account_id": a.ad_account_id, "level": a.level} for a in access]})
    return out


@app.post("/workspaces/{ws_id}/members")
def add_member(body: MemberIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
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
def set_access(membership_id: int, body: AccessIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
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
def add_credential(body: CredentialIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    cred = NaverApiCredential(workspace_id=m.workspace_id, label=body.label, api_key=body.api_key,
                              secret_key_enc=encrypt(body.secret_key), is_mock=body.is_mock)
    db.add(cred)
    db.commit()
    return {"id": cred.id, "label": cred.label, "is_mock": cred.is_mock}  # 비밀키는 반환하지 않는다


class ConnectIn(BaseModel):
    credential_id: int
    customer_id: str
    name: str


@app.post("/workspaces/{ws_id}/ad-accounts")
def connect_account(body: ConnectIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
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
    run = sync_account(db, acc, client)
    return {"id": acc.id, "customer_id": acc.customer_id, "name": acc.name, "sync_status": run.status, "sync_error": run.error}


@app.delete("/workspaces/{ws_id}/ad-accounts/{account_id}")
def disconnect_account(account_id: int, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
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
def list_accounts(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, None)
    out = []
    for acc in db.scalars(select(AdAccount).where(AdAccount.id.in_(ids))):
        last = db.scalar(select(SyncRun).where(SyncRun.ad_account_id == acc.id).order_by(SyncRun.id.desc()))
        out.append({"id": acc.id, "customer_id": acc.customer_id, "name": acc.name, "is_mock": acc.is_mock,
                    "last_sync": last and {"status": last.status, "error": last.error, "at": last.finished_at}})
    return out


@app.post("/workspaces/{ws_id}/ad-accounts/{account_id}/sync")
def sync(account_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
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


# ---------- 다계정 통합 조회 ----------
ProductType = Literal["WEB_SITE", "SHOPPING"] | None


@app.get("/workspaces/{ws_id}/campaigns")
def list_campaigns(account_ids: str | None = None, product: ProductType = None, q: str | None = None,
                   m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, _ids(account_ids))
    s = select(Campaign).where(Campaign.ad_account_id.in_(ids))
    if product:
        s = s.where(Campaign.campaign_tp == product)
    if q:
        s = s.where(Campaign.name.contains(q))
    return _rows(db.scalars(s.order_by(Campaign.ad_account_id, Campaign.id)),
                 "id", "ad_account_id", "naver_id", "name", "campaign_tp", "status", "daily_budget")


@app.get("/workspaces/{ws_id}/adgroups")
def list_adgroups(account_ids: str | None = None, product: ProductType = None, campaign_id: int | None = None,
                  q: str | None = None, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, _ids(account_ids))
    s = select(AdGroup).where(AdGroup.ad_account_id.in_(ids))
    if product:
        s = s.where(AdGroup.adgroup_type == product)
    if campaign_id:
        s = s.where(AdGroup.campaign_id == campaign_id)
    if q:
        s = s.where(AdGroup.name.contains(q))
    return _rows(db.scalars(s.order_by(AdGroup.ad_account_id, AdGroup.id)),
                 "id", "ad_account_id", "campaign_id", "naver_id", "name", "adgroup_type", "status", "bid_amt")


@app.get("/workspaces/{ws_id}/keywords")
def list_keywords(account_ids: str | None = None, adgroup_id: int | None = None, q: str | None = None,
                  m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, _ids(account_ids))
    s = select(Keyword).where(Keyword.ad_account_id.in_(ids))
    if adgroup_id:
        s = s.where(Keyword.adgroup_id == adgroup_id)
    if q:
        s = s.where(Keyword.keyword.contains(q))
    return _rows(db.scalars(s.order_by(Keyword.ad_account_id, Keyword.id)),
                 "id", "ad_account_id", "adgroup_id", "naver_id", "keyword", "status", "bid_amt", "use_group_bid")


@app.get("/workspaces/{ws_id}/ads")
def list_ads(ad_type: Literal["TEXT_45", "SHOPPING_PRODUCT_AD"], account_ids: str | None = None, adgroup_id: int | None = None,
             m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, _ids(account_ids))
    s = select(Ad).where(Ad.ad_account_id.in_(ids), Ad.ad_type == ad_type)
    if adgroup_id:
        s = s.where(Ad.adgroup_id == adgroup_id)
    return _rows(db.scalars(s.order_by(Ad.ad_account_id, Ad.id)), "id", "ad_account_id", "adgroup_id", "naver_id", "ad_type",
                 "status", "inspect_status", "bid_amt", "use_group_bid", "payload")


# ---------- 대량 작업 ----------
class ChangeIn(BaseModel):
    entity_type: str
    naver_id: str
    field: str
    value: str


class BulkIn(BaseModel):
    changes: list[ChangeIn]


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
def create_bulk_job(body: BulkIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _job_out(db, bulk.create_job(db, m, [c.model_dump() for c in body.changes], "UI"))


@app.post("/workspaces/{ws_id}/bulk-jobs/excel")
async def create_bulk_job_excel(file: UploadFile, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _job_out(db, bulk.create_job(db, m, bulk.parse_excel(await file.read()), "EXCEL"))


@app.get("/bulk-jobs/excel-template")
def excel_template():
    return Response(bulk.excel_template(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=bulk_template.xlsx"})


@app.get("/workspaces/{ws_id}/bulk-jobs")
def list_bulk_jobs(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    jobs = db.scalars(select(BulkJob).where(BulkJob.workspace_id == m.workspace_id).order_by(BulkJob.id.desc()).limit(50))
    return _rows(jobs, "id", "status", "source", "parent_job_id", "created_by", "created_at", "executed_at")


@app.get("/workspaces/{ws_id}/bulk-jobs/{job_id}")
def get_bulk_job(job_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _job_out(db, _job(db, m, job_id))


@app.post("/workspaces/{ws_id}/bulk-jobs/{job_id}/execute")
def execute_bulk_job(job_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _job_out(db, bulk.execute_job(db, m, _job(db, m, job_id)))


@app.post("/workspaces/{ws_id}/bulk-jobs/{job_id}/retry-failed")
def retry_bulk_job(job_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _job_out(db, bulk.retry_failed(db, m, _job(db, m, job_id)))


# ---------- 이력·성과·대시보드 ----------
@app.get("/workspaces/{ws_id}/audit-logs")
def audit_logs(user_id: int | None = None, account_id: int | None = None, m: Membership = Depends(membership),
               db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, [account_id] if account_id else None)
    s = select(AuditLog).where(AuditLog.workspace_id == m.workspace_id, AuditLog.ad_account_id.in_(ids))
    if user_id:
        s = s.where(AuditLog.user_id == user_id)
    return _rows(db.scalars(s.order_by(AuditLog.id.desc()).limit(500)), "id", "user_id", "ad_account_id", "job_id", "action",
                 "entity_type", "naver_id", "field", "before", "after", "created_at")


def _account_performance(db: Session, ids: set[int], since: date, until: date):
    q = (select(PerformanceDaily.ad_account_id, Campaign.campaign_tp, func.sum(PerformanceDaily.impressions),
                func.sum(PerformanceDaily.clicks), func.sum(PerformanceDaily.cost), func.sum(PerformanceDaily.conversions),
                func.sum(PerformanceDaily.revenue))
         .join(Campaign, Campaign.id == PerformanceDaily.campaign_id)
         .where(PerformanceDaily.ad_account_id.in_(ids), PerformanceDaily.date.between(since, until))
         .group_by(PerformanceDaily.ad_account_id, Campaign.campaign_tp))
    names = dict(db.execute(select(AdAccount.id, AdAccount.name).where(AdAccount.id.in_(ids))).all())
    out = {i: {"ad_account_id": i, "name": names[i], "WEB_SITE": None, "SHOPPING": None} for i in ids}
    for acc, tp, imp, clk, cost, conv, rev in db.execute(q):
        out[acc][tp] = {"impressions": imp, "clicks": clk, "cost": cost, "conversions": conv, "revenue": rev,
                        "ctr": round(clk / imp * 100, 2) if imp else None, "cpc": round(cost / clk) if clk else None,
                        # 매출 미제공(NULL)이면 ROAS도 NULL — 0과 구분
                        "roas": round(rev / cost * 100, 1) if rev is not None and cost else None}
    return list(out.values())


@app.get("/workspaces/{ws_id}/performance/accounts")
def performance_accounts(since: date | None = None, until: date | None = None, account_ids: str | None = None,
                         m: Membership = Depends(membership), db: Session = Depends(get_db)):
    until = until or date.today() - timedelta(days=1)
    since = since or until - timedelta(days=6)
    return _account_performance(db, resolve_account_ids(db, m, _ids(account_ids)), since, until)


@app.get("/workspaces/{ws_id}/dashboard")
def dashboard(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, None)
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
    }


# ---------- 구독 (광고 관리와 분리) ----------
@app.get("/workspaces/{ws_id}/subscription")
def subscription(m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscription).where(Subscription.workspace_id == m.workspace_id))
    plan = db.get(Plan, sub.plan_code)
    billable = db.scalar(select(func.count()).select_from(WorkspaceAdAccount).where(
        WorkspaceAdAccount.workspace_id == m.workspace_id, WorkspaceAdAccount.status == "CONNECTED"))
    return {"plan": plan.name, "status": sub.status, "trial_ends_at": sub.trial_ends_at, "billable_accounts": billable,
            "price_per_account": plan.price_per_account, "monthly_total": billable * plan.price_per_account}
