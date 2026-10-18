"""DB 모델. 설계는 docs/DB_SCHEMA.md."""
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now():
    return datetime.now(timezone.utc)


# ---- 테넌트·권한 ----
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(100))


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


# ---- 광고 데이터 (네이버 동기화 사본) ----
class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    naver_id: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    campaign_tp: Mapped[str] = mapped_column(String(20))  # WEB_SITE | SHOPPING
    status: Mapped[str] = mapped_column(String(3))  # ON | OFF
    daily_budget: Mapped[int] = mapped_column(Integer, default=0)


class AdGroup(Base):
    __tablename__ = "adgroups"
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    naver_id: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    adgroup_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(3))
    bid_amt: Mapped[int] = mapped_column(Integer)


class Keyword(Base):
    """파워링크 전용."""
    __tablename__ = "keywords"
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    adgroup_id: Mapped[int] = mapped_column(ForeignKey("adgroups.id"))
    naver_id: Mapped[str] = mapped_column(String(50), unique=True)
    keyword: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(3))
    bid_amt: Mapped[int] = mapped_column(Integer)
    use_group_bid: Mapped[bool] = mapped_column(Boolean, default=False)


class Ad(Base):
    """TEXT_45(파워링크 소재) | SHOPPING_PRODUCT_AD(쇼핑 상품소재, 소재 단위 입찰가)."""
    __tablename__ = "ads"
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    adgroup_id: Mapped[int] = mapped_column(ForeignKey("adgroups.id"))
    naver_id: Mapped[str] = mapped_column(String(50), unique=True)
    ad_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(3))
    inspect_status: Mapped[str] = mapped_column(String(20))
    bid_amt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    use_group_bid: Mapped[bool] = mapped_column(Boolean, default=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class AdExtension(Base):
    """파워링크 확장소재. 소유자는 캠페인 또는 광고그룹(네이버 ID). 현재는 조회 전용."""
    __tablename__ = "ad_extensions"
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    naver_id: Mapped[str] = mapped_column(String(50), unique=True)
    owner_naver_id: Mapped[str] = mapped_column(String(50))
    ext_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(3))
    inspect_status: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict | list] = mapped_column(JSON, default=dict)


class PerformanceDaily(Base):
    __tablename__ = "performance_daily"
    __table_args__ = (UniqueConstraint("campaign_id", "date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_account_id: Mapped[int] = mapped_column(ForeignKey("ad_accounts.id"), index=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"))
    date: Mapped[date] = mapped_column(Date)
    impressions: Mapped[int] = mapped_column(Integer)
    clicks: Mapped[int] = mapped_column(Integer)
    cost: Mapped[int] = mapped_column(Integer)
    conversions: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL = 미제공
    revenue: Mapped[int | None] = mapped_column(Integer, nullable=True)


# ---- 작업·감사 ----
class BulkJob(Base):
    __tablename__ = "bulk_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspaces.id"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(10))  # UI | EXCEL | RETRY
    status: Mapped[str] = mapped_column(String(10), default="PREVIEW")  # PREVIEW|RUNNING|DONE|PARTIAL|FAILED
    parent_job_id: Mapped[int | None] = mapped_column(ForeignKey("bulk_jobs.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


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
