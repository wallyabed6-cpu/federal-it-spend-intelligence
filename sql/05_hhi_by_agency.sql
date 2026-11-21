-- 05_hhi_by_agency.sql
-- vendor concentration per agency, FY2022-FY2026, using the Herfindahl-Hirschman Index.
--
-- HHI = sum over vendors of (market share in percent)^2
--   10,000 = one vendor gets everything; near 0 = spend spread over many vendors.
-- bands follow the 2023 DOJ/FTC merger guidelines:
--   under 1,000 unconcentrated | 1,000-1,800 moderately concentrated | over 1,800 highly concentrated
--
-- vendors with zero or negative net dollars (deobligations larger than obligations)
-- are left out, since a negative market share has no meaning.
-- cr4_pct = share held by the top 4 vendors, an easier number to say out loud.

WITH vendor_agency AS (
    SELECT
        a.agency,
        a.sector,
        f.vendor_key,
        SUM(f.obligation) AS obligated
    FROM fact_awards f
    JOIN dim_agency a ON a.agency_key = f.agency_key
    GROUP BY a.agency, a.sector, f.vendor_key
    HAVING SUM(f.obligation) > 0
),
shares AS (
    SELECT
        agency,
        sector,
        obligated,
        100.0 * obligated / SUM(obligated) OVER (PARTITION BY agency)       AS share_pct,
        ROW_NUMBER() OVER (PARTITION BY agency ORDER BY obligated DESC)     AS rank
    FROM vendor_agency
)
SELECT
    agency,
    sector,
    COUNT(*)                                                    AS vendors,
    ROUND(SUM(obligated) / 1e6, 1)                              AS obligated_m,
    ROUND(SUM(share_pct * share_pct), 0)                        AS hhi,
    ROUND(SUM(CASE WHEN rank <= 4 THEN share_pct ELSE 0 END), 1) AS cr4_pct,
    ROUND(MAX(share_pct), 1)                                    AS top_vendor_pct,
    CASE
        WHEN SUM(share_pct * share_pct) > 1800 THEN 'Highly concentrated'
        WHEN SUM(share_pct * share_pct) >= 1000 THEN 'Moderately concentrated'
        ELSE 'Unconcentrated'
    END                                                         AS concentration
FROM shares
GROUP BY agency, sector
ORDER BY hhi DESC;
