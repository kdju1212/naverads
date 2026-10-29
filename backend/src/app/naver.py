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
import re
import time
from datetime import date, timedelta
from urllib.parse import quote, urlsplit

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


def _check_expected(field, o, expect):
    """예약 실행: 지금 값이 미리보기 때(expect)와 다르면 실패. 비교 기준이 애매한 값(그룹 입찰가를 쓰는 키워드, 예산 미사용)은 건너뛴다."""
    if expect is None:
        return
    if field == "status":
        cur = "OFF" if o.get("userLock") else "ON"
    elif field == "daily_budget" and o.get("useDailyBudget"):
        cur = o.get("dailyBudget")
    elif field == "bid_amt" and not o.get("useGroupBidAmt"):
        cur = (o.get("adAttr") if isinstance(o.get("adAttr"), dict) else o).get("bidAmt")
    else:
        return
    if str(cur) != str(expect):
        raise NaverApiError(f"미리보기 이후 값이 바뀌어 실행하지 않았습니다 (미리보기 {expect}, 지금 {cur})")


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

# 파워링크 전체 목록 화면(검색 결과의 '광고 더보기'). 공식 API에 현재 순위 조회가 없어 이 화면을 읽는다
SERP = {"PC": ("https://ad.search.naver.com/search.naver?where=ad&query=",
               "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"),
        "MOBILE": ("https://m.ad.search.naver.com/search.naver?where=m_expd&query=",
                   "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148")}
SERP_AD_ID = re.compile(r"nad-a\d+-\d+-\d+")


class RealNaverClient:
    BASE = "https://api.searchad.naver.com"

    def __init__(self, api_key: str, secret_key: str, customer_id: str):
        self.api_key, self.secret_key, self.customer_id = api_key, secret_key, customer_id

    def _headers(self, method: str, uri: str) -> dict:
        ts = str(int(time.time() * 1000))
        sig = base64.b64encode(
            hmac.new(self.secret_key.encode(), f"{ts}.{method}.{uri}".encode(), hashlib.sha256).digest()
        ).decode()
        return {"X-Timestamp": ts, "X-API-KEY": self.api_key, "X-Customer": self.customer_id, "X-Signature": sig}

    def _req(self, method: str, uri: str, raw=False, base=BASE, **kw):
        try:
            r = httpx.request(method, base + uri, headers=self._headers(method, uri), timeout=20, **kw)
        except httpx.HTTPError as e:
            raise NaverApiError(f"네트워크 오류: {e}") from e
        except AttributeError as e:
            # Workers의 httpx(jsfetch)는 본문 없는 응답(소재 DELETE의 204)에서 body가 null이라 getReader에서 죽는다.
            # 네이버 오류 응답은 항상 JSON 본문이 있으니 본문 없음 = 성공으로 본다 (실계정 10/26)
            if "getReader" not in str(e):
                raise
            return None
        if r.status_code >= 400:
            raise NaverApiError(f"{r.status_code} {r.text[:200]}")
        if raw:
            return r.text
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

    def list_channels(self):
        return self._req("GET", "/ncc/channels")

    # 캠페인·광고그룹 생성: 만들자마자 비용이 나가지 않게 OFF(userLock)로 만든다. shortcut: 명세 기준, 실계정 미확인(파워링크 확인 후 이 줄 갱신)
    def create_campaign(self, campaign_tp, name, daily_budget):
        return self._req("POST", "/ncc/campaigns", json={
            "customerId": int(self.customer_id), "name": name, "campaignTp": campaign_tp, "dailyBudget": daily_budget,
            "useDailyBudget": True, "deliveryMethod": "STANDARD", "userLock": True})

    def create_adgroup(self, campaign_id, name, channel_id, bid, daily_budget):
        tp = self._req("GET", f"/ncc/campaigns/{campaign_id}")["campaignTp"]  # 광고그룹 유형은 캠페인 유형을 따른다
        return self._req("POST", "/ncc/adgroups", json=_adgroup_body(campaign_id, tp, name, channel_id, bid, daily_budget))

    def create_ad_extension(self, adgroup_id, ext_type, content):
        # 명세상 생성에 비즈채널·스케줄이 필수라 소유 광고그룹의 채널을 쓰고 매일 24시간 노출로 만든다
        grp = self._req("GET", f"/ncc/adgroups/{adgroup_id}")
        return self._req("POST", "/ncc/ad-extensions", json={
            "ownerId": adgroup_id, "type": ext_type, "userLock": False, "adExtension": content,
            "pcChannelId": grp.get("pcChannelId"), "mobileChannelId": grp.get("mobileChannelId"), "schedule": ALL_WEEK})

    def delete_ad_extension(self, ext_id):
        # 명세의 /ncc/ad-extensions/{id}는 실계정에서 404, 공식 샘플(AdExtensions.java)처럼 ids 쿼리로 지운다
        self._req("DELETE", "/ncc/ad-extensions", params={"ids": ext_id})

    def create_keyword(self, adgroup_id, keyword, bid, use_group_bid):
        # 명세(ncc-heroes-ncc.json): POST /ncc/keywords?nccAdgroupId= 본문은 KeywordRequest 배열.
        # 그룹 입찰가를 써도 bidAmt가 없으면 3916 "No value is entered in the default bid or bid amount field." (실계정 10/20)
        body = {"keyword": keyword, "bidAmt": bid, "useGroupBidAmt": use_group_bid}
        r = self._req("POST", "/ncc/keywords", params={"nccAdgroupId": adgroup_id}, json=[body])
        k = r[0] if isinstance(r, list) and r else r
        # 항목별 실패는 200 응답에 nccKeywordId 없이 resultStatus로 온다
        if not isinstance(k, dict) or "nccKeywordId" not in k:
            rs = k.get("resultStatus") if isinstance(k, dict) else None
            raise NaverApiError(f"{rs['code']} {rs['message']}" if rs else f"등록 응답에 키워드 ID가 없습니다: {json.dumps(r, ensure_ascii=False)[:250]}")
        return k

    # 제외검색어: 명세(ncc-heroes-ncc.json) /ncc/adgroups/{id}/restricted-keywords. 실계정 조회·등록·삭제 확인(10/27)
    def list_restricted_keywords(self, adgroup_id):
        return self._req("GET", f"/ncc/adgroups/{adgroup_id}/restricted-keywords", params={"type": "KEYWORD_PLUS_RESTRICT"}) or []

    def create_restricted_keyword(self, adgroup_id, keyword):
        r = self._req("POST", f"/ncc/adgroups/{adgroup_id}/restricted-keywords",
                      json=[{"nccAdgroupId": adgroup_id, "keyword": keyword, "type": "KEYWORD_PLUS_RESTRICT"}])
        k = r[0] if isinstance(r, list) and r else r
        if not isinstance(k, dict) or "nccAdgroupRestrictKwdId" not in k:
            rs = k.get("resultStatus") if isinstance(k, dict) else None
            raise NaverApiError(f"{rs['code']} {rs['message']}" if rs else f"등록 응답에 제외검색어 ID가 없습니다: {json.dumps(r, ensure_ascii=False)[:250]}")
        return k

    def delete_restricted_keyword(self, adgroup_id, kwd_id):
        self._req("DELETE", f"/ncc/adgroups/{adgroup_id}/restricted-keywords", params={"ids": kwd_id})

    def keyword_tool(self, hints):
        """연관 키워드 + 최근 30일 월 검색량. 명세(gh-pages assets/json/ncc-keywordstool.json)."""
        r = self._req("GET", "/keywordstool", params={"hintKeywords": ",".join(hints), "showDetail": "1"})
        return [_kwd_stat(k) for k in r.get("keywordList", [])]

    def _delete(self, path, nid):
        # 키워드는 ids 쿼리 방식(공식 샘플)이 실계정에서 1018 "No permission"(10/20) → 명세의 /{id} 경로를 먼저 시도
        try:
            self._req("DELETE", f"{path}/{nid}")
        except NaverApiError as e1:
            try:
                self._req("DELETE", path, params={"ids": nid})
            except NaverApiError as e2:
                raise NaverApiError(f"경로 방식: {e1} / ids 방식: {e2}")

    def delete_keyword(self, keyword_id):
        self._delete("/ncc/keywords", keyword_id)

    def delete_container(self, entity_type, naver_id):
        """캠페인·광고그룹 삭제. 안의 광고까지 사라지므로 켜져 있으면(ON) 지우지 않는다."""
        res = CONTAINER_RES[entity_type]
        if not self._req("GET", f"/ncc/{res}/{naver_id}").get("userLock"):
            raise NaverApiError(ON_NOT_DELETABLE)
        self._delete(f"/ncc/{res}", naver_id)

    def delete_ad(self, ad_id):
        self._delete("/ncc/ads", ad_id)

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

    def entity_stats(self, ids, since: date, until: date) -> dict:
        """키워드·광고그룹·소재 여러 개의 기간 합계(명세 getBulkEntityStatUsingGET). {id: 수치}"""
        fields = json.dumps(["impCnt", "clkCnt", "salesAmt", "ccnt", "convAmt", "avgRnk"])
        time_range = json.dumps({"since": since.isoformat(), "until": until.isoformat()})
        out = {}
        for i in range(0, len(ids), 100):
            # shortcut: ids는 쉼표로, 응답은 data 목록이라고 가정(실계정 미확인), 실계정 응답이 다르면 여기만 고친다
            r = self._req("GET", "/stats", params={"ids": ",".join(ids[i:i + 100]), "fields": fields, "timeRange": time_range})
            out.update({x["id"]: x for x in r.get("data", [])})
        return out

    def create_ad(self, adgroup_id, ad_type, ad, assets):
        # 명세 AdRequest. 검수·확인 전에 노출되지 않게 OFF로 만든다. shortcut: 실계정 미확인
        body = {"nccAdgroupId": adgroup_id, "type": ad_type, "ad": ad, "userLock": True, **({"assets": assets} if assets else {})}
        return self._req("POST", "/ncc/ads", json=body)

    def serp_ads(self, keyword, device) -> list[str]:
        """검색 화면의 파워링크 소재 ID(nad-...)를 노출 순서대로. Cloudflare에서도 한국 화면으로 보이는 것 확인(10/23).
        shortcut: 화면 HTML에 소재 ID가 순서대로 있다는 데 기대고 있다, 네이버가 화면을 바꾸면 여기만 고친다"""
        url, ua = SERP[device]
        try:
            r = httpx.get(url + quote(keyword), headers={"User-Agent": ua}, timeout=15)
        except httpx.HTTPError as e:
            raise NaverApiError(f"검색 화면 네트워크 오류: {e}") from e
        ids = list(dict.fromkeys(SERP_AD_ID.findall(r.text))) if r.status_code < 400 else []
        if not ids:  # 차단·화면 변경을 '내 광고 없음'으로 오해해 입찰가를 올리지 않도록 실패로 본다
            # 받은 화면 길이·제목·최종 주소: 차단·보안문자/해외 화면/광고 칸만 빠짐을 구분하려고 남긴다
            title = (m := re.search(r"<title[^>]*>(.*?)</title>", r.text, re.S | re.I)) and m.group(1).strip()[:80]
            raise NaverApiError(f"검색 화면에서 광고 목록을 읽지 못했습니다 ({r.status_code}, {len(r.text)}자, 제목: {title or '없음'}, {r.url})")
        return ids

    # 마스터 보고서(명세: gh-pages assets/json/master-report.json). 파일은 헤더 없는 TSV, 칸 구성은 브라우저(lib/naverData.ts) 참고
    def create_master_report(self, item):
        try:
            return self._req("POST", "/master-reports", json={"item": item})
        except NaverApiError as e:
            # 계정당 보고서 100개 한도("exceeded limit of '100' numbers of 'job'", 10/26). 다 받은 보고서는 화면이 지우지만
            # 그 전에 쌓인 것·지우기 실패분을 비운다. shortcut: 전부 지우므로 같은 계정에서 동시에 받던 보고서가 끊길 수 있음(다시 새로고침하면 됨)
            if "exceeded limit" not in str(e):
                raise
            self._req("DELETE", "/master-reports")
            return self._req("POST", "/master-reports", json={"item": item})

    def get_master_report(self, job_id):
        return self._req("GET", f"/master-reports/{job_id}")

    def delete_master_report(self, job_id):
        self._req("DELETE", f"/master-reports/{job_id}")

    def master_file(self, job) -> dict:
        """다운로드 주소 + 서명 헤더. 서명 uri는 쿼리를 뺀 경로(공식 샘플의 /report-download).
        Workers는 이걸로 JS fetch를 해서 파이썬이 본문을 건드리지 않는다(9MB 실측: CPU 25ms, httpx는 1.5초)."""
        return {"url": job["downloadUrl"], "headers": self._headers("GET", urlsplit(job["downloadUrl"]).path)}

    def get_many(self, kind, ids):
        """ids로 여러 개 조회(명세의 /ncc/{kind}?ids=). kind: adgroups | keywords | ads | ad-extensions"""
        out = []
        for i in range(0, len(ids), 100):  # shortcut: 한 번에 보낼 수 있는 개수는 명세에 없어 100개씩, 오류 나면 줄이기
            out += self._req("GET", f"/ncc/{kind}", params={"ids": ",".join(ids[i:i + 100])})
        return out

    def update(self, entity_type, naver_id, field, value, expect=None):
        if (entity_type, field) not in VERIFIED_WRITES and os.getenv("NAVER_ALLOW_REAL_WRITE") != "1":
            raise NaverApiError("이 항목의 실계정 수정은 공식 API 검증 전이라 아직 차단되어 있습니다")
        res, fields, apply = UPDATE_SPEC[(entity_type, field)]
        obj = self._req("GET", f"/ncc/{res}/{naver_id}")
        _check_expected(field, obj, expect)
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


def _status(o):
    return "OFF" if o.get("userLock") else "ON"


def _json(v):
    """네이버는 일부 필드(adExtension, assetData)를 JSON 문자열로 준다."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return {"text": v}
    return v if v is not None else {}


def _rsa_texts(assets) -> dict:
    # shortcut: assetData 형식은 명세에 없어 문자열/JSON 모두 받아 문자열 값만 모은다, 실응답 확인 후 정리
    out = {"headlines": [], "descriptions": []}
    for x in assets:
        key = {"HEADLINE": "headlines", "DESCRIPTION": "descriptions"}.get(x.get("linkType"))
        if key:
            d = _json(x.get("assetData"))
            out[key].append(" ".join(v for v in d.values() if isinstance(v, str)) if isinstance(d, dict) else str(d))
    return out


CONTAINER_RES = {"campaign": "campaigns", "adgroup": "adgroups"}
ON_NOT_DELETABLE = "ON 상태라 지우지 않았습니다. 먼저 OFF로 바꾼 뒤 삭제하세요"
MIN_BID = {"WEB_SITE": 70, "SHOPPING": 50}  # bulk.BID_RANGE 최저값과 같게(입찰가를 비우면 이 값)


def _adgroup_body(campaign_id, tp, name, channel_id, bid, daily_budget):
    return {"nccCampaignId": campaign_id, "name": name, "adgroupType": tp, "pcChannelId": channel_id, "mobileChannelId": channel_id,
            "bidAmt": bid or MIN_BID[tp], "useDailyBudget": daily_budget is not None, "dailyBudget": daily_budget or 0, "userLock": True}


def channel_row(aid, c):
    return {"ad_account_id": aid, "naver_id": c["nccBusinessChannelId"], "name": c.get("name", ""), "channel_tp": c.get("channelTp", ""),
            "key": c.get("channelKey", ""), "inspect_status": c.get("inspectStatus", "")}


# 브라우저 보관용 행. DB 사본 없이 네이버 ID로만 식별한다
def campaign_row(aid, c):
    return {"ad_account_id": aid, "naver_id": c["nccCampaignId"], "name": c["name"], "campaign_tp": c["campaignTp"],
            "status": _status(c), "daily_budget": c.get("dailyBudget") or 0}


def adgroup_row(aid, g):
    return {"ad_account_id": aid, "naver_id": g["nccAdgroupId"], "campaign_naver_id": g["nccCampaignId"], "name": g["name"],
            "adgroup_type": g["adgroupType"], "status": _status(g), "bid_amt": g["bidAmt"],
            # shortcut: 공유예산(sharedBudgetId) 그룹은 반영 안 함, 쓰는 계정이 생기면 sharedDailyBudget 표시
            "daily_budget": g.get("dailyBudget") if g.get("useDailyBudget") else None,
            "serving": g.get("statusReason") or g.get("status")}


def ad_row(aid, a):
    attr = a.get("adAttr") or {}
    payload = a.get("ad", {})
    if a.get("assets"):  # RSA_AD: 제목·설명은 ad가 아니라 assets에 온다
        payload = {**payload, **_rsa_texts(a["assets"])}
    return {"ad_account_id": aid, "naver_id": a["nccAdId"], "adgroup_naver_id": a["nccAdgroupId"], "ad_type": a["type"],
            "status": _status(a), "inspect_status": a.get("inspectStatus", ""), "bid_amt": attr.get("bidAmt"),
            "use_group_bid": attr.get("useGroupBidAmt", True), "payload": payload}


def extension_row(aid, e):
    return {"ad_account_id": aid, "naver_id": e["nccAdExtensionId"], "owner_naver_id": e["ownerId"], "ext_type": e["type"],
            "status": _status(e), "inspect_status": e.get("inspectStatus", ""), "payload": _json(e.get("adExtension"))}


# ---- Mock ----
_MOCK_STORE: dict[str, dict] = {}
MOCK_FAIL_IDS: set[str] = set()  # 테스트용: 여기 있는 naver_id 수정은 API 오류로 응답
MOCK_RIVALS = (900, 700, 500, 300, 150)  # 가상 검색 화면의 경쟁 광고 입찰가


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
    s["channels"] = {f"bsn-{cid}-site": {"nccBusinessChannelId": f"bsn-{cid}-site", "name": "자사몰", "channelTp": "SITE",
                                         "channelKey": "https://example.com", "inspectStatus": "APPROVED"},
                     f"bsn-{cid}-shop": {"nccBusinessChannelId": f"bsn-{cid}-shop", "name": "쇼핑몰", "channelTp": "MALL",
                                         "channelKey": "shop-example", "inspectStatus": "APPROVED"}}
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
        self.customer_id, self.s = customer_id, _MOCK_STORE.setdefault(customer_id, _seed(customer_id))

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

    def list_channels(self):
        return [dict(c) for c in self.s.get("channels", {}).values()]

    def create_campaign(self, campaign_tp, name, daily_budget):
        nid = f"cmp-{self.customer_id}-new{len(self.s['campaigns']) + 1}"
        self.s["campaigns"][nid] = {"nccCampaignId": nid, "name": name, "campaignTp": campaign_tp, "userLock": True, "dailyBudget": daily_budget}
        return dict(self.s["campaigns"][nid])

    def create_adgroup(self, campaign_id, name, channel_id, bid, daily_budget):
        camp = self.s["campaigns"].get(campaign_id)
        if camp is None:
            raise NaverApiError("대상 캠페인이 존재하지 않습니다")
        ch = self.s.get("channels", {}).get(channel_id)
        if ch is None or ch["channelTp"] != {"WEB_SITE": "SITE", "SHOPPING": "MALL"}[camp["campaignTp"]]:
            raise NaverApiError("캠페인 유형에 맞는 비즈채널이 아닙니다")
        nid = f"grp-{self.customer_id}-new{len(self.s['adgroups']) + 1}"
        self.s["adgroups"][nid] = {"nccAdgroupId": nid, **_adgroup_body(campaign_id, camp["campaignTp"], name, channel_id, bid, daily_budget)}
        return dict(self.s["adgroups"][nid])

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

    def create_keyword(self, adgroup_id, keyword, bid, use_group_bid):
        if adgroup_id not in self.s["adgroups"]:
            raise NaverApiError("대상 광고그룹이 존재하지 않습니다")
        if not bid:
            raise NaverApiError("3916 No value is entered in the default bid or bid amount field.")
        kid = f"kwd-mock-{len(self.s['keywords']) + 1}-{random.randint(1000, 9999)}"
        k = {"nccKeywordId": kid, "nccAdgroupId": adgroup_id, "keyword": keyword, "userLock": False,
             "bidAmt": bid, "useGroupBidAmt": use_group_bid}
        self.s["keywords"][kid] = k
        return dict(k)

    def list_restricted_keywords(self, adgroup_id):
        return [dict(k) for k in self.s.setdefault("restricted", {}).values() if k["nccAdgroupId"] == adgroup_id]

    def create_restricted_keyword(self, adgroup_id, keyword):
        if adgroup_id not in self.s["adgroups"]:
            raise NaverApiError("대상 광고그룹이 존재하지 않습니다")
        rid = f"nrk-{self.customer_id}-{len(self.s.setdefault('restricted', {})) + 1}"
        self.s["restricted"][rid] = {"nccAdgroupRestrictKwdId": rid, "nccAdgroupId": adgroup_id, "keyword": keyword, "type": "KEYWORD_PLUS_RESTRICT"}
        return dict(self.s["restricted"][rid])

    def delete_restricted_keyword(self, adgroup_id, kwd_id):
        k = self.s.setdefault("restricted", {}).get(kwd_id)
        if k is None or k["nccAdgroupId"] != adgroup_id:
            raise NaverApiError("대상 제외검색어가 존재하지 않습니다")
        del self.s["restricted"][kwd_id]

    def create_master_report(self, item):
        return {"id": f"mock-{item}", "item": item, "status": "REGIST"}

    def get_master_report(self, job_id):
        return {"id": job_id, "item": job_id.removeprefix("mock-"), "status": "BUILT", "downloadUrl": "mock"}

    def delete_master_report(self, job_id):
        pass

    def master_file(self, job) -> dict:
        """실계정 파일과 같은 칸 구성(헤더 없는 TSV)."""
        s, cid = self.s, self.customer_id
        lock = lambda o: "1" if o.get("userLock") else "0"  # noqa: E731
        ad_types = {"Ad": "TEXT_45", "RsaAd": "RSA_AD", "ShoppingProduct": "SHOPPING_PRODUCT_AD"}
        item = job["item"]
        if item == "Keyword":
            rows = [[cid, k["nccAdgroupId"], k["nccKeywordId"], k["keyword"], str(k["bidAmt"]), "", "", lock(k), "10",
                     "1" if k.get("useGroupBidAmt") else "0", "2026-07-01T00:00:00Z", "", ""] for k in s["keywords"].values()]
        elif item == "Adgroup":
            rows = [[cid, g["nccAdgroupId"], g["nccCampaignId"], g["name"], str(g["bidAmt"]), lock(g)] + [""] * 13
                    for g in s["adgroups"].values()]
        elif item in ad_types:
            rows = [[cid, a["nccAdgroupId"], a["nccAdId"], "10", "", "", lock(a), "", ""]
                    for a in s["ads"].values() if a["type"] == ad_types[item]]
        elif item == "AdExtension":
            rows = [[cid, e["nccAdExtensionId"], "8", e["ownerId"]] + [""] * 13 for e in s.get("ad-extensions", {}).values()]
        else:
            rows = []
        return {"text": "\n".join("\t".join(r) for r in rows)}

    def get_many(self, kind, ids):
        return [dict(self.s[kind][i]) for i in ids if i in self.s.get(kind, {})]

    def keyword_tool(self, hints):
        r = random.Random(",".join(hints))
        return [_kwd_stat({"relKeyword": f"{h}{s}", "monthlyPcQcCnt": str(r.randint(0, 5000)) if s else "< 10",
                           "monthlyMobileQcCnt": str(r.randint(0, 20000)), "compIdx": r.choice(["낮음", "중간", "높음"])})
                for h in hints for s in ("", " 추천", " 가격", " 후기", " 할인")]

    def delete_keyword(self, keyword_id):
        if keyword_id in MOCK_FAIL_IDS or self.s["keywords"].pop(keyword_id, None) is None:
            raise NaverApiError("대상 키워드가 존재하지 않습니다")

    def delete_container(self, entity_type, naver_id):
        obj = self.s[CONTAINER_RES[entity_type]].get(naver_id)
        if obj is None:
            raise NaverApiError("대상 객체가 존재하지 않습니다")
        if not obj.get("userLock"):
            raise NaverApiError(ON_NOT_DELETABLE)
        groups = {naver_id} if entity_type == "adgroup" else {g for g, x in self.s["adgroups"].items() if x["nccCampaignId"] == naver_id}
        for kind in ("keywords", "ads"):  # 네이버처럼 안의 키워드·소재도 같이 지운다
            for k in [k for k, x in self.s[kind].items() if x["nccAdgroupId"] in groups]:
                del self.s[kind][k]
        for g in groups:
            self.s["adgroups"].pop(g, None)
        self.s["campaigns"].pop(naver_id, None)

    def delete_ad(self, ad_id):
        if self.s["ads"].pop(ad_id, None) is None:
            raise NaverApiError("대상 소재가 존재하지 않습니다")

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

    def entity_stats(self, ids, since: date, until: date) -> dict:
        out = {}
        for i in ids:
            if i in MOCK_FAIL_IDS:
                raise NaverApiError("통계 조회 실패")
            r = random.Random(f"{i}{since}{until}")
            imp = r.randint(0, 3000)
            clk = imp * r.randint(0, 5) // 100
            out[i] = {"id": i, "impCnt": imp, "clkCnt": clk, "salesAmt": clk * r.randint(200, 800), "ccnt": clk // 20,
                      "convAmt": clk // 20 * 30000, "avgRnk": round(r.uniform(1, 8), 1)}
        return out

    def create_ad(self, adgroup_id, ad_type, ad, assets):
        if adgroup_id not in self.s["adgroups"]:
            raise NaverApiError("광고그룹이 없습니다")
        aid = f"nad-{self.customer_id}-{len(self.s['ads']) + 1}"
        self.s["ads"][aid] = {"nccAdId": aid, "nccAdgroupId": adgroup_id, "type": ad_type, "userLock": True,
                              "inspectStatus": "UNDER_REVIEW", "ad": ad, **({"assets": assets} if assets else {})}
        return dict(self.s["ads"][aid])

    def serp_ads(self, keyword, device):
        # 경쟁 광고 입찰가가 MOCK_RIVALS인 가상 화면: 입찰가 높은 순, 같으면 경쟁 광고가 먼저
        ads = [(-self._bid(k), a["nccAdId"]) for k in self.s["keywords"].values() if k["keyword"] == keyword and not k["userLock"]
               for a in self.s["ads"].values() if a["nccAdgroupId"] == k["nccAdgroupId"]]
        return [i for _, i in sorted([(-b, f"nad-rival-{b}") for b in MOCK_RIVALS] + ads, key=lambda x: x[0])]

    def _bid(self, k):
        return self.s["adgroups"][k["nccAdgroupId"]]["bidAmt"] if k["useGroupBidAmt"] else k["bidAmt"]

    def update(self, entity_type, naver_id, field, value, expect=None):
        if naver_id in MOCK_FAIL_IDS:
            raise NaverApiError("Mock API 오류: 요청이 거부되었습니다")
        res, _, apply = UPDATE_SPEC[(entity_type, field)]
        obj = self.s[res].get(naver_id)
        if obj is None:
            raise NaverApiError("대상 객체가 존재하지 않습니다")
        _check_expected(field, obj, expect)
        apply(obj, value)


def client_for(credential, customer_id: str, decrypt):
    if credential.is_mock:
        return MockNaverClient(customer_id.rpartition("-")[2])  # 저장된 Mock 번호는 mock{조직}-{번호}
    return RealNaverClient(credential.api_key, decrypt(credential.secret_key_enc), customer_id)
