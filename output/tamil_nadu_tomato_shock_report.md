# Statistical Price & Spread Intelligence Report: Tamil Nadu

## 1. Analysis Scope & Data Integrity
- **State Analyzed:** Tamil Nadu
- **Primary Commodity Case Study:** Tomato (₹/kg)
- **Reporting Period:** 2015-01-03 to 2023-11-03
- **Total Matched Records (6 Basket Commodities):** 15,430
- **Matched observation period:** The period reflects records available after the retail/wholesale inner join.
- **Target Metric:** Normalized Indicative Price Spreads & Relative Volatility ($CV$)

## 2. Verified Commodity Volatility Rankings
| Commodity | Normalized Unit | Mean Price | Std Dev | Min Price | Max Price | Obs | CV (%) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tomato** | ₹/kg | ₹24.53 | ₹14.98 | ₹8.00 | ₹116.00 | 2,870 | **61.09%** |
| **Onion** | ₹/kg | ₹28.37 | ₹14.77 | ₹13.00 | ₹131.89 | 2,870 | **52.07%** |
| **Potato** | ₹/kg | ₹27.70 | ₹7.47 | ₹16.00 | ₹48.00 | 2,870 | **26.98%** |
| **Rice** | ₹/kg | ₹39.80 | ₹7.85 | ₹27.25 | ₹57.73 | 2,870 | **19.72%** |
| **Wheat** | ₹/kg | ₹34.37 | ₹3.50 | ₹29.50 | ₹44.71 | 2,870 | **10.19%** |
| **Milk** | ₹/litre | ₹42.57 | ₹1.47 | ₹36.00 | ₹47.00 | 1,080 | **3.45%** |

## 3. Statistical Price-Change Alert Summary
- **Selected Case Study:** Tomato
- **Methodology:** Calendar-aware 7-day velocity ($\Delta P_{7d}$) vs. 30-day prior rolling baseline
- **Z-Score Threshold:** $|Z| \ge 2.5$
- **Minimum Velocity Threshold:** $|\Delta P_{7d}| \ge ₹5.00$ per kg
- **Total Statistical Alerts Flagged:** **131 days**

## 4. Analytical Distinctions & Limitations
- **Indicative Price Spread vs. Net Profit:** Spread equals `Retail Price - Wholesale Price` after unit normalization. It is a reported-price difference, NOT a direct estimate of retailer profit or an observed intermediary margin. Transport, storage, wastage, taxes and timing differences are not captured.
- **Matched-observation limitation:** Volatility and alert calculations use records retained by the retail/wholesale inner join. Dates without a matched record are unavailable to the current analysis; this may affect sample counts and alert detection.
- **Statistical Alerts vs. Supply Shocks:** Detected events represent statistically unusual price changes; they do not establish the cause. Verify with independent harvest, weather or transport evidence before attributing root cause.
