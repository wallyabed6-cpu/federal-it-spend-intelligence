# 02_clean.py
# reads the raw USAspending zips, applies cleaning rules, and writes one clean file.
#
# run:  python scripts/02_clean.py
# in:   data/raw/*.zip
# out:  data/clean/transactions.csv.gz   (one row per contract transaction)
#       data/clean/quality_log.csv       (rows affected by each rule, used in data_quality.md)

import os
import re
import glob
import zipfile
import pandas as pd

raw_dir = os.path.join("data", "raw")
clean_dir = os.path.join("data", "clean")
os.makedirs(clean_dir, exist_ok=True)

# each rule appends [rule, action, rows affected] here
quality = []


def note(rule, action, n):
    # record and print how many rows a rule touched
    quality.append([rule, action, int(n)])
    print(rule.ljust(48) + action.ljust(8) + str(int(n)).rjust(9))


# load every zip. each zip also has an empty subawards csv, so pick the transactions file by name
parts = []
for path in sorted(glob.glob(os.path.join(raw_dir, "*.zip"))):
    z = zipfile.ZipFile(path)
    for name in z.namelist():
        if "PrimeTransactions" in name:
            part = pd.read_csv(z.open(name), dtype=str)
            parts.append(part)
df = pd.concat(parts, ignore_index=True)
note("rows loaded from raw files", "info", len(df))

# rule 1: drop exact duplicate transactions
dupes = df["contract_transaction_unique_key"].duplicated()
note("duplicate transaction key", "drop", dupes.sum())
df = df[~dupes].copy()

# rule 2: dates and fiscal quarters
# federal fiscal year starts oct 1, so oct-dec is Q1 of the next fiscal year
df["action_date"] = pd.to_datetime(df["action_date"], errors="coerce")
bad_date = df["action_date"].isna()
note("action_date missing or unparseable", "drop", bad_date.sum())
df = df[~bad_date].copy()

month = df["action_date"].dt.month
year = df["action_date"].dt.year
df["fiscal_year"] = year
df.loc[month >= 10, "fiscal_year"] = year + 1
df["fiscal_quarter"] = ((month + 2) % 12) // 3 + 1
df["fy_quarter"] = "FY" + df["fiscal_year"].astype(str) + " Q" + df["fiscal_quarter"].astype(str)

reported_fy = pd.to_numeric(df["action_date_fiscal_year"], errors="coerce")
fy_mismatch = reported_fy != df["fiscal_year"]
note("fiscal year differs from API value", "flag", fy_mismatch.sum())

# rule 3: dollar amounts to numbers
df["obligation"] = pd.to_numeric(df["federal_action_obligation"], errors="coerce")
bad_amt = df["obligation"].isna()
note("obligation missing or not a number", "drop", bad_amt.sum())
df = df[~bad_amt].copy()
df["base_and_all_options_value"] = pd.to_numeric(df["base_and_all_options_value"], errors="coerce").fillna(0)

# negative = money taken back (deobligation). zero = paperwork-only action. both are real, so flag and keep
df["is_deobligation"] = df["obligation"] < 0
df["is_zero_dollar"] = df["obligation"] == 0
note("negative obligation (deobligation)", "flag", df["is_deobligation"].sum())
note("zero-dollar action", "flag", df["is_zero_dollar"].sum())

# rule 4: blank action_type is always modification 0, i.e. the original award
blank_action = df["action_type"].isna()
note("blank action_type on original award", "fill", blank_action.sum())
df.loc[blank_action, "action_type"] = "NEW AWARD"
df["is_new_award"] = df["modification_number"] == "0"

# rule 5: vendor parent company
# use the parent name when the API has one, otherwise fall back to the recipient name
no_parent = df["recipient_parent_name"].isna()
note("parent name missing, used recipient name", "fill", no_parent.sum())
df["parent_raw"] = df["recipient_parent_name"]
df.loc[no_parent, "parent_raw"] = df.loc[no_parent, "recipient_name"]
no_parent_uei = df["recipient_parent_uei"].isna()
df["parent_uei"] = df["recipient_parent_uei"]
df.loc[no_parent_uei, "parent_uei"] = df.loc[no_parent_uei, "recipient_uei"]

# legal suffixes to strip from the end of a name
suffixes = ["INC", "INCORPORATED", "LLC", "L L C", "LLP", "LP", "CORP", "CORPORATION", "CO",
            "COMPANY", "LTD", "LIMITED", "PLC", "PUBLIC LIMITED COMPANY", "HOLDINGS", "HOLDING"]


def clean_name(name):
    # uppercase, drop punctuation, then strip legal suffixes until none are left
    s = str(name).upper()
    s = s.replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    changed = True
    while changed:
        changed = False
        for suf in suffixes:
            if s.endswith(" " + suf):
                s = s[: -len(suf) - 1].strip()
                changed = True
    return s


# hand-checked aliases: subsidiaries or name variants -> one parent
# (applied after clean_name, so keys are already cleaned)
aliases = {
    "VERIZON MARYLAND": "VERIZON COMMUNICATIONS",
    "VERIZON VIRGINIA": "VERIZON COMMUNICATIONS",
    "HPI FEDERAL": "HP",
    "SATCOM DIRECT GOVERNMENT": "SATCOM DIRECT",
    "GENERAL DYNAMICS INFORMATION TECHNOLOGY": "GENERAL DYNAMICS",
    "GENERAL DYNAMICS MISSION SYSTEMS": "GENERAL DYNAMICS",
    "CACI ISS": "CACI INTERNATIONAL",
    "CACI NSS": "CACI INTERNATIONAL",
    "CACI ENTERPRISE SOLUTIONS": "CACI INTERNATIONAL",
    "DELOITTE TOUCHE TOHMATSU": "DELOITTE",
    "DELOITTE CONSULTING": "DELOITTE",
    "DELOITTE FINANCIAL ADVISORY SERVICES": "DELOITTE",
    "PERATON ENTERPRISE SOLUTIONS": "PERATON",
    "PERATON TECHNOLOGY SERVICES": "PERATON",
    "MANTECH ADVANCED SYSTEMS INTERNATIONAL": "MANTECH INTERNATIONAL",
}

# clean each distinct name once, then map back (much faster than 383k calls)
names = pd.Series(df["parent_raw"].unique())
cleaned = names.apply(clean_name)
name_map = pd.Series(cleaned.values, index=names.values)
df["vendor"] = df["parent_raw"].map(name_map)
alias_hit = df["vendor"].isin(list(aliases.keys()))
df.loc[alias_hit, "vendor"] = df.loc[alias_hit, "vendor"].map(aliases)

name_changed = df["vendor"] != df["parent_raw"].str.upper().str.strip()
note("vendor name standardized (suffix, punctuation)", "fix", name_changed.sum() - alias_hit.sum())
note("vendor mapped to parent via alias list", "fix", alias_hit.sum())
note("distinct parent names before", "info", df["parent_raw"].nunique())
note("distinct vendors after", "info", df["vendor"].nunique())

# rule 6: place of performance state
territories = ["PR", "GU", "VI", "AS", "MP"]
overseas = ["AE", "AP", "AA"]  # military mail codes, not states
df["state"] = df["primary_place_of_performance_state_code"].str.strip().str.upper()
df["state_type"] = "state"
df.loc[df["state"] == "DC", "state_type"] = "dc"
df.loc[df["state"].isin(territories), "state_type"] = "territory"
df.loc[df["state"].isin(overseas), "state_type"] = "overseas military"
no_state = df["state"].isna()
df.loc[no_state, "state"] = "UNK"
df.loc[no_state, "state_type"] = "unknown"
note("place of performance state missing", "flag", no_state.sum())
note("territory place of performance", "flag", df["state"].isin(territories).sum())
note("overseas military code (AE/AP)", "flag", df["state"].isin(overseas).sum())

# rule 7: sector, defense vs civilian
df["sector"] = "Civilian"
df.loc[df["awarding_agency_name"] == "Department of Defense", "sector"] = "Defense"

# rule 8: fill blank text categories so they group cleanly
for col in ["type_of_contract_pricing", "extent_competed", "product_or_service_code", "awarding_sub_agency_name"]:
    blank = df[col].isna()
    note(col + " blank", "fill", blank.sum())
    df.loc[blank, col] = "UNKNOWN"
df["offers"] = pd.to_numeric(df["number_of_offers_received"], errors="coerce")
note("number_of_offers_received blank (left blank)", "flag", df["offers"].isna().sum())

# rule 9: DoD publishes contract data ~90 days late, so its last fiscal quarter is incomplete
df["partial_period"] = (df["sector"] == "Defense") & (df["fy_quarter"] == "FY2026 Q4")
note("DoD FY2026 Q4 (publication lag, incomplete)", "flag", df["partial_period"].sum())

# keep the columns later steps need, with simple names
out = pd.DataFrame()
out["txn_key"] = df["contract_transaction_unique_key"]
out["award_key"] = df["contract_award_unique_key"]
out["piid"] = df["award_id_piid"]
out["mod_number"] = df["modification_number"]
out["action_date"] = df["action_date"].dt.strftime("%Y-%m-%d")
out["fiscal_year"] = df["fiscal_year"]
out["fiscal_quarter"] = df["fiscal_quarter"]
out["fy_quarter"] = df["fy_quarter"]
out["action_type"] = df["action_type"]
out["is_new_award"] = df["is_new_award"]
out["obligation"] = df["obligation"]
out["base_and_all_options_value"] = df["base_and_all_options_value"]
out["is_deobligation"] = df["is_deobligation"]
out["is_zero_dollar"] = df["is_zero_dollar"]
out["agency_code"] = df["awarding_agency_code"]
out["agency"] = df["awarding_agency_name"]
out["sub_agency"] = df["awarding_sub_agency_name"]
out["sector"] = df["sector"]
out["recipient_uei"] = df["recipient_uei"]
out["recipient_name"] = df["recipient_name"]
out["parent_uei"] = df["parent_uei"]
out["vendor"] = df["vendor"]
out["state"] = df["state"]
out["state_type"] = df["state_type"]
out["naics_code"] = df["naics_code"]
out["naics_description"] = df["naics_description"]
out["psc_code"] = df["product_or_service_code"]
out["award_type"] = df["award_type"]
out["pricing_type"] = df["type_of_contract_pricing"]
out["extent_competed"] = df["extent_competed"]
out["offers"] = df["offers"]
out["partial_period"] = df["partial_period"]

out_path = os.path.join(clean_dir, "transactions.csv.gz")
out.to_csv(out_path, index=False, compression="gzip")
note("rows written to clean file", "info", len(out))

log = pd.DataFrame(quality, columns=["rule", "action", "rows"])
log.to_csv(os.path.join(clean_dir, "quality_log.csv"), index=False)

# quick summary for the console
print()
print("total obligations ($B):", round(out["obligation"].sum() / 1e9, 2))
print(out.groupby(["sector", "fiscal_year"])["obligation"].sum().div(1e9).round(2).unstack())
print()
print("top 10 vendors ($B):")
print(out.groupby("vendor")["obligation"].sum().sort_values(ascending=False).head(10).div(1e9).round(2))
