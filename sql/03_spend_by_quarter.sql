-- 03_spend_by_quarter.sql
-- net obligations per fiscal quarter, defense vs. civilian.
-- is_partial = 1 marks DoD FY2026 Q4, which is incomplete because of DoD's ~90-day
-- publication lag (see data_quality.md). keep it visible but don't read it as a drop.

SELECT
    d.fiscal_year,
    d.fiscal_quarter,
    d.fy_quarter,
    a.sector,
    ROUND(SUM(f.obligation) / 1e6, 1)    AS obligated_m,
    COUNT(*)                             AS transactions,
    MAX(f.partial_period)                AS is_partial
FROM fact_awards f
JOIN dim_date d   ON d.date_key = f.date_key
JOIN dim_agency a ON a.agency_key = f.agency_key
GROUP BY d.fiscal_year, d.fiscal_quarter, d.fy_quarter, a.sector
ORDER BY d.fiscal_year, d.fiscal_quarter, a.sector;
