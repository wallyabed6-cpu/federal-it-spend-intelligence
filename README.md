# Federal IT Spend Intelligence

An end-to-end analysis of **$262.9B in federal IT services contract spending** (FY2022–FY2026), built on public USAspending.gov data. It covers market structure, vendor concentration risk, unusual-spending detection and a quarterly spend forecast, and ends in a 5-page Power BI report and a consulting-style findings memo.

**Stack:** Python (pandas, scikit-learn, statsmodels) · SQL (SQLite, star schema) · Power BI (PBIP/PBIR, DAX)

## Key results

- **Civilian agencies outspend DoD** on IT services in this scope: $157.8B vs $105.1B (60/40).
- **Every agency's vendor market is unconcentrated (HHI 127–627), but six bureaus are highly concentrated.** For example, the Missile Defense Agency gets 75% of its IT services from Lockheed Martin, and Treasury Departmental Offices gets 77% from one vendor.
- **Oracle holds 17.2% of VA's IT spend** (the health record program), and **Booz Allen holds 17.1% of GSA's**.
- **VA, MD and DC take 64%** of dollars by place of performance. **Q4 spending runs 2–3.6× Q1** every year.
- **1,985 transactions (top 1%)** are flagged as unusual by an Isolation Forest, each with a plain-English reason.
- **Forecast:** the model beats a "same as last year" baseline for defense in 8 of 8 rolling backtests (8.7% vs 12.3% average error). Civilian is roughly a tie, and the write-up says so.

Full write-up: **[findings.md](findings.md)**

## Scope

| | |
|---|---|
| Source | [USAspending.gov API](https://api.usaspending.gov) (`/api/v2/download/transactions/`), free, no key |
| Award types | Contracts only (A/B/C/D: BPA calls, purchase orders, delivery orders, definitive contracts) |
| NAICS | 541511, 541512, 541519, 518210 (IT services) |
| Agencies | DoD (defense); DHS, VA, HHS, Treasury, GSA (civilian) |
| Years | FY2022–FY2026 |
| Size | 383,385 transactions, 147,224 awards, 8,394 parent vendors |

Nothing was cut from the planned scope.

## Repo layout

```
scripts/
  01_ingest.py         pull transactions from the API (30 agency-year files)
  02_clean.py          standardize vendors, dates, quarters, dollars, flag bad rows
  03_load_db.py        build the SQLite star schema
  04_analysis.py       run every query in sql/, save results
  05_anomaly.py        Isolation Forest + "why flagged" reasons
  06_forecast.py       Holt-Winters quarterly forecast + backtest
  07_export.py         CSVs for Power BI
  validate_models.py   checks behind validation.md
sql/                   schema + 7 commented analysis queries (top vendors, quarters, states, HHI)
data/clean/            clean transactions, analysis outputs, model outputs
powerbi/               PBIP project, data/ CSVs, measures.dax, measures_explained.md
data_quality.md        every cleaning rule and the rows it affected
validation.md          what could make each model misleading, and what was checked
findings.md            executive summary and recommendations
```

## How to run

```bash
pip install -r requirements.txt
python scripts/01_ingest.py        # ~35 min, ~14 MB of zips into data/raw/
python scripts/02_clean.py
python scripts/03_load_db.py
python scripts/04_analysis.py
python scripts/05_anomaly.py
python scripts/06_forecast.py
python scripts/07_export.py
python scripts/validate_models.py  # optional: reruns the validation checks
```

`data/raw/` and the SQLite database are gitignored and rebuild from these scripts. The clean data and all outputs are committed, so steps 2–7 can run without re-downloading.

**Power BI:** open `powerbi/FederalITSpend.pbip` in Power BI Desktop, then Refresh. The CSV source paths point to the folder where the project was built. On another machine, update them under **Transform data → Data source settings → Change Source**.

## Data model

Star schema: `fact_awards` (one row per transaction) joined to `dim_date` (marked as the date table, with fiscal calendar), `dim_agency` (sub-agency → agency → sector), `dim_vendor`, `dim_naics`, `dim_state` and `dim_award`. Eighteen DAX measures cover spend, YoY, vendor share, HHI, anomalies and forecast vs actual. See [measures_explained.md](powerbi/measures_explained.md).

## Report pages

| Page | Screenshot |
|---|---|
| 1. Executive overview: KPIs, defense vs civilian trend, agency totals | `docs/screenshots/1_overview.png` *(placeholder)* |
| 2. Vendors: top 20 (re-ranks by agency), vendor × agency market share grid | `docs/screenshots/2_vendors.png` *(placeholder)* |
| 3. Map: obligations by state, top 15 states | `docs/screenshots/3_map.png` *(placeholder)* |
| 4. Risk: HHI by agency and bureau, flagged anomalies with reasons | `docs/screenshots/4_risk.png` *(placeholder)* |
| 5. Forecast: next 4 quarters with 80% bands, backtest scores | `docs/screenshots/5_forecast.png` *(placeholder)* |

## Limitations and validation

**Data**
- **DoD FY2026 Q4 is incomplete.** DoD publishes about 90 days late, so the forecast stops both series at FY2026 Q3.
- **Spend is grouped by awarding agency.** GSA buys on behalf of others, so some GSA dollars serve DoD.
- **Parent companies come from SAM.gov.** Private-equity owners can appear as the parent, and only Oracle–Cerner was merged by hand.
- **The downloaded files hold 99.2% of the API's own row count.** The 0.8% gap is almost all DoD and couldn't be traced.
- **Dollars are nominal** (not inflation-adjusted) and **net** (deobligations included).

**Anomaly model**
- **No labels exist,** so precision can't be measured. The output is a ranked review queue.
- **Debugging changed the model in four ways:**
  - deobligations are left out, since they had dominated the flags
  - history from before FY2022 is ignored
  - only unusually *large* actions can be flagged
  - micro-purchases under $10K are excluded, since they distorted each vendor's "typical" size
- **Stability:** the top 100 flags are 86% the same across random seeds, and year-end spending doesn't inflate the flags.
- **Known bias:** vendors that mix many small orders with big programs (e.g. Leidos) are over-flagged.

**Forecast**
- **19 quarters is a small sample.** The fitted model behaves like a fixed trend plus a fixed seasonal pattern.
- **Rolling backtest:** defense beats the baseline in 8 of 8 windows. Civilian is about a tie, and the model missed a 23% drop in FY2025 Q3.
- **The 80% bands are too narrow:** they held the actual value only 56–69% of the time.

Details: [data_quality.md](data_quality.md) · [validation.md](validation.md)
