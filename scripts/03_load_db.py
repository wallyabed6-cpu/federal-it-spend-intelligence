# 03_load_db.py
# builds the SQLite star schema from the clean transactions file.
#
# run:  python scripts/03_load_db.py
# in:   data/clean/transactions.csv.gz, sql/00_schema.sql
# out:  data/fed_it_spend.db   (gitignored, rebuilds in seconds)

import os
import sqlite3
import pandas as pd

clean_path = os.path.join("data", "clean", "transactions.csv.gz")
schema_path = os.path.join("sql", "00_schema.sql")
db_path = os.path.join("data", "fed_it_spend.db")

df = pd.read_csv(clean_path, dtype={"agency_code": str, "naics_code": str, "mod_number": str})
print("clean rows:", len(df))

# start from a fresh database and create the tables
if os.path.exists(db_path):
    os.remove(db_path)
con = sqlite3.connect(db_path)
with open(schema_path, encoding="utf-8") as f:
    con.executescript(f.read())

# dim_agency: one row per sub-agency
agency = df[["agency_code", "agency", "sub_agency", "sector"]].drop_duplicates()
agency = agency.sort_values(["agency", "sub_agency"]).reset_index(drop=True)
agency["agency_key"] = agency.index + 1
agency = agency[["agency_key", "agency_code", "agency", "sub_agency", "sector"]]

# dim_vendor: one row per standardized vendor name
vendor = df[["vendor"]].drop_duplicates()

# most common parent UEI for each vendor name
uei_counts = df.groupby(["vendor", "parent_uei"]).size().reset_index(name="n")
uei_counts = uei_counts.sort_values("n", ascending=False).drop_duplicates("vendor")
vendor = vendor.merge(uei_counts[["vendor", "parent_uei"]], on="vendor", how="left")

# how many separate recipients roll up into each vendor
recips = df.groupby("vendor")["recipient_uei"].nunique().reset_index(name="n_recipients")
vendor = vendor.merge(recips, on="vendor", how="left")
vendor = vendor.sort_values("vendor").reset_index(drop=True)
vendor["vendor_key"] = vendor.index + 1
vendor = vendor[["vendor_key", "vendor", "parent_uei", "n_recipients"]]

# dim_date: every day from the start of FY2022 to the end of FY2027
days = pd.date_range("2021-10-01", "2027-09-30", freq="D")
dates = pd.DataFrame()
dates["date_key"] = days.strftime("%Y%m%d").astype(int)
dates["date"] = days.strftime("%Y-%m-%d")
dates["calendar_year"] = days.year
dates["month"] = days.month
dates["month_name"] = days.strftime("%b")
dates["fiscal_year"] = days.year
dates.loc[dates["month"] >= 10, "fiscal_year"] = dates["calendar_year"] + 1
dates["fiscal_quarter"] = ((dates["month"] + 2) % 12) // 3 + 1
dates["fiscal_month"] = (dates["month"] + 2) % 12 + 1
dates["fy_quarter"] = "FY" + dates["fiscal_year"].astype(str) + " Q" + dates["fiscal_quarter"].astype(str)

# dim_naics: the four codes in scope
naics = df[["naics_code", "naics_description"]].drop_duplicates("naics_code")
naics = naics.sort_values("naics_code")

# dim_state: codes found in the data, with full names for the map
state_names = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
    "PR": "Puerto Rico", "GU": "Guam", "VI": "U.S. Virgin Islands", "AS": "American Samoa",
    "MP": "Northern Mariana Islands", "AE": "Armed Forces Europe", "AP": "Armed Forces Pacific",
    "AA": "Armed Forces Americas", "UNK": "Unknown",
}
state = df[["state", "state_type"]].drop_duplicates("state").sort_values("state")
state = state.rename(columns={"state": "state_code"})
state["state_name"] = state["state_code"].map(state_names)
missing_names = state["state_name"].isna().sum()
print("state codes without a name:", missing_names)
state["state_name"] = state["state_name"].fillna(state["state_code"])
state = state[["state_code", "state_name", "state_type"]]

# fact_awards: swap text columns for dimension keys
fact = df.merge(agency[["agency_key", "agency_code", "sub_agency"]], on=["agency_code", "sub_agency"], how="left")
fact = fact.merge(vendor[["vendor_key", "vendor"]], on="vendor", how="left")
fact["date_key"] = fact["action_date"].str.replace("-", "").astype(int)
fact = fact.rename(columns={"state": "state_code"})
for col in ["is_new_award", "is_deobligation", "is_zero_dollar", "partial_period"]:
    fact[col] = fact[col].astype(int)
fact = fact[[
    "txn_key", "award_key", "piid", "mod_number", "date_key", "agency_key", "vendor_key",
    "naics_code", "state_code", "recipient_uei", "recipient_name", "action_type", "award_type",
    "pricing_type", "extent_competed", "psc_code", "offers", "obligation",
    "base_and_all_options_value", "is_new_award", "is_deobligation", "is_zero_dollar", "partial_period",
]]
print("fact rows with a missing key:", fact[["agency_key", "vendor_key"]].isna().any(axis=1).sum())

# load dimensions first, then the fact table (foreign keys need the dimensions to exist)
agency.to_sql("dim_agency", con, if_exists="append", index=False)
vendor.to_sql("dim_vendor", con, if_exists="append", index=False)
dates.to_sql("dim_date", con, if_exists="append", index=False)
naics.to_sql("dim_naics", con, if_exists="append", index=False)
state.to_sql("dim_state", con, if_exists="append", index=False)
fact.to_sql("fact_awards", con, if_exists="append", index=False, chunksize=50000)
con.commit()

# check: row counts per table
print()
for table in ["dim_agency", "dim_vendor", "dim_date", "dim_naics", "dim_state", "fact_awards"]:
    n = con.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
    print(table.ljust(12), n)

# check: every foreign key resolves (sqlite lists any broken ones)
broken = con.execute("PRAGMA foreign_key_check").fetchall()
print("broken foreign keys:", len(broken))

# check: dollars in the database match the clean file
db_total = con.execute("SELECT SUM(obligation) FROM fact_awards").fetchone()[0]
print("total obligations, clean file ($):", round(df["obligation"].sum(), 2))
print("total obligations, database   ($):", round(db_total, 2))

con.close()
size_mb = os.path.getsize(db_path) / 1024 / 1024
print("saved", db_path, "(" + str(round(size_mb, 1)) + " MB)")
