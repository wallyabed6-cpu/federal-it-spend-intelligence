# 05_anomaly.py
# flags unusual contract transactions with an Isolation Forest, then explains each flag in plain English.
#
# run:  python scripts/05_anomaly.py
# in:   data/fed_it_spend.db
# out:  data/clean/anomalies.csv          (flagged rows only, with "why_flagged")
#       data/clean/anomaly_scores.csv.gz  (score for every row that was scored)
#       table "anomalies" in the database (same as anomalies.csv)
#
# scored rows: transactions that add at least $10,000 (the FAR micro-purchase threshold).
# deobligations, $0 paperwork actions, and micro-purchases are left out.
#
# features:
#   log_amount   size of this action (log10)
#   vendor_ratio this action vs. the vendor's median action size (log10)
#   peer_ratio   this action vs. the median action at the same agency + NAICS code (log10)
#   award_jump   this action vs. everything obligated on the same award before it (log10).
#                only for awards whose original award (mod 0) is in our data. older awards have
#                history from before FY2022 we can't see, so they get a neutral 0.

import os
import sqlite3
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

db_path = os.path.join("data", "fed_it_spend.db")
out_dir = os.path.join("data", "clean")
flag_share = 0.01      # flag the top ~1% most unusual
min_amount = 10000     # micro-purchase threshold: 23% of actions but 0.06% of dollars
seed = 42              # fixed so the same rows get flagged every run

con = sqlite3.connect(db_path)
query = """
SELECT f.txn_key, f.award_key, f.piid, f.mod_number, f.date_key, d.date, d.fy_quarter,
       d.fiscal_month, a.agency, a.sub_agency, a.sector, v.vendor, f.naics_code,
       f.action_type, f.obligation, f.partial_period
FROM fact_awards f
JOIN dim_date d   ON d.date_key = f.date_key
JOIN dim_agency a ON a.agency_key = f.agency_key
JOIN dim_vendor v ON v.vendor_key = f.vendor_key
"""
df = pd.read_sql(query, con)
print("transactions in database:", len(df))

# which awards started inside our window (their mod 0 is in the data)
started = df.loc[df["mod_number"] == "0", "award_key"].unique()
df["award_in_window"] = df["award_key"].isin(started)

# score only actions that add real money. $0 actions are paperwork, deobligations
# (money taken back) are a different question, and micro-purchases are card-style buys
# that would drag every vendor's "typical" size down to a few thousand dollars
df = df[df["obligation"] >= min_amount].copy()
print("transactions adding $10K or more (scored):", len(df))

df["abs_amt"] = df["obligation"]

# feature 1: size of the action
df["log_amount"] = np.log10(1 + df["abs_amt"])

# feature 2: vs. the vendor's typical action
vendor_median = df.groupby("vendor")["abs_amt"].median()
df["vendor_median"] = df["vendor"].map(vendor_median)
df["vendor_txns"] = df["vendor"].map(df["vendor"].value_counts())
df["vendor_ratio"] = np.log10(df["abs_amt"] / df["vendor_median"])

# feature 3: vs. typical actions for the same agency and NAICS code
df["peer"] = df["agency"] + " | " + df["naics_code"]
peer_median = df.groupby("peer")["abs_amt"].median()
df["peer_median"] = df["peer"].map(peer_median)
df["peer_ratio"] = np.log10(df["abs_amt"] / df["peer_median"])

# feature 4: vs. what the award had received before this action
# sort each award's actions in time order, then sum the dollars that came earlier
df = df.sort_values(["award_key", "date_key", "mod_number"])
df["prior_total"] = df.groupby("award_key")["obligation"].cumsum() - df["obligation"]
has_prior = (df["prior_total"] > 0) & df["award_in_window"]
df["award_ratio"] = np.nan
df.loc[has_prior, "award_ratio"] = df.loc[has_prior, "abs_amt"] / df.loc[has_prior, "prior_total"]
# first action on an award has nothing to compare to, so it gets a neutral 0
df["award_jump"] = 0.0
df.loc[has_prior, "award_jump"] = np.log10(1 + df.loc[has_prior, "award_ratio"])

features = ["log_amount", "vendor_ratio", "peer_ratio", "award_jump"]

# isolation forest flags both tails, but a $3 order isn't a risk. we only care about
# actions that are unusually big, so anything at or below the median counts as typical
X = pd.DataFrame(index=df.index)
for col in features:
    floor = df[col].median()
    X[col] = df[col].clip(lower=floor)
print()
print("feature summary:")
print(X.describe().round(2).to_string())

# fit the model and score every row (lower score = more unusual)
model = IsolationForest(n_estimators=300, contamination=flag_share, random_state=seed)
model.fit(X)
df["anomaly_score"] = model.decision_function(X)
df["is_anomaly"] = model.predict(X) == -1
print()
print("flagged:", df["is_anomaly"].sum(), "of", len(df))


def money(x):
    # $1,234,567 -> "$1.2M"
    if abs(x) >= 1e9:
        return "$" + str(round(x / 1e9, 1)) + "B"
    if abs(x) >= 1e6:
        return "$" + str(round(x / 1e6, 1)) + "M"
    if abs(x) >= 1e3:
        return "$" + str(round(x / 1e3)) + "K"
    return "$" + str(round(x))


def why(row):
    # turn the features into short reasons a reviewer can check by hand
    reasons = []
    if row["obligation"] >= 100e6:
        reasons.append("Over $100M in a single action")
    if row["vendor_ratio"] >= 1 and row["vendor_txns"] >= 5:
        times = round(10 ** row["vendor_ratio"])
        reasons.append(str(times) + "x the vendor's median action (" + money(row["vendor_median"]) + ")")
    if row["peer_ratio"] >= 1:
        times = round(10 ** row["peer_ratio"])
        reasons.append(str(times) + "x the typical " + row["agency"].replace("Department of the ", "").replace("Department of ", "")
                       + " action for NAICS " + row["naics_code"])
    if row["award_ratio"] >= 5:
        reasons.append(str(round(row["award_ratio"])) + "x everything obligated on this award before it")
    if len(reasons) == 0:
        reasons.append("Unusual mix of size, vendor history, and award history")
    return "; ".join(reasons)


flagged = df[df["is_anomaly"]].copy()
flagged["why_flagged"] = flagged.apply(why, axis=1)
flagged["year_end"] = flagged["fiscal_month"] == 12   # september, the year-end spending rush
flagged = flagged.sort_values("anomaly_score")
flagged["anomaly_rank"] = range(1, len(flagged) + 1)

# keep readable columns for the report
out = flagged[[
    "anomaly_rank", "txn_key", "award_key", "piid", "mod_number", "date", "fy_quarter", "agency",
    "sub_agency", "sector", "vendor", "naics_code", "action_type", "obligation", "vendor_median",
    "peer_median", "prior_total", "anomaly_score", "year_end", "why_flagged",
]]
out.to_csv(os.path.join(out_dir, "anomalies.csv"), index=False)
out.to_sql("anomalies", con, if_exists="replace", index=False)

scores = df[["txn_key", "anomaly_score", "is_anomaly"] + features]
scores.to_csv(os.path.join(out_dir, "anomaly_scores.csv.gz"), index=False, compression="gzip")
con.close()

# quick look at what got flagged
pd.set_option("display.width", 250)
pd.set_option("display.max_colwidth", 110)
print()
print("flagged by sector:")
print(flagged["sector"].value_counts().to_string())
print()
print("flagged that are new awards (mod 0):", (flagged["mod_number"] == "0").sum())
print("flagged with a fallback reason only:", flagged["why_flagged"].str.startswith("Unusual mix").sum())
print("flagged in september (year-end):", round(100 * flagged["year_end"].mean(), 1), "%",
      "| all scored rows in september:", round(100 * (df["fiscal_month"] == 12).mean(), 1), "%")
print()
print("top 15:")
show = out.head(15).copy()
show["obligation"] = show["obligation"].apply(money)
print(show[["anomaly_rank", "date", "agency", "vendor", "obligation", "why_flagged"]].to_string(index=False))
