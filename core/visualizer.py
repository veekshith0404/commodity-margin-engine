import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


class ChartVisualizer:
    """Create descriptive CV, retail/wholesale trend, and spread charts."""

    def __init__(self, output_dir: str | Path = "output") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def plot_relative_dispersion(
        self,
        df_dispersion: pd.DataFrame,
        state: str = "Karnataka",
    ) -> Path:
        """Plot CV while explicitly describing it as overall price dispersion."""
        if df_dispersion.empty:
            raise ValueError("Cannot plot relative dispersion from an empty table.")

        required = {"commodity", "cv_pct"}
        missing = required - set(df_dispersion.columns)
        if missing:
            raise ValueError(
                f"Dispersion table is missing columns: {sorted(missing)}"
            )

        valid = df_dispersion.dropna(subset=["cv_pct"]).copy()
        if valid.empty:
            raise ValueError("No valid CV values are available to plot.")

        clean_state = state.strip().title()
        plotted = valid.sort_values("cv_pct", ascending=True)
        fig, ax = plt.subplots(figsize=(10, 5))
        bars = ax.barh(
            plotted["commodity"].astype(str),
            plotted["cv_pct"],
            color="#2b5c8f",
            edgecolor="#1a365d",
            linewidth=0.8,
        )
        label_offset = max(float(plotted["cv_pct"].max()) * 0.015, 0.1)
        for bar in bars:
            value = bar.get_width()
            ax.text(
                value + label_offset,
                bar.get_y() + bar.get_height() / 2,
                f"{value:.1f}%",
                va="center",
                ha="left",
                fontsize=9,
                color="#1a202c",
                weight="bold",
            )

        ax.set_title(
            f"Overall Relative Price Dispersion: {clean_state}",
            fontsize=13,
            weight="bold",
            pad=12,
        )
        ax.set_xlabel("Coefficient of Variation (%) = Std Dev / Mean × 100")
        ax.text(
            0.0,
            -0.18,
            "CV pools prices across the available period; long-term trends can contribute.",
            transform=ax.transAxes,
            fontsize=9,
            color="#4a5568",
            va="top",
        )
        ax.grid(axis="x", linestyle="--", alpha=0.6)
        ax.set_xlim(0, max(float(plotted["cv_pct"].max()) * 1.2, 10.0))
        fig.tight_layout()

        path = self.output_dir / f"{clean_state.lower().replace(' ', '_')}_relative_dispersion.png"
        fig.savefig(path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        logging.info("Saved relative-dispersion chart: %s", path)
        return path

    def plot_price_trends_and_spreads(
        self,
        df_alerts: pd.DataFrame,
        commodity: str,
        state: str,
    ) -> Path:
        """Plot reported prices, two-sided alert markers and indicative spreads."""
        if df_alerts.empty:
            raise ValueError("Cannot plot price trends from an empty alert result.")

        required = {
            "date",
            "retail_price_normalized",
            "wholesale_price_normalized",
            "indicative_spread",
            "is_alert",
        }
        missing = required - set(df_alerts.columns)
        if missing:
            raise ValueError(
                f"Price-alert data is missing columns: {sorted(missing)}"
            )

        state_clean = state.strip().title()
        commodity_clean = commodity.strip().title()
        plot_df = df_alerts.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"], errors="coerce")
        plot_df = plot_df.dropna(subset=["date"]).sort_values("date").set_index("date")
        if plot_df.empty:
            raise ValueError("No valid dates are available to plot.")
        if plot_df.index.has_duplicates:
            raise ValueError("Duplicate dates found in chart data.")

        if "normalized_unit" in plot_df and plot_df["normalized_unit"].notna().any():
            unit = plot_df["normalized_unit"].dropna().iloc[0]
        else:
            unit = "₹/kg"

        alerts = plot_df["is_alert"].fillna(False).astype(bool)
        negative = plot_df.get(
            "spread_review_flag", plot_df["indicative_spread"] < -1e-6
        ).fillna(False).astype(bool)
        grouped_episodes = (
            int(plot_df.loc[alerts, "alert_event_id"].nunique())
            if "alert_event_id" in plot_df.columns else 0
        )

        fig, (ax_price, ax_spread) = plt.subplots(
            2,
            1,
            figsize=(12, 8),
            sharex=True,
            gridspec_kw={"height_ratios": [2, 1]},
        )
        ax_price.plot(
            plot_df.index,
            plot_df["retail_price_normalized"],
            label=f"Retail price ({unit})",
            color="#c0392b",
            linewidth=1.5,
        )
        ax_price.plot(
            plot_df.index,
            plot_df["wholesale_price_normalized"],
            label=f"Normalized wholesale price ({unit})",
            color="#2980b9",
            linewidth=1.2,
            linestyle="--",
        )
        if alerts.any():
            ax_price.scatter(
                plot_df.index[alerts],
                plot_df.loc[alerts, "retail_price_normalized"],
                color="black",
                s=25,
                zorder=5,
                label="Statistical alert (increase or decrease)",
            )
        ax_price.set_title(
            f"{state_clean}: {commodity_clean} Price Trends and Statistical Alerts",
            fontsize=13,
            weight="bold",
            pad=10,
        )
        ax_price.set_ylabel(f"Price ({unit})")
        ax_price.legend(loc="upper left", frameon=True)
        ax_price.grid(True, linestyle="--", alpha=0.5)
        ax_price.text(
            0.99,
            0.98,
            f"Alert days: {int(alerts.sum())} | Grouped alert periods: {grouped_episodes}",
            transform=ax_price.transAxes,
            ha="right",
            va="top",
            fontsize=9,
            bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
        )

        spread = plot_df["indicative_spread"]
        dates = plot_df.index
        positive_mask = (spread >= 0).fillna(False)
        negative_mask = (spread < -1e-6).fillna(False)
        ax_spread.fill_between(
            dates, spread, 0, where=positive_mask,
            color="#27ae60", alpha=0.30, label="Non-negative spread",
        )
        ax_spread.fill_between(
            dates, spread, 0, where=negative_mask,
            color="#e74c3c", alpha=0.30,
            label="Negative spread — review",
        )
        ax_spread.plot(dates, spread, color="#1e8449", linewidth=0.9)
        ax_spread.axhline(0, color="gray", linewidth=0.8, linestyle="--")
        if negative.any():
            ax_spread.scatter(
                dates[negative],
                spread.loc[negative],
                marker="x",
                color="#922b21",
                s=18,
                zorder=4,
                label="Negative spread observation",
            )
        ax_spread.set_ylabel(f"Indicative spread ({unit})")
        ax_spread.set_xlabel("Date")
        ax_spread.legend(loc="upper left", frameon=True)
        ax_spread.grid(True, linestyle="--", alpha=0.5)

        fig.tight_layout()
        path = self.output_dir / (
            f"{state_clean.lower().replace(' ', '_')}_"
            f"{commodity_clean.lower().replace(' ', '_')}_price_alerts.png"
        )
        fig.savefig(path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        logging.info("Saved price-trend and spread chart: %s", path)
        return path
