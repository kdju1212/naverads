-- 광고그룹 하루예산. NULL = 제한 없음(useDailyBudget=false)
ALTER TABLE adgroups ADD COLUMN daily_budget INTEGER;
