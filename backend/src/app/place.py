"""플레이스광고(네이버 지도·플레이스 검색에 나오는 광고, 광고그룹 유형 LOCAL_AD) 조회와 변경.
웹(/workspaces/{ws}/place...)과 Claude(place_ads_* 도구)가 같은 함수를 쓴다. 파워링크·쇼핑 코드와 따로 둬서 서로 건드리지 않는다.

변경은 두 단계다. plan이 권한·상한·ADVoost 규칙을 검사하고 대상·전후 값·최대 지출을 approval_requests에 저장한다.
apply는 그 요청을 만든 사람이, 같은 내용(해시 비교)으로, 15분 안에, 한 번만 실행할 수 있고 실행 직전에 권한·규칙을 다시 검사한다.
요청 형식 근거와 미확인 항목은 docs/PLACE_ADS_MAINTENANCE.md."""
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from . import bulk, safety
from .access import membership, resolve_account_ids
from .db import get_db
from .models import KST, ApprovalRequest, AuditLog, Membership, now, today_kst
from .naver import NaverApiError, RealNaverClient, _json, advoost_on

router = APIRouter()

# 서버가 강제하는 상한(작은 가게 기준). 운영에서 바꾸려면 Cloudflare 환경변수 PLACE_DAILY_BUDGET_MAX·PLACE_BID_MAX
BUDGET_MIN = 1_000
BUDGET_MAX = int(os.getenv("PLACE_DAILY_BUDGET_MAX", "100000"))
BID_MIN = 50  # shortcut: 플레이스 최소 입찰가는 공식 문서에서 확인 못 함(네이버 화면 기준 50원), 거부되면 이 값 조정
BID_MAX = int(os.getenv("PLACE_BID_MAX", "5000"))
APPROVAL_TTL = timedelta(minutes=15)
WEB_APPROVAL_TTL = timedelta(minutes=30)  # 웹 승인은 사장님이 웹을 열어 볼 시간이 필요하다(approvals.APPROVAL_TTL과 같게)
DETAIL_GROUPS = 15  # 상태 조회에서 소재·제외검색어까지 읽는 광고그룹 수(무료 플랜 요청당 외부 호출 50번 한도)

NOTICE = ("광고가 바로 나가는 것은 아니에요. 새로 만든 광고는 꺼진 상태로 만들어지고, 네이버 검토를 통과한 뒤 켜야 노출돼요. "
          "설정은 네이버에 바로 저장되지만 노출과 성과 숫자는 늦게 반영돼요(이 화면의 성과는 어제까지).")

# 네이버 오류 코드 → 사장님용 설명. 근거: 2026-09-16 릴리스 노트(ADVoost 플레이스)
FRIENDLY = {
    3752: "스마트플레이스에 업체 사진이 한 장도 없어 ADVoost를 켤 수 없어요. 스마트플레이스에 사진을 올린 뒤 다시 해 주세요.",
    3753: "네이버가 업체 정보를 불러오지 못했어요. 잠시 뒤 다시 해 주세요.",
    3754: "ADVoost가 켜진 광고그룹에는 제외검색어를 등록할 수 없어요. ADVoost가 노출할 검색어를 알아서 고릅니다.",
    3755: "ADVoost가 켜진 광고그룹은 입찰가를 직접 바꿀 수 없어요. 하루예산만 정하면 ADVoost가 알아서 조절해요.",
    3756: "병원·의원 업종은 ADVoost 플레이스를 쓸 수 없어요. 일반 플레이스광고로 진행해 주세요.",
    3837: "ADVoost가 켜진 동안에는 자동으로 만들어진 광고를 지울 수 없어요.",
    3838: "ADVoost가 자동으로 만든 광고는 따로 켜고 끌 수 없어요. 광고그룹의 ADVoost 설정을 켜거나 꺼 주세요.",
    3839: "ADVoost가 켜진 광고그룹에는 광고(소재)를 직접 추가할 수 없어요. 광고 내용은 스마트플레이스 업체 정보로 자동으로 만들어져요.",
    3840: "ADVoost 광고는 네이버가 자동으로 만들어요. 직접 만들 수 없어요.",
    4029: "ADVoost가 켜진 광고그룹에는 확장소재를 추가할 수 없어요.",
    4420: "ADVoost가 켜진 광고그룹은 노출 매체를 바꿀 수 없어요.",
    4422: "ADVoost가 켜진 광고그룹에는 제외검색어를 등록할 수 없어요.",
    5117: "ADVoost가 켜진 광고그룹은 지역·연령·성별 등 노출 대상을 바꿀 수 없어요.",
}

Action = Literal["create", "set_budget", "set_bid", "turn_on", "turn_off", "set_advoost", "add_negative_keyword", "remove_negative_keyword"]
ACTION_LABEL = {"create": "플레이스광고 새로 만들기", "set_budget": "하루예산 바꾸기", "set_bid": "입찰가 바꾸기", "turn_on": "광고 켜기",
                "turn_off": "광고 끄기", "set_advoost": "ADVoost 켜기/끄기", "add_negative_keyword": "제외검색어 추가",
                "remove_negative_keyword": "제외검색어 삭제"}
# 액션별 입력값: (타입, 필수)
PARAMS = {
    "create": {"business_id": (str, True), "daily_budget": (int, True), "use_advoost": (bool, True), "bid": (int, False), "ad_text": (str, False)},
    "set_budget": {"campaign_id": (str, True), "daily_budget": (int, True)},
    "set_bid": {"adgroup_id": (str, True), "bid": (int, True)},
    "turn_on": {"target_type": (str, True), "target_id": (str, True)},
    "turn_off": {"target_type": (str, True), "target_id": (str, True)},
    "set_advoost": {"adgroup_id": (str, True), "on": (bool, True)},
    "add_negative_keyword": {"adgroup_id": (str, True), "keyword": (str, True)},
    "remove_negative_keyword": {"adgroup_id": (str, True), "keyword_id": (str, True)},
}


class PlaceChange(BaseModel):
    ad_account_id: int
    action: Action
    params: dict = {}


class PlaceApply(BaseModel):
    approval_id: int
    change: PlaceChange


def friendly(err: Exception | str) -> str:
    if str(err).startswith("네트워크 오류"):  # 응답을 못 받으면 반영됐을 수 있다 → 다시 하기 전에 확인하게
        return "네이버 응답을 받지 못해 반영됐는지 알 수 없어요. 다시 하기 전에 네이버 광고관리에서 먼저 확인해 주세요"
    m = re.search(r'"code"\s*:\s*(\d+)', str(err))
    code = int(m.group(1)) if m else None
    return f"{FRIENDLY[code]} (네이버 오류 {code})" if code in FRIENDLY else f"네이버가 요청을 받아들이지 않았어요: {str(err)[:200]}"


def _block(code: int):
    """네이버가 거부할 것을 알고 있는 작업은 호출하기 전에 막는다(같은 설명 + 네이버 규칙 번호)."""
    raise HTTPException(400, f"{FRIENDLY[code]} (네이버 규칙 {code})")


def _norm(action: str, params: dict) -> dict:
    """허용한 입력값만 정해진 타입으로. 승인 해시는 이 결과로 계산하므로 모르는 값을 끼워 넣어도 실행 내용은 바뀌지 않는다."""
    out = {}
    for key, (typ, required) in PARAMS[action].items():
        v = params.get(key)
        if v is None or v == "":
            if required:
                raise HTTPException(400, f"{key} 값이 필요합니다")
            continue
        if typ is bool:
            if not isinstance(v, bool) and str(v).lower() not in ("true", "false"):
                raise HTTPException(400, f"{key}는 true 또는 false")
            v = v if isinstance(v, bool) else str(v).lower() == "true"
        elif typ is int:
            if isinstance(v, bool) or not str(v).strip().isdigit():
                raise HTTPException(400, f"{key}는 숫자(원)로 넣어 주세요")
            v = int(str(v).strip())
        else:
            v = str(v).strip()[:200]
        out[key] = v
    if out.get("target_type") not in (None, "campaign", "adgroup", "ad"):
        raise HTTPException(400, "target_type은 campaign·adgroup·ad 중 하나")
    return out


def _canonical(account_id: int, action: str, params: dict) -> str:
    return json.dumps({"ad_account_id": account_id, "action": action, "params": params}, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _won(v) -> str:
    return "없음" if v is None else f"{v:,}원"


def _check_budget(v: int):
    if not BUDGET_MIN <= v <= BUDGET_MAX or v % 10:
        raise HTTPException(400, f"하루예산은 {BUDGET_MIN:,}~{BUDGET_MAX:,}원, 10원 단위로 정해 주세요")


def _check_bid(v: int):
    if not BID_MIN <= v <= BID_MAX or v % 10:
        raise HTTPException(400, f"입찰가(클릭 한 번에 낼 최대 금액)는 {BID_MIN:,}~{BID_MAX:,}원, 10원 단위로 정해 주세요")


def _budget(c: dict) -> int | None:
    return c.get("dailyBudget") if c.get("useDailyBudget", True) and c.get("dailyBudget") else None


def _one(client, kind: str, nid: str, label: str) -> dict:
    found = client.get_many(kind, [nid])
    if not found:
        raise HTTPException(404, f"{label}을(를) 찾을 수 없어요 ({nid})")
    return found[0]


def _place_group(client, gid: str) -> dict:
    g = _one(client, "adgroups", gid, "광고그룹")
    if g.get("adgroupType") != "LOCAL_AD":
        raise HTTPException(400, "플레이스광고 광고그룹이 아니에요. 파워링크·쇼핑 광고는 다른 메뉴에서 바꿔 주세요")
    return g


def _place_campaign(client, cid: str) -> dict:
    c = _one(client, "campaigns", cid, "캠페인")
    if c.get("campaignTp") != "PLACE":
        raise HTTPException(400, "플레이스광고 캠페인이 아니에요. 파워링크·쇼핑 광고는 다른 메뉴에서 바꿔 주세요")
    return c


def _guard(db: Session, ws_id: int, account_id: int, client, ops: list[tuple]) -> dict:
    """계정 광고비 안전장치(safety.py): 네이버 지금 값으로 변경 후 하루예산 설정액 합계·최대 입찰가를 검사한다."""
    try:
        out = safety.check(db, ws_id, account_id, ops, lambda: client) or {}
    except safety.SafetyError as e:
        raise HTTPException(400, str(e))
    sf = safety.get(db, ws_id, account_id)
    return {**out, "daily_budget_limit": sf and sf.daily_budget_limit, "max_bid": sf and sf.max_bid, "note": safety.OVERSPEND_NOTE}


def _inspect(client, action: str, p: dict, guard, check_caps) -> dict:
    """현재 값을 네이버에서 읽어 규칙을 검사하고 사장님이 볼 요약(대상·전후·최대 지출·계정 안전장치·웹 승인 필요 여부)을 만든다.
    막아야 하면 HTTPException. increases: 이 변경으로 지출이 늘 수 있는지(안내 문구를 정한다)."""
    s = {"action": action, "label": ACTION_LABEL[action], "notes": []}
    ops: list[tuple] = []
    increases = False
    if action == "create":
        _check_budget(p["daily_budget"])
        ch = next((c for c in client.list_channels() if c["nccBusinessChannelId"] == p["business_id"]), None)
        if ch is None or ch.get("channelTp") != "PLACE":
            raise HTTPException(400, "선택한 업체가 이 광고 계정의 플레이스 업체(비즈채널)가 아니에요")
        if p["use_advoost"]:
            if "bid" in p:
                raise HTTPException(400, "ADVoost를 켜면 입찰가를 정하지 않아요(ADVoost가 알아서 조절). 입찰가를 비워 주세요")
            if "ad_text" in p:
                raise HTTPException(400, "ADVoost 광고 내용은 스마트플레이스 업체 정보로 자동으로 만들어져요. 광고 문구를 비워 주세요")
        else:
            if "bid" not in p:
                raise HTTPException(400, "일반 플레이스광고는 입찰가(클릭 한 번에 낼 최대 금액)가 필요해요")
            _check_bid(p["bid"])
            check_caps(("bid", p["bid"], None, None))  # 꺼진 상태로 만들어지므로 합계는 켤 때 검사, 입찰가 상한만 지금
            if isinstance(client, RealNaverClient) and os.getenv("NAVER_ALLOW_REAL_WRITE") != "1":
                raise HTTPException(400, "일반 플레이스광고 소재는 네이버 요청 형식이 확인되지 않아 아직 여기서 만들 수 없어요. "
                                         "ADVoost로 만들거나 네이버 광고관리에서 만들어 주세요")
        if ch.get("inspectStatus") not in (None, "", "APPROVED"):
            s["notes"].append("이 업체는 네이버 검토가 끝나지 않았어요. 검토가 끝나야 광고가 나갈 수 있어요.")
        s.update(target=f"업체 '{ch.get('name', '')}'", before="광고 없음",
                 after=("ADVoost 플레이스 (광고 내용·입찰가 자동)" if p["use_advoost"] else f"일반 플레이스광고, 입찰가 {_won(p['bid'])}")
                 + f", 하루예산 {_won(p['daily_budget'])}, 꺼진 상태로 만듦",
                 max_daily=p["daily_budget"])
        s["notes"].append("만든 뒤 바로 노출되지 않아요. 네이버 검토 후 '광고 켜기'를 해야 나가요.")
    elif action == "set_budget":
        _check_budget(p["daily_budget"])
        c = _place_campaign(client, p["campaign_id"])
        s.update(target=f"캠페인 '{c['name']}'", before=f"하루예산 {_won(_budget(c))}", after=f"하루예산 {_won(p['daily_budget'])}",
                 max_daily=p["daily_budget"])
        ops.append(("budget", c["nccCampaignId"], p["daily_budget"]))
        increases = _budget(c) is not None and p["daily_budget"] > _budget(c)
    elif action == "set_bid":
        _check_bid(p["bid"])
        g = _place_group(client, p["adgroup_id"])
        if advoost_on(g):
            _block(3755)
        camp = _place_campaign(client, g["nccCampaignId"])
        s.update(target=f"광고그룹 '{g['name']}'", before=f"입찰가 {_won(g.get('bidAmt'))}", after=f"입찰가 {_won(p['bid'])}",
                 max_daily=_budget(camp))
        ops.append(("bid", p["bid"], "adgroup", g["nccAdgroupId"]))
        increases = p["bid"] > (g.get("bidAmt") or 0)
        if increases:
            s["notes"].append("입찰가를 올리면 클릭 한 번 비용이 늘고 같은 하루예산을 더 빨리 쓸 수 있어요.")
    elif action in ("turn_on", "turn_off"):
        on = action == "turn_on"
        tt, tid = p["target_type"], p["target_id"]
        if tt == "campaign":
            camp = _place_campaign(client, tid)
            obj, name = camp, f"캠페인 '{camp['name']}'"
        else:
            if tt == "ad":
                ad = _one(client, "ads", tid, "광고(소재)")
                if ad.get("type") == "ADVOOST_PLACE_AD":
                    _block(3838)
                g = _place_group(client, ad["nccAdgroupId"])
                obj, name = ad, f"광고그룹 '{g['name']}'의 광고(소재)"
            else:
                g = _place_group(client, tid)
                obj, name = g, f"광고그룹 '{g['name']}'"
            camp = _place_campaign(client, g["nccCampaignId"])
        s.update(target=name, before="꺼짐" if obj.get("userLock") else "켜짐", after="켜짐" if on else "꺼짐",
                 max_daily=_budget(camp) if on else None)
        if on:
            ops.append(("on", tt, tid))
            increases = True
            s["notes"].append("켜도 네이버 검토 중이면 검토가 끝난 뒤에 노출돼요.")
    elif action == "set_advoost":
        g = _place_group(client, p["adgroup_id"])
        camp = _place_campaign(client, g["nccCampaignId"])
        s.update(target=f"광고그룹 '{g['name']}'", before="ADVoost 켜짐" if advoost_on(g) else "ADVoost 꺼짐",
                 after="ADVoost 켜짐" if p["on"] else "ADVoost 꺼짐", max_daily=_budget(camp) if p["on"] else None)
        if p["on"]:
            ops.append(("advoost", g["nccAdgroupId"]))
            increases = True
        s["notes"].append("ADVoost를 켜면 네이버가 업체 정보로 광고를 자동으로 만들고 입찰가·검색어를 알아서 조절해요. "
                          "켜져 있는 동안은 입찰가 변경·제외검색어 등록·광고 직접 추가를 할 수 없어요." if p["on"] else
                          "ADVoost를 끄면 자동으로 만든 광고는 지워지지 않고 꺼져요. 입찰가를 직접 정해 주세요.")
    elif action == "add_negative_keyword":
        g = _place_group(client, p["adgroup_id"])
        if advoost_on(g):
            _block(3754)
        s.update(target=f"광고그룹 '{g['name']}'", before="-", after=f"'{p['keyword']}' 검색에는 광고를 보여 주지 않음", max_daily=None)
    elif action == "remove_negative_keyword":
        g = _place_group(client, p["adgroup_id"])
        kw = next((k for k in client.list_restricted_keywords(g["nccAdgroupId"])
                   if k.get("nccAdgroupRestrictKwdId") == p["keyword_id"]), None)
        if kw is None:
            raise HTTPException(404, "이 광고그룹에 그 제외검색어가 없어요")
        s.update(target=f"광고그룹 '{g['name']}'", before=f"'{kw['keyword']}' 검색 제외", after="제외 해제",
                 max_daily=_budget(_place_campaign(client, g["nccCampaignId"])))
        ops.append(("expose",))
        increases = True
    s["safety"] = guard(ops)
    s["web_required"] = safety.web_approval_needed(ops, lambda: client)
    s["max_daily_spend"] = s.pop("max_daily")
    s["max_monthly_spend"] = s["max_daily_spend"] * 31 if s["max_daily_spend"] else None
    if action == "create":
        s["spend_text"] = f"꺼진 상태로 만들어 지금은 지출이 없어요. 켜면 캠페인 하루예산 설정액 {_won(p['daily_budget'])}까지 쓸 수 있어요"
    elif not increases:
        s["spend_text"] = "이 변경으로 지출이 늘지 않아요"
    elif s["max_daily_spend"]:
        s["spend_text"] = f"지출이 늘 수 있어요. 캠페인 하루예산 설정액 {_won(s['max_daily_spend'])} (31일이면 {_won(s['max_monthly_spend'])})"
    else:  # 하루예산 설정액이 없으면 이 화면이 하루 최대 지출을 말할 수 없다
        s["spend_text"] = "지출이 늘 수 있어요. 캠페인에 하루예산이 없어 하루 최대 지출을 정할 수 없어요"
    if s["safety"].get("total_after") is not None:
        s["spend_text"] += (f" · 변경 후 계정 하루예산 설정액 합계 {_won(s['safety']['total_after'])}"
                            f" (관리 기준 {_won(s['safety']['daily_budget_limit'])})")
    s["notes"].append(safety.OVERSPEND_NOTE)
    return s


def _audit(db, m, account_id, action, naver_id, field, before=None, after=None, entity="place"):
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=account_id, action=action, entity_type=entity,
                    naver_id=naver_id, field=field, before=None if before is None else str(before)[:50],
                    after=None if after is None else str(after)[:50]))


def _run(db, m, client, account_id: int, action: str, p: dict) -> list[dict]:
    """실제 변경. 단계별 결과를 돌려준다(앞 단계가 실패하면 뒤 단계는 하지 않음)."""
    steps = []

    def step(label, fn):
        if steps and not steps[-1]["ok"]:
            return None
        try:
            out = fn()
            steps.append({"step": label, "ok": True})
            return out
        except NaverApiError as e:
            steps.append({"step": label, "ok": False, "error": friendly(e)})
            return None

    if action == "create":
        ch = next(c for c in client.list_channels() if c["nccBusinessChannelId"] == p["business_id"])
        name = f"플레이스 {ch.get('name', '')[:20]} {datetime.now(KST):%m%d-%H%M}"
        camp = step("캠페인 만들기(꺼진 상태)", lambda: client.create_campaign("PLACE", name, p["daily_budget"]))
        if camp:
            _audit(db, m, account_id, "CREATE", camp["nccCampaignId"], "campaign", after=f"PLACE {p['daily_budget']}")
        grp = step("광고그룹 만들기(꺼진 상태)", lambda: client.create_place_adgroup(
            camp["nccCampaignId"], name, p["business_id"], p.get("bid"), p["use_advoost"])) if camp else None
        if grp:
            _audit(db, m, account_id, "CREATE", grp["nccAdgroupId"], "adgroup", after="ADVoost" if p["use_advoost"] else f"bid {p['bid']}")
        if grp and not p["use_advoost"]:
            ad = step("광고(소재) 만들기", lambda: client.create_place_ad(grp["nccAdgroupId"], ch.get("channelKey", ""),
                                                                    p.get("ad_text") or ch.get("name", "")))
            if ad:
                _audit(db, m, account_id, "CREATE", ad["nccAdId"], "ad", after="LOCAL_AD")
    elif action == "set_budget":
        if step("하루예산 바꾸기", lambda: client.update("campaign", p["campaign_id"], "daily_budget", str(p["daily_budget"])) or True):
            _audit(db, m, account_id, "UPDATE", p["campaign_id"], "daily_budget", after=p["daily_budget"])
    elif action == "set_bid":
        if step("입찰가 바꾸기", lambda: client.update("adgroup", p["adgroup_id"], "bid_amt", str(p["bid"])) or True):
            _audit(db, m, account_id, "UPDATE", p["adgroup_id"], "bid_amt", after=p["bid"])
    elif action in ("turn_on", "turn_off"):
        v = "ON" if action == "turn_on" else "OFF"
        if step(ACTION_LABEL[action], lambda: client.update(p["target_type"], p["target_id"], "status", v) or True):
            _audit(db, m, account_id, "UPDATE", p["target_id"], "status", after=v)
    elif action == "set_advoost":
        if step(ACTION_LABEL[action], lambda: client.set_advoost(p["adgroup_id"], p["on"]) or True):
            _audit(db, m, account_id, "UPDATE", p["adgroup_id"], "advoost", after="ON" if p["on"] else "OFF")
    elif action == "add_negative_keyword":
        k = step("제외검색어 추가", lambda: client.create_restricted_keyword(p["adgroup_id"], p["keyword"]))
        if k:
            _audit(db, m, account_id, "CREATE", p["adgroup_id"], "negative_kw", after=p["keyword"])
    elif action == "remove_negative_keyword":
        if step("제외검색어 삭제", lambda: client.delete_restricted_keyword(p["adgroup_id"], p["keyword_id"]) or True):
            _audit(db, m, account_id, "DELETE", p["adgroup_id"], "negative_kw", before=p["keyword_id"])
    return steps


def plan(db: Session, m: Membership, change: PlaceChange) -> dict:
    bulk._check_edit(db, m, change.ad_account_id)
    p = _norm(change.action, change.params)
    client = bulk._client(db, m.workspace_id, change.ad_account_id)
    try:
        summary = _inspect(client, change.action, p, *_checks(db, m.workspace_id, change.ad_account_id, client))
    except NaverApiError as e:
        raise HTTPException(400, friendly(e))
    payload = _canonical(change.ad_account_id, change.action, p)
    ttl = WEB_APPROVAL_TTL if summary["web_required"] else APPROVAL_TTL
    ar = ApprovalRequest(workspace_id=m.workspace_id, requested_by=m.user_id, tool=f"place:{change.action}"[:40], payload=payload,
                         payload_hash=hashlib.sha256(payload.encode()).hexdigest(), status="PENDING", expires_at=now() + ttl,
                         kind="place", ad_account_id=change.ad_account_id, web_required=summary["web_required"],
                         summary=json.dumps(summary, ensure_ascii=False, default=str))
    db.add(ar)
    db.flush()
    _audit_approval(db, m, ar, change.ad_account_id, "APPROVAL_PENDING")
    db.commit()
    out = {"approval_id": ar.id, "expires_in_minutes": int(ttl.total_seconds() // 60), "summary": summary}
    if summary["web_required"]:
        from .approvals import url  # approvals가 이 모듈을 불러 쓰므로 여기서
        return {**out, "web_required": True, "approve_url": url(ar),
                "how_to_apply": f"계정 하루예산 합계가 늘 수 있는 변경이라 사장님이 웹에서 직접 승인해야 실행돼요: {url(ar)} "
                                "(Claude는 승인·적용할 수 없어요). 승인하면 그 자리에서 실행되고 결과가 화면에 나와요."}
    return {**out, "how_to_apply": "이 내용을 사장님께 보여 주고 승인받은 뒤, 같은 change와 approval_id로 적용하세요."}


def _checks(db: Session, ws_id: int, account_id: int, client):
    """_inspect에 넘기는 검사 두 개: 안전장치 전체(네이버 다시 읽음), 입찰가 상한만."""
    return (lambda ops: _guard(db, ws_id, account_id, client, ops),
            lambda *ops: _caps(db, ws_id, account_id, list(ops)))


def _caps(db: Session, ws_id: int, account_id: int, ops: list[tuple]):
    try:
        safety.check_bids(safety.get(db, ws_id, account_id), ops)
    except safety.SafetyError as e:
        raise HTTPException(400, str(e))


def _audit_approval(db, m, ar: ApprovalRequest, account_id: int | None, action: str, after: str | None = None):
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=account_id, action=action, entity_type="approval",
                    naver_id=str(ar.id), field=ar.tool[6:26], after=after and after[:50]))


def _aware(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)  # SQLite는 시간대 없이 돌려준다


def apply(db: Session, m: Membership, approval_id: int, change: PlaceChange) -> dict:
    ar = db.get(ApprovalRequest, approval_id)
    if ar is None or ar.workspace_id != m.workspace_id or ar.requested_by != m.user_id or not ar.tool.startswith("place:"):
        raise HTTPException(404, "승인 요청을 찾을 수 없어요. 계획부터 다시 만들어 주세요")
    p = _norm(change.action, change.params)
    payload = _canonical(change.ad_account_id, change.action, p)
    if hashlib.sha256(payload.encode()).hexdigest() != ar.payload_hash:
        raise HTTPException(409, "승인한 내용과 실행하려는 내용이 달라요. 계획부터 다시 만들어 주세요")
    if ar.web_required:  # 계정 합계가 늘 수 있는 변경은 웹 승인 화면에서만 실행된다(Claude·이 경로로는 불가)
        from .approvals import url
        raise HTTPException(403, f"이 변경은 사장님이 웹 승인 화면에서 직접 승인해야 실행돼요: {url(ar)}")
    if ar.status == "PENDING" and _aware(ar.expires_at) < now():
        ar.status = "EXPIRED"
        _audit_approval(db, m, ar, change.ad_account_id, "APPROVAL_EXPIRED")
        db.commit()
        raise HTTPException(410, "승인한 지 15분이 지났어요. 계획부터 다시 만들어 주세요")
    # 한 번만 실행: PENDING → RUNNING을 한 문장으로 바꿔 동시에 두 번 눌러도 하나만 지나간다
    claimed = db.execute(update(ApprovalRequest).where(ApprovalRequest.id == ar.id, ApprovalRequest.status == "PENDING")
                         .values(status="RUNNING", decided_by=m.user_id, decided_at=now())).rowcount
    db.commit()
    if claimed != 1:
        raise HTTPException(409, "이미 실행했거나 실행 중인 요청이에요. 다시 하려면 계획부터 새로 만들어 주세요")
    db.refresh(ar)
    return _execute(db, m, ar, change)


def _execute(db: Session, m: Membership, ar: ApprovalRequest, change: PlaceChange) -> dict:
    """RUNNING으로 잡은 승인 요청을 실행한다(Claude 적용·웹 승인 공통). 계정 잠금 안에서 권한·네이버 지금 값·안전장치를 다시 검사하고,
    승인 때 보여 준 변경 전 값과 지금 값이 다르면 실행하지 않는다."""
    p = _norm(change.action, change.params)

    def finish(status, steps, error=None):
        ar.status, ar.result = {"SUCCESS": "DONE"}.get(status, status), json.dumps({"steps": steps, "error": error}, ensure_ascii=False)[:2000]
        _audit_approval(db, m, ar, change.ad_account_id, f"APPROVAL_{status}", error)
        db.commit()
        return {"status": status, "steps": steps, "error": error, "notice": NOTICE if status != "FAILED" else None}

    try:  # 승인 뒤 권한·상태가 바뀌었을 수 있어 실행 직전에 다시 검사한다
        bulk._check_edit(db, m, change.ad_account_id)
        client = bulk._client(db, m.workspace_id, change.ad_account_id)
        with safety.account_lock(db, change.ad_account_id):
            fresh = _inspect(client, change.action, p, *_checks(db, m.workspace_id, change.ad_account_id, client))
            shown = json.loads(ar.summary).get("before") if ar.summary else fresh.get("before")
            if shown != fresh.get("before"):
                return finish("FAILED", [], f"승인 때와 네이버의 지금 값이 달라 실행하지 않았어요(승인 때 {shown}, 지금 {fresh.get('before')}). "
                                            "계획부터 다시 만들어 주세요")
            steps = _run(db, m, client, change.ad_account_id, change.action, p)
    except safety.SafetyError as e:
        return finish("FAILED", [], str(e))
    except HTTPException as e:
        return finish("FAILED", [], e.detail)
    except NaverApiError as e:
        return finish("FAILED", [], friendly(e))
    ok = sum(s["ok"] for s in steps)
    return finish("SUCCESS" if ok == len(steps) else "PARTIAL" if ok else "FAILED", steps)


def cancel(db: Session, m: Membership, approval_id: int) -> dict:
    """사장님이 승인하지 않음(취소). 대기 중인 요청만, 만든 사람만."""
    ar = db.get(ApprovalRequest, approval_id)
    if ar is None or ar.workspace_id != m.workspace_id or ar.requested_by != m.user_id or not ar.tool.startswith("place:"):
        raise HTTPException(404, "승인 요청을 찾을 수 없어요")
    if db.execute(update(ApprovalRequest).where(ApprovalRequest.id == ar.id, ApprovalRequest.status == "PENDING")
                  .values(status="REJECTED", decided_by=m.user_id, decided_at=now())).rowcount != 1:
        raise HTTPException(409, "이미 실행했거나 취소한 요청이에요")
    _audit_approval(db, m, ar, json.loads(ar.payload)["ad_account_id"], "APPROVAL_REJECTED")
    db.commit()
    return {"status": "REJECTED"}


def overview(db: Session, m: Membership, account_id: int) -> dict:
    """업체·캠페인·광고그룹(ADVoost 여부)·소재·제외검색어·지난 7일 성과. 네이버에서 바로 읽는다."""
    resolve_account_ids(db, m, [account_id])
    client = bulk._client(db, m.workspace_id, account_id)
    try:
        businesses = [{"id": c["nccBusinessChannelId"], "name": c.get("name", ""), "place_id": c.get("channelKey", ""),
                       "review": c.get("inspectStatus", "")} for c in client.list_channels() if c.get("channelTp") == "PLACE"]
        camps = [c for c in client.list_campaigns() if c.get("campaignTp") == "PLACE"]
        out, n = [], 0
        for c in camps:
            groups = []
            for g in client.list_adgroups(c["nccCampaignId"]):
                if g.get("adgroupType") != "LOCAL_AD":
                    continue
                adv = advoost_on(g)
                row = {"id": g["nccAdgroupId"], "name": g["name"], "on": not g.get("userLock"), "advoost": adv,
                       "bid": None if adv else g.get("bidAmt"), "serving": g.get("statusReason") or g.get("status"), "ads": None,
                       "negative_keywords": None}
                n += 1
                if n <= DETAIL_GROUPS:
                    row["ads"] = [{"id": a["nccAdId"], "type": a["type"], "linked": a["type"] == "ADVOOST_PLACE_AD", "on": not a.get("userLock"),
                                   "review": a.get("inspectStatus", ""), "text": _json(a.get("ad")).get("description", "")}
                                  for a in client.list_ads(g["nccAdgroupId"])]
                    row["negative_keywords"] = [] if adv else [{"id": k["nccAdgroupRestrictKwdId"], "keyword": k["keyword"]}
                                                               for k in client.list_restricted_keywords(g["nccAdgroupId"])]
                groups.append(row)
            out.append({"id": c["nccCampaignId"], "name": c["name"], "on": not c.get("userLock"), "daily_budget": _budget(c), "groups": groups})
        until = today_kst() - timedelta(days=1)
        ids = [c["id"] for c in out]
        stats = client.entity_stats(ids, until - timedelta(days=6), until) if ids else {}
    except NaverApiError as e:
        raise HTTPException(400, friendly(e))
    for c in out:
        x = stats.get(c["id"], {})
        c["last_7_days"] = {"impressions": x.get("impCnt", 0), "clicks": x.get("clkCnt", 0), "cost": x.get("salesAmt", 0)}
    return {"businesses": businesses, "campaigns": out, "limits": {"daily_budget": [BUDGET_MIN, BUDGET_MAX], "bid": [BID_MIN, BID_MAX]},
            "stats_until": until.isoformat(), "notice": NOTICE,
            "partial": n > DETAIL_GROUPS and f"광고그룹이 많아 앞의 {DETAIL_GROUPS}개만 광고·제외검색어를 읽었어요"}


@router.get("/workspaces/{ws_id}/place")
async def get_place(ad_account_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return overview(db, m, ad_account_id)


@router.post("/workspaces/{ws_id}/place/plan")
async def post_plan(body: PlaceChange, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return plan(db, m, body)


class PlaceCancel(BaseModel):
    approval_id: int


@router.post("/workspaces/{ws_id}/place/cancel")
async def post_cancel(body: PlaceCancel, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return cancel(db, m, body.approval_id)


@router.post("/workspaces/{ws_id}/place/apply")
async def post_apply(body: PlaceApply, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return apply(db, m, body.approval_id, body.change)


_WS = {"workspace_id": {"type": "integer", "description": "조직 ID (list_ad_accounts 결과)"},
       "ad_account_id": {"type": "integer", "description": "광고 계정 ID (list_ad_accounts 결과의 id)"}}
_CHANGE = {
    "action": {"type": "string", "enum": list(PARAMS), "description":
               "create=새로 만들기(업체·하루예산·ADVoost 여부), set_budget=하루예산 바꾸기, set_bid=입찰가 바꾸기(ADVoost 그룹은 불가), "
               "turn_on/turn_off=켜기/끄기, set_advoost=ADVoost 켜기/끄기, add_negative_keyword/remove_negative_keyword=제외검색어"},
    "params": {"type": "object", "description":
               "create: business_id(place_ads_status의 businesses[].id), daily_budget(원), use_advoost(true 권장: 광고 문구·입찰가를 네이버가 알아서), "
               "bid(일반일 때만, 클릭당 최대 원), ad_text(일반일 때만) / set_budget: campaign_id, daily_budget / set_bid: adgroup_id, bid / "
               "turn_on·turn_off: target_type(campaign|adgroup|ad), target_id / set_advoost: adgroup_id, on / "
               "add_negative_keyword: adgroup_id, keyword / remove_negative_keyword: adgroup_id, keyword_id"},
}
TOOLS = [
    {"name": "place_ads_status", "description":
     "사장님 가게의 플레이스광고(네이버 지도·플레이스 검색 결과에 '광고'로 나오는 가게 광고) 현재 상태. 광고할 수 있는 업체 목록, 캠페인별 켜짐/꺼짐·하루예산, "
     "광고그룹별 ADVoost 사용 여부·입찰가, 광고(소재)·검토 상태, 제외검색어, 지난 7일 노출·클릭·비용을 돌려준다. "
     "'우리 가게 광고 어떻게 되고 있어?', '하루 1만 원으로 가게 알리고 싶어' 같은 요청을 받으면 먼저 이걸 부른다. 읽기만 한다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id"], "properties": _WS}},
    {"name": "place_ads_plan", "description":
     "플레이스광고를 바꾸기 전에 계획(미리보기)을 만든다. 아직 네이버에 아무것도 바뀌지 않는다. 결과의 summary(대상·지금 값→바뀔 값·하루/한 달 최대 지출·주의)를 "
     "채팅에 쉬운 말과 표로 보여 주고 사장님이 좋다고 하면 place_ads_apply를 부른다. 사장님 말 해석 예: "
     "'하루 1만 원으로 가게 알리고 싶어' → 업체가 하나면 create(daily_budget=10000, use_advoost=true), 여러 개면 어느 가게인지 물어본다. "
     "'광고 잠깐 멈춰' → turn_off. '예산 2만 원으로 올려' → set_budget. 하루예산은 1,000~100,000원, 입찰가는 50~5,000원(서버 상한). "
     "ADVoost가 켜진 그룹은 입찰가 변경·제외검색어·광고 직접 추가가 막혀 있다(오류에 이유가 나온다).",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "action", "params"], "properties": {**_WS, **_CHANGE}}},
    {"name": "place_ads_apply", "description":
     "place_ads_plan으로 만든 계획을 네이버에 실제로 적용한다. 계획 결과에 web_required가 true면(예산 올리기·캠페인/광고그룹 켜기·ADVoost 켜기) "
     "이 도구로는 적용되지 않으니 approve_url을 사장님께 알려 웹에서 승인받게 하고 get_approval로 결과를 확인한다. "
     "그 밖에는 계획과 똑같은 ad_account_id·action·params와 approval_id를 넣어야 하며 "
     "(하나라도 다르면 거부), 같은 계획은 한 번만, 15분 안에만 적용된다. 결과 status는 SUCCESS(모두 성공)·PARTIAL(일부만 성공)·FAILED. "
     "적용돼도 광고가 바로 노출된다고 말하지 말고 notice(검토·반영 지연)를 함께 전한다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "approval_id", "ad_account_id", "action", "params"],
                     "properties": {**_WS, "approval_id": {"type": "integer", "description": "place_ads_plan 결과의 approval_id"}, **_CHANGE}},
     "annotations": {"destructiveHint": True}},
    {"name": "place_ads_cancel", "description": "사장님이 계획을 승인하지 않거나 바꾸고 싶어 하면 그 계획(approval_id)을 취소한다. 기록에 '거절'로 남는다. "
     "고치고 싶다면 취소한 뒤 바뀐 내용으로 place_ads_plan을 다시 부른다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "approval_id"],
                     "properties": {"workspace_id": _WS["workspace_id"], "approval_id": {"type": "integer"}}}},
]


def call_tool(db, m: Membership, name: str, a: dict):
    if name == "place_ads_cancel":
        return cancel(db, m, int(a["approval_id"]))
    change = PlaceChange(ad_account_id=int(a["ad_account_id"]), action=a["action"], params=a.get("params") or {}) if name != "place_ads_status" else None
    if name == "place_ads_status":
        return overview(db, m, int(a["ad_account_id"]))
    if name == "place_ads_plan":
        return plan(db, m, change)
    return apply(db, m, int(a["approval_id"]), change)
