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

    # 미리보기 후 권한이 회수되면 그 작업은 보이지도 실행되지도 않는다
    mid = next(x["membership_id"] for x in c.get(f"/workspaces/{ws}/members", headers=owner).json() if x["email"] == "staff@a.com")
    j2 = c.post(f"/workspaces/{ws}/bulk-jobs", headers=staff, json={"changes": [ch(a1, "campaign", "cmp-1001-sh", "status", "OFF")]}).json()
    c.put(f"/workspaces/{ws}/members/{mid}/access", json={"ad_account_id": a1, "level": None}, headers=owner)
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{j2['id']}/execute", headers=staff).status_code == 404
    assert c.get(f"/workspaces/{ws}/bulk-jobs/{j2['id']}", headers=staff).status_code == 404

    # 성과·대시보드·구독
    perf = c.get(f"/workspaces/{ws}/performance/accounts", headers=owner).json()
    assert len(perf) == 2 and perf[0]["WEB_SITE"]["cost"] > 0 and perf[0]["SHOPPING"] is not None
    p1 = next(p for p in perf if p["ad_account_id"] == a1)
    perf_a1_cost = p1["WEB_SITE"]["cost"] + p1["SHOPPING"]["cost"]
    dash = c.get(f"/workspaces/{ws}/dashboard", headers=owner).json()
    assert dash["connected_accounts"] == 2 and job["id"] in dash["failed_jobs"] and dash["auto_bids"] == 0
    rj = next(j for j in dash["recent_jobs"] if j["id"] == job["id"])
    assert rj["counts"]["SUCCESS"] + rj["counts"]["FAILED"] > 0 and rj["accounts"] is None  # 행은 안 읽고 개수만
    from datetime import timedelta
    from app.models import today_kst
    until = today_kst() - timedelta(days=1)
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


def test_campaign_adgroup_create():
    owner, ws, acc = _account("cmpc@a.com", "6206")
    rows = lambda job: [r for a in job["accounts"] for r in a["rows"]]  # noqa: E731
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "campaign", "WEB_SITE", "create", "새 파워링크|30000"),
        ch(acc, "campaign", "SHOPPING", "create", "새 쇼핑|50000"),
        ch(acc, "campaign", "WEB_SITE", "create", "예산 없음|"),       # 일예산 필수
        ch(acc, "campaign", "BRAND", "create", "브랜드|10000"),          # 지원 안 하는 유형
    ]}).json()
    assert [r["status"] for r in rows(job)] == ["VALID", "VALID", "INVALID", "INVALID"]
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner).json()["status"] == "DONE"
    camps = {x["name"]: x for x in store("6206")["campaigns"].values()}
    pl, sh = camps["새 파워링크"], camps["새 쇼핑"]
    assert pl["userLock"] and pl["dailyBudget"] == 30000 and sh["campaignTp"] == "SHOPPING"  # 새 캠페인은 OFF

    chans = c.get(f"/workspaces/{ws}/ad-accounts/{acc}/naver/channels", headers=owner).json()
    site = next(x["naver_id"] for x in chans if x["channel_tp"] == "SITE")
    shop = next(x["naver_id"] for x in chans if x["channel_tp"] == "MALL")
    grp = lambda cmp, value, product="WEB_SITE": ch(acc, "adgroup", cmp, "create", value, product=product)  # noqa: E731
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        grp(pl["nccCampaignId"], f"그룹A|{site}|500|20000"),
        grp(pl["nccCampaignId"], f"그룹B|{site}"),                          # 입찰가·하루예산 비움
        grp(sh["nccCampaignId"], f"쇼핑그룹|{shop}||", "SHOPPING"),
        grp(pl["nccCampaignId"], f"채널 틀림|{shop}"),                       # 검증은 통과, 네이버(Mock)가 거부
        grp(pl["nccCampaignId"], "채널 없음||500"),
        grp(pl["nccCampaignId"], f"단위|{site}|505"),
    ]}).json()
    assert [r["status"] for r in rows(job)] == ["VALID", "VALID", "VALID", "VALID", "INVALID", "INVALID"]
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner).json()["status"] == "PARTIAL"
    groups = {g["name"]: g for g in store("6206")["adgroups"].values()}
    a, b, s_ = groups["그룹A"], groups["그룹B"], groups["쇼핑그룹"]
    assert a["userLock"] and a["bidAmt"] == 500 and a["useDailyBudget"] and a["dailyBudget"] == 20000 and a["pcChannelId"] == site
    assert b["bidAmt"] == 70 and not b["useDailyBudget"] and s_["adgroupType"] == "SHOPPING" and s_["bidAmt"] == 50
    assert "채널 틀림" not in groups
    acts = {(h["action"], h["field"]) for h in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()}
    assert {("CREATE", "campaign"), ("CREATE", "adgroup")} <= acts


def test_campaign_adgroup_delete_only_when_off():
    owner, ws, acc = _account("cmpd@a.com", "6207")
    s = store("6207")
    s["adgroups"]["grp-6207-pl2"]["userLock"] = True   # OFF 광고그룹
    s["campaigns"]["cmp-6207-sh"]["userLock"] = True   # OFF 캠페인(쇼핑)
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "adgroup", "grp-6207-pl1", "delete"),   # ON → 실패
        ch(acc, "adgroup", "grp-6207-pl2", "delete"),
        ch(acc, "campaign", "cmp-6207-sh", "delete"),
    ]}).json()
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner).json()["status"] == "PARTIAL"
    rows = {r["naver_id"]: r for a in c.get(f"/workspaces/{ws}/bulk-jobs/{job['id']}", headers=owner).json()["accounts"] for r in a["rows"]}
    assert rows["grp-6207-pl1"]["status"] == "FAILED" and "ON 상태" in rows["grp-6207-pl1"]["error"]
    assert "grp-6207-pl1" in s["adgroups"] and "grp-6207-pl2" not in s["adgroups"]
    assert not any(k["nccAdgroupId"] == "grp-6207-pl2" for k in s["keywords"].values())  # 안의 키워드도 삭제
    assert "cmp-6207-sh" not in s["campaigns"] and "grp-6207-sh1" not in s["adgroups"] and "ad-6207-sh1" not in s["ads"]
    acts = {(h["action"], h["field"]) for h in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()}
    assert {("DELETE", "campaign"), ("DELETE", "adgroup")} <= acts


def test_execute_runs_each_row_once():
    from app import bulk
    from app.db import SessionLocal
    from app.models import BulkJob, BulkJobRow, Membership
    from sqlalchemy import select

    owner, ws, acc = _account("once@a.com", "6208")
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "keyword", "grp-6208-pl1", "create", f"한번{i}", product="WEB_SITE") for i in range(3)]}).json()
    db = SessionLocal()
    try:
        # 다른 요청이 첫 행을 이미 실행 중인 상황: 이 요청은 그 행을 건너뛴다
        first = db.scalars(select(BulkJobRow).where(BulkJobRow.job_id == job["id"]).order_by(BulkJobRow.id)).first()
        first.status = "RUNNING"
        db.commit()
        m = db.scalar(select(Membership).where(Membership.workspace_id == ws))
        bulk.execute_job(db, m, db.get(BulkJob, job["id"]))
    finally:
        db.close()
    names = [k["keyword"] for k in store("6208")["keywords"].values()]
    assert "한번0" not in names and {"한번1", "한번2"} <= set(names)
    out = c.get(f"/workspaces/{ws}/bulk-jobs/{job['id']}", headers=owner).json()
    assert out["status"] == "PARTIAL"  # 끝까지 RUNNING인 행은 반영 여부를 몰라 실패로
    assert "연결이 끊겼습니다" in next(r for a in out["accounts"] for r in a["rows"] if r["after"] == "한번0")["error"]


def test_credential_key_rotation(monkeypatch):
    from cryptography.fernet import Fernet
    from sqlalchemy import select

    from app.bulk import rotate_credentials
    from app.db import SessionLocal
    from app.models import NaverApiCredential
    from app.security import _fernet, decrypt, encrypt

    monkeypatch.delenv("CRED_KEY", raising=False)
    old = encrypt("비밀")                                   # 예전 방식(APP_SECRET 열쇠)
    monkeypatch.setenv("CRED_KEY", Fernet.generate_key().decode())
    assert decrypt(old) == "비밀"                           # 옮기기 전에도 풀린다
    new = encrypt("새것")
    _fernet(os.environ["CRED_KEY"]).decrypt(new.encode())   # 새 값은 CRED_KEY 열쇠로

    owner = user("rot@a.com")
    ws = c.post("/workspaces", json={"name": "열쇠"}, headers=owner).json()["id"]
    db = SessionLocal()
    try:
        db.add(NaverApiCredential(workspace_id=ws, label="예전", api_key="k", secret_key_enc=old, is_mock=False))
        db.commit()
        rotate_credentials(db)
        rows = db.scalars(select(NaverApiCredential).where(NaverApiCredential.workspace_id == ws)).all()
    finally:
        db.close()
    assert _fernet(os.environ["CRED_KEY"]).decrypt(rows[0].secret_key_enc.encode()).decode() == "비밀"
    # 크론이 못 옮겨도 관리자가 자격증명 목록을 열면 그 조직 것은 옮겨지고, 어느 열쇠인지 보인다(키 값은 안 보임)
    db = SessionLocal()
    try:
        db.add(NaverApiCredential(workspace_id=ws, label="예전2", api_key="k", secret_key_enc=old, is_mock=False))
        db.commit()
    finally:
        db.close()
    listed = c.get(f"/workspaces/{ws}/credentials", headers=owner).json()
    assert [x["key"] for x in listed] == ["CRED_KEY", "CRED_KEY"] and "비밀" not in json.dumps(listed)
    monkeypatch.setenv("APP_SECRET", "다른 값")             # APP_SECRET이 바뀌어(새어) 있어도 CRED_KEY로 풀린다
    monkeypatch.setenv("APP_ENV", "prod")
    assert decrypt(rows[0].secret_key_enc) == "비밀"
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("APP_SECRET", raising=False)  # 로그인 토큰을 다시 쓰려고 원래 값으로
    # 어느 열쇠로도 안 풀리면(열쇠를 잃음) 목록이 멈추지 않고 UNREADABLE로 보인다
    monkeypatch.setenv("CRED_KEY", Fernet.generate_key().decode())
    r = c.get(f"/workspaces/{ws}/credentials", headers=owner)
    assert r.status_code == 200 and [x["key"] for x in r.json()] == ["UNREADABLE", "UNREADABLE"]
    # 예전 열쇠를 CRED_KEY_OLD로 같이 넣으면 계속 풀리고, 목록을 열면 새 열쇠로 옮겨진다
    old_key, new_key = os.environ["CRED_KEY"], Fernet.generate_key().decode()
    monkeypatch.setenv("CRED_KEY_OLD", old_key)
    monkeypatch.setenv("CRED_KEY", new_key)
    db = SessionLocal()
    try:
        db.add(NaverApiCredential(workspace_id=ws, label="열쇠교체", api_key="k", secret_key_enc=_fernet(old_key).encrypt(b"s3").decode(), is_mock=False))
        db.commit()
    finally:
        db.close()
    keys = [x["key"] for x in c.get(f"/workspaces/{ws}/credentials", headers=owner).json()]
    assert keys == ["UNREADABLE", "UNREADABLE", "CRED_KEY"]  # 옮긴 뒤라 CRED_KEY
    monkeypatch.delenv("CRED_KEY_OLD")
    assert [x["key"] for x in c.get(f"/workspaces/{ws}/credentials", headers=owner).json()][-1] == "CRED_KEY"


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
        ch(acc, "ad_extension", "ext-6106-pl1", "delete"),  # 확장소재 삭제는 대량 작업으로 안 함
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

    owner, ws, acc = _account("chunk@a.com", "8018")
    n = bulk.EXECUTE_CHUNK + 2
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "keyword", "grp-8018-pl1", "create", f"묶음{i}", product="WEB_SITE") for i in range(n)]}).json()
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
        status_code, text, url = 200, "<a i=nad-a001-01-2>x</a><a i=nad-a001-01-1></a><b nad-a001-01-2></b>", "u"

    got = {}
    monkeypatch.setattr("app.naver.httpx.get", lambda url, **kw: got.setdefault("url", url) and Page)
    assert RealNaverClient("k", "s", "1").serp_ads("원 피스", "MOBILE") == ["nad-a001-01-2", "nad-a001-01-1"]  # 노출 순서, 중복 제거
    assert got["url"].startswith("https://m.ad.search.naver.com/") and got["url"].endswith("%EC%9B%90%20%ED%94%BC%EC%8A%A4")
    Page.text = "<html><title>보안 확인</title>차단</html>"  # 광고 ID가 하나도 없으면 '내 광고 없음'이 아니라 실패
    with pytest.raises(NaverApiError, match="제목: 보안 확인"):
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

    monkeypatch.setenv("ROAS_AUTOMATION", "1")  # 정책상 꺼져 있는 기능의 동작 자체를 검증
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
    # Claude는 실행 못 함: 웹 작업 화면 링크만 받고, 사람이 웹(일반 로그인)에서 실행한다
    handoff, err = call("execute_job", workspace_id=ws, job_id=job["id"])
    assert not err and handoff["approval_required"] and handoff["url"].endswith(f"/jobs?id={job['id']}")
    assert store("8008")["keywords"][kws[0]["naver_id"]]["bidAmt"] == 300
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=owner).json()["status"] == "DONE"
    assert store("8008")["keywords"][kws[0]["naver_id"]]["bidAmt"] == 400

    def approve(res):  # 승인 요청 → 웹에서 승인(실행) → 결과
        assert res["approval_required"] and res["status"] == "PENDING", res
        return c.post(f"/workspaces/{ws}/approvals/{res['approval_id']}/approve", headers=owner).json()

    # 키워드별 성과(광고그룹 단위·ids), 소재·확장소재 등록(OFF로 생성), 작업 기록
    perf, err = call("get_entity_performance", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"])
    assert not err and len(perf["rows"]) == len(kws) and perf["rows"][0]["keyword"] and "avg_rank" in perf["rows"][0]
    assert call("get_entity_performance", workspace_id=ws, ad_account_id=acc, ids=[])[1]  # 대상 없음
    url = f"/workspaces/{ws}/performance/entities"
    assert c.post(url, headers=owner, json={"ad_account_id": acc, "ids": ["x"] * 501}).status_code == 400
    assert c.post(url, headers=owner, json={"ad_account_id": acc, "ids": ["x"], "since": "2026-01-01", "until": "2026-06-01"}).status_code == 400
    assert c.post(url, headers=owner, json={"ad_account_id": acc, "ids": ["x"]}).json()["rows"][0]["impressions"] >= 0
    ads_before = len(store("8008")["ads"])
    req, err = call("create_ad", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"], headlines=["여름 원피스", "무료배송"],
                    descriptions=["린넨 원피스 전 상품 무료배송"], pc_url="https://example.com")
    assert not err and len(store("8008")["ads"]) == ads_before  # 요청만, 아직 등록 안 됨
    done = approve(req)
    ad = done["result"]
    assert done["status"] == "DONE" and ad["status"] == "OFF" and ad["payload"]["headlines"] == ["여름 원피스", "무료배송"], done
    assert call("get_approval", workspace_id=ws, approval_id=req["approval_id"])[0]["status"] == "DONE"
    bad = approve(call("create_ad", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"], headlines=[], descriptions=["a"],
                       pc_url="https://example.com")[0])
    assert bad["status"] == "FAILED" and bad["result"]["error"]
    _, err = call("create_ad", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"], headlines=["가" * 16],
                  descriptions=["a"], pc_url="https://example.com")
    assert err and "16자" in str(_)  # 글자 수 초과는 승인 요청 전에 바로 거절
    ext = approve(call("create_ad_extension", workspace_id=ws, ad_account_id=acc, adgroup_id=groups[0]["naver_id"], ext_type="HEADLINE",
                       heading="오늘만 할인")[0])
    assert ext["status"] == "DONE" and ext["result"]["ext_type"] == "HEADLINE"
    logs, _ = call("list_audit_logs", workspace_id=ws, limit=20)  # 승인 요청·승인 기록도 함께 쌓인다
    assert logs[0]["user"] == "mcp@a.com" and {"ad", "ad_extension"} <= {x["entity_type"] for x in logs}

    # 자동입찰: 순위 확인 → 규칙 저장 → 지금 실행. 원피스1(300→400원)은 Mock 검색 화면 4위, 목표 1위라 20% 올림
    k = [{"ad_account_id": acc, "naver_id": kws[0]["naver_id"], "keyword": kws[0]["keyword"]}]
    assert call("check_ranks", workspace_id=ws, keywords=k)[0][0]["PC"] == 4
    assert approve(call("set_auto_bid", workspace_id=ws, keywords=k, device="PC", target_rank=11, max_bid=1000)[0])["status"] == "FAILED"  # PC는 10위까지
    assert approve(call("set_auto_bid", workspace_id=ws, keywords=k, device="PC", target_rank=1, max_bid=1000)[0])["result"] == {"ok": True}
    approve(call("run_auto_bids", workspace_id=ws, keywords=k)[0])
    assert store("8008")["keywords"][kws[0]["naver_id"]]["bidAmt"] == 480
    assert call("list_auto_bids", workspace_id=ws)[0][0]["last_result"] == "지금 4위 (목표 1위) · 400원 → 480원"
    approve(call("delete_auto_bid", workspace_id=ws, keywords=k)[0])
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

    monkeypatch.setenv("ROAS_AUTOMATION", "1")  # 정책상 꺼져 있는 기능의 동작 자체를 검증
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


def test_token_revocation():
    import time
    from app.security import _sign, sign_payload

    r = c.post("/auth/signup", json={"email": "revoke@a.com", "password": "password1", "name": "r"}).json()
    uid, t1 = r["id"], r["token"]
    t2 = c.post("/auth/login", json={"email": "revoke@a.com", "password": "password1"}).json()["token"]
    # Claude 출입증은 /mcp에서만 쓴다(일반 API는 거부 — test_mcp_token_scope)
    ok = lambda t: c.post("/mcp", headers={"Authorization": f"Bearer {t}"}, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 200  # noqa: E731
    refresh = lambda payload: c.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": sign_payload(payload, 60)})  # noqa: E731
    msg = f"{uid}.{int(time.time()) + 60}"
    old = f"{msg}.{_sign(msg)}"  # 버전 없는 예전 형식(배포 전 발급)
    assert ok(t1) and ok(t2) and ok(old)
    assert refresh({"t": "refresh", "u": uid}).status_code == 200  # 예전 Claude 연결도 그대로

    # 모든 기기 로그아웃: 웹 토큰·예전 토큰·Claude 갱신 토큰 모두 무효
    assert c.post("/auth/logout-all", headers={"Authorization": f"Bearer {t1}"}).json() == {"ok": True}
    assert not ok(t1) and not ok(t2) and not ok(old)
    assert refresh({"t": "refresh", "u": uid}).status_code == 400 and refresh({"t": "refresh", "u": uid, "v": 0}).status_code == 400
    t3 = c.post("/auth/login", json={"email": "revoke@a.com", "password": "password1"}).json()["token"]
    assert ok(t3) and refresh({"t": "refresh", "u": uid, "v": 1}).status_code == 200

    # 비밀번호 변경: 지금 기기는 새 토큰, 나머지는 끊김
    h = {"Authorization": f"Bearer {t3}"}
    assert c.post("/auth/password", headers=h, json={"current_password": "wrong", "new_password": "password2"}).status_code == 400
    assert c.post("/auth/password", headers=h, json={"current_password": "password1", "new_password": "short"}).status_code == 400
    t4 = c.post("/auth/password", headers=h, json={"current_password": "password1", "new_password": "password2"}).json()["token"]
    assert ok(t4) and not ok(t3) and refresh({"t": "refresh", "u": uid, "v": 1}).status_code == 400
    assert c.post("/auth/login", json={"email": "revoke@a.com", "password": "password2"}).status_code == 200


def test_google_login(monkeypatch):
    import base64
    from urllib.parse import parse_qs, urlsplit
    from app.security import read_token, sign_payload

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "gid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "gsecret")
    claims = {"aud": "gid", "email": "GLink@a.com", "email_verified": True, "name": "구글"}

    class Tok:
        def json(self):
            body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
            return {"id_token": f"h.{body}.s"}
    sent = {}
    monkeypatch.setattr("app.main.httpx.post", lambda url, data, **kw: sent.update(data) or Tok())

    def login(**params):
        r = c.get("/auth/google/start", params=params, follow_redirects=False)
        assert r.status_code == 302 and r.headers["location"].startswith("https://accounts.google.com/")
        state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
        return c.get("/auth/google/callback", params={"state": state, "code": "c1"}, follow_redirects=False)

    web = "http://localhost:3000/login"
    assert c.get("/auth/google/start", params={"redirect": "https://evil.com/login"}).status_code == 400  # 토큰을 남의 사이트로 안 보냄
    c.post("/auth/signup", json={"email": "glink@a.com", "password": "password1", "name": "기존"})
    r = login(redirect=web)
    assert sent["client_secret"] == "gsecret" and sent["redirect_uri"].endswith("/auth/google/callback")
    loc = r.headers["location"]
    assert loc.startswith(web + "#token=")
    uid = read_token(parse_qs(urlsplit(loc).fragment)["token"][0])[0]
    assert c.post("/auth/login", json={"email": "glink@a.com", "password": "password1"}).json()["id"] == uid  # 같은 이메일은 기존 계정

    claims.update(email="new-g@a.com")  # 처음 보는 이메일은 가입, 비밀번호 로그인은 안 됨
    loc = login(redirect=web).headers["location"]
    assert "#token=" in loc
    assert c.post("/auth/login", json={"email": "new-g@a.com", "password": "google$"}).status_code == 401
    gh = {"Authorization": f"Bearer {parse_qs(urlsplit(loc).fragment)['token'][0]}"}
    assert c.get("/auth/me", headers=gh).json()["has_password"] is False  # 화면이 비밀번호 변경을 숨긴다
    assert c.post("/auth/password", headers=gh, json={"current_password": "google$", "new_password": "password2"}).status_code == 400
    assert c.get("/auth/me", headers={"Authorization": f"Bearer {c.post('/auth/login', json={'email': 'glink@a.com', 'password': 'password1'}).json()['token']}"}).json()["has_password"]
    claims.update(email_verified=False)
    assert "#error=" in login(redirect=web).headers["location"]
    claims.update(email_verified=True)

    # 다른 브라우저(쿠키 없음)에서 콜백을 열면 거절 — 로그인 CSRF
    r = c.get("/auth/google/start", params={"redirect": web}, follow_redirects=False)
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    c.cookies.clear()
    assert c.get("/auth/google/callback", params={"state": state, "code": "c1"}).status_code == 400

    # Claude 연결 로그인 화면에서 Google로: 인가 코드가 Claude 주소로
    cb = "https://claude.ai/api/mcp/auth_callback"
    q = {"client_id": sign_payload({"t": "client", "r": [cb]}), "redirect_uri": cb, "code_challenge": "x", "code_challenge_method": "S256", "state": "s1"}
    assert "/auth/google/start?" in c.get("/oauth/authorize", params=q).text
    loc = login(**q).headers["location"]
    assert loc.startswith(cb + "?code=") and loc.endswith("&state=s1")

    monkeypatch.setenv("APP_ENV", "prod")  # 운영은 비밀번호 가입 막힘
    assert c.post("/auth/signup", json={"email": "x@a.com", "password": "password1", "name": "x"}).status_code == 403


def test_prod_rejects_mock_credential(monkeypatch):
    owner = user("mockprod@a.com")
    ws = c.post("/workspaces", json={"name": "대행사A"}, headers=owner).json()["id"]
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("APP_SECRET", "dev-only-secret")  # 운영은 APP_SECRET 필수, 위 토큰과 같은 값
    body = {"label": "m", "api_key": "k", "secret_key": "s"}
    assert c.post(f"/workspaces/{ws}/credentials", json=body, headers=owner).status_code == 403
    assert c.post(f"/workspaces/{ws}/credentials", json={**body, "is_mock": False}, headers=owner).status_code == 200


def test_mcp_token_security(monkeypatch):
    import base64
    import hashlib
    from datetime import timedelta
    from urllib.parse import parse_qs, urlparse
    from app import mcp

    web = user("mcpsec@a.com")
    cb = "http://localhost:3333/callback"
    client_id = c.post("/oauth/register", json={"redirect_uris": [cb]}).json()["client_id"]

    def connect():
        verifier = hashlib.sha256(os.urandom(8)).hexdigest()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        q = {"client_id": client_id, "redirect_uri": cb, "code_challenge": challenge, "code_challenge_method": "S256", "state": "s"}
        r = c.post("/oauth/authorize", data={**q, "email": "mcpsec@a.com", "password": "password1"}, follow_redirects=False)
        tok = {"grant_type": "authorization_code", "code": parse_qs(urlparse(r.headers["location"]).query)["code"][0],
               "redirect_uri": cb, "client_id": client_id, "code_verifier": verifier}
        t = c.post("/oauth/token", data=tok).json()
        assert c.post("/oauth/token", data=tok).status_code == 400  # 인가 코드는 한 번만
        return t
    refresh = lambda rt: c.post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": rt})  # noqa: E731
    ok = lambda t: c.post("/mcp", headers={"Authorization": f"Bearer {t}"}, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}).status_code == 200  # noqa: E731

    # 갱신 토큰 교체: 쓰면 새 갱신 토큰, 옛 것은 거절(60초 안 재사용은 재시도로 보고 거절만)
    t0 = connect()
    import time
    from app.security import read_payload
    assert t0["expires_in"] == 3600 and int(t0["access_token"].split(".")[3]) - time.time() <= 3600  # 출입증 1시간
    assert 6 * 86400 < read_payload(t0["refresh_token"], "refresh")["exp"] - time.time() <= 7 * 86400  # 갱신 토큰 7일
    t1 = refresh(t0["refresh_token"]).json()
    assert t1["refresh_token"] != t0["refresh_token"]
    assert refresh(t0["refresh_token"]).status_code == 400 and ok(t1["access_token"])
    # 늦게 재사용 = 탈취로 보고 Claude 연결 전부 끊기(웹 로그인은 그대로)
    monkeypatch.setattr(mcp, "REUSE_GRACE", timedelta(0))
    assert refresh(t0["refresh_token"]).status_code == 400
    assert not ok(t1["access_token"]) and refresh(t1["refresh_token"]).status_code == 400 and ok(web["Authorization"][7:])

    # Claude 연결만 끊기
    t2 = connect()
    assert ok(t2["access_token"])
    assert c.post("/auth/disconnect-claude", headers=web).json() == {"ok": True}
    assert not ok(t2["access_token"]) and refresh(t2["refresh_token"]).status_code == 400 and ok(web["Authorization"][7:])
    assert ok(connect()["access_token"])  # 다시 연결하면 된다


def test_delete_account():
    from sqlalchemy import text
    from app.db import engine

    owner = user("leaver@a.com")
    ws = c.post("/workspaces", json={"name": "혼자"}, headers=owner).json()["id"]
    cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=owner).json()["id"]
    acc = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": "7117", "name": "m"}, headers=owner).json()["id"]
    assert c.post(f"/workspaces/{ws}/ad-accounts/{acc}/sync", headers=owner).json()["status"] == "SUCCESS"
    assert c.put(f"/workspaces/{ws}/auto-bids", headers=owner, json={"keywords": [{"ad_account_id": acc, "naver_id": "nkw-1"}], "device": "PC",
                                                                    "target_rank": 3, "max_bid": 500}).status_code == 200
    staff = user("leaver-staff@a.com")
    c.post(f"/workspaces/{ws}/members", json={"email": "leaver-staff@a.com"}, headers=owner)
    # 남의 조직의 직원이기도 하다 → 그 조직은 남고 나만 빠진다
    boss = user("leaver-boss@a.com")
    other = c.post("/workspaces", json={"name": "남의 조직"}, headers=boss).json()["id"]
    c.post(f"/workspaces/{other}/members", json={"email": "leaver@a.com"}, headers=boss)

    assert c.post("/auth/delete-account", headers=owner, json={"password": "wrong"}).status_code == 400
    assert c.post("/auth/delete-account", headers=owner, json={"password": "password1"}).json() == {"ok": True}
    assert c.get("/workspaces", headers=owner).status_code == 401  # 토큰 무효
    assert c.get("/workspaces", headers=staff).json() == []  # 혼자 소유한 조직은 직원 것까지 사라짐
    assert [m["email"] for m in c.get(f"/workspaces/{other}/members", headers=boss).json()] == ["leaver-boss@a.com"]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM ad_accounts WHERE id = :a"), {"a": acc}).scalar() == 0
        assert conn.execute(text("PRAGMA foreign_key_check")).fetchall() == []  # D1은 외래 키를 검사한다
    assert c.post("/auth/login", json={"email": "leaver@a.com", "password": "password1"}).status_code == 401
    assert c.post("/auth/signup", json={"email": "leaver@a.com", "password": "password1", "name": "다시"}).status_code == 200


def test_audit_fixes(monkeypatch):
    # 이메일은 대소문자 구분 없이: 로그인·직원 추가
    h = user("CaseMix@a.com")
    assert c.post("/auth/login", json={"email": "casemix@A.com", "password": "password1"}).status_code == 200
    assert c.post("/auth/signup", json={"email": "casemix@a.com", "password": "password1", "name": "x"}).status_code == 409
    boss = user("case-boss@a.com")
    ws = c.post("/workspaces", json={"name": "대소문자"}, headers=boss).json()["id"]
    assert c.post(f"/workspaces/{ws}/members", json={"email": "CASEMIX@a.com"}, headers=boss).status_code == 200
    assert {x["email"] for x in c.get(f"/workspaces/{ws}/members", headers=h).json()} == {"case-boss@a.com", "casemix@a.com"}

    # 대량 작업 행 수 상한
    from app import bulk
    monkeypatch.setattr(bulk, "MAX_JOB_ROWS", 2)
    ch = {"entity_type": "campaign", "naver_id": "cmp-1", "field": "status", "value": "OFF"}
    r = c.post(f"/workspaces/{ws}/bulk-jobs", json={"changes": [ch] * 3}, headers=boss)
    assert r.status_code == 400 and "2행까지" in r.json()["detail"]

    # 계정 없는 기록(예약 등)도 이력에 보인다
    from app.db import SessionLocal
    from app.models import AuditLog
    db = SessionLocal()
    db.add(AuditLog(workspace_id=ws, user_id=1, action="JOB_SCHEDULE_FAIL", after="테스트"))
    db.commit()
    db.close()
    assert any(x["action"] == "JOB_SCHEDULE_FAIL" for x in c.get(f"/workspaces/{ws}/audit-logs", headers=boss).json())


def test_mock_cannot_squat_customer_id():
    # Mock 연결은 실제 광고주 번호를 차지하지 않는다(조직별 번호) → 진짜 계정 연결이 막히지 않는다
    from app.db import SessionLocal
    from app.models import AdAccount
    codes = []
    for name in ("squat-a@a.com", "squat-b@a.com"):
        h = user(name)
        ws = c.post("/workspaces", json={"name": name}, headers=h).json()["id"]
        cred = c.post(f"/workspaces/{ws}/credentials", json={"label": "m", "api_key": "k", "secret_key": "s"}, headers=h).json()["id"]
        r = c.post(f"/workspaces/{ws}/ad-accounts", json={"credential_id": cred, "customer_id": "4285993", "name": "x"}, headers=h)
        codes.append(r.status_code)
        if r.status_code == 200:
            assert r.json()["customer_id"] == f"mock{ws}-4285993"
            assert c.get(f"/workspaces/{ws}/ad-accounts", headers=h).json()[0]["customer_id"] == "4285993"  # 화면엔 넣은 번호만
            assert c.post(f"/workspaces/{ws}/ad-accounts/{r.json()['id']}/sync", headers=h).json()["status"] == "SUCCESS"  # Mock 동작 그대로
    assert codes == [200, 409]  # 다른 조직은 같은 Mock 번호를 못 씀(가짜 캠페인 ID가 겹침)
    db = SessionLocal()
    assert db.query(AdAccount).filter(AdAccount.customer_id == "4285993").count() == 0
    db.close()


def test_sync_in_chunks(monkeypatch):
    # 캠페인이 많으면 나눠 받는다(무료 플랜 요청당 호출 한도): Mock 캠페인 2개를 1개씩
    from app import sync
    owner, ws, acc = _account("sync-chunk@a.com", "6501")
    monkeypatch.setattr(sync, "SYNC_CHUNK", 1)
    url = f"/workspaces/{ws}/ad-accounts/{acc}/sync"
    r = c.post(url, headers=owner).json()
    assert r == {"status": "RUNNING", "error": None, "next_offset": 1}
    assert c.post(f"{url}?offset=1", headers=owner).json()["status"] == "SUCCESS"
    perf = c.get(f"/workspaces/{ws}/performance/accounts", headers=owner).json()[0]
    assert perf["WEB_SITE"]["cost"] > 0 and perf["SHOPPING"]["cost"] > 0  # 두 캠페인 모두 받음


# ---------- 보안 점검(10/29): 조직 간 격리·권한·정책 회귀 테스트 ----------
def _mcp_headers(h):
    """웹 로그인 헤더의 사용자로 Claude 연결 출입증을 만든다(OAuth 과정은 test_mcp_oauth_and_tools에서 따로 검증)."""
    from sqlalchemy import select

    from app.db import SessionLocal
    from app.models import User
    from app.security import make_token

    me = c.get("/auth/me", headers=h).json()
    db = SessionLocal()
    try:
        u = db.scalar(select(User).where(User.email == me["email"]))
        return {"Authorization": f"Bearer {make_token(u.id, u.token_version, u.mcp_version, 3600)}"}
    finally:
        db.close()


def _mcp_call(h, name, **args):
    r = c.post("/mcp", headers=h, json={"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": name, "arguments": args}})
    res = r.json()["result"]
    return json.loads(res["content"][0]["text"]), res["isError"]


def test_tenant_isolation_api():
    a, ws_a, acc_a = _account("iso-a@a.com", "9101")
    b, ws_b, acc_b = _account("iso-b@b.com", "9102")
    job_a = c.post(f"/workspaces/{ws_a}/bulk-jobs", headers=a, json={"changes": [
        ch(acc_a, "keyword", "kwd-9101-11", "bid_amt", "500", before="300", product="WEB_SITE")]}).json()["id"]
    cred_a = c.get(f"/workspaces/{ws_a}/credentials", headers=a).json()[0]["id"]

    # ① B가 A의 조직 ID를 직접 넣으면 전부 403
    for path in ("members", "ad-accounts", "credentials", "bulk-jobs", f"bulk-jobs/{job_a}", "audit-logs", "dashboard",
                 "auto-bids", "account-goals", "performance/accounts", f"ad-accounts/{acc_a}/naver/campaigns",
                 f"ad-accounts/{acc_a}/naver/channels"):
        assert c.get(f"/workspaces/{ws_a}/{path}", headers=b).status_code == 403, path
    assert c.post(f"/workspaces/{ws_a}/bulk-jobs/{job_a}/execute", headers=b).status_code == 403
    assert c.put(f"/workspaces/{ws_a}/credentials/{cred_a}", headers=b, json={"api_key": "x", "secret_key": "y"}).status_code == 403

    # ② B가 자기 조직 ID에 A의 계정·작업·자격증명 ID를 섞으면 막힌다
    base = f"/workspaces/{ws_b}"
    for path in (f"ad-accounts/{acc_a}/naver/campaigns", f"ad-accounts/{acc_a}/naver/channels",
                 f"ad-accounts/{acc_a}/adgroups/grp-9101-pl1/negative-keywords", f"keyword-tool?account_id={acc_a}&hint=x",
                 f"performance/accounts?account_ids={acc_a}", f"performance/daily?since=2026-10-01&until=2026-10-07&account_ids={acc_a}",
                 f"audit-logs?account_id={acc_a}"):
        assert c.get(f"{base}/{path}", headers=b).status_code == 403, path
    assert c.post(f"{base}/ad-accounts/{acc_a}/sync", headers=b).status_code == 403
    assert c.post(f"{base}/ad-accounts/{acc_a}/master-reports?item=Keyword", headers=b).status_code == 403
    assert c.post(f"{base}/performance/entities", headers=b, json={"ad_account_id": acc_a, "ids": ["kwd-9101-11"]}).status_code == 403
    assert c.get(f"{base}/bulk-jobs/{job_a}", headers=b).status_code == 404
    for path in (f"bulk-jobs/{job_a}/execute", f"bulk-jobs/{job_a}/retry-failed"):
        assert c.post(f"{base}/{path}", headers=b).status_code == 404, path
    assert c.post(f"{base}/bulk-jobs/{job_a}/schedule", headers=b, json={"scheduled_at": None}).status_code == 404
    assert c.put(f"{base}/credentials/{cred_a}", headers=b, json={"api_key": "x", "secret_key": "y"}).status_code == 404
    assert c.delete(f"{base}/credentials/{cred_a}", headers=b).status_code == 404
    assert c.post(f"{base}/ad-accounts", headers=b, json={"credential_id": cred_a, "customer_id": "9101", "name": "x"}).status_code == 404
    # 대량 작업에 A의 계정을 넣으면 그 행은 실행 안 되는 행(계정 이름도 안 알려 줌), A의 광고는 그대로
    job = c.post(f"{base}/bulk-jobs", headers=b, json={"changes": [
        ch(acc_a, "keyword", "kwd-9101-11", "bid_amt", "900", product="WEB_SITE"),
        ch(acc_a, "campaign", "cmp-9101-pl", "delete")]}).json()
    assert {r["status"] for x in job["accounts"] for r in x["rows"]} == {"INVALID"} and all(x["name"] is None for x in job["accounts"])
    kw = {"keywords": [{"ad_account_id": acc_a, "naver_id": "kwd-9101-11"}], "device": "PC", "target_rank": 1, "max_bid": 5000}
    assert c.put(f"{base}/auto-bids", headers=b, json=kw).status_code == 403
    assert c.post(f"{base}/auto-bids/delete", headers=b, json={"keywords": kw["keywords"]}).status_code == 403
    assert c.post(f"{base}/ad-extensions", headers=b, json={"ad_account_id": acc_a, "adgroup_naver_id": "grp-9101-pl1",
                                                            "ext_type": "HEADLINE", "heading": "침범"}).status_code == 403
    assert c.put(f"{base}/account-goals", headers=b, json={"ad_account_id": acc_a, "roas_target": 300, "max_bid": 1000}).status_code == 403
    assert store("9101")["keywords"]["kwd-9101-11"]["bidAmt"] == 300


def test_tenant_isolation_mcp():
    a, ws_a, acc_a = _account("iso-ma@a.com", "9111")
    b, ws_b, acc_b = _account("iso-mb@b.com", "9112")
    mb = _mcp_headers(b)
    accounts, _ = _mcp_call(mb, "list_ad_accounts")
    assert [w["id"] for w in accounts] == [ws_b]
    job_a = c.post(f"/workspaces/{ws_a}/bulk-jobs", headers=a, json={"changes": [
        ch(acc_a, "keyword", "kwd-9111-11", "bid_amt", "500", before="300", product="WEB_SITE")]}).json()["id"]
    # A의 조직 ID로
    for name, args in (("list_campaigns", {"ad_account_id": acc_a}), ("get_performance", {}), ("list_audit_logs", {}),
                       ("execute_job", {"job_id": job_a}), ("list_auto_bids", {})):
        data, err = _mcp_call(mb, name, workspace_id=ws_a, **args)
        assert err and "접근 권한" in data["error"], name
    # 자기 조직 ID + A의 계정·작업
    ads_before = len(store("9111")["ads"])
    for name, args in (("list_campaigns", {"ad_account_id": acc_a}), ("list_channels", {"ad_account_id": acc_a}),
                       ("list_keywords", {"ad_account_id": acc_a, "adgroup_id": "grp-9111-pl1"}),
                       ("create_ad_extension", {"ad_account_id": acc_a, "adgroup_id": "grp-9111-pl1", "ext_type": "HEADLINE", "heading": "x"}),
                       ("create_ad", {"ad_account_id": acc_a, "adgroup_id": "grp-9111-pl1", "headlines": ["x"], "descriptions": ["y"],
                                      "pc_url": "https://a.com"}),
                       ("execute_job", {"job_id": job_a}), ("schedule_job", {"job_id": job_a, "scheduled_at": None}),
                       ("set_auto_bid", {"keywords": [{"ad_account_id": acc_a, "naver_id": "kwd-9111-11"}], "device": "PC",
                                         "target_rank": 1, "max_bid": 500})):
        _, err = _mcp_call(mb, name, workspace_id=ws_b, **args)
        assert err, name
    prev, _ = _mcp_call(mb, "preview_changes", workspace_id=ws_b, changes=[ch(acc_a, "keyword", "kwd-9111-11", "bid_amt", "900")])
    assert prev["counts"]["VALID"] == 0
    assert store("9111")["keywords"]["kwd-9111-11"]["bidAmt"] == 300 and len(store("9111")["ads"]) == ads_before


def test_role_permissions():
    owner, ws, acc1 = _account("role-o@a.com", "9141")
    cred = c.get(f"/workspaces/{ws}/credentials", headers=owner).json()[0]["id"]
    acc2 = c.post(f"/workspaces/{ws}/ad-accounts", headers=owner, json={"credential_id": cred, "customer_id": "9142", "name": "y"}).json()["id"]
    staff = user("role-s@a.com")
    mid = c.post(f"/workspaces/{ws}/members", headers=owner, json={"email": "role-s@a.com"}).json()["membership_id"]
    c.put(f"/workspaces/{ws}/members/{mid}/access", headers=owner, json={"ad_account_id": acc1, "level": "EDIT"})
    c.put(f"/workspaces/{ws}/members/{mid}/access", headers=owner, json={"ad_account_id": acc2, "level": "VIEW"})
    # 직원(MEMBER)은 관리 기능 불가, OWNER 역할은 줄 수 없다
    assert c.get(f"/workspaces/{ws}/credentials", headers=staff).status_code == 403
    assert c.post(f"/workspaces/{ws}/members", headers=staff, json={"email": "role-o@a.com"}).status_code == 403
    assert c.put(f"/workspaces/{ws}/credentials/{cred}", headers=staff, json={"api_key": "k", "secret_key": "s"}).status_code == 403
    assert c.delete(f"/workspaces/{ws}/ad-accounts/{acc1}", headers=staff).status_code == 403
    assert c.post(f"/workspaces/{ws}/members", headers=owner, json={"email": "role-s@a.com", "role": "OWNER"}).status_code == 422
    # 보기 권한(acc2)으로는 조회만: 변경 행은 미리보기에서 걸러지고 자동입찰·확장소재·소재 등록도 403
    assert c.get(f"/workspaces/{ws}/ad-accounts/{acc2}/naver/campaigns", headers=staff).status_code == 200
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=staff, json={"changes": [
        ch(acc2, "campaign", "cmp-9142-pl", "status", "OFF", before="ON", product="WEB_SITE"),
        ch(acc1, "campaign", "cmp-9141-pl", "status", "OFF", before="ON", product="WEB_SITE")]}).json()
    assert sorted(r["status"] for x in job["accounts"] for r in x["rows"]) == ["INVALID", "VALID"]
    kw = {"keywords": [{"ad_account_id": acc2, "naver_id": "kwd-9142-11"}], "device": "PC", "target_rank": 1, "max_bid": 500}
    assert c.put(f"/workspaces/{ws}/auto-bids", headers=staff, json=kw).status_code == 403
    assert c.post(f"/workspaces/{ws}/ad-extensions", headers=staff, json={"ad_account_id": acc2, "adgroup_naver_id": "grp-9142-pl1",
                                                                         "ext_type": "HEADLINE", "heading": "x"}).status_code == 403
    _, err = _mcp_call(_mcp_headers(staff), "create_ad", workspace_id=ws, ad_account_id=acc2, adgroup_id="grp-9142-pl1",
                       headlines=["x"], descriptions=["y"], pc_url="https://a.com")
    assert err
    # 미리보기 뒤 수정 권한이 빠지면(acc1 EDIT → VIEW) 실행이 거부되고 광고는 그대로
    c.put(f"/workspaces/{ws}/members/{mid}/access", headers=owner, json={"ad_account_id": acc1, "level": "VIEW"})
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/execute", headers=staff).status_code == 403
    assert store("9141")["campaigns"]["cmp-9141-pl"]["userLock"] is False


def test_roas_automation_blocked_by_policy(monkeypatch):
    from app import bulk
    from app.db import SessionLocal

    monkeypatch.delenv("ROAS_AUTOMATION", raising=False)
    owner, ws, acc = _account("roas-off@a.com", "9121")
    url = f"/workspaces/{ws}/account-goals"
    assert c.put(url, headers=owner, json={"ad_account_id": acc, "roas_target": 300, "max_bid": 1000}).json() == {"ok": True}
    assert c.post(f"{url}/{acc}/run", headers=owner).status_code == 403
    before = {k: (v["bidAmt"], v["userLock"]) for k, v in store("9121")["keywords"].items()}
    db = SessionLocal()
    try:
        bulk.run_all_goals(db)  # 크론도 아무것도 안 한다
    finally:
        db.close()
    assert {k: (v["bidAmt"], v["userLock"]) for k, v in store("9121")["keywords"].items()} == before
    assert c.get(url, headers=owner).json()[0]["last_run_at"] is None


def test_credential_replace_delete():
    owner, ws, acc = _account("cred-rd@a.com", "9131")
    cred = c.get(f"/workspaces/{ws}/credentials", headers=owner).json()[0]["id"]
    r = c.put(f"/workspaces/{ws}/credentials/{cred}", headers=owner, json={"api_key": "new-k", "secret_key": "new-s"})
    assert r.status_code == 200 and "new-" not in r.text  # 키는 응답에 없다
    assert c.delete(f"/workspaces/{ws}/credentials/{cred}", headers=owner).status_code == 409  # 연결된 계정이 있으면
    c.delete(f"/workspaces/{ws}/ad-accounts/{acc}", headers=owner)
    assert c.delete(f"/workspaces/{ws}/credentials/{cred}", headers=owner).json() == {"ok": True}
    assert c.get(f"/workspaces/{ws}/credentials", headers=owner).json() == []
    logs = c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()
    assert {"CREDENTIAL_REPLACE", "CREDENTIAL_DELETE"} <= {h["action"] for h in logs} and "new-" not in json.dumps(logs)


def test_seo_ssrf_bypasses(monkeypatch):
    import httpx
    from app import seo

    for bad in ("http://2130706433/", "http://127.1/", "http://0x7f.0.0.1/", "http://localhost./", "http://a.localhost/",
                "http://printer.local/", "http://metadata.google.internal/", "http://169.254.169.254/latest/meta-data/",
                "http://[::ffff:127.0.0.1]/", "http://10.0.0.1/"):
        try:
            seo.check_url(bad)
            raise AssertionError(bad)
        except seo.SeoError:
            pass
    # 공개 주소가 내부 주소로 리다이렉트하면 그 주소는 요청하지 않는다
    calls = []

    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})
    seo = _mock_web(monkeypatch, handler)
    try:
        seo.fetch("https://example.com/")
        raise AssertionError("리다이렉트 차단 안 됨")
    except seo.SeoError:
        pass
    assert calls == ["https://example.com/"]


def test_security_headers():
    r = c.get("/oauth/authorize")
    assert r.headers["x-frame-options"] == "DENY" and "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert c.get("/auth/me").headers["x-content-type-options"] == "nosniff"


def test_oauth_code_concurrent_use():
    """같은 인가 코드를 동시에 내도(사용 기록 확인과 기록 사이에 끼어듦) 사용 기록은 하나만 남아 출입증은 한 번만 나간다."""
    from datetime import timedelta

    from sqlalchemy.exc import IntegrityError

    from app.db import SessionLocal
    from app.models import OAuthUsed, now

    key = "k" * 64
    db1, db2 = SessionLocal(), SessionLocal()
    try:
        assert db1.get(OAuthUsed, key) is None and db2.get(OAuthUsed, key) is None  # 둘 다 "처음 쓰는 코드"로 봄
        db1.add(OAuthUsed(key=key, used_at=now(), expires_at=now() + timedelta(minutes=5)))
        db1.commit()
        db2.add(OAuthUsed(key=key, used_at=now(), expires_at=now() + timedelta(minutes=5)))
        try:
            db2.commit()
            raise AssertionError("두 번째 기록이 성공함")
        except IntegrityError:
            db2.rollback()
    finally:
        db1.close()
        db2.close()


# ---------- 2차 보안 점검(10/29): 직원별 격리·토큰 범위·동시 요청·SSRF ----------
def _staff_org(prefix, c1, c2):
    """OWNER, ADMIN, 직원 A(광고주1 VIEW), 직원 B(광고주2 EDIT)인 조직."""
    owner, ws, acc1 = _account(f"{prefix}-o@a.com", c1)
    cred = c.get(f"/workspaces/{ws}/credentials", headers=owner).json()[0]["id"]
    acc2 = c.post(f"/workspaces/{ws}/ad-accounts", headers=owner, json={"credential_id": cred, "customer_id": c2, "name": "광고주2"}).json()["id"]
    c.post(f"/workspaces/{ws}/ad-accounts/{acc2}/sync", headers=owner)
    hs, mids = {}, {}
    for who, role in (("adm", "ADMIN"), ("sa", "MEMBER"), ("sb", "MEMBER")):
        hs[who] = user(f"{prefix}-{who}@a.com")
        mids[who] = c.post(f"/workspaces/{ws}/members", headers=owner, json={"email": f"{prefix}-{who}@a.com", "role": role}).json()["membership_id"]
    c.put(f"/workspaces/{ws}/members/{mids['sa']}/access", headers=owner, json={"ad_account_id": acc1, "level": "VIEW"})
    c.put(f"/workspaces/{ws}/members/{mids['sb']}/access", headers=owner, json={"ad_account_id": acc2, "level": "EDIT"})
    return owner, ws, acc1, acc2, hs, mids


def test_staff_job_isolation():
    owner, ws, acc1, acc2, hs, mids = _staff_org("stf", "9201", "9202")
    a, b, adm = hs["sa"], hs["sb"], hs["adm"]
    url = f"/workspaces/{ws}/bulk-jobs"
    job2 = c.post(url, headers=owner, json={"changes": [ch(acc2, "keyword", "kwd-9202-11", "bid_amt", "350", before="300", product="WEB_SITE")]}).json()["id"]
    c.post(f"{url}/{job2}/execute", headers=owner)  # 실행된 작업 = 대시보드·이력에 나온다
    mixed = c.post(url, headers=owner, json={"changes": [
        ch(acc1, "keyword", "kwd-9201-11", "bid_amt", "310", before="300", product="WEB_SITE"),
        ch(acc2, "keyword", "kwd-9202-12", "bid_amt", "610", before="600", product="WEB_SITE")]}).json()["id"]
    job1 = c.post(url, headers=owner, json={"changes": [ch(acc1, "keyword", "kwd-9201-12", "bid_amt", "620", before="600", product="WEB_SITE")]}).json()["id"]
    jobb = c.post(url, headers=b, json={"changes": [ch(acc2, "keyword", "kwd-9202-13", "bid_amt", "930", before="900", product="WEB_SITE")]}).json()["id"]

    # 직원 A(광고주1 보기): 광고주2가 들어간 작업은 목록·상세·대시보드·이력 어디에도 없다
    ids = lambda h: {j["id"] for j in c.get(url, headers=h).json()}  # noqa: E731
    assert ids(a) == {job1}
    for j in (job2, mixed, jobb):
        assert c.get(f"{url}/{j}", headers=a).status_code == 404
        assert c.post(f"{url}/{j}/execute", headers=a).status_code == 404
        assert c.post(f"{url}/{j}/retry-failed", headers=a).status_code == 404
        assert c.post(f"{url}/{j}/schedule", headers=a, json={"scheduled_at": None}).status_code == 404
    dash = c.get(f"/workspaces/{ws}/dashboard", headers=a).json()
    assert job2 not in {j["id"] for j in dash["recent_jobs"]} and job2 not in dash["failed_jobs"]
    logs = c.get(f"/workspaces/{ws}/audit-logs", headers=a).json()
    a_id = c.get("/auth/me", headers=a).json()["id"]
    assert all(x["ad_account_id"] in (acc1, None) for x in logs) and all(x["user_id"] == a_id for x in logs if x["ad_account_id"] is None)
    assert c.get(f"/workspaces/{ws}/audit-logs?account_id={acc2}", headers=a).status_code == 403
    # 보기 권한 작업은 볼 수 있지만 실행·예약·재실행은 403
    assert c.get(f"{url}/{job1}", headers=a).status_code == 200
    assert c.post(f"{url}/{job1}/execute", headers=a).status_code == 403
    assert store("9201")["keywords"]["kwd-9201-12"]["bidAmt"] == 600

    # 직원 B(광고주2 수정): 자기 계정 작업은 정상 실행, 광고주1이 섞인 작업은 안 보임
    assert ids(b) == {job2, jobb}
    assert c.get(f"{url}/{mixed}", headers=b).status_code == 404
    assert c.post(f"{url}/{jobb}/execute", headers=b).json()["status"] == "DONE"
    assert store("9202")["keywords"]["kwd-9202-13"]["bidAmt"] == 930

    # OWNER·ADMIN은 전부 보고 관리
    assert ids(owner) >= {job1, job2, mixed, jobb} and ids(adm) >= {job1, job2, mixed, jobb}
    assert c.post(f"{url}/{mixed}/execute", headers=adm).json()["status"] == "DONE"

    # 권한 회수 → 기존 작업도 즉시 안 보임
    c.put(f"/workspaces/{ws}/members/{mids['sb']}/access", headers=owner, json={"ad_account_id": acc2, "level": None})
    assert ids(b) == set() and c.get(f"{url}/{jobb}", headers=b).status_code == 404

    # MCP도 같은 정책
    ma = _mcp_headers(a)
    for name, args in (("execute_job", {"job_id": job2}), ("schedule_job", {"job_id": job2, "scheduled_at": None})):
        _, err = _mcp_call(ma, name, workspace_id=ws, **args)
        assert err, name
    handoff, err = _mcp_call(ma, "execute_job", workspace_id=ws, job_id=job1)
    assert not err and handoff["approval_required"] and store("9201")["keywords"]["kwd-9201-12"]["bidAmt"] == 600
    mlogs, _ = _mcp_call(ma, "list_audit_logs", workspace_id=ws)
    assert all(x["ad_account_id"] in (acc1, None) for x in mlogs)


def test_bulk_duplicate_key_per_account():
    owner, ws, acc1 = _account("dupk@a.com", "9211")
    cred = c.get(f"/workspaces/{ws}/credentials", headers=owner).json()[0]["id"]
    acc2 = c.post(f"/workspaces/{ws}/ad-accounts", headers=owner, json={"credential_id": cred, "customer_id": "9212", "name": "y"}).json()["id"]
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc1, "campaign", "WEB_SITE", "create", "브랜드|10000", product="WEB_SITE"),
        ch(acc2, "campaign", "WEB_SITE", "create", "브랜드|10000", product="WEB_SITE"),   # 다른 계정이면 중복 아님
        ch(acc2, "campaign", "WEB_SITE", "create", "브랜드|20000", product="WEB_SITE")]}).json()  # 같은 계정·이름은 중복
    assert [r["status"] for x in job["accounts"] for r in x["rows"]] == ["VALID", "VALID", "INVALID"]


def test_retry_skips_cut_off_rows():
    from sqlalchemy import select

    from app import bulk
    from app.db import SessionLocal
    from app.models import BulkJob, BulkJobRow

    owner, ws, acc = _account("cut@a.com", "9221")
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "keyword", "grp-9221-pl1", "create", "끊김키워드", product="WEB_SITE")]}).json()
    db = SessionLocal()
    try:  # 실행 중 연결이 끊겨 실패로 남은 상황
        row = db.scalars(select(BulkJobRow).where(BulkJobRow.job_id == job["id"])).one()
        row.status, row.error = "FAILED", bulk.CUT_OFF
        db.get(BulkJob, job["id"]).status = "FAILED"
        db.commit()
    finally:
        db.close()
    retry = c.post(f"/workspaces/{ws}/bulk-jobs/{job['id']}/retry-failed", headers=owner).json()
    assert retry["counts"]["VALID"] == 0 and retry["counts"]["INVALID"] == 1  # 두 번 등록되지 않게


def test_mcp_token_scope():
    owner, ws, acc = _account("scope@a.com", "9231")
    m = _mcp_headers(owner)
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "keyword", "kwd-9231-11", "bid_amt", "350", before="300", product="WEB_SITE")]}).json()["id"]
    # Claude 출입증으로 일반 API(조회·실행·예약)를 직접 부를 수 없다
    assert c.get("/workspaces", headers=m).status_code == 401
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job}/execute", headers=m).status_code == 401
    assert c.post(f"/workspaces/{ws}/bulk-jobs/{job}/schedule", headers=m, json={"scheduled_at": None}).status_code == 401
    assert store("9231")["keywords"]["kwd-9231-11"]["bidAmt"] == 300
    accounts, err = _mcp_call(m, "list_ad_accounts")
    assert not err and accounts[0]["id"] == ws


def test_oauth_refresh_concurrent(monkeypatch):
    """같은 갱신 토큰을 실제로 동시에(스레드 2개) 내면 새 토큰은 한 번만 나간다."""
    import threading

    from fastapi.testclient import TestClient

    from app import mcp
    from app.security import sign_payload

    h = user("conc@a.com")
    uid = c.get("/auth/me", headers=h).json()["id"]
    rt = sign_payload({"t": "refresh", "u": uid, "v": 0, "m": 0, "j": "conc"}, 3600)
    barrier = threading.Barrier(2, timeout=10)
    orig = mcp._use_once

    def both_checked(db, token, exp):
        # 사용 기록 조회 직후 두 요청을 맞춘다: 둘 다 "처음 쓰는 토큰"으로 본 뒤 기록하러 간다(진짜 경합)
        real_get = db.get

        def get_then_wait(*a, **k):
            r = real_get(*a, **k)
            barrier.wait()
            return r
        db.get = get_then_wait
        try:
            return orig(db, token, exp)
        finally:
            db.get = real_get
    monkeypatch.setattr(mcp, "_use_once", both_checked)
    codes = []

    def go():
        codes.append(TestClient(app).post("/oauth/token", data={"grant_type": "refresh_token", "refresh_token": rt}).status_code)
    ts = [threading.Thread(target=go) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(codes) == [200, 400]


def test_health_reports_policy(monkeypatch):
    monkeypatch.delenv("ROAS_AUTOMATION", raising=False)
    monkeypatch.setenv("CRED_KEY", "test-only")
    out = c.get("/health").json()
    assert out == {"ok": True, "roas_automation": False, "cred_key_loaded": True} and "test-only" not in json.dumps(out)


def _mock_web(monkeypatch, handler):
    """seo의 실제 요청 코드(_fetch_once 스트리밍)를 그대로 쓰되 네트워크 대신 handler가 응답한다."""
    import httpx

    from app import seo

    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(seo.httpx, "stream", lambda method, url, **kw: client.stream(method, url, headers=kw.get("headers")))
    monkeypatch.setattr(seo, "_check_dns", lambda host: None)  # 공개 도메인 DNS는 테스트에서 조회하지 않음
    return seo


def test_seo_ssrf_more(monkeypatch):
    import socket

    import httpx

    from app import seo

    for bad in ("http://user:pw@example.com/", "http://example.com@10.0.0.1/", "http://example.com:8080/", "http://example.com:22/",
                "http://[fe80::1]/", "http://[::ffff:10.0.0.1]/", "http://224.0.0.1/", "http://0.0.0.0/", "http://100.64.0.1/"):
        try:
            seo.check_url(bad)
            raise AssertionError(bad)
        except seo.SeoError:
            pass
    # 도메인이 내부 IP를 가리키면(로컬·VM 실행) 거부
    monkeypatch.setattr(seo, "ON_WORKERS", False)
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port: [(0, 0, 0, "", ("93.184.216.34", 0)), (0, 0, 0, "", ("10.1.2.3", 0))])
    try:
        seo.check_url("https://rebind.example.com/")
        raise AssertionError("내부 IP로 해석되는 도메인 통과")
    except seo.SeoError:
        pass

    seen = []

    def handler(req):
        seen.append(str(req.url))
        if req.url.path == "/loop":
            return httpx.Response(302, headers={"location": "/loop"})
        if req.url.path == "/internal":
            return httpx.Response(301, headers={"location": "http://169.254.169.254/latest/"})
        if req.url.path == "/big":
            return httpx.Response(200, content=iter([b"x" * 1_000_000] * 10))  # 길이 헤더 없이 10MB
        if req.url.path == "/biglen":
            return httpx.Response(200, headers={"content-length": "999999999"}, content=b"")
        return httpx.Response(200, text="<html><title>ok</title></html>")
    seo = _mock_web(monkeypatch, handler)
    for path, msg in (("/loop", "리다이렉트"), ("/internal", "내부 주소"), ("/big", "너무 큽니다"), ("/biglen", "너무 큽니다")):
        seen.clear()
        try:
            seo.fetch(f"https://example.com{path}")
            raise AssertionError(path)
        except seo.SeoError as e:
            assert msg in str(e), (path, e)
        assert not any("169.254" in u for u in seen)
    out = seo.fetch("https://example.com/")
    assert out["status"] == 200 and "<title>ok" in out["html"]


# ---------- MCP 광고 변경 승인(10/29) ----------
def _ext_request(mh, ws, acc, cid, heading="승인테스트"):
    res, err = _mcp_call(mh, "create_ad_extension", workspace_id=ws, ad_account_id=acc, adgroup_id=f"grp-{cid}-pl1",
                         ext_type="HEADLINE", heading=heading)
    assert not err and res["approval_required"] and res["status"] == "PENDING", res
    return res["approval_id"]


def _exts(cid):
    return [e for e in store(cid)["ad-extensions"].values() if e["type"] == "HEADLINE"]


def test_mcp_approval_required_and_single_use():
    owner, ws, acc = _account("apv@a.com", "9301")
    m = _mcp_headers(owner)
    url = f"/workspaces/{ws}/approvals"
    # 요청만으로는 실행 안 됨 → 웹에서 승인해야 저장된 내용 그대로 실행
    aid = _ext_request(m, ws, acc, "9301")
    assert _exts("9301") == []
    assert [x["approval_id"] for x in c.get(url, headers=owner).json()] == [aid]
    assert c.post(f"{url}/{aid}/approve", headers=m).status_code == 401  # Claude 출입증으로는 승인 못 함
    out = c.post(f"{url}/{aid}/approve", headers=owner).json()
    assert out["status"] == "DONE" and len(_exts("9301")) == 1
    assert c.post(f"{url}/{aid}/approve", headers=owner).status_code == 409  # 한 번만
    assert len(_exts("9301")) == 1
    # 거절 → 실행 안 됨, 거절 뒤 승인 불가
    aid = _ext_request(m, ws, acc, "9301", "거절될것")
    assert c.post(f"{url}/{aid}/reject", headers=owner).json()["status"] == "REJECTED"
    assert c.post(f"{url}/{aid}/approve", headers=owner).status_code == 409 and len(_exts("9301")) == 1
    acts = [x["action"] for x in c.get(f"/workspaces/{ws}/audit-logs", headers=owner).json()]
    assert {"APPROVAL_REQUEST", "APPROVAL_APPROVE", "APPROVAL_REJECT"} <= set(acts)


def test_mcp_approval_expired_and_tampered():
    from datetime import timedelta

    from app.db import SessionLocal
    from app.models import ApprovalRequest, now

    owner, ws, acc = _account("apv2@a.com", "9302")
    m = _mcp_headers(owner)
    url = f"/workspaces/{ws}/approvals"
    expired, tampered = _ext_request(m, ws, acc, "9302"), _ext_request(m, ws, acc, "9302", "원래내용")
    db = SessionLocal()
    try:
        db.get(ApprovalRequest, expired).expires_at = now() - timedelta(seconds=1)
        r = db.get(ApprovalRequest, tampered)
        r.payload = r.payload.replace("원래내용", "바꾼내용")  # 저장 뒤 내용이 바뀜
        db.commit()
    finally:
        db.close()
    assert c.post(f"{url}/{expired}/approve", headers=owner).status_code == 409
    assert _mcp_call(m, "get_approval", workspace_id=ws, approval_id=expired)[0]["status"] == "EXPIRED"
    out = c.post(f"{url}/{tampered}/approve", headers=owner).json()
    assert out["status"] == "FAILED" and _exts("9302") == []


def test_mcp_approval_who_can_approve():
    owner, ws, acc1, acc2, hs, mids = _staff_org("apw", "9311", "9312")
    sb, adm, sa = hs["sb"], hs["adm"], hs["sa"]
    url = f"/workspaces/{ws}/approvals"
    # 보기 권한(sa, 광고주1)으로는 요청도 못 만든다
    _, err = _mcp_call(_mcp_headers(sa), "create_ad_extension", workspace_id=ws, ad_account_id=acc1, adgroup_id="grp-9311-pl1",
                       ext_type="HEADLINE", heading="x")
    assert err
    aid = _ext_request(_mcp_headers(sb), ws, acc2, "9312")
    # 다른 직원은 목록에도 없고 승인도 못 함(존재 여부도 숨김), 다른 조직도 못 함
    assert c.get(url, headers=sa).json() == [] and c.post(f"{url}/{aid}/approve", headers=sa).status_code == 404
    outsider, ws_o, _ = _account("apw-out@b.com", "9313")
    assert c.post(f"{url}/{aid}/approve", headers=outsider).status_code == 403
    assert c.post(f"/workspaces/{ws_o}/approvals/{aid}/approve", headers=outsider).status_code == 404
    # 관리자는 보고 승인할 수 있다(실행은 승인한 사람 권한으로)
    assert aid in [x["approval_id"] for x in c.get(url, headers=adm).json()]
    assert c.post(f"{url}/{aid}/approve", headers=adm).json()["status"] == "DONE" and len(_exts("9312")) == 1


def test_mcp_approval_concurrent_approve(monkeypatch):
    """두 창에서 동시에 승인해도 한 번만 실행된다(상태 확인을 둘 다 통과한 뒤 경합)."""
    import threading

    from fastapi.testclient import TestClient

    from app import mcp

    owner, ws, acc = _account("apc@a.com", "9321")
    aid = _ext_request(_mcp_headers(owner), ws, acc, "9321")
    barrier = threading.Barrier(2, timeout=10)
    orig, seen = mcp._status_now, threading.local()

    def both_see_pending(r):
        st = orig(r)
        if not getattr(seen, "done", False):  # 요청마다 처음 상태 확인에서만 맞춘다(응답 만들 때는 안 기다림)
            seen.done = True
            barrier.wait()
        return st
    monkeypatch.setattr(mcp, "_status_now", both_see_pending)
    codes = []

    def go():
        codes.append(TestClient(app).post(f"/workspaces/{ws}/approvals/{aid}/approve", headers=owner).status_code)
    ts = [threading.Thread(target=go) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sorted(codes) == [200, 409] and len(_exts("9321")) == 1


def test_mcp_schedule_handoff():
    owner, ws, acc = _account("aps@a.com", "9331")
    m = _mcp_headers(owner)
    job = c.post(f"/workspaces/{ws}/bulk-jobs", headers=owner, json={"changes": [
        ch(acc, "keyword", "kwd-9331-11", "bid_amt", "350", before="300", product="WEB_SITE")]}).json()["id"]
    res, err = _mcp_call(m, "schedule_job", workspace_id=ws, job_id=job, scheduled_at="2030-01-01T00:00:00+09:00")
    assert not err and res["approval_required"] and res["url"].endswith(f"/jobs?id={job}")
    assert c.get(f"/workspaces/{ws}/bulk-jobs/{job}", headers=owner).json()["scheduled_at"] is None  # Claude는 예약 못 함
    c.post(f"/workspaces/{ws}/bulk-jobs/{job}/schedule", headers=owner, json={"scheduled_at": "2030-01-01T00:00:00+09:00"})
    out, err = _mcp_call(m, "schedule_job", workspace_id=ws, job_id=job, scheduled_at=None)  # 예약 취소는 Claude도 가능
    assert not err and out["scheduled_at"] is None
