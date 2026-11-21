# Model Validation

What could make each model misleading, what was checked, and what is still a limitation.
All numbers come from `scripts/05_anomaly.py`, `scripts/06_forecast.py`, and `scripts/validate_models.py`.

---

## 1. Anomaly detection (Isolation Forest)

**What it does:** scores 198,411 contract actions that add $10K or more, using four features:
- action size
- size vs. the vendor's median action
- size vs. the median at the same agency and NAICS code
- size vs. everything obligated on the award before it

It flags the 1% most unusual (1,985 rows across 1,309 awards).

**The honest framing:** there are no labels. Nobody has marked which federal contract actions are "really" anomalous, so precision and recall can't be measured. The output is a **review queue**: a ranked list of actions worth a second look, each with a reason a person can check. It is not a list of fraud or errors.

### Problems found during development (and fixed)

Each of these showed up in an earlier run. Each would have made the output misleading.

| Problem | Symptom | Fix |
|---|---|---|
| Deobligations dominated | 64% of flags were negative amounts. They're rare, so the model separates them easily, but "money taken back" isn't unusual *spending*. | Score only actions that add money. |
| Awards that started before FY2022 | A routine modification looked like "109x everything obligated before it", because the award's earlier history isn't in our 5-year window. | Award-history feature only used for awards whose original award (mod 0) is inside the window; others get a neutral value. |
| Isolation Forest flags both tails | Half the flags were *tiny* actions with no specific reason. A $3 order is statistically odd but not a risk. | Every feature is floored at its median, so only "bigger than typical" can look unusual. |
| Micro-purchases distorted "typical" | Leidos had 37% of all flags. Its 38,882 small Navy orders set its median action at $5K, so every normal program funding action looked like 3,000x. | Actions under $10K (the FAR micro-purchase threshold) are not scored. They're 23% of rows but 0.06% of dollars. |

### Checks on the final model

| Check | Result | What it means |
|---|---|---|
| Different random seeds (1, 7, 99) | Flagged-set overlap 0.78–0.88 (Jaccard); top-100 overlap 86 of 100 | Strongest flags are stable. Rows near the cutoff swap in and out, so treat rank ~1,500–2,000 as borderline. |
| Cutoff choice | 0.5% → 993 rows, 1% → 1,985, 2% → 3,969 | 1% is a workload choice, not a statistical one. The ranking is what matters. |
| Year-end spending | 17.8% of flags in September vs. 18.6% of all scored rows | The September rush is *not* inflating flags. Expected, because the peer and vendor comparisons cover all months. |
| Rules vs. model | 98.5% of flags have at least one specific plain-English reason; all 113 actions over $100M are flagged | The "why flagged" column explains almost every flag. 29 rows get only the generic reason. |
| Small vendors (median includes the scored row) | Flag rate 0.25% for vendors with 1–4 actions, 0.62% for 5–49, 1.13% for 50+ | A vendor's median includes the row being scored, so very small vendors look "typical of themselves" and are **under-flagged**. A one-time $50M award to a brand-new vendor gets caught by the peer and size features, not the vendor feature. |
| Flag concentration by vendor | Leidos: 16.5% of flags vs. 4.5% of dollars. HP: 2.9% vs. 0.2%. | **Still a limitation.** Vendors that mix many small orders with a few big programs have a low "typical" action, so their big actions stand out. The fix would be comparing within the same contract vehicle. Not done, to keep the model simple. |

### Is there data leakage?

Leakage matters most for supervised models predicting a future outcome. This model is unsupervised and descriptive, so the question becomes *"does each row get compared to information it shouldn't have?"*
- **Award history uses only earlier actions** (a running sum that excludes the current row). No future information.
- **Vendor and peer medians use the full 5 years, including later actions and the row itself.** That's fine for a look-back review, but this exact model could not be run "live" on day one of an award. A production version would use medians from prior periods only.

---

## 2. Spending forecast (Holt-Winters / ETS)

**What it does:**
- **Data:** quarterly net obligations, defense vs. civilian, FY2022 Q1 – FY2026 Q3 (19 quarters).
- **Model:** damped additive trend, multiplicative seasonality.
- **Output:** next 4 quarters with 80% prediction intervals.
- **Baseline:** "same quarter last year" (seasonal naive).

### Headline backtest (as required: last 4 known quarters held out)

| | Model MAPE | Seasonal naive MAPE |
|---|---|---|
| Defense | 12.3% | 13.6% |
| Civilian | 9.8% | 16.0% |

Bonus out-of-sample check: civilian FY2026 Q4 is complete in the data but was never shown to the model. Forecast $13.56B, actual $15.04B (−9.8%).

### Rolling-origin backtest (the more honest number)

One 4-quarter test can be luck. The model was refit from 8 different starting points (8 to 15 training quarters), each tested on the 4 quarters that followed:

| | Windows | Model avg MAPE | Naive avg MAPE | Model wins | 80% interval coverage |
|---|---|---|---|---|---|
| Defense | 8 | **8.7%** | 12.3% | 8 of 8 | 69% |
| Civilian | 8 | **12.1%** | 12.8% | 6 of 8 | 56% |

**How to say it in an interview:**
- For defense, the model reliably beats "same as last year".
- For civilian, it's roughly a tie on average and loses badly in one window (31.4% vs. 16.2%), so on the civilian side it doesn't add much over the simple baseline.

### What could make it misleading

| Risk | What was checked | Finding |
|---|---|---|
| **Data leakage** | Holdout quarters never used in fitting; model form chosen before testing, not by comparing test scores | Clean. One caveat: the year-end spike was seen during data exploration, which shaped the choice of seasonal model. That's domain knowledge, not tuning on the test set. |
| **Incomplete last quarter** | DoD FY2026 Q4 has $1.75B vs. the usual $7–9B (90-day publication lag) | Both series cut at FY2026 Q3. Including it would have made the forecast and the backtest look like a defense spending collapse. |
| **Small sample** | 19 quarters total, 15 to train the headline model | All three smoothing parameters were fit to 0, so the model is effectively a **fixed trend plus a fixed seasonal pattern**. It doesn't adapt to recent quarters. Mean in-sample error is ~$0, so there's no overall bias, but the model can't react to a change in direction. |
| **Year-end spike** | Q4 / Q1 ratio by year: defense 2.1–2.6x, civilian 3.0–3.6x | Multiplicative seasonality handles it. The civilian spike is shrinking (3.6x → 3.0x), which a fixed seasonal pattern will slowly get wrong. |
| **Structural breaks** | Worst window: civilian, trained through FY2025 Q2 | Civilian FY2025 Q3 fell 23% vs. the year before ($6.45B vs. $8.41B). The model kept the old upward trend and missed. The timing matches the 2025 review and cancellation of consulting and IT contracts at civilian agencies, but this project doesn't test that cause. |
| **Intervals too narrow** | Share of actual quarters inside the 80% interval | 69% (defense) and 56% (civilian) instead of ~80%. With smoothing at 0, the model underestimates its own uncertainty. **Read the intervals as optimistic.** Roughly doubling the width would match observed misses. |
| **Nominal dollars** | Not adjusted for inflation | Some of the upward trend is price growth, not more IT work. |
| **Net obligations** | Deobligations are included | A big deobligation in one quarter lowers that quarter. This is real, but it adds noise a forecaster can't predict. |

### Bottom line

Use the forecast for **direction and scale** ("civilian Q4 will likely land around $13–15B, about 3x Q1"), not for a precise budget number. The most defensible claim is the defense result: 8 of 8 rolling windows beat the naive baseline, averaging 8.7% error.
