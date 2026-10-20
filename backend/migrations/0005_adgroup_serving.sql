-- 광고그룹 운영 상태: 네이버 statusReason(없으면 status). 예산 소진·캠페인 OFF 등 노출 안 되는 이유
ALTER TABLE adgroups ADD COLUMN serving VARCHAR(40);
