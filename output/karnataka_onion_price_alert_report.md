# India Essential Commodities Price & Spread Intelligence Report: Karnataka

## 1. Analysis Scope and Coverage
- **State:** Karnataka
- **Detailed commodity:** Onion (₹/kg)
- **Matched basket period:** 2015-01-06 to 2023-11-03
- **Matched rows across the supported commodity basket:** 11,268
- **Join keys:** date, state and commodity; the join is inner, so unmatched dates are excluded.
- **Scope note:** reporting periods and sample sizes can differ by commodity. Each CV uses that commodity's own matched observations.

## 2. Input Data Quality

Counts below describe rows read from each source file. Issue counts may overlap when one row has multiple problems.

| Source | Input rows | Retained rows | Excluded rows | Invalid dates | Blank prices | Non-numeric prices | Non-finite prices | Non-positive prices | Missing state/commodity |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Retail | 1,901,416 | 1,826,128 | 75,288 | 0 | 75,288 | 0 | 0 | 0 | 0 |
| Wholesale | 2,015,860 | 1,892,196 | 123,664 | 0 | 123,664 | 0 | 0 | 0 | 0 |

- **State/commodity-filtered retail rows before transformer validation:** 14,935
- **State/commodity-filtered wholesale rows before transformer validation:** 15,928
- **Valid unique retail join keys:** 14,935
- **Valid unique wholesale join keys:** 15,928
- **Matched rows:** 11,268
- **Overall matched share of valid unique retail keys:** 75.4%

Blank, malformed, non-finite, non-positive-price and invalid-key rows are excluded before merging. The original CSV files are not modified.

## 3. Overall Relative Price Dispersion

CV (%) = sample standard deviation / mean price × 100. Prices are pooled across each commodity's available matched period, so CV can reflect long-term trends as well as shorter-term fluctuations. It is not a detrended short-term volatility measure.

| Commodity | Unit | Mean | Std dev | Minimum | Maximum | Matched observations | CV (%) | Retail-key match coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Tomato | ₹/kg | ₹25.10 | ₹16.20 | ₹8.75 | ₹119.97 | 1,882 | 64.56% | 2,489 keys; 75.61% |
| Onion | ₹/kg | ₹28.31 | ₹13.13 | ₹11.25 | ₹112.50 | 1,882 | 46.36% | 2,489 keys; 75.61% |
| Potato | ₹/kg | ₹26.61 | ₹5.60 | ₹17.67 | ₹54.00 | 1,882 | 21.06% | 2,489 keys; 75.61% |
| Rice | ₹/kg | ₹44.29 | ₹5.31 | ₹29.00 | ₹56.53 | 1,882 | 11.99% | 2,489 keys; 75.61% |
| Milk | ₹/litre | ₹39.46 | ₹4.59 | ₹29.00 | ₹50.77 | 1,858 | 11.64% | 2,490 keys; 74.62% |
| Wheat | ₹/kg | ₹34.01 | ₹3.23 | ₹28.00 | ₹43.17 | 1,882 | 9.51% | 2,489 keys; 75.61% |

- **Selected commodity retail-key match coverage:** 75.61% (1,882 matched of 2,489 valid retail keys).

## 4. Statistical Price-Change Alerts
- **Selected commodity:** Onion
- **Alert input:** Valid, deduplicated retail observations for the selected state and commodity, independent of wholesale-date availability.
- **Price-change measure:** Exact seven-calendar-day comparison; both dates must contain valid reported retail prices. No forward fill is used.
- **Z-score measure:** Log price change, ln(current price / reference price), compared with prior same-weekday log changes. The rolling baseline excludes the current change and spans up to the configured number of weeks, with at least five valid historical values required.
- **Absolute Z-score threshold:** 2.50
- **Minimum absolute seven-day percentage change:** 10.00%
- **Maximum gap between alert dates within a group:** 3 calendar days
- **Alert days:** 121
- **Grouped alert periods:** 76
- **Infinite Z-score observations:** 0
- **Alerts associated with the isolated-outlier heuristic:** 6

Alerts are two-sided: both unusually large increases and decreases can be flagged. The minimum-move gate uses the conventional absolute percentage change (for example, at least +10% or at most -10%); log changes are used for Z-scores. Grouping combines alert dates no more than the configured number of calendar days apart. These groups are analytical clusters, not independently confirmed market events. Infinite Z-scores can occur when the baseline standard deviation is zero and the observed change differs from the baseline mean.

The isolated-outlier heuristic marks a reported observation when its preceding and following reported prices agree within 15% of their mean and the middle price differs from each by at least 40%. An alert is associated with the heuristic when its current price or its exact seven-day reference is marked. This is a review cue only, not proof of a data error or causation.

## 5. Indicative Retail–Wholesale Spread Review
- **Negative spread review flags (spread below -₹0.000001):** 102
- **Spreads below -₹20 per normalized unit:** 10
- **Calculation:** normalized retail price minus normalized wholesale price.
- **Review flag:** spreads below -₹0.000001 are flagged using a numerical tolerance. This is not a materiality threshold; even small negative values are review signals, not confirmed errors.
- **Interpretation:** a negative spread is a review signal, not proof of an error. Source records, dates, market definitions and unit assumptions should be checked before drawing conclusions.
- **Not profit:** the spread is not retailer net profit and does not account fully for transport, storage, wastage, taxes, market fees or timing differences.

## 6. Limitations and Interpretation
- **Selection effects:** CV and spread analysis use matched retail/wholesale dates, while alert detection uses valid retail dates independently. Coverage differences therefore affect CV/spread analysis but do not discard retail-only alert observations.
- **Alert model:** the rolling baseline uses prior same-weekday log changes. It spans up to the configured number of weeks but may contain fewer valid historical values when prices are missing. Results still depend on the selected thresholds and source coverage.
- **Source anomalies:** numerically valid prices can still be implausible. Unusual observations are not automatically deleted.
- **Causation:** statistical alerts do not establish supply shocks or explain why prices changed; independent evidence is required.
- **Unit assumptions:** source CSVs have no per-row unit field. The documented registry must be rechecked whenever the source data or commodity definitions change.
