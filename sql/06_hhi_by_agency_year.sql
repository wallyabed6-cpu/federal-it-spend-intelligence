-- 06_hhi_by_agency_year.sql
-- same HHI as 05, but per agency per fiscal year, to show whether concentration is
-- rising or falling. DoD FY2026 is missing most of Q4 (publication lag), so treat
-- that one value with care.

WITH vendor_agency_year AS (
    SELECT
        a.agency,
        d.fiscal_year,
        f.vendor_key,
        SUM(f.obligation) AS obligated
    FROM fact_awards f
    JOIN dim_agency a ON a.agency_key = f.agency_key
    JOIN dim_date d   ON d.date_key = f.date_key
    GROUP BY a.agency, d.fiscal_year, f.vendor_key
    HAVING SUM(f.obligation) > 0
),
shares AS (
    SELECT
        agency,
        fiscal_year,
        100.0 * obligated / SUM(obligated) OVER (PARTITION BY agency, fiscal_year) AS share_pct
    FROM vendor_agency_year
)
SELECT
    agency,
    fiscal_year,
    COUNT(*)                              AS vendors,
    ROUND(SUM(share_pct * share_pct), 0)  AS hhi
FROM shares
GROUP BY agency, fiscal_year
ORDER BY agency, fiscal_year;
