"""네이버 → 로컬 DB 동기화. 계정 단위로 전체 교체(upsert)한다."""
import json
from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Ad, AdAccount, AdExtension, AdGroup, AutoBidRule, Campaign, Keyword, PerformanceDaily, SyncRun, now
from .naver import NaverApiError, _json, _rsa_texts, _status

STATS_DAYS = 30


class _Upserter:
    """계정의 기존 객체를 모델당 한 번에 읽어 두고 upsert. 객체마다 SELECT하면 Workers에서 CPU 한도를 넘는다."""

    def __init__(self, db: Session, account_id: int):
        self.db, self.aid, self.cache, self.seen = db, account_id, {}, set()

    def _load(self, model):
        if model not in self.cache:
            self.cache[model] = {o.naver_id: o for o in self.db.scalars(select(model).where(model.ad_account_id == self.aid))}
        return self.cache[model]

    def __call__(self, model, naver_id: str, **fields):
        self.seen.add((model, naver_id))
        obj = self._load(model).get(naver_id)
        if obj is None:
            obj = self.cache[model][naver_id] = model(naver_id=naver_id, ad_account_id=self.aid)
            self.db.add(obj)
        for k, v in fields.items():
            setattr(obj, k, v)
        return obj

    def remove_stale(self):
        """이번 동기화에서 네이버가 돌려주지 않은 객체를 지운다. 목록 조회가 전부 성공한 뒤에만 호출할 것."""
        gone = {m: [o for nid, o in self._load(m).items() if (m, nid) not in self.seen]
                for m in (Campaign, AdGroup, Keyword, Ad, AdExtension)}
        if gone[Keyword]:
            self.db.execute(delete(AutoBidRule).where(AutoBidRule.keyword_id.in_([k.id for k in gone[Keyword]])))
        if gone[Campaign]:
            self.db.execute(delete(PerformanceDaily).where(PerformanceDaily.campaign_id.in_([c.id for c in gone[Campaign]])))
        for m in (Keyword, Ad, AdExtension, AdGroup, Campaign):  # 외래키: 자식부터
            for o in gone[m]:
                self.db.delete(o)
            self.db.flush()


def _sync_extensions(_upsert, client, owner_id: str):
    for e in client.list_ad_extensions(owner_id):
        _upsert(AdExtension, e["nccAdExtensionId"], owner_naver_id=owner_id, ext_type=e["type"], status=_status(e),
                inspect_status=e.get("inspectStatus", ""), payload=_json(e.get("adExtension")))


def sync_account(db: Session, account: AdAccount, client) -> SyncRun:
    run = SyncRun(ad_account_id=account.id, status="SUCCESS")
    db.add(run)
    try:
        aid = account.id
        _upsert = _Upserter(db, aid)
        campaigns = []
        for c in client.list_campaigns():
            if c["campaignTp"] not in ("WEB_SITE", "SHOPPING"):
                continue  # MVP 범위 밖 캠페인 유형은 저장하지 않는다
            camp = _upsert(Campaign, c["nccCampaignId"], ad_account_id=aid, name=c["name"], campaign_tp=c["campaignTp"],
                           status=_status(c), daily_budget=c.get("dailyBudget") or 0)
            db.flush()
            campaigns.append(camp)
            if camp.campaign_tp == "WEB_SITE":
                _sync_extensions(_upsert, client, camp.naver_id)
            for g in client.list_adgroups(camp.naver_id):
                grp = _upsert(AdGroup, g["nccAdgroupId"], ad_account_id=aid, campaign_id=camp.id, name=g["name"],
                              adgroup_type=g["adgroupType"], status=_status(g), bid_amt=g["bidAmt"],
                              # shortcut: 공유예산(sharedBudgetId) 그룹은 반영 안 함, 쓰는 계정이 생기면 sharedDailyBudget 표시
                              daily_budget=g.get("dailyBudget") if g.get("useDailyBudget") else None,
                              serving=g.get("statusReason") or g.get("status"))
                db.flush()
                if grp.adgroup_type == "WEB_SITE":
                    _sync_extensions(_upsert, client, grp.naver_id)
                    for k in client.list_keywords(grp.naver_id):
                        _upsert(Keyword, k["nccKeywordId"], ad_account_id=aid, adgroup_id=grp.id, keyword=k["keyword"],
                                status=_status(k), bid_amt=k["bidAmt"], use_group_bid=k.get("useGroupBidAmt", False))
                for a in client.list_ads(grp.naver_id):
                    attr = a.get("adAttr") or {}
                    payload = a.get("ad", {})
                    if a.get("assets"):  # RSA_AD: 제목·설명은 ad가 아니라 assets에 온다
                        payload = {**payload, **_rsa_texts(a["assets"])}
                    _upsert(Ad, a["nccAdId"], ad_account_id=aid, adgroup_id=grp.id, ad_type=a["type"], status=_status(a),
                            inspect_status=a.get("inspectStatus", ""), bid_amt=attr.get("bidAmt"),
                            use_group_bid=attr.get("useGroupBidAmt", True), payload=payload)
        _upsert.remove_stale()  # 네이버에서 지운 항목. 조회 중 오류가 나면 여기 오지 않고 롤백된다
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
    since = until - timedelta(days=STATS_DAYS - 1)
    existing = {(r.campaign_id, r.date): r for r in db.scalars(select(PerformanceDaily).where(
        PerformanceDaily.ad_account_id == account.id, PerformanceDaily.date.between(since, until)))}
    for s in client.stats(list(by_naver), since, until):
        camp = by_naver[s["id"]]
        row = existing.get((camp.id, s["date"]))
        if row is None:
            row = PerformanceDaily(ad_account_id=account.id, campaign_id=camp.id, date=s["date"])
            db.add(row)
        row.impressions, row.clicks, row.cost = s["impCnt"], s["clkCnt"], s["salesAmt"]
        row.conversions, row.revenue = s.get("ccnt"), s.get("convAmt")
    db.commit()
