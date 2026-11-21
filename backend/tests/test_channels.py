"""channels.py: 메타·구글 계정 연결과 네이버와 나란히 보는 성과(get_cross_channel_performance). 외부 API는 가짜 응답."""
import json
from urllib.parse import parse_qs, unquote, urlsplit

import httpx

from test_core import _account, _mcp_headers, _viewer, c


class R:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        return self.data


def _fake(monkeypatch, sent):
    def get(url, params=None, headers=None, **kw):
        sent.append(("GET", url, params, headers))
        if headers["Authorization"] != "Bearer meta-tok":
            return R({"error": {"message": "Invalid OAuth access token", "code": 190}}, 400)
        if url.endswith("/act_111"):
            return R({"name": "메타 광고계정", "currency": "KRW", "account_status": 1})
        if (params or {}).get("after") == "c2":
            return R({"data": [{"campaign_id": "m2", "campaign_name": "리타겟", "impressions": "100", "clicks": "5", "spend": "2000",
                                "account_currency": "KRW"}]})
        return R({"data": [{"campaign_id": "m1", "campaign_name": "구매", "impressions": "1000", "clicks": "20", "spend": "10000.4",
                            "account_currency": "KRW", "actions": [{"action_type": "purchase", "value": "3"}, {"action_type": "omni_purchase", "value": "4"}],
                            "action_values": [{"action_type": "omni_purchase", "value": "50000"}]}],
                  "paging": {"cursors": {"after": "c2"}, "next": "https://graph.facebook.com/next"}})

    def post(url, data=None, json=None, headers=None, **kw):
        sent.append(("POST", url, data or json, headers))
        if url == "https://oauth2.googleapis.com/token":
            if data["grant_type"] == "authorization_code":
                return R({"access_token": "a", "refresh_token": "g-refresh", "scope": "openid https://www.googleapis.com/auth/adwords email"})
            return R({"access_token": "g-access"})
        if "descriptive_name" in json["query"]:
            return R({"results": [{"customer": {"descriptiveName": "구글 광고"}}]})
        if "FROM conversion_action" in json["query"]:
            act = lambda i, name, inc: {"conversionAction": {"resourceName": f"customers/1/conversionActions/{i}", "id": i, "name": name,  # noqa: E731
                                                            "category": "PURCHASE", "status": "ENABLED", "countingType": "ONE_PER_CLICK",
                                                            "includeInConversionsMetric": inc, "clickThroughLookbackWindowDays": "30"}}
            return R({"results": [act("1", "구매", True), act("2", "장바구니", False), act("3", "전화", True)]})
        if "FROM customer" in json["query"]:  # 액션 × 날짜, 전환 0인 날은 행 없음, 4는 삭제된 액션
            row = lambda i, d, n: {"segments": {"conversionAction": f"customers/1/conversionActions/{i}", "date": d},  # noqa: E731
                                   "metrics": {"conversions": n if i == "1" else 0, "conversionsValue": n * 1000.0, "allConversions": n, "allConversionsValue": n * 1000.0}}
            return R({"results": [row("1", "2026-11-03", 2), row("1", "2026-11-05", 1), row("2", "2026-11-02", 7), row("4", "2026-11-06", 9)]})
        if "conversion_action_name" in json["query"]:
            return R({"results": [{"campaign": {"id": "9", "name": "검색"}, "segments": {"conversionActionName": "구매"},
                                   "metrics": {"conversions": 3.0, "conversionsValue": 3000.0, "allConversions": 3.0, "allConversionsValue": 3000.0}},
                                  {"campaign": {"id": "9", "name": "검색"}, "segments": {"conversionActionName": "장바구니"},
                                   "metrics": {"allConversions": 7.0, "allConversionsValue": 7000.0}}]})
        return R({"results": [{"campaign": {"id": "9", "name": "검색"}, "customer": {"currencyCode": "KRW"},
                               "metrics": {"impressions": "500", "clicks": "10", "costMicros": "7000000000", "conversions": 2.0, "conversionsValue": 14000.0}}]})

    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)


def test_cross_channel(monkeypatch):
    owner, ws, acc = _account("cross@a.com", "9701")
    sent = []
    _fake(monkeypatch, sent)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "gid")
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "dev")

    # 메타: 토큰이 틀리면 저장하지 않는다, 맞으면 계정 이름을 받아 저장(토큰은 돌려주지 않음)
    bad = c.post(f"/workspaces/{ws}/channels/meta", headers=owner, json={"ad_account_id": "act_111", "access_token": "wrong"})
    assert bad.status_code == 400 and "다시 연결" in bad.json()["detail"]
    meta = c.post(f"/workspaces/{ws}/channels/meta", headers=owner, json={"ad_account_id": "act_111", "access_token": "meta-tok"}).json()
    assert meta["name"] == "메타 광고계정" and "token" not in json.dumps(meta)

    # 구글: 설정 화면 → Google 동의 → 콜백에서 갱신 토큰 저장(로그인은 그대로)
    web = "http://localhost:3000/settings"
    assert c.get("/auth/google/start", params={"redirect": web, "ads_ws": ws, "customer_id": "12-34"}, headers=owner,
                 follow_redirects=False).headers["location"].startswith(web + "#ads_error=")  # 고객 ID 형식
    r = c.get("/auth/google/start", params={"redirect": web, "ads_ws": ws, "customer_id": "123-456-7890"}, headers=owner, follow_redirects=False)
    q = parse_qs(urlsplit(r.headers["location"]).query)
    assert "adwords" in q["scope"][0] and q["access_type"] == ["offline"]
    done = c.get("/auth/google/callback", params={"state": q["state"][0], "code": "c1"}, follow_redirects=False)
    assert done.headers["location"] == web + "#google_ads=linked", unquote(done.headers["location"])
    assert "naverads_session" not in done.cookies
    chans = c.get(f"/workspaces/{ws}/channels", headers=owner).json()
    assert [(x["channel"], x["account_id"], x["name"]) for x in chans] == [("META", "111", "메타 광고계정"), ("GOOGLE", "1234567890", "구글 광고")]

    # 직원은 연결을 못 만든다
    viewer = _viewer(owner, ws, acc, "crossv@a.com")
    assert c.post(f"/workspaces/{ws}/channels/meta", headers=viewer, json={"ad_account_id": "1", "access_token": "x"}).status_code == 403
    assert c.get("/auth/google/start", params={"redirect": web, "ads_ws": ws, "customer_id": "1234567890"}, headers=viewer,
                 follow_redirects=False).status_code == 403

    def tool(h, **a):
        res = c.post("/mcp", headers=_mcp_headers(h), json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "get_cross_channel_performance", "arguments": {"workspace_id": ws, **a}}}).json()["result"]
        return json.loads(res["content"][0]["text"]), res["isError"]

    out, err = tool(owner, since="2026-11-01", until="2026-11-07")
    assert not err
    by = {x["channel"]: x for x in out["accounts"]}
    assert set(by) == {"NAVER", "META", "GOOGLE"}
    # 메타: 두 페이지 합계, 구매는 omni_purchase 하나만(purchase와 겹침)
    assert (by["META"]["cost"], by["META"]["clicks"], by["META"]["conversions"], by["META"]["revenue"], by["META"]["roas"]) == (12000, 25, 4, 50000, 416.7)
    assert (by["GOOGLE"]["cost"], by["GOOGLE"]["conversions"], by["GOOGLE"]["roas"]) == (7000, 2, 200.0)  # 마이크로 → 원
    assert [x["campaign_id"] for x in out["campaigns"]] == ["m1", "9", "m2"]  # 비용 큰 순
    assert any("VAT" in n for n in out["notes"])
    g = [s for s in sent if s[1].endswith("googleAds:search") and "campaign" in s[2]["query"]][-1]
    assert g[3]["developer-token"] == "dev" and "'2026-11-01' AND '2026-11-07'" in g[2]["query"]

    # 구글 전환 액션: 설정 + 액션별 실적(삭제된 액션 제외) + 마지막 전환일 + 캠페인 × 액션
    res = c.post("/mcp", headers=_mcp_headers(owner), json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "get_google_conversions", "arguments": {"workspace_id": ws, "account_id": "123-456-7890", "since": "2026-11-01", "until": "2026-11-07"}}}).json()["result"]
    conv = json.loads(res["content"][0]["text"])
    assert not res["isError"], conv
    acts = {a["name"]: a for a in conv["accounts"][0]["actions"]}
    assert (acts["구매"]["conversions"], acts["구매"]["all_conversions"], acts["구매"]["last_conversion_date"], acts["구매"]["in_conversions"]) == (3, 3, "2026-11-05", True)
    assert (acts["장바구니"]["conversions"], acts["장바구니"]["all_conversions"]) == (0, 7)  # 전환에 포함 안 됨
    assert acts["전화"]["last_conversion_date"] is None and acts["전화"]["click_lookback_days"] == "30"
    assert [(x["action"], x["all_conversions"]) for x in conv["accounts"][0]["campaigns"]] == [("장바구니", 7), ("구매", 3)]
    before = len(sent)  # 질문 3개라도 출입증 갱신은 계정당 한 번
    c.post("/mcp", headers=_mcp_headers(owner), json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "get_google_conversions", "arguments": {"workspace_id": ws}}})
    assert sum(1 for s in sent[before:] if s[1] == "https://oauth2.googleapis.com/token") == 1

    # 직원: 네이버만, 메타·구글은 관리자만
    vout, _ = tool(viewer)
    assert {x["channel"] for x in vout["accounts"]} == {"NAVER"}

    # 한 매체가 실패해도 나머지는 보이고, 실패 이유가 남는다
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    out, err = tool(owner)
    assert not err and "GOOGLE_ADS_DEVELOPER_TOKEN" in {x["channel"]: x for x in out["accounts"]}["GOOGLE"]["error"]
    assert tool(owner, since="2026-01-01", until="2026-11-01")[1]  # 93일 넘음

    # 연결 해제하면 토큰이 지워지고 조회에서 빠진다
    assert c.delete(f"/workspaces/{ws}/channels/{chans[0]['id']}", headers=owner).json() == {"ok": True}
    assert [x["channel"] for x in c.get(f"/workspaces/{ws}/channels", headers=owner).json()] == ["GOOGLE"]


def test_google_tools(monkeypatch):
    """구글 조회·변경 도구: 최대 입찰가 전엔 변경 못 함, 예산 늘리는 변경·높은 입찰가는 서버가 막음, 실행 전 구글 검사(validateOnly)."""
    import hashlib

    from app.google_ads import _phone

    owner, ws, acc = _account("gtools@a.com", "9702")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "gid")
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "dev")
    sent = []

    def post(url, data=None, json=None, headers=None, **kw):
        sent.append((url, json))
        if url == "https://oauth2.googleapis.com/token":
            return R({"access_token": "a", "refresh_token": "g-refresh", "scope": "openid https://www.googleapis.com/auth/adwords"})
        if url.endswith("googleAds:search"):
            q = json["query"]
            if "descriptive_name" in q:
                return R({"results": [{"customer": {"descriptiveName": "구글"}}]})
            if "FROM campaign_budget" in q:
                return R({"results": [{"campaignBudget": {"resourceName": "customers/5555555555/campaignBudgets/7", "amountMicros": "50000000000"}}]})
            if "FROM recommendation" in q:
                return R({"results": [{"recommendation": {"resourceName": "customers/5555555555/recommendations/r1", "type": "CAMPAIGN_BUDGET"}}]})
            return R({"results": [{"campaign": {"id": str(i)}} for i in range(250)]})
        if url.endswith(":generateKeywordIdeas"):
            return R({"results": [{"text": "a", "keywordIdeaMetrics": {"avgMonthlySearches": "10"}},
                                  {"text": "b", "keywordIdeaMetrics": {"avgMonthlySearches": "90", "highTopOfPageBidMicros": "1500000000"}}]})
        if url.endswith("googleAds:mutate") and not json["validateOnly"]:
            return R({"error": {"message": "Request contains an invalid argument.", "details": [{"errors": [{"message": "Too low."}]}]}}, 400)
        if url.endswith("offlineUserDataJobs:create"):
            return R({"resourceName": "customers/5555555555/offlineUserDataJobs/1"})
        return R({"ok": True})

    monkeypatch.setattr(httpx, "post", post)
    web = "http://localhost:3000/settings"
    r = c.get("/auth/google/start", params={"redirect": web, "ads_ws": ws, "customer_id": "555-555-5555"}, headers=owner, follow_redirects=False)
    c.get("/auth/google/callback", params={"state": parse_qs(urlsplit(r.headers["location"]).query)["state"][0], "code": "c"}, follow_redirects=False)
    conn = c.get(f"/workspaces/{ws}/channels", headers=owner).json()[0]

    def tool(name, **a):
        res = c.post("/mcp", headers=_mcp_headers(owner), json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": name, "arguments": {"workspace_id": ws, "account_id": "555-555-5555", **a}}}).json()["result"]
        return json.loads(res["content"][0]["text"]), res["isError"]

    out, err = tool("google_ads_search", query="SELECT campaign.id FROM campaign")
    assert not err and out["rows"] == 250 and len(out["results"]) == 200 and "truncated" in out
    assert tool("google_ads_search", query="DELETE x")[1]
    out, _ = tool("google_keyword_ideas", keywords=["말랑이"])
    assert [(x["keyword"], x["top_bid_high"]) for x in out["ideas"]] == [("b", 1500), ("a", 0)]
    out, err = tool("google_audience_insights", method="searchAudienceInsightsAttributes", body={"queryText": "육아", "dimensions": ["AFFINITY_USER_INTEREST"]})
    assert not err and sent[-1][0].endswith("customers/5555555555:searchAudienceInsightsAttributes")
    assert sent[-1][1] == {"customerInsightsGroup": "구글", "queryText": "육아", "dimensions": ["AFFINITY_USER_INTEREST"]}  # 이름표는 계정 이름
    assert tool("google_audience_insights", method="googleAds:mutate")[1]  # 정한 조회 method만
    out, err = tool("google_ad_preview", asset_group_ids=["11"])
    assert not err and sent[-1][0].endswith("customers/5555555555:generateShareablePreviews")
    assert sent[-1][1] == {"shareablePreviews": [{"assetGroupIdentifier": {"assetGroupId": "11"}}]}
    rec = {"recommendationTypes": ["KEYWORD"], "advertisingChannelType": "SEARCH", "seedInfo": {"urlSeed": "https://a.com"}}
    out, err = tool("google_generate_recommendations", body=rec)
    assert not err and sent[-1][0].endswith("customers/5555555555/recommendations:generate") and sent[-1][1] == rec
    assert tool("google_generate_recommendations", body={"recommendationTypes": ["KEYWORD"], "advertisingChannelType": "DISPLAY"})[1]

    ops = lambda *o: {"mutateOperations": list(o)}  # noqa: E731
    pause = {"campaignOperation": {"update": {"resourceName": "customers/5555555555/campaigns/1", "status": "PAUSED"}, "updateMask": "status"}}
    out, err = tool("google_ads_change", action="mutate", body=ops(pause))
    assert err and "최대 입찰가" in out["error"]  # 최대 입찰가 정하기 전
    assert c.put(f"/workspaces/{ws}/channels/{conn['id']}/max-bid", headers=owner, json={"max_bid": 1000}).json() == {"ok": True}

    out, err = tool("google_ads_change", action="mutate", body=ops(pause))
    assert not err and out["validate_only"] and sent[-1][1]["validateOnly"] is True  # 기본은 구글 검사만
    blocked = [
        {"campaignOperation": {"create": {"name": "새 캠페인", "status": "ENABLED"}}},
        {"campaignOperation": {"update": {"resourceName": "customers/5555555555/campaigns/1", "status": "ENABLED"}}},
        {"campaignBudgetOperation": {"update": {"resourceName": "customers/5555555555/campaignBudgets/7", "amountMicros": "60000000000"}}},
        {"adGroupOperation": {"create": {"name": "g", "cpcBidMicros": "1500000000"}}},
    ]
    for op in blocked:
        n = len(sent)
        out, err = tool("google_ads_change", action="mutate", body=ops(op), validate_only=False)
        assert err and not any(u.endswith("googleAds:mutate") for u, _ in sent[n:]), (op, out)
    down = {"campaignBudgetOperation": {"update": {"resourceName": "customers/5555555555/campaignBudgets/7", "amountMicros": "40000000000"}}}
    out, err = tool("google_ads_change", action="mutate", body=ops(down, pause), validate_only=False)
    assert err and "Too low." in out["error"]  # 구글이 준 칸별 이유를 그대로 전한다
    out, err = tool("google_ads_change", action="apply_recommendations", body={"operations": [{"resourceName": "customers/5555555555/recommendations/r1"}]})
    assert err and "CAMPAIGN_BUDGET" in out["error"]

    out, _ = tool("google_customer_match", user_list_id="3", emails=[" A@b.com", "bad"], phones=["010-1234-5678"])
    assert (out["emails"], out["phones"]) == (1, 1)
    out, err = tool("google_customer_match", user_list_id="3", emails=[" A@b.com"], validate_only=False)
    assert not err and out["uploaded"] == 1
    add = next(j for u, j in sent if u.endswith(":addOperations"))
    assert add["operations"][0]["create"]["userIdentifiers"][0]["hashedEmail"] == hashlib.sha256(b"a@b.com").hexdigest()
    assert "a@b.com" not in json.dumps(sent)
    assert _phone("010-1234-5678") == "+821012345678" and _phone("+1 650 555 0100") == "+16505550100"


def test_meta_search(monkeypatch):
    """메타 조회 도구: Graph API GET 그대로, 이 계정 아래만, 덮어쓰기 칸(method 등) 막음, 페이지 넘김 200행까지."""
    owner, ws, acc = _account("msearch@a.com", "9703")
    sent = []

    def get(url, params=None, headers=None, **kw):
        sent.append((url, params))
        if url.endswith("/act_222"):
            return R({"name": "메타", "spend_cap": "1000000"} if "fields" in (params or {}) else {"name": "메타"})
        page = int((params or {}).get("after") or 0)
        return R({"data": [{"ad_id": str(page * 150 + i)} for i in range(150)],
                  "paging": {"cursors": {"after": str(page + 1)}, "next": "https://graph.facebook.com/next"}})

    monkeypatch.setattr(httpx, "get", get)
    c.post(f"/workspaces/{ws}/channels/meta", headers=owner, json={"ad_account_id": "act_222", "access_token": "t"})

    def tool(**a):
        res = c.post("/mcp", headers=_mcp_headers(owner), json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
            "name": "meta_ads_search", "arguments": {"workspace_id": ws, "account_id": "222", **a}}}).json()["result"]
        return json.loads(res["content"][0]["text"]), res["isError"]

    out, err = tool(params={"level": "ad", "time_range": {"since": "2026-11-01", "until": "2026-11-07"}, "breakdowns": "age,gender"})
    assert not err and out["rows"] == 300 and len(out["data"]) == 200 and "truncated" in out  # 두 페이지에서 멈춤
    assert sent[-2][0].endswith("/act_222/insights") and sent[-2][1]["time_range"] == '{"since": "2026-11-01", "until": "2026-11-07"}'
    out, err = tool(path="act_222", params={"fields": "spend_cap"})
    assert not err and out["result"]["spend_cap"] == "1000000"
    assert tool(path="123/insights")[1] is False
    for bad in ({"path": "act_999/insights"}, {"path": "ads", "params": {"method": "post"}}, {"path": "../me"}, {"path": "me/adaccounts"}):
        assert tool(**bad)[1], bad
    assert tool(account_id="333")[1]  # 연결 안 된 계정
