# Validation Results

Executed in the working environment on the supplied CSV versions on 2026-10-23.

## Automated tests

Command:

```powershell
python -m unittest discover -s tests -v
```

Result: **6 tests passed**. The tests cover unit registry behavior, unit conversion and `Milk @` normalization, duplicate-key aggregation, seven-calendar-day change across a date gap, alert detection after stable history, and state/commodity-specific report filenames.

## End-to-end sample runs

| Command | Result | Matched rows | Retail records matched | Statistical alerts |
|---|---|---:|---:|---:|
| `python main.py --state Karnataka --commodity Tomato` | Completed | 11,268 | 75.4% | 84 |
| `python main.py --state Karnataka --commodity Onion` | Completed | 11,268 | 75.4% | 49 |
| `python main.py --state Maharashtra --commodity Onion` | Completed | 17,311 | 92.5% | 73 |
| `python main.py --state "Tamil Nadu" --commodity Tomato` | Completed | 15,430 | 83.0% | 131 |

All four runs generated a state-specific volatility chart, a state-and-commodity-specific spread/alert chart, and a state-and-commodity-specific Markdown report.

These alert totals are outputs of the current configured detector. They should be described as statistical price-change alerts, not confirmed supply shocks. Results may change if the dataset, matching logic, thresholds or methodology changes.

## Performance note

A single full-dataset Karnataka–Tomato run completed in approximately 10 seconds in this working environment. This is an environment-specific observation, not a guaranteed performance benchmark for other computers.

## Remaining limitation

The supplied flat CSV files do not include a per-row `unit` column. The commodity-unit registry is documented in `README.md` and informed by source metadata. Before extending beyond the six registered commodities, check the source unit conventions and add tests for any new mapping.
