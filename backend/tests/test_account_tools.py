"""account_tools.py: 비즈머니·노출 제한 IP·비즈채널·타기팅·대용량 보고서 Claude 도구. 네이버는 Mock만 쓴다."""
import json

from test_core import _account, _mcp_headers, _viewer, c


def _tool(h, ws, acc):
    """도구 인자에 name이 있어(비즈채널 이름) test_core._mcp_call 대신 인자를 dict로 보낸다."""
    def call(tool, **a):
        r = c.post("/mcp", headers=h, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                            "params": {"name": tool, "arguments": {"workspace_id": ws, "ad_account_id": acc, **a}}})
        res = r.json()["result"]
        return json.loads(res["content"][0]["text"]), res["isError"]
    return call


def test_adgroup_daily_budget():
    """광고그룹 하루예산은 미리보기 → 실행으로 바꾸고, 계정 합계를 늘리지 않아 웹 승인 없이 실행된다."""
    from app.naver import _MOCK_STORE

    owner, ws, acc = _account("grpbud@a.com", "9502")
    ch = lambda nid, v: {"entity_type": "adgroup", "naver_id": nid, "field": "daily_budget", "value": v, "ad_account_id": acc}  # noqa: E731
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [ch("grp-9502-pl1", "30000"), ch("grp-9502-pl2", "15")]}).json()
    assert [r["status"] for a in job["accounts"] for r in a["rows"]] == ["VALID", "INVALID"]  # 50원 미만
    out = c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner).json()
    assert "approval" not in out and out["status"] in ("DONE", "PARTIAL")
    g = _MOCK_STORE["9502"]["adgroups"]["grp-9502-pl1"]
    assert g["dailyBudget"] == 30000 and g["useDailyBudget"]


def test_account_tools():
    owner, ws, acc = _account("tools@a.com", "9501")
    h = _mcp_headers(owner)
    call = _tool(h, ws, acc)

    money, err = call("get_bizmoney", since="2026-11-01", until="2026-11-03")
    assert not err and money["balance"]["bizmoney"] == 152000 and len(money["rows"]) == 3
    assert [r["date"] for r in money["rows"]] == ["2026-11-01", "2026-11-02", "2026-11-03"] and money["rows"][0]["useRefundableAmt"] == 8000
    spent, err = call("get_bizmoney", since="2026-11-01", until="2026-11-03", history="exhaust")
    assert not err and spent["rows"] == [{"campaignTp": 1, "useRefundableAmt": 812, "date": "2026-11-03"}]  # 원 단위·0원 칸 빼기
    assert call("get_bizmoney", since="2026-01-01", until="2026-11-03")[1]  # 93일 넘음

    assert call("add_ip_exclusion", ip="1.2.3.999")[1]  # 형식 오류
    ip, err = call("add_ip_exclusion", ip=" 1.2.3.4 ", memo="경쟁사")
    assert not err and ip["filterIp"] == "1.2.3.4"
    assert call("add_ip_exclusion", ip="1.2.3.4")[1]  # 네이버 거부(중복)는 오류로
    assert [x["filterIp"] for x in call("list_ip_exclusions")[0]] == ["1.2.3.4"]
    assert not call("delete_ip_exclusion", ip_filter_id=ip["ipFilterId"], ip="1.2.3.4")[1]
    assert call("list_ip_exclusions")[0] == []

    assert call("create_site_channel", name="새 사이트", url="example.com")[1]  # http(s) 없음
    ch, err = call("create_site_channel", name="새 사이트", url="https://new.example.com")
    assert not err and ch["inspectStatus"] == "UNDER_REVIEW"
    assert not call("reinspect_channel", channel_id=ch["nccBusinessChannelId"])[1]

    grp = "grp-9501-pl1"
    t, err = call("get_targeting", adgroup_id=grp, type="DV", codes=True)
    assert not err and t["current"] == [] and {x["code"] for x in t["codes"]} == {"PC", "MOBILE"}
    assert call("set_targeting", adgroup_id=grp, type="DV", codes=[" "])[1]  # 빈 목록이면 전부 꺼지므로 막는다
    assert call("set_targeting", adgroup_id=grp, type="AD", codes=["x"])[1]  # 지원 안 하는 유형
    out, err = call("set_targeting", adgroup_id=grp, type="DV", codes=["MOBILE", "MOBILE"])
    assert not err and [x["dictionaryCode"] for x in out] == ["MOBILE"]

    assert call("request_stat_report", report_type="AD", date="2099-01-01")[1]  # 오늘 이후
    job, err = call("request_stat_report", report_type="EXPKEYWORD", date="2026-11-08")
    assert not err
    rep, err = call("get_stat_report", report_job_id=job["reportJobId"])
    assert not err and rep["total_lines"] == len(rep["preview"]) > 0

    # 입찰가 예측: 순위·최소·성과, 쇼핑은 position·minimum만
    est, err = call("estimate_bid", kind="position", keys=["원피스"], device="PC", positions=[1, 3])
    assert not err and [x["bid"] for x in est["estimate"]] == [1000, 333]
    assert not call("estimate_bid", kind="minimum", keys=["원피스"], device="MOBILE")[1]
    perf, err = call("estimate_bid", kind="performance", keys=["원피스", "롱 원피스"], device="PC", bids=[100, 500])
    assert not err and len(perf["items"]) == 4
    assert call("estimate_bid", kind="performance", keys=["원피스"], device="PC")[1]  # 입찰가 없음
    assert call("estimate_bid", kind="median", product="SHOPPING", keys=["123"], device="PC")[1]
    assert not call("estimate_bid", kind="position", product="SHOPPING", keys=["123"], device="PC", positions=[1])[1]

    hist, err = call("get_inspect_history", ids=["kwd-9501-11"])
    assert not err and hist[0]["id"] == "kwd-9501-11"
    assert not call("request_inspect", kind="keyword", naver_id="kwd-9501-11")[1]
    assert call("request_inspect", kind="campaign", naver_id="x")[1]

    copied, err = call("copy_ads", ad_ids=["ad-9501-pl1"], target_adgroup_id="grp-9501-pl2")
    assert not err and copied[0]["userLock"] is True and copied[0]["nccAdgroupId"] == "grp-9501-pl2"  # 복사본은 OFF

    opt, err = call("set_adgroup_options", adgroup_id=grp, use_exp_search=False, ai_ads_opt_in=False)
    assert not err and opt["useExpSearch"] is False and opt["aiAdsOptIn"] is False
    assert call("set_adgroup_options", adgroup_id=grp, ai_ads_opt_in=True)[1]  # ADVoost Max 켜기는 웹 승인 대상
    assert call("set_adgroup_options", adgroup_id=grp)[1]

    logs = {(x["entity_type"], x["action"]) for x in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()}
    assert {("ip_exclusion", "CREATE"), ("ip_exclusion", "DELETE"), ("channel", "CREATE"), ("channel", "UPDATE"),
            ("targeting", "UPDATE"), ("keyword", "UPDATE"), ("ad", "CREATE"), ("adgroup", "UPDATE")} <= logs

    # 보기 권한만 있으면 조회는 되고 변경은 안 된다
    v = _mcp_headers(_viewer(owner, ws, acc, "toolsv@a.com"))
    vcall = _tool(v, ws, acc)
    assert not vcall("list_ip_exclusions")[1] and not vcall("get_bizmoney")[1]
    for tool, a in (("add_ip_exclusion", {"ip": "5.6.7.8"}), ("create_site_channel", {"name": "x", "url": "https://x.com"}),
                    ("set_targeting", {"adgroup_id": grp, "type": "DV", "codes": ["PC"]}),
                    ("copy_ads", {"ad_ids": ["ad-9501-pl1"], "target_adgroup_id": grp}),
                    ("set_adgroup_options", {"adgroup_id": grp, "use_exp_search": True})):
        assert vcall(tool, **a)[1], tool


def test_search_terms_real_layout():
    """실계정 EXPKEYWORD 줄(2026-11-08) 그대로: 같은 검색어의 기기·매체별 줄을 합치고 비용 큰 순."""
    from app.account_tools import search_terms

    lines = ["20261108\t4286027\tcmp-a\tgrp-35\t수제말랑이\t8753\tM\t0\t106\t6\t561\t0",
             "20261108\t4286027\tcmp-a\tgrp-35\t수제말랑이\t122875\tP\t0\t1\t0\t0\t0",
             "20261108\t4286027\tcmp-a\tgrp-33\t슬랑이\t8753\tM\t1\t542\t1\t142\t0",
             "20261108\t4286027\tcmp-a\tgrp-33\t퐁퐁미니\t8753\tM\t1\t1\t0\t0\t0", "깨진 줄"]
    out = search_terms(lines)
    assert out["terms"] == 3 and out["total_cost"] == 703 and out["total_clicks"] == 7
    assert out["rows"][0] == {"adgroup_id": "grp-35", "search_term": "수제말랑이", "impressions": 107, "clicks": 6, "cost": 561}


def test_media_exp_negative_keyword_url():
    owner, ws, acc = _account("media@a.com", "9503")
    call = _tool(_mcp_headers(owner), ws, acc)
    grp = "grp-9503-pl1"

    assert call("get_media_target", adgroup_id=grp)[0]["type"] == 1  # 기본은 모든 매체
    assert call("set_media_target", adgroup_id=grp, search=[], contents=[])[1]  # 다 끄기는 막는다
    out, err = call("set_media_target", adgroup_id=grp, search=["naver", "partner"], contents=[])
    assert not err and out["type"] == 2 and out["search"] == ["naver", "partner"] and out["contents"] == []
    out, _ = call("set_media_target", adgroup_id=grp, search=["partner", "naver"], contents=["naver", "partner"])
    assert out["type"] == 1  # 전부 켜면 '모든 매체' 형식

    added, err = call("add_exp_negative_keywords", adgroup_id=grp, keywords=["만드는법", " 만드는법 ", "도안"])
    assert not err and [x["keyword"] for x in added["added"]] == ["만드는법", "도안"] and added["failed"] == []
    lst, _ = call("list_exp_negative_keywords", adgroup_id=grp)
    assert {x["keyword"] for x in lst} == {"만드는법", "도안"}
    assert call("list_negative_keywords", adgroup_id=grp)[0] == []  # 일반 제외검색어와 섞이지 않는다
    assert not call("delete_exp_negative_keyword", adgroup_id=grp, naver_id=lst[0]["naver_id"], keyword=lst[0]["keyword"])[1]
    assert len(call("list_exp_negative_keywords", adgroup_id=grp)[0]) == 1

    opt, err = call("set_adgroup_options", adgroup_id=grp, exp_search_budget_ratio=40)
    assert not err and opt["expSearchBudgetRatio"] == 40
    assert call("set_adgroup_options", adgroup_id=grp, exp_search_budget_ratio=0)[1]

    assert call("set_keyword_url", keyword_id="kwd-9503-11", pc_url="example.com")[1]
    assert not call("set_keyword_url", keyword_id="kwd-9503-11", pc_url="https://example.com/a")[1]

    job, _ = call("request_stat_report", report_type="EXPKEYWORD", date="2026-11-08")
    from app.naver import MockNaverClient
    assert MockNaverClient("9503").stat_file(job).count("\n") == 3  # Mock 파일도 실계정과 같은 12칸


def test_get_stats():
    owner, ws, acc = _account("stats@a.com", "9504")
    call = _tool(_mcp_headers(owner), ws, acc)
    out, err = call("get_stats", ids=["grp-9504-pl1"], breakdown="hh24", today=True)
    assert not err and out["period"] == "today" and len(out["data"][0]["breakdowns"]) == 24
    out, err = call("get_stats", ids=["grp-9504-pl1", "grp-9504-pl2"], since="2026-11-01", until="2026-11-07")
    assert not err and len(out["data"]) == 2 and "purchaseCcnt" in out["data"][0]
    assert call("get_stats", ids=["a", "b"], breakdown="dayw")[1]  # 쪼개 보기는 1개만
    assert call("get_stats", ids=["a"], breakdown="month")[1]
    assert call("get_stats", ids=["a"], since="2026-01-01", until="2026-11-07")[1]  # 93일 넘음
