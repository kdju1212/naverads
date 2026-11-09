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


def test_account_tools():
    owner, ws, acc = _account("tools@a.com", "9501")
    h = _mcp_headers(owner)
    call = _tool(h, ws, acc)

    money, err = call("get_bizmoney", since="2026-11-01", until="2026-11-03")
    assert not err and money["balance"]["bizmoney"] == 152000 and len(money["daily"]) == 3
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

    logs = {(x["entity_type"], x["action"]) for x in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()}
    assert {("ip_exclusion", "CREATE"), ("ip_exclusion", "DELETE"), ("channel", "CREATE"), ("channel", "UPDATE"),
            ("targeting", "UPDATE")} <= logs

    # 보기 권한만 있으면 조회는 되고 변경은 안 된다
    v = _mcp_headers(_viewer(owner, ws, acc, "toolsv@a.com"))
    vcall = _tool(v, ws, acc)
    assert not vcall("list_ip_exclusions")[1] and not vcall("get_bizmoney")[1]
    for tool, a in (("add_ip_exclusion", {"ip": "5.6.7.8"}), ("create_site_channel", {"name": "x", "url": "https://x.com"}),
                    ("set_targeting", {"adgroup_id": grp, "type": "DV", "codes": ["PC"]})):
        assert vcall(tool, **a)[1], tool
