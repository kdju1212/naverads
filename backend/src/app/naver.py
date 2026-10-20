"""네이버 검색광고 API 클라이언트 (실계정 / Mock).

두 클라이언트는 같은 인터페이스를 가진다. 응답 필드명은 네이버 API 형식(nccCampaignId, userLock ...)을 따른다.
실계정 쓰기는 공식 샘플(github.com/naver/searchad-apidoc java-sample)로 확인한 VERIFIED_WRITES만 허용하고,
나머지는 NAVER_ALLOW_REAL_WRITE=1 일 때만 허용한다.
"""
import base64
import hashlib
import hmac
import json
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


def _set_group_bid(o, v):
    o["bidAmt"] = int(v)  # 광고그룹에는 useGroupBidAmt가 없다


def _set_ad_bid(o, v):
    o["adAttr"] = {**o.get("adAttr", {}), "bidAmt": int(v), "useGroupBidAmt": False}


UPDATE_SPEC = {
    ("campaign", "status"): ("campaigns", "userLock", _set_lock),
    ("campaign", "daily_budget"): ("campaigns", "budget", _set_budget),
    ("adgroup", "status"): ("adgroups", "userLock", _set_lock),
    ("adgroup", "bid_amt"): ("adgroups", "bidAmt", _set_group_bid),
    ("keyword", "status"): ("keywords", "userLock", _set_lock),
    ("keyword", "bid_amt"): ("keywords", "bidAmt", _set_bid),
    ("ad", "status"): ("ads", "userLock", _set_lock),
    ("ad", "bid_amt"): ("ads", "adAttr", _set_ad_bid),  # 쇼핑 상품소재 전용 — 검증 필요
    ("ad_extension", "status"): ("ad-extensions", "userLock", _set_lock),
}
# 공식 샘플 AdManagementSample.java·명세(gh-pages assets/json/ncc-heroes-ncc.json)로 경로·fields를 확인한 것만
# (쇼핑 소재 입찰가는 미확인)
VERIFIED_WRITES = {("campaign", "status"), ("campaign", "daily_budget"), ("adgroup", "status"), ("adgroup", "bid_amt"),
                   ("keyword", "status"), ("keyword", "bid_amt"), ("ad", "status"),
                   # 확장소재: 명세에 fields 목록은 없지만 userLock이 ON/OFF용으로 정의돼 있다(응답 검증으로 반영 확인)
                   ("ad_extension", "status")}


# 확장소재 노출 스케줄: 요일별 0~23시 비트 합 (2^24-1 = 매시간)
ALL_WEEK = {d: 2 ** 24 - 1 for d in ("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")}


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
        return r.json() if r.content else None  # DELETE는 본문 없이 응답할 수 있다

    def list_campaigns(self):
        return self._req("GET", "/ncc/campaigns")

    def list_adgroups(self, campaign_id):
        return self._req("GET", "/ncc/adgroups", params={"nccCampaignId": campaign_id})

    def list_keywords(self, adgroup_id):
        return self._req("GET", "/ncc/keywords", params={"nccAdgroupId": adgroup_id})

    def list_ads(self, adgroup_id):
        return self._req("GET", "/ncc/ads", params={"nccAdgroupId": adgroup_id})

    def list_ad_extensions(self, owner_id):
        return self._req("GET", "/ncc/ad-extensions", params={"ownerId": owner_id})

    def create_ad_extension(self, adgroup_id, ext_type, content):
        # 명세상 생성에 비즈채널·스케줄이 필수라 소유 광고그룹의 채널을 쓰고 매일 24시간 노출로 만든다
        grp = self._req("GET", f"/ncc/adgroups/{adgroup_id}")
        return self._req("POST", "/ncc/ad-extensions", json={
            "ownerId": adgroup_id, "type": ext_type, "userLock": False, "adExtension": content,
            "pcChannelId": grp.get("pcChannelId"), "mobileChannelId": grp.get("mobileChannelId"), "schedule": ALL_WEEK})

    def delete_ad_extension(self, ext_id):
        # 명세의 /ncc/ad-extensions/{id}는 실계정에서 404, 공식 샘플(AdExtensions.java)처럼 ids 쿼리로 지운다
        self._req("DELETE", "/ncc/ad-extensions", params={"ids": ext_id})

    def create_keyword(self, adgroup_id, keyword, bid):
        # 명세(ncc-heroes-ncc.json): POST /ncc/keywords?nccAdgroupId= 본문은 KeywordRequest 배열. bid가 None이면 그룹 입찰가
        body = {"keyword": keyword, "useGroupBidAmt": bid is None, **({"bidAmt": bid} if bid else {})}
        r = self._req("POST", "/ncc/keywords", params={"nccAdgroupId": adgroup_id}, json=[body])
        k = r[0] if isinstance(r, list) and r else r
        # 실계정에서 200인데 nccKeywordId 없는 응답이 왔다(10/20) → 실패 행 사유에 응답을 남겨 원인 확인
        if not isinstance(k, dict) or "nccKeywordId" not in k:
            raise NaverApiError(f"등록 응답에 키워드 ID가 없습니다: {json.dumps(r, ensure_ascii=False)[:250]}")
        return k

    def keyword_tool(self, hints):
        """연관 키워드 + 최근 30일 월 검색량. 명세(gh-pages assets/json/ncc-keywordstool.json)."""
        r = self._req("GET", "/keywordstool", params={"hintKeywords": ",".join(hints), "showDetail": "1"})
        return [_kwd_stat(k) for k in r.get("keywordList", [])]

    def delete_keyword(self, keyword_id):
        # 확장소재처럼 /{id} 경로 대신 명세의 ids 쿼리 방식
        self._req("DELETE", "/ncc/keywords", params={"ids": keyword_id})

    def stats(self, campaign_ids, since: date, until: date):
        # 명세(gh-pages assets/json/ncc-report.json): 일별(timeIncrement=1)은 단일 id만 지원, salesAmt는 VAT 포함
        fields = json.dumps(["impCnt", "clkCnt", "salesAmt", "ccnt", "convAmt"])
        time_range = json.dumps({"since": since.isoformat(), "until": until.isoformat()})
        out = []
        for cid in campaign_ids:
            r = self._req("GET", "/stats", params={"id": cid, "fields": fields, "timeRange": time_range, "timeIncrement": "1"})
            for s in r.get("data", []):
                out.append({"id": cid, "date": date.fromisoformat(s["dateStart"]), "impCnt": s.get("impCnt", 0),
                            "clkCnt": s.get("clkCnt", 0), "salesAmt": s.get("salesAmt", 0),
                            "ccnt": s.get("ccnt"), "convAmt": s.get("convAmt")})
        return out

    def estimate_bids(self, device, items):
        """items: [(nccKeywordId, 순위)] → {nccKeywordId: 예상 입찰가}. 명세(gh-pages assets/json/estimate.json)."""
        out = {}
        for i in range(0, len(items), 100):  # shortcut: 한 번에 보낼 수 있는 개수는 명세에 없어 100개씩, 오류 나면 줄이기
            chunk = items[i:i + 100]
            r = self._req("POST", "/estimate/average-position-bid/id", json={
                "device": device, "items": [{"key": k, "position": p} for k, p in chunk]})
            # 응답은 요청 순서대로 온다. nccKeywordId가 있으면 그걸 쓴다
            for (k, _), e in zip(chunk, r.get("estimate", [])):
                out[e.get("nccKeywordId") or k] = e.get("bid")
        return out

    def update(self, entity_type, naver_id, field, value):
        if (entity_type, field) not in VERIFIED_WRITES and os.getenv("NAVER_ALLOW_REAL_WRITE") != "1":
            raise NaverApiError("이 항목의 실계정 수정은 공식 API 검증 전이라 아직 차단되어 있습니다")
        res, fields, apply = UPDATE_SPEC[(entity_type, field)]
        obj = self._req("GET", f"/ncc/{res}/{naver_id}")
        before = dict(obj)
        apply(obj, value)
        want = {k: v for k, v in obj.items() if before.get(k) != v}
        out = self._req("PUT", f"/ncc/{res}/{naver_id}", params={"fields": fields}, json=obj)
        # 네이버가 200을 주면서 이전 값을 돌려주는 경우가 있어(searchad-apidoc#982) 바꾼 필드가 응답에 반영됐는지 확인한다
        got = {k: out.get(k) for k in want}
        if got != want:
            raise NaverApiError(f"네이버에 반영되지 않았습니다 (요청 {want}, 응답 {got})")


def _kwd_stat(k):
    # 검색량이 적으면 숫자 대신 "< 10" 문자열이 온다 → 0 (화면에서 "10 미만")
    n = lambda v: int(v) if str(v).isdigit() else 0  # noqa: E731
    return {"keyword": k["relKeyword"], "pc": n(k.get("monthlyPcQcCnt")), "mobile": n(k.get("monthlyMobileQcCnt")),
            "comp": k.get("compIdx", "")}


# ---- Mock ----
_MOCK_STORE: dict[str, dict] = {}
MOCK_FAIL_IDS: set[str] = set()  # 테스트용: 여기 있는 naver_id 수정은 API 오류로 응답


def _seed(cid: str) -> dict:
    s = {"campaigns": {}, "adgroups": {}, "keywords": {}, "ads": {}, "ad-extensions": {}}
    pl, sh = f"cmp-{cid}-pl", f"cmp-{cid}-sh"
    s["campaigns"][pl] = {"nccCampaignId": pl, "name": "파워링크_브랜드", "campaignTp": "WEB_SITE", "userLock": False, "dailyBudget": 50000}
    s["campaigns"][sh] = {"nccCampaignId": sh, "name": "쇼핑검색_상품", "campaignTp": "SHOPPING", "userLock": False, "dailyBudget": 30000}
    for i in (1, 2):
        g = f"grp-{cid}-pl{i}"
        s["adgroups"][g] = {"nccAdgroupId": g, "nccCampaignId": pl, "name": f"파워링크그룹{i}", "adgroupType": "WEB_SITE", "userLock": False, "bidAmt": 500,
                           "useDailyBudget": i == 1, "dailyBudget": 20000,
                           "status": "ELIGIBLE" if i == 2 else "LIMITED_ELIGIBLE", **({"statusReason": "GROUP_LIMITED_BY_BUDGET"} if i == 1 else {})}
        for k, kw in enumerate(["원피스", "여름 원피스", "롱 원피스"], 1):
            kid = f"kwd-{cid}-{i}{k}"
            s["keywords"][kid] = {"nccKeywordId": kid, "nccAdgroupId": g, "keyword": f"{kw}{i}", "userLock": False, "bidAmt": 300 * k, "useGroupBidAmt": False}
        aid = f"ad-{cid}-pl{i}"
        s["ads"][aid] = {"nccAdId": aid, "nccAdgroupId": g, "type": "TEXT_45", "userLock": False, "inspectStatus": "APPROVED",
                         "ad": {"headline": "여름 원피스 할인", "description": "전 상품 무료배송", "pc": {"final": "https://example.com"}}}
        eid = f"ext-{cid}-pl{i}"
        s["ad-extensions"][eid] = {"nccAdExtensionId": eid, "ownerId": g, "type": "SUB_LINKS", "userLock": False,
                                   "inspectStatus": "APPROVED",
                                   "adExtension": '[{"name": "신상품", "final": "https://example.com/new"}]'}
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

    def list_ad_extensions(self, owner_id):
        # .get: 이 키가 생기기 전에 만들어진 Mock 저장소도 있다
        return [dict(e) for e in self.s.get("ad-extensions", {}).values() if e["ownerId"] == owner_id]

    def create_ad_extension(self, adgroup_id, ext_type, content):
        if adgroup_id not in self.s["adgroups"]:
            raise NaverApiError("대상 광고그룹이 존재하지 않습니다")
        eid = f"ext-mock-{len(self.s.setdefault('ad-extensions', {})) + 1}-{random.randint(1000, 9999)}"
        e = {"nccAdExtensionId": eid, "ownerId": adgroup_id, "type": ext_type, "userLock": False,
             "inspectStatus": "UNDER_REVIEW", "adExtension": json.dumps(content, ensure_ascii=False)}
        self.s["ad-extensions"][eid] = e
        return dict(e)

    def delete_ad_extension(self, ext_id):
        if self.s.get("ad-extensions", {}).pop(ext_id, None) is None:
            raise NaverApiError("대상 확장소재가 존재하지 않습니다")

    def create_keyword(self, adgroup_id, keyword, bid):
        if adgroup_id not in self.s["adgroups"]:
            raise NaverApiError("대상 광고그룹이 존재하지 않습니다")
        kid = f"kwd-mock-{len(self.s['keywords']) + 1}-{random.randint(1000, 9999)}"
        g = self.s["adgroups"][adgroup_id]
        k = {"nccKeywordId": kid, "nccAdgroupId": adgroup_id, "keyword": keyword, "userLock": False,
             "bidAmt": bid or g["bidAmt"], "useGroupBidAmt": bid is None}
        self.s["keywords"][kid] = k
        return dict(k)

    def keyword_tool(self, hints):
        r = random.Random(",".join(hints))
        return [_kwd_stat({"relKeyword": f"{h}{s}", "monthlyPcQcCnt": str(r.randint(0, 5000)) if s else "< 10",
                           "monthlyMobileQcCnt": str(r.randint(0, 20000)), "compIdx": r.choice(["낮음", "중간", "높음"])})
                for h in hints for s in ("", " 추천", " 가격", " 후기", " 할인")]

    def delete_keyword(self, keyword_id):
        if keyword_id in MOCK_FAIL_IDS or self.s["keywords"].pop(keyword_id, None) is None:
            raise NaverApiError("대상 키워드가 존재하지 않습니다")

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

    def estimate_bids(self, device, items):
        # 순위가 높을수록(숫자가 작을수록) 비싸다
        base = 1000 if device == "PC" else 700
        return {k: base // p // 10 * 10 + 70 for k, p in items if k in self.s["keywords"]}

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
