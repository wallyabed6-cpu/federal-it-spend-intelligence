# validate_models.py
# checks behind validation.md. run after 05_anomaly.py and 06_forecast.py.
#
# run:  python scripts/validate_models.py
# in:   data/fed_it_spend.db, data/clean/anomaly_scores.csv.gz, data/clean/anomalies.csv
# out:  printed results only (copied into validation.md)

import os
import sqlite3
import warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

warnings.filterwarnings("ignore")
db_path = os.path.join("data", "fed_it_spend.db")
con = sqlite3.connect(db_path)

print("=" * 70)
print("ANOMALY MODEL")
print("=" * 70)

scores = pd.read_csv(os.path.join("data", "clean", "anomaly_scores.csv.gz"))
flagged = pd.read_csv(os.path.join("data", "clean", "anomalies.csv"))
features = ["log_amount", "vendor_ratio", "peer_ratio", "award_jump"]

# rebuild the same model input as 05_anomaly.py (features floored at their median)
X = pd.DataFrame(index=scores.index)
for col in features:
    X[col] = scores[col].clip(lower=scores[col].median())
base = set(scores.loc[scores["is_anomaly"], "txn_key"])

# check 1: does a different random seed flag the same rows?
print()
print("1. seed stability (overlap with the seed-42 flags)")
for seed in [1, 7, 99]:
    m = IsolationForest(n_estimators=300, contamination=0.01, random_state=seed)
    pred = m.fit(X).predict(X) == -1
    other = set(scores.loc[pred, "txn_key"])
    overlap = len(base & other) / len(base | other)
    print("   seed", str(seed).rjust(2), "-> jaccard overlap", round(overlap, 3))

# check 2: are the strongest flags stable? top 100 by score at seed 42 vs seed 7
m = IsolationForest(n_estimators=300, contamination=0.01, random_state=7)
m.fit(X)
alt_score = m.decision_function(X)
top_a = set(scores.nsmallest(100, "anomaly_score")["txn_key"])
top_b = set(scores.loc[np.argsort(alt_score)[:100], "txn_key"])
print("   top-100 overlap, seed 42 vs 7:", len(top_a & top_b), "of 100")

# check 3: how sensitive is the flag count to the 1% choice?
print()
print("2. cutoff sensitivity (flagged rows at other contamination levels)")
for share in [0.005, 0.01, 0.02]:
    cut = np.quantile(scores["anomaly_score"], share)
    print("   top", str(share * 100) + "%", "->", (scores["anomaly_score"] <= cut).sum(), "rows")

# check 4: small vendors. their median includes the row being scored, so a vendor with
# 1-2 actions always looks "typical" of itself. are they under- or over-flagged?
vend = pd.read_sql("""
SELECT f.txn_key, v.vendor FROM fact_awards f JOIN dim_vendor v ON v.vendor_key = f.vendor_key
WHERE f.obligation >= 10000
""", con)
scores = scores.merge(vend, on="txn_key", how="left")
counts = scores["vendor"].value_counts()
scores["vendor_txns"] = scores["vendor"].map(counts)
scores["vendor_size"] = "50+ actions"
scores.loc[scores["vendor_txns"] < 50, "vendor_size"] = "5-49 actions"
scores.loc[scores["vendor_txns"] < 5, "vendor_size"] = "1-4 actions"
print()
print("3. flag rate by vendor size (vendor median includes the scored row)")
rate = scores.groupby("vendor_size")["is_anomaly"].agg(["count", "mean"])
rate["mean"] = (rate["mean"] * 100).round(2)
rate.columns = ["scored rows", "flag rate %"]
print(rate.to_string())

# check 5: vendor concentration of flags vs. share of scored dollars
print()
print("4. vendors with the most flags: share of flags vs. share of scored dollars")
amt = pd.read_sql("SELECT txn_key, obligation FROM fact_awards WHERE obligation >= 10000", con)
scores = scores.merge(amt, on="txn_key", how="left")
by_vendor = scores.groupby("vendor").agg(flags=("is_anomaly", "sum"), dollars=("obligation", "sum"))
by_vendor["flag_share_pct"] = (100 * by_vendor["flags"] / by_vendor["flags"].sum()).round(1)
by_vendor["dollar_share_pct"] = (100 * by_vendor["dollars"] / by_vendor["dollars"].sum()).round(1)
print(by_vendor.sort_values("flags", ascending=False).head(5)[["flags", "flag_share_pct", "dollar_share_pct"]].to_string())

# check 6: do the plain-english rules agree with the model?
print()
print("5. rules vs. model")
rule_hit = ~flagged["why_flagged"].str.startswith("Unusual mix")
print("   flagged rows with at least one specific rule:", rule_hit.sum(), "of", len(flagged),
      "(" + str(round(100 * rule_hit.mean(), 1)) + "%)")
print("   flagged rows over $100M:", (flagged["obligation"] >= 100e6).sum(),
      "| all scored rows over $100M:", (scores["obligation"] >= 100e6).sum())

# check 7: year-end
dates = pd.read_sql("""
SELECT f.txn_key, d.fiscal_month FROM fact_awards f JOIN dim_date d ON d.date_key = f.date_key
WHERE f.obligation >= 10000
""", con)
scores = scores.merge(dates, on="txn_key", how="left")
sept_all = (scores["fiscal_month"] == 12).mean() * 100
sept_flag = (scores.loc[scores["is_anomaly"], "fiscal_month"] == 12).mean() * 100
print()
print("6. year-end: september share of flags", round(sept_flag, 1), "% vs. all scored rows", round(sept_all, 1), "%")

print()
print("=" * 70)
print("FORECAST MODEL")
print("=" * 70)

q = pd.read_sql("""
SELECT d.fiscal_year * 10 + d.fiscal_quarter AS ord, d.fy_quarter, a.sector, SUM(f.obligation) / 1e9 AS b
FROM fact_awards f JOIN dim_date d ON d.date_key = f.date_key JOIN dim_agency a ON a.agency_key = f.agency_key
GROUP BY 1, 2, 3 ORDER BY 1
""", con)
q = q[q["ord"] <= 20263]


def fit_ets(values):
    # same model as 06_forecast.py
    series = pd.Series(values, index=range(len(values)))
    model = ETSModel(series, error="mul", trend="add", damped_trend=True, seasonal="mul", seasonal_periods=4)
    return model.fit(disp=False)


# check 1: rolling origin. test on every 4-quarter window we can, not just the last one.
# the model needs 2 full years (8 quarters) to start, so training runs from 8 to 15 quarters
print()
print("1. rolling-origin backtest (train on everything before, test the next 4 quarters)")
rows = []
for sector in ["Defense", "Civilian"]:
    s = q[q["sector"] == sector]
    values = s["b"].to_numpy()
    labels = list(s["fy_quarter"])
    for end in range(12, len(values) + 1):
        train = values[:end - 4]
        test = values[end - 4:end]
        fit = fit_ets(train)
        frame = fit.get_prediction(start=len(train), end=len(train) + 3).summary_frame(alpha=0.2)
        fc = frame["mean"].to_numpy()
        naive = values[end - 8:end - 4]
        inside = ((test >= frame["pi_lower"].to_numpy()) & (test <= frame["pi_upper"].to_numpy())).sum()
        rows.append([sector, labels[end - 4] + " - " + labels[end - 1], len(train),
                     round(np.mean(np.abs(fc - test) / test) * 100, 1),
                     round(np.mean(np.abs(naive - test) / test) * 100, 1), inside])
roll = pd.DataFrame(rows, columns=["sector", "test window", "train qtrs", "model MAPE %", "naive MAPE %", "inside 80% PI (of 4)"])
print(roll.to_string(index=False))
print()
summary = roll.groupby("sector").agg(windows=("test window", "count"), model=("model MAPE %", "mean"),
                                     naive=("naive MAPE %", "mean"), inside=("inside 80% PI (of 4)", "sum"))
summary["model"] = summary["model"].round(1)
summary["naive"] = summary["naive"].round(1)
summary["model wins"] = roll.assign(win=roll["model MAPE %"] < roll["naive MAPE %"]).groupby("sector")["win"].sum()
summary["PI coverage %"] = (100 * summary["inside"] / (4 * summary["windows"])).round(0)
print("   average across windows (80% interval should cover ~80%):")
print(summary.to_string())

# check 2: are the residuals biased? (mean error on the training fit)
print()
print("2. in-sample fit on all 19 quarters")
for sector in ["Defense", "Civilian"]:
    values = q.loc[q["sector"] == sector, "b"].to_numpy()
    fit = fit_ets(values)
    resid = values - fit.fittedvalues.to_numpy()
    params = dict(zip(fit.param_names, np.round(fit.params, 3)))
    print("  ", sector, "| mean residual $B", round(resid.mean(), 3), "| alpha", params["smoothing_level"],
          "beta", params["smoothing_trend"], "gamma", params["smoothing_seasonal"], "phi", params["damping_trend"])

# check 3: how big is the q4 spike, and is the error worse in q4?
print()
print("3. seasonal shape: Q4 as a multiple of Q1 in the same fiscal year")
for sector in ["Defense", "Civilian"]:
    s = q[q["sector"] == sector].copy()
    s["fy"] = s["ord"] // 10
    s["qtr"] = s["ord"] % 10
    q1 = s[s["qtr"] == 1].set_index("fy")["b"]
    q4 = s[s["qtr"] == 4].set_index("fy")["b"]
    ratio = (q4 / q1).dropna().round(2)
    print("  ", sector, ratio.to_dict())

con.close()
