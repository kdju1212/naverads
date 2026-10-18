"""네이버 검색광고 API 클라이언트 (실계정 / Mock).

두 클라이언트는 같은 인터페이스를 가진다. 응답 필드명은 네이버 API 형식(nccCampaignId, userLock ...)을 따른다.
실계정 쓰기는 공식 샘플(github.com/naver/searchad-apidoc java-sample)로 확인한 VERIFIED_WRITES만 허용하고,
나머지는 NAVER_ALLOW_REAL_WRITE=1 일 때만 허용한다.
"""
import base64
import hashlib
import hmac
import os
import random
import time
from datetime import date, timedelta

import httpx


class NaverApiError(Exception):
    pass


# 우리 필드 → (네이버 리소스 경로, fields 파라미터, 객체 수정 함수)
def _set_lock(o, v):
    o["userLock"] = v == "OFF"


def _set_budget(o, v):
    o["dailyBudget"], o["useDailyBudget"] = int(v), True


def _set_bid(o, v):
    o["bidAmt"], o["useGroupBidAmt"] = int(v), False


def _set_ad_bid(o, v):
    o["adAttr"] = {**o.get("adAttr", {}), "bidAmt": int(v), "useGroupBidAmt": False}


UPDATE_SPEC = {
    ("campaign", "status"): ("campaigns", "userLock", _set_lock),
    ("campaign", "daily_budget"): ("campaigns", "budget", _set_budget),
    ("adgroup", "status"): ("adgroups", "userLock", _set_lock),
    ("adgroup", "bid_amt"): ("adgroups", "bidAmt", _set_bid),
    ("keyword", "status"): ("keywords", "userLock", _set_lock),
    ("keyword", "bid_amt"): ("keywords", "bidAmt", _set_bid),
    ("ad", "status"): ("ads", "userLock", _set_lock),
    ("ad", "bid_amt"): ("ads", "adAttr", _set_ad_bid),  # 쇼핑 상품소재 전용 — 검증 필요
}
# 공식 샘플 AdManagementSample.java가 같은 경로·fields로 호출하는 것만 (예산·그룹 입찰가·쇼핑 소재 입찰가는 미확인)
VERIFIED_WRITES = {("campaign", "status"), ("adgroup", "status"), ("keyword", "status"), ("keyword", "bid_amt"), ("ad", "status")}


class RealNaverClient:
    BASE = "https://api.searchad.naver.com"

    def __init__(self, api_key: str, secret_key: str, customer_id: str):
        self.api_key, self.secret_key, self.customer_id = api_key, secret_key, customer_id

    def _req(self, method: str, uri: str, **kw):
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(
            hmac.new(self.secret_key.encode(), f"{ts}.{method}.{uri}".encode(), hashlib.sha256).digest()
        ).decode()
        headers = {"X-Timestamp": ts, "X-API-KEY": self.api_key, "X-Customer": self.customer_id, "X-Signature": sig}
        try:
            r = httpx.request(method, self.BASE + uri, headers=headers, timeout=20, **kw)
        except httpx.HTTPError as e:
            raise NaverApiError(f"네트워크 오류: {e}") from e
        if r.status_code >= 400:
            raise NaverApiError(f"{r.status_code} {r.text[:200]}")
        return r.json()

    def list_campaigns(self):
        return self._req("GET", "/ncc/campaigns")

    def list_adgroups(self, campaign_id):
        return self._req("GET", "/ncc/adgroups", params={"nccCampaignId": campaign_id})

    def list_keywords(self, adgroup_id):
        return self._req("GET", "/ncc/keywords", params={"nccAdgroupId": adgroup_id})

    def list_ads(self, adgroup_id):
        return self._req("GET", "/ncc/ads", params={"nccAdgroupId": adgroup_id})

    def stats(self, campaign_ids, since: date, until: date):
        raise NaverApiError("성과 통계 API 미검증 — 실계정 성과 조회는 아직 지원하지 않습니다")

    def update(self, entity_type, naver_id, field, value):
        if (entity_type, field) not in VERIFIED_WRITES and os.getenv("NAVER_ALLOW_REAL_WRITE") != "1":
            raise NaverApiError("이 항목의 실계정 수정은 공식 API 검증 전이라 아직 차단되어 있습니다")
        res, fields, apply = UPDATE_SPEC[(entity_type, field)]
        obj = self._req("GET", f"/ncc/{res}/{naver_id}")
        apply(obj, value)
        out = self._req("PUT", f"/ncc/{res}/{naver_id}", params={"fields": fields}, json=obj)
        # 네이버가 200을 주면서 이전 값을 돌려주는 경우가 있어(searchad-apidoc#982) 응답으로 반영 여부를 확인한다
        if out.get(fields) != obj.get(fields):
            raise NaverApiError(f"네이버에 반영되지 않았습니다 (요청 {obj.get(fields)}, 응답 {out.get(fields)})")


# ---- Mock ----
_MOCK_STORE: dict[str, dict] = {}
MOCK_FAIL_IDS: set[str] = set()  # 테스트용: 여기 있는 naver_id 수정은 API 오류로 응답


def _seed(cid: str) -> dict:
    s = {"campaigns": {}, "adgroups": {}, "keywords": {}, "ads": {}}
    pl, sh = f"cmp-{cid}-pl", f"cmp-{cid}-sh"
    s["campaigns"][pl] = {"nccCampaignId": pl, "name": "파워링크_브랜드", "campaignTp": "WEB_SITE", "userLock": False, "dailyBudget": 50000}
    s["campaigns"][sh] = {"nccCampaignId": sh, "name": "쇼핑검색_상품", "campaignTp": "SHOPPING", "userLock": False, "dailyBudget": 30000}
    for i in (1, 2):
        g = f"grp-{cid}-pl{i}"
        s["adgroups"][g] = {"nccAdgroupId": g, "nccCampaignId": pl, "name": f"파워링크그룹{i}", "adgroupType": "WEB_SITE", "userLock": False, "bidAmt": 500}
        for k, kw in enumerate(["원피스", "여름 원피스", "롱 원피스"], 1):
            kid = f"kwd-{cid}-{i}{k}"
            s["keywords"][kid] = {"nccKeywordId": kid, "nccAdgroupId": g, "keyword": f"{kw}{i}", "userLock": False, "bidAmt": 300 * k, "useGroupBidAmt": False}
        aid = f"ad-{cid}-pl{i}"
        s["ads"][aid] = {"nccAdId": aid, "nccAdgroupId": g, "type": "TEXT_45", "userLock": False, "inspectStatus": "APPROVED",
                         "ad": {"headline": "여름 원피스 할인", "description": "전 상품 무료배송", "pc": {"final": "https://example.com"}}}
    g = f"grp-{cid}-sh1"
    s["adgroups"][g] = {"nccAdgroupId": g, "nccCampaignId": sh, "name": "쇼핑그룹1", "adgroupType": "SHOPPING", "userLock": False, "bidAmt": 300}
    for p in (1, 2, 3):
        aid = f"ad-{cid}-sh{p}"
        s["ads"][aid] = {"nccAdId": aid, "nccAdgroupId": g, "type": "SHOPPING_PRODUCT_AD", "userLock": False, "inspectStatus": "APPROVED",
                         "ad": {"productName": f"린넨 원피스 {p}", "productId": f"{cid}{p:04d}"},
                         "adAttr": {"bidAmt": 200 * p, "useGroupBidAmt": False}}
    return s


class MockNaverClient:
    def __init__(self, customer_id: str):
        if not customer_id.isdigit():
            raise NaverApiError("고객 ID는 숫자여야 합니다")
        self.s = _MOCK_STORE.setdefault(customer_id, _seed(customer_id))

    def list_campaigns(self):
        return [dict(c) for c in self.s["campaigns"].values()]

    def list_adgroups(self, campaign_id):
        return [dict(g) for g in self.s["adgroups"].values() if g["nccCampaignId"] == campaign_id]

    def list_keywords(self, adgroup_id):
        return [dict(k) for k in self.s["keywords"].values() if k["nccAdgroupId"] == adgroup_id]

    def list_ads(self, adgroup_id):
        return [dict(a) for a in self.s["ads"].values() if a["nccAdgroupId"] == adgroup_id]

    def stats(self, campaign_ids, since: date, until: date):
        out, d = [], since
        while d <= until:
            for cid in campaign_ids:
                r = random.Random(f"{cid}{d}")
                imp = r.randint(500, 5000)
                clk = imp * r.randint(1, 5) // 100
                cost = clk * r.randint(200, 800)
                conv = clk * r.randint(0, 8) // 100
                out.append({"id": cid, "date": d, "impCnt": imp, "clkCnt": clk, "salesAmt": cost,
                            "ccnt": conv, "convAmt": conv * r.randint(20000, 60000)})
            d += timedelta(days=1)
        return out

    def update(self, entity_type, naver_id, field, value):
        if naver_id in MOCK_FAIL_IDS:
            raise NaverApiError("Mock API 오류: 요청이 거부되었습니다")
        res, _, apply = UPDATE_SPEC[(entity_type, field)]
        obj = self.s[res].get(naver_id)
        if obj is None:
            raise NaverApiError("대상 객체가 존재하지 않습니다")
        apply(obj, value)


def client_for(credential, customer_id: str, decrypt):
    if credential.is_mock:
        return MockNaverClient(customer_id)
    return RealNaverClient(credential.api_key, decrypt(credential.secret_key_enc), customer_id)
