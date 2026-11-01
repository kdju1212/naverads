"""인증과 광고 계정 단위 접근 검증. 모든 조회·쓰기는 여기를 거친다."""
import hashlib

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import AccountAccess, Membership, OAuthUsed, User, WorkspaceAdAccount
from .security import read_token

ADMIN_ROLES = {"OWNER", "ADMIN"}


def logged_out_key(token: str) -> str:
    """로그아웃한 로그인 토큰의 기록 키(oauth_used 표를 같이 쓴다. 토큰 자체가 아니라 해시만 저장).
    shortcut: 토큰에 무작위 값이 없어 같은 사용자가 같은 초에 두 번 로그인하면 토큰이 같고, 하나를 로그아웃하면 둘 다 끊긴다.
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


async def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    return user_from_header(db, authorization)


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
