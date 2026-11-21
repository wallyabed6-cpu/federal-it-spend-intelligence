# 01_ingest.py
# pulls federal IT services contract transactions from the USAspending API.
#
# how it works:
#   1. asks the API how many transactions match each agency + fiscal year
#   2. asks the API to build a CSV download for each agency + fiscal year
#   3. waits for each file to finish, then saves the zip to data/raw/
#
# run:  python scripts/01_ingest.py          (counts + downloads)
#       python scripts/01_ingest.py count    (counts only, no downloads)
#
# API docs: https://api.usaspending.gov/docs/endpoints
#   POST /api/v2/search/spending_by_transaction_count/
#   POST /api/v2/download/transactions/
#   GET  /api/v2/download/status?file_name=...

import os
import sys
import time
import requests
import pandas as pd

base = "https://api.usaspending.gov"
raw_dir = os.path.join("data", "raw")
log_path = os.path.join(raw_dir, "ingest_log.txt")

# scope
naics = ["541511", "541512", "541519", "518210"]
contract_types = ["A", "B", "C", "D"]  # BPA call, purchase order, delivery order, definitive contract
years = [2022, 2023, 2024, 2025, 2026]
agencies = [
    "Department of Defense",
    "Department of Homeland Security",
    "Department of Veterans Affairs",
    "Department of Health and Human Services",
    "Department of the Treasury",
    "General Services Administration",
]

# only the columns we need (keeps files small)
columns = [
    "contract_transaction_unique_key",
    "contract_award_unique_key",
    "award_id_piid",
    "modification_number",
    "action_date",
    "action_date_fiscal_year",
    "action_type",
    "federal_action_obligation",
    "base_and_all_options_value",
    "awarding_agency_code",
    "awarding_agency_name",
    "awarding_sub_agency_name",
    "recipient_uei",
    "recipient_name",
    "recipient_parent_uei",
    "recipient_parent_name",
    "primary_place_of_performance_state_code",
    "naics_code",
    "naics_description",
    "product_or_service_code",
    "award_type",
    "type_of_contract_pricing",
    "extent_competed",
    "number_of_offers_received",
]

wait_between_calls = 2   # seconds between API calls
wait_for_file = 15       # seconds between status checks


def log(msg):
    # print and append to the log file
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = stamp + "  " + msg
    print(line)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def make_filters(agency, year):
    # fiscal year runs oct 1 to sep 30
    start = str(year - 1) + "-10-01"
    end = str(year) + "-09-30"
    filters = {}
    filters["award_type_codes"] = contract_types
    filters["naics_codes"] = {"require": naics}
    filters["agencies"] = [{"type": "awarding", "tier": "toptier", "name": agency}]
    filters["time_period"] = [{"start_date": start, "end_date": end}]
    return filters


def post(url, body):
    # post with simple retries for rate limits and server errors
    for attempt in range(5):
        r = requests.post(url, json=body, timeout=120)
        if r.status_code == 200:
            return r.json()
        if r.status_code == 429 or r.status_code >= 500:
            pause = 30 * (attempt + 1)
            log("got " + str(r.status_code) + ", waiting " + str(pause) + "s and retrying")
            time.sleep(pause)
            continue
        # a 4xx other than 429 means the request itself is wrong
        log("error " + str(r.status_code) + ": " + r.text[:500])
        r.raise_for_status()
    raise RuntimeError("gave up after 5 tries: " + url)


def get_count(agency, year):
    # number of contract transactions that match
    url = base + "/api/v2/search/spending_by_transaction_count/"
    body = {"filters": make_filters(agency, year)}
    data = post(url, body)
    return data["results"]["contracts"]


def short_name(agency):
    # "Department of Homeland Security" -> "homeland_security"
    name = agency.lower()
    name = name.replace("department of the ", "")
    name = name.replace("department of ", "")
    name = name.replace(" ", "_")
    return name


def download(agency, year):
    # ask the API to build the file, wait for it, then save the zip
    out_path = os.path.join(raw_dir, short_name(agency) + "_fy" + str(year) + ".zip")
    if os.path.exists(out_path):
        log("already have " + out_path + ", skipping")
        return

    url = base + "/api/v2/download/transactions/"
    body = {"filters": make_filters(agency, year), "columns": columns, "file_format": "csv"}
    job = post(url, body)
    file_name = job["file_name"]
    log("requested " + file_name)

    # poll the status endpoint until the file is ready
    status_url = base + "/api/v2/download/status"
    while True:
        time.sleep(wait_for_file)
        r = requests.get(status_url, params={"file_name": file_name}, timeout=60)
        if r.status_code != 200:
            log("status check got " + str(r.status_code) + ", trying again")
            continue
        s = r.json()
        if s["status"] == "finished":
            log("finished: " + str(s["total_rows"]) + " rows, " + str(s["seconds_elapsed"]) + "s")
            file_url = s["file_url"]
            break
        if s["status"] == "failed":
            log("download failed: " + str(s["message"]))
            return
        log("still " + s["status"] + " (" + str(s["seconds_elapsed"]) + "s)")

    # file_url is usually a full link, but handle a relative one too
    if file_url.startswith("/"):
        file_url = base + file_url

    # stream the zip to disk
    tmp_path = out_path + ".part"
    with requests.get(file_url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(tmp_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
    os.replace(tmp_path, out_path)
    size_mb = os.path.getsize(out_path) / 1024 / 1024
    log("saved " + out_path + " (" + str(round(size_mb, 1)) + " MB)")


# main
os.makedirs(raw_dir, exist_ok=True)
count_only = len(sys.argv) > 1 and sys.argv[1] == "count"
log("starting ingest, count_only=" + str(count_only))

# step 1: row counts for every agency and year
rows = []
for agency in agencies:
    for year in years:
        n = get_count(agency, year)
        log(agency + " FY" + str(year) + ": " + str(n) + " transactions")
        rows.append([agency, year, n])
        time.sleep(wait_between_calls)

counts = pd.DataFrame(rows, columns=["agency", "fiscal_year", "transactions"])
counts.to_csv(os.path.join(raw_dir, "row_counts.csv"), index=False)

# show a small summary table
pivot = counts.pivot(index="agency", columns="fiscal_year", values="transactions")
print()
print(pivot)
print()
log("total transactions in scope: " + str(counts["transactions"].sum()))

if count_only:
    log("count only, stopping here")
    sys.exit(0)

# step 2: one download per agency and year (each stays under the 500k row cap)
for agency in agencies:
    for year in years:
        download(agency, year)
        time.sleep(wait_between_calls)

log("ingest done")
