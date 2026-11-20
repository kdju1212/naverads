-- 메타·구글 광고 계정 조회 연결(통합 성과 비교용, 조회만). 토큰은 CRED_KEY로 암호화
CREATE TABLE channel_connections (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    channel VARCHAR(10) NOT NULL,
    account_id VARCHAR(30) NOT NULL,
    name VARCHAR(200) NOT NULL,
    token_enc VARCHAR(2000) NOT NULL,
    login_customer_id VARCHAR(30),
    connected_by INTEGER NOT NULL REFERENCES users(id),
    connected_at DATETIME NOT NULL,
    UNIQUE (workspace_id, channel, account_id)
);
CREATE INDEX ix_channel_connections_workspace_id ON channel_connections (workspace_id);
