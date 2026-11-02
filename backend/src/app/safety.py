"""광고비 안전장치. 조직·광고 계정별로 '하루예산 관리 기준'(켜진 캠페인 하루예산 설정액 합계의 한도)과 '클릭당 최대 입찰가'를 둔다.

비용이 늘거나 광고가 시작될 수 있는 작업(켜기·예산 올리기·입찰가 올리기·새 입찰가)은 실행 직전에 네이버의 현재 설정을 다시 읽어 검사하고,
같은 계정의 비용 변경은 account_lock으로 한 번에 하나씩 실행한다.
모든 실행 경로가 여기를 거친다: 대량 작업 execute_job(웹·Claude·예약·자동입찰·목표 ROAS), 예약 등록, 플레이스(place.py),
쇼핑 상품소재(shopping_ads.py), 확장소재 등록(bulk.create_extension), 자동입찰·목표 ROAS 저장(main). 끄기·예산 줄이기·삭제·조회는 막지 않는다.
계산 방식·한계·출처: docs/AD_SAFETY_AND_APPROVALS.md"""
import secrets
from contextlib import contextmanager
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import bindparam, delete, select, text, update
from sqlalchemy.orm import Session

from .models import AccountLock, AccountSafety, AuditLog, Membership, now
from .naver import NaverApiError, _json, advoost_on

# 네이버는 광고 중지 반영 지연 등으로 설정한 하루예산보다 더 과금될 수 있다고 안내한다 → 설정액을 실제 과금 상한이라고 말하지 않는다
OVERSPEND_NOTE = ("하루예산 설정액은 실제 과금의 절대 상한이 아니에요. 네이버가 광고를 멈추는 데 시간이 걸려 "
                  "설정액보다 조금 더 과금될 수 있어요. 네이버 광고주센터에서 직접 바꾼 설정은 이 웹이 막을 수 없어요.")
OPEN_CAMPAIGN_MAX = 10  # 하루예산 없는 켜진 캠페인은 광고그룹까지 읽어야 해서 이 개수까지만(무료 플랜 요청당 외부 호출 50번)
LIMIT_RANGE = (1_000, 1_000_000_000)
BID_RANGE = (50, 100_000)
NOT_SET = ("이 광고 계정은 아직 광고비 안전장치(하루예산 관리 기준·클릭당 최대 입찰가)를 정하지 않아 광고를 켜거나 "
           "예산·입찰가를 올릴 수 없어요. 설정 > 광고비 안전장치에서 먼저 정해 주세요")
ADVOOST_NOTE = ("ADVoost는 네이버가 입찰가를 알아서 정해 이 계정의 클릭당 최대 입찰가를 적용할 수 없어요. "
                "캠페인 하루예산 설정액 안에서만 쓰도록 켜요(하루예산도 실제 과금의 절대 상한은 아니에요)")
EFFECTIVE_GROUP_MAX = 10  # 켤 때 실제 입찰가를 읽는 광고그룹 수(그룹마다 키워드·소재 2번 호출, 무료 플랜 요청당 외부 호출 50번)


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
        self.objs: dict[str, dict | None] = {}  # 키워드·소재 등 개별 조회 결과(_prefetch)

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
    """대량 작업 행 → 안전장치 검사 대상.
    ("on", 유형, id) 광고 시작 / ("budget", 캠페인 id, 금액) / ("bid", 금액, 유형, id) 기존 대상 입찰가(올리는지는 네이버 지금 값과 비교) /
    ("bid", 금액, None, None) 새로 만드는 대상 입찰가(늘 증가로 봄) / ("expose",) 제외검색어 삭제(노출이 늘 수 있음).
    플레이스는 ("advoost", 광고그룹 id)도 쓴다."""
    if entity_type == "negative_keyword":
        return [("expose",)] if field == "delete" else []
    if field == "delete":
        return []
    if field == "status":
        return [("on", entity_type, naver_id)] if value == "ON" else []
    if field == "daily_budget":
        return [("budget", naver_id, int(value))]
    if field == "bid_amt":
        return [("bid", int(value), entity_type, naver_id)]
    if field == "create" and entity_type == "keyword":
        bid = value.partition("|")[2].strip()
        return [("bid", int(bid) if bid.isdigit() else 70, None, None)]  # 비우면 bulk가 최저가 70원으로 만든다. 키워드는 켜진 상태로 생긴다
    if field == "create" and entity_type == "adgroup":
        bid = (value.split("|") + ["", "", ""])[2].strip()
        return [("bid", int(bid) if bid.isdigit() else 70, None, None)]
    return []  # 캠페인 생성은 꺼진 상태로 만들어진다 → 켤 때 검사


def check_bids(s: AccountSafety | None, ops: list[tuple]):
    bids = [o[1] for o in ops if o[0] == "bid"]
    if bids and s is None:
        raise SafetyError(NOT_SET)
    for v in bids:
        if v > s.max_bid:
            raise SafetyError(f"입찰가 {v:,}원이 이 계정의 클릭당 최대 입찰가 {s.max_bid:,}원보다 높아요. "
                              "입찰가를 낮추거나 관리자가 최대 입찰가를 바꿔야 해요")


def _ad_bid(a: dict) -> int | None:
    """쇼핑 상품소재의 자기 입찰가(그룹 입찰가를 쓰면 None, 그 밖의 소재는 자기 입찰가가 없어 None).
    쇼핑 상품소재인데 입찰가 정보를 읽을 수 없으면 0원으로 보지 않고 SafetyError."""
    if a.get("type") != "SHOPPING_PRODUCT_AD":
        return None
    attr = _json(a.get("adAttr"))
    if not isinstance(attr, dict) or (not attr.get("useGroupBidAmt") and not isinstance(attr.get("bidAmt"), int)):
        raise SafetyError(f"쇼핑 상품소재({a.get('nccAdId')})의 입찰가를 네이버 응답에서 확인할 수 없어 비용이 늘 수 있는 변경을 막았어요")
    return None if attr.get("useGroupBidAmt") else attr["bidAmt"]


def _bid_of(o: dict, label: str) -> int:
    """입찰가 필드가 없거나 숫자가 아니면 0원으로 보지 않고 막는다(확인할 수 없는 값으로 통과시키지 않게)."""
    v = o.get("bidAmt")
    if not isinstance(v, int) or isinstance(v, bool):
        raise SafetyError(f"{label}의 입찰가를 네이버 응답에서 확인할 수 없어 비용이 늘 수 있는 변경을 막았어요")
    return v


def _group_bids(snap: Snapshot, g: dict, max_bid: int, notes: list[str]):
    """광고그룹이 켜지면 실제로 쓰일 입찰가(그룹 입찰가, 켜진 키워드의 자기 입찰가, 쇼핑 상품소재 입찰가)가 최대 입찰가 이하인지.
    ADVoost 그룹은 입찰가를 정할 수 없어 캠페인 하루예산이 있을 때만 통과하고, 통제할 수 없다는 사실을 notes에 남긴다."""
    name = g.get("name", g["nccAdgroupId"])
    if advoost_on(g):
        if _budget(snap.camps.get(g["nccCampaignId"], {})) is None:
            raise SafetyError(f"광고그룹 '{name}'은 ADVoost라 입찰가 상한을 걸 수 없는데, 캠페인에 하루예산이 없어 켤 수 없어요. "
                              "캠페인 하루예산을 먼저 정해 주세요")
        if ADVOOST_NOTE not in notes:
            notes.append(ADVOOST_NOTE)
        return
    if _bid_of(g, f"광고그룹 '{name}'") > max_bid:
        raise SafetyError(f"광고그룹 '{name}'의 입찰가 {g['bidAmt']:,}원이 클릭당 최대 입찰가 {max_bid:,}원보다 높아 켤 수 없어요. 입찰가를 먼저 낮춰 주세요")
    c = snap.client
    over = [k for k in c.list_keywords(g["nccAdgroupId"])
            if _on(k) and not k.get("useGroupBidAmt") and _bid_of(k, f"키워드 '{k.get('keyword', '')}'") > max_bid]
    over += [a for a in c.list_ads(g["nccAdgroupId"]) if _on(a) and (_ad_bid(a) or 0) > max_bid]
    if over:
        raise SafetyError(f"광고그룹 '{name}' 안에 클릭당 최대 입찰가 {max_bid:,}원보다 높은 입찰가를 쓰는 키워드·소재가 {len(over)}개 있어 "
                          "켤 수 없어요. 그 입찰가를 먼저 낮춰 주세요")


KINDS = {"keyword": "keywords", "adgroup": "adgroups", "ad": "ads"}


def _prefetch(snap: Snapshot, ops: list[tuple]):
    """입찰가를 볼 기존 대상을 유형별로 한 번에 읽어 둔다(행마다 부르면 무료 플랜 요청당 외부 호출 한도를 넘는다)."""
    want: dict[str, list[str]] = {}
    for o in ops:
        if (o[0] == "bid" and o[2] in KINDS) or (o[0] == "on" and o[1] in ("keyword", "ad")):
            etype, nid = (o[2], o[3]) if o[0] == "bid" else (o[1], o[2])
            want.setdefault(etype, []).append(nid)
    for etype, ids in want.items():
        snap.objs.update({x[{"keyword": "nccKeywordId", "adgroup": "nccAdgroupId", "ad": "nccAdId"}[etype]]: x
                          for x in snap.client.get_many(KINDS[etype], list(dict.fromkeys(ids)))})


def _obj(snap: Snapshot, etype: str, nid: str) -> dict | None:
    if nid not in snap.objs:
        found = snap.client.get_many(KINDS[etype], [nid])
        snap.objs[nid] = found[0] if found else None
    return snap.objs[nid]


def _current_bid(snap: Snapshot, etype: str, nid: str) -> int:
    """기존 대상의 지금 실제 입찰가(그룹 입찰가를 쓰면 그룹 값). 찾지 못하면 SafetyError."""
    o = _obj(snap, etype, nid)
    if not o:
        raise SafetyError(f"입찰가를 확인할 대상({nid})을 네이버에서 찾지 못해 실행하지 않았어요")
    if etype == "adgroup":
        return _bid_of(o, f"광고그룹({nid})")
    own = (None if o.get("useGroupBidAmt") else _bid_of(o, f"키워드({nid})")) if etype == "keyword" else _ad_bid(o)
    return own if own is not None else _bid_of(snap.group(o["nccAdgroupId"]), f"광고그룹({o['nccAdgroupId']})")


def _effective_on(snap: Snapshot, etype: str, nid: str, max_bid: int, notes: list[str]):
    """기존 대상을 켤 때: 실제로 쓰일 입찰가가 최대 입찰가 이하인지(그룹 입찰가 상속 포함). 판단할 수 없으면 SafetyError."""
    if etype == "campaign":
        if nid not in snap.camps:
            raise SafetyError(f"캠페인({nid})을 네이버에서 찾지 못해 실행하지 않았어요")
        groups = [g for g in snap.groups_of(nid).values() if _on(g)]
        if len(groups) > EFFECTIVE_GROUP_MAX:
            raise SafetyError(f"캠페인에 켜진 광고그룹이 {EFFECTIVE_GROUP_MAX}개보다 많아 실제 입찰가를 다 확인하지 못해 켜지 않았어요. "
                              "광고그룹 일부를 끈 뒤 나눠 켜 주세요")
        for g in groups:
            _group_bids(snap, g, max_bid, notes)
    elif etype == "adgroup":
        _group_bids(snap, snap.group(nid), max_bid, notes)
    elif etype in ("keyword", "ad"):
        if etype == "ad":
            a = _obj(snap, "ad", nid)
            if a and advoost_on(snap.group(a["nccAdgroupId"])):
                return _group_bids(snap, snap.group(a["nccAdgroupId"]), max_bid, notes)
        if _current_bid(snap, etype, nid) > max_bid:
            raise SafetyError(f"켜려는 대상({nid})의 실제 입찰가가 클릭당 최대 입찰가 {max_bid:,}원보다 높아 켤 수 없어요. 입찰가를 먼저 낮춰 주세요")
    # 확장소재는 입찰가가 없다(합계 검사만)


def web_approval_needed(ops: list[tuple], get_client) -> bool:
    """웹에서 사람이 승인해야 하는 변경인지(사용자 결정 2026-11-02): 계정 하루예산 설정액 합계를 늘릴 수 있는 것만 —
    캠페인 하루예산 증액, 캠페인·광고그룹 켜기, ADVoost 켜기. 증액인지는 네이버 지금 값으로 본다(못 읽으면 승인 필요로 본다)."""
    if any(o[0] == "advoost" or (o[0] == "on" and o[1] in ("campaign", "adgroup")) for o in ops):
        return True
    budgets = [o for o in ops if o[0] == "budget"]
    if not budgets:
        return False
    try:
        camps = {c["nccCampaignId"]: c for c in get_client().list_campaigns()}
    except NaverApiError:
        return True
    return any(cid not in camps or (_budget(camps[cid]) is not None and v > _budget(camps[cid])) for _, cid, v in budgets)


def check(db: Session, ws_id: int, account_id: int, ops: list[tuple], get_client) -> dict | None:
    """ops를 실행해도 되는지. 안 되면 SafetyError(사장님용 이유). 비용이 늘 수 있는 작업(켜기·예산 증액·입찰가 올리기·새 입찰가·
    제외검색어 삭제·ADVoost 켜기)은 네이버 지금 설정을 다시 읽어 실제 입찰가와 '변경 후 켜진 캠페인 하루예산 설정액 합계 ≤ 관리 기준'을 본다.
    돌려주는 dict: 변경 후 합계·기준·최대 입찰가·통제할 수 없는 항목(uncontrolled)·과금 안내(승인 카드·미리보기에 보여 줌)."""
    if not ops:
        return None
    s = get(db, ws_id, account_id)
    check_bids(s, ops)
    notes: list[str] = []
    try:
        snap = Snapshot(get_client())
        _prefetch(snap, ops)
        increasing = False
        for op in ops:
            kind = op[0]
            if kind == "bid":
                increasing |= op[2] is None or op[1] > _current_bid(snap, op[2], op[3])  # 내리기는 합계와 상관없이 허용
                continue
            if kind == "budget":
                c = snap.camps.get(op[1])
                if c is None:
                    raise SafetyError(f"캠페인({op[1]})을 네이버에서 찾지 못해 실행하지 않았어요")
                cur = _budget(c)
                if cur is None or op[2] <= cur:
                    continue  # 예산 줄이기(또는 그대로)는 언제나 허용. 무제한 → 금액 설정도 줄이기에 해당
                c["dailyBudget"], c["useDailyBudget"] = op[2], True
            elif s is None:
                raise SafetyError(NOT_SET)
            elif kind == "on":
                _effective_on(snap, op[1], op[2], s.max_bid, notes)
                if op[1] == "campaign":
                    snap.camps[op[2]]["userLock"] = False
                elif op[1] == "adgroup":
                    snap.group(op[2])["userLock"] = False
            elif kind == "advoost":
                _group_bids(snap, {**snap.group(op[1]), "adgroupAttrJson": {"useAdvoost": True}}, s.max_bid, notes)
            increasing = True  # 키워드·소재·확장소재 켜기, 제외검색어 삭제도 광고가 더 나갈 수 있어 합계가 기준 안이어야 한다
        if not increasing:
            return {"max_bid": s.max_bid, "daily_budget_limit": s.daily_budget_limit, "note": OVERSPEND_NOTE} if s else None
        if s is None:
            raise SafetyError(NOT_SET)
        total, reasons, _ = snap.total()
    except NaverApiError as e:
        raise SafetyError(f"네이버의 지금 설정을 읽지 못해 실행하지 않았어요. 잠시 뒤 다시 해 주세요 ({str(e)[:100]})")
    if total is None:
        raise SafetyError("계정의 하루예산 설정액 합계를 정확히 계산할 수 없어 비용이 늘 수 있는 변경(광고 시작·예산 증액·입찰가 올리기)을 막았어요: "
                          + " / ".join(reasons[:3]))
    if total > s.daily_budget_limit:
        raise SafetyError(f"변경 후 켜진 캠페인의 하루예산 설정액 합계가 {total:,}원으로 이 계정의 관리 기준 {s.daily_budget_limit:,}원을 넘어요. "
                          "다른 캠페인을 끄거나 예산을 줄인 뒤 다시 해 주세요")
    return {"total_after": total, "daily_budget_limit": s.daily_budget_limit, "max_bid": s.max_bid, "uncontrolled": notes,
            "note": OVERSPEND_NOTE}


def preview(db: Session, ws_id: int, account_id: int, ops: list[tuple], get_client) -> dict:
    """check와 같지만 막는 대신 결과를 돌려준다(미리보기·승인 카드용)."""
    try:
        out = check(db, ws_id, account_id, ops, get_client) or {}
        return {"ad_account_id": account_id, "ok": True, **out, "note": OVERSPEND_NOTE}
    except SafetyError as e:
        return {"ad_account_id": account_id, "ok": False, "reason": str(e), "note": OVERSPEND_NOTE}


# ---- 계정별 실행 잠금: 같은 광고 계정의 비용 변경은 한 번에 하나만(검사 → 네이버 반영 사이에 다른 작업이 끼어 함께 통과하지 않게) ----
LOCK_LEASE = timedelta(seconds=90)  # 요청이 죽어도 이 시간이 지나면 다른 작업이 잠금을 가져간다(장애 복구)
BUSY = "같은 광고 계정에서 다른 비용 변경이 실행 중이라 겹치지 않게 실행하지 않았어요. 잠시 뒤 다시 실행해 주세요"
_T = AccountLock.__table__.c.expires_at.type
_TAKE = text("INSERT INTO account_locks (ad_account_id, holder, expires_at) VALUES (:a, :h, :e) "
             "ON CONFLICT (ad_account_id) DO UPDATE SET holder = excluded.holder, expires_at = excluded.expires_at "
             "WHERE account_locks.expires_at < :n").bindparams(bindparam("e", type_=_T), bindparam("n", type_=_T))


def take_lock(db: Session, account_id: int) -> str | None:
    """잠금을 얻으면 잠금 열쇠(holder), 다른 작업이 쥐고 있으면 None. 한 문장으로 올려 동시에 와도 하나만 얻는다."""
    holder = secrets.token_hex(8)
    db.execute(_TAKE, {"a": account_id, "h": holder, "e": now() + LOCK_LEASE, "n": now()})
    db.commit()
    return holder if db.scalar(select(AccountLock.holder).where(AccountLock.ad_account_id == account_id)) == holder else None


LOCK_LOST = "실행 중 계정 잠금 시간이 지나 다른 작업과 겹칠 수 있어 이 행은 실행하지 않았어요. 잠시 뒤 다시 실행해 주세요"


def renew_lock(db: Session, account_id: int, holder: str) -> bool:
    """내 잠금이면 임대를 다시 LOCK_LEASE만큼 늘린다. 이미 만료돼 남이 가져갔거나 풀렸으면 False(그 뒤 비용 변경은 하지 않는다)."""
    ok = db.execute(update(AccountLock).where(AccountLock.ad_account_id == account_id, AccountLock.holder == holder,
                                              AccountLock.expires_at >= now()).values(expires_at=now() + LOCK_LEASE)).rowcount == 1
    db.commit()
    return ok


def release_lock(db: Session, account_id: int, holder: str):
    db.execute(delete(AccountLock).where(AccountLock.ad_account_id == account_id, AccountLock.holder == holder))
    db.commit()


@contextmanager
def account_lock(db: Session, account_id: int):
    holder = take_lock(db, account_id)
    if holder is None:
        raise SafetyError(BUSY)
    try:
        yield
    finally:
        release_lock(db, account_id, holder)


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
            "actions": actions + (["정리될 때까지 광고 켜기·예산 증액·입찰가 올리기는 막히고, 조회와 광고 끄기는 할 수 있어요"] if actions else [])}


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
