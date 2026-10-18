"""네이버 → 로컬 DB 동기화. 계정 단위로 전체 교체(upsert)한다."""
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Ad, AdAccount, AdGroup, Campaign, Keyword, PerformanceDaily, SyncRun, now
from .naver import NaverApiError

STATS_DAYS = 30


def _upsert(db: Session, model, naver_id: str, **fields):
    obj = db.scalar(select(model).where(model.naver_id == naver_id))
    if obj is None:
        obj = model(naver_id=naver_id)
        db.add(obj)
    for k, v in fields.items():
        setattr(obj, k, v)
    db.flush()
    return obj


def _status(o):
    return "OFF" if o.get("userLock") else "ON"


def sync_account(db: Session, account: AdAccount, client) -> SyncRun:
    run = SyncRun(ad_account_id=account.id, status="SUCCESS")
    db.add(run)
    try:
        aid = account.id
        campaigns = []
        for c in client.list_campaigns():
            if c["campaignTp"] not in ("WEB_SITE", "SHOPPING"):
                continue  # MVP 범위 밖 캠페인 유형은 저장하지 않는다
            camp = _upsert(db, Campaign, c["nccCampaignId"], ad_account_id=aid, name=c["name"], campaign_tp=c["campaignTp"],
                           status=_status(c), daily_budget=c.get("dailyBudget") or 0)
            campaigns.append(camp)
            for g in client.list_adgroups(camp.naver_id):
                grp = _upsert(db, AdGroup, g["nccAdgroupId"], ad_account_id=aid, campaign_id=camp.id, name=g["name"],
                              adgroup_type=g["adgroupType"], status=_status(g), bid_amt=g["bidAmt"])
                if grp.adgroup_type == "WEB_SITE":
                    for k in client.list_keywords(grp.naver_id):
                        _upsert(db, Keyword, k["nccKeywordId"], ad_account_id=aid, adgroup_id=grp.id, keyword=k["keyword"],
                                status=_status(k), bid_amt=k["bidAmt"], use_group_bid=k.get("useGroupBidAmt", False))
                for a in client.list_ads(grp.naver_id):
                    attr = a.get("adAttr") or {}
                    _upsert(db, Ad, a["nccAdId"], ad_account_id=aid, adgroup_id=grp.id, ad_type=a["type"], status=_status(a),
                            inspect_status=a.get("inspectStatus", ""), bid_amt=attr.get("bidAmt"),
                            use_group_bid=attr.get("useGroupBidAmt", True), payload=a.get("ad", {}))
        db.commit()
        _sync_stats(db, account, client, campaigns)
    except NaverApiError as e:
        db.rollback()
        run.status, run.error = "FAILED", str(e)[:300]
        db.add(run)
    run.finished_at = now()
    db.commit()
    return run


def _sync_stats(db: Session, account: AdAccount, client, campaigns: list[Campaign]):
    by_naver = {c.naver_id: c for c in campaigns}
    until = date.today() - timedelta(days=1)
    for s in client.stats(list(by_naver), until - timedelta(days=STATS_DAYS - 1), until):
        camp = by_naver[s["id"]]
        row = db.scalar(select(PerformanceDaily).where(PerformanceDaily.campaign_id == camp.id, PerformanceDaily.date == s["date"]))
        if row is None:
            row = PerformanceDaily(ad_account_id=account.id, campaign_id=camp.id, date=s["date"])
            db.add(row)
        row.impressions, row.clicks, row.cost = s["impCnt"], s["clkCnt"], s["salesAmt"]
        row.conversions, row.revenue = s.get("ccnt"), s.get("convAmt")
    db.commit()
