-- 00_schema.sql
-- star schema for federal IT contract spending.
-- one fact table (one row per contract transaction) surrounded by five dimensions.
-- run by scripts/03_load_db.py, which drops and rebuilds everything each time.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_awards;
DROP TABLE IF EXISTS dim_agency;
DROP TABLE IF EXISTS dim_vendor;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_naics;
DROP TABLE IF EXISTS dim_state;

-- one row per awarding sub-agency (e.g. Department of the Army), rolled up to its parent agency
CREATE TABLE dim_agency (
    agency_key   INTEGER PRIMARY KEY,
    agency_code  TEXT NOT NULL,      -- toptier code, e.g. 097 = DoD
    agency       TEXT NOT NULL,      -- e.g. Department of Defense
    sub_agency   TEXT NOT NULL,      -- e.g. Department of the Army
    sector       TEXT NOT NULL       -- Defense or Civilian
);

-- one row per standardized parent company (see data_quality.md, rule 5)
CREATE TABLE dim_vendor (
    vendor_key     INTEGER PRIMARY KEY,
    vendor         TEXT NOT NULL UNIQUE,
    parent_uei     TEXT,             -- most common parent UEI for this name
    n_recipients   INTEGER           -- distinct recipient UEIs rolled into this parent
);

-- one row per calendar day, with federal fiscal calendar columns
-- runs through FY2027 so forecast quarters have dates to join to
CREATE TABLE dim_date (
    date_key        INTEGER PRIMARY KEY,   -- YYYYMMDD
    date            TEXT NOT NULL,         -- YYYY-MM-DD
    calendar_year   INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    month_name      TEXT NOT NULL,
    fiscal_year     INTEGER NOT NULL,      -- Oct 1 starts the next fiscal year
    fiscal_quarter  INTEGER NOT NULL,      -- Q1 = Oct-Dec
    fiscal_month    INTEGER NOT NULL,      -- 1 = October
    fy_quarter      TEXT NOT NULL          -- e.g. FY2024 Q1
);

-- one row per NAICS industry code in scope
CREATE TABLE dim_naics (
    naics_code         TEXT PRIMARY KEY,
    naics_description  TEXT NOT NULL
);

-- one row per place-of-performance code, including territories and UNK
CREATE TABLE dim_state (
    state_code  TEXT PRIMARY KEY,
    state_name  TEXT NOT NULL,
    state_type  TEXT NOT NULL      -- state, dc, territory, overseas military, unknown
);

-- one row per contract transaction (an award or a modification to it)
CREATE TABLE fact_awards (
    txn_key                     TEXT PRIMARY KEY,
    award_key                   TEXT NOT NULL,     -- groups an award with its modifications
    piid                        TEXT,
    mod_number                  TEXT,
    date_key                    INTEGER NOT NULL REFERENCES dim_date(date_key),
    agency_key                  INTEGER NOT NULL REFERENCES dim_agency(agency_key),
    vendor_key                  INTEGER NOT NULL REFERENCES dim_vendor(vendor_key),
    naics_code                  TEXT NOT NULL REFERENCES dim_naics(naics_code),
    state_code                  TEXT NOT NULL REFERENCES dim_state(state_code),
    recipient_uei               TEXT,
    recipient_name              TEXT,
    action_type                 TEXT,
    award_type                  TEXT,
    pricing_type                TEXT,
    extent_competed             TEXT,
    psc_code                    TEXT,
    offers                      INTEGER,
    obligation                  REAL NOT NULL,     -- federal_action_obligation, dollars
    base_and_all_options_value  REAL,
    is_new_award                INTEGER NOT NULL,  -- 1 = modification 0
    is_deobligation             INTEGER NOT NULL,
    is_zero_dollar              INTEGER NOT NULL,
    partial_period              INTEGER NOT NULL   -- 1 = DoD FY2026 Q4, incomplete
);

-- indexes on the join and filter columns used in sql/ queries
CREATE INDEX ix_fact_date   ON fact_awards(date_key);
CREATE INDEX ix_fact_agency ON fact_awards(agency_key);
CREATE INDEX ix_fact_vendor ON fact_awards(vendor_key);
CREATE INDEX ix_fact_state  ON fact_awards(state_code);
CREATE INDEX ix_fact_award  ON fact_awards(award_key);
