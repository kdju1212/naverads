"""인증과 광고 계정 단위 접근 검증. 모든 조회·쓰기는 여기를 거친다."""
import hashlib
import os

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import AccountAccess, Membership, OAuthUsed, User, WorkspaceAdAccount
from .security import read_token

ADMIN_ROLES = {"OWNER", "ADMIN"}
# 웹 로그인은 HttpOnly 쿠키(브라우저 JS가 토큰을 읽을 수 없음). Bearer 헤더는 Claude(/mcp)와 테스트·API 문서용으로 남긴다.
SESSION_COOKIE = "naverads_session"
CSRF_HEADER = "x-naverads-csrf"  # 쿠키로 로그인한 쓰기 요청은 이 헤더가 있어야 한다(다른 사이트 폼·링크는 이 헤더를 못 붙인다)
# 로그인 쿠키를 쓰는 웹 주소(CORS·출처 검사·로그인 후 돌려보낼 주소). 로컬 화면 주소는 로컬(APP_ENV=dev)에서만
WEB_ORIGINS = {"https://naverads.djkim0509.workers.dev"} | ({"http://localhost:3000"} if os.getenv("APP_ENV", "dev") == "dev" else set())
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def logged_out_key(token: str) -> str:
    """로그아웃한 로그인 토큰의 기록 키(oauth_used 표를 같이 쓴다. 토큰 자체가 아니라 해시만 저장).
    shortcut: 토큰에 무작위 값(jti)이 없다. 웹 토큰은 만료 시각에 무작위를 섞어(security.make_token) 같은 초 로그인도 대개 다른 토큰이다.
    기기마다 따로 끊어야 할 일이 생기면 토큰에 무작위 값(jti)을 넣는다"""
    return hashlib.sha256(f"logout:{token}".encode()).hexdigest()


def user_from_header(db: Session, authorization: str, allow_mcp: bool = False) -> User:
    """allow_mcp: Claude 연결 출입증은 /mcp에서만 받는다. 일반 API(직접 실행·예약 등)를 Claude 토큰으로 부르지 못하게."""
    token = authorization.removeprefix("Bearer ").strip()
    t = read_token(token)
    if t and t[2] is not None and not allow_mcp:
        t = None
    if t and db.get(OAuthUsed, logged_out_key(token)):  # 이 기기에서 로그아웃한 토큰
        t = None
    user = db.get(User, t[0]) if t else None
    # 비밀번호 변경·모든 기기 로그아웃 이전 토큰, 또는 Claude 연결 끊기 이전의 Claude 토큰
    if not user or user.token_version != t[1] or (t[2] is not None and t[2] != user.mcp_version):
        raise HTTPException(401, "로그인이 필요합니다")
    return user


def membership_of(db: Session, ws_id: int, user: User) -> Membership:
    m = db.scalar(select(Membership).where(Membership.workspace_id == ws_id, Membership.user_id == user.id))
    if not m:
        raise HTTPException(403, "이 조직에 접근 권한이 없습니다")
    return m


def session_token(request: Request, authorization: str = "") -> tuple[str, bool]:
    """(토큰, 쿠키에서 왔는지). Authorization 헤더가 있으면 그것을, 없으면 로그인 쿠키를 쓴다."""
    if authorization.strip():
        return authorization.removeprefix("Bearer ").strip(), False
    return request.cookies.get(SESSION_COOKIE, ""), True


def check_csrf(request: Request):
    """쿠키 인증 쓰기 요청: CSRF 헤더가 있고, 출처(Origin)가 있으면 웹 주소여야 한다. CORS도 웹 주소만 허용(main)."""
    origin = request.headers.get("origin")
    if request.method not in SAFE_METHODS and (request.headers.get(CSRF_HEADER) != "1" or (origin and origin not in WEB_ORIGINS)):
        raise HTTPException(403, "요청을 확인할 수 없어요. 화면을 새로고침한 뒤 다시 해 주세요")


async def current_user(request: Request, authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    token, from_cookie = session_token(request, authorization)
    if from_cookie and token:
        check_csrf(request)
    return user_from_header(db, f"Bearer {token}")


async def membership(ws_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Membership:
    return membership_of(db, ws_id, user)


async def admin_membership(m: Membership = Depends(membership)) -> Membership:
    if m.role not in ADMIN_ROLES:
        raise HTTPException(403, "관리자 권한이 필요합니다")
    return m


def accessible_account_ids(db: Session, m: Membership, edit: bool = False) -> set[int]:
    connected = set(db.scalars(select(WorkspaceAdAccount.ad_account_id).where(
        WorkspaceAdAccount.workspace_id == m.workspace_id, WorkspaceAdAccount.status == "CONNECTED")))
    if m.role in ADMIN_ROLES:
        return connected
    q = select(AccountAccess.ad_account_id).where(AccountAccess.membership_id == m.id)
    if edit:
        q = q.where(AccountAccess.level == "EDIT")
    return connected & set(db.scalars(q))


def resolve_account_ids(db: Session, m: Membership, requested: list[int] | None, edit: bool = False) -> set[int]:
    """요청한 계정이 하나라도 권한 밖이면 403. 요청이 없으면 접근 가능한 전체."""
    allowed = accessible_account_ids(db, m, edit)
    if not requested:
        return allowed
    denied = set(requested) - allowed
    if denied:
        raise HTTPException(403, f"권한이 없는 광고 계정: {sorted(denied)}")
    return set(requested)
