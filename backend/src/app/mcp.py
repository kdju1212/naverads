"""Claude 커넥터(MCP). 사용자는 Claude에 {서버}/mcp 주소만 추가하고, 처음 한 번 이 앱 계정으로 로그인한다(OAuth).
도구는 웹 화면이 쓰는 엔드포인트 함수를 그대로 불러서 권한 검사·감사 로그·검증이 웹과 같다.
MCP SDK 없이 JSON-RPC를 직접 처리한다(Workers 무료 플랜 CPU 한도, 상태 없는 POST만 쓰면 충분)."""
import base64
import hashlib
import html
import json
import secrets
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from . import bulk, main as api
from .access import membership_of, user_from_header
from .db import SessionLocal
from .models import OAuthUsed, User, now
from .naver import _status, ad_row, adgroup_row, extension_row
from .security import make_token, read_payload, sign_payload, verify_password

router = APIRouter()
CODE_TTL = 300
# Claude 연결: 출입증은 짧게(새면 1시간 안에 쓸모없음), 만료되면 Claude가 갱신 토큰으로 알아서 새로 받는다.
# 갱신 토큰은 쓸 때마다 교체되므로, 7일 동안 한 번도 안 쓰면 다시 로그인
ACCESS_TTL = 60 * 60
REFRESH_TTL = 60 * 60 * 24 * 7
# 공개 등록(DCR)이라 아무나 클라이언트를 만들 수 있으므로, 로그인 결과(코드)는 Claude와 내 PC(Claude Code)로만 보낸다
WEB = "https://naverads.djkim0509.workers.dev"  # 약관·방침 링크용 웹 주소
CLAUDE_CALLBACKS = {"https://claude.ai/api/mcp/auth_callback", "https://claude.com/api/mcp/auth_callback"}


def _base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


def _redirect_ok(uri: str) -> bool:
    u = urlparse(uri)
    return uri in CLAUDE_CALLBACKS or (u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1"))


# ---------- OAuth ----------
@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/mcp")
async def protected_resource(request: Request):
    return {"resource": _base(request) + "/mcp", "authorization_servers": [_base(request)]}


@router.get("/.well-known/oauth-authorization-server")
async def authorization_server(request: Request):
    b = _base(request)
    return {"issuer": b, "authorization_endpoint": b + "/oauth/authorize", "token_endpoint": b + "/oauth/token",
            "registration_endpoint": b + "/oauth/register", "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"], "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"]}


@router.post("/oauth/register", status_code=201)
async def register(request: Request):
    body = await request.json()
    uris = body.get("redirect_uris") or []
    if not uris or not all(isinstance(u, str) and _redirect_ok(u) for u in uris):
        return JSONResponse({"error": "invalid_redirect_uri"}, 400)
    # shortcut: 클라이언트를 DB에 저장하지 않고 redirect_uris를 서명해 ID로 쓴다, 클라이언트별 차단이 필요해지면 테이블로
    return {"client_id": sign_payload({"t": "client", "r": uris}), "redirect_uris": uris, "client_name": body.get("client_name"),
            "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"]}


def _auth_params(p) -> tuple[dict | None, str | None]:
    """(인가 요청 값, 오류). 잘못된 클라이언트·주소면 그 주소로 보내지 않고 화면에 오류를 띄운다."""
    keys = ("client_id", "redirect_uri", "code_challenge", "code_challenge_method", "state")
    q = {k: p.get(k) or "" for k in keys}
    client = read_payload(q["client_id"], "client")
    if not client or q["redirect_uri"] not in client["r"]:
        return None, "등록되지 않은 연결 요청입니다. Claude에서 다시 연결해 주세요."
    if q["code_challenge_method"] != "S256" or not q["code_challenge"]:
        return None, "지원하지 않는 로그인 방식입니다(PKCE S256 필요)."
    return q, None


def _login_page(q: dict | None, error: str = "", status: int = 200) -> HTMLResponse:
    e = html.escape
    hidden = "".join(f'<input type="hidden" name="{k}" value="{e(v)}">' for k, v in (q or {}).items())
    target = e(urlparse(q["redirect_uri"]).hostname or "") if q else ""
    form = "" if q is None else f"""
<form method="post">{hidden}
<label>이메일<input name="email" type="email" autocomplete="username" required></label>
<label>비밀번호<input name="password" type="password" autocomplete="current-password" required></label>
<button>로그인하고 연결</button></form>
<a class="google" href="/auth/google/start?{e(urlencode(q))}">Google로 로그인하고 연결</a>
<p class="sub">로그인하면 {target} 의 Claude가 내 권한 안에서 광고 계정을 조회·수정할 수 있습니다.
<a href="{WEB}/terms">이용약관</a> · <a href="{WEB}/privacy">개인정보처리방침</a></p>"""
    err = f'<p class="err" role="alert">{e(error)}</p>' if error else ""
    return HTMLResponse(f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Claude 연결</title>
<style>body{{font-family:system-ui,sans-serif;background:#f6f7f9;color:#111;display:grid;place-items:center;min-height:100vh;margin:0;padding:16px}}
main{{background:#fff;border:1px solid #e3e5e8;border-radius:12px;padding:28px;width:100%;max-width:360px;box-sizing:border-box}}
h1{{font-size:20px;margin:0 0 16px}}label{{display:block;font-size:14px;margin-bottom:12px}}
input:not([type=hidden]){{display:block;width:100%;box-sizing:border-box;margin-top:4px;padding:10px;border:1px solid #c9ccd1;border-radius:8px;font-size:15px}}
button{{width:100%;padding:11px;border:0;border-radius:8px;background:#03c75a;color:#fff;font-size:15px;font-weight:600;cursor:pointer}}
.google{{display:block;margin-top:10px;padding:10px;border:1px solid #c9ccd1;border-radius:8px;text-align:center;color:#111;text-decoration:none;font-size:15px}}
.sub{{font-size:13px;color:#555}}.err{{color:#c62828;font-size:14px}}</style></head>
<body><main><h1>네이버 광고 관리 · Claude 연결</h1>{err}{form}</main></body></html>""", status)


@router.get("/oauth/authorize")
async def authorize_page(request: Request):
    q, err = _auth_params(request.query_params)
    return _login_page(q, err or "", 400 if err else 200)


@router.post("/oauth/authorize")
async def authorize(request: Request):
    form = await request.form()
    q, err = _auth_params(form)
    if err:
        return _login_page(None, err, 400)
    email, ip = str(form.get("email") or ""), request.headers.get("cf-connecting-ip")
    db = SessionLocal()
    try:  # 웹 로그인과 같은 실패 횟수 제한
        if api.login_blocked(db, email, ip):
            return _login_page(q, api.LOGIN_BLOCKED, 429)
        user = api.user_by_email(db, email)
        ok = bool(user) and await verify_password(str(form.get("password") or ""), user.password_hash)
        api.record_login(db, email, ip, ok)
    finally:
        db.close()
    if not ok:
        return _login_page(q, "이메일 또는 비밀번호가 올바르지 않습니다", 401)
    return code_redirect(q, user.id)


def code_redirect(q: dict, user_id: int) -> RedirectResponse:
    """로그인한 사용자의 인가 코드를 Claude로 보낸다(비밀번호·Google 로그인 공통)."""
    # 코드는 5분짜리 서명값이고, 한 번 쓰면 /oauth/token이 기록해 다시 못 쓴다
    code = sign_payload({"t": "code", "u": user_id, "c": q["client_id"], "r": q["redirect_uri"], "ch": q["code_challenge"]}, CODE_TTL)
    sep = "&" if "?" in q["redirect_uri"] else "?"
    return RedirectResponse(q["redirect_uri"] + sep + urlencode({"code": code, "state": q["state"]}), 302)


def _tokens(user: User) -> dict:
    return {"access_token": make_token(user.id, user.token_version, user.mcp_version, ACCESS_TTL), "token_type": "Bearer", "expires_in": ACCESS_TTL,
            "refresh_token": sign_payload({"t": "refresh", "u": user.id, "v": user.token_version, "m": user.mcp_version,
                                           "j": secrets.token_hex(8)}, REFRESH_TTL)}


# 갱신 토큰을 이 시간 안에 다시 쓰면 Claude의 재시도로 보고 거절만, 그 뒤면 탈취로 보고 Claude 연결을 모두 끊는다
REUSE_GRACE = timedelta(seconds=60)


def _use_once(db, token: str, exp: int) -> datetime | None:
    """처음 쓰는 토큰이면 기록하고 None, 이미 쓴 토큰이면 처음 쓴 시각."""
    key = hashlib.sha256(token.encode()).hexdigest()
    if used := db.get(OAuthUsed, key):
        return used.used_at.replace(tzinfo=used.used_at.tzinfo or timezone.utc)  # SQLite·D1은 시간대 없이 돌려준다
    db.execute(delete(OAuthUsed).where(OAuthUsed.expires_at < now()))  # 만료된 기록은 지워 표가 커지지 않게
    db.add(OAuthUsed(key=key, used_at=now(), expires_at=datetime.fromtimestamp(exp, timezone.utc)))
    return None


@router.post("/oauth/token")
async def token(request: Request):
    f = await request.form()
    bad = JSONResponse({"error": "invalid_grant"}, 400)
    db = SessionLocal()
    try:
        if f.get("grant_type") == "authorization_code":
            raw = str(f.get("code") or "")
            c = read_payload(raw, "code")
            verifier = str(f.get("code_verifier") or "").encode()
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier).digest()).decode().rstrip("=")
            if not c or c["r"] != f.get("redirect_uri") or c["c"] != f.get("client_id") or c["ch"] != challenge or _use_once(db, raw, c["exp"]):
                return bad
            user = db.get(User, c["u"])
        elif f.get("grant_type") == "refresh_token":
            raw = str(f.get("refresh_token") or "")
            r = read_payload(raw, "refresh")
            user = db.get(User, r["u"]) if r else None
            # 탈퇴했거나 비밀번호 변경·모든 기기 로그아웃·Claude 연결 끊기 이전의 갱신 토큰(버전 없는 예전 토큰은 0)
            if user and (r.get("v", 0) != user.token_version or r.get("m", 0) != user.mcp_version):
                user = None
            if user and (first := _use_once(db, raw, r["exp"])):
                if now() - first > REUSE_GRACE:
                    user.mcp_version += 1
                    db.commit()
                user = None
        else:
            return JSONResponse({"error": "unsupported_grant_type"}, 400)
        if not user:
            return bad
        try:
            db.commit()  # 같은 토큰을 동시에 내면 사용 기록(기본키)이 겹쳐 한쪽만 성공한다
        except IntegrityError:
            db.rollback()
            return bad
        return _tokens(user)
    finally:
        db.close()


# ---------- 도구 ----------
WS = {"workspace_id": {"type": "integer", "description": "조직 ID (list_ad_accounts 결과)"}}
ACC = {**WS, "ad_account_id": {"type": "integer", "description": "광고 계정 ID (list_ad_accounts 결과의 id)"}}
PERIOD = {"since": {"type": "string", "description": "시작일 YYYY-MM-DD"}, "until": {"type": "string", "description": "종료일 YYYY-MM-DD"},
          "account_ids": {"type": "array", "items": {"type": "integer"}, "description": "광고 계정 ID들. 비우면 볼 수 있는 전체"}}
CHANGE = {"type": "object", "required": ["entity_type", "naver_id", "field", "value", "ad_account_id"], "properties": {
    "entity_type": {"enum": ["campaign", "adgroup", "keyword", "ad", "ad_extension", "negative_keyword"]},
    "naver_id": {"type": "string", "description": "대상 네이버 ID. 키워드·제외검색어 등록(create)이면 광고그룹 ID, 광고그룹 create면 캠페인 ID, "
                  "캠페인 create면 유형(WEB_SITE 파워링크 | SHOPPING 쇼핑검색), 제외검색어 삭제면 제외검색어 ID"},
    "field": {"enum": ["status", "bid_amt", "daily_budget", "create", "delete"],
              "description": "status: ON/OFF, bid_amt: 입찰가(10원 단위), daily_budget: 캠페인 일예산, create: 캠페인·광고그룹·키워드·제외검색어 등록, delete: 캠페인·광고그룹(OFF인 것만, 안의 광고까지 삭제)·키워드·소재·제외검색어 삭제"},
    "value": {"type": "string", "description": "새 값. 캠페인 create는 '이름|일예산'(일예산 필수), "
              "광고그룹 create는 '이름|비즈채널ID|입찰가|하루예산'(비즈채널은 list_channels에서 캠페인 유형에 맞는 것: 파워링크는 SITE, 쇼핑은 MALL. "
              "입찰가 비우면 최저, 하루예산 비우면 제한 없음). 새 캠페인·광고그룹은 OFF로 만들어진다. 키워드 create는 '키워드' 또는 '키워드|입찰가'(입찰가 비우면 70원), "
              "제외검색어 create는 검색어, 제외검색어 delete는 광고그룹 ID, 그 밖의 delete는 빈 문자열"},
    "ad_account_id": {"type": "integer"},
    "before": {"type": "string", "description": "목록 도구로 확인한 현재 값(같으면 미리보기에서 걸러짐)"},
    "product": {"enum": ["WEB_SITE", "SHOPPING"], "description": "캠페인·광고그룹 유형. 키워드 등록은 광고그룹 유형"},
    "ad_type": {"type": "string", "description": "소재 입찰가 변경 시 소재 유형"}}}

KEYS = {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["ad_account_id", "naver_id"], "properties": {
    "ad_account_id": {"type": "integer"}, "naver_id": {"type": "string", "description": "키워드 네이버 ID (list_keywords 결과)"},
    "keyword": {"type": "string", "description": "키워드 문구(자동입찰 목록 표시용)"}}}}

TOOLS = [
    {"name": "list_ad_accounts", "description": "내가 속한 조직과 조직별로 볼 수 있는 네이버 광고 계정 목록. 다른 도구의 workspace_id·ad_account_id는 여기서 얻는다.",
     "inputSchema": {"type": "object", "properties": {}}, "annotations": {"readOnlyHint": True}},
    {"name": "get_performance", "description": "광고 계정별·상품 유형별 성과 합계(노출·클릭·비용·전환·매출·CTR·CPC·ROAS). 기간을 비우면 어제까지 7일.",
     "inputSchema": {"type": "object", "required": ["workspace_id"], "properties": {**WS, **PERIOD}}, "annotations": {"readOnlyHint": True}},
    {"name": "get_daily_performance", "description": "일별 성과 합계(최대 93일).",
     "inputSchema": {"type": "object", "required": ["workspace_id", "since", "until"], "properties": {
         **WS, **PERIOD, "product": {"enum": ["WEB_SITE", "SHOPPING"], "description": "파워링크(WEB_SITE)·쇼핑검색만 보려면"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "get_entity_performance", "description": "키워드·광고그룹·소재별 성과 합계(노출·클릭·비용·전환·매출·CTR·CPC·ROAS·평균 노출 순위). "
     "adgroup_id를 주면 그 광고그룹의 키워드 전체(키워드 문구·상태·입찰가 포함), ids를 주면 그 대상들(최대 500개). 기간을 비우면 어제까지 7일. 네이버에서 바로 조회.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id"], "properties": {
         **ACC, "since": PERIOD["since"], "until": PERIOD["until"], "adgroup_id": {"type": "string", "description": "광고그룹 네이버 ID"},
         "ids": {"type": "array", "items": {"type": "string"}, "description": "캠페인·광고그룹·키워드·소재 네이버 ID들"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "list_audit_logs", "description": "작업 기록(누가 언제 무엇을 바꿨는지: 대량 작업·자동입찰·등록·삭제). 최신순.",
     "inputSchema": {"type": "object", "required": ["workspace_id"], "properties": {
         **WS, "ad_account_id": {"type": "integer", "description": "이 광고 계정만"}, "limit": {"type": "integer", "description": "개수(기본 50, 최대 500)"}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "list_campaigns", "description": "광고 계정의 캠페인(파워링크·쇼핑검색) 목록과 상태·일예산. 네이버에서 바로 조회.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id"], "properties": ACC}, "annotations": {"readOnlyHint": True}},
    {"name": "list_adgroups", "description": "캠페인의 광고그룹 목록과 상태·입찰가·하루예산·운영 상태.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "campaign_id"], "properties": {
         **ACC, "campaign_id": {"type": "string", "description": "캠페인 네이버 ID"}}}, "annotations": {"readOnlyHint": True}},
    {"name": "list_keywords", "description": "광고그룹의 키워드 목록과 상태·입찰가.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id"], "properties": {
         **ACC, "adgroup_id": {"type": "string", "description": "광고그룹 네이버 ID"}}}, "annotations": {"readOnlyHint": True}},
    {"name": "list_ads", "description": "광고그룹의 소재 목록(유형·상태·검수 상태·문구, 쇼핑 상품소재는 입찰가). 소재 입찰가 변경 시 ad_type을 여기서 얻는다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id"], "properties": {
         **ACC, "adgroup_id": {"type": "string", "description": "광고그룹 네이버 ID"}}}, "annotations": {"readOnlyHint": True}},
    {"name": "list_ad_extensions", "description": "광고그룹의 확장소재 목록(유형·상태·검수 상태·내용).",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id"], "properties": {
         **ACC, "adgroup_id": {"type": "string", "description": "광고그룹 네이버 ID"}}}, "annotations": {"readOnlyHint": True}},
    {"name": "related_keywords", "description": "네이버 키워드 도구의 연관 키워드와 월간 검색수(검색량 많은 순 상위 100개). hint는 띄어쓰기 없는 키워드, 쉼표로 최대 5개.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "hint"], "properties": {
         **ACC, "hint": {"type": "string"}}}, "annotations": {"readOnlyHint": True}},
    {"name": "check_ranks", "description": "키워드의 지금 순위(PC·모바일 네이버 검색 화면에서 내 광고가 몇 위인지, 노출 안 되면 null). 한 번에 10개까지.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "keywords"], "properties": {**WS, "keywords": {**KEYS, "maxItems": 10}}},
     "annotations": {"readOnlyHint": True}},
    {"name": "list_auto_bids", "description": "조직의 자동입찰 규칙 목록(기기·목표 순위·최대 입찰가·마지막 실행 결과).",
     "inputSchema": {"type": "object", "required": ["workspace_id"], "properties": WS}, "annotations": {"readOnlyHint": True}},
    {"name": "set_auto_bid", "description": "키워드에 자동입찰 규칙을 만들거나 덮어쓴다(바로 저장). 10분마다 순위를 읽어 목표보다 아래면 입찰가를 20% 올리고 "
     "위면 10% 내린다(최대 입찰가 이하). 한 번에 목표 순위로 가지 않고 몇십 분에 걸쳐 맞춘다. 조직당 20개까지. "
     "기기·목표 순위·최대 입찰가를 사용자에게 확인받은 뒤 호출. enabled=false면 규칙을 남긴 채 중지.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "keywords", "device", "target_rank", "max_bid"], "properties": {
         **WS, "keywords": KEYS, "device": {"enum": ["PC", "MOBILE"]},
         "target_rank": {"type": "integer", "description": "목표 순위. PC 1~10, 모바일 1~5"},
         "max_bid": {"type": "integer", "description": "최대 입찰가(70~100,000원, 10원 단위)"}, "enabled": {"type": "boolean"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "delete_auto_bid", "description": "키워드의 자동입찰 규칙을 지운다(입찰가는 지금 값 그대로).",
     "inputSchema": {"type": "object", "required": ["workspace_id", "keywords"], "properties": {**WS, "keywords": KEYS}},
     "annotations": {"destructiveHint": True}},
    {"name": "run_auto_bids", "description": "자동입찰을 10분 기다리지 않고 지금 한 번 실행해 입찰가를 실제로 바꾼다. keywords를 주면 그 키워드 규칙만. "
     "결과는 list_auto_bids의 last_result로 확인.",
     "inputSchema": {"type": "object", "required": ["workspace_id"], "properties": {**WS, "keywords": KEYS}},
     "annotations": {"destructiveHint": True}},
    {"name": "create_ad", "description": "파워링크 광고그룹에 소재를 등록한다(바로 실행, OFF 상태로 만들어져 검수 후 사용자가 켬). "
     "먼저 제목·설명·URL 초안을 사용자에게 보여 주고 승인받은 뒤 호출. RSA_AD(반응형)는 제목 여러 개·설명 여러 개, TEXT_45는 첫 제목·설명만 쓴다. "
     "글자 수·개수 제한은 네이버가 검사해 오류로 알려 준다(보통 제목 15자, 설명 45자).",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id", "headlines", "descriptions", "pc_url"], "properties": {
         **ACC, "adgroup_id": {"type": "string"}, "ad_type": {"enum": ["RSA_AD", "TEXT_45"], "description": "기본 RSA_AD"},
         "headlines": {"type": "array", "items": {"type": "string"}}, "descriptions": {"type": "array", "items": {"type": "string"}},
         "pc_url": {"type": "string", "description": "PC 연결 URL"}, "mobile_url": {"type": "string", "description": "비우면 PC URL"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "create_ad_extension", "description": "파워링크 광고그룹에 확장소재를 등록한다(바로 실행). 사용자 승인 후 호출. "
     "DESCRIPTION(홍보문구: heading은 할인·사은품·추가선물증정·이벤트·신상품 중 하나, description 14자), HEADLINE(추가제목: heading에 15자), "
     "DESCRIPTION_EXTRA(추가설명: description 45자), SUB_LINKS(서브링크: links [{name, final}]).",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id", "ext_type"], "properties": {
         **ACC, "adgroup_id": {"type": "string"}, "ext_type": {"enum": ["DESCRIPTION", "HEADLINE", "DESCRIPTION_EXTRA", "SUB_LINKS"]},
         "heading": {"type": "string"}, "description": {"type": "string"},
         "links": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "final": {"type": "string"}}}}}},
     "annotations": {"destructiveHint": True}},
    {"name": "list_channels", "description": "광고 계정의 비즈채널(사이트·쇼핑몰 등) 목록. 광고그룹을 만들 때 비즈채널 ID를 여기서 고른다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id"], "properties": ACC}, "annotations": {"readOnlyHint": True}},
    {"name": "preview_changes", "description": "ON/OFF·입찰가·일예산 변경, 캠페인·광고그룹·키워드 등록, 캠페인·광고그룹·키워드 삭제의 미리보기를 만든다. 아직 네이버에 반영되지 않는다. "
     "행마다 검증 결과(VALID/INVALID)가 나오니 사용자에게 보여 주고 승인을 받은 뒤 execute_job을 부른다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "changes"], "properties": {
         **WS, "changes": {"type": "array", "items": CHANGE, "minItems": 1}}}},
    {"name": "execute_job", "description": "미리보기 작업을 네이버에 실제 반영한다. 사용자가 preview_changes 결과를 확인하고 실행을 승인했을 때만 호출. "
     "한 번에 몇 행씩 실행하므로 status가 RUNNING이면 같은 job_id로 다시 호출한다.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "job_id"], "properties": {**WS, "job_id": {"type": "integer"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "schedule_job", "description": "미리보기 작업을 정한 시각에 실행하도록 예약한다(예: 11월 12일 0시에 ON). 10분마다 도는 크론이 실행해 최대 10분 늦을 수 있다. "
     "사용자가 preview_changes 결과와 시각을 승인했을 때만 호출. scheduled_at을 null로 주면 예약 취소.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "job_id", "scheduled_at"], "properties": {
         **WS, "job_id": {"type": "integer"},
         "scheduled_at": {"type": ["string", "null"], "description": "시간대 포함 ISO 시각, 한국 시간이면 +09:00 (예: 2026-11-12T00:00:00+09:00)"}}},
     "annotations": {"destructiveHint": True}},
    {"name": "list_negative_keywords", "description": "광고그룹의 제외검색어 목록(naver_id·keyword). 등록·삭제는 preview_changes의 entity_type=negative_keyword로.",
     "inputSchema": {"type": "object", "required": ["workspace_id", "ad_account_id", "adgroup_id"], "properties": {**ACC, "adgroup_id": {"type": "string"}}},
     "annotations": {"readOnlyHint": True}},
]


def _day(s):
    return date.fromisoformat(s) if s else None


def _joined(ids):
    return ",".join(map(str, ids)) if ids else None


async def _call(db, user: User, name: str, a: dict):
    if name == "list_ad_accounts":
        out = await api.my_workspaces(user=user, db=db)
        for w in out:
            w["accounts"] = await api.list_accounts(m=membership_of(db, w["id"], user), db=db)
        return out
    m = membership_of(db, int(a["workspace_id"]), user)
    if name == "get_performance":
        return await api.performance_accounts(_day(a.get("since")), _day(a.get("until")), _joined(a.get("account_ids")), m=m, db=db)
    if name == "get_daily_performance":
        return await api.performance_daily(_day(a["since"]), _day(a["until"]), _joined(a.get("account_ids")), a.get("product"), m=m, db=db)
    if name == "preview_changes":
        return await api.create_bulk_job(api.BulkIn(changes=a["changes"]), m=m, db=db)
    if name == "execute_job":
        return await api.execute_bulk_job(int(a["job_id"]), m=m, db=db)
    if name == "schedule_job":
        return await api.schedule_bulk_job(api.ScheduleIn(scheduled_at=a.get("scheduled_at")), int(a["job_id"]), m=m, db=db)
    if name == "list_audit_logs":
        logs = (await api.audit_logs(None, a.get("ad_account_id"), m=m, db=db))[:min(int(a.get("limit") or 50), 500)]
        names = dict(db.execute(select(User.id, User.name).where(User.id.in_({x["user_id"] for x in logs}))).all())
        return [{**x, "user": names.get(x["user_id"])} for x in logs]
    if name == "check_ranks":
        return await api.keyword_ranks(api.AutoBidKeysIn(keywords=a["keywords"]), m=m, db=db)
    if name == "list_auto_bids":
        return await api.list_auto_bids(m=m, db=db)
    if name == "set_auto_bid":
        return await api.set_auto_bids(api.AutoBidIn(**{k: v for k, v in a.items() if k != "workspace_id"}), m=m, db=db)
    if name == "delete_auto_bid":
        return await api.delete_auto_bids(api.AutoBidKeysIn(keywords=a["keywords"]), m=m, db=db)
    if name == "run_auto_bids":
        return await api.run_auto_bids(api.AutoBidKeysIn(keywords=a["keywords"]) if a.get("keywords") else None, m=m, db=db)
    acc = int(a["ad_account_id"])
    if name == "list_campaigns":
        return await api.naver_objects(acc, "campaigns", m=m, db=db)
    if name == "list_channels":
        return await api.naver_objects(acc, "channels", m=m, db=db)
    if name == "list_adgroups":
        return [adgroup_row(acc, g) for g in api._naver(db, m, acc, lambda c: c.list_adgroups(a["campaign_id"]))]
    if name == "list_keywords":
        return [{"naver_id": k["nccKeywordId"], "keyword": k["keyword"], "status": _status(k), "bid_amt": k["bidAmt"],
                 "use_group_bid": k.get("useGroupBidAmt")} for k in api._naver(db, m, acc, lambda c: c.list_keywords(a["adgroup_id"]))]
    if name == "list_ads":
        return [ad_row(acc, x) for x in api._naver(db, m, acc, lambda c: c.list_ads(a["adgroup_id"]))]
    if name == "list_negative_keywords":
        return await api.negative_keywords(acc, a["adgroup_id"], m=m, db=db)
    if name == "list_ad_extensions":
        return [extension_row(acc, x) for x in api._naver(db, m, acc, lambda c: c.list_ad_extensions(a["adgroup_id"]))]
    if name == "get_entity_performance":
        kws = {}
        if a.get("adgroup_id"):
            kws = {k["nccKeywordId"]: {"keyword": k["keyword"], "status": _status(k), "bid_amt": k["bidAmt"]}
                   for k in api._naver(db, m, acc, lambda c: c.list_keywords(a["adgroup_id"]))}
            if not kws:
                return {"rows": []}
        body = api.EntityPerfIn(ad_account_id=acc, ids=list(kws) or a.get("ids") or [], since=a.get("since"), until=a.get("until"))
        r = await api.performance_entities(body, m=m, db=db)
        r["rows"] = [{**kws.get(x["naver_id"], {}), **x} for x in r["rows"]]
        return r
    if name == "create_ad":
        return bulk.create_ad(db, m, acc, a["adgroup_id"], a.get("ad_type") or "RSA_AD", a["headlines"], a["descriptions"],
                              a["pc_url"], a.get("mobile_url") or "")
    if name == "create_ad_extension":
        return await api.create_ad_extension(api.ExtensionIn(ad_account_id=acc, adgroup_naver_id=a["adgroup_id"], **{
            k: a[k] for k in ("ext_type", "heading", "description", "links") if k in a}), m=m, db=db)
    if name == "related_keywords":
        return (await api.keyword_tool(acc, a["hint"], m=m, db=db))[:100]  # 웹 화면과 같이 검색량 상위 100개
    raise HTTPException(400, f"알 수 없는 도구: {name}")


PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26")


@router.post("/mcp")
async def mcp(request: Request):
    db = SessionLocal()
    try:
        try:
            user = user_from_header(db, request.headers.get("authorization") or "", allow_mcp=True)
        except HTTPException:
            meta = _base(request) + "/.well-known/oauth-protected-resource"
            return JSONResponse({"error": "invalid_token"}, 401, headers={"WWW-Authenticate": f'Bearer resource_metadata="{meta}"'})
        msg = await request.json()
        method, mid, params = msg.get("method"), msg.get("id"), msg.get("params") or {}
        if mid is None:  # 알림(notifications/initialized 등)은 응답 본문 없음
            return Response(status_code=202)
        if method == "initialize":
            v = params.get("protocolVersion")
            result = {"protocolVersion": v if v in PROTOCOLS else PROTOCOLS[0], "capabilities": {"tools": {}},
                      "serverInfo": {"name": "naverads", "version": "0.1.0"},
                      "instructions": "네이버 검색광고 관리. 먼저 list_ad_accounts로 조직·계정을 확인한다. "
                                      "변경은 preview_changes → 사용자 승인 → execute_job(또는 schedule_job으로 예약) 순서로만 한다."}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            try:
                data, err = await _call(db, user, params.get("name"), params.get("arguments") or {}), False
            except HTTPException as e:
                data, err = {"error": e.detail}, True
            except (KeyError, ValueError, TypeError) as e:  # 인자 누락·형식 오류
                data, err = {"error": f"잘못된 인자: {e}"}, True
            result = {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, default=str)}], "isError": err}
        else:
            return JSONResponse({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"지원하지 않는 메서드: {method}"}})
        return JSONResponse({"jsonrpc": "2.0", "id": mid, "result": result})
    finally:
        db.close()


@router.get("/mcp")
async def mcp_stream():
    return Response(status_code=405)  # 서버가 먼저 보내는 알림(SSE)은 쓰지 않는다
