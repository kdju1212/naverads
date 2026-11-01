"""플레이스광고(place.py): 일반/ADVoost 허용·금지 작업, 계정 간 차단, 상한, 승인 변조·재사용, 네이버 실패. 네이버는 Mock만 쓴다."""
from datetime import timedelta

from test_core import _account, _mcp_call, _mcp_headers, _safe, _viewer, c, user

from app import place
from app.naver import MOCK_FAIL_IDS, _MOCK_STORE, advoost_on


def _plan(h, ws, acc, action, **params):
    return c.post(f"/workspaces/{ws}/place/plan", headers=h, json={"ad_account_id": acc, "action": action, "params": params})


def _apply(h, ws, approval_id, acc, action, **params):
    return c.post(f"/workspaces/{ws}/place/apply", headers=h,
                  json={"approval_id": approval_id, "change": {"ad_account_id": acc, "action": action, "params": params}})


def _do(h, ws, acc, action, **params):
    r = _plan(h, ws, acc, action, **params)
    assert r.status_code == 200, r.json()
    out = _apply(h, ws, r.json()["approval_id"], acc, action, **params)
    assert out.status_code == 200, out.json()
    return out.json()


def _new_place(h, ws, acc, cid, advoost=True, business="place", **extra):
    params = {"business_id": f"bsn-{cid}-{business}", "daily_budget": 10000, "use_advoost": advoost, **extra}
    out = _do(h, ws, acc, "create", **params)
    st = _MOCK_STORE[cid]
    camp = max((c for c in st["campaigns"].values() if c["campaignTp"] == "PLACE"), key=lambda c: c["nccCampaignId"])
    grp = next((g for g in st["adgroups"].values() if g["nccCampaignId"] == camp["nccCampaignId"]), None)
    return out, camp, grp


def test_advoost_create_and_rules():
    owner, ws, acc = _account("pl-adv@a.com", "8101")
    r = _plan(owner, ws, acc, "create", business_id="bsn-8101-place", daily_budget=10000, use_advoost=True)
    s = r.json()["summary"]
    assert s["max_daily_spend"] == 10000 and s["max_monthly_spend"] == 310000 and "꺼진 상태" in s["after"]

    out, camp, grp = _new_place(owner, ws, acc, "8101")
    assert out["status"] == "SUCCESS" and "바로 나가는 것은 아니에요" in out["notice"]
    assert camp["userLock"] and grp["userLock"] and grp["adgroupType"] == "LOCAL_AD" and advoost_on(grp) and grp["bidAmt"] == 0
    linked = [a for a in _MOCK_STORE["8101"]["ads"].values() if a["nccAdgroupId"] == grp["nccAdgroupId"]]
    assert [a["type"] for a in linked] == ["ADVOOST_PLACE_AD"]  # 연동형 소재는 네이버가 자동으로 만든다

    gid = grp["nccAdgroupId"]
    for action, params, code in (("set_bid", {"adgroup_id": gid, "bid": 300}, "3755"),
                                 ("add_negative_keyword", {"adgroup_id": gid, "keyword": "배달"}, "3754"),
                                 ("turn_off", {"target_type": "ad", "target_id": linked[0]["nccAdId"]}, "3838")):
        r = _plan(owner, ws, acc, action, **params)
        assert r.status_code == 400 and code in r.json()["detail"], (action, r.json())
    # 입찰가·문구는 ADVoost가 정한다
    r = _plan(owner, ws, acc, "create", business_id="bsn-8101-place", daily_budget=10000, use_advoost=True, bid=300)
    assert r.status_code == 400 and "입찰가를 비워" in r.json()["detail"]

    # 허용: 하루예산, 켜기, ADVoost 끄기(연동 소재는 지워지지 않고 꺼짐)
    assert _do(owner, ws, acc, "set_budget", campaign_id=camp["nccCampaignId"], daily_budget=20000)["status"] == "SUCCESS"
    assert _MOCK_STORE["8101"]["campaigns"][camp["nccCampaignId"]]["dailyBudget"] == 20000
    assert _do(owner, ws, acc, "turn_on", target_type="adgroup", target_id=gid)["status"] == "SUCCESS"
    assert _do(owner, ws, acc, "set_advoost", adgroup_id=gid, on=False)["status"] == "SUCCESS"
    assert not advoost_on(_MOCK_STORE["8101"]["adgroups"][gid]) and _MOCK_STORE["8101"]["ads"][linked[0]["nccAdId"]]["userLock"]
    assert _do(owner, ws, acc, "set_bid", adgroup_id=gid, bid=300)["status"] == "SUCCESS"  # 끈 뒤에는 입찰가 변경 가능

    logs = c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()
    assert {(x["action"], x["field"]) for x in logs} >= {("CREATE", "campaign"), ("CREATE", "adgroup"), ("UPDATE", "daily_budget"),
                                                         ("UPDATE", "advoost"), ("UPDATE", "bid_amt")}


def test_regular_place_allowed_actions():
    owner, ws, acc = _account("pl-reg@a.com", "8102")
    out, camp, grp = _new_place(owner, ws, acc, "8102", advoost=False, bid=200, ad_text="떡볶이 맛집")
    assert out["status"] == "SUCCESS" and [s["ok"] for s in out["steps"]] == [True, True, True]
    gid = grp["nccAdgroupId"]
    ads = [a for a in _MOCK_STORE["8102"]["ads"].values() if a["nccAdgroupId"] == gid]
    assert [a["type"] for a in ads] == ["LOCAL_AD"] and grp["bidAmt"] == 200
    assert _plan(owner, ws, acc, "create", business_id="bsn-8102-place", daily_budget=10000, use_advoost=False).status_code == 400  # 입찰가 필요

    assert _do(owner, ws, acc, "set_bid", adgroup_id=gid, bid=350)["status"] == "SUCCESS"
    assert _do(owner, ws, acc, "add_negative_keyword", adgroup_id=gid, keyword="배달")["status"] == "SUCCESS"
    st = c.get(f"/workspaces/{ws}/place?ad_account_id={acc}", headers=owner).json()
    g = st["campaigns"][0]["groups"][0]
    assert not g["advoost"] and g["bid"] == 350 and [k["keyword"] for k in g["negative_keywords"]] == ["배달"]
    assert {b["name"] for b in st["businesses"]} == {"행복 분식", "사진 없는 가게", "튼튼 의원"}
    assert _do(owner, ws, acc, "remove_negative_keyword", adgroup_id=gid, keyword_id=g["negative_keywords"][0]["id"])["status"] == "SUCCESS"
    # ADVoost를 켜면 연동형 소재가 생기고, 그 뒤 일반 소재 추가는 막힌다(네이버가 거부 → 사장님용 설명)
    assert _do(owner, ws, acc, "set_advoost", adgroup_id=gid, on=True)["status"] == "SUCCESS"
    assert "3839" in _create_ad_blocked("8102", gid)


def _create_ad_blocked(cid, gid):
    from app.naver import MockNaverClient, NaverApiError
    try:
        MockNaverClient(cid).create_place_ad(gid, "x", "문구")
    except NaverApiError as e:
        return place.friendly(e)
    raise AssertionError("ADVoost 그룹에 소재 추가가 통과됨")


def test_advoost_business_conditions_partial():
    """사진 없는 업체·병의원은 네이버가 광고그룹을 거부한다: 캠페인만 만들어진 '일부 성공'으로 알린다."""
    owner, ws, acc = _account("pl-cond@a.com", "8103")
    out, camp, grp = _new_place(owner, ws, acc, "8103", business="place-noimg")
    assert out["status"] == "PARTIAL" and grp is None and camp["userLock"]
    assert out["steps"][0]["ok"] and not out["steps"][1]["ok"] and "사진" in out["steps"][1]["error"] and "3752" in out["steps"][1]["error"]
    out, _, _ = _new_place(owner, ws, acc, "8103", business="place-clinic")
    assert out["status"] == "PARTIAL" and "3756" in out["steps"][1]["error"]


def test_caps_enforced():
    owner, ws, acc = _account("pl-cap@a.com", "8104")
    assert "하루예산은" in _plan(owner, ws, acc, "create", business_id="bsn-8104-place", daily_budget=place.BUDGET_MAX + 10,
                                use_advoost=True).json()["detail"]
    assert _plan(owner, ws, acc, "create", business_id="bsn-8104-place", daily_budget=10005, use_advoost=True).status_code == 400
    assert "입찰가" in _plan(owner, ws, acc, "create", business_id="bsn-8104-place", daily_budget=10000, use_advoost=False,
                            bid=place.BID_MAX + 10).json()["detail"]
    _, camp, grp = _new_place(owner, ws, acc, "8104", advoost=False, bid=100)
    # 계정 광고비 안전장치: 켜진 캠페인 하루예산 설정액 합계(파워링크 5만+쇼핑 3만=8만)가 관리 기준 8.5만이면
    # 이 캠페인(1만)을 켜면 9만이라 막히고, 최대 입찰가 150원을 넘는 입찰가도 막힌다
    _safe(owner, ws, acc, limit=85_000, max_bid=150)
    r = _plan(owner, ws, acc, "turn_on", target_type="campaign", target_id=camp["nccCampaignId"])
    assert r.status_code == 400 and "90,000원" in r.json()["detail"] and "85,000원" in r.json()["detail"]
    r = _plan(owner, ws, acc, "set_bid", adgroup_id=grp["nccAdgroupId"], bid=200)
    assert r.status_code == 400 and "최대 입찰가 150원" in r.json()["detail"]
    assert _plan(owner, ws, acc, "turn_off", target_type="campaign", target_id=camp["nccCampaignId"]).status_code == 200  # 끄기는 허용
    _safe(owner, ws, acc, limit=95_000, max_bid=150)
    s = _plan(owner, ws, acc, "turn_on", target_type="campaign", target_id=camp["nccCampaignId"]).json()["summary"]
    assert s["safety"]["total_after"] == 90_000 and "합계 90,000원" in s["spend_text"] and "절대 상한이 아니에요" in " ".join(s["notes"])


def test_approval_tamper_reuse_expiry_and_owner():
    owner, ws, acc = _account("pl-apr@a.com", "8105")
    _, camp, _ = _new_place(owner, ws, acc, "8105")
    cid = camp["nccCampaignId"]
    aid = _plan(owner, ws, acc, "set_budget", campaign_id=cid, daily_budget=20000).json()["approval_id"]
    r = _apply(owner, ws, aid, acc, "set_budget", campaign_id=cid, daily_budget=90000)  # 승인 뒤 금액 바꿔치기
    assert r.status_code == 409 and _MOCK_STORE["8105"]["campaigns"][cid]["dailyBudget"] == 10000
    other = _viewer(owner, ws, acc, "pl-apr-v@a.com")
    assert _apply(other, ws, aid, acc, "set_budget", campaign_id=cid, daily_budget=20000).status_code == 404  # 남의 승인 요청
    # 모르는 값을 끼워 넣어도 실행 내용은 그대로(허용한 값만 해시) → 통과
    assert _apply(owner, ws, aid, acc, "set_budget", campaign_id=cid, daily_budget=20000, extra="x").json()["status"] == "SUCCESS"
    assert _apply(owner, ws, aid, acc, "set_budget", campaign_id=cid, daily_budget=20000).status_code == 409  # 재사용

    aid = _plan(owner, ws, acc, "set_budget", campaign_id=cid, daily_budget=30000).json()["approval_id"]
    real_now = place.now
    place.now = lambda: real_now() + timedelta(minutes=16)
    try:
        assert _apply(owner, ws, aid, acc, "set_budget", campaign_id=cid, daily_budget=30000).status_code == 410
    finally:
        place.now = real_now
    assert _MOCK_STORE["8105"]["campaigns"][cid]["dailyBudget"] == 20000


def test_cross_account_and_role_blocks():
    owner, ws, acc = _account("pl-iso@a.com", "8106")
    _, camp, _ = _new_place(owner, ws, acc, "8106")
    outsider, ws_b, acc_b = _account("pl-iso-b@a.com", "8107")
    # 다른 조직: 남의 계정으로 계획 못 만들고 조회도 못 함
    assert _plan(outsider, ws, acc, "turn_off", target_type="campaign", target_id=camp["nccCampaignId"]).status_code == 403
    assert _plan(outsider, ws_b, acc, "turn_off", target_type="campaign", target_id=camp["nccCampaignId"]).status_code == 403
    assert c.get(f"/workspaces/{ws_b}/place?ad_account_id={acc}", headers=outsider).status_code == 403
    # 내 계정 ID에 남의 캠페인 ID를 붙여도 내 계정에서 찾을 수 없다(네이버는 계정별로 조회)
    assert _plan(outsider, ws_b, acc_b, "turn_off", target_type="campaign", target_id=camp["nccCampaignId"]).status_code == 404
    # 보기 권한만 있는 직원은 계획을 못 만든다
    viewer = _viewer(owner, ws, acc, "pl-iso-v@a.com")
    assert _plan(viewer, ws, acc, "set_budget", campaign_id=camp["nccCampaignId"], daily_budget=20000).status_code == 403
    assert c.get(f"/workspaces/{ws}/place?ad_account_id={acc}", headers=viewer).status_code == 200
    # 승인 뒤 권한이 사라지면 실행 때 다시 막힌다
    from app.db import SessionLocal
    from app.models import AccountAccess, Membership
    staff = user("pl-iso-s@a.com")
    mid = c.post(f"/workspaces/{ws}/members", json={"email": "pl-iso-s@a.com"}, headers=owner).json()["membership_id"]
    c.put(f"/workspaces/{ws}/members/{mid}/access", json={"ad_account_id": acc, "level": "EDIT"}, headers=owner)
    aid = _plan(staff, ws, acc, "turn_off", target_type="campaign", target_id=camp["nccCampaignId"]).json()["approval_id"]
    with SessionLocal() as db:
        db.query(AccountAccess).filter(AccountAccess.membership_id == mid).delete()
        db.commit()
        assert db.get(Membership, mid) is not None
    out = _apply(staff, ws, aid, acc, "turn_off", target_type="campaign", target_id=camp["nccCampaignId"]).json()
    assert out["status"] == "FAILED" and "권한" in out["error"]


def test_powerlink_targets_rejected_and_naver_failure():
    owner, ws, acc = _account("pl-misc@a.com", "8108")
    r = _plan(owner, ws, acc, "set_bid", adgroup_id="grp-8108-pl1", bid=300)  # 파워링크 그룹은 플레이스 도구로 못 바꾼다
    assert r.status_code == 400 and "플레이스광고 광고그룹이 아니에요" in r.json()["detail"]
    r = _plan(owner, ws, acc, "create", business_id="bsn-8108-site", daily_budget=10000, use_advoost=True)
    assert r.status_code == 400 and "플레이스 업체" in r.json()["detail"]

    _, camp, _ = _new_place(owner, ws, acc, "8108")
    cid = camp["nccCampaignId"]
    aid = _plan(owner, ws, acc, "set_budget", campaign_id=cid, daily_budget=20000).json()["approval_id"]
    MOCK_FAIL_IDS.add(cid)
    try:
        out = _apply(owner, ws, aid, acc, "set_budget", campaign_id=cid, daily_budget=20000).json()
    finally:
        MOCK_FAIL_IDS.discard(cid)
    assert out["status"] == "FAILED" and not out["steps"][0]["ok"] and "네이버가 요청을 받아들이지 않았어요" in out["steps"][0]["error"]
    assert out["notice"] is None  # 실패면 '검토 후 노출' 안내를 하지 않는다


def test_mcp_place_tools():
    owner, ws, acc = _account("pl-mcp@a.com", "8109")
    h = _mcp_headers(owner)
    names = {t["name"] for t in c.post("/mcp", headers=h, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()["result"]["tools"]}
    assert {"place_ads_status", "place_ads_plan", "place_ads_apply"} <= names
    st, err = _mcp_call(h, "place_ads_status", workspace_id=ws, ad_account_id=acc)
    assert not err and len(st["businesses"]) == 3 and st["campaigns"] == []
    change = {"ad_account_id": acc, "action": "create", "params": {"business_id": "bsn-8109-place", "daily_budget": 10000, "use_advoost": True}}
    pl, err = _mcp_call(h, "place_ads_plan", workspace_id=ws, **change)
    assert not err and pl["summary"]["max_daily_spend"] == 10000
    bad, err = _mcp_call(h, "place_ads_apply", workspace_id=ws, approval_id=pl["approval_id"],
                         **{**change, "params": {**change["params"], "daily_budget": 50000}})
    assert err
    out, err = _mcp_call(h, "place_ads_apply", workspace_id=ws, approval_id=pl["approval_id"], **change)
    assert not err and out["status"] == "SUCCESS"
    st, _ = _mcp_call(h, "place_ads_status", workspace_id=ws, ad_account_id=acc)
    g = st["campaigns"][0]["groups"][0]
    assert g["advoost"] and g["bid"] is None and g["ads"][0]["linked"] and st["campaigns"][0]["daily_budget"] == 10000
