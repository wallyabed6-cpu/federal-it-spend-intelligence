-- 02_top_vendors_by_agency.sql
-- top 20 vendors within each agency, FY2022-FY2026.
-- share_of_agency_pct = vendor dollars / that agency's total IT dollars.

WITH vendor_agency AS (
    SELECT
        a.agency,
        v.vendor,
        SUM(f.obligation) AS obligated
    FROM fact_awards f
    JOIN dim_agency a ON a.agency_key = f.agency_key
    JOIN dim_vendor v ON v.vendor_key = f.vendor_key
    GROUP BY a.agency, v.vendor
),
ranked AS (
    SELECT
        agency,
        vendor,
        obligated,
        SUM(obligated) OVER (PARTITION BY agency)                     AS agency_total,
        ROW_NUMBER() OVER (PARTITION BY agency ORDER BY obligated DESC) AS rank
    FROM vendor_agency
)
SELECT
    agency,
    rank,
    vendor,
    ROUND(obligated / 1e6, 1)                       AS obligated_m,
    ROUND(100.0 * obligated / agency_total, 2)      AS share_of_agency_pct
FROM ranked
WHERE rank <= 20
ORDER BY agency, rank;
