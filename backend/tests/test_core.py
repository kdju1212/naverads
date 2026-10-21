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


def ch(acc, etype, nid, field, value="", **kw):
    return {"entity_type": etype, "naver_id": nid, "field": field, "value": value, "ad_account_id": acc, **kw}


def store(cid):
    from app.naver import _MOCK_STORE
    return _MOCK_STORE[cid]


def test_full_flow():
    owner, staff, ws, a1, a2, cred = setup_agency()

    # 다른 조직은 아무것도 볼 수 없다
    outsider = user("other@b.com")
    ws_b = c.post("/workspaces", json={"name": "대행사B"}, headers=outsider).json()["id"]
    assert c.get(f"/workspaces/{ws}/ad-accounts/{a1}/naver/campaigns", headers=outsider).status_code == 403
    assert c.get(f"/workspaces/{ws_b}/ad-accounts/{a1}/naver/campaigns", headers=outsider).status_code == 403

    # 직원은 VIEW 계정 수정 불가, EDIT 계정만 VALID. 계정·이전 값·유형은 화면(브라우저 보관본)이 보낸다
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=staff, json={"changes": [
        ch(a1, "campaign", "cmp-1001-pl", "status", "OFF", before="ON", product="WEB_SITE"),
        ch(a2, "campaign", "cmp-1002-pl", "status", "OFF", before="ON", product="WEB_SITE"),       # VIEW 계정
        ch(a1, "keyword", "kwd-1001-11", "bid_amt", "65", before="300"),                          # 파워링크 최소 미만
        ch(a1, "ad", "ad-1001-pl1", "bid_amt", "500", ad_type="TEXT_45", product="WEB_SITE"),       # 텍스트 소재는 입찰가 없음
        ch(a1, "ad", "ad-1001-sh1", "bid_amt", "250", before="200", ad_type="SHOPPING_PRODUCT_AD", product="SHOPPING"),
        ch(a1, "adgroup", "grp-1001-pl1", "bid_amt", "800", before="500", product="WEB_SITE"),
        ch(a1, "adgroup", "grp-1001-pl1", "bid_amt", "900", before="500", product="WEB_SITE"),     # 중복
        ch(a1, "campaign", "cmp-1001-xx", "status", "OFF", invalid="보관본에 없는 ID입니다"),         # 화면이 찾은 오류
        ch(a1, "campaign", "cmp-1001-sh", "status", "ON", before="ON"),                            # 현재 값과 같음
    ]}).json()
    rows = [r for acc in job["accounts"] for r in acc["rows"]]
    assert job["counts"] == {"VALID": 3, "INVALID": 6, "SUCCESS": 0, "FAILED": 0}, [(r["naver_id"], r["error"]) for r in rows]
    assert next(r for r in rows if r["naver_id"] == "cmp-1002-pl")["error"] == "대상이 없거나 수정 권한이 없습니다"
    assert next(acc for acc in job["accounts"] if acc["ad_account_id"] is None)  # 권한 없는 행은 계정을 붙이지 않는다

    # 실행: 한 행은 API 실패 → PARTIAL, 감사 로그 기록, Mock 네이버에 반영
    MOCK_FAIL_IDS.add("grp-1001-pl1")
    done = c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=staff).json()
    assert done["status"] == "PARTIAL" and done["counts"]["SUCCESS"] == 2 and done["counts"]["FAILED"] == 1
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=staff).status_code == 409
    assert store("1001")["campaigns"]["cmp-1001-pl"]["userLock"] is True
    logs = c.get(f"/workspaces/{ws}/audit-logs?account_id={a1}", headers=owner).json()
    assert any(l["naver_id"] == "ad-1001-sh1" and l["before"] == "200" and l["after"] == "250" for l in logs)

    # 실패 행만 재실행(계정·이전 값은 원래 행에서)
    MOCK_FAIL_IDS.clear()
    retry = c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/retry-failed", headers=staff).json()
    assert retry["parent_job_id"] == job["id"] and retry["counts"]["VALID"] == 1
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{retry['id']}/execute", headers=staff).json()["status"] == "DONE"
    assert store("1001")["adgroups"]["grp-1001-pl1"]["bidAmt"] == 800

    # 확장소재 ON/OFF (내용 수정은 없음)
    ej = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(a1, "ad_extension", "ext-1001-pl1", "status", "OFF", before="ON"),
        ch(a1, "ad_extension", "ext-1001-pl1", "payload", "x")]}).json()
    assert ej["counts"]["VALID"] == 1 and ej["counts"]["INVALID"] == 1
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{ej['id']}/execute", headers=owner).json()["counts"]["SUCCESS"] == 1
    assert store("1001")["ad-extensions"]["ext-1001-pl1"]["userLock"] is True

    # 확장소재 생성·삭제: 입력 검증, VIEW 권한 계정은 거부, 감사 로그
    url = f"/workspaces/{ws}/ad-extensions"
    g1 = {"ad_account_id": a1, "adgroup_naver_id": "grp-1001-pl1"}
    assert c.post(url, headers=owner, json={**g1, "ext_type": "DESCRIPTION", "heading": "이벤트"}).status_code == 400
    assert c.post(url, headers=owner, json={**g1, "ext_type": "SUB_LINKS", "links": [{"name": "a", "final": "javascript:x"}]}).status_code == 400
    assert c.post(url, headers=staff, json={"ad_account_id": a2, "adgroup_naver_id": "grp-1002-pl1", "ext_type": "DESCRIPTION",
                                           "heading": "할인", "description": "b"}).status_code == 403  # VIEW 계정
    assert c.post(url, headers=owner, json={**g1, "ext_type": "DESCRIPTION", "heading": "특가", "description": "b"}).status_code == 400
    assert c.post(url, headers=owner, json={**g1, "ext_type": "DESCRIPTION", "heading": "할인", "description": "가" * 15}).status_code == 400
    assert c.post(url, headers=owner, json={**g1, "ext_type": "HEADLINE", "heading": "가" * 16}).status_code == 400
    for body, payload in [({"ext_type": "DESCRIPTION", "heading": "할인", "description": "가" * 14}, {"heading": "할인", "description": "가" * 14}),
                          ({"ext_type": "HEADLINE", "heading": "공식몰"}, {"headline": "공식몰"}),
                          ({"ext_type": "DESCRIPTION_EXTRA", "description": "가" * 45}, {"description": "가" * 45})]:
        made = c.post(url, headers=owner, json={**g1, **body}).json()
        assert made["payload"] == payload and made["ad_account_id"] == a1 and made["owner_naver_id"] == "grp-1001-pl1"
    new = c.post(url, headers=owner, json={**g1, "ext_type": "SUB_LINKS", "links": [{"name": "신상품", "final": "https://example.com/a"}]}).json()
    assert new["payload"] == [{"name": "신상품", "final": "https://example.com/a"}] and new["ext_type"] == "SUB_LINKS"
    q = {"account_id": a1, "owner_naver_id": "grp-1001-pl1", "ext_type": "SUB_LINKS"}
    assert c.delete(f"{url}/{new['naver_id']}", params=q, headers=staff).status_code == 200  # a1은 EDIT
    assert new["naver_id"] not in store("1001")["ad-extensions"]
    assert c.delete(f"{url}/ext-1002-pl1", params={**q, "account_id": a2}, headers=staff).status_code == 403
    logs = c.get(f"/workspaces/{ws}/audit-logs?account_id={a1}", headers=owner).json()
    assert {l["action"] for l in logs if l["naver_id"] == new["naver_id"]} == {"CREATE", "DELETE"}

    # 엑셀: 서버는 읽기만, 화면이 계정을 채워 EXCEL 작업으로 만든다
    wb = Workbook()
    wb.active.append(["entity_type", "naver_id", "field", "value"])
    wb.active.append(["campaign", "cmp-1002-sh", "daily_budget", 70000])
    wb.active.append(["keyword", "kwd-1002-11", "status", "OFF"])
    buf = io.BytesIO()
    wb.save(buf)
    parsed = c.post(f"/workspaces/{ws}/bulk-jobs/excel/parse", headers=owner, files={"file": ("b.xlsx", buf.getvalue())}).json()
    assert parsed == [{"entity_type": "campaign", "naver_id": "cmp-1002-sh", "field": "daily_budget", "value": "70000"},
                      {"entity_type": "keyword", "naver_id": "kwd-1002-11", "field": "status", "value": "OFF"}]
    ex = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"source": "EXCEL", "changes": [{**p, "ad_account_id": a2} for p in parsed]}).json()
    assert ex["source"] == "EXCEL" and ex["counts"]["VALID"] == 2
    assert c.get("/bulk-jobs/excel-template").status_code == 200

    # 미리보기 후 권한이 회수되면 실행 시 실패
    mid = next(x["membership_id"] for x in c.get(f"/workspaces/{ws}/members", headers=owner).json() if x["email"] == "staff@a.com")
    j2 = c.post(f"/workspaces/{ws}/bulk-jobs", headers=staff, json={"changes": [ch(a1, "campaign", "cmp-1001-sh", "status", "OFF")]}).json()
    c.put(f"/workspaces/{ws}/members/{mid}/access", json={"ad_account_id": a1, "level": None}, headers=owner)
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{j2['id']}/execute", headers=staff).json()["status"] == "FAILED"

    # 성과·대시보드·구독
    perf = c.get(f"/workspaces/{ws}/performance/accounts", headers=owner).json()
    assert len(perf) == 2 and perf[0]["WEB_SITE"]["cost"] > 0 and perf[0]["SHOPPING"] is not None
    p1 = next(p for p in perf if p["ad_account_id"] == a1)
    perf_a1_cost = p1["WEB_SITE"]["cost"] + p1["SHOPPING"]["cost"]
    dash = c.get(f"/workspaces/{ws}/dashboard", headers=owner).json()
    assert dash["connected_accounts"] == 2 and job["id"] in dash["failed_jobs"] and dash["auto_bids"] == 0
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
    assert c.get(f"/workspaces/{ws}/ad-accounts/{a2}/naver/campaigns", headers=owner).status_code == 403
    assert c.get(f"/workspaces/{ws}/subscription", headers=owner).json()["billable_accounts"] == 1


def test_connect_validation():
    owner = user("v@a.com")
    ws = c.post("/workspaces", json={"name": "V"}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=owner).json()
    assert "secret_key" not in cred
    r = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred["id"], "customer_id": "abc", "name": "x"}, headers=owner)
    assert r.status_code == 400
    assert c.get(f"/workspaces/{ws}/ad-accounts").status_code == 401


def _account(email, cid):
    owner = user(email)
    ws = c.post("/workspaces", json={"name": email}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=owner).json()["id"]
    acc = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": cid, "name": "x"}, headers=owner).json()["id"]
    assert c.post(f"/workspaces/{ws}/ad-accounts/{acc}/sync", headers=owner).json()["status"] == "SUCCESS"
    return owner, ws, acc


def test_auto_bid():
    from app.bulk import run_all_auto_bids
    from app.db import SessionLocal

    owner, ws, acc = _account("bid@a.com", "4004")
    k1 = {"ad_account_id": acc, "naver_id": "kwd-4004-11", "keyword": "원피스1"}  # 입찰가 300
    k2 = {"ad_account_id": acc, "naver_id": "kwd-4004-12", "keyword": "여름 원피스1"}  # 600
    url = f"/workspaces/{ws}/auto-bids"

    assert c.put(url, headers=owner, json={"keywords": [k1], "device": "MOBILE", "target_rank": 6, "max_bid": 500}).status_code == 400
    assert c.put(url, headers=owner, json={"keywords": [k1], "device": "PC", "target_rank": 1, "max_bid": 505}).status_code == 400
    outsider = user("bid2@b.com")
    ws_b = c.post("/workspaces", json={"name": "B2"}, headers=outsider).json()["id"]
    assert c.put(f"/workspaces/{ws_b}/auto-bids", headers=outsider,
                 json={"keywords": [k1], "device": "PC", "target_rank": 1, "max_bid": 500}).status_code == 403

    # Mock 예상가: PC 1위 1070원 → 최대 500원으로 제한, PC 5위 270원. 현재 입찰가는 네이버에서 조회
    c.put(url, headers=owner, json={"keywords": [k1], "device": "PC", "target_rank": 1, "max_bid": 500})
    c.put(url, headers=owner, json={"keywords": [k2], "device": "PC", "target_rank": 5, "max_bid": 5000})
    jobs = c.post(f"{url}/run", headers=owner).json()["job_ids"]
    assert len(jobs) == 1 and c.get(f"/workspaces/{ws}/bulk-jobs/{jobs[0]}", headers=owner).json()["status"] == "DONE"
    kws = store("4004")["keywords"]
    assert kws["kwd-4004-11"]["bidAmt"] == 500 and kws["kwd-4004-12"]["bidAmt"] == 270
    rules = c.get(url, headers=owner).json()
    assert rules[0]["keyword"] == "원피스1" and rules[0]["keyword_naver_id"] == "kwd-4004-11"
    assert "최대 500원" in rules[0]["last_result"] and "300원 → 500원" in rules[0]["last_result"]
    assert c.get(f"/workspaces/{ws}/dashboard", headers=owner).json()["auto_bids"] == 2

    # 다시 돌리면 변경 없음 → 작업도 안 만든다 (크론 경로)
    db = SessionLocal()
    run_all_auto_bids(db)
    db.close()
    assert all("변경 없음" in r["last_result"] for r in c.get(url, headers=owner).json())

    # 네이버에서 지워진 키워드는 결과에 표시
    kws.pop("kwd-4004-12")
    c.post(f"{url}/run", headers=owner)
    assert "네이버에 키워드가 없습니다" in next(r for r in c.get(url, headers=owner).json() if r["keyword_naver_id"] == "kwd-4004-12")["last_result"]

    assert c.post(f"{url}/delete", headers=owner, json={"keywords": [k1, k2]}).json() == {"ok": True}
    assert c.get(url, headers=owner).json() == []

    # 조직당 개수 제한: 한도를 1로 낮춰 2번째 키워드는 거절, 같은 키워드 덮어쓰기·중지는 허용
    from app import main
    main.AUTO_BID_LIMIT = 1
    try:
        body = {"device": "PC", "target_rank": 1, "max_bid": 500}
        assert c.put(url, headers=owner, json={**body, "keywords": [k1]}).status_code == 200
        assert c.put(url, headers=owner, json={**body, "keywords": [k1]}).status_code == 200
        r = c.put(url, headers=owner, json={**body, "keywords": [k2]})
        assert r.status_code == 400 and "1개까지" in r.json()["detail"]
        assert c.put(url, headers=owner, json={**body, "keywords": [k2], "enabled": False}).status_code == 200
    finally:
        main.AUTO_BID_LIMIT = 20


def test_stats_sync_removes_deleted_campaign():
    owner, ws, acc = _account("stale@a.com", "5005")
    store("5005")["campaigns"].pop("cmp-5005-sh")  # 네이버 화면에서 쇼핑 캠페인을 지운 상황
    assert c.post(f"/workspaces/{ws}/ad-accounts/{acc}/sync", headers=owner).json()["status"] == "SUCCESS"
    perf = c.get(f"/workspaces/{ws}/performance/accounts", headers=owner).json()[0]
    assert perf["SHOPPING"] is None and perf["WEB_SITE"] is not None


def test_delete_extension_already_gone():
    owner, ws, acc = _account("gone@a.com", "3003")
    store("3003")["ad-extensions"].pop("ext-3003-pl1")  # 네이버 화면에서 먼저 지워진 상황
    r = c.delete(f"/workspaces/{ws}/ad-extensions/ext-3003-pl1", params={"account_id": acc, "owner_naver_id": "grp-3003-pl1"}, headers=owner)
    assert r.json() == {"ok": True, "already_gone": True}


def test_keyword_create_delete():
    owner, ws, acc = _account("kwc@a.com", "6006")
    old = {"ad_account_id": acc, "naver_id": "kwd-6006-11", "keyword": "원피스1"}
    c.put(f"/workspaces/{ws}/auto-bids", headers=owner, json={"keywords": [old], "device": "PC", "target_rank": 1, "max_bid": 500})

    new = lambda grp, value, **kw: ch(acc, "keyword", grp, "create", value, product="WEB_SITE", **kw)  # noqa: E731
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        new("grp-6006-pl1", "새 키워드|550"),
        new("grp-6006-pl1", "기본가 키워드"),
        new("grp-6006-pl1", "새 키워드|600"),                               # 같은 키워드 중복
        new("grp-6006-pl1", "원피스1", invalid="이미 등록된 키워드입니다"),   # 화면이 보관본으로 찾음
        new("grp-6006-pl1", "x|505"),                                       # 10원 단위 아님
        ch(acc, "keyword", "grp-6006-sh1", "create", "쇼핑", product="SHOPPING"),
        ch(acc, "keyword", old["naver_id"], "delete", before="원피스1"),
    ]}).json()
    rows = [r for a in job["accounts"] for r in a["rows"]]
    assert [r["status"] for r in rows] == ["VALID", "VALID", "INVALID", "INVALID", "INVALID", "INVALID", "VALID"]
    assert rows[-1]["before"] == "원피스1"

    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner).json()["status"] == "DONE"
    now = {k["keyword"]: k for k in store("6006")["keywords"].values()}
    assert "원피스1" not in now and now["새 키워드"]["bidAmt"] == 550 and not now["새 키워드"]["useGroupBidAmt"]
    assert now["기본가 키워드"]["bidAmt"] == 70  # 입찰가 비우면 70원
    assert c.get(f"/workspaces/{ws}/auto-bids", headers=owner).json() == []
    acts = {(h["action"], h["field"]) for h in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()}
    assert {("CREATE", "keyword"), ("DELETE", "keyword")} <= acts


def test_execute_in_chunks():
    from app import bulk

    owner, ws, acc = _account("chunk@a.com", "8008")
    n = bulk.EXECUTE_CHUNK + 2
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "keyword", "grp-8008-pl1", "create", f"묶음{i}", product="WEB_SITE") for i in range(n)]}).json()
    url = f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute"
    first = c.post(url, headers=owner).json()  # 요청이 끊긴 RUNNING 작업도 이렇게 이어 간다
    assert first["status"] == "RUNNING" and first["counts"]["SUCCESS"] == bulk.EXECUTE_CHUNK and first["counts"]["VALID"] == 2
    last = c.post(url, headers=owner).json()
    assert last["status"] == "DONE" and last["counts"]["SUCCESS"] == n and last["executed_at"]
    assert c.post(url, headers=owner).status_code == 409


def test_rsa_texts():
    from app.naver import _rsa_texts

    assets = [{"linkType": "HEADLINE", "assetData": '{"text": "여름 세일"}'},
              {"linkType": "HEADLINE", "assetData": "무료배송"},
              {"linkType": "DESCRIPTION", "assetData": {"text": "전 상품 할인"}},
              {"linkType": "OTHER", "assetData": "무시"}]
    assert _rsa_texts(assets) == {"headlines": ["여름 세일", "무료배송"], "descriptions": ["전 상품 할인"]}


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


def test_keyword_tool():
    owner = user("kt@a.com")
    ws = c.post("/workspaces", json={"name": "T"}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=owner).json()["id"]
    acc = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": "7007", "name": "t"}, headers=owner).json()["id"]
    url = f"/workspaces/{ws}/keyword-tool"
    rows = c.get(url, params={"account_id": acc, "hint": "린넨 원피스, 린넨원피스,"}, headers=owner).json()
    assert len(rows) == 5 and rows[0]["keyword"].startswith("린넨원피스")  # 띄어쓰기 제거·중복 제거
    assert [r["pc"] + r["mobile"] for r in rows] == sorted((r["pc"] + r["mobile"] for r in rows), reverse=True)
    assert next(r for r in rows if r["keyword"] == "린넨원피스")["pc"] == 0  # "< 10"
    assert c.get(url, params={"account_id": acc, "hint": " , "}, headers=owner).status_code == 400
    outsider = user("kt2@b.com")
    ws_b = c.post("/workspaces", json={"name": "T2"}, headers=outsider).json()["id"]
    assert c.get(f"/workspaces/{ws_b}/keyword-tool", params={"account_id": acc, "hint": "a"}, headers=outsider).status_code == 403


def test_master_file_signing():
    from app.naver import RealNaverClient

    src = RealNaverClient("k", "s", "1").master_file({"downloadUrl": "https://api.searchad.naver.com/report-download?authtoken=T"})
    assert src["url"].endswith("?authtoken=T") and src["headers"]["X-Customer"] == "1"
    # 서명 uri는 쿼리를 뺀 경로
    import base64, hashlib, hmac
    ts = src["headers"]["X-Timestamp"]
    want = base64.b64encode(hmac.new(b"s", f"{ts}.GET./report-download".encode(), hashlib.sha256).digest()).decode()
    assert src["headers"]["X-Signature"] == want


def test_master_reports_and_lookup():
    owner = user("mr@a.com")
    ws = c.post("/workspaces", json={"name": "M"}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=owner).json()["id"]
    acc = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": "9009", "name": "t"}, headers=owner).json()["id"]
    base = f"/workspaces/{ws}/ad-accounts/{acc}"
    job = c.post(f"{base}/master-reports", params={"item": "Keyword"}, headers=owner).json()
    assert c.get(f"{base}/master-reports/{job['id']}", headers=owner).json()["status"] == "BUILT"
    rows = [r.split("\t") for r in c.get(f"{base}/master-reports/{job['id']}/file", headers=owner).text.split("\n")]
    assert len(rows) == 6 and all(len(r) == 13 for r in rows) and rows[0][2].startswith("kwd-")
    assert c.post(f"{base}/master-reports", params={"item": "Nope"}, headers=owner).status_code == 422

    camps = c.get(f"{base}/naver/campaigns", headers=owner).json()
    assert {x["campaign_tp"] for x in camps} == {"WEB_SITE", "SHOPPING"} and camps[0]["ad_account_id"] == acc
    g = c.get(f"{base}/naver/adgroups", params={"ids": "grp-9009-pl1,grp-9009-pl2"}, headers=owner).json()
    assert [x["serving"] for x in g] == ["GROUP_LIMITED_BY_BUDGET", "ELIGIBLE"] and g[1]["daily_budget"] is None
    e = c.get(f"{base}/naver/ad-extensions", params={"ids": "ext-9009-pl1"}, headers=owner).json()
    assert e[0]["payload"] == [{"name": "신상품", "final": "https://example.com/new"}]

    outsider = user("mr2@b.com")
    assert c.get(f"{base}/naver/campaigns", headers=outsider).status_code == 403
    assert c.get(f"{base}/master-reports/x/file", headers=outsider).status_code == 403
    assert c.get(f"{base}/master-reports/x/file").status_code == 401
