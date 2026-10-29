import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from core.analytics import CommodityAnalytics
from core.transformer import (
    COMMODITY_UNIT_REGISTRY,
    DataTransformer,
    SPREAD_NUMERICAL_TOLERANCE,
)
from main import build_report_path


def make_price_frame(prices, start="2024-01-01", unit="₹/kg"):
    return pd.DataFrame({
        "date": pd.date_range(start, periods=len(prices), freq="D"),
        "commodity": "Tomato",
        "state_name": "Karnataka",
        "normalized_unit": unit,
        "retail_price_normalized": prices,
    })


class UnitAndTransformTests(unittest.TestCase):
    def test_registry_has_explicit_six_commodity_units(self):
        self.assertEqual(set(COMMODITY_UNIT_REGISTRY), {
            "Tomato", "Onion", "Potato", "Rice", "Wheat", "Milk"
        })
        self.assertEqual(COMMODITY_UNIT_REGISTRY["Tomato"]["unit"], "₹/kg")
        self.assertEqual(COMMODITY_UNIT_REGISTRY["Milk"]["unit"], "₹/litre")

    def test_transform_normalizes_tomato_and_milk_units(self):
        date = pd.Timestamp("2023-01-01")
        retail = pd.DataFrame({
            "date": [date, date, date],
            "state_name": ["Karnataka", "Karnataka", "Karnataka"],
            "commodity": ["Tomato", "Milk @", "Rice"],
            "retail_price_kg": [30.0, 40.0, 45.0],
        })
        wholesale = pd.DataFrame({
            "date": [date, date, date],
            "state_name": ["Karnataka", "Karnataka", "Karnataka"],
            "commodity": ["Tomato", "Milk @", "Rice"],
            "wholesale_price_quintal": [2000.0, 5000.0, 3000.0],
        })
        transformer = DataTransformer(retail, wholesale)
        result = transformer.transform(" karnataka ", ["tomato", "milk", "rice"])
        by_commodity = result.set_index("commodity")
        self.assertAlmostEqual(by_commodity.loc["Tomato", "wholesale_price_normalized"], 20.0)
        self.assertAlmostEqual(by_commodity.loc["Tomato", "indicative_spread"], 10.0)
        self.assertEqual(by_commodity.loc["Milk", "normalized_unit"], "₹/litre")
        self.assertAlmostEqual(by_commodity.loc["Milk", "wholesale_price_normalized"], 50.0)
        self.assertAlmostEqual(by_commodity.loc["Milk", "indicative_spread"], -10.0)
        self.assertTrue(bool(by_commodity.loc["Milk", "spread_review_flag"]))
        self.assertAlmostEqual(by_commodity.loc["Rice", "wholesale_price_normalized"], 30.0)
        self.assertAlmostEqual(by_commodity.loc["Rice", "indicative_spread"], 15.0)

    def test_known_state_name_aliases_are_normalized_to_match(self):
        date = pd.Timestamp("2024-01-01")
        retail = pd.DataFrame({
            "date": [date, date],
            "state_name": ["Andaman and Nicobar", "DNH and DD"],
            "commodity": ["Tomato", "Tomato"],
            "retail_price_kg": [20.0, 30.0],
        })
        wholesale = pd.DataFrame({
            "date": [date, date],
            "state_name": [
                "Andaman And Nicobar Islands",
                "The Dadra And Nagar Haveli And Daman And Diu",
            ],
            "commodity": ["Tomato", "Tomato"],
            "wholesale_price_quintal": [1500.0, 2500.0],
        })
        transformer = DataTransformer(retail, wholesale)
        andaman = transformer.transform("Andaman and Nicobar", ["Tomato"])
        dnh = transformer.transform("DNH and DD", ["Tomato"])
        self.assertEqual(len(andaman), 1)
        self.assertEqual(len(dnh), 1)

    def test_retail_only_series_keeps_rows_without_wholesale_matches(self):
        dates = pd.date_range("2024-01-01", periods=60, freq="D")
        prices = [100.0] * 60
        prices[42] = 120.0
        retail = pd.DataFrame({
            "date": dates, "state_name": "Karnataka", "commodity": "Tomato",
            "retail_price_kg": prices,
        })
        # Wholesale only exists on the first date; it must not gate later retail alerts.
        wholesale = pd.DataFrame({
            "date": [dates[0]], "state_name": ["Karnataka"],
            "commodity": ["Tomato"], "wholesale_price_quintal": [10000.0],
        })
        transformer = DataTransformer(retail, wholesale)
        retail_series = transformer.prepare_retail_series("Karnataka", "Tomato")
        self.assertEqual(len(retail_series), 60)
        self.assertEqual(retail_series["retail_price_normalized"].notna().sum(), 60)
        alerts = CommodityAnalytics(retail_series).detect_price_change_alerts(
            "Tomato", z_threshold=2.5, min_pct_change=10.0, window_weeks=5
        )
        target = alerts.loc[alerts["date"] == dates[42]].iloc[0]
        self.assertTrue(bool(target["is_alert"]))

    def test_duplicate_keys_are_aggregated_before_merge(self):
        date = pd.Timestamp("2023-01-01")
        retail = pd.DataFrame({
            "date": [date, date], "state_name": ["Karnataka"] * 2,
            "commodity": ["Tomato"] * 2, "retail_price_kg": [30.0, 32.0],
        })
        wholesale = pd.DataFrame({
            "date": [date, date], "state_name": ["Karnataka"] * 2,
            "commodity": ["Tomato"] * 2,
            "wholesale_price_quintal": [2000.0, 2200.0],
        })
        transformer = DataTransformer(retail, wholesale)
        result = transformer.transform("Karnataka", ["Tomato"])
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result.iloc[0]["retail_price_normalized"], 31.0)
        self.assertAlmostEqual(result.iloc[0]["wholesale_price_normalized"], 21.0)
        self.assertAlmostEqual(result.iloc[0]["indicative_spread"], 10.0)

    def test_transform_filters_invalid_prices_and_reports_counts(self):
        dates = pd.date_range("2024-01-01", periods=4, freq="D")
        retail = pd.DataFrame({
            "date": dates, "state_name": ["Karnataka"] * 4,
            "commodity": ["Tomato"] * 4,
            "retail_price_kg": [20.0, 0.0, -1.0, np.inf],
        })
        wholesale = pd.DataFrame({
            "date": dates, "state_name": ["Karnataka"] * 4,
            "commodity": ["Tomato"] * 4,
            "wholesale_price_quintal": [1500.0] * 4,
        })
        transformer = DataTransformer(retail, wholesale)
        result = transformer.transform("Karnataka", ["Tomato"])
        self.assertEqual(len(result), 1)
        self.assertEqual(transformer.quality_summary["retail_invalid"]["excluded_rows"], 3)
        self.assertTrue(np.isfinite(result["indicative_spread"]).all())

    def test_unsupported_commodity_is_rejected(self):
        retail = pd.DataFrame({"date": [], "state_name": [], "commodity": [], "retail_price_kg": []})
        wholesale = pd.DataFrame({"date": [], "state_name": [], "commodity": [], "wholesale_price_quintal": []})
        with self.assertRaisesRegex(ValueError, "Unsupported commodity"):
            DataTransformer(retail, wholesale).transform("Karnataka", ["Tea"])

    def test_missing_transform_columns_are_reported_clearly(self):
        retail = pd.DataFrame({"date": [], "state_name": [], "commodity": []})
        wholesale = pd.DataFrame({"date": [], "state_name": [], "commodity": [], "wholesale_price_quintal": []})
        with self.assertRaisesRegex(ValueError, "Retail input is missing"):
            DataTransformer(retail, wholesale).transform("Karnataka", ["Tomato"])

    def test_no_overlap_returns_empty_and_zero_coverage(self):
        retail = pd.DataFrame({
            "date": [pd.Timestamp("2024-01-01")], "state_name": ["Karnataka"],
            "commodity": ["Tomato"], "retail_price_kg": [20.0],
        })
        wholesale = pd.DataFrame({
            "date": [pd.Timestamp("2024-01-02")], "state_name": ["Karnataka"],
            "commodity": ["Tomato"], "wholesale_price_quintal": [1500.0],
        })
        transformer = DataTransformer(retail, wholesale)
        self.assertTrue(transformer.transform("Karnataka", ["Tomato"]).empty)
        self.assertEqual(transformer.quality_summary["matched_rows"], 0)

    def test_all_invalid_prices_on_one_side_return_empty_without_merge_error(self):
        date = pd.Timestamp("2024-01-01")
        valid_retail = pd.DataFrame({
            "date": [date], "state_name": ["Karnataka"],
            "commodity": ["Tomato"], "retail_price_kg": [20.0],
        })
        valid_wholesale = pd.DataFrame({
            "date": [date], "state_name": ["Karnataka"],
            "commodity": ["Tomato"], "wholesale_price_quintal": [2000.0],
        })
        invalid_retail = valid_retail.copy()
        invalid_retail["retail_price_kg"] = 0.0
        invalid_wholesale = valid_wholesale.copy()
        invalid_wholesale["wholesale_price_quintal"] = -1.0

        with self.subTest(invalid_side="retail"):
            transformer = DataTransformer(invalid_retail, valid_wholesale)
            result = transformer.transform("Karnataka", ["Tomato"])
            self.assertTrue(result.empty)
            self.assertEqual(transformer.quality_summary["matched_rows"], 0)
            self.assertEqual(
                transformer.quality_summary["retail_invalid"]["non_positive_prices"],
                1,
            )

        with self.subTest(invalid_side="wholesale"):
            transformer = DataTransformer(valid_retail, invalid_wholesale)
            result = transformer.transform("Karnataka", ["Tomato"])
            self.assertTrue(result.empty)
            self.assertEqual(transformer.quality_summary["matched_rows"], 0)
            self.assertEqual(
                transformer.quality_summary["wholesale_invalid"]["non_positive_prices"],
                1,
            )

    def test_spread_review_tolerance_boundary(self):
        date = pd.Timestamp("2024-01-01")
        for wholesale_price, expected_flag in (
            (2500.00011, True),   # normalized spread ≈ -₹0.0000011
            (2500.00009, False),  # normalized spread ≈ -₹0.0000009
        ):
            with self.subTest(wholesale_price=wholesale_price):
                retail = pd.DataFrame({
                    "date": [date], "state_name": ["Karnataka"],
                    "commodity": ["Tomato"], "retail_price_kg": [25.0],
                })
                wholesale = pd.DataFrame({
                    "date": [date], "state_name": ["Karnataka"],
                    "commodity": ["Tomato"],
                    "wholesale_price_quintal": [wholesale_price],
                })
                result = DataTransformer(retail, wholesale).transform(
                    "Karnataka", ["Tomato"]
                )
                self.assertEqual(bool(result.iloc[0]["spread_review_flag"]), expected_flag)

    def test_tiny_float_residue_is_not_flagged_as_material_negative_spread(self):
        date = pd.Timestamp("2024-01-01")
        retail = pd.DataFrame({
            "date": [date], "state_name": ["Karnataka"],
            "commodity": ["Tomato"], "retail_price_kg": [25.1],
        })
        wholesale = pd.DataFrame({
            "date": [date], "state_name": ["Karnataka"],
            "commodity": ["Tomato"], "wholesale_price_quintal": [2510.0],
        })
        result = DataTransformer(retail, wholesale).transform("Karnataka", ["Tomato"])
        self.assertGreaterEqual(result.iloc[0]["indicative_spread"], -SPREAD_NUMERICAL_TOLERANCE)
        self.assertFalse(bool(result.iloc[0]["spread_review_flag"]))


class AnalyticsTests(unittest.TestCase):
    def test_cv_is_calculated_from_available_observations(self):
        df = pd.DataFrame({
            "commodity": ["Tomato", "Tomato"],
            "retail_price_normalized": [10.0, 20.0],
        })
        row = CommodityAnalytics(df).compute_volatility_table().iloc[0]
        expected_std = np.std([10.0, 20.0], ddof=1)
        self.assertAlmostEqual(row["mean_price"], 15.0)
        self.assertAlmostEqual(row["std_price"], expected_std)
        self.assertAlmostEqual(row["cv_pct"], expected_std / 15.0 * 100)

    def test_exact_seven_calendar_day_change_is_calculated(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-01-08"]),
            "commodity": ["Tomato", "Tomato"],
            "state_name": ["Karnataka", "Karnataka"],
            "normalized_unit": ["₹/kg", "₹/kg"],
            "retail_price_normalized": [10.0, 20.0],
        })
        result = CommodityAnalytics(df).detect_price_change_alerts(
            "Tomato", window_weeks=5, min_pct_change=0.0
        )
        row = result.loc[result["date"] == pd.Timestamp("2024-01-08")].iloc[0]
        self.assertEqual(row["reference_price_7d"], 10.0)
        self.assertAlmostEqual(row["price_diff_7d"], 10.0)
        self.assertAlmostEqual(row["price_change_pct_7d"], 100.0)
        self.assertAlmostEqual(row["price_change_log_7d"], np.log(2.0))

    def test_missing_exact_reference_does_not_get_forward_filled(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-01-10"]),
            "commodity": ["Tomato", "Tomato"],
            "state_name": ["Karnataka", "Karnataka"],
            "normalized_unit": ["₹/kg", "₹/kg"],
            "retail_price_normalized": [10.0, 20.0],
        })
        result = CommodityAnalytics(df).detect_price_change_alerts(
            "Tomato", window_weeks=5, min_pct_change=0.0
        )
        row = result.loc[result["date"] == pd.Timestamp("2024-01-10")].iloc[0]
        self.assertTrue(pd.isna(row["reference_price_7d"]))
        self.assertTrue(pd.isna(row["price_diff_7d"]))
        self.assertFalse(bool(row["is_alert"]))

    def test_z_score_matches_hand_calculation_using_prior_same_weekday_weeks(self):
        dates = pd.date_range("2024-01-01", periods=120, freq="D")
        prices = [100.0 + 0.12 * i + 0.8 * np.sin(i * 0.37) for i in range(120)]
        prices = [price + (20.0 if i >= 100 else 0.0) for i, price in enumerate(prices)]
        df = pd.DataFrame({
            "date": dates, "commodity": "Tomato", "state_name": "Karnataka",
            "normalized_unit": "₹/kg", "retail_price_normalized": prices,
        })
        result = CommodityAnalytics(df).detect_price_change_alerts(
            "Tomato", z_threshold=2.5, min_pct_change=0.0, window_weeks=10
        )
        target_date = dates[100]
        row = result.loc[result["date"] == target_date].iloc[0]
        prior_changes = result.loc[
            (result["date"] < target_date)
            & (result["date"].dt.day_of_week == target_date.day_of_week),
            "price_change_log_7d",
        ].dropna().tail(10)
        expected = (row["price_change_log_7d"] - prior_changes.mean()) / prior_changes.std(ddof=1)
        self.assertEqual(len(prior_changes), 10)
        self.assertTrue(np.isfinite(row["z_score"]))
        self.assertAlmostEqual(row["z_score"], expected, places=8)

    def test_percentage_gate_blocks_large_z_when_change_is_too_small(self):
        dates = pd.date_range("2024-01-01", periods=130, freq="D")
        prices = [100.0 + 0.02 * i + 0.03 * (i % 4) for i in range(130)]
        prices = [price + (1.0 if i >= 100 else 0.0) for i, price in enumerate(prices)]
        df = pd.DataFrame({
            "date": dates, "commodity": "Tomato", "state_name": "Karnataka",
            "normalized_unit": "₹/kg", "retail_price_normalized": prices,
        })
        result = CommodityAnalytics(df).detect_price_change_alerts(
            "Tomato", z_threshold=2.5, min_pct_change=10.0, window_weeks=10
        )
        row = result.loc[result["date"] == dates[100]].iloc[0]
        self.assertGreaterEqual(abs(row["z_score"]), 2.5)
        self.assertLess(abs(row["price_change_pct_7d"]), 10.0)
        self.assertFalse(bool(row["is_alert"]))

    def test_percentage_gate_flags_relative_increase_below_five_currency_units(self):
        dates = pd.date_range("2024-01-01", periods=80, freq="D")
        prices = [10.0 + (i % 4) * 0.05 for i in range(80)]
        prices = [price + (1.5 if i >= 45 else 0.0) for i, price in enumerate(prices)]
        df = pd.DataFrame({
            "date": dates, "commodity": "Tomato", "state_name": "Karnataka",
            "normalized_unit": "₹/kg", "retail_price_normalized": prices,
        })
        result = CommodityAnalytics(df).detect_price_change_alerts(
            "Tomato", min_pct_change=10.0, window_weeks=8
        )
        row = result.loc[result["date"] == dates[45]].iloc[0]
        self.assertLess(abs(row["price_diff_7d"]), 5.0)
        self.assertGreaterEqual(abs(row["price_change_pct_7d"]), 10.0)
        self.assertTrue(bool(row["is_alert"]))

    def test_rolling_baseline_requires_five_prior_weekly_changes(self):
        dates = pd.date_range("2024-01-01", periods=29, freq="D")
        prices = [10.0 + 0.02 * i + (i % 3) * 0.1 for i in range(29)]
        df = make_price_frame(prices)
        df["date"] = dates
        result = CommodityAnalytics(df).detect_price_change_alerts(
            "Tomato", min_pct_change=0.0, window_weeks=8
        )
        # Mondays at indices 7, 14 and 21 are the only three prior valid
        # seven-day changes for the Monday at index 28. Five are required.
        target = result.loc[result["date"] == dates[28]].iloc[0]
        self.assertTrue(pd.isna(target["z_score"]))
        self.assertFalse(bool(target["is_alert"]))

    def test_zero_variance_history_has_explicit_infinite_z_score(self):
        dates = pd.date_range("2024-01-01", periods=90, freq="D")
        prices = [10.0] * 45 + [12.0] * 45
        df = make_price_frame(prices)
        df["date"] = dates
        result = CommodityAnalytics(df).detect_price_change_alerts(
            "Tomato", min_pct_change=10.0, window_weeks=8
        )
        row = result.loc[result["date"] == dates[45]].iloc[0]
        self.assertTrue(np.isinf(row["z_score"]))
        self.assertTrue(bool(row["is_alert"]))

    def test_invalid_prices_are_rejected_by_analytics(self):
        for invalid in (0.0, -1.0, np.inf, -np.inf, "not-a-number"):
            with self.subTest(invalid=invalid):
                df = make_price_frame([10.0, 11.0, 12.0])
                df["retail_price_normalized"] = pd.Series(
                    [10.0, invalid, 12.0], dtype="object"
                )
                with self.assertRaisesRegex(ValueError, "invalid prices"):
                    CommodityAnalytics(df).detect_price_change_alerts("Tomato")

    def test_duplicate_dates_are_rejected(self):
        df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "commodity": ["Tomato", "Tomato"],
            "retail_price_normalized": [10.0, 11.0],
        })
        with self.assertRaisesRegex(ValueError, "duplicate dates"):
            CommodityAnalytics(df).detect_price_change_alerts("Tomato")

    def test_parameter_validation(self):
        df = make_price_frame([10.0] * 20)
        cases = [
            ({"z_threshold": np.nan}, "z_threshold"),
            ({"min_pct_change": np.inf}, "min_pct_change"),
            ({"window_weeks": 4}, "window_weeks"),
            ({"window_weeks": 5.5}, "window_weeks"),
            ({"event_gap_days": 0}, "event_gap_days"),
        ]
        for kwargs, message in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaisesRegex(ValueError, message):
                    CommodityAnalytics(df).detect_price_change_alerts("Tomato", **kwargs)

    def test_consecutive_alert_dates_share_event_id(self):
        dates = pd.date_range("2024-01-01", periods=90, freq="D")
        prices = [10.0 + 0.02 * i + 0.01 * (i % 4) for i in range(90)]
        prices = [price + (4.0 if i >= 45 else 0.0) for i, price in enumerate(prices)]
        df = pd.DataFrame({
            "date": dates, "commodity": "Tomato", "state_name": "Karnataka",
            "normalized_unit": "₹/kg", "retail_price_normalized": prices,
        })
        result = CommodityAnalytics(df).detect_price_change_alerts(
            "Tomato", min_pct_change=10.0, window_weeks=8
        )
        alert_dates = result.loc[result["is_alert"], ["date", "alert_event_id"]]
        self.assertFalse(alert_dates.empty)
        ids = alert_dates["alert_event_id"].dropna()
        self.assertTrue(ids.notna().all())
        adjacent = alert_dates.loc[
            alert_dates["date"].diff().dt.days.le(1).fillna(False)
        ]
        if len(adjacent) >= 2:
            self.assertEqual(adjacent.iloc[0]["alert_event_id"], adjacent.iloc[1]["alert_event_id"])

    def test_separated_step_changes_get_distinct_event_ids(self):
        dates = pd.date_range("2024-01-01", periods=150, freq="D")
        prices = [10.0] * 150
        for i in range(45, 95):
            prices[i] = 13.0
        for i in range(95, 150):
            prices[i] = 18.0
        df = make_price_frame(prices)
        df["date"] = dates
        result = CommodityAnalytics(df).detect_price_change_alerts(
            "Tomato", min_pct_change=10.0, window_weeks=8
        )
        first = result.loc[result["date"].between(dates[45], dates[51]) & result["is_alert"]]
        second = result.loc[result["date"].between(dates[95], dates[101]) & result["is_alert"]]
        self.assertFalse(first.empty)
        self.assertFalse(second.empty)
        self.assertNotEqual(first["alert_event_id"].iloc[0], second["alert_event_id"].iloc[0])
        self.assertTrue(result.loc[~result["is_alert"], "alert_event_id"].isna().all())

    def test_no_alerts_produce_missing_event_ids(self):
        dates = pd.date_range("2024-01-01", periods=90, freq="D")
        prices = [10.0 + 0.01 * i for i in range(90)]
        result = CommodityAnalytics(make_price_frame(prices)).detect_price_change_alerts(
            "Tomato", z_threshold=100.0, min_pct_change=10.0, window_weeks=8
        )
        self.assertFalse(result["is_alert"].any())
        self.assertTrue(result["alert_event_id"].isna().all())

    def test_event_gap_boundary_includes_exactly_three_days(self):
        # Successive alert dates at the configured maximum gap belong together.
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        alert_mask = pd.Series(False, index=dates)
        alert_mask.loc[dates[1]] = True
        alert_mask.loc[dates[4]] = True
        alert_mask.loc[dates[8]] = True
        from core.analytics import assign_alert_event_ids
        ids = assign_alert_event_ids(alert_mask, event_gap_days=3)
        self.assertEqual(ids.loc[dates[1]], ids.loc[dates[4]])
        self.assertNotEqual(ids.loc[dates[4]], ids.loc[dates[8]])
        self.assertTrue(ids.loc[~alert_mask].isna().all())

    def test_z_score_gate_includes_exact_threshold(self):
        dates = pd.date_range("2024-01-01", periods=120, freq="D")
        prices = [100.0 + 0.03 * i + 0.4 * np.sin(i * 0.29) for i in range(120)]
        prices = [price + (20.0 if i >= 105 else 0.0) for i, price in enumerate(prices)]
        frame = make_price_frame(prices)
        frame["date"] = dates
        initial = CommodityAnalytics(frame).detect_price_change_alerts(
            "Tomato", z_threshold=0.0, min_pct_change=0.0, window_weeks=10
        )
        target = initial.loc[initial["date"] == dates[105]].iloc[0]
        self.assertTrue(np.isfinite(target["z_score"]))
        exact = CommodityAnalytics(frame).detect_price_change_alerts(
            "Tomato", z_threshold=float(abs(target["z_score"])),
            min_pct_change=0.0, window_weeks=10
        )
        exact_target = exact.loc[exact["date"] == dates[105]].iloc[0]
        self.assertTrue(bool(exact_target["is_alert"]))

    def test_percentage_gate_includes_exact_ten_percent_decrease(self):
        dates = pd.date_range("2024-01-01", periods=80, freq="D")
        prices = [100.0] * 80
        # Make a non-zero baseline and an exact 10% decrease at the target date.
        for index in range(7, 70, 7):
            prices[index] = 100.0 + (index % 3) * 0.5
        prices[70] = 90.0
        frame = make_price_frame(prices)
        frame["date"] = dates
        result = CommodityAnalytics(frame).detect_price_change_alerts(
            "Tomato", z_threshold=0.0, min_pct_change=10.0, window_weeks=8
        )
        row = result.loc[result["date"] == dates[70]].iloc[0]
        self.assertAlmostEqual(row["price_change_pct_7d"], -10.0)
        self.assertTrue(bool(row["is_alert"]))

    def test_zero_variance_tolerance_boundary_is_explicit(self):
        dates = pd.date_range("2024-01-01", periods=50, freq="D")
        for log_delta, should_be_infinite in ((0.5e-12, False), (2.0e-12, True)):
            with self.subTest(log_delta=log_delta):
                prices = [100.0] * 50
                prices[42] = 100.0 * np.exp(log_delta)
                frame = make_price_frame(prices)
                frame["date"] = dates
                result = CommodityAnalytics(frame).detect_price_change_alerts(
                    "Tomato", z_threshold=0.0, min_pct_change=0.0, window_weeks=5
                )
                row = result.loc[result["date"] == dates[42]].iloc[0]
                self.assertEqual(bool(np.isinf(row["z_score"])), should_be_infinite)
                if not should_be_infinite:
                    self.assertEqual(float(row["z_score"]), 0.0)

    def test_isolated_outlier_heuristic_marks_an_observation(self):
        dates = pd.date_range("2024-01-01", periods=20, freq="D")
        prices = [10.0] * 20
        prices[10] = 20.0
        result = CommodityAnalytics(make_price_frame(prices)).detect_price_change_alerts(
            "Tomato", z_threshold=2.5, min_pct_change=10.0, window_weeks=5
        )
        row = result.loc[result["date"] == dates[10]].iloc[0]
        self.assertTrue(bool(row["is_isolated_price_outlier"]))

    def test_log_change_z_score_uses_log_metric(self):
        dates = pd.date_range("2024-01-01", periods=50, freq="D")
        prices = [100.0 + 0.5 * i + 2.0 * np.sin(i * 0.7) for i in range(50)]
        frame = make_price_frame(prices)
        frame["date"] = dates
        result = CommodityAnalytics(frame).detect_price_change_alerts(
            "Tomato", min_pct_change=0.0, window_weeks=5, z_threshold=0.0
        )
        self.assertIn("price_change_log_7d", result.columns)
        target_date = dates[35]
        row = result.loc[result["date"] == target_date].iloc[0]
        self.assertAlmostEqual(
            row["price_change_log_7d"],
            np.log(prices[35] / prices[28]),
        )


class OutputPathTests(unittest.TestCase):
    def test_report_names_are_unique_by_state_and_commodity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tomato = build_report_path(root, "Karnataka", "Tomato")
            onion = build_report_path(root, "Karnataka", "Onion")
            tamil_nadu = build_report_path(root, "Tamil Nadu", "Tomato")
            self.assertEqual(tomato.name, "karnataka_tomato_price_alert_report.md")
            self.assertEqual(onion.name, "karnataka_onion_price_alert_report.md")
            self.assertEqual(tamil_nadu.name, "tamil_nadu_tomato_price_alert_report.md")
            self.assertEqual(len({tomato, onion, tamil_nadu}), 3)


if __name__ == "__main__":
    unittest.main()
