import json
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

    # Mock 검색 화면: 경쟁 광고 900·700·500·300·150원. 원피스1(300원) 5위 → 목표 1위라 20% 올림, 여름 원피스1(600원) 3위 = 목표
    c.put(url, headers=owner, json={"keywords": [k1], "device": "PC", "target_rank": 1, "max_bid": 500})
    c.put(url, headers=owner, json={"keywords": [k2], "device": "MOBILE", "target_rank": 3, "max_bid": 5000})
    jobs = c.post(f"{url}/run", headers=owner).json()["job_ids"]
    assert len(jobs) == 1 and c.get(f"/workspaces/{ws}/bulk-jobs/{jobs[0]}", headers=owner).json()["status"] == "DONE"
    kws = store("4004")["keywords"]
    assert kws["kwd-4004-11"]["bidAmt"] == 360 and kws["kwd-4004-12"]["bidAmt"] == 600
    rules = {r["keyword_naver_id"]: r for r in c.get(url, headers=owner).json()}
    assert rules["kwd-4004-11"]["keyword"] == "원피스1"
    assert rules["kwd-4004-11"]["last_result"] == "지금 5위 (목표 1위) · 300원 → 360원"
    assert rules["kwd-4004-12"]["last_result"] == "지금 3위 (목표 3위) · 변경 없음"
    assert c.get(f"/workspaces/{ws}/dashboard", headers=owner).json()["auto_bids"] == 2

    # 크론 경로: 360원은 4위 → 다시 올림
    db = SessionLocal()
    run_all_auto_bids(db)
    db.close()
    assert kws["kwd-4004-11"]["bidAmt"] == 430

    # 지금 순위 확인 (보기 권한)
    r = c.post(f"/workspaces/{ws}/ranks", headers=owner, json={"keywords": [k1, k2]}).json()
    assert r == [{"naver_id": "kwd-4004-11", "PC": 4, "MOBILE": 4}, {"naver_id": "kwd-4004-12", "PC": 3, "MOBILE": 3}]
    assert c.post(f"/workspaces/{ws}/ranks", headers=owner, json={"keywords": [k1] * 11}).status_code == 400

    # 꺼진 키워드는 노출이 안 돼 입찰가만 오르므로 건너뜀
    kws["kwd-4004-11"]["userLock"] = True
    c.post(f"{url}/run", headers=owner)
    assert kws["kwd-4004-11"]["bidAmt"] == 430
    assert "OFF라 건너뜀" in next(r for r in c.get(url, headers=owner).json() if r["keyword_naver_id"] == "kwd-4004-11")["last_result"]
    kws["kwd-4004-11"]["userLock"] = False

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


def test_master_report_limit_clears_and_retries():
    from app.naver import NaverApiError, RealNaverClient

    calls = []

    def fake_req(method, uri, **kw):
        calls.append((method, uri))
        if len(calls) == 1:
            raise NaverApiError('400 {"detail":"exceeded limit of \'100\' numbers of \'job\'"}')
        return {"id": "job-1"}

    cl = RealNaverClient("k", "s", "1")
    cl._req = fake_req
    assert cl.create_master_report("Keyword") == {"id": "job-1"}
    assert calls == [("POST", "/master-reports"), ("DELETE", "/master-reports"), ("POST", "/master-reports")]


def test_ad_delete():
    owner, ws, acc = _account("addel@a.com", "6106")
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "ad", "ad-6106-pl1", "delete", product="WEB_SITE"),
        ch(acc, "adgroup", "grp-6106-pl1", "delete", product="WEB_SITE"),  # 광고그룹 삭제는 허용 안 함
    ]}).json()
    assert [r["status"] for a in job["accounts"] for r in a["rows"]] == ["VALID", "INVALID"]
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner).json()["status"] == "DONE"
    assert "ad-6106-pl1" not in store("6106")["ads"] and "ad-6106-pl2" in store("6106")["ads"]
    acts = {(h["action"], h["field"]) for h in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()}
    assert ("DELETE", "ad") in acts


def test_negative_keywords():
    owner, ws, acc = _account("neg@a.com", "6107")
    url, grp = f"/workspaces/{ws}/ad-accounts/{acc}/adgroups/grp-6107-pl1/negative-keywords", "grp-6107-pl1"
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "negative_keyword", grp, "create", "무료"), ch(acc, "negative_keyword", grp, "create", "중고"),
        ch(acc, "negative_keyword", grp, "create", ""),  # 빈 검색어
    ]}).json()
    assert [r["status"] for a in job["accounts"] for r in a["rows"]] == ["VALID", "VALID", "INVALID"]
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner).json()["status"] == "DONE"
    neg = c.get(url, headers=owner).json()
    assert [n["keyword"] for n in neg] == ["무료", "중고"]
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "negative_keyword", neg[0]["naver_id"], "delete", grp)]}).json()
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner).json()["status"] == "DONE"
    assert [n["keyword"] for n in c.get(url, headers=owner).json()] == ["중고"]
    acts = {(h["action"], h["field"]) for h in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()}
    assert {("CREATE", "negative_keyword"), ("DELETE", "negative_keyword")} <= acts


def test_schedule_job(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app import bulk
    from app.db import SessionLocal

    owner, ws, acc = _account("sched@a.com", "6108")
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "campaign", "cmp-6108-pl", "status", "OFF", before="ON", product="WEB_SITE")]}).json()
    url = f"/workspaces/{ws}/bulk-jobs/{job['id']}/schedule"
    at = datetime.now(timezone.utc) + timedelta(days=16)
    assert c.post(url, headers=owner, json={"scheduled_at": "2026-11-12T00:00:00"}).status_code == 400  # 시간대 없음
    assert c.post(url, headers=owner, json={"scheduled_at": "2020-01-01T00:00:00+09:00"}).status_code == 400  # 과거
    kst = at.astimezone(timezone(timedelta(hours=9))).isoformat()
    assert c.post(url, headers=owner, json={"scheduled_at": kst}).json()["scheduled_at"]

    run = lambda: (lambda db: (bulk.run_scheduled_jobs(db), db.close()))(SessionLocal())  # noqa: E731
    run()  # 아직 시각 전
    camps = store("6108")["campaigns"]
    assert camps["cmp-6108-pl"]["userLock"] is False
    monkeypatch.setattr(bulk, "now", lambda: at + timedelta(minutes=1))
    run()
    assert camps["cmp-6108-pl"]["userLock"] is True
    assert c.get(f"/workspaces/{ws}/bulk-jobs/{job['id']}", headers=owner).json()["status"] == "DONE"
    assert c.post(url, headers=owner, json={"scheduled_at": None}).status_code == 409  # 실행된 작업은 예약 불가


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

    import pytest

    from app.naver import NaverApiError, RealNaverClient

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

    class Page:
        status_code, text = 200, "<a i=nad-a001-01-2>x</a><a i=nad-a001-01-1></a><b nad-a001-01-2></b>"

    got = {}
    monkeypatch.setattr("app.naver.httpx.get", lambda url, **kw: got.setdefault("url", url) and Page)
    assert RealNaverClient("k", "s", "1").serp_ads("원 피스", "MOBILE") == ["nad-a001-01-2", "nad-a001-01-1"]  # 노출 순서, 중복 제거
    assert got["url"].startswith("https://m.ad.search.naver.com/") and got["url"].endswith("%EC%9B%90%20%ED%94%BC%EC%8A%A4")
    Page.text = "<html>차단</html>"  # 광고 ID가 하나도 없으면 '내 광고 없음'이 아니라 실패
    with pytest.raises(NaverApiError):
        RealNaverClient("k", "s", "1").serp_ads("원피스", "PC")


def test_next_bid():
    from app.bulk import next_bid
    assert next_bid(300, 5, 1, 500) == 360 and next_bid(300, None, 1, 500) == 360  # 아래거나 안 보이면 +20%
    assert next_bid(480, 5, 1, 500) == 500 and next_bid(500, 4, 1, 500) == 500    # 최대 입찰가에서 멈춤
    assert next_bid(600, 2, 5, 5000) == 540 and next_bid(70, 1, 3, 500) == 70     # 위면 -10%, 최소 70원
    assert next_bid(400, 3, 3, 500) == 400 and next_bid(70, 9, 1, 500) == 80      # 목표면 그대로, 최소 10원씩


def test_goal_bid():
    from app.bulk import goal_bid
    s = lambda clk, cost, conv=0, rev=0: {"clkCnt": clk, "salesAmt": cost, "ccnt": conv, "convAmt": rev}  # noqa: E731
    assert goal_bid(500, s(9, 900, 1, 9000), 300, 1000, None, True) is None                # 클릭 부족
    assert goal_bid(500, s(50, 20000), 300, 1000, 20000, True) == "OFF"                    # 무전환 비용 초과
    assert goal_bid(500, s(50, 20000), 300, 1000, None, True) is None                      # OFF 기준 없음
    assert goal_bid(500, s(50, 10000, 1, 20000), 300, 1000, None, True) == 450             # 200% < 300% → -10%
    assert goal_bid(500, s(50, 10000, 1, 40000), 300, 1000, None, True) == 550             # 400% → +10%
    assert goal_bid(500, s(50, 10000, 1, 40000), 300, 1000, None, False) is None           # 계정이 목표 미달이면 안 올림
    assert goal_bid(500, s(50, 10000, 1, 31000), 300, 1000, None, True) is None            # 목표 근처
    assert goal_bid(500, s(50, 10000, 1, 40000), 300, 520, None, True) == 520              # 최대 입찰가
    assert goal_bid(80, s(50, 10000, 1, 10000), 300, 1000, None, True) == 70               # 최소 70원


def test_account_goal(monkeypatch):
    from datetime import datetime
    from app import bulk
    from app.db import SessionLocal
    from app.naver import MockNaverClient

    owner, ws, acc = _account("goal@a.com", "4006")
    url = f"/workspaces/{ws}/account-goals"
    goal = {"ad_account_id": acc, "roas_target": 300, "max_bid": 1000, "off_cost": 20000}
    assert c.put(url, headers=owner, json={**goal, "max_bid": 1005}).status_code == 400
    outsider = user("goal2@b.com")
    ws_b = c.post("/workspaces", json={"name": "G2"}, headers=outsider).json()["id"]
    assert c.put(f"/workspaces/{ws_b}/account-goals", headers=outsider, json=goal).status_code == 403
    assert c.put(url, headers=owner, json=goal).json() == {"ok": True}

    stats = {"cmp-4006-pl": {"clkCnt": 100, "salesAmt": 10000, "ccnt": 5, "convAmt": 40000},   # 계정 400% → 올림 허용
             "kwd-4006-11": {"clkCnt": 20, "salesAmt": 2000, "ccnt": 1, "convAmt": 10000},     # 500% → 300→330
             "kwd-4006-12": {"clkCnt": 20, "salesAmt": 5000, "ccnt": 1, "convAmt": 10000},     # 200% → 600→540
             "kwd-4006-13": {"clkCnt": 20, "salesAmt": 25000, "ccnt": 0},                      # 무전환 → OFF
             "kwd-4006-21": {"clkCnt": 5, "salesAmt": 500, "ccnt": 1, "convAmt": 90000}}       # 클릭 부족 → 그대로
    seen = []
    monkeypatch.setattr(MockNaverClient, "entity_stats", lambda self, ids, since, until: seen.append(ids) or {i: stats[i] for i in ids if i in stats})

    t = datetime(2026, 10, 27, 10, tzinfo=bulk.KST)
    monkeypatch.setattr(bulk, "datetime", type("D", (datetime,), {"now": staticmethod(lambda tz=None: t)}))
    # 지금 실행 = 1단계(시작: 캠페인 성과·광고그룹 목록). 쇼핑 캠페인은 빼고 파워링크만
    r = c.post(f"{url}/{acc}/run", headers=owner).json()["last_result"]
    assert "7일 계정 ROAS 400% (목표 300%)" in r and "광고그룹 2개 남음" in r and seen == [["cmp-4006-pl"]]

    # 나머지는 크론이 1단계씩(광고그룹 2개), 끝나면 그날은 더 안 돈다
    for _ in range(4):
        db = SessionLocal()
        bulk.run_all_goals(db)
        db.close()
    kws = store("4006")["keywords"]
    assert [kws[f"kwd-4006-1{i}"]["bidAmt"] for i in (1, 2, 3)] == [330, 540, 900] and kws["kwd-4006-13"]["userLock"] is True
    assert kws["kwd-4006-21"]["bidAmt"] == 300
    g = c.get(url, headers=owner).json()[0]
    assert g["last_result"].endswith("키워드 6개 확인, 입찰가 조정 2개, OFF 1개") and len(seen) == 3
    assert c.delete(f"{url}/{acc}", headers=owner).json() == {"ok": True} and c.get(url, headers=owner).json() == []


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
    import pytest

    from app.naver import NaverApiError, RealNaverClient

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


def test_seo_fetch_blocks():
    u = user("seo@a.com")
    ws = c.post("/workspaces", json={"name": "SEO"}, headers=u).json()["id"]
    for bad in ("https://smartstore.naver.com/shop/products/1", "https://m.smartstore.naver.com/x", "https://brand.naver.com/b",
                "ftp://a.com", "a.com", "http://localhost:8000", "http://127.0.0.1", "http://192.168.0.1/admin", "http://[::1]/"):
        r = c.get(f"/workspaces/{ws}/seo-fetch", params={"url": bad}, headers=u)
        assert r.status_code == 400, bad
    assert "스마트스토어" in c.get(f"/workspaces/{ws}/seo-fetch", params={"url": "https://smartstore.naver.com/a"}, headers=u).json()["detail"]
    assert c.get(f"/workspaces/{ws}/seo-fetch", params={"url": "https://a.com"}, headers=user("seo2@b.com")).status_code == 403


def test_mcp_oauth_and_tools():
    import base64
    import hashlib
    from urllib.parse import parse_qs, urlparse

    owner = user("mcp@a.com")
    ws = c.post("/workspaces", json={"name": "M"}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=owner).json()["id"]
    acc = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": "8008", "name": "m"}, headers=owner).json()["id"]

    # 토큰 없으면 401 + 로그인 안내 주소
    r = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401 and "resource_metadata=" in r.headers["www-authenticate"]
    assert c.get("/.well-known/oauth-authorization-server").json()["registration_endpoint"].endswith("/oauth/register")

    # 등록: Claude·localhost 외 주소는 거부
    assert c.post("/oauth/register", json={"redirect_uris": ["https://evil.com/cb"]}).status_code == 400
    cb = "http://localhost:3333/callback"
    client_id = c.post("/oauth/register", json={"redirect_uris": [cb]}).json()["client_id"]

    verifier = "v" * 50
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    q = {"client_id": client_id, "redirect_uri": cb, "code_challenge": challenge, "code_challenge_method": "S256", "state": "s1"}
    assert c.get("/oauth/authorize", params={**q, "redirect_uri": "http://localhost:9/other"}).status_code == 400  # 등록 안 한 주소
    assert c.get("/oauth/authorize", params=q).status_code == 200
    assert c.post("/oauth/authorize", data={**q, "email": "mcp@a.com", "password": "wrong"}, follow_redirects=False).status_code == 401
    r = c.post("/oauth/authorize", data={**q, "email": "mcp@a.com", "password": "password1"}, follow_redirects=False)
    loc = urlparse(r.headers["location"])
    code = parse_qs(loc.query)["code"][0]
    assert r.status_code == 302 and parse_qs(loc.query)["state"] == ["s1"]

    tok = {"grant_type": "authorization_code", "code": code, "redirect_uri": cb, "client_id": client_id}
    assert c.post("/oauth/token", data={**tok, "code_verifier": "x" * 50}).status_code == 400  # PKCE 불일치
    t = c.post("/oauth/token", data={**tok, "code_verifier": verifier}).json()
    assert c.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": code}).status_code == 400  # 코드는 갱신 토큰이 아님
    t = c.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": t["refresh_token"]}).json()
    h = {"Authorization": f"Bearer {t['access_token']}"}
    assert c.get(f"/workspaces/{ws}/ad-accounts", headers={"Authorization": f"Bearer {t['refresh_token']}"}).status_code == 401

    def call(name, **args):
        r = c.post("/mcp", headers=h, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": name, "arguments": args}})
        res = r.json()["result"]
        return json.loads(res["content"][0]["text"]), res["isError"]

    init = c.post("/mcp", headers=h, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}).json()
    assert init["result"]["protocolVersion"] == "2025-06-18"
    assert c.post("/mcp", headers=h, json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202

    accounts, _ = call("list_ad_accounts")
    assert accounts[0]["id"] == ws and accounts[0]["accounts"][0]["id"] == acc
    camps, _ = call("list_campaigns", workspace_id=ws, ad_account_id=acc)
    groups, _ = call("list_adgroups", workspace_id=ws, ad_account_id=acc, campaign_id=camps[0]["naver_id"])
    kws, _ = call("list_keywords", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"])
    assert kws[0]["bid_amt"] == 300
    ads, _ = call("list_ads", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"])
    exts, _ = call("list_ad_extensions", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"])
    assert ads[0]["ad_type"] == "TEXT_45" and exts[0]["ext_type"] == "SUB_LINKS"
    perf, err = call("get_performance", workspace_id=ws)
    assert not err

    job, _ = call("preview_changes", workspace_id=ws, changes=[
        {"entity_type": "keyword", "naver_id": kws[0]["naver_id"], "field": "bid_amt", "value": "400", "ad_account_id": acc, "before": "300"}])
    assert job["counts"]["VALID"] == 1 and store("8008")["keywords"][kws[0]["naver_id"]]["bidAmt"] == 300  # 미리보기는 반영 안 함
    done, _ = call("execute_job", workspace_id=ws, job_id=job["id"])
    assert done["status"] == "DONE" and store("8008")["keywords"][kws[0]["naver_id"]]["bidAmt"] == 400

    # 키워드별 성과(광고그룹 단위·ids), 소재·확장소재 등록(OFF로 생성), 작업 기록
    perf, err = call("get_entity_performance", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"])
    assert not err and len(perf["rows"]) == len(kws) and perf["rows"][0]["keyword"] and "avg_rank" in perf["rows"][0]
    assert call("get_entity_performance", workspace_id=ws, ad_account_id=acc, ids=[])[1]  # 대상 없음
    url = f"/workspaces/{ws}/performance/entities"
    assert c.post(url, headers=owner, json={"ad_account_id": acc, "ids": ["x"] * 501}).status_code == 400
    assert c.post(url, headers=owner, json={"ad_account_id": acc, "ids": ["x"], "since": "2026-01-01", "until": "2026-06-01"}).status_code == 400
    assert c.post(url, headers=owner, json={"ad_account_id": acc, "ids": ["x"]}).json()["rows"][0]["impressions"] >= 0
    ad, err = call("create_ad", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"], headlines=["여름 원피스", "무료배송"],
                   descriptions=["린넨 원피스 전 상품 무료배송"], pc_url="https://example.com")
    assert not err and ad["status"] == "OFF" and ad["payload"]["headlines"] == ["여름 원피스", "무료배송"], ad
    assert call("create_ad", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"], headlines=[], descriptions=["a"],
                pc_url="https://example.com")[1]
    ext, err = call("create_ad_extension", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"], ext_type="HEADLINE",
                    heading="오늘만 할인")
    assert not err and ext["ext_type"] == "HEADLINE"
    logs, _ = call("list_audit_logs", workspace_id=ws, limit=3)
    assert len(logs) == 3 and logs[0]["user"] == "mcp@a.com" and {x["entity_type"] for x in logs[:2]} == {"ad", "ad_extension"}

    # 자동입찰: 순위 확인 → 규칙 저장 → 지금 실행. 원피스1(300→400원)은 Mock 검색 화면 4위, 목표 1위라 20% 올림
    k = [{"ad_account_id": acc, "naver_id": kws[0]["naver_id"], "keyword": kws[0]["keyword"]}]
    assert call("check_ranks", workspace_id=ws, keywords=k)[0][0]["PC"] == 4
    assert call("set_auto_bid", workspace_id=ws, keywords=k, device="PC", target_rank=11, max_bid=1000)[1]  # PC는 10위까지
    assert call("set_auto_bid", workspace_id=ws, keywords=k, device="PC", target_rank=1, max_bid=1000) == ({"ok": True}, False)
    call("run_auto_bids", workspace_id=ws, keywords=k)
    assert store("8008")["keywords"][kws[0]["naver_id"]]["bidAmt"] == 480
    assert call("list_auto_bids", workspace_id=ws)[0][0]["last_result"] == "지금 4위 (목표 1위) · 400원 → 480원"
    call("delete_auto_bid", workspace_id=ws, keywords=k)
    assert call("list_auto_bids", workspace_id=ws)[0] == []

    # 다른 조직 사용자는 도구로도 못 본다
    other = user("mcp2@b.com")
    h = other
    assert call("list_campaigns", workspace_id=ws, ad_account_id=acc) == ({"error": "이 조직에 접근 권한이 없습니다"}, True)
    assert call("get_daily_performance", workspace_id=ws)[1]  # 인자 누락


def _viewer(owner, ws, acc, email):
    v = user(email)
    mid = c.post(f"/workspaces/{ws}/members", json={"email": email}, headers=owner).json()["membership_id"]
    c.put(f"/workspaces/{ws}/members/{mid}/access", json={"ad_account_id": acc, "level": "VIEW"}, headers=owner)
    return v


def test_schedule_guards(monkeypatch):
    from datetime import datetime, timedelta, timezone
    from app import bulk
    from app.db import SessionLocal

    owner, ws, acc = _account("guard@a.com", "6200")
    viewer = _viewer(owner, ws, acc, "guardv@a.com")
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "keyword", "kwd-6200-11", "bid_amt", "400", before="300"),
        ch(acc, "keyword", "kwd-6200-12", "bid_amt", "700", before="600"),
        ch(acc, "adgroup", "grp-6200-pl1", "status", "OFF", before="ON", product="WEB_SITE")]}).json()
    url = f"/workspaces/{ws}/bulk-jobs/{job['id']}"
    at = datetime.now(timezone.utc) + timedelta(days=20)
    # 보기 권한 직원이 남의 미리보기를 예약하면 만든 사람 권한으로 실행되므로 막는다
    assert c.post(f"{url}/schedule", headers=viewer, json={"scheduled_at": at.isoformat()}).status_code == 403
    assert c.post(f"{url}/schedule", headers=owner, json={"scheduled_at": at.isoformat()}).status_code == 200
    assert c.post(f"{url}/execute", headers=owner).status_code == 409  # 크론과 겹쳐 두 번 실행되지 않게

    kws = store("6200")["keywords"]
    kws["kwd-6200-11"]["bidAmt"] = 350  # 예약 후 누가 네이버에서 직접 바꿈
    monkeypatch.setattr(bulk, "now", lambda: at + timedelta(minutes=1))
    db = SessionLocal()
    bulk.run_scheduled_jobs(db)
    db.close()
    out = c.get(url, headers=owner).json()
    rows = {r["naver_id"]: r for r in out["accounts"][0]["rows"]}
    assert out["status"] == "PARTIAL" and "미리보기 이후 값이 바뀌어" in rows["kwd-6200-11"]["error"]
    assert kws["kwd-6200-11"]["bidAmt"] == 350 and kws["kwd-6200-12"]["bidAmt"] == 700
    assert store("6200")["adgroups"]["grp-6200-pl1"]["userLock"] is True

    # 예상 못 한 오류가 나도 작업을 끝내 다음 크론이 같은 작업에 막히지 않는다
    job2 = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "keyword", "kwd-6200-13", "bid_amt", "1000", before="900")]}).json()
    c.post(f"/workspaces/{ws}/bulk-jobs/{job2['id']}/schedule", headers=owner, json={"scheduled_at": at.isoformat()})
    monkeypatch.setattr(bulk, "execute_job", lambda *a, **k: 1 / 0)
    db = SessionLocal()
    bulk.run_scheduled_jobs(db)
    db.close()
    assert c.get(f"/workspaces/{ws}/bulk-jobs/{job2['id']}", headers=owner).json()["status"] == "FAILED"


def test_auto_bid_guards(monkeypatch):
    from app import bulk

    owner, ws, acc = _account("cap@a.com", "6300")
    viewer = _viewer(owner, ws, acc, "capv@a.com")
    url = f"/workspaces/{ws}/auto-bids"
    k = {"ad_account_id": acc, "naver_id": "kwd-6300-11", "keyword": "원피스1"}  # 300원, 5위
    c.put(url, headers=owner, json={"keywords": [k], "device": "PC", "target_rank": 1, "max_bid": 5000})
    kws = store("6300")["keywords"]
    assert c.post(f"{url}/run", headers=viewer).json() == {"job_ids": []} and kws["kwd-6300-11"]["bidAmt"] == 300

    monkeypatch.setattr(bulk, "AUTO_BID_DAILY_MAX", 1)
    c.post(f"{url}/run", headers=owner)
    assert kws["kwd-6300-11"]["bidAmt"] == 360
    c.post(f"{url}/run", headers=owner)
    assert kws["kwd-6300-11"]["bidAmt"] == 360
    assert "오늘 자동 변경 1번" in c.get(url, headers=owner).json()[0]["last_result"]


def test_goal_guards(monkeypatch):
    from datetime import datetime
    from app import bulk
    from app.db import SessionLocal
    from app.naver import MockNaverClient

    owner, ws, acc = _account("goal3@a.com", "6400")
    c.put(f"/workspaces/{ws}/auto-bids", headers=owner, json={"keywords": [{"ad_account_id": acc, "naver_id": "kwd-6400-11"}],
                                                             "device": "PC", "target_rank": 1, "max_bid": 5000})
    url = f"/workspaces/{ws}/account-goals"
    c.put(url, headers=owner, json={"ad_account_id": acc, "roas_target": 300, "max_bid": 1000, "off_cost": 20000})
    stats = {"cmp-6400-pl": {"clkCnt": 100, "salesAmt": 30000, "ccnt": 0},                  # 계정 전환 0 = 추적 안 됨일 수 있음
             "kwd-6400-11": {"clkCnt": 20, "salesAmt": 5000, "ccnt": 1, "convAmt": 10000},  # 200%라 내릴 대상이지만 순위 자동입찰 키워드
             "kwd-6400-13": {"clkCnt": 20, "salesAmt": 25000, "ccnt": 0}}                   # 원래면 무전환 OFF
    monkeypatch.setattr(MockNaverClient, "entity_stats", lambda self, ids, since, until: {i: stats[i] for i in ids if i in stats})
    t = datetime(2026, 10, 27, 10, tzinfo=bulk.KST)
    monkeypatch.setattr(bulk, "datetime", type("D", (datetime,), {"now": staticmethod(lambda tz=None: t)}))
    c.post(f"{url}/{acc}/run", headers=owner)
    for _ in range(4):
        db = SessionLocal()
        bulk.run_all_goals(db)
        db.close()
    kws = store("6400")["keywords"]
    assert kws["kwd-6400-11"]["bidAmt"] == 300 and kws["kwd-6400-13"]["userLock"] is False
    assert "계정 전환 0건이라 무전환 OFF 안 함" in c.get(url, headers=owner).json()[0]["last_result"]


def test_login_limit(monkeypatch):
    from datetime import timedelta
    from app import main

    user("lock@a.com")
    login = lambda email, pw, **h: c.post("/auth/login", json={"email": email, "password": pw}, headers=h)  # noqa: E731
    for _ in range(main.LOGIN_MAX["email"]):
        assert login("lock@a.com", "wrong").status_code == 401
    r = login("lock@a.com", "password1")  # 맞는 비밀번호도 막힌 동안은 거부
    assert r.status_code == 429 and "15분" in r.json()["detail"]
    for _ in range(main.LOGIN_MAX["email"]):  # 없는 이메일도 똑같이 막혀 가입 여부가 드러나지 않는다
        login("nobody@a.com", "wrong")
    assert login("nobody@a.com", "wrong").status_code == 429

    # MCP(Claude 연결) 로그인도 같은 제한
    cb = "http://localhost:3333/callback"
    q = {"client_id": c.post("/oauth/register", json={"redirect_uris": [cb]}).json()["client_id"], "redirect_uri": cb,
         "code_challenge": "x" * 43, "code_challenge_method": "S256", "state": "s"}
    assert c.post("/oauth/authorize", data={**q, "email": "lock@a.com", "password": "password1"}, follow_redirects=False).status_code == 429

    # 15분이 지나면 다시 로그인, 성공하면 실패 기록이 지워진다
    real_now = main.now
    monkeypatch.setattr(main, "now", lambda: real_now() + timedelta(minutes=16))
    assert login("lock@a.com", "password1").status_code == 200
    for _ in range(main.LOGIN_MAX["email"] - 1):
        login("lock@a.com", "wrong")
    assert login("lock@a.com", "password1").status_code == 200

    # 같은 IP에서 여러 이메일로 틀리면 IP로 막는다
    monkeypatch.setitem(main.LOGIN_MAX, "ip", 3)
    ip = {"cf-connecting-ip": "203.0.113.9"}
    for i in range(3):
        login(f"spray{i}@a.com", "wrong", **ip)
    assert login("lock@a.com", "password1", **ip).status_code == 429
    assert login("lock@a.com", "password1").status_code == 200  # 다른 IP는 그대로
