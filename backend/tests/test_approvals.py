"""웹 승인(계정 하루예산 합계가 늘 수 있는 변경)·계정 잠금·실제 입찰가·우회 경로·쿠키 세션 보안. 네이버는 Mock만 쓴다.
Mock 계정 기본값: 켜진 캠페인 파워링크(하루예산 5만, 그룹1 입찰가 500·하루예산 2만, 그룹2 입찰가 500·무제한) + 쇼핑(3만) = 합계 8만.
키워드 kwd-{cid}-{그룹}{1~3} 입찰가 300·600·900, 쇼핑 소재 입찰가 200·400·600."""
from datetime import timedelta

from fastapi.testclient import TestClient
from test_core import END, _account, _mcp_call, _mcp_headers, _safe, _viewer, c, ch, user
from test_safety import _fresh, _job, _rows, _run

from app import approvals, bulk, safety
from app.db import SessionLocal
from app.main import app
from app.models import AccountAccess, ApprovalRequest, BulkJob, BulkJobRow
from app.naver import _MOCK_STORE, MockNaverClient
from app.security import make_token, read_token

CSRF = {"x-naverads-csrf": "1"}


def _approve(h, ws, aid):
    return c.post(f"/workspaces/{ws}/approvals/{aid}/approve", headers=h)


def _request(h, ws, changes):
    """미리보기 → 실행 요청. 웹 승인 대상이면 실행되지 않고 승인 요청이 나온다."""
    job = _job(h, ws, changes)
    out = _run(h, ws, job["id"])
    return job, out.get("approval")


def _off(cid, *camps):
    for x in camps:
        _MOCK_STORE[cid]["campaigns"][x]["userLock"] = True


def _staff(owner, ws, acc, email, level="EDIT"):
    h = user(email)
    mid = c.post(f"/workspaces/{ws}/members", json={"email": email}, headers=owner).json()["membership_id"]
    c.put(f"/workspaces/{ws}/members/{mid}/access", json={"ad_account_id": acc, "level": level}, headers=owner)
    return h, mid


def _revoke(mid):
    with SessionLocal() as db:
        db.query(AccountAccess).filter(AccountAccess.membership_id == mid).delete()
        db.commit()


def test_web_approval_required_bound_and_single_use():
    owner, ws, acc = _account("ap-req@a.com", "7401")
    MockNaverClient("7401")
    _off("7401", "cmp-7401-pl")
    job, ap = _request(owner, ws, [ch(acc, "campaign", "cmp-7401-pl", "status", "ON", before="OFF")])
    # 승인 없이 실행: 아무것도 바뀌지 않고 승인 요청만
    assert ap["status"] == "PENDING" and ap["web_required"] and _MOCK_STORE["7401"]["campaigns"]["cmp-7401-pl"]["userLock"] is True
    sm = ap["summary"]
    assert sm["rows"][0]["before"] == "OFF" and sm["rows"][0]["after"] == "ON" and sm["safety"][0]["total_after"] == 80_000
    assert "절대 상한이 아니에요" in sm["note"] and "광고주센터" in sm["note"]
    assert ap["approval_id"] in [x["approval_id"] for x in c.get(f"/workspaces/{ws}/approvals", headers=owner).json()]
    # 변조: 승인 요청 뒤 실행할 행이 바뀌면 승인되지 않는다
    with SessionLocal() as db:
        row = db.query(BulkJobRow).filter(BulkJobRow.job_id == job["id"]).one()
        row.before = "ON"
        db.commit()
    assert _approve(owner, ws, ap["approval_id"]).status_code == 409
    with SessionLocal() as db:
        db.query(BulkJobRow).filter(BulkJobRow.job_id == job["id"]).update({"before": "OFF"})
        db.commit()
    r = _approve(owner, ws, ap["approval_id"]).json()
    assert r["status"] == "DONE" and r["job"]["status"] == "DONE" and _MOCK_STORE["7401"]["campaigns"]["cmp-7401-pl"]["userLock"] is False
    # 재사용: 같은 승인으로 다시 실행·승인할 수 없다
    assert _approve(owner, ws, ap["approval_id"]).status_code == 409
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner).status_code == 409
    acts = [x["action"] for x in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json() if x["entity_type"] == "approval"]
    assert {"APPROVAL_PENDING", "APPROVAL_APPROVED", "APPROVAL_DONE"} <= set(acts)
    # 예산 줄이기·끄기는 승인 없이 바로
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "campaign", "cmp-7401-pl", "daily_budget", "40000"),
                                           ch(acc, "campaign", "cmp-7401-sh", "status", "OFF")])["id"])
    assert out["status"] == "DONE" and "approval" not in out


def test_approval_other_users_mcp_expiry_reject():
    owner, ws, acc = _account("ap-who@a.com", "7402")
    MockNaverClient("7402")
    _off("7402", "cmp-7402-pl")
    job, ap = _request(owner, ws, [ch(acc, "campaign", "cmp-7402-pl", "status", "ON")])
    aid = ap["approval_id"]
    staff, _ = _staff(owner, ws, acc, "ap-who-s@a.com")
    viewer = _viewer(owner, ws, acc, "ap-who-v@a.com")
    outsider, ws_b, _ = _account("ap-who-b@a.com", "7412")
    assert _approve(staff, ws, aid).status_code == 403  # 수정 권한이 있어도 요청자·관리자가 아니면
    assert _approve(viewer, ws, aid).status_code == 403
    assert _approve(outsider, ws_b, aid).status_code == 404 and c.post(f"/workspaces/{ws}/approvals/{aid}/approve", headers=outsider).status_code == 403
    assert _approve(_mcp_headers(owner), ws, aid).status_code == 401  # Claude 토큰은 승인 API를 못 부른다
    # 만료
    real = approvals.now
    approvals.now = lambda: real() + timedelta(minutes=31)
    try:
        assert _approve(owner, ws, aid).status_code == 410
    finally:
        approvals.now = real
    assert c.get(f"/workspaces/{ws}/approvals/{aid}", headers=owner).json()["status"] == "EXPIRED"
    ap2 = _run(owner, ws, job["id"])["approval"]  # 다시 실행하면 새 승인 요청
    assert ap2["approval_id"] != aid and ap2["status"] == "PENDING"
    # 거절
    assert c.post(f"/workspaces/{ws}/approvals/{ap2['approval_id']}/reject", headers=owner).json()["status"] == "REJECTED"
    assert _approve(owner, ws, ap2["approval_id"]).status_code == 409
    assert _MOCK_STORE["7402"]["campaigns"]["cmp-7402-pl"]["userLock"] is True


def test_permission_revoked_and_naver_changed_after_approval():
    owner, ws, acc = _account("ap-rev@a.com", "7403")
    MockNaverClient("7403")
    _off("7403", "cmp-7403-pl")
    # 직원이 요청 → 권한 회수 → 승인 불가
    staff, mid = _staff(owner, ws, acc, "ap-rev-s@a.com")
    _, ap = _request(staff, ws, [ch(acc, "campaign", "cmp-7403-pl", "status", "ON")])
    _revoke(mid)
    assert _approve(staff, ws, ap["approval_id"]).status_code in (403, 404)
    # 예약 작업: 승인 뒤 권한이 회수되면 실행 시각에 다시 막힌다
    staff2, mid2 = _staff(owner, ws, acc, "ap-rev-s2@a.com")
    job = _job(staff2, ws, [ch(acc, "campaign", "cmp-7403-pl", "status", "ON")])
    at = (bulk.now() + timedelta(hours=1)).isoformat()
    ap = c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/schedule", headers=staff2, json={"scheduled_at": at}).json()["approval"]
    assert _approve(staff2, ws, ap["approval_id"]).json()["status"] == "APPROVED"
    _revoke(mid2)
    with SessionLocal() as db:
        db.get(BulkJob, job["id"]).scheduled_at = bulk.now() - timedelta(minutes=1)
        db.commit()
        bulk.run_scheduled_jobs(db)
    out = c.get(f"/workspaces/{ws}/bulk-jobs/{job['id']}", headers=owner).json()
    assert out["status"] == "FAILED" and "권한" in _rows(out)["cmp-7403-pl"]["error"]
    assert _MOCK_STORE["7403"]["campaigns"]["cmp-7403-pl"]["userLock"] is True
    # 승인 요청 뒤 네이버 광고주센터에서 값을 바꿈 → 승인 때 보여 준 변경 전 값과 달라 실행하지 않음
    _, ap = _request(owner, ws, [ch(acc, "campaign", "cmp-7403-sh", "daily_budget", "40000", before="30000")])
    _MOCK_STORE["7403"]["campaigns"]["cmp-7403-sh"]["dailyBudget"] = 35_000
    r = _approve(owner, ws, ap["approval_id"]).json()
    assert r["status"] == "FAILED" and "바뀌어" in _rows(r["job"])["cmp-7403-sh"]["error"]
    assert _MOCK_STORE["7403"]["campaigns"]["cmp-7403-sh"]["dailyBudget"] == 35_000
    assert c.get(f"/workspaces/{ws}/approvals/{ap['approval_id']}", headers=owner).json()["status"] == "FAILED"


def test_bid_increase_needs_known_total():
    owner, ws, acc = _account("ap-bid@a.com", "7404")
    MockNaverClient("7404")
    _MOCK_STORE["7404"]["campaigns"]["cmp-7404-pl"]["dailyBudget"] = 0  # 캠페인 예산 없음 + 그룹2 무제한 → 합계 계산 불가
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "kwd-7404-11", "bid_amt", "400", product="WEB_SITE")])["id"])
    assert out["status"] == "FAILED" and "계산할 수 없어" in _rows(out)["kwd-7404-11"]["error"]
    assert _MOCK_STORE["7404"]["keywords"]["kwd-7404-11"]["bidAmt"] == 300
    # 입찰가 내리기는 합계와 상관없이 된다
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "kwd-7404-12", "bid_amt", "500", product="WEB_SITE")])["id"])
    assert out["status"] == "DONE"
    # 새 키워드(켜진 상태로 생김)도 비용 증가로 본다
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "grp-7404-pl1", "create", "새키워드|100", product="WEB_SITE")])["id"])
    assert out["status"] == "FAILED"
    # 합계가 이미 관리 기준을 넘는 계정
    _MOCK_STORE["7404"]["campaigns"]["cmp-7404-pl"]["dailyBudget"] = 50_000
    _safe(owner, ws, acc, limit=70_000, max_bid=10_000)
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "kwd-7404-11", "bid_amt", "400", product="WEB_SITE")])["id"])
    assert out["status"] == "FAILED" and "관리 기준" in _rows(out)["kwd-7404-11"]["error"]
    # 안전장치 미설정 계정
    o2, ws2, acc2 = _fresh("ap-bid2@a.com", "7414")
    out = _run(o2, ws2, _job(o2, ws2, [ch(acc2, "keyword", "kwd-7414-11", "bid_amt", "400", product="WEB_SITE")])["id"])
    assert out["status"] == "FAILED" and "아직" in _rows(out)["kwd-7414-11"]["error"]


def test_turn_on_checks_effective_bid():
    owner, ws, acc = _account("ap-on@a.com", "7405")
    MockNaverClient("7405")
    st = _MOCK_STORE["7405"]
    _safe(owner, ws, acc, limit=1_000_000, max_bid=800)
    st["keywords"]["kwd-7405-13"]["userLock"] = True  # 입찰가 900 > 800
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "kwd-7405-13", "status", "ON")])["id"])
    assert out["status"] == "FAILED" and "실제 입찰가" in _rows(out)["kwd-7405-13"]["error"] and st["keywords"]["kwd-7405-13"]["userLock"]
    # 그룹 입찰가를 물려받는 키워드: 그룹 입찰가로 판단
    st["adgroups"]["grp-7405-pl2"]["bidAmt"] = 850
    st["keywords"]["kwd-7405-21"].update(useGroupBidAmt=True, userLock=True)
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "kwd-7405-21", "status", "ON")])["id"])
    assert out["status"] == "FAILED" and st["keywords"]["kwd-7405-21"]["userLock"]
    st["keywords"]["kwd-7405-11"]["userLock"] = True  # 300원은 통과
    assert _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "kwd-7405-11", "status", "ON")])["id"])["status"] == "DONE"
    # 광고그룹 켜기(웹 승인 대상 아님, 11/02 2차 결정): 승인 요청 없이 실행되지만, 안에 최대 입찰가를 넘는 켜진 키워드가 있으면 실행 직전에 막힌다
    st["adgroups"]["grp-7405-pl1"]["userLock"] = True
    st["keywords"]["kwd-7405-13"]["userLock"] = False
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "adgroup", "grp-7405-pl1", "status", "ON")])["id"])
    assert "approval" not in out and out["status"] == "FAILED" and "높은 입찰가" in _rows(out)["grp-7405-pl1"]["error"]
    assert st["adgroups"]["grp-7405-pl1"]["userLock"]
    st["keywords"]["kwd-7405-13"]["userLock"] = True  # 넘는 키워드를 끄면 승인 없이 켜진다
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "adgroup", "grp-7405-pl1", "status", "ON")])["id"])
    assert "approval" not in out and out["status"] == "DONE" and st["adgroups"]["grp-7405-pl1"]["userLock"] is False
    # 쇼핑 상품소재 켜기
    st["ads"]["ad-7405-sh3"].update(adAttr={"bidAmt": 900, "useGroupBidAmt": False}, userLock=True)
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "ad", "ad-7405-sh3", "status", "ON")])["id"])
    assert out["status"] == "FAILED" and st["ads"]["ad-7405-sh3"]["userLock"]


def test_two_campaigns_serialized_and_account_lock():
    owner, ws, acc = _account("ap-lock@a.com", "7406")
    MockNaverClient("7406")
    st = _MOCK_STORE["7406"]
    _safe(owner, ws, acc, limit=90_000, max_bid=10_000)
    st["campaigns"]["cmp-7406-x"] = {"nccCampaignId": "cmp-7406-x", "name": "새캠페인", "campaignTp": "WEB_SITE", "userLock": True, "dailyBudget": 40_000}
    _off("7406", "cmp-7406-pl")  # 켜진 합계 3만
    # 각각이면 통과(3+5=8만, 3+4=7만), 둘 다면 12만 > 9만: 두 요청이 같은 옛 상태만 보고 함께 통과하지 않는다
    _, a = _request(owner, ws, [ch(acc, "campaign", "cmp-7406-pl", "status", "ON")])
    _, b = _request(owner, ws, [ch(acc, "campaign", "cmp-7406-x", "status", "ON")])
    assert a["summary"]["safety"][0]["ok"] and b["summary"]["safety"][0]["ok"]
    assert _approve(owner, ws, a["approval_id"]).json()["status"] == "DONE"
    r = _approve(owner, ws, b["approval_id"]).json()
    assert r["status"] == "FAILED" and "관리 기준" in _rows(r["job"])["cmp-7406-x"]["error"] and st["campaigns"]["cmp-7406-x"]["userLock"]
    # 다른 요청이 잠금을 쥐고 있으면(동시 실행) 비용 행은 실행하지 않고 끄기 행은 실행한다
    with SessionLocal() as db:
        holder = safety.take_lock(db, acc)
        assert holder and safety.take_lock(db, acc) is None
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "kwd-7406-11", "bid_amt", "400", product="WEB_SITE"),
                                           ch(acc, "keyword", "kwd-7406-12", "status", "OFF")])["id"])
    r = _rows(out)
    assert out["status"] == "PARTIAL" and r["kwd-7406-11"]["error"] == safety.BUSY and r["kwd-7406-12"]["status"] == "SUCCESS"
    assert st["keywords"]["kwd-7406-11"]["bidAmt"] == 300
    # 잠금을 쥔 요청이 죽어도 90초 뒤에는 다른 요청이 가져간다(장애 복구)
    real = safety.now
    safety.now = lambda: real() + timedelta(seconds=100)
    try:
        assert _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "kwd-7406-11", "bid_amt", "400", product="WEB_SITE")])["id"])["status"] == "DONE"
    finally:
        safety.now = real
    with SessionLocal() as db:
        safety.release_lock(db, acc, holder)  # 남의 잠금은 못 푼다(이미 다른 요청이 가져가고 풀었음) — 오류 없이 지나간다
        assert safety.take_lock(db, acc) is not None


def test_bypass_paths():
    owner, ws, acc = _account("ap-path@a.com", "7407")
    MockNaverClient("7407")
    st = _MOCK_STORE["7407"]
    _off("7407", "cmp-7407-pl")
    mh = _mcp_headers(owner)
    # Claude 예약: 승인 요청만 만들고, 승인 없이 시각이 되면 실행하지 않는다
    pv, _ = _mcp_call(mh, "preview_changes", workspace_id=ws, changes=[ch(acc, "campaign", "cmp-7407-pl", "status", "ON")])
    out, err = _mcp_call(mh, "schedule_job", workspace_id=ws, job_id=pv["id"], scheduled_at=(bulk.now() + timedelta(hours=1)).isoformat())
    assert not err and out["approval"]["status"] == "PENDING"
    with SessionLocal() as db:
        db.get(BulkJob, pv["id"]).scheduled_at = bulk.now() - timedelta(minutes=1)
        db.commit()
        bulk.run_scheduled_jobs(db)
    out = c.get(f"/workspaces/{ws}/bulk-jobs/{pv['id']}", headers=owner).json()
    assert out["status"] == "FAILED" and "웹 승인" in _rows(out)["cmp-7407-pl"]["error"] and st["campaigns"]["cmp-7407-pl"]["userLock"]
    assert _mcp_call(mh, "get_approval", workspace_id=ws, approval_id=_approval_of(pv["id"]))[0]["status"] == "EXPIRED"
    # 쇼핑 상품소재: 입찰가를 비우면 그룹 입찰가(300)를 물려받아 그 값으로 상한 검사
    _safe(owner, ws, acc, limit=100_000_000, max_bid=250)
    r = c.post(f"/workspaces/{ws}/shopping-ads", headers=owner, json={"ad_account_id": acc, "adgroup_naver_id": "grp-7407-sh1", "product_id": "777"})
    assert r.status_code == 400 and "광고그룹 입찰가" in r.json()["detail"]
    r = c.post(f"/workspaces/{ws}/shopping-ads", headers=owner, json={"ad_account_id": acc, "adgroup_naver_id": "grp-7407-sh1", "product_id": "777", "bid_amt": 200})
    assert r.status_code == 200
    # 목표 ROAS 저장도 계정 최대 입찰가를 넘을 수 없다
    r = c.put(f"/workspaces/{ws}/account-goals", headers=owner, json={"ad_account_id": acc, "roas_target": 300, "max_bid": 500})
    assert r.status_code == 400 and "250원" in r.json()["detail"]
    # 합계를 계산할 수 없는 계정: 확장소재 등록(켜진 상태로 생김)과 자동입찰 올리기가 막힌다
    _safe(owner, ws, acc, limit=100_000_000, max_bid=10_000)
    st["campaigns"]["cmp-7407-sh"]["sharedBudgetId"] = "sbg-1"
    r = c.post(f"/workspaces/{ws}/ad-extensions", headers=owner, json={"ad_account_id": acc, "adgroup_naver_id": "grp-7407-pl1",
                                                                       "ext_type": "HEADLINE", "heading": "무료배송"})
    assert r.status_code == 400 and "공유예산" in r.json()["detail"]
    url = f"/workspaces/{ws}/auto-bids"
    assert c.put(url, headers=owner, json={"keywords": [{"ad_account_id": acc, "naver_id": "kwd-7407-11"}], "device": "PC", "target_rank": 1,
                                           "max_bid": 1000, "ends_on": END}).status_code == 200
    c.post(f"{url}/run", headers=owner)
    assert st["keywords"]["kwd-7407-11"]["bidAmt"] == 300 and "실패" in c.get(url, headers=owner).json()[0]["last_result"]


def _approval_of(job_id):
    with SessionLocal() as db:
        return db.query(ApprovalRequest).filter(ApprovalRequest.job_id == job_id).order_by(ApprovalRequest.id.desc()).first().id


def test_advoost_and_place_spend_text():
    from test_place import _do, _new_place, _plan
    owner, ws, acc = _account("ap-adv@a.com", "7408")
    _, camp, grp = _new_place(owner, ws, acc, "7408")  # 꺼진 ADVoost 캠페인(하루예산 1만)
    cid = camp["nccCampaignId"]
    gid = grp["nccAdgroupId"]
    s = _plan(owner, ws, acc, "turn_on", target_type="adgroup", target_id=gid).json()["summary"]
    # 광고그룹 켜기는 웹 승인 대상이 아니지만(11/02 2차 결정) ADVoost 그룹이면 통제할 수 없는 항목을 표시한다
    assert not s["web_required"] and any("ADVoost" in n for n in s["safety"]["uncontrolled"])
    # 캠페인 하루예산이 없으면 ADVoost 켜기를 막는다(입찰가도 예산도 상한이 없게 되므로)
    _MOCK_STORE["7408"]["campaigns"][cid].update(dailyBudget=0, useDailyBudget=False)
    r = _plan(owner, ws, acc, "turn_on", target_type="adgroup", target_id=gid)
    assert r.status_code == 400 and "ADVoost" in r.json()["detail"]
    # 일반 플레이스 그룹 입찰가: 올리면 '지출이 늘 수 있어요', 내리면 '늘지 않아요'
    _, camp2, grp2 = _new_place(owner, ws, acc, "7408", advoost=False, bid=300)
    _MOCK_STORE["7408"]["campaigns"][camp2["nccCampaignId"]].update(dailyBudget=0, useDailyBudget=False)
    up = _plan(owner, ws, acc, "set_bid", adgroup_id=grp2["nccAdgroupId"], bid=500).json()["summary"]
    assert "늘 수 있어요" in up["spend_text"] and "늘지 않아요" not in up["spend_text"]
    down = _plan(owner, ws, acc, "set_bid", adgroup_id=grp2["nccAdgroupId"], bid=200).json()["summary"]
    assert down["spend_text"] == "이 변경으로 지출이 늘지 않아요" and not down["web_required"]
    # ADVoost 켜기는 웹 승인 대상
    _MOCK_STORE["7408"]["campaigns"][camp2["nccCampaignId"]].update(dailyBudget=10000, useDailyBudget=True)
    plan = _plan(owner, ws, acc, "set_advoost", adgroup_id=grp2["nccAdgroupId"], on=True).json()
    assert plan["web_required"]
    out, err = _mcp_call(_mcp_headers(owner), "place_ads_apply", workspace_id=ws, approval_id=plan["approval_id"], ad_account_id=acc,
                         action="set_advoost", params={"adgroup_id": grp2["nccAdgroupId"], "on": True})
    assert err and "웹 승인" in out["error"]
    assert _do(owner, ws, acc, "turn_off", target_type="campaign", target_id=cid)["status"] == "SUCCESS"


def test_emergency_stop_and_naver_failure(monkeypatch):
    owner, ws, acc = _account("ap-stop@a.com", "7409")
    MockNaverClient("7409")
    viewer = _viewer(owner, ws, acc, "ap-stop-v@a.com")
    body = {"ad_account_id": acc, "entity_type": "campaign", "naver_id": "cmp-7409-pl"}
    assert c.post(f"/workspaces/{ws}/stop", headers=viewer, json=body).status_code == 403
    with SessionLocal() as db:
        holder = safety.take_lock(db, acc)  # 다른 비용 변경이 실행 중이어도 끄기는 바로
    assert c.post(f"/workspaces/{ws}/stop", headers=owner, json=body).json()["ok"]
    assert _MOCK_STORE["7409"]["campaigns"]["cmp-7409-pl"]["userLock"] is True
    with SessionLocal() as db:
        safety.release_lock(db, acc, holder)
    assert "EMERGENCY_STOP" in [x["action"] for x in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()]
    # 승인 뒤 네이버 조회 실패 → 실행하지 않음(실패로 기록)
    _, ap = _request(owner, ws, [ch(acc, "campaign", "cmp-7409-pl", "status", "ON")])
    monkeypatch.setattr(MockNaverClient, "list_campaigns", lambda self: (_ for _ in ()).throw(bulk.NaverApiError("503 점검 중")))
    r = _approve(owner, ws, ap["approval_id"]).json()
    assert r["status"] == "FAILED" and "읽지 못해" in _rows(r["job"])["cmp-7409-pl"]["error"]
    assert _MOCK_STORE["7409"]["campaigns"]["cmp-7409-pl"]["userLock"] is True
    # 지금 값을 네이버에서 읽지 못하면 실행할 수 있는 승인 요청을 만들지 않고 이유를 알려 준다
    job = _job(owner, ws, [ch(acc, "campaign", "cmp-7409-sh", "daily_budget", "40000")])
    r = c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner)
    assert r.status_code == 400 and "승인 요청을 만들지 않았어요" in r.json()["detail"]
    with SessionLocal() as db:
        assert db.query(ApprovalRequest).filter(ApprovalRequest.job_id == job["id"]).count() == 0


def test_cookie_session_csrf_cors_logout(monkeypatch):
    import time

    from app import security
    s = TestClient(app, base_url="https://testserver")
    t0 = c.post("/auth/signup", json={"email": "ck@a.com", "password": "password1", "name": "ck"}).json()["token"]
    r = s.post("/auth/login", json={"email": "ck@a.com", "password": "password1"})
    assert r.status_code == 200 and "token" not in r.json()  # 토큰은 본문에 없고 HttpOnly 쿠키로만
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
    tok = r.cookies["naverads_session"]
    assert s.get("/auth/me").json()["email"] == "ck@a.com"
    # 쿠키로 로그인한 쓰기 요청: CSRF 헤더 필요, 출처가 있으면 웹 주소여야 한다
    assert s.post("/workspaces", json={"name": "x"}).status_code == 403
    assert s.post("/workspaces", json={"name": "x"}, headers={**CSRF, "Origin": "https://evil.com"}).status_code == 403
    assert s.post("/workspaces", json={"name": "x"}, headers={**CSRF, "Origin": "https://naverads.djkim0509.workers.dev"}).status_code == 200
    assert c.post("/workspaces", json={"name": "y"}, headers={"Authorization": f"Bearer {t0}"}).status_code == 200  # 헤더 토큰은 CSRF 대상 아님
    # CORS: 웹 주소만, 쿠키 허용
    pre = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type,x-naverads-csrf"}
    assert "access-control-allow-origin" not in s.options("/workspaces", headers={**pre, "Origin": "https://evil.com"}).headers
    ok = s.options("/workspaces", headers={**pre, "Origin": "https://naverads.djkim0509.workers.dev"}).headers
    assert ok["access-control-allow-origin"] == "https://naverads.djkim0509.workers.dev" and ok["access-control-allow-credentials"] == "true"
    # Claude 토큰을 쿠키에 넣어도 일반 API는 거부
    uid = read_token(tok)[0]
    s2 = TestClient(app, base_url="https://testserver")
    s2.cookies.set("naverads_session", make_token(uid, 0, 0, 600))
    assert s2.get("/auth/me").status_code == 401
    # 만료된 세션
    s2.cookies.set("naverads_session", make_token(uid, 0, None, -1))
    assert s2.get("/auth/me").status_code == 401
    # 로그아웃: 쿠키를 지우고 그 토큰은 서버에서 무효
    r = s.post("/auth/logout", headers=CSRF)
    assert r.status_code == 200 and 'naverads_session=""' in r.headers["set-cookie"]
    assert c.get("/auth/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
    # 예전 웹(localStorage 토큰) → 쿠키로 옮기기: 예전 토큰은 무효가 되고 쿠키로 계속
    t0 = make_token(uid, 0, None, 3000)  # 로그인과 다른 시각에 받은 예전 토큰
    real = time.time
    monkeypatch.setattr(security.time, "time", lambda: real() + 700)  # 로그아웃한 토큰과 다른 시각에 새 토큰을 받게(같은 초면 같을 수 있다)
    s3 = TestClient(app, base_url="https://testserver")
    r = s3.post("/auth/session", headers={"Authorization": f"Bearer {t0}"})
    assert r.status_code == 200 and s3.get("/auth/me").status_code == 200
    assert c.get("/auth/me", headers={"Authorization": f"Bearer {t0}"}).status_code == 401


def test_budget_increase_after_first_chunk_needs_web_approval():
    """처음 실행 때는 '줄이기'였던 예산 행이, 앞 묶음 실행 뒤 다른 작업으로 예산이 더 낮아져 '올리기'가 되면 웹 승인 없이 실행되지 않는다."""
    owner, ws, acc = _account("ap-chunk@a.com", "7410")
    MockNaverClient("7410")
    st = _MOCK_STORE["7410"]
    fillers = [ch(acc, "keyword", f"kwd-7410-{g}{k}", "status", "OFF") for g in (1, 2) for k in (1, 2, 3)][:5]
    job = _job(owner, ws, fillers + [ch(acc, "campaign", "cmp-7410-pl", "daily_budget", "40000")])  # 지금 5만 → 4만(줄이기)
    first = _run(owner, ws, job["id"])  # 앞 5행만 실행, 승인 요청 없음
    assert first["status"] == "RUNNING" and "approval" not in first
    assert _run(owner, ws, _job(owner, ws, [ch(acc, "campaign", "cmp-7410-pl", "daily_budget", "20000")])["id"])["status"] == "DONE"
    out = _run(owner, ws, job["id"])  # 이제 2만 → 4만은 올리기
    assert st["campaigns"]["cmp-7410-pl"]["dailyBudget"] == 20_000 and "웹 승인" in _rows(out)["cmp-7410-pl"]["error"]


def test_missing_before_filled_for_web_approval_and_checked():
    """Claude가 before를 안 넣어도 승인 화면에 네이버 지금 값을 보여 주고, 승인 뒤 그 값이 바뀌면 실행하지 않는다."""
    owner, ws, acc = _account("ap-before@a.com", "7411")
    MockNaverClient("7411")
    _off("7411", "cmp-7411-pl")
    _, ap = _request(owner, ws, [ch(acc, "campaign", "cmp-7411-pl", "status", "ON"), ch(acc, "campaign", "cmp-7411-sh", "daily_budget", "40000")])
    shown = {r["naver_id"]: r["before"] for r in ap["summary"]["rows"]}
    assert shown == {"cmp-7411-pl": "OFF", "cmp-7411-sh": "30000"}
    _MOCK_STORE["7411"]["campaigns"]["cmp-7411-sh"]["dailyBudget"] = 35_000  # 승인 전에 광고주센터에서 바꿈
    r = _approve(owner, ws, ap["approval_id"]).json()
    assert "바뀌어" in _rows(r["job"])["cmp-7411-sh"]["error"] and _MOCK_STORE["7411"]["campaigns"]["cmp-7411-sh"]["dailyBudget"] == 35_000


def test_deleted_account_forgets_google_sub():
    from app.db import SessionLocal as S
    from app.models import User
    h = user("ap-del@a.com")
    with S() as db:
        u = db.query(User).filter(User.email == "ap-del@a.com").one()
        u.google_sub = "g-del"
        db.commit()
    assert c.post("/auth/delete-account", headers=h, json={"password": "password1"}).json()["ok"]
    with S() as db:
        assert db.query(User).filter(User.google_sub == "g-del").first() is None


def test_claimed_before_is_reference_only_and_large_job_fully_viewable():
    """승인 요청의 변경 전 값은 서버가 네이버에서 읽는다(보낸 값은 참고). 100건이 넘어도 실행 전에 전체 행을 볼 수 있다."""
    owner, ws, acc = _account("ap-big@a.com", "7413")
    MockNaverClient("7413")
    _off("7413", "cmp-7413-pl")
    fake = [ch(acc, "campaign", "cmp-7413-pl", "status", "ON"),  # 변경 전 값 없음 → 서버가 채움
            ch(acc, "campaign", "cmp-7413-sh", "daily_budget", "40000", before="90000")]  # 허위: 지금은 3만(→ 올리기)
    extra = [ch(acc, "keyword", f"kwd-7413-x{i}", "status", "OFF") for i in range(119)]  # 네이버에 없는 키워드 → 승인 요청을 만들 수 없음
    job = _job(owner, ws, fake + extra)
    r = c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner)
    assert r.status_code == 400 and "찾지 못했어요" in r.json()["detail"]
    st = _MOCK_STORE["7413"]
    for i in range(119):  # 실제로 있는 키워드로 채운다
        st["keywords"][f"kwd-7413-x{i}"] = {"nccKeywordId": f"kwd-7413-x{i}", "nccAdgroupId": "grp-7413-pl1", "keyword": f"k{i}",
                                            "userLock": False, "bidAmt": 100, "useGroupBidAmt": False}
    _, ap = _request(owner, ws, fake + extra)
    rows = {x["naver_id"]: x for x in ap["summary"]["rows"]}
    assert rows["cmp-7413-pl"]["before"] == "OFF" and "claimed_before" not in rows["cmp-7413-pl"]
    assert rows["cmp-7413-sh"]["before"] == "30000" and rows["cmp-7413-sh"]["claimed_before"] == "90000"
    assert len(ap["summary"]["rows"]) == 100 and ap["summary"]["more_rows"] == 21
    full = c.get(f"/workspaces/{ws}/bulk-jobs/{ap['job_id']}", headers=owner).json()  # 승인 화면의 '전체 보기'
    assert sum(len(a["rows"]) for a in full["accounts"]) == 121
    r = _approve(owner, ws, ap["approval_id"]).json()
    assert r["status"] in ("RUNNING", "APPROVED") or r["job"]["status"] == "RUNNING"  # 5행씩 이어서 실행


def test_missing_bid_fields_block_cost_increase():
    owner, ws, acc = _account("ap-miss@a.com", "7415")
    MockNaverClient("7415")
    st = _MOCK_STORE["7415"]
    st["keywords"]["kwd-7415-11"].update(userLock=True)
    del st["keywords"]["kwd-7415-11"]["bidAmt"]  # 입찰가 필드 없음 → 0원으로 보지 않는다
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "kwd-7415-11", "status", "ON")])["id"])
    assert out["status"] == "FAILED" and "확인할 수 없어" in _rows(out)["kwd-7415-11"]["error"]
    st["ads"]["ad-7415-sh1"].update(adAttr="??", userLock=True)  # 쇼핑 소재 입찰가 정보를 읽을 수 없음
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "ad", "ad-7415-sh1", "status", "ON")])["id"])
    assert out["status"] == "FAILED" and "확인할 수 없어" in _rows(out)["ad-7415-sh1"]["error"]
    del st["adgroups"]["grp-7415-pl2"]["bidAmt"]  # 그룹 입찰가 없음: 그룹 입찰가를 쓰는 키워드 입찰가 올리기도 판단 불가
    st["keywords"]["kwd-7415-21"]["useGroupBidAmt"] = True
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "kwd-7415-21", "bid_amt", "400", product="WEB_SITE")])["id"])
    assert out["status"] == "FAILED" and st["keywords"]["kwd-7415-21"]["bidAmt"] == 300


def test_lock_lease_renewed_and_lost_lock_stops(monkeypatch):
    """긴 실행 중 잠금 임대가 끝나 다른 작업이 가져가면, 남은 비용 행은 실행하지 않는다. 정상이면 행마다 임대를 연장한다."""
    owner, ws, acc = _account("ap-lease@a.com", "7416")
    MockNaverClient("7416")
    st = _MOCK_STORE["7416"]
    real_now, real_update = safety.now, MockNaverClient.update
    shift = {"s": 0}
    safety.now = lambda: real_now() + timedelta(seconds=shift["s"])

    def slow_update(self, *a, **kw):  # 네이버 호출 한 번에 60초 걸린다고 가정
        real_update(self, *a, **kw)
        shift["s"] += 60
    monkeypatch.setattr(MockNaverClient, "update", slow_update)
    try:
        changes = [ch(acc, "keyword", f"kwd-7416-1{k}", "bid_amt", str(100 + k * 10), product="WEB_SITE") for k in (1, 2, 3)]
        out = _run(owner, ws, _job(owner, ws, changes)["id"])  # 60초씩 3번 = 180초 > 임대 90초, 행마다 연장돼 모두 성공
        assert out["status"] == "DONE"

        def steal_after_first(self, *a, **kw):  # 첫 행 뒤 임대가 끝나고 다른 작업이 잠금을 가져감
            real_update(self, *a, **kw)
            shift["s"] += 100
            with SessionLocal() as db2:
                assert safety.take_lock(db2, acc)
        monkeypatch.setattr(MockNaverClient, "update", steal_after_first)
        changes = [ch(acc, "keyword", f"kwd-7416-2{k}", "bid_amt", str(100 + k * 10), product="WEB_SITE") for k in (1, 2)]
        r = _rows(_run(owner, ws, _job(owner, ws, changes)["id"]))
        assert r["kwd-7416-21"]["status"] == "SUCCESS" and r["kwd-7416-22"]["error"] == safety.LOCK_LOST
        assert st["keywords"]["kwd-7416-22"]["bidAmt"] == 600
    finally:
        safety.now = real_now


def test_network_error_marks_unknown_and_is_not_retried(monkeypatch):
    owner, ws, acc = _account("ap-net@a.com", "7417")
    MockNaverClient("7417")
    real = MockNaverClient.create_keyword

    def timeout_after_write(self, *a, **kw):  # 네이버엔 만들어졌지만 응답을 못 받음
        real(self, *a, **kw)
        raise bulk.NaverApiError("네트워크 오류: timed out")
    monkeypatch.setattr(MockNaverClient, "create_keyword", timeout_after_write)
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "grp-7417-pl1", "create", "새키워드|100", product="WEB_SITE")])["id"])
    assert _rows(out)["grp-7417-pl1"]["error"] == bulk.UNKNOWN
    monkeypatch.setattr(MockNaverClient, "create_keyword", real)
    retry = c.post(f"/workspaces/{ws}/bulk-jobs/{out['id']}/retry-failed", headers=owner).json()
    assert retry["counts"]["VALID"] == 0 and retry["counts"]["INVALID"] == 1  # 확인 없이 다시 만들지 않는다
    assert sum(k["keyword"] == "새키워드" for k in _MOCK_STORE["7417"]["keywords"].values()) == 1


def test_auto_bid_rechecks_permission_at_run():
    owner, ws, acc = _account("ap-abr@a.com", "7418")
    MockNaverClient("7418")
    staff, mid = _staff(owner, ws, acc, "ap-abr-s@a.com")
    url = f"/workspaces/{ws}/auto-bids"
    k = {"ad_account_id": acc, "naver_id": "kwd-7418-11", "keyword": "원피스1"}
    assert c.put(url, headers=staff, json={"keywords": [k], "device": "PC", "target_rank": 1, "max_bid": 1000, "ends_on": END}).status_code == 200
    _revoke(mid)  # 규칙을 승인(저장)한 직원의 권한 회수 → 다음 실행부터 바꾸지 않는다
    with SessionLocal() as db:
        bulk.run_all_auto_bids(db)
    assert _MOCK_STORE["7418"]["keywords"]["kwd-7418-11"]["bidAmt"] == 300
    assert "권한" in c.get(url, headers=owner).json()[0]["last_result"]


def test_place_lock_renewed_and_lost_lock_stops(monkeypatch):
    """플레이스 실행 중 네이버 호출이 길어 잠금 임대가 끝나고 다른 작업이 잠금을 가져가면, 남은 단계(광고그룹·소재 만들기)는 하지 않는다."""
    from test_place import _apply, _plan
    owner, ws, acc = _account("ap-plock@a.com", "7419")
    MockNaverClient("7419")
    st = _MOCK_STORE["7419"]
    params = {"business_id": "bsn-7419-place", "daily_budget": 10000, "use_advoost": True}
    aid = _plan(owner, ws, acc, "create", **params).json()["approval_id"]
    real_now, real_create = safety.now, MockNaverClient.create_campaign
    shift = {"s": 0}
    safety.now = lambda: real_now() + timedelta(seconds=shift["s"])

    def slow_create(self, *a, **kw):  # 캠페인 만들기가 오래 걸려 임대가 끝나고, 그사이 다른 작업이 잠금을 가져감
        out = real_create(self, *a, **kw)
        shift["s"] += 100
        with SessionLocal() as db2:
            assert safety.take_lock(db2, acc)
        return out
    monkeypatch.setattr(MockNaverClient, "create_campaign", slow_create)
    try:
        out = _apply(owner, ws, aid, acc, "create", **params).json()
    finally:
        safety.now = real_now
    groups = [g for g in st["adgroups"].values() if g.get("adgroupType") == "LOCAL_AD"]
    assert out["status"] == "PARTIAL" and not groups and safety.LOCK_LOST in out["steps"][-1]["error"]


def test_place_network_error_not_retried(monkeypatch):
    """플레이스 만들기 중 응답을 못 받으면(반영됐을 수 있음) '알 수 없음'으로 끝내고, 같은 승인으로 다시 실행해 중복 생성하지 않는다."""
    from test_place import _apply, _plan
    owner, ws, acc = _account("ap-pnet@a.com", "7420")
    MockNaverClient("7420")
    st = _MOCK_STORE["7420"]
    params = {"business_id": "bsn-7420-place", "daily_budget": 10000, "use_advoost": True}
    aid = _plan(owner, ws, acc, "create", **params).json()["approval_id"]
    real = MockNaverClient.create_campaign

    def written_but_no_reply(self, *a, **kw):
        real(self, *a, **kw)
        raise bulk.NaverApiError("네트워크 오류: timed out")
    monkeypatch.setattr(MockNaverClient, "create_campaign", written_but_no_reply)
    out = _apply(owner, ws, aid, acc, "create", **params).json()
    assert out["status"] == "FAILED" and "알 수 없어요" in out["steps"][0]["error"]
    monkeypatch.setattr(MockNaverClient, "create_campaign", real)
    assert _apply(owner, ws, aid, acc, "create", **params).status_code == 409  # 같은 승인으로 다시 실행 안 됨
    assert sum(c["campaignTp"] == "PLACE" for c in st["campaigns"].values()) == 1


def test_extension_lock_and_unknown_result(monkeypatch):
    """확장소재 등록: 조회 중 잠금을 잃으면 등록 요청을 보내지 않고, 잠금이 유지되면 등록되며, 응답이 끊기면 다시 보내지 않고 확인을 안내한다."""
    owner, ws, acc = _account("ap-ext@a.com", "7421")
    MockNaverClient("7421")
    st = _MOCK_STORE["7421"]
    body = {"ad_account_id": acc, "adgroup_naver_id": "grp-7421-pl1", "ext_type": "HEADLINE", "heading": "무료배송"}
    count = lambda: sum(e["ownerId"] == "grp-7421-pl1" for e in st["ad-extensions"].values())  # noqa: E731
    before = count()
    real_now, real_list, real_create = safety.now, MockNaverClient.list_campaigns, MockNaverClient.create_ad_extension
    shift = {"s": 0}
    safety.now = lambda: real_now() + timedelta(seconds=shift["s"])

    def slow_lookup(self):  # 안전장치 조회가 오래 걸리고 그사이 다른 작업이 잠금을 가져감
        shift["s"] += 100
        with SessionLocal() as db2:
            assert safety.take_lock(db2, acc)
        return real_list(self)
    monkeypatch.setattr(MockNaverClient, "list_campaigns", slow_lookup)
    try:
        r = c.post(f"/workspaces/{ws}/ad-extensions", headers=owner, json=body)
    finally:
        safety.now = real_now
    assert r.status_code == 409 and r.json()["detail"] == safety.LOCK_LOST and count() == before  # 보내지 않음
    monkeypatch.setattr(MockNaverClient, "list_campaigns", real_list)
    with SessionLocal() as db:  # 가져간 작업이 끝난 상태
        db.query(safety.AccountLock).delete()
        db.commit()
    assert c.post(f"/workspaces/{ws}/ad-extensions", headers=owner, json=body).status_code == 200 and count() == before + 1

    def written_but_no_reply(self, *a, **kw):
        real_create(self, *a, **kw)
        raise bulk.NaverApiError("네트워크 오류: timed out")
    monkeypatch.setattr(MockNaverClient, "create_ad_extension", written_but_no_reply)
    r = c.post(f"/workspaces/{ws}/ad-extensions", headers=owner, json=body)
    assert r.status_code == 400 and r.json()["detail"] == bulk.UNKNOWN and count() == before + 2  # 한 번만 보냄, 확인 안내


def test_reject_audit_once_and_preview_audit_has_account():
    # D1은 문장마다 바로 저장돼 기록을 먼저 남긴다. 두 번째 거절(409)은 기록을 남기지 않는다
    owner, ws, acc = _account("ap-audit@a.com", "7499")
    MockNaverClient("7499")
    _off("7499", "cmp-7499-pl")
    job, ap = _request(owner, ws, [ch(acc, "campaign", "cmp-7499-pl", "status", "ON", before="OFF")])
    url = f"/workspaces/{ws}/approvals/{ap['approval_id']}/reject"
    assert c.post(url, headers=owner).status_code == 200 and c.post(url, headers=owner).status_code == 409
    logs = c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()
    assert [l["action"] for l in logs if l["job_id"] == job["id"]] == ["APPROVAL_REJECTED", "APPROVAL_PENDING", "JOB_PREVIEW"]
    assert all(l["ad_account_id"] == acc for l in logs if l["job_id"] == job["id"])
    done = _run(owner, ws, _job(owner, ws, [ch(acc, "campaign", "cmp-7499-pl", "status", "OFF")])["id"])
    assert any(l["action"] == "JOB_DONE" and l["ad_account_id"] == acc
               for l in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json() if l["job_id"] == done["id"])


def test_claude_direct_per_account_admin_only():
    # 관리자가 웹에서 켠 계정만: 캠페인 켜기가 웹 승인 없이 Claude 허용 버튼으로 실행된다. 직원·Claude 토큰은 못 켠다
    owner, ws, acc = _account("ap-direct@a.com", "7498")
    MockNaverClient("7498")
    _off("7498", "cmp-7498-pl")
    url = f"/workspaces/{ws}/ad-accounts/{acc}/safety/claude-direct"
    staff, _ = _staff(owner, ws, acc, "ap-direct-staff@a.com")
    h = _mcp_headers(owner)
    assert c.put(url, json={"on": True}, headers=staff).status_code == 403
    assert c.put(url, json={"on": True}, headers=h).status_code == 401
    on = [ch(acc, "campaign", "cmp-7498-pl", "status", "ON")]
    pv, _ = _mcp_call(h, "preview_changes", workspace_id=ws, changes=on)
    assert _mcp_call(h, "execute_job", workspace_id=ws, job_id=pv["id"])[0]["approval"]["status"] == "PENDING"
    assert c.put(url, json={"on": True}, headers=owner).status_code == 200
    assert _mcp_call(h, "get_ad_safety", workspace_id=ws, ad_account_id=acc)[0]["claude_direct"] is True
    pv, _ = _mcp_call(h, "preview_changes", workspace_id=ws, changes=on)
    out, _ = _mcp_call(h, "execute_job", workspace_id=ws, job_id=pv["id"])
    assert "approval" not in out and out["status"] == "DONE" and _MOCK_STORE["7498"]["campaigns"]["cmp-7498-pl"]["userLock"] is False
    logs = c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()
    assert any(l["action"] == "CLAUDE_DIRECT_SET" and l["after"] == "ON" for l in logs)
