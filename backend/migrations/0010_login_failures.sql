-- 로그인 실패 횟수 제한: 이메일·IP별 15분 안 실패 횟수
CREATE TABLE login_failures (
	"key" VARCHAR(330) NOT NULL,
	count INTEGER NOT NULL,
	first_at DATETIME NOT NULL,
	PRIMARY KEY ("key")
);
CREATE INDEX ix_login_failures_first_at ON login_failures (first_at);
