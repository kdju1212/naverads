-- 광고 데이터 사본(캠페인·광고그룹·키워드·소재·확장소재)은 서버에 두지 않는다(브라우저가 마스터 보고서로 받아 보관).
-- 자동입찰 규칙·성과 통계는 사본 테이블 대신 네이버 ID를 직접 저장한다.

CREATE TABLE auto_bid_rules_new (
	id INTEGER NOT NULL,
	workspace_id INTEGER NOT NULL,
	ad_account_id INTEGER NOT NULL,
	keyword_naver_id VARCHAR(50) NOT NULL,
	keyword VARCHAR(100) NOT NULL,
	device VARCHAR(6) NOT NULL,
	target_rank INTEGER NOT NULL,
	max_bid INTEGER NOT NULL,
	enabled BOOLEAN NOT NULL,
	created_by INTEGER NOT NULL,
	last_run_at DATETIME,
	last_result VARCHAR(300),
	PRIMARY KEY (id),
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id),
	FOREIGN KEY(created_by) REFERENCES users (id),
	UNIQUE (workspace_id, keyword_naver_id)
);
INSERT INTO auto_bid_rules_new (id, workspace_id, ad_account_id, keyword_naver_id, keyword, device, target_rank, max_bid, enabled, created_by, last_run_at, last_result)
SELECT r.id, r.workspace_id, k.ad_account_id, k.naver_id, k.keyword, r.device, r.target_rank, r.max_bid, r.enabled, r.created_by, r.last_run_at, r.last_result
FROM auto_bid_rules r JOIN keywords k ON k.id = r.keyword_id;
DROP TABLE auto_bid_rules;
ALTER TABLE auto_bid_rules_new RENAME TO auto_bid_rules;
CREATE INDEX ix_auto_bid_rules_workspace_id ON auto_bid_rules (workspace_id);

CREATE TABLE performance_daily_new (
	id INTEGER NOT NULL,
	ad_account_id INTEGER NOT NULL,
	campaign_naver_id VARCHAR(50) NOT NULL,
	campaign_tp VARCHAR(20) NOT NULL,
	date DATE NOT NULL,
	impressions INTEGER NOT NULL,
	clicks INTEGER NOT NULL,
	cost INTEGER NOT NULL,
	conversions INTEGER,
	revenue INTEGER,
	PRIMARY KEY (id),
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id),
	UNIQUE (campaign_naver_id, date)
);
INSERT INTO performance_daily_new (id, ad_account_id, campaign_naver_id, campaign_tp, date, impressions, clicks, cost, conversions, revenue)
SELECT p.id, p.ad_account_id, c.naver_id, c.campaign_tp, p.date, p.impressions, p.clicks, p.cost, p.conversions, p.revenue
FROM performance_daily p JOIN campaigns c ON c.id = p.campaign_id;
DROP TABLE performance_daily;
ALTER TABLE performance_daily_new RENAME TO performance_daily;
CREATE INDEX ix_performance_daily_ad_account_id ON performance_daily (ad_account_id);

DROP TABLE ad_extensions;
DROP TABLE keywords;
DROP TABLE ads;
DROP TABLE adgroups;
DROP TABLE campaigns;
