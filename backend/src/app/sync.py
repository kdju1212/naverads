"""성과 통계 동기화(캠페인별 일별). 광고 데이터 사본은 서버에 두지 않는다(브라우저가 마스터 보고서로 받음).
계정 연결 시 접근 확인도 이것으로 한다."""
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import AdAccount, PerformanceDaily, SyncRun, now, today_kst
from .naver import NaverApiError

STATS_DAYS = 30


def sync_account(db: Session, account: AdAccount, client) -> SyncRun:
    run = SyncRun(ad_account_id=account.id, status="SUCCESS")
    db.add(run)
    try:
        campaigns = {c["nccCampaignId"]: c["campaignTp"] for c in client.list_campaigns()
                     if c["campaignTp"] in ("WEB_SITE", "SHOPPING")}  # MVP 범위 밖 캠페인 유형은 저장하지 않는다
        _sync_stats(db, account, client, campaigns)
    except NaverApiError as e:
        db.rollback()
        run.status, run.error = "FAILED", str(e)[:300]
        db.add(run)
    run.finished_at = now()
    db.commit()
    return run


def _sync_stats(db: Session, account: AdAccount, client, campaigns: dict[str, str]):
    until = today_kst() - timedelta(days=1)
    since = until - timedelta(days=STATS_DAYS - 1)
    # 네이버에서 지운 캠페인의 통계는 지운다
    db.execute(delete(PerformanceDaily).where(PerformanceDaily.ad_account_id == account.id,
                                              PerformanceDaily.campaign_naver_id.not_in(list(campaigns))))
    existing = {(r.campaign_naver_id, r.date): r for r in db.scalars(select(PerformanceDaily).where(
        PerformanceDaily.ad_account_id == account.id, PerformanceDaily.date.between(since, until)))}
    for s in client.stats(list(campaigns), since, until):
        row = existing.get((s["id"], s["date"]))
        if row is None:
            row = PerformanceDaily(ad_account_id=account.id, campaign_naver_id=s["id"], campaign_tp=campaigns[s["id"]], date=s["date"])
            db.add(row)
        row.impressions, row.clicks, row.cost = s["impCnt"], s["clkCnt"], s["salesAmt"]
        row.conversions, row.revenue = s.get("ccnt"), s.get("convAmt")
    db.commit()
