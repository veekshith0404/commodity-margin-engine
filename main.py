import argparse
import logging
from pathlib import Path
import pandas as pd
from core.loader import DataLoader
from core.transformer import DataTransformer, COMMODITY_UNIT_REGISTRY
from core.analytics import CommodityAnalytics
from core.visualizer import ChartVisualizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def build_report_path(output_dir: Path, state: str, commodity: str) -> Path:
    """Return a state/commodity-specific report path so runs never overwrite one another."""
    def slug(value: str) -> str:
        return "_".join(value.strip().lower().split())

    return output_dir / f"{slug(state)}_{slug(commodity)}_shock_report.md"

def generate_markdown_report(
    state: str,
    commodity: str,
    df_merged: pd.DataFrame,
    df_volatility: pd.DataFrame,
    df_shocks: pd.DataFrame,
    output_path: Path
) -> None:
    """Generates an executive statistical summary report in Markdown format."""
    min_date = df_merged['date'].min().strftime('%Y-%m-%d')
    max_date = df_merged['date'].max().strftime('%Y-%m-%d')
    total_obs = len(df_merged)
    
    unit = COMMODITY_UNIT_REGISTRY.get(commodity, {}).get("unit", "₹/kg")
    shock_sub = df_shocks[df_shocks['is_alert'] == True]
    total_alerts = len(shock_sub)

    report_lines = [
        f"# Statistical Price & Spread Intelligence Report: {state}",
        "",
        "## 1. Analysis Scope & Data Integrity",
        f"- **State Analyzed:** {state}",
        f"- **Primary Commodity Case Study:** {commodity} ({unit})",
        f"- **Reporting Period:** {min_date} to {max_date}",
        f"- **Total Matched Records (6 Basket Commodities):** {total_obs:,}",
        f"- **Matched observation period:** The period reflects records available after the retail/wholesale inner join.",
        f"- **Target Metric:** Normalized Indicative Price Spreads & Relative Volatility ($CV$)",
        "",
        "## 2. Verified Commodity Volatility Rankings",
        "| Commodity | Normalized Unit | Mean Price | Std Dev | Min Price | Max Price | Obs | CV (%) |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
    ]

    for _, row in df_volatility.iterrows():
        c_name = row['commodity']
        c_unit = COMMODITY_UNIT_REGISTRY.get(c_name, {}).get("unit", "₹/kg")
        report_lines.append(
            f"| **{c_name}** | {c_unit} | ₹{row['mean_price']:.2f} | ₹{row['std_price']:.2f} | "
            f"₹{row['min_price']:.2f} | ₹{row['max_price']:.2f} | {int(row['observations']):,} | **{row['cv_pct']:.2f}%** |"
        )

    report_lines.extend([
        "",
        "## 3. Statistical Price-Change Alert Summary",
        f"- **Selected Case Study:** {commodity}",
        "- **Methodology:** Calendar-aware 7-day velocity ($\\Delta P_{7d}$) vs. 30-day prior rolling baseline",
        "- **Z-Score Threshold:** $|Z| \\ge 2.5$",
        f"- **Minimum Velocity Threshold:** $|\\Delta P_{{7d}}| \\ge ₹5.00$ per {unit.split('/')[-1]}",
        f"- **Total Statistical Alerts Flagged:** **{total_alerts} days**",
        "",
        "## 4. Analytical Distinctions & Limitations",
        "- **Indicative Price Spread vs. Net Profit:** Spread equals `Retail Price - Wholesale Price` after unit normalization. It is a reported-price difference, NOT a direct estimate of retailer profit or an observed intermediary margin. Transport, storage, wastage, taxes and timing differences are not captured.",
        "- **Matched-observation limitation:** Volatility and alert calculations use records retained by the retail/wholesale inner join. Dates without a matched record are unavailable to the current analysis; this may affect sample counts and alert detection.",
        "- **Statistical Alerts vs. Supply Shocks:** Detected events represent statistically unusual price changes; they do not establish the cause. Verify with independent harvest, weather or transport evidence before attributing root cause.",
        ""
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    logging.info(f"Executive report generated successfully: {output_path}")

def run_pipeline(state: str, primary_commodity: str):
    clean_state = state.strip().title()
    clean_commodity = primary_commodity.strip().title()

    if clean_commodity not in COMMODITY_UNIT_REGISTRY:
        raise ValueError(
            f"Unsupported commodity '{clean_commodity}'. Supported commodities: {list(COMMODITY_UNIT_REGISTRY.keys())}"
        )

    logging.info(f"Starting Engine for State='{clean_state}', Commodity='{clean_commodity}'...")

    # 1. Ingestion
    loader = DataLoader(
        retail_path="data/daily-retail-prices-of-essential-commodities.csv",
        wholesale_path="data/state-level-daily-wholesale-price.csv"
    )
    df_retail = loader.load_retail()
    df_wholesale = loader.load_wholesale()

    # 2. Transformation
    basket = list(COMMODITY_UNIT_REGISTRY.keys())
    transformer = DataTransformer(df_retail, df_wholesale)
    df_merged = transformer.transform(state=clean_state, commodities=basket)

    if df_merged.empty:
        logging.error(f"No records available for state '{clean_state}'. Please verify state spelling and dataset coverage.")
        return

    available_commodities = set(df_merged["commodity"].astype(str).unique())
    if clean_commodity not in available_commodities:
        logging.error(
            f"No matched observations for commodity '{clean_commodity}' in '{clean_state}'. "
            f"Available commodities in this run: {sorted(available_commodities)}"
        )
        return

    # 3. Analytics
    analytics = CommodityAnalytics(df_merged)
    df_volatility = analytics.compute_volatility_table()

    print("\n" + "=" * 65)
    print(f"VOLATILITY RANKINGS: {clean_state.upper()} (6-COMMODITY BASKET)")
    print("=" * 65)
    print(df_volatility.to_string(index=False))
    print("=" * 65 + "\n")

    # Calendar-aware shock detection
    df_shocks = analytics.detect_shocks(commodity=clean_commodity, z_threshold=2.5, min_price_change=5.0)

    # 4. Visualizations
    visualizer = ChartVisualizer(output_dir="output")
    vol_path = visualizer.plot_volatility_ranking(df_volatility, state=clean_state)
    shock_path = visualizer.plot_price_spread_and_shocks(df_shocks, commodity=clean_commodity, state=clean_state)

    # 5. Executive Report Generation
    report_path = build_report_path(Path("output"), clean_state, clean_commodity)
    generate_markdown_report(
        state=clean_state,
        commodity=clean_commodity,
        df_merged=df_merged,
        df_volatility=df_volatility,
        df_shocks=df_shocks,
        output_path=report_path
    )

    logging.info("Pipeline execution complete! Generated outputs:")
    logging.info(f" - Volatility Chart: {vol_path}")
    logging.info(f" - Price & Spread Chart: {shock_path}")
    logging.info(f" - Executive Markdown Report: {report_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="India Essential Commodities Price & Margin Engine")
    parser.add_argument("--state", type=str, default="Karnataka", help="Target Indian State (e.g. Karnataka, Maharashtra)")
    parser.add_argument("--commodity", type=str, default="Tomato", help="Target commodity for detailed analysis")
    args = parser.parse_args()

    run_pipeline(state=args.state, primary_commodity=args.commodity)