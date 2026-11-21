# 04_analysis.py
# runs every numbered query in sql/ against the database and saves each result as a csv.
#
# run:  python scripts/04_analysis.py
# in:   data/fed_it_spend.db, sql/01_*.sql ... sql/06_*.sql
# out:  data/clean/analysis/<query name>.csv

import os
import glob
import sqlite3
import pandas as pd

db_path = os.path.join("data", "fed_it_spend.db")
out_dir = os.path.join("data", "clean", "analysis")
os.makedirs(out_dir, exist_ok=True)

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", 20)

con = sqlite3.connect(db_path)

# 00_schema.sql builds the tables, so skip it; everything else is a query
paths = sorted(glob.glob(os.path.join("sql", "*.sql")))
for path in paths:
    name = os.path.basename(path).replace(".sql", "")
    if name.startswith("00_"):
        continue
    with open(path, encoding="utf-8") as f:
        query = f.read()
    result = pd.read_sql(query, con)
    result.to_csv(os.path.join(out_dir, name + ".csv"), index=False)

    # print a short preview of each result
    print("=" * 80)
    print(name, "(" + str(len(result)) + " rows)")
    print(result.head(12).to_string(index=False))
    print()

con.close()
