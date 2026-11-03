-- 계정별 'Claude에서 바로 실행': 켜면 캠페인 켜기·하루예산 증액·ADVoost 켜기도 웹 승인 없이 실행(안전장치 검사는 그대로). 열 추가만, 기존 계정은 꺼짐
ALTER TABLE account_safety ADD COLUMN claude_direct BOOLEAN NOT NULL DEFAULT 0;
