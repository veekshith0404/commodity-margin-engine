# India Essential Commodities Price & Spread Intelligence Engine

A modular Python command-line pipeline for analyzing historical retail and wholesale prices of essential commodities in India. It compares relative retail-price variability across six commodities, computes an **indicative retail–wholesale price spread** where observations align, and flags statistically unusual seven-day retail-price changes.

> **Interpretation note:** this project does not estimate retailer net profit or prove the cause of a price movement. A spread is a difference between reported prices. Statistical alerts are candidates for further investigation, not confirmed supply shocks.

## What it does

- Loads historical retail and state-level wholesale CSVs with Pandas.
- Validates the required schema and parses source date formats.
- Normalizes state/commodity labels and checks duplicate join keys.
- Converts source wholesale price units into commodity-specific normalized units.
- Joins retail and wholesale observations by date, state and commodity.
- Calculates coefficient of variation (CV%) for Tomato, Onion, Potato, Rice, Wheat and Milk.
- Uses a calendar-indexed seven-day retail-price change and a prior 30-calendar-day baseline to flag unusual price changes.
- Exports charts and a state/commodity-specific Markdown report.

## Architecture

```text
commodity-margin-engine/
├── core/
│   ├── __init__.py
│   ├── loader.py
│   ├── transformer.py
│   ├── analytics.py
│   └── visualizer.py
├── data/                  # Add source CSV files locally; raw CSVs are gitignored
├── output/                # Example charts/report and new generated outputs
├── tests/
│   └── test_pipeline.py
├── main.py
├── requirements.txt
├── README.md
└── .gitignore
```

## Data sources and coverage

The project uses two locally downloaded Department of Consumer Affairs (DCA) price files available through the India Data Portal/data distribution ecosystem:

1. `daily-retail-prices-of-essential-commodities.csv` — **1,901,416 rows** in the version used for this project, covering approximately 2015-01-01 through 2023-11-03.
2. `state-level-daily-wholesale-price.csv` — **2,015,860 rows** in the version used for this project, covering approximately 2015 through 2024-08-28.

These dates and counts describe the local files used for the reported runs; a different download/version may have different coverage.

Reference metadata:
- [India Data Portal retail price resource](https://ckandev.indiadataportal.com/dataset/price-monitoring/resource/45f8c494-03d2-46b5-aa1a-a5e3656c3da6)
- [DCA essential commodity dataset metadata, including unit conventions](https://dataful.in/datasets/19913/)
- [DCA daily wholesale and retail prices in Maharashtra](https://dataful.in/datasets/19910/)
- [DCA daily wholesale and retail prices in Tamil Nadu](https://dataful.in/datasets/19900/)

The local flat CSVs contain the columns `id`, `date`, `state_name`, `state_code`, `commodity`, and `price`; they do **not** carry a per-row unit column. The code therefore uses a documented commodity-unit registry based on the source's stated conventions for the six selected commodities:

| Commodity | Retail normalized unit | Wholesale source unit | Conversion to normalized unit |
|---|---|---|---|
| Tomato | ₹/kg | ₹/quintal | divide wholesale price by 100 |
| Onion | ₹/kg | ₹/quintal | divide wholesale price by 100 |
| Potato | ₹/kg | ₹/quintal | divide wholesale price by 100 |
| Rice | ₹/kg | ₹/quintal | divide wholesale price by 100 |
| Wheat | ₹/kg | ₹/quintal | divide wholesale price by 100 |
| Milk (source label `Milk @`, normalized to `Milk`) | ₹/litre | ₹/100 litres | divide wholesale price by 100 |

Because units are not stored in each local CSV row, this mapping is an explicit source-based assumption. Reconfirm it if the input files are replaced or expanded to additional commodities. Unsupported commodities are rejected by the unit registry rather than silently converted.

## Installation

Use Python 3.10 or newer. From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Place the two CSV files inside `data/` using the exact filenames shown above. The datasets are intentionally excluded from Git because they are large; obtain them from the sources and follow any applicable reuse conditions.

## Run the pipeline

```powershell
python main.py --state Karnataka --commodity Tomato
python main.py --state Karnataka --commodity Onion
python main.py --state Maharashtra --commodity Onion
python main.py --state "Tamil Nadu" --commodity Tomato
```

Each successful run produces:

- `{state}_volatility_ranking.png` — CV ranking for the six-commodity basket.
- `{state}_{commodity}_spread_shocks.png` — retail/wholesale trend, statistical alert markers and indicative spread.
- `{state}_{commodity}_shock_report.md` — a report specific to that state and commodity, so subsequent runs do not overwrite earlier reports.

State and commodity names are normalized for casing. A commodity must be supported by the unit registry and have matched observations for the selected state.

## Methods

### Relative volatility

For each commodity, the coefficient of variation is calculated as standard deviation divided by mean price, multiplied by 100. CV is used to compare historical relative variability across commodities with different price levels. It is descriptive; it does not guarantee future volatility.

### Price spread

`indicative_spread = normalized_retail_price - normalized_wholesale_price`

This is an indicative difference between reported prices. It is **not** retailer net profit and may not represent the margin earned on the same physical batch of goods. Transport, storage, wastage, taxes, market/quality differences and reporting-time differences are not modelled.

### Statistical price-change alerts

The detector reindexes the available selected series to a daily calendar, permits at most three days of forward filling only for the seven-day velocity reference, uses a prior rolling baseline, and applies both a Z-score threshold and an absolute price-change threshold. Its present inputs are the matched retail/wholesale dataframe, so only dates retained by the inner join can be evaluated as actual observations. This can reduce the alert series compared with using every retail-only record. A flagged observation is a **statistical price-change alert**, not evidence by itself of a supply-chain shock or its cause.

## Observed sample runs

The following values are examples from runs using the local file versions described above. Alert counts are methodology-dependent and should be regenerated after code or data changes.

| State | Detail commodity | Matched rows in six-commodity basket | CV examples | Current alert output |
|---|---|---:|---|---:|
| Karnataka | Tomato | 11,268 | Tomato 64.56%; Onion 46.36% | 84 Tomato alerts |
| Karnataka | Onion | 11,268 | Tomato 64.56%; Onion 46.36% | 49 Onion alerts |
| Maharashtra | Onion | 17,311 | Onion 45.20%; Tomato 43.15% | 73 Onion alerts |
| Tamil Nadu | Tomato | 15,430 | Tomato 61.09%; Onion 52.07% | 131 Tomato alerts |

These are the outputs reported by the current implementation, not independently verified causes of price movements. The matched basket has uneven observation coverage; for example, some commodities have fewer valid prices than others. The pipeline logs missing-price counts and merge coverage for each state.

## Tests

The test suite uses small synthetic data and does not require loading the large CSVs:

```powershell
python -m unittest discover -s tests -v
```

Tests cover the unit registry and conversion, text normalization (`Milk @`), duplicate-key aggregation, calendar-day price differences across a gap, detection after a stable baseline, and distinct report paths.

## Limitations and next steps

- The source CSVs do not include a per-row unit column; the project depends on a documented commodity-unit registry.
- The retail/wholesale inner join reduces the available analysis dates and can introduce selection effects in the volatility and alert calculations.
- The minimum absolute price-change threshold is fixed at ₹5 per normalized unit; its suitability should be reviewed for each commodity.
- Statistical alerts require external context before being attributed to weather, crop disease, transport disruption or policy action.
- The national wholesale dataset is optional and is not required for the core pipeline.
