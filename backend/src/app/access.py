"""인증과 광고 계정 단위 접근 검증. 모든 조회·쓰기는 여기를 거친다."""
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import AccountAccess, Membership, User, WorkspaceAdAccount
from .security import read_token

ADMIN_ROLES = {"OWNER", "ADMIN"}


async def current_user(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> User:
    uid = read_token(authorization.removeprefix("Bearer ").strip())
    user = db.get(User, uid) if uid else None
    if not user:
        raise HTTPException(401, "로그인이 필요합니다")
    return user


async def membership(ws_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)) -> Membership:
    m = db.scalar(select(Membership).where(Membership.workspace_id == ws_id, Membership.user_id == user.id))
    if not m:
        raise HTTPException(403, "이 조직에 접근 권한이 없습니다")
    return m


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
