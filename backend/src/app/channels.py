"""메타·구글 광고 계정 연결과 네이버와 나란히 보는 성과 조회. 구글 수정·등록은 google_ads.py.
질문마다 각 매체 API를 바로 부르고 서버에 쌓지 않는다(무료 플랜·서버 DB에 광고 데이터 안 둠).
- 메타: 비즈니스 관리자 시스템 사용자 토큰 + 광고계정 ID를 설정 화면에 붙여넣기(ads_read 권한)
- 구글: 설정 화면에서 Google로 adwords 범위 동의 → 갱신 토큰 저장. 개발자 토큰은 Worker 시크릿 GOOGLE_ADS_DEVELOPER_TOKEN"""
import json
import os
import re
from datetime import date, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .access import ADMIN_ROLES, admin_membership
from .db import get_db
from .models import AuditLog, ChannelConnection, Membership, today_kst
from .security import decrypt, encrypt

router = APIRouter()
META_API = "https://graph.facebook.com/v27.0"  # 2026-11-04 출시, 약 2년 지원
GOOGLE_ADS_API = "https://googleads.googleapis.com/v26"  # 2026-10-14 출시, 약 1년 지원
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
# 메타 구매 전환: 앞에 있는 것 하나만 쓴다(omni_purchase가 웹·앱·오프라인 구매를 합친 값이라 나머지와 겹침)
META_PURCHASE = ("omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase")
NOTES = ["비용: 메타·구글은 VAT 별도, 네이버는 동기화된 성과 통계 기준(대용량 보고서 비용은 VAT 포함으로 확인됨) — 정확히 비교하려면 VAT 차이를 감안",
         "전환: 매체마다 기준이 다름(메타 기본 클릭 7일·조회 1일, 구글은 전환 액션 설정의 기간, 네이버는 네이버 전환 추적) — 같은 주문이 여러 매체에 잡힐 수 있음",
         "네이버는 마지막 동기화까지의 값, 메타·구글은 지금 조회한 값"]


class ChannelError(Exception):
    pass


def _ws_rows(db: Session, ws_id: int) -> list[ChannelConnection]:
    return list(db.scalars(select(ChannelConnection).where(ChannelConnection.workspace_id == ws_id).order_by(ChannelConnection.id)))


def visible(db: Session, m: Membership) -> list[dict]:
    # shortcut: 메타·구글 계정은 담당 계정 배정(AccountAccess)이 없어 관리자만 본다, 직원에게 보여 줄 일이 생기면 배정 표에 매체 칸 추가
    if m.role not in ADMIN_ROLES:
        return []
    return [{"id": c.id, "channel": c.channel, "account_id": c.account_id, "name": c.name, "login_customer_id": c.login_customer_id,
             "max_bid": c.max_bid} for c in _ws_rows(db, m.workspace_id)]


# ---------- 메타 ----------
def _meta_get(path: str, token: str, params: dict | None = None, post: bool = False) -> dict:
    try:
        r = (httpx.post if post else httpx.get)(META_API + path, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=20)
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ChannelError(f"메타 API 호출 실패: {e}") from e
    if r.status_code >= 400 or "error" in data:
        err = data.get("error") or {}
        hint = " (토큰이 만료·취소됨 — 설정에서 다시 연결)" if err.get("code") == 190 else ""
        raise ChannelError(f"메타 API 오류: {err.get('message') or r.status_code}{hint}")
    return data


def meta_account(token: str, account_id: str) -> dict:
    return _meta_get(f"/act_{account_id}", token, {"fields": "name,currency,account_status"})


def meta_campaigns(token: str, account_id: str, since: date, until: date) -> list[dict]:
    params = {"level": "campaign", "fields": "campaign_id,campaign_name,impressions,clicks,spend,actions,action_values,account_currency",
              "time_range": json.dumps({"since": since.isoformat(), "until": until.isoformat()}), "limit": 500}
    data, rows = _meta_get(f"/act_{account_id}/insights", token, params), []
    for _ in range(20):  # 캠페인 1만 개까지(요청당 외부 호출 한도 안에서)
        for x in data.get("data", []):
            acts = {a["action_type"]: a["value"] for a in x.get("actions") or []}
            vals = {a["action_type"]: a["value"] for a in x.get("action_values") or []}
            kind = next((k for k in META_PURCHASE if k in acts), None)
            rows.append({"campaign_id": x["campaign_id"], "campaign_name": x.get("campaign_name"), "impressions": int(x.get("impressions") or 0),
                         "clicks": int(x.get("clicks") or 0), "cost": round(float(x.get("spend") or 0)), "currency": x.get("account_currency"),
                         "conversions": round(float(acts[kind]), 2) if kind else 0, "revenue": round(float(vals.get(kind) or 0)) if kind else 0})
        nxt = (data.get("paging") or {}).get("cursors", {}).get("after") if (data.get("paging") or {}).get("next") else None
        if not nxt:
            break
        data = _meta_get(f"/act_{account_id}/insights", token, {**params, "after": nxt})
    return rows


# ---------- 구글 ----------
def google_access_token(refresh_token: str) -> str:
    try:
        r = httpx.post(GOOGLE_TOKEN, data={"grant_type": "refresh_token", "refresh_token": refresh_token,
                                           "client_id": os.getenv("GOOGLE_CLIENT_ID", ""), "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", "")}, timeout=15)
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ChannelError(f"구글 로그인 갱신 실패: {e}") from e
    if "access_token" not in data:
        raise ChannelError("구글 연결이 끊겼습니다(권한 취소·만료) — 설정에서 다시 연결하세요")
    return data["access_token"]


def google_search(refresh_token: str, customer_id: str, login_customer_id: str | None, query: str) -> list[dict]:
    return google_searches(refresh_token, customer_id, login_customer_id, [query])[0]


def google_headers(refresh_token: str, login_customer_id: str | None) -> dict:
    dev = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    if not dev:
        raise ChannelError("서버에 구글 광고 개발자 토큰(GOOGLE_ADS_DEVELOPER_TOKEN)이 없습니다(관리자 확인 필요)")
    headers = {"Authorization": f"Bearer {google_access_token(refresh_token)}", "developer-token": dev}
    if login_customer_id:
        headers["login-customer-id"] = login_customer_id
    return headers


def google_post(path: str, body: dict, headers: dict, get: bool = False) -> dict:
    """path: 'customers/123/googleAds:search' 같은 API 주소 뒷부분(get이면 body를 주소 칸으로). 오류는 구글이 준 칸별 이유까지 붙여 돌려준다(Claude가 고쳐 다시 보낼 수 있게)."""
    try:
        r = (httpx.get(f"{GOOGLE_ADS_API}/{path}", params=body, headers=headers, timeout=30) if get
             else httpx.post(f"{GOOGLE_ADS_API}/{path}", json=body, headers=headers, timeout=30))
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ChannelError(f"구글 광고 API 호출 실패: {e}") from e
    if r.status_code >= 400:
        err = (data[0] if isinstance(data, list) else data).get("error") or {}  # 오류는 배열로 올 때가 있다
        why = [x.get("message") for d in err.get("details") or [] for x in d.get("errors") or [] if x.get("message")]
        raise ChannelError(f"구글 광고 API 오류: {err.get('message') or r.status_code}" + (f" — {'; '.join(why[:10])}" if why else ""))
    return data


def google_searches(refresh_token: str, customer_id: str, login_customer_id: str | None, queries: list[str]) -> list[list[dict]]:
    """질문 여러 개를 출입증 한 번으로(무료 플랜 요청당 외부 호출 수 한도)."""
    headers = google_headers(refresh_token, login_customer_id)
    out = []
    for query in queries:
        body, rows = {"query": query}, []
        for _ in range(10):  # 한 페이지 1만 행
            data = google_post(f"customers/{customer_id}/googleAds:search", body, headers)
            rows += data.get("results", [])
            if not data.get("nextPageToken"):
                break
            body = {"query": query, "pageToken": data["nextPageToken"]}
        out.append(rows)
    return out


def google_campaigns(refresh_token: str, customer_id: str, login_customer_id: str | None, since: date, until: date) -> list[dict]:
    q = ("SELECT campaign.id, campaign.name, customer.currency_code, metrics.impressions, metrics.clicks, metrics.cost_micros, "
         f"metrics.conversions, metrics.conversions_value FROM campaign WHERE segments.date BETWEEN '{since}' AND '{until}'")
    out = []
    for x in google_search(refresh_token, customer_id, login_customer_id, q):
        mt, c = x.get("metrics", {}), x.get("campaign", {})
        # REST는 int64를 문자열로 준다
        out.append({"campaign_id": str(c.get("id")), "campaign_name": c.get("name"), "impressions": int(mt.get("impressions") or 0),
                    "clicks": int(mt.get("clicks") or 0), "cost": round(int(mt.get("costMicros") or 0) / 1e6),
                    "currency": x.get("customer", {}).get("currencyCode"), "conversions": round(float(mt.get("conversions") or 0), 2),
                    "revenue": round(float(mt.get("conversionsValue") or 0))})
    return out


def google_customer_name(refresh_token: str, customer_id: str, login_customer_id: str | None) -> str:
    rows = google_search(refresh_token, customer_id, login_customer_id, "SELECT customer.descriptive_name FROM customer LIMIT 1")
    return (rows[0].get("customer", {}).get("descriptiveName") if rows else None) or customer_id


def google_customer_id(s: str | None) -> str | None:
    """'123-456-7890' → '1234567890'. 형식이 틀리면 ValueError."""
    if not s:
        return None
    d = re.sub(r"[\s-]", "", s)
    if not re.fullmatch(r"\d{10}", d):
        raise ValueError("구글 광고 고객 ID는 숫자 10자리입니다(예: 123-456-7890)")
    return d


def google_connect_done(db: Session, ga: dict, token_response: dict, back: str) -> RedirectResponse:
    """Google 동의 뒤(main.google_callback): 갱신 토큰으로 계정 접근을 확인하고 저장한다. 결과는 #google_ads=linked 또는 #ads_error=…(내 계정의 Google 로그인 연결 결과와 섞이지 않게)"""
    rt = token_response.get("refresh_token")
    if not rt or GOOGLE_ADS_SCOPE not in (token_response.get("scope") or ""):
        return RedirectResponse(back + "#" + urlencode({"ads_error": "구글 광고 권한을 받지 못했습니다. 동의 화면에서 Google Ads 권한을 허용해 주세요"}), 302)
    try:
        name = google_customer_name(rt, ga["c"], ga.get("lc"))
        _save(db, ga["w"], ga["u"], "GOOGLE", ga["c"], name, rt, ga.get("lc"))
    except (ChannelError, HTTPException) as e:
        return RedirectResponse(back + "#" + urlencode({"ads_error": str(getattr(e, "detail", e))}), 302)
    return RedirectResponse(back + "#google_ads=linked", 302)


CONV_METRICS = "metrics.conversions, metrics.conversions_value, metrics.all_conversions, metrics.all_conversions_value"


def _conv(mt: dict) -> dict:
    return {"conversions": round(float(mt.get("conversions") or 0), 2), "conversions_value": round(float(mt.get("conversionsValue") or 0)),
            "all_conversions": round(float(mt.get("allConversions") or 0), 2), "all_conversions_value": round(float(mt.get("allConversionsValue") or 0))}


def google_conversions(refresh_token: str, customer_id: str, login_customer_id: str | None, since: date, until: date) -> dict:
    """전환 액션 설정 + 기간 안 액션별 실적(마지막으로 전환이 잡힌 날) + 캠페인 × 액션별 실적."""
    within = f"segments.date BETWEEN '{since}' AND '{until}'"
    actions, by_day, by_campaign = google_searches(refresh_token, customer_id, login_customer_id, [
        "SELECT conversion_action.resource_name, conversion_action.id, conversion_action.name, conversion_action.category, "
        "conversion_action.status, conversion_action.type, conversion_action.counting_type, conversion_action.include_in_conversions_metric, "
        "conversion_action.click_through_lookback_window_days, conversion_action.view_through_lookback_window_days "
        "FROM conversion_action WHERE conversion_action.status != 'REMOVED'",
        f"SELECT segments.conversion_action, segments.date, {CONV_METRICS} FROM customer WHERE {within}",
        f"SELECT campaign.id, campaign.name, segments.conversion_action_name, {CONV_METRICS} FROM campaign WHERE {within}"])
    out = {}
    for x in actions:
        a = x.get("conversionAction", {})
        out[a.get("resourceName")] = {
            "id": str(a.get("id")), "name": a.get("name"), "category": a.get("category"), "status": a.get("status"), "type": a.get("type"),
            "counting_type": a.get("countingType"), "in_conversions": a.get("includeInConversionsMetric"),
            "click_lookback_days": a.get("clickThroughLookbackWindowDays"), "view_lookback_days": a.get("viewThroughLookbackWindowDays"),
            **dict.fromkeys(("conversions", "conversions_value", "all_conversions", "all_conversions_value"), 0), "last_conversion_date": None}
    for x in by_day:  # 전환이 0인 날은 행이 오지 않는다
        seg = x.get("segments", {})
        a = out.get(seg.get("conversionAction"))
        if not a:  # 삭제된 액션의 예전 전환은 빼고 본다
            continue
        for k, v in _conv(x.get("metrics", {})).items():
            a[k] = round(a[k] + v, 2)
        if seg.get("date") and (not a["last_conversion_date"] or seg["date"] > a["last_conversion_date"]):
            a["last_conversion_date"] = seg["date"]
    campaigns = [{"campaign_id": str(x.get("campaign", {}).get("id")), "campaign_name": x.get("campaign", {}).get("name"),
                  "action": x.get("segments", {}).get("conversionActionName"), **_conv(x.get("metrics", {}))} for x in by_campaign]
    campaigns.sort(key=lambda r: -r["all_conversions"])
    return {"actions": list(out.values()), "campaigns": campaigns[:100]}


CONVERSION_NOTES = ["conversions(전환수)는 '전환에 포함'(in_conversions=true)인 액션만, all_conversions(모든 전환)는 전부 — 입찰·ROAS는 conversions 기준",
                    "기간 안에 전환이 하나도 없으면 last_conversion_date가 null: 태그 문제인지 그냥 전환이 없었는지는 구글 광고 화면의 진단에서 확인",
                    "전환은 클릭한 날 기준으로 잡혀, 최근 며칠 값은 집계 기간(click_lookback_days) 동안 늘어날 수 있음"]


def conversions_tool(db: Session, m: Membership, account_id: str | None, since: date, until: date) -> dict:
    want = google_customer_id(account_id)
    conns = [c for c in (_ws_rows(db, m.workspace_id) if m.role in ADMIN_ROLES else [])
             if c.channel == "GOOGLE" and (not want or c.account_id == want)]
    if not conns:
        raise HTTPException(404, "연결된 구글 광고 계정이 없습니다(관리자가 웹 설정에서 연결, 관리자만 조회)")
    accounts = []
    for c in conns:
        base = {"account_id": c.account_id, "name": c.name}
        try:
            accounts.append({**base, **google_conversions(decrypt(c.token_enc), c.account_id, c.login_customer_id, since, until)})
        except ChannelError as e:
            accounts.append({**base, "error": str(e)})
    return {"since": since.isoformat(), "until": until.isoformat(), "accounts": accounts, "notes": CONVERSION_NOTES}


# ---------- 저장·화면 ----------
def _save(db: Session, ws_id: int, user_id: int, channel: str, account_id: str, name: str, token: str, login_cid: str | None = None):
    try:
        enc = encrypt(token)
    except RuntimeError as e:
        raise HTTPException(503, f"서버 설정이 끝나지 않아 토큰을 저장할 수 없습니다(관리자 확인 필요): {e}") from e
    row = db.scalar(select(ChannelConnection).where(ChannelConnection.workspace_id == ws_id, ChannelConnection.channel == channel,
                                                    ChannelConnection.account_id == account_id))
    if row:  # 같은 계정을 다시 연결하면 토큰만 바꾼다(토큰 만료·재발급)
        row.name, row.token_enc, row.login_customer_id, row.connected_by = name, enc, login_cid, user_id
    else:
        row = ChannelConnection(workspace_id=ws_id, channel=channel, account_id=account_id, name=name[:200], token_enc=enc,
                                login_customer_id=login_cid, connected_by=user_id)
        db.add(row)
    db.add(AuditLog(workspace_id=ws_id, user_id=user_id, action="CHANNEL_CONNECT", field=channel.lower(), naver_id=f"{channel}:{account_id}"))
    try:
        db.commit()
    except IntegrityError:  # 같은 계정을 동시에 두 번 연결
        db.rollback()
        raise HTTPException(409, "이미 연결 중인 계정입니다. 잠시 후 다시 확인하세요") from None
    return row


class MetaIn(BaseModel):
    ad_account_id: str
    access_token: str


@router.get("/workspaces/{ws_id}/channels")
async def list_channels(m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    return visible(db, m)  # 토큰은 반환하지 않는다


@router.post("/workspaces/{ws_id}/channels/meta")
async def connect_meta(body: MetaIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    acc, token = body.ad_account_id.strip().removeprefix("act_"), body.access_token.strip()
    if not acc.isdigit() or not token:
        raise HTTPException(400, "메타 광고계정 ID(숫자, act_ 뒤의 번호)와 토큰을 입력하세요")
    try:
        info = meta_account(token, acc)  # 이 토큰으로 이 계정을 실제로 볼 수 있는지 확인
    except ChannelError as e:
        raise HTTPException(400, f"메타 광고계정 접근 확인 실패: {e}") from e
    row = _save(db, m.workspace_id, m.user_id, "META", acc, info.get("name") or acc, token)
    return {"id": row.id, "channel": "META", "account_id": acc, "name": row.name}


class MaxBidIn(BaseModel):
    max_bid: int


@router.put("/workspaces/{ws_id}/channels/{conn_id}/max-bid")
async def set_max_bid(conn_id: int, body: MaxBidIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    """구글 광고 변경 도구(google_ads.py)의 클릭당 최대 입찰가(계정 통화 단위). 정하기 전엔 변경 도구를 못 쓴다."""
    row = db.get(ChannelConnection, conn_id)
    if not row or row.workspace_id != m.workspace_id:
        raise HTTPException(404, "연결을 찾을 수 없습니다")
    if body.max_bid <= 0:
        raise HTTPException(400, "최대 입찰가는 0보다 커야 합니다")
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, action="UPDATE", entity_type="channel", field="max_bid",
                    naver_id=f"{row.channel}:{row.account_id}", before=str(row.max_bid), after=str(body.max_bid)))
    row.max_bid = body.max_bid
    db.commit()
    return {"ok": True}


@router.delete("/workspaces/{ws_id}/channels/{conn_id}")
async def disconnect(conn_id: int, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    row = db.get(ChannelConnection, conn_id)
    if not row or row.workspace_id != m.workspace_id:
        raise HTTPException(404, "연결을 찾을 수 없습니다")
    db.delete(row)  # 토큰은 지운다(메타·구글 쪽 권한 취소는 각 매체에서)
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, action="CHANNEL_DISCONNECT", field=row.channel.lower(),
                    naver_id=f"{row.channel}:{row.account_id}"))
    db.commit()
    return {"ok": True}


# ---------- 통합 성과(MCP) ----------
def _perf(imp, clk, cost, conv, rev) -> dict:
    return {"impressions": imp, "clicks": clk, "cost": cost, "conversions": conv, "revenue": rev,
            "ctr": round(clk / imp * 100, 2) if imp else None, "cpc": round(cost / clk) if clk else None,
            "roas": round(rev / cost * 100, 1) if rev is not None and cost else None}


def cross_performance(db: Session, m: Membership, naver_rows: list[dict], since: date, until: date) -> dict:
    """naver_rows: main.performance_accounts 결과(계정별·상품별). 메타·구글은 연결마다 캠페인 단위로 바로 조회한다.
    한 매체가 실패해도 나머지는 보여 주고, 실패한 계정은 error 칸에 이유를 둔다."""
    accounts, campaigns = [], []
    for a in naver_rows:
        parts = [p for p in (a.get("WEB_SITE"), a.get("SHOPPING"), a.get("PLACE")) if p]
        conv = [p["conversions"] for p in parts if p["conversions"] is not None]
        rev = [p["revenue"] for p in parts if p["revenue"] is not None]
        accounts.append({"channel": "NAVER", "account_id": str(a["ad_account_id"]), "name": a["name"], "currency": "KRW",
                         **_perf(sum(p["impressions"] for p in parts), sum(p["clicks"] for p in parts), sum(p["cost"] for p in parts),
                                 sum(conv) if conv else None, sum(rev) if rev else None)})
    for c in _ws_rows(db, m.workspace_id) if m.role in ADMIN_ROLES else []:
        base = {"channel": c.channel, "account_id": c.account_id, "name": c.name}
        try:
            token = decrypt(c.token_enc)
            rows = (meta_campaigns(token, c.account_id, since, until) if c.channel == "META"
                    else google_campaigns(token, c.account_id, c.login_customer_id, since, until))
        except ChannelError as e:
            accounts.append({**base, "error": str(e)})
            continue
        accounts.append({**base, "currency": rows[0]["currency"] if rows else None,
                         **_perf(*(sum(r[k] for r in rows) for k in ("impressions", "clicks", "cost", "conversions", "revenue")))})
        campaigns += [{**base, **{k: r[k] for k in ("campaign_id", "campaign_name", "currency")},
                       **_perf(r["impressions"], r["clicks"], r["cost"], r["conversions"], r["revenue"])} for r in rows]
    campaigns.sort(key=lambda r: -r["cost"])
    notes = NOTES if m.role in ADMIN_ROLES else [*NOTES, "메타·구글 계정은 관리자만 볼 수 있어 네이버만 보여 줍니다"]
    return {"since": since.isoformat(), "until": until.isoformat(), "accounts": accounts, "campaigns": campaigns[:50], "notes": notes}


def period(since: str | None, until: str | None) -> tuple[date, date]:
    u = date.fromisoformat(until) if until else today_kst() - timedelta(days=1)
    s = date.fromisoformat(since) if since else u - timedelta(days=6)
    if s > u or (u - s).days > 92:
        raise HTTPException(400, "기간은 93일 이내")
    return s, u


TOOL = {"name": "get_cross_channel_performance",
        "description": "네이버·메타·구글 광고를 같은 칸(노출·클릭·비용·전환·전환매출·CTR·CPC·ROAS)으로 나란히 비교한다. 기간을 비우면 어제까지 7일(최대 93일). "
                       "accounts는 매체·계정별 합계, campaigns는 메타·구글 캠페인(비용 큰 순 50개, 네이버 캠페인은 get_entity_performance). "
                       "메타·구글 계정은 관리자가 웹 설정에서 연결하고 관리자만 본다. 조회만 한다. "
                       "답할 때 notes의 VAT·전환 기준 차이를 함께 알려 주고, error가 있는 계정은 이유를 전한다.",
        "inputSchema": {"type": "object", "required": ["workspace_id"], "properties": {
            "workspace_id": {"type": "integer", "description": "조직 ID (list_ad_accounts 결과)"},
            "since": {"type": "string", "description": "시작일 YYYY-MM-DD"}, "until": {"type": "string", "description": "종료일 YYYY-MM-DD"}}},
        "annotations": {"readOnlyHint": True}}

CONVERSIONS_TOOL = {
    "name": "get_google_conversions",
    "description": "구글 광고 전환 액션: 설정(이름·종류·상태·전환에 포함 여부·한 번/매번 집계·집계 기간)과 기간 안 액션별 전환수·전환가치·"
                   "마지막으로 전환이 잡힌 날, 캠페인 × 액션별 실적(모든 전환 많은 순 100개). '전환 액션 뭐 있어', '어떤 전환이 많이 잡혀', "
                   "'전환 제대로 잡혀' 같은 질문에. 기간을 비우면 어제까지 7일(최대 93일). 관리자만, 조회만 한다. 답할 때 notes를 함께 알려 준다.",
    "inputSchema": {"type": "object", "required": ["workspace_id"], "properties": {
        "workspace_id": TOOL["inputSchema"]["properties"]["workspace_id"],
        "account_id": {"type": "string", "description": "구글 광고 고객 ID(list_ad_accounts의 other_channels). 비우면 연결된 구글 계정 전부"},
        "since": TOOL["inputSchema"]["properties"]["since"], "until": TOOL["inputSchema"]["properties"]["until"]}},
    "annotations": {"readOnlyHint": True}}
