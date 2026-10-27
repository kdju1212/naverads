-- 키워드별 KPI(0007)는 계정 목표 ROAS로 바꾼다. KPI 규칙은 목표 순위가 0이라 남기면 입찰가만 오르므로 지운다.
DELETE FROM auto_bid_rules WHERE kpi IS NOT NULL;
ALTER TABLE auto_bid_rules DROP COLUMN kpi;
ALTER TABLE auto_bid_rules DROP COLUMN kpi_target;
ALTER TABLE auto_bid_rules DROP COLUMN off_cost;

CREATE TABLE account_goals (
	id INTEGER NOT NULL,
	workspace_id INTEGER NOT NULL,
	ad_account_id INTEGER NOT NULL,
	roas_target INTEGER NOT NULL,
	max_bid INTEGER NOT NULL,
	off_cost INTEGER,
	enabled BOOLEAN NOT NULL,
	created_by INTEGER NOT NULL,
	run_date VARCHAR(10),
	state VARCHAR(4000),
	last_run_at DATETIME,
	last_result VARCHAR(300),
	PRIMARY KEY (id),
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id),
	FOREIGN KEY(created_by) REFERENCES users (id),
	UNIQUE (workspace_id, ad_account_id)
);
CREATE INDEX ix_account_goals_workspace_id ON account_goals (workspace_id);
