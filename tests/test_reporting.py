import tempfile
import unittest
from pathlib import Path

import pandas as pd

from core.analytics import CommodityAnalytics
from core.transformer import DataTransformer
from core.visualizer import ChartVisualizer
from main import build_report_path, generate_markdown_report


class ReportingAndChartTests(unittest.TestCase):
    def make_matched_data(self):
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        prices = [10.0 + 0.03 * i + (i % 5) * 0.02 for i in range(100)]
        retail = pd.DataFrame({
            "date": dates,
            "state_name": "Karnataka",
            "commodity": "Tomato",
            "retail_price_kg": prices,
        })
        wholesale = pd.DataFrame({
            "date": dates,
            "state_name": "Karnataka",
            "commodity": "Tomato",
            "wholesale_price_quintal": [900.0] * 100,
        })
        transformer = DataTransformer(retail, wholesale)
        merged = transformer.transform("Karnataka", ["Tomato"])
        return merged, transformer.quality_summary

    def test_report_includes_threshold_alert_counts_and_quality_rows(self):
        merged, quality = self.make_matched_data()
        analytics = CommodityAnalytics(merged)
        dispersion = analytics.compute_volatility_table()
        alerts = analytics.detect_price_change_alerts(
            "Tomato", min_pct_change=0.0, window_weeks=5
        )
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "report.md"
            generate_markdown_report(
                state="Karnataka",
                commodity="Tomato",
                df_merged=merged,
                df_dispersion=dispersion,
                df_alerts=alerts,
                output_path=report_path,
                loader_stats={
                    "retail": {
                        "source_rows": 100, "retained_rows": 100,
                        "excluded_rows": 0, "invalid_dates": 0,
                        "blank_prices": 0, "non_numeric_prices": 0,
                        "non_finite_prices": 0, "non_positive_prices": 0,
                        "missing_state_or_commodity": 0,
                    },
                    "wholesale": {
                        "source_rows": 100, "retained_rows": 100,
                        "excluded_rows": 0, "invalid_dates": 0,
                        "blank_prices": 0, "non_numeric_prices": 0,
                        "non_finite_prices": 0, "non_positive_prices": 0,
                        "missing_state_or_commodity": 0,
                    },
                },
                transform_stats=quality,
            )
            text = report_path.read_text(encoding="utf-8")
            self.assertIn("Exact seven-calendar-day comparison", text)
            self.assertIn("Log price change", text)
            self.assertIn("Selected commodity retail-key match coverage", text)
            self.assertIn("Alerts associated with the isolated-outlier heuristic", text)
            self.assertIn("Negative spread review flags", text)
            self.assertIn("Non-positive prices", text)
            self.assertIn("Infinite Z-score observations", text)
            self.assertIn("Retail-key match coverage", text)
            self.assertIn("not independently confirmed market events", text)
            self.assertIn(
                f"- **Alert days:** {int(alerts['is_alert'].sum()):,}",
                text,
            )
            expected_groups = int(
                alerts.loc[alerts["is_alert"], "alert_event_id"].nunique()
            )
            self.assertIn(f"- **Grouped alert periods:** {expected_groups:,}", text)

    def test_visualizer_creates_both_expected_charts(self):
        merged, _ = self.make_matched_data()
        analytics = CommodityAnalytics(merged)
        dispersion = analytics.compute_volatility_table()
        alerts = analytics.detect_price_change_alerts(
            "Tomato", min_pct_change=0.0, window_weeks=5
        )
        with tempfile.TemporaryDirectory() as tmp:
            visualizer = ChartVisualizer(tmp)
            dispersion_path = visualizer.plot_relative_dispersion(
                dispersion, state="Karnataka"
            )
            price_path = visualizer.plot_price_trends_and_spreads(
                alerts, commodity="Tomato", state="Karnataka"
            )
            self.assertTrue(dispersion_path.exists())
            self.assertTrue(price_path.exists())
            self.assertEqual(
                dispersion_path.name, "karnataka_relative_dispersion.png"
            )
            self.assertEqual(
                price_path.name, "karnataka_tomato_price_alerts.png"
            )

    def test_report_requires_nonempty_matched_data(self):
        empty = pd.DataFrame()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "empty matched dataset"):
                generate_markdown_report(
                    state="Karnataka", commodity="Tomato",
                    df_merged=empty, df_dispersion=empty, df_alerts=empty,
                    output_path=Path(tmp) / "report.md",
                )


if __name__ == "__main__":
    unittest.main()
