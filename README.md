# India Essential Commodities Price & Spread Intelligence Engine

A modular Python command-line analytics pipeline for examining Indian retail and state-level wholesale prices for six essential commodities. It validates source rows, standardizes labels and units, joins matched observations, calculates overall relative price dispersion, flags statistically unusual seven-day retail price changes, examines indicative price spreads, and generates charts and Markdown reports.

> **Interpretation limits:** The coefficient of variation (CV) includes long-term price trends. Statistical alerts are not confirmed market events, and a retail–wholesale price spread is not retailer net profit. Suspicious observations are flagged for review rather than silently deleted.

## 1. Features

- Loads large retail and wholesale CSV files with Pandas.
- Validates source columns, dates, prices, state names, and commodity names.
- Excludes and counts invalid dates, missing or malformed prices, non-finite prices, non-positive prices, and missing join keys.
- Uses `float64` for price values and spread calculations.
- Normalizes state and commodity labels, including the source label `Milk @`.
- Aggregates duplicate join keys using a daily mean before a one-to-one inner join.
- Converts wholesale values using a documented commodity-unit registry.
- Calculates the coefficient of variation across each commodity's available matched period.
- Detects price changes using the valid retail series before any wholesale merge, so missing wholesale records do not suppress retail alerts.
- Calculates exact seven-calendar-day price changes only when both the current and seven-days-prior retail prices are observed. No forward filling is used.
- Computes Z-scores from log price changes against a prior-only, same-weekday baseline. A separate conventional percentage-change gate applies the minimum movement threshold.
- Groups alert observations using a configurable calendar-day gap and records infinite Z-score cases.
- Flags negative indicative spreads using a numerical tolerance. These flags are review signals, not proof of an error.
- Reports how many alert days are associated with an isolated-retail-outlier heuristic. These observations are retained for investigation rather than automatically removed.
- Produces descriptive charts and state- and commodity-specific Markdown reports containing data-quality counts, coverage, methodology, and limitations.

## 2. Project layout

```text
commodity-margin-engine/
├── core/
│   ├── __init__.py
│   ├── loader.py
│   ├── transformer.py
│   ├── analytics.py
│   └── visualizer.py
├── data/
│   └── .gitkeep
├── output/                     # Regenerated local charts and reports
├── tests/
│   ├── test_pipeline.py
│   ├── test_loader_hardening.py
│   └── test_reporting.py
├── main.py
├── prepare_review.py
├── refresh_sample_outputs.py
├── build_review_package.py
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
├── TEST_RESULTS.md
├── README.md
└── .gitignore
```

Raw CSVs, virtual environments, caches, and generated release ZIP archives are excluded from Git. Original source files remain unchanged; invalid rows are excluded in memory and their counts are recorded in reports and logs.

## 3. Data sources, versions, and unit assumptions

The project uses two locally downloaded price datasets distributed through the India Data Portal / Department of Consumer Affairs data ecosystem:

1. `daily-retail-prices-of-essential-commodities.csv`
2. `state-level-daily-wholesale-price.csv`

Reference metadata:

- [India Data Portal retail price resource](https://ckandev.indiadataportal.com/dataset/price-monitoring/resource/45f8c494-03d2-46b5-aa1a-a5e3656c3da6)
- [DCA essential commodity dataset metadata and unit conventions](https://dataful.in/datasets/19913/)
- [DCA daily wholesale and retail prices in Maharashtra](https://dataful.in/datasets/19910/)
- [DCA daily wholesale and retail prices in Tamil Nadu](https://dataful.in/datasets/19900/)

The exact local row counts and coverage can change when the files are downloaded again. Keep the filenames above unless the loader configuration is updated.

The CSV files do not include a per-row unit field. The registry therefore records source-based assumptions for the selected commodities:

| Commodity | Retail normalized unit | Wholesale source-unit assumption | Conversion to normalized unit |
|---|---|---|---|
| Tomato | ₹/kg | ₹/quintal | Wholesale price ÷ 100 |
| Onion | ₹/kg | ₹/quintal | Wholesale price ÷ 100 |
| Potato | ₹/kg | ₹/quintal | Wholesale price ÷ 100 |
| Rice | ₹/kg | ₹/quintal | Wholesale price ÷ 100 |
| Wheat | ₹/kg | ₹/quintal | Wholesale price ÷ 100 |
| Milk (`Milk @` in source) | ₹/litre | ₹/100 litres | Wholesale price ÷ 100 |

One quintal equals 100 kilograms. The milk mapping assumes that the source wholesale price is expressed per 100 litres. Reconfirm these assumptions whenever the datasets, source definitions, or supported commodities change. Unsupported commodities are rejected rather than assigned a fallback unit.

## 4. Requirements and setup

Use **Python 3.12 or newer**, together with the dependency versions pinned in `requirements.txt`.

From the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

Copy the two source CSV files into `data/`, using the filenames listed above. The large source files are intentionally not bundled with the project ZIP and are ignored by Git.

## 5. Run the analysis

The default example analyzes Karnataka tomato prices:

```powershell
python main.py --state Karnataka --commodity Tomato
```

Other examples:

```powershell
python main.py --state Karnataka --commodity Onion
python main.py --state Maharashtra --commodity Onion
python main.py --state "Tamil Nadu" --commodity Tomato
```

### Detection parameters

Example using the default parameters:

```powershell
python main.py --state Karnataka --commodity Tomato --z-threshold 2.5 --min-pct-change 10 --baseline-weeks 30 --event-gap-days 3
```

| Parameter | Default | Meaning |
|---|---:|---|
| `--z-threshold` | 2.5 | Minimum absolute rolling Z-score |
| `--min-pct-change` | 10 | Minimum absolute seven-calendar-day percentage change |
| `--baseline-weeks` | 30 | A rolling span of up to 30 prior same-weekday weekly changes. Missing values may leave fewer usable observations; at least five valid prior changes are required. |
| `--event-gap-days` | 3 | Alert dates separated by no more than this number of calendar days are assigned to the same group. |

`--window` remains an alias for `--baseline-weeks`. It represents the number of weeks of prior same-weekday changes, not calendar days.

These thresholds are analysis parameters, not universally validated market standards. Compare results across thresholds and states before drawing economic conclusions.

### One-command release check and review package

After placing both CSV files in `data/` and installing `requirements-dev.txt`, run:

```powershell
python prepare_review.py
```

This command checks dependency consistency, compiles the code, runs the automated test suite, removes stale generated charts and reports, regenerates the four documented sample combinations using the current defaults, updates `TEST_RESULTS.md` from the new local results, and builds `commodity-margin-engine-final-release.zip`.

The ZIP excludes raw CSVs, virtual environments, Git metadata, and other ZIP files. The script checks for both source files before removing old outputs and does not modify the original CSVs.

To regenerate only the charts and reports without running the other release checks, use:

```powershell
python refresh_sample_outputs.py
```

Each successful analysis generates:

- `{state}_relative_dispersion.png` — a CV chart labelled as overall relative price dispersion.
- `{state}_{commodity}_price_alerts.png` — retail and wholesale trends, two-sided statistical alert markers, and indicative spread review.
- `{state}_{commodity}_price_alert_report.md` — a report containing data-quality counts, per-commodity match coverage, retail-only alert methodology, alert and group counts, isolated-outlier association counts, spread review counts, and limitations.

## 6. Methods

### 6.1 Overall relative price dispersion

For each commodity:

`CV (%) = sample standard deviation / mean price × 100`

Prices are pooled across that commodity's available matched period. CV can reflect long-term price trends and shorter-term variation. It is **not** a detrended short-term volatility estimate or a forecast.

### 6.2 Indicative retail–wholesale price spread

The calculation is:

`Indicative spread = normalized retail price − normalized wholesale price`

A positive spread means the matched retail value exceeds the normalized wholesale value. A negative spread means the matched wholesale value exceeds the retail value.

Negative spreads are review signals, not automatically data errors. Date, unit, source, market-definition, and reporting-time differences should be investigated before drawing conclusions.

The spread is not retailer net profit. Transport, storage, wastage, taxes, market fees, quality differences, and reporting-time differences are not fully modelled.

A small numerical tolerance of ₹0.000001 per normalized unit is used when flagging negative spreads to avoid treating tiny floating-point residuals as review flags. This is **not an economic materiality threshold**.

The report also summarizes spreads below −₹20 per normalized unit using an **illustrative reporting cutoff**. This cutoff is not a validated economic materiality threshold or proof of an error. Observations below it should be investigated in context rather than automatically classified as confirmed anomalies.

### 6.3 Seven-day percentage change

For date `t`, the pipeline compares the reported retail price at `t` with the reported retail price at exactly `t − 7 calendar days`.

If either observation is missing, that seven-day change is unavailable. No imputation is used for this comparison; a gap does not silently turn the metric into a seven-to-ten-day change.

The alert detector runs on the selected state and commodity retail series before wholesale prices are merged.

### 6.4 Rolling Z-score and alerts

The detector calculates a Z-score from the log price change:

`ln(current price / price seven days earlier)`

This value is compared with up to 30 earlier same-weekday changes. The rolling baseline spans up to 30 weeks, is shifted to exclude the current change, and requires at least five valid prior values.

Using log changes avoids the directional scale asymmetry of ordinary percentage returns in the Z-score calculation, although it does not make the observations independent.

The default detector flags changes when **both** conditions are met:

- The absolute Z-score of the log change is at least `2.5`.
- The absolute conventional seven-day percentage change is at least `10%`—at least +10% or at most −10%.

Alerts are two-sided, so unusual price increases and decreases can both be flagged.

With a zero-variance baseline, a non-zero deviation can produce an infinite Z-score; the report counts these cases. Such alerts require interpretation alongside the underlying price changes and data coverage.

The log-change measure and percentage threshold serve different purposes: the former is used for statistical standardization, while the latter is the minimum-movement gate.

### 6.5 Alert groups

Alert observations are grouped when successive alert dates are no more than three calendar days apart by default.

Non-alert rows retain a missing event ID. These groups help summarize nearby alert dates; they are not independently confirmed price shocks or supply-chain events.

### 6.6 Data quality and matching

The loader checks required columns, parses dates, and validates prices and join keys. It excludes missing or malformed prices, non-finite prices, non-positive prices, invalid dates, and missing state or commodity keys, and records the excluded-row counts.

An invalid-date rate above 1% stops processing for review rather than silently dropping a substantial portion of a dataset. A dataset in which all dates are invalid also raises an error.

The transformer harmonizes known state-name aliases, aggregates duplicate date/state/commodity keys using a daily mean before the inner join, and reports valid unique-key counts and match coverage overall and by commodity.

Matching remains a limitation for CV and spread calculations: unmatched dates are excluded, and coverage can differ between commodities and states. Retail-only alert detection does not require a same-day wholesale match.

## 7. Testing and validation

Run the automated suite:

```powershell
pytest -q
```

The tests use synthetic data and temporary CSV files; they do not require the two large source datasets. They cover loading and validation, unit normalization for vegetables, grains, and milk, state-name aliases, duplicate aggregation, retail-only alert preparation, no-overlap joins, CV arithmetic, exact seven-day references, missing reference dates, hand-calculated prior-only same-weekday log-change Z-scores, percentage and Z-score gate boundaries, zero-variance behaviour, isolated-outlier association, spread-tolerance boundaries, invalid prices, event grouping, report counts and content, and chart generation.

Passing tests demonstrate the tested behaviours, not that every row in a real-world source file is valid or that an alert threshold is economically optimal. Run the full-data sample analyses and review the generated outputs whenever the code, methodology, source data, or parameters change.

## 8. Important limitations

- Units are assumed from source metadata because individual rows do not contain a unit field.
- CV and spread calculations use an inner-join subset; state and commodity coverage are uneven. Retail alerts are calculated separately from the retail-only series.
- Duplicate-key means may hide different markets if the source data uses a finer market definition than the local CSV columns expose.
- The isolated-outlier heuristic marks a reported price when the preceding and following reported observations agree within 15% of their mean and the middle value differs from both by at least 40%. An alert is associated with the heuristic when its current observation or its exact seven-day reference is marked. This is a diagnostic association, not proof of an error or causation; observations are retained for review.
- CV includes long-term trends.
- Alert output depends on thresholds, baseline length, data coverage, and historical price behaviour.
- Alert groups do not prove independent events or their causes.
- The ₹20 reporting cutoff is illustrative and should not be interpreted as a validated economic threshold.
- Replacing the input CSVs requires rechecking their schemas, date conventions, units, coverage, and source versions.

## 9. Project summary

This project demonstrates a modular Python analytics workflow for validating and transforming large CSV files, joining retail and wholesale price observations, applying documented unit assumptions, calculating descriptive statistics, detecting unusual price changes, visualizing spreads, and producing transparent reports with data-quality counts and limitations.