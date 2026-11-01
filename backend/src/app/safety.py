"""광고비 안전장치. 조직·광고 계정별로 '하루예산 관리 기준'(켜진 캠페인 하루예산 설정액 합계의 한도)과 '클릭당 최대 입찰가'를 둔다.

비용이 늘거나 광고가 시작될 수 있는 작업(켜기·예산 올리기·입찰가)은 실행 직전에 네이버의 현재 설정을 다시 읽어 검사한다.
모든 실행 경로가 여기를 거친다: 대량 작업 execute_job(웹·Claude·예약·자동입찰·목표 ROAS), 예약 등록, 플레이스(place.py),
쇼핑 상품소재(shopping_ads.py), 자동입찰 규칙 저장(main.set_auto_bids). 끄기·예산 줄이기·삭제·조회는 막지 않는다.
계산 방식·한계·출처: docs/AD_SAFETY_AND_APPROVALS.md"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AccountSafety, AuditLog, Membership, now
from .naver import NaverApiError

# 네이버는 광고 중지 반영 지연 등으로 설정한 하루예산보다 더 과금될 수 있다고 안내한다 → 설정액을 실제 과금 상한이라고 말하지 않는다
OVERSPEND_NOTE = ("하루예산 설정액은 실제 과금의 절대 상한이 아니에요. 네이버가 광고를 멈추는 데 시간이 걸려 "
                  "설정액보다 조금 더 과금될 수 있어요.")
OPEN_CAMPAIGN_MAX = 10  # 하루예산 없는 켜진 캠페인은 광고그룹까지 읽어야 해서 이 개수까지만(무료 플랜 요청당 외부 호출 50번)
LIMIT_RANGE = (1_000, 1_000_000_000)
BID_RANGE = (50, 100_000)
NOT_SET = ("이 광고 계정은 아직 광고비 안전장치(하루예산 관리 기준·클릭당 최대 입찰가)를 정하지 않아 광고를 켜거나 "
           "예산·입찰가를 올릴 수 없어요. 설정 > 광고비 안전장치에서 먼저 정해 주세요")


class SafetyError(Exception):
    pass


def get(db: Session, ws_id: int, account_id: int) -> AccountSafety | None:
    return db.scalar(select(AccountSafety).where(AccountSafety.workspace_id == ws_id, AccountSafety.ad_account_id == account_id))


def _on(o) -> bool:
    return not o.get("userLock")


def _shared(o) -> bool:
    return bool(o.get("sharedBudgetId") or o.get("sharedBudget"))


def _budget(o) -> int | None:
    """설정된 하루예산(없으면 None = 무제한). useDailyBudget이 없는 응답은 dailyBudget 값으로 판단한다."""
    v = o.get("dailyBudget")
    return v if o.get("useDailyBudget", True) and v else None


class Snapshot:
    """네이버의 지금 캠페인·광고그룹 설정. 변경을 흉내 낸 뒤 합계를 다시 계산할 수 있다."""

    def __init__(self, client):
        self.client = client
        self.camps = {c["nccCampaignId"]: dict(c) for c in client.list_campaigns()}
        self.groups: dict[str, dict[str, dict]] = {}

    def groups_of(self, cid: str) -> dict[str, dict]:
        if cid not in self.groups:
            self.groups[cid] = {g["nccAdgroupId"]: dict(g) for g in self.client.list_adgroups(cid)}
        return self.groups[cid]

    def group(self, gid: str) -> dict:
        for gs in self.groups.values():
            if gid in gs:
                return gs[gid]
        found = self.client.get_many("adgroups", [gid])
        if not found or found[0]["nccCampaignId"] not in self.camps:
            raise SafetyError(f"광고그룹({gid})을 네이버에서 찾지 못해 실행하지 않았어요")
        return self.groups_of(found[0]["nccCampaignId"])[gid]

    def total(self) -> tuple[int | None, list[str], list[dict]]:
        """켜진 캠페인의 하루예산 설정액 합계. 캠페인에 예산이 있으면 그 값만(아래 광고그룹 예산은 그 안에 포함되므로 더하지 않음),
        캠페인에 예산이 없으면 켜진 광고그룹 예산의 합. 공유예산·무제한이 있으면 계산 불가(None)와 이유."""
        total, reasons, rows, opened = 0, [], [], 0
        for cid, c in self.camps.items():
            if not _on(c):
                continue
            name = c.get("name", cid)
            if _shared(c):
                reasons.append(f"캠페인 '{name}'은 공유예산을 써서 계정 합계를 정확히 계산할 수 없어요")
                continue
            b = _budget(c)
            if b is None:
                opened += 1
                if opened > OPEN_CAMPAIGN_MAX:
                    reasons.append(f"하루예산이 없는 켜진 캠페인이 {OPEN_CAMPAIGN_MAX}개보다 많아 계산하지 못했어요")
                    break
                b = 0
                for g in self.groups_of(cid).values():
                    if not _on(g):
                        continue
                    if _shared(g):
                        reasons.append(f"광고그룹 '{g.get('name', '')}'(캠페인 '{name}')은 공유예산을 써서 계산할 수 없어요")
                    elif _budget(g) is None:
                        reasons.append(f"캠페인 '{name}'과 그 광고그룹 '{g.get('name', '')}'에 하루예산이 없어(무제한) 계산할 수 없어요")
                    else:
                        b += _budget(g)
            rows.append({"id": cid, "name": name, "type": c.get("campaignTp"), "daily_budget": b,
                         "from": "campaign" if _budget(c) is not None else "adgroups"})
            total += b
        return (None if reasons else total), reasons, rows


def ops_of_row(entity_type: str, field: str, naver_id: str, value: str) -> list[tuple]:
    """대량 작업 행 → 안전장치 검사 대상. ("on", 유형, id) 광고 시작 / ("budget", 캠페인 id, 금액) / ("bid", 금액)."""
    if entity_type == "negative_keyword" or field == "delete":
        return []
    if field == "status":
        return [("on", entity_type, naver_id)] if value == "ON" else []
    if field == "daily_budget":
        return [("budget", naver_id, int(value))]
    if field == "bid_amt":
        return [("bid", int(value))]
    if field == "create" and entity_type == "keyword":
        bid = value.partition("|")[2].strip()
        return [("bid", int(bid) if bid.isdigit() else 70)]  # 비우면 bulk가 최저가 70원으로 만든다
    if field == "create" and entity_type == "adgroup":
        bid = (value.split("|") + ["", "", ""])[2].strip()
        return [("bid", int(bid) if bid.isdigit() else 70)]
    return []  # 캠페인 생성은 꺼진 상태로 만들어진다 → 켤 때 검사


def check_bids(s: AccountSafety | None, ops: list[tuple]):
    bids = [o[1] for o in ops if o[0] == "bid"]
    if bids and s is None:
        raise SafetyError(NOT_SET)
    for v in bids:
        if v > s.max_bid:
            raise SafetyError(f"입찰가 {v:,}원이 이 계정의 클릭당 최대 입찰가 {s.max_bid:,}원보다 높아요. "
                              "입찰가를 낮추거나 관리자가 최대 입찰가를 바꿔야 해요")


def check(db: Session, ws_id: int, account_id: int, ops: list[tuple], get_client) -> dict | None:
    """ops를 실행해도 되는지. 안 되면 SafetyError(사장님용 이유). 하루예산 합계 검사가 필요하면 네이버를 다시 읽는다.
    돌려주는 dict: 변경 후 합계·기준·최대 입찰가·과금 안내(승인 카드·미리보기에 보여 줌)."""
    s = get(db, ws_id, account_id)
    check_bids(s, ops)
    starts = [o for o in ops if o[0] in ("on", "budget", "start")]
    if not starts:
        return {"max_bid": s.max_bid, "daily_budget_limit": s.daily_budget_limit, "note": OVERSPEND_NOTE} if s and ops else None
    try:
        snap = Snapshot(get_client())
        increasing = False
        for op in starts:
            if op[0] == "budget":
                c = snap.camps.get(op[1])
                if c is None:
                    raise SafetyError(f"캠페인({op[1]})을 네이버에서 찾지 못해 실행하지 않았어요")
                cur = _budget(c)
                if cur is not None and op[2] <= cur:
                    continue  # 예산 줄이기(또는 그대로)는 언제나 허용. 무제한 → 금액 설정도 줄이기에 해당
                if cur is None:
                    continue
                c["dailyBudget"], c["useDailyBudget"] = op[2], True
            elif op[0] == "on" and op[1] == "campaign":
                if op[2] not in snap.camps:
                    raise SafetyError(f"캠페인({op[2]})을 네이버에서 찾지 못해 실행하지 않았어요")
                snap.camps[op[2]]["userLock"] = False
            elif op[0] == "on" and op[1] == "adgroup":
                snap.group(op[2])["userLock"] = False
            increasing = True  # 키워드·소재·확장소재 켜기와 'start'도 광고 시작이라 합계가 기준 안이어야 한다
        if not increasing:
            return None
        if s is None:
            raise SafetyError(NOT_SET)
        total, reasons, _ = snap.total()
    except NaverApiError as e:
        raise SafetyError(f"네이버의 지금 예산 설정을 읽지 못해 실행하지 않았어요. 잠시 뒤 다시 해 주세요 ({str(e)[:100]})")
    if total is None:
        raise SafetyError("계정의 하루예산 설정액 합계를 정확히 계산할 수 없어 광고 시작·예산 증액을 막았어요: " + " / ".join(reasons[:3]))
    if total > s.daily_budget_limit:
        raise SafetyError(f"변경 후 켜진 캠페인의 하루예산 설정액 합계가 {total:,}원으로 이 계정의 관리 기준 {s.daily_budget_limit:,}원을 넘어요. "
                          "다른 캠페인을 끄거나 예산을 줄인 뒤 다시 해 주세요")
    return {"total_after": total, "daily_budget_limit": s.daily_budget_limit, "max_bid": s.max_bid, "note": OVERSPEND_NOTE}


def preview(db: Session, ws_id: int, account_id: int, ops: list[tuple], get_client) -> dict:
    """check와 같지만 막는 대신 결과를 돌려준다(미리보기·승인 카드용)."""
    try:
        out = check(db, ws_id, account_id, ops, get_client) or {}
        return {"ad_account_id": account_id, "ok": True, **out, "note": OVERSPEND_NOTE}
    except SafetyError as e:
        return {"ad_account_id": account_id, "ok": False, "reason": str(e), "note": OVERSPEND_NOTE}


def status(db: Session, ws_id: int, account_id: int, get_client) -> dict:
    """설정 화면·처음 연결: 지금 켜진 캠페인의 하루예산 설정액과 합계, 문제와 필요한 조치."""
    s = get(db, ws_id, account_id)
    out = {"configured": s is not None, "daily_budget_limit": s and s.daily_budget_limit, "max_bid": s and s.max_bid,
           "set_by": s and s.set_by, "set_at": s and s.set_at, "note": OVERSPEND_NOTE}
    try:
        total, reasons, rows = Snapshot(get_client()).total()
    except NaverApiError as e:
        return {**out, "total": None, "campaigns": [], "problems": [f"네이버 설정을 읽지 못했어요: {str(e)[:100]}"], "needs_action": True,
                "actions": ["잠시 뒤 다시 확인해 주세요"]}
    actions = []
    if s is None:
        actions.append("하루예산 관리 기준과 클릭당 최대 입찰가를 정해 주세요. 정하기 전에는 광고 켜기·예산 증액·입찰가 변경이 막혀요")
    if reasons:
        actions.append("공유예산이나 하루예산이 없는(무제한) 캠페인·광고그룹에 하루예산을 정하거나 꺼 주세요")
    if s is not None and total is not None and total > s.daily_budget_limit:
        actions.append(f"켜진 캠페인의 하루예산 설정액 합계({total:,}원)가 관리 기준({s.daily_budget_limit:,}원)을 넘어요. "
                       "캠페인을 끄거나 예산을 줄여 주세요")
    return {**out, "total": total, "campaigns": rows, "problems": reasons, "needs_action": bool(actions),
            "actions": actions + (["정리될 때까지 광고 켜기·예산 증액은 막히고, 조회와 광고 끄기는 할 수 있어요"] if actions else [])}


def save(db: Session, m: Membership, account_id: int, daily_budget_limit: int, max_bid: int, confirmed: bool) -> AccountSafety:
    """관리자가 금액을 직접 확인하고 저장한다(confirmed=True가 아니면 거부). 바꿀 때마다 이력을 남긴다."""
    if not confirmed:
        raise HTTPException(400, "금액을 확인했다는 표시(confirmed)가 필요해요")
    for v, (lo, hi), label in ((daily_budget_limit, LIMIT_RANGE, "하루예산 관리 기준"), (max_bid, BID_RANGE, "클릭당 최대 입찰가")):
        if not lo <= v <= hi or v % 10:
            raise HTTPException(400, f"{label}은 {lo:,}~{hi:,}원, 10원 단위")
    s = get(db, m.workspace_id, account_id)
    before = s and f"{s.daily_budget_limit}/{s.max_bid}"
    if s is None:
        s = AccountSafety(workspace_id=m.workspace_id, ad_account_id=account_id)
        db.add(s)
    s.daily_budget_limit, s.max_bid, s.set_by, s.set_at = daily_budget_limit, max_bid, m.user_id, now()
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=account_id, action="SAFETY_SET", entity_type="account",
                    field="limit/max_bid", before=before, after=f"{daily_budget_limit}/{max_bid}"))
    db.commit()
    return s
