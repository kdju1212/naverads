-- 동기화 기록을 조직별로: 같은 광고 계정(고객번호)을 여러 조직이 연결해도 각 조직은 자기가 동기화에 성공한 날까지만 성과를 본다
-- (광고주가 다른 대행사로 옮기면 예전 대행사 키는 네이버가 거부해 그 뒤 성과가 안 보임). 열 추가만, 기존 데이터 유지
ALTER TABLE sync_runs ADD COLUMN workspace_id INTEGER REFERENCES workspaces (id);
CREATE INDEX ix_sync_runs_workspace_id ON sync_runs (workspace_id);
-- 기존 기록은 그 계정이 한 조직에만 연결돼 있으면 그 조직 것으로(여러 조직이면 누구 것인지 몰라 비워 둠 → 다음 새로고침부터 보임)
UPDATE sync_runs SET workspace_id = (SELECT w.workspace_id FROM workspace_ad_accounts w WHERE w.ad_account_id = sync_runs.ad_account_id)
WHERE (SELECT COUNT(*) FROM workspace_ad_accounts w WHERE w.ad_account_id = sync_runs.ad_account_id) = 1;
