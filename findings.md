# Findings: Federal IT Services Spending, FY2022–FY2026

**Scope:** $262.9B in net contract obligations. DoD plus DHS, VA, HHS, Treasury and GSA; IT services NAICS codes 541511, 541512, 541519 and 518210; 383,385 transactions; 8,394 parent vendors. Source: USAspending.gov.

## Executive summary

Federal IT services money looks competitive from the top and concentrated from the bottom. Every agency's vendor base is broad, but six bureaus rely on a single contractor for half or more of their IT spend. Spending clusters in the Washington region and spikes at fiscal year-end. Both patterns are predictable enough to plan around.

## Key findings

**1. Civilian agencies, not DoD, are the bigger IT services buyer in this scope: 60% of the total.**
Civilian agencies obligated **$157.8B** against DoD's **$105.1B** over five years. DoD is still the largest single buyer, but VA, HHS, GSA, DHS and Treasury together outspend it. Combined spending has been roughly flat since FY2023, at $52–55B a year.

**2. Agency-wide markets are unconcentrated, but six bureaus depend heavily on one vendor.**
Every agency scores under 1,000 HHI (DoD 127 to GSA 627), because each buys from 700–4,500 vendors. One level down, six bureaus with $250M+ of IT spend are *highly concentrated* (HHI over 1,800):

| Bureau | Top vendor | Top vendor share | HHI |
|---|---|---|---|
| Treasury Departmental Offices | Lancer Information Solutions | 77% | 5,943 |
| Missile Defense Agency | Lockheed Martin | 75% | 5,904 |
| DARPA | Securigence | 70% | 5,086 |
| U.S. Mint | PFSweb (top 4 hold 98%) | 49% | 4,113 |
| Agency for Healthcare Research and Quality | Westat | 50% | 2,885 |
| Defense Threat Reduction Agency | Booz Allen Hamilton | 48% | 2,783 |

**3. At agency level, three single-vendor positions stand out.**
**Oracle holds 17.2% of VA's** IT services spend (the electronic health record program, which also puts Kansas 7th among states at $7.2B). **Booz Allen holds 17.1% of GSA and 13.9% of VA**, and **FCN holds 11.5% of Treasury**. The top 5 vendors overall (Booz Allen, General Dynamics, Leidos, CACI, Deloitte) hold **21.5%** of all dollars, and the top 20 hold **42.2%**.

**4. Spending is geographically concentrated and timed to year-end.**
Virginia, Maryland and DC receive **64%** of all dollars by place of performance. Q4 (July–September) spend runs **2.1–2.6× Q1 for defense and 3.0–3.6× for civilian** agencies in every year. The civilian spike has eased slightly, from 3.6× in FY2022 to 3.0× in FY2025.

**5. 1,985 transactions (the top 1%) stand out as unusual, and 113 of them are single actions over $100M.**
The flagged actions total $61.0B. They're large by design: the model looks for actions that are big *relative to the vendor, agency and award*, so this is a review queue rather than a measure of waste. A typical flag reads "160× the vendor's median action; 125× everything obligated on this award before it."

**Forecast:** the model expects **$25.9B defense** (80% range $22.9–29.1B) and **$32.5B civilian** ($28.9–35.9B) over the next four quarters (FY2026 Q4 – FY2027 Q3). It beat a "same as last year" baseline in 8 of 8 rolling tests for defense, averaging 8.7% error. For civilian it was roughly a tie (12.1% vs 12.8%), and its ranges are too narrow, so treat them as optimistic. See [`validation.md`](validation.md).

## Recommendations

**1. Run vendor-dependence reviews at the six highly concentrated bureaus.**
For each bureau, confirm whether the dominant vendor is there because of a legitimate sole-source need (a proprietary system, classified work) or because the work has drifted. Then set a transition or second-source plan for the next recompete. Start with Treasury Departmental Offices and the Missile Defense Agency, the two highest HHIs. *Why it matters:* a single vendor holding 75%+ of a bureau's IT work is a continuity risk and weakens the government's negotiating position.

**2. Move civilian obligations earlier in the year.**
Civilian Q4 spend is about 3× Q1. Agencies could set quarterly obligation targets (for example, 50% obligated by the end of Q2) and track them on a dashboard like this one. Year-end rushes are when pricing and requirement reviews get compressed.

**3. Use the anomaly ranking as a monthly review queue.**
Each month, have contracting officers review the top-ranked flagged actions, starting with single actions over $100M and actions many times larger than the award's prior history. Record the outcome (expected, needs follow-up), so the model can later be tuned against real labels.

## For contractors (business development view)

- **Recompete windows at concentrated bureaus** (finding 2) are openings for challengers, and incumbents there should defend early.
- **DHS, HHS and DoD have the most fragmented markets** (HHI 127–171), where a new entrant's path is widest.
- **Plan proposal capacity for Q3–Q4**, when 40–50% of each year's dollars are obligated.

## Caveats

- Covers **awarding** agency. GSA buys IT on behalf of other agencies, so some GSA spend serves DoD and others.
- **DoD FY2026 Q4 is incomplete** (publication lag). FY2026 defense totals understate the year.
- Parent companies come from SAM.gov as of each transaction. Private-equity owners (e.g. Veritas Capital) can appear as the parent, and only one acquisition (Oracle–Cerner) was merged by hand.
- Dollars are **nominal**, not adjusted for inflation.
- Details: [`data_quality.md`](data_quality.md) and [`validation.md`](validation.md).
