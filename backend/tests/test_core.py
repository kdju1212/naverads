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
    dash = c.get(f"/workspaces/{ws}/dashboard", headers=owner).json()
    assert dash["connected_accounts"] == 2 and job["id"] in dash["failed_jobs"]
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


def test_rsa_texts():
    from app.sync import _rsa_texts

    assets = [{"linkType": "HEADLINE", "assetData": '{"text": "여름 세일"}'},
              {"linkType": "HEADLINE", "assetData": "무료배송"},
              {"linkType": "DESCRIPTION", "assetData": {"text": "전 상품 할인"}},
              {"linkType": "OTHER", "assetData": "무시"}]
    assert _rsa_texts(assets) == {"headlines": ["여름 세일", "무료배송"], "descriptions": ["전 상품 할인"]}
