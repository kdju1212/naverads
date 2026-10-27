-- KPI 자동운영: 목표 순위 대신 CPA·ROAS·CPC 목표와 무전환 OFF 기준
ALTER TABLE auto_bid_rules ADD COLUMN kpi VARCHAR(4);
ALTER TABLE auto_bid_rules ADD COLUMN kpi_target INTEGER;
ALTER TABLE auto_bid_rules ADD COLUMN off_cost INTEGER;
