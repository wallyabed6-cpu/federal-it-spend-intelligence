-- 04_spend_by_state.sql
-- net obligations by place of performance (where the work happens, not where the
-- vendor is headquartered). feeds the Power BI map.
-- territories, overseas military codes, and unknown are kept but labeled by state_type
-- so the map can filter them out.

SELECT
    s.state_code,
    s.state_name,
    s.state_type,
    ROUND(SUM(f.obligation) / 1e6, 1)                                   AS obligated_m,
    ROUND(SUM(CASE WHEN a.sector = 'Defense'  THEN f.obligation ELSE 0 END) / 1e6, 1) AS defense_m,
    ROUND(SUM(CASE WHEN a.sector = 'Civilian' THEN f.obligation ELSE 0 END) / 1e6, 1) AS civilian_m,
    ROUND(100.0 * SUM(f.obligation) / (SELECT SUM(obligation) FROM fact_awards), 2) AS share_pct,
    COUNT(DISTINCT f.vendor_key)                                        AS vendors
FROM fact_awards f
JOIN dim_state s  ON s.state_code = f.state_code
JOIN dim_agency a ON a.agency_key = f.agency_key
GROUP BY s.state_code, s.state_name, s.state_type
ORDER BY obligated_m DESC;
