# Statistical Price & Spread Intelligence Report: Maharashtra

## 1. Analysis Scope & Data Integrity
- **State Analyzed:** Maharashtra
- **Primary Commodity Case Study:** Onion (₹/kg)
- **Reporting Period:** 2015-01-01 to 2023-11-03
- **Total Matched Records (6 Basket Commodities):** 17,311
- **Matched observation period:** The period reflects records available after the retail/wholesale inner join.
- **Target Metric:** Normalized Indicative Price Spreads & Relative Volatility ($CV$)

## 2. Verified Commodity Volatility Rankings
| Commodity | Normalized Unit | Mean Price | Std Dev | Min Price | Max Price | Obs | CV (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Onion** | ₹/kg | ₹26.91 | ₹12.16 | ₹12.00 | ₹92.00 | 2,885 | **45.20%** |
| **Tomato** | ₹/kg | ₹29.87 | ₹12.89 | ₹11.25 | ₹132.26 | 2,885 | **43.15%** |
| **Potato** | ₹/kg | ₹24.14 | ₹6.33 | ₹12.50 | ₹46.75 | 2,885 | **26.24%** |
| **Milk** | ₹/litre | ₹42.49 | ₹5.86 | ₹34.00 | ₹59.35 | 2,885 | **13.78%** |
| **Rice** | ₹/kg | ₹36.39 | ₹4.47 | ₹26.00 | ₹48.89 | 2,883 | **12.28%** |
| **Wheat** | ₹/kg | ₹30.68 | ₹3.75 | ₹23.50 | ₹40.12 | 2,888 | **12.21%** |

## 3. Statistical Price-Change Alert Summary
- **Selected Case Study:** Onion
- **Methodology:** Calendar-aware 7-day velocity ($\Delta P_{7d}$) vs. 30-day prior rolling baseline
- **Z-Score Threshold:** $|Z| \ge 2.5$
- **Minimum Velocity Threshold:** $|\Delta P_{7d}| \ge ₹5.00$ per kg
- **Total Statistical Alerts Flagged:** **73 days**

## 4. Analytical Distinctions & Limitations
- **Indicative Price Spread vs. Net Profit:** Spread equals `Retail Price - Wholesale Price` after unit normalization. It is a reported-price difference, NOT a direct estimate of retailer profit or an observed intermediary margin. Transport, storage, wastage, taxes and timing differences are not captured.
- **Matched-observation limitation:** Volatility and alert calculations use records retained by the retail/wholesale inner join. Dates without a matched record are unavailable to the current analysis; this may affect sample counts and alert detection.
- **Statistical Alerts vs. Supply Shocks:** Detected events represent statistically unusual price changes; they do not establish the cause. Verify with independent harvest, weather or transport evidence before attributing root cause.
