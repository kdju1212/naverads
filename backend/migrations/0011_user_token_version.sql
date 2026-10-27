-- 토큰 강제 폐기: 비밀번호 변경·모든 기기 로그아웃 때 1 올리면 이전에 발급한 로그인·Claude 연결 토큰이 모두 무효
ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0;
