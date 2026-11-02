"""DB 모델. 설계는 docs/DB_SCHEMA.md."""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now():
    return datetime.now(timezone.utc)


KST = timezone(timedelta(hours=9))


def today_kst() -> date:
    """네이버 통계의 '하루'는 한국 날짜다. 서버 시계(UTC)의 date.today()는 오전 9시 전까지 하루 늦다."""
    return datetime.now(KST).date()


# ---- 테넌트·권한 ----
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))
    token_version: Mapped[int] = mapped_column(Integer, default=0)  # 올리면 이전 토큰이 모두 무효(비밀번호 변경·모든 기기 로그아웃)
    mcp_version: Mapped[int] = mapped_column(Integer, default=0)  # 올리면 Claude(MCP) 토큰만 무효
    # Google 계정 고유 식별자(id_token의 sub). 이메일이 아니라 이 값으로 Google 로그인을 찾는다(0016)
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)


class LoginFailure(Base):
    """로그인 실패 횟수. key는 "email:주소" 또는 "ip:주소", first_at부터 LOGIN_WINDOW 동안 센다."""
    __tablename__ = "login_failures"
    key: Mapped[str] = mapped_column(String(330), primary_key=True)
    count: Mapped[int] = mapped_column(Integer)
    first_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class OAuthUsed(Base):
    """한 번 쓴 인가 코드·갱신 토큰(sha256). expires_at이 지나면 토큰 자체가 만료라 지워도 된다."""
    __tablename__ = "oauth_used"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ApprovalRequest(Base):
    """승인 후 실행하는 광고 변경.
    - kind='place': 플레이스 계획(place.py). tool='place:<action>', payload=정확한 변경 내용 JSON.
    - kind='job': 대량 작업(bulk_jobs) 실행 승인. job_id에 묶이고 payload_hash는 그때의 실행할 행들로 계산한다.
    web_required=True(계정 하루예산 합계를 늘릴 수 있는 변경)면 웹에 로그인한 사람이 /approvals에서 승인해야만 실행된다(Claude 토큰은 승인 불가).
    상태: PENDING → (APPROVED: 예약 작업이 시각을 기다림) → RUNNING → DONE|PARTIAL|FAILED, 또는 REJECTED|EXPIRED."""
    __tablename__ = "approval_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    tool: Mapped[str] = mapped_column(String(40))
    payload: Mapped[str] = mapped_column(String(8000))  # 도구 인자 JSON(SQLite·D1은 길이를 강제하지 않음)
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(10), default="PENDING")
    result: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    kind: Mapped[str] = mapped_column(String(10), default="place")  # place | job (0016)
    ad_account_id: Mapped[int | None] = mapped_column(ForeignKey("ad_accounts.id"), nullable=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("bulk_jobs.id"), nullable=True, index=True)
    web_required: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str | None] = mapped_column(String(8000), nullable=True)  # 승인 화면에 보여 준 내용 JSON(대상·전후 값·합계·안내)


class AccountLock(Base):
    """광고 계정별 실행 잠금(safety.account_lock). 같은 계정의 비용 변경이 동시에 검사를 통과하지 않게 한다.
    expires_at이 지나면 죽은 요청의 잠금으로 보고 다른 요청이 가져간다(0016)."""
    __tablename__ = "account_locks"
    ad_account_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    holder: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(20), default="AGENCY")  # AGENCY | DIRECT_ADVERTISER


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(10))  # OWNER | ADMIN | MEMBER


class NaverApiCredential(Base):
    __tablename__ = "naver_api_credentials"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"))
    label: Mapped[str] = mapped_column(String(100))
    api_key: Mapped[str] = mapped_column(String(255))
    secret_key_enc: Mapped[str] = mapped_column(String(500))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)


class AdAccount(Base):
    __tablename__ = "ad_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    is_mock: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkspaceAdAccount(Base):
    __tablename__ = "workspace_ad_accounts"
    __table_args__ = (UniqueConstraint("workspace_id", "ad_account_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"))
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"))
    credential_id: Mapped[int] = mapped_column(ForeignKey("naver_api_credentials.id"))
    status: Mapped[str] = mapped_column(String(15), default="CONNECTED")  # CONNECTED | DISCONNECTED
    connected_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AccountAccess(Base):
    __tablename__ = "account_access"
    __table_args__ = (UniqueConstraint("membership_id", "ad_account_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    membership_id: Mapped[int] = mapped_column(ForeignKey("memberships.id"))
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"))
    level: Mapped[str] = mapped_column(String(5))  # VIEW | EDIT


# ---- 광고 데이터 사본(캠페인~확장소재)은 서버에 두지 않는다: 브라우저가 마스터 보고서로 받아 보관(frontend/lib/naverData.ts) ----
class PerformanceDaily(Base):
    __tablename__ = "performance_daily"
    __table_args__ = (UniqueConstraint("campaign_naver_id", "date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    campaign_naver_id: Mapped[str] = mapped_column(String(50))
    campaign_tp: Mapped[str] = mapped_column(String(20))  # WEB_SITE | SHOPPING
    date: Mapped[date] = mapped_column(Date)
    impressions: Mapped[int] = mapped_column(Integer)
    clicks: Mapped[int] = mapped_column(Integer)
    cost: Mapped[int] = mapped_column(Integer)
    conversions: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL = 미제공
    revenue: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AccountSafety(Base):
    """광고비 안전장치(조직·광고 계정별). 관리자가 금액을 직접 확인해 저장한다. 없으면 비용이 늘 수 있는 작업은 막힌다(safety.py)."""
    __tablename__ = "account_safety"
    __table_args__ = (UniqueConstraint("workspace_id", "ad_account_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"))
    daily_budget_limit: Mapped[int] = mapped_column(Integer)  # 켜진 캠페인 하루예산 설정액 합계의 관리 기준(원)
    max_bid: Mapped[int] = mapped_column(Integer)  # 클릭당 최대 입찰가(원)
    set_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AutoBidRule(Base):
    """키워드 자동입찰: 목표 순위의 예상 입찰가로 맞추되 최대 입찰가를 넘지 않는다. 실행은 만든 사람 권한으로."""
    __tablename__ = "auto_bid_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    __table_args__ = (UniqueConstraint("workspace_id", "keyword_naver_id"),)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"))
    keyword_naver_id: Mapped[str] = mapped_column(String(50))
    keyword: Mapped[str] = mapped_column(String(100))  # 화면 표시용(설정 시점)
    device: Mapped[str] = mapped_column(String(6))  # PC | MOBILE
    target_rank: Mapped[int] = mapped_column(Integer)
    max_bid: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))  # 범위(대상·최대 입찰가·기간)를 승인한 사람
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)  # 승인한 실행 기간의 마지막 날(한국 날짜). NULL = 승인 전(0015 이전 규칙)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result: Mapped[str | None] = mapped_column(String(300), nullable=True)


# ---- 작업·감사 ----
class AccountGoal(Base):
    """광고주 계정 목표 ROAS: 하루 한 번 파워링크 키워드를 광고그룹씩 나눠 최근 7일 ROAS로 조정(bulk.run_goal_step).
    실행은 마지막으로 저장한 사람 권한으로."""
    __tablename__ = "account_goals"
    __table_args__ = (UniqueConstraint("workspace_id", "ad_account_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"))
    roas_target: Mapped[int] = mapped_column(Integer)  # %
    max_bid: Mapped[int] = mapped_column(Integer)
    off_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 키워드 7일 비용이 이 이상인데 전환 0이면 OFF
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    run_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 마지막으로 시작한 날(한국 날짜)
    state: Mapped[str | None] = mapped_column(String(4000), nullable=True)  # 진행 중 실행 JSON: 남은 광고그룹·집계·작업 ID
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_result: Mapped[str | None] = mapped_column(String(300), nullable=True)


class BulkJob(Base):
    __tablename__ = "bulk_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(10))  # UI | EXCEL | RETRY | AUTO_BID
    status: Mapped[str] = mapped_column(String(10), default="PREVIEW")  # PREVIEW|RUNNING|DONE|PARTIAL|FAILED
    parent_job_id: Mapped[int | None] = mapped_column(ForeignKey("bulk_jobs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # 예약 실행(크론이 이 시각 이후 실행)


class BulkJobRow(Base):
    __tablename__ = "bulk_job_rows"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("bulk_jobs.id"), index=True)
    ad_account_id: Mapped[int | None] = mapped_column(ForeignKey("ad_accounts.id"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(20))  # SQLite·D1은 길이를 강제하지 않아 마이그레이션 불필요
    naver_id: Mapped[str] = mapped_column(String(50))
    field: Mapped[str] = mapped_column(String(20))
    before: Mapped[str | None] = mapped_column(String(50), nullable=True)
    after: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(10))  # VALID | INVALID | SUCCESS | FAILED
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    ad_account_id: Mapped[int | None] = mapped_column(ForeignKey("ad_accounts.id"), nullable=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("bulk_jobs.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(30))  # UPDATE | CREATE | DELETE | ACCOUNT_CONNECT | ACCOUNT_DISCONNECT | ACCESS_SET
    entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # ad_extension은 10자 초과
    naver_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    field: Mapped[str | None] = mapped_column(String(20), nullable=True)
    before: Mapped[str | None] = mapped_column(String(50), nullable=True)
    after: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SyncRun(Base):
    __tablename__ = "sync_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    # 동기화한 조직(같은 계정을 여러 조직이 연결할 수 있다). NULL = 0014 이전 기록 중 주인을 알 수 없는 것
    workspace_id: Mapped[int | None] = mapped_column(ForeignKey("workspaces.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(10))  # SUCCESS | FAILED
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---- 구독 (광고 관리 테이블과 분리) ----
class Plan(Base):
    __tablename__ = "plans"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    price_per_account: Mapped[int] = mapped_column(Integer)
    trial_days: Mapped[int] = mapped_column(Integer)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), unique=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"))
    status: Mapped[str] = mapped_column(String(10))  # TRIALING | ACTIVE | CANCELED
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
