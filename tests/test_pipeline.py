import unittest
from pathlib import Path
import tempfile

import pandas as pd

from core.analytics import CommodityAnalytics
from core.transformer import DataTransformer, COMMODITY_UNIT_REGISTRY
from main import build_report_path


class UnitMappingTests(unittest.TestCase):
    def test_unit_registry_contains_expected_units(self):
        self.assertEqual(COMMODITY_UNIT_REGISTRY["Tomato"]["unit"], "₹/kg")
        self.assertEqual(COMMODITY_UNIT_REGISTRY["Milk"]["unit"], "₹/litre")
        self.assertEqual(COMMODITY_UNIT_REGISTRY["Tomato"]["divisor"], 100.0)
        self.assertEqual(COMMODITY_UNIT_REGISTRY["Milk"]["divisor"], 100.0)

    def test_transform_normalizes_units_and_cleans_milk_name(self):
        date = pd.Timestamp("2023-01-01")
        retail = pd.DataFrame({
            "date": [date, date],
            "state_name": ["Karnataka", "Karnataka"],
            "commodity": ["Tomato", "Milk @"],
            "retail_price_kg": [30.0, 40.0],
        })
        wholesale = pd.DataFrame({
            "date": [date, date],
            "state_name": ["Karnataka", "Karnataka"],
            "commodity": ["Tomato", "Milk @"],
            "wholesale_price_quintal": [2000.0, 5000.0],
        })

        result = DataTransformer(retail, wholesale).transform(
            state=" karnataka ", commodities=["tomato", "milk"]
        )
        by_commodity = result.set_index("commodity")

        self.assertAlmostEqual(by_commodity.loc["Tomato", "wholesale_price_normalized"], 20.0)
        self.assertAlmostEqual(by_commodity.loc["Tomato", "indicative_spread"], 10.0)
        self.assertEqual(by_commodity.loc["Milk", "normalized_unit"], "₹/litre")
        self.assertAlmostEqual(by_commodity.loc["Milk", "wholesale_price_normalized"], 50.0)
        self.assertAlmostEqual(by_commodity.loc["Milk", "indicative_spread"], -10.0)

    def test_duplicate_join_keys_are_aggregated_before_merge(self):
        date = pd.Timestamp("2023-01-01")
        retail = pd.DataFrame({
            "date": [date, date],
            "state_name": ["Karnataka", "Karnataka"],
            "commodity": ["Tomato", "Tomato"],
            "retail_price_kg": [30.0, 32.0],
        })
        wholesale = pd.DataFrame({
            "date": [date, date],
            "state_name": ["Karnataka", "Karnataka"],
            "commodity": ["Tomato", "Tomato"],
            "wholesale_price_quintal": [2000.0, 2200.0],
        })

        result = DataTransformer(retail, wholesale).transform(
            state="Karnataka", commodities=["Tomato"]
        )
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result.iloc[0]["retail_price_normalized"], 31.0)
        self.assertAlmostEqual(result.iloc[0]["wholesale_price_normalized"], 21.0)
        self.assertAlmostEqual(result.iloc[0]["indicative_spread"], 10.0)


class CalendarShockTests(unittest.TestCase):
    def test_seven_day_velocity_uses_calendar_days_across_gap(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-01-08"]),
            "commodity": ["Tomato", "Tomato"],
            "state_name": ["Karnataka", "Karnataka"],
            "normalized_unit": ["₹/kg", "₹/kg"],
            "retail_price_normalized": [10.0, 20.0],
        })
        result = CommodityAnalytics(df).detect_shocks("Tomato")
        target = result.loc[result["date"] == pd.Timestamp("2024-01-08")].iloc[0]
        self.assertAlmostEqual(target["price_diff_7d"], 10.0)

    def test_large_jump_after_stable_history_is_flagged(self):
        dates = pd.date_range("2024-01-01", periods=70, freq="D")
        prices = [10.0] * 45 + [30.0] * 25
        df = pd.DataFrame({
            "date": dates,
            "commodity": "Tomato",
            "state_name": "Karnataka",
            "normalized_unit": "₹/kg",
            "retail_price_normalized": prices,
        })
        result = CommodityAnalytics(df).detect_shocks(
            "Tomato", z_threshold=2.5, min_price_change=5.0, window=30
        )
        jump_day = pd.Timestamp("2024-02-15")  # index 45; first elevated price
        row = result.loc[result["date"] == jump_day].iloc[0]
        self.assertTrue(bool(row["is_alert"]))


class OutputPathTests(unittest.TestCase):
    def test_report_names_are_unique_by_state_and_commodity(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            tomato = build_report_path(output, "Karnataka", "Tomato")
            onion = build_report_path(output, "Karnataka", "Onion")
            tamil_nadu = build_report_path(output, "Tamil Nadu", "Tomato")
            self.assertEqual(tomato.name, "karnataka_tomato_shock_report.md")
            self.assertEqual(onion.name, "karnataka_onion_shock_report.md")
            self.assertEqual(tamil_nadu.name, "tamil_nadu_tomato_shock_report.md")
            self.assertEqual(len({tomato, onion, tamil_nadu}), 3)


if __name__ == "__main__":
    unittest.main()
