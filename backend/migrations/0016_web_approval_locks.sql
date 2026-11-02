-- 웹 승인(계정 하루예산 합계를 늘릴 수 있는 변경)·계정별 실행 잠금·Google 고유 식별자.
-- 열·표·색인만 추가한다. 기존 행은 그대로이고, 기존 승인 요청(플레이스)은 kind='place', web_required=0으로 읽힌다.
ALTER TABLE approval_requests ADD COLUMN kind VARCHAR(10) NOT NULL DEFAULT 'place';
ALTER TABLE approval_requests ADD COLUMN ad_account_id INTEGER REFERENCES ad_accounts (id);
ALTER TABLE approval_requests ADD COLUMN job_id INTEGER REFERENCES bulk_jobs (id);
ALTER TABLE approval_requests ADD COLUMN web_required BOOLEAN NOT NULL DEFAULT 0;
ALTER TABLE approval_requests ADD COLUMN summary VARCHAR(8000);
CREATE INDEX ix_approval_requests_job_id ON approval_requests (job_id);

CREATE TABLE account_locks (
	ad_account_id INTEGER NOT NULL,
	holder VARCHAR(32) NOT NULL,
	expires_at DATETIME NOT NULL,
	PRIMARY KEY (ad_account_id)
);

-- SQLite는 ADD COLUMN에 UNIQUE를 못 붙여 색인으로 만든다(NULL은 여러 개 허용 = 아직 Google을 연결하지 않은 계정)
ALTER TABLE users ADD COLUMN google_sub VARCHAR(255);
CREATE UNIQUE INDEX ix_users_google_sub ON users (google_sub);
