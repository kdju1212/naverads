-- Claude(MCP)의 광고 변경 요청: 웹에서 사람이 승인해야 서버가 저장된 내용 그대로 실행한다(새 표만 추가, 기존 데이터 영향 없음)
CREATE TABLE approval_requests (
	id INTEGER NOT NULL,
	workspace_id INTEGER NOT NULL,
	requested_by INTEGER NOT NULL,
	tool VARCHAR(40) NOT NULL,
	payload VARCHAR(8000) NOT NULL,
	payload_hash VARCHAR(64) NOT NULL,
	status VARCHAR(10) NOT NULL,
	result VARCHAR(2000),
	decided_by INTEGER,
	created_at DATETIME NOT NULL,
	expires_at DATETIME NOT NULL,
	decided_at DATETIME,
	PRIMARY KEY (id),
	FOREIGN KEY(workspace_id) REFERENCES workspaces (id),
	FOREIGN KEY(requested_by) REFERENCES users (id),
	FOREIGN KEY(decided_by) REFERENCES users (id)
);
CREATE INDEX ix_approval_requests_workspace_id ON approval_requests (workspace_id);
