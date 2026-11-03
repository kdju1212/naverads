import base64
import hmac
import json
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, EmailStr
from sqlalchemy import and_, bindparam, delete, false, func, or_, select, text, update
from sqlalchemy.orm import Session

from . import bulk, naver, safety, seo
from .access import (ADMIN_ROLES, CSRF_HEADER, SESSION_COOKIE, WEB_ORIGINS, accessible_account_ids, admin_membership, current_user, membership,
                     membership_of, resolve_account_ids, logged_out_key, session_token, user_from_header)
from .db import Base, engine, get_db
from .models import (AccountAccess, AccountGoal, AccountSafety, AdAccount, ApprovalRequest, AuditLog, AutoBidRule, BulkJob, BulkJobRow, LoginFailure, Membership, NaverApiCredential, OAuthUsed,
                     PerformanceDaily, Plan, Subscription, SyncRun, User, Workspace, WorkspaceAdAccount, KST, now, today_kst)
from .naver import NaverApiError, client_for
from .security import TOKEN_TTL, decrypt, encrypt, hash_password, key_of, make_token, read_payload, read_token, sign_payload, verify_password
from .sync import sync_account

app = FastAPI(title="네이버 광고 통합 관리 API")
# 웹 로그인이 쿠키라 출처를 웹 주소로만 허용한다(다른 사이트의 스크립트는 쿠키를 실어 보내도 응답을 읽지 못한다). Claude(/mcp)는 서버끼리 호출
app.add_middleware(CORSMiddleware, allow_origins=sorted(WEB_ORIGINS), allow_credentials=True, allow_methods=["*"],
                   allow_headers=["authorization", "content-type", CSRF_HEADER])
SECURITY_HEADERS = {"X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                    # Claude 연결 로그인 화면(HTML)을 다른 사이트가 틀 안에 넣어 클릭을 유도하지 못하게
                    "X-Frame-Options": "DENY", "Content-Security-Policy": "frame-ancestors 'none'"}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    res = await call_next(request)
    for k, v in SECURITY_HEADERS.items():
        res.headers.setdefault(k, v)
    return res
# 로컬(SQLite)은 create_all, Cloudflare D1은 migrations/*.sql 로 스키마 관리
if engine is not None:
    Base.metadata.create_all(engine)

DEFAULT_PLAN = {"code": "PER_ACCOUNT", "name": "계정당 요금제", "price_per_account": 19_900, "trial_days": 14}


def _ids(s: str | None) -> list[int] | None:
    return [int(x) for x in s.split(",") if x] if s else None


def _rows(objs, *cols):
    return [{c: getattr(o, c) for c in cols} for o in objs]


# ---------- 인증 ----------
class SignupIn(BaseModel):
    email: EmailStr
    password: str
    name: str


@app.get("/health")
async def health():
    """공개 점검용: 정책 스위치가 운영에서 어떤 상태인지(값만, 비밀 없음)."""
    # cred_key_loaded: 네이버 비밀키 열쇠(CRED_KEY)를 서버가 읽었는지만(값은 내보내지 않음)
    return {"ok": True, "roas_automation": bulk.roas_automation_on(), "cred_key_loaded": bool(os.getenv("CRED_KEY"))}


@app.post("/auth/signup")
async def signup(body: SignupIn, db: Session = Depends(get_db)):
    if os.getenv("APP_ENV", "dev") != "dev":  # 운영 가입은 Google로만(이메일 인증). 비밀번호 가입은 로컬·테스트용
        raise HTTPException(403, "회원가입은 Google로 계속하기를 이용하세요")
    if len(body.password) < 8:
        raise HTTPException(400, "비밀번호는 8자 이상")
    if user_by_email(db, body.email):
        raise HTTPException(409, "이미 가입된 이메일입니다")
    user = User(email=body.email.lower(), password_hash=await hash_password(body.password), name=body.name)
    db.add(user)
    db.commit()
    token = make_token(user.id, user.token_version)
    return _with_session(JSONResponse({"id": user.id, "token": token}), token)  # 가입은 로컬·테스트 전용이라 토큰도 돌려준다


def _with_session(res: Response, token: str) -> Response:
    """웹 로그인 쿠키: HttpOnly(JS가 못 읽음)·Secure·SameSite=Strict(다른 사이트에서 시작한 요청에는 안 실림). 웹과 API는
    같은 사이트(djkim0509.workers.dev, workers.dev는 공개 접미사)라 Strict여도 화면의 요청에 실린다. 로컬도 localhost는 Secure 쿠키를 받는다."""
    res.set_cookie(SESSION_COOKIE, token, max_age=TOKEN_TTL, path="/", httponly=True, secure=True, samesite="strict")
    return res


def _revoke(db: Session, token: str):
    """이 토큰을 만료 시각까지 서버에서 무효로 한다(로그아웃·쿠키로 옮긴 예전 토큰)."""
    if not read_token(token):
        return
    key = logged_out_key(token)
    db.execute(delete(OAuthUsed).where(OAuthUsed.expires_at < now()))  # 만료된 기록은 지워 표가 커지지 않게
    if not db.get(OAuthUsed, key):
        db.add(OAuthUsed(key=key, used_at=now(), expires_at=datetime.fromtimestamp(int(token.split(".")[-2]), timezone.utc)))
    db.commit()


def user_by_email(db: Session, email: str) -> User | None:
    """이메일은 대소문자를 구분하지 않는다(Google 가입은 소문자로 저장)."""
    return db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))


class LoginIn(BaseModel):
    email: EmailStr
    password: str


# 15분 안에 이만큼 틀리면 그 15분이 끝날 때까지 로그인을 막는다(없는 이메일도 똑같이 세어 가입 여부가 드러나지 않게)
LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_MAX = {"email": 5, "ip": 30}
LOGIN_BLOCKED = "로그인 실패가 많아 15분 동안 막혔습니다. 잠시 후 다시 시도하세요"


def _login_keys(email: str, ip: str | None) -> dict[str, int]:
    keys = {f"email:{email.strip().lower()}": LOGIN_MAX["email"]}
    if ip:  # Cloudflare가 넣는 CF-Connecting-IP(로컬·테스트에는 없음)
        keys[f"ip:{ip}"] = LOGIN_MAX["ip"]
    return keys


_COUNT_ATTEMPT = text("INSERT INTO login_failures (key, count, first_at) VALUES (:k, 1, :t) "
                      "ON CONFLICT (key) DO UPDATE SET count = count + 1").bindparams(
    bindparam("t", type_=LoginFailure.__table__.c.first_at.type))


def login_blocked(db: Session, email: str, ip: str | None) -> bool:
    """이번 시도를 비밀번호 확인 전에 먼저 센다(한 문장으로 올려서 동시에 보낸 요청도 하나씩 셈). 한도를 넘으면 True.
    맞는 비밀번호면 record_login이 되돌린다."""
    keys = _login_keys(email, ip)
    db.execute(delete(LoginFailure).where(LoginFailure.first_at <= now() - LOGIN_WINDOW))  # 지난 기록은 지워 표가 커지지 않게
    for k in keys:
        db.execute(_COUNT_ATTEMPT, {"k": k, "t": now()})
    db.commit()
    return any(n > keys[k] for k, n in db.execute(select(LoginFailure.key, LoginFailure.count).where(LoginFailure.key.in_(keys))))


def record_login(db: Session, email: str, ip: str | None, ok: bool):
    """시도는 login_blocked가 이미 셌다. 성공이면 그 이메일 기록을 지우고 IP 횟수에서 이번 시도를 뺀다."""
    if not ok:
        return
    email_key, *ip_key = _login_keys(email, ip)
    db.execute(delete(LoginFailure).where(LoginFailure.key == email_key))
    if ip_key:
        db.execute(update(LoginFailure).where(LoginFailure.key == ip_key[0]).values(count=LoginFailure.count - 1))
    db.commit()


@app.post("/auth/login")
async def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = request.headers.get("cf-connecting-ip")
    if login_blocked(db, body.email, ip):
        raise HTTPException(429, LOGIN_BLOCKED)
    user = user_by_email(db, body.email)
    ok = bool(user) and await verify_password(body.password, user.password_hash)
    record_login(db, body.email, ip, ok)
    if not ok:
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다")
    return _with_session(JSONResponse({"id": user.id}), make_token(user.id, user.token_version))  # 토큰은 HttpOnly 쿠키로만


@app.get("/auth/me")
async def me(user: User = Depends(current_user)):
    return {"id": user.id, "email": user.email, "name": user.name, "has_password": user.password_hash != GOOGLE_ONLY,
            "google_linked": bool(user.google_sub)}


@app.post("/auth/session")
async def upgrade_session(authorization: str = Header(""), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """예전 웹(localStorage 토큰)에서 쿠키 로그인으로 옮기기: Bearer로 한 번 부르면 그 토큰은 무효로 하고 새 토큰을 HttpOnly 쿠키로 준다."""
    if not authorization.strip():
        raise HTTPException(400, "옮길 로그인 토큰이 없습니다")
    old = authorization.removeprefix("Bearer ").strip()
    _revoke(db, old)
    new = make_token(user.id, user.token_version)
    if new == old:  # 같은 초에 받은 토큰은 같은 값이라(무작위 값 없음) 만료를 1초 당겨 다른 토큰으로
        new = make_token(user.id, user.token_version, ttl=TOKEN_TTL - 1)
    return _with_session(JSONResponse({"ok": True}), new)


@app.post("/auth/logout")
async def logout(request: Request, authorization: str = Header(""), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """이 기기만 로그아웃: 지금 토큰을 만료 시각까지 서버에서 무효로 하고 쿠키를 지운다(다른 기기·Claude 연결은 그대로)."""
    _revoke(db, session_token(request, authorization)[0])
    res = JSONResponse({"ok": True})
    res.delete_cookie(SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="strict")
    return res


@app.post("/auth/logout-all")
async def logout_all(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """모든 기기 로그아웃: 이 사용자에게 발급한 로그인·Claude 연결(MCP) 토큰을 모두 무효로 한다."""
    user.token_version += 1
    db.commit()
    return {"ok": True}


@app.post("/auth/disconnect-claude")
async def disconnect_claude(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Claude 연결만 끊기: Claude(MCP) 토큰만 무효로 하고 웹 로그인은 그대로 둔다."""
    user.mcp_version += 1
    db.commit()
    return {"ok": True}


def _delete_workspace(db: Session, ws_id: int):
    """조직과 그 데이터를 모두 지운다. 광고 계정은 다른 조직에 연결 기록이 없을 때만 지운다. 참조하는 표부터 지운다(D1은 외래 키 검사)."""
    acc_ids = list(db.scalars(select(WorkspaceAdAccount.ad_account_id).where(WorkspaceAdAccount.workspace_id == ws_id)))
    db.execute(delete(AuditLog).where(AuditLog.workspace_id == ws_id))
    db.execute(delete(BulkJobRow).where(BulkJobRow.job_id.in_(select(BulkJob.id).where(BulkJob.workspace_id == ws_id))))
    for model in (ApprovalRequest, BulkJob, AutoBidRule, AccountGoal, Subscription, SyncRun, AccountSafety):  # 승인 요청이 작업을 참조해 먼저
        db.execute(delete(model).where(model.workspace_id == ws_id))
    db.execute(delete(AccountAccess).where(AccountAccess.membership_id.in_(select(Membership.id).where(Membership.workspace_id == ws_id))))
    for model in (Membership, WorkspaceAdAccount, NaverApiCredential):
        db.execute(delete(model).where(model.workspace_id == ws_id))
    shared = set(db.scalars(select(WorkspaceAdAccount.ad_account_id).where(WorkspaceAdAccount.ad_account_id.in_(acc_ids))))
    if orphan := [a for a in acc_ids if a not in shared]:
        for model in (PerformanceDaily, SyncRun, BulkJobRow, AuditLog):
            db.execute(delete(model).where(model.ad_account_id.in_(orphan)))
        db.execute(delete(AdAccount).where(AdAccount.id.in_(orphan)))
    db.execute(delete(Workspace).where(Workspace.id == ws_id))


class DeleteMeIn(BaseModel):
    password: str = ""  # 비밀번호 계정은 비밀번호로 확인
    email: str = ""  # Google 계정은 이메일을 다시 입력해 확인


@app.post("/auth/delete-account")
async def delete_account(body: DeleteMeIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """회원 탈퇴. 혼자 소유한 조직은 데이터까지 지우고, 다른 조직에서는 빠진다.
    작업 이력·감사 기록이 남는 다른 조직을 위해 사용자 행은 지우지 않고 개인정보를 지운 '탈퇴한 사용자'로 남긴다."""
    if user.password_hash == GOOGLE_ONLY:
        if body.email.strip().lower() != user.email.lower():
            raise HTTPException(400, "이메일이 일치하지 않습니다")
    else:
        ip = request.headers.get("cf-connecting-ip")
        if login_blocked(db, user.email, ip):
            raise HTTPException(429, LOGIN_BLOCKED)
        ok = await verify_password(body.password, user.password_hash)
        record_login(db, user.email, ip, ok)
        if not ok:
            raise HTTPException(400, "비밀번호가 올바르지 않습니다")
    for m in list(db.scalars(select(Membership).where(Membership.user_id == user.id))):
        owners = db.scalar(select(func.count(Membership.id)).where(Membership.workspace_id == m.workspace_id, Membership.role == "OWNER"))
        if m.role == "OWNER" and owners == 1:
            _delete_workspace(db, m.workspace_id)
        else:
            db.execute(delete(AccountAccess).where(AccountAccess.membership_id == m.id))
            db.delete(m)
    user.email, user.name, user.password_hash = f"deleted-{user.id}@deleted.invalid", "탈퇴한 사용자", "deleted$"
    user.google_sub = None  # Google 고유 ID도 지운다(개인 식별자 보관 안 함, 같은 Google로 다시 가입하면 새 계정)
    user.token_version, user.mcp_version = user.token_version + 1, user.mcp_version + 1
    db.commit()
    return {"ok": True}


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


@app.post("/auth/password")
async def change_password(body: PasswordIn, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """비밀번호 변경. 다른 기기·Claude 연결은 끊고, 지금 기기는 새 토큰으로 계속 쓴다."""
    if user.password_hash == GOOGLE_ONLY:
        raise HTTPException(400, "Google로 로그인한 계정은 비밀번호가 없습니다")
    ip = request.headers.get("cf-connecting-ip")
    if login_blocked(db, user.email, ip):  # 현재 비밀번호 대입도 로그인과 같이 막는다
        raise HTTPException(429, LOGIN_BLOCKED)
    ok = await verify_password(body.current_password, user.password_hash)
    record_login(db, user.email, ip, ok)
    if not ok:
        raise HTTPException(400, "현재 비밀번호가 올바르지 않습니다")
    if len(body.new_password) < 8:
        raise HTTPException(400, "비밀번호는 8자 이상")
    user.password_hash, user.token_version = await hash_password(body.new_password), user.token_version + 1
    db.commit()
    return _with_session(JSONResponse({"ok": True}), make_token(user.id, user.token_version))  # 지금 기기는 새 쿠키로 계속


# ---------- Google 로그인 (가입은 Google로만: 이메일 인증을 Google이 대신) ----------
GOOGLE_AUTH, GOOGLE_TOKEN = "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token"
# 로그인 뒤 돌려보내는 웹 주소는 WEB_ORIGINS(access.py)만
GOOGLE_ONLY = "google$"  # 비밀번호 없는 계정: 어떤 비밀번호와도 맞지 않는다(verify_password)
STATE_COOKIE = "g_state"


def _google_callback_url(request: Request) -> str:
    return str(request.base_url).rstrip("/") + "/auth/google/callback"


def _google_done(st: dict, user: User | None = None, error: str = ""):
    """웹은 로그인 쿠키를 심고 웹으로(토큰을 주소에 싣지 않음), Claude 연결은 인가 코드로. 오류는 #error=…"""
    if "q" in st:
        res = mcp.code_redirect(st["q"], user.id) if user else mcp._login_page(st["q"], error, 400)
    elif user and "l" not in st:
        res = _with_session(RedirectResponse(st["r"], 302), make_token(user.id, user.token_version))
    else:  # Google 연결(설정 화면)은 지금 로그인을 그대로 두고 결과만
        res = RedirectResponse(st["r"] + "#" + urlencode({"google": "linked"} if user else {"error": error}), 302)
    res.delete_cookie(STATE_COOKIE, path="/auth/google")
    return res


@app.get("/auth/google/start")
async def google_start(request: Request, redirect: str = "", link: bool = False, db: Session = Depends(get_db)):
    """link=true: 로그인한 사람이 설정 화면에서 자기 계정에 Google을 연결(기존 계정은 이메일만으로 연결하지 않는다).
    화면에서 같은 사이트로 이동한 요청이라 로그인 쿠키가 실린다."""
    p = request.query_params
    if "client_id" in p:  # Claude 연결 로그인 화면에서 옴
        q, err = mcp._auth_params(p)
        if err:
            return mcp._login_page(None, err, 400)
        st = {"q": q}
    elif f"{(u := urlsplit(redirect)).scheme}://{u.netloc}" in WEB_ORIGINS:
        st = {"r": redirect}
        if link:
            st["l"] = user_from_header(db, f"Bearer {session_token(request, request.headers.get('authorization', ''))[0]}").id
    else:
        raise HTTPException(400, "허용되지 않은 주소입니다")
    if not os.getenv("GOOGLE_CLIENT_ID"):
        return _google_done(st, error="Google 로그인이 아직 설정되지 않았습니다")
    # 로그인 CSRF 방지: 시작한 브라우저의 쿠키와 state의 값이 같아야 콜백을 받는다
    nonce = secrets.token_urlsafe(16)
    state = sign_payload({"t": "google", "n": nonce, **st}, 600)
    res = RedirectResponse(GOOGLE_AUTH + "?" + urlencode({"client_id": os.getenv("GOOGLE_CLIENT_ID"), "redirect_uri": _google_callback_url(request),
                                                         "response_type": "code", "scope": "openid email profile", "state": state,
                                                         "prompt": "select_account"}), 302)
    res.set_cookie(STATE_COOKIE, nonce, max_age=600, path="/auth/google", httponly=True, samesite="lax", secure=request.url.scheme == "https")
    return res


@app.get("/auth/google/callback")
async def google_callback(request: Request, state: str = "", code: str = "", db: Session = Depends(get_db)):
    st = read_payload(state, "google")
    if not st or not hmac.compare_digest(st["n"], request.cookies.get(STATE_COOKIE, "")):
        raise HTTPException(400, "로그인 요청이 만료되었거나 다른 브라우저에서 시작되었습니다. 처음부터 다시 시도하세요")
    if not code:
        return _google_done(st, error="Google 로그인이 취소되었습니다")
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    try:
        r = httpx.post(GOOGLE_TOKEN, data={"code": code, "client_id": client_id, "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
                                           "redirect_uri": _google_callback_url(request), "grant_type": "authorization_code"}, timeout=15)
        seg = r.json()["id_token"].split(".")[1]
        # Google 토큰 엔드포인트에서 HTTPS로 직접 받은 id_token이라 서명 검증 없이 내용만 읽는다(Google OpenID Connect 문서가 허용).
        # 대신 iss·aud·exp·email_verified·sub를 확인한다
        info = json.loads(base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4)))
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return _google_done(st, error="Google 로그인에 실패했습니다. 다시 시도하세요")
    if (info.get("iss") not in GOOGLE_ISSUERS or info.get("aud") != client_id or not isinstance(info.get("exp"), int)
            or info["exp"] < datetime.now(timezone.utc).timestamp() or not info.get("sub")):
        return _google_done(st, error="Google 로그인 정보를 확인하지 못했습니다. 다시 시도하세요")
    if not info.get("email_verified") or not info.get("email"):
        return _google_done(st, error="인증된 Google 이메일이 아닙니다")
    user, error = google_user(db, str(info["sub"]), info["email"].lower(), info.get("name"), st.get("l"), info.get("hd"))
    return _google_done(st, user=user, error=error)


GOOGLE_ISSUERS = {"https://accounts.google.com", "accounts.google.com"}


def google_authoritative(email: str, hd: str | None) -> bool:
    """Google이 이 이메일 주소의 주인인지: Gmail 주소이거나, Google Workspace 조직(hd)의 도메인 주소.
    근거: Google OpenID Connect 문서(사용자 식별은 sub, 조직 판단은 이메일 도메인이 아니라 hd). Gmail 주소는 지워져도 다른 사람에게 다시 주지 않는다."""
    domain = email.rpartition("@")[2]
    return domain in ("gmail.com", "googlemail.com") or (bool(hd) and hd.lower() == domain)


LEGACY_GOOGLE_BLOCKED = ("예전에 Google로 가입한 계정을 연결하려면 본인 확인이 필요합니다. 이 이메일은 Google이 주인임을 확인할 수 없는 주소라 "
                         "자동으로 연결하지 않았어요. 관리자에게 문의해 주세요")


def google_user(db: Session, sub: str, email: str, name: str | None, link_user_id: int | None, hd: str | None = None) -> tuple[User | None, str]:
    """Google 고유 식별자(sub)로 계정을 찾는다. 이메일만 같은 기존 계정에는 자동으로 붙이지 않는다(그 계정으로 로그인한 뒤 설정에서 연결).
    전환 예외: 예전에 Google로 가입해 sub 없이 저장된 계정(비밀번호 없음)은 Google이 그 이메일의 주인일 때(google_authoritative)만
    처음 로그인 때 sub를 기록한다. 그 밖(Google 계정에 등록한 다른 회사 메일 등)은 주인이 바뀌었을 수 있어 운영자가 본인 확인 후 연결한다
    (docs/SECURITY_OPERATIONS.md 2절)."""
    owner = db.scalar(select(User).where(User.google_sub == sub))
    if link_user_id is not None:
        user = db.get(User, link_user_id)
        if owner and owner.id != link_user_id:
            return None, "이 Google 계정은 이미 다른 계정에 연결돼 있습니다"
        if user.google_sub and user.google_sub != sub:
            return None, "이미 다른 Google 계정이 연결돼 있습니다"
        user.google_sub = sub
        db.commit()
        return user, ""
    if owner:
        return owner, ""
    user = user_by_email(db, email)
    if user and user.password_hash == GOOGLE_ONLY and not user.google_sub:
        if not google_authoritative(email, hd):
            return None, LEGACY_GOOGLE_BLOCKED
        user.google_sub = sub
        db.commit()
        return user, ""
    if user:
        return None, "이미 비밀번호로 가입된 이메일입니다. 비밀번호로 로그인한 뒤 설정에서 Google 연결을 해 주세요"
    user = User(email=email, password_hash=GOOGLE_ONLY, name=(name or email.split("@")[0])[:100], google_sub=sub)
    db.add(user)
    db.commit()
    return user, ""


# ---------- 조직·직원·권한 ----------
class WorkspaceIn(BaseModel):
    name: str
    type: Literal["AGENCY", "DIRECT_ADVERTISER"] = "AGENCY"


@app.post("/workspaces")
async def create_workspace(body: WorkspaceIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ws = Workspace(name=body.name, type=body.type)
    db.add(ws)
    db.flush()
    db.add(Membership(workspace_id=ws.id, user_id=user.id, role="OWNER"))
    plan = db.get(Plan, DEFAULT_PLAN["code"]) or Plan(**DEFAULT_PLAN)
    db.add(plan)
    db.add(Subscription(workspace_id=ws.id, plan_code=plan.code, status="TRIALING",
                        trial_ends_at=now() + timedelta(days=plan.trial_days)))
    db.commit()
    return {"id": ws.id, "name": ws.name, "type": ws.type}


@app.get("/workspaces")
async def my_workspaces(user: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Workspace, Membership.role).join(Membership, Membership.workspace_id == Workspace.id).where(Membership.user_id == user.id)
    return [{"id": w.id, "name": w.name, "type": w.type, "role": r} for w, r in db.execute(q)]


class MemberIn(BaseModel):
    email: EmailStr
    role: Literal["ADMIN", "MEMBER"] = "MEMBER"


@app.get("/workspaces/{ws_id}/members")
async def list_members(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    q = select(Membership, User).join(User, User.id == Membership.user_id).where(Membership.workspace_id == m.workspace_id)
    members = db.execute(q).all()
    access: dict[int, list] = {}
    for a in db.scalars(select(AccountAccess).where(AccountAccess.membership_id.in_([mem.id for mem, _ in members]))):
        access.setdefault(a.membership_id, []).append({"ad_account_id": a.ad_account_id, "level": a.level})
    return [{"membership_id": mem.id, "user_id": u.id, "email": u.email, "name": u.name, "role": mem.role, "access": access.get(mem.id, [])}
            for mem, u in members]


@app.post("/workspaces/{ws_id}/members")
async def add_member(body: MemberIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    user = user_by_email(db, body.email)
    if not user:
        raise HTTPException(404, "가입된 사용자가 아닙니다")  # shortcut: 초대 메일 없음, 가입 후 추가. 초대 플로우는 2단계
    if db.scalar(select(Membership).where(Membership.workspace_id == m.workspace_id, Membership.user_id == user.id)):
        raise HTTPException(409, "이미 소속된 직원입니다")
    mem = Membership(workspace_id=m.workspace_id, user_id=user.id, role=body.role)
    db.add(mem)
    db.commit()
    return {"membership_id": mem.id}


class AccessIn(BaseModel):
    ad_account_id: int
    level: Literal["VIEW", "EDIT"] | None  # None = 배정 해제


@app.put("/workspaces/{ws_id}/members/{membership_id}/access")
async def set_access(membership_id: int, body: AccessIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    target = db.get(Membership, membership_id)
    if not target or target.workspace_id != m.workspace_id:
        raise HTTPException(404, "직원을 찾을 수 없습니다")
    if not db.scalar(select(WorkspaceAdAccount).where(WorkspaceAdAccount.workspace_id == m.workspace_id,
                                                      WorkspaceAdAccount.ad_account_id == body.ad_account_id,
                                                      WorkspaceAdAccount.status == "CONNECTED")):
        raise HTTPException(404, "이 조직에 연결된 광고 계정이 아닙니다")
    row = db.scalar(select(AccountAccess).where(AccountAccess.membership_id == membership_id,
                                                AccountAccess.ad_account_id == body.ad_account_id))
    before = row.level if row else None
    if body.level is None:
        if row:
            db.delete(row)
    elif row:
        row.level = body.level
    else:
        db.add(AccountAccess(membership_id=membership_id, ad_account_id=body.ad_account_id, level=body.level))
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=body.ad_account_id, action="ACCESS_SET",
                    field=f"membership:{membership_id}", before=before, after=body.level))
    db.commit()
    return {"ok": True}


# ---------- 네이버 자격증명·광고 계정 ----------
class CredentialIn(BaseModel):
    label: str
    api_key: str
    secret_key: str
    is_mock: bool = True


@app.post("/workspaces/{ws_id}/credentials")
async def add_credential(body: CredentialIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    if body.is_mock and os.getenv("APP_ENV", "dev") != "dev":  # Mock은 로컬 화면 확인·테스트용
        raise HTTPException(403, "운영에서는 Mock 자격증명을 등록할 수 없습니다")
    cred = NaverApiCredential(workspace_id=m.workspace_id, label=body.label, api_key=body.api_key,
                              secret_key_enc=_encrypt(body.secret_key), is_mock=body.is_mock)
    db.add(cred)
    db.commit()
    return {"id": cred.id, "label": cred.label, "is_mock": cred.is_mock}  # 비밀키는 반환하지 않는다


@app.get("/workspaces/{ws_id}/credentials")
async def list_credentials(m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    bulk.rotate_credentials(db, m.workspace_id)  # 크론이 못 옮긴 것도 관리자가 목록을 열면 옮겨진다
    creds = db.scalars(select(NaverApiCredential).where(NaverApiCredential.workspace_id == m.workspace_id)).all()
    # 키는 반환하지 않는다. key: 어느 열쇠로 암호화돼 있는지(CRED_KEY | APP_SECRET)
    return [{**r, "key": key_of(c.secret_key_enc)} for r, c in zip(_rows(creds, "id", "label", "is_mock"), creds)]


class CredentialKeysIn(BaseModel):
    api_key: str
    secret_key: str


@app.put("/workspaces/{ws_id}/credentials/{cred_id}")
async def replace_credential(cred_id: int, body: CredentialKeysIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    """키가 샜거나 네이버에서 재발급했을 때 같은 자격증명의 키만 바꾼다(연결된 계정은 그대로)."""
    cred = _credential(db, m, cred_id)
    if not body.api_key.strip() or not body.secret_key.strip():
        raise HTTPException(400, "API Key와 Secret Key를 입력하세요")
    cred.api_key, cred.secret_key_enc = body.api_key.strip(), _encrypt(body.secret_key.strip())
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, action="CREDENTIAL_REPLACE", field="credential", naver_id=str(cred.id)))
    db.commit()
    return {"id": cred.id, "label": cred.label, "is_mock": cred.is_mock}  # 키는 반환하지 않는다


@app.delete("/workspaces/{ws_id}/credentials/{cred_id}")
async def delete_credential(cred_id: int, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    cred = _credential(db, m, cred_id)
    if db.scalar(select(WorkspaceAdAccount.id).where(WorkspaceAdAccount.credential_id == cred.id, WorkspaceAdAccount.status == "CONNECTED")):
        raise HTTPException(409, "이 자격증명으로 연결된 광고 계정이 있습니다. 계정 연결을 먼저 해제하세요")
    db.execute(delete(WorkspaceAdAccount).where(WorkspaceAdAccount.credential_id == cred.id))  # 해제된 연결 기록(키 참조)도 같이
    db.delete(cred)
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, action="CREDENTIAL_DELETE", field="credential", naver_id=str(cred_id)))
    db.commit()
    return {"ok": True}


def _encrypt(secret: str) -> str:
    try:
        return encrypt(secret)
    except RuntimeError as e:  # 운영에 CRED_KEY가 없음 → 로그인 서명 열쇠(APP_SECRET)로 새로 암호화하지 않는다
        raise HTTPException(503, f"서버 설정이 끝나지 않아 API 키를 저장할 수 없습니다(관리자 확인 필요): {e}")


def _credential(db: Session, m: Membership, cred_id: int) -> NaverApiCredential:
    cred = db.get(NaverApiCredential, cred_id)
    if not cred or cred.workspace_id != m.workspace_id:
        raise HTTPException(404, "자격증명을 찾을 수 없습니다")
    return cred


class ConnectIn(BaseModel):
    credential_id: int
    customer_id: str
    name: str


@app.post("/workspaces/{ws_id}/ad-accounts")
async def connect_account(body: ConnectIn, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    cred = db.get(NaverApiCredential, body.credential_id)
    if not cred or cred.workspace_id != m.workspace_id:
        raise HTTPException(404, "자격증명을 찾을 수 없습니다")
    # 광고 계정은 고객 ID로 조직 간에 공유된다. Mock은 아무나 만들 수 있어, 실제 광고주 번호를 먼저 차지해
    # 진짜 계정 연결을 막지 못하게 조직별 번호(mock{조직}-{번호})로 따로 둔다
    cid = f"mock{m.workspace_id}-{body.customer_id}" if cred.is_mock else body.customer_id
    # 가짜 캠페인 ID는 번호로 만들어져 성과 표(캠페인 ID가 전체에서 하나)에서 겹치므로 Mock 번호는 조직끼리 겹치지 않게
    # (예전 방식으로 번호 그대로 저장된 Mock 계정도 같은 번호로 본다)
    if cred.is_mock and db.scalar(select(AdAccount.id).where(
            or_(AdAccount.customer_id.like(f"mock%-{body.customer_id}"), AdAccount.customer_id == body.customer_id),
            AdAccount.customer_id != cid)):
        raise HTTPException(409, "다른 조직이 Mock으로 쓰는 번호입니다. 다른 숫자를 넣어 주세요")
    try:
        client = client_for(cred, cid, decrypt)
        client.list_campaigns()  # 이 자격증명으로 해당 계정에 실제 접근 가능한지 검증
    except NaverApiError as e:
        raise HTTPException(400, f"광고 계정 접근 검증 실패: {e}")
    acc = db.scalar(select(AdAccount).where(AdAccount.customer_id == cid))
    if acc is None:
        acc = AdAccount(customer_id=cid, name=body.name, is_mock=cred.is_mock)
        db.add(acc)
        db.flush()
    elif acc.is_mock != cred.is_mock:
        raise HTTPException(400, "Mock/실계정 구분이 기존 계정과 다릅니다")
    link = db.scalar(select(WorkspaceAdAccount).where(WorkspaceAdAccount.workspace_id == m.workspace_id,
                                                      WorkspaceAdAccount.ad_account_id == acc.id))
    if link and link.status == "CONNECTED":
        raise HTTPException(409, "이미 연결된 계정입니다")
    if link:
        link.status, link.credential_id, link.connected_by, link.connected_at = "CONNECTED", cred.id, m.user_id, now()
    else:
        db.add(WorkspaceAdAccount(workspace_id=m.workspace_id, ad_account_id=acc.id, credential_id=cred.id, connected_by=m.user_id))
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=acc.id, action="ACCOUNT_CONNECT"))
    db.commit()
    # 성과 통계 동기화는 별도 요청(POST .../sync). 광고 데이터는 화면이 마스터 보고서로 받는다
    return {"id": acc.id, "customer_id": acc.customer_id, "name": acc.name}


@app.delete("/workspaces/{ws_id}/ad-accounts/{account_id}")
async def disconnect_account(account_id: int, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    link = db.scalar(select(WorkspaceAdAccount).where(WorkspaceAdAccount.workspace_id == m.workspace_id,
                                                      WorkspaceAdAccount.ad_account_id == account_id,
                                                      WorkspaceAdAccount.status == "CONNECTED"))
    if not link:
        raise HTTPException(404, "연결된 계정이 아닙니다")
    link.status = "DISCONNECTED"  # 데이터·이력은 보존, 접근만 차단
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=account_id, action="ACCOUNT_DISCONNECT"))
    db.commit()
    return {"ok": True}


@app.get("/workspaces/{ws_id}/ad-accounts")
async def list_accounts(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, None)
    last = _last_syncs(db, m.workspace_id, ids)
    guard = {g.ad_account_id: {"daily_budget_limit": g.daily_budget_limit, "max_bid": g.max_bid}
             for g in db.scalars(select(AccountSafety).where(AccountSafety.workspace_id == m.workspace_id))}
    # Mock은 mock{조직}-{번호}로 저장하지만(connect_account) 화면에는 넣은 번호만
    return [{"id": acc.id, "customer_id": acc.customer_id.rpartition("-")[2], "name": acc.name, "is_mock": acc.is_mock,
             "last_sync": (s := last.get(acc.id)) and {"status": s.status, "error": s.error, "at": s.finished_at},
             "safety": guard.get(acc.id)}
            for acc in db.scalars(select(AdAccount).where(AdAccount.id.in_(ids)))]


def _last_syncs(db: Session, ws_id: int, ids, status: str | None = None) -> dict[int, SyncRun]:
    """이 조직이 한 계정별 마지막 동기화를 쿼리 한 번으로(계정마다 따로 조회하면 무료 플랜 요청당 쿼리 한도를 넘는다).
    같은 광고 계정을 다른 조직도 연결할 수 있어 조직별로 본다."""
    latest = select(func.max(SyncRun.id)).where(SyncRun.workspace_id == ws_id, SyncRun.ad_account_id.in_(ids))
    if status:
        latest = latest.where(SyncRun.status == status)
    return {s.ad_account_id: s for s in db.scalars(select(SyncRun).where(SyncRun.id.in_(latest.group_by(SyncRun.ad_account_id))))}


def _own_stats(db: Session, ws_id: int, ids):
    """성과는 계정마다 이 조직이 마지막으로 직접 동기화에 성공한 날까지만(동기화는 어제까지 받는다).
    광고 계정·성과 표는 조직끼리 공유되는데, 광고주가 다른 대행사로 옮기면 예전 대행사 키는 네이버가 거부해 동기화가 실패하므로
    그 뒤 새 대행사가 받은 성과는 예전 대행사에 안 보인다."""
    upto = {}
    for i, s in _last_syncs(db, ws_id, ids, "SUCCESS").items():
        at = s.finished_at if s.finished_at.tzinfo else s.finished_at.replace(tzinfo=timezone.utc)  # SQLite는 시간대 없이 돌려준다
        upto[i] = at.astimezone(KST).date() - timedelta(days=1)
    return or_(*(and_(PerformanceDaily.ad_account_id == i, PerformanceDaily.date <= d) for i, d in upto.items())) if upto else false()


class SafetyIn(BaseModel):
    daily_budget_limit: int
    max_bid: int
    confirmed: bool = False  # 화면에서 금액과 현황을 보고 '확인했어요'를 체크해야 true


@app.get("/workspaces/{ws_id}/ad-accounts/{account_id}/safety")
async def get_safety(account_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """광고비 안전장치 설정과 네이버의 지금 하루예산 설정액 현황·필요한 조치(처음 연결 때 보여 줌)."""
    resolve_account_ids(db, m, [account_id])
    return safety.status(db, m.workspace_id, account_id, lambda: bulk._client(db, m.workspace_id, account_id))


@app.put("/workspaces/{ws_id}/ad-accounts/{account_id}/safety")
async def put_safety(body: SafetyIn, account_id: int, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    resolve_account_ids(db, m, [account_id])
    safety.save(db, m, account_id, body.daily_budget_limit, body.max_bid, body.confirmed)
    return safety.status(db, m.workspace_id, account_id, lambda: bulk._client(db, m.workspace_id, account_id))


class DirectIn(BaseModel):
    on: bool


@app.put("/workspaces/{ws_id}/ad-accounts/{account_id}/safety/claude-direct")
async def put_claude_direct(body: DirectIn, account_id: int, m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    """관리자만, 웹에서만(일반 API는 Claude 토큰을 받지 않는다). 켜면 이 계정의 웹 승인 대상도 Claude 허용 버튼으로 실행된다."""
    resolve_account_ids(db, m, [account_id])
    safety.set_direct(db, m, account_id, body.on)
    return {"claude_direct": body.on}


class StopIn(BaseModel):
    ad_account_id: int
    entity_type: Literal["campaign", "adgroup", "keyword", "ad", "ad_extension"]
    naver_id: str


@app.post("/workspaces/{ws_id}/stop")
async def emergency_stop(body: StopIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """광고 긴급 중지(OFF): 승인·안전장치 검사 없이 바로 끈다(돈이 더 나가지 않는 방향). 수정 권한은 확인하고 이력을 남긴다."""
    bulk._check_edit(db, m, body.ad_account_id)
    try:
        bulk._client(db, m.workspace_id, body.ad_account_id).update(body.entity_type, body.naver_id, "status", "OFF")
    except NaverApiError as e:
        raise HTTPException(400, f"네이버가 끄기 요청을 받아들이지 않았어요: {e}")
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=body.ad_account_id, action="EMERGENCY_STOP",
                    entity_type=body.entity_type, naver_id=body.naver_id, field="status", after="OFF"))
    db.commit()
    return {"ok": True, "message": "껐어요. 네이버 검색 결과에서 빠지기까지 조금 걸릴 수 있어요"}


@app.post("/workspaces/{ws_id}/ad-accounts/{account_id}/sync")
async def sync(account_id: int, offset: int = 0, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """캠페인이 많으면 나눠 받는다: status가 RUNNING이면 화면이 next_offset으로 다시 부른다."""
    resolve_account_ids(db, m, [account_id])
    link = db.scalar(select(WorkspaceAdAccount).where(WorkspaceAdAccount.workspace_id == m.workspace_id,
                                                      WorkspaceAdAccount.ad_account_id == account_id))
    acc = db.get(AdAccount, account_id)
    try:
        client = client_for(db.get(NaverApiCredential, link.credential_id), acc.customer_id, decrypt)
    except NaverApiError as e:
        raise HTTPException(400, str(e))
    run, nxt = sync_account(db, acc, client, m.workspace_id, max(offset, 0))
    if run is None:
        return {"status": "RUNNING", "error": None, "next_offset": nxt}
    return {"status": run.status, "error": run.error, "next_offset": None}


@app.get("/workspaces/{ws_id}/keyword-tool")
async def keyword_tool(account_id: int, hint: str, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """연관 키워드. 네이버 키워드 도구는 띄어쓰기 없는 키워드 최대 5개까지 받는다."""
    resolve_account_ids(db, m, [account_id])
    hints = list(dict.fromkeys(h.replace(" ", "") for h in hint.split(",") if h.strip()))[:5]
    if not hints:
        raise HTTPException(400, "키워드를 입력하세요")
    try:
        rows = bulk._client(db, m.workspace_id, account_id).keyword_tool(hints)
    except NaverApiError as e:
        raise HTTPException(400, f"연관 키워드 조회 실패: {e}")
    return sorted(rows, key=lambda r: -(r["pc"] + r["mobile"]))


@app.get("/workspaces/{ws_id}/seo-fetch")
async def seo_fetch(url: str, m: Membership = Depends(membership)):
    """SEO·GEO 점검용으로 광고주 페이지와 robots.txt 등을 가져온다. 판정은 브라우저가 한다."""
    try:
        return seo.fetch(url)
    except seo.SeoError as e:
        raise HTTPException(400, str(e))


# ---------- 네이버 원본 조회 (브라우저 보관용, DB에 저장하지 않음) ----------
MasterItem = Literal["Adgroup", "Keyword", "Ad", "RsaAd", "ShoppingProduct", "AdExtension"]
ROW_OF = {"adgroups": naver.adgroup_row, "ads": naver.ad_row, "ad-extensions": naver.extension_row}


def _naver(db: Session, m: Membership, account_id: int, fn):
    resolve_account_ids(db, m, [account_id])
    try:
        return fn(bulk._client(db, m.workspace_id, account_id))
    except NaverApiError as e:
        raise HTTPException(400, f"네이버 조회 실패: {e}")


@app.post("/workspaces/{ws_id}/ad-accounts/{account_id}/master-reports")
async def create_master_report(account_id: int, item: MasterItem, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _naver(db, m, account_id, lambda c: c.create_master_report(item))


@app.get("/workspaces/{ws_id}/ad-accounts/{account_id}/master-reports/{job_id}")
async def get_master_report(account_id: int, job_id: str, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _naver(db, m, account_id, lambda c: c.get_master_report(job_id))


@app.delete("/workspaces/{ws_id}/ad-accounts/{account_id}/master-reports/{job_id}")
async def delete_master_report(account_id: int, job_id: str, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """다 받은 보고서를 지운다(네이버 계정당 100개 한도)."""
    _naver(db, m, account_id, lambda c: c.delete_master_report(job_id))
    return {"ok": True}


def master_file_source(db: Session, authorization: str, ws_id: int, account_id: int, job_id: str) -> dict:
    """{"url", "headers"} 또는 {"text"}(Mock). Workers 진입점(src/main.py)이 직접 불러 JS fetch로 본문을 넘긴다.
    authorization은 "Bearer 토큰"(헤더 또는 로그인 쿠키 값). 읽기(GET)라 CSRF 검사는 없다."""
    m = membership_of(db, ws_id, user_from_header(db, authorization))
    return _naver(db, m, account_id, lambda c: c.master_file(c.get_master_report(job_id)))


@app.get("/workspaces/{ws_id}/ad-accounts/{account_id}/master-reports/{job_id}/file")
async def master_report_file(ws_id: int, account_id: int, job_id: str, request: Request, authorization: str = Header(default=""),
                             db: Session = Depends(get_db)):
    """로컬·테스트용. Workers에서는 src/main.py가 이 경로를 먼저 가로챈다(큰 파일을 파이썬이 다루면 CPU 한도 초과)."""
    src = master_file_source(db, f"Bearer {session_token(request, authorization)[0]}", ws_id, account_id, job_id)
    if "text" not in src:
        r = httpx.get(src["url"], headers=src["headers"], timeout=60)
        if r.status_code >= 400:
            raise HTTPException(400, f"보고서 다운로드 실패: {r.status_code}")
        src["text"] = r.text
    return Response(src["text"], media_type="text/tab-separated-values; charset=utf-8")


@app.get("/workspaces/{ws_id}/ad-accounts/{account_id}/naver/{kind}")
async def naver_objects(account_id: int, kind: Literal["campaigns", "adgroups", "ads", "ad-extensions", "channels"], ids: str = "",
                        m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """캠페인·비즈채널은 전체, 나머지는 ids(쉼표)로. 마스터 보고서에 없는 값(운영 상태·소재 문구·확장소재 내용)을 채운다."""
    if kind == "channels":  # 광고그룹 만들 때 고르는 비즈채널(사이트·쇼핑몰)
        return [naver.channel_row(account_id, c) for c in _naver(db, m, account_id, lambda c: c.list_channels())]
    if kind == "campaigns":
        return [naver.campaign_row(account_id, c) for c in _naver(db, m, account_id, lambda c: c.list_campaigns())
                if c["campaignTp"] in ("WEB_SITE", "SHOPPING")]  # MVP 범위 밖 캠페인 유형은 보여 주지 않는다
    id_list = [i for i in ids.split(",") if i]
    if len(id_list) > 500:
        raise HTTPException(400, "한 번에 500개까지")
    return [ROW_OF[kind](account_id, o) for o in _naver(db, m, account_id, lambda c: c.get_many(kind, id_list))]


ProductType = Literal["WEB_SITE", "SHOPPING", "PLACE"] | None


# ---------- 확장소재 ----------
class SubLinkIn(BaseModel):
    name: str
    final: str


class ExtensionIn(BaseModel):
    ad_account_id: int
    adgroup_naver_id: str
    # 실데이터로 내용 구조를 확인한 유형만: DESCRIPTION(홍보문구) {heading: 구분, description}, HEADLINE(추가제목) {headline},
    # DESCRIPTION_EXTRA(추가설명) {description}, SUB_LINKS [{name, final}]
    ext_type: Literal["DESCRIPTION", "HEADLINE", "DESCRIPTION_EXTRA", "SUB_LINKS"]
    heading: str = ""
    description: str = ""
    links: list[SubLinkIn] = []


PROMO_HEADINGS = ("할인", "사은품", "추가선물증정", "이벤트", "신상품")  # 네이버 화면의 홍보문구 구분
TEXT_LIMITS = {"DESCRIPTION": ("홍보문구", 14), "HEADLINE": ("추가제목", 15), "DESCRIPTION_EXTRA": ("추가설명", 45)}


@app.post("/workspaces/{ws_id}/ad-extensions")
async def create_ad_extension(body: ExtensionIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """화면 보관본에 넣을 행을 돌려준다. 쇼핑 광고그룹 등은 화면이 고르지 못하게 하고, 네이버도 거부한다."""
    if body.ext_type in TEXT_LIMITS:
        label, limit = TEXT_LIMITS[body.ext_type]
        text = (body.heading if body.ext_type == "HEADLINE" else body.description).strip()
        if not text or len(text) > limit:
            raise HTTPException(400, f"{label}는 1~{limit}자로 입력하세요")
        if body.ext_type == "DESCRIPTION" and body.heading not in PROMO_HEADINGS:
            raise HTTPException(400, f"홍보문구 구분은 {', '.join(PROMO_HEADINGS)} 중 하나")
        content = {"DESCRIPTION": {"heading": body.heading, "description": text}, "HEADLINE": {"headline": text},
                   "DESCRIPTION_EXTRA": {"description": text}}[body.ext_type]
    else:
        links = [{"name": x.name.strip(), "final": x.final.strip()} for x in body.links]
        if not links or any(not x["name"] or not x["final"].startswith(("http://", "https://")) for x in links):
            raise HTTPException(400, "서브링크는 이름과 http(s):// 로 시작하는 URL을 입력하세요")
        content = links
    return bulk.create_extension(db, m, body.ad_account_id, body.adgroup_naver_id, body.ext_type, content)


@app.delete("/workspaces/{ws_id}/ad-extensions/{naver_id}")
async def delete_ad_extension(naver_id: str, account_id: int, owner_naver_id: str, ext_type: str | None = None,
                              m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return {"ok": True, "already_gone": bulk.delete_extension(db, m, account_id, naver_id, owner_naver_id, ext_type)}


# ---------- 대량 작업 ----------
class ChangeIn(BaseModel):
    """광고 데이터 사본이 서버에 없어 화면(브라우저 보관본)이 대상의 계정·이전 값·유형을 같이 보낸다."""
    entity_type: str
    naver_id: str
    field: str
    value: str
    ad_account_id: int | None = None
    before: str | None = None
    product: Literal["WEB_SITE", "SHOPPING"] | None = None  # 키워드 등록은 광고그룹 유형
    ad_type: str | None = None
    invalid: str | None = None  # 화면이 찾은 오류(없는 ID, 이미 있는 키워드 등) → 그 행은 실행하지 않음


class BulkIn(BaseModel):
    changes: list[ChangeIn]
    source: Literal["UI", "EXCEL"] = "UI"


def _job_accounts(db: Session, job_ids: list[int]) -> dict[int, tuple[set[int], bool]]:
    """작업별 (대상 광고 계정들, 계정 없는 행이 있는지). 계정 없는 행 = 권한 없거나 대상 없음으로 걸러진 행."""
    out: dict[int, tuple[set[int], bool]] = {j: (set(), False) for j in job_ids}
    for jid, acc in db.execute(select(BulkJobRow.job_id, BulkJobRow.ad_account_id).where(BulkJobRow.job_id.in_(job_ids)).distinct()):
        accs, unassigned = out[jid]
        out[jid] = (accs, True) if acc is None else (accs | {acc}, unassigned)
    return out


def _visible_jobs(db: Session, m: Membership, jobs: list[BulkJob]) -> list[BulkJob]:
    """직원은 대상 계정이 모두 자기에게 배정된 작업만 본다(권한이 회수되면 그 작업도 안 보임).
    계정 없는 행에는 만든 사람이 넣은 다른 계정 ID·값이 있을 수 있어 그런 작업은 만든 사람만 본다. 관리자는 조직 전체."""
    if m.role in ADMIN_ROLES or not jobs:
        return jobs
    allowed = accessible_account_ids(db, m)
    acc = _job_accounts(db, [j.id for j in jobs])
    return [j for j in jobs if acc[j.id][0] <= allowed and (not acc[j.id][1] or j.created_by == m.user_id)]


def _job(db: Session, m: Membership, job_id: int, edit: bool = False) -> BulkJob:
    """edit면 실행·예약·재실행: 실행할 행의 계정을 모두 수정할 수 있어야 한다(남의 작업을 실행해 실패로 만들지 못하게)."""
    job = db.get(BulkJob, job_id)
    if not job or job.workspace_id != m.workspace_id or not _visible_jobs(db, m, [job]):
        raise HTTPException(404, "작업을 찾을 수 없습니다")  # 다른 계정 작업이 있는지도 알려 주지 않는다
    if edit:
        need = set(db.scalars(select(BulkJobRow.ad_account_id).where(
            BulkJobRow.job_id == job.id, BulkJobRow.status.in_(("VALID", "FAILED")), BulkJobRow.ad_account_id.is_not(None))))
        if not need <= accessible_account_ids(db, m, edit=True):
            raise HTTPException(403, "이 작업의 광고 계정을 수정할 권한이 없습니다")
    return job


def _job_out(db: Session, job: BulkJob):
    rows = db.scalars(select(BulkJobRow).where(BulkJobRow.job_id == job.id).order_by(BulkJobRow.id)).all()
    names = dict(db.execute(select(AdAccount.id, AdAccount.name).where(AdAccount.id.in_({r.ad_account_id for r in rows}))).all())
    by_account: dict = {}
    for r in rows:
        by_account.setdefault(r.ad_account_id, {"ad_account_id": r.ad_account_id, "name": names.get(r.ad_account_id), "rows": []})["rows"].append(
            {"id": r.id, "entity_type": r.entity_type, "naver_id": r.naver_id, "field": r.field, "before": r.before,
             "after": r.after, "status": r.status, "error": r.error})
    counts = {s: sum(r.status == s for r in rows) for s in ("VALID", "INVALID", "SUCCESS", "FAILED")}
    return {"id": job.id, "status": job.status, "source": job.source, "parent_job_id": job.parent_job_id,
            "created_by": job.created_by, "created_at": job.created_at, "executed_at": job.executed_at,
            "scheduled_at": job.scheduled_at, "counts": counts, "accounts": list(by_account.values())}


@app.post("/workspaces/{ws_id}/bulk-jobs")
async def create_bulk_job(body: BulkIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    job = bulk.create_job(db, m, [c.model_dump() for c in body.changes], body.source)
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, job_id=job.id, action="JOB_PREVIEW", entity_type="job",
                    ad_account_id=bulk.job_account(db, job.id)))
    db.commit()
    return {**_job_out(db, job), "safety": _job_safety(db, m, job)}


def _job_safety(db: Session, m: Membership, job: BulkJob) -> list[dict]:
    """미리보기·승인용: 계정마다 변경 후 하루예산 설정액 합계·클릭당 최대 입찰가·막히는 이유(네이버 지금 값 기준)."""
    ops: dict[int, list] = {}
    for r in db.scalars(select(BulkJobRow).where(BulkJobRow.job_id == job.id, BulkJobRow.status == "VALID")):
        ops.setdefault(r.ad_account_id, []).extend(safety.ops_of_row(r.entity_type, r.field, r.naver_id, r.after or ""))
    return [safety.preview(db, m.workspace_id, acc, o, lambda acc=acc: bulk._client(db, m.workspace_id, acc)) for acc, o in ops.items() if o]


@app.post("/workspaces/{ws_id}/bulk-jobs/excel/parse")
async def parse_bulk_excel(file: UploadFile, m: Membership = Depends(membership)):
    """엑셀 → 변경 목록. 화면이 보관본으로 계정·이전 값을 채워 POST /bulk-jobs(source=EXCEL)로 미리보기를 만든다."""
    return bulk.parse_excel(await file.read())


@app.get("/bulk-jobs/excel-template")
async def excel_template():
    return Response(bulk.excel_template(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=bulk_template.xlsx"})


@app.get("/workspaces/{ws_id}/bulk-jobs")
async def list_bulk_jobs(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    jobs = db.scalars(select(BulkJob).where(BulkJob.workspace_id == m.workspace_id).order_by(BulkJob.id.desc()).limit(200)).all()
    return _rows(_visible_jobs(db, m, jobs)[:50], "id", "status", "source", "parent_job_id", "created_by", "created_at", "executed_at", "scheduled_at")


@app.get("/workspaces/{ws_id}/bulk-jobs/{job_id}")
async def get_bulk_job(job_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    job = _job(db, m, job_id)
    return {**_job_out(db, job), **({"safety": _job_safety(db, m, job)} if job.status == "PREVIEW" else {})}


@app.post("/workspaces/{ws_id}/bulk-jobs/{job_id}/execute")
async def execute_bulk_job(job_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """최대 EXECUTE_CHUNK행씩 실행. 응답 status가 RUNNING이면 화면이 다시 호출한다."""
    job = _job(db, m, job_id, edit=True)
    if job.scheduled_at is not None:  # 크론과 같이 실행돼 두 번 반영되지 않게
        raise HTTPException(409, "예약된 작업입니다. 예약을 취소한 뒤 실행하세요")
    try:
        return _job_out(db, bulk.execute_job(db, m, job, bulk.EXECUTE_CHUNK))
    except bulk.ApprovalRequired:  # 계정 하루예산 합계가 늘 수 있는 작업: 승인 요청만 만들고 실행하지 않는다(웹 /approvals에서 승인)
        return {**_job_out(db, job), "approval": approvals.pending_reply(approvals.request_for_job(db, m, job))}


class ScheduleIn(BaseModel):
    scheduled_at: datetime | None  # 시간대 포함(예: 2026-11-12T00:00:00+09:00). null이면 예약 취소


@app.post("/workspaces/{ws_id}/bulk-jobs/{job_id}/schedule")
async def schedule_bulk_job(body: ScheduleIn, job_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """미리보기 작업을 정한 시각에 실행하도록 예약(10분마다 도는 크론이 실행하므로 최대 10분 늦을 수 있다). 실행은 작업을 만든 사람 권한으로."""
    job = _job(db, m, job_id, edit=True)
    if job.created_by != m.user_id and m.role not in ADMIN_ROLES:  # 예약 실행은 만든 사람 권한이라 남이 대신 예약하면 권한이 넘어간다
        raise HTTPException(403, "작업을 만든 사람이나 관리자만 예약할 수 있습니다")
    if job.status != "PREVIEW":
        raise HTTPException(409, "미리보기 상태의 작업만 예약할 수 있습니다")
    at = body.scheduled_at
    if at is not None:
        if at.tzinfo is None:
            raise HTTPException(400, "시간대가 있는 시각이어야 합니다")
        if not now() < at < now() + timedelta(days=366):
            raise HTTPException(400, "예약 시각은 지금부터 1년 안이어야 합니다")
        valid = db.scalars(select(BulkJobRow).where(BulkJobRow.job_id == job.id, BulkJobRow.status == "VALID")).all()
        if not valid:
            raise HTTPException(400, "실행할 수 있는 행이 없습니다")
        # 예약 시점에도 안전장치를 검사한다(실행 시점에 다시 검사해 그때 조건이 달라졌으면 실행하지 않는다)
        if blocked := bulk.safety_blocks(db, m.workspace_id, valid, {}):
            raise HTTPException(400, f"광고비 안전장치에 걸려 예약할 수 없어요: {next(iter(blocked.values()))}")
    # 예약을 바꾸거나 취소하면 전에 받은 승인·승인 요청은 쓰지 않는다(새 시각으로 다시 승인)
    for ar in db.scalars(select(ApprovalRequest).where(ApprovalRequest.job_id == job.id, ApprovalRequest.status.in_(("PENDING", "APPROVED")))):
        ar.status = "EXPIRED"
    # SQLite·D1은 시간대를 버리고 저장하므로 다른 시각(now(), UTC)과 비교되게 UTC로 맞춘다
    job.scheduled_at = at and at.astimezone(timezone.utc)
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, job_id=job.id, action="JOB_SCHEDULE",
                    after=at.isoformat()[:50] if at else "취소"))
    db.commit()
    if at is not None and bulk.needs_web_approval(db, m.workspace_id, valid, {}):  # 예약할 때 웹 승인(예약 시각까지), 실행 때 다시 확인
        return {**_job_out(db, job), "approval": approvals.pending_reply(approvals.request_for_job(db, m, job))}
    return _job_out(db, job)


@app.get("/workspaces/{ws_id}/ad-accounts/{account_id}/adgroups/{adgroup_id}/negative-keywords")
async def negative_keywords(account_id: int, adgroup_id: str, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """광고그룹의 제외검색어. 서버에 저장하지 않고 네이버에서 바로 조회한다. 등록·삭제는 대량 작업(entity_type=negative_keyword)."""
    return [{"naver_id": k["nccAdgroupRestrictKwdId"], "adgroup_naver_id": k["nccAdgroupId"], "keyword": k["keyword"]}
            for k in _naver(db, m, account_id, lambda c: c.list_restricted_keywords(adgroup_id))]


@app.post("/workspaces/{ws_id}/bulk-jobs/{job_id}/retry-failed")
async def retry_bulk_job(job_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    return _job_out(db, bulk.retry_failed(db, m, _job(db, m, job_id, edit=True)))


# ---------- 자동입찰 (목표 순위) ----------
AUTO_BID_LIMIT = 20


class KeywordRef(BaseModel):
    ad_account_id: int
    naver_id: str
    keyword: str = ""


class AutoBidIn(BaseModel):
    keywords: list[KeywordRef]
    device: Literal["PC", "MOBILE"]
    target_rank: int
    max_bid: int
    enabled: bool = True
    ends_on: date | None = None  # 승인하는 실행 기간의 마지막 날(한국 날짜, 최대 90일 뒤). 켜는 규칙은 필수


AUTO_BID_DAYS_MAX = 90


class AutoBidKeysIn(BaseModel):
    keywords: list[KeywordRef]


def _editable(db: Session, m: Membership, refs: list[KeywordRef]) -> list[KeywordRef]:
    allowed = resolve_account_ids(db, m, None, edit=True)
    if not refs or any(k.ad_account_id not in allowed for k in refs):
        raise HTTPException(403, "키워드가 없거나 수정 권한이 없습니다")
    return refs


def _rule(db: Session, m: Membership, k: KeywordRef) -> AutoBidRule | None:
    r = db.scalar(select(AutoBidRule).where(AutoBidRule.workspace_id == m.workspace_id, AutoBidRule.keyword_naver_id == k.naver_id))
    if r and r.ad_account_id != k.ad_account_id:  # 요청한 계정은 _editable이 검사했다 — 규칙이 다른 계정 것이면 그 계정 권한 없이 못 건드린다
        raise HTTPException(403, "다른 광고 계정의 자동입찰 규칙입니다")
    return r


@app.get("/workspaces/{ws_id}/auto-bids")
async def list_auto_bids(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, None)
    q = select(AutoBidRule).where(AutoBidRule.workspace_id == m.workspace_id, AutoBidRule.ad_account_id.in_(ids)).order_by(AutoBidRule.id)
    return _rows(db.scalars(q), "id", "ad_account_id", "keyword_naver_id", "keyword", "device", "target_rank", "max_bid", "enabled",
                 "last_run_at", "last_result", "ends_on")


@app.put("/workspaces/{ws_id}/auto-bids")
async def set_auto_bids(body: AutoBidIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """선택한 키워드에 같은 규칙을 만들거나 덮어쓴다. 실행은 마지막으로 저장한 사람의 권한으로 한다."""
    hi_rank = 10 if body.device == "PC" else 5
    if not 1 <= body.target_rank <= hi_rank:
        raise HTTPException(400, f"{body.device} 목표 순위는 1~{hi_rank}위")
    lo, hi = bulk.BID_RANGE["WEB_SITE"]
    if not lo <= body.max_bid <= hi or body.max_bid % 10:
        raise HTTPException(400, f"최대 입찰가는 {lo:,}~{hi:,}원, 10원 단위")
    kws = _editable(db, m, body.keywords)
    if body.enabled:  # 저장 = 범위 승인: 대상 키워드·최대 입찰가·기간. 범위를 바꾸려면 다시 저장(재승인)
        if body.ends_on is None or not today_kst() <= body.ends_on <= today_kst() + timedelta(days=AUTO_BID_DAYS_MAX):
            raise HTTPException(400, f"자동입찰을 실행할 기간(마지막 날)을 오늘부터 {AUTO_BID_DAYS_MAX}일 안으로 정해 주세요")
        for acc in {k.ad_account_id for k in kws}:
            sf = safety.get(db, m.workspace_id, acc)
            if sf is None:
                raise HTTPException(400, safety.NOT_SET)
            if body.max_bid > sf.max_bid:
                raise HTTPException(400, f"자동입찰 최대 입찰가 {body.max_bid:,}원이 이 계정의 클릭당 최대 입찰가 {sf.max_bid:,}원보다 높아요")
    on = set(db.scalars(select(AutoBidRule.keyword_naver_id).where(AutoBidRule.workspace_id == m.workspace_id,
                                                                   AutoBidRule.enabled.is_(True))))
    # 무료 플랜은 크론 1회당 외부 호출 수 한도가 있어 키워드가 많으면 실행이 끊긴다
    if body.enabled and len(on | {k.naver_id for k in kws}) > AUTO_BID_LIMIT:
        raise HTTPException(400, f"자동입찰은 조직당 {AUTO_BID_LIMIT}개까지입니다 (지금 {len(on)}개 사용 중)")
    for k in kws:
        r = _rule(db, m, k)
        if r is None:
            r = AutoBidRule(workspace_id=m.workspace_id, keyword_naver_id=k.naver_id)
            db.add(r)
        r.ad_account_id, r.keyword = k.ad_account_id, k.keyword[:100]
        r.device, r.target_rank, r.max_bid, r.enabled, r.created_by = (body.device, body.target_rank, body.max_bid,
                                                                       body.enabled, m.user_id)
        r.ends_on = body.ends_on if body.enabled else r.ends_on
        db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=k.ad_account_id, action="AUTO_BID_SET",
                        entity_type="keyword", naver_id=k.naver_id, field="auto_bid",
                        after=(f"{body.device} {body.target_rank}위 최대 {body.max_bid} ~{body.ends_on:%m/%d}" if body.enabled else "중지")))
    db.commit()
    return {"ok": True, "scope": body.enabled and {
        "keywords": [k.keyword or k.naver_id for k in kws], "device": body.device, "target_rank": body.target_rank,
        "max_bid": body.max_bid, "ends_on": body.ends_on,
        "how": f"10분마다 순위를 읽어 목표보다 아래면 입찰가를 20% 올리고 위면 10% 내려요(최대 {body.max_bid:,}원, 키워드당 하루 "
               f"{bulk.AUTO_BID_DAILY_MAX}번까지, {body.ends_on}까지). 대상·기간·최대 입찰가를 늘리려면 다시 승인(저장)해야 해요"}}


@app.post("/workspaces/{ws_id}/auto-bids/delete")
async def delete_auto_bids(body: AutoBidKeysIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    for k in _editable(db, m, body.keywords):
        r = _rule(db, m, k)
        if r:
            db.delete(r)
            db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=k.ad_account_id,
                            action="AUTO_BID_DELETE", entity_type="keyword", naver_id=k.naver_id, field="auto_bid"))
    db.commit()
    return {"ok": True}


RANK_LIMIT = 10  # 검색 화면을 키워드마다 PC·모바일 2번 읽으므로 무료 플랜 요청당 외부 호출 한도 안에서


@app.post("/workspaces/{ws_id}/ranks")
async def keyword_ranks(body: AutoBidKeysIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """지금 순위 확인. 보기 권한이면 된다."""
    if not 1 <= len(body.keywords) <= RANK_LIMIT:
        raise HTTPException(400, f"순위 확인은 한 번에 1~{RANK_LIMIT}개입니다")
    allowed = resolve_account_ids(db, m, None)
    if any(k.ad_account_id not in allowed for k in body.keywords):
        raise HTTPException(403, "이 광고 계정을 볼 권한이 없습니다")
    return bulk.check_ranks(db, m.workspace_id, body.keywords)


@app.post("/workspaces/{ws_id}/auto-bids/run")
async def run_auto_bids(body: AutoBidKeysIn | None = None, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """지금 실행. keywords를 주면 그 키워드 규칙만. 부른 사람이 수정할 수 있는 계정의 규칙만 돈다."""
    q = select(AutoBidRule.id).where(AutoBidRule.workspace_id == m.workspace_id,
                                     AutoBidRule.ad_account_id.in_(resolve_account_ids(db, m, None, edit=True)))
    if body and body.keywords:
        q = q.where(AutoBidRule.keyword_naver_id.in_([k.naver_id for k in _editable(db, m, body.keywords)]))
    jobs = bulk.run_auto_bids(db, m.workspace_id, list(db.scalars(q)))
    return {"job_ids": [j.id for j in jobs]}


# ---------- 계정 목표 ROAS ----------
class AccountGoalIn(BaseModel):
    ad_account_id: int
    roas_target: int
    max_bid: int
    off_cost: int | None = None
    enabled: bool = True


def _goal(db: Session, m: Membership, account_id: int, edit=True) -> AccountGoal | None:
    if account_id not in resolve_account_ids(db, m, None, edit=edit):
        raise HTTPException(403, "이 광고 계정을 수정할 권한이 없습니다")
    return db.scalar(select(AccountGoal).where(AccountGoal.workspace_id == m.workspace_id, AccountGoal.ad_account_id == account_id))


@app.get("/workspaces/{ws_id}/account-goals")
async def list_account_goals(m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, None)
    q = select(AccountGoal).where(AccountGoal.workspace_id == m.workspace_id, AccountGoal.ad_account_id.in_(ids))
    return _rows(db.scalars(q), "ad_account_id", "roas_target", "max_bid", "off_cost", "enabled", "last_run_at", "last_result")


@app.put("/workspaces/{ws_id}/account-goals")
async def set_account_goal(body: AccountGoalIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """광고주 계정의 목표 ROAS를 만들거나 덮어쓴다. 실행은 마지막으로 저장한 사람의 권한으로 한다."""
    lo, hi = bulk.BID_RANGE["WEB_SITE"]
    if not 1 <= body.roas_target <= 100_000:
        raise HTTPException(400, "목표 ROAS는 1~100,000%")
    if not lo <= body.max_bid <= hi or body.max_bid % 10:
        raise HTTPException(400, f"최대 입찰가는 {lo:,}~{hi:,}원, 10원 단위")
    if body.off_cost is not None and body.off_cost <= 0:
        raise HTTPException(400, "무전환 OFF 기준 비용은 1원 이상")
    g = _goal(db, m, body.ad_account_id)
    if body.enabled:  # 목표 ROAS 자동 조정도 계정 클릭당 최대 입찰가를 넘을 수 없다
        sf = safety.get(db, m.workspace_id, body.ad_account_id)
        if sf is None:
            raise HTTPException(400, safety.NOT_SET)
        if body.max_bid > sf.max_bid:
            raise HTTPException(400, f"최대 입찰가 {body.max_bid:,}원이 이 계정의 클릭당 최대 입찰가 {sf.max_bid:,}원보다 높아요")
    if g is None:
        g = AccountGoal(workspace_id=m.workspace_id, ad_account_id=body.ad_account_id)
        db.add(g)
    g.roas_target, g.max_bid, g.off_cost, g.enabled, g.created_by = body.roas_target, body.max_bid, body.off_cost, body.enabled, m.user_id
    db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=body.ad_account_id, action="GOAL_SET",
                    entity_type="account", naver_id=str(body.ad_account_id), field="roas_goal",
                    after=f"ROAS {body.roas_target}% 최대 {body.max_bid}" + (f" 무전환 OFF {body.off_cost}" if body.off_cost else "")
                    + ("" if body.enabled else " 중지")))
    db.commit()
    return {"ok": True}


@app.delete("/workspaces/{ws_id}/account-goals/{account_id}")
async def delete_account_goal(account_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    if g := _goal(db, m, account_id):
        db.delete(g)
        db.add(AuditLog(workspace_id=m.workspace_id, user_id=m.user_id, ad_account_id=account_id, action="GOAL_DELETE",
                        entity_type="account", naver_id=str(account_id), field="roas_goal"))
        db.commit()
    return {"ok": True}


@app.post("/workspaces/{ws_id}/account-goals/{account_id}/run")
async def run_account_goal(account_id: int, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """지금 실행: 오늘 실행을 새로 시작(진행 중이면 이어서)하고 한 단계만 돈다. 나머지는 10분마다 크론이 이어 간다."""
    if not bulk.roas_automation_on():
        raise HTTPException(403, "ROAS 기준 자동 입찰 변경은 지금 정책상 쓰지 않습니다(ROAS는 보고서·추천용)")
    g = _goal(db, m, account_id)
    if g is None:
        raise HTTPException(404, "목표가 없습니다")
    bulk.run_goal_step(db, g, start=True)
    return {"last_result": g.last_result}


# ---------- 이력·성과·대시보드 ----------
@app.get("/workspaces/{ws_id}/audit-logs")
async def audit_logs(user_id: int | None = None, account_id: int | None = None, m: Membership = Depends(membership),
               db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, [account_id] if account_id else None)
    # 예약·예약 실패처럼 계정이 없는 기록은 계정을 고르지 않았을 때 같이 보인다
    # 계정 없는 기록(예약·자격증명 등)은 관리자에게는 전부, 직원에게는 자기 기록만
    unassigned = AuditLog.ad_account_id.is_(None) & (AuditLog.user_id == m.user_id) if m.role not in ADMIN_ROLES else AuditLog.ad_account_id.is_(None)
    in_scope = AuditLog.ad_account_id.in_(ids) if account_id else or_(AuditLog.ad_account_id.in_(ids), unassigned)
    s = select(AuditLog).where(AuditLog.workspace_id == m.workspace_id, in_scope)
    if user_id:
        s = s.where(AuditLog.user_id == user_id)
    return _rows(db.scalars(s.order_by(AuditLog.id.desc()).limit(500)), "id", "user_id", "ad_account_id", "job_id", "action",
                 "entity_type", "naver_id", "field", "before", "after", "created_at")


def _account_performance(db: Session, ws_id: int, ids: set[int], since: date, until: date):
    q = (select(PerformanceDaily.ad_account_id, PerformanceDaily.campaign_tp, func.sum(PerformanceDaily.impressions),
                func.sum(PerformanceDaily.clicks), func.sum(PerformanceDaily.cost), func.sum(PerformanceDaily.conversions),
                func.sum(PerformanceDaily.revenue))
         .where(PerformanceDaily.ad_account_id.in_(ids), PerformanceDaily.date.between(since, until), _own_stats(db, ws_id, ids))
         .group_by(PerformanceDaily.ad_account_id, PerformanceDaily.campaign_tp))
    names = dict(db.execute(select(AdAccount.id, AdAccount.name).where(AdAccount.id.in_(ids))).all())
    out = {i: {"ad_account_id": i, "name": names[i], "WEB_SITE": None, "SHOPPING": None, "PLACE": None} for i in ids}
    for acc, tp, imp, clk, cost, conv, rev in db.execute(q):
        out[acc][tp] = _perf(imp, clk, cost, conv, rev)
    return list(out.values())


def _perf(imp, clk, cost, conv, rev) -> dict:
    return {"impressions": imp, "clicks": clk, "cost": cost, "conversions": conv, "revenue": rev,
            "ctr": round(clk / imp * 100, 2) if imp else None, "cpc": round(cost / clk) if clk else None,
            # 매출 미제공(NULL)이면 ROAS도 NULL — 0과 구분
            "roas": round(rev / cost * 100, 1) if rev is not None and cost else None}


class EntityPerfIn(BaseModel):
    ad_account_id: int
    ids: list[str]
    since: date | None = None
    until: date | None = None


ENTITY_PERF_LIMIT = 500  # 100개당 외부 호출 1번 — 무료 플랜 요청당 한도 안에서


@app.post("/workspaces/{ws_id}/performance/entities")
async def performance_entities(body: EntityPerfIn, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """키워드·광고그룹·소재별 기간 합계. 서버에 저장하지 않고 네이버에서 바로 조회한다. 기간을 비우면 어제까지 7일."""
    if not 1 <= len(body.ids) <= ENTITY_PERF_LIMIT:
        raise HTTPException(400, f"성과 조회는 한 번에 1~{ENTITY_PERF_LIMIT}개입니다")
    until = body.until or today_kst() - timedelta(days=1)
    since = body.since or until - timedelta(days=6)
    if since > until or (until - since).days > 92:
        raise HTTPException(400, "기간은 93일 이내")
    stats = _naver(db, m, body.ad_account_id, lambda c: c.entity_stats(body.ids, since, until))
    out = []
    for i in body.ids:
        x = stats.get(i, {})
        out.append({"naver_id": i, **_perf(x.get("impCnt", 0), x.get("clkCnt", 0), x.get("salesAmt", 0), x.get("ccnt", 0),
                                           x.get("convAmt")), "avg_rank": x.get("avgRnk")})
    return {"since": since, "until": until, "rows": out}


@app.get("/workspaces/{ws_id}/performance/accounts")
async def performance_accounts(since: date | None = None, until: date | None = None, account_ids: str | None = None,
                         m: Membership = Depends(membership), db: Session = Depends(get_db)):
    until = until or today_kst() - timedelta(days=1)
    since = since or until - timedelta(days=6)
    return _account_performance(db, m.workspace_id, resolve_account_ids(db, m, _ids(account_ids)), since, until)


@app.get("/workspaces/{ws_id}/performance/daily")
async def performance_daily(since: date, until: date, account_ids: str | None = None, product: ProductType = None,
                            m: Membership = Depends(membership), db: Session = Depends(get_db)):
    """일별 합계. 동기화된 행이 없는 날은 0 (전환·매출은 미제공 NULL 유지)."""
    if since > until or (until - since).days > 92:
        raise HTTPException(400, "기간은 93일 이내")
    ids = resolve_account_ids(db, m, _ids(account_ids))
    q = (select(PerformanceDaily.date, func.sum(PerformanceDaily.impressions), func.sum(PerformanceDaily.clicks),
                func.sum(PerformanceDaily.cost), func.sum(PerformanceDaily.conversions), func.sum(PerformanceDaily.revenue))
         .where(PerformanceDaily.ad_account_id.in_(ids), PerformanceDaily.date.between(since, until), _own_stats(db, m.workspace_id, ids))
         .group_by(PerformanceDaily.date))
    if product:
        q = q.where(PerformanceDaily.campaign_tp == product)
    # D1은 날짜를 문자열로 돌려줄 수 있어 문자열 키로 맞춘다
    by_day = {str(d)[:10]: (imp, clk, cost, conv, rev) for d, imp, clk, cost, conv, rev in db.execute(q)}
    out, d = [], since
    while d <= until:
        imp, clk, cost, conv, rev = by_day.get(d.isoformat(), (0, 0, 0, None, None))
        out.append({"date": d.isoformat(), "impressions": imp, "clicks": clk, "cost": cost, "conversions": conv, "revenue": rev})
        d += timedelta(days=1)
    return out


@app.get("/workspaces/{ws_id}/dashboard")
async def dashboard(account_ids: str | None = None, m: Membership = Depends(membership), db: Session = Depends(get_db)):
    ids = resolve_account_ids(db, m, None)
    selected = resolve_account_ids(db, m, _ids(account_ids))
    jobs = _visible_jobs(db, m, db.scalars(select(BulkJob).where(BulkJob.workspace_id == m.workspace_id, BulkJob.status != "PREVIEW")
                                           .order_by(BulkJob.id.desc()).limit(50)).all())[:10]
    # 엑셀 작업은 행이 수천 개일 수 있어 행을 다 읽지 않고 상태별 개수만 센다(무료 플랜 CPU 한도)
    counts: dict[int, dict] = {j.id: dict.fromkeys(("VALID", "INVALID", "SUCCESS", "FAILED"), 0) for j in jobs}
    for job_id, status, n in db.execute(select(BulkJobRow.job_id, BulkJobRow.status, func.count())
                                        .where(BulkJobRow.job_id.in_(list(counts))).group_by(BulkJobRow.job_id, BulkJobRow.status)):
        counts[job_id][status] = n
    failed_syncs = [{"ad_account_id": i, "error": s.error, "at": s.finished_at} for i, s in _last_syncs(db, m.workspace_id, ids).items() if s.status == "FAILED"]
    return {
        "connected_accounts": len(ids),
        "recent_jobs": [_rows([j], "id", "status", "source", "parent_job_id", "created_by", "created_at", "executed_at", "scheduled_at")[0]
                        | {"counts": counts[j.id], "accounts": None} for j in jobs],
        "failed_jobs": [j.id for j in jobs if j.status in ("PARTIAL", "FAILED")],
        "sync_errors": failed_syncs,
        "auto_bids": db.scalar(select(func.count()).select_from(AutoBidRule).where(
            AutoBidRule.workspace_id == m.workspace_id, AutoBidRule.ad_account_id.in_(selected), AutoBidRule.enabled.is_(True))),
    }


# ---------- 구독 (광고 관리와 분리) ----------
@app.get("/workspaces/{ws_id}/subscription")
async def subscription(m: Membership = Depends(admin_membership), db: Session = Depends(get_db)):
    sub = db.scalar(select(Subscription).where(Subscription.workspace_id == m.workspace_id))
    plan = db.get(Plan, sub.plan_code)
    billable = db.scalar(select(func.count()).select_from(WorkspaceAdAccount).where(
        WorkspaceAdAccount.workspace_id == m.workspace_id, WorkspaceAdAccount.status == "CONNECTED"))
    return {"plan": plan.name, "status": sub.status, "trial_ends_at": sub.trial_ends_at, "billable_accounts": billable,
            "price_per_account": plan.price_per_account, "monthly_total": billable * plan.price_per_account}


# Claude 커넥터(MCP)는 위 엔드포인트 함수들을 불러 쓰므로 맨 아래에서 등록
from . import approvals, mcp, place, shopping_ads  # noqa: E402

app.include_router(approvals.router)
app.include_router(mcp.router)
app.include_router(shopping_ads.router)
app.include_router(place.router)
