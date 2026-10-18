"""대량 작업 엔진: 미리보기(검증) → 실행(권한 재검증) → 행별 결과 + 감사 로그.
모든 광고 데이터 쓰기는 이 경로만 사용한다."""
import io

from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from .access import accessible_account_ids
from .models import (Ad, AdAccount, AdExtension, AdGroup, AuditLog, BulkJob, BulkJobRow, Campaign, Keyword, Membership,
                     NaverApiCredential, WorkspaceAdAccount, now)
from .naver import NaverApiError, client_for
from .security import decrypt

ENTITY_MODELS = {"campaign": Campaign, "adgroup": AdGroup, "keyword": Keyword, "ad": Ad, "ad_extension": AdExtension}
ALLOWED_FIELDS = {
    "campaign": {"status", "daily_budget"},
    "adgroup": {"status", "bid_amt"},
    "keyword": {"status", "bid_amt"},
    "ad": {"status", "bid_amt"},
    "ad_extension": {"status"},  # 파워링크 확장소재: ON/OFF만 (내용 수정은 유형별 구조 확인 후)
}
# shortcut: 입찰가·예산 한도는 가정값, 공식 문서 확인 후 수정
BID_RANGE = {"WEB_SITE": (70, 100_000), "SHOPPING": (50, 100_000)}
MIN_BUDGET = 50
EXCEL_HEADER = ["entity_type", "naver_id", "field", "value"]


def _product(entity_type: str, obj) -> str:
    if entity_type == "campaign":
        return obj.campaign_tp
    if entity_type == "adgroup":
        return obj.adgroup_type
    if entity_type == "keyword":
        return "WEB_SITE"
    return "SHOPPING" if obj.ad_type == "SHOPPING_PRODUCT_AD" else "WEB_SITE"


def _validate(entity_type: str, obj, field: str, value: str) -> tuple[str | None, str | None]:
    """(before, error) 반환."""
    if field not in ALLOWED_FIELDS[entity_type]:
        return None, f"{entity_type}에서 수정할 수 없는 항목: {field}"
    before = getattr(obj, field)
    if field == "status":
        if value not in ("ON", "OFF"):
            return before, "상태는 ON 또는 OFF"
    else:
        if entity_type == "ad" and obj.ad_type != "SHOPPING_PRODUCT_AD":
            return before, "입찰가는 쇼핑 상품소재에만 설정할 수 있습니다"
        if not value.isdigit():
            return before, "숫자만 입력하세요"
        n = int(value)
        if n % 10:
            return before, "10원 단위로 입력하세요"
        if field == "daily_budget" and n < MIN_BUDGET:
            return before, f"일예산은 {MIN_BUDGET}원 이상"
        if field == "bid_amt":
            lo, hi = BID_RANGE[_product(entity_type, obj)]
            if not lo <= n <= hi:
                return before, f"입찰가는 {lo:,}~{hi:,}원"
    if str(before) == value:
        return before, "현재 값과 동일합니다"
    return before, None


def create_job(db: Session, m: Membership, changes: list[dict], source: str, parent_job_id: int | None = None) -> BulkJob:
    if not changes:
        raise HTTPException(400, "변경 내용이 없습니다")
    allowed = accessible_account_ids(db, m, edit=True)
    job = BulkJob(workspace_id=m.workspace_id, created_by=m.user_id, source=source, parent_job_id=parent_job_id)
    db.add(job)
    db.flush()
    seen = set()
    for ch in changes:
        etype, nid, field, value = (str(ch.get(k, "")).strip() for k in EXCEL_HEADER)
        row = BulkJobRow(job_id=job.id, entity_type=etype, naver_id=nid, field=field, after=value, status="INVALID")
        model = ENTITY_MODELS.get(etype)
        obj = db.scalar(select(model).where(model.naver_id == nid)) if model else None
        if model is None:
            row.error = f"알 수 없는 유형: {etype}"
        elif obj is None or obj.ad_account_id not in allowed:
            row.error = "대상이 없거나 수정 권한이 없습니다"  # 다른 조직 객체의 존재 여부를 노출하지 않는다
        elif (nid, field) in seen:
            row.ad_account_id, row.error = obj.ad_account_id, "같은 대상·항목이 중복되었습니다"
        else:
            seen.add((nid, field))
            row.ad_account_id = obj.ad_account_id
            before, row.error = _validate(etype, obj, field, value)
            row.before = None if before is None else str(before)
            if row.error is None:
                row.status = "VALID"
        db.add(row)
    db.commit()
    return job


def _client(db: Session, workspace_id: int, account_id: int):
    link = db.scalar(select(WorkspaceAdAccount).where(
        WorkspaceAdAccount.workspace_id == workspace_id, WorkspaceAdAccount.ad_account_id == account_id))
    return client_for(db.get(NaverApiCredential, link.credential_id), db.get(AdAccount, account_id).customer_id, decrypt)


def execute_job(db: Session, m: Membership, job: BulkJob) -> BulkJob:
    if job.status != "PREVIEW":
        raise HTTPException(409, "이미 실행된 작업입니다")
    rows = db.scalars(select(BulkJobRow).where(BulkJobRow.job_id == job.id, BulkJobRow.status == "VALID")).all()
    if not rows:
        raise HTTPException(400, "실행할 수 있는 행이 없습니다")
    job.status = "RUNNING"
    db.commit()
    allowed = accessible_account_ids(db, m, edit=True)  # 미리보기 이후 권한이 바뀌었을 수 있다
    clients = {}
    for row in rows:
        if row.ad_account_id not in allowed:
            row.status, row.error = "FAILED", "실행 시점에 수정 권한이 없습니다"
            continue
        try:
            if row.ad_account_id not in clients:
                clients[row.ad_account_id] = _client(db, m.workspace_id, row.ad_account_id)
            clients[row.ad_account_id].update(row.entity_type, row.naver_id, row.field, row.after)
        except NaverApiError as e:
            row.status, row.error = "FAILED", str(e)[:300]
            continue
        model = ENTITY_MODELS[row.entity_type]
        obj = db.scalar(select(model).where(model.naver_id == row.naver_id))
        setattr(obj, row.field, row.after if row.field == "status" else int(row.after))
        if row.field == "bid_amt" and hasattr(obj, "use_group_bid"):
            obj.use_group_bid = False
        row.status = "SUCCESS"
        db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=row.ad_account_id, job_id=job.id,
                        action="UPDATE", entity_type=row.entity_type, naver_id=row.naver_id, field=row.field,
                        before=row.before, after=row.after))
        db.commit()  # 행 단위 커밋: 중간에 죽어도 성공한 변경과 감사 로그는 남는다
    results = {r.status for r in rows}
    job.status = "DONE" if results == {"SUCCESS"} else "FAILED" if "SUCCESS" not in results else "PARTIAL"
    job.executed_at = now()
    db.commit()
    return job


def retry_failed(db: Session, m: Membership, job: BulkJob) -> BulkJob:
    failed = db.scalars(select(BulkJobRow).where(BulkJobRow.job_id == job.id, BulkJobRow.status == "FAILED")).all()
    if not failed:
        raise HTTPException(400, "재실행할 실패 행이 없습니다")
    changes = [{"entity_type": r.entity_type, "naver_id": r.naver_id, "field": r.field, "value": r.after} for r in failed]
    return create_job(db, m, changes, "RETRY", parent_job_id=job.id)


def parse_excel(data: bytes) -> list[dict]:
    try:
        ws = load_workbook(io.BytesIO(data), read_only=True).active
    except Exception:
        raise HTTPException(400, "엑셀(.xlsx) 파일을 읽을 수 없습니다")
    rows = list(ws.iter_rows(values_only=True))
    if not rows or [str(c or "").strip() for c in rows[0][:4]] != EXCEL_HEADER:
        raise HTTPException(400, f"첫 행은 {EXCEL_HEADER} 이어야 합니다")
    return [dict(zip(EXCEL_HEADER, ("" if c is None else str(c) for c in r[:4]))) for r in rows[1:] if any(r[:4])]


def excel_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "bulk"
    ws.append(EXCEL_HEADER)
    ws.append(["campaign", "cmp-...", "status", "OFF"])
    ws.append(["adgroup", "grp-...", "bid_amt", "500"])
    ws.append(["ad", "ad-...(쇼핑 상품소재)", "bid_amt", "300"])
    guide = wb.create_sheet("guide")
    for line in [["entity_type", "campaign | adgroup | keyword(파워링크) | ad | ad_extension(파워링크 확장소재)"],
                 ["field", "status(ON/OFF), daily_budget(캠페인), bid_amt(광고그룹·키워드·쇼핑 상품소재), 확장소재는 status만"],
                 ["value", "10원 단위 숫자 또는 ON/OFF"]]:
        guide.append(line)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
