"""구글 광고 API를 Claude 도구로(작업정리 28번). 기능마다 도구를 만들지 않고 구글 API 모양 그대로 받는다:
GAQL 조회 하나로 모든 보고서, googleAds:mutate 하나로 모든 수정·등록(캠페인 생성·키워드·광고·확장·타기팅·입찰 전략),
그 밖에 키워드 플래너·잠재고객 인사이트·광고 미리보기·새 캠페인 추천·추천 적용·오프라인 전환 업로드·고객 목록 업로드.
안전장치(네이버와 같은 생각): validate_only로 구글 검사 → 채팅 표 → 허용 버튼으로 실행. 실행 때 서버가 다시 막는다:
- 하루예산을 늘릴 수 있는 변경(캠페인 켜기, PAUSED 아닌 캠페인 만들기, 예산 올리기, 캠페인 예산 바꿔 끼우기, 예산 추천 적용)
  shortcut: 구글엔 웹 승인 흐름이 없어 아예 막고 구글 광고 화면에서 하게 한다, 필요해지면 approvals.py에 구글 종류 추가
- 클릭당 입찰가는 연결마다 정한 최대 입찰가 이하(정하기 전엔 변경 못 함)
  shortcut: 기본 입찰가만 본다(기기·지역 입찰 조정 배율로 넘을 수 있음, CPM·CPV 입찰은 안 봄), 문제가 되면 bidModifier 상한 추가"""
import hashlib
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .access import ADMIN_ROLES
from .channels import ChannelError, google_customer_id, google_headers, google_post, google_search
from .models import AuditLog, ChannelConnection, Membership
from .security import decrypt

ROWS = 200  # 조회 결과는 앞 200행만(Claude 답 길이)
BID_KEYS = ("cpcBidMicros", "cpcBidCeilingMicros")
BUDGET_NAME = re.compile(r"customers/\d+/campaignBudgets/\d+")
REC_NAME = re.compile(r"customers/\d+/recommendations/[\w~-]+")
PATHS = {"mutate": "/googleAds:mutate", "apply_recommendations": "/recommendations:apply", "upload_click_conversions": ":uploadClickConversions"}


def _conn(db: Session, m: Membership, account_id: str) -> ChannelConnection:
    if m.role not in ADMIN_ROLES:
        raise HTTPException(403, "구글 광고 계정은 관리자만 쓸 수 있습니다")
    row = db.scalar(select(ChannelConnection).where(ChannelConnection.workspace_id == m.workspace_id, ChannelConnection.channel == "GOOGLE",
                                                    ChannelConnection.account_id == google_customer_id(account_id)))
    if not row:
        raise HTTPException(404, "연결된 구글 광고 계정이 아닙니다(list_ad_accounts의 other_channels 확인, 관리자가 웹 설정에서 연결)")
    return row


def _api(fn):
    try:
        return fn()
    except ChannelError as e:
        raise HTTPException(400, str(e)) from e


def search_tool(db: Session, m: Membership, a: dict) -> dict:
    c, q = _conn(db, m, a["account_id"]), a["query"].strip()
    if not q.upper().startswith("SELECT"):
        raise HTTPException(400, "GAQL SELECT 문만 됩니다")
    rows = _api(lambda: google_search(decrypt(c.token_enc), c.account_id, c.login_customer_id, q))
    return {"account_id": c.account_id, "rows": len(rows), "results": rows[:ROWS],
            **({"truncated": f"앞 {ROWS}행만 — ORDER BY·LIMIT·WHERE로 좁히세요"} if len(rows) > ROWS else {})}


def keyword_ideas(db: Session, m: Membership, a: dict) -> dict:
    c, kws, url = _conn(db, m, a["account_id"]), [k for k in a.get("keywords") or [] if k.strip()][:20], (a.get("url") or "").strip()
    if not kws and not url:
        raise HTTPException(400, "keywords나 url 중 하나는 넣으세요")
    seed = {"keywordAndUrlSeed": {"keywords": kws, "url": url}} if kws and url else {"keywordSeed": {"keywords": kws}} if kws else {"urlSeed": {"url": url}}
    body = {"language": f"languageConstants/{a.get('language_id') or 1012}",  # 1012 한국어
            "geoTargetConstants": [f"geoTargetConstants/{a.get('geo_id') or 2410}"],  # 2410 대한민국
            "keywordPlanNetwork": "GOOGLE_SEARCH", **seed}
    data = _api(lambda: google_post(f"customers/{c.account_id}:generateKeywordIdeas", body, google_headers(decrypt(c.token_enc), c.login_customer_id)))
    ideas = []
    for x in data.get("results", []):
        mt = x.get("keywordIdeaMetrics") or {}
        ideas.append({"keyword": x.get("text"), "avg_monthly_searches": int(mt.get("avgMonthlySearches") or 0), "competition": mt.get("competition"),
                      "top_bid_low": round(int(mt.get("lowTopOfPageBidMicros") or 0) / 1e6), "top_bid_high": round(int(mt.get("highTopOfPageBidMicros") or 0) / 1e6)})
    ideas.sort(key=lambda r: -r["avg_monthly_searches"])
    return {"account_id": c.account_id, "ideas": ideas[:100]}


INSIGHTS = ("searchAudienceInsightsAttributes", "generateAudienceCompositionInsights", "generateSuggestedTargetingInsights",
            "generateAudienceOverlapInsights", "generateTargetingSuggestionMetrics", "generateInsightsFinderReport")


def audience_insights(db: Session, m: Membership, a: dict) -> dict:
    """AudienceInsightsService(GAQL 밖 조회). 본문은 구글 REST 그대로, customerInsightsGroup(필수 이름표)은 비우면 계정 이름."""
    c, method = _conn(db, m, a["account_id"]), a["method"]
    if method not in INSIGHTS:
        raise HTTPException(400, f"method는 {', '.join(INSIGHTS)} 중 하나")
    return {"method": method, **_read(c, f"customers/{c.account_id}:{method}", {"customerInsightsGroup": c.name, **(a.get("body") or {})})}


def _read(c: ChannelConnection, path: str, body: dict, get: bool = False) -> dict:
    """GAQL 밖 조회 API(광고를 바꾸지 않음)."""
    data = _api(lambda: google_post(path, body, google_headers(decrypt(c.token_enc), c.login_customer_id), get))
    return {"account_id": c.account_id, "result": data}


# 광고를 바꾸지 않는 나머지 API 전부(v26 discovery 문서 기준). 이름: (GET 여부, 주소). {c}=고객 ID, {r}=resource 칸
READS = {
    **{n: (False, f"customers/{{c}}:{n}") for n in (
        "generateKeywordHistoricalMetrics", "generateKeywordForecastMetrics", "generateAdGroupThemes", "generateReachForecast",
        "generateBenchmarksMetrics", "generateCreatorInsights", "generateTrendingInsights", "generateAudienceDefinition", "suggestBrands",
        "suggestKeywordThemes", "suggestSmartCampaignAd", "suggestSmartCampaignBudgetOptions", "suggestTravelAssets", "checkLocalServicesEligibility")},
    **{n: (False, n) for n in (
        "listPlannableLocations", "listPlannableProducts", "listPlannableUserInterests", "listPlannableUserLists", "listBenchmarksAvailableDates",
        "listBenchmarksLocations", "listBenchmarksProducts", "listBenchmarksSources", "generateConversionRates")},
    "quoteCampaigns": (False, "customers/{c}/reservations:quoteCampaigns"),  # 예약 캠페인 견적만(예약은 bookCampaigns)
    "listInsightsEligibleDates": (False, "audienceInsights:listInsightsEligibleDates"),
    "suggestGeoTargetConstants": (False, "geoTargetConstants:suggest"),
    "suggestKeywordThemeConstants": (False, "keywordThemeConstants:suggest"),
    "searchGoogleAdsFields": (False, "googleAdsFields:search"),
    "listInvoices": (True, "customers/{c}/invoices"),
    "listPaymentsAccounts": (True, "customers/{c}/paymentsAccounts"),
    "getIdentityVerification": (True, "customers/{c}/getIdentityVerification"),
    "listAccessibleCustomers": (True, "customers:listAccessibleCustomers"),
    "fetchIncentive": (True, "incentives:fetchIncentive"),
    **{n: (True, f"{{r}}:{n}") for n in ("getSmartCampaignStatus", "listAsyncErrors", "listExperimentAsyncErrors", "listResults")},
    "getOperation": (True, "{r}"),
}


def read_tool(db: Session, m: Membership, a: dict) -> dict:
    c, method, body = _conn(db, m, a["account_id"]), a["method"], dict(a.get("body") or {})
    if method not in READS:
        raise HTTPException(400, f"method는 {', '.join(READS)} 중 하나")
    get, path = READS[method]
    if "{r}" in path:
        r = str(a.get("resource_name") or "")
        if not re.fullmatch(rf"customers/{c.account_id}/[\w~/-]+", r) or ".." in r:
            raise HTTPException(400, f"resource_name은 customers/{c.account_id}/… 모양(이 계정 것만)")
        path = path.replace("{r}", r)
    return {"method": method, **_read(c, path.replace("{c}", c.account_id), body, get)}


def previews(db: Session, m: Membership, a: dict) -> dict:
    c, ids = _conn(db, m, a["account_id"]), [str(x) for x in a["asset_group_ids"]][:20]
    if not ids or not all(x.isdigit() for x in ids):
        raise HTTPException(400, "asset_group_ids는 PMax 애셋 그룹 ID(숫자) 목록")
    return _read(c, f"customers/{c.account_id}:generateShareablePreviews", {"shareablePreviews": [{"assetGroupIdentifier": {"assetGroupId": x}} for x in ids]})


def generate_recommendations(db: Session, m: Membership, a: dict) -> dict:
    """아직 없는 캠페인에 대한 구글 추천(예산·키워드·입찰 전략·사이트링크). 받기만 하고 적용하지 않는다."""
    c, body = _conn(db, m, a["account_id"]), dict(a.get("body") or {})
    if not body.get("recommendationTypes") or body.get("advertisingChannelType") not in ("SEARCH", "PERFORMANCE_MAX"):
        raise HTTPException(400, "body에 recommendationTypes와 advertisingChannelType(SEARCH 또는 PERFORMANCE_MAX)이 필요해요")
    return _read(c, f"customers/{c.account_id}/recommendations:generate", body)


def _bids(o, out: list[int]) -> list[int]:
    if isinstance(o, dict):
        for k, v in o.items():
            if k in BID_KEYS:
                out.append(int(v))
            else:
                _bids(v, out)
    elif isinstance(o, list):
        for v in o:
            _bids(v, out)
    return out


def _check_bids(body: dict, max_bid: int):
    if over := [b for b in _bids(body, []) if b > max_bid * 1_000_000]:
        raise HTTPException(400, f"클릭당 입찰가 {max(over) / 1e6:,.0f}이(가) 이 계정의 최대 입찰가 {max_bid:,}보다 높아요(웹 설정에서 바꿀 수 있음)")


def _camel(o):
    """구글 REST는 칸 이름을 cpc_bid_micros·cpcBidMicros 둘 다 받는다. 검사한 모양 그대로 보내도록 camelCase로 맞춘다(안전장치 우회 방지)."""
    if isinstance(o, dict):
        return {re.sub(r"_([a-z0-9])", lambda x: x.group(1).upper(), k): _camel(v) for k, v in o.items()}
    return [_camel(v) for v in o] if isinstance(o, list) else o


def guard(ops: list[dict], max_bid: int, budgets_now) -> None:
    """하루예산을 늘릴 수 있는 변경을 막는다. budgets_now(이름 목록) → {예산 이름: 지금 amountMicros}."""
    raise_to = {}
    for op in ops:
        if not isinstance(op, dict) or len(op) != 1:
            raise HTTPException(400, "mutateOperations의 각 항목은 {'campaignOperation': {...}}처럼 한 종류만")
        (kind, body), = op.items()
        new = body.get("create") or body.get("update") or {}
        if kind == "campaignOperation" and "create" in body and new.get("status") != "PAUSED":
            raise HTTPException(400, "캠페인은 status: PAUSED로만 만들 수 있어요. 켜기는 구글 광고 화면에서 직접 하세요(하루예산 합계가 늘 수 있는 변경)")
        # 상태는 허용 목록으로(구글은 enum을 숫자로도 받는다: 2 = ENABLED)
        if kind == "campaignOperation" and "update" in body and (new.get("status", "PAUSED") not in ("PAUSED", "REMOVED") or "campaignBudget" in new):
            raise HTTPException(400, "캠페인 켜기·예산 바꿔 끼우기는 구글 광고 화면에서 직접 하세요(하루예산 합계가 늘 수 있는 변경)")
        if kind == "campaignBudgetOperation" and "update" in body and {"amountMicros", "totalAmountMicros"} & set(new):
            if not BUDGET_NAME.fullmatch(str(new.get("resourceName"))):
                raise HTTPException(400, "예산 update에는 resourceName(customers/…/campaignBudgets/…)이 필요해요")
            raise_to[new["resourceName"]] = (int(new.get("amountMicros") or 0), int(new.get("totalAmountMicros") or 0))
    _check_bids(ops, max_bid)
    if raise_to:
        now = budgets_now(list(raise_to))
        if up := [n for n, v in raise_to.items() if n not in now or v[0] > now[n][0] or v[1] > now[n][1]]:
            raise HTTPException(400, f"예산 올리기는 구글 광고 화면에서 직접 하세요(내리기만 됨): {', '.join(up)}")


def change_tool(db: Session, m: Membership, a: dict) -> dict:
    c, action, body = _conn(db, m, a["account_id"]), a["action"], _camel(dict(a.get("body") or {}))
    if action not in PATHS:
        raise HTTPException(400, f"action은 {', '.join(PATHS)} 중 하나")
    if not c.max_bid:
        raise HTTPException(400, "이 구글 계정의 클릭당 최대 입찰가를 웹 설정에서 먼저 정하세요(정하기 전엔 변경 못 함)")
    check, token = a.get("validate_only", True) is not False, decrypt(c.token_enc)
    search = lambda q: _api(lambda: google_search(token, c.account_id, c.login_customer_id, q))  # noqa: E731
    if action == "mutate":
        def budgets_now(names):
            rows = search(f"SELECT campaign_budget.resource_name, campaign_budget.amount_micros, campaign_budget.total_amount_micros FROM campaign_budget "
                          f"WHERE campaign_budget.resource_name IN ({', '.join(repr(n) for n in names)})")
            return {(b := r["campaignBudget"])["resourceName"]: (int(b.get("amountMicros") or 0), int(b.get("totalAmountMicros") or 0)) for r in rows}
        guard(body.get("mutateOperations") or [], c.max_bid, budgets_now)
        body["validateOnly"] = check
    elif action == "apply_recommendations":
        names = [o.get("resourceName") for o in body.get("operations") or []]
        if not names or not all(REC_NAME.fullmatch(str(n)) for n in names):
            raise HTTPException(400, "operations마다 resourceName(customers/…/recommendations/…)이 필요해요")
        _check_bids(body, c.max_bid)
        recs = search("SELECT recommendation.resource_name, recommendation.type, recommendation.campaign, recommendation.impact "
                      f"FROM recommendation WHERE recommendation.resource_name IN ({', '.join(repr(n) for n in names)})")
        if bad := [r["recommendation"]["type"] for r in recs if "BUDGET" in r["recommendation"].get("type", "")]:
            raise HTTPException(400, f"예산 추천({', '.join(bad)})은 구글 광고 화면에서 직접 적용하세요(하루예산 합계가 늘 수 있는 변경)")
        if check:  # 추천 적용엔 구글 검사(validateOnly)가 없어 적용될 추천을 보여 준다
            return {"validate_only": True, "recommendations": recs}
    else:
        body.update(validateOnly=check, partialFailure=True)  # 클릭 전환 업로드는 partialFailure가 필수
    if not check:  # 기록을 먼저 남긴다(요청이 끊겨도 시도는 남게)
        db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, action="GOOGLE_CHANGE", entity_type="google",
                        naver_id=f"GOOGLE:{c.account_id}", field=action[:20], after=f"{len(body.get('mutateOperations') or body.get('operations') or body.get('conversions') or [])}건"))
        db.commit()
    data = _api(lambda: google_post(f"customers/{c.account_id}{PATHS[action]}", body, google_headers(token, c.login_customer_id)))
    return {"validate_only": check, "result": data}


def _email(e: str) -> str:
    return e.strip().lower()


def _phone(p: str) -> str:
    """E.164: 010-1234-5678 → +821012345678 (국내 번호는 한국으로 본다)."""
    d = re.sub(r"[^\d+]", "", p)
    return d if d.startswith("+") else "+82" + d[1:] if d.startswith("0") else "+" + d


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def customer_match(db: Session, m: Membership, a: dict) -> dict:
    """고객 목록(이메일·전화)을 정규화 → SHA-256으로 바꿔 올린다. 원문은 구글에도 서버에도 남기지 않는다."""
    c = _conn(db, m, a["account_id"])
    ids = [{"hashedEmail": _sha(_email(e))} for e in a.get("emails") or [] if "@" in e]
    ids += [{"hashedPhoneNumber": _sha(_phone(p))} for p in a.get("phones") or [] if re.search(r"\d{7}", re.sub(r"\D", "", p))]
    if not ids or len(ids) > 10000:
        raise HTTPException(400, "올바른 이메일·전화번호를 1~10,000개 넣으세요")
    if not str(a["user_list_id"]).isdigit():
        raise HTTPException(400, "user_list_id는 숫자(고객 목록 ID)")
    if a.get("validate_only", True) is not False:
        return {"validate_only": True, "user_list_id": a["user_list_id"], "emails": sum("hashedEmail" in x for x in ids), "phones": sum("hashedPhoneNumber" in x for x in ids)}
    h, cid = google_headers(decrypt(c.token_enc), c.login_customer_id), c.account_id
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, action="GOOGLE_CHANGE", entity_type="google",
                    naver_id=f"GOOGLE:{cid}", field="customer_match", after=f"{len(ids)}건"))
    db.commit()

    def run():
        job = google_post(f"customers/{cid}/offlineUserDataJobs:create", {"job": {"type": "CUSTOMER_MATCH_USER_LIST", "customerMatchUserListMetadata": {
            "userList": f"customers/{cid}/userLists/{a['user_list_id']}"}}}, h)["resourceName"]
        added = google_post(f"{job}:addOperations", {"enablePartialFailure": True, "operations": [{"create": {"userIdentifiers": [x]}} for x in ids]}, h)
        google_post(f"{job}:run", {}, h)
        return {"job": job, "uploaded": len(ids), "partial_failure": added.get("partialFailureError"),
                "note": "구글이 몇 시간에 걸쳐 맞춘다. 상태는 google_ads_search로 offline_user_data_job.status 조회"}
    return _api(run)


ACCOUNT = {"type": "string", "description": "구글 광고 고객 ID(list_ad_accounts의 other_channels, 예: 123-456-7890)"}
CHECK = {"type": "boolean", "description": "기본 true = 구글 검사만(바뀌지 않음). 검사 통과 → 채팅에 표 → false로 실행"}
WS = {"type": "integer", "description": "조직 ID (list_ad_accounts 결과)"}
TOOLS = [
    {"name": "google_ads_search",
     "description": "구글 광고 조회: GAQL(Google Ads Query Language) SELECT 문을 그대로 실행해 결과 행(REST JSON, int64는 문자열, 금액은 micros ÷ 1,000,000)을 돌려준다(앞 200행). "
                    "예: 광고그룹·키워드·광고별 성과(ad_group, keyword_view, ad_group_ad), 검색어 보고서(search_term_view), "
                    "일·시간·요일·기기·지역(segments.date/hour/day_of_week/device, geographic_view), 연령·성별(age_range_view, gender_view), "
                    "품질평가점수(ad_group_criterion.quality_info.*), 노출 점유율(metrics.search_impression_share 등), "
                    "예산 제한(campaign.primary_status_reasons), 광고 승인 거부(ad_group_ad.policy_summary), 변경 기록(change_event, 최근 30일·LIMIT 필수), "
                    "추천사항(recommendation), 전환 액션(conversion_action), 고객 목록(user_list), 자산(asset). 기간 조건은 segments.date BETWEEN 'YYYY-MM-DD' AND '…' 또는 DURING LAST_7_DAYS. "
                    "관리자만, 조회만 한다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "account_id", "query"], "properties": {
         "workspace_id": WS, "account_id": ACCOUNT, "query": {"type": "string", "description": "GAQL SELECT 문"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "google_keyword_ideas",
     "description": "구글 키워드 플래너: 키워드·URL로 추천 키워드와 월 검색량·경쟁도·페이지 상단 입찰가(낮음~높음, 계정 통화) — 검색량 큰 순 100개. 기본 한국어·대한민국. 조회만 한다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "account_id"], "properties": {
         "workspace_id": WS, "account_id": ACCOUNT, "keywords": {"type": "array", "items": {"type": "string"}, "description": "씨앗 키워드(최대 20)"},
         "url": {"type": "string", "description": "씨앗 페이지 주소"}, "language_id": {"type": "integer", "description": "언어 상수 ID(기본 1012 한국어)"},
         "geo_id": {"type": "integer", "description": "지역 상수 ID(기본 2410 대한민국)"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "google_audience_insights",
     "description": "구글 잠재고객 인사이트(AudienceInsightsService). body는 구글 REST 요청 본문 그대로(camelCase). method: "
                    "searchAudienceInsightsAttributes = 관심사·인구통계·주제 등 속성 찾기 {queryText, dimensions: ['AFFINITY_USER_INTEREST', 'IN_MARKET_USER_INTEREST', 'AGE_RANGE', 'GENDER', ...]} — 다른 method에 넣을 속성은 여기서 얻는다; "
                    "generateAudienceCompositionInsights = 이 잠재고객은 어떤 관심사·나이·성별·기기로 이뤄졌나 {audience: {...}, dimensions: [...]}; "
                    "generateSuggestedTargetingInsights = 이 잠재고객에 맞는 타기팅 추천; generateAudienceOverlapInsights = 한 속성과 다른 속성들의 겹침; "
                    "generateTargetingSuggestionMetrics = 타기팅 후보별 도달 가능 규모; generateInsightsFinderReport = 구글 인사이트 파인더 보고서 링크. "
                    "지역은 대개 locations: [{geoTargetConstant: 'geoTargetConstants/2410'}](대한민국). customerInsightsGroup은 비우면 계정 이름. 관리자만, 조회만 한다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "account_id", "method"], "properties": {
         "workspace_id": WS, "account_id": ACCOUNT, "method": {"type": "string", "enum": list(INSIGHTS)},
         "body": {"type": "object", "description": "구글 REST 요청 본문"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "google_ads_read",
     "description": "구글 광고 API 중 GAQL·다른 구글 도구 밖의 조회 전부(광고를 바꾸지 않음). body는 구글 REST 요청 본문 그대로(camelCase, GET은 주소 칸). method: "
                    "키워드 = generateKeywordHistoricalMetrics(정한 키워드의 월별 검색량 추이 {keywords, language, geoTargetConstants}), "
                    "generateKeywordForecastMetrics(예상 노출·클릭·비용 {campaign: {keywordPlanNetwork, biddingStrategy, adGroups: [{biddableKeywords}]}, forecastPeriod}), "
                    "generateAdGroupThemes(키워드를 광고그룹 묶음으로 {keywords, adGroups}); "
                    "도달 계획 = listPlannableLocations, listPlannableProducts{plannableLocationId}, listPlannableUserInterests, listPlannableUserLists, generateReachForecast, "
                    "quoteCampaigns(예약 캠페인 견적만); 벤치마크 = listBenchmarksAvailableDates·Locations·Products·Sources, generateBenchmarksMetrics, generateConversionRates; "
                    "유튜브 = generateCreatorInsights, generateTrendingInsights; 잠재고객 = generateAudienceDefinition, listInsightsEligibleDates; "
                    "찾기·제안 = suggestGeoTargetConstants(지역 이름 → 지역 ID {locale: 'ko', countryCode: 'KR', locationNames: {names: [...]}}), suggestBrands, "
                    "suggestKeywordThemeConstants, suggestKeywordThemes, suggestSmartCampaignAd, suggestSmartCampaignBudgetOptions, suggestTravelAssets, checkLocalServicesEligibility; "
                    "계정·결제 = listAccessibleCustomers(내 로그인으로 볼 수 있는 계정), listInvoices{billingSetup, issueYear, issueMonth}, listPaymentsAccounts, getIdentityVerification, fetchIncentive; "
                    "GAQL 칸 찾기 = searchGoogleAdsFields{query}; 작업 상태(resource_name 필요) = getSmartCampaignStatus, listAsyncErrors, listExperimentAsyncErrors, listResults, getOperation. "
                    "관리자만, 조회만 한다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "account_id", "method"], "properties": {
         "workspace_id": WS, "account_id": ACCOUNT, "method": {"type": "string", "enum": list(READS)},
         "body": {"type": "object", "description": "구글 REST 요청 본문(GET method는 주소 칸)"},
         "resource_name": {"type": "string", "description": "작업 상태 method에서 대상(customers/<ID>/…)"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "google_ad_preview",
     "description": "구글 광고 미리보기 공유 링크(ShareablePreviewService). PMax 애셋 그룹만 된다(반응형 검색·디스플레이 광고는 구글이 지원 안 함). "
                    "애셋 그룹 ID는 google_ads_search로 asset_group.id 조회. 링크는 iframe에 못 넣으니 그대로 알려 준다. 관리자만, 조회만 한다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "account_id", "asset_group_ids"], "properties": {
         "workspace_id": WS, "account_id": ACCOUNT, "asset_group_ids": {"type": "array", "items": {"type": "string"}, "description": "PMax 애셋 그룹 ID(최대 20)"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "google_generate_recommendations",
     "description": "만들기 전 캠페인에 대한 구글 추천(RecommendationService.GenerateRecommendations). body는 구글 REST 요청 본문 그대로(camelCase): "
                    "recommendationTypes(CAMPAIGN_BUDGET, KEYWORD, MAXIMIZE_CLICKS_OPT_IN, MAXIMIZE_CONVERSIONS_OPT_IN, MAXIMIZE_CONVERSION_VALUE_OPT_IN, "
                    "SET_TARGET_CPA, SET_TARGET_ROAS, SITELINK_ASSET, TARGET_CPA_OPT_IN, TARGET_ROAS_OPT_IN), advertisingChannelType(SEARCH·PERFORMANCE_MAX) 필수, "
                    "선택: seedInfo{urlSeed, keywordSeeds}, budgetInfo{currentBudget}, biddingInfo, conversionTrackingStatus, countryCodes['KR'], languageCodes['ko'], "
                    "positiveLocationsIds, adGroupInfo, assetGroupInfo, campaignSitelinkCount. 정보가 부족하거나 이미 추천 상태면 그 종류는 결과가 없다. "
                    "받기만 하고 적용하지 않는다(만들기는 google_ads_change). 관리자만.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "account_id", "body"], "properties": {
         "workspace_id": WS, "account_id": ACCOUNT, "body": {"type": "object", "description": "구글 REST 요청 본문"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "google_ads_change",
     "description": "구글 광고 수정·등록. body는 구글 광고 REST API 요청 본문 그대로(camelCase). action: "
                    "mutate = googleAds:mutate의 {mutateOperations: [...]} — 켜기/끄기(status), 입찰가(cpcBidMicros), 예산 내리기, 입찰 전략, 키워드·제외 키워드(adGroupCriterion·campaignCriterion), "
                    "반응형 검색광고(adGroupAd), 사이트링크·콜아웃·전화(asset + campaignAsset/adGroupAsset), 타기팅(지역·요일 시간·기기·잠재고객 criterion), "
                    "캠페인 생성(검색·디스플레이·PMax·쇼핑·동영상, 임시 ID -1·-2로 예산·캠페인·광고그룹을 한 번에, campaign.status는 PAUSED), 고객 목록 만들기(userList). 한 요청은 전부 되거나 전부 안 된다. "
                    "apply_recommendations = recommendations:apply의 {operations: [{resourceName}]}; upload_click_conversions = {conversions: [{gclid, conversionAction, conversionDateTime: 'YYYY-MM-DD hh:mm:ss+09:00', conversionValue, currencyCode}]}. "
                    "순서: validate_only=true로 구글 검사 → 바뀔 내용(대상·지금 값 → 바뀔 값, 입찰가, 문구)을 채팅 표로 → validate_only=false로 실행. "
                    "서버가 막는 것: 캠페인 켜기·PAUSED 아닌 캠페인 만들기·예산 올리기·캠페인 예산 바꿔 끼우기·예산 추천 적용(구글 광고 화면에서 직접 하라고 안내), 최대 입찰가 넘는 클릭당 입찰가. "
                    "오류 문구에 구글이 알려 준 칸별 이유가 있으니 고쳐 다시 검사한다. 관리자만.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "account_id", "action", "body"], "properties": {
         "workspace_id": WS, "account_id": ACCOUNT, "action": {"type": "string", "enum": list(PATHS)},
         "body": {"type": "object", "description": "구글 광고 REST 요청 본문(validateOnly는 서버가 넣는다)"}, "validate_only": CHECK}},
     "annotations": {"destructiveHint": True}},
    {"name": "google_customer_match",
     "description": "구글 고객 목록(Customer Match)에 이메일·전화번호를 올린다. 서버가 정규화(소문자, 전화는 +82 형식) 후 SHA-256으로 바꿔 보내고 원문은 남기지 않는다. "
                    "고객 목록은 먼저 google_ads_change(mutate, userListOperation create crmBasedUserList)로 만든다. 고객에게 광고 활용 동의를 받은 목록만. "
                    "validate_only=true면 개수만 센다. 관리자만.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "account_id", "user_list_id"], "properties": {
         "workspace_id": WS, "account_id": ACCOUNT, "user_list_id": {"type": "string", "description": "고객 목록 ID(숫자)"},
         "emails": {"type": "array", "items": {"type": "string"}}, "phones": {"type": "array", "items": {"type": "string"}}, "validate_only": CHECK}},
     "annotations": {"destructiveHint": True}},
]
CALLS = {"google_ads_search": search_tool, "google_keyword_ideas": keyword_ideas, "google_audience_insights": audience_insights, "google_ad_preview": previews, "google_ads_read": read_tool,
         "google_generate_recommendations": generate_recommendations, "google_ads_change": change_tool, "google_customer_match": customer_match}
