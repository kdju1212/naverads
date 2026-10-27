-- 예약 실행: 크론이 이 시각(UTC) 이후 미리보기 작업을 실행
ALTER TABLE bulk_jobs ADD COLUMN scheduled_at DATETIME;
