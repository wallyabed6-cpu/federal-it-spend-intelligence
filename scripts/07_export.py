# 07_export.py
# exports clean csvs for power bi: one file per fact and dimension table.
#
# run:  python scripts/07_export.py   (after 03_load_db.py, 05_anomaly.py, 06_forecast.py)
# in:   data/fed_it_spend.db
# out:  powerbi/data/*.csv
#
# design choices for power bi:
#   - long text keys (txn_key, award_key) become small integer ids, which keeps the fact
#     file small and makes relationships faster
#   - the anomaly flag, rank, and "why flagged" reason are columns on fact_awards (blank when
#     not flagged), so the risk page needs no extra table or relationship
#   - forecast and backtest tables stand alone (they are at quarter level, not day level)

import os
import sqlite3
import pandas as pd

db_path = os.path.join("data", "fed_it_spend.db")
out_dir = os.path.join("powerbi", "data")
os.makedirs(out_dir, exist_ok=True)
con = sqlite3.connect(db_path)


def save(df, name):
    # write one csv and report its size
    path = os.path.join(out_dir, name + ".csv")
    df.to_csv(path, index=False)
    size_mb = os.path.getsize(path) / 1024 / 1024
    print(name.ljust(20), str(len(df)).rjust(8), "rows", str(round(size_mb, 1)).rjust(6), "MB")


# fact_awards: one row per transaction
fact = pd.read_sql("""
SELECT txn_key, award_key, date_key, agency_key, vendor_key, naics_code, state_code,
       action_type, extent_competed, obligation, is_new_award, is_deobligation, partial_period
FROM fact_awards
ORDER BY date_key, txn_key
""", con)

# integer ids instead of long text keys
fact["txn_id"] = range(1, len(fact) + 1)
award_ids = pd.Series(range(1, fact["award_key"].nunique() + 1), index=fact["award_key"].unique())
fact["award_id"] = fact["award_key"].map(award_ids)

# attach anomaly results (blank for rows that weren't flagged)
anom = pd.read_sql("SELECT txn_key, anomaly_rank, why_flagged FROM anomalies", con)
fact = fact.merge(anom, on="txn_key", how="left")
fact["is_anomaly"] = fact["anomaly_rank"].notna().astype(int)
fact["anomaly_rank"] = fact["anomaly_rank"].astype("Int64")
print("anomalies attached:", fact["is_anomaly"].sum())

fact = fact[[
    "txn_id", "award_id", "date_key", "agency_key", "vendor_key", "naics_code", "state_code",
    "action_type", "extent_competed", "obligation", "is_new_award", "is_deobligation",
    "partial_period", "is_anomaly", "anomaly_rank", "why_flagged",
]]
save(fact, "fact_awards")

# award lookup, so a flagged row can be traced back to its USAspending award id
awards = pd.read_sql("SELECT DISTINCT award_key, piid FROM fact_awards", con)
awards = awards.drop_duplicates("award_key")
awards["award_id"] = awards["award_key"].map(award_ids)
awards = awards.sort_values("award_id")
save(awards[["award_id", "award_key", "piid"]], "dim_award")

# dimensions, straight from the database
save(pd.read_sql("SELECT * FROM dim_agency", con), "dim_agency")
save(pd.read_sql("SELECT * FROM dim_vendor", con), "dim_vendor")
save(pd.read_sql("SELECT * FROM dim_date", con), "dim_date")
save(pd.read_sql("SELECT * FROM dim_naics", con), "dim_naics")
save(pd.read_sql("SELECT * FROM dim_state", con), "dim_state")

# forecast: actuals, backtest, and future quarters in one long table
save(pd.read_sql("SELECT * FROM forecast", con), "forecast")
save(pd.read_sql("SELECT * FROM forecast_backtest", con), "forecast_backtest")

# check: dollars in the export match the database
db_total = con.execute("SELECT SUM(obligation) FROM fact_awards").fetchone()[0]
print()
print("total obligations, database ($):", round(db_total, 2))
print("total obligations, export   ($):", round(fact["obligation"].sum(), 2))
con.close()
