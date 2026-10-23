# Statistical Price & Spread Intelligence Report: Karnataka

## 1. Analysis Scope & Data Integrity
- **State Analyzed:** Karnataka
- **Primary Commodity Case Study:** Onion (₹/kg)
- **Reporting Period:** 2015-01-06 to 2023-11-03
- **Total Matched Records (6 Basket Commodities):** 11,268
- **Matched observation period:** The period reflects records available after the retail/wholesale inner join.
- **Target Metric:** Normalized Indicative Price Spreads & Relative Volatility ($CV$)

## 2. Verified Commodity Volatility Rankings
| Commodity | Normalized Unit | Mean Price | Std Dev | Min Price | Max Price | Obs | CV (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tomato** | ₹/kg | ₹25.10 | ₹16.20 | ₹8.75 | ₹119.97 | 1,882 | **64.56%** |
| **Onion** | ₹/kg | ₹28.31 | ₹13.13 | ₹11.25 | ₹112.50 | 1,882 | **46.36%** |
| **Potato** | ₹/kg | ₹26.61 | ₹5.60 | ₹17.67 | ₹54.00 | 1,882 | **21.06%** |
| **Rice** | ₹/kg | ₹44.29 | ₹5.31 | ₹29.00 | ₹56.53 | 1,882 | **11.99%** |
| **Milk** | ₹/litre | ₹39.46 | ₹4.59 | ₹29.00 | ₹50.77 | 1,858 | **11.64%** |
| **Wheat** | ₹/kg | ₹34.01 | ₹3.23 | ₹28.00 | ₹43.17 | 1,882 | **9.51%** |

## 3. Statistical Price-Change Alert Summary
- **Selected Case Study:** Onion
- **Methodology:** Calendar-aware 7-day velocity ($\Delta P_{7d}$) vs. 30-day prior rolling baseline
- **Z-Score Threshold:** $|Z| \ge 2.5$
- **Minimum Velocity Threshold:** $|\Delta P_{7d}| \ge ₹5.00$ per kg
- **Total Statistical Alerts Flagged:** **49 days**

## 4. Analytical Distinctions & Limitations
- **Indicative Price Spread vs. Net Profit:** Spread equals `Retail Price - Wholesale Price` after unit normalization. It is a reported-price difference, NOT a direct estimate of retailer profit or an observed intermediary margin. Transport, storage, wastage, taxes and timing differences are not captured.
- **Matched-observation limitation:** Volatility and alert calculations use records retained by the retail/wholesale inner join. Dates without a matched record are unavailable to the current analysis; this may affect sample counts and alert detection.
- **Statistical Alerts vs. Supply Shocks:** Detected events represent statistically unusual price changes; they do not establish the cause. Verify with independent harvest, weather or transport evidence before attributing root cause.
