"""성과 통계 동기화(캠페인별 일별). 광고 데이터 사본은 서버에 두지 않는다(브라우저가 마스터 보고서로 받음).
계정 연결 시 접근 확인도 이것으로 한다."""
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import AdAccount, PerformanceDaily, SyncRun, now, today_kst
from .naver import NaverApiError

STATS_DAYS = 30
# 일별 통계는 캠페인마다 네이버 호출 1번이라, 무료 플랜 요청당 호출 한도(50) 안에서 캠페인을 이만큼씩 나눠 받는다
SYNC_CHUNK = 30


def sync_account(db: Session, account: AdAccount, client, offset: int = 0) -> tuple[SyncRun | None, int | None]:
    """offset번째 캠페인부터 SYNC_CHUNK개. 남았으면 (None, 다음 offset) — 화면이 그 offset으로 다시 부른다.
    다 받았거나 실패하면 (SyncRun, None)."""
    try:
        campaigns = {c["nccCampaignId"]: c["campaignTp"] for c in client.list_campaigns()
                     if c["campaignTp"] in ("WEB_SITE", "SHOPPING")}  # MVP 범위 밖 캠페인 유형은 저장하지 않는다
        ids = sorted(campaigns)  # 나눠 받는 동안 순서가 바뀌지 않게
        _sync_stats(db, account, client, campaigns, ids[offset:offset + SYNC_CHUNK], prune=offset == 0)
    except NaverApiError as e:
        db.rollback()
        run = SyncRun(ad_account_id=account.id, status="FAILED", error=str(e)[:300], finished_at=now())
        db.add(run)
        db.commit()
        return run, None
    if offset + SYNC_CHUNK < len(ids):
        return None, offset + SYNC_CHUNK
    run = SyncRun(ad_account_id=account.id, status="SUCCESS", finished_at=now())
    db.add(run)
    db.commit()
    return run, None


def _sync_stats(db: Session, account: AdAccount, client, campaigns: dict[str, str], chunk: list[str], prune: bool):
    until = today_kst() - timedelta(days=1)
    since = until - timedelta(days=STATS_DAYS - 1)
    if prune:  # 네이버에서 지운 캠페인의 통계는 지운다
        db.execute(delete(PerformanceDaily).where(PerformanceDaily.ad_account_id == account.id,
                                                  PerformanceDaily.campaign_naver_id.not_in(list(campaigns))))
    existing = {(r.campaign_naver_id, r.date): r for r in db.scalars(select(PerformanceDaily).where(
        PerformanceDaily.ad_account_id == account.id, PerformanceDaily.campaign_naver_id.in_(chunk),
        PerformanceDaily.date.between(since, until)))}
    for s in client.stats(chunk, since, until):
        row = existing.get((s["id"], s["date"]))
        if row is None:
            row = PerformanceDaily(ad_account_id=account.id, campaign_naver_id=s["id"], campaign_tp=campaigns[s["id"]], date=s["date"])
            db.add(row)
        row.impressions, row.clicks, row.cost = s["impCnt"], s["clkCnt"], s["salesAmt"]
        row.conversions, row.revenue = s.get("ccnt"), s.get("convAmt")
    db.commit()
