-- 07_hhi_by_sub_agency.sql
-- vendor concentration one level down: per sub-agency (bureau or military department),
-- FY2022-FY2026. agency-wide HHI hides dependence because each agency buys from
-- thousands of vendors; single bureaus often lean on one or two.
--
-- same HHI math and DOJ/FTC bands as 05_hhi_by_agency.sql.
-- only sub-agencies with at least $250M of IT spend over the five years are kept,
-- so small offices with a handful of contracts don't top the list by default.

WITH vendor_sub AS (
    SELECT
        a.agency,
        a.sub_agency,
        f.vendor_key,
        SUM(f.obligation) AS obligated
    FROM fact_awards f
    JOIN dim_agency a ON a.agency_key = f.agency_key
    GROUP BY a.agency, a.sub_agency, f.vendor_key
    HAVING SUM(f.obligation) > 0
),
shares AS (
    SELECT
        agency,
        sub_agency,
        vendor_key,
        obligated,
        100.0 * obligated / SUM(obligated) OVER (PARTITION BY agency, sub_agency)     AS share_pct,
        ROW_NUMBER() OVER (PARTITION BY agency, sub_agency ORDER BY obligated DESC)   AS rank
    FROM vendor_sub
)
SELECT
    s.agency,
    s.sub_agency,
    COUNT(*)                                                         AS vendors,
    ROUND(SUM(s.obligated) / 1e6, 1)                                 AS obligated_m,
    ROUND(SUM(s.share_pct * s.share_pct), 0)                         AS hhi,
    ROUND(SUM(CASE WHEN s.rank <= 4 THEN s.share_pct ELSE 0 END), 1) AS cr4_pct,
    MAX(CASE WHEN s.rank = 1 THEN v.vendor END)                      AS top_vendor,
    ROUND(MAX(s.share_pct), 1)                                       AS top_vendor_pct,
    CASE
        WHEN SUM(s.share_pct * s.share_pct) > 1800 THEN 'Highly concentrated'
        WHEN SUM(s.share_pct * s.share_pct) >= 1000 THEN 'Moderately concentrated'
        ELSE 'Unconcentrated'
    END                                                              AS concentration
FROM shares s
JOIN dim_vendor v ON v.vendor_key = s.vendor_key
GROUP BY s.agency, s.sub_agency
HAVING SUM(s.obligated) >= 250e6
ORDER BY hhi DESC;
