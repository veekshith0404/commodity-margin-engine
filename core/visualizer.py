import logging
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class ChartVisualizer:
    """
    Renders publication-ready, gap-safe visualizations for volatility rankings
    and multi-panel commodity price trends with indicative spreads.
    """
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_volatility_ranking(self, df_volatility: pd.DataFrame, state: str = "Karnataka") -> Path:
        """Horizontal bar chart showing relative volatility (CV%) across commodities."""
        fig, ax = plt.subplots(figsize=(10, 5))
        df_sorted = df_volatility.sort_values(by='cv_pct', ascending=True)

        bars = ax.barh(
            df_sorted['commodity'].astype(str),
            df_sorted['cv_pct'],
            color='#2b5c8f',
            edgecolor='#1a365d',
            linewidth=0.8
        )
        
        for bar in bars:
            width = bar.get_width()
            ax.text(
                width + 0.8,
                bar.get_y() + bar.get_height() / 2,
                f"{width:.1f}%",
                va='center',
                ha='left',
                fontsize=9,
                color='#1a202c',
                weight='bold'
            )

        clean_state = state.strip().title()
        ax.set_title(f"Commodity Relative Volatility: {clean_state} (Coefficient of Variation %)", fontsize=13, weight='bold', pad=12)
        ax.set_xlabel("CV (%) = (Std Dev / Mean) * 100", fontsize=10)
        ax.grid(axis='x', linestyle='--', alpha=0.6)
        ax.set_xlim(0, max(df_sorted['cv_pct'].max() * 1.15, 10))

        plt.tight_layout()
        save_name = f"{clean_state.lower().replace(' ', '_')}_volatility_ranking.png"
        save_path = self.output_dir / save_name
        plt.savefig(save_path, dpi=300)
        plt.close()
        logging.info(f"Saved volatility chart: {save_path}")
        return save_path

    def plot_price_spread_and_shocks(self, df_shocks: pd.DataFrame, commodity: str, state: str) -> Path:
        """
        Dual-panel commodity price trend and indicative spread visualization.
        Missing reporting dates appear as natural gaps without artificial interpolation.
        """
        clean_state = state.strip().title()
        clean_commodity = commodity.strip().title()
        df_plot = df_shocks.sort_values('date').set_index('date')

        unit = df_plot['normalized_unit'].dropna().iloc[0] if 'normalized_unit' in df_plot.columns and not df_plot['normalized_unit'].dropna().empty else "₹/kg"

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True, gridspec_kw={'height_ratios': [2, 1]})

        # Panel 1: Retail vs. Wholesale Price Curves
        ax1.plot(df_plot.index, df_plot['retail_price_normalized'], label=f'Retail Price ({unit})', color='#c0392b', lw=1.6)
        ax1.plot(df_plot.index, df_plot['wholesale_price_normalized'], label=f'Wholesale Price ({unit})', color='#2980b9', lw=1.2, linestyle='--')

        # Statistical Price-Change Alerts
        alerts = df_plot[df_plot['is_alert'] == True]
        if not alerts.empty:
            ax1.scatter(alerts.index, alerts['retail_price_normalized'], color='black', s=35, zorder=5, label='Statistical Price-Change Alert')

        ax1.set_title(f"{clean_state}: {clean_commodity} Retail vs. Wholesale Price & Detected Alerts", fontsize=13, weight='bold', pad=10)
        ax1.set_ylabel(f"Price ({unit})", fontsize=10)
        ax1.legend(loc='upper left', frameon=True)
        ax1.grid(True, linestyle='--', alpha=0.5)

        # Panel 2: Indicative Price Spread (Retail - Wholesale)
        spread = df_plot['indicative_spread']
        ax2.fill_between(df_plot.index, spread, 0, where=(spread >= 0), color='#27ae60', alpha=0.35, label='Positive Spread')
        ax2.fill_between(df_plot.index, spread, 0, where=(spread < 0), color='#e74c3c', alpha=0.35, label='Negative Spread')
        ax2.plot(df_plot.index, spread, color='#1e8449', lw=0.9)
        ax2.axhline(0, color='gray', lw=0.8, linestyle='--')

        ax2.set_ylabel(f"Indicative Spread ({unit})", fontsize=10)
        ax2.set_xlabel("Date", fontsize=10)
        ax2.legend(loc='upper left', frameon=True)
        ax2.grid(True, linestyle='--', alpha=0.5)

        plt.tight_layout()
        save_name = f"{clean_state.lower().replace(' ', '_')}_{clean_commodity.lower().replace(' ', '_')}_spread_shocks.png"
        save_path = self.output_dir / save_name
        plt.savefig(save_path, dpi=300)
        plt.close()
        logging.info(f"Saved price & spread chart: {save_path}")
        return save_path