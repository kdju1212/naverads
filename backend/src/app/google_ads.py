"""구글 광고 API를 Claude 도구로(작업정리 28번). 기능마다 도구를 만들지 않고 구글 API 모양 그대로 받는다:
GAQL 조회 하나로 모든 보고서, googleAds:mutate 하나로 모든 수정·등록(캠페인 생성·키워드·광고·확장·타기팅·입찰 전략),
그 밖에 키워드 플래너·추천 적용·오프라인 전환 업로드·고객 목록 업로드.
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
        if kind == "campaignOperation" and "update" in body and (new.get("status") == "ENABLED" or "campaignBudget" in new):
            raise HTTPException(400, "캠페인 켜기·예산 바꿔 끼우기는 구글 광고 화면에서 직접 하세요(하루예산 합계가 늘 수 있는 변경)")
        if kind == "campaignBudgetOperation" and "update" in body and "amountMicros" in new:
            if not BUDGET_NAME.fullmatch(str(new.get("resourceName"))):
                raise HTTPException(400, "예산 update에는 resourceName(customers/…/campaignBudgets/…)이 필요해요")
            raise_to[new["resourceName"]] = int(new["amountMicros"])
    _check_bids(ops, max_bid)
    if raise_to:
        now = budgets_now(list(raise_to))
        if up := [n for n, v in raise_to.items() if n not in now or v > now[n]]:
            raise HTTPException(400, f"예산 올리기는 구글 광고 화면에서 직접 하세요(내리기만 됨): {', '.join(up)}")


def change_tool(db: Session, m: Membership, a: dict) -> dict:
    c, action, body = _conn(db, m, a["account_id"]), a["action"], dict(a.get("body") or {})
    if action not in PATHS:
        raise HTTPException(400, f"action은 {', '.join(PATHS)} 중 하나")
    if not c.max_bid:
        raise HTTPException(400, "이 구글 계정의 클릭당 최대 입찰가를 웹 설정에서 먼저 정하세요(정하기 전엔 변경 못 함)")
    check, token = a.get("validate_only", True) is not False, decrypt(c.token_enc)
    search = lambda q: _api(lambda: google_search(token, c.account_id, c.login_customer_id, q))  # noqa: E731
    if action == "mutate":
        def budgets_now(names):
            rows = search(f"SELECT campaign_budget.resource_name, campaign_budget.amount_micros FROM campaign_budget "
                          f"WHERE campaign_budget.resource_name IN ({', '.join(repr(n) for n in names)})")
            return {r["campaignBudget"]["resourceName"]: int(r["campaignBudget"].get("amountMicros") or 0) for r in rows}
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
CALLS = {"google_ads_search": search_tool, "google_keyword_ideas": keyword_ideas, "google_ads_change": change_tool, "google_customer_match": customer_match}
