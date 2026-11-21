# 06_forecast.py
# forecasts quarterly IT obligations for the next 4 quarters, defense vs. civilian.
#
# run:  python scripts/06_forecast.py
# in:   data/fed_it_spend.db
# out:  data/clean/forecast.csv            (actuals, backtest, and future forecast in one table)
#       data/clean/forecast_backtest.csv   (error metrics for the held-out quarters)
#       tables "forecast" and "forecast_backtest" in the database
#
# method:
#   series ends at FY2026 Q3 for both sectors. DoD's FY2026 Q4 is incomplete (publication lag),
#   so we stop both series there to keep them comparable (see data_quality.md).
#   model: Holt-Winters exponential smoothing (statsmodels ETSModel) with a damped additive
#   trend and multiplicative seasonality, since the Q4 year-end spike grows with total spend.
#   baseline: seasonal naive (forecast = same quarter last year). the model has to beat it.
#   backtest: fit on the first 15 quarters, forecast the last 4 known quarters, compare.

import os
import sqlite3
import warnings
import numpy as np
import pandas as pd
from statsmodels.tsa.exponential_smoothing.ets import ETSModel

# statsmodels warns about convergence on short series; we check the results ourselves below
warnings.filterwarnings("ignore")

db_path = os.path.join("data", "fed_it_spend.db")
out_dir = os.path.join("data", "clean")
last_quarter = "FY2026 Q3"
holdout = 4
horizon = 4

con = sqlite3.connect(db_path)
query = """
SELECT d.fiscal_year, d.fiscal_quarter, d.fy_quarter, a.sector, SUM(f.obligation) AS obligated
FROM fact_awards f
JOIN dim_date d   ON d.date_key = f.date_key
JOIN dim_agency a ON a.agency_key = f.agency_key
GROUP BY d.fiscal_year, d.fiscal_quarter, d.fy_quarter, a.sector
ORDER BY d.fiscal_year, d.fiscal_quarter
"""
q = pd.read_sql(query, con)

# keep quarters up to the cutoff, in $ billions for readability
q["order"] = q["fiscal_year"] * 10 + q["fiscal_quarter"]
cutoff = int(last_quarter[2:6]) * 10 + int(last_quarter[-1])
q = q[q["order"] <= cutoff].copy()
q["obligated_b"] = q["obligated"] / 1e9


def next_quarters(fy_quarter, n):
    # "FY2026 Q3", 2 -> ["FY2026 Q4", "FY2027 Q1"]
    year = int(fy_quarter[2:6])
    qtr = int(fy_quarter[-1])
    labels = []
    for i in range(n):
        qtr = qtr + 1
        if qtr == 5:
            qtr = 1
            year = year + 1
        labels.append("FY" + str(year) + " Q" + str(qtr))
    return labels


def fit_ets(values):
    # damped additive trend, multiplicative seasonality, 4 quarters per year
    # (statsmodels needs a pandas series, not a plain array, to build prediction intervals)
    series = pd.Series(values, index=range(len(values)))
    model = ETSModel(series, error="mul", trend="add", damped_trend=True,
                     seasonal="mul", seasonal_periods=4)
    return model.fit(disp=False)


rows = []
metrics = []
for sector in ["Defense", "Civilian"]:
    s = q[q["sector"] == sector].sort_values("order")
    labels = list(s["fy_quarter"])
    values = s["obligated_b"].to_numpy()
    print(sector, ":", len(values), "quarters,", labels[0], "to", labels[-1])

    # actuals
    for i in range(len(values)):
        rows.append([sector, labels[i], "actual", values[i], np.nan, np.nan])

    # backtest: train on all but the last 4, forecast those 4
    train = values[:-holdout]
    test = values[-holdout:]
    test_labels = labels[-holdout:]

    fit = fit_ets(train)
    pred = fit.get_prediction(start=len(train), end=len(train) + holdout - 1)
    frame = pred.summary_frame(alpha=0.2)   # 80% interval
    model_fc = frame["mean"].to_numpy()

    # seasonal naive: same quarter one year earlier
    naive_fc = values[-holdout - 4:-4]

    for i in range(holdout):
        rows.append([sector, test_labels[i], "backtest", model_fc[i],
                     frame["pi_lower"].iloc[i], frame["pi_upper"].iloc[i]])
        rows.append([sector, test_labels[i], "backtest_naive", naive_fc[i], np.nan, np.nan])

    # error metrics on the held-out year
    model_mae = np.mean(np.abs(model_fc - test))
    model_mape = np.mean(np.abs(model_fc - test) / test) * 100
    naive_mae = np.mean(np.abs(naive_fc - test))
    naive_mape = np.mean(np.abs(naive_fc - test) / test) * 100
    total_err = (model_fc.sum() - test.sum()) / test.sum() * 100
    metrics.append([sector, "Holt-Winters (ETS)", round(model_mae, 3), round(model_mape, 1), round(total_err, 1)])
    metrics.append([sector, "Seasonal naive", round(naive_mae, 3), round(naive_mape, 1),
                    round((naive_fc.sum() - test.sum()) / test.sum() * 100, 1)])

    # quarter-by-quarter view of the backtest
    check = pd.DataFrame()
    check["quarter"] = test_labels
    check["actual_b"] = test.round(2)
    check["model_b"] = model_fc.round(2)
    check["naive_b"] = naive_fc.round(2)
    check["model_err_pct"] = ((model_fc - test) / test * 100).round(1)
    print(check.to_string(index=False))

    # final model: refit on every known quarter, forecast the next 4
    full_fit = fit_ets(values)
    fc = full_fit.get_prediction(start=len(values), end=len(values) + horizon - 1)
    fc_frame = fc.summary_frame(alpha=0.2)
    future_labels = next_quarters(labels[-1], horizon)
    for i in range(horizon):
        rows.append([sector, future_labels[i], "forecast", fc_frame["mean"].iloc[i],
                     fc_frame["pi_lower"].iloc[i], fc_frame["pi_upper"].iloc[i]])
    print("fitted params:", dict(zip(full_fit.param_names, np.round(full_fit.params, 3))))
    print()

out = pd.DataFrame(rows, columns=["sector", "fy_quarter", "series", "obligated_b", "lower_80_b", "upper_80_b"])
out["fiscal_year"] = out["fy_quarter"].str[2:6].astype(int)
out["fiscal_quarter"] = out["fy_quarter"].str[-1].astype(int)
out = out[["sector", "fiscal_year", "fiscal_quarter", "fy_quarter", "series", "obligated_b", "lower_80_b", "upper_80_b"]]
out.to_csv(os.path.join(out_dir, "forecast.csv"), index=False)
out.to_sql("forecast", con, if_exists="replace", index=False)

backtest = pd.DataFrame(metrics, columns=["sector", "model", "mae_b", "mape_pct", "total_error_pct"])
backtest.to_csv(os.path.join(out_dir, "forecast_backtest.csv"), index=False)
backtest.to_sql("forecast_backtest", con, if_exists="replace", index=False)

print("backtest on the last 4 known quarters (FY2025 Q4 - FY2026 Q3):")
print(backtest.to_string(index=False))
print()
print("forecast, next 4 quarters ($B, 80% interval):")
future = out[out["series"] == "forecast"].copy()
print(future[["sector", "fy_quarter", "obligated_b", "lower_80_b", "upper_80_b"]].round(2).to_string(index=False))

# extra out-of-sample check: civilian FY2026 Q4 is complete in the data, so compare the
# forecast for it to what actually happened (defense FY2026 Q4 is partial, so no check there)
civ_q4 = pd.read_sql("""
SELECT SUM(f.obligation) / 1e9 AS b FROM fact_awards f
JOIN dim_date d ON d.date_key = f.date_key JOIN dim_agency a ON a.agency_key = f.agency_key
WHERE a.sector = 'Civilian' AND d.fy_quarter = 'FY2026 Q4'
""", con)["b"].iloc[0]
civ_fc = future[(future["sector"] == "Civilian") & (future["fy_quarter"] == "FY2026 Q4")]
print()
print("civilian FY2026 Q4: forecast", round(civ_fc["obligated_b"].iloc[0], 2), "vs actual", round(civ_q4, 2),
      "(" + str(round((civ_fc["obligated_b"].iloc[0] - civ_q4) / civ_q4 * 100, 1)) + "%)")
con.close()
