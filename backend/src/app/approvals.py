"""웹 승인(사용자 결정 2026-11-02): 계정 하루예산 설정액 합계를 늘릴 수 있는 변경(캠페인 하루예산 증액, 캠페인·광고그룹 켜기,
ADVoost 켜기)은 웹에 로그인한 사람이 이 화면에서 승인해야만 서버가 실행한다.

- Claude(MCP)는 승인 요청만 만든다. 승인 엔드포인트는 웹 로그인으로만 부를 수 있다(access.user_from_header가 Claude 토큰을 거부, 쿠키는 CSRF 검사).
- 승인은 조직·광고 계정·요청자·정확한 내용(payload_hash)·만료 시각에 묶인다. PENDING → RUNNING(또는 예약 작업은 APPROVED)을
  UPDATE 한 문장으로 바꿔 한 번만 쓰인다.
- 실행 직전에 권한·네이버 지금 값(승인 때 변경 전 값)·안전장치를 다시 확인한다(bulk.execute_job, place._execute).
그 밖의 변경(입찰가·키워드/소재 켜기·등록·삭제·자동입찰)은 Claude 허용 버튼과 서버 안전장치로 처리한다."""
import json
import os
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from . import bulk, main as api, place, safety
from .access import ADMIN_ROLES, accessible_account_ids, membership
from .db import get_db
from .models import AdAccount, ApprovalRequest, AuditLog, BulkJob, BulkJobRow, Membership, now

router = APIRouter()
APPROVAL_TTL = timedelta(minutes=30)  # 승인 대기 시간(웹을 열어 볼 여유). 예약 작업은 예약 시각까지
WEB_URL = os.getenv("WEB_URL", "https://naverads.djkim0509.workers.dev")
SUMMARY_ROWS = 100
LABEL = {"status": "상태", "daily_budget": "하루예산", "bid_amt": "입찰가", "create": "등록", "delete": "삭제"}


def url(ar: ApprovalRequest) -> str:
    return f"{WEB_URL}/approvals?id={ar.id}"


def _aware(t):
    return place._aware(t)


def out(ar: ApprovalRequest) -> dict:
    """웹·Claude에 보여 줄 승인 요청. status로 대기·승인·거절·만료·실행 결과를 구분한다."""
    return {"approval_id": ar.id, "kind": ar.kind, "status": ar.status, "web_required": ar.web_required, "job_id": ar.job_id,
            "ad_account_id": ar.ad_account_id, "requested_by": ar.requested_by, "decided_by": ar.decided_by,
            "created_at": ar.created_at, "expires_at": ar.expires_at, "decided_at": ar.decided_at,
            "summary": json.loads(ar.summary) if ar.summary else None, "result": json.loads(ar.result) if ar.result else None,
            "approve_url": url(ar)}


def _audit(db, m, ar: ApprovalRequest, action: str, after: str | None = None):
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=ar.ad_account_id, job_id=ar.job_id, action=action,
                    entity_type="approval", naver_id=str(ar.id), field=ar.kind, after=after and after[:50]))


def _job_summary(db: Session, m: Membership, job: BulkJob, rows: list[BulkJobRow]) -> dict:
    names = dict(db.execute(select(AdAccount.id, AdAccount.name).where(AdAccount.id.in_({r.ad_account_id for r in rows}))).all())
    return {"title": f"대량 작업 #{job.id} 실행" + (f" (예약 {job.scheduled_at:%Y-%m-%d %H:%M} UTC)" if job.scheduled_at else ""),
            "why": "계정의 하루예산 설정액 합계가 늘 수 있는 변경(캠페인 하루예산 올리기·캠페인/광고그룹 켜기)이 있어 웹 승인이 필요해요",
            "rows": [{"account": names.get(r.ad_account_id), "ad_account_id": r.ad_account_id, "entity_type": r.entity_type,
                      "naver_id": r.naver_id, "what": LABEL.get(r.field, r.field), "before": r.before, "after": r.after} for r in rows[:SUMMARY_ROWS]],
            "more_rows": max(0, len(rows) - SUMMARY_ROWS),
            "safety": api._job_safety(db, m, job), "note": safety.OVERSPEND_NOTE}


def request_for_job(db: Session, m: Membership, job: BulkJob) -> ApprovalRequest:
    """이 작업의 승인 요청(대기 중인 것이 있으면 그것, 없으면 새로). 실행할 행이 그대로인지 해시로 묶는다."""
    rows = db.scalars(select(BulkJobRow).where(BulkJobRow.job_id == job.id, BulkJobRow.status == "VALID").order_by(BulkJobRow.id)).all()
    h = bulk.job_hash(rows)
    for ar in db.scalars(select(ApprovalRequest).where(ApprovalRequest.job_id == job.id, ApprovalRequest.status == "PENDING")):
        if _aware(ar.expires_at) >= now() and ar.payload_hash == h:
            return ar
        ar.status = "EXPIRED"
        _audit(db, m, ar, "APPROVAL_EXPIRED")
    accs = {r.ad_account_id for r in rows}
    expires = (job.scheduled_at and _aware(job.scheduled_at)) or now() + APPROVAL_TTL
    ar = ApprovalRequest(workspace_id=m.workspace_id, requested_by=m.user_id, tool="bulk_job", kind="job", job_id=job.id,
                         ad_account_id=next(iter(accs)) if len(accs) == 1 else None, web_required=True,
                         payload=json.dumps({"job_id": job.id}), payload_hash=h, status="PENDING", expires_at=expires,
                         summary=json.dumps(_job_summary(db, m, job, rows), ensure_ascii=False, default=str))
    db.add(ar)
    db.flush()
    _audit(db, m, ar, "APPROVAL_PENDING")
    db.commit()
    return ar


def pending_reply(ar: ApprovalRequest) -> dict:
    return {**out(ar), "message": f"사장님이 웹에서 직접 승인해야 실행돼요. 승인 화면: {url(ar)} (Claude는 승인할 수 없어요). "
                                  "승인 전에는 네이버에 아무것도 바뀌지 않아요."}


def _get(db: Session, m: Membership, approval_id: int) -> ApprovalRequest:
    ar = db.get(ApprovalRequest, approval_id)
    if ar is None or ar.workspace_id != m.workspace_id or not _visible(db, m, ar):
        raise HTTPException(404, "승인 요청을 찾을 수 없어요")
    return ar


def _accounts(db: Session, ar: ApprovalRequest) -> set[int]:
    if ar.kind == "job":
        return set(db.scalars(select(BulkJobRow.ad_account_id).where(BulkJobRow.job_id == ar.job_id, BulkJobRow.ad_account_id.is_not(None))))
    return {json.loads(ar.payload)["ad_account_id"]}


def _visible(db: Session, m: Membership, ar: ApprovalRequest) -> bool:
    return m.role in ADMIN_ROLES or ar.requested_by == m.user_id or _accounts(db, ar) <= accessible_account_ids(db, m)


def _expire_if_due(db: Session, m: Membership, ar: ApprovalRequest) -> bool:
    if ar.status == "PENDING" and _aware(ar.expires_at) < now():
        ar.status = "EXPIRED"
        _audit(db, m, ar, "APPROVAL_EXPIRED")
        db.commit()
    return ar.status == "EXPIRED"


def approve(db: Session, m: Membership, approval_id: int) -> dict:
    """웹에서 승인하고 바로 실행한다(예약 작업은 승인만 하고 크론이 예약 시각에 실행). 요청한 본인이나 관리자이면서
    대상 광고 계정을 모두 수정할 수 있어야 한다."""
    ar = _get(db, m, approval_id)
    if not ar.web_required:
        raise HTTPException(400, "웹 승인 대상이 아닌 요청이에요")
    if ar.requested_by != m.user_id and m.role not in ADMIN_ROLES:
        raise HTTPException(403, "요청한 본인이나 관리자만 승인할 수 있어요")
    if not _accounts(db, ar) <= accessible_account_ids(db, m, edit=True):
        raise HTTPException(403, "이 광고 계정을 수정할 권한이 없어 승인할 수 없어요")
    if _expire_if_due(db, m, ar):
        raise HTTPException(410, "승인 시간이 지났어요. Claude나 화면에서 다시 요청해 주세요")
    if ar.status != "PENDING":
        raise HTTPException(409, "이미 승인·거절했거나 실행한 요청이에요")
    if ar.kind == "job":
        job = db.get(BulkJob, ar.job_id)
        rows = db.scalars(select(BulkJobRow).where(BulkJobRow.job_id == job.id, BulkJobRow.status == "VALID").order_by(BulkJobRow.id)).all()
        if job.status != "PREVIEW" or bulk.job_hash(rows) != ar.payload_hash:
            raise HTTPException(409, "승인 요청 뒤 작업 내용이 바뀌었어요. 다시 요청해 주세요")
    # 한 번만: PENDING에서 바꾼 요청만 지나간다. 작업은 APPROVED(실행이 RUNNING으로 바꿈), 플레이스는 바로 RUNNING
    if db.execute(update(ApprovalRequest).where(ApprovalRequest.id == ar.id, ApprovalRequest.status == "PENDING")
                  .values(status="RUNNING" if ar.kind == "place" else "APPROVED", decided_by=m.user_id, decided_at=now())).rowcount != 1:
        db.rollback()
        raise HTTPException(409, "이미 승인·거절했거나 실행한 요청이에요")
    _audit(db, m, ar, "APPROVAL_APPROVED")
    db.commit()
    db.refresh(ar)
    if ar.kind == "place":
        res = place._execute(db, m, ar, place.PlaceChange(**json.loads(ar.payload)))
        db.refresh(ar)
        return {**out(ar), "place": res}
    if job.scheduled_at:
        return {**out(ar), "message": "승인했어요. 예약 시각에 실행 직전 값을 다시 확인하고 실행해요"}
    try:
        job = bulk.execute_job(db, m, job, bulk.EXECUTE_CHUNK)
    except HTTPException as e:
        ar.status, ar.result = "FAILED", json.dumps({"error": e.detail}, ensure_ascii=False)
        _audit(db, m, ar, "APPROVAL_FAILED", str(e.detail))
        db.commit()
        raise
    db.refresh(ar)
    return {**out(ar), "job": api._job_out(db, job)}


def reject(db: Session, m: Membership, approval_id: int) -> dict:
    ar = _get(db, m, approval_id)
    if ar.requested_by != m.user_id and m.role not in ADMIN_ROLES:
        raise HTTPException(403, "요청한 본인이나 관리자만 거절할 수 있어요")
    if db.execute(update(ApprovalRequest).where(ApprovalRequest.id == ar.id, ApprovalRequest.status.in_(("PENDING", "APPROVED")))
                  .values(status="REJECTED", decided_by=m.user_id, decided_at=now())).rowcount != 1:
        raise HTTPException(409, "이미 실행했거나 끝난 요청이에요")
    if ar.kind == "job":  # 예약 작업이면 예약도 풀어 크론이 실행하지 않게
        job = db.get(BulkJob, ar.job_id)
        if job.status == "PREVIEW":
            job.scheduled_at = None
    _audit(db, m, ar, "APPROVAL_REJECTED")
    db.commit()
    db.refresh(ar)
    return out(ar)


@router.get("/workspaces/{ws_id}/approvals")
async def list_approvals(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """웹 승인 화면: 대기 중인 요청과 최근 결과(볼 수 있는 계정만)."""
    q = (select(ApprovalRequest).where(ApprovalRequest.workspace_id == m.workspace_id,
                                       or_(ApprovalRequest.web_required.is_(True), ApprovalRequest.requested_by == m.user_id))
         .order_by(ApprovalRequest.id.desc()).limit(50))
    items = [ar for ar in db.scalars(q) if _visible(db, m, ar)]
    for ar in items:
        if ar.status == "PENDING" and _aware(ar.expires_at) < now():
            ar.status = "EXPIRED"
    db.commit()
    return [out(ar) for ar in items]


@router.get("/workspaces/{ws_id}/approvals/{approval_id}")
async def get_approval(approval_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ar = _get(db, m, approval_id)
    _expire_if_due(db, m, ar)
    return out(ar)


@router.post("/workspaces/{ws_id}/approvals/{approval_id}/approve")
async def post_approve(approval_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return approve(db, m, approval_id)


@router.post("/workspaces/{ws_id}/approvals/{approval_id}/reject")
async def post_reject(approval_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return reject(db, m, approval_id)
