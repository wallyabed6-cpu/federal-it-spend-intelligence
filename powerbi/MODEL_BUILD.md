# Model build instructions (step 7e)

Instructions for a Claude Code session on the Windows PC, using Microsoft's
`powerbi-modeling` MCP server, connected to `FederalITSpend` open in Power BI Desktop.

**Before starting:** `git pull`, open `powerbi/FederalITSpend.pbip` in Desktop, click
**Refresh**, and confirm it loads with no errors. Then commit, so there is a rollback point.

## 1. Relationships (star schema)

All many-to-one, single cross-filter direction (dimension filters fact), active.

| From (many) | To (one) |
|---|---|
| fact_awards[date_key] | dim_date[date_key] |
| fact_awards[agency_key] | dim_agency[agency_key] |
| fact_awards[vendor_key] | dim_vendor[vendor_key] |
| fact_awards[naics_code] | dim_naics[naics_code] |
| fact_awards[state_code] | dim_state[state_code] |
| fact_awards[award_id] | dim_award[award_id] |

`forecast` and `forecast_backtest` stay unrelated. They're at quarter level and are used only on the Forecast page.

## 2. Date table

- Mark `dim_date` as the date table, using `dim_date[date]`.
- `dim_date[month_name]` sort by `dim_date[fiscal_month]`, so October comes first.

## 3. Column hygiene

- Hide on `fact_awards`: txn_id, award_id, date_key, agency_key, vendor_key, naics_code, state_code, is_new_award, is_deobligation, partial_period, is_anomaly.
- Hide `dim_date[date_key]`, `dim_agency[agency_key]`, `dim_vendor[vendor_key]`, `dim_award[award_id]`.
- Set `summarizeBy: none` on every key, code, year, quarter, month and flag column. Only `obligation` and the forecast `*_b` columns should sum by default.
- Format `fact_awards[obligation]` as currency, `$#,0`.
- Data category: `dim_state[state_name]` = State or Province. `dim_state[state_code]` = State or Province as well.

## 4. Measures

Create every measure in `powerbi/measures.dax` exactly as written, with the description from the comment above it.

| Measure | Table | Display folder | Format |
|---|---|---|---|
| Total Obligations | fact_awards | Spend | `\$#,0;(\$#,0);\$#,0` (billions set per visual) |
| Prior Year Obligations | fact_awards | Spend | `\$#,0;(\$#,0);\$#,0` |
| YoY Growth % | fact_awards | Spend | `0.0%` |
| Award Count | fact_awards | Spend | `#,0` |
| Vendor Share of Agency Spend | fact_awards | Concentration | `0.0%` |
| HHI | fact_awards | Concentration | `#,0` |
| HHI Band | fact_awards | Concentration | text |
| Top 4 Vendor Share | fact_awards | Concentration | `0.0%` |
| Anomaly Count | fact_awards | Risk | `#,0` |
| Anomaly Dollars | fact_awards | Risk | `\$#,0;(\$#,0);\$#,0` |
| Anomaly Rate | fact_awards | Risk | `0.00%` |
| Actual ($B) | forecast | Forecast | `$#,0.00"B"` |
| Forecast ($B) | forecast | Forecast | `$#,0.00"B"` |
| Forecast Lower ($B) | forecast | Forecast | `$#,0.00"B"` |
| Forecast Upper ($B) | forecast | Forecast | `$#,0.00"B"` |
| Forecast vs Actual % | forecast | Forecast | `0.0%` |
| Backtest MAPE | forecast | Forecast | `0.0%` |
| Baseline MAPE | forecast | Forecast | `0.0%` |

## 5. Check the numbers (run as DAX queries through the MCP server)

These come from the Python/SQL pipeline. The model must match them.

| Check | Expected |
|---|---|
| `COUNTROWS(fact_awards)` | 383,385 |
| rows where `fact_awards[obligation]` is blank | 0 |
| `[Total Obligations]` | 262,888,521,413.39 |
| `[Total Obligations]` by `dim_agency[sector]`, FY2025 | Civilian ≈ $30.49B, Defense ≈ $23.25B |
| `[HHI]` by `dim_agency[agency]` | DoD 127, DHS 152, HHS 171, Treasury 364, VA 606, GSA 627 |
| `[Anomaly Count]` | 1,985 |
| `[Backtest MAPE]` for sector Defense / Civilian | 12.3% / 9.8% |
| `COUNTROWS(dim_naics)` | 4 (none split by the comma in "DATA PROCESSING, HOSTING, AND RELATED SERVICES") |

If any check fails, stop and report it. Don't adjust a measure to force the number.

## 6. Finish

Save in Desktop (Ctrl+S). Then `git add powerbi` and commit with the message
"Step 7e: relationships, date table, measures".

> Note: the scaled formats (`$#,0.0,,,"B"`) were replaced after page 1 testing. Power BI applied its own display units on top and showed "$262.9 bnB". Dollar measures now use plain currency, and each visual sets display units to billions.
