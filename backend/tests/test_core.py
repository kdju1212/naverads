import io
import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"
if os.path.exists("test.db"):
    os.remove("test.db")

from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import Workbook  # noqa: E402

from app.main import app  # noqa: E402
from app.naver import MOCK_FAIL_IDS  # noqa: E402

c = TestClient(app)


def user(email):
    r = c.post("/auth/signup", json={"email": email, "password": "password1", "name": email})
    return {"Authorization": f"Bearer {r.json()['token']}"}


def setup_agency():
    owner = user("owner@a.com")
    ws = c.post("/workspaces", json={"name": "대행사A"}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "mock", "api_key": "k", "secret_key": "s"}, headers=owner).json()["id"]
    a1 = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": "1001", "name": "광고주1"}, headers=owner).json()
    a2 = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": "1002", "name": "광고주2"}, headers=owner).json()
    for a in (a1, a2):
        assert c.post(f"/workspaces/{ws}/ad-accounts/{a['id']}/sync", headers=owner).json()["status"] == "SUCCESS"
    staff = user("staff@a.com")
    mid = c.post(f"/workspaces/{ws}/members", json={"email": "staff@a.com"}, headers=owner).json()["membership_id"]
    c.put(f"/workspaces/{ws}/members/{mid}/access", json={"ad_account_id": a1["id"], "level": "EDIT"}, headers=owner)
    c.put(f"/workspaces/{ws}/members/{mid}/access", json={"ad_account_id": a2["id"], "level": "VIEW"}, headers=owner)
    return owner, staff, ws, a1["id"], a2["id"], cred


def test_full_flow():
    owner, staff, ws, a1, a2, cred = setup_agency()

    # 다계정 통합 조회 + 유형 필터
    camps = c.get(f"/workspaces/{ws}/campaigns", headers=owner).json()
    assert {x["ad_account_id"] for x in camps} == {a1, a2} and len(camps) == 4
    assert len(c.get(f"/workspaces/{ws}/campaigns?product=SHOPPING", headers=owner).json()) == 2
    assert len(c.get(f"/workspaces/{ws}/ads?ad_type=SHOPPING_PRODUCT_AD&account_ids={a1}", headers=owner).json()) == 3
    exts = c.get(f"/workspaces/{ws}/ad-extensions?account_ids={a1}", headers=owner).json()
    assert [(e["ext_type"], e["owner_name"]) for e in exts] == [("SUB_LINKS", "파워링크그룹1"), ("SUB_LINKS", "파워링크그룹2")]
    assert exts[0]["payload"] == [{"name": "신상품", "final": "https://example.com/new"}]  # JSON 문자열을 풀어 저장

    # 다른 조직은 아무것도 볼 수 없다
    outsider = user("other@b.com")
    ws_b = c.post("/workspaces", json={"name": "대행사B"}, headers=outsider).json()["id"]
    assert c.get(f"/workspaces/{ws}/campaigns", headers=outsider).status_code == 403
    assert c.get(f"/workspaces/{ws_b}/campaigns?account_ids={a1}", headers=outsider).status_code == 403

    # 직원은 VIEW 계정 수정 불가, EDIT 계정만 VALID
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=staff, json={"changes": [
        {"entity_type": "campaign", "naver_id": "cmp-1001-pl", "field": "status", "value": "OFF"},
        {"entity_type": "campaign", "naver_id": "cmp-1002-pl", "field": "status", "value": "OFF"},
        {"entity_type": "keyword", "naver_id": "kwd-1001-11", "field": "bid_amt", "value": "65"},     # 파워링크 최소 미만
        {"entity_type": "ad", "naver_id": "ad-1001-pl1", "field": "bid_amt", "value": "500"},         # 텍스트 소재는 입찰가 없음
        {"entity_type": "ad", "naver_id": "ad-1001-sh1", "field": "bid_amt", "value": "250"},         # 쇼핑 상품소재 입찰가
        {"entity_type": "adgroup", "naver_id": "grp-1001-pl1", "field": "bid_amt", "value": "800"},
        {"entity_type": "adgroup", "naver_id": "grp-1001-pl1", "field": "bid_amt", "value": "900"},   # 중복
    ]}).json()
    status = [r["status"] for acc in job["accounts"] for r in acc["rows"]]
    assert job["counts"] == {"VALID": 3, "INVALID": 4, "SUCCESS": 0, "FAILED": 0}, status

    # 실행: 한 행은 API 실패 → PARTIAL, 감사 로그 기록
    MOCK_FAIL_IDS.add("grp-1001-pl1")
    done = c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=staff).json()
    assert done["status"] == "PARTIAL" and done["counts"]["SUCCESS"] == 2 and done["counts"]["FAILED"] == 1
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=staff).status_code == 409
    camp = next(x for x in c.get(f"/workspaces/{ws}/campaigns", headers=staff).json() if x["naver_id"] == "cmp-1001-pl")
    assert camp["status"] == "OFF"
    logs = c.get(f"/workspaces/{ws}/audit-logs?account_id={a1}", headers=owner).json()
    assert any(l["naver_id"] == "ad-1001-sh1" and l["before"] == "200" and l["after"] == "250" for l in logs)

    # 실패 행만 재실행
    MOCK_FAIL_IDS.clear()
    retry = c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/retry-failed", headers=staff).json()
    assert retry["parent_job_id"] == job["id"] and retry["counts"]["VALID"] == 1
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{retry['id']}/execute", headers=staff).json()["status"] == "DONE"

    # 확장소재 ON/OFF (내용 수정은 없음)
    ej = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        {"entity_type": "ad_extension", "naver_id": "ext-1001-pl1", "field": "status", "value": "OFF"},
        {"entity_type": "ad_extension", "naver_id": "ext-1001-pl1", "field": "payload", "value": "x"}]}).json()
    assert ej["counts"]["VALID"] == 1 and ej["counts"]["INVALID"] == 1
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{ej['id']}/execute", headers=owner).json()["counts"]["SUCCESS"] == 1
    ext = next(e for e in c.get(f"/workspaces/{ws}/ad-extensions?account_ids={a1}", headers=owner).json()
               if e["naver_id"] == "ext-1001-pl1")
    assert ext["status"] == "OFF"

    # 확장소재 생성·삭제: 입력 검증, VIEW 권한 계정은 거부, 감사 로그
    grps = {g["naver_id"]: g["id"] for g in c.get(f"/workspaces/{ws}/adgroups", headers=owner).json()}
    url = f"/workspaces/{ws}/ad-extensions"
    assert c.post(url, headers=owner, json={"adgroup_id": grps["grp-1001-pl1"], "ext_type": "DESCRIPTION", "heading": "이벤트"}).status_code == 400
    assert c.post(url, headers=owner, json={"adgroup_id": grps["grp-1001-pl1"], "ext_type": "SUB_LINKS",
                                           "links": [{"name": "a", "final": "javascript:x"}]}).status_code == 400
    assert c.post(url, headers=owner, json={"adgroup_id": grps["grp-1001-sh1"], "ext_type": "DESCRIPTION",
                                           "heading": "할인", "description": "b"}).status_code == 400  # 쇼핑 그룹
    assert c.post(url, headers=staff, json={"adgroup_id": grps["grp-1002-pl1"], "ext_type": "DESCRIPTION",
                                           "heading": "할인", "description": "b"}).status_code == 403  # VIEW 계정
    g1 = grps["grp-1001-pl1"]
    assert c.post(url, headers=owner, json={"adgroup_id": g1, "ext_type": "DESCRIPTION", "heading": "특가",
                                           "description": "b"}).status_code == 400  # 홍보문구 구분 밖
    assert c.post(url, headers=owner, json={"adgroup_id": g1, "ext_type": "DESCRIPTION", "heading": "할인",
                                           "description": "가" * 15}).status_code == 400  # 14자 초과
    assert c.post(url, headers=owner, json={"adgroup_id": g1, "ext_type": "HEADLINE", "heading": "가" * 16}).status_code == 400
    for body, payload in [({"ext_type": "DESCRIPTION", "heading": "할인", "description": "가" * 14}, {"heading": "할인", "description": "가" * 14}),
                          ({"ext_type": "HEADLINE", "heading": "공식몰"}, {"headline": "공식몰"}),
                          ({"ext_type": "DESCRIPTION_EXTRA", "description": "가" * 45}, {"description": "가" * 45})]:
        made = c.post(url, headers=owner, json={"adgroup_id": g1, **body}).json()
        assert next(e for e in c.get(f"{url}?account_ids={a1}", headers=owner).json() if e["id"] == made["id"])["payload"] == payload
    new = c.post(url, headers=owner, json={"adgroup_id": grps["grp-1001-pl1"], "ext_type": "SUB_LINKS",
                                          "links": [{"name": "신상품", "final": "https://example.com/a"}]}).json()
    row = next(e for e in c.get(f"{url}?account_ids={a1}", headers=owner).json() if e["id"] == new["id"])
    assert row["payload"] == [{"name": "신상품", "final": "https://example.com/a"}] and row["owner_name"] == "파워링크그룹1"
    assert c.delete(f"{url}/{new['id']}", headers=owner).json() == {"ok": True, "already_gone": False}
    assert all(e["id"] != new["id"] for e in c.get(f"{url}?account_ids={a1}", headers=owner).json())
    logs = c.get(f"/workspaces/{ws}/audit-logs?account_id={a1}", headers=owner).json()
    assert {l["action"] for l in logs if l["naver_id"] == new["naver_id"]} == {"CREATE", "DELETE"}

    # 엑셀 업로드 → 미리보기
    wb = Workbook()
    wb.active.append(["entity_type", "naver_id", "field", "value"])
    wb.active.append(["campaign", "cmp-1002-sh", "daily_budget", "70000"])
    wb.active.append(["keyword", "kwd-1002-11", "status", "OFF"])
    buf = io.BytesIO()
    wb.save(buf)
    ex = c.post(f"/workspaces/{ws}/bulk-jobs/excel", headers=owner,
                files={"file": ("b.xlsx", buf.getvalue())}).json()
    assert ex["source"] == "EXCEL" and ex["counts"]["VALID"] == 2
    assert c.get("/bulk-jobs/excel-template").status_code == 200

    # 미리보기 후 권한이 회수되면 실행 시 실패
    mid = next(x["membership_id"] for x in c.get(f"/workspaces/{ws}/members", headers=owner).json() if x["email"] == "staff@a.com")
    j2 = c.post(f"/workspaces/{ws}/bulk-jobs", headers=staff, json={"changes": [
        {"entity_type": "campaign", "naver_id": "cmp-1001-sh", "field": "status", "value": "OFF"}]}).json()
    c.put(f"/workspaces/{ws}/members/{mid}/access", json={"ad_account_id": a1, "level": None}, headers=owner)
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{j2['id']}/execute", headers=staff).json()["status"] == "FAILED"

    # 성과·대시보드·구독
    perf = c.get(f"/workspaces/{ws}/performance/accounts", headers=owner).json()
    assert len(perf) == 2 and perf[0]["WEB_SITE"]["cost"] > 0 and perf[0]["SHOPPING"] is not None
    p1 = next(p for p in perf if p["ad_account_id"] == a1)
    perf_a1_cost = p1["WEB_SITE"]["cost"] + p1["SHOPPING"]["cost"]
    dash = c.get(f"/workspaces/{ws}/dashboard", headers=owner).json()
    assert dash["connected_accounts"] == 2 and job["id"] in dash["failed_jobs"]
    ops = c.get(f"/workspaces/{ws}/dashboard?account_ids={a1}", headers=owner).json()["ops"]
    assert sum(ops["campaign"].values()) == 2 and ops["campaign"] == {"ON": 1, "OFF": 1} and sum(ops["keyword"].values()) == 6
    from datetime import date, timedelta
    until = date.today() - timedelta(days=1)
    daily = c.get(f"/workspaces/{ws}/performance/daily?since={until - timedelta(days=6)}&until={until}&account_ids={a1}",
                  headers=owner).json()
    pl = c.get(f"/workspaces/{ws}/performance/daily?since={until - timedelta(days=6)}&until={until}&account_ids={a1}&product=WEB_SITE",
               headers=owner).json()
    assert len(daily) == 7 and daily[-1]["date"] == until.isoformat()
    assert sum(d["cost"] for d in daily) == perf_a1_cost and 0 < sum(d["cost"] for d in pl) < perf_a1_cost
    assert c.get(f"/workspaces/{ws}/performance/daily?since={until}&until={until - timedelta(days=1)}", headers=owner).status_code == 400
    sub = c.get(f"/workspaces/{ws}/subscription", headers=owner).json()
    assert sub["status"] == "TRIALING" and sub["monthly_total"] == 2 * 19_900
    assert c.get(f"/workspaces/{ws}/subscription", headers=staff).status_code == 403

    # 계정 해제 → 접근 차단, 구독 과금 계정 감소
    assert c.delete(f"/workspaces/{ws}/ad-accounts/{a2}", headers=owner).status_code == 200
    assert c.get(f"/workspaces/{ws}/campaigns?account_ids={a2}", headers=owner).status_code == 403
    assert c.get(f"/workspaces/{ws}/subscription", headers=owner).json()["billable_accounts"] == 1


def test_connect_validation():
    owner = user("v@a.com")
    ws = c.post("/workspaces", json={"name": "V"}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=owner).json()
    assert "secret_key" not in cred
    r = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred["id"], "customer_id": "abc", "name": "x"}, headers=owner)
    assert r.status_code == 400
    assert c.get(f"/workspaces/{ws}/campaigns").status_code == 401


def test_real_write_gate(monkeypatch):
    import pytest
    from app.naver import NaverApiError, RealNaverClient

    calls = []

    def fake_req(self, method, uri, **kw):
        calls.append((method, uri, kw.get("params")))
        return {"bidAmt": 100, "useGroupBidAmt": True} if method == "GET" else echo(kw["json"])

    echo = lambda o: o  # noqa: E731
    monkeypatch.setattr(RealNaverClient, "_req", fake_req)
    cl = RealNaverClient("k", "s", "1")

    cl.update("keyword", "nkw-1", "bid_amt", 150)  # 검증된 항목은 허용
    assert calls[-1] == ("PUT", "/ncc/keywords/nkw-1", {"fields": "bidAmt"})

    echo = lambda o: {**o, "bidAmt": 100}  # noqa: E731 — 네이버가 이전 값을 돌려준 경우
    with pytest.raises(NaverApiError, match="반영되지"):
        cl.update("keyword", "nkw-1", "bid_amt", 150)

    echo = lambda o: o  # noqa: E731
    cl.update("campaign", "cmp-1", "daily_budget", 10000)
    assert calls[-1] == ("PUT", "/ncc/campaigns/cmp-1", {"fields": "budget"})

    echo = lambda o: {**o, "dailyBudget": 0, "useDailyBudget": False}  # noqa: E731 — 예산이 반영 안 된 경우
    with pytest.raises(NaverApiError, match="반영되지"):
        cl.update("campaign", "cmp-1", "daily_budget", 10000)

    echo = lambda o: {k: v for k, v in o.items() if k != "useGroupBidAmt"}  # noqa: E731 — 광고그룹 응답엔 이 필드가 없다
    cl.update("adgroup", "grp-1", "bid_amt", 300)
    assert calls[-1] == ("PUT", "/ncc/adgroups/grp-1", {"fields": "bidAmt"})

    n = len(calls)
    with pytest.raises(NaverApiError, match="차단"):
        cl.update("ad", "nad-1", "bid_amt", 300)  # 미검증 항목은 차단, 호출도 안 함
    assert len(calls) == n


def test_real_stats(monkeypatch):
    import json
    from datetime import date

    from app.naver import RealNaverClient

    calls = []

    def fake_req(self, method, uri, **kw):
        calls.append((method, uri, kw["params"]))
        return {"data": [{"dateStart": "2026-10-01", "dateEnd": "2026-10-01", "impCnt": 10, "clkCnt": 2, "salesAmt": 300}]}

    monkeypatch.setattr(RealNaverClient, "_req", fake_req)
    rows = RealNaverClient("k", "s", "1").stats(["cmp-1", "cmp-2"], date(2026, 10, 1), date(2026, 10, 1))
    assert [c[2]["id"] for c in calls] == ["cmp-1", "cmp-2"]  # 일별 통계는 캠페인별로 따로 요청
    assert json.loads(calls[0][2]["timeRange"]) == {"since": "2026-10-01", "until": "2026-10-01"}
    assert rows[0] == {"id": "cmp-1", "date": date(2026, 10, 1), "impCnt": 10, "clkCnt": 2, "salesAmt": 300,
                       "ccnt": None, "convAmt": None}

    RealNaverClient("k", "s", "1").delete_ad_extension("ext-1")
    assert calls[-1] == ("DELETE", "/ncc/ad-extensions", {"ids": "ext-1"})  # 경로 방식은 실계정 404

    def fake_est(self, method, uri, **kw):
        calls.append((method, uri, kw["json"]))
        return {"device": "PC", "estimate": [{"keyword": "a", "position": 3, "bid": 1230}, {"keyword": "b", "position": 3, "bid": 70}]}

    monkeypatch.setattr(RealNaverClient, "_req", fake_est)
    assert RealNaverClient("k", "s", "1").estimate_bids("PC", [("nkw-1", 3), ("nkw-2", 3)]) == {"nkw-1": 1230, "nkw-2": 70}
    assert calls[-1] == ("POST", "/estimate/average-position-bid/id",
                         {"device": "PC", "items": [{"key": "nkw-1", "position": 3}, {"key": "nkw-2", "position": 3}]})


def test_rsa_texts():
    from app.sync import _rsa_texts

    assets = [{"linkType": "HEADLINE", "assetData": '{"text": "여름 세일"}'},
              {"linkType": "HEADLINE", "assetData": "무료배송"},
              {"linkType": "DESCRIPTION", "assetData": {"text": "전 상품 할인"}},
              {"linkType": "OTHER", "assetData": "무시"}]
    assert _rsa_texts(assets) == {"headlines": ["여름 세일", "무료배송"], "descriptions": ["전 상품 할인"]}


def test_auto_bid():
    from app.bulk import run_all_auto_bids
    from app.db import SessionLocal

    owner = user("bid@a.com")
    ws = c.post("/workspaces", json={"name": "B"}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=owner).json()["id"]
    acc = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": "4004", "name": "b"}, headers=owner).json()
    c.post(f"/workspaces/{ws}/ad-accounts/{acc['id']}/sync", headers=owner)
    kws = {k["naver_id"]: k for k in c.get(f"/workspaces/{ws}/keywords", headers=owner).json()}
    k1, k2 = kws["kwd-4004-11"], kws["kwd-4004-12"]  # 입찰가 300, 600
    url = f"/workspaces/{ws}/auto-bids"

    assert c.put(url, headers=owner, json={"keyword_ids": [k1["id"]], "device": "MOBILE", "target_rank": 6, "max_bid": 500}).status_code == 400
    assert c.put(url, headers=owner, json={"keyword_ids": [k1["id"]], "device": "PC", "target_rank": 1, "max_bid": 505}).status_code == 400
    outsider = user("bid2@b.com")
    ws_b = c.post("/workspaces", json={"name": "B2"}, headers=outsider).json()["id"]
    assert c.put(f"/workspaces/{ws_b}/auto-bids", headers=outsider,
                 json={"keyword_ids": [k1["id"]], "device": "PC", "target_rank": 1, "max_bid": 500}).status_code == 403

    # Mock 예상가: PC 1위 1070원 → 최대 500원으로 제한, PC 5위 270원
    c.put(url, headers=owner, json={"keyword_ids": [k1["id"]], "device": "PC", "target_rank": 1, "max_bid": 500})
    c.put(url, headers=owner, json={"keyword_ids": [k2["id"]], "device": "PC", "target_rank": 5, "max_bid": 5000})
    jobs = c.post(f"{url}/run", headers=owner).json()["job_ids"]
    assert len(jobs) == 1 and c.get(f"/workspaces/{ws}/bulk-jobs/{jobs[0]}", headers=owner).json()["status"] == "DONE"
    bids = {k["naver_id"]: k["bid_amt"] for k in c.get(f"/workspaces/{ws}/keywords", headers=owner).json()}
    assert bids["kwd-4004-11"] == 500 and bids["kwd-4004-12"] == 270
    rules = c.get(url, headers=owner).json()
    assert "최대 500원" in rules[0]["last_result"] and "300원 → 500원" in rules[0]["last_result"]

    # 다시 돌리면 변경 없음 → 작업도 안 만든다 (크론 경로)
    db = SessionLocal()
    run_all_auto_bids(db)
    db.close()
    assert all("변경 없음" in r["last_result"] for r in c.get(url, headers=owner).json())

    assert c.post(f"{url}/delete", headers=owner, json={"keyword_ids": [k1["id"], k2["id"]]}).json() == {"ok": True}
    assert c.get(url, headers=owner).json() == []

    # 조직당 개수 제한: 한도를 1로 낮춰 2번째 키워드는 거절, 같은 키워드 덮어쓰기·중지는 허용
    from app import main
    main.AUTO_BID_LIMIT = 1
    try:
        body = {"device": "PC", "target_rank": 1, "max_bid": 500}
        assert c.put(url, headers=owner, json={**body, "keyword_ids": [k1["id"]]}).status_code == 200
        assert c.put(url, headers=owner, json={**body, "keyword_ids": [k1["id"]]}).status_code == 200
        r = c.put(url, headers=owner, json={**body, "keyword_ids": [k2["id"]]})
        assert r.status_code == 400 and "1개까지" in r.json()["detail"]
        assert c.put(url, headers=owner, json={**body, "keyword_ids": [k2["id"]], "enabled": False}).status_code == 200
    finally:
        main.AUTO_BID_LIMIT = 20


def test_sync_removes_stale():
    from app.naver import _MOCK_STORE

    owner = user("stale@a.com")
    ws = c.post("/workspaces", json={"name": "S"}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=owner).json()["id"]
    acc = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": "5005", "name": "s"}, headers=owner).json()["id"]
    sync = lambda: c.post(f"/workspaces/{ws}/ad-accounts/{acc}/sync", headers=owner).json()["status"]  # noqa: E731
    assert sync() == "SUCCESS"
    kw = next(k for k in c.get(f"/workspaces/{ws}/keywords", headers=owner).json() if k["naver_id"] == "kwd-5005-11")
    c.put(f"/workspaces/{ws}/auto-bids", headers=owner, json={"keyword_ids": [kw["id"]], "device": "PC", "target_rank": 1, "max_bid": 500})

    # 네이버 화면에서 키워드·확장소재·쇼핑 캠페인(성과 통계 있음)을 지운 상황
    s = _MOCK_STORE["5005"]
    s["keywords"].pop("kwd-5005-11")
    s["ad-extensions"].pop("ext-5005-pl1")
    s["campaigns"].pop("cmp-5005-sh")
    assert sync() == "SUCCESS"

    get = lambda p: {x["naver_id"] for x in c.get(f"/workspaces/{ws}/{p}", headers=owner).json()}  # noqa: E731
    assert "kwd-5005-11" not in get("keywords") and "kwd-5005-12" in get("keywords")
    assert get("ad-extensions") == {"ext-5005-pl2"}
    assert get("campaigns") == {"cmp-5005-pl"}
    assert "grp-5005-sh1" not in get("adgroups") and not get("ads?ad_type=SHOPPING_PRODUCT_AD")
    assert c.get(f"/workspaces/{ws}/auto-bids", headers=owner).json() == []
    perf = c.get(f"/workspaces/{ws}/performance/accounts", headers=owner).json()[0]
    assert perf["SHOPPING"] is None and perf["WEB_SITE"] is not None


def test_delete_extension_already_gone():
    from app.naver import _MOCK_STORE

    owner = user("gone@a.com")
    ws = c.post("/workspaces", json={"name": "G"}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=owner).json()["id"]
    acc = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": "3003", "name": "g"}, headers=owner).json()
    c.post(f"/workspaces/{ws}/ad-accounts/{acc['id']}/sync", headers=owner)
    ext = c.get(f"/workspaces/{ws}/ad-extensions", headers=owner).json()[0]
    _MOCK_STORE["3003"]["ad-extensions"].pop(ext["naver_id"])  # 네이버 화면에서 먼저 지워진 상황
    assert c.delete(f"/workspaces/{ws}/ad-extensions/{ext['id']}", headers=owner).json() == {"ok": True, "already_gone": True}


def test_keyword_create_delete():
    owner = user("kwc@a.com")
    ws = c.post("/workspaces", json={"name": "K"}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=owner).json()["id"]
    acc = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": "6006", "name": "k"}, headers=owner).json()["id"]
    c.post(f"/workspaces/{ws}/ad-accounts/{acc}/sync", headers=owner)
    kws = lambda: {k["keyword"]: k for k in c.get(f"/workspaces/{ws}/keywords", headers=owner).json()}  # noqa: E731
    old = kws()["원피스1"]
    c.put(f"/workspaces/{ws}/auto-bids", headers=owner, json={"keyword_ids": [old["id"]], "device": "PC", "target_rank": 1, "max_bid": 500})

    ch = lambda nid, field, value="": {"entity_type": "keyword", "naver_id": nid, "field": field, "value": value}  # noqa: E731
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch("grp-6006-pl1", "create", "새 키워드|550"),
        ch("grp-6006-pl1", "create", "그룹가 키워드"),
        ch("grp-6006-pl1", "create", "새 키워드|600"),   # 같은 키워드 중복
        ch("grp-6006-pl1", "create", "원피스1"),          # 이미 있음
        ch("grp-6006-pl1", "create", "x|505"),            # 10원 단위 아님
        ch("grp-6006-sh1", "create", "쇼핑"),             # 쇼핑 광고그룹
        ch(old["naver_id"], "delete"),
    ]}).json()
    rows = [r for a in job["accounts"] for r in a["rows"]]
    assert [r["status"] for r in rows] == ["VALID", "VALID", "INVALID", "INVALID", "INVALID", "INVALID", "VALID"]
    assert rows[-1]["before"] == "원피스1"

    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner).json()["status"] == "DONE"
    now = kws()
    assert "원피스1" not in now and now["새 키워드"]["bid_amt"] == 550 and not now["새 키워드"]["use_group_bid"]
    assert now["그룹가 키워드"]["use_group_bid"] and now["그룹가 키워드"]["bid_amt"] == 500
    assert c.get(f"/workspaces/{ws}/auto-bids", headers=owner).json() == []
    # 동기화해도 그대로 (Mock 네이버에도 반영됨)
    c.post(f"/workspaces/{ws}/ad-accounts/{acc}/sync", headers=owner)
    assert set(kws()) == set(now)
    acts = {(h["action"], h["field"]) for h in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()}
    assert {("CREATE", "keyword"), ("DELETE", "keyword")} <= acts
