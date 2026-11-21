# Data Quality

Rules applied by `scripts/02_clean.py`. Row counts come from `data/clean/quality_log.csv`, which the script rewrites on every run.

**Input:** 383,385 contract transactions (30 files: 6 agencies x FY2022–FY2026, NAICS 541511/541512/541519/518210, award types A/B/C/D).
**Output:** 383,385 rows in `data/clean/transactions.csv.gz`. No rows were dropped; problems are flagged instead so totals still tie back to USAspending.

## Ingest check (step 1)

| Check | Result |
|---|---|
| Rows the count endpoint reported | 386,576 |
| Rows in the downloaded files | 383,385 (99.2%) |
| Gap | 3,191 rows, almost all DoD (1–2% per year). Civilian agencies match within 1 row per file. |

The gap is between two USAspending endpoints (`spending_by_transaction_count` vs. `download/transactions`), not something our code drops. The download is the source of truth for this project. Not resolved; noted as a limitation.

## Cleaning rules

| # | Rule | Action | Rows affected |
|---|---|---|---|
| 1 | Duplicate `contract_transaction_unique_key` | drop | 0 |
| 2 | `action_date` missing or unparseable | drop | 0 |
| 2 | Fiscal year derived from date (Oct–Dec = Q1 of next FY) differs from the API's value | flag | 0 |
| 3 | Obligation missing or not a number | drop | 0 |
| 3 | Negative obligation (deobligation: money taken back) | flag, keep | 37,481 |
| 3 | Zero-dollar action (paperwork only, e.g. admin changes, closeouts) | flag, keep | 89,609 |
| 4 | Blank `action_type`. Every one is modification `0`, the original award. | fill "NEW AWARD" | 118,725 |
| 5 | Parent company name missing | fill with recipient name | 41 |
| 5 | Vendor name standardized: uppercase, punctuation removed, legal suffixes stripped (INC, LLC, CORP, HOLDINGS, ...) | fix | 347,575 |
| 5 | Vendor mapped to parent via hand-checked alias list (e.g. VERIZON MARYLAND → VERIZON COMMUNICATIONS, HPI FEDERAL → HP, DELOITTE CONSULTING → DELOITTE) | fix | 26,759 |
| 6 | Place of performance state missing | fill "UNK", flag | 4,580 |
| 6 | Territory (PR, GU, VI, AS, MP) | flag, keep | 422 |
| 6 | Overseas military mail code (AE, AP) | flag, keep | 38 |
| 7 | Sector assigned: DoD = Defense, all others = Civilian | derive | all rows |
| 8 | Blank `type_of_contract_pricing` / `extent_competed` / `product_or_service_code` | fill "UNKNOWN" | 20 / 30 / 4 |
| 8 | Blank `number_of_offers_received` (mostly orders where it isn't reported) | leave blank, flag | 129,783 |
| 9 | DoD FY2026 Q4 (see below) | flag `partial_period` | 3,392 |

Vendor standardization cut distinct parent names from 8,901 to 8,396.

## Known issues to keep in mind

**DoD FY2026 Q4 is incomplete.** DoD publishes contract data about 90 days late. DoD transactions per month drop from ~4,000 to 62 in August 2026 and 0 in September 2026. DoD FY2026 Q4 shows $1.75B against $7–9B in the same quarter of prior years. Civilian FY2026 is complete (September 2026 has the usual year-end spike).
- The forecast ends **both** series at FY2026 Q3, so defense and civilian are tested on the same quarters.
- FY2026 defense totals are labeled "partial year" anywhere they appear.

**Year-end spending spike.** Q4 (Jul–Sep) is roughly 2–3.5x Q1 in every year for both sectors. This is real federal behavior ("use it or lose it"), not a data error. The forecast must model seasonality, and anomaly detection should not treat September awards as unusual just because they are large.

**Parent company coverage.** Parent names come from SAM.gov via USAspending, as of each transaction. Limits:
- Private equity owners can appear as the parent. `VERITAS CAPITAL FUND MANAGEMENT` ($4.9B) rolls up several portfolio companies, while `PERATON` (a Veritas company) also appears on its own. These are left as reported, not merged by hand.
- Acquisitions are not back-dated. A company bought mid-period shows under its old parent before the deal.
- The alias list only covers name variants found among the larger vendors. Smaller vendors may still have duplicates.

**Deobligations.** Negative amounts are kept so totals match USAspending. A large deobligation can make a vendor's or quarter's net spend look small. Anomaly detection looks at both positive and negative outliers.
