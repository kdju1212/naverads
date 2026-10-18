-- models.py 에서 생성 (sqlite 방언). 모델 변경 시 새 번호의 마이그레이션 파일을 추가한다.
CREATE TABLE ad_accounts (
	id INTEGER NOT NULL, 
	customer_id VARCHAR(30) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	is_mock BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (customer_id)
);

CREATE TABLE plans (
	code VARCHAR(20) NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	price_per_account INTEGER NOT NULL, 
	trial_days INTEGER NOT NULL, 
	PRIMARY KEY (code)
);

CREATE TABLE users (
	id INTEGER NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
);

CREATE TABLE workspaces (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	type VARCHAR(20) NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE bulk_jobs (
	id INTEGER NOT NULL, 
	workspace_id INTEGER NOT NULL, 
	created_by INTEGER NOT NULL, 
	source VARCHAR(10) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	parent_job_id INTEGER, 
	created_at DATETIME NOT NULL, 
	executed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(created_by) REFERENCES users (id), 
	FOREIGN KEY(parent_job_id) REFERENCES bulk_jobs (id)
);

CREATE INDEX ix_bulk_jobs_workspace_id ON bulk_jobs (workspace_id);

CREATE TABLE campaigns (
	id INTEGER NOT NULL, 
	ad_account_id INTEGER NOT NULL, 
	naver_id VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	campaign_tp VARCHAR(20) NOT NULL, 
	status VARCHAR(3) NOT NULL, 
	daily_budget INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id), 
	UNIQUE (naver_id)
);

CREATE INDEX ix_campaigns_ad_account_id ON campaigns (ad_account_id);

CREATE TABLE memberships (
	id INTEGER NOT NULL, 
	workspace_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	role VARCHAR(10) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, user_id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);

CREATE TABLE naver_api_credentials (
	id INTEGER NOT NULL, 
	workspace_id INTEGER NOT NULL, 
	label VARCHAR(100) NOT NULL, 
	api_key VARCHAR(255) NOT NULL, 
	secret_key_enc VARCHAR(500) NOT NULL, 
	is_mock BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id)
);

CREATE TABLE subscriptions (
	id INTEGER NOT NULL, 
	workspace_id INTEGER NOT NULL, 
	plan_code VARCHAR(20) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	trial_ends_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(plan_code) REFERENCES plans (code)
);

CREATE TABLE sync_runs (
	id INTEGER NOT NULL, 
	ad_account_id INTEGER NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	error VARCHAR(300), 
	started_at DATETIME NOT NULL, 
	finished_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id)
);

CREATE INDEX ix_sync_runs_ad_account_id ON sync_runs (ad_account_id);

CREATE TABLE account_access (
	id INTEGER NOT NULL, 
	membership_id INTEGER NOT NULL, 
	ad_account_id INTEGER NOT NULL, 
	level VARCHAR(5) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (membership_id, ad_account_id), 
	FOREIGN KEY(membership_id) REFERENCES memberships (id), 
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id)
);

CREATE TABLE adgroups (
	id INTEGER NOT NULL, 
	ad_account_id INTEGER NOT NULL, 
	campaign_id INTEGER NOT NULL, 
	naver_id VARCHAR(50) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	adgroup_type VARCHAR(20) NOT NULL, 
	status VARCHAR(3) NOT NULL, 
	bid_amt INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id), 
	FOREIGN KEY(campaign_id) REFERENCES campaigns (id), 
	UNIQUE (naver_id)
);

CREATE INDEX ix_adgroups_ad_account_id ON adgroups (ad_account_id);

CREATE TABLE audit_logs (
	id INTEGER NOT NULL, 
	workspace_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	ad_account_id INTEGER, 
	job_id INTEGER, 
	action VARCHAR(30) NOT NULL, 
	entity_type VARCHAR(10), 
	naver_id VARCHAR(50), 
	field VARCHAR(20), 
	"before" VARCHAR(50), 
	"after" VARCHAR(50), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id), 
	FOREIGN KEY(job_id) REFERENCES bulk_jobs (id)
);

CREATE INDEX ix_audit_logs_workspace_id ON audit_logs (workspace_id);

CREATE TABLE bulk_job_rows (
	id INTEGER NOT NULL, 
	job_id INTEGER NOT NULL, 
	ad_account_id INTEGER, 
	entity_type VARCHAR(10) NOT NULL, 
	naver_id VARCHAR(50) NOT NULL, 
	field VARCHAR(20) NOT NULL, 
	"before" VARCHAR(50), 
	"after" VARCHAR(50) NOT NULL, 
	status VARCHAR(10) NOT NULL, 
	error VARCHAR(300), 
	PRIMARY KEY (id), 
	FOREIGN KEY(job_id) REFERENCES bulk_jobs (id), 
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id)
);

CREATE INDEX ix_bulk_job_rows_job_id ON bulk_job_rows (job_id);

CREATE TABLE performance_daily (
	id INTEGER NOT NULL, 
	ad_account_id INTEGER NOT NULL, 
	campaign_id INTEGER NOT NULL, 
	date DATE NOT NULL, 
	impressions INTEGER NOT NULL, 
	clicks INTEGER NOT NULL, 
	cost INTEGER NOT NULL, 
	conversions INTEGER, 
	revenue INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (campaign_id, date), 
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id), 
	FOREIGN KEY(campaign_id) REFERENCES campaigns (id)
);

CREATE INDEX ix_performance_daily_ad_account_id ON performance_daily (ad_account_id);

CREATE TABLE workspace_ad_accounts (
	id INTEGER NOT NULL, 
	workspace_id INTEGER NOT NULL, 
	ad_account_id INTEGER NOT NULL, 
	credential_id INTEGER NOT NULL, 
	status VARCHAR(15) NOT NULL, 
	connected_by INTEGER NOT NULL, 
	connected_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (workspace_id, ad_account_id), 
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id), 
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id), 
	FOREIGN KEY(credential_id) REFERENCES naver_api_credentials (id), 
	FOREIGN KEY(connected_by) REFERENCES users (id)
);

CREATE TABLE ads (
	id INTEGER NOT NULL, 
	ad_account_id INTEGER NOT NULL, 
	adgroup_id INTEGER NOT NULL, 
	naver_id VARCHAR(50) NOT NULL, 
	ad_type VARCHAR(30) NOT NULL, 
	status VARCHAR(3) NOT NULL, 
	inspect_status VARCHAR(20) NOT NULL, 
	bid_amt INTEGER, 
	use_group_bid BOOLEAN NOT NULL, 
	payload JSON NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id), 
	FOREIGN KEY(adgroup_id) REFERENCES adgroups (id), 
	UNIQUE (naver_id)
);

CREATE INDEX ix_ads_ad_account_id ON ads (ad_account_id);

CREATE TABLE keywords (
	id INTEGER NOT NULL, 
	ad_account_id INTEGER NOT NULL, 
	adgroup_id INTEGER NOT NULL, 
	naver_id VARCHAR(50) NOT NULL, 
	keyword VARCHAR(100) NOT NULL, 
	status VARCHAR(3) NOT NULL, 
	bid_amt INTEGER NOT NULL, 
	use_group_bid BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id), 
	FOREIGN KEY(adgroup_id) REFERENCES adgroups (id), 
	UNIQUE (naver_id)
);

CREATE INDEX ix_keywords_ad_account_id ON keywords (ad_account_id);

