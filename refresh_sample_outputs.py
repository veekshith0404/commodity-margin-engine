"""Regenerate the project's documented sample reports and charts.

Run from the project root after placing both source CSVs in ``data/``.
Old generated images/reports from earlier methodology versions are removed
first so they cannot be mistaken for current results.
"""
from pathlib import Path

from main import run_pipeline


SAMPLE_RUNS = [
    ("Karnataka", "Tomato"),
    ("Karnataka", "Onion"),
    ("Maharashtra", "Onion"),
    ("Tamil Nadu", "Tomato"),
]
GENERATED_SUFFIXES = (
    "_volatility_ranking.png",
    "_spread_shocks.png",
    "_shock_report.md",
    "_relative_dispersion.png",
    "_price_alerts.png",
    "_price_alert_report.md",
)


def main() -> None:
    output = Path("output")
    output.mkdir(parents=True, exist_ok=True)

    removed = 0
    for path in output.iterdir():
        if path.is_file() and path.name.endswith(GENERATED_SUFFIXES):
            path.unlink()
            removed += 1
    print(f"Removed {removed} stale generated output file(s).")

    for state, commodity in SAMPLE_RUNS:
        print(f"\n### Generating {state} / {commodity} ###")
        run_pipeline(state=state, primary_commodity=commodity)

    print("\nAll sample analyses completed with the current methodology.")
    print("Review the newly generated output/*.png and output/*_price_alert_report.md files.")


if __name__ == "__main__":
    main()
