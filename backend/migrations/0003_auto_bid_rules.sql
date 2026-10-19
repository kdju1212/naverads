CREATE TABLE auto_bid_rules (
	id INTEGER NOT NULL,
	workspace_id INTEGER NOT NULL,
	keyword_id INTEGER NOT NULL,
	device VARCHAR(6) NOT NULL,
	target_rank INTEGER NOT NULL,
	max_bid INTEGER NOT NULL,
	enabled BOOLEAN NOT NULL,
	created_by INTEGER NOT NULL,
	last_run_at DATETIME,
	last_result VARCHAR(300),
	PRIMARY KEY (id),
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
	FOREIGN KEY(keyword_id) REFERENCES keywords (id),
	FOREIGN KEY(created_by) REFERENCES users (id),
	UNIQUE (keyword_id)
);

CREATE INDEX ix_auto_bid_rules_workspace_id ON auto_bid_rules (workspace_id);
