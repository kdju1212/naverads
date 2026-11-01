-- 광고비 안전장치(조직·광고 계정별 하루예산 관리 기준·클릭당 최대 입찰가)와 자동입찰 승인 기간. 새 표·열 추가만, 기존 데이터 유지
-- 기존 계정은 행이 없어 '미설정' → 관리자가 금액을 정하기 전까지 광고 켜기·예산 증액·입찰가 변경이 막힌다(끄기·조회는 가능)
CREATE TABLE account_safety (
	id INTEGER NOT NULL,
	workspace_id INTEGER NOT NULL,
	ad_account_id INTEGER NOT NULL,
	daily_budget_limit INTEGER NOT NULL,
	max_bid INTEGER NOT NULL,
	set_by INTEGER NOT NULL,
	set_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (workspace_id, ad_account_id),
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
	FOREIGN KEY(ad_account_id) REFERENCES ad_accounts (id),
	FOREIGN KEY(set_by) REFERENCES users (id)
);
CREATE INDEX ix_account_safety_workspace_id ON account_safety (workspace_id);
-- 자동입찰 실행 기간: 기존 규칙은 NULL(승인 전)이라 다시 저장(범위 승인)할 때까지 실행하지 않는다
ALTER TABLE auto_bid_rules ADD COLUMN ends_on DATE;
