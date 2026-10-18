CREATE TABLE ad_extensions (
	id INTEGER NOT NULL,
	ad_account_id INTEGER NOT NULL,
	naver_id VARCHAR(50) NOT NULL,
	owner_naver_id VARCHAR(50) NOT NULL,
	ext_type VARCHAR(40) NOT NULL,
	status VARCHAR(3) NOT NULL,
	inspect_status VARCHAR(20) NOT NULL,
	payload JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id),
	UNIQUE (naver_id)
);

CREATE INDEX ix_ad_extensions_ad_account_id ON ad_extensions (ad_account_id);
