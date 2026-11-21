-- 구글 광고 변경 도구(google_ads.py)의 클릭당 최대 입찰가(계정 통화 단위). NULL이면 변경 도구를 쓸 수 없다
ALTER TABLE channel_connections ADD COLUMN max_bid INTEGER;
