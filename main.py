import argparse
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.analytics import CommodityAnalytics
from core.loader import DataLoader
from core.transformer import DataTransformer, COMMODITY_UNIT_REGISTRY
from core.visualizer import ChartVisualizer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

DEFAULT_Z_THRESHOLD = 2.5
DEFAULT_MIN_PCT_CHANGE = 10.0
DEFAULT_BASELINE_WEEKS = 30
DEFAULT_EVENT_GAP_DAYS = 3


def build_report_path(output_dir: Path, state: str, commodity: str) -> Path:
    """Return a state/commodity-specific statistical alert report path."""
    def slug(value: str) -> str:
        return "_".join(value.strip().lower().split())

    return output_dir / f"{slug(state)}_{slug(commodity)}_price_alert_report.md"


def _format_currency(value: Any) -> str:
    if pd.isna(value):
        return "N/A"
    return f"₹{value:.2f}"


def _format_percent(value: Any) -> str:
    if pd.isna(value):
        return "N/A"
    return f"{value:.2f}%"


def _data_quality_lines(
    loader_stats: dict[str, dict[str, Any]],
    transform_stats: dict[str, Any],
) -> list[str]:
    lines = [
        "",
        "## 2. Input Data Quality",
        "",
        "Counts below describe rows read from each source file. Issue counts may overlap when one row has multiple problems.",
        "",
        "| Source | Input rows | Retained rows | Excluded rows | Invalid dates | Blank prices | Non-numeric prices | Non-finite prices | Non-positive prices | Missing state/commodity |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for source_name in ("retail", "wholesale"):
        stats = loader_stats.get(source_name, {})
        lines.append(
            f"| {source_name.title()} "
            f"| {stats.get('source_rows', 0):,} "
            f"| {stats.get('retained_rows', 0):,} "
            f"| {stats.get('excluded_rows', 0):,} "
            f"| {stats.get('invalid_dates', 0):,} "
            f"| {stats.get('blank_prices', 0):,} "
            f"| {stats.get('non_numeric_prices', 0):,} "
            f"| {stats.get('non_finite_prices', 0):,} "
            f"| {stats.get('non_positive_prices', 0):,} "
            f"| {stats.get('missing_state_or_commodity', 0):,} |"
        )

    lines.extend([
        "",
        f"- **State/commodity-filtered retail rows before transformer validation:** {transform_stats.get('filtered_retail_rows', 0):,}",
        f"- **State/commodity-filtered wholesale rows before transformer validation:** {transform_stats.get('filtered_wholesale_rows', 0):,}",
        f"- **Valid unique retail join keys:** {transform_stats.get('valid_retail_keys', 0):,}",
        f"- **Valid unique wholesale join keys:** {transform_stats.get('valid_wholesale_keys', 0):,}",
        f"- **Matched rows:** {transform_stats.get('matched_rows', 0):,}",
        f"- **Overall matched share of valid unique retail keys:** {transform_stats.get('retail_key_coverage_pct', 0.0):.1f}%",
        "",
        "Blank, malformed, non-finite, non-positive-price and invalid-key rows are excluded before merging. The original CSV files are not modified.",
    ])
    return lines


def generate_markdown_report(
    state: str,
    commodity: str,
    df_merged: pd.DataFrame,
    df_dispersion: pd.DataFrame,
    df_alerts: pd.DataFrame,
    output_path: Path,
    loader_stats: dict[str, dict[str, Any]] | None = None,
    transform_stats: dict[str, Any] | None = None,
    z_threshold: float = DEFAULT_Z_THRESHOLD,
    min_pct_change: float = DEFAULT_MIN_PCT_CHANGE,
    baseline_weeks: int = DEFAULT_BASELINE_WEEKS,
    event_gap_days: int = DEFAULT_EVENT_GAP_DAYS,
) -> None:
    """Generate a methodology-consistent Markdown report."""
    if df_merged.empty:
        raise ValueError("Cannot create a report from an empty matched dataset.")

    min_date = pd.to_datetime(df_merged["date"]).min().strftime("%Y-%m-%d")
    max_date = pd.to_datetime(df_merged["date"]).max().strftime("%Y-%m-%d")
    basket_rows = len(df_merged)
    unit = COMMODITY_UNIT_REGISTRY[commodity]["unit"]
    loader_stats = loader_stats or {}
    transform_stats = transform_stats or {}

    if df_alerts.empty:
        alert_days = 0
        event_count = 0
        infinite_z_scores = 0
        negative_spread_rows = 0
        severe_negative_spread_rows = 0
        outlier_associated_alerts = 0
    else:
        alert_mask = df_alerts["is_alert"].fillna(False).astype(bool)
        alert_days = int(alert_mask.sum())
        event_count = int(df_alerts.loc[alert_mask, "alert_event_id"].nunique())
        infinite_z_scores = int(
            np.isinf(pd.to_numeric(df_alerts["z_score"], errors="coerce")).sum()
        )
        spreads = df_alerts.get(
            "indicative_spread", pd.Series(np.nan, index=df_alerts.index, dtype="float64")
        )
        negative_spread_rows = int(
            df_alerts.get("spread_review_flag", pd.Series(False, index=df_alerts.index))
            .fillna(False).astype(bool).sum()
        )
        severe_negative_spread_rows = int((spreads < -20.0).sum())
        outlier_associated_alerts = int(
            df_alerts.get(
                "outlier_associated_alert", pd.Series(False, index=df_alerts.index)
            ).fillna(False).astype(bool).sum()
        )

    report_lines = [
        f"# India Essential Commodities Price & Spread Intelligence Report: {state}",
        "",
        "## 1. Analysis Scope and Coverage",
        f"- **State:** {state}",
        f"- **Detailed commodity:** {commodity} ({unit})",
        f"- **Matched basket period:** {min_date} to {max_date}",
        f"- **Matched rows across the supported commodity basket:** {basket_rows:,}",
        "- **Join keys:** date, state and commodity; the join is inner, so unmatched dates are excluded.",
        "- **Scope note:** reporting periods and sample sizes can differ by commodity. Each CV uses that commodity's own matched observations.",
    ]
    report_lines.extend(_data_quality_lines(loader_stats, transform_stats))
    report_lines.extend([
        "",
        "## 3. Overall Relative Price Dispersion",
        "",
        "CV (%) = sample standard deviation / mean price × 100. Prices are pooled across each commodity's available matched period, so CV can reflect long-term trends as well as shorter-term fluctuations. It is not a detrended short-term volatility measure.",
        "",
        "| Commodity | Unit | Mean | Std dev | Minimum | Maximum | Matched observations | CV (%) | Retail-key match coverage |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    coverage_by_commodity = transform_stats.get("coverage_by_commodity", {})
    selected_coverage = coverage_by_commodity.get(commodity, {})
    selected_retail_keys = int(selected_coverage.get("valid_retail_keys", 0))
    selected_matched_keys = int(selected_coverage.get("matched_keys", 0))
    selected_match_pct = selected_coverage.get("retail_match_pct", np.nan)
    for _, row in df_dispersion.iterrows():
        name = str(row["commodity"])
        row_unit = COMMODITY_UNIT_REGISTRY[name]["unit"]
        coverage = coverage_by_commodity.get(name, {})
        retail_key_count = int(coverage.get("valid_retail_keys", 0))
        match_pct = coverage.get("retail_match_pct", np.nan)
        report_lines.append(
            f"| {name} | {row_unit} | {_format_currency(row['mean_price'])} "
            f"| {_format_currency(row['std_price'])} | {_format_currency(row['min_price'])} "
            f"| {_format_currency(row['max_price'])} | {int(row['observations']):,} "
            f"| {_format_percent(row['cv_pct'])} | {retail_key_count:,} keys; {_format_percent(match_pct)} |"
        )
    report_lines.extend([
        "",
        f"- **Selected commodity retail-key match coverage:** {_format_percent(selected_match_pct)} "
        f"({selected_matched_keys:,} matched of {selected_retail_keys:,} valid retail keys).",
    ])

    report_lines.extend([
        "",
        "## 4. Statistical Price-Change Alerts",
        f"- **Selected commodity:** {commodity}",
        "- **Alert input:** Valid, deduplicated retail observations for the selected state and commodity, independent of wholesale-date availability.",
        "- **Price-change measure:** Exact seven-calendar-day comparison; both dates must contain valid reported retail prices. No forward fill is used.",
        "- **Z-score measure:** Log price change, ln(current price / reference price), compared with prior same-weekday log changes. The rolling baseline excludes the current change and spans up to the configured number of weeks, with at least five valid historical values required.",
        f"- **Absolute Z-score threshold:** {z_threshold:.2f}",
        f"- **Minimum absolute seven-day percentage change:** {min_pct_change:.2f}%",
        f"- **Maximum gap between alert dates within a group:** {event_gap_days} calendar days",
        f"- **Alert days:** {alert_days:,}",
        f"- **Grouped alert periods:** {event_count:,}",
        f"- **Infinite Z-score observations:** {infinite_z_scores:,}",
        f"- **Alerts associated with the isolated-outlier heuristic:** {outlier_associated_alerts:,}",
        "",
        "Alerts are two-sided: both unusually large increases and decreases can be flagged. The minimum-move gate uses the conventional absolute percentage change (for example, at least +10% or at most -10%); log changes are used for Z-scores. Grouping combines alert dates no more than the configured number of calendar days apart. These groups are analytical clusters, not independently confirmed market events. Infinite Z-scores can occur when the baseline standard deviation is zero and the observed change differs from the baseline mean.",
        "",
        "The isolated-outlier heuristic marks a reported observation when its preceding and following reported prices agree within 15% of their mean and the middle price differs from each by at least 40%. An alert is associated with the heuristic when its current price or its exact seven-day reference is marked. This is a review cue only, not proof of a data error or causation.",
        "",
        "## 5. Indicative Retail–Wholesale Spread Review",
        f"- **Negative spread review flags (spread below -₹0.000001):** {negative_spread_rows:,}",
        f"- **Spreads below -₹20 per normalized unit:** {severe_negative_spread_rows:,}",
        "- **Calculation:** normalized retail price minus normalized wholesale price.",
        "- **Review flag:** spreads below -₹0.000001 are flagged using a numerical tolerance. This is not a materiality threshold; even small negative values are review signals, not confirmed errors.",
        "- **Interpretation:** a negative spread is a review signal, not proof of an error. Source records, dates, market definitions and unit assumptions should be checked before drawing conclusions.",
        "- **Not profit:** the spread is not retailer net profit and does not account fully for transport, storage, wastage, taxes, market fees or timing differences.",
        "",
        "## 6. Limitations and Interpretation",
        "- **Selection effects:** CV and spread analysis use matched retail/wholesale dates, while alert detection uses valid retail dates independently. Coverage differences therefore affect CV/spread analysis but do not discard retail-only alert observations.",
        "- **Alert model:** the rolling baseline uses prior same-weekday log changes. It spans up to the configured number of weeks but may contain fewer valid historical values when prices are missing. Results still depend on the selected thresholds and source coverage.",
        "- **Source anomalies:** numerically valid prices can still be implausible. Unusual observations are not automatically deleted.",
        "- **Causation:** statistical alerts do not establish supply shocks or explain why prices changed; independent evidence is required.",
        "- **Unit assumptions:** source CSVs have no per-row unit field. The documented registry must be rechecked whenever the source data or commodity definitions change.",
        "",
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(report_lines), encoding="utf-8")
    logging.info("Price alert report generated: %s", output_path)


def run_pipeline(
    state: str,
    primary_commodity: str,
    z_threshold: float = DEFAULT_Z_THRESHOLD,
    min_pct_change: float = DEFAULT_MIN_PCT_CHANGE,
    baseline_weeks: int = DEFAULT_BASELINE_WEEKS,
    event_gap_days: int = DEFAULT_EVENT_GAP_DAYS,
) -> None:
    """Execute ingestion, transformation, analysis and output generation."""
    clean_state = state.strip().title()
    clean_commodity = primary_commodity.strip().title()

    if clean_commodity not in COMMODITY_UNIT_REGISTRY:
        raise ValueError(
            f"Unsupported commodity '{clean_commodity}'. "
            f"Supported commodities: {list(COMMODITY_UNIT_REGISTRY)}"
        )
    if not np.isfinite(z_threshold) or z_threshold < 0:
        raise ValueError("z_threshold must be a finite non-negative number.")
    if not np.isfinite(min_pct_change) or min_pct_change < 0:
        raise ValueError("min_pct_change must be a finite non-negative number.")
    if not isinstance(baseline_weeks, int) or isinstance(baseline_weeks, bool) or baseline_weeks < 5:
        raise ValueError("baseline_weeks must be an integer of at least 5.")
    if not isinstance(event_gap_days, int) or isinstance(event_gap_days, bool) or event_gap_days < 1:
        raise ValueError("event_gap_days must be a positive integer.")

    logging.info(
        "Starting Price & Spread Intelligence Engine for %s / %s.",
        clean_state, clean_commodity,
    )

    loader = DataLoader(
        retail_path="data/daily-retail-prices-of-essential-commodities.csv",
        wholesale_path="data/state-level-daily-wholesale-price.csv",
    )
    retail = loader.load_retail()
    wholesale = loader.load_wholesale()

    transformer = DataTransformer(retail, wholesale)
    basket = list(COMMODITY_UNIT_REGISTRY)
    merged = transformer.transform(state=clean_state, commodities=basket)
    if merged.empty:
        raise ValueError(
            f"No matched data found for state '{clean_state}'. "
            "Check spelling and dataset coverage."
        )

    retail_alert_series = transformer.prepare_retail_series(
        state=clean_state,
        commodity=clean_commodity,
    )
    if retail_alert_series.empty:
        raise ValueError(
            f"No valid retail observations for '{clean_commodity}' in '{clean_state}'."
        )

    analytics = CommodityAnalytics(merged)
    dispersion = analytics.compute_volatility_table()
    print("\n" + "=" * 76)
    print(f"OVERALL RELATIVE PRICE DISPERSION: {clean_state.upper()} (SIX-COMMODITY BASKET)")
    print("=" * 76)
    print(dispersion.to_string(index=False))
    print("=" * 76 + "\n")

    alerts = CommodityAnalytics(retail_alert_series).detect_price_change_alerts(
        commodity=clean_commodity,
        z_threshold=z_threshold,
        min_pct_change=min_pct_change,
        window_weeks=baseline_weeks,
        event_gap_days=event_gap_days,
    )

    # Add wholesale/spread fields after retail-only alert detection. Missing
    # wholesale matches remain NaN and cannot suppress a retail price alert.
    spread_columns = [
        "date", "wholesale_price_normalized", "indicative_spread", "spread_review_flag"
    ]
    selected_spreads = merged.loc[
        merged["commodity"].astype("string").eq(clean_commodity), spread_columns
    ].copy()
    alerts["date"] = pd.to_datetime(alerts["date"], errors="coerce")
    selected_spreads["date"] = pd.to_datetime(selected_spreads["date"], errors="coerce")
    # The detector initializes this field to False when it has no spread input;
    # remove that placeholder so the matched spread review flag can be attached.
    alerts = alerts.drop(columns=["spread_review_flag"], errors="ignore")
    alerts = alerts.merge(
        selected_spreads,
        on="date",
        how="left",
        validate="one_to_one",
    )
    alerts["spread_review_flag"] = alerts["spread_review_flag"].eq(True)

    visualizer = ChartVisualizer(output_dir="output")
    dispersion_path = visualizer.plot_relative_dispersion(dispersion, state=clean_state)
    spread_path = visualizer.plot_price_trends_and_spreads(
        alerts, commodity=clean_commodity, state=clean_state,
    )
    report_path = build_report_path(Path("output"), clean_state, clean_commodity)
    generate_markdown_report(
        state=clean_state,
        commodity=clean_commodity,
        df_merged=merged,
        df_dispersion=dispersion,
        df_alerts=alerts,
        output_path=report_path,
        loader_stats=loader.load_stats,
        transform_stats=transformer.quality_summary,
        z_threshold=z_threshold,
        min_pct_change=min_pct_change,
        baseline_weeks=baseline_weeks,
        event_gap_days=event_gap_days,
    )

    logging.info("Pipeline execution complete. Generated outputs:")
    logging.info(" - Relative dispersion chart: %s", dispersion_path)
    logging.info(" - Price trend/spread chart: %s", spread_path)
    logging.info(" - Price alert report: %s", report_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="India Essential Commodities Price & Spread Intelligence Engine"
    )
    parser.add_argument("--state", type=str, default="Karnataka", help="Target Indian state.")
    parser.add_argument("--commodity", type=str, default="Tomato", help="Commodity for detailed analysis.")
    parser.add_argument("--z-threshold", type=float, default=DEFAULT_Z_THRESHOLD)
    parser.add_argument("--min-pct-change", type=float, default=DEFAULT_MIN_PCT_CHANGE)
    parser.add_argument(
        "--baseline-weeks", "--window", dest="baseline_weeks", type=int,
        default=DEFAULT_BASELINE_WEEKS,
        help="Number of prior same-weekday weekly changes in the baseline (default: 30).",
    )
    parser.add_argument(
        "--event-gap-days", type=int, default=DEFAULT_EVENT_GAP_DAYS,
        help="Maximum calendar-day distance between alert dates in one group (default: 3).",
    )
    args = parser.parse_args()
    run_pipeline(
        state=args.state,
        primary_commodity=args.commodity,
        z_threshold=args.z_threshold,
        min_pct_change=args.min_pct_change,
        baseline_weeks=args.baseline_weeks,
        event_gap_days=args.event_gap_days,
    )
