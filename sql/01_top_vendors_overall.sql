-- 01_top_vendors_overall.sql
-- top 20 vendors by net obligated dollars, FY2022-FY2026, all six agencies.
-- net = new obligations minus deobligations, so it matches USAspending totals.
-- share_pct is each vendor's slice of all in-scope IT spend.

WITH vendor_totals AS (
    SELECT
        v.vendor,
        SUM(f.obligation)              AS obligated,
        COUNT(DISTINCT f.award_key)    AS awards,
        COUNT(*)                       AS transactions
    FROM fact_awards f
    JOIN dim_vendor v ON v.vendor_key = f.vendor_key
    GROUP BY v.vendor
)
SELECT
    RANK() OVER (ORDER BY obligated DESC)                         AS rank,
    vendor,
    ROUND(obligated / 1e6, 1)                                     AS obligated_m,
    ROUND(100.0 * obligated / SUM(obligated) OVER (), 2)          AS share_pct,
    awards,
    transactions
FROM vendor_totals
ORDER BY obligated DESC
LIMIT 20;
