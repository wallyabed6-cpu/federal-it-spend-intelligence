# DAX Measures, Explained

One plain-English sentence per measure, followed by the follow-up question an interviewer is likely to ask. Full DAX is in [`measures.dax`](measures.dax).

## Spend

| Measure | What it does |
|---|---|
| **Total Obligations** | Adds up every obligated dollar in the current filter, with deobligations (money taken back) subtracted, so it matches USAspending's net totals ($262.9B overall). |
| **Prior Year Obligations** | Shows the same total for the same period one year earlier, using `SAMEPERIODLASTYEAR` on the marked date table. |
| **YoY Growth %** | Compares this period with the same period last year: (this year − last year) ÷ last year. |
| **Award Count** | Counts distinct contract awards, so an award and all of its modifications count once. |

*Likely question:* "Why does FY2026 defense growth look negative?" DoD publishes contract data about 90 days late, so its FY2026 Q4 is incomplete. The overview card uses FY2025, the last complete year.

## Concentration

| Measure | What it does |
|---|---|
| **Vendor Share of Agency Spend** | Divides a vendor's dollars by the total for whatever agency is in the filter, using `REMOVEFILTERS(dim_vendor)` to get the denominator. |
| **HHI** | Squares every vendor's market share (in percent) and adds them up. 10,000 means one vendor gets everything, and close to 0 means spend is spread across many vendors. |
| **HHI Band** | Labels the HHI using the 2023 DOJ/FTC merger guideline thresholds: under 1,000 unconcentrated, 1,000–1,800 moderate, over 1,800 high. |
| **Top 4 Vendor Share** | The percent of spend held by the four biggest vendors, which is easier to say out loud than an HHI. |

*Likely question:* "Why leave out vendors with negative net dollars?" A negative market share has no meaning. It only happens when deobligations exceed new obligations in the period. The SQL version (`sql/05_hhi_by_agency.sql`) uses the same rule, and the Power BI numbers match it.

*Likely question:* "How does HHI work inside DAX?" `ADDCOLUMNS(VALUES(dim_vendor[vendor_key]), "@amt", [Total Obligations])` builds a small table of each vendor's dollars in the current filter. `FILTER` drops vendors at zero or below, and `SUMX` adds up the squared shares.

## Risk

| Measure | What it does |
|---|---|
| **Anomaly Count** | Counts the transactions the Isolation Forest flagged as the most unusual 1%. |
| **Anomaly Dollars** | Adds up the dollars in those flagged transactions. |
| **Anomaly Rate** | Divides flagged transactions by the transactions the model actually scored (actions adding $10K or more). |

*Likely question:* "Flagged transactions are $61B, about 23% of all dollars. Is a quarter of spending suspicious?" No. The model looks for actions that are unusually *large* for their vendor, agency and award, so the flags are naturally the big-dollar actions. It's a ranked review queue, not an estimate of waste.

## Forecast

| Measure | What it does |
|---|---|
| **Actual ($B)** | Shows known quarterly spend from the forecast table, in billions. |
| **Forecast ($B)** | Shows the model's line: the 4 backtest quarters plus the 4 future quarters. |
| **Forecast Lower / Upper ($B)** | Shows the 80% prediction interval around the forecast. |
| **Forecast vs Actual %** | For the backtest quarters only, shows how far the forecast was from what happened. Positive means the model was too high. |
| **Backtest MAPE** | Shows the model's average percent error on the 4 held-out quarters. |
| **Baseline MAPE** | Shows the same error for the "same quarter last year" baseline, so the model can be judged against something simple. |

*Likely question:* "Why is the forecast a separate table with no relationships?" It's at quarter level, while everything else is at day or transaction level. Keeping it unrelated avoids misleading cross-filtering. It's used only on the Forecast page.
