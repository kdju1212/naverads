"""대량 작업 엔진: 미리보기(검증) → 실행(권한 재검증) → 행별 결과 + 감사 로그.
모든 광고 데이터 쓰기는 이 모듈만 사용한다(확장소재 생성·삭제도 여기서 권한 확인·감사 로그)."""
import io

from fastapi import HTTPException
from openpyxl import Workbook, load_workbook
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .access import accessible_account_ids
from .models import (Ad, AdAccount, AdExtension, AdGroup, AuditLog, AutoBidRule, BulkJob, BulkJobRow, Campaign, Keyword, Membership,
                     NaverApiCredential, WorkspaceAdAccount, now)
from .naver import NaverApiError, client_for
from .security import decrypt
from .sync import _json, _status

ENTITY_MODELS = {"campaign": Campaign, "adgroup": AdGroup, "keyword": Keyword, "ad": Ad, "ad_extension": AdExtension}
ALLOWED_FIELDS = {
    "campaign": {"status", "daily_budget"},
    "adgroup": {"status", "bid_amt"},
    "keyword": {"status", "bid_amt", "create", "delete"},  # create: naver_id는 광고그룹, value는 "키워드" 또는 "키워드|입찰가"
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


def _split_new_keyword(value: str) -> tuple[str, str]:
    kw, _, bid = value.partition("|")
    return kw.strip(), bid.strip()


def _validate_new_keyword(grp: AdGroup, value: str) -> str | None:
    kw, bid = _split_new_keyword(value)
    if grp.adgroup_type != "WEB_SITE":
        return "키워드는 파워링크 광고그룹에만 등록할 수 있습니다"
    if not kw:
        return "키워드를 입력하세요"
    if bid:
        lo, hi = BID_RANGE["WEB_SITE"]
        if not bid.isdigit() or int(bid) % 10 or not lo <= int(bid) <= hi:
            return f"입찰가는 {lo:,}~{hi:,}원, 10원 단위 (비우면 {lo}원)"
    return None


def _validate(entity_type: str, obj, field: str, value: str) -> tuple[str | None, str | None]:
    """(before, error) 반환."""
    if field not in ALLOWED_FIELDS[entity_type]:
        return None, f"{entity_type}에서 수정할 수 없는 항목: {field}"
    if field == "create":
        return None, _validate_new_keyword(obj, value)
    if field == "delete":
        return obj.keyword, None
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
        model = AdGroup if (etype, field) == ("keyword", "create") else ENTITY_MODELS.get(etype)
        obj = db.scalar(select(model).where(model.naver_id == nid)) if model else None
        key = (nid, field, _split_new_keyword(value)[0] if field == "create" else "")
        if model is None:
            row.error = f"알 수 없는 유형: {etype}"
        elif obj is None or obj.ad_account_id not in allowed:
            row.error = "대상이 없거나 수정 권한이 없습니다"  # 다른 조직 객체의 존재 여부를 노출하지 않는다
        elif key in seen:
            row.ad_account_id, row.error = obj.ad_account_id, "같은 대상·항목이 중복되었습니다"
        else:
            seen.add(key)
            row.ad_account_id = obj.ad_account_id
            before, row.error = _validate(etype, obj, field, value)
            row.before = None if before is None else str(before)
            if row.error is None and field == "create" and db.scalar(select(Keyword.id).where(
                    Keyword.adgroup_id == obj.id, Keyword.keyword == key[2])):
                row.error = "이미 등록된 키워드입니다"
            if row.error is None:
                row.status = "VALID"
        db.add(row)
    db.commit()
    return job


def _client(db: Session, workspace_id: int, account_id: int):
    link = db.scalar(select(WorkspaceAdAccount).where(
        WorkspaceAdAccount.workspace_id == workspace_id, WorkspaceAdAccount.ad_account_id == account_id))
    return client_for(db.get(NaverApiCredential, link.credential_id), db.get(AdAccount, account_id).customer_id, decrypt)


# 무료 플랜은 요청 1번에 D1 쿼리+외부 호출 50번까지라, 화면 실행은 몇 행씩 나눠 여러 번 요청한다(행마다 약 5번 + 고정 약 15번)
EXECUTE_CHUNK = 3


def execute_job(db: Session, m: Membership, job: BulkJob, limit: int | None = None) -> BulkJob:
    """VALID 행을 최대 limit개 실행. 남은 행이 있으면 RUNNING으로 두고 반환하니 다시 호출하면 이어서 실행한다
    (중간에 요청이 끊긴 RUNNING 작업도 같은 방법으로 이어 간다)."""
    if job.status not in ("PREVIEW", "RUNNING"):
        raise HTTPException(409, "이미 실행된 작업입니다")
    q = select(BulkJobRow).where(BulkJobRow.job_id == job.id, BulkJobRow.status == "VALID").order_by(BulkJobRow.id)
    rows = db.scalars(q.limit(limit) if limit else q).all()
    if not rows and job.status == "PREVIEW":
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
            client = clients[row.ad_account_id]
            if row.field == "create":
                kw, bid = _split_new_keyword(row.after)
                grp = db.scalar(select(AdGroup).where(AdGroup.naver_id == row.naver_id))
                bid_amt = int(bid) if bid else BID_RANGE["WEB_SITE"][0]  # 비우면 최저 입찰가(사용자 요청 10/20)
                created = client.create_keyword(row.naver_id, kw, bid_amt, False)
            elif row.field == "delete":
                client.delete_keyword(row.naver_id)
            else:
                client.update(row.entity_type, row.naver_id, row.field, row.after)
        except NaverApiError as e:
            row.status, row.error = "FAILED", str(e)[:300]
            continue
        audit = dict(action="UPDATE", naver_id=row.naver_id, field=row.field, before=row.before, after=row.after)
        if row.field == "create":
            db.add(Keyword(ad_account_id=grp.ad_account_id, adgroup_id=grp.id, naver_id=created["nccKeywordId"],
                           keyword=created.get("keyword", kw), status=_status(created),
                           bid_amt=created.get("bidAmt") or bid_amt, use_group_bid=created.get("useGroupBidAmt", False)))
            audit.update(action="CREATE", naver_id=created["nccKeywordId"], field="keyword", after=kw)
        elif row.field == "delete":
            obj = db.scalar(select(Keyword).where(Keyword.naver_id == row.naver_id))
            db.execute(delete(AutoBidRule).where(AutoBidRule.keyword_id == obj.id))
            db.delete(obj)
            audit.update(action="DELETE", field="keyword", after=None)
        else:
            model = ENTITY_MODELS[row.entity_type]
            obj = db.scalar(select(model).where(model.naver_id == row.naver_id))
            setattr(obj, row.field, row.after if row.field == "status" else int(row.after))
            if row.field == "bid_amt" and hasattr(obj, "use_group_bid"):
                obj.use_group_bid = False
        row.status = "SUCCESS"
        db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=row.ad_account_id, job_id=job.id,
                        entity_type=row.entity_type, **audit))
        db.commit()  # 행 단위 커밋: 중간에 죽어도 성공한 변경과 감사 로그는 남는다
    db.commit()
    results = set(db.scalars(select(BulkJobRow.status).where(BulkJobRow.job_id == job.id, BulkJobRow.status != "INVALID")))
    if "VALID" in results:
        return job
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


def run_auto_bids(db: Session, workspace_id: int, rule_ids: list[int] | None = None) -> list[BulkJob]:
    """자동입찰 규칙 실행: 목표 순위 예상 입찰가(최대 입찰가 이하)로 바꿀 키워드를 모아 만든 사람별 대량 작업으로 실행한다.
    권한 확인·네이버 반영 검증·감사 로그는 일반 대량 작업과 같다."""
    s = select(AutoBidRule).where(AutoBidRule.workspace_id == workspace_id, AutoBidRule.enabled.is_(True))
    if rule_ids is not None:
        s = s.where(AutoBidRule.id.in_(rule_ids))
    by_user: dict[int, list[AutoBidRule]] = {}
    for r in db.scalars(s):
        by_user.setdefault(r.created_by, []).append(r)
    jobs = []
    for user_id, rules in by_user.items():
        m = db.scalar(select(Membership).where(Membership.workspace_id == workspace_id, Membership.user_id == user_id))
        allowed = accessible_account_ids(db, m, edit=True) if m else set()
        kws = {k.id: k for k in db.scalars(select(Keyword).where(Keyword.id.in_([r.keyword_id for r in rules])))}
        groups: dict[tuple, list[AutoBidRule]] = {}
        for r in rules:
            r.last_run_at = now()
            if kws[r.keyword_id].ad_account_id not in allowed:
                r.last_result = "규칙을 만든 사람에게 이 계정 수정 권한이 없습니다"
            else:
                groups.setdefault((kws[r.keyword_id].ad_account_id, r.device), []).append(r)
        changes, rule_by_nid = [], {}
        for (account_id, device), rs in groups.items():
            try:
                est = _client(db, workspace_id, account_id).estimate_bids(
                    device, [(kws[r.keyword_id].naver_id, r.target_rank) for r in rs])
            except NaverApiError as e:
                for r in rs:
                    r.last_result = f"예상 입찰가 조회 실패: {e}"[:300]
                continue
            lo = BID_RANGE["WEB_SITE"][0]
            for r in rs:
                kw, bid = kws[r.keyword_id], est.get(kws[r.keyword_id].naver_id)
                if not bid:
                    r.last_result = "예상 입찰가가 없습니다 (노출 데이터 부족)"
                    continue
                target = max(lo, min(bid, r.max_bid) // 10 * 10)
                r.last_result = f"{r.target_rank}위 예상 {bid:,}원" + (f" > 최대 {r.max_bid:,}원" if bid > r.max_bid else "")
                if target == kw.bid_amt and not kw.use_group_bid:
                    r.last_result += " · 변경 없음"
                    continue
                r.last_result += f" · {kw.bid_amt:,}원 → {target:,}원"
                changes.append({"entity_type": "keyword", "naver_id": kw.naver_id, "field": "bid_amt", "value": str(target)})
                rule_by_nid[kw.naver_id] = r
        db.commit()
        if not changes:
            continue
        job = execute_job(db, m, create_job(db, m, changes, "AUTO_BID"))
        for row in db.scalars(select(BulkJobRow).where(BulkJobRow.job_id == job.id, BulkJobRow.status != "SUCCESS")):
            rule_by_nid[row.naver_id].last_result = f"{rule_by_nid[row.naver_id].last_result} 실패: {row.error}"[:300]
        db.commit()
        jobs.append(job)
    return jobs


def run_all_auto_bids(db: Session):
    """크론용: 규칙이 있는 모든 조직. 한 조직이 실패해도 나머지는 돈다."""
    for ws_id in set(db.scalars(select(AutoBidRule.workspace_id).where(AutoBidRule.enabled.is_(True)))):
        try:
            run_auto_bids(db, ws_id)
        except Exception as e:  # noqa: BLE001
            db.rollback()
            print(f"자동입찰 실패 workspace={ws_id}: {e}")


def parse_excel(data: bytes) -> list[dict]:
    try:
        ws = load_workbook(io.BytesIO(data), read_only=True).active
    except Exception:
        raise HTTPException(400, "엑셀(.xlsx) 파일을 읽을 수 없습니다")
    rows = list(ws.iter_rows(values_only=True))
    if not rows or [str(c or "").strip() for c in rows[0][:4]] != EXCEL_HEADER:
        raise HTTPException(400, f"첫 행은 {EXCEL_HEADER} 이어야 합니다")
    return [dict(zip(EXCEL_HEADER, ("" if c is None else str(c) for c in r[:4]))) for r in rows[1:] if any(r[:4])]


def create_extension(db: Session, m: Membership, grp: AdGroup, ext_type: str, content) -> AdExtension:
    """확장소재 생성은 행 단위 미리보기 없이 바로 실행하되, 권한 확인과 감사 로그는 같은 규칙을 따른다."""
    if grp.ad_account_id not in accessible_account_ids(db, m, edit=True):
        raise HTTPException(403, "이 광고 계정을 수정할 권한이 없습니다")
    if grp.adgroup_type != "WEB_SITE":
        raise HTTPException(400, "확장소재는 파워링크 광고그룹에만 만들 수 있습니다")
    try:
        e = _client(db, m.workspace_id, grp.ad_account_id).create_ad_extension(grp.naver_id, ext_type, content)
    except NaverApiError as err:
        raise HTTPException(400, f"네이버 확장소재 생성 실패: {err}")
    ext = AdExtension(ad_account_id=grp.ad_account_id, naver_id=e["nccAdExtensionId"], owner_naver_id=grp.naver_id,
                      ext_type=e.get("type", ext_type), status=_status(e), inspect_status=e.get("inspectStatus", ""),
                      payload=_json(e["adExtension"]) if e.get("adExtension") else content)
    db.add(ext)
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=grp.ad_account_id, action="CREATE",
                    entity_type="ad_extension", naver_id=ext.naver_id, field="ext_type", after=ext.ext_type))
    db.commit()
    return ext


def delete_extension(db: Session, m: Membership, ext: AdExtension):
    if ext.ad_account_id not in accessible_account_ids(db, m, edit=True):
        raise HTTPException(403, "이 광고 계정을 수정할 권한이 없습니다")
    client = _client(db, m.workspace_id, ext.ad_account_id)
    gone = False
    try:
        client.delete_ad_extension(ext.naver_id)
    except NaverApiError as err:
        # 네이버에서 이미 지워진 확장소재는 404가 난다(다음 동기화 전까지는 앱에 남아 있다): 소유자 목록으로 실제 존재 여부를 확인
        try:
            gone = all(e["nccAdExtensionId"] != ext.naver_id for e in client.list_ad_extensions(ext.owner_naver_id))
        except NaverApiError:
            gone = False
        if not gone:
            raise HTTPException(400, f"네이버 확장소재 삭제 실패: {err}")
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=ext.ad_account_id, action="DELETE",
                    entity_type="ad_extension", naver_id=ext.naver_id, field="ext_type", before=ext.ext_type,
                    after="네이버에 이미 없음" if gone else None))
    db.delete(ext)
    db.commit()
    return gone


def excel_template() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "bulk"
    ws.append(EXCEL_HEADER)
    ws.append(["campaign", "cmp-...", "status", "OFF"])
    ws.append(["adgroup", "grp-...", "bid_amt", "500"])
    ws.append(["ad", "ad-...(쇼핑 상품소재)", "bid_amt", "300"])
    ws.append(["keyword", "grp-...(광고그룹)", "create", "여름 원피스|500"])
    ws.append(["keyword", "kwd-...", "delete", ""])
    guide = wb.create_sheet("guide")
    for line in [["entity_type", "campaign | adgroup | keyword(파워링크) | ad | ad_extension(파워링크 확장소재)"],
                 ["field", "status(ON/OFF), daily_budget(캠페인), bid_amt(광고그룹·키워드·쇼핑 상품소재), 확장소재는 status만"],
                 ["value", "10원 단위 숫자 또는 ON/OFF"],
                 ["키워드 등록", "entity_type=keyword, naver_id=광고그룹 ID(grp-...), field=create, value=키워드|입찰가 (입찰가 비우면 70원)"],
                 ["키워드 삭제", "entity_type=keyword, naver_id=키워드 ID(kwd-...), field=delete, value 비움"]]:
        guide.append(line)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
