-- Claude 연결만 끊기: 올리면 Claude(MCP) 토큰만 무효(웹 로그인은 그대로)
ALTER TABLE users ADD COLUMN mcp_version INTEGER NOT NULL DEFAULT 0;
-- 한 번 쓴 인가 코드·갱신 토큰(sha256). 다시 오면 거절, 갱신 토큰을 늦게 재사용하면 탈취로 보고 Claude 연결을 모두 끊는다
CREATE TABLE oauth_used (
	"key" VARCHAR(64) NOT NULL,
	used_at DATETIME NOT NULL,
	expires_at DATETIME NOT NULL,
	PRIMARY KEY ("key")
);
CREATE INDEX ix_oauth_used_expires_at ON oauth_used (expires_at);
