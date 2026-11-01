"""광고비 안전장치(safety.py)와 승인: 합계 계산·계산 불가, 입찰가 상한·미설정, 웹·Claude·예약·자동입찰 우회 시도, 다른 계정,
승인 후 네이버 설정 변경, 네이버 조회 실패·일부 실패, 자동입찰 범위·중지, 긴급 중지. 네이버는 Mock만 쓴다.
Mock 계정 기본값: 켜진 캠페인 파워링크(하루예산 5만, 그룹1 2만·그룹2 무제한) + 쇼핑(3만) = 합계 8만."""
from datetime import timedelta

from test_core import END, _account, _mcp_call, _mcp_headers, _safe, _viewer, c, ch, user

from app import bulk, safety
from app.db import SessionLocal
from app.models import today_kst
from app.naver import _MOCK_STORE, MockNaverClient


def _job(h, ws, changes):
    return c.post(f"/workspaces/{ws}/bulk-jobs", headers=h, json={"changes": changes}).json()


def _run(h, ws, job_id):
    return c.post(f"/workspaces/{ws}/bulk-jobs/{job_id}/execute", headers=h).json()


def _rows(job):
    return {r["naver_id"]: r for a in job["accounts"] for r in a["rows"]}


def _fresh(email, cid):
    """안전장치 미설정 계정(_account가 넉넉하게 정해 둔 것을 지운다)."""
    owner, ws, acc = _account(email, cid)
    with SessionLocal() as db:
        db.delete(safety.get(db, ws, acc))
        db.commit()
    return owner, ws, acc


def test_totals_shared_and_uncomputable():
    cid = "7301"
    MockNaverClient(cid)
    st = _MOCK_STORE[cid]
    total, reasons, rows = safety.Snapshot(MockNaverClient(cid)).total()
    assert total == 80_000 and not reasons and {r["name"]: r["from"] for r in rows} == {"파워링크_브랜드": "campaign", "쇼핑검색_상품": "campaign"}
    # 캠페인 예산이 없으면 켜진 광고그룹 예산의 합(캠페인과 그룹을 중복해서 더하지 않음). 무제한 그룹이 켜져 있으면 계산 불가
    st["campaigns"][f"cmp-{cid}-pl"]["dailyBudget"] = 0
    total, reasons, _ = safety.Snapshot(MockNaverClient(cid)).total()
    assert total is None and "무제한" in reasons[0]
    st["adgroups"][f"grp-{cid}-pl2"]["userLock"] = True
    assert safety.Snapshot(MockNaverClient(cid)).total()[0] == 20_000 + 30_000
    st["campaigns"][f"cmp-{cid}-sh"]["sharedBudgetId"] = "sbg-1"
    total, reasons, _ = safety.Snapshot(MockNaverClient(cid)).total()
    assert total is None and "공유예산" in reasons[0]


def test_setup_status_and_admin_only():
    owner, ws, acc = _fresh("sf-setup@a.com", "7302")
    st = c.get(f"/workspaces/{ws}/ad-accounts/{acc}/safety", headers=owner).json()
    assert not st["configured"] and st["total"] == 80_000 and st["needs_action"] and "절대 상한이 아니에요" in st["note"]
    assert c.get(f"/workspaces/{ws}/ad-accounts", headers=owner).json()[0]["safety"] is None
    body = {"daily_budget_limit": 100_000, "max_bid": 1_000}
    assert c.put(f"/workspaces/{ws}/ad-accounts/{acc}/safety", headers=owner, json=body).status_code == 400  # 확인 표시 없이 저장 안 함
    viewer = _viewer(owner, ws, acc, "sf-setup-v@a.com")
    assert c.put(f"/workspaces/{ws}/ad-accounts/{acc}/safety", headers=viewer, json={**body, "confirmed": True}).status_code == 403
    other, ws_b, _ = _account("sf-setup-b@a.com", "7303")
    assert c.put(f"/workspaces/{ws_b}/ad-accounts/{acc}/safety", headers=other, json={**body, "confirmed": True}).status_code == 403
    st = c.put(f"/workspaces/{ws}/ad-accounts/{acc}/safety", headers=owner, json={**body, "confirmed": True}).json()
    assert st["configured"] and not st["needs_action"] and st["daily_budget_limit"] == 100_000
    _safe(owner, ws, acc, limit=50_000, max_bid=1_000)  # 이미 기준을 넘는 상태 → 조치 안내
    st = c.get(f"/workspaces/{ws}/ad-accounts/{acc}/safety", headers=owner).json()
    assert st["needs_action"] and any("80,000원" in a for a in st["actions"])
    logs = [x for x in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json() if x["action"] == "SAFETY_SET"]
    assert [x["after"] for x in logs][:2] == ["50000/1000", "100000/1000"] and logs[0]["before"] == "100000/1000"  # 최신순


def test_unset_blocks_increases_but_allows_stop_and_decrease():
    owner, ws, acc = _fresh("sf-unset@a.com", "7304")
    job = _job(owner, ws, [ch(acc, "keyword", "kwd-7304-11", "bid_amt", "400", product="WEB_SITE"),
                           ch(acc, "campaign", "cmp-7304-pl", "daily_budget", "40000"),
                           ch(acc, "keyword", "kwd-7304-12", "status", "OFF")])
    assert any(not s["ok"] and "아직" in s["reason"] for s in job["safety"])
    r = _rows(_run(owner, ws, job["id"]))
    assert r["kwd-7304-11"]["status"] == "FAILED" and "아직" in r["kwd-7304-11"]["error"]
    assert r["cmp-7304-pl"]["status"] == "SUCCESS" and r["kwd-7304-12"]["status"] == "SUCCESS"  # 예산 줄이기·끄기는 허용
    assert _MOCK_STORE["7304"]["keywords"]["kwd-7304-11"]["bidAmt"] == 300


def test_bid_cap_preview_and_execute():
    owner, ws, acc = _account("sf-bid@a.com", "7305")
    _safe(owner, ws, acc, limit=1_000_000, max_bid=500)
    job = _job(owner, ws, [ch(acc, "keyword", "kwd-7305-11", "bid_amt", "600", product="WEB_SITE"),
                           ch(acc, "keyword", "kwd-7305-12", "bid_amt", "500", product="WEB_SITE"),
                           ch(acc, "keyword", "grp-7305-pl1", "create", "새키워드|900", product="WEB_SITE")])
    r = _rows(job)
    assert r["kwd-7305-11"]["status"] == "INVALID" and "최대 입찰가 500원" in r["kwd-7305-11"]["error"]
    assert r["grp-7305-pl1"]["status"] == "INVALID" and r["kwd-7305-12"]["status"] == "VALID"
    # 미리보기 뒤 관리자가 상한을 낮추면 실행 때 다시 막힌다
    _safe(owner, ws, acc, limit=1_000_000, max_bid=400)
    r = _rows(_run(owner, ws, job["id"]))
    assert r["kwd-7305-12"]["status"] == "FAILED" and "400원" in r["kwd-7305-12"]["error"]


def test_budget_total_web_mcp_partial_and_naver_failure(monkeypatch):
    owner, ws, acc = _account("sf-total@a.com", "7306")
    _safe(owner, ws, acc, limit=90_000, max_bid=10_000)
    # 웹: 파워링크 5만→7만이면 합계 10만 > 9만 → 막힘. 같은 작업의 끄기 행은 그대로 실행 = 일부 성공
    job = _job(owner, ws, [ch(acc, "campaign", "cmp-7306-pl", "daily_budget", "70000"),
                           ch(acc, "keyword", "kwd-7306-11", "status", "OFF")])
    assert job["safety"][0]["ok"] is False and "100,000원" in job["safety"][0]["reason"]
    out = _run(owner, ws, job["id"])
    r = _rows(out)
    assert out["status"] == "PARTIAL" and r["cmp-7306-pl"]["status"] == "FAILED" and "90,000원" in r["cmp-7306-pl"]["error"]
    assert _MOCK_STORE["7306"]["campaigns"]["cmp-7306-pl"]["dailyBudget"] == 50_000
    # Claude(MCP): 같은 검사
    h = _mcp_headers(owner)
    pv, _ = _mcp_call(h, "preview_changes", workspace_id=ws, changes=[ch(acc, "campaign", "cmp-7306-pl", "daily_budget", "70000")])
    assert pv["safety"][0]["ok"] is False
    out, _ = _mcp_call(h, "execute_job", workspace_id=ws, job_id=pv["id"])
    assert out["status"] == "FAILED" and "관리 기준" in _rows(out)["cmp-7306-pl"]["error"]
    # 기준 안이면 실행
    assert _run(owner, ws, _job(owner, ws, [ch(acc, "campaign", "cmp-7306-pl", "daily_budget", "60000")])["id"])["status"] == "DONE"
    # 네이버 재조회 실패 → 실행하지 않음
    monkeypatch.setattr(MockNaverClient, "list_campaigns", lambda self: (_ for _ in ()).throw(bulk.NaverApiError("503 점검 중")))
    out = _run(owner, ws, _job(owner, ws, [ch(acc, "keyword", "kwd-7306-12", "status", "ON")])["id"])
    assert out["status"] == "FAILED" and "읽지 못해" in _rows(out)["kwd-7306-12"]["error"]


def test_scheduled_checked_at_schedule_and_run():
    owner, ws, acc = _account("sf-sched@a.com", "7307")
    _MOCK_STORE["7307"]["campaigns"]["cmp-7307-pl"]["userLock"] = True  # 꺼진 캠페인(합계 3만)
    _safe(owner, ws, acc, limit=60_000, max_bid=10_000)
    at = (bulk.now() + timedelta(hours=1)).isoformat()
    too_much = _job(owner, ws, [ch(acc, "campaign", "cmp-7307-pl", "daily_budget", "40000"),
                                ch(acc, "campaign", "cmp-7307-pl", "status", "ON")])
    r = c.post(f"/workspaces/{ws}/bulk-jobs/{too_much['id']}/schedule", headers=owner, json={"scheduled_at": at})
    assert r.status_code == 400 and "예약할 수 없어요" in r.json()["detail"]
    ok = _job(owner, ws, [ch(acc, "campaign", "cmp-7307-pl", "status", "ON")])  # 3만+5만 = 8만 > 6만 → 역시 막힘
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{ok['id']}/schedule", headers=owner, json={"scheduled_at": at}).status_code == 400
    _safe(owner, ws, acc, limit=80_000, max_bid=10_000)
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{ok['id']}/schedule", headers=owner, json={"scheduled_at": at}).status_code == 200
    # 예약 뒤 네이버에서 쇼핑 예산을 올렸다(외부 변경) → 실행 시점 재조회에서 막고 실행하지 않는다
    _MOCK_STORE["7307"]["campaigns"]["cmp-7307-sh"]["dailyBudget"] = 50_000
    with SessionLocal() as db:
        from app.models import BulkJob
        job = db.get(BulkJob, ok["id"])
        job.scheduled_at = bulk.now() - timedelta(minutes=1)
        db.commit()
        bulk.run_scheduled_jobs(db)
    out = c.get(f"/workspaces/{ws}/bulk-jobs/{ok['id']}", headers=owner).json()
    assert out["status"] == "FAILED" and "100,000원" in _rows(out)["cmp-7307-pl"]["error"]
    assert _MOCK_STORE["7307"]["campaigns"]["cmp-7307-pl"]["userLock"] is True


def test_auto_bid_scope_caps_expiry_and_stop():
    owner, ws, acc = _account("sf-ab@a.com", "7308")
    _safe(owner, ws, acc, limit=1_000_000, max_bid=500)
    url = f"/workspaces/{ws}/auto-bids"
    k = {"ad_account_id": acc, "naver_id": "kwd-7308-11", "keyword": "원피스1"}  # 300원, Mock 화면 4위
    base = {"keywords": [k], "device": "PC", "target_rank": 1}
    assert "계정의 클릭당 최대 입찰가 500원" in c.put(url, headers=owner, json={**base, "max_bid": 1000, "ends_on": END}).json()["detail"]
    assert "기간" in c.put(url, headers=owner, json={**base, "max_bid": 500}).json()["detail"]
    late = (today_kst() + timedelta(days=91)).isoformat()
    assert c.put(url, headers=owner, json={**base, "max_bid": 500, "ends_on": late}).status_code == 400
    out = c.put(url, headers=owner, json={**base, "max_bid": 500, "ends_on": END}).json()
    assert out["scope"]["max_bid"] == 500 and out["scope"]["ends_on"] == END and "다시 승인" in out["scope"]["how"]
    kws = _MOCK_STORE["7308"]["keywords"]
    c.post(f"{url}/run", headers=owner)
    assert kws["kwd-7308-11"]["bidAmt"] == 360
    # 관리자가 계정 상한을 낮추면 승인 범위(500)보다 낮은 계정 상한이 적용된다
    _safe(owner, ws, acc, limit=1_000_000, max_bid=400)
    c.post(f"{url}/run", headers=owner)
    assert kws["kwd-7308-11"]["bidAmt"] == 400
    # 기간이 끝나면 실행하지 않는다
    with SessionLocal() as db:
        from app.models import AutoBidRule
        db.query(AutoBidRule).filter(AutoBidRule.keyword_naver_id == "kwd-7308-11").update({"ends_on": today_kst() - timedelta(days=1)})
        db.commit()
    kws["kwd-7308-11"]["bidAmt"] = 300
    c.post(f"{url}/run", headers=owner)
    assert kws["kwd-7308-11"]["bidAmt"] == 300 and "기간" in c.get(url, headers=owner).json()[0]["last_result"]
    # 중지는 언제든(기간 없이)
    assert c.put(url, headers=owner, json={**base, "max_bid": 500, "enabled": False}).status_code == 200
    assert c.get(url, headers=owner).json()[0]["enabled"] is False


def test_auto_bid_unset_safety_blocks():
    owner, ws, acc = _fresh("sf-ab2@a.com", "7309")
    r = c.put(f"/workspaces/{ws}/auto-bids", headers=owner,
              json={"keywords": [{"ad_account_id": acc, "naver_id": "kwd-7309-11"}], "device": "PC", "target_rank": 1, "max_bid": 500, "ends_on": END})
    assert r.status_code == 400 and "아직" in r.json()["detail"]


def test_place_approval_after_naver_change_and_audits():
    owner, ws, acc = _account("sf-pl@a.com", "7310")
    _safe(owner, ws, acc, limit=95_000, max_bid=1_000)
    from test_place import _apply, _new_place, _plan
    _, camp, _ = _new_place(owner, ws, acc, "7310")  # 꺼진 플레이스 캠페인 1만
    params = {"target_type": "campaign", "target_id": camp["nccCampaignId"]}
    aid = _plan(owner, ws, acc, "turn_on", **params).json()["approval_id"]  # 8만+1만 = 9만 ≤ 9.5만
    _MOCK_STORE["7310"]["campaigns"]["cmp-7310-sh"]["dailyBudget"] = 40_000  # 승인 뒤 네이버에서 예산을 올림
    out = _apply(owner, ws, aid, acc, "turn_on", **params).json()
    assert out["status"] == "FAILED" and "100,000원" in out["error"] and _MOCK_STORE["7310"]["campaigns"][camp["nccCampaignId"]]["userLock"]
    aid2 = _plan(owner, ws, acc, "set_budget", campaign_id=camp["nccCampaignId"], daily_budget=5000).json()["approval_id"]
    assert c.post(f"/workspaces/{ws}/place/cancel", headers=owner, json={"approval_id": aid2}).json()["status"] == "REJECTED"
    assert _apply(owner, ws, aid2, acc, "set_budget", campaign_id=camp["nccCampaignId"], daily_budget=5000).status_code == 409
    acts = {x["action"] for x in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json() if x["entity_type"] == "approval"}
    assert {"APPROVAL_PENDING", "APPROVAL_FAILED", "APPROVAL_REJECTED", "APPROVAL_SUCCESS"} <= acts


def test_emergency_stop_needs_no_approval_or_safety():
    owner, ws, acc = _fresh("sf-stop@a.com", "7311")
    r = c.post(f"/workspaces/{ws}/stop", headers=owner, json={"ad_account_id": acc, "entity_type": "campaign", "naver_id": "cmp-7311-pl"})
    assert r.status_code == 200 and _MOCK_STORE["7311"]["campaigns"]["cmp-7311-pl"]["userLock"] is True
    out, err = _mcp_call(_mcp_headers(owner), "stop_ad", workspace_id=ws, ad_account_id=acc, entity_type="keyword", naver_id="kwd-7311-11")
    assert not err and _MOCK_STORE["7311"]["keywords"]["kwd-7311-11"]["userLock"] is True
    assert sum(x["action"] == "EMERGENCY_STOP" for x in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()) == 2
    viewer = _viewer(owner, ws, acc, "sf-stop-v@a.com")  # 수정 권한은 필요
    assert c.post(f"/workspaces/{ws}/stop", headers=viewer, json={"ad_account_id": acc, "entity_type": "campaign",
                                                                   "naver_id": "cmp-7311-sh"}).status_code == 403
    outsider = user("sf-stop-o@a.com")
    assert c.post(f"/workspaces/{ws}/stop", headers=outsider, json={"ad_account_id": acc, "entity_type": "campaign",
                                                                     "naver_id": "cmp-7311-sh"}).status_code == 403


def test_mcp_get_ad_safety():
    owner, ws, acc = _account("sf-mcp@a.com", "7312")
    out, err = _mcp_call(_mcp_headers(owner), "get_ad_safety", workspace_id=ws, ad_account_id=acc)
    assert not err and out["configured"] and out["total"] == 80_000
